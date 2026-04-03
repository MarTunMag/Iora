"""Tests for RetestCandidate and build_retest_candidates."""
import pandas as pd
import pytest

from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate, build_retest_candidates


def _make_event(**overrides) -> OpportunityEvent:
    defaults = dict(
        timestamp=pd.Timestamp("2025-01-15 10:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type="wick_touch", zone_side="demand",
        zone_role="continuation", age_bucket="fresh",
        bias_alignment="with_daily", test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    defaults.update(overrides)
    return OpportunityEvent(**defaults)


def test_candidate_fields():
    ev = _make_event()
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert c.event.tf_pair == "H1@H4"
    assert c.zone_top == 1.2550
    assert c.zone_bottom == 1.2500
    assert c.entry_price == 1.2560
    assert c.direction == "long"  # demand zone → long


def test_candidate_direction_supply():
    ev = _make_event(zone_side="supply")
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2540, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert c.direction == "short"


def test_candidate_zone_thickness():
    ev = _make_event()
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert abs(c.zone_thickness - 0.0050) < 1e-8


def test_build_candidates_returns_list(small_engine_data):
    """build_retest_candidates runs engine and returns enriched candidates."""
    candidates = build_retest_candidates(
        data_by_tf=small_engine_data,
        entry_tf="M5",
        symbol="TEST",
    )
    assert isinstance(candidates, list)
    for c in candidates:
        assert isinstance(c, RetestCandidate)
        assert c.zone_top > c.zone_bottom
        assert c.atr > 0
        assert c.entry_price > 0
