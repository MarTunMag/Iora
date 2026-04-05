"""Tests for HMA indicator module."""
import numpy as np
import pandas as pd

from iora.indicators.hma import (
    compute_wma,
    compute_hma,
    compute_hma_direction,
    compute_ha_hma_cross,
    compute_bars_since_cross,
)


class TestWMA:
    def test_wma_basic(self):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        wma = compute_wma(series, 3)
        # WMA(3) weights: [1,2,3], sum=6
        # At index 2: (1*1 + 2*2 + 3*3) / 6 = 14/6 ≈ 2.333
        assert abs(wma.iloc[2] - 14.0 / 6.0) < 1e-6
        # At index 3: (1*2 + 2*3 + 3*4) / 6 = 20/6 ≈ 3.333
        assert abs(wma.iloc[3] - 20.0 / 6.0) < 1e-6

    def test_wma_nan_before_period(self):
        series = pd.Series([1.0, 2.0, 3.0])
        wma = compute_wma(series, 3)
        assert pd.isna(wma.iloc[0])
        assert pd.isna(wma.iloc[1])
        assert not pd.isna(wma.iloc[2])


class TestHMA:
    def test_hma_produces_values(self):
        np.random.seed(42)
        series = pd.Series(np.cumsum(np.random.randn(100)) + 100)
        hma = compute_hma(series, 24)
        # HMA should have valid values after warmup
        valid = hma.dropna()
        assert len(valid) > 50

    def test_hma_follows_trend(self):
        # Strong uptrend — HMA should be rising
        series = pd.Series(np.linspace(100, 120, 60))
        hma = compute_hma(series, 12)
        valid = hma.dropna()
        # Last 10 values should be monotonically increasing
        tail = valid.iloc[-10:]
        diffs = tail.diff().iloc[1:]
        assert (diffs > 0).all()


class TestHMADirection:
    def test_rising_trend(self):
        series = pd.Series(np.linspace(100, 120, 60))
        hma = compute_hma(series, 12)
        atr = pd.Series(np.full(60, 0.5))
        direction = compute_hma_direction(hma, atr)
        # Last values should be +1 (rising)
        assert direction.iloc[-1] == 1

    def test_falling_trend(self):
        series = pd.Series(np.linspace(120, 100, 60))
        hma = compute_hma(series, 12)
        atr = pd.Series(np.full(60, 0.5))
        direction = compute_hma_direction(hma, atr)
        assert direction.iloc[-1] == -1

    def test_flat_detection(self):
        # Flat series — direction should be 0
        series = pd.Series(np.full(60, 100.0) + np.random.randn(60) * 0.001)
        hma = compute_hma(series, 12)
        atr = pd.Series(np.full(60, 1.0))
        direction = compute_hma_direction(hma, atr, flat_threshold=0.05)
        # Most values should be 0 (flat)
        assert (direction.iloc[-10:] == 0).sum() >= 5


class TestHACross:
    def test_bullish_cross(self):
        # HA starts below HMA, then crosses above
        ha_close = pd.Series([98, 99, 100, 101, 102, 103])
        hma = pd.Series([101, 101, 101, 100, 100, 100])
        ha_above, cross_dir = compute_ha_hma_cross(ha_close, hma)
        # Cross happens at index 3 (98<101, 99<101, 100<101, 101>100)
        assert ha_above.iloc[3] is True or ha_above.iloc[3] == True
        assert cross_dir.iloc[3] == 1  # bullish

    def test_bearish_cross(self):
        ha_close = pd.Series([103, 102, 101, 100, 99, 98])
        hma = pd.Series([100, 100, 100, 101, 101, 101])
        ha_above, cross_dir = compute_ha_hma_cross(ha_close, hma)
        # Find where it crosses below
        last_dir = cross_dir.iloc[-1]
        assert last_dir == -1  # bearish

    def test_cross_direction_persists(self):
        ha_close = pd.Series([98, 99, 102, 103, 104, 105])
        hma = pd.Series([101, 101, 101, 101, 101, 101])
        ha_above, cross_dir = compute_ha_hma_cross(ha_close, hma)
        # After bullish cross, direction should persist
        cross_idx = ha_above[ha_above].index[0]
        assert (cross_dir.iloc[cross_idx:] == 1).all()


class TestBarsSinceCross:
    def test_basic_counting(self):
        cross_raw = pd.Series([0, 0, 1, 0, 0, -1, 0, 0])
        bsc = compute_bars_since_cross(cross_raw)
        assert bsc.iloc[0] == 9999  # before first cross
        assert bsc.iloc[1] == 9999
        assert bsc.iloc[2] == 0  # at cross
        assert bsc.iloc[3] == 1  # 1 bar after
        assert bsc.iloc[4] == 2  # 2 bars after
        assert bsc.iloc[5] == 0  # new cross
        assert bsc.iloc[6] == 1

    def test_no_cross(self):
        cross_raw = pd.Series([0, 0, 0, 0])
        bsc = compute_bars_since_cross(cross_raw)
        assert (bsc == 9999).all()
