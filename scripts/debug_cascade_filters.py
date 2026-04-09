#!/usr/bin/env python -u
"""Debug cascade filter firing rates on GBPUSD.

Counts how often each cascade feature fires during a full H1 bar iteration.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from collections import Counter

import pandas as pd

from iora.data.bar_iterator import iter_bars
from iora.data.parquet_storage import ParquetStorage
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.engine.cascade_state import CascadePhaseState, cascade_state_tick
from iora.engine.events import EventBus
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig, PushZoneEngineState,
    init_push_zone_state, push_zone_engine_tick,
)


def main():
    storage = ParquetStorage("data")
    symbol = "GBPUSD"
    entry_tf = "H1"

    all_tfs = ["M5", "M15", "H1", "H4", "D1", "W1"]
    data_by_tf = {}
    for tf in all_tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df):,} bars")

    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, entry_tf)
    state = init_push_zone_state(tfs, period_depth=3)
    bus = EventBus()
    config = PushZoneEngineConfig()
    cascade_st = CascadePhaseState()

    # Counters
    phase_counts = Counter()
    tl_break_event_counts = Counter()  # per TF
    tl_break_total = 0
    zones_with_bos_choch = Counter()  # "BOS" / "CHoCH" count
    seen_tagged_zones = set()  # Track ALL zones that get tagged during run
    h1_zone_count_max = 0
    h1_zone_count_5plus_bars = 0
    h1_impulse_broken_bars = 0
    choch_conviction_counts = Counter()
    consumption_counts = Counter()
    total_bars = 0

    for ctx in iter_bars(data_by_tf[entry_tf], aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        cascade_state_tick(
            cascade_st, state.tick_states,
            state.tl_states, state.bar_tl_events, ctx.close,
        )

        phase_counts[cascade_st.phase] += 1

        # Count TL break events this bar
        for ev in cascade_st.bar_tl_events:
            tl_break_event_counts[f"{ev.tf}_{ev.tl_type}"] += 1
            tl_break_total += 1

        # Count zones with BOS/CHoCH attribution
        for tf, ts in state.tick_states.items():
            for z in ts.supply_zones + ts.demand_zones:
                if z.caused_bos_choch:
                    zones_with_bos_choch[f"{tf}_{z.caused_bos_choch}"] += 1
                    zkey = (tf, z.top, z.bottom, z.caused_bos_choch, z.origin_time)
                    seen_tagged_zones.add(zkey)

        # H1 zone count stats
        if cascade_st.h1_push_zone_count > h1_zone_count_max:
            h1_zone_count_max = cascade_st.h1_push_zone_count
        if cascade_st.h1_push_zone_count >= 5:
            h1_zone_count_5plus_bars += 1
        if not cascade_st.h1_impulse_tl_intact:
            h1_impulse_broken_bars += 1

        # CHoCH conviction
        for tf_label in ("h4", "h1", "m15"):
            conv = getattr(cascade_st, f"{tf_label}_last_choch_conviction")
            if conv:
                choch_conviction_counts[f"{tf_label}_{conv}"] += 1

        # Consumption count
        consumption_counts[cascade_st.h4_consumption_count] += 1

        total_bars += 1

    print(f"\n{'='*60}")
    print(f"  GBPUSD Cascade Debug — {total_bars:,} H1 bars")
    print(f"{'='*60}")

    print(f"\n  Phase distribution:")
    for phase, count in phase_counts.most_common():
        print(f"    {phase:30s} {count:6d} ({count/total_bars*100:.1f}%)")

    print(f"\n  TL Break events total: {tl_break_total}")
    for key, count in tl_break_event_counts.most_common():
        print(f"    {key:30s} {count:6d}")

    print(f"\n  Zones with BOS/CHoCH attribution (cumulative per-bar snapshot):")
    # This counts duplicates (same zone counted on every bar it exists)
    # Better: count unique zones
    print(f"    (Note: these are per-bar snapshots, not unique zones)")
    for key, count in zones_with_bos_choch.most_common(20):
        print(f"    {key:30s} {count:6d}")

    print(f"\n  H1 zone count stats:")
    print(f"    Max zone count ever: {h1_zone_count_max}")
    print(f"    Bars with count >= 5: {h1_zone_count_5plus_bars} ({h1_zone_count_5plus_bars/total_bars*100:.2f}%)")
    print(f"    Bars with H1 impulse TL broken: {h1_impulse_broken_bars} ({h1_impulse_broken_bars/total_bars*100:.2f}%)")

    print(f"\n  CHoCH conviction distribution:")
    for key, count in choch_conviction_counts.most_common():
        print(f"    {key:30s} {count:6d} ({count/total_bars*100:.1f}%)")

    print(f"\n  H4 consumption count distribution:")
    for cc, count in sorted(consumption_counts.items()):
        print(f"    count={cc}: {count:6d} ({count/total_bars*100:.1f}%)")

    # Also count UNIQUE zones with caused_bos_choch (at end of run)
    print(f"\n  Unique zone attributions (zones still alive at end):")
    unique_attributed = set()
    for tf, ts in state.tick_states.items():
        for z in ts.supply_zones + ts.demand_zones:
            if z.caused_bos_choch:
                unique_attributed.add((tf, z.top, z.bottom, z.caused_bos_choch, z.origin_time))
    print(f"    Total unique zones with BOS/CHoCH tag: {len(unique_attributed)}")
    bos_count = sum(1 for x in unique_attributed if x[3] == "BOS")
    choch_count = sum(1 for x in unique_attributed if x[3] == "CHoCH")
    print(f"    BOS: {bos_count}, CHoCH: {choch_count}")
    per_tf = Counter()
    for x in unique_attributed:
        per_tf[x[0]] += 1
    for tf, c in per_tf.most_common():
        print(f"      {tf}: {c}")

    print(f"\n  Zones tagged during run (seen_tagged_zones):")
    print(f"    Total unique zones tagged: {len(seen_tagged_zones)}")
    tag_tf = Counter()
    tag_type = Counter()
    for x in seen_tagged_zones:
        tag_tf[x[0]] += 1
        tag_type[x[3]] += 1
    for t, c in tag_type.most_common():
        print(f"    {t}: {c}")
    for tf, c in tag_tf.most_common():
        print(f"      {tf}: {c}")

    print(f"\n  Push trendline state (TL active / TL broken per TF):")
    for tf in ["H1", "H4", "D1"]:
        tl_st = state.tl_states.get(tf)
        if tl_st:
            print(f"    {tf} desc: active={tl_st.desc_active}, broken={tl_st.desc_broken}")
            print(f"    {tf} asc:  active={tl_st.asc_active}, broken={tl_st.asc_broken}")


if __name__ == "__main__":
    main()
