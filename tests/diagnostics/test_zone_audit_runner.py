"""Integration test: zone audit runner on real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.zone_audit_runner import run_zone_audit, ZoneAuditResult


@pytest.fixture(scope="module")
def gbpusd_audit():
    """Run audit on real GBPUSD data (skip if unavailable)."""
    storage = ParquetStorage("data")
    tfs = ["M5", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load("GBPUSD", tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
    if "M5" not in data_by_tf:
        pytest.skip("GBPUSD M5 data not available")
    return run_zone_audit(data_by_tf, base_tf="M5")


class TestZoneAuditRunner:
    def test_produces_result(self, gbpusd_audit):
        """Audit produces a ZoneAuditResult."""
        assert isinstance(gbpusd_audit, ZoneAuditResult)

    def test_has_reports_per_tf(self, gbpusd_audit):
        """Reports exist for each TF that was processed."""
        assert len(gbpusd_audit.reports) > 0
        tfs_present = {r.tf for r in gbpusd_audit.reports}
        assert "M5" in tfs_present

    def test_has_lifecycle_records(self, gbpusd_audit):
        """Lifecycle records captured for individual zones."""
        assert len(gbpusd_audit.lifecycle_records) > 0

    def test_zones_created_positive(self, gbpusd_audit):
        """Zone engine created zones across the data range."""
        total = sum(r.zones_created for r in gbpusd_audit.reports)
        assert total > 100

    def test_population_snapshots(self, gbpusd_audit):
        """Per-bar population snapshots recorded."""
        assert len(gbpusd_audit.population_snapshots) > 0
        snap = gbpusd_audit.population_snapshots[0]
        assert "tf" in snap
        assert "count" in snap
