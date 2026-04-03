"""Unit tests for opportunity counter classification functions."""
from __future__ import annotations

import pandas as pd

from iora.diagnostics.opportunity_counter import classify_touch, is_near_miss
from iora.engine.push_zone_models import PushZone


def _demand(top=1.3000, bottom=1.2980):
    return PushZone(top=top, bottom=bottom, is_supply=False,
                    origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")


def _supply(top=1.3100, bottom=1.3080):
    return PushZone(top=top, bottom=bottom, is_supply=True,
                    origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")


class TestClassifyTouch:
    def test_wick_touch_demand(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.2990, close=1.3020)
        assert result == "wick_touch"

    def test_body_close_demand(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.2970, close=1.2990)
        assert result == "body_close"

    def test_break_through_demand(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3010, low=1.2960, close=1.2970)
        assert result == "break_through"

    def test_wick_touch_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3090, low=1.3050, close=1.3060)
        assert result == "wick_touch"

    def test_body_close_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3110, low=1.3070, close=1.3090)
        assert result == "body_close"

    def test_break_through_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3120, low=1.3070, close=1.3110)
        assert result == "break_through"

    def test_no_touch(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.3010, close=1.3030)
        assert result is None

    def test_no_touch_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3070, low=1.3050, close=1.3060)
        assert result is None


class TestIsNearMiss:
    def test_near_miss_demand(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = is_near_miss(z, high=1.3050, low=1.3003, atr=0.002, pip_size=0.0001)
        assert result is True

    def test_not_near_miss_too_far(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = is_near_miss(z, high=1.3050, low=1.3020, atr=0.002, pip_size=0.0001)
        assert result is False

    def test_near_miss_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = is_near_miss(z, high=1.3077, low=1.3050, atr=0.002, pip_size=0.0001)
        assert result is True

    def test_touched_not_near_miss(self):
        z = _demand(top=1.3000, bottom=1.2980)
        result = is_near_miss(z, high=1.3050, low=1.2990, atr=0.002, pip_size=0.0001)
        assert result is False

    def test_pip_floor_prevents_sub_pip(self):
        z = _demand(top=1.3000, bottom=1.2998)
        result = is_near_miss(z, high=1.3050, low=1.30005, atr=0.0005, pip_size=0.0001)
        assert result is True

    def test_jpy_pip_size(self):
        z = PushZone(top=150.00, bottom=149.80, is_supply=False,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")
        result = is_near_miss(z, high=150.50, low=150.03, atr=0.50, pip_size=0.01)
        assert result is True
