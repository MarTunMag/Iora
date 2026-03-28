"""
Zone engine — HA supply/demand zone detection + nesting + UB chain counts.

Pine reference:
  ha_supply_demand_zones.pine (lives at C:\\Oriz\\tw_indicators\\ — separate TradingView project)

Orchestrates:
  - zone_tick() per 7 TFs (M1, M5, M15, H1, H4, D, W)
  - 8 nested zone combo checks
  - UB chain counting (unbroken zone counts per TF)
  - Bias-based zone visibility (macro_bias input)

Data flow:
  Parquet → compute_pivot_events() per TF (vectorized)
  → build_aligned_multi_tf() (merge_asof, no lookahead)
  → iter_bars() → zone_tick() per bar → zone arrays + nesting + UB chain
"""

from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd

from iora.engine.models import FractalZone, BarContext
from iora.engine.events import EventBus
from iora.engine.zone_tick import (
    ZoneTickState,
    zone_tick,
    get_visible_zones,
    get_all_zones,
)
from iora.engine.nested_zones import (
    NestedZoneState,
    NestedCombo,
    NESTED_COMBOS,
    run_nested_combos,
)
from iora.data.tf_alignment import TF_ORDER

# TF label → Pine max_zones default
_DEFAULT_MAX_ZONES: dict[str, int] = {
    "M1": 1,
    "M5": 1,
    "M15": 1,
    "H1": 1,
    "H4": 1,
    "D1": 2,
    "W1": 2,
}


@dataclass(slots=True)
class ZoneConfig:
    doji_pct: float = 5.0
    lookback: int = 10
    max_zones: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_MAX_ZONES))
    enabled_nested: set[str] = field(
        default_factory=lambda: {c.label for c in NESTED_COMBOS if c.default_on}
    )
    max_nested_per_combo: int = 2
    ub_exhaust_threshold: int = 5


@dataclass(slots=True)
class UBChainCounts:
    """Unbroken zone counts per TF (live recount every bar)."""

    h1_sup: int = 0
    h1_dem: int = 0
    h4_sup: int = 0
    h4_dem: int = 0
    d_sup: int = 0
    d_dem: int = 0
    h1_sup_exhausted: bool = False
    h1_dem_exhausted: bool = False


@dataclass(slots=True)
class ZoneState:
    """
    Full mutable state for the zone engine across all TFs.
    """

    zone_states: dict[str, ZoneTickState] = field(default_factory=dict)
    nested_states: dict[str, NestedZoneState] = field(default_factory=dict)
    ub_chain: UBChainCounts = field(default_factory=UBChainCounts)


def init_zone_state(tf_list: list[str] | None = None) -> ZoneState:
    """Create a fresh ZoneState with ZoneTickState per TF."""
    if tf_list is None:
        tf_list = list(TF_ORDER)
    zone_states = {tf: ZoneTickState() for tf in tf_list}
    nested_states: dict[str, NestedZoneState] = {}
    return ZoneState(zone_states=zone_states, nested_states=nested_states)


def zone_engine_tick(
    state: ZoneState,
    ctx: BarContext,
    config: ZoneConfig,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar through the zone engine.

    For each TF present in ctx.edges, if an edge fires (new HTF pivot),
    call zone_tick with the pivot data. Break detection runs every bar
    for all TFs. Nested combos run after all TF zone_ticks.

    Mutates ``state`` in place.
    """
    close = ctx.close

    for tf in state.zone_states:
        htf_data = ctx.htf.get(tf, {})
        edge_data = ctx.edges.get(tf, {})

        # Edge-fired pivot flags
        hi_fire = bool(edge_data.get("edge_hi_fire", False))
        lo_fire = bool(edge_data.get("edge_lo_fire", False))

        # Pivot data (only meaningful when fire is True, but zone_tick
        # guards on fire flags)
        hi_ztop = htf_data.get("ztop") if hi_fire else None
        hi_zbot = htf_data.get("zbot") if hi_fire else None
        hi_time_raw = htf_data.get("hi_time")
        hi_time = pd.Timestamp(hi_time_raw) if hi_time_raw is not None else None
        hi_is_hh = bool(htf_data.get("hi_is_hh", False))

        lo_ztop = htf_data.get("ztop") if lo_fire else None
        lo_zbot = htf_data.get("zbot") if lo_fire else None
        lo_time_raw = htf_data.get("lo_time")
        lo_time = pd.Timestamp(lo_time_raw) if lo_time_raw is not None else None
        lo_is_ll = bool(htf_data.get("lo_is_ll", False))

        max_z = config.max_zones.get(tf, 1)

        zone_tick(
            state=state.zone_states[tf],
            close=close,
            hi_fire=hi_fire,
            hi_ztop=hi_ztop,
            hi_zbot=hi_zbot,
            hi_time=hi_time,
            hi_is_hh=hi_is_hh,
            lo_fire=lo_fire,
            lo_ztop=lo_ztop,
            lo_zbot=lo_zbot,
            lo_time=lo_time,
            lo_is_ll=lo_is_ll,
            lookback=config.lookback,
            max_zones=max_z,
            timeframe=tf,
            bar_time=ctx.timestamp,
            bus=bus,
        )

    # Nested combo checks (after all TF zone_ticks)
    if config.enabled_nested:
        run_nested_combos(
            zone_states=state.zone_states,
            nested_states=state.nested_states,
            close=close,
            enabled_combos=config.enabled_nested,
            max_nested=config.max_nested_per_combo,
            bar_time=ctx.timestamp,
            bus=bus,
        )

    # UB chain recount (live every bar)
    _recount_ub_chain(state, config.ub_exhaust_threshold)


def _recount_ub_chain(state: ZoneState, threshold: int) -> None:
    """Recount unbroken zones for H1/H4/D (Pine S14 lines 797-816)."""
    ub = state.ub_chain

    h1 = state.zone_states.get("H1")
    if h1:
        ub.h1_sup = len(h1.supply_zones)
        ub.h1_dem = len(h1.demand_zones)
        ub.h1_sup_exhausted = ub.h1_sup >= threshold
        ub.h1_dem_exhausted = ub.h1_dem >= threshold

    h4 = state.zone_states.get("H4")
    if h4:
        ub.h4_sup = len(h4.supply_zones)
        ub.h4_dem = len(h4.demand_zones)

    d = state.zone_states.get("D1")
    if d:
        ub.d_sup = len(d.supply_zones)
        ub.d_dem = len(d.demand_zones)


