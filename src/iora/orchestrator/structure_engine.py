"""
Structure engine — trendlines + HH/LL structure + H1 wave state machine.

Pine reference:
  spring_leaf_wave_navigator.pine (lives at C:\\Oriz\\tw_indicators\\ — separate TradingView project)

Orchestrates:
  - Push trendlines per 7 TFs (M1, M5, M15, H1, H4, D, W)
  - TL break detection (M15, H1, H4, D)
  - H4/D/W structural counting (HH/LL/LH/HL)
  - H1 4-phase wave state machine (IMP/COR)
  - H4 push phase tracking

Data flow:
  Aligned multi-TF data → iter_bars → structure_tick() per bar
  → trendlines + breaks + structure + wave state
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import Trendline, BarContext, FractalZone
from iora.engine.events import EventBus
from iora.engine.trendline_tick import (
    TrendlineTickState,
    trendline_tick,
    get_all_trendlines,
)
from iora.engine.structure_count import (
    StructureCountState,
    H4PushPhaseState,
    structure_count_tick,
    h4_push_phase_tick,
)
from iora.engine.wave_sm import (
    WaveSMState,
    wave_sm_tick,
    get_wave_label,
)
from iora.engine.ew_classify import (
    EWState,
    ew_classify_tick,
)
from iora.engine.xtf_trendline import (
    XTFTrendlineState,
    XTF_PARENT_TFS,
    XTF_ANCHOR_MAP,
    xtf_trendline_tick,
)
from iora.data.tf_alignment import TF_ORDER

# TFs that have break detection enabled (Pine S16)
_BREAK_TFS = {"M15", "H1", "H4", "D1"}


@dataclass(slots=True)
class StructureConfig:
    doji_pct: float = 5.0
    lookback: int = 10
    tl_history: int = 10
    break_tfs: set[str] = field(default_factory=lambda: set(_BREAK_TFS))


@dataclass(slots=True)
class StructureState:
    """Full mutable state for the structure engine."""

    tl_states: dict[str, TrendlineTickState] = field(default_factory=dict)
    xtf_tl_states: dict[str, XTFTrendlineState] = field(default_factory=dict)
    d_structure: StructureCountState = field(
        default_factory=lambda: StructureCountState(phase="D Unknown")
    )
    w_structure: StructureCountState = field(
        default_factory=lambda: StructureCountState(phase="W Unknown")
    )
    h4_push: H4PushPhaseState = field(default_factory=H4PushPhaseState)
    wave_sm: WaveSMState = field(default_factory=WaveSMState)
    ew: EWState = field(default_factory=EWState)


def init_structure_state(tf_list: list[str] | None = None) -> StructureState:
    """Create a fresh StructureState with TrendlineTickState per TF."""
    if tf_list is None:
        tf_list = list(TF_ORDER)
    tl_states = {tf: TrendlineTickState() for tf in tf_list}
    xtf_tl_states = {tf: XTFTrendlineState() for tf in XTF_PARENT_TFS}
    return StructureState(tl_states=tl_states, xtf_tl_states=xtf_tl_states)


def _process_trendlines(
    state: StructureState, ctx: BarContext, config: StructureConfig, bus: EventBus | None,
) -> None:
    """Run trendline_tick for all TFs."""
    for tf in state.tl_states:
        htf_data = ctx.htf.get(tf, {})
        edge_data = ctx.edges.get(tf, {})

        hi_fire = bool(edge_data.get("edge_hi_fire", False))
        lo_fire = bool(edge_data.get("edge_lo_fire", False))

        hi_price = htf_data.get("hi_price") if hi_fire else None
        hi_time_raw = htf_data.get("hi_time") if hi_fire else None
        hi_time = pd.Timestamp(hi_time_raw) if hi_time_raw is not None else None
        hi_is_hh = bool(htf_data.get("hi_is_hh", False)) if hi_fire else False

        lo_price = htf_data.get("lo_price") if lo_fire else None
        lo_time_raw = htf_data.get("lo_time") if lo_fire else None
        lo_time = pd.Timestamp(lo_time_raw) if lo_time_raw is not None else None
        lo_is_ll = bool(htf_data.get("lo_is_ll", False)) if lo_fire else False

        tl_bus = bus if tf in config.break_tfs else None

        trendline_tick(
            state=state.tl_states[tf],
            hi_fire=hi_fire,
            hi_price=hi_price,
            hi_time=hi_time,
            hi_is_hh=hi_is_hh,
            lo_fire=lo_fire,
            lo_price=lo_price,
            lo_time=lo_time,
            lo_is_ll=lo_is_ll,
            bar_high=ctx.high,
            bar_low=ctx.low,
            bar_time=ctx.timestamp,
            timeframe=tf,
            tl_max_history=config.tl_history,
            bus=tl_bus,
        )


def _process_structure(
    state: StructureState,
    ctx: BarContext,
    d_supply_zones: list[FractalZone] | None,
    d_demand_zones: list[FractalZone] | None,
) -> None:
    """H4→D and D→W structure counting + H4 push phase."""
    # H4 → D
    h4_edge = ctx.edges.get("H4", {})
    h4_htf = ctx.htf.get("H4", {})
    h4_hi_fire = bool(h4_edge.get("edge_hi_fire", False))
    h4_lo_fire = bool(h4_edge.get("edge_lo_fire", False))

    structure_count_tick(
        state=state.d_structure,
        hi_fire=h4_hi_fire,
        hi_ztop=h4_htf.get("ztop") if h4_hi_fire else None,
        hi_is_hh=bool(h4_htf.get("hi_is_hh", False)) if h4_hi_fire else False,
        lo_fire=h4_lo_fire,
        lo_zbot=h4_htf.get("zbot") if h4_lo_fire else None,
        lo_is_ll=bool(h4_htf.get("lo_is_ll", False)) if h4_lo_fire else False,
        level_prefix="D",
    )

    h4_push_phase_tick(
        state=state.h4_push,
        hi_fire=h4_hi_fire,
        hi_ztop=h4_htf.get("ztop") if h4_hi_fire else None,
        hi_zbot=h4_htf.get("zbot") if h4_hi_fire else None,
        lo_fire=h4_lo_fire,
        lo_ztop=h4_htf.get("ztop") if h4_lo_fire else None,
        lo_zbot=h4_htf.get("zbot") if h4_lo_fire else None,
        d_supply_zones=d_supply_zones,
        d_demand_zones=d_demand_zones,
    )

    # D → W
    d_edge = ctx.edges.get("D1", {})
    d_htf = ctx.htf.get("D1", {})
    d_hi_fire = bool(d_edge.get("edge_hi_fire", False))
    d_lo_fire = bool(d_edge.get("edge_lo_fire", False))

    structure_count_tick(
        state=state.w_structure,
        hi_fire=d_hi_fire,
        hi_ztop=d_htf.get("ztop") if d_hi_fire else None,
        hi_is_hh=bool(d_htf.get("hi_is_hh", False)) if d_hi_fire else False,
        lo_fire=d_lo_fire,
        lo_zbot=d_htf.get("zbot") if d_lo_fire else None,
        lo_is_ll=bool(d_htf.get("lo_is_ll", False)) if d_lo_fire else False,
        level_prefix="W",
    )


def _process_wave(state: StructureState, ctx: BarContext) -> None:
    """H1 wave state machine."""
    h1_edge = ctx.edges.get("H1", {})
    h1_htf = ctx.htf.get("H1", {})
    h1_hi_fire = bool(h1_edge.get("edge_hi_fire", False))
    h1_lo_fire = bool(h1_edge.get("edge_lo_fire", False))

    wave_sm_tick(
        state=state.wave_sm,
        hi_fire=h1_hi_fire,
        hi_ztop=h1_htf.get("ztop") if h1_hi_fire else None,
        hi_zbot=h1_htf.get("zbot") if h1_hi_fire else None,
        hi_is_hh=bool(h1_htf.get("hi_is_hh", False)) if h1_hi_fire else False,
        lo_fire=h1_lo_fire,
        lo_ztop=h1_htf.get("ztop") if h1_lo_fire else None,
        lo_zbot=h1_htf.get("zbot") if h1_lo_fire else None,
        lo_is_ll=bool(h1_htf.get("lo_is_ll", False)) if h1_lo_fire else False,
        bar_time=ctx.timestamp,
    )


def _process_ew(state: StructureState) -> None:
    """Elliott Wave classification (runs after wave SM)."""
    h1_tl = state.tl_states.get("H1")
    ew_classify_tick(state.ew, state.wave_sm, h1_tl_state=h1_tl)


def _process_xtf_trendlines(
    state: StructureState,
    ctx: BarContext,
    zone_states: dict | None,
    bus: EventBus | None,
) -> None:
    """Run cross-TF zone-anchored trendlines for W1, D1, H4."""
    if zone_states is None:
        return
    for parent_tf, xtf_state in state.xtf_tl_states.items():
        child_tf = XTF_ANCHOR_MAP.get(parent_tf)
        if not child_tf:
            continue
        child_zs = zone_states.get(child_tf)
        if child_zs is None:
            continue
        xtf_trendline_tick(
            state=xtf_state,
            parent_tf=parent_tf,
            child_supply_zones=child_zs.supply_zones,
            child_demand_zones=child_zs.demand_zones,
            bar_high=ctx.high,
            bar_low=ctx.low,
            bar_time=ctx.timestamp,
            bus=bus,
        )


def structure_tick(
    state: StructureState,
    ctx: BarContext,
    config: StructureConfig,
    d_supply_zones: list[FractalZone] | None = None,
    d_demand_zones: list[FractalZone] | None = None,
    bus: EventBus | None = None,
    zone_states: dict | None = None,
) -> None:
    """
    Process one bar through the structure engine.

    Runs trendline_tick for all TFs, cross-TF zone-anchored trendlines,
    structure counting for H4→D and D→W, H4 push phase, and H1 wave SM.

    Mutates ``state`` in place.
    """
    _process_trendlines(state, ctx, config, bus)
    _process_xtf_trendlines(state, ctx, zone_states, bus)
    _process_structure(state, ctx, d_supply_zones, d_demand_zones)
    _process_wave(state, ctx)
    _process_ew(state)


