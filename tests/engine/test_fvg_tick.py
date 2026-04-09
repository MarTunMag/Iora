"""Tests for FVG (Fair Value Gap) detection engine."""
import pandas as pd
import pytest

from iora.engine.fvg_tick import FVGState, FVGEvent, fvg_tick, fvg_overlaps_zone


def _ts(i: int = 0) -> pd.Timestamp:
    return pd.Timestamp("2024-01-01") + pd.Timedelta(hours=i)


class TestFVGDetection:
    """Test FVG creation on 3-bar gap patterns."""

    def test_bullish_fvg_detected(self):
        """Bullish FVG: bar[2].high < bar[0].low."""
        state = FVGState()
        # Bar 0: high=1.10, low=1.09
        fvg_tick(state, 1.10, 1.09, 0, _ts(0), "H1")
        assert len(state.active_fvgs) == 0  # Need 3 bars

        # Bar 1: high=1.12, low=1.11 (gap building)
        fvg_tick(state, 1.12, 1.11, 1, _ts(1), "H1")
        assert len(state.active_fvgs) == 0

        # Bar 2: low=1.11, high=1.13 → prev2_high(1.10) < bar_low(1.11) = bullish FVG
        events = fvg_tick(state, 1.13, 1.11, 2, _ts(2), "H1")
        assert len(events) == 1
        assert events[0].direction == "bullish"
        assert events[0].top == 1.11  # bar[0].low
        assert events[0].bottom == 1.10  # bar[2].high

    def test_bearish_fvg_detected(self):
        """Bearish FVG: bar[2].low > bar[0].high."""
        state = FVGState()
        # Bar 0: high=1.12, low=1.11
        fvg_tick(state, 1.12, 1.11, 0, _ts(0), "H1")
        # Bar 1: high=1.10, low=1.09
        fvg_tick(state, 1.10, 1.09, 1, _ts(1), "H1")
        # Bar 2: high=1.08, low=1.07 → prev2_low(1.11) > bar_high(1.08) = bearish FVG
        events = fvg_tick(state, 1.08, 1.07, 2, _ts(2), "H1")
        assert len(events) == 1
        assert events[0].direction == "bearish"
        assert events[0].top == 1.11  # bar[2].low
        assert events[0].bottom == 1.08  # bar[0].high

    def test_no_fvg_when_no_gap(self):
        """No FVG when bars overlap."""
        state = FVGState()
        fvg_tick(state, 1.10, 1.09, 0, _ts(0), "H1")
        fvg_tick(state, 1.11, 1.095, 1, _ts(1), "H1")
        events = fvg_tick(state, 1.105, 1.095, 2, _ts(2), "H1")
        assert len(events) == 0


class TestFVGFill:
    """Test FVG fill (removal) logic."""

    def test_bullish_fvg_filled(self):
        """Bullish FVG filled when bar_low drops to FVG bottom."""
        state = FVGState()
        fvg_tick(state, 1.10, 1.09, 0, _ts(0), "H1")
        fvg_tick(state, 1.12, 1.11, 1, _ts(1), "H1")
        fvg_tick(state, 1.13, 1.11, 2, _ts(2), "H1")
        assert len(state.active_fvgs) == 1

        # Bar fills the gap (low drops to FVG bottom)
        fvg_tick(state, 1.12, 1.10, 3, _ts(3), "H1")
        assert len(state.active_fvgs) == 0  # Filled

    def test_bullish_fvg_not_filled_partial(self):
        """Bullish FVG NOT filled when bar only partially enters."""
        state = FVGState()
        fvg_tick(state, 1.10, 1.09, 0, _ts(0), "H1")
        fvg_tick(state, 1.12, 1.11, 1, _ts(1), "H1")
        fvg_tick(state, 1.13, 1.11, 2, _ts(2), "H1")
        assert len(state.active_fvgs) == 1

        # Bar only partially enters (low > FVG bottom)
        fvg_tick(state, 1.12, 1.105, 3, _ts(3), "H1")
        assert len(state.active_fvgs) == 1  # Still active


class TestFVGOverlap:
    """Test zone overlap helper."""

    def test_overlap_detected(self):
        fvg = FVGEvent(tf="H1", direction="bullish", top=1.11, bottom=1.10,
                       bar_idx=0, timestamp=_ts())
        assert fvg_overlaps_zone([fvg], 1.12, 1.105) is True

    def test_no_overlap(self):
        fvg = FVGEvent(tf="H1", direction="bullish", top=1.11, bottom=1.10,
                       bar_idx=0, timestamp=_ts())
        assert fvg_overlaps_zone([fvg], 1.15, 1.12) is False

    def test_empty_fvgs(self):
        assert fvg_overlaps_zone([], 1.12, 1.10) is False


class TestFVGCap:
    """Test MAX_ACTIVE cap."""

    def test_cap_enforced(self):
        state = FVGState()
        state.MAX_ACTIVE = 3
        # Create a gap pattern then shift window
        for i in range(20):
            # Alternate: big gap bars
            if i % 3 == 0:
                fvg_tick(state, 2.0 + i * 0.1, 1.0, i, _ts(i), "H1")
            elif i % 3 == 1:
                fvg_tick(state, 3.0 + i * 0.1, 2.5 + i * 0.1, i, _ts(i), "H1")
            else:
                fvg_tick(state, 4.0 + i * 0.1, 3.5 + i * 0.1, i, _ts(i), "H1")
        assert len(state.active_fvgs) <= 3
