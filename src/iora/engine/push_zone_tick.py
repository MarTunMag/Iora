# src/iora/engine/push_zone_tick.py
"""
Push zone tick — per-TF per-bar zone creation, break detection, push/reversal validation.

Pine reference: iora_push_zones_v2.pine S6 process() method.
Follows same pattern as zone_tick.py but adds push validation logic.
"""
from __future__ import annotations

from math import isnan, nan

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.events import EventBus
from iora.engine.models import EventID


def push_zone_tick(
    state: PushZoneTickState,
    close: float,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_zbot: float | None,
    hi_time: pd.Timestamp | None,
    hi_is_hh: bool,
    hi_txt: str,
    seq_hh: float,
    lo_fire: bool,
    lo_ztop: float | None,
    lo_zbot: float | None,
    lo_time: pd.Timestamp | None,
    lo_is_ll: bool,
    lo_txt: str,
    seq_ll: float,
    bar_time: pd.Timestamp,
    tf_seconds: int,
    max_age: int,
    timeframe: str = "",
    bus: EventBus | None = None,
) -> list[PushZone]:
    """
    Process one bar for a single TF. Mutates state in place.

    Returns list of broken zones (for event emission / diagnostics).

    Sequence (matches Pine process()):
      1. Zone expire + break detection (body-close)
      2. Zone creation (on fire with valid boundaries)
      3. Push validation (boundary-break rule)
      4. Reversal tagging
      5. BOS/CHoCH classification
    """
    SOFT_CAP: int = 30  # Max zones per side per TF
    broken: list[PushZone] = []

    # --- 1. Break detection (body-close only, no age expiry) ---
    for zones in (state.supply_zones, state.demand_zones):
        i: int = len(zones) - 1
        while i >= 0:
            z: PushZone = zones[i]
            is_broken: bool = close > z.top if z.is_supply else close < z.bottom
            if is_broken:
                broken.append(zones.pop(i))
            i -= 1

    # Track broken zones as breakers (flipped polarity)
    for bz in broken:
        if bz.is_supply:
            # Broken supply → demand breaker
            state.demand_breakers.append(bz)
            if len(state.demand_breakers) > state.MAX_BREAKERS_PER_SIDE:
                state.demand_breakers.pop(0)
        else:
            # Broken demand → supply breaker
            state.supply_breakers.append(bz)
            if len(state.supply_breakers) > state.MAX_BREAKERS_PER_SIDE:
                state.supply_breakers.pop(0)

    # Remove breaker zones that get broken themselves (body-close)
    state.supply_breakers = [
        b for b in state.supply_breakers if not (close > b.top)
    ]
    state.demand_breakers = [
        b for b in state.demand_breakers if not (close < b.bottom)
    ]

    # Emit break events
    if bus is not None:
        for bz in broken:
            bus.emit(
                EventID.ZONE_BREAK,
                timestamp=bar_time,
                timeframe=timeframe,
                payload={
                    "top": bz.top, "bot": bz.bottom,
                    "side": "supply" if bz.is_supply else "demand",
                    "is_push": bz.is_push, "is_reversal": bz.is_reversal,
                    "origin_time": bz.origin_time,
                },
            )

    # --- 2. Zone creation ---
    if hi_fire and hi_ztop is not None and hi_zbot is not None and hi_ztop > hi_zbot:
        origin: pd.Timestamp = hi_time if hi_time is not None else bar_time
        state.sup_count += 1
        z = PushZone(
            top=hi_ztop,
            bottom=hi_zbot,
            is_supply=True,
            origin_time=origin,
            timeframe=timeframe,
            swing_cls=hi_txt,
            count_num=state.sup_count,
        )
        state.supply_zones.append(z)
        # Soft cap: evict oldest if exceeded
        while len(state.supply_zones) > SOFT_CAP:
            state.supply_zones.pop(0)
        if bus is not None:
            bus.emit(
                EventID.ZONE_FIRE,
                timestamp=bar_time,
                timeframe=timeframe,
                payload={
                    "top": z.top, "bot": z.bottom,
                    "side": "supply", "swing_cls": hi_txt,
                },
            )

    if lo_fire and lo_ztop is not None and lo_zbot is not None and lo_ztop > lo_zbot:
        origin = lo_time if lo_time is not None else bar_time
        state.dem_count += 1
        z = PushZone(
            top=lo_ztop,
            bottom=lo_zbot,
            is_supply=False,
            origin_time=origin,
            timeframe=timeframe,
            swing_cls=lo_txt,
            count_num=state.dem_count,
        )
        state.demand_zones.append(z)
        # Soft cap: evict oldest if exceeded
        while len(state.demand_zones) > SOFT_CAP:
            state.demand_zones.pop(0)
        if bus is not None:
            bus.emit(
                EventID.ZONE_FIRE,
                timestamp=bar_time,
                timeframe=timeframe,
                payload={
                    "top": z.top, "bot": z.bottom,
                    "side": "demand", "swing_cls": lo_txt,
                },
            )

    # --- 3-5. Push validation, reversal, BOS/CHoCH ---
    _push_validate(state, hi_fire, hi_txt, seq_hh, lo_fire, lo_txt, seq_ll, timeframe)

    return broken


def _push_validate(
    state: PushZoneTickState,
    hi_fire: bool,
    hi_txt: str,
    seq_hh: float,
    lo_fire: bool,
    lo_txt: str,
    seq_ll: float,
    timeframe: str = "",
) -> None:
    """Push validation + reversal tagging + BOS/CHoCH classification + zone attribution.

    Pine reference: iora_push_zones_v2.pine lines 301-363.

    Zone attribution (Level 4): When a BOS/CHoCH is classified, tag the last-created
    zone on the OPPOSITE side as the "causing zone". This identifies reversal targets:
    "the H1 zone that caused the H4 CHoCH".
    """
    # Bearish push: demand fires with LL -> tag most recent supply as PUSH
    if lo_fire and lo_txt == "LL":
        boundary_ok: bool = isnan(state.prev_push_extreme_lo) or seq_ll < state.prev_push_extreme_lo
        if boundary_ok:
            struct_cls = _classify_struct(state.trend, is_bullish_push=False)
            # Tag most recent supply as PUSH
            for i in range(len(state.supply_zones) - 1, -1, -1):
                z: PushZone = state.supply_zones[i]
                z.is_push = True
                z.struct_cls = struct_cls
                break
            # Tag most recent demand as REVERSAL (trigger zone)
            for i in range(len(state.demand_zones) - 1, -1, -1):
                z = state.demand_zones[i]
                z.is_reversal = True
                break
            # Zone attribution: the causing zone is the last supply (push direction)
            if struct_cls in ("BOS", "CHoCH") and state.supply_zones:
                causing = state.supply_zones[-1]
                causing.caused_bos_choch = struct_cls
                causing.caused_event_tf = timeframe
            state.prev_push_extreme_lo = seq_ll

    # Bullish push: supply fires with HH -> tag most recent demand as PUSH
    if hi_fire and hi_txt == "HH":
        boundary_ok = isnan(state.prev_push_extreme_hi) or seq_hh > state.prev_push_extreme_hi
        if boundary_ok:
            struct_cls = _classify_struct(state.trend, is_bullish_push=True)
            # Tag most recent demand as PUSH
            for i in range(len(state.demand_zones) - 1, -1, -1):
                z = state.demand_zones[i]
                z.is_push = True
                z.struct_cls = struct_cls
                break
            # Tag most recent supply as REVERSAL (trigger zone)
            for i in range(len(state.supply_zones) - 1, -1, -1):
                z = state.supply_zones[i]
                z.is_reversal = True
                break
            # Zone attribution: the causing zone is the last demand (push direction)
            if struct_cls in ("BOS", "CHoCH") and state.demand_zones:
                causing = state.demand_zones[-1]
                causing.caused_bos_choch = struct_cls
                causing.caused_event_tf = timeframe
            state.prev_push_extreme_hi = seq_hh


def _classify_struct(trend: int, is_bullish_push: bool) -> str:
    """BOS/CHoCH classification based on push direction vs trend."""
    if trend == 0:
        return ""
    if is_bullish_push:
        return "BOS" if trend == 1 else "CHoCH"
    else:
        return "BOS" if trend == -1 else "CHoCH"
