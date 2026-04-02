from __future__ import annotations

from math import isnan

import pandas as pd

from iora.engine.push_zone_models import PushZone, PeriodTracker, PushZoneTickState


class TestPushZone:
    def test_create_supply_zone(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"), timeframe="H1", swing_cls="HH",
        )
        assert z.top == 1.2500
        assert z.bottom == 1.2400
        assert z.is_supply is True
        assert z.timeframe == "H1"
        assert z.swing_cls == "HH"
        assert z.is_push is False
        assert z.is_reversal is False
        assert z.is_terminal is False
        assert z.struct_cls == ""
        assert z.count_num == 0

    def test_create_demand_zone(self):
        z = PushZone(
            top=1.2400, bottom=1.2300, is_supply=False,
            origin_time=pd.Timestamp("2026-01-01"), timeframe="M5", swing_cls="LL",
        )
        assert z.is_supply is False
        assert z.swing_cls == "LL"

    def test_push_zone_mutable(self):
        z = PushZone(
            top=1.25, bottom=1.24, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        z.is_push = True
        z.struct_cls = "BOS"
        assert z.is_push is True
        assert z.struct_cls == "BOS"

    def test_contains_price_inside(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2450) is True

    def test_contains_price_outside(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2350) is False

    def test_contains_price_boundary(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2500) is True
        assert z.contains_price(1.2400) is True


class TestPeriodTracker:
    def test_initial_state(self):
        pt = PeriodTracker()
        assert isnan(pt.cur_hi)
        assert isnan(pt.cur_lo)
        assert len(pt.prev_highs) == 0
        assert len(pt.prev_lows) == 0
        assert pt.hi_brk_time is None
        assert pt.lo_brk_time is None

    def test_rotate_period(self):
        pt = PeriodTracker()
        pt.cur_hi = 1.2500
        pt.cur_lo = 1.2400
        pt.cur_hi_time = pd.Timestamp("2026-01-01 04:00")
        pt.cur_lo_time = pd.Timestamp("2026-01-01 02:00")
        pt.rotate(pd.Timestamp("2026-01-02"))
        assert pt.prev_highs[0] == 1.2500
        assert pt.prev_lows[0] == 1.2400
        assert len(pt.prev_highs) == 1
        assert pt.hi_brk_time is None

    def test_rotate_caps_at_depth(self):
        pt = PeriodTracker(history_depth=3)
        for i in range(5):
            pt.cur_hi = 1.25 + i * 0.001
            pt.cur_lo = 1.24 - i * 0.001
            pt.cur_hi_time = pd.Timestamp(f"2026-01-0{i+1}")
            pt.cur_lo_time = pd.Timestamp(f"2026-01-0{i+1}")
            pt.rotate(pd.Timestamp(f"2026-01-0{i+2}"))
        assert len(pt.prev_highs) == 3
        assert len(pt.prev_lows) == 3
        assert pt.prev_highs[0] == 1.254


class TestPushZoneTickState:
    def test_initial_state(self):
        st = PushZoneTickState()
        assert len(st.supply_zones) == 0
        assert len(st.demand_zones) == 0
        assert st.trend == 0
        assert st.sup_count == 0
        assert st.dem_count == 0
        assert isnan(st.prev_push_extreme_hi)
