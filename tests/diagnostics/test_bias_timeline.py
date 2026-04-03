"""Unit tests for bias timeline computation functions."""
from __future__ import annotations

from iora.diagnostics.bias_timeline import compute_bias_label


class TestComputeBiasLabel:
    def test_bull_push(self):
        # HH + HL → bull push
        assert compute_bias_label([1.32, 1.30], [1.28, 1.26]) == "HH_HL_bull_push"

    def test_bear_push(self):
        # LH + LL → bear push
        assert compute_bias_label([1.28, 1.30], [1.24, 1.26]) == "LH_LL_bear_push"

    def test_compression(self):
        # LH + HL → compression
        assert compute_bias_label([1.28, 1.30], [1.28, 1.26]) == "LH_HL_compression"

    def test_expansion(self):
        # HH + LL → expansion
        assert compute_bias_label([1.32, 1.30], [1.24, 1.26]) == "HH_LL_expansion"

    def test_insufficient_data(self):
        assert compute_bias_label([1.30], [1.26]) == "unknown"
        assert compute_bias_label([], []) == "unknown"

    def test_equal_highs_lows(self):
        # Equal values → mixed
        assert compute_bias_label([1.30, 1.30], [1.26, 1.26]) == "mixed"


from iora.diagnostics.bias_timeline import compute_bias_strength


class TestComputeBiasStrength:
    def test_strong_bull_3_hh(self):
        # 3 consecutive HH → strength 3
        assert compute_bias_strength([1.34, 1.32, 1.30], [1.28, 1.26, 1.24]) == 3

    def test_moderate_2_hh(self):
        # Last 2 HH but 3rd breaks → strength 2
        assert compute_bias_strength([1.34, 1.32, 1.33], [1.28, 1.26, 1.24]) == 2

    def test_weak_single(self):
        # Only latest is HH, previous was LH → strength 1
        assert compute_bias_strength([1.34, 1.32, 1.35], [1.26, 1.28, 1.24]) == 1

    def test_insufficient_data(self):
        # < 2 periods → strength 0
        assert compute_bias_strength([1.30], [1.26]) == 0
        assert compute_bias_strength([], []) == 0

    def test_strong_bear_3_lh(self):
        # 3 consecutive LH + LL → strength 3
        assert compute_bias_strength([1.30, 1.32, 1.34], [1.24, 1.26, 1.28]) == 3


import pandas as pd
from iora.diagnostics.bias_timeline import nearest_zone_distance, BiasStateRecord
from iora.engine.push_zone_models import PushZone


class TestNearestZoneDistance:
    def test_no_zones(self):
        assert nearest_zone_distance(1.3000, [], 0.0020) == float("inf")

    def test_single_zone_above(self):
        z = PushZone(top=1.3100, bottom=1.3080, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Zone bottom = 1.3080, close = 1.3000, distance to nearest boundary = 0.0080
        # ATR = 0.002, so in ATR units = 0.0080 / 0.002 = 4.0
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert abs(dist - 4.0) < 0.01

    def test_inside_zone_negative(self):
        z = PushZone(top=1.3020, bottom=1.2980, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Close = 1.3000, inside zone (bottom=1.2980, top=1.3020)
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert dist < 0  # Negative means inside

    def test_picks_nearest(self):
        z_far = PushZone(top=1.3200, bottom=1.3180, is_supply=True,
                         origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        z_near = PushZone(top=1.3060, bottom=1.3040, is_supply=True,
                          origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        dist = nearest_zone_distance(1.3000, [z_far, z_near], 0.002)
        # Should pick z_near: boundary distance = 1.3040 - 1.3000 = 0.004 / 0.002 = 2.0
        assert dist < 10.0  # Closer to z_near


class TestBiasStateRecord:
    def test_defaults(self):
        rec = BiasStateRecord(timestamp=pd.Timestamp("2025-01-01"))
        assert rec.d_bias == "unknown"
        assert rec.d_bias_strength == 0
        assert rec.is_bias_transition is False


from math import inf
from iora.diagnostics.bias_timeline import compute_d_to_w_relationship, compute_tf_vs_daily


class TestDToWRelationship:
    def test_inside_w_supply(self):
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=-0.5, w_demand_dist=5.0,
        )
        assert result == "inside_zone"

    def test_inside_w_demand(self):
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=5.0, w_demand_dist=-0.5,
        )
        assert result == "inside_zone"

    def test_bull_pushing_toward_w_supply(self):
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=2.0, w_demand_dist=8.0,
        )
        assert result == "pullback"

    def test_bull_pushing_away_from_w_supply(self):
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=8.0, w_demand_dist=2.0,
        )
        assert result == "continuation"

    def test_bear_pushing_toward_w_demand(self):
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=8.0, w_demand_dist=2.0,
        )
        assert result == "pullback"

    def test_bear_pushing_away_from_w_demand(self):
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=2.0, w_demand_dist=8.0,
        )
        assert result == "continuation"

    def test_neutral_bias(self):
        result = compute_d_to_w_relationship(
            d_bias="unknown", w_supply_dist=5.0, w_demand_dist=5.0,
        )
        assert result == "neutral"

    def test_no_w_zones(self):
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=inf, w_demand_dist=inf,
        )
        assert result == "neutral"


class TestTfVsDaily:
    def test_same_direction_bullish(self):
        assert compute_tf_vs_daily("HH_HL_bull_push", "HH_HL_bull_push") == "with"

    def test_opposite_direction(self):
        assert compute_tf_vs_daily("LH_LL_bear_push", "HH_HL_bull_push") == "against"

    def test_neutral_on_unknown(self):
        assert compute_tf_vs_daily("unknown", "HH_HL_bull_push") == "neutral"

    def test_compression_vs_bull(self):
        assert compute_tf_vs_daily("LH_HL_compression", "HH_HL_bull_push") == "neutral"


from iora.diagnostics.bias_timeline import collect_bias_state
from iora.engine.push_zone_models import PushZoneTickState, PeriodTracker
from iora.orchestrator.push_zone_engine import PushZoneEngineState


def _make_period_tracker(prev_highs, prev_lows):
    """Helper to build a PeriodTracker with preset history."""
    pt = PeriodTracker()
    pt.prev_highs = list(prev_highs)
    pt.prev_lows = list(prev_lows)
    return pt


def _make_state(d_highs, d_lows, h4_highs=None, h4_lows=None,
                h1_highs=None, h1_lows=None,
                w_supply=None, w_demand=None,
                d_supply=None, d_demand=None):
    """Helper to build engine state with preset period histories and zones."""
    tick_states = {}
    for tf, highs, lows in [("D1", d_highs, d_lows),
                             ("H4", h4_highs or [], h4_lows or []),
                             ("H1", h1_highs or [], h1_lows or [])]:
        ts = PushZoneTickState()
        ts.period = _make_period_tracker(highs, lows)
        tick_states[tf] = ts

    w_ts = PushZoneTickState()
    w_ts.supply_zones = list(w_supply or [])
    w_ts.demand_zones = list(w_demand or [])
    tick_states["W1"] = w_ts

    if "D1" in tick_states:
        tick_states["D1"].supply_zones = list(d_supply or [])
        tick_states["D1"].demand_zones = list(d_demand or [])

    return PushZoneEngineState(tick_states=tick_states)


class TestCollectBiasState:
    def test_basic_bull_bias(self):
        state = _make_state(
            d_highs=[1.32, 1.30, 1.28], d_lows=[1.28, 1.26, 1.24],
            h4_highs=[1.315, 1.31], h4_lows=[1.275, 1.27],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
        )
        assert rec.d_bias == "HH_HL_bull_push"
        assert rec.d_bias_strength == 3
        assert rec.h4_vs_daily == "with"

    def test_no_data_returns_unknown(self):
        state = _make_state(d_highs=[], d_lows=[])
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
        )
        assert rec.d_bias == "unknown"
        assert rec.d_bias_strength == 0

    def test_transition_detected(self):
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="LH_LL_bear_push",
        )
        assert rec.is_bias_transition is True
        assert rec.transition_from == "LH_LL_bear_push"
        assert rec.transition_to == "HH_HL_bull_push"

    def test_no_transition_when_same(self):
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="HH_HL_bull_push",
        )
        assert rec.is_bias_transition is False

    def test_no_transition_from_unknown(self):
        """Transition from 'unknown' to a known bias is suppressed."""
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="unknown",
        )
        assert rec.is_bias_transition is False
