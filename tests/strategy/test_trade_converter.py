"""Tests for trade dict -> SweepTradeRecord converter."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.strategy.trade_converter import convert_trades, SweepTradeRecord


def _make_trade(
    direction="long", pnl_pips=10.0, exit_reason="tp_hit",
    entry_price=1.2950, exit_price=1.2960,
) -> dict:
    return {
        "entry_time": pd.Timestamp("2025-01-01 10:00"),
        "exit_time": pd.Timestamp("2025-01-01 12:00"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "direction": direction,
        "sl_price": 1.2920,
        "tp_price": 1.3000,
        "exit_reason": exit_reason,
        "pnl_pips": pnl_pips,
        "signal_type": "push",
        "struct_cls": "BOS",
        "zone_tf": "M5",
        "parent_tf": "H1",
        "nesting_depth": 1,
        "rr_ratio": 2.0,
    }


def test_convert_single_trade():
    """Single trade dict converts to SweepTradeRecord."""
    trades = [_make_trade()]
    records = convert_trades(trades, symbol="GBPUSD")
    assert len(records) == 1
    r = records[0]
    assert r.symbol == "GBPUSD"
    assert r.direction == 1  # long -> 1
    assert r.entry_price == 1.2950
    assert r.exit_price == 1.2960
    assert r.exit_reason == "tp_hit"
    assert r.pnl_pips == 10.0


def test_convert_short_trade():
    """Short trade direction maps to -1."""
    trades = [_make_trade(direction="short", pnl_pips=-15.0,
                          exit_reason="sl_hit", exit_price=1.2980)]
    records = convert_trades(trades, symbol="GBPUSD")
    assert records[0].direction == -1
    assert records[0].pnl_pips < 0


def test_convert_empty():
    """Empty list returns empty list."""
    records = convert_trades([], symbol="GBPUSD")
    assert records == []


def test_convert_multiple():
    """Multiple trades get sequential trade_ids."""
    trades = [_make_trade(), _make_trade(pnl_pips=-5.0, exit_reason="sl_hit")]
    records = convert_trades(trades, symbol="GBPUSD")
    assert len(records) == 2
    assert records[0].trade_id != records[1].trade_id


def test_return_r_computed():
    """return_r is pnl_pips / risk_pips (entry-SL distance)."""
    t = _make_trade(pnl_pips=20.0)
    records = convert_trades([t], symbol="GBPUSD")
    # risk = |1.2950 - 1.2920| / 0.0001 = 30 pips
    # return_r = 20 / 30 ~ 0.667
    assert records[0].return_r == pytest.approx(20.0 / 30.0, abs=0.01)


def test_is_winner_property():
    """SweepTradeRecord has is_winner/is_loser properties."""
    t_win = _make_trade(pnl_pips=10.0)
    t_loss = _make_trade(pnl_pips=-5.0, exit_reason="sl_hit")
    records = convert_trades([t_win, t_loss], symbol="GBPUSD")
    assert records[0].is_winner is True
    assert records[1].is_winner is False
