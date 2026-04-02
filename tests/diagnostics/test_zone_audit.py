import pandas as pd
import pytest
from iora.engine.push_zone_models import PushZone
from iora.diagnostics.zone_audit import ZoneAuditReport, ZoneLifecycleRecord, compute_audit


def test_audit_report_from_zones():
    """compute_audit produces correct statistics from zone records."""
    records = [
        ZoneLifecycleRecord(
            tf="M5", side="supply", origin_time=pd.Timestamp("2025-01-01"),
            break_time=pd.Timestamp("2025-01-05"), test_count=3,
            first_test_time=pd.Timestamp("2025-01-02"),
            replacement_count=1, lifespan_bars=100,
            birth_period_pattern="HH_HL", birth_price_distance=0.001,
        ),
        ZoneLifecycleRecord(
            tf="M5", side="supply", origin_time=pd.Timestamp("2025-01-03"),
            break_time=pd.Timestamp("2025-01-04"), test_count=0,
            first_test_time=None,
            replacement_count=0, lifespan_bars=50,
            birth_period_pattern="LH_LL", birth_price_distance=0.002,
        ),
    ]
    report = compute_audit(records, tf="M5", side="supply")
    assert report.zones_created == 2
    assert report.zones_broken == 2
    assert report.zones_untouched == 1  # second zone had test_count=0
    assert report.zones_retested == 1
    assert report.avg_tests_before_break == pytest.approx(1.5)  # (3 + 0) / 2


def test_audit_report_empty():
    """Empty records produce zero-filled report."""
    report = compute_audit([], tf="M5", side="supply")
    assert report.zones_created == 0
    assert report.avg_tests_before_break == 0.0


def test_lifecycle_record_dataclass():
    """ZoneLifecycleRecord holds correct fields."""
    rec = ZoneLifecycleRecord(
        tf="H1", side="demand", origin_time=pd.Timestamp("2025-01-01"),
        break_time=None, test_count=5,
        first_test_time=pd.Timestamp("2025-01-02"),
        replacement_count=2, lifespan_bars=500,
        birth_period_pattern="HH_HL", birth_price_distance=0.003,
    )
    assert rec.break_time is None  # Still alive
    assert rec.test_count == 5
