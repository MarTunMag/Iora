"""
H4/D/W structural counting — HH/LL/LH/HL progression tracking.

Ports Pine S11 (canopy.pine lines 789-959).

Tracks consecutive HH/LL/LH/HL patterns from H4 pivots to derive
D-level phase (push/pull), and from D pivots to derive W-level phase.

H4 push phase tracks whether H4 supply hits D supply zone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import FractalZone


@dataclass(slots=True)
class StructureCountState:
    """
    Mutable state for one level of structural counting.
    E.g., H4→D or D→W.

    Tracks previous pivot levels and consecutive HH/LL/LH/HL counts.
    """

    prev_sup_top: float | None = None
    prev_dem_bot: float | None = None

    hh_count: int = 0
    ll_count: int = 0
    lh_count: int = 0
    hl_count: int = 0

    phase: str = "Unknown"


@dataclass(slots=True)
class H4PushPhaseState:
    """
    H4 push phase tracking — counts consecutive H4 pushes
    and detects when H4 supply/demand reaches D zone.
    """

    push_count: int = 0
    phase: str = "Unknown"
    at_d_zone: bool = False


def structure_count_tick(
    state: StructureCountState,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_is_hh: bool,
    lo_fire: bool,
    lo_zbot: float | None,
    lo_is_ll: bool,
    level_prefix: str = "D",
) -> None:
    """
    Process one bar for structural counting at a given level.

    For D-level counting, feed H4 pivot edges.
    For W-level counting, feed D pivot edges.

    Mutates ``state`` in place.
    """
    if hi_fire and hi_ztop is not None:
        if state.prev_sup_top is not None and hi_ztop > state.prev_sup_top:
            # HH
            state.hh_count += 1
            state.lh_count = 0
            state.ll_count = 0
            state.phase = f"{level_prefix} Push ^"
        elif state.prev_sup_top is not None:
            # LH
            state.lh_count += 1
            state.hh_count = 0
            state.phase = f"{level_prefix} Pull v"
        state.prev_sup_top = hi_ztop

    if lo_fire and lo_zbot is not None:
        if state.prev_dem_bot is not None and lo_zbot < state.prev_dem_bot:
            # LL
            state.ll_count += 1
            state.hl_count = 0
            state.hh_count = 0
            state.phase = f"{level_prefix} Push v"
        elif state.prev_dem_bot is not None:
            # HL
            state.hl_count += 1
            state.ll_count = 0
            state.phase = f"{level_prefix} Pull ^"
        state.prev_dem_bot = lo_zbot


def h4_push_phase_tick(
    state: H4PushPhaseState,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_zbot: float | None,
    lo_fire: bool,
    lo_ztop: float | None,
    lo_zbot: float | None,
    d_supply_zones: list[FractalZone] | None = None,
    d_demand_zones: list[FractalZone] | None = None,
) -> None:
    """
    Track H4 push phase — count consecutive H4 pivots and detect
    when H4 reaches D-level zone.

    Pine reference: canopy.pine lines 842-865.
    """
    if hi_fire and hi_ztop is not None:
        # Check if H4 supply is inside any D supply zone
        at_d = False
        if d_supply_zones:
            for dz in d_supply_zones:
                if hi_zbot is not None and hi_ztop <= dz.top and hi_zbot >= dz.bot:
                    at_d = True
                    break
        if at_d:
            state.phase = "H4 @ D SUP"
            state.at_d_zone = True
        else:
            state.push_count += 1
            state.phase = f"H4 Push {state.push_count}"
            state.at_d_zone = False

    if lo_fire and lo_zbot is not None:
        at_d = False
        if d_demand_zones:
            for dz in d_demand_zones:
                if lo_ztop is not None and lo_ztop <= dz.top and lo_zbot >= dz.bot:
                    at_d = True
                    break
        if at_d:
            state.phase = "H4 @ D DEM"
            state.at_d_zone = True
        else:
            state.push_count += 1
            state.phase = f"H4 Push {state.push_count}"
            state.at_d_zone = False
