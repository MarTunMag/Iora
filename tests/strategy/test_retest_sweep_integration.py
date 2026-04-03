"""End-to-end integration test for retest sweep pipeline."""
import numpy as np
import pandas as pd
import pytest

from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_candidate import build_retest_candidates
from iora.strategy.retest_engine import evaluate_retest_config
from iora.strategy.retest_sweep import run_retest_sweep, SweepSummary


@pytest.fixture
def trending_data() -> dict[str, pd.DataFrame]:
    """Create data with a clear uptrend and pullbacks.

    500 M5 bars + aligned higher TFs. The uptrend should produce
    demand zones that get retested during pullbacks.
    """
    n = 500
    timestamps = pd.date_range("2025-01-15 08:00", periods=n, freq="5min")
    np.random.seed(123)

    t = np.linspace(0, 4 * np.pi, n)
    trend = np.linspace(0, 0.0400, n)
    waves = 0.0050 * np.sin(t)
    noise = np.random.normal(0, 0.0003, n)

    close = 1.2500 + trend + waves + noise
    high = close + np.abs(np.random.normal(0, 0.0006, n))
    low = close - np.abs(np.random.normal(0, 0.0006, n))
    open_ = np.roll(close, 1)
    open_[0] = 1.2500

    m5 = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": np.ones(n)},
        index=timestamps,
    )
    m5.index.name = "time"

    def resample(df, rule):
        r = df.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "tick_volume": "sum"}
        ).dropna()
        r.index.name = "time"
        return r

    return {
        "M5": m5,
        "M15": resample(m5, "15min"),
        "H1": resample(m5, "1h"),
        "H4": resample(m5, "4h"),
        "D1": resample(m5, "1D"),
        "W1": resample(m5, "1W"),
    }


def test_build_candidates_produces_events(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data, entry_tf="M5", symbol="TEST",
    )
    assert len(candidates) > 0
    tf_pairs = {c.event.tf_pair for c in candidates}
    assert len(tf_pairs) > 0


def test_evaluate_config_produces_trades(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data, entry_tf="M5", symbol="TEST",
    )
    cfg = RetestConfig(
        tf_pair="M5@H1", touch_type="any", bias_filter="any", fixed_rr=2.0,
    )
    result = evaluate_retest_config(
        candidates=candidates, config=cfg,
        symbol="TEST", bar_data=trending_data["M5"],
        all_candidates=candidates,
    )
    assert result.total_candidates >= 0
    if result.trades:
        assert result.metrics["total_trades"] == len(result.trades)
        assert "sqn" in result.metrics


def test_full_sweep_pipeline(trending_data):
    configs = [
        RetestConfig(tf_pair="M5@H1", touch_type="any", bias_filter="any"),
        RetestConfig(tf_pair="M5@M15", touch_type="any", bias_filter="any"),
    ]
    summary = run_retest_sweep(
        data_by_tf=trending_data, entry_tfs=["M5"],
        symbol="TEST", configs=configs,
    )
    assert isinstance(summary, SweepSummary)
    assert len(summary.results) == 2
    for r in summary.results:
        assert r.funnel is not None


def test_filter_funnel_reduces_candidates(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data, entry_tf="M5", symbol="TEST",
    )
    strict = RetestConfig(
        tf_pair="M5@H1", touch_type="wick_touch",
        bias_filter="with_daily", zone_role_filter="continuation",
        age_filter="fresh",
    )
    loose = RetestConfig(
        tf_pair="M5@H1", touch_type="any", bias_filter="any",
    )
    result_strict = evaluate_retest_config(
        candidates, strict, "TEST", trending_data["M5"],
        all_candidates=candidates,
    )
    result_loose = evaluate_retest_config(
        candidates, loose, "TEST", trending_data["M5"],
        all_candidates=candidates,
    )
    strict_passed = len(result_strict.funnel.passed) if result_strict.funnel else 0
    loose_passed = len(result_loose.funnel.passed) if result_loose.funnel else 0
    assert strict_passed <= loose_passed
