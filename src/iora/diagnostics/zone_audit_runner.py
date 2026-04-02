"""Zone Audit Runner — runs zone engine and collects lifecycle records.

Produces ZoneAuditResult with per-zone lifecycle data and
per-bar zone population snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState, PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.engine.push_zone_models import PushZone
from iora.diagnostics.zone_audit import (
    ZoneLifecycleRecord, ZoneAuditReport, compute_audit,
)


@dataclass(slots=True)
class ZoneAuditResult:
    """Full audit output for one symbol."""
    symbol: str
    reports: list[ZoneAuditReport]
    lifecycle_records: list[ZoneLifecycleRecord]
    population_snapshots: list[dict]


def run_zone_audit(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> ZoneAuditResult:
    """Run zone engine on data and collect zone lifecycle statistics."""
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()

    # Track zone snapshots: id(zone) → zone reference + creation bar
    zone_registry: dict[int, tuple[PushZone, int]] = {}
    broken_records: list[ZoneLifecycleRecord] = []
    population_snapshots: list[dict] = []

    bar_idx = 0
    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs):
        # Snapshot zone ids BEFORE tick
        pre_ids: set[int] = set()
        for tf, ts in state.tick_states.items():
            for z in ts.supply_zones:
                pre_ids.add(id(z))
            for z in ts.demand_zones:
                pre_ids.add(id(z))

        push_zone_engine_tick(state, ctx, PushZoneEngineConfig(), bus=bus)
        bus.drain()

        # Register new zones
        for tf, ts in state.tick_states.items():
            for z in list(ts.supply_zones) + list(ts.demand_zones):
                zid = id(z)
                if zid not in pre_ids and zid not in zone_registry:
                    zone_registry[zid] = (z, bar_idx)

        # Check for broken zones (were in pre_ids, now gone)
        post_ids: set[int] = set()
        for tf, ts in state.tick_states.items():
            for z in ts.supply_zones:
                post_ids.add(id(z))
            for z in ts.demand_zones:
                post_ids.add(id(z))

        for zid in pre_ids - post_ids:
            if zid in zone_registry:
                z, creation_bar = zone_registry.pop(zid)
                broken_records.append(ZoneLifecycleRecord(
                    tf=z.timeframe,
                    side="supply" if z.is_supply else "demand",
                    origin_time=z.origin_time,
                    break_time=ctx.timestamp,
                    test_count=z.test_count,
                    first_test_time=z.first_test_time,
                    replacement_count=z.replacement_count,
                    lifespan_bars=bar_idx - creation_bar,
                    birth_period_pattern=z.birth_period_pattern,
                    birth_price_distance=z.birth_price_distance,
                ))

        # Periodic population snapshot (every 100 bars to keep memory bounded)
        if bar_idx % 100 == 0:
            for tf, ts in state.tick_states.items():
                population_snapshots.append({
                    "bar_idx": bar_idx,
                    "timestamp": ctx.timestamp,
                    "tf": tf,
                    "supply_count": len(ts.supply_zones),
                    "demand_count": len(ts.demand_zones),
                    "count": len(ts.supply_zones) + len(ts.demand_zones),
                })

        bar_idx += 1

    # Still-alive zones → lifecycle records with break_time=None
    all_records = list(broken_records)
    for zid, (z, creation_bar) in zone_registry.items():
        all_records.append(ZoneLifecycleRecord(
            tf=z.timeframe,
            side="supply" if z.is_supply else "demand",
            origin_time=z.origin_time,
            break_time=None,
            test_count=z.test_count,
            first_test_time=z.first_test_time,
            replacement_count=z.replacement_count,
            lifespan_bars=bar_idx - creation_bar,
            birth_period_pattern=z.birth_period_pattern,
            birth_price_distance=z.birth_price_distance,
        ))

    # Compute per-TF per-side reports
    reports: list[ZoneAuditReport] = []
    for tf in tfs:
        for side in ("supply", "demand"):
            tf_records = [r for r in all_records if r.tf == tf and r.side == side]
            if tf_records:
                report = compute_audit(tf_records, tf, side)
                # Compute avg/max zones alive from population snapshots
                tf_pops = [s for s in population_snapshots if s["tf"] == tf]
                if tf_pops:
                    side_key = f"{side}_count"
                    counts = [s[side_key] for s in tf_pops]
                    report.avg_zones_alive = sum(counts) / len(counts)
                    report.max_zones_alive = max(counts)
                reports.append(report)

    return ZoneAuditResult(
        symbol=symbol,
        reports=reports,
        lifecycle_records=all_records,
        population_snapshots=population_snapshots,
    )
