#!/usr/bin/env python
"""Run --all-tfs opportunity counter for all 5 analysis symbols sequentially.

Each symbol runs 4 entry TFs in parallel internally (M1/M5/M15/H1).
Results saved to results/ with _alltfs suffix.

Usage:
    python scripts/run_all_symbols_alltfs.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.diagnostics.opportunity_runner import run_opportunity_counter_all_tfs

SYMBOLS = ["GBPUSD", "EURUSD", "USDJPY", "XAUUSD", "GBPJPY"]
OUT_DIR = Path("results")


def run_symbol(symbol: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {symbol} — starting --all-tfs (parallel, full date ranges)")
    print(f"{'='*60}")
    t0 = time.time()

    result = run_opportunity_counter_all_tfs(
        storage_base_dir="data",
        symbol=symbol,
        max_workers=4,
    )

    elapsed = time.time() - t0
    print(f"\n{symbol} completed in {elapsed:.1f}s ({elapsed/60:.1f}m)")
    print(f"Total events: {len(result.events):,}")

    # Show data periods
    if result.data_periods:
        print("\nData periods:")
        for dp in sorted(result.data_periods, key=lambda p: p.entry_tf):
            print(f"  {dp.entry_tf}: {dp.start:%Y-%m-%d} to {dp.end:%Y-%m-%d} "
                  f"({dp.years:.1f} years, {dp.bar_count:,} bars)")

    # Show summary per TF pair
    summary = result.summary()
    for tf_pair, counts in sorted(summary.items()):
        entry_tf = tf_pair.split("@")[0]
        period_str = ""
        for dp in result.data_periods:
            if dp.entry_tf == entry_tf:
                period_str = f" ({dp.years:.1f} yrs)"
                break
        print(f"\n  {tf_pair}{period_str}:")
        print(f"    Wick touches:    {counts.get('wick_touch', 0):>8,}")
        print(f"    Body closes:     {counts.get('body_close', 0):>8,}")
        print(f"    Near-misses:     {counts.get('near_miss', 0):>8,}")
        print(f"    Break-throughs:  {counts.get('break_through', 0):>8,}")
        print(f"    Total:           {counts.get('total', 0):>8,}")

    # Save CSVs
    sym_dir = OUT_DIR / symbol.upper()
    sym_dir.mkdir(parents=True, exist_ok=True)
    out_path = sym_dir / f"{symbol.lower()}_alltfs_opportunities.csv"
    df = result.to_dataframe()
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df):,} events to {out_path}")

    matrix = result.opportunity_matrix()
    matrix_path = sym_dir / f"{symbol.lower()}_alltfs_opportunity_matrix.csv"
    matrix.to_csv(matrix_path, index=False)
    print(f"Saved matrix ({len(matrix):,} combos) to {matrix_path}")


def main():
    total_start = time.time()
    print(f"Running opportunity counter (--all-tfs) for {len(SYMBOLS)} symbols")
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Each symbol runs M1/M5/M15/H1 entry TFs in parallel with full date ranges")

    for symbol in SYMBOLS:
        try:
            run_symbol(symbol)
        except Exception as e:
            print(f"\nERROR on {symbol}: {e}")
            import traceback
            traceback.print_exc()

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  ALL DONE — {len(SYMBOLS)} symbols in {total_elapsed:.1f}s ({total_elapsed/60:.1f}m)")
    print(f"{'='*60}")

    # Final summary: list output files
    print("\nOutput files:")
    for f in sorted(OUT_DIR.glob("*/*_alltfs_*")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.parent.name}/{f.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
