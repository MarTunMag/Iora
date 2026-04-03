"""Unit tests for opportunity counter classification functions."""
from __future__ import annotations

import pandas as pd

from iora.diagnostics.opportunity_counter import (
    classify_touch, is_near_miss,
    classify_zone_role, classify_age_bucket, classify_bias_alignment,
    classify_test_count,
)
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


class TestClassifyZoneRole:
    def test_push(self):
        z = _demand()
        z.is_push = True
        assert classify_zone_role(z, prev_swing_cls="") == "push"

    def test_reversal(self):
        z = _demand()
        z.is_reversal = True
        assert classify_zone_role(z, prev_swing_cls="") == "reversal"

    def test_continuation_hh_after_hh(self):
        z = _demand()
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "continuation"

    def test_continuation_ll_after_ll(self):
        z = _supply()
        z.swing_cls = "LL"
        assert classify_zone_role(z, prev_swing_cls="LL") == "continuation"

    def test_pullback_lh_after_hh(self):
        z = _supply()
        z.swing_cls = "LH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "pullback"

    def test_pullback_hl_after_ll(self):
        z = _demand()
        z.swing_cls = "HL"
        assert classify_zone_role(z, prev_swing_cls="LL") == "pullback"

    def test_no_prev_unknown(self):
        z = _demand()
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="") == "unknown"

    def test_push_takes_priority(self):
        z = _demand()
        z.is_push = True
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "push"


class TestClassifyAgeBucket:
    def test_fresh(self):
        assert classify_age_bucket(5) == "fresh"
    def test_young(self):
        assert classify_age_bucket(30) == "young"
    def test_mature(self):
        assert classify_age_bucket(100) == "mature"
    def test_old(self):
        assert classify_age_bucket(250) == "old"
    def test_boundary_fresh_young(self):
        assert classify_age_bucket(10) == "fresh"
        assert classify_age_bucket(11) == "young"
    def test_boundary_young_mature(self):
        assert classify_age_bucket(50) == "young"
        assert classify_age_bucket(51) == "mature"
    def test_boundary_mature_old(self):
        assert classify_age_bucket(200) == "mature"
        assert classify_age_bucket(201) == "old"


class TestClassifyBiasAlignment:
    def test_with_daily_demand_bull(self):
        assert classify_bias_alignment(is_supply=False, d_bias="HH_HL_bull_push") == "with_daily"
    def test_against_daily_demand_bear(self):
        assert classify_bias_alignment(is_supply=False, d_bias="LH_LL_bear_push") == "against_daily"
    def test_with_daily_supply_bear(self):
        assert classify_bias_alignment(is_supply=True, d_bias="LH_LL_bear_push") == "with_daily"
    def test_against_daily_supply_bull(self):
        assert classify_bias_alignment(is_supply=True, d_bias="HH_HL_bull_push") == "against_daily"
    def test_at_transition(self):
        assert classify_bias_alignment(is_supply=False, d_bias="HH_HL_bull_push",
                                       is_transition=True) == "at_transition"
    def test_neutral_on_unknown(self):
        assert classify_bias_alignment(is_supply=False, d_bias="unknown") == "neutral"
    def test_neutral_on_compression(self):
        assert classify_bias_alignment(is_supply=False, d_bias="LH_HL_compression") == "neutral"


class TestClassifyTestCount:
    def test_first_touch(self):
        assert classify_test_count(0) == "first_touch"
    def test_retested_1(self):
        assert classify_test_count(1) == "retested_1"
    def test_retested_2plus(self):
        assert classify_test_count(2) == "retested_2plus"
        assert classify_test_count(5) == "retested_2plus"
