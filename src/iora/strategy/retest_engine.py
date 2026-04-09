"""Retest trade simulation engine — Stage 2 of Level 4.

Filters candidates via the filter funnel, then simulates trades bar-by-bar
with SL/TP hit detection. Computes metrics via compute_metrics().
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from iora.indicators.heikin_ashi import calculate_heikin_ashi
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate, ZoneBirthEvent
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
class _PendingLimit:
    """Unfilled limit order waiting to be triggered on subsequent bars."""
    candidate: RetestCandidate
    limit_price: float
    placed_bar_idx: int
    zone_key: tuple[float, float]


@dataclass(slots=True)
class _ActiveTrigger:
    """H4 zone triggered by an H1 retest — tracks dynamic nesting window."""
    h4_zone_top: float
    h4_zone_bottom: float
    h4_zone_side: str
    trigger_bar_idx: int
    window_bars: int
    candidate: RetestCandidate
    fills: int = 0
    max_fills: int = 3


@dataclass(slots=True)
class _OpenTrade:
    """Internal tracking of a live simulated trade."""
    candidate: RetestCandidate
    sl: float
    tp: float
    trade_id: str
    symbol: str
    pip_size: float

    # Spread-adjusted entry (for P&L calculation)
    effective_entry: float = float('nan')  # Entry + spread cost (nan = same as candidate entry)

    # Partial TP state
    partial: bool = False
    unit1_pct: float = 0.5
    unit1_tp: float = float('nan')   # Unit 1 TP price (fixed R:R)
    unit1_closed: bool = False       # Unit 1 has been locked
    original_sl: float = float('nan')  # SL before breakeven move
    breakeven_sl: float = float('nan')  # BE level after Unit 1 TP (entry + buffer)

    @property
    def _entry_for_pnl(self) -> float:
        """Entry price for P&L: effective_entry if spread applied, else candidate entry."""
        return self.effective_entry if not math.isnan(self.effective_entry) else self.candidate.entry_price

    def close_at(
        self,
        exit_price: float,
        exit_time: pd.Timestamp,
        reason: str,
    ) -> RetestTradeRecord:
        """Close this trade and produce a RetestTradeRecord."""
        c = self.candidate
        ev = c.event
        entry = self._entry_for_pnl

        direction = 1 if c.direction == "long" else -1
        raw_pnl = (exit_price - entry) * direction
        pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0

        sl_ref = self.original_sl if self.partial else self.sl
        # For signal-flip trades with no real SL, use zone width as risk reference
        if abs(sl_ref) > 1e6 or sl_ref == 0.0:
            risk_raw = abs(c.zone_top - c.zone_bottom)
        else:
            risk_raw = abs(entry - sl_ref)
        tp_ref = self.tp
        if abs(tp_ref) > 1e6 or tp_ref == 0.0:
            tp_raw = abs(raw_pnl)  # Actual P&L as reward
        else:
            tp_raw = abs(tp_ref - entry)
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
            entry_price=entry,
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
        entry = self._entry_for_pnl
        direction = 1 if c.direction == "long" else -1
        risk_raw = abs(entry - self.original_sl)
        risk_pips = risk_raw / self.pip_size if self.pip_size > 0 else 0.0

        unit2_pct = 1.0 - self.unit1_pct

        if reason == "sl_hit":
            # Full loss on both units — SL hit before Unit 1 locked
            raw_pnl = (self.original_sl - entry) * direction
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = self.original_sl
        elif reason == "partial_full":
            # Both units hit their TPs
            u1_pnl = (self.unit1_tp - entry) * direction
            u2_pnl = (self.tp - entry) * direction
            raw_pnl = self.unit1_pct * u1_pnl + unit2_pct * u2_pnl
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = self.tp  # Report Unit 2 TP as exit price
        elif reason == "partial_be":
            # Unit 1 locked profit, Unit 2 at breakeven SL (may include buffer)
            u1_pnl = (self.unit1_tp - entry) * direction
            u2_pnl = (self.breakeven_sl - entry) * direction  # 0 if no buffer
            raw_pnl = self.unit1_pct * u1_pnl + unit2_pct * u2_pnl
            pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
            exit_price = self.breakeven_sl
        else:
            # end_of_data or unknown — close at current levels
            # If unit1 was locked, compute blended; otherwise simple close
            if self.unit1_closed:
                u1_pnl = (self.unit1_tp - entry) * direction
                # Unit 2 still open — no specific exit price available
                raw_pnl = self.unit1_pct * u1_pnl  # Conservative: Unit 2 at BE
                pnl_pips = raw_pnl / self.pip_size if self.pip_size > 0 else 0.0
                exit_price = entry
            else:
                raw_pnl = 0.0
                pnl_pips = 0.0
                exit_price = entry

        reward_raw = abs(self.tp - entry)
        reward_pips = reward_raw / self.pip_size if self.pip_size > 0 else 0.0
        return_r = pnl_pips / risk_pips if risk_pips > 0 else 0.0
        rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0.0

        return RetestTradeRecord(
            trade_id=self.trade_id,
            symbol=self.symbol,
            direction=direction,
            entry_time=ev.timestamp,
            exit_time=exit_time,
            entry_price=entry,
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

def prepare_ha_trail_data(
    entry_tf_data: pd.DataFrame,
    trail_tf_data: pd.DataFrame,
) -> pd.Series:
    """Compute HA low/high on trail TF and forward-fill onto entry TF index.

    Returns a DataFrame with 'ha_trail_low' and 'ha_trail_high' columns
    aligned to the entry TF index.
    """
    ha = calculate_heikin_ashi(trail_tf_data)
    # Forward-fill trail TF HA values onto entry TF timestamps
    trail = pd.DataFrame({
        "ha_trail_low": ha["low"],
        "ha_trail_high": ha["high"],
    }, index=ha.index)
    # merge_asof: for each entry bar, find the most recent trail bar
    aligned = pd.merge_asof(
        entry_tf_data[["open"]],  # Left side: entry TF index
        trail,
        left_index=True, right_index=True,
        direction="backward",
    )
    return aligned[["ha_trail_low", "ha_trail_high"]]


def evaluate_retest_config(
    candidates: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: Optional[pd.DataFrame] = None,
    pip_size: Optional[float] = None,
    all_candidates: Optional[list[RetestCandidate]] = None,
    trail_tf_data: Optional[pd.DataFrame] = None,
    zone_births: Optional[dict] = None,
    cascade_timeline: Optional[dict] = None,
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

    # Prepare HA trail data if needed
    ha_trail: Optional[pd.DataFrame] = None
    if config.unit2_trail != "none" and trail_tf_data is not None:
        ha_trail = prepare_ha_trail_data(bar_data, trail_tf_data)

    # Simulate trades bar by bar
    trades = _simulate_with_bars(passed, config, symbol, bar_data, ps, ha_trail,
                                  zone_births=zone_births,
                                  cascade_timeline=cascade_timeline)
    result.trades = trades

    # Compute metrics
    result.metrics = _compute_retest_metrics(trades, symbol, spread_pips=config.spread_pips)
    return result


# ---------------------------------------------------------------------------
# Signal-flip helpers
# ---------------------------------------------------------------------------

def _make_flip_candidate(
    birth: ZoneBirthEvent,
    config: RetestConfig,
    prev_candidate: RetestCandidate,
) -> RetestCandidate:
    """Create a synthetic RetestCandidate from a zone birth event for a flipped trade."""
    direction = "long" if birth.zone_side == "demand" else "short"
    entry_price = birth.zone_top if direction == "short" else birth.zone_bottom

    # Synthetic OpportunityEvent with placeholder fields
    synth_event = OpportunityEvent(
        timestamp=birth.timestamp,
        zone_tf=birth.zone_tf,
        entry_tf=config.entry_tf,
        tf_pair=config.tf_pair,
        touch_type="signal_flip",
        zone_side=birth.zone_side,
        zone_role="signal_flip",
        age_bucket="fresh",
        bias_alignment="signal_flip",
        test_count_cls="0",
        zone_age_bars=0,
        zone_test_count=0,
        bias_strength=0,
        price_distance_at_touch=0.0,
        replacement_count=0,
        birth_period_pattern="signal_flip",
    )

    return RetestCandidate(
        event=synth_event,
        zone_top=birth.zone_top,
        zone_bottom=birth.zone_bottom,
        entry_price=entry_price,
        atr=prev_candidate.atr,
        period_hi=prev_candidate.period_hi,
        period_lo=prev_candidate.period_lo,
    )


def _is_window_active(
    config: RetestConfig,
    cascade_timeline: Optional[dict],
    ts: 'pd.Timestamp',
) -> bool:
    """Evaluate whether the structural window is active at this bar.

    Uses cascade_phase_filter, tl_break_filter from config to determine
    whether the system should be flipping or flat.
    """
    if config.flip_window != "windowed" or cascade_timeline is None:
        return True  # Always active

    snap = cascade_timeline.get(ts)
    if snap is None:
        return False  # No cascade data = inactive

    # Check cascade_phase_filter
    if config.cascade_phase_filter != "any":
        if config.cascade_phase_filter == "h4_correction":
            if snap.phase != "h4_correction":
                return False
        elif config.cascade_phase_filter == "d1_push":
            if snap.phase != "d1_push":
                return False
        elif config.cascade_phase_filter == "h4_correction_tl_break":
            if snap.phase != "h4_correction" or snap.h4_correction_tl_intact:
                return False

    # Check tl_break_filter
    if config.tl_break_filter != "any":
        if config.tl_break_filter == "after_correction_break":
            # M15 or H4 correction TL must have broken recently
            m15_broke = 0 <= snap.m15_correction_bars_since_break <= (config.tl_break_lookback or 999)
            h4_broke = not snap.h4_correction_tl_intact
            if not (m15_broke or h4_broke):
                return False
        elif config.tl_break_filter == "after_impulse_break":
            m15_broke = 0 <= snap.m15_impulse_bars_since_break <= (config.tl_break_lookback or 999)
            h4_broke = not snap.h4_impulse_tl_intact
            if not (m15_broke or h4_broke):
                return False

    # --- Layer 2.5: HTF level break context ---
    if config.htf_level_break_context != "any":
        lookback = config.htf_break_lookback
        brk_map = {
            "after_dy_lo_x": snap.d1_lo_brk_time,
            "after_dy_hi_x": snap.d1_hi_brk_time,
            "after_h4_lo_x": snap.h4_lo_brk_time,
            "after_h4_hi_x": snap.h4_hi_brk_time,
            "after_h1_lo_x": snap.h1_lo_brk_time,
            "after_h1_hi_x": snap.h1_hi_brk_time,
        }
        brk_time = brk_map.get(config.htf_level_break_context)
        if brk_time is None:
            return False  # No break occurred this period
        # If lookback > 0, check recency (rough: compare timestamps)
        if lookback > 0 and brk_time is not None:
            # brk_time exists means break happened this period — always pass
            # (lookback in bars would need bar counting; for now period-level is sufficient)
            pass

    # --- Layer 2.5: M15 trendline state ---
    if config.m15_tl_state != "any":
        if config.m15_tl_state == "after_correction_break":
            if snap.m15_correction_tl_intact:
                return False  # M15 correction TL still intact
        elif config.m15_tl_state == "impulse_intact":
            if not snap.m15_impulse_tl_intact:
                return False  # M15 impulse TL broken

    return True


# ---------------------------------------------------------------------------
# _simulate_with_bars
# ---------------------------------------------------------------------------

def _simulate_with_bars(
    passed: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: pd.DataFrame,
    pip_size: float,
    ha_trail: Optional[pd.DataFrame] = None,
    zone_births: Optional[dict[pd.Timestamp, list[ZoneBirthEvent]]] = None,
    cascade_timeline: Optional[dict] = None,
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
    pending_limits: list[_PendingLimit] = []
    active_triggers: list[_ActiveTrigger] = []
    trade_counter = 0

    is_signal_flip = config.exit_mode in ("signal_flip", "signal_flip_with_safety")
    has_safety_sl = config.exit_mode == "signal_flip_with_safety"
    is_windowed = config.flip_window == "windowed" and is_signal_flip

    use_limit = config.entry_mode == "limit"
    carry_limits = use_limit and config.limit_ttl != 1

    for idx, (ts, row) in enumerate(bar_data.iterrows()):
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])
        bar_close = float(row["close"])

        # --- Exit check (all open trades) ---
        still_open: list[_OpenTrade] = []

        if is_signal_flip and open_trades:
            # Signal-flip exit: check for opposite-direction zone fire on entry TF
            births_at_bar = zone_births.get(ts, []) if zone_births else []
            entry_tf = config.entry_tf
            window_active = _is_window_active(config, cascade_timeline, ts)

            for ot in open_trades:
                c = ot.candidate
                flipped = False

                for birth in births_at_bar:
                    if birth.zone_tf != entry_tf:
                        continue
                    # Check if this birth is opposite to current trade direction
                    opposite = (
                        (c.direction == "long" and birth.zone_side == "supply")
                        or (c.direction == "short" and birth.zone_side == "demand")
                    )
                    if not opposite:
                        continue

                    # Close current trade at the new zone's edge
                    exit_price = birth.zone_bottom if birth.zone_side == "supply" else birth.zone_top

                    if is_windowed and not window_active:
                        # Window inactive — close and go flat (don't re-open)
                        trades.append(ot.close_at(exit_price, ts, "window_close"))
                        flipped = True  # Mark as handled (position closed)
                        open_trades_new = []  # Go flat
                        break

                    trades.append(ot.close_at(exit_price, ts, "signal_flip"))

                    # Open flipped trade in opposite direction
                    flip_candidate = _make_flip_candidate(birth, config, c)
                    new_dir = "short" if birth.zone_side == "supply" else "long"
                    eff_entry = _compute_effective_entry(
                        flip_candidate.entry_price, new_dir,
                        config.spread_pips, pip_size,
                    )

                    # Safety SL = zone far boundary (structural invalidation)
                    if has_safety_sl:
                        if new_dir == "long":
                            safety_sl = birth.zone_bottom - config.sl_buffer_atr * flip_candidate.atr
                        else:
                            safety_sl = birth.zone_top + config.sl_buffer_atr * flip_candidate.atr
                    else:
                        # No SL — use extreme values so it never triggers
                        safety_sl = 0.0 if new_dir == "long" else 1e9

                    trade_counter += 1
                    trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"
                    open_trades_new = [_OpenTrade(
                        candidate=flip_candidate,
                        sl=safety_sl,
                        tp=1e9 if new_dir == "long" else 0.0,  # No fixed TP
                        trade_id=trade_id,
                        symbol=symbol,
                        pip_size=pip_size,
                        effective_entry=eff_entry,
                    )]
                    flipped = True
                    break

                if flipped:
                    # Replace open_trades with the new flipped trade (or empty if window closed)
                    still_open = open_trades_new
                    break
                else:
                    # Safety SL check (only for signal_flip_with_safety)
                    if has_safety_sl:
                        direction = 1 if c.direction == "long" else -1
                        sl_hit = (bar_low <= ot.sl) if direction == 1 else (bar_high >= ot.sl)
                        if sl_hit:
                            trades.append(ot.close_at(ot.sl, ts, "safety_sl_hit"))
                        else:
                            still_open.append(ot)
                    else:
                        still_open.append(ot)
        else:
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

        # --- HA trail SL update (tighten only, never widen) ---
        if ha_trail is not None and config.unit2_trail != "none":
            for ot in open_trades:
                if ot.partial and ot.unit1_closed:
                    c = ot.candidate
                    if ts in ha_trail.index:
                        ha_row = ha_trail.loc[ts]
                    else:
                        continue
                    if c.direction == "long":
                        trail_level = float(ha_row["ha_trail_low"])
                        if not math.isnan(trail_level):
                            ot.sl = max(ot.sl, trail_level)
                    else:
                        trail_level = float(ha_row["ha_trail_high"])
                        if not math.isnan(trail_level):
                            ot.sl = min(ot.sl, trail_level)

        # --- Pending limit fill check (before new entries) ---
        if carry_limits and pending_limits and len(open_trades) < max_open:
            surviving: list[_PendingLimit] = []
            filled_one = False
            for pl in pending_limits:
                if filled_one:
                    surviving.append(pl)
                    continue

                bars_pending = idx - pl.placed_bar_idx

                # TTL expiry: 0 = until zone breaks (no bar limit)
                if config.limit_ttl > 0 and bars_pending > config.limit_ttl:
                    continue  # Expired — drop

                # Zone break cancellation (body-close through boundary)
                if pl.candidate.direction == "long" and bar_close < pl.candidate.zone_bottom:
                    continue  # Zone broken
                if pl.candidate.direction == "short" and bar_close > pl.candidate.zone_top:
                    continue  # Zone broken

                # Check fill
                if pl.candidate.direction == "long" and bar_low <= pl.limit_price:
                    _enter_from_pending(
                        pl, config, symbol, pip_size, ts,
                        open_trades, trade_counter,
                    )
                    trade_counter += 1
                    filled_one = True
                    if config.touch_policy == "first_touch":
                        consumed_zones.add(pl.zone_key)
                    continue  # Don't re-add to surviving

                if pl.candidate.direction == "short" and bar_high >= pl.limit_price:
                    _enter_from_pending(
                        pl, config, symbol, pip_size, ts,
                        open_trades, trade_counter,
                    )
                    trade_counter += 1
                    filled_one = True
                    if config.touch_policy == "first_touch":
                        consumed_zones.add(pl.zone_key)
                    continue

                surviving.append(pl)
            pending_limits = surviving

        # === HTF-triggered LTF nesting: dynamic mode ===
        if config.ltf_nesting == "dynamic":
            # 1. Register new triggers from entry_map
            if ts in entry_map:
                c = entry_map[ts]
                zone_key_dyn = (c.zone_top, c.zone_bottom)
                already_triggered = any(
                    t.h4_zone_top == c.zone_top and t.h4_zone_bottom == c.zone_bottom
                    for t in active_triggers
                )
                if not already_triggered:
                    active_triggers.append(_ActiveTrigger(
                        h4_zone_top=c.zone_top,
                        h4_zone_bottom=c.zone_bottom,
                        h4_zone_side=c.event.zone_side,
                        trigger_bar_idx=idx,
                        window_bars=config.trigger_window_bars,
                        candidate=c,
                        max_fills=config.max_ltf_per_trigger,
                    ))

            # 2. Process active triggers
            surviving_triggers: list[_ActiveTrigger] = []
            for trig in active_triggers:
                bars_elapsed = idx - trig.trigger_bar_idx
                # Window expiry
                if bars_elapsed > trig.window_bars:
                    continue
                # H4 zone break (body-close)
                if trig.h4_zone_side == "demand" and bar_close < trig.h4_zone_bottom:
                    continue
                if trig.h4_zone_side == "supply" and bar_close > trig.h4_zone_top:
                    continue

                # 3. Check for zone births inside this trigger's H4 zone
                if zone_births and ts in zone_births:
                    ltf_tf = config.entry_tf_override or config.entry_tf
                    for birth in zone_births[ts]:
                        if trig.fills >= trig.max_fills:
                            break
                        if birth.zone_tf != ltf_tf:
                            continue
                        if birth.zone_side != trig.h4_zone_side:
                            continue
                        # Geometric containment
                        if birth.zone_top > trig.h4_zone_top or birth.zone_bottom < trig.h4_zone_bottom:
                            continue
                        if config.require_ltf_push and not birth.is_push:
                            continue

                        # Place pending limit at LTF zone edge
                        limit_buf = _LIMIT_BUFFER_ATR * trig.candidate.atr
                        if trig.h4_zone_side == "demand":
                            limit_price = birth.zone_top - limit_buf
                        else:
                            limit_price = birth.zone_bottom + limit_buf

                        ltf_candidate = RetestCandidate(
                            event=trig.candidate.event,
                            zone_top=birth.zone_top,
                            zone_bottom=birth.zone_bottom,
                            entry_price=limit_price,
                            atr=trig.candidate.atr,
                            period_hi=trig.candidate.period_hi,
                            period_lo=trig.candidate.period_lo,
                            ltf_choch_zone_boundary=trig.candidate.ltf_choch_zone_boundary,
                            next_opposing_zone_price=trig.candidate.next_opposing_zone_price,
                            d1_range_midpoint=trig.candidate.d1_range_midpoint,
                            opposing_zone_h1=trig.candidate.opposing_zone_h1,
                            opposing_zone_h4=trig.candidate.opposing_zone_h4,
                            opposing_zone_d1=trig.candidate.opposing_zone_d1,
                            breaker_zones=trig.candidate.breaker_zones,
                            hma_direction_h1=trig.candidate.hma_direction_h1,
                            hma_direction_h4=trig.candidate.hma_direction_h4,
                            ha_above_hma_h1=trig.candidate.ha_above_hma_h1,
                            ha_above_hma_h4=trig.candidate.ha_above_hma_h4,
                            bars_since_hma_cross_h1=trig.candidate.bars_since_hma_cross_h1,
                            bars_since_hma_cross_h4=trig.candidate.bars_since_hma_cross_h4,
                            hma_cross_direction_h1=trig.candidate.hma_cross_direction_h1,
                            hma_cross_direction_h4=trig.candidate.hma_cross_direction_h4,
                            d_to_w_relationship=trig.candidate.d_to_w_relationship,
                            inside_w_zone=trig.candidate.inside_w_zone,
                        )

                        ltf_zone_key = (birth.zone_top, birth.zone_bottom)
                        if not any(p.zone_key == ltf_zone_key for p in pending_limits):
                            # Check immediate fill
                            filled = False
                            if trig.h4_zone_side == "demand" and bar_low <= limit_price:
                                filled = True
                            elif trig.h4_zone_side == "supply" and bar_high >= limit_price:
                                filled = True

                            if filled and len(open_trades) < max_open:
                                _enter_ltf_trade(
                                    ltf_candidate, config, symbol, pip_size,
                                    open_trades, trade_counter,
                                )
                                trade_counter += 1
                                trig.fills += 1
                            elif carry_limits:
                                pending_limits.append(_PendingLimit(
                                    candidate=ltf_candidate,
                                    limit_price=limit_price,
                                    placed_bar_idx=idx,
                                    zone_key=ltf_zone_key,
                                ))
                                trig.fills += 1

                surviving_triggers.append(trig)
            active_triggers = surviving_triggers

            # For dynamic mode, skip standard entry (unless trigger_also_trades)
            if not config.trigger_also_trades:
                continue

        # --- Windowed re-entry from zone births (when flat during active window) ---
        if is_signal_flip and is_windowed and not open_trades:
            window_active = _is_window_active(config, cascade_timeline, ts)
            if window_active:
                births_at_bar = zone_births.get(ts, []) if zone_births else []
                entry_tf = config.entry_tf
                for birth in births_at_bar:
                    if birth.zone_tf != entry_tf:
                        continue
                    # Enter on any zone birth when window is active and flat
                    flip_candidate = _make_flip_candidate(birth, config,
                        passed[0] if passed else None)
                    if flip_candidate is None:
                        continue
                    new_dir = "short" if birth.zone_side == "supply" else "long"
                    eff_entry = _compute_effective_entry(
                        flip_candidate.entry_price, new_dir,
                        config.spread_pips, pip_size,
                    )
                    if has_safety_sl:
                        if new_dir == "long":
                            safety_sl = birth.zone_bottom - config.sl_buffer_atr * flip_candidate.atr
                        else:
                            safety_sl = birth.zone_top + config.sl_buffer_atr * flip_candidate.atr
                    else:
                        safety_sl = 0.0 if new_dir == "long" else 1e9

                    trade_counter += 1
                    trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"
                    open_trades.append(_OpenTrade(
                        candidate=flip_candidate,
                        sl=safety_sl,
                        tp=1e9 if new_dir == "long" else 0.0,
                        trade_id=trade_id,
                        symbol=symbol,
                        pip_size=pip_size,
                        effective_entry=eff_entry,
                    ))
                    break  # Only one entry per bar

        # --- Entry check ---
        if len(open_trades) >= max_open or ts not in entry_map:
            continue

        candidate = entry_map[ts]
        zone_key = (candidate.zone_top, candidate.zone_bottom)

        # Apply first_touch policy
        if config.touch_policy == "first_touch" and zone_key in consumed_zones:
            continue

        # === HTF-triggered LTF nesting: static mode ===
        if config.ltf_nesting == "static":
            if not candidate.nested_ltf_zones:
                # No nested zones — skip this candidate entirely
                continue
            ltf_count = 0
            override_tf = config.entry_tf_override or ""
            for ltf_top, ltf_bot, ltf_tf, ltf_side, ltf_is_push in candidate.nested_ltf_zones:
                if ltf_count >= config.max_ltf_per_trigger:
                    break
                # Filter by configured LTF override
                if override_tf and ltf_tf != override_tf:
                    continue
                # Filter by push requirement
                if config.require_ltf_push and not ltf_is_push:
                    continue
                ltf_zone_key = (ltf_top, ltf_bot)
                if config.touch_policy == "first_touch" and ltf_zone_key in consumed_zones:
                    continue
                if any(p.zone_key == ltf_zone_key for p in pending_limits):
                    continue

                limit_buf = _LIMIT_BUFFER_ATR * candidate.atr
                if candidate.direction == "long":
                    limit_price = ltf_top - limit_buf
                else:
                    limit_price = ltf_bot + limit_buf

                # Create modified candidate with LTF zone boundaries
                ltf_candidate = RetestCandidate(
                    event=candidate.event,
                    zone_top=ltf_top,
                    zone_bottom=ltf_bot,
                    entry_price=limit_price,
                    atr=candidate.atr,
                    period_hi=candidate.period_hi,
                    period_lo=candidate.period_lo,
                    ltf_choch_zone_boundary=candidate.ltf_choch_zone_boundary,
                    next_opposing_zone_price=candidate.next_opposing_zone_price,
                    d1_range_midpoint=candidate.d1_range_midpoint,
                    opposing_zone_h1=candidate.opposing_zone_h1,
                    opposing_zone_h4=candidate.opposing_zone_h4,
                    opposing_zone_d1=candidate.opposing_zone_d1,
                    breaker_zones=candidate.breaker_zones,
                    hma_direction_h1=candidate.hma_direction_h1,
                    hma_direction_h4=candidate.hma_direction_h4,
                    ha_above_hma_h1=candidate.ha_above_hma_h1,
                    ha_above_hma_h4=candidate.ha_above_hma_h4,
                    bars_since_hma_cross_h1=candidate.bars_since_hma_cross_h1,
                    bars_since_hma_cross_h4=candidate.bars_since_hma_cross_h4,
                    hma_cross_direction_h1=candidate.hma_cross_direction_h1,
                    hma_cross_direction_h4=candidate.hma_cross_direction_h4,
                    d_to_w_relationship=candidate.d_to_w_relationship,
                    inside_w_zone=candidate.inside_w_zone,
                )

                # Check immediate fill
                filled = False
                if candidate.direction == "long" and bar_low <= limit_price:
                    filled = True
                elif candidate.direction == "short" and bar_high >= limit_price:
                    filled = True

                if filled and len(open_trades) < max_open:
                    _enter_ltf_trade(
                        ltf_candidate, config, symbol, pip_size,
                        open_trades, trade_counter,
                    )
                    trade_counter += 1
                    ltf_count += 1
                    if config.touch_policy == "first_touch":
                        consumed_zones.add(ltf_zone_key)
                elif carry_limits:
                    pending_limits.append(_PendingLimit(
                        candidate=ltf_candidate,
                        limit_price=limit_price,
                        placed_bar_idx=idx,
                        zone_key=ltf_zone_key,
                    ))
                    ltf_count += 1

            # Optionally also trade the H1@H4 directly
            if not config.trigger_also_trades:
                if config.touch_policy == "first_touch":
                    consumed_zones.add(zone_key)
                continue  # Skip standard entry — nested zones handle it

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
            if use_limit:
                limit_buf = _LIMIT_BUFFER_ATR * candidate.atr
                if config.limit_edge == "top":
                    # Entry near zone top (where price first enters zone)
                    if candidate.direction == "long":
                        limit_price = candidate.zone_top - limit_buf
                        filled = bar_low <= limit_price
                    else:
                        limit_price = candidate.zone_bottom + limit_buf
                        filled = bar_high >= limit_price
                else:
                    # Default "bottom": deepest entry near zone boundary
                    if candidate.direction == "long":
                        limit_price = candidate.zone_bottom + limit_buf
                        filled = bar_low <= limit_price
                    else:
                        limit_price = candidate.zone_top - limit_buf
                        filled = bar_high >= limit_price

                if not filled:
                    if carry_limits:
                        # Don't replace existing pending for same zone
                        already_pending = any(
                            p.zone_key == zone_key for p in pending_limits
                        )
                        if not already_pending:
                            pending_limits.append(_PendingLimit(
                                candidate=candidate,
                                limit_price=limit_price,
                                placed_bar_idx=idx,
                                zone_key=zone_key,
                            ))
                    continue  # Limit order not reached — no entry this bar

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

            # Compute spread-adjusted entry
            eff_entry = _compute_effective_entry(
                candidate.entry_price, candidate.direction,
                config.spread_pips, pip_size)

            if is_signal_flip:
                # Signal-flip initial entry: SL = zone boundary (safety),
                # TP = none (exits via opposite signal)
                if has_safety_sl:
                    sl = compute_retest_sl(
                        candidate, mode=config.sl_mode,
                        atr_mult=config.sl_atr_mult,
                        buffer_atr=config.sl_buffer_atr,
                    )
                    sl = _apply_min_sl(
                        candidate.entry_price, sl, candidate.direction,
                        config.min_sl_pips, pip_size,
                        config.spread_pips, config.min_sl_spread_mult,
                    )
                else:
                    sl = 0.0 if candidate.direction == "long" else 1e9
                tp = 1e9 if candidate.direction == "long" else 0.0

                trade_counter += 1
                trade_id = f"{symbol}_{config.tf_pair}_{trade_counter:04d}"
                open_trades.append(_OpenTrade(
                    candidate=candidate,
                    sl=sl,
                    tp=tp,
                    trade_id=trade_id,
                    symbol=symbol,
                    pip_size=pip_size,
                    effective_entry=eff_entry,
                ))
            else:
                # Fixed SL/TP modes: compute SL with configurable buffer
                sl = compute_retest_sl(
                    candidate,
                    mode=config.sl_mode,
                    atr_mult=config.sl_atr_mult,
                    buffer_atr=config.sl_buffer_atr,
                )
                sl = _apply_min_sl(candidate.entry_price, sl, candidate.direction,
                                   config.min_sl_pips, pip_size,
                                   config.spread_pips, config.min_sl_spread_mult)

                if config.partial_tp:
                    # Partial TP: Unit 1 at fixed R:R, Unit 2 at HTF zone
                    risk = abs(candidate.entry_price - sl)
                    if candidate.direction == "long":
                        unit1_tp = candidate.entry_price + config.partial_unit1_rr * risk
                        be_sl = candidate.entry_price - config.breakeven_buffer_atr * candidate.atr
                    else:
                        unit1_tp = candidate.entry_price - config.partial_unit1_rr * risk
                        be_sl = candidate.entry_price + config.breakeven_buffer_atr * candidate.atr

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
                        effective_entry=eff_entry,
                        partial=True,
                        unit1_pct=config.partial_unit1_pct,
                        unit1_tp=unit1_tp,
                        unit1_closed=False,
                        original_sl=sl,
                        breakeven_sl=be_sl,
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
                        effective_entry=eff_entry,
                    ))

        if config.touch_policy == "first_touch":
            consumed_zones.add(zone_key)

    # Close any remaining open trades at end of data
    if open_trades:
        last_ts = bar_data.index[-1]
        last_close = float(bar_data.iloc[-1]["close"])
        reason = "open_at_close" if is_signal_flip else "end_of_data"
        for ot in open_trades:
            if ot.partial:
                trades.append(ot.close_partial(last_ts, reason))
            else:
                trades.append(ot.close_at(last_close, last_ts, reason))

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
            ot.sl = ot.breakeven_sl  # Move SL to breakeven (+ optional buffer)

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


def _apply_min_sl(
    entry_price: float,
    sl: float,
    direction: str,
    min_sl_pips: float,
    pip_size: float,
    spread_pips: float = 0.0,
    min_sl_spread_mult: float = 0.0,
) -> float:
    """Enforce minimum SL distance. Returns adjusted SL if too tight.

    Effective min SL = max(min_sl_pips, spread_pips * min_sl_spread_mult).
    This ensures SL is always wider than the spread cost.
    """
    eff_min_sl = min_sl_pips
    if min_sl_spread_mult > 0 and spread_pips > 0:
        eff_min_sl = max(eff_min_sl, spread_pips * min_sl_spread_mult)
    if eff_min_sl <= 0:
        return sl
    sl_dist_pips = abs(entry_price - sl) / pip_size if pip_size > 0 else 0.0
    if sl_dist_pips >= eff_min_sl:
        return sl
    if direction == "long":
        return entry_price - eff_min_sl * pip_size
    return entry_price + eff_min_sl * pip_size


def _compute_effective_entry(
    entry_price: float,
    direction: str,
    spread_pips: float,
    pip_size: float,
) -> float:
    """Compute spread-adjusted entry price for P&L calculation."""
    if spread_pips <= 0:
        return float('nan')  # nan = no adjustment
    spread_cost = spread_pips * pip_size
    if direction == "long":
        return entry_price + spread_cost  # Buy at ask
    return entry_price - spread_cost  # Sell at bid


def _enter_from_pending(
    pl: _PendingLimit,
    config: RetestConfig,
    symbol: str,
    pip_size: float,
    fill_ts: pd.Timestamp,
    open_trades: list[_OpenTrade],
    trade_counter: int,
) -> None:
    """Convert a filled pending limit into an open trade."""
    # Override entry price on candidate with the limit price
    candidate = RetestCandidate(
        event=pl.candidate.event,
        zone_top=pl.candidate.zone_top,
        zone_bottom=pl.candidate.zone_bottom,
        entry_price=pl.limit_price,
        atr=pl.candidate.atr,
        period_hi=pl.candidate.period_hi,
        period_lo=pl.candidate.period_lo,
        ltf_choch_zone_boundary=pl.candidate.ltf_choch_zone_boundary,
        next_opposing_zone_price=pl.candidate.next_opposing_zone_price,
        opposing_zone_h1=pl.candidate.opposing_zone_h1,
        opposing_zone_h4=pl.candidate.opposing_zone_h4,
        opposing_zone_d1=pl.candidate.opposing_zone_d1,
        breaker_zones=pl.candidate.breaker_zones,
        d_to_w_relationship=pl.candidate.d_to_w_relationship,
        inside_w_zone=pl.candidate.inside_w_zone,
    )

    sl = compute_retest_sl(candidate, mode=config.sl_mode, atr_mult=config.sl_atr_mult,
                           buffer_atr=config.sl_buffer_atr)
    sl = _apply_min_sl(candidate.entry_price, sl, candidate.direction,
                       config.min_sl_pips, pip_size,
                       config.spread_pips, config.min_sl_spread_mult)
    eff_entry = _compute_effective_entry(
        candidate.entry_price, candidate.direction, config.spread_pips, pip_size)

    if config.partial_tp:
        risk = abs(candidate.entry_price - sl)
        if candidate.direction == "long":
            unit1_tp = candidate.entry_price + config.partial_unit1_rr * risk
            be_sl = candidate.entry_price - config.breakeven_buffer_atr * candidate.atr
        else:
            unit1_tp = candidate.entry_price - config.partial_unit1_rr * risk
            be_sl = candidate.entry_price + config.breakeven_buffer_atr * candidate.atr

        tp = compute_retest_tp(
            candidate, sl_price=sl, mode="htf_zone",
            fixed_rr=config.partial_unit1_rr, tp_htf=config.partial_unit2_tp,
        )
        trade_id = f"{symbol}_{config.tf_pair}_{trade_counter + 1:04d}"
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
            partial=True, unit1_pct=config.partial_unit1_pct,
            unit1_tp=unit1_tp, unit1_closed=False, original_sl=sl,
            breakeven_sl=be_sl,
        ))
    else:
        tp = compute_retest_tp(
            candidate, sl_price=sl, mode=config.tp_mode,
            fixed_rr=config.fixed_rr, tp_htf=config.tp_htf,
        )
        trade_id = f"{symbol}_{config.tf_pair}_{trade_counter + 1:04d}"
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
        ))


def _enter_ltf_trade(
    candidate: RetestCandidate,
    config: RetestConfig,
    symbol: str,
    pip_size: float,
    open_trades: list[_OpenTrade],
    trade_counter: int,
) -> None:
    """Enter a trade from an LTF nested zone (reuses existing SL/TP logic)."""
    sl = compute_retest_sl(candidate, mode=config.sl_mode,
                           atr_mult=config.sl_atr_mult, buffer_atr=config.sl_buffer_atr)
    sl = _apply_min_sl(candidate.entry_price, sl, candidate.direction,
                       config.min_sl_pips, pip_size,
                       config.spread_pips, config.min_sl_spread_mult)
    eff_entry = _compute_effective_entry(
        candidate.entry_price, candidate.direction, config.spread_pips, pip_size)

    trade_id = f"{symbol}_{config.tf_pair}_ltf_{trade_counter + 1:04d}"

    if config.partial_tp:
        risk = abs(candidate.entry_price - sl)
        if candidate.direction == "long":
            unit1_tp = candidate.entry_price + config.partial_unit1_rr * risk
            be_sl = candidate.entry_price - config.breakeven_buffer_atr * candidate.atr
        else:
            unit1_tp = candidate.entry_price - config.partial_unit1_rr * risk
            be_sl = candidate.entry_price + config.breakeven_buffer_atr * candidate.atr

        tp = compute_retest_tp(
            candidate, sl_price=sl, mode="htf_zone",
            fixed_rr=config.partial_unit1_rr, tp_htf=config.partial_unit2_tp,
        )
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
            partial=True, unit1_pct=config.partial_unit1_pct,
            unit1_tp=unit1_tp, unit1_closed=False, original_sl=sl,
            breakeven_sl=be_sl,
        ))
    else:
        tp = compute_retest_tp(
            candidate, sl_price=sl, mode=config.tp_mode,
            fixed_rr=config.fixed_rr, tp_htf=config.tp_htf,
        )
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
        ))


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
    spread_pips: float = 0.0,
) -> dict:
    """Compute metrics from retest trades via the sweep_runner compute_metrics.

    Adds signal-flip specific metrics when flip trades are present.
    """
    sweep_records = _adapt_to_sweep_records(trades, symbol)
    metrics = compute_metrics(sweep_records)

    # Signal-flip metrics
    flip_trades = [t for t in trades if t.exit_reason == "signal_flip"]
    flip_count = len(flip_trades)
    metrics["flip_count"] = flip_count

    if flip_count > 0:
        flip_pips = [abs(t.pnl_pips) for t in flip_trades]
        metrics["avg_flip_pips"] = sum(flip_pips) / flip_count

        flip_durations = [
            (t.exit_time - t.entry_time).total_seconds() / 60.0
            for t in flip_trades
        ]
        metrics["avg_flip_duration_mins"] = sum(flip_durations) / flip_count
    else:
        metrics["avg_flip_pips"] = 0.0
        metrics["avg_flip_duration_mins"] = 0.0

    # Spread accounting:
    # total_pnl_pips already includes spread (via effective_entry on each trade).
    # gross_pnl_pips = what P&L would be WITHOUT spread.
    # net_after_spread = total_pnl_pips (already correct, no double-counting).
    all_trade_count = len(trades)
    total_spread_cost = all_trade_count * spread_pips
    metrics["total_spread_cost_pips"] = total_spread_cost
    metrics["gross_pnl_pips"] = metrics.get("total_pnl_pips", 0.0) + total_spread_cost
    metrics["net_after_spread"] = metrics.get("total_pnl_pips", 0.0)  # Already spread-adjusted

    # Safety SL hits
    safety_hits = sum(1 for t in trades if t.exit_reason == "safety_sl_hit")
    metrics["safety_sl_hits"] = safety_hits

    # Open at close (signal-flip end-of-data)
    open_at_close = sum(1 for t in trades if t.exit_reason == "open_at_close")
    metrics["open_at_close"] = open_at_close

    return metrics
