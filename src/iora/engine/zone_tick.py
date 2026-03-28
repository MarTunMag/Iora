"""
Pine-parity zone_tick() engine.

Ports the Pine zone_tick() function from spring_leaf_grove.pine (S6-S7).
Manages per-TF zone arrays: creation on pivot fire, break detection on
close-based crossing, immediate removal of broken zones, two-pass trimming
(hard lookback + visual max_zones).

Pine reference (grove.pine lines 266-399):
  - Break detection: iterate zones in reverse, close > top (supply) / close < bot (demand)
  - Broken zones removed from active array immediately
  - Supply creation: on hi_fire edge, FractalZone(top=ztop, bot=zbot, is_supply=True, ...)
  - Demand creation: on lo_fire edge, FractalZone(top=ztop, bot=zbot, is_supply=False, ...)
  - Pass 1 (hard trim): oldest zones deleted when count > lookback
  - Pass 2 (visual trim): zones beyond max_zones hidden (box deleted) but kept for scans
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import FractalZone, EventID
from iora.engine.events import EventBus


@dataclass(slots=True)
class ZoneTickState:
    """
    Mutable per-TF state for zone_tick. Mirrors Pine's `var` arrays.

    supply_zones / demand_zones hold active (unbroken) FractalZone objects.
    seq_sup / seq_dem are monotonic counters for structural sequencing.
    """

    supply_zones: list[FractalZone] = field(default_factory=list)
    demand_zones: list[FractalZone] = field(default_factory=list)
    seq_sup: int = 0
    seq_dem: int = 0


def zone_tick(
    state: ZoneTickState,
    close: float,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_zbot: float | None,
    hi_time: pd.Timestamp | None,
    hi_is_hh: bool,
    lo_fire: bool,
    lo_ztop: float | None,
    lo_zbot: float | None,
    lo_time: pd.Timestamp | None,
    lo_is_ll: bool,
    lookback: int = 10,
    max_zones: int = 1,
    timeframe: str = "",
    bar_time: pd.Timestamp | None = None,
    bus: EventBus | None = None,
) -> tuple[list[FractalZone], list[FractalZone]]:
    """
    Process one bar for a single TF's zone arrays.

    Mutates ``state`` in place. Returns (broken_supply, broken_demand) lists
    of zones broken on this bar (for downstream BOS/CHoCH logic).

    Args:
        state:      Mutable ZoneTickState for this TF.
        close:      Current bar's close price (base TF).
        hi_fire:    True if a supply pivot edge fired this bar.
        hi_ztop:    Zone top for the new supply zone.
        hi_zbot:    Zone bottom for the new supply zone.
        hi_time:    Origin timestamp of the supply pivot.
        hi_is_hh:   True if this is a Higher High (HH), else LH.
        lo_fire:    True if a demand pivot edge fired this bar.
        lo_ztop:    Zone top for the new demand zone.
        lo_zbot:    Zone bottom for the new demand zone.
        lo_time:    Origin timestamp of the demand pivot.
        lo_is_ll:   True if this is a Lower Low (LL), else HL.
        lookback:   Hard array size limit per side.
        max_zones:  Visual display limit per side (zones beyond hidden).
        timeframe:  TF label for event metadata.
        bar_time:   Current bar timestamp for events.
        bus:        Optional EventBus for emitting ZONE_FIRE/ZONE_BREAK.
    """
    broken_supply: list[FractalZone] = []
    broken_demand: list[FractalZone] = []

    # ------------------------------------------------------------------
    # 1. Break detection — iterate in reverse (newest first)
    # ------------------------------------------------------------------
    # Supply zones: broken when close > zone.top
    i = len(state.supply_zones) - 1
    while i >= 0:
        z = state.supply_zones[i]
        if close > z.top:
            z.is_broken = True
            broken_supply.append(z)
            state.supply_zones.pop(i)
            if bus is not None and bar_time is not None:
                bus.emit(
                    EventID.ZONE_BREAK,
                    bar_time,
                    timeframe,
                    {
                        "side": "supply",
                        "top": z.top,
                        "bot": z.bot,
                        "is_hh_or_ll": z.is_hh_or_ll,
                        "origin_time": str(z.origin_time),
                    },
                )
        i -= 1

    # Demand zones: broken when close < zone.bot
    i = len(state.demand_zones) - 1
    while i >= 0:
        z = state.demand_zones[i]
        if close < z.bot:
            z.is_broken = True
            broken_demand.append(z)
            state.demand_zones.pop(i)
            if bus is not None and bar_time is not None:
                bus.emit(
                    EventID.ZONE_BREAK,
                    bar_time,
                    timeframe,
                    {
                        "side": "demand",
                        "top": z.top,
                        "bot": z.bot,
                        "is_hh_or_ll": z.is_hh_or_ll,
                        "origin_time": str(z.origin_time),
                    },
                )
        i -= 1

    # ------------------------------------------------------------------
    # 2. Supply zone creation on hi_fire edge
    # ------------------------------------------------------------------
    if hi_fire and hi_ztop is not None and hi_zbot is not None:
        state.seq_sup += 1
        new_zone = FractalZone(
            top=hi_ztop,
            bot=hi_zbot,
            is_supply=True,
            is_hh_or_ll=hi_is_hh,
            origin_time=hi_time if hi_time is not None else (bar_time or pd.NaT),
            seq_num=state.seq_sup,
        )
        state.supply_zones.append(new_zone)

        if bus is not None and bar_time is not None:
            bus.emit(
                EventID.ZONE_FIRE,
                bar_time,
                timeframe,
                {
                    "side": "supply",
                    "top": hi_ztop,
                    "bot": hi_zbot,
                    "is_hh": hi_is_hh,
                    "seq": state.seq_sup,
                },
            )

        # Pass 1: hard trim — oldest first until count <= lookback
        if len(state.supply_zones) > lookback:
            state.supply_zones[:] = state.supply_zones[-lookback:]

    # ------------------------------------------------------------------
    # 3. Demand zone creation on lo_fire edge
    # ------------------------------------------------------------------
    if lo_fire and lo_ztop is not None and lo_zbot is not None:
        state.seq_dem += 1
        new_zone = FractalZone(
            top=lo_ztop,
            bot=lo_zbot,
            is_supply=False,
            is_hh_or_ll=lo_is_ll,
            origin_time=lo_time if lo_time is not None else (bar_time or pd.NaT),
            seq_num=state.seq_dem,
        )
        state.demand_zones.append(new_zone)

        if bus is not None and bar_time is not None:
            bus.emit(
                EventID.ZONE_FIRE,
                bar_time,
                timeframe,
                {
                    "side": "demand",
                    "top": lo_ztop,
                    "bot": lo_zbot,
                    "is_ll": lo_is_ll,
                    "seq": state.seq_dem,
                },
            )

        # Pass 1: hard trim
        if len(state.demand_zones) > lookback:
            state.demand_zones[:] = state.demand_zones[-lookback:]

    return broken_supply, broken_demand


def get_visible_zones(
    state: ZoneTickState,
    max_zones: int = 1,
) -> tuple[list[FractalZone], list[FractalZone]]:
    """
    Return the most recent ``max_zones`` supply and demand zones
    (Pass 2 visual trim). Does not mutate state — zones beyond max_zones
    are still in the array for structural scans.
    """
    vis_sup = (
        state.supply_zones[-max_zones:]
        if len(state.supply_zones) > max_zones
        else list(state.supply_zones)
    )
    vis_dem = (
        state.demand_zones[-max_zones:]
        if len(state.demand_zones) > max_zones
        else list(state.demand_zones)
    )
    return vis_sup, vis_dem


def get_all_zones(state: ZoneTickState) -> list[FractalZone]:
    """Return all active (unbroken) zones from both sides."""
    return list(state.supply_zones) + list(state.demand_zones)
