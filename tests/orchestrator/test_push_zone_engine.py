from __future__ import annotations

from math import nan

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone, PushZoneTickState, PeriodTracker
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState,
    PushZoneEngineConfig,
    init_push_zone_state,
    push_zone_engine_tick,
    _check_nesting,
)
from iora.engine.models import BarContext
from iora.engine.events import EventBus


def _make_ctx(
    close: float,
    high: float,
    low: float,
    bar_time: pd.Timestamp,
    htf: dict | None = None,
    edges: dict | None = None,
) -> BarContext:
    return BarContext(
        idx=0,
        timestamp=bar_time,
        open_=close,
        high=high,
        low=low,
        close=close,
        htf=htf or {},
        edges=edges or {},
    )


T0 = pd.Timestamp("2026-01-01 00:00")
T1 = pd.Timestamp("2026-01-01 01:00")


class TestInitState:
    def test_creates_state_for_all_tfs(self):
        state = init_push_zone_state(["M5", "H1", "H4"])
        assert "M5" in state.tick_states
        assert "H1" in state.tick_states
        assert "H4" in state.tick_states
        assert len(state.tick_states) == 3

    def test_each_tf_has_period_tracker(self):
        state = init_push_zone_state(["H1"])
        assert isinstance(state.tick_states["H1"].period, PeriodTracker)


class TestPeriodTracking:
    def test_trend_updates_on_hi_break(self):
        """When high breaks previous period high, trend goes to +1."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        ts.period.prev_highs = [1.2500]
        ts.period.prev_hi_times = [T0]
        ctx = _make_ctx(close=1.2480, high=1.2510, low=1.2450, bar_time=T1,
                        htf={"H1": {"new_period": False}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.trend == 1

    def test_trend_updates_on_lo_break(self):
        """When low breaks previous period low, trend goes to -1."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        ts.period.prev_lows = [1.2300]
        ts.period.prev_lo_times = [T0]
        ctx = _make_ctx(close=1.2310, high=1.2350, low=1.2290, bar_time=T1,
                        htf={"H1": {"new_period": False}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.trend == -1

    def test_rotate_on_new_period(self):
        """On new period boundary, current hi/lo rotate into prev lists."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        ts.period.cur_hi = 1.2600
        ts.period.cur_lo = 1.2400
        ts.period.cur_hi_time = T0
        ts.period.cur_lo_time = T0
        ctx = _make_ctx(close=1.2500, high=1.2510, low=1.2490, bar_time=T1,
                        htf={"H1": {"new_period": True}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.period.prev_highs[0] == 1.2600
        assert ts.period.prev_lows[0] == 1.2400


class TestNesting:
    def test_child_inside_parent_detected(self):
        """Child zone fully inside parent = nested."""
        parent = PushZone(
            top=1.2600, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        )
        child = PushZone(
            top=1.2550, bottom=1.2450, is_supply=True,
            origin_time=T0, timeframe="M5",
        )
        result = _check_nesting(child, [parent])
        assert result is not None

    def test_opposing_direction_is_terminal(self):
        """Child inside parent with opposing direction — terminal case."""
        parent = PushZone(
            top=1.2600, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        )
        child = PushZone(
            top=1.2550, bottom=1.2450, is_supply=False,
            origin_time=T0, timeframe="M5",
        )
        result = _check_nesting(child, [parent])
        assert result is not None
        assert child.is_supply != result.is_supply


class TestCountReset:
    def test_hh_resets_supply_count(self):
        """HH supply fire resets supply count to 0, then increments to 1."""
        state = init_push_zone_state(["H1"])
        state.tick_states["H1"].sup_count = 5
        ctx = _make_ctx(close=1.25, high=1.26, low=1.24, bar_time=T1,
                        edges={"H1": {"edge_hi_fire": True, "edge_lo_fire": False}},
                        htf={"H1": {
                            "hi_fire": True, "ztop": 1.27, "zbot": 1.26,
                            "hi_time": T0, "hi_is_hh": True,
                            "hi_txt": "HH", "seq_hh": 1.27,
                            "lo_fire": False, "lo_time": None,
                            "lo_is_ll": False, "lo_txt": "", "seq_ll": nan,
                            "new_period": False,
                        }})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert state.tick_states["H1"].sup_count == 1
