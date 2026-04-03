#!/usr/bin/env python
"""Run retest strategy sweep for a symbol.

Usage:
    python scripts/run_retest_sweep.py GBPUSD
    python scripts/run_retest_sweep.py GBPUSD --pairs H1@H4,M15@H4
    python scripts/run_retest_sweep.py GBPUSD --top 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep, default_configs


def main():
    parser = argparse.ArgumentParser(description="Run retest strategy sweep")
    parser.add_argument("symbol", help="Symbol (e.g., GBPUSD)")
    parser.add_argument("--pairs", default=None,
                        help="Comma-separated TF pairs to sweep (default: priority pairs)")
    parser.add_argument("--top", type=int, default=10,
                        help="Show top N configs by SQN (default: 10)")
    parser.add_argument("--save-csv", action="store_true",
                        help="Save results to CSV")
    args = parser.parse_args()

    storage = ParquetStorage("data")
    symbol = args.symbol.upper()

    if args.pairs:
        pairs = [p.strip() for p in args.pairs.split(",")]
        configs = [c for c in default_configs() if c.tf_pair in pairs]
    else:
        configs = default_configs()

    entry_tfs = list({c.entry_tf for c in configs})

    # Load data — need entry TFs + their context TFs
    all_tfs = set()
    for etf in entry_tfs:
        all_tfs.add(etf)
        from iora.diagnostics.opportunity_runner import _tfs_for_entry
        all_tfs.update(_tfs_for_entry(etf))

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  Loaded {tf}: {len(df):,} bars "
                  f"({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")

    print(f"\nRunning retest sweep for {symbol} "
          f"({len(configs)} configs, entry TFs: {entry_tfs})...")
    t0 = time.time()

    summary = run_retest_sweep(
        data_by_tf=data_by_tf, entry_tfs=entry_tfs,
        symbol=symbol, configs=configs,
    )

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Total configs evaluated: {len(summary.results)}")

    top = summary.top_by_sqn(args.top)
    if top:
        print(f"\n{'='*80}")
        print(f"  TOP {len(top)} CONFIGS BY SQN")
        print(f"{'='*80}")
        for i, r in enumerate(top, 1):
            m = r.metrics
            cfg = r.config
            print(f"\n  #{i}: {cfg.tf_pair} | "
                  f"touch={cfg.touch_type} bias={cfg.bias_filter} "
                  f"role={cfg.zone_role_filter} age={cfg.age_filter}")
            print(f"    SL={cfg.sl_mode} TP={cfg.tp_mode} RR={cfg.fixed_rr}")
            print(f"    Trades: {m.get('total_trades', 0):,} | "
                  f"WR: {m.get('win_rate', 0)*100:.1f}% | "
                  f"SQN: {m.get('sqn', 0):.2f} | "
                  f"Expectancy: {m.get('avg_r', 0):.3f}R")
            print(f"    PF: {m.get('profit_factor', 0):.2f} | "
                  f"Sharpe: {m.get('sharpe', 0):.2f} | "
                  f"MaxDD: {m.get('max_dd_r', 0):.1f}R")
            if r.funnel:
                active = [s for s in r.funnel.steps if s.removed > 0]
                if active:
                    parts = " → ".join(f"{s.name}(-{s.removed})" for s in active)
                    print(f"    Funnel: {r.funnel.total_input} → {parts} → {len(r.funnel.passed)}")

    if args.save_csv and summary.results:
        import pandas as pd
        out_dir = Path("results") / symbol
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for r in summary.results:
            row = {
                "tf_pair": r.config.tf_pair,
                "touch_type": r.config.touch_type,
                "bias_filter": r.config.bias_filter,
                "zone_role_filter": r.config.zone_role_filter,
                "age_filter": r.config.age_filter,
                "sl_mode": r.config.sl_mode,
                "tp_mode": r.config.tp_mode,
                "fixed_rr": r.config.fixed_rr,
                "cascade_filter": r.config.cascade_filter,
                "session_filter": r.config.session_filter,
                **r.metrics,
            }
            rows.append(row)
        df = pd.DataFrame(rows)
        out_path = out_dir / f"{symbol.lower()}_retest_sweep.csv"
        df.to_csv(out_path, index=False)
        print(f"\nSaved sweep results ({len(df)} configs) to {out_path}")


if __name__ == "__main__":
    main()
