#!/usr/bin/env python
"""
Run Growth-only backtest on historical data.

Usage:
    python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01
    python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01 --balance 1000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from flint.data.parquet_storage import ParquetStorage
from flint.orchestrator.pipeline import PipelineConfig
from flint.orchestrator.signal_engine import run_signal_engine
from flint.backtest.evaluator import evaluate_trades
from flint.backtest.reporter import PerformanceReporter
from flint.paths import DATA_DIR, REPORTS_DIR

logger = logging.getLogger(__name__)

# TFs required by the signal engine
REQUIRED_TFS = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]


def main():
    parser = argparse.ArgumentParser(description="Run Growth-only backtest")
    parser.add_argument("--symbol", default="GBPUSD", help="Trading symbol")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--base-tf", default="M15", help="Base timeframe")
    parser.add_argument("--balance", type=float, default=1000.0, help="Initial balance")
    parser.add_argument("--risk-pct", type=float, default=0.01, help="Risk per trade")
    parser.add_argument("--run-name", default="", help="Report folder name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    run_name = args.run_name or f"{args.symbol}_{args.start}_{args.end}"
    output_dir = REPORTS_DIR / "backtest" / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    logger.info(f"Loading {args.symbol} data from {args.start} to {args.end}...")
    storage = ParquetStorage(DATA_DIR)
    data_by_tf: dict[str, pd.DataFrame] = {}

    for tf in REQUIRED_TFS:
        df = storage.load(args.symbol, tf, start_date=args.start, end_date=args.end)
        if not df.empty:
            data_by_tf[tf] = df
            logger.info(f"  {tf}: {len(df)} bars")
        else:
            logger.warning(f"  {tf}: no data")

    if args.base_tf not in data_by_tf:
        logger.error(f"No data for base TF {args.base_tf}")
        sys.exit(1)

    # 2. Run signal engine (Growth lifecycle only)
    logger.info("Running signal engine (Growth entry + exit + SL trail)...")
    t0 = time.time()
    signal_output = run_signal_engine(
        data_by_tf,
        args.base_tf,
        pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
        account_balance=args.balance,
        risk_pct=args.risk_pct,
        disabled_rules=["scalp_entry", "growth_addon", "tp_targets"],
    )
    elapsed = time.time() - t0
    logger.info(f"Signal engine completed in {elapsed:.1f}s")
    logger.info(f"  Signals: {len(signal_output.signals)}")
    logger.info(f"  Trade log events: {len(signal_output.trade_log)}")

    # 3. Evaluate trades
    logger.info("Evaluating trades...")
    last_close = float(data_by_tf[args.base_tf].iloc[-1]["close"])
    result = evaluate_trades(
        signal_output, args.symbol,
        initial_balance=args.balance,
        last_close=last_close,
    )
    logger.info(f"  Completed trades: {len(result.trades)}")

    if not result.trades:
        logger.warning("No trades to evaluate. Check rules and data range.")
        sys.exit(0)

    # 4. Generate reports
    logger.info("Generating reports...")
    reporter = PerformanceReporter(reports_dir=output_dir)

    report = reporter.generate_report(
        result.metrics, args.symbol, run_name,
        result.trades, initial_balance=args.balance,
    )
    reporter.save_report(report, "metrics.json")
    reporter.save_text_summary(report, "summary.txt")

    # Charts
    reporter.generate_all_charts(
        result.trades, initial_balance=args.balance,
        output_dir=output_dir,
    )

    # 5. Save trade details with contexts
    trades_detail = []
    for trade, ctx in zip(result.trades, result.trade_contexts):
        td = {
            "trade_id": trade.trade_id,
            "direction": "long" if trade.direction == 1 else "short",
            "entry_time": str(trade.entry_time),
            "exit_time": str(trade.exit_time),
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "lots": trade.position_size,
            "pnl_dollars": round(trade.pnl_dollars, 2),
            "return_r": round(trade.return_r, 2),
            "exit_reason": trade.exit_reason,
            "sl_price": trade.sl_price,
            "cost_dollars": round(trade.cost_dollars, 2),
            "holding_hours": round(
                trade.holding_period.total_seconds() / 3600, 1
            ),
            "entry_context": ctx,
        }
        trades_detail.append(td)

    trades_path = output_dir / "trades.json"
    with open(trades_path, "w") as f:
        json.dump(trades_detail, f, indent=2, default=str)

    # 6. Save signal breakdown
    breakdown_path = output_dir / "signal_breakdown.json"
    with open(breakdown_path, "w") as f:
        json.dump(result.signal_type_breakdown, f, indent=2)

    # 7. Print summary
    m = result.metrics
    print("\n" + "=" * 60)
    print(f"  BACKTEST RESULTS: {args.symbol} {args.start} -> {args.end}")
    print("=" * 60)
    print(f"  Trades:        {m.get('total_trades', 0)}")
    print(f"  Win Rate:      {m.get('win_rate', 0):.1%}")
    print(f"  Total R:       {m.get('total_r', 0):+.1f}")
    print(f"  Expectancy:    {m.get('expectancy', 0):+.2f}R")
    print(f"  SQN:           {m.get('sqn', 0):.2f}")
    print(f"  Profit Factor: {m.get('profit_factor', 0):.2f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown_pct', 0):.1f}%")
    print(f"  Sharpe:        {m.get('sharpe', 0):.2f}")
    print(f"  Total P&L:     ${m.get('total_pnl', 0):+.2f}")
    print(f"  Balance:       ${args.balance}")
    print("=" * 60)

    # Breakdown summary
    print("\n  BREAKDOWN BY ZONE TF:")
    for zone, gm in result.signal_type_breakdown.get("by_zone_tf", {}).items():
        print(f"    {zone:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY DIRECTION:")
    for d, gm in result.signal_type_breakdown.get("by_direction", {}).items():
        print(f"    {d:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY BIAS ALIGNMENT:")
    for b, gm in result.signal_type_breakdown.get("by_bias_alignment", {}).items():
        print(f"    {b:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY EXIT REASON:")
    for er, gm in result.signal_type_breakdown.get("by_exit_reason", {}).items():
        print(f"    {er:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print(f"\n  Reports saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
