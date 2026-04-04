"""RetestCandidate — enriched retest event for Level 4 sweep."""
from __future__ import annotations

from dataclasses import dataclass
from math import isnan, nan

import pandas as pd

from iora.data.bar_iterator import iter_bars
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.diagnostics.bias_timeline import collect_bias_state
from iora.diagnostics.bias_timeline_runner import _compute_atr
from iora.diagnostics.opportunity_counter import OpportunityEvent, detect_events
from iora.engine.events import EventBus
from iora.engine.push_zone_models import PushZoneTickState
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    PushZoneEngineState,
    init_push_zone_state,
    push_zone_engine_tick,
)


@dataclass(slots=True)
class RetestCandidate:
    """An OpportunityEvent enriched with zone state for SL/TP computation."""

    event: OpportunityEvent

    # Zone boundaries at touch time
    zone_top: float
    zone_bottom: float
    entry_price: float       # Bar close at touch
    atr: float               # ATR(14) on entry TF at touch bar

    # Period levels on zone TF (for period-based SL)
    period_hi: float
    period_lo: float

    # Structural levels for SL/TP (Part 1 enrichment)
    ltf_choch_zone_boundary: float = nan   # LTF zone edge inside context zone (structural SL)
    next_opposing_zone_price: float = nan  # Nearest opposing zone on context TF (structural TP)
    d1_range_midpoint: float = nan         # Midpoint of D1 supply top + D1 demand bottom

    # Phase 3 bias context (from BiasStateRecord at entry time)
    d_to_w_relationship: str = "neutral"
    inside_w_zone: bool = False

    @property
    def direction(self) -> str:
        """Trade direction implied by zone side."""
        return "long" if self.event.zone_side == "demand" else "short"

    @property
    def zone_thickness(self) -> float:
        """Absolute distance between zone boundaries."""
        return self.zone_top - self.zone_bottom


from iora.diagnostics.opportunity_runner import _get_pip_size


def _find_ltf_choch_boundary(
    state: PushZoneEngineState,
    entry_tf: str,
    zone_side: str,
    ctx_zone_top: float,
    ctx_zone_bottom: float,
) -> float:
    """Find the LTF zone edge inside the context zone for structural SL.

    For long (demand retest): most recent LTF supply zone inside context zone → bottom edge.
    For short (supply retest): most recent LTF demand zone inside context zone → top edge.
    Returns NaN if no qualifying LTF zone exists.
    """
    ltf_ts = state.tick_states.get(entry_tf)
    if ltf_ts is None:
        return nan

    if zone_side == "demand":
        # Long entry — look for LTF supply zones inside the context demand zone
        for z in reversed(ltf_ts.supply_zones):
            if z.bottom >= ctx_zone_bottom and z.top <= ctx_zone_top:
                return z.bottom
    else:
        # Short entry — look for LTF demand zones inside the context supply zone
        for z in reversed(ltf_ts.demand_zones):
            if z.bottom >= ctx_zone_bottom and z.top <= ctx_zone_top:
                return z.top

    return nan


def _find_opposing_zone_price(
    ctx_tf_ts: PushZoneTickState,
    zone_side: str,
    entry_price: float,
) -> float:
    """Find the nearest opposing zone on the context TF for structural TP.

    For long: nearest supply zone top above entry price.
    For short: nearest demand zone bottom below entry price.
    Returns NaN if no qualifying zone exists.
    """
    if zone_side == "demand":
        # Long entry — find nearest supply zone above entry
        best = nan
        for z in ctx_tf_ts.supply_zones:
            if z.top > entry_price:
                if isnan(best) or z.top < best:
                    best = z.top
        return best
    else:
        # Short entry — find nearest demand zone below entry
        best = nan
        for z in ctx_tf_ts.demand_zones:
            if z.bottom < entry_price:
                if isnan(best) or z.bottom > best:
                    best = z.bottom
        return best


def _compute_d1_range_midpoint(state: PushZoneEngineState) -> float:
    """Compute midpoint between nearest D1 supply top and D1 demand bottom.

    Returns NaN if D1 zones aren't available on both sides.
    """
    d1_ts = state.tick_states.get("D1")
    if d1_ts is None:
        return nan
    if not d1_ts.supply_zones or not d1_ts.demand_zones:
        return nan
    # Use the most recent (last) zones on each side
    supply_top = d1_ts.supply_zones[-1].top
    demand_bottom = d1_ts.demand_zones[-1].bottom
    return (supply_top + demand_bottom) / 2.0


def build_retest_candidates(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> list[RetestCandidate]:
    """Run zone engine + bias + event detection and return enriched RetestCandidates.

    Mirrors _run_single_entry_tf() from opportunity_runner.py, but additionally
    captures zone.top, zone.bottom, period.cur_hi, period.cur_lo at event time.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label (must include entry_tf)
        entry_tf: Entry timeframe to iterate on
        symbol: Symbol name (used for pip size)
        period_depth: Period tracker history depth

    Returns:
        List of RetestCandidate with zone geometry and ATR attached.
    """
    if entry_tf not in data_by_tf:
        return []

    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, entry_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    base_df = data_by_tf[entry_tf]
    atr_series = _compute_atr(base_df, period=14)
    pip_size = _get_pip_size(symbol)

    candidates: list[RetestCandidate] = []
    prev_d_bias = ""
    prev_swing_cls: dict[str, dict[str, str]] = {}
    bar_idx = 0

    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
        if isnan(atr_val):
            atr_val = 0.002

        bias_rec = collect_bias_state(
            state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
        )
        prev_d_bias = bias_rec.d_bias

        events = detect_events(
            tick_states=state.tick_states,
            entry_tf=entry_tf,
            high=ctx.high, low=ctx.low, close=ctx.close,
            timestamp=ctx.timestamp,
            bias_rec=bias_rec, atr=atr_val, pip_size=pip_size,
            bar_idx=bar_idx, prev_swing_cls=prev_swing_cls,
        )

        for event in events:
            # Look up the matching zone to get geometry + period levels
            ctx_tf = event.zone_tf
            ts = state.tick_states.get(ctx_tf)
            if ts is None:
                continue

            zone_list = ts.demand_zones if event.zone_side == "demand" else ts.supply_zones
            # Find the zone that triggered this event — approximate match by
            # price interaction. When multiple zones overlap, the last match
            # (most recently created) wins. This is a best-effort lookup since
            # OpportunityEvent doesn't carry a zone identity.
            matched_zone = None
            for z in zone_list:
                if event.zone_side == "demand":
                    entered = ctx.low <= z.top
                else:
                    entered = ctx.high >= z.bottom
                if entered:
                    # Use the last matched zone (most recently created wins
                    # when multiple zones overlap, consistent with detect_events order)
                    matched_zone = z

            if matched_zone is None:
                continue

            period_hi = ts.period.cur_hi if not isnan(ts.period.cur_hi) else matched_zone.top
            period_lo = ts.period.cur_lo if not isnan(ts.period.cur_lo) else matched_zone.bottom

            # Structural SL: find LTF zone inside context zone
            ltf_boundary = _find_ltf_choch_boundary(
                state, entry_tf, event.zone_side,
                matched_zone.top, matched_zone.bottom,
            )

            # Structural TP: find nearest opposing zone on context TF
            opposing_price = _find_opposing_zone_price(
                ts, event.zone_side, ctx.close,
            )

            # D1 range midpoint for premium/discount filter
            d1_mid = _compute_d1_range_midpoint(state)

            # Phase 3: extract W zone and D-to-W context from bias record
            is_inside_w = (
                bias_rec.nearest_w_supply_dist < 0
                or bias_rec.nearest_w_demand_dist < 0
            )

            candidates.append(RetestCandidate(
                event=event,
                zone_top=matched_zone.top,
                zone_bottom=matched_zone.bottom,
                entry_price=ctx.close,
                atr=atr_val,
                period_hi=period_hi,
                period_lo=period_lo,
                ltf_choch_zone_boundary=ltf_boundary,
                next_opposing_zone_price=opposing_price,
                d1_range_midpoint=d1_mid,
                d_to_w_relationship=bias_rec.d_to_w_relationship,
                inside_w_zone=is_inside_w,
            ))

        # Update prev_swing_cls for next bar
        for tf, ts in state.tick_states.items():
            if tf not in prev_swing_cls:
                prev_swing_cls[tf] = {"supply": "", "demand": ""}
            if ts.supply_zones and ts.supply_zones[-1].swing_cls:
                prev_swing_cls[tf]["supply"] = ts.supply_zones[-1].swing_cls
            if ts.demand_zones and ts.demand_zones[-1].swing_cls:
                prev_swing_cls[tf]["demand"] = ts.demand_zones[-1].swing_cls

        bar_idx += 1

    return candidates
