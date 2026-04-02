"""Tests for sweep runner and comprehensive metrics."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.strategy.sweep_runner import (
    run_sweep, run_multi_symbol_sweep, compute_metrics,
)
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.trade_converter import SweepTradeRecord
from iora.engine.push_zone_models import PushZone


def _zone(is_supply: bool, top: float, bottom: float) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
        is_push=True, struct_cls="BOS",
        swing_cls="HH" if is_supply else "LL", count_num=1,
    )


def _make_timeline(n: int = 50) -> list[ZoneTimelineBar]:
    """Synthetic timeline with one fire at bar 5."""
    bars: list[ZoneTimelineBar] = []
    demand = _zone(False, 1.2900, 1.2880)
    for i in range(n):
        fires = [demand] if i == 5 else []
        bars.append(ZoneTimelineBar(
            timestamp=pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=5 * i),
            open_=1.29 + 0.001 * i, high=1.295 + 0.001 * i,
            low=1.285 + 0.001 * i, close=1.29 + 0.001 * i,
            fires=fires, breaks=[],
            zones_by_tf={"M5": [demand] if i >= 5 else []},
            trend_by_tf={"M5": 0},
            period_levels_by_tf={"M5": {"highs": [], "lows": []}},
            zone_counts_by_tf={"M5": (0, 1 if i >= 5 else 0)},
        ))
    return bars


def _make_record(
    pnl_pips: float = 10.0,
    return_r: float = 1.0,
    direction: int = 1,
    signal_type: str = "push",
    struct_cls: str = "BOS",
    exit_reason: str = "tp_hit",
    hold_hours: float = 2.0,
) -> SweepTradeRecord:
    entry_time = pd.Timestamp("2025-01-01 10:00")
    return SweepTradeRecord(
        trade_id="t_0001",
        symbol="GBPUSD",
        direction=direction,
        entry_time=entry_time,
        exit_time=entry_time + pd.Timedelta(hours=hold_hours),
        entry_price=1.2950,
        exit_price=1.2960 if pnl_pips > 0 else 1.2940,
        pnl_pips=pnl_pips,
        risk_pips=30.0,
        reward_pips=60.0,
        return_r=return_r,
        rr_ratio=2.0,
        exit_reason=exit_reason,
        sl_price=1.2920,
        tp_price=1.3010,
        signal_type=signal_type,
        struct_cls=struct_cls,
        zone_tf="M5",
    )


# ---------------------------------------------------------------------------
# compute_metrics tests
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_empty_records(self):
        """No trades returns zero metrics."""
        m = compute_metrics([])
        assert m["total_trades"] == 0
        assert m["win_rate"] == 0.0
        assert m["sqn"] == 0.0

    def test_all_winners(self):
        """All winning trades gives 100% win rate."""
        records = [
            _make_record(pnl_pips=10.0, return_r=0.5),
            _make_record(pnl_pips=20.0, return_r=1.0),
            _make_record(pnl_pips=15.0, return_r=0.75),
        ]
        m = compute_metrics(records)
        assert m["total_trades"] == 3
        assert m["win_rate"] == 1.0
        assert m["losses"] == 0
        assert m["max_loss_streak"] == 0
        assert m["max_win_streak"] == 3
        assert m["profit_factor"] == float("inf")

    def test_mixed_trades(self):
        """Mixed wins and losses computes all metrics."""
        records = [
            _make_record(pnl_pips=20.0, return_r=1.0, exit_reason="tp_hit"),
            _make_record(pnl_pips=-10.0, return_r=-0.5, exit_reason="sl_hit"),
            _make_record(pnl_pips=30.0, return_r=1.5, exit_reason="tp_hit"),
            _make_record(pnl_pips=-15.0, return_r=-0.75, exit_reason="sl_hit"),
        ]
        m = compute_metrics(records)
        assert m["total_trades"] == 4
        assert m["wins"] == 2
        assert m["losses"] == 2
        assert m["win_rate"] == 0.5
        assert m["tp_hits"] == 2
        assert m["sl_hits"] == 2
        assert m["total_pnl_pips"] == pytest.approx(25.0)
        assert m["total_r"] == pytest.approx(1.25)
        assert m["profit_factor"] == pytest.approx(50.0 / 25.0)
        assert m["max_dd_pips"] > 0
        assert m["sharpe"] != 0
        assert m["sqn"] != 0

    def test_drawdown_computation(self):
        """Max drawdown is correctly computed."""
        # Equity: +10, +10-20=-10, -10+30=+20, +20-5=+15
        records = [
            _make_record(pnl_pips=10.0, return_r=1.0),
            _make_record(pnl_pips=-20.0, return_r=-2.0),
            _make_record(pnl_pips=30.0, return_r=3.0),
            _make_record(pnl_pips=-5.0, return_r=-0.5),
        ]
        m = compute_metrics(records)
        # Equity: [10, -10, 20, 15]
        # Running max: [10, 10, 20, 20]
        # Drawdown: [0, 20, 0, 5]
        assert m["max_dd_pips"] == pytest.approx(20.0)

    def test_streaks(self):
        """Win/loss streaks correctly computed."""
        records = [
            _make_record(pnl_pips=10.0, return_r=0.5),
            _make_record(pnl_pips=20.0, return_r=1.0),
            _make_record(pnl_pips=15.0, return_r=0.75),
            _make_record(pnl_pips=-5.0, return_r=-0.25),
            _make_record(pnl_pips=-10.0, return_r=-0.5),
        ]
        m = compute_metrics(records)
        assert m["max_win_streak"] == 3
        assert m["max_loss_streak"] == 2

    def test_direction_breakdown(self):
        """Breakdown by direction gives separate stats."""
        records = [
            _make_record(pnl_pips=10.0, return_r=0.5, direction=1),
            _make_record(pnl_pips=-5.0, return_r=-0.25, direction=1),
            _make_record(pnl_pips=20.0, return_r=1.0, direction=-1),
        ]
        m = compute_metrics(records)
        assert m["long_trades"] == 2
        assert m["long_wins"] == 1
        assert m["long_win_rate"] == 0.5
        assert m["short_trades"] == 1
        assert m["short_wins"] == 1
        assert m["short_win_rate"] == 1.0

    def test_signal_type_breakdown(self):
        """Breakdown by signal_type gives per-type stats."""
        records = [
            _make_record(pnl_pips=10.0, return_r=0.5, signal_type="push"),
            _make_record(pnl_pips=-5.0, return_r=-0.25, signal_type="reversal"),
            _make_record(pnl_pips=20.0, return_r=1.0, signal_type="push"),
        ]
        m = compute_metrics(records)
        assert m["signal_type_push_n"] == 2
        assert m["signal_type_push_wr"] == 1.0
        assert m["signal_type_reversal_n"] == 1
        assert m["signal_type_reversal_wr"] == 0.0

    def test_holding_period(self):
        """Average holding period stats computed."""
        records = [
            _make_record(pnl_pips=10.0, return_r=0.5, hold_hours=3.0),
            _make_record(pnl_pips=-5.0, return_r=-0.25, hold_hours=1.0),
        ]
        m = compute_metrics(records)
        assert m["avg_hold_hours"] == pytest.approx(2.0)
        assert m["avg_win_hold_hours"] == pytest.approx(3.0)
        assert m["avg_loss_hold_hours"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# run_sweep tests
# ---------------------------------------------------------------------------

class TestRunSweep:
    def test_single_config(self):
        """Single config returns DataFrame with 1 row."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "total_trades" in df.columns
        assert "win_rate" in df.columns
        assert "entry_tf" in df.columns
        assert "sqn" in df.columns
        assert "sharpe" in df.columns
        assert "calmar" in df.columns

    def test_multiple_configs(self):
        """Multiple configs return one row per config."""
        timeline = _make_timeline()
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                           sl_mode="atr", tp_mode="fixed_rr"),
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                           sl_mode="zone", tp_mode="fixed_rr"),
        ]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        assert len(df) == 2

    def test_no_configs(self):
        """Empty config list returns empty DataFrame."""
        timeline = _make_timeline()
        df = run_sweep(timeline, [], symbol="GBPUSD")
        assert len(df) == 0

    def test_result_columns(self):
        """Result DataFrame has config + metrics columns."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        # Config columns
        assert "sl_mode" in df.columns
        assert "tp_mode" in df.columns
        assert "entry_tf" in df.columns
        # Comprehensive metric columns
        assert "total_trades" in df.columns
        assert "total_signals" in df.columns
        assert "profit_factor" in df.columns
        assert "expectancy_r" in df.columns
        assert "max_dd_pips" in df.columns


# ---------------------------------------------------------------------------
# run_multi_symbol_sweep tests
# ---------------------------------------------------------------------------

class TestRunMultiSymbolSweep:
    def test_returns_dataframe_with_symbol_column(self):
        """Multi-symbol sweep adds symbol column."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        timelines = {"GBPUSD": timeline, "EURUSD": timeline}
        df = run_multi_symbol_sweep(timelines, configs)
        assert "symbol" in df.columns
        assert set(df["symbol"].unique()) == {"GBPUSD", "EURUSD"}
        assert len(df) == 2
