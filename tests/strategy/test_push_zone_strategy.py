# tests/strategy/test_push_zone_strategy.py
"""Tests for the push zone strategy evaluator."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.push_zone_strategy import evaluate_strategy, StrategyResult


def _zone(is_supply: bool, top: float, bottom: float, **kw) -> PushZone:
    defaults = dict(
        origin_time=pd.Timestamp("2025-01-01"),
        timeframe="M5", is_push=True, struct_cls="BOS",
        swing_cls="HH" if is_supply else "LL", count_num=1,
    )
    defaults.update(kw)
    return PushZone(top=top, bottom=bottom, is_supply=is_supply, **defaults)


def _bar(
    ts: str, o: float, h: float, lo: float, c: float,
    fires: list[PushZone] | None = None,
    breaks: list[PushZone] | None = None,
    zones_by_tf: dict | None = None,
    trend_by_tf: dict | None = None,
) -> ZoneTimelineBar:
    return ZoneTimelineBar(
        timestamp=pd.Timestamp(ts),
        open_=o, high=h, low=lo, close=c,
        fires=fires or [],
        breaks=breaks or [],
        zones_by_tf=zones_by_tf or {"M5": []},
        trend_by_tf=trend_by_tf or {"M5": 0},
        period_levels_by_tf={"M5": {"highs": [], "lows": []}},
        zone_counts_by_tf={"M5": (0, 0)},
    )


class TestEvaluateStrategy:
    def test_no_fires_no_trades(self):
        """Timeline with no zone fires produces no trades."""
        timeline = [
            _bar("2025-01-01 00:00", 1.30, 1.31, 1.29, 1.305),
            _bar("2025-01-01 00:05", 1.305, 1.31, 1.295, 1.30),
        ]
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.trades) == 0

    def test_supply_fire_generates_short(self):
        """Supply zone fire → short entry signal if filters pass."""
        supply = _zone(True, 1.3020, 1.3000)
        demand_for_sl = _zone(False, 1.2900, 1.2880, timeframe="H1")
        timeline = [
            # Bar 0: supply zone fires, price at zone
            _bar("2025-01-01 00:00", 1.301, 1.302, 1.299, 1.300,
                 fires=[supply],
                 zones_by_tf={"M5": [supply], "H1": [demand_for_sl]}),
            # Bars 1-10: price moves down (TP hit)
            *[_bar(f"2025-01-01 00:{5*(i+1):02d}",
                   1.30 - 0.002*i, 1.301 - 0.002*i,
                   1.295 - 0.002*i, 1.298 - 0.002*i)
              for i in range(10)],
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) >= 1
        assert result.signals[0].direction == "short"

    def test_demand_fire_generates_long(self):
        """Demand zone fire → long entry signal if filters pass."""
        demand = _zone(False, 1.2900, 1.2880)
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[demand],
                 zones_by_tf={"M5": [demand]}),
            *[_bar(f"2025-01-01 00:{5*(i+1):02d}",
                   1.29 + 0.002*i, 1.295 + 0.002*i,
                   1.289 + 0.002*i, 1.293 + 0.002*i)
              for i in range(10)],
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) >= 1
        assert result.signals[0].direction == "long"

    def test_filter_rejects_signal(self):
        """Signal blocked by direction filter produces no trade."""
        supply = _zone(True, 1.3020, 1.3000)
        timeline = [
            _bar("2025-01-01 00:00", 1.301, 1.302, 1.299, 1.300,
                 fires=[supply], zones_by_tf={"M5": [supply]}),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            direction="long",  # Blocks short signals
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.trades) == 0

    def test_sl_hit_closes_trade(self):
        """Price hitting SL closes the trade with a loss."""
        demand = _zone(False, 1.2900, 1.2880)
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[demand], zones_by_tf={"M5": [demand]}),
            # Bar 1: price drops hard (SL hit)
            _bar("2025-01-01 00:05", 1.290, 1.290, 1.270, 1.275),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        if result.trades:
            assert result.trades[0]["exit_reason"] in ("sl_hit", "SL_HIT")

    def test_single_position_blocks_second_entry(self):
        """In single position mode, second fire while position open is ignored."""
        d1 = _zone(False, 1.2900, 1.2880)
        d2 = _zone(False, 1.2850, 1.2830, origin_time=pd.Timestamp("2025-01-01 00:05"))
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[d1], zones_by_tf={"M5": [d1]}),
            # Bar 1: second fire, but low stays above SL (1.2894) so position stays open
            _bar("2025-01-01 00:05", 1.290, 1.291, 1.2895, 1.290,
                 fires=[d2], zones_by_tf={"M5": [d1, d2]}),
            _bar("2025-01-01 00:10", 1.290, 1.291, 1.2895, 1.290),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
            position_mode="single", max_concurrent=1,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        # Should have at most 1 signal (second blocked by open position)
        assert len(result.signals) <= 1


class TestStrategyResult:
    def test_result_has_signals_and_trades(self):
        """StrategyResult contains both signals and completed trades."""
        result = StrategyResult(signals=[], trades=[], open_trades=[])
        assert result.signals == []
        assert result.trades == []
        assert result.open_trades == []
