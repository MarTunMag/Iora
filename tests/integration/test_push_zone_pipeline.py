from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.orchestrator.pipeline import PipelineConfig, run_pipeline


def _make_trending_data(n_bars: int = 200) -> dict[str, pd.DataFrame]:
    """Generate synthetic H1 data with a clear uptrend then downtrend."""
    idx = pd.date_range("2026-01-01", periods=n_bars, freq="h")
    mid = n_bars // 2
    prices_up = 1.2000 + np.cumsum(np.random.RandomState(42).normal(0.0002, 0.001, mid))
    prices_dn = prices_up[-1] + np.cumsum(np.random.RandomState(43).normal(-0.0002, 0.001, n_bars - mid))
    prices = np.concatenate([prices_up, prices_dn])
    noise = np.random.RandomState(44).normal(0, 0.0005, n_bars)
    df = pd.DataFrame({
        "open": prices,
        "high": prices + abs(noise) + 0.001,
        "low": prices - abs(noise) - 0.001,
        "close": prices + noise,
    }, index=idx)
    return {"H1": df}


class TestPushZonePipeline:
    def test_push_zones_detected_in_trending_data(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True, macro_bias_on=False, cycle_on=False)
        output = run_pipeline(data, base_tf="H1", config=config)
        all_zones = []
        for tf, zones in output.push_zones_by_tf.items():
            all_zones.extend(zones)
        assert len(all_zones) > 0, "Expected push zones in trending data"

    def test_push_zones_off_by_default(self):
        data = _make_trending_data(200)
        config = PipelineConfig(macro_bias_on=False, cycle_on=False)
        output = run_pipeline(data, base_tf="H1", config=config)
        assert output.push_zones_by_tf == {}

    def test_trend_state_populated(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True, macro_bias_on=False, cycle_on=False)
        output = run_pipeline(data, base_tf="H1", config=config)
        assert "H1" in output.push_trend_by_tf

    def test_period_levels_populated(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True, macro_bias_on=False, cycle_on=False)
        output = run_pipeline(data, base_tf="H1", config=config)
        assert "H1" in output.period_levels_by_tf
        levels = output.period_levels_by_tf["H1"]
        assert "highs" in levels
        assert "lows" in levels
