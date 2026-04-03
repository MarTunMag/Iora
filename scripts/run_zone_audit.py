"""Run zone activity audit across symbols.

Usage: python scripts/run_zone_audit.py [--symbols GBPUSD,EURUSD] [--output results/]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.zone_audit_runner import run_zone_audit

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Zone activity audit")
    parser.add_argument("--symbols", default="GBPUSD",
                        help="Comma-separated symbols (default: GBPUSD)")
    parser.add_argument("--output", default="results",
                        help="Output directory (default: results)")
    parser.add_argument("--base-tf", default="M5",
                        help="Base timeframe (default: M5)")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    storage = ParquetStorage("data")

    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Auditing {symbol}...")
        tfs = [args.base_tf, "M15", "H1", "H4", "D1", "W1"]
        data_by_tf = {}
        for tf in tfs:
            df = storage.load(symbol, tf)
            if df is not None and not df.empty:
                data_by_tf[tf] = df

        if args.base_tf not in data_by_tf:
            print(f"  SKIP {symbol}: no {args.base_tf} data")
            continue

        t0 = time.monotonic()
        result = run_zone_audit(data_by_tf, base_tf=args.base_tf, symbol=symbol)
        elapsed = time.monotonic() - t0
        print(f"  Done in {elapsed:.1f}s — {len(result.lifecycle_records)} zones tracked")

        # Print summary
        for report in result.reports:
            print(f"\n  {report.tf} {report.side}:")
            print(f"    Created: {report.zones_created}  Broken: {report.zones_broken}")
            print(f"    Retested: {report.zones_retested}  Untouched: {report.zones_untouched}")
            print(f"    Avg tests before break: {report.avg_tests_before_break:.1f}")
            print(f"    Avg alive: {report.avg_zones_alive:.1f}  Max alive: {report.max_zones_alive}")

        # Save lifecycle records
        if result.lifecycle_records:
            records_df = pd.DataFrame([{
                "tf": r.tf, "side": r.side,
                "origin_time": r.origin_time,
                "break_time": r.break_time,
                "test_count": r.test_count,
                "first_test_time": r.first_test_time,
                "replacement_count": r.replacement_count,
                "lifespan_bars": r.lifespan_bars,
                "birth_period_pattern": r.birth_period_pattern,
                "birth_price_distance": r.birth_price_distance,
            } for r in result.lifecycle_records])
            import os
            sym_dir = f"{args.output}/{symbol.upper()}"
            os.makedirs(sym_dir, exist_ok=True)
            out_path = f"{sym_dir}/{symbol.lower()}_zone_audit.csv"
            records_df.to_csv(out_path, index=False)
            print(f"\n  Saved to {out_path}")


if __name__ == "__main__":
    main()
