#!/usr/bin/env python -u
"""Run HTF-triggered LTF entry sweep across multiple symbols overnight.

Usage:
    python -u scripts/run_overnight_sweep.py
    python -u scripts/run_overnight_sweep.py --symbols GBPUSD,XAUUSD
    python -u scripts/run_overnight_sweep.py --pairs H1@H4  # Only H1@H4 nesting configs
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_sweep import htf_triggered_ltf_configs, run_retest_sweep

DEFAULT_SYMBOLS = [
    "GBPUSD", "EURUSD", "USDJPY", "GBPJPY",
    "XAUUSD", "BTCUSD", "US500", "USTEC",
]


def run_one_symbol(
    symbol: str,
    storage: ParquetStorage,
    output_dir: Path,
    pair_filter: set[str] | None = None,
) -> pd.DataFrame | None:
    """Run sweep for one symbol, return results DataFrame or None on failure."""
    print(f"\n{'='*60}")
    print(f"  {symbol}")
    print(f"{'='*60}")

    configs = htf_triggered_ltf_configs(symbol)
    if pair_filter:
        configs = [c for c in configs if c.tf_pair in pair_filter]
    print(f"  {len(configs)} configs")

    # Determine TFs needed
    entry_tfs = sorted({c.entry_tf for c in configs})
    all_tfs: set[str] = set()
    from iora.diagnostics.opportunity_runner import _tfs_for_entry
    for etf in entry_tfs:
        all_tfs.add(etf)
        all_tfs.update(_tfs_for_entry(etf))
    ltf_tfs = {c.entry_tf_override for c in configs if c.entry_tf_override}
    all_tfs.update(ltf_tfs)

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"    {tf}: {len(df):,} bars")
        else:
            print(f"    {tf}: MISSING — skipping")

    if not data_by_tf:
        print(f"  SKIP {symbol} — no data loaded")
        return None

    print(f"  Running sweep...")
    t0 = time.time()
    try:
        summary = run_retest_sweep(
            data_by_tf=data_by_tf,
            entry_tfs=entry_tfs,
            symbol=symbol,
            configs=configs,
            parallel=False,
        )
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s — {len(summary.results)} results")

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
    print(f"  Saved: {csv_path}")

    # Show top 5
    viable = df[df["total_trades"] >= 30].sort_values("sqn", ascending=False)
    if not viable.empty:
        print(f"  Top 5 by SQN (min 30 trades):")
        for _, row in viable.head(5).iterrows():
            print(f"    {row['tf_pair']} nest={row['ltf_nesting']} "
                  f"sp={row['spread_pips']} partial={row['partial_tp']} "
                  f"| SQN={row['sqn']:.2f} WR={row['win_rate']:.0%} "
                  f"trades={row['total_trades']:.0f}")
    else:
        print(f"  No configs with 30+ trades")

    return df


def main():
    parser = argparse.ArgumentParser(description="Overnight multi-symbol sweep")
    parser.add_argument("--symbols", default=None,
                        help="Comma-separated symbols (default: 8 standard)")
    parser.add_argument("--pairs", default=None,
                        help="Comma-separated TF pairs filter (e.g., H1@H4)")
    parser.add_argument("--output", default="results/sweeps/htf_triggered")
    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = DEFAULT_SYMBOLS

    pair_filter = None
    if args.pairs:
        pair_filter = {p.strip() for p in args.pairs.split(",")}

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    storage = ParquetStorage("data")

    print(f"Overnight sweep: {len(symbols)} symbols")
    print(f"Symbols: {', '.join(symbols)}")
    if pair_filter:
        print(f"Pairs filter: {pair_filter}")
    print(f"Output: {output_dir}")
    print(f"Start: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    all_dfs = []
    t_total = time.time()

    for sym in symbols:
        df = run_one_symbol(sym, storage, output_dir, pair_filter)
        if df is not None:
            all_dfs.append(df)

    # Merge all results
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined_path = output_dir / "ALL_COMBINED.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\n{'='*60}")
        print(f"Combined results: {combined_path} ({len(combined)} rows)")

    total_elapsed = time.time() - t_total
    print(f"\nTotal time: {total_elapsed/60:.1f} minutes")
    print(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
