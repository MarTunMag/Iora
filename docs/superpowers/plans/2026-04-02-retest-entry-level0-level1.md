# Retest Entry System — Level 0 + Level 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove age-based zone expiry, enrich PushZone with retest/birth metadata, add retest detection to the orchestrator, and build a zone activity audit module that reveals zone population dynamics across all 38 symbols.

**Architecture:** Minimal changes to the proven zone engine — remove expiry, add soft cap, enrich metadata at creation. Retest detection (touch counting) runs in the orchestrator's per-bar loop. Zone audit is a new diagnostic module that consumes engine output and produces population statistics. No strategy changes.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest. Existing engine/orchestrator patterns.

**Spec:** `docs/superpowers/specs/2026-04-02-retest-entry-system-design.md`

---

### Task 1: Add new metadata fields to PushZone

**Files:**
- Modify: `src/iora/engine/push_zone_models.py:14-31`
- Test: `tests/engine/test_push_zone_models.py`

- [ ] **Step 1: Write failing tests for new PushZone fields**

```python
# tests/engine/test_push_zone_models.py — add to existing test file or create

import pandas as pd
from iora.engine.push_zone_models import PushZone


def test_pushzone_new_metadata_fields_defaults():
    """New metadata fields have correct defaults."""
    z = PushZone(
        top=1.3000, bottom=1.2980, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    assert z.birth_price_distance == 0.0
    assert z.birth_bias_d == "unknown"
    assert z.birth_bias_w == "unknown"
    assert z.birth_period_pattern == "unknown"
    assert z.replacement_count == 0
    assert z.test_count == 0
    assert z.first_test_time is None


def test_pushzone_metadata_fields_settable():
    """New metadata fields can be set at construction."""
    z = PushZone(
        top=1.3000, bottom=1.2980, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
        birth_price_distance=2.5,
        birth_bias_d="HH_HL_bull_push",
        birth_bias_w="pushing_from_w",
        birth_period_pattern="HH_HL",
        replacement_count=0,
        test_count=0,
        first_test_time=None,
    )
    assert z.birth_price_distance == 2.5
    assert z.birth_bias_d == "HH_HL_bull_push"
    assert z.birth_period_pattern == "HH_HL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_push_zone_models.py -v -k "metadata"`
Expected: FAIL — fields don't exist on PushZone

- [ ] **Step 3: Add fields to PushZone dataclass**

In `src/iora/engine/push_zone_models.py`, add after the existing fields (line 28, after `count_num`):

```python
    # --- Retest & birth metadata (Level 0 enrichment) ---
    birth_price_distance: float = 0.0    # ATR(14) units from zone midpoint to close at creation
    birth_bias_d: str = "unknown"        # Daily bias at creation (e.g., "HH_HL_bull_push")
    birth_bias_w: str = "unknown"        # Weekly context at creation
    birth_period_pattern: str = "unknown" # Period pattern at creation (e.g., "HH_HL")
    replacement_count: int = 0           # Same-TF same-side zones created since this one
    test_count: int = 0                  # Times price touched this zone
    first_test_time: pd.Timestamp | None = None  # Timestamp of first retest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_push_zone_models.py -v -k "metadata"`
Expected: PASS

- [ ] **Step 5: Run full existing test suite to verify no regressions**

Run: `pytest tests/ -x -q`
Expected: All existing tests pass (PushZone uses `slots=True` but new fields with defaults are backwards-compatible)

- [ ] **Step 6: Commit**

```bash
git add src/iora/engine/push_zone_models.py tests/engine/test_push_zone_models.py
git commit -m "feat(engine): add retest and birth metadata fields to PushZone"
```

---

### Task 2: Remove age-based expiry, add soft cap

**Files:**
- Modify: `src/iora/engine/push_zone_tick.py:58-72` (expiry logic)
- Modify: `src/iora/engine/push_zone_tick.py:89-140` (creation age check)
- Test: `tests/engine/test_push_zone_tick.py`

- [ ] **Step 1: Write failing tests for new lifecycle behavior**

```python
# tests/engine/test_push_zone_tick.py — add these tests

import pandas as pd
from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.push_zone_tick import push_zone_tick


def _make_state_with_zones(n_supply: int = 0, n_demand: int = 0) -> PushZoneTickState:
    """Helper: create state with N pre-existing zones."""
    state = PushZoneTickState()
    for i in range(n_supply):
        state.supply_zones.append(PushZone(
            top=1.3000 + i * 0.001, bottom=1.2990 + i * 0.001,
            is_supply=True, origin_time=pd.Timestamp("2024-01-01"),
            timeframe="M5",
        ))
    for i in range(n_demand):
        state.demand_zones.append(PushZone(
            top=1.2900 + i * 0.001, bottom=1.2890 + i * 0.001,
            is_supply=False, origin_time=pd.Timestamp("2024-01-01"),
            timeframe="M5",
        ))
    return state


def test_zone_not_expired_by_age():
    """Zones should NOT be removed by age — only by body-close break."""
    state = _make_state_with_zones(n_supply=1)
    # Zone is very old (2024-01-01) but price hasn't broken it
    push_zone_tick(
        state=state, close=1.2950,  # Below supply top, no break
        hi_fire=False, hi_ztop=None, hi_zbot=None, hi_time=None,
        hi_is_hh=False, hi_txt="", seq_hh=float("nan"),
        lo_fire=False, lo_ztop=None, lo_zbot=None, lo_time=None,
        lo_is_ll=False, lo_txt="", seq_ll=float("nan"),
        bar_time=pd.Timestamp("2026-06-01"),  # 2.5 years later!
        tf_seconds=300, max_age=50, timeframe="M5",
    )
    assert len(state.supply_zones) == 1  # Zone survives — no age expiry


def test_zone_still_broken_by_body_close():
    """Body-close break still removes zones (not affected by expiry removal)."""
    state = _make_state_with_zones(n_supply=1)
    push_zone_tick(
        state=state, close=1.3050,  # Above supply top — broken
        hi_fire=False, hi_ztop=None, hi_zbot=None, hi_time=None,
        hi_is_hh=False, hi_txt="", seq_hh=float("nan"),
        lo_fire=False, lo_ztop=None, lo_zbot=None, lo_time=None,
        lo_is_ll=False, lo_txt="", seq_ll=float("nan"),
        bar_time=pd.Timestamp("2026-06-01"),
        tf_seconds=300, max_age=50, timeframe="M5",
    )
    assert len(state.supply_zones) == 0  # Broken by body close


def test_soft_cap_evicts_oldest(self):
    """When more than 30 zones per side, oldest is evicted."""
    state = _make_state_with_zones(n_supply=30)
    # Fire a new supply zone — should evict oldest
    push_zone_tick(
        state=state, close=1.3500,
        hi_fire=True, hi_ztop=1.3600, hi_zbot=1.3550,
        hi_time=pd.Timestamp("2026-06-01"),
        hi_is_hh=False, hi_txt="LH", seq_hh=float("nan"),
        lo_fire=False, lo_ztop=None, lo_zbot=None, lo_time=None,
        lo_is_ll=False, lo_txt="", seq_ll=float("nan"),
        bar_time=pd.Timestamp("2026-06-01"),
        tf_seconds=300, max_age=50, timeframe="M5",
    )
    assert len(state.supply_zones) <= 30  # Soft cap enforced


def test_zone_creation_ignores_age_check():
    """New zones are created even when origin is old (age check removed)."""
    state = PushZoneTickState()
    # Fire with an old origin time — should still create
    push_zone_tick(
        state=state, close=1.2900,
        hi_fire=True, hi_ztop=1.3000, hi_zbot=1.2980,
        hi_time=pd.Timestamp("2024-01-01"),  # Very old origin
        hi_is_hh=False, hi_txt="LH", seq_hh=float("nan"),
        lo_fire=False, lo_ztop=None, lo_zbot=None, lo_time=None,
        lo_is_ll=False, lo_txt="", seq_ll=float("nan"),
        bar_time=pd.Timestamp("2026-06-01"),
        tf_seconds=300, max_age=50, timeframe="M5",
    )
    assert len(state.supply_zones) == 1  # Zone created despite old origin
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/engine/test_push_zone_tick.py -v -k "expired or cap or age_check"`
Expected: FAIL — `test_zone_not_expired_by_age` fails (zone gets expired), `test_zone_creation_ignores_age_check` fails (zone not created)

- [ ] **Step 3: Modify push_zone_tick.py**

In `src/iora/engine/push_zone_tick.py`:

**Remove age-based expiry (lines 58-72).** Replace with body-close-only break + soft cap:

```python
    # --- 1. Break detection (body-close only, no age expiry) ---
    SOFT_CAP: int = 30  # Max zones per side per TF
    broken: list[PushZone] = []
    for zones in (state.supply_zones, state.demand_zones):
        i: int = len(zones) - 1
        while i >= 0:
            z: PushZone = zones[i]
            is_broken: bool = close > z.top if z.is_supply else close < z.bottom
            if is_broken:
                broken.append(zones.pop(i))
            i -= 1
```

**Remove age check on zone creation (lines 89-93 and 116-119).** Remove the `if (bar_ms - origin_ms) < max_age_ms:` guard so zones are always created:

```python
    # --- 2. Zone creation ---
    if hi_fire and hi_ztop is not None and hi_zbot is not None and hi_ztop > hi_zbot:
        origin: pd.Timestamp = hi_time if hi_time is not None else bar_time
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
        # Soft cap: evict oldest if exceeded
        while len(state.supply_zones) > SOFT_CAP:
            state.supply_zones.pop(0)  # Remove oldest (index 0)
        # ... (keep existing bus.emit)
```

Same pattern for demand zone creation (lo_fire block).

Also remove `bar_ms` and `max_age_ms` computation at top of function (line 54-55) since they're no longer used. Keep the `max_age` parameter in the signature for backwards compatibility but it becomes unused.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/engine/test_push_zone_tick.py -v`
Expected: PASS (including existing tests — body-close break still works)

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass. The `max_age` param is still accepted but ignored.

- [ ] **Step 6: Commit**

```bash
git add src/iora/engine/push_zone_tick.py tests/engine/test_push_zone_tick.py
git commit -m "feat(engine): remove age-based zone expiry, add soft cap (30 per side)"
```

---

### Task 3: Add retest detection to orchestrator

**Files:**
- Modify: `src/iora/orchestrator/push_zone_engine.py:85-189`
- Test: `tests/orchestrator/test_push_zone_engine.py`

The orchestrator's per-bar loop (`push_zone_engine_tick`) processes all TFs. After the tick function runs (step 3 in the loop), we add step 3.5: retest detection. This checks all active zones against the current bar's OHLC and increments `test_count`/`first_test_time`.

- [ ] **Step 1: Write failing tests for retest detection**

```python
# tests/orchestrator/test_push_zone_engine.py — add these tests

import pandas as pd
from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.orchestrator.push_zone_engine import _detect_retests


def test_detect_retests_demand_wick_touch():
    """Demand zone retest: bar low enters zone, close above zone."""
    zone = PushZone(
        top=1.2900, bottom=1.2880, is_supply=False,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.demand_zones.append(zone)
    _detect_retests(ts, high=1.2950, low=1.2895, close=1.2940,
                    bar_time=pd.Timestamp("2025-01-02"))
    assert zone.test_count == 1
    assert zone.first_test_time == pd.Timestamp("2025-01-02")


def test_detect_retests_supply_wick_touch():
    """Supply zone retest: bar high enters zone, close below zone."""
    zone = PushZone(
        top=1.3000, bottom=1.2980, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.supply_zones.append(zone)
    _detect_retests(ts, high=1.2990, low=1.2950, close=1.2960,
                    bar_time=pd.Timestamp("2025-01-02"))
    assert zone.test_count == 1


def test_detect_retests_no_touch():
    """No retest when price doesn't reach zone."""
    zone = PushZone(
        top=1.2900, bottom=1.2880, is_supply=False,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.demand_zones.append(zone)
    _detect_retests(ts, high=1.2950, low=1.2920, close=1.2940,
                    bar_time=pd.Timestamp("2025-01-02"))
    assert zone.test_count == 0
    assert zone.first_test_time is None


def test_detect_retests_body_close_inside_not_counted():
    """Body close inside zone that also breaks it is NOT a retest (it's a break)."""
    zone = PushZone(
        top=1.2900, bottom=1.2880, is_supply=False,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.demand_zones.append(zone)
    # Close below zone bottom — this is a break, not a retest
    _detect_retests(ts, high=1.2910, low=1.2870, close=1.2875,
                    bar_time=pd.Timestamp("2025-01-02"))
    assert zone.test_count == 0  # Breaks aren't retests


def test_detect_retests_multiple_touches():
    """Multiple retests increment test_count, first_test_time stays."""
    zone = PushZone(
        top=1.2900, bottom=1.2880, is_supply=False,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.demand_zones.append(zone)
    _detect_retests(ts, high=1.2950, low=1.2895, close=1.2940,
                    bar_time=pd.Timestamp("2025-01-02"))
    _detect_retests(ts, high=1.2950, low=1.2890, close=1.2930,
                    bar_time=pd.Timestamp("2025-01-03"))
    assert zone.test_count == 2
    assert zone.first_test_time == pd.Timestamp("2025-01-02")  # First stays


def test_detect_retests_replacement_count():
    """When a new zone fires, all existing same-side zones get replacement_count += 1."""
    old_zone = PushZone(
        top=1.2900, bottom=1.2880, is_supply=False,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    ts = PushZoneTickState()
    ts.demand_zones.append(old_zone)
    # Simulate new demand zone added
    new_zone = PushZone(
        top=1.2850, bottom=1.2830, is_supply=False,
        origin_time=pd.Timestamp("2025-01-05"), timeframe="M5",
    )
    ts.demand_zones.append(new_zone)
    # Call replacement count update
    from iora.orchestrator.push_zone_engine import _update_replacement_counts
    _update_replacement_counts(ts, new_supply=False, new_demand=True)
    assert old_zone.replacement_count == 1
    assert new_zone.replacement_count == 0  # The new one itself isn't replaced
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/orchestrator/test_push_zone_engine.py -v -k "detect_retests or replacement"`
Expected: FAIL — `_detect_retests` and `_update_replacement_counts` don't exist

- [ ] **Step 3: Implement retest detection and replacement counting**

In `src/iora/orchestrator/push_zone_engine.py`, add these functions:

```python
def _detect_retests(
    ts: PushZoneTickState,
    high: float,
    low: float,
    close: float,
    bar_time: pd.Timestamp,
) -> None:
    """Check all active zones for retest events. Mutates zones in place.

    A retest is: wick enters zone but close stays outside (not a break).
    - Demand: low <= zone.top AND close > zone.bottom
    - Supply: high >= zone.bottom AND close < zone.top
    """
    for z in ts.demand_zones:
        if low <= z.top and close > z.bottom:
            z.test_count += 1
            if z.first_test_time is None:
                z.first_test_time = bar_time

    for z in ts.supply_zones:
        if high >= z.bottom and close < z.top:
            z.test_count += 1
            if z.first_test_time is None:
                z.first_test_time = bar_time


def _update_replacement_counts(
    ts: PushZoneTickState,
    new_supply: bool,
    new_demand: bool,
) -> None:
    """Increment replacement_count on existing zones when new same-side zone fires."""
    if new_supply:
        for z in ts.supply_zones[:-1]:  # All except the newest (last)
            z.replacement_count += 1
    if new_demand:
        for z in ts.demand_zones[:-1]:
            z.replacement_count += 1
```

Then in `push_zone_engine_tick()`, after the `push_zone_tick()` call (line 173) and before nesting detection (line 175), add:

```python
        # --- 3.5. Retest detection + replacement counting ---
        new_supply = hi_fire and hi_ztop is not None and hi_zbot is not None and hi_ztop > hi_zbot
        new_demand = lo_fire and lo_ztop is not None and lo_zbot is not None and lo_ztop > lo_zbot
        _update_replacement_counts(ts, new_supply, new_demand)
        _detect_retests(ts, high, low, close, bar_time)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/orchestrator/test_push_zone_engine.py -v -k "detect_retests or replacement"`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/iora/orchestrator/push_zone_engine.py tests/orchestrator/test_push_zone_engine.py
git commit -m "feat(engine): add retest detection and replacement counting to orchestrator"
```

---

### Task 4: Add birth_period_pattern computation

**Files:**
- Create: `src/iora/diagnostics/__init__.py`
- Create: `src/iora/diagnostics/period_pattern.py`
- Test: `tests/diagnostics/test_period_pattern.py`

The `birth_period_pattern` is computed from the `PeriodTracker`'s 3-deep history. This is a pure function that can be called at zone creation time.

- [ ] **Step 1: Write failing tests**

```python
# tests/diagnostics/test_period_pattern.py

from iora.diagnostics.period_pattern import compute_period_pattern


def test_bull_push_pattern():
    """HH + HL = bull push."""
    assert compute_period_pattern(
        prev_highs=[1.3100, 1.3000],  # HH
        prev_lows=[1.2900, 1.2850],   # HL
    ) == "HH_HL"


def test_bear_push_pattern():
    """LH + LL = bear push."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3100],  # LH
        prev_lows=[1.2800, 1.2900],   # LL
    ) == "LH_LL"


def test_compression_pattern():
    """LH + HL = compression."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3100],  # LH
        prev_lows=[1.2900, 1.2850],   # HL
    ) == "LH_HL"


def test_expansion_pattern():
    """HH + LL = expansion."""
    assert compute_period_pattern(
        prev_highs=[1.3100, 1.3000],  # HH
        prev_lows=[1.2800, 1.2900],   # LL
    ) == "HH_LL"


def test_insufficient_history():
    """Less than 2 periods returns 'unknown'."""
    assert compute_period_pattern(prev_highs=[1.3000], prev_lows=[1.2900]) == "unknown"
    assert compute_period_pattern(prev_highs=[], prev_lows=[]) == "unknown"


def test_equal_values():
    """Equal highs/lows returns 'mixed'."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3000],
        prev_lows=[1.2900, 1.2900],
    ) == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_period_pattern.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement period pattern computation**

Create `src/iora/diagnostics/__init__.py` (empty file).

Create `src/iora/diagnostics/period_pattern.py`:

```python
"""Compute period pattern from PeriodTracker history."""
from __future__ import annotations


def compute_period_pattern(
    prev_highs: list[float],
    prev_lows: list[float],
) -> str:
    """Derive structural pattern from the last 2 period highs and lows.

    Returns one of: "HH_HL", "LH_LL", "LH_HL", "HH_LL", "mixed", "unknown".
    prev_highs[0] is most recent, prev_highs[1] is the one before.
    """
    if len(prev_highs) < 2 or len(prev_lows) < 2:
        return "unknown"

    h0, h1 = prev_highs[0], prev_highs[1]
    l0, l1 = prev_lows[0], prev_lows[1]

    hh = h0 > h1
    lh = h0 < h1
    hl = l0 > l1
    ll = l0 < l1

    if hh and hl:
        return "HH_HL"
    if lh and ll:
        return "LH_LL"
    if lh and hl:
        return "LH_HL"
    if hh and ll:
        return "HH_LL"
    return "mixed"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_period_pattern.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/__init__.py src/iora/diagnostics/period_pattern.py tests/diagnostics/test_period_pattern.py
git commit -m "feat(diagnostics): add period pattern computation from period tracker history"
```

---

### Task 5: Wire birth metadata into zone creation

**Files:**
- Modify: `src/iora/orchestrator/push_zone_engine.py:85-189`
- Test: `tests/orchestrator/test_push_zone_engine.py`

After `push_zone_tick()` creates a zone, the orchestrator enriches it with birth context (period pattern, price distance). Bias fields (`birth_bias_d`, `birth_bias_w`) are populated later by Level 2 — for now they stay as `"unknown"`.

- [ ] **Step 1: Write failing tests**

```python
# tests/orchestrator/test_push_zone_engine.py — add these tests

import pandas as pd
import numpy as np
from iora.engine.push_zone_models import PushZoneTickState, PushZone, PeriodTracker
from iora.orchestrator.push_zone_engine import _enrich_birth_metadata


def test_enrich_birth_metadata_period_pattern():
    """New zone gets birth_period_pattern from period tracker."""
    ts = PushZoneTickState()
    ts.period = PeriodTracker()
    ts.period.prev_highs = [1.3100, 1.3000, 1.2900]
    ts.period.prev_lows = [1.2900, 1.2850, 1.2800]
    zone = PushZone(
        top=1.3050, bottom=1.3020, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    _enrich_birth_metadata(zone, ts, close=1.3040)
    assert zone.birth_period_pattern == "HH_HL"


def test_enrich_birth_metadata_price_distance():
    """birth_price_distance is set relative to zone midpoint."""
    ts = PushZoneTickState()
    ts.period = PeriodTracker()
    zone = PushZone(
        top=1.3000, bottom=1.2980, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    # Zone midpoint = 1.2990, close = 1.2940, distance = 0.005
    _enrich_birth_metadata(zone, ts, close=1.2940)
    assert zone.birth_price_distance == abs(1.2990 - 1.2940)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/orchestrator/test_push_zone_engine.py -v -k "enrich_birth"`
Expected: FAIL — `_enrich_birth_metadata` doesn't exist

- [ ] **Step 3: Implement birth metadata enrichment**

In `src/iora/orchestrator/push_zone_engine.py`:

```python
from iora.diagnostics.period_pattern import compute_period_pattern


def _enrich_birth_metadata(
    zone: PushZone,
    ts: PushZoneTickState,
    close: float,
) -> None:
    """Enrich a newly created zone with birth context metadata."""
    # Period pattern from period tracker
    zone.birth_period_pattern = compute_period_pattern(
        ts.period.prev_highs, ts.period.prev_lows,
    )
    # Price distance (raw, not ATR-normalized yet — ATR normalization
    # happens at diagnostic/audit level where ATR data is available)
    zone_mid = (zone.top + zone.bottom) / 2.0
    zone.birth_price_distance = abs(zone_mid - close)
```

Then in `push_zone_engine_tick()`, after the `push_zone_tick()` call and replacement counting, enrich new zones:

```python
        # --- 3.6. Enrich birth metadata on newly created zones ---
        if new_supply and ts.supply_zones:
            _enrich_birth_metadata(ts.supply_zones[-1], ts, close)
        if new_demand and ts.demand_zones:
            _enrich_birth_metadata(ts.demand_zones[-1], ts, close)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/orchestrator/test_push_zone_engine.py -v -k "enrich_birth"`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/iora/orchestrator/push_zone_engine.py tests/orchestrator/test_push_zone_engine.py
git commit -m "feat(engine): wire birth metadata into zone creation"
```

---

### Task 6: Zone Activity Audit module

**Files:**
- Create: `src/iora/diagnostics/zone_audit.py`
- Test: `tests/diagnostics/test_zone_audit.py`

This is a diagnostic module that runs the zone engine on a symbol and collects zone lifecycle statistics. It produces a `ZoneAuditReport` dataclass.

- [ ] **Step 1: Write failing tests**

```python
# tests/diagnostics/test_zone_audit.py

import pandas as pd
import pytest
from iora.engine.push_zone_models import PushZone
from iora.diagnostics.zone_audit import ZoneAuditReport, ZoneLifecycleRecord, compute_audit


def _make_zone(tf: str, is_supply: bool, top: float, bottom: float,
               test_count: int = 0, origin: str = "2025-01-01",
               first_test_time=None, replacement_count: int = 0) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp(origin), timeframe=tf,
        test_count=test_count, first_test_time=first_test_time,
        replacement_count=replacement_count,
    )


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_zone_audit.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement zone audit module**

Create `src/iora/diagnostics/zone_audit.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_zone_audit.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/zone_audit.py tests/diagnostics/test_zone_audit.py
git commit -m "feat(diagnostics): add zone activity audit module (Level 1)"
```

---

### Task 7: Zone Audit Runner (CLI + per-bar population tracking)

**Files:**
- Create: `src/iora/diagnostics/zone_audit_runner.py`
- Create: `scripts/run_zone_audit.py`
- Test: `tests/diagnostics/test_zone_audit_runner.py`

This runs the zone engine on a symbol, collects per-zone lifecycle records with per-bar population snapshots, and produces the full audit report.

- [ ] **Step 1: Write failing tests**

```python
# tests/diagnostics/test_zone_audit_runner.py

import pandas as pd
import pytest
from iora.diagnostics.zone_audit_runner import run_zone_audit, ZoneAuditResult


@pytest.fixture(scope="module")
def gbpusd_audit():
    """Run audit on real GBPUSD data (skip if unavailable)."""
    from iora.data.parquet_storage import ParquetStorage
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
        # Should have supply + demand per TF
        tfs_present = {r.tf for r in gbpusd_audit.reports}
        assert "M5" in tfs_present

    def test_has_lifecycle_records(self, gbpusd_audit):
        """Lifecycle records captured for individual zones."""
        assert len(gbpusd_audit.lifecycle_records) > 0

    def test_zones_created_positive(self, gbpusd_audit):
        """Zone engine created zones across the data range."""
        total = sum(r.zones_created for r in gbpusd_audit.reports)
        assert total > 100  # 21 months of data should produce many zones

    def test_population_snapshots(self, gbpusd_audit):
        """Per-bar population snapshots recorded."""
        assert len(gbpusd_audit.population_snapshots) > 0
        # Each snapshot has tf, side, count, timestamp
        snap = gbpusd_audit.population_snapshots[0]
        assert "tf" in snap
        assert "count" in snap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_zone_audit_runner.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement zone audit runner**

Create `src/iora/diagnostics/zone_audit_runner.py`:

```python
"""Zone Audit Runner — runs zone engine and collects lifecycle records.

Produces ZoneAuditResult with per-zone lifecycle data and
per-bar zone population snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState, PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.engine.push_zone_models import PushZone
from iora.diagnostics.zone_audit import (
    ZoneLifecycleRecord, ZoneAuditReport, compute_audit,
)


@dataclass(slots=True)
class ZoneAuditResult:
    """Full audit output for one symbol."""
    symbol: str
    reports: list[ZoneAuditReport]
    lifecycle_records: list[ZoneLifecycleRecord]
    population_snapshots: list[dict]


def run_zone_audit(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> ZoneAuditResult:
    """Run zone engine on data and collect zone lifecycle statistics."""
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()

    # Track zone snapshots: id(zone) → zone reference + creation bar
    zone_registry: dict[int, tuple[PushZone, int]] = {}
    broken_records: list[ZoneLifecycleRecord] = []
    population_snapshots: list[dict] = []

    bar_idx = 0
    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs):
        # Snapshot zone ids BEFORE tick
        pre_ids: set[int] = set()
        for tf, ts in state.tick_states.items():
            for z in ts.supply_zones:
                pre_ids.add(id(z))
            for z in ts.demand_zones:
                pre_ids.add(id(z))

        push_zone_engine_tick(state, ctx, PushZoneEngineConfig(), bus=bus)
        bus.drain()

        # Register new zones
        for tf, ts in state.tick_states.items():
            for z in list(ts.supply_zones) + list(ts.demand_zones):
                zid = id(z)
                if zid not in pre_ids and zid not in zone_registry:
                    zone_registry[zid] = (z, bar_idx)

        # Check for broken zones (were in pre_ids, now gone)
        post_ids: set[int] = set()
        for tf, ts in state.tick_states.items():
            for z in ts.supply_zones:
                post_ids.add(id(z))
            for z in ts.demand_zones:
                post_ids.add(id(z))

        for zid in pre_ids - post_ids:
            if zid in zone_registry:
                z, creation_bar = zone_registry.pop(zid)
                broken_records.append(ZoneLifecycleRecord(
                    tf=z.timeframe,
                    side="supply" if z.is_supply else "demand",
                    origin_time=z.origin_time,
                    break_time=ctx.timestamp,
                    test_count=z.test_count,
                    first_test_time=z.first_test_time,
                    replacement_count=z.replacement_count,
                    lifespan_bars=bar_idx - creation_bar,
                    birth_period_pattern=z.birth_period_pattern,
                    birth_price_distance=z.birth_price_distance,
                ))

        # Periodic population snapshot (every 100 bars to keep memory bounded)
        if bar_idx % 100 == 0:
            for tf, ts in state.tick_states.items():
                population_snapshots.append({
                    "bar_idx": bar_idx,
                    "timestamp": ctx.timestamp,
                    "tf": tf,
                    "supply_count": len(ts.supply_zones),
                    "demand_count": len(ts.demand_zones),
                    "count": len(ts.supply_zones) + len(ts.demand_zones),
                })

        bar_idx += 1

    # Still-alive zones → lifecycle records with break_time=None
    all_records = list(broken_records)
    for zid, (z, creation_bar) in zone_registry.items():
        all_records.append(ZoneLifecycleRecord(
            tf=z.timeframe,
            side="supply" if z.is_supply else "demand",
            origin_time=z.origin_time,
            break_time=None,
            test_count=z.test_count,
            first_test_time=z.first_test_time,
            replacement_count=z.replacement_count,
            lifespan_bars=bar_idx - creation_bar,
            birth_period_pattern=z.birth_period_pattern,
            birth_price_distance=z.birth_price_distance,
        ))

    # Compute per-TF per-side reports
    reports: list[ZoneAuditReport] = []
    for tf in tfs:
        for side in ("supply", "demand"):
            tf_records = [r for r in all_records if r.tf == tf and r.side == side]
            if tf_records:
                report = compute_audit(tf_records, tf, side)
                # Compute avg/max zones alive from population snapshots
                tf_pops = [s for s in population_snapshots if s["tf"] == tf]
                if tf_pops:
                    side_key = f"{side}_count"
                    counts = [s[side_key] for s in tf_pops]
                    report.avg_zones_alive = sum(counts) / len(counts)
                    report.max_zones_alive = max(counts)
                reports.append(report)

    return ZoneAuditResult(
        symbol=symbol,
        reports=reports,
        lifecycle_records=all_records,
        population_snapshots=population_snapshots,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_zone_audit_runner.py -v`
Expected: PASS

- [ ] **Step 5: Create CLI script**

Create `scripts/run_zone_audit.py`:

```python
"""Run zone activity audit across symbols.

Usage: python scripts/run_zone_audit.py [--symbols GBPUSD,EURUSD] [--output results/]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.zone_audit_runner import run_zone_audit

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Zone activity audit")
    parser.add_argument("--symbols", default="GBPUSD",
                        help="Comma-separated symbols (default: GBPUSD)")
    parser.add_argument("--output", default="results",
                        help="Output directory (default: results)")
    parser.add_argument("--base-tf", default="M5",
                        help="Base timeframe (default: M5)")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    storage = ParquetStorage("data")

    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Auditing {symbol}...")
        tfs = [args.base_tf, "M15", "H1", "H4", "D1", "W1"]
        data_by_tf = {}
        for tf in tfs:
            df = storage.load(symbol, tf)
            if df is not None and not df.empty:
                data_by_tf[tf] = df

        if args.base_tf not in data_by_tf:
            print(f"  SKIP {symbol}: no {args.base_tf} data")
            continue

        t0 = time.monotonic()
        result = run_zone_audit(data_by_tf, base_tf=args.base_tf, symbol=symbol)
        elapsed = time.monotonic() - t0
        print(f"  Done in {elapsed:.1f}s — {len(result.lifecycle_records)} zones tracked")

        # Print summary
        for report in result.reports:
            print(f"\n  {report.tf} {report.side}:")
            print(f"    Created: {report.zones_created}  Broken: {report.zones_broken}")
            print(f"    Retested: {report.zones_retested}  Untouched: {report.zones_untouched}")
            print(f"    Avg tests before break: {report.avg_tests_before_break:.1f}")
            print(f"    Avg alive: {report.avg_zones_alive:.1f}  Max alive: {report.max_zones_alive}")

        # Save lifecycle records
        if result.lifecycle_records:
            records_df = pd.DataFrame([{
                "tf": r.tf, "side": r.side,
                "origin_time": r.origin_time,
                "break_time": r.break_time,
                "test_count": r.test_count,
                "first_test_time": r.first_test_time,
                "replacement_count": r.replacement_count,
                "lifespan_bars": r.lifespan_bars,
                "birth_period_pattern": r.birth_period_pattern,
                "birth_price_distance": r.birth_price_distance,
            } for r in result.lifecycle_records])
            out_path = f"{args.output}/{symbol}_zone_audit.csv"
            records_df.to_csv(out_path, index=False)
            print(f"\n  Saved to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the audit on GBPUSD to validate**

Run: `python scripts/run_zone_audit.py --symbols GBPUSD --output results`
Expected: Completes in ~240s (same as sweep), prints zone statistics per TF

- [ ] **Step 7: Commit**

```bash
git add src/iora/diagnostics/zone_audit_runner.py scripts/run_zone_audit.py tests/diagnostics/test_zone_audit_runner.py
git commit -m "feat(diagnostics): add zone audit runner with CLI and per-bar population tracking"
```

---

### Task 8: Integration test — verify existing sweep still works

**Files:**
- Test: `tests/strategy/test_sweep_integration.py`

After changing the zone engine lifecycle, the existing strategy sweep must still produce results. This is a regression check.

- [ ] **Step 1: Run existing sweep integration tests**

Run: `pytest tests/strategy/test_sweep_integration.py -v`
Expected: All 3 tests pass. Trade counts may change (zones live longer → more fires possible) but the tests check for `> 0` trades, not exact counts.

- [ ] **Step 2: Run the existing sweep script to compare**

Run: `python scripts/run_sweep.py --symbols GBPUSD --output results/gbpusd_sweep_v2.csv`
Expected: Completes successfully. Compare trade counts to `results/gbpusd_sweep.csv` — expect different numbers since zones no longer expire.

- [ ] **Step 3: Commit any test adjustments if needed**

If existing tests need threshold adjustments due to lifecycle change, update them and commit:

```bash
git add tests/strategy/test_sweep_integration.py
git commit -m "test: adjust sweep integration tests for new zone lifecycle"
```
