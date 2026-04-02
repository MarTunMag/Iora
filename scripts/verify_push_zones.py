"""
Verify Python push zone engine output against Pine indicator.

Loads GBPUSD data, runs the push zone engine, and prints zone events
for manual comparison against TradingView charts.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "src")

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.engine.events import EventBus


def main():
    storage = ParquetStorage("data")
    symbol = "GBPUSD"

    # Load TFs needed
    tfs = ["M5", "M15", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df)} bars, {df.index[0]} -> {df.index[-1]}")

    base_tf = "M5"
    if base_tf not in data_by_tf:
        print(f"ERROR: No {base_tf} data for {symbol}")
        return

    print(f"\nBuilding aligned data (base={base_tf})...")
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    print(f"  Aligned: {len(aligned_df)} bars")

    tfs_available = [tf for tf in tfs if tf in data_by_tf]

    print("\nRunning push zone engine...")
    state = init_push_zone_state(tfs_available, period_depth=3)
    config = PushZoneEngineConfig()
    bus = EventBus()

    zone_events = []
    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs_available):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        for ev in bus.drain():
            zone_events.append({
                "time": ev.timestamp,
                "tf": ev.timeframe,
                "type": ev.id.name,
                "payload": ev.payload,
            })

    print(f"\nTotal events: {len(zone_events)}")
    print(f"  ZONE_FIRE: {sum(1 for e in zone_events if e['type'] == 'ZONE_FIRE')}")
    print(f"  ZONE_BREAK: {sum(1 for e in zone_events if e['type'] == 'ZONE_BREAK')}")

    # Print final zone state
    print("\n--- Final Zone State ---")
    for tf in tfs_available:
        ts = state.tick_states.get(tf)
        if ts is None:
            continue
        sup = list(ts.supply_zones)
        dem = list(ts.demand_zones)
        push_sup = [z for z in sup if z.is_push]
        push_dem = [z for z in dem if z.is_push]
        rev = [z for z in sup + dem if z.is_reversal]
        print(f"\n  {tf}: {len(sup)}S {len(dem)}D | "
              f"Push: {len(push_sup)}S {len(push_dem)}D | "
              f"Rev: {len(rev)} | Trend: {ts.trend}")
        for z in sup + dem:
            role = "PUSH" if z.is_push else ("REV" if z.is_reversal else ("TERM" if z.is_terminal else ""))
            cls = f" {z.struct_cls}" if z.struct_cls else ""
            print(f"    {'S' if z.is_supply else 'D'} {z.swing_cls}{cls} "
                  f"#{z.count_num} {role} "
                  f"[{z.bottom:.5f} — {z.top:.5f}] @ {z.origin_time}")


if __name__ == "__main__":
    main()
