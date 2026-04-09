#!/usr/bin/env python
"""Run HTF-triggered LTF entry sweep on one or more symbols.

Usage:
    python scripts/run_htf_triggered_sweep.py GBPUSD
    python scripts/run_htf_triggered_sweep.py GBPUSD --output results/htf_triggered/
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_sweep import htf_triggered_ltf_configs, run_retest_sweep


def main():
    parser = argparse.ArgumentParser(description="HTF-triggered LTF entry sweep")
    parser.add_argument("symbol", help="Symbol (e.g., GBPUSD)")
    parser.add_argument("--output", default="results/sweeps/htf_triggered", help="Output directory")
    parser.add_argument("--pairs", default=None,
                        help="Comma-separated TF pairs to include (e.g., H1@H4,M5@M15)")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    storage = ParquetStorage("data")
    configs = htf_triggered_ltf_configs(symbol)

    if args.pairs:
        pairs = {p.strip() for p in args.pairs.split(",")}
        configs = [c for c in configs if c.tf_pair in pairs]

    print(f"Generated {len(configs)} configs for {symbol}")

    # Determine all TFs needed
    entry_tfs = sorted({c.entry_tf for c in configs})
    all_tfs: set[str] = set()
    from iora.diagnostics.opportunity_runner import _tfs_for_entry
    for etf in entry_tfs:
        all_tfs.add(etf)
        all_tfs.update(_tfs_for_entry(etf))
    # Also load LTF TFs needed for nesting
    ltf_tfs = {c.entry_tf_override for c in configs if c.entry_tf_override}
    all_tfs.update(ltf_tfs)

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  Loaded {tf}: {len(df):,} bars "
                  f"({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")

    print(f"\nRunning sweep on {symbol}...")
    t0 = time.time()
    summary = run_retest_sweep(
        data_by_tf=data_by_tf,
        entry_tfs=entry_tfs,
        symbol=symbol,
        configs=configs,
        parallel=False,  # Single entry TF, no parallelism benefit
    )
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s — {len(summary.results)} results")

    # Build CSV
    rows = []
    for r in summary.results:
        m = r.metrics
        cfg = r.config
        rows.append({
            "symbol": symbol,
            "tf_pair": cfg.tf_pair,
            "ltf_nesting": cfg.ltf_nesting,
            "entry_tf_override": cfg.entry_tf_override,
            "trigger_window_bars": cfg.trigger_window_bars,
            "spread_pips": cfg.spread_pips,
            "partial_tp": cfg.partial_tp,
            "min_sl_pips": cfg.min_sl_pips,
            "min_sl_spread_mult": cfg.min_sl_spread_mult,
            "require_ltf_push": cfg.require_ltf_push,
            "total_trades": m.get("total_trades", 0),
            "win_rate": m.get("win_rate", 0),
            "sqn": m.get("sqn", 0),
            "pf": m.get("profit_factor", 0),
            "avg_r": m.get("avg_r", 0),
            "total_r": m.get("total_r", 0),
            "max_dd_r": m.get("max_dd_r", 0),
            "avg_sl_pips": m.get("avg_risk_pips", 0),
        })

    df = pd.DataFrame(rows)
    csv_path = output_dir / f"{symbol}.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Results saved to {csv_path}")

    # Print top 10 by SQN
    viable = df[df["total_trades"] >= 30].sort_values("sqn", ascending=False)
    if not viable.empty:
        print(f"\nTop 10 by SQN (min 30 trades):")
        print(viable.head(10).to_string(index=False))
    else:
        print("\nNo configs with 30+ trades found.")


if __name__ == "__main__":
    main()
