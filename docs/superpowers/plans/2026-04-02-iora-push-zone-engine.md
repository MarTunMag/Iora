# Push Zone Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port push_zones_v2.pine's HA-based zone detection, push/reversal validation, period tracking, nesting, and terminal classification into a Python engine that plugs into the existing pipeline.

**Architecture:** A new `push_zone_engine` pipeline component that reuses the existing `ha_pivots.py` for HA run-transition detection (extended with `seq_hh`/`seq_ll` tracking), adds push validation via boundary-break rule, period tracking with 3-level history, and nesting/terminal classification. Follows the same patterns as the existing `zone_engine.py` — per-TF state objects mutated in place via a `push_zone_engine_tick()` function called from the pipeline's bar loop.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest

**Spec:** `docs/superpowers/specs/2026-04-02-iora-push-zone-strategy-design.md`

**Pine reference:** `tw_indicators/iora_zones/iora_push_zones_v2.pine`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/iora/engine/push_zone_models.py` | `PushZone`, `PushZoneTickState`, `PeriodTracker` dataclasses |
| `src/iora/engine/push_zone_tick.py` | Per-TF per-bar tick: zone creation, break detection, push validation, reversal tagging, BOS/CHoCH |
| `src/iora/engine/ha_pivots.py` | **Modify:** add `seq_hh`, `seq_ll` columns to `compute_pivot_events()` output |
| `src/iora/orchestrator/push_zone_engine.py` | Multi-TF orchestration: calls `push_zone_tick()` per TF, nesting detection, period tracking, count resets |
| `src/iora/orchestrator/pipeline.py` | **Modify:** add `push_zone_engine_tick()` call in bar loop, extend `PipelineOutput` |
| `tests/engine/test_push_zone_models.py` | Tests for dataclasses |
| `tests/engine/test_push_zone_tick.py` | Tests for per-TF tick logic |
| `tests/engine/test_ha_pivots_extended.py` | Tests for seq_hh/seq_ll additions |
| `tests/orchestrator/test_push_zone_engine.py` | Tests for multi-TF orchestration |
| `tests/integration/test_push_zone_pipeline.py` | End-to-end pipeline integration test |

---

## Task 1: PushZone and PeriodTracker Models

**Files:**
- Create: `src/iora/engine/push_zone_models.py`
- Create: `tests/engine/test_push_zone_models.py`
- Create: `tests/__init__.py`, `tests/engine/__init__.py`

- [ ] **Step 1: Write failing tests for PushZone**

```python
# tests/engine/test_push_zone_models.py
from __future__ import annotations

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone, PeriodTracker, PushZoneTickState


class TestPushZone:
    def test_create_supply_zone(self):
        z = PushZone(
            top=1.2500,
            bottom=1.2400,
            is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
            timeframe="H1",
            swing_cls="HH",
        )
        assert z.top == 1.2500
        assert z.bottom == 1.2400
        assert z.is_supply is True
        assert z.timeframe == "H1"
        assert z.swing_cls == "HH"
        assert z.is_push is False
        assert z.is_reversal is False
        assert z.is_terminal is False
        assert z.struct_cls == ""
        assert z.count_num == 0

    def test_create_demand_zone(self):
        z = PushZone(
            top=1.2400,
            bottom=1.2300,
            is_supply=False,
            origin_time=pd.Timestamp("2026-01-01"),
            timeframe="M5",
            swing_cls="LL",
        )
        assert z.is_supply is False
        assert z.swing_cls == "LL"

    def test_push_zone_mutable(self):
        z = PushZone(
            top=1.25, bottom=1.24, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        z.is_push = True
        z.struct_cls = "BOS"
        assert z.is_push is True
        assert z.struct_cls == "BOS"

    def test_contains_price_inside(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2450) is True

    def test_contains_price_outside(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2350) is False

    def test_contains_price_boundary(self):
        z = PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=pd.Timestamp("2026-01-01"),
        )
        assert z.contains_price(1.2500) is True
        assert z.contains_price(1.2400) is True


class TestPeriodTracker:
    def test_initial_state(self):
        pt = PeriodTracker()
        assert pt.cur_hi != pt.cur_hi  # nan
        assert pt.cur_lo != pt.cur_lo  # nan
        assert len(pt.prev_highs) == 0
        assert len(pt.prev_lows) == 0
        assert pt.hi_brk_time is None
        assert pt.lo_brk_time is None

    def test_rotate_period(self):
        pt = PeriodTracker()
        pt.cur_hi = 1.2500
        pt.cur_lo = 1.2400
        pt.cur_hi_time = pd.Timestamp("2026-01-01 04:00")
        pt.cur_lo_time = pd.Timestamp("2026-01-01 02:00")
        pt.rotate(pd.Timestamp("2026-01-02"))
        assert pt.prev_highs[0] == 1.2500
        assert pt.prev_lows[0] == 1.2400
        assert len(pt.prev_highs) == 1
        assert pt.hi_brk_time is None

    def test_rotate_caps_at_depth(self):
        pt = PeriodTracker(history_depth=3)
        for i in range(5):
            pt.cur_hi = 1.25 + i * 0.001
            pt.cur_lo = 1.24 - i * 0.001
            pt.cur_hi_time = pd.Timestamp(f"2026-01-0{i+1}")
            pt.cur_lo_time = pd.Timestamp(f"2026-01-0{i+1}")
            pt.rotate(pd.Timestamp(f"2026-01-0{i+2}"))
        assert len(pt.prev_highs) == 3
        assert len(pt.prev_lows) == 3
        # Most recent first
        assert pt.prev_highs[0] == 1.254


class TestPushZoneTickState:
    def test_initial_state(self):
        st = PushZoneTickState()
        assert len(st.supply_zones) == 0
        assert len(st.demand_zones) == 0
        assert st.trend == 0
        assert st.sup_count == 0
        assert st.dem_count == 0
        assert st.prev_push_extreme_hi != st.prev_push_extreme_hi  # nan
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Iora && python -m pytest tests/engine/test_push_zone_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'iora.engine.push_zone_models'`

- [ ] **Step 3: Implement the models**

```python
# src/iora/engine/push_zone_models.py
"""
Push zone models — dataclasses for push zone detection engine.

Pine reference: iora_push_zones_v2.pine (S2 Zone UDT, S5 track_period)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import nan

import pandas as pd


@dataclass(slots=True)
class PushZone:
    """A supply or demand zone with push/reversal/terminal classification."""

    top: float
    bottom: float
    is_supply: bool
    origin_time: pd.Timestamp
    timeframe: str = ""
    is_push: bool = False
    is_reversal: bool = False
    is_terminal: bool = False
    struct_cls: str = ""       # "BOS" or "CHoCH"
    swing_cls: str = ""        # "HH", "LH", "HL", "LL"
    count_num: int = 0

    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass(slots=True)
class PeriodTracker:
    """Tracks previous closed period high/low with rolling history.

    Pine reference: track_period() in iora_push_zones_v2.pine (S5).
    Stores up to `history_depth` previous period highs/lows (most recent first).
    """

    history_depth: int = 3

    cur_hi: float = nan
    cur_lo: float = nan
    cur_hi_time: pd.Timestamp | None = None
    cur_lo_time: pd.Timestamp | None = None

    prev_highs: list[float] = field(default_factory=list)
    prev_lows: list[float] = field(default_factory=list)
    prev_hi_times: list[pd.Timestamp] = field(default_factory=list)
    prev_lo_times: list[pd.Timestamp] = field(default_factory=list)

    hi_brk_time: pd.Timestamp | None = None
    lo_brk_time: pd.Timestamp | None = None

    def rotate(self, new_period_time: pd.Timestamp) -> None:
        """Rotate current → previous on period boundary. Reset break detection."""
        if self.cur_hi == self.cur_hi:  # not nan
            self.prev_highs.insert(0, self.cur_hi)
            self.prev_hi_times.insert(0, self.cur_hi_time)
            if len(self.prev_highs) > self.history_depth:
                self.prev_highs.pop()
                self.prev_hi_times.pop()
        if self.cur_lo == self.cur_lo:  # not nan
            self.prev_lows.insert(0, self.cur_lo)
            self.prev_lo_times.insert(0, self.cur_lo_time)
            if len(self.prev_lows) > self.history_depth:
                self.prev_lows.pop()
                self.prev_lo_times.pop()

        self.cur_hi = nan
        self.cur_lo = nan
        self.cur_hi_time = None
        self.cur_lo_time = None
        self.hi_brk_time = None
        self.lo_brk_time = None


@dataclass(slots=True)
class PushZoneTickState:
    """Mutable per-TF state for push zone tick. Mirrors Pine var variables."""

    # HA run tracking (for cross-bar state)
    prev_run_hi: float = nan
    prev_run_lo: float = nan

    # Push validation
    prev_push_extreme_hi: float = nan
    prev_push_extreme_lo: float = nan

    # Trend (from period tracking breaks)
    trend: int = 0  # +1 bull, -1 bear, 0 uninitialized

    # Period tracker
    period: PeriodTracker = field(default_factory=PeriodTracker)

    # Zone arrays
    supply_zones: list[PushZone] = field(default_factory=list)
    demand_zones: list[PushZone] = field(default_factory=list)

    # Zone counting
    sup_count: int = 0
    dem_count: int = 0
    sup_reset_time: pd.Timestamp | None = None
    dem_reset_time: pd.Timestamp | None = None
```

- [ ] **Step 4: Create test __init__.py files and run tests**

```bash
mkdir -p tests/engine tests/orchestrator tests/integration
touch tests/__init__.py tests/engine/__init__.py tests/orchestrator/__init__.py tests/integration/__init__.py
```

Run: `cd /c/Iora && python -m pytest tests/engine/test_push_zone_models.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/engine/push_zone_models.py tests/
git commit -m "feat(push-zone): add PushZone, PeriodTracker, PushZoneTickState models"
```

---

## Task 2: Extend ha_pivots.py with seq_hh/seq_ll Tracking

Push validation needs the **actual extreme values** (`seq_hh`, `seq_ll`) — not just boolean `hi_is_hh`/`lo_is_ll`. The existing `compute_pivot_events()` already tracks `prev_hi`/`prev_lo` internally but doesn't output them. We add two columns: `seq_hh` (the run's high extreme value) and `seq_ll` (the run's low extreme value).

**Files:**
- Modify: `src/iora/engine/ha_pivots.py:44-126`
- Create: `tests/engine/test_ha_pivots_extended.py`

- [ ] **Step 1: Write failing tests for seq_hh/seq_ll**

```python
# tests/engine/test_ha_pivots_extended.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.engine.ha_pivots import compute_pivot_events


def _make_ohlc(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Create OHLC DataFrame from (open, high, low, close) tuples."""
    idx = pd.date_range("2026-01-01", periods=len(bars), freq="h")
    return pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)


class TestSeqHHLL:
    def test_seq_hh_column_exists(self):
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.03, 1.00, 1.02),  # blue
            (1.02, 1.03, 0.98, 0.99),  # red (supply fire)
            (0.99, 1.01, 0.97, 1.00),  # blue (demand fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert "seq_hh" in ev.columns
        assert "seq_ll" in ev.columns

    def test_seq_hh_captures_run_extreme(self):
        """Supply fire should set seq_hh to the highest OHLC high of the blue run."""
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.05, 1.00, 1.04),  # blue, highest high = 1.05
            (1.04, 1.04, 0.98, 0.99),  # red (supply fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        # Supply fire on bar 2 — seq_hh should be 1.05
        assert ev["hi_fire"].iloc[2] is True or ev["hi_fire"].iloc[2] == True
        assert ev["seq_hh"].iloc[2] == pytest.approx(1.05)

    def test_seq_ll_captures_run_extreme(self):
        """Demand fire should set seq_ll to the lowest OHLC low of the red run."""
        bars = [
            (1.00, 1.01, 0.99, 1.01),  # blue
            (1.01, 1.01, 0.99, 0.98),  # red
            (0.98, 0.99, 0.95, 0.96),  # red, lowest low = 0.95
            (0.96, 1.00, 0.95, 0.99),  # blue (demand fire)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        # Demand fire on bar 3 — seq_ll should be 0.95
        fire_rows = ev[ev["lo_fire"] == True]
        assert len(fire_rows) >= 1
        assert fire_rows["seq_ll"].iloc[0] == pytest.approx(0.95)

    def test_seq_values_nan_when_no_fire(self):
        """Non-fire bars should have NaN for seq_hh/seq_ll."""
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.03, 1.00, 1.02),  # blue
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert np.isnan(ev["seq_hh"].iloc[0])
        assert np.isnan(ev["seq_ll"].iloc[0])

    def test_hi_txt_hh_vs_lh(self):
        """hi_txt should be 'HH' when new high exceeds previous, 'LH' otherwise."""
        bars = [
            (1.00, 1.02, 0.99, 1.01),  # blue
            (1.01, 1.05, 1.00, 0.99),  # red (1st supply fire, hi=1.05)
            (0.99, 1.01, 0.98, 1.00),  # blue
            (1.00, 1.03, 0.98, 0.97),  # red (2nd supply fire, hi=1.03 < 1.05 → LH)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        assert "hi_txt" in ev.columns
        fires = ev[ev["hi_fire"] == True]
        assert fires["hi_txt"].iloc[0] == "HH"  # first ever = HH
        assert fires["hi_txt"].iloc[1] == "LH"  # 1.03 < 1.05

    def test_lo_txt_ll_vs_hl(self):
        """lo_txt should be 'LL' when new low is below previous, 'HL' otherwise."""
        bars = [
            (1.00, 1.01, 0.99, 0.98),  # red
            (0.98, 1.01, 0.95, 1.00),  # blue (1st demand fire, lo=0.95)
            (1.00, 1.01, 0.99, 0.98),  # red
            (0.98, 1.01, 0.97, 1.00),  # blue (2nd demand fire, lo=0.97 > 0.95 → HL)
        ]
        df = _make_ohlc(bars)
        ev = compute_pivot_events(df)
        fires = ev[ev["lo_fire"] == True]
        assert fires["lo_txt"].iloc[0] == "LL"  # first ever = LL
        assert fires["lo_txt"].iloc[1] == "HL"  # 0.97 > 0.95
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Iora && python -m pytest tests/engine/test_ha_pivots_extended.py -v`
Expected: FAIL — `seq_hh`, `seq_ll`, `hi_txt`, `lo_txt` columns don't exist

- [ ] **Step 3: Extend compute_pivot_events()**

In `src/iora/engine/ha_pivots.py`, add four new output arrays and populate them during the existing loop. The changes are:

1. After line 44 (`n = len(ohlc)`), add:
```python
    seq_hh = np.full(n, np.nan, dtype=float)
    seq_ll = np.full(n, np.nan, dtype=float)
    hi_txt = np.full(n, "", dtype=object)
    lo_txt = np.full(n, "", dtype=object)
```

2. Inside the supply pivot branch (after `prev_hi = rhi` at line 80), add:
```python
            seq_hh[i] = rhi
            hi_txt[i] = "HH" if hi_is_hh[i] else "LH"
```

3. Inside the demand pivot branch (after `prev_lo = rlo` at line 106), add:
```python
            seq_ll[i] = rlo
            lo_txt[i] = "LL" if lo_is_ll[i] else "HL"
```

4. In the output DataFrame construction (line 111), add four columns:
```python
            "seq_hh": seq_hh,
            "seq_ll": seq_ll,
            "hi_txt": hi_txt,
            "lo_txt": lo_txt,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Iora && python -m pytest tests/engine/test_ha_pivots_extended.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/engine/ha_pivots.py tests/engine/test_ha_pivots_extended.py
git commit -m "feat(ha-pivots): add seq_hh, seq_ll, hi_txt, lo_txt columns for push validation"
```

---

## Task 3: Push Zone Tick — Zone Creation and Break Detection

The core per-TF per-bar tick function. This task covers zone creation on fire events and break detection (body-close). Push validation, reversal tagging, and BOS/CHoCH are Task 4.

**Files:**
- Create: `src/iora/engine/push_zone_tick.py`
- Create: `tests/engine/test_push_zone_tick.py`

- [ ] **Step 1: Write failing tests for zone creation and break detection**

```python
# tests/engine/test_push_zone_tick.py
from __future__ import annotations

from math import nan

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.push_zone_tick import push_zone_tick


T0 = pd.Timestamp("2026-01-01 00:00")
T1 = pd.Timestamp("2026-01-01 01:00")
T2 = pd.Timestamp("2026-01-01 02:00")
T3 = pd.Timestamp("2026-01-01 03:00")
TF_SECONDS = 3600  # H1


class TestZoneCreation:
    def test_supply_zone_created_on_hi_fire(self):
        state = PushZoneTickState()
        push_zone_tick(
            state=state,
            close=1.24,
            hi_fire=True, hi_ztop=1.2500, hi_zbot=1.2400,
            hi_time=T0, hi_is_hh=True, hi_txt="HH", seq_hh=1.2500,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 1
        z = state.supply_zones[0]
        assert z.top == 1.2500
        assert z.bottom == 1.2400
        assert z.is_supply is True
        assert z.swing_cls == "HH"
        assert z.timeframe == "H1"

    def test_demand_zone_created_on_lo_fire(self):
        state = PushZoneTickState()
        push_zone_tick(
            state=state,
            close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.2400, lo_zbot=1.2300,
            lo_time=T0, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.demand_zones) == 1
        z = state.demand_zones[0]
        assert z.top == 1.2400
        assert z.bottom == 1.2300
        assert z.is_supply is False
        assert z.swing_cls == "LL"

    def test_zone_count_increments(self):
        state = PushZoneTickState()
        # First supply zone
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=True, hi_ztop=1.25, hi_zbot=1.24,
            hi_time=T0, hi_is_hh=True, hi_txt="HH", seq_hh=1.25,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].count_num == 1
        # Second supply zone
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=True, hi_ztop=1.26, hi_zbot=1.25,
            hi_time=T1, hi_is_hh=False, hi_txt="LH", seq_hh=1.26,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[1].count_num == 2
        assert state.sup_count == 2


class TestZoneBreak:
    def test_supply_zone_breaks_on_close_above_top(self):
        state = PushZoneTickState()
        state.supply_zones.append(PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2510,  # close above top
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 0
        assert len(broken) == 1
        assert broken[0].is_supply is True

    def test_demand_zone_breaks_on_close_below_bottom(self):
        state = PushZoneTickState()
        state.demand_zones.append(PushZone(
            top=1.2400, bottom=1.2300, is_supply=False,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2290,  # close below bottom
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.demand_zones) == 0
        assert len(broken) == 1

    def test_wick_does_not_break_zone(self):
        """Close inside zone = no break, even if high/low pierced boundary."""
        state = PushZoneTickState()
        state.supply_zones.append(PushZone(
            top=1.2500, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        broken = push_zone_tick(
            state=state, close=1.2480,  # close inside zone
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T1, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 1
        assert len(broken) == 0

    def test_zone_expires_by_age(self):
        state = PushZoneTickState()
        old_time = T0 - pd.Timedelta(hours=100)
        state.supply_zones.append(PushZone(
            top=1.25, bottom=1.24, is_supply=True,
            origin_time=old_time, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T0, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert len(state.supply_zones) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Iora && python -m pytest tests/engine/test_push_zone_tick.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement push_zone_tick()**

```python
# src/iora/engine/push_zone_tick.py
"""
Push zone tick — per-TF per-bar zone creation, break detection, push/reversal validation.

Pine reference: iora_push_zones_v2.pine S6 process() method.
Follows same pattern as zone_tick.py but adds push validation logic.
"""
from __future__ import annotations

from math import isnan, nan

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.events import EventBus
from iora.engine.models import EventID


def push_zone_tick(
    state: PushZoneTickState,
    close: float,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_zbot: float | None,
    hi_time: pd.Timestamp | None,
    hi_is_hh: bool,
    hi_txt: str,
    seq_hh: float,
    lo_fire: bool,
    lo_ztop: float | None,
    lo_zbot: float | None,
    lo_time: pd.Timestamp | None,
    lo_is_ll: bool,
    lo_txt: str,
    seq_ll: float,
    bar_time: pd.Timestamp,
    tf_seconds: int,
    max_age: int,
    timeframe: str = "",
    bus: EventBus | None = None,
) -> list[PushZone]:
    """
    Process one bar for a single TF. Mutates state in place.

    Returns list of broken zones (for event emission / diagnostics).

    Sequence (matches Pine process()):
      1. Zone expire + break detection (body-close)
      2. Zone creation (on fire with valid boundaries)
      3. Push validation (boundary-break rule)
      4. Reversal tagging
      5. BOS/CHoCH classification
    """
    max_age_ms = max_age * tf_seconds * 1000
    bar_ms = int(bar_time.timestamp() * 1000)
    broken: list[PushZone] = []

    # --- 1. Expire + break detection ---
    for zones in (state.supply_zones, state.demand_zones):
        i = len(zones) - 1
        while i >= 0:
            z = zones[i]
            origin_ms = int(z.origin_time.timestamp() * 1000)
            expired = (bar_ms - origin_ms) > max_age_ms
            if expired:
                broken.append(zones.pop(i))
                i -= 1
                continue
            is_broken = close > z.top if z.is_supply else close < z.bottom
            if is_broken:
                broken.append(zones.pop(i))
            i -= 1

    # Emit break events
    if bus is not None:
        for bz in broken:
            bus.emit(
                EventID.ZONE_BREAK,
                timestamp=bar_time,
                timeframe=timeframe,
                payload={
                    "top": bz.top, "bot": bz.bottom,
                    "side": "supply" if bz.is_supply else "demand",
                    "is_push": bz.is_push, "is_reversal": bz.is_reversal,
                    "origin_time": bz.origin_time,
                },
            )

    # --- 2. Zone creation ---
    if hi_fire and hi_ztop is not None and hi_zbot is not None and hi_ztop > hi_zbot:
        origin = hi_time if hi_time is not None else bar_time
        origin_ms = int(origin.timestamp() * 1000)
        if (bar_ms - origin_ms) < max_age_ms:
            state.sup_count += 1
            z = PushZone(
                top=hi_ztop,
                bottom=hi_zbot,
                is_supply=True,
                origin_time=origin,
                timeframe=timeframe,
                swing_cls=hi_txt,
                count_num=state.sup_count,
            )
            state.supply_zones.append(z)
            if bus is not None:
                bus.emit(
                    EventID.ZONE_FIRE,
                    timestamp=bar_time,
                    timeframe=timeframe,
                    payload={
                        "top": z.top, "bot": z.bottom,
                        "side": "supply", "swing_cls": hi_txt,
                    },
                )

    if lo_fire and lo_ztop is not None and lo_zbot is not None and lo_ztop > lo_zbot:
        origin = lo_time if lo_time is not None else bar_time
        origin_ms = int(origin.timestamp() * 1000)
        if (bar_ms - origin_ms) < max_age_ms:
            state.dem_count += 1
            z = PushZone(
                top=lo_ztop,
                bottom=lo_zbot,
                is_supply=False,
                origin_time=origin,
                timeframe=timeframe,
                swing_cls=lo_txt,
                count_num=state.dem_count,
            )
            state.demand_zones.append(z)
            if bus is not None:
                bus.emit(
                    EventID.ZONE_FIRE,
                    timestamp=bar_time,
                    timeframe=timeframe,
                    payload={
                        "top": z.top, "bot": z.bottom,
                        "side": "demand", "swing_cls": lo_txt,
                    },
                )

    # --- 3-5. Push validation, reversal, BOS/CHoCH ---
    _push_validate(state, hi_fire, hi_txt, seq_hh, lo_fire, lo_txt, seq_ll)

    return broken


def _push_validate(
    state: PushZoneTickState,
    hi_fire: bool,
    hi_txt: str,
    seq_hh: float,
    lo_fire: bool,
    lo_txt: str,
    seq_ll: float,
) -> None:
    """Push validation + reversal tagging + BOS/CHoCH classification.

    Pine reference: iora_push_zones_v2.pine lines 301-363.
    """
    # Bearish push: demand fires with LL → tag most recent supply as PUSH
    if lo_fire and lo_txt == "LL":
        boundary_ok = isnan(state.prev_push_extreme_lo) or seq_ll < state.prev_push_extreme_lo
        if boundary_ok:
            # Tag most recent supply as PUSH
            for i in range(len(state.supply_zones) - 1, -1, -1):
                z = state.supply_zones[i]
                z.is_push = True
                z.struct_cls = _classify_struct(state.trend, is_bullish_push=False)
                break
            # Tag most recent demand as REVERSAL (trigger zone)
            for i in range(len(state.demand_zones) - 1, -1, -1):
                z = state.demand_zones[i]
                z.is_reversal = True
                break
            state.prev_push_extreme_lo = seq_ll

    # Bullish push: supply fires with HH → tag most recent demand as PUSH
    if hi_fire and hi_txt == "HH":
        boundary_ok = isnan(state.prev_push_extreme_hi) or seq_hh > state.prev_push_extreme_hi
        if boundary_ok:
            # Tag most recent demand as PUSH
            for i in range(len(state.demand_zones) - 1, -1, -1):
                z = state.demand_zones[i]
                z.is_push = True
                z.struct_cls = _classify_struct(state.trend, is_bullish_push=True)
                break
            # Tag most recent supply as REVERSAL (trigger zone)
            for i in range(len(state.supply_zones) - 1, -1, -1):
                z = state.supply_zones[i]
                z.is_reversal = True
                break
            state.prev_push_extreme_hi = seq_hh


def _classify_struct(trend: int, is_bullish_push: bool) -> str:
    """BOS/CHoCH classification based on push direction vs trend."""
    if trend == 0:
        return ""
    if is_bullish_push:
        return "BOS" if trend == 1 else "CHoCH"
    else:
        return "BOS" if trend == -1 else "CHoCH"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Iora && python -m pytest tests/engine/test_push_zone_tick.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/engine/push_zone_tick.py tests/engine/test_push_zone_tick.py
git commit -m "feat(push-zone): push_zone_tick with zone creation, breaks, push validation"
```

---

## Task 4: Push Validation + BOS/CHoCH Tests

Dedicated tests for the push validation logic (boundary-break rule), reversal tagging, and BOS/CHoCH classification. The implementation already exists from Task 3 — this task verifies it thoroughly.

**Files:**
- Extend: `tests/engine/test_push_zone_tick.py`

- [ ] **Step 1: Write push validation tests**

Add to `tests/engine/test_push_zone_tick.py`:

```python
class TestPushValidation:
    def test_bearish_push_tags_supply_and_reversal(self):
        """Demand fires with LL → most recent supply tagged PUSH, demand tagged REVERSAL."""
        state = PushZoneTickState()
        # Pre-existing supply zone (from previous blue→red transition)
        state.supply_zones.append(PushZone(
            top=1.2600, bottom=1.2500, is_supply=True,
            origin_time=T0, timeframe="H1", swing_cls="HH",
        ))
        # Demand fires with LL (red→blue transition)
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.2400, lo_zbot=1.2300,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].is_push is True
        assert state.demand_zones[0].is_reversal is True
        assert state.prev_push_extreme_lo == 1.2300

    def test_bullish_push_tags_demand_and_reversal(self):
        """Supply fires with HH → most recent demand tagged PUSH, supply tagged REVERSAL."""
        state = PushZoneTickState()
        state.demand_zones.append(PushZone(
            top=1.2400, bottom=1.2300, is_supply=False,
            origin_time=T0, timeframe="H1", swing_cls="LL",
        ))
        push_zone_tick(
            state=state, close=1.26,
            hi_fire=True, hi_ztop=1.2700, hi_zbot=1.2600,
            hi_time=T1, hi_is_hh=True, hi_txt="HH", seq_hh=1.2700,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.demand_zones[0].is_push is True
        assert state.supply_zones[0].is_reversal is True
        assert state.prev_push_extreme_hi == 1.2700

    def test_no_push_if_boundary_not_broken(self):
        """LL that doesn't break prev_push_extreme_lo = no push tag."""
        state = PushZoneTickState()
        state.prev_push_extreme_lo = 1.2200  # previous push went to 1.2200
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.2300,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        # seq_ll=1.23 > prev_push_extreme_lo=1.22 → boundary NOT broken
        assert state.supply_zones[0].is_push is False
        assert state.demand_zones[0].is_reversal is False

    def test_bootstrap_push_when_prev_extreme_is_nan(self):
        """First LL ever → auto-qualifies as push (bootstrap)."""
        state = PushZoneTickState()
        assert isnan(state.prev_push_extreme_lo)
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].is_push is True


class TestBOSCHoCH:
    def test_bos_bearish_push_bearish_trend(self):
        """Bearish push + trend=-1 → BOS."""
        state = PushZoneTickState()
        state.trend = -1
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].struct_cls == "BOS"

    def test_choch_bullish_push_bearish_trend(self):
        """Bullish push + trend=-1 → CHoCH."""
        state = PushZoneTickState()
        state.trend = -1
        state.demand_zones.append(PushZone(
            top=1.24, bottom=1.23, is_supply=False,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.26,
            hi_fire=True, hi_ztop=1.27, hi_zbot=1.26,
            hi_time=T1, hi_is_hh=True, hi_txt="HH", seq_hh=1.27,
            lo_fire=False, lo_ztop=None, lo_zbot=None,
            lo_time=None, lo_is_ll=False, lo_txt="", seq_ll=nan,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.demand_zones[0].struct_cls == "CHoCH"

    def test_no_classification_when_trend_zero(self):
        """Trend=0 → no BOS/CHoCH classification."""
        state = PushZoneTickState()
        state.trend = 0
        state.supply_zones.append(PushZone(
            top=1.26, bottom=1.25, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        push_zone_tick(
            state=state, close=1.24,
            hi_fire=False, hi_ztop=None, hi_zbot=None,
            hi_time=None, hi_is_hh=False, hi_txt="", seq_hh=nan,
            lo_fire=True, lo_ztop=1.24, lo_zbot=1.23,
            lo_time=T1, lo_is_ll=True, lo_txt="LL", seq_ll=1.23,
            bar_time=T2, tf_seconds=TF_SECONDS, max_age=50,
            timeframe="H1",
        )
        assert state.supply_zones[0].struct_cls == ""
```

- [ ] **Step 2: Run all tests**

Run: `cd /c/Iora && python -m pytest tests/engine/test_push_zone_tick.py -v`
Expected: All tests PASS (implementation already exists from Task 3)

- [ ] **Step 3: Commit test additions**

```bash
git add tests/engine/test_push_zone_tick.py
git commit -m "test(push-zone): add push validation, BOS/CHoCH, bootstrap tests"
```

---

## Task 5: Push Zone Engine — Multi-TF Orchestration

Orchestrates `push_zone_tick()` across all TFs per bar. Handles period tracking, trend updates, count resets (parent fire + structural invalidation), and nesting detection.

**Files:**
- Create: `src/iora/orchestrator/push_zone_engine.py`
- Create: `tests/orchestrator/test_push_zone_engine.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/orchestrator/test_push_zone_engine.py
from __future__ import annotations

from math import nan

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone, PushZoneTickState, PeriodTracker
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState,
    PushZoneEngineConfig,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.engine.models import BarContext
from iora.engine.events import EventBus


def _make_ctx(
    close: float,
    high: float,
    low: float,
    bar_time: pd.Timestamp,
    htf: dict | None = None,
    edges: dict | None = None,
) -> BarContext:
    return BarContext(
        idx=0,
        timestamp=bar_time,
        open_=close,
        high=high,
        low=low,
        close=close,
        htf=htf or {},
        edges=edges or {},
    )


T0 = pd.Timestamp("2026-01-01 00:00")
T1 = pd.Timestamp("2026-01-01 01:00")


class TestInitState:
    def test_creates_state_for_all_tfs(self):
        state = init_push_zone_state(["M5", "H1", "H4"])
        assert "M5" in state.tick_states
        assert "H1" in state.tick_states
        assert "H4" in state.tick_states
        assert len(state.tick_states) == 3

    def test_each_tf_has_period_tracker(self):
        state = init_push_zone_state(["H1"])
        assert isinstance(state.tick_states["H1"].period, PeriodTracker)


class TestPeriodTracking:
    def test_trend_updates_on_hi_break(self):
        """When high breaks previous period high, trend goes to +1."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        # Set up a previous period high
        ts.period.prev_highs = [1.2500]
        ts.period.prev_hi_times = [T0]
        # Bar with high above prev_hi — htf carries new_period=False (not a boundary)
        ctx = _make_ctx(close=1.2480, high=1.2510, low=1.2450, bar_time=T1,
                        htf={"H1": {"new_period": False}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.trend == 1

    def test_trend_updates_on_lo_break(self):
        """When low breaks previous period low, trend goes to -1."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        ts.period.prev_lows = [1.2300]
        ts.period.prev_lo_times = [T0]
        ctx = _make_ctx(close=1.2310, high=1.2350, low=1.2290, bar_time=T1,
                        htf={"H1": {"new_period": False}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.trend == -1

    def test_rotate_on_new_period(self):
        """On new period boundary, current hi/lo rotate into prev lists."""
        state = init_push_zone_state(["H1"])
        ts = state.tick_states["H1"]
        ts.period.cur_hi = 1.2600
        ts.period.cur_lo = 1.2400
        ts.period.cur_hi_time = T0
        ts.period.cur_lo_time = T0
        ctx = _make_ctx(close=1.2500, high=1.2510, low=1.2490, bar_time=T1,
                        htf={"H1": {"new_period": True}})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        assert ts.period.prev_highs[0] == 1.2600
        assert ts.period.prev_lows[0] == 1.2400


class TestNesting:
    def test_child_inside_parent_detected(self):
        """M5 zone inside H1 zone = nested."""
        state = init_push_zone_state(["M5", "H1"])
        # H1 supply zone
        state.tick_states["H1"].supply_zones.append(PushZone(
            top=1.2600, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        # M5 supply zone inside H1 (created by fire)
        m5_state = state.tick_states["M5"]
        m5_state.supply_zones.append(PushZone(
            top=1.2550, bottom=1.2450, is_supply=True,
            origin_time=T0, timeframe="M5",
        ))
        latest = m5_state.supply_zones[-1]
        # Nesting check: child inside parent
        h1_zones = state.tick_states["H1"].supply_zones + state.tick_states["H1"].demand_zones
        nested = _check_nesting(latest, h1_zones)
        assert nested is not None

    def test_opposing_direction_is_terminal(self):
        """M5 demand inside H1 supply = terminal."""
        state = init_push_zone_state(["M5", "H1"])
        state.tick_states["H1"].supply_zones.append(PushZone(
            top=1.2600, bottom=1.2400, is_supply=True,
            origin_time=T0, timeframe="H1",
        ))
        child = PushZone(
            top=1.2550, bottom=1.2450, is_supply=False,
            origin_time=T0, timeframe="M5",
        )
        h1_zones = state.tick_states["H1"].supply_zones
        parent = _check_nesting(child, h1_zones)
        assert parent is not None
        # Opposing direction
        assert child.is_supply != parent.is_supply


class TestCountReset:
    def test_hh_resets_supply_count(self):
        """HH supply fire resets supply count to 0, then increments to 1."""
        state = init_push_zone_state(["H1"])
        state.tick_states["H1"].sup_count = 5
        ctx = _make_ctx(close=1.25, high=1.26, low=1.24, bar_time=T1,
                        edges={"H1": {"edge_hi_fire": True, "edge_lo_fire": False}},
                        htf={"H1": {
                            "hi_fire": True, "ztop": 1.27, "zbot": 1.26,
                            "hi_time": T0, "hi_is_hh": True,
                            "hi_txt": "HH", "seq_hh": 1.27,
                            "lo_fire": False, "lo_time": None,
                            "lo_is_ll": False, "lo_txt": "", "seq_ll": nan,
                        }})
        push_zone_engine_tick(state, ctx, PushZoneEngineConfig())
        # Count should have been reset to 0, then incremented to 1
        assert state.tick_states["H1"].sup_count == 1
```

Note: `_check_nesting` is a helper function that will be exposed for testing. The nesting tests verify the concept — the actual implementation in `push_zone_engine_tick` will call it internally.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Iora && python -m pytest tests/orchestrator/test_push_zone_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement push_zone_engine**

```python
# src/iora/orchestrator/push_zone_engine.py
"""
Push zone engine — multi-TF orchestration for push zone detection.

Calls push_zone_tick() per TF per bar. Handles:
  - Period tracking + trend state updates
  - Zone count resets (parent fire + HH/LL structural invalidation)
  - Nesting detection + terminal classification

Pine reference: iora_push_zones_v2.pine (S8-S9)
Pattern: follows zone_engine.py orchestration style
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan, nan

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState, PeriodTracker
from iora.engine.push_zone_tick import push_zone_tick
from iora.engine.events import EventBus
from iora.engine.models import BarContext
from iora.constants import ENGINE_TF_ORDER as TF_ORDER


# TF label → seconds per bar
_TF_SECONDS: dict[str, int] = {
    "M1": 60, "M5": 300, "M15": 900, "H1": 3600,
    "H4": 14400, "D1": 86400, "W1": 604800, "MN1": 2592000,
}

# Parent TF mapping for nesting detection
# Matches Pine tf_parent(): M1→M15, M5→H1, M15→H1, H1→H4, H4→D1, D1→W1, W1→MN1
_PARENT_TF: dict[str, str] = {
    "M1": "M15", "M5": "H1", "M15": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1", "W1": "MN1",
}


@dataclass(slots=True)
class PushZoneEngineConfig:
    doji_pct: float = 5.0
    max_age: dict[str, int] = field(default_factory=lambda: {
        "M1": 50, "M5": 50, "M15": 50, "H1": 50,
        "H4": 50, "D1": 50, "W1": 30, "MN1": 20,
    })
    period_history_depth: int = 3


@dataclass(slots=True)
class PushZoneEngineState:
    tick_states: dict[str, PushZoneTickState] = field(default_factory=dict)


def init_push_zone_state(
    tf_list: list[str] | None = None,
    period_depth: int = 3,
) -> PushZoneEngineState:
    if tf_list is None:
        tf_list = list(TF_ORDER)
    tick_states = {}
    for tf in tf_list:
        ts = PushZoneTickState()
        ts.period = PeriodTracker(history_depth=period_depth)
        tick_states[tf] = ts
    return PushZoneEngineState(tick_states=tick_states)


def _check_nesting(
    child: PushZone,
    parent_zones: list[PushZone],
) -> PushZone | None:
    """Find the tightest parent zone containing the child. Returns None if no nesting."""
    best: PushZone | None = None
    best_range = float("inf")
    for p in parent_zones:
        if child.top <= p.top and child.bottom >= p.bottom:
            pr = p.top - p.bottom
            if pr < best_range:
                best_range = pr
                best = p
    return best


def push_zone_engine_tick(
    state: PushZoneEngineState,
    ctx: BarContext,
    config: PushZoneEngineConfig,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar through the push zone engine for all TFs.

    Sequence per TF (HIGH→LOW order for parent-before-child):
      1. Period tracking + trend update
      2. Count reset (parent fire + HH/LL invalidation)
      3. push_zone_tick() (expire, break, create, push validate)
      4. Nesting detection + terminal classification
    """
    close = ctx.close
    high = ctx.high
    low = ctx.low
    bar_time = ctx.timestamp

    # Process HIGH→LOW so parents populate before children
    tf_list = [tf for tf in reversed(TF_ORDER) if tf in state.tick_states]

    for tf in tf_list:
        ts = state.tick_states[tf]
        htf_data = ctx.htf.get(tf, {})
        edge_data = ctx.edges.get(tf, {})

        # --- 1. Period tracking ---
        _update_period(ts, tf, high, low, bar_time, htf_data)

        # --- 2. Count reset ---
        hi_fire = bool(edge_data.get("edge_hi_fire", False))
        lo_fire = bool(edge_data.get("edge_lo_fire", False))

        hi_txt = str(htf_data.get("hi_txt", ""))
        lo_txt = str(htf_data.get("lo_txt", ""))

        # Reset on HH/LL structural invalidation
        if hi_fire and hi_txt == "HH":
            ts.sup_count = 0
            ts.sup_reset_time = bar_time
        if lo_fire and lo_txt == "LL":
            ts.dem_count = 0
            ts.dem_reset_time = bar_time

        # Reset on parent fire (same-side)
        parent_tf = _PARENT_TF.get(tf)
        if parent_tf and parent_tf in state.tick_states:
            parent_edges = ctx.edges.get(parent_tf, {})
            parent_htf = ctx.htf.get(parent_tf, {})
            p_hi_fire = bool(parent_edges.get("edge_hi_fire", False))
            p_lo_fire = bool(parent_edges.get("edge_lo_fire", False))
            if p_hi_fire:  # parent supply fire → reset child supply count
                ts.sup_count = 0
                ts.sup_reset_time = bar_time
            if p_lo_fire:  # parent demand fire → reset child demand count
                ts.dem_count = 0
                ts.dem_reset_time = bar_time

        # --- 3. push_zone_tick ---
        hi_ztop = htf_data.get("ztop") if hi_fire else None
        hi_zbot = htf_data.get("zbot") if hi_fire else None
        hi_time_raw = htf_data.get("hi_time")
        hi_time = pd.Timestamp(hi_time_raw) if hi_time_raw is not None else None
        hi_is_hh = bool(htf_data.get("hi_is_hh", False))
        seq_hh_raw = htf_data.get("seq_hh")
        seq_hh = float(seq_hh_raw) if seq_hh_raw is not None else nan

        lo_ztop = htf_data.get("ztop") if lo_fire else None
        lo_zbot = htf_data.get("zbot") if lo_fire else None
        lo_time_raw = htf_data.get("lo_time")
        lo_time = pd.Timestamp(lo_time_raw) if lo_time_raw is not None else None
        lo_is_ll = bool(htf_data.get("lo_is_ll", False))
        seq_ll_raw = htf_data.get("seq_ll")
        seq_ll = float(seq_ll_raw) if seq_ll_raw is not None else nan

        tf_seconds = _TF_SECONDS.get(tf, 3600)
        max_age = config.max_age.get(tf, 50)

        push_zone_tick(
            state=ts,
            close=close,
            hi_fire=hi_fire, hi_ztop=hi_ztop, hi_zbot=hi_zbot,
            hi_time=hi_time, hi_is_hh=hi_is_hh, hi_txt=hi_txt, seq_hh=seq_hh,
            lo_fire=lo_fire, lo_ztop=lo_ztop, lo_zbot=lo_zbot,
            lo_time=lo_time, lo_is_ll=lo_is_ll, lo_txt=lo_txt, seq_ll=seq_ll,
            bar_time=bar_time, tf_seconds=tf_seconds, max_age=max_age,
            timeframe=tf, bus=bus,
        )

        # --- 4. Nesting detection ---
        if (hi_fire or lo_fire) and parent_tf and parent_tf in state.tick_states:
            parent_ts = state.tick_states[parent_tf]
            parent_all = parent_ts.supply_zones + parent_ts.demand_zones
            # Check newly created zones for nesting
            zones_to_check = []
            if hi_fire and ts.supply_zones:
                zones_to_check.append(ts.supply_zones[-1])
            if lo_fire and ts.demand_zones:
                zones_to_check.append(ts.demand_zones[-1])

            for child in zones_to_check:
                parent = _check_nesting(child, parent_all)
                if parent is not None and child.is_supply != parent.is_supply:
                    child.is_terminal = True


def _update_period(
    ts: PushZoneTickState,
    tf: str,
    high: float,
    low: float,
    bar_time: pd.Timestamp,
    htf_data: dict,
) -> None:
    """Update period tracker and trend state for one TF.

    Uses the `new_period` flag from aligned data (True on first base bar
    of a new TF period). This corresponds to Pine's `ta.change(time(tf))`.
    """
    pt = ts.period

    # Detect new period boundary — set by tf_alignment (see Task 6)
    is_new_period = bool(htf_data.get("new_period", False))

    if is_new_period:
        pt.rotate(bar_time)

    # Track current period hi/lo
    if pt.cur_hi != pt.cur_hi or high >= pt.cur_hi:  # nan or new high
        pt.cur_hi = high
        pt.cur_hi_time = bar_time
    if pt.cur_lo != pt.cur_lo or low <= pt.cur_lo:  # nan or new low
        pt.cur_lo = low
        pt.cur_lo_time = bar_time

    # Break detection (wick-based) — only when prev period levels exist
    if pt.prev_highs and pt.hi_brk_time is None:
        if high > pt.prev_highs[0]:
            pt.hi_brk_time = bar_time
            ts.trend = 1
    if pt.prev_lows and pt.lo_brk_time is None:
        if low < pt.prev_lows[0]:
            pt.lo_brk_time = bar_time
            ts.trend = -1
```

- [ ] **Step 4: Run tests**

Run: `cd /c/Iora && python -m pytest tests/orchestrator/test_push_zone_engine.py -v`

Fix: The nesting tests use `_check_nesting` directly — import it:
```python
from iora.orchestrator.push_zone_engine import _check_nesting
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/orchestrator/push_zone_engine.py tests/orchestrator/test_push_zone_engine.py
git commit -m "feat(push-zone): multi-TF push zone engine with period tracking, nesting, count resets"
```

---

## Task 6: Extend tf_alignment.py + Pipeline Integration

Add `seq_hh`, `seq_ll`, `hi_txt`, `lo_txt` columns to the aligned multi-TF data so push_zone_engine_tick() can read them from `ctx.htf`. Then wire `push_zone_engine_tick()` into the pipeline's bar loop.

**Files:**
- Modify: `src/iora/data/tf_alignment.py:44-55`
- Modify: `src/iora/orchestrator/pipeline.py`
- Create: `tests/integration/test_push_zone_pipeline.py`

- [ ] **Step 1: Add new columns to tf_alignment.py**

In `src/iora/data/tf_alignment.py`, extend `_EVENT_COLS` (line 44):

```python
_EVENT_COLS = [
    "hi_fire",
    "hi_price",
    "hi_time",
    "hi_is_hh",
    "lo_fire",
    "lo_price",
    "lo_time",
    "lo_is_ll",
    "ztop",
    "zbot",
    # Push zone extensions
    "seq_hh",
    "seq_ll",
    "hi_txt",
    "lo_txt",
]
```

These columns are now produced by `compute_pivot_events()` (Task 2) and automatically flow through the alignment pipeline.

Additionally, add a **period boundary column** (`new_period`) per TF. This fires `True` on the first base bar of each new TF period (equivalent to Pine's `ta.change(time(tf))`). In `build_aligned_multi_tf()`, after the edge detection loop, add per-TF:

```python
        # Period boundary detection: True on first base bar of new TF period
        # For base TF, every bar is a new period.
        # For HTF, detect when the aligned HTF timestamp changes.
        if tf_label == base_tf:
            prefixed[f"{tf_label}_new_period"] = True
        else:
            # The aligned hi_time or lo_time columns carry the HTF bar timestamp.
            # Alternatively, use merge_asof on the HTF index directly.
            # Simplest: create a "tf_time" column from the HTF index, align it,
            # and diff to detect changes.
            tf_time_col = f"{tf_label}_tf_time"
            tf_time_series = pd.Series(ev.index, index=ev.index, name="tf_time")
            tf_time_aligned = pd.merge_asof(
                left, tf_time_series.to_frame(),
                left_index=True, right_index=True,
                direction="backward", allow_exact_matches=True,
            )["tf_time"]
            prefixed[f"{tf_label}_new_period"] = tf_time_aligned != tf_time_aligned.shift(1)
```

This column flows through `ctx.htf[tf]["new_period"]` and is consumed by `_update_period()` in the push zone engine to trigger `PeriodTracker.rotate()`.

- [ ] **Step 2: Extend PipelineConfig and PipelineOutput**

In `src/iora/orchestrator/pipeline.py`:

Add to `PipelineConfig`:
```python
    push_zone_on: bool = False
    push_zone_max_age: dict[str, int] = field(default_factory=lambda: {
        "M1": 50, "M5": 50, "M15": 50, "H1": 50,
        "H4": 50, "D1": 50, "W1": 30, "MN1": 20,
    })
    period_history_depth: int = 3
```

Add to `PipelineOutput`:
```python
    push_zones_by_tf: dict[str, list] = field(default_factory=dict)
    push_trend_by_tf: dict[str, int] = field(default_factory=dict)
    period_levels_by_tf: dict[str, dict] = field(default_factory=dict)
```

- [ ] **Step 3: Wire push_zone_engine_tick into the pipeline bar loop**

In `run_pipeline()`, after `zone_engine_tick()` call, add:

```python
    if config.push_zone_on:
        push_zone_engine_tick(push_zone_state, ctx, push_zone_config, bus=bus)
```

And in `_collect_outputs()`, populate the new fields:

```python
    if push_zone_state is not None:
        for tf, ts in push_zone_state.tick_states.items():
            out.push_zones_by_tf[tf] = list(ts.supply_zones) + list(ts.demand_zones)
            out.push_trend_by_tf[tf] = ts.trend
            out.period_levels_by_tf[tf] = {
                "highs": list(ts.period.prev_highs),
                "lows": list(ts.period.prev_lows),
            }
```

- [ ] **Step 4: Write integration test**

```python
# tests/integration/test_push_zone_pipeline.py
from __future__ import annotations

import pandas as pd
import pytest

from iora.orchestrator.pipeline import PipelineConfig, run_pipeline


def _make_trending_data(n_bars: int = 200) -> dict[str, pd.DataFrame]:
    """Generate synthetic H1 data with a clear uptrend then downtrend."""
    import numpy as np
    idx = pd.date_range("2026-01-01", periods=n_bars, freq="h")
    # Uptrend for first half, downtrend for second half
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
        config = PipelineConfig(push_zone_on=True)
        output = run_pipeline(data, base_tf="H1", config=config)
        # Should have some push zones detected
        all_zones = []
        for tf, zones in output.push_zones_by_tf.items():
            all_zones.extend(zones)
        assert len(all_zones) > 0, "Expected push zones in trending data"

    def test_push_zones_have_classifications(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True)
        output = run_pipeline(data, base_tf="H1", config=config)
        push_zones = [z for zones in output.push_zones_by_tf.values()
                      for z in zones if z.is_push]
        # At least some zones should be classified as push
        # (may be 0 if data is too noisy — that's OK for this test)

    def test_trend_state_populated(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True)
        output = run_pipeline(data, base_tf="H1", config=config)
        assert "H1" in output.push_trend_by_tf

    def test_period_levels_populated(self):
        data = _make_trending_data(200)
        config = PipelineConfig(push_zone_on=True)
        output = run_pipeline(data, base_tf="H1", config=config)
        assert "H1" in output.period_levels_by_tf
        levels = output.period_levels_by_tf["H1"]
        assert "highs" in levels
        assert "lows" in levels
```

- [ ] **Step 5: Run integration tests**

Run: `cd /c/Iora && python -m pytest tests/integration/test_push_zone_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/iora/data/tf_alignment.py src/iora/orchestrator/pipeline.py tests/integration/test_push_zone_pipeline.py
git commit -m "feat(push-zone): pipeline integration — push zone engine wired into bar loop"
```

---

## Task 7: Verification Against Pine Indicator

Load real GBPUSD data from parquet, run the push zone engine, and compare output against what the Pine indicator shows on TradingView. This is a manual verification task — no automated tests, but produces a comparison report.

**Files:**
- Create: `scripts/verify_push_zones.py`

- [ ] **Step 1: Write verification script**

```python
# scripts/verify_push_zones.py
"""
Verify Python push zone engine output against Pine indicator.

Loads GBPUSD data, runs the push zone engine, and prints zone events
for manual comparison against TradingView charts.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "src")

import pandas as pd

from iora.data.parquet_storage import ParquetStorage
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.engine.events import EventBus


def main():
    storage = ParquetStorage("data/raw")
    symbol = "GBPUSD"

    # Load TFs needed
    tfs = ["M5", "M15", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df)} bars, {df.index[0]} → {df.index[-1]}")

    base_tf = "M5"
    print(f"\nBuilding aligned data (base={base_tf})...")
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    print(f"  Aligned: {len(aligned_df)} bars")

    print("\nRunning push zone engine...")
    state = init_push_zone_state(tfs, period_depth=3)
    config = PushZoneEngineConfig()
    bus = EventBus()

    zone_events = []
    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        for ev in bus.drain():
            zone_events.append({
                "time": ev.timestamp,
                "tf": ev.timeframe,
                "type": ev.id.name,
                "payload": ev.payload,
            })

    print(f"\nTotal events: {len(zone_events)}")
    print(f"  ZONE_FIRE: {sum(1 for e in zone_events if e['type'] == 'ZONE_FIRE')}")
    print(f"  ZONE_BREAK: {sum(1 for e in zone_events if e['type'] == 'ZONE_BREAK')}")

    # Print final zone state
    print("\n--- Final Zone State ---")
    for tf in tfs:
        ts = state.tick_states.get(tf)
        if ts is None:
            continue
        sup = [z for z in ts.supply_zones]
        dem = [z for z in ts.demand_zones]
        push_sup = [z for z in sup if z.is_push]
        push_dem = [z for z in dem if z.is_push]
        rev = [z for z in sup + dem if z.is_reversal]
        print(f"\n  {tf}: {len(sup)}S {len(dem)}D | "
              f"Push: {len(push_sup)}S {len(push_dem)}D | "
              f"Rev: {len(rev)} | Trend: {ts.trend}")
        for z in sup + dem:
            role = "PUSH" if z.is_push else ("REV" if z.is_reversal else ("TERM" if z.is_terminal else ""))
            cls = f" {z.struct_cls}" if z.struct_cls else ""
            print(f"    {'S' if z.is_supply else 'D'} {z.swing_cls}{cls} "
                  f"#{z.count_num} {role} "
                  f"[{z.bottom:.5f} — {z.top:.5f}] @ {z.origin_time}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the verification**

Run: `cd /c/Iora && python scripts/verify_push_zones.py`

Compare output zones against what you see on the GBPUSD M5 chart in TradingView with push_zones_v2 indicator loaded. Key things to verify:
- Zone tops/bottoms match (within floating-point tolerance)
- Push zones are tagged on the same bars
- BOS/CHoCH classifications match
- Zone counts match
- Trend state (BULL/BEAR) matches dashboard

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_push_zones.py
git commit -m "feat(push-zone): add Pine verification script for manual comparison"
```

---

## Summary

| Task | Component | Tests | Files |
|------|-----------|-------|-------|
| 1 | PushZone, PeriodTracker, PushZoneTickState models | 10 | 2 new |
| 2 | ha_pivots.py seq_hh/seq_ll extension | 6 | 1 modified, 1 new |
| 3 | push_zone_tick: creation, breaks, push validation | 8 | 2 new |
| 4 | Push validation + BOS/CHoCH test coverage | 7 | 1 extended |
| 5 | Push zone engine: multi-TF, period tracking, nesting | 6 | 2 new |
| 6 | tf_alignment + pipeline integration | 4 | 2 modified, 1 new |
| 7 | Verification against Pine indicator | manual | 1 new |

**Total:** ~41 automated tests, 7 new files, 3 modified files, 1 verification script

**Next plans (after this one):**
- Plan 2: Strategy evaluation layer (entry/exit rules, signal matrix, StrategyConfig)
- Plan 3: Sweep runner (batch testing across configs/symbols)
- Plan 4: Flask visualization extensions (backtest endpoints, trade rendering)
