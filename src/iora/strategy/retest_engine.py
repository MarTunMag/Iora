"""Retest trade simulation engine — Stage 2 of Level 4.

Filters candidates via the filter funnel, then simulates trades bar-by-bar
with SL/TP hit detection. Computes metrics via compute_metrics().
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.filter_funnel import FilterFunnel, apply_filters, apply_filters_with_cascade
from iora.strategy.retest_sl_tp import compute_retest_sl, compute_retest_tp
from iora.strategy.trade_converter import SweepTradeRecord, _get_pip_size
from iora.strategy.sweep_runner import compute_metrics


# ---------------------------------------------------------------------------
# RetestTradeRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RetestTradeRecord:
    """Trade record produced by the retest simulation engine."""

    # Core trade fields
    trade_id: str
    symbol: str
    direction: int          # 1=LONG, -1=SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    sl_price: float
    tp_price: float
    pnl_pips: float
    risk_pips: float
    reward_pips: float
    return_r: float
    rr_ratio: float
    exit_reason: str        # "sl_hit", "tp_hit", "end_of_data"

    # Retest context
    tf_pair: str
    touch_type: str
    zone_role: str
    bias_alignment: str
    age_bucket: str
    test_count_cls: str

    # Optional zone context (defaults for optional fields)
    zone_top: float = 0.0
    zone_bottom: float = 0.0
    bias_strength: int = 0
    replacement_count: int = 0
    birth_period_pattern: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pips > 0

    @property
    def holding_period(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time


# ---------------------------------------------------------------------------
# RetestResult
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RetestResult:
    """Result of evaluating one RetestConfig."""
    symbol: str
    config: RetestConfig
    trades: list[RetestTradeRecord] = field(default_factory=list)
    funnel: Optional[FilterFunnel] = None
    total_candidates: int = 0
    metrics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# _OpenTrade
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _OpenTrade:
    """Internal tracking of a live simulated trade."""
    candidate: RetestCandidate
    sl: float
    tp: float
    trade_id: str
    symbol: str
    pip_size: float

    def close_at(
        self,
        exit_price: float,
        exit_time: pd.Timestamp,
        reason: str,
    ) -> RetestTradeRecord:
        """Close this trade and produce a RetestTradeRecord."""
        c = self.candidate
        ev = c.event

        direction = 1 if c.direction == "long" else -1
        raw_pnl = (exit_price - c.entry_price) * direction
        pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0

        risk_raw = abs(c.entry_price - self.sl)
        tp_raw = abs(self.tp - c.entry_price)
        risk_pips = risk_raw / self.pip_size if self.pip_size > 0 else 0.0
        reward_pips = tp_raw / self.pip_size if self.pip_size > 0 else 0.0
        return_r = pnl_pips / risk_pips if risk_pips > 0 else 0.0
        rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0.0

        return RetestTradeRecord(
            trade_id=self.trade_id,
            symbol=self.symbol,
            direction=direction,
            entry_time=ev.timestamp,
            exit_time=exit_time,
            entry_price=c.entry_price,
            exit_price=exit_price,
            sl_price=self.sl,
            tp_price=self.tp,
            pnl_pips=pnl_pips,
            risk_pips=risk_pips,
            reward_pips=reward_pips,
            return_r=return_r,
            rr_ratio=rr_ratio,
            exit_reason=reason,
            tf_pair=ev.tf_pair,
            touch_type=ev.touch_type,
            zone_role=ev.zone_role,
            bias_alignment=ev.bias_alignment,
            age_bucket=ev.age_bucket,
            test_count_cls=ev.test_count_cls,
            zone_top=c.zone_top,
            zone_bottom=c.zone_bottom,
            bias_strength=ev.bias_strength,
            replacement_count=ev.replacement_count,
            birth_period_pattern=ev.birth_period_pattern,
        )


# ---------------------------------------------------------------------------
# evaluate_retest_config — main entry point
# ---------------------------------------------------------------------------

def evaluate_retest_config(
    candidates: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: Optional[pd.DataFrame] = None,
    pip_size: Optional[float] = None,
    all_candidates: Optional[list[RetestCandidate]] = None,
) -> RetestResult:
    """Filter candidates, simulate trades, return RetestResult.

    Args:
        candidates: All retest candidates (may span multiple tf_pairs).
        config: RetestConfig specifying filters, SL/TP, and simulation params.
        symbol: Trading symbol (used for pip size and trade IDs).
        bar_data: Optional OHLC DataFrame indexed by timestamp for simulation.
        pip_size: Override pip size (auto-detected from symbol if None).
        all_candidates: All candidates across all tf_pairs for cascade context.

    Returns:
        RetestResult with funnel, trades, and computed metrics.
    """
    # Filter to matching tf_pair first
    tf_filtered = [c for c in candidates if c.event.tf_pair == config.tf_pair]

    # Apply all filters (including cascade if configured)
    funnel = apply_filters_with_cascade(tf_filtered, config, all_candidates=all_candidates)
    passed = funnel.passed

    result = RetestResult(
        symbol=symbol,
        config=config,
        funnel=funnel,
        total_candidates=len(tf_filtered),
    )

    if not passed or bar_data is None or bar_data.empty:
        result.metrics = compute_metrics([])
        return result

    # Resolve pip size
    ps = pip_size if pip_size is not None else _get_pip_size(symbol)

    # Simulate trades bar by bar
    trades = _simulate_with_bars(passed, config, symbol, bar_data, ps)
    result.trades = trades

    # Compute metrics
    result.metrics = _compute_retest_metrics(trades, symbol)
    return result


# ---------------------------------------------------------------------------
# _simulate_with_bars
# ---------------------------------------------------------------------------

def _simulate_with_bars(
    passed: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: pd.DataFrame,
    pip_size: float,
) -> list[RetestTradeRecord]:
    """Bar-by-bar simulation: entries from candidate map, SL/TP exit checks."""

    # Build entry_map: timestamp → list of candidates at that bar
    # When multiple candidates share a timestamp, use the one with smallest
    # price_distance_at_touch (nearest to price).
    entry_map: dict[pd.Timestamp, RetestCandidate] = {}
    for c in passed:
        ts = c.event.timestamp
        if ts not in entry_map:
            entry_map[ts] = c
        else:
            existing = entry_map[ts]
            if c.event.price_distance_at_touch < existing.event.price_distance_at_touch:
                entry_map[ts] = c

    # Track consumed zones for first_touch policy
    # Key: (zone_top, zone_bottom) tuple
    consumed_zones: set[tuple[float, float]] = set()

    trades: list[RetestTradeRecord] = []
    open_trade: Optional[_OpenTrade] = None
    trade_counter = 0

    for idx, (ts, row) in enumerate(bar_data.iterrows()):
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])

        # --- Exit check (open trade first) ---
        if open_trade is not None:
            c = open_trade.candidate
            direction = 1 if c.direction == "long" else -1

            # Check SL and TP based on direction.
            # For longs: SL hit if low <= sl; TP hit if high >= tp
            # For shorts: SL hit if high >= sl; TP hit if low <= tp
            # SL takes priority if both hit in same bar.
            sl_hit = False
            tp_hit = False

            if direction == 1:  # LONG
                if bar_low <= open_trade.sl:
                    sl_hit = True
                elif bar_high >= open_trade.tp:
                    tp_hit = True
            else:  # SHORT
                if bar_high >= open_trade.sl:
                    sl_hit = True
                elif bar_low <= open_trade.tp:
                    tp_hit = True

            if sl_hit:
                trades.append(open_trade.close_at(open_trade.sl, ts, "sl_hit"))
                open_trade = None
            elif tp_hit:
                trades.append(open_trade.close_at(open_trade.tp, ts, "tp_hit"))
                open_trade = None

        # --- Entry check ---
        if open_trade is None and ts in entry_map:
            candidate = entry_map[ts]
            zone_key = (candidate.zone_top, candidate.zone_bottom)

            # Apply first_touch policy
            if config.touch_policy == "first_touch" and zone_key in consumed_zones:
                pass  # Skip this entry
            else:
                # Determine entry price based on entry_mode
                use_limit = config.entry_mode == "limit"
                if use_limit:
                    limit_buf = 0.1 * candidate.atr
                    if candidate.direction == "long":
                        limit_price = candidate.zone_bottom + limit_buf
                        filled = bar_low <= limit_price
                    else:
                        limit_price = candidate.zone_top - limit_buf
                        filled = bar_high >= limit_price

                    if not filled:
                        continue  # Limit order not reached — no entry

                    # Override entry price on candidate for SL/TP computation
                    candidate = RetestCandidate(
                        event=candidate.event,
                        zone_top=candidate.zone_top,
                        zone_bottom=candidate.zone_bottom,
                        entry_price=limit_price,
                        atr=candidate.atr,
                        period_hi=candidate.period_hi,
                        period_lo=candidate.period_lo,
                        ltf_choch_zone_boundary=candidate.ltf_choch_zone_boundary,
                        next_opposing_zone_price=candidate.next_opposing_zone_price,
                        d_to_w_relationship=candidate.d_to_w_relationship,
                        inside_w_zone=candidate.inside_w_zone,
                    )

                # Compute SL and TP
                sl = compute_retest_sl(
                    candidate,
                    mode=config.sl_mode,
                    atr_mult=config.sl_atr_mult,
                )
                tp = compute_retest_tp(
                    candidate,
                    sl_price=sl,
                    mode=config.tp_mode,
                    fixed_rr=config.fixed_rr,
                )

                trade_counter += 1
                trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"

                open_trade = _OpenTrade(
                    candidate=candidate,
                    sl=sl,
                    tp=tp,
                    trade_id=trade_id,
                    symbol=symbol,
                    pip_size=pip_size,
                )

                if config.touch_policy == "first_touch":
                    consumed_zones.add(zone_key)

    # Close any remaining open trade at end of data
    if open_trade is not None:
        last_ts = bar_data.index[-1]
        last_close = float(bar_data.iloc[-1]["close"])
        trades.append(open_trade.close_at(last_close, last_ts, "end_of_data"))

    return trades


# ---------------------------------------------------------------------------
# _adapt_to_sweep_records — bridge to compute_metrics
# ---------------------------------------------------------------------------

def _adapt_to_sweep_records(
    trades: list[RetestTradeRecord],
    symbol: str,
) -> list[SweepTradeRecord]:
    """Map RetestTradeRecord → SweepTradeRecord for compute_metrics()."""
    records: list[SweepTradeRecord] = []
    for t in trades:
        # Map touch_type → signal_type (retest context → push-zone convention)
        signal_type = t.touch_type  # e.g. "wick_touch", "body_close"
        # Extract zone_tf from tf_pair (entry@zone → zone part)
        zone_tf = t.tf_pair.split("@")[1] if "@" in t.tf_pair else t.tf_pair

        records.append(SweepTradeRecord(
            trade_id=t.trade_id,
            symbol=symbol,
            direction=t.direction,
            entry_time=t.entry_time,
            exit_time=t.exit_time,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            pnl_pips=t.pnl_pips,
            risk_pips=t.risk_pips,
            reward_pips=t.reward_pips,
            return_r=t.return_r,
            rr_ratio=t.rr_ratio,
            exit_reason=t.exit_reason,
            sl_price=t.sl_price,
            tp_price=t.tp_price,
            signal_type=signal_type,
            struct_cls="",
            zone_tf=zone_tf,
            zone_top=t.zone_top,
            zone_bottom=t.zone_bottom,
        ))
    return records


# ---------------------------------------------------------------------------
# _compute_retest_metrics
# ---------------------------------------------------------------------------

def _compute_retest_metrics(
    trades: list[RetestTradeRecord],
    symbol: str,
) -> dict:
    """Compute metrics from retest trades via the sweep_runner compute_metrics."""
    sweep_records = _adapt_to_sweep_records(trades, symbol)
    return compute_metrics(sweep_records)
