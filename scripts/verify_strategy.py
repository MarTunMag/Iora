# scripts/verify_strategy.py
"""Verify push zone strategy against real GBPUSD data.

Runs multiple configs, prints signal/trade counts and basic metrics.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.strategy_config import StrategyConfig, make_preset
from iora.strategy.push_zone_strategy import evaluate_strategy


def main():
    storage = ParquetStorage("data")
    symbol = "GBPUSD"

    tfs = ["M5", "M15", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df)} bars, {df.index[0]} -> {df.index[-1]}")

    print("\nBuilding zone timeline (this is the expensive step)...")
    t0 = time.monotonic()
    timeline = build_zone_timeline(data_by_tf, base_tf="M5")
    t_build = time.monotonic() - t0
    print(f"  Timeline: {len(timeline)} bars in {t_build:.1f}s")

    # Test multiple configs
    configs = {
        "default": StrategyConfig(require_nesting=False, no_trade_zones=False),
        "aggressive": make_preset("aggressive"),
        "conservative": make_preset("conservative"),
        "long_only": StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="long",
        ),
        "bos_only": StrategyConfig(
            require_nesting=False, no_trade_zones=False, struct_filter="bos_only",
        ),
    }

    print(f"\n{'Config':<20} {'Signals':>8} {'Trades':>8} {'Open':>6} "
          f"{'Win':>6} {'Loss':>6} {'WR%':>6} {'Time':>6}")
    print("-" * 80)

    for name, cfg in configs.items():
        t0 = time.monotonic()
        result = evaluate_strategy(timeline, cfg, symbol=symbol)
        elapsed = time.monotonic() - t0

        wins = sum(1 for t in result.trades if t["pnl_pips"] > 0)
        losses = sum(1 for t in result.trades if t["pnl_pips"] <= 0)
        wr = (wins / len(result.trades) * 100) if result.trades else 0

        print(f"{name:<20} {len(result.signals):>8} {len(result.trades):>8} "
              f"{len(result.open_trades):>6} {wins:>6} {losses:>6} "
              f"{wr:>5.1f}% {elapsed:>5.2f}s")

    # Print sample trades from default config
    result = evaluate_strategy(timeline, configs["default"], symbol=symbol)
    print(f"\n--- Sample Trades (first 10) ---")
    for t in result.trades[:10]:
        pnl = t["pnl_pips"]
        print(f"  {t['direction']:>5} {t['signal_type']:<10} {t['struct_cls']:<5} "
              f"@ {t['entry_price']:.5f} -> {t['exit_price']:.5f} "
              f"{t['exit_reason']:<7} {pnl:>+8.1f} pips  "
              f"RR={t['rr_ratio']:.1f}")


if __name__ == "__main__":
    main()
