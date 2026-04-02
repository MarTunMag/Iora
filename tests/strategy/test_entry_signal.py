"""Tests for EntrySignal dataclass."""
from __future__ import annotations

import pandas as pd

from iora.strategy.entry_signal import EntrySignal
from iora.engine.push_zone_models import PushZone


def _make_zone(is_supply=True, top=1.30, bottom=1.29):
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"),
        timeframe="M5", is_push=True,
        struct_cls="BOS", swing_cls="HH", count_num=1,
    )


def test_entry_signal_creation():
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="BOS",
        direction="short", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={"M5": -1, "H1": -1, "H4": 1},
        period_levels={"H1": {"highs": [1.31], "lows": [1.28]}},
        zone_counts={"M5": (3, 2)}, exhaustion={"M5_sup": False},
        sl_price=1.3010, tp_price=1.2850,
        risk_pips=10.0, reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02 10:00"), entry_price=1.2950,
    )
    assert sig.direction == "short"
    assert sig.zone is zone
    assert sig.nesting_depth == 0
    assert sig.risk_pips == 10.0


def test_entry_signal_rr_ratio():
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="BOS",
        direction="short", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.3010, tp_price=1.2850,
        risk_pips=10.0, reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.2950,
    )
    assert sig.rr_ratio == 5.0


def test_entry_signal_rr_zero_risk():
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="",
        direction="long", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.29, tp_price=1.31,
        risk_pips=0.0, reward_pips=20.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.29,
    )
    assert sig.rr_ratio == 0.0


def test_entry_signal_to_dict():
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="BOS",
        direction="short", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={"M5": -1}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.3010, tp_price=1.2850,
        risk_pips=10.0, reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.2950,
    )
    d = sig.to_dict()
    assert d["zone_tf"] == "M5"
    assert d["signal_type"] == "push"
    assert d["direction"] == "short"
    assert d["entry_price"] == 1.2950
    assert d["rr_ratio"] == 5.0
    assert d["zone_top"] == 1.30
    assert d["zone_bottom"] == 1.29
