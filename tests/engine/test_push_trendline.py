"""Tests for push_trendline.py — PeriodTracker-based trendline detection."""
import math

import pytest

from iora.engine.push_trendline import (
    PushTrendlineState,
    PushTrendlineBreakEvent,
    push_trendline_tick,
    _project_price,
    _classify_tl,
    get_projected_prices,
)


# ---------------------------------------------------------------------------
# _project_price
# ---------------------------------------------------------------------------

class TestProjectPrice:
    def test_flat_line(self):
        assert _project_price(1.0, 0, 1.0, 10, 20) == 1.0

    def test_descending_slope(self):
        # 1.35 at bar 0, 1.33 at bar 10 → slope = -0.002/bar
        # At bar 20: 1.33 + (-0.002)*(20-10) = 1.31
        assert _project_price(1.35, 0, 1.33, 10, 20) == pytest.approx(1.31)

    def test_ascending_slope(self):
        # 1.30 at bar 0, 1.32 at bar 10 → slope = +0.002/bar
        # At bar 20: 1.32 + 0.002*10 = 1.34
        assert _project_price(1.30, 0, 1.32, 10, 20) == pytest.approx(1.34)

    def test_same_bar_returns_p2(self):
        assert _project_price(1.0, 5, 2.0, 5, 10) == 2.0


# ---------------------------------------------------------------------------
# _classify_tl
# ---------------------------------------------------------------------------

class TestClassifyTL:
    def test_bearish_desc_is_impulse(self):
        assert _classify_tl("desc", -1) == "impulse"

    def test_bearish_asc_is_correction(self):
        assert _classify_tl("asc", -1) == "correction"

    def test_bullish_asc_is_impulse(self):
        assert _classify_tl("asc", 1) == "impulse"

    def test_bullish_desc_is_correction(self):
        assert _classify_tl("desc", 1) == "correction"

    def test_unknown_trend(self):
        assert _classify_tl("desc", 0) == "unknown"
        assert _classify_tl("asc", 0) == "unknown"


# ---------------------------------------------------------------------------
# Descending TL construction
# ---------------------------------------------------------------------------

class TestDescendingTL:
    def test_two_lh_pivots_create_active_tl(self):
        """Two consecutive lower highs should activate a descending TL."""
        state = PushTrendlineState()

        # Bar 10: first swing high at 1.35
        push_trendline_tick(state, 10, 1.34, 1.30, 1.32, [1.35], [], 0)
        assert not state.desc_active

        # Bar 20: second swing high at 1.33 (LH) → TL activates
        push_trendline_tick(state, 20, 1.32, 1.28, 1.30, [1.33, 1.35], [], 0)
        assert state.desc_active
        assert state.desc_anchor1_price == 1.35
        assert state.desc_anchor2_price == 1.33

    def test_hh_replaces_anchor1(self):
        """A higher high should replace anchor1, not create a TL."""
        state = PushTrendlineState()

        push_trendline_tick(state, 10, 1.34, 1.30, 1.32, [1.35], [], 0)
        # HH: 1.37 > 1.35
        push_trendline_tick(state, 20, 1.36, 1.32, 1.34, [1.37, 1.35], [], 0)
        assert not state.desc_active
        assert state.desc_anchor1_price == 1.37

    def test_reanchor_on_new_lh(self):
        """Third LH below projected TL re-anchors: shift a2→a1, new→a2."""
        state = PushTrendlineState()

        # Build TL: 1.35 @ bar 0, 1.33 @ bar 10
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [1.35], [], 0)
        push_trendline_tick(state, 10, 1.32, 1.28, 1.30, [1.33, 1.35], [], 0)
        assert state.desc_active

        # Bar 20: projected TL = 1.33 + (-0.002)*10 = 1.31
        # New LH at 1.30 (below 1.31) → re-anchor
        push_trendline_tick(state, 20, 1.29, 1.26, 1.28, [1.30, 1.33, 1.35], [], 0)
        assert state.desc_active
        assert state.desc_anchor1_price == 1.33
        assert state.desc_anchor2_price == 1.30


class TestAscendingTL:
    def test_two_hl_pivots_create_active_tl(self):
        """Two consecutive higher lows should activate an ascending TL."""
        state = PushTrendlineState()

        # Bar 10: first swing low at 1.30
        push_trendline_tick(state, 10, 1.34, 1.30, 1.32, [], [1.30], 0)
        assert not state.asc_active

        # Bar 20: second swing low at 1.32 (HL) → TL activates
        push_trendline_tick(state, 20, 1.36, 1.32, 1.34, [], [1.32, 1.30], 0)
        assert state.asc_active
        assert state.asc_anchor1_price == 1.30
        assert state.asc_anchor2_price == 1.32

    def test_ll_replaces_anchor1(self):
        """A lower low should replace anchor1."""
        state = PushTrendlineState()

        push_trendline_tick(state, 10, 1.34, 1.30, 1.32, [], [1.30], 0)
        # LL: 1.28 < 1.30
        push_trendline_tick(state, 20, 1.32, 1.28, 1.30, [], [1.28, 1.30], 0)
        assert not state.asc_active
        assert state.asc_anchor1_price == 1.28


# ---------------------------------------------------------------------------
# Break detection
# ---------------------------------------------------------------------------

class TestBreakDetection:
    def _build_desc_tl(self) -> PushTrendlineState:
        """Helper: build a descending TL with anchors at bar 0 (1.35) and bar 10 (1.33)."""
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [1.35], [], -1)
        push_trendline_tick(state, 10, 1.32, 1.28, 1.30, [1.33, 1.35], [], -1)
        assert state.desc_active
        return state

    def _build_asc_tl(self) -> PushTrendlineState:
        """Helper: build an ascending TL with anchors at bar 0 (1.30) and bar 10 (1.32)."""
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [], [1.30], 1)
        push_trendline_tick(state, 10, 1.36, 1.32, 1.34, [], [1.32, 1.30], 1)
        assert state.asc_active
        return state

    def test_desc_tl_break_close_mode(self):
        """Body close above projected descending TL = bullish break."""
        state = self._build_desc_tl()
        # At bar 20: projected = 1.33 + (-0.002)*10 = 1.31
        # Close at 1.32 > 1.31 → break
        events = push_trendline_tick(
            state, 20, 1.33, 1.29, 1.32,
            [1.33, 1.35], [], -1, break_mode="close", tf="H1",
        )
        assert len(events) == 1
        assert events[0].break_direction == "bullish"
        assert events[0].tl_type == "impulse"  # desc TL in bearish trend
        assert state.desc_broken

    def test_desc_tl_no_break_close_below(self):
        """Close below projected TL should NOT break."""
        state = self._build_desc_tl()
        # At bar 20: projected = 1.31, close at 1.29 < 1.31
        events = push_trendline_tick(
            state, 20, 1.33, 1.29, 1.29,
            [1.33, 1.35], [], -1, break_mode="close",
        )
        assert len(events) == 0
        assert not state.desc_broken

    def test_desc_tl_wick_mode_uses_high(self):
        """Wick mode: high above projected TL = break even if close is below."""
        state = self._build_desc_tl()
        # At bar 20: projected = 1.31, high = 1.33 > 1.31, close = 1.29
        events = push_trendline_tick(
            state, 20, 1.33, 1.29, 1.29,
            [1.33, 1.35], [], -1, break_mode="wick",
        )
        assert len(events) == 1
        assert events[0].break_direction == "bullish"

    def test_asc_tl_break_close_mode(self):
        """Body close below projected ascending TL = bearish break."""
        state = self._build_asc_tl()
        # At bar 20: projected = 1.32 + (0.002)*10 = 1.34
        # Close at 1.33 < 1.34 → break
        events = push_trendline_tick(
            state, 20, 1.35, 1.33, 1.33,
            [], [1.32, 1.30], 1, break_mode="close", tf="H1",
        )
        assert len(events) == 1
        assert events[0].break_direction == "bearish"
        assert events[0].tl_type == "impulse"  # asc TL in bullish trend
        assert state.asc_broken

    def test_break_fires_once(self):
        """After breaking, subsequent bars should NOT re-fire."""
        state = self._build_desc_tl()
        # First break
        events1 = push_trendline_tick(
            state, 20, 1.33, 1.29, 1.32,
            [1.33, 1.35], [], -1, break_mode="close",
        )
        assert len(events1) == 1

        # Same situation next bar — should not fire again
        events2 = push_trendline_tick(
            state, 21, 1.34, 1.30, 1.33,
            [1.33, 1.35], [], -1, break_mode="close",
        )
        assert len(events2) == 0

    def test_break_resets_on_new_pivot(self):
        """After break, a new pivot resets the TL and it can break again."""
        state = self._build_desc_tl()
        # Break
        push_trendline_tick(
            state, 20, 1.33, 1.29, 1.32,
            [1.33, 1.35], [], -1, break_mode="close",
        )
        assert state.desc_broken

        # New pivot arrives → resets broken state, starts fresh
        push_trendline_tick(
            state, 30, 1.31, 1.27, 1.29,
            [1.31, 1.33, 1.35], [], -1, break_mode="close",
        )
        # After break, new pivot resets to fresh anchor1
        assert not state.desc_broken
        assert state.desc_anchor1_price == 1.31


# ---------------------------------------------------------------------------
# Impulse/correction in break events
# ---------------------------------------------------------------------------

class TestImpulseCorrection:
    def test_bearish_trend_desc_break_is_impulse(self):
        """In bearish trend, descending TL break = impulse break (potential reversal)."""
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [1.35], [], -1)
        push_trendline_tick(state, 10, 1.32, 1.28, 1.30, [1.33, 1.35], [], -1)
        events = push_trendline_tick(
            state, 20, 1.33, 1.29, 1.32,
            [1.33, 1.35], [], -1, break_mode="close", tf="H1",
        )
        assert events[0].tl_type == "impulse"

    def test_bearish_trend_asc_break_is_correction(self):
        """In bearish trend, ascending TL break = correction break (trend resumes)."""
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [], [1.30], -1)
        push_trendline_tick(state, 10, 1.36, 1.32, 1.34, [], [1.32, 1.30], -1)
        # Break ascending TL: close below projected
        # At bar 20: proj = 1.32 + 0.002*10 = 1.34, close = 1.33 < 1.34
        events = push_trendline_tick(
            state, 20, 1.35, 1.33, 1.33,
            [], [1.32, 1.30], -1, break_mode="close", tf="H1",
        )
        assert events[0].tl_type == "correction"

    def test_bullish_trend_asc_break_is_impulse(self):
        """In bullish trend, ascending TL break = impulse break."""
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [], [1.30], 1)
        push_trendline_tick(state, 10, 1.36, 1.32, 1.34, [], [1.32, 1.30], 1)
        events = push_trendline_tick(
            state, 20, 1.35, 1.33, 1.33,
            [], [1.32, 1.30], 1, break_mode="close", tf="H1",
        )
        assert events[0].tl_type == "impulse"


# ---------------------------------------------------------------------------
# get_projected_prices
# ---------------------------------------------------------------------------

class TestGetProjectedPrices:
    def test_no_active_tl(self):
        state = PushTrendlineState()
        d, a = get_projected_prices(state, 10)
        assert math.isnan(d)
        assert math.isnan(a)

    def test_active_desc_tl(self):
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [1.35], [], 0)
        push_trendline_tick(state, 10, 1.32, 1.28, 1.30, [1.33, 1.35], [], 0)
        d, a = get_projected_prices(state, 20)
        assert d == pytest.approx(1.31)
        assert math.isnan(a)

    def test_broken_tl_returns_nan(self):
        state = PushTrendlineState()
        push_trendline_tick(state, 0, 1.34, 1.30, 1.32, [1.35], [], 0)
        push_trendline_tick(state, 10, 1.32, 1.28, 1.30, [1.33, 1.35], [], 0)
        # Break it
        push_trendline_tick(state, 20, 1.33, 1.29, 1.32,
                            [1.33, 1.35], [], 0, break_mode="close")
        d, a = get_projected_prices(state, 25)
        assert math.isnan(d)
