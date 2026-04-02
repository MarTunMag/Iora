# tests/strategy/test_sl_tp.py
"""Tests for SL/TP computation across 4 modes each."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone
from iora.strategy.sl_tp import compute_sl, compute_tp


def _zone(is_supply: bool, top: float, bottom: float) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="H1",
    )


# --- SL Tests ---

class TestComputeSL:
    def test_zone_sl_long(self):
        """Long SL below nearest demand zone bottom with buffer."""
        demand = _zone(False, 1.2940, 1.2930)
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="zone",
            zones=[demand], atr=0.0050, period_levels=None,
        )
        # SL = demand bottom - buffer (atr * 0.15 = 0.00075)
        # demand.bottom=1.2930, buffer=0.00075 → SL=1.29225
        # distance = 1.2950 - 1.29225 = 0.00275, max_dist = 0.005*3=0.015 → within cap
        assert sl == pytest.approx(1.29225, abs=1e-4)

    def test_zone_sl_short(self):
        """Short SL above nearest supply zone top with buffer."""
        supply = _zone(True, 1.2960, 1.2950)
        sl = compute_sl(
            direction="short", entry_price=1.2940, mode="zone",
            zones=[supply], atr=0.0050, period_levels=None,
        )
        # SL = supply top + buffer = 1.2960 + 0.00075 = 1.29675
        assert sl == pytest.approx(1.29675, abs=1e-4)

    def test_zone_sl_no_zone_falls_back_to_atr(self):
        """When no suitable zone found, fall back to ATR-based SL."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="zone",
            zones=[], atr=0.0020, period_levels=None,
        )
        # Fallback: entry - 1.5 * ATR
        assert sl == pytest.approx(1.2920, abs=1e-4)

    def test_structure_sl_long(self):
        """Long SL below period low at given depth."""
        levels = {"lows": [1.2850, 1.2800, 1.2750]}
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="structure",
            zones=[], atr=0.0020, period_levels=levels, period_depth=1,
        )
        # SL = period low[0] - buffer
        assert sl < 1.2850

    def test_structure_sl_depth_2(self):
        """Deeper period depth uses second level."""
        levels = {"lows": [1.2850, 1.2800, 1.2750]}
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="structure",
            zones=[], atr=0.0020, period_levels=levels, period_depth=2,
        )
        assert sl < 1.2800

    def test_atr_sl_long(self):
        """ATR SL: entry - atr * multiplier."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="atr",
            zones=[], atr=0.0020, period_levels=None, atr_mult=1.5,
        )
        assert sl == pytest.approx(1.2920, abs=1e-4)

    def test_atr_sl_short(self):
        """ATR SL: entry + atr * multiplier."""
        sl = compute_sl(
            direction="short", entry_price=1.2950, mode="atr",
            zones=[], atr=0.0020, period_levels=None, atr_mult=1.5,
        )
        assert sl == pytest.approx(1.2980, abs=1e-4)

    def test_fixed_pips_sl(self):
        """Fixed pips SL."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="fixed_pips",
            zones=[], atr=0.0020, period_levels=None,
            fixed_pips=15.0, pip_size=0.0001,
        )
        assert sl == pytest.approx(1.2935, abs=1e-4)


# --- TP Tests ---

class TestComputeTP:
    def test_zone_tp_long(self):
        """Long TP at nearest supply zone with buffer."""
        supply = _zone(True, 1.3050, 1.3030)
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="zone", zones=[supply], atr=0.0020, period_levels=None,
        )
        # TP near supply bottom - buffer
        assert tp > 1.2950  # above entry
        assert tp < 1.3050  # below zone top

    def test_zone_tp_short(self):
        """Short TP at nearest demand zone with buffer."""
        demand = _zone(False, 1.2880, 1.2860)
        tp = compute_tp(
            direction="short", entry_price=1.2950, sl_price=1.2980,
            mode="zone", zones=[demand], atr=0.0020, period_levels=None,
        )
        assert tp < 1.2950  # below entry
        assert tp > 1.2860  # above zone bottom

    def test_fixed_rr_tp(self):
        """Fixed R:R TP: entry + (risk * rr_mult)."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="fixed_rr", zones=[], atr=0.0020, period_levels=None,
            fixed_rr=3.0,
        )
        risk = 1.2950 - 1.2920  # 0.003
        expected = 1.2950 + risk * 3.0  # 1.304
        assert tp == pytest.approx(expected, abs=1e-4)

    def test_atr_tp_long(self):
        """ATR TP: entry + atr * multiplier."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="atr", zones=[], atr=0.0020, period_levels=None,
            atr_mult=3.0,
        )
        assert tp == pytest.approx(1.3010, abs=1e-4)

    def test_zone_tp_no_zone_falls_back(self):
        """No opposing zone → fall back to fixed_rr TP."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="zone", zones=[], atr=0.0020, period_levels=None,
        )
        # Falls back to default R:R of 2.0
        risk = 1.2950 - 1.2920
        expected = 1.2950 + risk * 2.0
        assert tp == pytest.approx(expected, abs=1e-4)
