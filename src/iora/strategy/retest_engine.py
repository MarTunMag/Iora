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
from iora.strategy.retest_sl_tp import compute_retest_sl, compute_retest_tp, compute_layered_sl, _LIMIT_BUFFER_ATR
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

    # Partial TP state
    partial: bool = False
    unit1_pct: float = 0.5
    unit1_tp: float = float('nan')   # Unit 1 TP price (fixed R:R)
    unit1_closed: bool = False       # Unit 1 has been locked
    original_sl: float = float('nan')  # SL before breakeven move

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

        risk_raw = abs(c.entry_price - (self.original_sl if self.partial else self.sl))
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
            sl_price=self.original_sl if self.partial else self.sl,
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

    def close_partial(
        self,
        exit_time: pd.Timestamp,
        reason: str,
    ) -> RetestTradeRecord:
        """Close a partial-TP trade with blended P&L.

        reason must be one of:
            "partial_full" — both Unit 1 TP and Unit 2 TP hit
            "partial_be"   — Unit 1 locked, Unit 2 hit breakeven SL
            "sl_hit"       — original SL hit before any partial lock
            "end_of_data"  — data ended (close at last bar close)
        """
        c = self.candidate
        ev = c.event
        direction = 1 if c.direction == "long" else -1
        risk_raw = abs(c.entry_price - self.original_sl)
        risk_pips = risk_raw / self.pip_size if self.pip_size > 0 else 0.0

        unit2_pct = 1.0 - self.unit1_pct

        if reason == "sl_hit":
            # Full loss on both units — SL hit before Unit 1 locked
            raw_pnl = (self.original_sl - c.entry_price) * direction
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = self.original_sl
        elif reason == "partial_full":
            # Both units hit their TPs
            u1_pnl = (self.unit1_tp - c.entry_price) * direction
            u2_pnl = (self.tp - c.entry_price) * direction
            raw_pnl = self.unit1_pct * u1_pnl + unit2_pct * u2_pnl
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = self.tp  # Report Unit 2 TP as exit price
        elif reason == "partial_be":
            # Unit 1 locked profit, Unit 2 at breakeven
            u1_pnl = (self.unit1_tp - c.entry_price) * direction
            raw_pnl = self.unit1_pct * u1_pnl  # Unit 2 = 0 (breakeven)
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = c.entry_price  # Breakeven
        else:
            # end_of_data or unknown — close at current levels
            # If unit1 was locked, compute blended; otherwise simple close
            if self.unit1_closed:
                u1_pnl = (self.unit1_tp - c.entry_price) * direction
                # Unit 2 still open — no specific exit price available
                raw_pnl = self.unit1_pct * u1_pnl  # Conservative: Unit 2 at BE
                pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
                exit_price = c.entry_price
            else:
                raw_pnl = 0.0
                pnl_pips = 0.0
                exit_price = c.entry_price

        reward_raw = abs(self.tp - c.entry_price)
        reward_pips = reward_raw / self.pip_size if self.pip_size > 0 else 0.0
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
            sl_price=self.original_sl,
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

    is_layered = config.entry_mode == "cascade_layered"
    max_open = config.max_concurrent if is_layered else 1

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
    open_trades: list[_OpenTrade] = []
    trade_counter = 0

    for idx, (ts, row) in enumerate(bar_data.iterrows()):
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])

        # --- Exit check (all open trades) ---
        still_open: list[_OpenTrade] = []
        for ot in open_trades:
            c = ot.candidate
            direction = 1 if c.direction == "long" else -1

            if ot.partial:
                # Partial TP exit logic: 2-unit tracking
                closed = _check_partial_exit(ot, bar_high, bar_low, ts, trades)
                if not closed:
                    still_open.append(ot)
            else:
                # Standard single-unit exit
                sl_hit = False
                tp_hit = False

                if direction == 1:  # LONG
                    if bar_low <= ot.sl:
                        sl_hit = True
                    elif bar_high >= ot.tp:
                        tp_hit = True
                else:  # SHORT
                    if bar_high >= ot.sl:
                        sl_hit = True
                    elif bar_low <= ot.tp:
                        tp_hit = True

                if sl_hit:
                    trades.append(ot.close_at(ot.sl, ts, "sl_hit"))
                elif tp_hit:
                    trades.append(ot.close_at(ot.tp, ts, "tp_hit"))
                else:
                    still_open.append(ot)
        open_trades = still_open

        # --- Entry check ---
        if len(open_trades) >= max_open or ts not in entry_map:
            continue

        candidate = entry_map[ts]
        zone_key = (candidate.zone_top, candidate.zone_bottom)

        # Apply first_touch policy
        if config.touch_policy == "first_touch" and zone_key in consumed_zones:
            continue

        if is_layered:
            # Cascade layered: place limit orders at each breaker zone
            before = len(open_trades)
            _enter_layered(
                candidate, config, symbol, bar_high, bar_low,
                open_trades, trades, pip_size, trade_counter, max_open,
            )
            trade_counter += len(open_trades) - before
        else:
            # Standard market or limit entry
            use_limit = config.entry_mode == "limit"
            if use_limit:
                limit_buf = _LIMIT_BUFFER_ATR * candidate.atr
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
                    opposing_zone_h1=candidate.opposing_zone_h1,
                    opposing_zone_h4=candidate.opposing_zone_h4,
                    opposing_zone_d1=candidate.opposing_zone_d1,
                    breaker_zones=candidate.breaker_zones,
                    d_to_w_relationship=candidate.d_to_w_relationship,
                    inside_w_zone=candidate.inside_w_zone,
                )

            # Compute SL
            sl = compute_retest_sl(
                candidate,
                mode=config.sl_mode,
                atr_mult=config.sl_atr_mult,
            )

            if config.partial_tp:
                # Partial TP: Unit 1 at fixed R:R, Unit 2 at HTF zone
                risk = abs(candidate.entry_price - sl)
                if candidate.direction == "long":
                    unit1_tp = candidate.entry_price + config.partial_unit1_rr * risk
                else:
                    unit1_tp = candidate.entry_price - config.partial_unit1_rr * risk

                # Unit 2 TP: HTF opposing zone
                tp = compute_retest_tp(
                    candidate,
                    sl_price=sl,
                    mode="htf_zone",
                    fixed_rr=config.partial_unit1_rr,
                    tp_htf=config.partial_unit2_tp,
                )

                trade_counter += 1
                trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"

                open_trades.append(_OpenTrade(
                    candidate=candidate,
                    sl=sl,
                    tp=tp,
                    trade_id=trade_id,
                    symbol=symbol,
                    pip_size=pip_size,
                    partial=True,
                    unit1_pct=config.partial_unit1_pct,
                    unit1_tp=unit1_tp,
                    unit1_closed=False,
                    original_sl=sl,
                ))
            else:
                tp = compute_retest_tp(
                    candidate,
                    sl_price=sl,
                    mode=config.tp_mode,
                    fixed_rr=config.fixed_rr,
                    tp_htf=config.tp_htf,
                )

                trade_counter += 1
                trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"

                open_trades.append(_OpenTrade(
                    candidate=candidate,
                    sl=sl,
                    tp=tp,
                    trade_id=trade_id,
                    symbol=symbol,
                    pip_size=pip_size,
                ))

        if config.touch_policy == "first_touch":
            consumed_zones.add(zone_key)

    # Close any remaining open trades at end of data
    if open_trades:
        last_ts = bar_data.index[-1]
        last_close = float(bar_data.iloc[-1]["close"])
        for ot in open_trades:
            if ot.partial:
                trades.append(ot.close_partial(last_ts, "end_of_data"))
            else:
                trades.append(ot.close_at(last_close, last_ts, "end_of_data"))

    return trades


def _check_partial_exit(
    ot: _OpenTrade,
    bar_high: float,
    bar_low: float,
    ts: pd.Timestamp,
    trades: list[RetestTradeRecord],
) -> bool:
    """Check partial TP exit conditions. Returns True if trade fully closed."""
    c = ot.candidate
    direction = 1 if c.direction == "long" else -1

    if not ot.unit1_closed:
        # Phase 1: Both units open, original SL active
        sl_hit = (bar_low <= ot.sl) if direction == 1 else (bar_high >= ot.sl)
        if sl_hit:
            trades.append(ot.close_partial(ts, "sl_hit"))
            return True

        # Check Unit 1 TP
        u1_hit = (bar_high >= ot.unit1_tp) if direction == 1 else (bar_low <= ot.unit1_tp)
        if u1_hit:
            ot.unit1_closed = True
            ot.sl = c.entry_price  # Move SL to breakeven

            # Also check if Unit 2 TP hit on the same bar
            u2_hit = (bar_high >= ot.tp) if direction == 1 else (bar_low <= ot.tp)
            if u2_hit:
                trades.append(ot.close_partial(ts, "partial_full"))
                return True
            return False  # Unit 1 locked, Unit 2 still running

        # Check if Unit 2 TP hit before Unit 1 (rare but possible)
        u2_hit = (bar_high >= ot.tp) if direction == 1 else (bar_low <= ot.tp)
        if u2_hit:
            # Both units close at their TPs (Unit 2 TP is further, implies Unit 1 also hit)
            ot.unit1_closed = True
            trades.append(ot.close_partial(ts, "partial_full"))
            return True

        return False

    else:
        # Phase 2: Unit 1 locked, Unit 2 running with breakeven SL
        be_hit = (bar_low <= ot.sl) if direction == 1 else (bar_high >= ot.sl)
        if be_hit:
            trades.append(ot.close_partial(ts, "partial_be"))
            return True

        u2_hit = (bar_high >= ot.tp) if direction == 1 else (bar_low <= ot.tp)
        if u2_hit:
            trades.append(ot.close_partial(ts, "partial_full"))
            return True

        return False


def _enter_layered(
    candidate: RetestCandidate,
    config: RetestConfig,
    symbol: str,
    bar_high: float,
    bar_low: float,
    open_trades: list[_OpenTrade],
    trades: list[RetestTradeRecord],
    pip_size: float,
    trade_counter_base: int,
    max_open: int,
) -> None:
    """Place layered limit orders at breaker zones inside the context zone.

    Each breaker zone generates an independent trade with its own entry/SL
    but shared TP logic (zone or fixed R:R from each layer's own risk).
    """
    if not candidate.breaker_zones:
        return

    limit_buf = _LIMIT_BUFFER_ATR * candidate.atr
    layer_num = 0

    for brk_top, brk_bottom, brk_tf in candidate.breaker_zones:
        if len(open_trades) >= max_open:
            break

        # Compute limit price at breaker zone edge
        if candidate.direction == "long":
            limit_price = brk_top + limit_buf
            filled = bar_low <= limit_price
        else:
            limit_price = brk_bottom - limit_buf
            filled = bar_high >= limit_price

        if not filled:
            continue

        layer_num += 1

        # Create a candidate copy with the limit entry price
        layer_candidate = RetestCandidate(
            event=candidate.event,
            zone_top=candidate.zone_top,
            zone_bottom=candidate.zone_bottom,
            entry_price=limit_price,
            atr=candidate.atr,
            period_hi=candidate.period_hi,
            period_lo=candidate.period_lo,
            ltf_choch_zone_boundary=candidate.ltf_choch_zone_boundary,
            next_opposing_zone_price=candidate.next_opposing_zone_price,
            opposing_zone_h1=candidate.opposing_zone_h1,
            opposing_zone_h4=candidate.opposing_zone_h4,
            opposing_zone_d1=candidate.opposing_zone_d1,
            breaker_zones=candidate.breaker_zones,
            d_to_w_relationship=candidate.d_to_w_relationship,
            inside_w_zone=candidate.inside_w_zone,
        )

        # Compute SL using layered mode
        sl = compute_layered_sl(
            direction=candidate.direction,
            brk_top=brk_top,
            brk_bottom=brk_bottom,
            ctx_zone_top=candidate.zone_top,
            ctx_zone_bottom=candidate.zone_bottom,
            atr=candidate.atr,
            mode=config.layered_sl_mode,
        )

        # TP: use standard TP computation (zone or fixed_rr from this layer's risk)
        tp = compute_retest_tp(
            layer_candidate,
            sl_price=sl,
            mode=config.tp_mode,
            fixed_rr=config.fixed_rr,
            tp_htf=config.tp_htf,
        )

        trade_id = f"{symbol}_{config.tf_pair}_{trade_counter_base + layer_num:04d}_L{layer_num}"

        open_trades.append(_OpenTrade(
            candidate=layer_candidate,
            sl=sl,
            tp=tp,
            trade_id=trade_id,
            symbol=symbol,
            pip_size=pip_size,
        ))


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
