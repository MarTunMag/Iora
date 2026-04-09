#!/usr/bin/env python -u
"""Run M1@M5 signal-flip sweep across symbols.

Usage:
    python -u scripts/run_signal_flip_sweep.py
    python -u scripts/run_signal_flip_sweep.py --symbols GBPUSD
    python -u scripts/run_signal_flip_sweep.py --symbols GBPUSD --output results/sweeps/signal_flip/
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep

DEFAULT_SYMBOLS = [
    "GBPUSD", "EURUSD", "USDJPY", "GBPJPY",
    "XAUUSD", "BTCUSD", "US500", "USTEC",
]

# Default spreads per symbol (in pips)
SPREAD_MAP: dict[str, float] = {
    "GBPUSD": 1.5, "EURUSD": 1.0, "USDJPY": 1.0,
    "GBPJPY": 2.5, "XAUUSD": 2.5, "BTCUSD": 10.0,
    "US500": 1.0, "USTEC": 1.5,
}


def signal_flip_configs(symbol: str) -> list[RetestConfig]:
    """Generate signal-flip sweep configs for one symbol."""
    spread = SPREAD_MAP.get(symbol, 1.5)
    configs: list[RetestConfig] = []

    # --- Baseline: fixed SL/TP M1@M5 for comparison ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="fixed_sl_tp",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # --- Config 1: Raw signal-flip (no cascade filters) ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="signal_flip",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # --- Config 2: Signal-flip with safety SL ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="signal_flip_with_safety",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # --- Config 3: Signal-flip with h4_correction filter ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="signal_flip",
        spread_pips=spread,
        cascade_phase_filter="h4_correction",
        entry_mode="market",
        direction="both",
    ))

    # --- Config 4: Signal-flip with against_daily bias ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="signal_flip",
        spread_pips=spread,
        bias_filter="against_daily",
        entry_mode="market",
        direction="both",
    ))

    # --- Config 5: Signal-flip with correction TL break ---
    configs.append(RetestConfig(
        tf_pair="M1@M5",
        exit_mode="signal_flip",
        spread_pips=spread,
        tl_break_filter="after_correction_break",
        entry_mode="market",
        direction="both",
    ))

    # --- Entry TF variations ---
    # M5@M15 signal-flip
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M1@M15 signal-flip
    configs.append(RetestConfig(
        tf_pair="M1@M15",
        exit_mode="signal_flip",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # --- Windowed configs (active-window architecture) ---
    # M5@M15 windowed with h4_correction
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        cascade_phase_filter="h4_correction",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M5@M15 windowed with correction TL break
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        tl_break_filter="after_correction_break",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M5@M15 windowed with h4_correction + correction TL break
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        cascade_phase_filter="h4_correction",
        tl_break_filter="after_correction_break",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # --- Layer 2.5: Structural sequence configs ---
    # M5@M15 windowed with M15 correction TL break (internal correction over)
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        m15_tl_state="after_correction_break",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M5@M15 windowed with H4 lo/hi break context
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        htf_level_break_context="after_h4_lo_x",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M5@M15 windowed: full XAUUSD sequence (h4_correction + m15 TL break)
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        cascade_phase_filter="h4_correction",
        m15_tl_state="after_correction_break",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    # M5@M15 windowed: h4_correction + m15 TL break + H4 lo X
    configs.append(RetestConfig(
        tf_pair="M5@M15",
        exit_mode="signal_flip",
        flip_window="windowed",
        cascade_phase_filter="h4_correction",
        m15_tl_state="after_correction_break",
        htf_level_break_context="after_h4_lo_x",
        spread_pips=spread,
        entry_mode="market",
        direction="both",
    ))

    return configs


def run_one_symbol(
    symbol: str,
    storage: ParquetStorage,
    output_dir: Path,
) -> pd.DataFrame | None:
    """Run signal-flip sweep for one symbol."""
    print(f"\n{'='*60}")
    print(f"  {symbol}")
    print(f"{'='*60}")

    configs = signal_flip_configs(symbol)
    print(f"  {len(configs)} configs")

    # Need M1 for signal-flip entry TF
    all_tfs = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]
    entry_tfs = ["M1", "M5"]

    data_by_tf = {}
    for tf in all_tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"    {tf}: {len(df):,} bars")
        else:
            print(f"    {tf}: MISSING")

    if "M1" not in data_by_tf or "M5" not in data_by_tf:
        print(f"  SKIP {symbol} — missing M1 or M5 data")
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
            "exit_mode": r.config.exit_mode,
            "cascade_phase_filter": r.config.cascade_phase_filter,
            "bias_filter": r.config.bias_filter,
            "tl_break_filter": r.config.tl_break_filter,
            "htf_level_break_context": r.config.htf_level_break_context,
            "m15_tl_state": r.config.m15_tl_state,
            "flip_window": r.config.flip_window,
            "direction": r.config.direction,
            "spread_pips": r.config.spread_pips,
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
            "avg_sl_pips": m.get("avg_sl_pips", 0),
            # Signal-flip metrics
            "flip_count": m.get("flip_count", 0),
            "avg_flip_pips": m.get("avg_flip_pips", 0),
            "avg_flip_duration_mins": m.get("avg_flip_duration_mins", 0),
            "gross_pnl_pips": m.get("gross_pnl_pips", 0),
            "total_spread_cost_pips": m.get("total_spread_cost_pips", 0),
            "net_after_spread": m.get("net_after_spread", 0),
            "safety_sl_hits": m.get("safety_sl_hits", 0),
            "open_at_close": m.get("open_at_close", 0),
            "total_pnl_pips": m.get("total_pnl_pips", 0),
        })

    if not rows:
        print(f"  No trades generated")
        return None

    df_results = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{symbol.lower()}_signal_flip_sweep.csv"
    df_results.to_csv(out_path, index=False)
    print(f"  Saved: {out_path}")

    # Print all results
    print(f"\n  Results:")
    for _, row in df_results.iterrows():
        label = f"{row['tf_pair']} {row['exit_mode']}"
        if row.get('flip_window', 'always') == "windowed":
            label += " [W]"
        if row['cascade_phase_filter'] != "any":
            label += f" +{row['cascade_phase_filter']}"
        if row['bias_filter'] != "any":
            label += f" +{row['bias_filter']}"
        if row['tl_break_filter'] != "any":
            label += f" +{row['tl_break_filter']}"
        if row.get('htf_level_break_context', 'any') != "any":
            label += f" +{row['htf_level_break_context']}"
        if row.get('m15_tl_state', 'any') != "any":
            label += f" +m15:{row['m15_tl_state']}"

        print(f"    {label:50s} "
              f"trades={row['total_trades']:5.0f} WR={row['win_rate']:5.1%} "
              f"PF={row['profit_factor']:5.2f} avgR={row['avg_r']:+.3f} "
              f"flips={row['flip_count']:.0f} avgFlip={row['avg_flip_pips']:.1f}pip "
              f"gross={row['gross_pnl_pips']:.0f} spread={row['total_spread_cost_pips']:.0f} "
              f"net={row['net_after_spread']:.0f}pip "
              f"maxDD={row['max_dd_r']:.1f}R streak={row['max_loss_streak']:.0f}L")

    # Annual equity breakdown for signal-flip configs
    print(f"\n  Annual breakdown (signal-flip configs):")
    for r in summary.results:
        if r.config.exit_mode not in ("signal_flip", "signal_flip_with_safety"):
            continue
        if not r.trades:
            continue
        label = f"{r.config.tf_pair} {r.config.exit_mode}"
        if r.config.cascade_phase_filter != "any":
            label += f" +{r.config.cascade_phase_filter}"

        # Group trades by year
        year_pnl: dict[int, float] = {}
        year_count: dict[int, int] = {}
        for t in r.trades:
            yr = t.exit_time.year
            year_pnl[yr] = year_pnl.get(yr, 0.0) + t.pnl_pips
            year_count[yr] = year_count.get(yr, 0) + 1

        print(f"\n    {label}:")
        for yr in sorted(year_pnl.keys()):
            pnl = year_pnl[yr]
            cnt = year_count[yr]
            daily = pnl / 252 if cnt > 0 else 0
            print(f"      {yr}: {pnl:+10.0f} pip  ({cnt:5d} trades, {daily:+.1f} pip/day)")
        total = sum(year_pnl.values())
        years = len(year_pnl)
        print(f"      TOTAL: {total:+10.0f} pip over {years} years ({total/years:+.0f}/yr)")

    return df_results


def main():
    parser = argparse.ArgumentParser(description="Signal-flip M1@M5 sweep")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbols (default: all 8)")
    parser.add_argument("--output", type=str, default="results/sweeps/signal_flip",
                        help="Output directory for CSV results")
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    storage = ParquetStorage("data")
    output_dir = Path(args.output)

    t_start = time.time()

    all_results = []
    for symbol in symbols:
        df = run_one_symbol(symbol, storage, output_dir)
        if df is not None:
            all_results.append(df)

    total_time = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"  Complete: {len(symbols)} symbols in {total_time:.0f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
