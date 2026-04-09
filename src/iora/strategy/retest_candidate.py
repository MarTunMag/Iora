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
from iora.engine.cascade_state import CascadePhaseState, cascade_state_tick


@dataclass(slots=True)
class ZoneBirthEvent:
    """A push zone born on a specific bar."""
    timestamp: pd.Timestamp
    zone_top: float
    zone_bottom: float
    zone_tf: str
    zone_side: str       # "demand" or "supply"
    is_push: bool
    origin_time: pd.Timestamp  # Zone creation time (for identity)


@dataclass(slots=True)
class CascadeSnapshot:
    """Per-bar snapshot of cascade phase state for windowed signal-flip."""
    phase: str                          # e.g. "h4_correction", "d1_push"
    h4_correction_tl_intact: bool
    h4_impulse_tl_intact: bool
    h1_correction_tl_intact: bool
    h1_impulse_tl_intact: bool
    m15_correction_bars_since_break: int = -1
    m15_impulse_bars_since_break: int = -1
    h1_push_zone_count: int = 0

    # Layer 2.5: HTF level break timestamps (None = not broken this period)
    d1_hi_brk_time: pd.Timestamp | None = None
    d1_lo_brk_time: pd.Timestamp | None = None
    h4_hi_brk_time: pd.Timestamp | None = None
    h4_lo_brk_time: pd.Timestamp | None = None
    h1_hi_brk_time: pd.Timestamp | None = None
    h1_lo_brk_time: pd.Timestamp | None = None

    # Layer 2.5: M15 TL state
    m15_correction_tl_intact: bool = True
    m15_impulse_tl_intact: bool = True
    m15_trend: int = 0                  # +1 bullish, -1 bearish, 0 flat


@dataclass(slots=True)
class CandidateBuildResult:
    """Result of build_retest_candidates with optional zone birth events."""
    candidates: list['RetestCandidate']
    zone_births: dict  # pd.Timestamp → list[ZoneBirthEvent], empty if not collected
    cascade_timeline: dict = field(default_factory=dict)  # pd.Timestamp → CascadeSnapshot


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

    # Cross-TF TP targets — opposing zones on higher TFs
    opposing_zone_h1: float = nan          # Nearest H1 opposing zone
    opposing_zone_h4: float = nan          # Nearest H4 opposing zone
    opposing_zone_d1: float = nan          # Nearest D1 opposing zone

    # Breaker zones inside the context zone (for layered limit orders)
    # Each tuple: (zone_top, zone_bottom, zone_tf) of a broken LTF zone
    breaker_zones: list[tuple[float, float, str]] = field(default_factory=list)

    # Nested LTF zones (populated when ltf_nesting="static")
    # Each: (zone_top, zone_bottom, zone_tf, zone_side, is_push)
    nested_ltf_zones: list[tuple[float, float, str, str, bool]] = field(default_factory=list)

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

    # Cascade phase state (from push zone trendline engine)
    cascade_phase: str = "unknown"
    h1_push_zone_count: int = 0
    h1_impulse_tl_intact: bool = True
    h1_correction_tl_intact: bool = True
    h4_impulse_tl_intact: bool = True
    h4_correction_tl_intact: bool = True
    is_reversal_target_zone: bool = False  # Zone tagged as CHoCH-causing

    # TL break recency (bars since last break per TF/type, -1 = never)
    h1_impulse_bars_since_break: int = -1
    h1_correction_bars_since_break: int = -1
    h4_impulse_bars_since_break: int = -1
    h4_correction_bars_since_break: int = -1

    # EW-derived exhaustion signals
    h1_zone4_overlaps_zone1: bool = False
    h1_wave3_extension_ratio: float = float('nan')

    # CHoCH conviction classification
    h4_choch_conviction: str = ""    # "strong", "weak", "pre", ""
    h1_choch_conviction: str = ""

    # Momentum consumption count (child TFs aligned after H4 CHoCH)
    h4_consumption_count: int = 0
    h4_consumption_complete: bool = False

    # Structural overlap metrics (Phase 3)
    pivot_cascade_depth: int = 0        # How many TFs confirm same direction
    fvg_at_candidate: bool = False      # Unfilled candle FVG overlaps candidate zone
    breaker_at_candidate: bool = False  # Breaker zone overlaps candidate zone
    structural_fvg_position: str = "none"  # "inside_gap", "at_gap_boundary", "none"

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


def _find_nested_ltf_zones(
    state: PushZoneEngineState,
    ltf_tf: str,
    zone_side: str,
    ctx_zone_top: float,
    ctx_zone_bottom: float,
    require_push: bool = False,
    max_zones: int = 5,
) -> list[tuple[float, float, str, str, bool]]:
    """Find LTF zones geometrically inside a context zone (same side).

    For demand H4 zone: LTF demand zones with top <= H4 top AND bottom >= H4 bottom.
    For supply H4 zone: LTF supply zones with bottom >= H4 bottom AND top <= H4 top.

    Returns list of (zone_top, zone_bottom, zone_tf, zone_side, is_push) sorted by
    proximity to price entry edge — for demand: zone_top descending (nearest first),
    for supply: zone_bottom ascending (nearest first).
    """
    ts = state.tick_states.get(ltf_tf)
    if ts is None:
        return []

    zone_list = ts.demand_zones if zone_side == "demand" else ts.supply_zones
    results: list[tuple[float, float, str, str, bool]] = []

    for z in zone_list:
        # Geometric containment: LTF zone fully inside context zone
        if z.top > ctx_zone_top or z.bottom < ctx_zone_bottom:
            continue

        if require_push and not z.is_push:
            continue

        results.append((z.top, z.bottom, ltf_tf, zone_side, z.is_push))

    # Sort by proximity to where price first enters:
    # demand = nearest to zone top (highest first)
    # supply = nearest to zone bottom (lowest first)
    if zone_side == "demand":
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        results.sort(key=lambda x: x[1], reverse=False)

    return results[:max_zones]


def _compute_pivot_cascade_depth(
    state: "PushZoneEngineState",
    zone_side: str,
) -> int:
    """Count how many TFs have trend matching the entry direction."""
    entry_dir = 1 if zone_side == "demand" else -1
    count = 0
    for tf in ("D1", "W1", "H4", "H1", "M15", "M5"):
        ts = state.tick_states.get(tf)
        if ts is not None and ts.trend == entry_dir:
            count += 1
    return count


def _check_fvg_at_zone(
    state: "PushZoneEngineState",
    zone_top: float,
    zone_bottom: float,
) -> bool:
    """Check if any active FVG (any TF) overlaps the candidate zone."""
    from iora.engine.fvg_tick import fvg_overlaps_zone
    for tf, fvg_st in state.fvg_states.items():
        if fvg_overlaps_zone(fvg_st.active_fvgs, zone_top, zone_bottom):
            return True
    return False


def _check_structural_fvg(
    state: "PushZoneEngineState",
    zone_top: float,
    zone_bottom: float,
) -> str:
    """Check zone's relationship to structural FVGs across all TF pairs."""
    from iora.engine.structural_fvg import structural_fvg_at_zone
    for key, sfvg_st in state.structural_fvg_states.items():
        result = structural_fvg_at_zone(sfvg_st.active_fvgs, zone_top, zone_bottom)
        if result != "none":
            return result
    return "none"


def _check_breaker_at_zone(
    state: "PushZoneEngineState",
    zone_top: float,
    zone_bottom: float,
    zone_side: str,
) -> bool:
    """Check if any breaker zone overlaps the candidate zone.

    For demand entries (long), look for demand breakers (former supply).
    For supply entries (short), look for supply breakers (former demand).
    """
    for tf, ts in state.tick_states.items():
        breakers = ts.demand_breakers if zone_side == "demand" else ts.supply_breakers
        for b in breakers:
            if b.top >= zone_bottom and b.bottom <= zone_top:
                return True
    return False


def _zone_overlaps_reversal_target(
    zone: "PushZone",
    cascade_st: "CascadePhaseState",
    atr: float,
) -> bool:
    """Check if a zone overlaps the H1 or H4 reversal target within 1 ATR tolerance."""
    tolerance = atr
    for rt_top, rt_bot in [
        (cascade_st.h1_reversal_target_top, cascade_st.h1_reversal_target_bottom),
        (cascade_st.h4_reversal_target_top, cascade_st.h4_reversal_target_bottom),
    ]:
        if isnan(rt_top) or isnan(rt_bot):
            continue
        # Overlap check with tolerance
        if zone.top + tolerance >= rt_bot and zone.bottom - tolerance <= rt_top:
            return True
    return False


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


def _build_candidates_core(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
    ltf_tf: str = "",
    require_ltf_push: bool = False,
    collect_births: bool = False,
    birth_tfs: list[str] | None = None,
    collect_cascade_timeline: bool = False,
) -> CandidateBuildResult:
    """Core candidate building logic with optional nesting enrichment and birth tracking.

    Mirrors _run_single_entry_tf() from opportunity_runner.py, but additionally
    captures zone.top, zone.bottom, period.cur_hi, period.cur_lo at event time.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label (must include entry_tf)
        entry_tf: Entry timeframe to iterate on
        symbol: Symbol name (used for pip size)
        period_depth: Period tracker history depth
        hma_period: HMA period for direction/cross computation
        hma_source: "close" or "ha_close" — source series for HMA
        ltf_tf: LTF for nested zone lookup (static nesting). Empty = skip.
        require_ltf_push: Only include LTF push zones in nesting.
        collect_births: If True, track zone birth events across birth_tfs.
        birth_tfs: TFs to monitor for zone births (dynamic nesting).

    Returns:
        CandidateBuildResult with candidates and optional zone_births dict.
    """
    if entry_tf not in data_by_tf:
        return CandidateBuildResult(candidates=[], zone_births={})

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

    # Determine LTF TFs to scan for nesting enrichment
    # Always populate for H1@H4 and H1@D1 pairs when LTF data is available
    nesting_ltf_tfs: list[str] = []
    if ltf_tf:
        nesting_ltf_tfs = [ltf_tf]
    else:
        # Auto-populate for qualifying pairs: check if M15, M5, M1 are in data
        for candidate_ltf in ["M15", "M5", "M1"]:
            if candidate_ltf in tfs and candidate_ltf != entry_tf:
                nesting_ltf_tfs.append(candidate_ltf)

    # Zone birth tracking state (dynamic nesting)
    seen_zones: set[tuple] = set()
    zone_births: dict[pd.Timestamp, list[ZoneBirthEvent]] = {}
    cascade_timeline: dict[pd.Timestamp, CascadeSnapshot] = {}
    _birth_tfs = birth_tfs or []

    candidates: list[RetestCandidate] = []
    prev_d_bias = ""
    prev_swing_cls: dict[str, dict[str, str]] = {}
    bar_idx = 0
    cascade_phase_st = CascadePhaseState()

    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        # Update cascade phase state (reads push zone trends + TL breaks)
        cascade_state_tick(
            cascade_phase_st,
            state.tick_states,
            state.tl_states,
            state.bar_tl_events,
            ctx.close,
        )

        # Cascade timeline for windowed signal-flip
        if collect_cascade_timeline:
            # Collect HTF period break timestamps from PeriodTracker
            d1_ts = state.tick_states.get("D1")
            h4_ts = state.tick_states.get("H4")
            h1_ts = state.tick_states.get("H1")
            cascade_timeline[ctx.timestamp] = CascadeSnapshot(
                phase=cascade_phase_st.phase,
                h4_correction_tl_intact=cascade_phase_st.h4_correction_tl_intact,
                h4_impulse_tl_intact=cascade_phase_st.h4_impulse_tl_intact,
                h1_correction_tl_intact=cascade_phase_st.h1_correction_tl_intact,
                h1_impulse_tl_intact=cascade_phase_st.h1_impulse_tl_intact,
                m15_correction_bars_since_break=cascade_phase_st.m15_correction_bars_since_break,
                m15_impulse_bars_since_break=cascade_phase_st.m15_impulse_bars_since_break,
                h1_push_zone_count=cascade_phase_st.h1_push_zone_count,
                # Layer 2.5: HTF period break timestamps
                d1_hi_brk_time=d1_ts.period.hi_brk_time if d1_ts else None,
                d1_lo_brk_time=d1_ts.period.lo_brk_time if d1_ts else None,
                h4_hi_brk_time=h4_ts.period.hi_brk_time if h4_ts else None,
                h4_lo_brk_time=h4_ts.period.lo_brk_time if h4_ts else None,
                h1_hi_brk_time=h1_ts.period.hi_brk_time if h1_ts else None,
                h1_lo_brk_time=h1_ts.period.lo_brk_time if h1_ts else None,
                # Layer 2.5: M15 TL state
                m15_correction_tl_intact=cascade_phase_st.m15_correction_tl_intact,
                m15_impulse_tl_intact=cascade_phase_st.m15_impulse_tl_intact,
                m15_trend=cascade_phase_st.m15_trend,
            )

        # Zone birth tracking — detect new zones born on this bar
        if collect_births and _birth_tfs:
            births_this_bar: list[ZoneBirthEvent] = []
            for btf in _birth_tfs:
                bts = state.tick_states.get(btf)
                if bts is None:
                    continue
                for side, zones in [("demand", bts.demand_zones), ("supply", bts.supply_zones)]:
                    for z in zones:
                        zkey = (z.top, z.bottom, z.origin_time, btf, side)
                        if zkey not in seen_zones:
                            seen_zones.add(zkey)
                            births_this_bar.append(ZoneBirthEvent(
                                timestamp=ctx.timestamp,
                                zone_top=z.top, zone_bottom=z.bottom,
                                zone_tf=btf, zone_side=side,
                                is_push=z.is_push,
                                origin_time=z.origin_time,
                            ))
            if births_this_bar:
                zone_births[ctx.timestamp] = births_this_bar

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

            # Cross-TF TP targets: opposing zones on H1, H4, D1
            opp_h1 = nan
            opp_h4 = nan
            opp_d1 = nan
            for target_tf in ["H1", "H4", "D1"]:
                target_ts = state.tick_states.get(target_tf)
                if target_ts is not None and target_tf != ctx_tf:
                    opp_price = _find_opposing_zone_price(
                        target_ts, event.zone_side, ctx.close,
                    )
                    if target_tf == "H1":
                        opp_h1 = opp_price
                    elif target_tf == "H4":
                        opp_h4 = opp_price
                    else:
                        opp_d1 = opp_price

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

            # Nested LTF zones for static nesting (populate for HTF pairs)
            nested_ltf: list[tuple[float, float, str, str, bool]] = []
            if nesting_ltf_tfs and event.zone_tf != entry_tf:
                for n_tf in nesting_ltf_tfs:
                    if n_tf in state.tick_states:
                        nested_ltf.extend(_find_nested_ltf_zones(
                            state=state,
                            ltf_tf=n_tf,
                            zone_side=event.zone_side,
                            ctx_zone_top=matched_zone.top,
                            ctx_zone_bottom=matched_zone.bottom,
                            require_push=require_ltf_push,
                        ))

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
                opposing_zone_h1=opp_h1,
                opposing_zone_h4=opp_h4,
                opposing_zone_d1=opp_d1,
                breaker_zones=breaker_zones,
                nested_ltf_zones=nested_ltf,
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
                cascade_phase=cascade_phase_st.phase,
                h1_push_zone_count=cascade_phase_st.h1_push_zone_count,
                h1_impulse_tl_intact=cascade_phase_st.h1_impulse_tl_intact,
                h1_correction_tl_intact=cascade_phase_st.h1_correction_tl_intact,
                h4_impulse_tl_intact=cascade_phase_st.h4_impulse_tl_intact,
                h4_correction_tl_intact=cascade_phase_st.h4_correction_tl_intact,
                is_reversal_target_zone=(
                    matched_zone.caused_bos_choch == "CHoCH"
                    or _zone_overlaps_reversal_target(
                        matched_zone, cascade_phase_st, atr_val)
                ),
                h1_impulse_bars_since_break=cascade_phase_st.h1_impulse_bars_since_break,
                h1_correction_bars_since_break=cascade_phase_st.h1_correction_bars_since_break,
                h4_impulse_bars_since_break=cascade_phase_st.h4_impulse_bars_since_break,
                h4_correction_bars_since_break=cascade_phase_st.h4_correction_bars_since_break,
                h1_zone4_overlaps_zone1=cascade_phase_st.h1_zone4_overlaps_zone1,
                h1_wave3_extension_ratio=cascade_phase_st.h1_wave3_extension_ratio,
                h4_choch_conviction=cascade_phase_st.h4_last_choch_conviction,
                h1_choch_conviction=cascade_phase_st.h1_last_choch_conviction,
                h4_consumption_count=cascade_phase_st.h4_consumption_count,
                h4_consumption_complete=cascade_phase_st.h4_consumption_complete,
                pivot_cascade_depth=_compute_pivot_cascade_depth(
                    state, event.zone_side),
                fvg_at_candidate=_check_fvg_at_zone(
                    state, matched_zone.top, matched_zone.bottom),
                breaker_at_candidate=_check_breaker_at_zone(
                    state, matched_zone.top, matched_zone.bottom,
                    event.zone_side),
                structural_fvg_position=_check_structural_fvg(
                    state, matched_zone.top, matched_zone.bottom),
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

    return CandidateBuildResult(
        candidates=candidates,
        zone_births=zone_births,
        cascade_timeline=cascade_timeline,
    )


def build_retest_candidates(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
    ltf_tf: str = "",
    require_ltf_push: bool = False,
) -> list[RetestCandidate]:
    """Run zone engine + bias + event detection and return enriched RetestCandidates.

    This is the standard entry point. For dynamic nesting (zone birth events),
    use ``build_retest_candidates_with_births`` instead.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label (must include entry_tf)
        entry_tf: Entry timeframe to iterate on
        symbol: Symbol name (used for pip size)
        period_depth: Period tracker history depth
        hma_period: HMA period for direction/cross computation
        hma_source: "close" or "ha_close" — source series for HMA
        ltf_tf: LTF for nested zone lookup (static nesting). Empty = skip.
        require_ltf_push: Only include LTF push zones in nesting.

    Returns:
        List of RetestCandidate with zone geometry and ATR attached.
    """
    result = _build_candidates_core(
        data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
        period_depth=period_depth, hma_period=hma_period, hma_source=hma_source,
        ltf_tf=ltf_tf, require_ltf_push=require_ltf_push,
        collect_births=False, birth_tfs=None,
    )
    return result.candidates


def build_retest_candidates_with_births(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
    ltf_tf: str = "",
    require_ltf_push: bool = False,
    birth_tfs: list[str] | None = None,
    collect_cascade_timeline: bool = False,
) -> CandidateBuildResult:
    """Run zone engine + bias + event detection with zone birth event collection.

    Same as ``build_retest_candidates`` but additionally collects zone birth
    events for dynamic nesting mode.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label (must include entry_tf)
        entry_tf: Entry timeframe to iterate on
        symbol: Symbol name (used for pip size)
        period_depth: Period tracker history depth
        hma_period: HMA period for direction/cross computation
        hma_source: "close" or "ha_close" — source series for HMA
        ltf_tf: LTF for nested zone lookup (static nesting). Empty = skip.
        require_ltf_push: Only include LTF push zones in nesting.
        birth_tfs: TFs to monitor for zone births (e.g. ["M15", "M5"]).
                   If None or empty, birth tracking is disabled.
        collect_cascade_timeline: If True, capture per-bar CascadeSnapshot for windowed mode.

    Returns:
        CandidateBuildResult with candidates, zone_births, and cascade_timeline.
    """
    return _build_candidates_core(
        data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
        period_depth=period_depth, hma_period=hma_period, hma_source=hma_source,
        ltf_tf=ltf_tf, require_ltf_push=require_ltf_push,
        collect_births=bool(birth_tfs), birth_tfs=birth_tfs,
        collect_cascade_timeline=collect_cascade_timeline,
    )
