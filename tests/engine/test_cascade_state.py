"""Tests for cascade_state.py — D1→H4→H1 cascade phase classification."""
import math

import pytest

from iora.engine.cascade_state import (
    CascadePhaseState,
    cascade_state_tick,
    _classify_phase,
    _price_near_zone,
)
from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.push_trendline import PushTrendlineState, PushTrendlineBreakEvent


def _make_tick_state(trend: int = 0, sup_count: int = 0, dem_count: int = 0) -> PushZoneTickState:
    ts = PushZoneTickState()
    ts.trend = trend
    ts.sup_count = sup_count
    ts.dem_count = dem_count
    return ts


def _make_push_zone_states(**kwargs) -> dict[str, PushZoneTickState]:
    """Build push_zone_states dict from keyword args like D1=(-1, 0, 0)."""
    result: dict[str, PushZoneTickState] = {}
    for tf, (trend, sup, dem) in kwargs.items():
        result[tf] = _make_tick_state(trend, sup, dem)
    return result


class TestClassifyPhase:
    def test_unknown_when_no_d1_trend(self):
        state = CascadePhaseState()
        assert _classify_phase(state, 1.30) == "unknown"

    def test_d1_push_when_aligned(self):
        state = CascadePhaseState(d1_trend=-1, h4_trend=-1)
        assert _classify_phase(state, 1.30) == "d1_push"

    def test_h4_correction_when_opposing(self):
        state = CascadePhaseState(d1_trend=-1, h4_trend=1)
        assert _classify_phase(state, 1.30) == "h4_correction"

    def test_h4_correction_tl_break(self):
        state = CascadePhaseState(
            d1_trend=-1, h4_trend=1,
            h4_correction_tl_intact=False,
        )
        assert _classify_phase(state, 1.30) == "h4_correction_tl_break"

    def test_h1_extended(self):
        state = CascadePhaseState(d1_trend=-1, h4_trend=-1, h1_push_zone_count=5)
        assert _classify_phase(state, 1.30) == "h1_extended"

    def test_h1_terminal(self):
        state = CascadePhaseState(
            d1_trend=-1, h4_trend=-1,
            h1_push_zone_count=6,
            h1_impulse_tl_intact=False,
        )
        assert _classify_phase(state, 1.30) == "h1_terminal"

    def test_at_reversal_target(self):
        state = CascadePhaseState(
            d1_trend=-1, h4_trend=-1,
            h1_push_zone_count=7,
            h1_impulse_tl_intact=False,
            h1_reversal_target_top=1.32,
            h1_reversal_target_bottom=1.31,
        )
        # Price inside zone
        assert _classify_phase(state, 1.315) == "at_reversal_target"
        # Price far away
        assert _classify_phase(state, 1.40) == "h1_terminal"

    def test_h1_extended_overrides_d1_push(self):
        """5+ zones takes priority over d1_push."""
        state = CascadePhaseState(d1_trend=-1, h4_trend=-1, h1_push_zone_count=8)
        assert _classify_phase(state, 1.30) == "h1_extended"


class TestPriceNearZone:
    def test_inside_zone(self):
        assert _price_near_zone(1.315, 1.32, 1.31)

    def test_near_zone_within_one_height(self):
        # Zone 1.31-1.32 (height=0.01), price at 1.305 = 0.005 below bot
        assert _price_near_zone(1.305, 1.32, 1.31)

    def test_far_from_zone(self):
        assert not _price_near_zone(1.40, 1.32, 1.31)

    def test_nan_zone(self):
        assert not _price_near_zone(1.30, float('nan'), float('nan'))


class TestCascadeStateTick:
    def test_basic_d1_push_phase(self):
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(-1, 0, 0), H4=(-1, 0, 0), H1=(0, 0, 0), M15=(0, 0, 0))
        tls: dict[str, PushTrendlineState] = {}
        tl_events: dict[str, list[PushTrendlineBreakEvent]] = {}

        phase = cascade_state_tick(state, pzs, tls, tl_events, 1.30)
        assert phase == "d1_push"
        assert state.d1_trend == -1
        assert state.h4_trend == -1

    def test_h4_correction_detected(self):
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(-1, 0, 0), H4=(1, 0, 0), H1=(0, 0, 0), M15=(0, 0, 0))
        phase = cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert phase == "h4_correction"

    def test_h1_zone_count_from_sup_count(self):
        """Bearish D1: count supply zones at H1."""
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(-1, 5, 2), H4=(-1, 0, 0), H1=(-1, 6, 2), M15=(0, 0, 0))
        phase = cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_push_zone_count == 6
        assert phase == "h1_extended"

    def test_h1_zone_count_from_dem_count(self):
        """Bullish D1: count demand zones at H1."""
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(1, 2, 7), H4=(1, 0, 0), H1=(1, 2, 7), M15=(0, 0, 0))
        phase = cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_push_zone_count == 7
        assert phase == "h1_extended"

    def test_tl_break_event_updates_state(self):
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(-1, 0, 0), H4=(1, 0, 0), H1=(0, 0, 0), M15=(0, 0, 0))

        ev = PushTrendlineBreakEvent(
            tf="H4", tl_type="correction", break_direction="bearish",
            bar_idx=100, break_price=1.30, projected_price=1.31,
            anchor1_price=1.32, anchor2_price=1.31,
        )
        phase = cascade_state_tick(state, pzs, {}, {"H4": [ev]}, 1.30)
        assert not state.h4_correction_tl_intact
        assert phase == "h4_correction_tl_break"

    def test_d1_trend_change_resets_zone_count(self):
        state = CascadePhaseState()
        # First tick: D1 bearish with 6 supply zones
        pzs = _make_push_zone_states(D1=(-1, 6, 0), H4=(-1, 0, 0), H1=(-1, 6, 0), M15=(0, 0, 0))
        cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_push_zone_count == 6

        # D1 flips to bullish → count resets
        pzs2 = _make_push_zone_states(D1=(1, 6, 0), H4=(1, 0, 0), H1=(1, 6, 3), M15=(0, 0, 0))
        cascade_state_tick(state, pzs2, {}, {}, 1.30)
        assert state.h1_push_zone_count == 3  # Now counting demand

    def test_impulse_tl_break_triggers_terminal(self):
        state = CascadePhaseState()
        pzs = _make_push_zone_states(D1=(-1, 6, 0), H4=(-1, 0, 0), H1=(-1, 6, 0), M15=(0, 0, 0))

        ev = PushTrendlineBreakEvent(
            tf="H1", tl_type="impulse", break_direction="bullish",
            bar_idx=200, break_price=1.32, projected_price=1.31,
            anchor1_price=1.34, anchor2_price=1.33,
        )
        phase = cascade_state_tick(state, pzs, {}, {"H1": [ev]}, 1.32)
        assert phase == "h1_terminal"
        assert not state.h1_impulse_tl_intact


class TestEWExhaustionSignals:
    def _make_h1_with_zones(self, trend, sup_count, zones_supply, zones_demand=None):
        """Build H1 tick state with specific zone data."""
        ts = PushZoneTickState()
        ts.trend = trend
        ts.sup_count = sup_count
        ts.dem_count = 0
        for z in zones_supply:
            ts.supply_zones.append(z)
        if zones_demand:
            for z in zones_demand:
                ts.demand_zones.append(z)
        return ts

    def _make_zone(self, top, bottom, is_supply=True):
        import pandas as pd
        return PushZone(
            top=top, bottom=bottom, is_supply=is_supply,
            origin_time=pd.Timestamp("2026-01-01"),
        )

    def test_zone1_stored_on_first_count(self):
        state = CascadePhaseState()
        z1 = self._make_zone(1.35, 1.34)
        h1_ts = self._make_h1_with_zones(-1, 1, [z1])
        pzs = {"D1": _make_tick_state(-1), "H4": _make_tick_state(-1),
               "H1": h1_ts, "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_zone1_top == 1.35
        assert state.h1_zone1_bottom == 1.34
        assert state.h1_zone1_range == pytest.approx(0.01)

    def test_zone3_extension_ratio(self):
        state = CascadePhaseState()
        z1 = self._make_zone(1.35, 1.34)
        h1_ts = self._make_h1_with_zones(-1, 1, [z1])
        pzs = {"D1": _make_tick_state(-1), "H4": _make_tick_state(-1),
               "H1": h1_ts, "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs, {}, {}, 1.30)

        # Count 2
        z2 = self._make_zone(1.33, 1.32)
        h1_ts.supply_zones.append(z2)
        h1_ts.sup_count = 2
        pzs["H1"] = h1_ts
        cascade_state_tick(state, pzs, {}, {}, 1.30)

        # Count 3: zone3 bottom = 1.29, zone2 bottom = 1.32
        z3 = self._make_zone(1.30, 1.29)
        h1_ts.supply_zones.append(z3)
        h1_ts.sup_count = 3
        pzs["H1"] = h1_ts
        cascade_state_tick(state, pzs, {}, {}, 1.28)
        # zone3_range = |1.32 - 1.29| = 0.03
        # zone1_range = 0.01
        # extension = 3.0
        assert state.h1_zone3_range == pytest.approx(0.03)
        assert state.h1_wave3_extension_ratio == pytest.approx(3.0)

    def test_zone4_overlap_bearish(self):
        state = CascadePhaseState()
        z1 = self._make_zone(1.35, 1.34)
        h1_ts = self._make_h1_with_zones(-1, 1, [z1])
        pzs = {"D1": _make_tick_state(-1), "H4": _make_tick_state(-1),
               "H1": h1_ts, "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs, {}, {}, 1.30)

        # Skip to count 4 with overlap: zone4 top (1.345) > zone1 bottom (1.34)
        z2 = self._make_zone(1.33, 1.32)
        z3 = self._make_zone(1.30, 1.29)
        z4 = self._make_zone(1.345, 1.335)  # Overlaps zone1
        h1_ts.supply_zones.extend([z2, z3, z4])
        h1_ts.sup_count = 4
        pzs["H1"] = h1_ts
        cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_zone4_overlaps_zone1 is True

    def test_zone4_no_overlap_bearish(self):
        state = CascadePhaseState()
        z1 = self._make_zone(1.35, 1.34)
        h1_ts = self._make_h1_with_zones(-1, 1, [z1])
        pzs = {"D1": _make_tick_state(-1), "H4": _make_tick_state(-1),
               "H1": h1_ts, "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs, {}, {}, 1.30)

        z2 = self._make_zone(1.33, 1.32)
        z3 = self._make_zone(1.30, 1.29)
        z4 = self._make_zone(1.28, 1.27)  # No overlap (below zone1)
        h1_ts.supply_zones.extend([z2, z3, z4])
        h1_ts.sup_count = 4
        pzs["H1"] = h1_ts
        cascade_state_tick(state, pzs, {}, {}, 1.25)
        assert state.h1_zone4_overlaps_zone1 is False

    def test_ew_reset_on_direction_change(self):
        state = CascadePhaseState()
        z1 = self._make_zone(1.35, 1.34)
        h1_ts = self._make_h1_with_zones(-1, 1, [z1])
        pzs = {"D1": _make_tick_state(-1), "H4": _make_tick_state(-1),
               "H1": h1_ts, "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs, {}, {}, 1.30)
        assert state.h1_zone1_top == 1.35

        # D1 trend flips
        pzs2 = {"D1": _make_tick_state(1), "H4": _make_tick_state(1),
                "H1": _make_tick_state(1, 0, 2), "M15": _make_tick_state(0)}
        cascade_state_tick(state, pzs2, {}, {}, 1.30)
        assert math.isnan(state.h1_zone1_top)
