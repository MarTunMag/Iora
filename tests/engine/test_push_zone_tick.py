# tests/engine/test_push_zone_tick.py
from __future__ import annotations

from math import nan

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.push_zone_tick import push_zone_tick


T0 = pd.Timestamp("2026-01-01 00:00")
T1 = pd.Timestamp("2026-01-01 01:00")
T2 = pd.Timestamp("2026-01-01 02:00")
T3 = pd.Timestamp("2026-01-01 03:00")
TF_SECONDS = 3600  # H1


class TestZoneCreation:
    def test_supply_zone_created_on_hi_fire(self):
        state = PushZoneTickState()
        push_zone_tick(
            state=state,
            close=1.24,
            hi_fire=True, hi_ztop=1.2500, hi_zbot=1.2400,
            hi_time=T0, hi_is_hh=True, hi_txt="HH", seq_hh=1.2500,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 1
        z = state.supply_zones[0]
        assert z.top == 1.2500
        assert z.bottom == 1.2400
        assert z.is_supply is True
        assert z.swing_cls == "HH"
        assert z.timeframe == "H1"

    def test_demand_zone_created_on_lo_fire(self):
        state = PushZoneTickState()
        push_zone_tick(
            state=state,
            close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.2400, lo_zbot=1.2300,
            lo_time=T0, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.demand_zones) == 1
        z = state.demand_zones[0]
        assert z.top == 1.2400
        assert z.bottom == 1.2300
        assert z.is_supply is False
        assert z.swing_cls == "LL"

    def test_zone_count_increments(self):
        state = PushZoneTickState()
        # First supply zone
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=True, hi_ztop=1.25, hi_zbot=1.24,
            hi_time=T0, hi_is_hh=True, hi_txt="HH", seq_hh=1.25,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].count_num == 1
        # Second supply zone
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=True, hi_ztop=1.26, hi_zbot=1.25,
            hi_time=T1, hi_is_hh=False, hi_txt="LH", seq_hh=1.26,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[1].count_num == 2
        assert state.sup_count == 2


class TestZoneBreak:
    def test_supply_zone_breaks_on_close_above_top(self):
        state = PushZoneTickState()
        state.supply_zones.append(PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2510,  # close above top
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 0
        assert len(broken) == 1
        assert broken[0].is_supply is True

    def test_demand_zone_breaks_on_close_below_bottom(self):
        state = PushZoneTickState()
        state.demand_zones.append(PushZone(
            top=1.2400, bottom=1.2300, is_supply=False,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2290,  # close below bottom
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.demand_zones) == 0
        assert len(broken) == 1

    def test_wick_does_not_break_zone(self):
        """Close inside zone = no break, even if high/low pierced boundary."""
        state = PushZoneTickState()
        state.supply_zones.append(PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2480,  # close inside zone
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 1
        assert len(broken) == 0

    def test_zone_expires_by_age(self):
        state = PushZoneTickState()
        old_time = T0 - pd.Timedelta(hours=100)
        state.supply_zones.append(PushZone(
            top=1.25, bottom=1.24, is_supply=True,
            origin_time=old_time, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T0, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 0
