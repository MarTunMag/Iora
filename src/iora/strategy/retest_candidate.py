"""RetestCandidate — enriched retest event for Level 4 sweep."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan, nan

import numpy as np
import pandas as pd

from iora.data.bar_iterator import iter_bars
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.indicators.heikin_ashi import calculate_heikin_ashi
from iora.indicators.hma import (
    compute_hma, compute_hma_direction, compute_ha_hma_cross, compute_bars_since_cross,
)
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

    # Breaker zones inside the context zone (for layered limit orders)
    # Each tuple: (zone_top, zone_bottom, zone_tf) of a broken LTF zone
    breaker_zones: list[tuple[float, float, str]] = field(default_factory=list)

    # HMA state at entry time (from reference TF)
    hma_direction_h1: int = 0       # +1 rising, -1 falling, 0 flat/unavailable
    hma_direction_h4: int = 0
    ha_above_hma_h1: bool = False   # HA close > HMA on H1 at this bar
    ha_above_hma_h4: bool = False
    bars_since_hma_cross_h1: int = 9999  # entry-TF bars since last cross
    bars_since_hma_cross_h4: int = 9999
    hma_cross_direction_h1: int = 0  # +1 bullish, -1 bearish
    hma_cross_direction_h4: int = 0

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


def _find_breaker_zones(
    state: PushZoneEngineState,
    entry_tf: str,
    zone_side: str,
    ctx_zone_top: float,
    ctx_zone_bottom: float,
    max_zones: int = 3,
) -> list[tuple[float, float, str]]:
    """Find LTF opposing zones inside the context zone (breaker zones).

    For demand retest: LTF supply zones inside context zone (broken resistance → breaker demand).
    For supply retest: LTF demand zones inside context zone (broken support → breaker supply).
    Returns up to max_zones sorted by price (highest first for demand, lowest first for supply).
    Each tuple: (zone_top, zone_bottom, zone_tf).
    """
    from iora.constants import ENGINE_TF_ORDER

    # Determine which TFs are lower than the context zone's TF by checking
    # which TFs have tick states and are in the ENGINE_TF_ORDER before entry_tf
    entry_idx = ENGINE_TF_ORDER.index(entry_tf) if entry_tf in ENGINE_TF_ORDER else 0
    # Look at entry_tf and anything lower
    ltf_candidates = ENGINE_TF_ORDER[:entry_idx + 1]

    results: list[tuple[float, float, str]] = []
    for tf in ltf_candidates:
        ts = state.tick_states.get(tf)
        if ts is None:
            continue

        if zone_side == "demand":
            # Long retest — find LTF supply zones inside the context demand zone
            for z in ts.supply_zones:
                if z.bottom >= ctx_zone_bottom and z.top <= ctx_zone_top:
                    results.append((z.top, z.bottom, tf))
        else:
            # Short retest — find LTF demand zones inside the context supply zone
            for z in ts.demand_zones:
                if z.bottom >= ctx_zone_bottom and z.top <= ctx_zone_top:
                    results.append((z.top, z.bottom, tf))

    # Sort: for demand retests, highest first (shallowest fill first);
    # for supply retests, lowest first (shallowest fill first)
    if zone_side == "demand":
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        results.sort(key=lambda x: x[1], reverse=False)

    return results[:max_zones]


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


@dataclass(slots=True)
class _HmaAlignedState:
    """Pre-computed HMA state aligned to entry TF index."""
    direction: pd.Series       # int: +1, -1, 0
    ha_above_hma: pd.Series    # bool
    bars_since_cross: pd.Series  # int
    cross_direction: pd.Series   # int: +1, -1, 0 (forward-filled)


def _precompute_hma_state(
    ref_tf_df: pd.DataFrame,
    entry_tf_df: pd.DataFrame,
    hma_period: int = 24,
    hma_source: str = "close",
) -> _HmaAlignedState | None:
    """Pre-compute HMA state on a reference TF and align to entry TF.

    Args:
        ref_tf_df: OHLC DataFrame for the reference TF (H1 or H4)
        entry_tf_df: OHLC DataFrame for the entry TF (base index)
        hma_period: HMA period
        hma_source: "close" or "ha_close"

    Returns:
        _HmaAlignedState aligned to entry_tf_df index, or None if ref TF unavailable.
    """
    if ref_tf_df is None or ref_tf_df.empty:
        return None

    # Compute HMA source
    if hma_source == "ha_close":
        ha_df = calculate_heikin_ashi(ref_tf_df)
        source = ha_df["close"]
    else:
        source = ref_tf_df["close"].astype(float)

    hma = compute_hma(source, hma_period)

    # ATR on reference TF for flat threshold
    ref_atr = _compute_atr(ref_tf_df, period=14)

    # Direction
    direction = compute_hma_direction(hma, ref_atr)

    # HA close for cross detection (always use HA close, not regular close)
    ha_df = calculate_heikin_ashi(ref_tf_df)
    ha_close = ha_df["close"]

    ha_above, cross_dir = compute_ha_hma_cross(ha_close, hma)

    # Raw cross events for bars_since computation
    cross_raw = pd.Series(0, index=ref_tf_df.index, dtype=int)
    _prev = np.empty(len(ha_above), dtype=bool)
    _prev[0] = False
    _prev[1:] = ha_above.values[:-1]
    prev_above_arr = pd.Series(_prev, index=ha_above.index)
    cross_raw[ha_above & ~prev_above_arr] = 1
    cross_raw[~ha_above & prev_above_arr] = -1
    bars_since = compute_bars_since_cross(cross_raw)

    # Align to entry TF via merge_asof (forward-fill, no lookahead)
    # The ref TF value at time T is only visible on entry TF bars at T or later.
    ref_state = pd.DataFrame({
        "direction": direction,
        "ha_above_hma": ha_above,
        "bars_since_cross": bars_since,
        "cross_direction": cross_dir,
    }, index=ref_tf_df.index)

    aligned = pd.merge_asof(
        entry_tf_df[["close"]].rename(columns={"close": "_dummy"}),
        ref_state,
        left_index=True, right_index=True,
        direction="backward",
    )

    # Convert bars_since_cross from ref-TF bars to entry-TF bars:
    # Align cross timestamps to entry TF, then count entry bars since each cross.
    cross_times = ref_tf_df.index[cross_raw != 0]
    if len(cross_times) > 0:
        # For each entry bar, find the nearest prior cross time via merge_asof
        cross_time_aligned = pd.merge_asof(
            entry_tf_df[["close"]].rename(columns={"close": "_d2"}),
            pd.DataFrame({"cross_time": cross_times}, index=cross_times),
            left_index=True, right_index=True,
            direction="backward",
        )
        # Vectorized: use searchsorted to find entry-TF bar index of each cross time
        entry_idx = entry_tf_df.index
        cross_ts = cross_time_aligned["cross_time"]
        # For each entry bar, find the entry-bar index of its aligned cross time
        cross_entry_idx = entry_idx.searchsorted(cross_ts, side="left")
        # bars_since = current_entry_idx - cross_entry_idx
        current_idx = np.arange(len(entry_idx))
        entry_bars_since = np.where(
            pd.notna(cross_ts),
            current_idx - cross_entry_idx,
            9999,
        ).astype(int)
        aligned["bars_since_cross"] = entry_bars_since

    return _HmaAlignedState(
        direction=aligned["direction"].fillna(0).astype(int),
        ha_above_hma=aligned["ha_above_hma"].fillna(False).astype(bool),
        bars_since_cross=aligned["bars_since_cross"].fillna(9999).astype(int),
        cross_direction=aligned["cross_direction"].fillna(0).astype(int),
    )


def build_retest_candidates(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
) -> list[RetestCandidate]:
    """Run zone engine + bias + event detection and return enriched RetestCandidates.

    Mirrors _run_single_entry_tf() from opportunity_runner.py, but additionally
    captures zone.top, zone.bottom, period.cur_hi, period.cur_lo at event time.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label (must include entry_tf)
        entry_tf: Entry timeframe to iterate on
        symbol: Symbol name (used for pip size)
        period_depth: Period tracker history depth
        hma_period: HMA period for direction/cross computation
        hma_source: "close" or "ha_close" — source series for HMA

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

    # Pre-compute HMA state on H1 and H4 (aligned to entry TF)
    hma_h1 = _precompute_hma_state(
        data_by_tf.get("H1"), base_df, hma_period, hma_source,
    ) if "H1" in data_by_tf and entry_tf != "H1" else None
    hma_h4 = _precompute_hma_state(
        data_by_tf.get("H4"), base_df, hma_period, hma_source,
    ) if "H4" in data_by_tf and entry_tf not in ("H1", "H4") else None

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

            # Breaker zones: LTF opposing zones inside context zone
            breaker_zones = _find_breaker_zones(
                state, entry_tf, event.zone_side,
                matched_zone.top, matched_zone.bottom,
            )

            # HMA state lookup
            i = ctx.idx
            hma_dir_h1 = int(hma_h1.direction.iloc[i]) if hma_h1 is not None and i < len(hma_h1.direction) else 0
            hma_dir_h4 = int(hma_h4.direction.iloc[i]) if hma_h4 is not None and i < len(hma_h4.direction) else 0
            ha_above_h1 = bool(hma_h1.ha_above_hma.iloc[i]) if hma_h1 is not None and i < len(hma_h1.ha_above_hma) else False
            ha_above_h4 = bool(hma_h4.ha_above_hma.iloc[i]) if hma_h4 is not None and i < len(hma_h4.ha_above_hma) else False
            bsc_h1 = int(hma_h1.bars_since_cross.iloc[i]) if hma_h1 is not None and i < len(hma_h1.bars_since_cross) else 9999
            bsc_h4 = int(hma_h4.bars_since_cross.iloc[i]) if hma_h4 is not None and i < len(hma_h4.bars_since_cross) else 9999
            cross_dir_h1 = int(hma_h1.cross_direction.iloc[i]) if hma_h1 is not None and i < len(hma_h1.cross_direction) else 0
            cross_dir_h4 = int(hma_h4.cross_direction.iloc[i]) if hma_h4 is not None and i < len(hma_h4.cross_direction) else 0

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
                breaker_zones=breaker_zones,
                hma_direction_h1=hma_dir_h1,
                hma_direction_h4=hma_dir_h4,
                ha_above_hma_h1=ha_above_h1,
                ha_above_hma_h4=ha_above_h4,
                bars_since_hma_cross_h1=bsc_h1,
                bars_since_hma_cross_h4=bsc_h4,
                hma_cross_direction_h1=cross_dir_h1,
                hma_cross_direction_h4=cross_dir_h4,
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
