"""Integration test: opportunity counter on real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.opportunity_runner import run_opportunity_counter, OpportunityResult


@pytest.fixture(scope="module")
def gbpusd_opp():
    """Run opportunity counter on real GBPUSD data (skip if unavailable)."""
    storage = ParquetStorage("data")
    tfs = ["M5", "H1", "H4", "D1", "W1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load("GBPUSD", tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
    if "M5" not in data_by_tf:
        pytest.skip("GBPUSD M5 data not available")
    return run_opportunity_counter(data_by_tf, base_tf="M5", symbol="GBPUSD")


class TestOpportunityRunner:
    def test_produces_result(self, gbpusd_opp):
        assert isinstance(gbpusd_opp, OpportunityResult)

    def test_has_events(self, gbpusd_opp):
        assert len(gbpusd_opp.events) > 100

    def test_events_have_tf_pairs(self, gbpusd_opp):
        tf_pairs = {e.tf_pair for e in gbpusd_opp.events}
        assert "M5@H1" in tf_pairs

    def test_touch_types_present(self, gbpusd_opp):
        types = {e.touch_type for e in gbpusd_opp.events}
        assert "wick_touch" in types

    def test_to_dataframe(self, gbpusd_opp):
        df = gbpusd_opp.to_dataframe()
        assert len(df) == len(gbpusd_opp.events)
        assert "tf_pair" in df.columns
        assert "touch_type" in df.columns

    def test_summary_per_tf_pair(self, gbpusd_opp):
        summary = gbpusd_opp.summary()
        assert len(summary) > 0
        first = list(summary.values())[0]
        assert "wick_touch" in first or "total" in first

    def test_opportunity_matrix(self, gbpusd_opp):
        matrix = gbpusd_opp.opportunity_matrix()
        assert len(matrix) > 0
        assert "count" in matrix.columns
        assert "tf_pair" in matrix.columns
