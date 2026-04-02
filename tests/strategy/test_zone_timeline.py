# tests/strategy/test_zone_timeline.py
"""Tests for ZoneTimeline builder."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.strategy.zone_timeline import ZoneTimelineBar, build_zone_timeline
from iora.engine.push_zone_models import PushZone


def _make_ohlc(n: int = 100, base: float = 1.30) -> pd.DataFrame:
    """Generate synthetic OHLC data."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="5min")
    close = base + np.cumsum(rng.normal(0, 0.0005, n))
    high = close + rng.uniform(0, 0.001, n)
    low = close - rng.uniform(0, 0.001, n)
    open_ = close + rng.normal(0, 0.0003, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=dates,
    )


class TestZoneTimelineBar:
    def test_dataclass_fields(self):
        bar = ZoneTimelineBar(
            timestamp=pd.Timestamp("2025-01-01"),
            open_=1.30, high=1.31, low=1.29, close=1.305,
            fires=[], breaks=[],
            zones_by_tf={}, trend_by_tf={},
            period_levels_by_tf={},
            zone_counts_by_tf={},
        )
        assert bar.timestamp == pd.Timestamp("2025-01-01")
        assert bar.fires == []
        assert bar.trend_by_tf == {}


class TestBuildZoneTimeline:
    def test_returns_list_of_bars(self):
        """build_zone_timeline returns one ZoneTimelineBar per base TF bar."""
        m5 = _make_ohlc(200)
        h1 = m5.resample("1h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        ).dropna()
        data_by_tf = {"M5": m5, "H1": h1}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        assert len(timeline) == len(m5)
        assert all(isinstance(b, ZoneTimelineBar) for b in timeline)

    def test_bar_ohlc_matches_source(self):
        """OHLC in timeline bars matches source data."""
        m5 = _make_ohlc(50)
        data_by_tf = {"M5": m5}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        assert timeline[0].open_ == pytest.approx(m5.iloc[0]["open"])
        assert timeline[0].close == pytest.approx(m5.iloc[0]["close"])

    def test_timeline_captures_trend(self):
        """Trend state is captured per bar (may be 0 initially)."""
        m5 = _make_ohlc(200)
        data_by_tf = {"M5": m5}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        # At least some bars should have trend captured
        assert all("M5" in b.trend_by_tf for b in timeline)
