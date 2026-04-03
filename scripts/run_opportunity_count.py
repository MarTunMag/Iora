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
    parser.add_argument("--tfs", default="M5,H1,H4,D1,W1", help="Comma-separated TFs")
    parser.add_argument("--save-csv", action="store_true", help="Save events to CSV")
    parser.add_argument("--all-tfs", action="store_true",
                        help="Run all entry TFs (M1,M5,M15,H1) for full 8-pair coverage")
    args = parser.parse_args()

    storage = ParquetStorage("data")
    tfs = [t.strip() for t in args.tfs.split(",")]

    data_by_tf = {}
    for tf in tfs:
        df = storage.load(args.symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  Loaded {tf}: {len(df)} bars")
        else:
            print(f"  {tf}: no data")

    if args.all_tfs:
        # Ensure all entry TFs are loaded for full coverage
        all_tfs = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]
        for tf in all_tfs:
            if tf not in data_by_tf:
                df = storage.load(args.symbol, tf)
                if df is not None and not df.empty:
                    data_by_tf[tf] = df
                    print(f"  Loaded {tf}: {len(df)} bars")
        print(f"\nRunning opportunity counter for {args.symbol} (ALL entry TFs)...")
        result = run_opportunity_counter_all_tfs(data_by_tf, symbol=args.symbol)
    else:
        if args.base_tf not in data_by_tf:
            print(f"Error: base TF {args.base_tf} has no data")
            sys.exit(1)
        print(f"\nRunning opportunity counter for {args.symbol} (entry TF: {args.base_tf})...")
        result = run_opportunity_counter(
            data_by_tf, base_tf=args.base_tf, symbol=args.symbol,
        )

    print(f"\n=== Opportunity Count: {args.symbol} ===")
    print(f"Total events: {len(result.events)}")

    summary = result.summary()
    for tf_pair, counts in sorted(summary.items()):
        print(f"\n{tf_pair}:")
        print(f"  Wick touches:    {counts.get('wick_touch', 0):>6}")
        print(f"  Body closes:     {counts.get('body_close', 0):>6}")
        print(f"  Near-misses:     {counts.get('near_miss', 0):>6}")
        print(f"  Break-throughs:  {counts.get('break_through', 0):>6}")
        print(f"  Total:           {counts.get('total', 0):>6}")
        print(f"  --- Bias alignment ---")
        print(f"  With daily:      {counts.get('with_daily', 0):>6}")
        print(f"  Against daily:   {counts.get('against_daily', 0):>6}")
        print(f"  At transition:   {counts.get('at_transition', 0):>6}")
        print(f"  Neutral:         {counts.get('neutral', 0):>6}")

    if args.save_csv:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{args.symbol.lower()}_opportunities.csv"
        df = result.to_dataframe()
        df.to_csv(out_path, index=False)
        print(f"\nSaved {len(df)} events to {out_path}")

        matrix = result.opportunity_matrix()
        matrix_path = out_dir / f"{args.symbol.lower()}_opportunity_matrix.csv"
        matrix.to_csv(matrix_path, index=False)
        print(f"Saved matrix ({len(matrix)} combos) to {matrix_path}")


if __name__ == "__main__":
    main()
