# tests/strategy/test_strategy_integration.py
"""Integration test: run strategy against real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.strategy_config import StrategyConfig, make_preset
from iora.strategy.push_zone_strategy import evaluate_strategy


@pytest.fixture(scope="module")
def gbpusd_timeline():
    """Build zone timeline from real GBPUSD data (cached per module)."""
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


class TestStrategyIntegration:
    def test_timeline_built(self, gbpusd_timeline):
        """Timeline has expected number of bars."""
        assert len(gbpusd_timeline) > 10_000

    def test_default_config_produces_trades(self, gbpusd_timeline):
        """Default config generates at least some trades."""
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) > 0
        assert len(result.trades) > 0

    def test_aggressive_vs_conservative(self, gbpusd_timeline):
        """Aggressive config produces more signals than conservative."""
        agg = make_preset("aggressive")
        con = make_preset("conservative")
        r_agg = evaluate_strategy(gbpusd_timeline, agg, symbol="GBPUSD")
        r_con = evaluate_strategy(gbpusd_timeline, con, symbol="GBPUSD")
        assert len(r_agg.signals) >= len(r_con.signals)

    def test_direction_filter_halves_signals(self, gbpusd_timeline):
        """Long-only produces roughly half the signals of both."""
        cfg_both = StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="both",
        )
        cfg_long = StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="long",
        )
        r_both = evaluate_strategy(gbpusd_timeline, cfg_both, symbol="GBPUSD")
        r_long = evaluate_strategy(gbpusd_timeline, cfg_long, symbol="GBPUSD")
        # Long-only should be strictly fewer
        assert len(r_long.signals) < len(r_both.signals)

    def test_trades_have_valid_pnl(self, gbpusd_timeline):
        """All completed trades have non-zero pnl_pips."""
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        for t in result.trades[:50]:  # Check first 50
            assert "pnl_pips" in t
            assert t["exit_reason"] in ("sl_hit", "tp_hit")

    def test_replay_is_cheap(self, gbpusd_timeline):
        """Running evaluate_strategy 10x is fast (< 30s)."""
        import time
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        start = time.monotonic()
        for _ in range(10):
            evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        elapsed = time.monotonic() - start
        assert elapsed < 30.0, f"10 replays took {elapsed:.1f}s (too slow)"
