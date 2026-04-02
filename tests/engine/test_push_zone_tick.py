# tests/engine/test_push_zone_tick.py
from __future__ import annotations

from math import isnan, nan

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

    def test_zone_not_expired_by_age(self):
        """Zones should NOT be removed by age — only by body-close break."""
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
        assert len(state.supply_zones) == 1  # Zone survives — no age expiry

    def test_soft_cap_evicts_oldest(self):
        """When more than 30 zones per side, oldest is evicted."""
        state = PushZoneTickState()
        for i in range(30):
            state.supply_zones.append(PushZone(
                top=1.3000 + i * 0.001, bottom=1.2990 + i * 0.001,
                is_supply=True, origin_time=T0, timeframe="H1",
            ))
        # Fire a new supply zone — should evict oldest
        push_zone_tick(
            state=state, close=1.3500,
            hi_fire=True, hi_ztop=1.3600, hi_zbot=1.3550,
            hi_time=T1, hi_is_hh=False, hi_txt="LH", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) <= 30  # Soft cap enforced

    def test_zone_creation_ignores_age_check(self):
        """New zones are created even when origin is old (age check removed)."""
        state = PushZoneTickState()
        push_zone_tick(
            state=state, close=1.2900,
            hi_fire=True, hi_ztop=1.3000, hi_zbot=1.2980,
            hi_time=pd.Timestamp("2024-01-01"),  # Very old origin
            hi_is_hh=False, hi_txt="LH", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=pd.Timestamp("2026-06-01"),
            tf_seconds=TF_SECONDS, max_age=50, timeframe="H1",
        )
        assert len(state.supply_zones) == 1  # Zone created despite old origin


class TestPushValidation:
    def test_bearish_push_tags_supply_and_reversal(self):
        """Demand fires with LL → most recent supply tagged PUSH, demand tagged REVERSAL."""
        state = PushZoneTickState()
        state.supply_zones.append(PushZone(
            top=1.2600, bottom=1.2500, is_supply=True,
            origin_time=T0, timeframe="H1", swing_cls="HH",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.2400, lo_zbot=1.2300,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].is_push is True
        assert state.demand_zones[0].is_reversal is True
        assert state.prev_push_extreme_lo == 1.2300

    def test_bullish_push_tags_demand_and_reversal(self):
        """Supply fires with HH → most recent demand tagged PUSH, supply tagged REVERSAL."""
        state = PushZoneTickState()
        state.demand_zones.append(PushZone(
            top=1.2400, bottom=1.2300, is_supply=False,
            origin_time=T0, timeframe="H1", swing_cls="LL",
        ))
        push_zone_tick(
            state=state, close=1.26,
            hi_fire=True, hi_ztop=1.2700, hi_zbot=1.2600,
            hi_time=T1, hi_is_hh=True, hi_txt="HH", seq_hh=1.2700,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.demand_zones[0].is_push is True
        assert state.supply_zones[0].is_reversal is True
        assert state.prev_push_extreme_hi == 1.2700

    def test_no_push_if_boundary_not_broken(self):
        """LL that doesn't break prev_push_extreme_lo = no push tag."""
        state = PushZoneTickState()
        state.prev_push_extreme_lo = 1.2200
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].is_push is False
        assert state.demand_zones[0].is_reversal is False

    def test_bootstrap_push_when_prev_extreme_is_nan(self):
        """First LL ever → auto-qualifies as push (bootstrap)."""
        state = PushZoneTickState()
        assert isnan(state.prev_push_extreme_lo)
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].is_push is True


class TestBOSCHoCH:
    def test_bos_bearish_push_bearish_trend(self):
        """Bearish push + trend=-1 → BOS."""
        state = PushZoneTickState()
        state.trend = -1
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].struct_cls == "BOS"

    def test_choch_bullish_push_bearish_trend(self):
        """Bullish push + trend=-1 → CHoCH."""
        state = PushZoneTickState()
        state.trend = -1
        state.demand_zones.append(PushZone(
            top=1.24, bottom=1.23, is_supply=False,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.26,
            hi_fire=True, hi_ztop=1.27, hi_zbot=1.26,
            hi_time=T1, hi_is_hh=True, hi_txt="HH", seq_hh=1.27,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.demand_zones[0].struct_cls == "CHoCH"

    def test_no_classification_when_trend_zero(self):
        """Trend=0 → no BOS/CHoCH classification."""
        state = PushZoneTickState()
        state.trend = 0
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].struct_cls == ""
