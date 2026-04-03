"""Unit tests for opportunity counter classification functions."""
from __future__ import annotations

import pandas as pd

from iora.diagnostics.opportunity_counter import classify_touch
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
