# tests/strategy/test_filter_funnel.py
"""Tests for filter funnel logic."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.filter_funnel import apply_filters, FilterFunnel


def _candidate(touch_type="wick_touch", bias="with_daily", role="continuation",
               age="fresh", test_cls="retested_1", side="demand",
               strength=2, replacement=0, hour=10) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=pd.Timestamp(f"2025-01-15 {hour:02d}:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type=touch_type, zone_side=side,
        zone_role=role, age_bucket=age,
        bias_alignment=bias, test_count_cls=test_cls,
        zone_age_bars=5, zone_test_count=1, bias_strength=strength,
        price_distance_at_touch=1.5, replacement_count=replacement,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )


def test_no_filters_passes_all():
    candidates = [_candidate(), _candidate(touch_type="body_close")]
    cfg = RetestConfig(touch_type="any", bias_filter="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2
    assert funnel.steps[0].name == "touch_type"


def test_touch_type_filter():
    candidates = [
        _candidate(touch_type="wick_touch"),
        _candidate(touch_type="body_close"),
        _candidate(touch_type="near_miss"),
    ]
    cfg = RetestConfig(touch_type="wick_touch")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    assert funnel.passed[0].event.touch_type == "wick_touch"


def test_bias_filter():
    candidates = [
        _candidate(bias="with_daily"),
        _candidate(bias="against_daily"),
        _candidate(bias="neutral"),
    ]
    cfg = RetestConfig(bias_filter="with_daily", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1


def test_direction_filter_long():
    candidates = [
        _candidate(side="demand"),   # long
        _candidate(side="supply"),   # short
    ]
    cfg = RetestConfig(direction="long", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    assert funnel.passed[0].direction == "long"


def test_session_filter_london():
    candidates = [
        _candidate(hour=10),  # Inside London (07-16)
        _candidate(hour=3),   # Asian session
        _candidate(hour=20),  # Late NY
    ]
    cfg = RetestConfig(session_filter="london", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1


def test_session_filter_no_asian():
    candidates = [
        _candidate(hour=10),  # London
        _candidate(hour=3),   # Asian
        _candidate(hour=14),  # London-NY overlap
    ]
    cfg = RetestConfig(session_filter="no_asian", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_age_filter_fresh_young():
    candidates = [
        _candidate(age="fresh"),
        _candidate(age="young"),
        _candidate(age="mature"),
        _candidate(age="old"),
    ]
    cfg = RetestConfig(age_filter="fresh_young", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_min_bias_strength():
    candidates = [
        _candidate(strength=1),
        _candidate(strength=2),
        _candidate(strength=3),
    ]
    cfg = RetestConfig(min_bias_strength=2, touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_funnel_step_tracking():
    candidates = [
        _candidate(touch_type="wick_touch", bias="with_daily"),
        _candidate(touch_type="body_close", bias="with_daily"),
        _candidate(touch_type="wick_touch", bias="against_daily"),
    ]
    cfg = RetestConfig(touch_type="wick_touch", bias_filter="with_daily")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    # Touch type filter should remove 1 (body_close)
    touch_step = next(s for s in funnel.steps if s.name == "touch_type")
    assert touch_step.input_count == 3
    assert touch_step.output_count == 2
    assert touch_step.removed == 1
    # Bias filter should remove 1 (against_daily)
    bias_step = next(s for s in funnel.steps if s.name == "bias_filter")
    assert bias_step.input_count == 2
    assert bias_step.output_count == 1
    assert bias_step.removed == 1
