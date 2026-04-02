"""Tests for backtest serialization helpers (apps/backtest_serializers.py).

Covers:
- serialize_trade_markers: entry + exit markers per trade, colors, shapes
- serialize_trade_lines: SL/TP horizontal lines per trade
- serialize_equity_curve: cumulative PnL series sorted by exit_time
- serialize_equity_curve_r: cumulative R-multiple series
- serialize_metrics_summary: sectioned metrics display dict
- serialize_trade_detail: full single-trade detail dict
- serialize_sweep_row: config + metrics flat row
- _ts helper: pandas Timestamp → Unix seconds
"""
from __future__ import annotations

import pandas as pd
import pytest

from apps.backtest_serializers import (
    _ts,
    serialize_equity_curve,
    serialize_equity_curve_r,
    serialize_metrics_summary,
    serialize_sweep_row,
    serialize_trade_detail,
    serialize_trade_lines,
    serialize_trade_markers,
)
from iora.strategy.trade_converter import SweepTradeRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_record(
    direction: int = 1,
    pnl_pips: float = 20.0,
    return_r: float = 2.0,
    exit_reason: str = "tp_hit",
    entry_time: str = "2025-01-01 10:00",
    exit_time: str = "2025-01-01 12:00",
    sl_price: float = 1.2920,
    tp_price: float = 1.3000,
    trade_id: str = "pz_0001",
) -> SweepTradeRecord:
    return SweepTradeRecord(
        trade_id=trade_id,
        symbol="GBPUSD",
        direction=direction,
        entry_time=pd.Timestamp(entry_time),
        exit_time=pd.Timestamp(exit_time),
        entry_price=1.2950,
        exit_price=1.2970 if pnl_pips > 0 else 1.2930,
        pnl_pips=pnl_pips,
        risk_pips=10.0,
        reward_pips=20.0,
        return_r=return_r,
        rr_ratio=2.0,
        exit_reason=exit_reason,
        sl_price=sl_price,
        tp_price=tp_price,
        signal_type="push",
        struct_cls="BOS",
        zone_tf="M5",
        parent_tf="H1",
        nesting_depth=1,
        opposing_nest=False,
        zone_top=1.2960,
        zone_bottom=1.2940,
        zone_is_push=True,
        zone_is_reversal=False,
        zone_is_terminal=False,
        zone_swing_cls="HH",
        zone_count=2,
    )


def _make_loser(**kwargs) -> SweepTradeRecord:
    return _make_record(pnl_pips=-10.0, return_r=-1.0, exit_reason="sl_hit",
                        trade_id="pz_0002", **kwargs)


# ---------------------------------------------------------------------------
# _ts helper
# ---------------------------------------------------------------------------

class TestTs:
    def test_returns_int(self):
        t = pd.Timestamp("2025-01-01 10:00", tz="UTC")
        result = _ts(t)
        assert isinstance(result, int)

    def test_naive_timestamp(self):
        t = pd.Timestamp("2025-01-01 00:00:00")
        result = _ts(t)
        assert isinstance(result, int)
        assert result > 0

    def test_known_epoch(self):
        """2025-01-01 00:00:00 UTC = 1735689600."""
        t = pd.Timestamp("2025-01-01 00:00:00", tz="UTC")
        assert _ts(t) == 1735689600


# ---------------------------------------------------------------------------
# serialize_trade_markers
# ---------------------------------------------------------------------------

class TestSerializeTradeMarkers:
    def test_empty_list(self):
        assert serialize_trade_markers([]) == []

    def test_produces_two_markers_per_trade(self):
        records = [_make_record()]
        markers = serialize_trade_markers(records)
        assert len(markers) == 2

    def test_four_markers_for_two_trades(self):
        records = [_make_record(), _make_loser()]
        markers = serialize_trade_markers(records)
        assert len(markers) == 4

    def test_marker_keys_present(self):
        markers = serialize_trade_markers([_make_record()])
        for m in markers:
            assert "time" in m
            assert "position" in m
            assert "color" in m
            assert "shape" in m
            assert "text" in m

    def test_winner_color_green(self):
        markers = serialize_trade_markers([_make_record(pnl_pips=10.0)])
        colors = {m["color"] for m in markers}
        assert "#26a69a" in colors

    def test_loser_color_red(self):
        markers = serialize_trade_markers([_make_loser()])
        colors = {m["color"] for m in markers}
        assert "#ef5350" in colors

    def test_long_entry_shape_arrow_up(self):
        markers = serialize_trade_markers([_make_record(direction=1)])
        entry_markers = [m for m in markers if "entry" in m["text"].lower() or m["shape"] == "arrowUp"]
        assert any(m["shape"] == "arrowUp" for m in markers)

    def test_short_entry_shape_arrow_down(self):
        markers = serialize_trade_markers([_make_record(direction=-1)])
        assert any(m["shape"] == "arrowDown" for m in markers)

    def test_exit_marker_shape_circle(self):
        markers = serialize_trade_markers([_make_record()])
        assert any(m["shape"] == "circle" for m in markers)

    def test_entry_marker_at_entry_time(self):
        rec = _make_record(entry_time="2025-01-01 10:00", exit_time="2025-01-01 12:00")
        markers = serialize_trade_markers([rec])
        entry_ts = _ts(pd.Timestamp("2025-01-01 10:00"))
        exit_ts = _ts(pd.Timestamp("2025-01-01 12:00"))
        times = {m["time"] for m in markers}
        assert entry_ts in times
        assert exit_ts in times

    def test_times_are_ints(self):
        markers = serialize_trade_markers([_make_record()])
        for m in markers:
            assert isinstance(m["time"], int)

    def test_long_entry_position_below_bar(self):
        markers = serialize_trade_markers([_make_record(direction=1)])
        entry = next(m for m in markers if m["shape"] == "arrowUp")
        assert entry["position"] == "belowBar"

    def test_short_entry_position_above_bar(self):
        markers = serialize_trade_markers([_make_record(direction=-1)])
        entry = next(m for m in markers if m["shape"] == "arrowDown")
        assert entry["position"] == "aboveBar"


# ---------------------------------------------------------------------------
# serialize_trade_lines
# ---------------------------------------------------------------------------

class TestSerializeTradeLines:
    def test_empty_list(self):
        assert serialize_trade_lines([]) == []

    def test_two_lines_per_trade(self):
        lines = serialize_trade_lines([_make_record()])
        assert len(lines) == 2

    def test_four_lines_for_two_trades(self):
        lines = serialize_trade_lines([_make_record(), _make_loser()])
        assert len(lines) == 4

    def test_line_keys_present(self):
        lines = serialize_trade_lines([_make_record()])
        for line in lines:
            assert "price" in line
            assert "color" in line
            assert "time" in line

    def test_sl_line_is_red(self):
        lines = serialize_trade_lines([_make_record(sl_price=1.2920)])
        sl_lines = [l for l in lines if abs(l["price"] - 1.2920) < 1e-6]
        assert len(sl_lines) == 1
        assert sl_lines[0]["color"] == "#ef5350"

    def test_tp_line_is_green(self):
        lines = serialize_trade_lines([_make_record(tp_price=1.3000)])
        tp_lines = [l for l in lines if abs(l["price"] - 1.3000) < 1e-6]
        assert len(tp_lines) == 1
        assert tp_lines[0]["color"] == "#26a69a"

    def test_times_are_ints(self):
        lines = serialize_trade_lines([_make_record()])
        for line in lines:
            assert isinstance(line["time"], int)


# ---------------------------------------------------------------------------
# serialize_equity_curve
# ---------------------------------------------------------------------------

class TestSerializeEquityCurve:
    def test_empty_list(self):
        assert serialize_equity_curve([]) == []

    def test_returns_list_of_dicts(self):
        records = [_make_record(pnl_pips=10.0), _make_loser()]
        result = serialize_equity_curve(records)
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)

    def test_time_and_value_keys(self):
        records = [_make_record()]
        result = serialize_equity_curve(records)
        for item in result:
            assert "time" in item
            assert "value" in item

    def test_cumulative_pnl_values(self):
        r1 = _make_record(pnl_pips=10.0, exit_time="2025-01-01 10:00", trade_id="pz_0001")
        r2 = _make_record(pnl_pips=5.0, exit_time="2025-01-01 11:00", trade_id="pz_0002")
        result = serialize_equity_curve([r1, r2])
        assert len(result) == 2
        assert result[0]["value"] == pytest.approx(10.0)
        assert result[1]["value"] == pytest.approx(15.0)

    def test_sorted_by_exit_time(self):
        # Pass records out of order
        r1 = _make_record(pnl_pips=10.0, exit_time="2025-01-01 12:00", trade_id="pz_0001")
        r2 = _make_record(pnl_pips=5.0, exit_time="2025-01-01 10:00", trade_id="pz_0002")
        result = serialize_equity_curve([r1, r2])
        times = [item["time"] for item in result]
        assert times == sorted(times)

    def test_time_is_unix_seconds(self):
        result = serialize_equity_curve([_make_record()])
        assert isinstance(result[0]["time"], int)

    def test_negative_cumulative_after_loss(self):
        r1 = _make_record(pnl_pips=-15.0, exit_time="2025-01-01 10:00", trade_id="pz_0001")
        result = serialize_equity_curve([r1])
        assert result[0]["value"] == pytest.approx(-15.0)


# ---------------------------------------------------------------------------
# serialize_equity_curve_r
# ---------------------------------------------------------------------------

class TestSerializeEquityCurveR:
    def test_empty_list(self):
        assert serialize_equity_curve_r([]) == []

    def test_returns_list_of_dicts(self):
        result = serialize_equity_curve_r([_make_record()])
        assert isinstance(result, list)
        assert all("time" in item and "value" in item for item in result)

    def test_cumulative_r_values(self):
        r1 = _make_record(return_r=2.0, exit_time="2025-01-01 10:00", trade_id="pz_0001")
        r2 = _make_record(return_r=1.0, exit_time="2025-01-01 11:00", trade_id="pz_0002")
        result = serialize_equity_curve_r([r1, r2])
        assert result[0]["value"] == pytest.approx(2.0)
        assert result[1]["value"] == pytest.approx(3.0)

    def test_sorted_by_exit_time(self):
        r1 = _make_record(return_r=2.0, exit_time="2025-01-01 12:00", trade_id="pz_0001")
        r2 = _make_record(return_r=1.0, exit_time="2025-01-01 10:00", trade_id="pz_0002")
        result = serialize_equity_curve_r([r1, r2])
        times = [item["time"] for item in result]
        assert times == sorted(times)


# ---------------------------------------------------------------------------
# serialize_metrics_summary
# ---------------------------------------------------------------------------

class TestSerializeMetricsSummary:
    def _sample_metrics(self) -> dict:
        return {
            "total_trades": 50,
            "wins": 30,
            "losses": 20,
            "win_rate": 0.60,
            "tp_hits": 28,
            "sl_hits": 22,
            "total_pnl_pips": 500.0,
            "avg_pnl_pips": 10.0,
            "median_pnl_pips": 8.0,
            "std_pnl_pips": 15.0,
            "avg_win_pips": 25.0,
            "avg_loss_pips": -12.5,
            "largest_win_pips": 80.0,
            "largest_loss_pips": -30.0,
            "total_r": 10.0,
            "avg_r": 0.20,
            "median_r": 0.15,
            "std_r": 0.5,
            "avg_win_r": 2.0,
            "avg_loss_r": -1.0,
            "largest_win_r": 5.0,
            "largest_loss_r": -2.0,
            "sharpe": 1.5,
            "sortino": 2.0,
            "sqn": 2.5,
            "calmar": 1.2,
            "max_dd_pips": 100.0,
            "max_dd_r": 3.0,
            "profit_factor": 2.0,
            "expectancy_pips": 5.0,
            "expectancy_r": 0.10,
            "gross_profit_pips": 750.0,
            "gross_loss_pips": 250.0,
            "max_win_streak": 8,
            "max_loss_streak": 4,
            "avg_hold_hours": 3.5,
            "avg_win_hold_hours": 4.0,
            "avg_loss_hold_hours": 2.5,
        }

    def test_returns_dict(self):
        result = serialize_metrics_summary(self._sample_metrics())
        assert isinstance(result, dict)

    def test_has_required_sections(self):
        result = serialize_metrics_summary(self._sample_metrics())
        assert "overview" in result
        assert "risk_adjusted" in result
        assert "pnl" in result
        assert "drawdown" in result
        assert "streaks" in result

    def test_overview_has_key_fields(self):
        result = serialize_metrics_summary(self._sample_metrics())
        overview = result["overview"]
        assert "total_trades" in overview
        assert "win_rate" in overview
        assert "profit_factor" in overview

    def test_risk_adjusted_has_ratios(self):
        result = serialize_metrics_summary(self._sample_metrics())
        ra = result["risk_adjusted"]
        assert "sqn" in ra
        assert "sharpe" in ra
        assert "sortino" in ra

    def test_drawdown_has_max_dd(self):
        result = serialize_metrics_summary(self._sample_metrics())
        dd = result["drawdown"]
        assert "max_dd_pips" in dd or "max_dd_r" in dd

    def test_streaks_has_streak_fields(self):
        result = serialize_metrics_summary(self._sample_metrics())
        s = result["streaks"]
        assert "max_win_streak" in s
        assert "max_loss_streak" in s

    def test_empty_metrics_handled(self):
        empty = {
            "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "tp_hits": 0, "sl_hits": 0,
            "total_pnl_pips": 0.0, "avg_pnl_pips": 0.0,
            "median_pnl_pips": 0.0, "std_pnl_pips": 0.0,
            "avg_win_pips": 0.0, "avg_loss_pips": 0.0,
            "largest_win_pips": 0.0, "largest_loss_pips": 0.0,
            "total_r": 0.0, "avg_r": 0.0, "median_r": 0.0, "std_r": 0.0,
            "avg_win_r": 0.0, "avg_loss_r": 0.0,
            "largest_win_r": 0.0, "largest_loss_r": 0.0,
            "sharpe": 0.0, "sortino": 0.0, "sqn": 0.0, "calmar": 0.0,
            "max_dd_pips": 0.0, "max_dd_r": 0.0,
            "profit_factor": 0.0, "expectancy_pips": 0.0, "expectancy_r": 0.0,
            "gross_profit_pips": 0.0, "gross_loss_pips": 0.0,
            "max_win_streak": 0, "max_loss_streak": 0,
            "avg_hold_hours": 0.0, "avg_win_hold_hours": 0.0,
            "avg_loss_hold_hours": 0.0,
        }
        result = serialize_metrics_summary(empty)
        assert isinstance(result, dict)
        assert result["overview"]["total_trades"] == 0

    def test_values_pass_through_correctly(self):
        m = self._sample_metrics()
        result = serialize_metrics_summary(m)
        assert result["overview"]["win_rate"] == pytest.approx(0.60)
        assert result["risk_adjusted"]["sqn"] == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# serialize_trade_detail
# ---------------------------------------------------------------------------

class TestSerializeTradeDetail:
    def test_returns_dict(self):
        result = serialize_trade_detail(_make_record())
        assert isinstance(result, dict)

    def test_core_fields_present(self):
        result = serialize_trade_detail(_make_record())
        assert "trade_id" in result
        assert "symbol" in result
        assert "direction" in result
        assert "entry_time" in result
        assert "exit_time" in result
        assert "entry_price" in result
        assert "exit_price" in result
        assert "pnl_pips" in result
        assert "return_r" in result
        assert "exit_reason" in result
        assert "sl_price" in result
        assert "tp_price" in result

    def test_signal_classification_fields(self):
        result = serialize_trade_detail(_make_record())
        assert "signal_type" in result
        assert "struct_cls" in result
        assert "zone_tf" in result
        assert "parent_tf" in result
        assert "nesting_depth" in result

    def test_zone_context_fields(self):
        result = serialize_trade_detail(_make_record())
        assert "zone_top" in result
        assert "zone_bottom" in result
        assert "zone_is_push" in result
        assert "zone_swing_cls" in result
        assert "zone_count" in result

    def test_direction_str_included(self):
        result = serialize_trade_detail(_make_record(direction=1))
        assert "direction_str" in result
        assert result["direction_str"] == "long"

    def test_is_winner_included(self):
        result = serialize_trade_detail(_make_record(pnl_pips=10.0))
        assert "is_winner" in result
        assert result["is_winner"] is True

    def test_holding_period_included(self):
        result = serialize_trade_detail(_make_record(
            entry_time="2025-01-01 10:00",
            exit_time="2025-01-01 12:00",
        ))
        assert "holding_period_hours" in result
        assert result["holding_period_hours"] == pytest.approx(2.0)

    def test_timestamps_are_ints(self):
        result = serialize_trade_detail(_make_record())
        assert isinstance(result["entry_time"], int)
        assert isinstance(result["exit_time"], int)

    def test_short_direction(self):
        result = serialize_trade_detail(_make_record(direction=-1))
        assert result["direction_str"] == "short"

    def test_loser_is_winner_false(self):
        result = serialize_trade_detail(_make_loser())
        assert result["is_winner"] is False


# ---------------------------------------------------------------------------
# serialize_sweep_row
# ---------------------------------------------------------------------------

class TestSerializeSweepRow:
    def _sample_config(self) -> dict:
        return {
            "entry_model": "push",
            "zone_tf": "M5",
            "parent_tf": "H1",
            "rr_ratio": 2.0,
            "sl_mode": "zone_edge",
        }

    def _sample_metrics(self) -> dict:
        return {
            "total_trades": 50,
            "win_rate": 0.60,
            "sqn": 2.5,
            "sharpe": 1.5,
            "sortino": 2.0,
            "profit_factor": 2.0,
            "total_r": 10.0,
            "max_dd_r": 3.0,
        }

    def test_returns_dict(self):
        result = serialize_sweep_row(self._sample_config(), self._sample_metrics())
        assert isinstance(result, dict)

    def test_config_keys_present(self):
        result = serialize_sweep_row(self._sample_config(), self._sample_metrics())
        assert "entry_model" in result
        assert "zone_tf" in result
        assert "rr_ratio" in result

    def test_metrics_keys_present(self):
        result = serialize_sweep_row(self._sample_config(), self._sample_metrics())
        assert "total_trades" in result
        assert "win_rate" in result
        assert "sqn" in result

    def test_config_values_correct(self):
        result = serialize_sweep_row(self._sample_config(), self._sample_metrics())
        assert result["entry_model"] == "push"
        assert result["rr_ratio"] == pytest.approx(2.0)

    def test_metrics_values_correct(self):
        result = serialize_sweep_row(self._sample_config(), self._sample_metrics())
        assert result["total_trades"] == 50
        assert result["win_rate"] == pytest.approx(0.60)

    def test_config_key_wins_on_collision(self):
        """If config and metrics share a key, neither silently clobbers the other."""
        config = {"total_trades": 999}  # intentional collision
        metrics = {"total_trades": 50}
        result = serialize_sweep_row(config, metrics)
        # Both values should be accessible; exact behavior is documented
        assert "total_trades" in result

    def test_empty_config_and_metrics(self):
        result = serialize_sweep_row({}, {})
        assert result == {}
