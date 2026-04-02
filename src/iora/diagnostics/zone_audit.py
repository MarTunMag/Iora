"""Zone Activity Audit — Level 1 diagnostics.

Computes zone population statistics from lifecycle records.
No strategy logic — purely descriptive.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class ZoneLifecycleRecord:
    """One zone's full lifecycle from creation to break (or still alive)."""
    tf: str
    side: str  # "supply" or "demand"
    origin_time: pd.Timestamp
    break_time: pd.Timestamp | None  # None if still alive
    test_count: int
    first_test_time: pd.Timestamp | None
    replacement_count: int
    lifespan_bars: int
    birth_period_pattern: str
    birth_price_distance: float


@dataclass(slots=True)
class ZoneAuditReport:
    """Aggregate statistics for one TF + side combination."""
    tf: str
    side: str
    zones_created: int
    zones_broken: int
    zones_untouched: int
    zones_retested: int
    avg_tests_before_break: float
    avg_bars_to_first_test: float
    avg_zones_alive: float
    max_zones_alive: int
    replacement_survival: dict  # {1: pct, 2: pct, "3+": pct}

    def to_dict(self) -> dict:
        return {
            "tf": self.tf, "side": self.side,
            "zones_created": self.zones_created,
            "zones_broken": self.zones_broken,
            "zones_untouched": self.zones_untouched,
            "zones_retested": self.zones_retested,
            "avg_tests_before_break": self.avg_tests_before_break,
            "avg_bars_to_first_test": self.avg_bars_to_first_test,
            "avg_zones_alive": self.avg_zones_alive,
            "max_zones_alive": self.max_zones_alive,
        }


def compute_audit(
    records: list[ZoneLifecycleRecord],
    tf: str,
    side: str,
) -> ZoneAuditReport:
    """Compute audit statistics from lifecycle records."""
    n = len(records)
    if n == 0:
        return ZoneAuditReport(
            tf=tf, side=side, zones_created=0, zones_broken=0,
            zones_untouched=0, zones_retested=0,
            avg_tests_before_break=0.0, avg_bars_to_first_test=0.0,
            avg_zones_alive=0.0, max_zones_alive=0,
            replacement_survival={},
        )

    broken = [r for r in records if r.break_time is not None]
    untouched = [r for r in records if r.test_count == 0]
    retested = [r for r in records if r.test_count > 0]

    avg_tests = sum(r.test_count for r in records) / n

    tested_records = [r for r in retested if r.first_test_time is not None]
    avg_bars_to_first = (
        sum(r.lifespan_bars for r in tested_records) / len(tested_records)
        if tested_records else 0.0
    )

    # Replacement survival: % of zones surviving N replacements
    survival: dict = {}
    for threshold in [1, 2]:
        survived = sum(1 for r in records if r.replacement_count >= threshold)
        survival[threshold] = survived / n if n > 0 else 0.0
    survived_3 = sum(1 for r in records if r.replacement_count >= 3)
    survival["3+"] = survived_3 / n if n > 0 else 0.0

    return ZoneAuditReport(
        tf=tf, side=side,
        zones_created=n,
        zones_broken=len(broken),
        zones_untouched=len(untouched),
        zones_retested=len(retested),
        avg_tests_before_break=avg_tests,
        avg_bars_to_first_test=avg_bars_to_first,
        avg_zones_alive=0.0,  # Computed by run_audit (needs per-bar tracking)
        max_zones_alive=0,    # Computed by run_audit
        replacement_survival=survival,
    )
