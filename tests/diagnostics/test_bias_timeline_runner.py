"""Integration test: bias timeline runner on real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.bias_timeline_runner import run_bias_timeline, BiasTimelineResult


@pytest.fixture(scope="module")
def gbpusd_timeline():
    """Run bias timeline on real GBPUSD data (skip if unavailable)."""
    storage = ParquetStorage("data")
    tfs = ["M5", "H1", "H4", "D1", "W1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load("GBPUSD", tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
    if "M5" not in data_by_tf:
        pytest.skip("GBPUSD M5 data not available")
    return run_bias_timeline(data_by_tf, base_tf="M5", symbol="GBPUSD")


class TestBiasTimelineRunner:
    def test_produces_result(self, gbpusd_timeline):
        assert isinstance(gbpusd_timeline, BiasTimelineResult)

    def test_has_records(self, gbpusd_timeline):
        assert len(gbpusd_timeline.records) > 1000

    def test_records_have_timestamps(self, gbpusd_timeline):
        rec = gbpusd_timeline.records[500]
        assert rec.timestamp is not None

    def test_bias_not_all_unknown(self, gbpusd_timeline):
        """After warm-up, daily bias should be computed."""
        known = [r for r in gbpusd_timeline.records if r.d_bias != "unknown"]
        assert len(known) > 0

    def test_transitions_detected(self, gbpusd_timeline):
        """At least some bias transitions should occur over 21 months."""
        transitions = [r for r in gbpusd_timeline.records if r.is_bias_transition]
        assert len(transitions) > 0

    def test_to_dataframe(self, gbpusd_timeline):
        df = gbpusd_timeline.to_dataframe()
        assert len(df) == len(gbpusd_timeline.records)
        assert "d_bias" in df.columns
        assert "timestamp" in df.columns

    def test_summary_has_counts(self, gbpusd_timeline):
        summary = gbpusd_timeline.summary()
        assert "total_bars" in summary
        assert "transition_count" in summary
        assert summary["total_bars"] > 0
