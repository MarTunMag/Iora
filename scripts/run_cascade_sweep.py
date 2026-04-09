#!/usr/bin/env python -u
"""Run cascade trendline engine sweep across symbols.

Usage:
    python -u scripts/run_cascade_sweep.py
    python -u scripts/run_cascade_sweep.py --symbols GBPUSD
    python -u scripts/run_cascade_sweep.py --symbols GBPUSD --diagnostics
    python -u scripts/run_cascade_sweep.py --symbols GBPUSD --output results/sweeps/cascade/
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from math import isnan
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_sweep import cascade_sweep_configs, run_retest_sweep

DEFAULT_SYMBOLS = [
    "GBPUSD", "EURUSD", "USDJPY", "GBPJPY",
    "XAUUSD", "BTCUSD", "US500", "USTEC",
]


def _run_diagnostics(
    symbol: str,
    storage: ParquetStorage,
) -> None:
    """Run a diagnostic pass to check TL breaks, zone attribution, and cascade phases."""
    from iora.data.tf_alignment import build_aligned_multi_tf
    from iora.data.bar_iterator import iter_bars
    from iora.engine.events import EventBus
    from iora.engine.cascade_state import CascadePhaseState, cascade_state_tick
    from iora.orchestrator.push_zone_engine import (
        PushZoneEngineConfig, PushZoneEngineState,
        init_push_zone_state, push_zone_engine_tick,
    )
    from iora.constants import TF_ORDER

    all_tfs = ["M5", "M15", "H1", "H4", "D1", "W1"]
    data_by_tf = {}
    for tf in all_tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df

    if "H1" not in data_by_tf or "H4" not in data_by_tf:
        print(f"  SKIP {symbol} diagnostics — missing H1 or H4 data")
        return

    base_tf = "M5"
    config = PushZoneEngineConfig()
    tf_list = [tf for tf in TF_ORDER if tf in data_by_tf]

    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf, config.doji_pct)
    base_df = data_by_tf[base_tf]

    state = init_push_zone_state(tf_list, config.period_history_depth)
    cascade_st = CascadePhaseState()
    bus = EventBus()

    # Counters
    tl_events_by_tf: dict[str, Counter] = {}
    pivot_counts_by_tf: dict[str, dict] = {}
    phase_counts: Counter = Counter()
    max_h1_zone_count = 0
    zones_with_choch = 0
    total_zones = 0
    reversal_target_updates = 0
    bar_count = 0

    for ctx in iter_bars(base_df, aligned_df, tf_list):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        cascade_state_tick(cascade_st, state.tick_states, state.tl_states,
                           state.bar_tl_events, ctx.close)

        # Count TL break events
        for tf_key, events in state.bar_tl_events.items():
            if tf_key not in tl_events_by_tf:
                tl_events_by_tf[tf_key] = Counter()
            for ev in events:
                tl_events_by_tf[tf_key][ev.tl_type] += 1

        # Track phase
        phase_counts[cascade_st.phase] += 1
        if cascade_st.h1_push_zone_count > max_h1_zone_count:
            max_h1_zone_count = cascade_st.h1_push_zone_count

        # Track reversal targets
        if not isnan(cascade_st.h1_reversal_target_top):
            reversal_target_updates += 1

        bar_count += 1

    # Pivot counts
    for tf in ["H4", "H1", "M15"]:
        ts = state.tick_states.get(tf)
        if ts:
            pivot_counts_by_tf[tf] = {
                "prev_highs": len(ts.period.prev_highs),
                "prev_lows": len(ts.period.prev_lows),
            }

    # Zone attribution
    for tf in tf_list:
        ts = state.tick_states.get(tf)
        if ts:
            for z in ts.supply_zones + ts.demand_zones:
                total_zones += 1
                if z.caused_bos_choch:
                    zones_with_choch += 1

    print(f"\n{'='*60}")
    print(f"  === DIAGNOSTICS ({symbol}, {bar_count} bars) ===")
    print(f"{'='*60}")
    print(f"\n  TrendlineBreakEvents per TF:")
    for tf in ["H4", "H1", "M15", "M5"]:
        c = tl_events_by_tf.get(tf, Counter())
        print(f"    {tf}: impulse={c.get('impulse', 0)}, correction={c.get('correction', 0)}, "
              f"unknown={c.get('unknown', 0)}")

    print(f"\n  PeriodTracker pivot counts:")
    for tf in ["H4", "H1", "M15"]:
        p = pivot_counts_by_tf.get(tf, {})
        print(f"    {tf}: prev_highs={p.get('prev_highs', 0)} entries, "
              f"prev_lows={p.get('prev_lows', 0)} entries")

    print(f"\n  CascadeState maximums observed:")
    print(f"    h1_push_zone_count max: {max_h1_zone_count}")
    print(f"    cascade phases seen:")
    for phase, count in phase_counts.most_common():
        print(f"      {phase}: {count} ({count/bar_count*100:.1f}%)")

    print(f"\n  Zone attribution:")
    print(f"    Active zones: {total_zones}")
    print(f"    Zones with caused_bos_choch set: {zones_with_choch}")
    print(f"    Bars with H1 reversal target set: {reversal_target_updates}")

    print(f"\n  TL break recency (final state):")
    for attr in ("h4_impulse", "h4_correction", "h1_impulse", "h1_correction",
                 "m15_impulse", "m15_correction"):
        val = getattr(cascade_st, f"{attr}_bars_since_break")
        print(f"    {attr}: {'never' if val < 0 else f'{val} bars ago'}")

    print()


def run_one_symbol(
    symbol: str,
    storage: ParquetStorage,
    output_dir: Path,
    h1h4_only: bool = False,
) -> pd.DataFrame | None:
    """Run cascade sweep for one symbol."""
    print(f"\n{'='*60}")
    print(f"  {symbol}")
    print(f"{'='*60}")

    configs = cascade_sweep_configs(symbol)
    if h1h4_only:
        configs = [c for c in configs if c.tf_pair == "H1@H4"]
    print(f"  {len(configs)} configs{' (H1@H4 only)' if h1h4_only else ''}")

    # Determine needed TFs from configs
    has_m1 = any(c.tf_pair.startswith("M1") for c in configs)
    all_tfs = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"] if has_m1 else ["M5", "M15", "H1", "H4", "D1", "W1"]
    entry_tfs = ["H1", "M1"] if has_m1 else ["H1"]

    data_by_tf = {}
    for tf in all_tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"    {tf}: {len(df):,} bars")
        else:
            print(f"    {tf}: MISSING")

    if "H1" not in data_by_tf or "H4" not in data_by_tf:
        print(f"  SKIP {symbol} — missing H1 or H4 data")
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
        import traceback
        traceback.print_exc()
        return None

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s — {len(summary.results)} results")

    # Build results DataFrame
    rows = []
    for r in summary.results:
        m = r.metrics
        if m.get("total_trades", 0) == 0:
            continue
        rows.append({
            "symbol": symbol,
            "tf_pair": r.config.tf_pair,
            "cascade_phase_filter": r.config.cascade_phase_filter,
            "tl_break_filter": r.config.tl_break_filter,
            "tl_break_lookback": r.config.tl_break_lookback,
            "h1_zone_count_filter": r.config.h1_zone_count_filter,
            "reversal_target_entry": r.config.reversal_target_entry,
            "ew_overlap_filter": r.config.ew_overlap_filter,
            "ew_extension_filter": r.config.ew_extension_filter,
            "choch_conviction_filter": r.config.choch_conviction_filter,
            "min_consumption_count": r.config.min_consumption_count,
            "require_fvg_at_entry": r.config.require_fvg_at_entry,
            "min_pivot_cascade_depth": r.config.min_pivot_cascade_depth,
            "require_breaker_zone": r.config.require_breaker_zone,
            "structural_fvg_filter": r.config.structural_fvg_filter,
            "bias_filter": r.config.bias_filter,
            "test_count_filter": r.config.test_count_filter,
            "direction": r.config.direction,
            "zone_role_filter": r.config.zone_role_filter,
            # Core metrics
            "total_trades": m.get("total_trades", 0),
            "win_rate": m.get("win_rate", 0),
            "avg_r": m.get("avg_r", 0),
            "total_r": m.get("total_r", 0),
            "profit_factor": m.get("profit_factor", 0),
            "expectancy_r": m.get("expectancy_r", 0),
            # Quality metrics
            "sqn": m.get("sqn", 0),
            "sharpe": m.get("sharpe", 0),
            "sortino": m.get("sortino", 0),
            "calmar": m.get("calmar", 0),
            # Risk metrics
            "max_dd_r": m.get("max_dd_r", 0),
            "avg_win_r": m.get("avg_win_r", 0),
            "avg_loss_r": m.get("avg_loss_r", 0),
            "largest_win_r": m.get("largest_win_r", 0),
            "largest_loss_r": m.get("largest_loss_r", 0),
            # Streak / duration
            "max_win_streak": m.get("max_win_streak", 0),
            "max_loss_streak": m.get("max_loss_streak", 0),
            "avg_hold_hours": m.get("avg_hold_hours", 0),
            # Execution
            "avg_sl_pips": m.get("avg_sl_pips", 0),
        })

    if not rows:
        print(f"  No trades generated")
        return None

    df_results = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{symbol.lower()}_cascade_sweep.csv"
    df_results.to_csv(out_path, index=False)
    print(f"  Saved: {out_path}")

    # Top 10 by PF (minimum 30 trades)
    viable = df_results[df_results["total_trades"] >= 30]
    top = viable.nlargest(10, "profit_factor")
    print(f"\n  Top 10 by PF (min 30 trades):")
    for _, row in top.iterrows():
        print(f"    phase={row['cascade_phase_filter']:25s} bias={row['bias_filter']:15s} "
              f"trades={row['total_trades']:4.0f} WR={row['win_rate']:5.1%} "
              f"PF={row['profit_factor']:5.2f} avgR={row['avg_r']:+.3f} "
              f"maxDD={row['max_dd_r']:.1f}R avgWin={row['avg_win_r']:+.2f} "
              f"avgLoss={row['avg_loss_r']:+.2f} SL={row['avg_sl_pips']:.1f}pip "
              f"streak={row['max_loss_streak']:.0f}L hold={row['avg_hold_hours']:.0f}h")

    return df_results


def main():
    parser = argparse.ArgumentParser(description="Cascade trendline sweep")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols (default: all 8)")
    parser.add_argument("--diagnostics", action="store_true",
                        help="Run diagnostic pass (TL break counts, zone attribution, etc.)")
    parser.add_argument("--output", type=str, default="results/sweeps/cascade",
                        help="Output directory for CSV results")
    parser.add_argument("--h1h4-only", action="store_true",
                        help="Only run H1@H4 configs (skip M1@M5)")
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    storage = ParquetStorage("data")
    output_dir = Path(args.output)

    t_start = time.time()

    if args.diagnostics:
        for symbol in symbols:
            _run_diagnostics(symbol, storage)
    else:
        all_results = []
        for symbol in symbols:
            df = run_one_symbol(symbol, storage, output_dir, h1h4_only=args.h1h4_only)
            if df is not None:
                all_results.append(df)

    total_time = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Complete: {len(symbols)} symbols in {total_time:.0f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
