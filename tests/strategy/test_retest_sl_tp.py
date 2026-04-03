# tests/strategy/test_retest_sl_tp.py
"""Tests for retest-specific SL/TP computation."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sl_tp import compute_retest_sl, compute_retest_tp


def _candidate(side="demand", zone_top=1.2550, zone_bottom=1.2500,
               entry_price=1.2560, atr=0.0080,
               period_hi=1.2600, period_lo=1.2450) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=pd.Timestamp("2025-01-15 10:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type="wick_touch", zone_side=side,
        zone_role="continuation", age_bucket="fresh",
        bias_alignment="with_daily", test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=zone_top, zone_bottom=zone_bottom,
        entry_price=entry_price, atr=atr,
        period_hi=period_hi, period_lo=period_lo,
    )


class TestZoneSL:
    def test_long_sl_below_zone(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="zone")
        assert sl < c.zone_bottom
        assert sl > 0

    def test_short_sl_above_zone(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="zone")
        assert sl > c.zone_top


class TestAtrSL:
    def test_long_atr_sl(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="atr", atr_mult=1.5)
        expected = c.entry_price - 1.5 * c.atr
        assert abs(sl - expected) < 1e-8

    def test_short_atr_sl(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="atr", atr_mult=1.5)
        expected = c.entry_price + 1.5 * c.atr
        assert abs(sl - expected) < 1e-8


class TestPeriodSL:
    def test_long_period_sl(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="period")
        assert sl < c.period_lo

    def test_short_period_sl(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="period")
        assert sl > c.period_hi


class TestTP:
    def test_fixed_rr_long(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="zone")
        risk = c.entry_price - sl
        tp = compute_retest_tp(c, sl, mode="fixed_rr", fixed_rr=2.0)
        expected = c.entry_price + 2.0 * risk
        assert abs(tp - expected) < 1e-8

    def test_fixed_rr_short(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="zone")
        risk = sl - c.entry_price
        tp = compute_retest_tp(c, sl, mode="fixed_rr", fixed_rr=2.0)
        expected = c.entry_price - 2.0 * risk
        assert abs(tp - expected) < 1e-8
