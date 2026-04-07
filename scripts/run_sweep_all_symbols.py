#!/usr/bin/env python
"""Run retest sweep for all 5 analysis symbols, save CSVs.

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
from iora.strategy.retest_sweep import run_retest_sweep, default_configs

SYMBOLS = ["GBPUSD", "EURUSD", "USDJPY", "XAUUSD", "GBPJPY"]


def run_symbol(symbol: str, storage: ParquetStorage, configs: list[RetestConfig]) -> None:
    print(f"\n{'='*70}", flush=True)
    print(f"  {symbol}", flush=True)
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
    top = summary.top_by_sqn(10)
    has_trades = [r for r in summary.results if len(r.trades) > 0]
    total_trades = sum(len(r.trades) for r in summary.results)
    print(f"  Configs with trades: {len(has_trades)}/{len(summary.results)}", flush=True)
    print(f"  Total trades across all configs: {total_trades:,}", flush=True)

    if top:
        print(f"\n  TOP {len(top)} BY SQN (min 30 trades):", flush=True)
        for i, r in enumerate(top, 1):
            m = r.metrics
            cfg = r.config
            hma_info = ""
            if cfg.hma_filter != "any":
                hma_info += f" hma={cfg.hma_filter}"
            if cfg.hma_cross_trigger != "none":
                hma_info += f" cross={cfg.hma_cross_trigger}@{cfg.hma_cross_lookback}"
            entry_info = cfg.entry_mode
            if cfg.entry_mode == "cascade_layered":
                entry_info += f"/{cfg.layered_sl_mode}"
            print(f"    #{i}: {cfg.tf_pair} | entry={entry_info} "
                  f"bias={cfg.bias_filter} role={cfg.zone_role_filter} "
                  f"sl={cfg.sl_mode} rr={cfg.fixed_rr}{hma_info}",
                  flush=True)
            print(f"       Trades={m.get('total_trades',0):,} "
                  f"WR={m.get('win_rate',0)*100:.1f}% "
                  f"SQN={m.get('sqn',0):.2f} "
                  f"AvgR={m.get('avg_r',0):.3f} "
                  f"PF={m.get('profit_factor',0):.2f} "
                  f"MaxDD={m.get('max_dd_r',0):.1f}R",
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
            "fixed_rr": r.config.fixed_rr,
            "sl_atr_mult": r.config.sl_atr_mult,
            "cascade_filter": r.config.cascade_filter,
            "cascade_lookback": r.config.cascade_lookback,
            "cascade_direction": r.config.cascade_direction,
            "session_filter": r.config.session_filter,
            "touch_policy": r.config.touch_policy,
            "max_replacement_count": r.config.max_replacement_count,
            "min_bias_strength": r.config.min_bias_strength,
            "birth_pattern_filter": r.config.birth_pattern_filter,
            "retest_number_filter": r.config.retest_number_filter,
            "time_since_creation_filter": r.config.time_since_creation_filter,
            "parent_tf_boundary_filter": r.config.parent_tf_boundary_filter,
            "inside_w_zone_filter": r.config.inside_w_zone_filter,
            "d_to_w_filter": r.config.d_to_w_filter,
            "near_pdh_pdl": r.config.near_pdh_pdl,
            "premium_discount": r.config.premium_discount,
            "layered_sl_mode": r.config.layered_sl_mode,
            "hma_filter": r.config.hma_filter,
            "hma_cross_trigger": r.config.hma_cross_trigger,
            "hma_cross_lookback": str(r.config.hma_cross_lookback),
            "hma_period": r.config.hma_period,
            "hma_source": r.config.hma_source,
            "total_candidates": r.total_candidates,
            "passed_filters": len(r.funnel.passed) if r.funnel else 0,
            "num_trades": len(r.trades),
            **r.metrics,
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    out_path = out_dir / f"{symbol.lower()}_retest_sweep.csv"
    df.to_csv(out_path, index=False)
    print(f"\n  Saved {len(df)} configs to {out_path}", flush=True)

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run retest sweep for symbols")
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS,
                        help="Symbols to sweep (default: all 5)")
    parser.add_argument("--parallel-symbols", type=int, default=1,
                        help="Number of symbols to run concurrently (default: 1, max: 2)")
    args = parser.parse_args()

    symbols = args.symbols
    max_sym_workers = min(args.parallel_symbols, 2)

    storage = ParquetStorage("data")
    configs = default_configs()
    print(f"Running retest sweep: {len(configs)} configs × {len(symbols)} symbols"
          f" (parallel_symbols={max_sym_workers})", flush=True)

    total_start = time.time()

    if max_sym_workers > 1 and len(symbols) > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=max_sym_workers) as pool:
            futures = {
                pool.submit(run_symbol, sym, storage, configs): sym
                for sym in symbols
            }
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"\nERROR on {sym}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
    else:
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
    for f in sorted(Path("results").glob("*/*_retest_sweep.csv")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.parent.name}/{f.name} ({size_kb:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
