"""Run a parameter sweep across configs on GBPUSD.

Usage: python scripts/run_sweep.py [--symbols GBPUSD,EURUSD] [--output results.csv]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.sweep_runner import run_sweep, run_multi_symbol_sweep
from iora.strategy.config_grid import build_config_grid


def main():
    parser = argparse.ArgumentParser(description="Push zone strategy sweep")
    parser.add_argument("--symbols", default="GBPUSD",
                        help="Comma-separated symbols (default: GBPUSD)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: print to stdout)")
    parser.add_argument("--base-tf", default="M5",
                        help="Base timeframe (default: M5)")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    storage = ParquetStorage("data")

    # Define sweep grid
    grid = build_config_grid({
        "sl_mode": ["zone", "atr"],
        "tp_mode": ["zone", "fixed_rr"],
        "require_nesting": [True, False],
        "no_trade_zones": [True, False],
    })
    print(f"Sweep grid: {len(grid)} configs x {len(symbols)} symbols "
          f"= {len(grid) * len(symbols)} runs")

    # Build timelines (expensive -- once per symbol)
    timelines = {}
    for symbol in symbols:
        tfs = [args.base_tf, "M15", "H1", "H4", "D1"]
        data_by_tf = {}
        for tf in tfs:
            df = storage.load(symbol, tf)
            if df is not None and not df.empty:
                data_by_tf[tf] = df

        if args.base_tf not in data_by_tf:
            print(f"  SKIP {symbol}: no {args.base_tf} data")
            continue

        t0 = time.monotonic()
        timelines[symbol] = build_zone_timeline(data_by_tf, base_tf=args.base_tf)
        print(f"  {symbol}: {len(timelines[symbol])} bars "
              f"({time.monotonic() - t0:.1f}s)")

    # Run sweep
    t0 = time.monotonic()
    df = run_multi_symbol_sweep(timelines, grid)
    elapsed = time.monotonic() - t0
    print(f"\nSweep complete: {len(df)} results in {elapsed:.1f}s")

    # Sort by expectancy_r descending
    if "expectancy_r" in df.columns:
        df = df.sort_values("expectancy_r", ascending=False)

    # Output
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Results saved to {args.output}")
    else:
        # Print top 10 configs
        display_cols = [
            "symbol", "sl_mode", "tp_mode", "require_nesting", "no_trade_zones",
            "total_trades", "win_rate", "expectancy_r", "sqn", "sharpe",
            "profit_factor", "max_dd_r", "calmar", "total_r",
        ]
        cols = [c for c in display_cols if c in df.columns]
        print(f"\n{'='*120}")
        print("Top 10 configs by expectancy (R):")
        print(df[cols].head(10).to_string(index=False))
        print(f"\nBottom 5 configs:")
        print(df[cols].tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
