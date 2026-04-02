"""Integration test: sweep across configs on real GBPUSD data."""
from __future__ import annotations

import time

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.sweep_runner import run_sweep
from iora.strategy.config_grid import build_config_grid
from iora.strategy.strategy_config import StrategyConfig


@pytest.fixture(scope="module")
def gbpusd_timeline():
    storage = ParquetStorage("data")
    tfs = ["M5", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load("GBPUSD", tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
    if "M5" not in data_by_tf:
        pytest.skip("GBPUSD M5 data not available")
    return build_zone_timeline(data_by_tf, base_tf="M5")


class TestSweepIntegration:
    def test_grid_sweep_produces_results(self, gbpusd_timeline):
        """Grid sweep across SL/TP modes produces comparison table."""
        grid = build_config_grid({
            "sl_mode": ["zone", "atr"],
            "tp_mode": ["zone", "fixed_rr"],
            "require_nesting": [False],
            "no_trade_zones": [False],
        })
        df = run_sweep(gbpusd_timeline, grid, symbol="GBPUSD")
        assert len(df) == 4  # 2 x 2
        assert "win_rate" in df.columns
        assert "total_trades" in df.columns
        assert all(df["total_trades"] > 0)
        # Comprehensive metrics present
        assert "sqn" in df.columns
        assert "sharpe" in df.columns
        assert "profit_factor" in df.columns
        assert "max_dd_pips" in df.columns

    def test_sweep_configs_differ(self, gbpusd_timeline):
        """Different configs produce different results."""
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                           sl_mode="atr", tp_mode="fixed_rr", fixed_rr=1.0),
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                           sl_mode="atr", tp_mode="fixed_rr", fixed_rr=5.0),
        ]
        df = run_sweep(gbpusd_timeline, configs, symbol="GBPUSD")
        # Different R:R targets should produce different win rates
        assert df.iloc[0]["win_rate"] != df.iloc[1]["win_rate"]

    def test_sweep_performance(self, gbpusd_timeline):
        """Sweeping 10 configs takes < 30s (replay is cheap)."""
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                           sl_mode="atr", tp_mode="fixed_rr",
                           fixed_rr=float(rr))
            for rr in range(1, 11)
        ]
        start = time.monotonic()
        df = run_sweep(gbpusd_timeline, configs, symbol="GBPUSD")
        elapsed = time.monotonic() - start
        assert len(df) == 10
        assert elapsed < 30.0
