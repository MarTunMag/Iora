"""Tests for retest sweep runner."""
import pandas as pd
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep, SweepSummary, default_configs


def test_default_configs_not_empty():
    configs = default_configs()
    assert len(configs) > 0
    for cfg in configs:
        assert isinstance(cfg, RetestConfig)


def test_sweep_summary_ranking():
    s = SweepSummary(results=[])
    assert s.top_by_sqn(5) == []


def test_run_sweep_with_synthetic_data(small_engine_data):
    """Run sweep on tiny synthetic data — should complete without error."""
    configs = [RetestConfig(tf_pair="M5@H1", touch_type="any", bias_filter="any")]
    summary = run_retest_sweep(
        data_by_tf=small_engine_data,
        entry_tfs=["M5"],
        symbol="TEST",
        configs=configs,
    )
    assert isinstance(summary, SweepSummary)
