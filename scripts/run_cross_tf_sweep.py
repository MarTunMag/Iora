#!/usr/bin/env python
"""Run cross-TF TP sweep — focused limit configs with HTF zone targets.

This is a FOCUSED sweep (~80-100 configs) separate from the 797-config discovery sweep.
Runs each symbol sequentially with timing per stage.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.opportunity_runner import _tfs_for_entry
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep, cross_tf_tp_configs, partial_tp_configs

SYMBOLS = ["GBPUSD", "EURUSD", "USDJPY", "XAUUSD", "GBPJPY"]


def run_symbol(symbol: str, storage: ParquetStorage, configs: list[RetestConfig]) -> None:
    print(f"\n{'='*70}", flush=True)
    print(f"  {symbol} — Cross-TF TP Sweep", flush=True)
    print(f"{'='*70}", flush=True)

    entry_tfs = sorted({c.entry_tf for c in configs})
    all_tfs = set()
    for etf in entry_tfs:
        all_tfs.add(etf)
        all_tfs.update(_tfs_for_entry(etf))

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df):,} bars "
                  f"({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})",
                  flush=True)

    t0 = time.time()
    summary = run_retest_sweep(
        data_by_tf=data_by_tf,
        entry_tfs=entry_tfs,
        symbol=symbol,
        configs=configs,
    )
    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s ({elapsed/60:.1f}m)", flush=True)

    # Show top configs
    top = summary.top_by_sqn(15)
    has_trades = [r for r in summary.results if len(r.trades) > 0]
    total_trades = sum(len(r.trades) for r in summary.results)
    print(f"  Configs with trades: {len(has_trades)}/{len(summary.results)}", flush=True)
    print(f"  Total trades across all configs: {total_trades:,}", flush=True)

    if top:
        print(f"\n  TOP {len(top)} BY SQN (min 30 trades):", flush=True)
        for i, r in enumerate(top, 1):
            m = r.metrics
            cfg = r.config
            tp_info = cfg.tp_mode
            if cfg.partial_tp:
                tp_info = f"partial({cfg.partial_unit1_pct:.0%}@rr{cfg.partial_unit1_rr}+{cfg.partial_unit2_tp})"
            elif cfg.tp_mode == "htf_zone":
                tp_info = f"htf_zone@{cfg.tp_htf}"
            elif cfg.tp_mode == "fixed_rr":
                tp_info = f"rr={cfg.fixed_rr}"
            filter_info = ""
            if cfg.bias_filter != "any":
                filter_info += f" bias={cfg.bias_filter}"
            if cfg.retest_number_filter != "any":
                filter_info += f" retest={cfg.retest_number_filter}"
            print(f"    #{i}: {cfg.tf_pair} | limit | tp={tp_info} "
                  f"sl={cfg.sl_mode}{filter_info}",
                  flush=True)
            print(f"       Trades={m.get('total_trades',0):,} "
                  f"WR={m.get('win_rate',0)*100:.1f}% "
                  f"SQN={m.get('sqn',0):.2f} "
                  f"AvgR={m.get('avg_r',0):.3f} "
                  f"PF={m.get('profit_factor',0):.2f} "
                  f"TotalPips={m.get('total_pips',0):,.0f} "
                  f"AvgWin={m.get('avg_win_pips',0):.1f}p "
                  f"AvgLoss={m.get('avg_loss_pips',0):.1f}p "
                  f"AvgHold={m.get('avg_hold_hours',0):.1f}h",
                  flush=True)
    else:
        print("  No configs with >= 30 trades", flush=True)

    # Save CSV
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
            "direction": r.config.direction,
            "entry_mode": r.config.entry_mode,
            "sl_mode": r.config.sl_mode,
            "tp_mode": r.config.tp_mode,
            "tp_htf": r.config.tp_htf,
            "fixed_rr": r.config.fixed_rr,
            "sl_atr_mult": r.config.sl_atr_mult,
            "partial_tp": r.config.partial_tp,
            "partial_unit1_pct": r.config.partial_unit1_pct,
            "partial_unit1_rr": r.config.partial_unit1_rr,
            "partial_unit2_tp": r.config.partial_unit2_tp,
            "cascade_filter": r.config.cascade_filter,
            "session_filter": r.config.session_filter,
            "touch_policy": r.config.touch_policy,
            "retest_number_filter": r.config.retest_number_filter,
            "total_candidates": r.total_candidates,
            "passed_filters": len(r.funnel.passed) if r.funnel else 0,
            "num_trades": len(r.trades),
            **r.metrics,
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    out_suffix = "partial_tp_sweep" if any(r.config.partial_tp for r in summary.results) else "cross_tf_sweep"
    out_path = out_dir / f"{symbol.lower()}_{out_suffix}.csv"
    df.to_csv(out_path, index=False)
    print(f"\n  Saved {len(df)} configs to {out_path}", flush=True)

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run cross-TF TP sweep for symbols")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS,
                        help="Symbols to sweep (default: all 5)")
    parser.add_argument("--mode", choices=["cross_tf", "partial"], default="cross_tf",
                        help="Config set: cross_tf (htf_zone) or partial (partial TP)")
    args = parser.parse_args()

    symbols = args.symbols
    storage = ParquetStorage("data")
    if args.mode == "partial":
        configs = partial_tp_configs()
        label = "Partial TP"
    else:
        configs = cross_tf_tp_configs()
        label = "Cross-TF TP"
    print(f"{label} Sweep: {len(configs)} configs x {len(symbols)} symbols",
          flush=True)

    total_start = time.time()

    for symbol in symbols:
        try:
            run_symbol(symbol, storage, configs)
        except Exception as e:
            print(f"\nERROR on {symbol}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}", flush=True)
    print(f"  ALL DONE — {len(symbols)} symbols in {total_elapsed:.0f}s "
          f"({total_elapsed/60:.1f}m)", flush=True)
    print(f"{'='*70}", flush=True)

    # List output files
    print("\nOutput files:", flush=True)
    for f in sorted(Path("results").glob("*/*_*_sweep.csv")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.parent.name}/{f.name} ({size_kb:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
