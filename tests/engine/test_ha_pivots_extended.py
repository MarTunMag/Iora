# tests/engine/test_ha_pivots_extended.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.engine.ha_pivots import compute_pivot_events


def _make_ohlc(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Create OHLC DataFrame from (open, high, low, close) tuples."""
    idx = pd.date_range("2026-01-01", periods=len(bars), freq="h")
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)


class TestSeqHHLL:
    def test_seq_hh_column_exists(self):
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.03, 1.00, 1.02),  # blue
            (1.02, 1.03, 0.98, 0.99),  # red (supply fire)
            (0.99, 1.01, 0.97, 1.00),  # blue (demand fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert "seq_hh" in ev.columns
        assert "seq_ll" in ev.columns

    def test_seq_hh_captures_run_extreme(self):
        """Supply fire should set seq_hh to the highest OHLC high of the blue run."""
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.05, 1.00, 1.04),  # blue, highest high = 1.05
            (1.04, 1.04, 0.98, 0.99),  # red (supply fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert ev["hi_fire"].iloc[2] is True or ev["hi_fire"].iloc[2] == True
        assert ev["seq_hh"].iloc[2] == pytest.approx(1.05)

    def test_seq_ll_captures_run_extreme(self):
        """Demand fire should set seq_ll to the lowest OHLC low of the red run."""
        bars = [
            (1.00, 1.10, 0.99, 1.09),  # HA blue
            (1.09, 1.10, 0.80, 0.81),  # HA red
            (0.81, 0.82, 0.70, 0.71),  # HA red, lowest low = 0.70
            (0.71, 1.10, 0.69, 1.09),  # HA blue (demand fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        fire_rows = ev[ev["lo_fire"] == True]
        assert len(fire_rows) >= 1
        assert fire_rows["seq_ll"].iloc[0] == pytest.approx(0.70)

    def test_seq_values_nan_when_no_fire(self):
        """Non-fire bars should have NaN for seq_hh/seq_ll."""
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.03, 1.00, 1.02),  # blue
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert np.isnan(ev["seq_hh"].iloc[0])
        assert np.isnan(ev["seq_ll"].iloc[0])

    def test_hi_txt_hh_vs_lh(self):
        """hi_txt should be 'HH' when new high exceeds previous, 'LH' otherwise."""
        bars = [
            (1.00, 1.10, 0.99, 1.09),  # HA blue
            (1.09, 1.15, 1.08, 1.14),  # HA blue, high=1.15
            (1.14, 1.15, 1.08, 1.14),  # HA blue
            (1.14, 1.15, 0.80, 0.81),  # HA red (1st supply fire, hi=1.15 -> HH)
            (0.81, 0.82, 0.70, 0.71),  # HA red
            (0.71, 1.05, 0.70, 1.04),  # HA blue
            (1.04, 1.10, 1.03, 1.09),  # HA blue, high=1.10
            (1.09, 1.10, 0.80, 0.81),  # HA red (2nd supply fire, hi=1.10 < 1.15 -> LH)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert "hi_txt" in ev.columns
        fires = ev[ev["hi_fire"] == True]
        assert len(fires) == 2
        assert fires["hi_txt"].iloc[0] == "HH"  # first ever = HH
        assert fires["hi_txt"].iloc[1] == "LH"  # 1.10 < 1.15

    def test_lo_txt_ll_vs_hl(self):
        """lo_txt should be 'LL' when new low is below previous, 'HL' otherwise."""
        bars = [
            (1.00, 1.01, 0.80, 0.81),  # HA red
            (0.81, 0.82, 0.70, 0.71),  # HA red, low=0.70
            (0.71, 1.10, 0.69, 1.09),  # HA blue (1st demand fire, lo=0.70 -> LL)
            (1.09, 1.10, 1.08, 1.09),  # HA blue
            (1.09, 1.10, 0.85, 0.86),  # HA red
            (0.86, 0.87, 0.75, 0.76),  # HA red, low=0.75
            (0.76, 1.10, 0.74, 1.09),  # HA blue (2nd demand fire, lo=0.75 > 0.70 -> HL)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        fires = ev[ev["lo_fire"] == True]
        assert len(fires) == 2
        assert fires["lo_txt"].iloc[0] == "LL"  # first ever = LL
        assert fires["lo_txt"].iloc[1] == "HL"  # 0.75 > 0.70
