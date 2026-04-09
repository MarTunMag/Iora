"""
Push zone engine — multi-TF orchestration for push zone detection.

Calls push_zone_tick() per TF per bar. Handles:
  - Period tracking + trend state updates
  - Zone count resets (parent fire + HH/LL structural invalidation)
  - Nesting detection + terminal classification

Pine reference: iora_push_zones_v2.pine (S8-S9)
Pattern: follows zone_engine.py orchestration style
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan, nan

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState, PeriodTracker
from iora.engine.push_zone_tick import push_zone_tick
from iora.engine.push_trendline import (
    PushTrendlineState,
    PushTrendlineBreakEvent,
    push_trendline_tick,
)
from iora.engine.fvg_tick import FVGState, FVGEvent, fvg_tick
from iora.engine.structural_fvg import (
    StructuralFVGState,
    StructuralFVGEvent,
    structural_fvg_tick,
)
from iora.engine.events import EventBus
from iora.engine.models import BarContext
from iora.constants import TF_ORDER
from iora.diagnostics.period_pattern import compute_period_pattern


# TF label → seconds per bar
_TF_SECONDS: dict[str, int] = {
    "M1": 60, "M5": 300, "M15": 900, "H1": 3600,
    "H4": 14400, "D1": 86400, "W1": 604800, "MN1": 2592000,
}

# Parent TF mapping for nesting detection
# Matches Pine tf_parent(): M1→M15, M5→H1, M15→H1, H1→H4, H4→D1, D1→W1, W1→MN1
_PARENT_TF: dict[str, str] = {
    "M1": "M15", "M5": "H1", "M15": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1", "W1": "MN1",
}


@dataclass(slots=True)
class PushZoneEngineConfig:
    doji_pct: float = 5.0
    max_age: dict[str, int] = field(default_factory=lambda: {
        "M1": 50, "M5": 50, "M15": 50, "H1": 50,
        "H4": 50, "D1": 50, "W1": 30, "MN1": 20,
    })
    period_history_depth: int = 3


@dataclass(slots=True)
class PushZoneEngineState:
    tick_states: dict[str, PushZoneTickState] = field(default_factory=dict)
    tl_states: dict[str, PushTrendlineState] = field(default_factory=dict)
    fvg_states: dict[str, FVGState] = field(default_factory=dict)
    structural_fvg_states: dict[str, StructuralFVGState] = field(default_factory=dict)
    bar_idx: int = 0
    bar_tl_events: dict[str, list[PushTrendlineBreakEvent]] = field(default_factory=dict)


def init_push_zone_state(
    tf_list: list[str] | None = None,
    period_depth: int = 3,
) -> PushZoneEngineState:
    if tf_list is None:
        tf_list = list(TF_ORDER)
    tick_states = {}
    tl_states = {}
    fvg_states = {}
    structural_fvg_states = {}
    for tf in tf_list:
        ts = PushZoneTickState()
        ts.period = PeriodTracker(history_depth=period_depth)
        tick_states[tf] = ts
        tl_states[tf] = PushTrendlineState()
        fvg_states[tf] = FVGState()
    # Structural FVG: one state per HTF→LTF pair
    _SFVG_PAIRS = [
        ("D1", "H4"), ("H4", "H1"), ("H1", "M15"), ("M15", "M5"), ("M5", "M1"),
    ]
    for htf, ltf in _SFVG_PAIRS:
        if htf in tick_states and ltf in tick_states:
            key = f"{htf}>{ltf}"
            st = StructuralFVGState()
            st.htf = htf
            st.ltf = ltf
            structural_fvg_states[key] = st
    return PushZoneEngineState(
        tick_states=tick_states, tl_states=tl_states,
        fvg_states=fvg_states, structural_fvg_states=structural_fvg_states,
    )


def _check_nesting(
    child: PushZone,
    parent_zones: list[PushZone],
) -> PushZone | None:
    """Find the tightest parent zone containing the child. Returns None if no nesting."""
    best: PushZone | None = None
    best_range = float("inf")
    for p in parent_zones:
        if child.top <= p.top and child.bottom >= p.bottom:
            pr = p.top - p.bottom
            if pr < best_range:
                best_range = pr
                best = p
    return best


def _detect_retests(
    ts: PushZoneTickState,
    high: float,
    low: float,
    close: float,
    bar_time: pd.Timestamp,
) -> None:
    """Check all active zones for retest events. Mutates zones in place.

    A retest is: wick enters zone but close stays outside (not a break).
    - Demand: low <= zone.top AND close > zone.bottom
    - Supply: high >= zone.bottom AND close < zone.top
    """
    for z in ts.demand_zones:
        if low <= z.top and close > z.bottom:
            z.test_count += 1
            if z.first_test_time is None:
                z.first_test_time = bar_time

    for z in ts.supply_zones:
        if high >= z.bottom and close < z.top:
            z.test_count += 1
            if z.first_test_time is None:
                z.first_test_time = bar_time


def _update_replacement_counts(
    ts: PushZoneTickState,
    new_supply: bool,
    new_demand: bool,
) -> None:
    """Increment replacement_count on existing zones when new same-side zone fires."""
    if new_supply:
        for z in ts.supply_zones[:-1]:  # All except the newest (last)
            z.replacement_count += 1
    if new_demand:
        for z in ts.demand_zones[:-1]:
            z.replacement_count += 1


def _enrich_birth_metadata(
    zone: PushZone,
    ts: PushZoneTickState,
    close: float,
) -> None:
    """Enrich a newly created zone with birth context metadata."""
    zone.birth_period_pattern = compute_period_pattern(
        ts.period.prev_highs, ts.period.prev_lows,
    )
    zone_mid = (zone.top + zone.bottom) / 2.0
    zone.birth_price_distance = abs(zone_mid - close)


def push_zone_engine_tick(
    state: PushZoneEngineState,
    ctx: BarContext,
    config: PushZoneEngineConfig,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar through the push zone engine for all TFs.

    Sequence per TF (HIGH→LOW order for parent-before-child):
      1. Period tracking + trend update
      2. Count reset (parent fire + HH/LL invalidation)
      3. push_zone_tick() (expire, break, create, push validate)
      4. Nesting detection + terminal classification
    """
    close = ctx.close
    high = ctx.high
    low = ctx.low
    bar_time = ctx.timestamp
    state.bar_idx += 1
    state.bar_tl_events = {}

    # Process HIGH→LOW so parents populate before children
    tf_list = [tf for tf in reversed(TF_ORDER) if tf in state.tick_states]

    for tf in tf_list:
        ts = state.tick_states[tf]
        htf_data = ctx.htf.get(tf, {})
        edge_data = ctx.edges.get(tf, {})

        # --- 1. Period tracking ---
        _update_period(ts, tf, high, low, bar_time, htf_data)

        # --- 2. Count reset ---
        hi_fire = bool(edge_data.get("edge_hi_fire", False))
        lo_fire = bool(edge_data.get("edge_lo_fire", False))

        hi_txt = str(htf_data.get("hi_txt", ""))
        lo_txt = str(htf_data.get("lo_txt", ""))

        # Reset on HH/LL structural invalidation
        if hi_fire and hi_txt == "HH":
            ts.sup_count = 0
            ts.sup_reset_time = bar_time
        if lo_fire and lo_txt == "LL":
            ts.dem_count = 0
            ts.dem_reset_time = bar_time

        # Reset on parent fire (same-side)
        parent_tf = _PARENT_TF.get(tf)
        if parent_tf and parent_tf in state.tick_states:
            parent_edges = ctx.edges.get(parent_tf, {})
            p_hi_fire = bool(parent_edges.get("edge_hi_fire", False))
            p_lo_fire = bool(parent_edges.get("edge_lo_fire", False))
            if p_hi_fire:
                ts.sup_count = 0
                ts.sup_reset_time = bar_time
            if p_lo_fire:
                ts.dem_count = 0
                ts.dem_reset_time = bar_time

        # --- 3. push_zone_tick ---
        hi_ztop = htf_data.get("ztop") if hi_fire else None
        hi_zbot = htf_data.get("zbot") if hi_fire else None
        hi_time_raw = htf_data.get("hi_time")
        hi_time = pd.Timestamp(hi_time_raw) if hi_time_raw is not None else None
        hi_is_hh = bool(htf_data.get("hi_is_hh", False))
        seq_hh_raw = htf_data.get("seq_hh")
        seq_hh = float(seq_hh_raw) if seq_hh_raw is not None else nan

        lo_ztop = htf_data.get("ztop") if lo_fire else None
        lo_zbot = htf_data.get("zbot") if lo_fire else None
        lo_time_raw = htf_data.get("lo_time")
        lo_time = pd.Timestamp(lo_time_raw) if lo_time_raw is not None else None
        lo_is_ll = bool(htf_data.get("lo_is_ll", False))
        seq_ll_raw = htf_data.get("seq_ll")
        seq_ll = float(seq_ll_raw) if seq_ll_raw is not None else nan

        tf_seconds = _TF_SECONDS.get(tf, 3600)
        max_age = config.max_age.get(tf, 50)

        push_zone_tick(
            state=ts,
            close=close,
            hi_fire=hi_fire, hi_ztop=hi_ztop, hi_zbot=hi_zbot,
            hi_time=hi_time, hi_is_hh=hi_is_hh, hi_txt=hi_txt, seq_hh=seq_hh,
            lo_fire=lo_fire, lo_ztop=lo_ztop, lo_zbot=lo_zbot,
            lo_time=lo_time, lo_is_ll=lo_is_ll, lo_txt=lo_txt, seq_ll=seq_ll,
            bar_time=bar_time, tf_seconds=tf_seconds, max_age=max_age,
            timeframe=tf, bus=bus,
        )

        # --- 3.5. Retest detection + replacement counting ---
        new_supply = hi_fire and hi_ztop is not None and hi_zbot is not None and hi_ztop > hi_zbot
        new_demand = lo_fire and lo_ztop is not None and lo_zbot is not None and lo_ztop > lo_zbot
        _update_replacement_counts(ts, new_supply, new_demand)
        _detect_retests(ts, high, low, close, bar_time)

        # --- 3.6. Enrich birth metadata on newly created zones ---
        if new_supply and ts.supply_zones:
            _enrich_birth_metadata(ts.supply_zones[-1], ts, close)
        if new_demand and ts.demand_zones:
            _enrich_birth_metadata(ts.demand_zones[-1], ts, close)

        # --- 4. Nesting detection ---
        if (hi_fire or lo_fire) and parent_tf and parent_tf in state.tick_states:
            parent_ts = state.tick_states[parent_tf]
            parent_all = parent_ts.supply_zones + parent_ts.demand_zones
            zones_to_check = []
            if hi_fire and ts.supply_zones:
                zones_to_check.append(ts.supply_zones[-1])
            if lo_fire and ts.demand_zones:
                zones_to_check.append(ts.demand_zones[-1])

            for child in zones_to_check:
                parent = _check_nesting(child, parent_all)
                if parent is not None and child.is_supply != parent.is_supply:
                    child.is_terminal = True

        # --- 5. Push trendline detection ---
        tl_state = state.tl_states.get(tf)
        if tl_state is not None:
            tl_events = push_trendline_tick(
                state=tl_state,
                bar_idx=state.bar_idx,
                bar_high=high,
                bar_low=low,
                bar_close=close,
                prev_highs=ts.period.prev_highs,
                prev_lows=ts.period.prev_lows,
                trend=ts.trend,
                break_mode="close",
                tf=tf,
            )
            if tl_events:
                state.bar_tl_events[tf] = tl_events

        # --- 6. FVG detection (candle FVGs) ---
        fvg_state = state.fvg_states.get(tf)
        if fvg_state is not None:
            fvg_tick(
                state=fvg_state,
                bar_high=high,
                bar_low=low,
                bar_idx=state.bar_idx,
                timestamp=bar_time,
                tf=tf,
            )

    # --- 7. Structural FVG detection (per HTF→LTF pair, after all TFs updated) ---
    for key, sfvg_st in state.structural_fvg_states.items():
        htf_ts = state.tick_states.get(sfvg_st.htf)
        ltf_ts = state.tick_states.get(sfvg_st.ltf)
        if htf_ts is not None and ltf_ts is not None:
            structural_fvg_tick(
                state=sfvg_st,
                htf_prev_highs=htf_ts.period.prev_highs,
                htf_prev_lows=htf_ts.period.prev_lows,
                ltf_prev_highs=ltf_ts.period.prev_highs,
                ltf_prev_lows=ltf_ts.period.prev_lows,
                bar_high=high,
                bar_low=low,
                bar_idx=state.bar_idx,
            )


def _update_period(
    ts: PushZoneTickState,
    tf: str,
    high: float,
    low: float,
    bar_time: pd.Timestamp,
    htf_data: dict,
) -> None:
    """Update period tracker and trend state for one TF."""
    pt = ts.period

    is_new_period = bool(htf_data.get("new_period", False))
    if is_new_period:
        pt.rotate(bar_time)

    # Track current period hi/lo
    if isnan(pt.cur_hi) or high >= pt.cur_hi:
        pt.cur_hi = high
        pt.cur_hi_time = bar_time
    if isnan(pt.cur_lo) or low <= pt.cur_lo:
        pt.cur_lo = low
        pt.cur_lo_time = bar_time

    # Break detection (wick-based)
    if pt.prev_highs and pt.hi_brk_time is None:
        if high > pt.prev_highs[0]:
            pt.hi_brk_time = bar_time
            ts.trend = 1
    if pt.prev_lows and pt.lo_brk_time is None:
        if low < pt.prev_lows[0]:
            pt.lo_brk_time = bar_time
            ts.trend = -1
