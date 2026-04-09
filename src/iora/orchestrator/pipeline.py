"""
Pipeline — unified single-pass orchestration.

Orchestrates zone_engine_tick + structure_tick + cascade + HTF bias + macro bias + cycle
on each bar, returning all engine outputs in PipelineOutput.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import (
    MacroBiasState,
    StructuralCycleState,
    FractalZone,
    BarContext,
    EventID,
)
from iora.engine.structure_count import StructureCountState, H4PushPhaseState
from iora.engine.wave_sm import WaveSMState
from iora.engine.ew_classify import EWState
from iora.engine.events import EventBus
from iora.engine.macro_bias import MacroBiasTickState, macro_bias_tick
from iora.engine.cycle_sm import CycleTickState, cycle_tick
from iora.engine.trendline_tick import TrendlineTickState
from iora.engine.xtf_trendline import XTFTrendlineState
from iora.engine.early_cascade import (
    EarlyCascadeState,
    early_cascade_tick,
    inject_early_anchors,
)
from iora.engine.cascade_tracker import (
    CascadeTrackerState,
    CascadeSignal,
    init_cascade_state,
    cascade_tick,
    get_cascade_summary,
)
from iora.engine.htf_bias import (
    HTFBiasState,
    init_htf_bias_state,
    htf_bias_tick,
)
from iora.engine.cascade_state import (
    CascadePhaseState,
    cascade_state_tick,
)

from iora.orchestrator.zone_engine import (
    ZoneConfig,
    ZoneState,
    UBChainCounts,
    init_zone_state,
    zone_engine_tick,
)
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    PushZoneEngineState,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.orchestrator.structure_engine import (
    StructureConfig,
    StructureState,
    init_structure_state,
    structure_tick,
)
from iora.engine.wave_sm import get_wave_label

from iora.data.tf_alignment import TF_ORDER, build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars


@dataclass(slots=True)
class PipelineConfig:
    doji_pct: float = 5.0
    spread_buffer: float = 0.00010
    use_m1_tl_for_bias: bool = False
    cycle_on: bool = True
    macro_bias_on: bool = True
    # Inherited zone/structure config
    lookback: int = 30  # Keep more zones in memory for user-controlled display
    tl_history: int = 10
    ub_exhaust_threshold: int = 5
    push_zone_on: bool = False
    push_zone_max_age: dict[str, int] = field(default_factory=lambda: {
        "M1": 50, "M5": 50, "M15": 50, "H1": 50,
        "H4": 50, "D1": 50, "W1": 30, "MN1": 20,
    })
    period_history_depth: int = 3


@dataclass(slots=True)
class StructureBreak:
    """A BOS or CHOCH event from a zone break."""

    timestamp: pd.Timestamp  # When the break happened
    timeframe: str  # Zone TF (e.g. "H4")
    break_type: str  # "BOS" or "CHOCH"
    direction: str  # "bull" or "bear"
    level: float  # The price level that was broken
    zone_struct: str  # "HH", "LH", "LL", "HL"
    origin_time: pd.Timestamp | None = None
    zone_top: float = 0.0  # Full zone bounds for ghost rendering
    zone_bot: float = 0.0


@dataclass(slots=True)
class PipelineOutput:
    """Complete output from the unified pipeline."""

    # Macro bias
    macro_bias_state: MacroBiasState
    macro_bias: int  # convenience: -1/0/+1

    # Structural cycle
    cycle_state: StructuralCycleState
    cycle_label: str

    # Terminal exhaustion
    h1_sup_exhausted: bool
    h1_dem_exhausted: bool

    # UB chain (from zone engine)
    ub_chain: UBChainCounts

    # Structure breaks (BOS/CHOCH) per zone TF
    structure_breaks: list[StructureBreak] = field(default_factory=list)

    # --- Pass-through from zone engine + structure engine ---
    zones_by_tf: dict[str, list[FractalZone]] = field(default_factory=dict)
    nested_zones: dict[str, object] = field(default_factory=dict)
    tl_states: dict[str, TrendlineTickState] = field(default_factory=dict)
    xtf_tl_states: dict[str, XTFTrendlineState] = field(default_factory=dict)
    d_structure: StructureCountState | None = None
    w_structure: StructureCountState | None = None
    h4_push: H4PushPhaseState | None = None
    wave_sm: WaveSMState | None = None
    ew: EWState | None = None
    wave_label: str = ""
    ew_pattern: str = ""
    # --- Cascade tracker ---
    cascade_state: CascadeTrackerState | None = None
    cascade_signals: list[CascadeSignal] = field(default_factory=list)
    cascade_summary: dict = field(default_factory=dict)

    # --- HTF Bias cascade ---
    htf_bias: HTFBiasState | None = None

    # --- Push Zone Engine ---
    push_zones_by_tf: dict[str, list] = field(default_factory=dict)
    push_trend_by_tf: dict[str, int] = field(default_factory=dict)
    period_levels_by_tf: dict[str, dict] = field(default_factory=dict)

    # --- Cascade Phase (push-zone based) ---
    cascade_phase_state: CascadePhaseState | None = None
    cascade_phase: str = "unknown"


# ---------------------------------------------------------------------------
# Per-bar sub-functions (called in sequence from main loop)
# ---------------------------------------------------------------------------


def _classify_structure_breaks(
    bus: EventBus,
    ev_offset: int,
    structure_breaks: list[StructureBreak],
) -> None:
    """Scan new ZONE_BREAK events and classify as BOS or CHOCH."""
    for ev in bus.peek()[ev_offset:]:
        if ev.id != EventID.ZONE_BREAK:
            continue
        payload = ev.payload
        side = payload.get("side")  # "supply" or "demand"
        is_hh_or_ll = payload.get("is_hh_or_ll", False)

        if side == "supply":
            zone_struct = "HH" if is_hh_or_ll else "LH"
            break_type = "BOS" if is_hh_or_ll else "CHOCH"
            direction = "bull"
            level = payload.get("top", 0.0)
        else:
            zone_struct = "LL" if is_hh_or_ll else "HL"
            break_type = "BOS" if is_hh_or_ll else "CHOCH"
            direction = "bear"
            level = payload.get("bot", 0.0)

        raw_origin = payload.get("origin_time")
        origin_ts = pd.Timestamp(raw_origin) if raw_origin else None

        structure_breaks.append(
            StructureBreak(
                timestamp=ev.timestamp,
                timeframe=ev.timeframe,
                break_type=break_type,
                direction=direction,
                level=level,
                zone_struct=zone_struct,
                origin_time=origin_ts,
                zone_top=payload.get("top", 0.0),
                zone_bot=payload.get("bot", 0.0),
            )
        )


def _tick_structure_and_cascade(
    structure_state: StructureState,
    zone_state: ZoneState,
    cascade_state: CascadeTrackerState,
    htf_bias_state: HTFBiasState,
    ctx: BarContext,
    structure_config: StructureConfig,
    bus: EventBus,
    ev_offset: int,
) -> None:
    """Run structure tick, cascade tracker, and HTF bias cascade."""
    # D zones for structure engine h4_push cross-reference
    d_zs = zone_state.zone_states.get("D1")
    d_sup = d_zs.supply_zones if d_zs else []
    d_dem = d_zs.demand_zones if d_zs else []

    structure_tick(
        structure_state, ctx, structure_config,
        d_supply_zones=d_sup, d_demand_zones=d_dem, bus=bus,
        zone_states=zone_state.zone_states,
    )

    bar_events = bus.peek()[ev_offset:]
    cascade_tick(
        state=cascade_state,
        tl_states=structure_state.tl_states,
        zone_states=zone_state.zone_states,
        d_structure=structure_state.d_structure,
        w_structure=structure_state.w_structure,
        bar_close=ctx.close,
        bar_high=ctx.high,
        bar_low=ctx.low,
        bar_time=ctx.timestamp,
        events=bar_events,
    )

    htf_bias_tick(
        state=htf_bias_state,
        tl_states=structure_state.tl_states,
        zone_states=zone_state.zone_states,
        d_structure=structure_state.d_structure,
        w_structure=structure_state.w_structure,
        cascade_state=cascade_state,
        bar_close=ctx.close,
    )


def _tick_macro_bias(
    bias_state: MacroBiasTickState,
    structure_state: StructureState,
    zone_state: ZoneState,
    ctx: BarContext,
    bus: EventBus,
) -> None:
    """Run macro bias tick with extracted zone/TL params."""
    m5_tl = structure_state.tl_states.get("M5")
    h4_zs = zone_state.zone_states.get("H4")
    d_zs = zone_state.zone_states.get("D1")
    ub = zone_state.ub_chain

    macro_bias_tick(
        state=bias_state,
        m5_tl=m5_tl,
        h4_supply_zones=h4_zs.supply_zones if h4_zs else [],
        h4_demand_zones=h4_zs.demand_zones if h4_zs else [],
        d_supply_zones=d_zs.supply_zones if d_zs else [],
        d_demand_zones=d_zs.demand_zones if d_zs else [],
        close=ctx.close,
        bar_high=ctx.high,
        bar_low=ctx.low,
        bar_time=ctx.timestamp,
        h1_sup_exhausted=ub.h1_sup_exhausted,
        h1_dem_exhausted=ub.h1_dem_exhausted,
        bus=bus,
    )


def _tick_cycle(
    cycle_state_obj: CycleTickState,
    structure_state: StructureState,
    zone_state: ZoneState,
    ctx: BarContext,
    bus: EventBus,
) -> None:
    """Run cycle state machine tick with extracted params."""
    h4_tl = structure_state.tl_states.get("H4")
    h4_zs = zone_state.zone_states.get("H4")
    h1_zs = zone_state.zone_states.get("H1")
    ub = zone_state.ub_chain

    cycle_tick(
        state=cycle_state_obj,
        d_ll_count=structure_state.d_structure.ll_count,
        d_hh_count=structure_state.d_structure.hh_count,
        h4_demand_zones=h4_zs.demand_zones if h4_zs else [],
        h4_supply_zones=h4_zs.supply_zones if h4_zs else [],
        h1_supply_zones=h1_zs.supply_zones if h1_zs else [],
        h1_demand_zones=h1_zs.demand_zones if h1_zs else [],
        h4_bear_tl_broken=h4_tl.bear_broken if h4_tl else False,
        h4_bull_tl_broken=h4_tl.bull_broken if h4_tl else False,
        close=ctx.close,
        bar_time=ctx.timestamp,
        h1_sup_exhausted=ub.h1_sup_exhausted,
        h1_dem_exhausted=ub.h1_dem_exhausted,
        bus=bus,
    )


def _collect_outputs(
    zone_state: ZoneState,
    structure_state: StructureState,
    bias_state: MacroBiasTickState,
    cycle_state_obj: CycleTickState,
    cascade_state: CascadeTrackerState,
    htf_bias_state: HTFBiasState,
    structure_breaks: list[StructureBreak],
    tf_list: list[str],
    push_zone_state: PushZoneEngineState | None = None,
    cascade_phase_state: CascadePhaseState | None = None,
) -> PipelineOutput:
    """Assemble final PipelineOutput from all engine states."""
    zones_by_tf: dict[str, list[FractalZone]] = {}
    for tf in tf_list:
        zs = zone_state.zone_states[tf]
        zones_by_tf[tf] = list(zs.supply_zones) + list(zs.demand_zones)

    push_zones_by_tf: dict[str, list] = {}
    push_trend_by_tf: dict[str, int] = {}
    period_levels_by_tf: dict[str, dict] = {}
    if push_zone_state is not None:
        for tf, ts in push_zone_state.tick_states.items():
            push_zones_by_tf[tf] = list(ts.supply_zones) + list(ts.demand_zones)
            push_trend_by_tf[tf] = ts.trend
            period_levels_by_tf[tf] = {
                "highs": list(ts.period.prev_highs),
                "lows": list(ts.period.prev_lows),
            }

    return PipelineOutput(
        macro_bias_state=bias_state.to_model(),
        macro_bias=bias_state.macro_bias,
        cycle_state=cycle_state_obj.to_model(),
        cycle_label=cycle_state_obj.phase_label,
        h1_sup_exhausted=zone_state.ub_chain.h1_sup_exhausted,
        h1_dem_exhausted=zone_state.ub_chain.h1_dem_exhausted,
        ub_chain=zone_state.ub_chain,
        structure_breaks=structure_breaks,
        zones_by_tf=zones_by_tf,
        nested_zones=zone_state.nested_states,
        tl_states=dict(structure_state.tl_states),
        xtf_tl_states=dict(structure_state.xtf_tl_states),
        d_structure=structure_state.d_structure,
        w_structure=structure_state.w_structure,
        h4_push=structure_state.h4_push,
        wave_sm=structure_state.wave_sm,
        ew=structure_state.ew,
        wave_label=get_wave_label(structure_state.wave_sm),
        ew_pattern=structure_state.ew.name,
        cascade_state=cascade_state,
        cascade_signals=cascade_state.signals,
        cascade_summary=get_cascade_summary(cascade_state),
        htf_bias=htf_bias_state,
        push_zones_by_tf=push_zones_by_tf,
        push_trend_by_tf=push_trend_by_tf,
        period_levels_by_tf=period_levels_by_tf,
        cascade_phase_state=cascade_phase_state,
        cascade_phase=cascade_phase_state.phase if cascade_phase_state else "unknown",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_pipeline(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    config: PipelineConfig | None = None,
) -> PipelineOutput:
    """
    Full unified pipeline: zone_engine_tick + structure_tick + cascade + bias + cycle in one pass.

    Each bar runs the sub-functions in sequence:
      1. zone_engine_tick (zones + nested + UB chain)
      2. _classify_structure_breaks (BOS/CHOCH from zone break events)
      3. _tick_structure_and_cascade (TLs + structure + wave + cascade + HTF bias)
      4. _tick_macro_bias (optional)
      5. _tick_cycle (optional)
    """
    if config is None:
        config = PipelineConfig()

    zone_config = ZoneConfig(
        doji_pct=config.doji_pct,
        lookback=config.lookback,
        ub_exhaust_threshold=config.ub_exhaust_threshold,
    )
    structure_config = StructureConfig(
        doji_pct=config.doji_pct,
        lookback=config.lookback,
        tl_history=config.tl_history,
    )

    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf, config.doji_pct)
    base_df = data_by_tf[base_tf]
    tf_list = [tf for tf in TF_ORDER if tf in data_by_tf]

    # Initialize all states
    zone_state = init_zone_state(tf_list)
    structure_state = init_structure_state(tf_list)
    early_cascade_state = EarlyCascadeState()
    bias_state = MacroBiasTickState()
    cycle_state_obj = CycleTickState()
    cascade_state = init_cascade_state(tf_list)
    htf_bias_state = init_htf_bias_state()
    push_zone_state: PushZoneEngineState | None = None
    push_zone_config: PushZoneEngineConfig | None = None
    cascade_phase_state: CascadePhaseState | None = None
    if config.push_zone_on:
        push_zone_state = init_push_zone_state(tf_list, config.period_history_depth)
        push_zone_config = PushZoneEngineConfig(
            doji_pct=config.doji_pct,
            max_age=config.push_zone_max_age,
            period_history_depth=config.period_history_depth,
        )
        cascade_phase_state = CascadePhaseState()
    bus = EventBus()
    structure_breaks: list[StructureBreak] = []

    # Bar-by-bar iteration
    for ctx in iter_bars(base_df, aligned_df, tf_list):
        ev_offset = len(bus)

        zone_engine_tick(zone_state, ctx, zone_config, bus)
        _classify_structure_breaks(bus, ev_offset, structure_breaks)

        if push_zone_state is not None:
            push_zone_engine_tick(push_zone_state, ctx, push_zone_config, bus=bus)

            # Cascade phase tick: reads push zone trends + trendline breaks
            if cascade_phase_state is not None:
                cascade_state_tick(
                    cascade_phase_state,
                    push_zone_state.tick_states,
                    push_zone_state.tl_states,
                    push_zone_state.bar_tl_events,
                    ctx.close,
                )

        # Early cascade: detect parent-TF structural shifts via child-TF CHoCH
        # and inject early anchors into XTF trendlines BEFORE structure_tick
        early_anchors = early_cascade_tick(
            early_cascade_state, zone_state.zone_states, ctx.timestamp, bus,
        )
        if early_anchors:
            inject_early_anchors(early_anchors, structure_state.xtf_tl_states)

        _tick_structure_and_cascade(
            structure_state, zone_state, cascade_state, htf_bias_state,
            ctx, structure_config, bus, ev_offset,
        )
        if config.macro_bias_on:
            _tick_macro_bias(bias_state, structure_state, zone_state, ctx, bus)
        if config.cycle_on:
            _tick_cycle(cycle_state_obj, structure_state, zone_state, ctx, bus)

    return _collect_outputs(
        zone_state, structure_state, bias_state, cycle_state_obj,
        cascade_state, htf_bias_state, structure_breaks, tf_list,
        push_zone_state=push_zone_state,
        cascade_phase_state=cascade_phase_state,
    )
