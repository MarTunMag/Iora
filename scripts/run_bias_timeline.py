#!/usr/bin/env python
"""Run bias timeline for a symbol and print summary.

Usage:
    python scripts/run_bias_timeline.py GBPUSD
    python scripts/run_bias_timeline.py GBPUSD --base-tf M5 --save-csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.bias_timeline_runner import run_bias_timeline


def main():
    parser = argparse.ArgumentParser(description="Run bias timeline analysis")
    parser.add_argument("symbol", help="Symbol to analyze (e.g., GBPUSD)")
    parser.add_argument("--base-tf", default="M5", help="Base timeframe (default: M5)")
    parser.add_argument("--tfs", default="M5,H1,H4,D1,W1", help="Comma-separated TFs")
    parser.add_argument("--save-csv", action="store_true", help="Save timeline to CSV")
    parser.add_argument("--sample-every", type=int, default=1,
                        help="Collect every N bars (default: 1)")
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

    if args.base_tf not in data_by_tf:
        print(f"Error: base TF {args.base_tf} has no data")
        sys.exit(1)

    print(f"\nRunning bias timeline for {args.symbol}...")
    result = run_bias_timeline(
        data_by_tf, base_tf=args.base_tf, symbol=args.symbol,
        sample_every=args.sample_every,
    )

    summary = result.summary()
    print(f"\n=== Bias Timeline: {args.symbol} ===")
    print(f"Total bars:       {summary['total_bars']}")
    print(f"Transitions:      {summary['transition_count']}")
    print(f"\nBias distribution:")
    for label, count in sorted(summary.get("bias_distribution", {}).items(),
                                key=lambda x: -x[1]):
        pct = count / summary["total_bars"] * 100
        print(f"  {label:30s} {count:6d} ({pct:5.1f}%)")

    print(f"\nD-to-W relationship:")
    for label, count in sorted(summary.get("d_to_w_distribution", {}).items(),
                                key=lambda x: -x[1]):
        pct = count / summary["total_bars"] * 100
        print(f"  {label:20s} {count:6d} ({pct:5.1f}%)")

    if args.save_csv:
        out_dir = Path("results") / args.symbol.upper()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{args.symbol.lower()}_bias_timeline.csv"
        df = result.to_dataframe()
        df.to_csv(out_path, index=False)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
