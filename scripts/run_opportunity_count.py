#!/usr/bin/env python
"""Run opportunity counter for a symbol and print summary.

Usage:
    python scripts/run_opportunity_count.py GBPUSD
    python scripts/run_opportunity_count.py GBPUSD --base-tf M5 --save-csv
    python scripts/run_opportunity_count.py GBPUSD --all-tfs --save-csv
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.opportunity_runner import (
    run_opportunity_counter, run_opportunity_counter_all_tfs,
)


def main():
    parser = argparse.ArgumentParser(description="Run opportunity counter")
    parser.add_argument("symbol", help="Symbol to analyze (e.g., GBPUSD)")
    parser.add_argument("--base-tf", default="M5", help="Base/entry timeframe (default: M5)")
    parser.add_argument("--tfs", default="M5,H1,H4,D1,W1", help="Comma-separated TFs to load (single-TF mode)")
    parser.add_argument("--save-csv", action="store_true", help="Save events to CSV")
    parser.add_argument("--all-tfs", action="store_true",
                        help="Run all entry TFs (M1,M5,M15,H1) in parallel, each with full date range")
    parser.add_argument("--workers", type=int, default=4,
                        help="Max parallel workers for --all-tfs (default: 4)")
    args = parser.parse_args()

    t_start = time.time()

    if args.all_tfs:
        print(f"Running opportunity counter for {args.symbol} (ALL entry TFs, parallel, full date ranges)...")
        result = run_opportunity_counter_all_tfs(
            storage_base_dir="data",
            symbol=args.symbol,
            max_workers=args.workers,
        )
    else:
        storage = ParquetStorage("data")
        tfs = [t.strip() for t in args.tfs.split(",")]

        # Ensure base-tf's context TFs are loaded
        from iora.diagnostics.opportunity_runner import _tfs_for_entry
        needed_tfs = _tfs_for_entry(args.base_tf)
        all_tfs = list(dict.fromkeys(tfs + needed_tfs))  # preserve order, deduplicate

        data_by_tf = {}
        for tf in all_tfs:
            df = storage.load(args.symbol, tf)
            if df is not None and not df.empty:
                data_by_tf[tf] = df
                print(f"  Loaded {tf}: {len(df):,} bars ({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")
            else:
                print(f"  {tf}: no data")

        if args.base_tf not in data_by_tf:
            print(f"Error: base TF {args.base_tf} has no data")
            sys.exit(1)
        print(f"\nRunning opportunity counter for {args.symbol} (entry TF: {args.base_tf})...")
        result = run_opportunity_counter(
            data_by_tf, base_tf=args.base_tf, symbol=args.symbol,
        )

    elapsed = time.time() - t_start
    print(f"\n=== Opportunity Count: {args.symbol} (completed in {elapsed:.1f}s) ===")
    print(f"Total events: {len(result.events):,}")

    # Show data periods
    if result.data_periods:
        print("\nData periods:")
        for dp in sorted(result.data_periods, key=lambda p: p.entry_tf):
            print(f"  {dp.entry_tf}: {dp.start:%Y-%m-%d} to {dp.end:%Y-%m-%d} "
                  f"({dp.years:.1f} years, {dp.bar_count:,} bars)")

    summary = result.summary()
    for tf_pair, counts in sorted(summary.items()):
        # Find the matching data period for this entry TF
        entry_tf = tf_pair.split("@")[0]
        period_str = ""
        for dp in result.data_periods:
            if dp.entry_tf == entry_tf:
                period_str = f" ({dp.years:.1f} yrs, {dp.start:%Y-%m-%d} to {dp.end:%Y-%m-%d})"
                break

        print(f"\n{tf_pair}{period_str}:")
        print(f"  Wick touches:    {counts.get('wick_touch', 0):>6,}")
        print(f"  Body closes:     {counts.get('body_close', 0):>6,}")
        print(f"  Near-misses:     {counts.get('near_miss', 0):>6,}")
        print(f"  Break-throughs:  {counts.get('break_through', 0):>6,}")
        print(f"  Total:           {counts.get('total', 0):>6,}")
        print(f"  --- Bias alignment ---")
        print(f"  With daily:      {counts.get('with_daily', 0):>6,}")
        print(f"  Against daily:   {counts.get('against_daily', 0):>6,}")
        print(f"  At transition:   {counts.get('at_transition', 0):>6,}")
        print(f"  Neutral:         {counts.get('neutral', 0):>6,}")

    if args.save_csv:
        out_dir = Path("results") / args.symbol.upper()
        out_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_alltfs" if args.all_tfs else ""
        out_path = out_dir / f"{args.symbol.lower()}{suffix}_opportunities.csv"
        df = result.to_dataframe()
        df.to_csv(out_path, index=False)
        print(f"\nSaved {len(df):,} events to {out_path}")

        matrix = result.opportunity_matrix()
        matrix_path = out_dir / f"{args.symbol.lower()}{suffix}_opportunity_matrix.csv"
        matrix.to_csv(matrix_path, index=False)
        print(f"Saved matrix ({len(matrix):,} combos) to {matrix_path}")


if __name__ == "__main__":
    main()
