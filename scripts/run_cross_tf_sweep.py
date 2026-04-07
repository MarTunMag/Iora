#!/usr/bin/env python
"""Run cross-TF TP sweep — focused limit configs with HTF zone targets.

This is a FOCUSED sweep (~80-100 configs) separate from the 797-config discovery sweep.
Supports --all-symbols for full 38-symbol portfolio and --parallel-symbols for concurrency.
"""
from __future__ import annotations

import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.opportunity_runner import _tfs_for_entry
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep, cross_tf_tp_configs, partial_tp_configs

SYMBOLS = ["GBPUSD", "EURUSD", "USDJPY", "XAUUSD", "GBPJPY"]


def v3_realistic_configs() -> list[RetestConfig]:
    """V3 realistic execution sweep — TTL, BE buffer, HA trailing.

    108 configs covering:
      S1: TTL sweep (pure limit, no partial) — 15
      S2: TTL + partial TP — 15
      S3: BE buffer sweep — 12
      S4: HA trail sweep — 12
      S5: Combined best combos — 18
      S6: TTL + BE buffer combos — 9
      S7: Production candidate combos (70/30 split) — 18
      S8: Against-daily + realistic combos — 6
    """
    configs: list[RetestConfig] = []
    pairs = ["M5@M15", "M15@H1", "H1@H4"]

    # --- S1: TTL sweep (pure limit, no partial) — 15 configs ---
    for pair in pairs:
        for ttl in [1, 3, 6, 12, 0]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       fixed_rr=3.0, limit_ttl=ttl))

    # --- S2: TTL + partial TP — 15 configs ---
    for pair in pairs:
        for ttl in [1, 3, 6, 12, 0]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp="H1", limit_ttl=ttl))

    # --- S3: BE buffer sweep — 12 configs ---
    for pair in pairs:
        for be_buf in [0.0, 0.1, 0.25, 0.5]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp="H1", breakeven_buffer_atr=be_buf))

    # --- S4: HA trail sweep — 12 configs ---
    for pair in pairs:
        for trail in ["none", "ha_m5", "ha_m15", "ha_h1"]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp="H1", unit2_trail=trail))

    # --- S5: Combined best combos — 18 configs ---
    for ttl in [3, 6, 0]:
        for trail in ["ha_m15", "ha_h1"]:
            for pair in pairs:
                configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                           partial_tp=True, partial_unit1_rr=3.0,
                                           partial_unit2_tp="H1", limit_ttl=ttl,
                                           breakeven_buffer_atr=0.25, unit2_trail=trail))

    # --- S6: TTL + BE buffer combos — 9 configs ---
    for pair in pairs:
        for ttl in [3, 6, 0]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp="H1", limit_ttl=ttl,
                                       breakeven_buffer_atr=0.25))

    # --- S7: Production candidate combos (70/30 split) — 18 configs ---
    for pair in pairs:
        for ttl in [3, 6, 0]:
            for trail in ["ha_m15", "ha_h1"]:
                configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                           partial_tp=True, partial_unit1_pct=0.7,
                                           partial_unit1_rr=3.0, partial_unit2_tp="H1",
                                           limit_ttl=ttl, breakeven_buffer_atr=0.25,
                                           unit2_trail=trail))

    # --- S8: Against-daily + realistic combos — 6 configs ---
    for pair in pairs:
        for ttl in [6, 0]:
            configs.append(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp="H1", limit_ttl=ttl,
                                       breakeven_buffer_atr=0.25, unit2_trail="ha_m15",
                                       bias_filter="against_daily"))

    return configs


def m1_precision_configs() -> list[RetestConfig]:
    """M1@M5 and M1@M15 precision entry sweep — tight SL, high R:R potential."""
    configs: list[RetestConfig] = []

    # ═══ M1@M5 PRECISION ENTRIES ═══

    # --- TTL sweep (pure limit, no partial) ---
    for ttl in [1, 3, 6, 12, 0]:
        configs.append(RetestConfig(tf_pair="M1@M5", entry_mode="limit", sl_mode="zone",
                                   fixed_rr=3.0, limit_ttl=ttl))

    # --- Partial TP (Unit 2 at M15 and H1 targets) ---
    for ttl in [1, 3, 6, 0]:
        for u2tp in ["M15", "H1"]:
            configs.append(RetestConfig(tf_pair="M1@M5", entry_mode="limit", sl_mode="zone",
                                       partial_tp=True, partial_unit1_rr=3.0,
                                       partial_unit2_tp=u2tp, limit_ttl=ttl))

    # --- Higher R:R (M1 SL is tiny → can afford wider targets) ---
    for rr in [4.0, 6.0, 8.0, 10.0]:
        configs.append(RetestConfig(tf_pair="M1@M5", entry_mode="limit", sl_mode="zone",
                                   fixed_rr=rr, limit_ttl=0))

    # --- Against-daily ---
    configs.append(RetestConfig(tf_pair="M1@M5", entry_mode="limit", sl_mode="zone",
                               fixed_rr=3.0, limit_ttl=0, bias_filter="against_daily"))

    # --- Partial TP + against-daily ---
    for u2tp in ["M15", "H1"]:
        configs.append(RetestConfig(tf_pair="M1@M5", entry_mode="limit", sl_mode="zone",
                                   partial_tp=True, partial_unit1_rr=3.0,
                                   partial_unit2_tp=u2tp, limit_ttl=0,
                                   bias_filter="against_daily"))

    # ═══ COMPARISON: M5@M15 MARKET vs LIMIT ═══

    for rr in [3.0, 4.0, 6.0]:
        configs.append(RetestConfig(tf_pair="M5@M15", entry_mode="market", sl_mode="zone",
                                   fixed_rr=rr, limit_ttl=1))

    configs.append(RetestConfig(tf_pair="M5@M15", entry_mode="limit", sl_mode="zone",
                               fixed_rr=3.0, limit_ttl=0))

    # ═══ M1@M15 PRECISION (M1 entry at M15 zones — wider context) ═══

    # --- TTL sweep ---
    for ttl in [0, 3, 6]:
        configs.append(RetestConfig(tf_pair="M1@M15", entry_mode="limit", sl_mode="zone",
                                   fixed_rr=3.0, limit_ttl=ttl))

    # --- Higher R:R ---
    for rr in [4.0, 6.0, 8.0, 10.0]:
        configs.append(RetestConfig(tf_pair="M1@M15", entry_mode="limit", sl_mode="zone",
                                   fixed_rr=rr, limit_ttl=0))

    # --- Partial TP ---
    for u2tp in ["H1", "H4"]:
        configs.append(RetestConfig(tf_pair="M1@M15", entry_mode="limit", sl_mode="zone",
                                   partial_tp=True, partial_unit1_rr=3.0,
                                   partial_unit2_tp=u2tp, limit_ttl=0))

    return configs


def v3_spread_configs() -> list[RetestConfig]:
    """V3 spread test — realistic live performance with spread + SL floor + edge entry."""
    configs: list[RetestConfig] = []
    pairs = ["M5@M15", "M15@H1", "H1@H4"]
    spreads = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]

    # --- Section 1: Spread impact at each TF pair (bottom edge, TTL=0) ---
    for pair in pairs:
        for spread in spreads:
            # Pure limit, no min SL
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                fixed_rr=3.0, limit_ttl=0, spread_pips=spread))
            # With min SL = 5 pips
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                fixed_rr=3.0, limit_ttl=0, spread_pips=spread, min_sl_pips=5.0))
            # With min SL = 10 pips
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                fixed_rr=3.0, limit_ttl=0, spread_pips=spread, min_sl_pips=10.0))

    # --- Section 2: Wider SL buffer (0.15 default → 0.25, 0.50, 0.75, 1.0) ---
    for pair in pairs:
        for sl_buf in [0.15, 0.25, 0.50, 0.75, 1.0]:
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                fixed_rr=3.0, limit_ttl=0, spread_pips=1.5, sl_buffer_atr=sl_buf))

    # --- Section 3: Zone TOP edge entry (higher fill rate, wider natural SL) ---
    for pair in pairs:
        for edge in ["bottom", "top"]:
            for spread in [0.0, 1.0, 1.5, 2.0]:
                configs.append(RetestConfig(
                    tf_pair=pair, entry_mode="limit", sl_mode="zone",
                    fixed_rr=3.0, limit_ttl=0, limit_edge=edge, spread_pips=spread))

    # --- Section 4: Partial TP with spread ---
    for pair in ["M5@M15", "H1@H4"]:
        for spread in [0.0, 1.0, 1.5, 2.0]:
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                partial_tp=True, partial_unit1_rr=3.0, partial_unit2_tp="H1",
                limit_ttl=0, spread_pips=spread, min_sl_pips=5.0))

    # --- Section 5: Combined best — top edge + spread + partial ---
    for pair in ["M5@M15", "M15@H1", "H1@H4"]:
        for spread in [0.0, 1.0, 1.5, 2.0]:
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                fixed_rr=3.0, limit_ttl=0, limit_edge="top", spread_pips=spread))
            configs.append(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                partial_tp=True, partial_unit1_rr=3.0, partial_unit2_tp="H1",
                limit_ttl=0, limit_edge="top", spread_pips=spread))

    return configs


def _trail_tfs_from_configs(configs: list[RetestConfig]) -> set[str]:
    """Extract unique trail TFs from configs that use HA trailing."""
    tfs: set[str] = set()
    for cfg in configs:
        if cfg.unit2_trail != "none":
            tfs.add(cfg.unit2_trail.replace("ha_", "").upper())
    return tfs


def _format_tp_info(cfg: RetestConfig) -> str:
    if cfg.partial_tp:
        return f"partial({cfg.partial_unit1_pct:.0%}@rr{cfg.partial_unit1_rr}+{cfg.partial_unit2_tp})"
    if cfg.tp_mode == "htf_zone":
        return f"htf_zone@{cfg.tp_htf}"
    if cfg.tp_mode == "fixed_rr":
        return f"rr={cfg.fixed_rr}"
    return cfg.tp_mode


def _save_results(summary, symbol: str, suffix: str,
                   sweep_version: str = "") -> str:
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
            # V3 realistic execution columns
            "limit_ttl": r.config.limit_ttl,
            "breakeven_buffer_atr": r.config.breakeven_buffer_atr,
            "unit2_trail": r.config.unit2_trail,
            "spread_pips": r.config.spread_pips,
            "min_sl_pips": r.config.min_sl_pips,
            "sl_buffer_atr": r.config.sl_buffer_atr,
            "limit_edge": r.config.limit_edge,
            "total_candidates": r.total_candidates,
            "passed_filters": len(r.funnel.passed) if r.funnel else 0,
            "num_trades": len(r.trades),
            **r.metrics,
        }
        if sweep_version:
            row["sweep_version"] = sweep_version
        rows.append(row)
    df = pd.DataFrame(rows)
    out_path = out_dir / f"{symbol.lower()}_{suffix}.csv"
    df.to_csv(out_path, index=False)
    return str(out_path)


def run_symbol(symbol: str, storage: ParquetStorage,
               configs: list[RetestConfig], label: str = "Cross-TF TP",
               sweep_version: str = "") -> None:
    print(f"\n{'='*70}", flush=True)
    print(f"  {symbol} -- {label} Sweep", flush=True)
    print(f"{'='*70}", flush=True)

    entry_tfs = sorted({c.entry_tf for c in configs})
    all_tfs = set()
    for etf in entry_tfs:
        all_tfs.add(etf)
        all_tfs.update(_tfs_for_entry(etf))
    # Add trail TFs needed for HA trailing
    all_tfs.update(_trail_tfs_from_configs(configs))

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df):,} bars "
                  f"({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})",
                  flush=True)

    if not data_by_tf:
        print(f"  SKIP {symbol}: no data loaded", flush=True)
        return

    t0 = time.time()
    summary = run_retest_sweep(
        data_by_tf=data_by_tf,
        entry_tfs=entry_tfs,
        symbol=symbol,
        configs=configs,
    )
    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s ({elapsed/60:.1f}m)", flush=True)

    has_trades = [r for r in summary.results if len(r.trades) > 0]
    total_trades = sum(len(r.trades) for r in summary.results)
    print(f"  Configs with trades: {len(has_trades)}/{len(summary.results)}", flush=True)
    print(f"  Total trades across all configs: {total_trades:,}", flush=True)

    top = summary.top_by_sqn(10)
    if top:
        print(f"\n  TOP {len(top)} BY SQN (min 30 trades):", flush=True)
        for i, r in enumerate(top, 1):
            m = r.metrics
            cfg = r.config
            tp_info = _format_tp_info(cfg)
            filter_info = ""
            if cfg.bias_filter != "any":
                filter_info += f" bias={cfg.bias_filter}"
            if cfg.retest_number_filter != "any":
                filter_info += f" retest={cfg.retest_number_filter}"
            v3_info = ""
            if cfg.limit_ttl != 1:
                v3_info += f" ttl={cfg.limit_ttl}"
            if cfg.breakeven_buffer_atr > 0:
                v3_info += f" be_buf={cfg.breakeven_buffer_atr}"
            if cfg.unit2_trail != "none":
                v3_info += f" trail={cfg.unit2_trail}"
            if cfg.spread_pips > 0:
                v3_info += f" spread={cfg.spread_pips}p"
            if cfg.min_sl_pips > 0:
                v3_info += f" minSL={cfg.min_sl_pips}p"
            if cfg.sl_buffer_atr != 0.15:
                v3_info += f" slBuf={cfg.sl_buffer_atr}"
            if cfg.limit_edge != "bottom":
                v3_info += f" edge={cfg.limit_edge}"
            print(f"    #{i}: {cfg.tf_pair} | limit | tp={tp_info} "
                  f"sl={cfg.sl_mode}{filter_info}{v3_info}",
                  flush=True)
            print(f"       Trades={m.get('total_trades',0):,} "
                  f"WR={m.get('win_rate',0)*100:.1f}% "
                  f"SQN={m.get('sqn',0):.2f} "
                  f"AvgR={m.get('avg_r',0):.3f} "
                  f"PF={m.get('profit_factor',0):.2f} "
                  f"AvgWin={m.get('avg_win_pips',0):.1f}p "
                  f"AvgLoss={m.get('avg_loss_pips',0):.1f}p "
                  f"AvgHold={m.get('avg_hold_hours',0):.1f}h",
                  flush=True)
    else:
        print("  No configs with >= 30 trades", flush=True)

    # Save CSV
    if sweep_version:
        # V3+ mode: single file with sweep_version column
        path = _save_results(summary, symbol, f"{sweep_version}_sweep",
                             sweep_version=sweep_version)
        print(f"\n  Saved {len(summary.results)} configs to {path}", flush=True)
    else:
        # Legacy: split partial and cross_tf
        has_partial = any(r.config.partial_tp for r in summary.results)
        has_cross = any(not r.config.partial_tp for r in summary.results)

        if has_partial and has_cross:
            from iora.strategy.retest_sweep import SweepSummary
            partial_results = [r for r in summary.results if r.config.partial_tp]
            cross_results = [r for r in summary.results if not r.config.partial_tp]
            ps = SweepSummary(results=partial_results)
            cs = SweepSummary(results=cross_results)
            p1 = _save_results(ps, symbol, "partial_tp_sweep")
            p2 = _save_results(cs, symbol, "cross_tf_sweep")
            print(f"\n  Saved {len(partial_results)} partial configs to {p1}", flush=True)
            print(f"  Saved {len(cross_results)} cross-TF configs to {p2}", flush=True)
        else:
            suffix = "partial_tp_sweep" if has_partial else "cross_tf_sweep"
            path = _save_results(summary, symbol, suffix)
            print(f"\n  Saved {len(summary.results)} configs to {path}", flush=True)

    return summary


def _run_symbol_safe(symbol: str, storage: ParquetStorage,
                     configs: list[RetestConfig], label: str,
                     sweep_version: str = "") -> tuple[str, float, bool]:
    """Wrapper for parallel execution. Returns (symbol, elapsed, success)."""
    t0 = time.time()
    try:
        run_symbol(symbol, storage, configs, label, sweep_version=sweep_version)
        return (symbol, time.time() - t0, True)
    except Exception as e:
        print(f"\nERROR on {symbol}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return (symbol, time.time() - t0, False)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run cross-TF TP sweep for symbols")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Symbols to sweep (default: core 5)")
    parser.add_argument("--all-symbols", action="store_true",
                        help="Sweep all symbols found in data/raw/")
    parser.add_argument("--mode", choices=["cross_tf", "partial", "all", "realistic",
                                          "m1_precision", "spread_test"],
                        default="cross_tf",
                        help="Config set: cross_tf, partial, all, realistic (v3), "
                             "m1_precision, or spread_test")
    parser.add_argument("--parallel-symbols", type=int, default=1,
                        help="Number of symbols to process in parallel")
    parser.add_argument("--pairs", type=str, default=None,
                        help="Comma-separated TF pairs to filter configs "
                             "(e.g. M1@M5,M1@M15)")
    args = parser.parse_args()

    if args.all_symbols:
        symbols = sorted([
            d for d in os.listdir("data/raw")
            if os.path.isdir(f"data/raw/{d}")
        ])
    else:
        symbols = args.symbols or SYMBOLS

    storage = ParquetStorage("data")

    sweep_version = ""
    if args.mode == "realistic":
        configs = v3_realistic_configs()
        label = "V3 Realistic Execution"
        sweep_version = "v3_realistic"
    elif args.mode == "m1_precision":
        configs = m1_precision_configs()
        label = "V3 M1 Precision Entry"
        sweep_version = "v3_m1_precision"
    elif args.mode == "spread_test":
        configs = v3_spread_configs()
        label = "V3 Spread Reality Test"
        sweep_version = "v3_spread_test"
    elif args.mode == "all":
        cross_configs = cross_tf_tp_configs()
        partial_configs_list = partial_tp_configs()
        configs = cross_configs + partial_configs_list
        label = "Cross-TF + Partial TP"
    elif args.mode == "partial":
        configs = partial_tp_configs()
        label = "Partial TP"
    else:
        configs = cross_tf_tp_configs()
        label = "Cross-TF TP"

    # Apply --pairs filter if specified
    if args.pairs:
        allowed_pairs = set(args.pairs.split(","))
        configs = [c for c in configs if c.tf_pair in allowed_pairs]

    print(f"{label} Sweep: {len(configs)} configs x {len(symbols)} symbols",
          flush=True)
    print(f"Parallel workers: {args.parallel_symbols}", flush=True)
    print(f"Symbols: {', '.join(symbols)}", flush=True)

    total_start = time.time()
    completed = 0
    failed = []

    if args.parallel_symbols > 1:
        with ThreadPoolExecutor(max_workers=args.parallel_symbols) as executor:
            futures = {
                executor.submit(_run_symbol_safe, sym, storage, configs, label,
                                sweep_version): sym
                for sym in symbols
            }
            for future in as_completed(futures):
                sym, elapsed, success = future.result()
                completed += 1
                if not success:
                    failed.append(sym)
                print(f"\n  [{completed}/{len(symbols)}] {sym} done in "
                      f"{elapsed:.0f}s {'OK' if success else 'FAILED'}",
                      flush=True)
    else:
        for symbol in symbols:
            try:
                run_symbol(symbol, storage, configs, label,
                           sweep_version=sweep_version)
            except Exception as e:
                print(f"\nERROR on {symbol}: {e}", flush=True)
                import traceback
                traceback.print_exc()
                failed.append(symbol)
            completed += 1
            print(f"\n  [{completed}/{len(symbols)}] done", flush=True)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}", flush=True)
    print(f"  ALL DONE -- {len(symbols)} symbols in {total_elapsed:.0f}s "
          f"({total_elapsed/60:.1f}m)", flush=True)
    if failed:
        print(f"  FAILED: {', '.join(failed)}", flush=True)
    print(f"{'='*70}", flush=True)

    # List output files
    print("\nOutput files:", flush=True)
    for f in sorted(Path("results").glob("*/*_*_sweep.csv")):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.parent.name}/{f.name} ({size_kb:.1f} KB)", flush=True)


if __name__ == "__main__":
    main()
