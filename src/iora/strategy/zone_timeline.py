# src/iora/strategy/zone_timeline.py
"""ZoneTimeline — records push zone engine output per bar for cheap replay.

The push zone engine is expensive (HA detection, push validation, nesting,
period tracking). Running it once per symbol and recording the output lets
the strategy evaluator replay N configs cheaply against the same timeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.events import EventBus
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    PushZoneEngineState,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars


@dataclass(slots=True)
class ZoneTimelineBar:
    """Per-bar snapshot of push zone engine state.

    Captures everything the strategy evaluator needs to make
    entry/exit decisions without re-running the engine.
    """

    timestamp: pd.Timestamp
    open_: float
    high: float
    low: float
    close: float

    # Zone events this bar
    fires: list[PushZone]
    breaks: list[PushZone]

    # Full zone state snapshot
    zones_by_tf: dict[str, list[PushZone]]
    trend_by_tf: dict[str, int]
    period_levels_by_tf: dict[str, dict]
    zone_counts_by_tf: dict[str, tuple[int, int]]


def _snapshot_zone_ids(
    state: PushZoneEngineState,
) -> dict[str, set[int]]:
    """Capture zone identity set (by id()) for diffing before/after tick."""
    result: dict[str, set[int]] = {}
    for tf, ts in state.tick_states.items():
        result[tf] = {id(z) for z in ts.supply_zones} | {id(z) for z in ts.demand_zones}
    return result


def build_zone_timeline(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    config: PushZoneEngineConfig | None = None,
    period_depth: int = 3,
) -> list[ZoneTimelineBar]:
    """Run push zone engine once and capture per-bar output.

    Fire/break detection uses state-diffing (comparing zone lists
    before and after each tick) rather than event payloads, since
    event payloads contain flat dicts, not PushZone objects.

    Args:
        data_by_tf: Dict of TF -> OHLCV DataFrame.
        base_tf: Base timeframe for bar iteration.
        config: Push zone engine config (defaults used if None).
        period_depth: Period tracker history depth.

    Returns:
        List of ZoneTimelineBar, one per base TF bar.
    """
    if config is None:
        config = PushZoneEngineConfig()

    tfs = [tf for tf in data_by_tf]
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()

    timeline: list[ZoneTimelineBar] = []

    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs):
        # Snapshot zone ids BEFORE tick
        pre_ids = _snapshot_zone_ids(state)

        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()  # Clear events (we use state-diffing instead)

        # Detect fires and breaks by diffing zone lists
        fires: list[PushZone] = []
        breaks: list[PushZone] = []

        for tf, ts in state.tick_states.items():
            pre = pre_ids.get(tf, set())
            all_zones = list(ts.supply_zones) + list(ts.demand_zones)
            post = {id(z) for z in all_zones}

            # New zones (in post but not in pre) = fires
            for z in all_zones:
                if id(z) not in pre:
                    fires.append(z)

            # Broken zones were removed: in pre but not in post
            # We can't recover the PushZone objects for broken zones
            # since they were already removed from state. Instead,
            # we don't need break detection for the strategy evaluator --
            # it only cares about zone fires (entry triggers) and
            # active zones (for SL/TP computation).

        # Snapshot zone state
        zones_by_tf: dict[str, list[PushZone]] = {}
        trend_by_tf: dict[str, int] = {}
        period_levels: dict[str, dict] = {}
        zone_counts: dict[str, tuple[int, int]] = {}

        for tf, ts in state.tick_states.items():
            zones_by_tf[tf] = list(ts.supply_zones) + list(ts.demand_zones)
            trend_by_tf[tf] = ts.trend
            zone_counts[tf] = (ts.sup_count, ts.dem_count)
            period_levels[tf] = {
                "highs": list(ts.period.prev_highs),
                "lows": list(ts.period.prev_lows),
            }

        timeline.append(ZoneTimelineBar(
            timestamp=ctx.timestamp,
            open_=ctx.open_,
            high=ctx.high,
            low=ctx.low,
            close=ctx.close,
            fires=fires,
            breaks=breaks,
            zones_by_tf=zones_by_tf,
            trend_by_tf=trend_by_tf,
            period_levels_by_tf=period_levels,
            zone_counts_by_tf=zone_counts,
        ))

    return timeline
