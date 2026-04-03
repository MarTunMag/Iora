# Retest Entry System — Level 3: Opportunity Counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Count retest events (wick touch, body close, near-miss, break-through) across all TF pairs and filter dimensions to reveal the opportunity landscape before any win/loss logic.

**Architecture:** Diagnostic module running alongside the zone engine in the per-bar loop (same pattern as Level 1/2 runners). The opportunity counter classifies each zone interaction into touch type, bias alignment, zone role, age bucket, and test count — producing an opportunity matrix DataFrame. The runner loops over multiple entry TFs (M1, M5, M15, H1) in separate engine passes to cover all 8 spec TF pairs, merging events into a single result.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest. Existing engine/orchestrator patterns.

**Spec:** `docs/superpowers/specs/2026-04-02-retest-entry-system-design.md` (Level 3 section, lines 159-212)

**Scope note:** This plan covers the data pipeline only (event classification + counting + runner + CLI). Flask visualization (opportunity heatmap, near-miss ratio charts) is deferred to the Phase 5 Flask plan.

---

## File Structure

```
src/iora/diagnostics/
    opportunity_counter.py        # Event classification functions + OpportunityEvent dataclass
    opportunity_runner.py         # Runner: engine loop → per-bar event detection → OpportunityResult

tests/diagnostics/
    test_opportunity_counter.py   # Unit tests for classification functions (synthetic data)
    test_opportunity_runner.py    # Integration test on real GBPUSD data

scripts/
    run_opportunity_count.py      # CLI: run opportunity counter for a symbol, print summary + save CSV
```

**Dependency map:**
- `opportunity_counter.py` depends on: `push_zone_models.py` (PushZone), `bias_timeline.py` (BiasStateRecord, `_bias_direction`)
- `opportunity_runner.py` depends on: `opportunity_counter.py`, `bias_timeline.py` + `bias_timeline_runner.py` (collect_bias_state, _compute_atr), `push_zone_engine.py` (engine loop)

---

### Task 1: Touch type classification

**Files:**
- Create: `src/iora/diagnostics/opportunity_counter.py`
- Test: `tests/diagnostics/test_opportunity_counter.py`

Pure functions that classify a bar's interaction with a zone. No engine dependency.

- [ ] **Step 1: Write failing tests for `classify_touch`**

```python
# tests/diagnostics/test_opportunity_counter.py
"""Unit tests for opportunity counter classification functions."""
from __future__ import annotations

import pandas as pd

from iora.diagnostics.opportunity_counter import classify_touch
from iora.engine.push_zone_models import PushZone


def _demand(top=1.3000, bottom=1.2980):
    return PushZone(top=top, bottom=bottom, is_supply=False,
                    origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")


def _supply(top=1.3100, bottom=1.3080):
    return PushZone(top=top, bottom=bottom, is_supply=True,
                    origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")


class TestClassifyTouch:
    def test_wick_touch_demand(self):
        # Low enters demand zone, close stays above
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.2990, close=1.3020)
        assert result == "wick_touch"

    def test_body_close_demand(self):
        # Close inside demand zone
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.2970, close=1.2990)
        assert result == "body_close"

    def test_break_through_demand(self):
        # Close below demand zone bottom (blew through)
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3010, low=1.2960, close=1.2970)
        assert result == "break_through"

    def test_wick_touch_supply(self):
        # High enters supply zone, close stays below
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3090, low=1.3050, close=1.3060)
        assert result == "wick_touch"

    def test_body_close_supply(self):
        # Close inside supply zone
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3110, low=1.3070, close=1.3090)
        assert result == "body_close"

    def test_break_through_supply(self):
        # Close above supply zone top
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3120, low=1.3070, close=1.3110)
        assert result == "break_through"

    def test_no_touch(self):
        # Price never reaches zone
        z = _demand(top=1.3000, bottom=1.2980)
        result = classify_touch(z, high=1.3050, low=1.3010, close=1.3030)
        assert result is None

    def test_no_touch_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        result = classify_touch(z, high=1.3070, low=1.3050, close=1.3060)
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v -k "TestClassifyTouch"`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `classify_touch`**

```python
# src/iora/diagnostics/opportunity_counter.py
"""Opportunity Counter — Level 3 diagnostics.

Counts retest events per TF pair per filter dimension.
No strategy, no trades — purely counting opportunities.
"""
from __future__ import annotations


def classify_touch(
    zone,  # PushZone
    high: float,
    low: float,
    close: float,
) -> str | None:
    """Classify a bar's interaction with a zone.

    Returns: "wick_touch", "body_close", "break_through", or None (no interaction).

    - wick_touch: price entered zone but close stayed outside
    - body_close: close is inside zone boundaries
    - break_through: price entered zone AND close went through the other side
    """
    if zone.is_supply:
        entered = high >= zone.bottom
        if not entered:
            return None
        if close > zone.top:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close < zone.bottom
    else:  # demand
        entered = low <= zone.top
        if not entered:
            return None
        if close < zone.bottom:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close > zone.top
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/opportunity_counter.py tests/diagnostics/test_opportunity_counter.py
git commit -m "feat(diagnostics): add touch type classification (Level 3)"
```

---

### Task 2: Near-miss detection

**Files:**
- Modify: `src/iora/diagnostics/opportunity_counter.py`
- Test: `tests/diagnostics/test_opportunity_counter.py`

- [ ] **Step 1: Write failing tests for `is_near_miss`**

```python
# Add to tests/diagnostics/test_opportunity_counter.py
from iora.diagnostics.opportunity_counter import is_near_miss


class TestIsNearMiss:
    def test_near_miss_demand(self):
        # Low came close to demand zone top but didn't enter
        z = _demand(top=1.3000, bottom=1.2980)
        # zone_thickness = 0.002, threshold = min(0.0005, 0.001) = 0.0005
        # floor = 0.0001 (1 pip), so threshold = max(0.0005, 0.0001) = 0.0005
        # low = 1.3003 → distance = 1.3003 - 1.3000 = 0.0003 < 0.0005 → near miss
        result = is_near_miss(z, high=1.3050, low=1.3003, atr=0.002, pip_size=0.0001)
        assert result is True

    def test_not_near_miss_too_far(self):
        z = _demand(top=1.3000, bottom=1.2980)
        # low = 1.3020 → distance = 0.0020 > threshold → not near miss
        result = is_near_miss(z, high=1.3050, low=1.3020, atr=0.002, pip_size=0.0001)
        assert result is False

    def test_near_miss_supply(self):
        z = _supply(top=1.3100, bottom=1.3080)
        # high = 1.3077 → distance = 1.3080 - 1.3077 = 0.0003 < threshold
        result = is_near_miss(z, high=1.3077, low=1.3050, atr=0.002, pip_size=0.0001)
        assert result is True

    def test_touched_not_near_miss(self):
        # Price actually entered zone — not a near miss
        z = _demand(top=1.3000, bottom=1.2980)
        result = is_near_miss(z, high=1.3050, low=1.2990, atr=0.002, pip_size=0.0001)
        assert result is False

    def test_pip_floor_prevents_sub_pip(self):
        # Very thin zone on M1: thickness=0.0002, ATR=0.0005
        z = _demand(top=1.3000, bottom=1.2998)
        # threshold = max(min(0.00005, 0.00025), 0.0001) = max(0.00005, 0.0001) = 0.0001
        # low = 1.30005 → distance = 0.00005 < 0.0001 → near miss
        result = is_near_miss(z, high=1.3050, low=1.30005, atr=0.0005, pip_size=0.0001)
        assert result is True

    def test_jpy_pip_size(self):
        # JPY pair: pip_size = 0.01
        z = PushZone(top=150.00, bottom=149.80, is_supply=False,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="H1")
        # thickness = 0.20, atr = 0.50
        # threshold = max(min(0.05, 0.25), 0.01) = max(0.05, 0.01) = 0.05
        # low = 150.03 → distance = 0.03 < 0.05 → near miss
        result = is_near_miss(z, high=150.50, low=150.03, atr=0.50, pip_size=0.01)
        assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v -k "TestIsNearMiss"`
Expected: FAIL

- [ ] **Step 3: Implement `is_near_miss`**

Add to `src/iora/diagnostics/opportunity_counter.py`:

```python
def is_near_miss(
    zone,  # PushZone
    high: float,
    low: float,
    atr: float,
    pip_size: float = 0.0001,
) -> bool:
    """Check if price came close to a zone without touching it.

    Threshold: max(min(0.25 * zone_thickness, 0.5 * ATR), 1.0 * pip_size).
    The pip floor prevents sub-pip thresholds on very thin zones.
    """
    zone_thickness = zone.top - zone.bottom
    threshold = max(min(0.25 * zone_thickness, 0.5 * atr), pip_size)

    if zone.is_supply:
        # Price must NOT have entered (high < zone.bottom)
        if high >= zone.bottom:
            return False
        distance = zone.bottom - high
    else:  # demand
        # Price must NOT have entered (low > zone.top)
        if low <= zone.top:
            return False
        distance = low - zone.top

    return distance <= threshold
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/opportunity_counter.py tests/diagnostics/test_opportunity_counter.py
git commit -m "feat(diagnostics): add near-miss detection with ATR-relative threshold"
```

---

### Task 3: Zone role classification and dimension helpers

**Files:**
- Modify: `src/iora/diagnostics/opportunity_counter.py`
- Test: `tests/diagnostics/test_opportunity_counter.py`

Zone role (continuation/pullback) requires comparing a zone's `swing_cls` to the previous same-side zone on the same TF. Age bucket and bias alignment are simple categorizations.

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/diagnostics/test_opportunity_counter.py
from iora.diagnostics.opportunity_counter import (
    classify_zone_role, classify_age_bucket, classify_bias_alignment,
    classify_test_count,
)


class TestClassifyZoneRole:
    def test_push(self):
        z = _demand()
        z.is_push = True
        assert classify_zone_role(z, prev_swing_cls="") == "push"

    def test_reversal(self):
        z = _demand()
        z.is_reversal = True
        assert classify_zone_role(z, prev_swing_cls="") == "reversal"

    def test_continuation_hh_after_hh(self):
        z = _demand()
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "continuation"

    def test_continuation_ll_after_ll(self):
        z = _supply()
        z.swing_cls = "LL"
        assert classify_zone_role(z, prev_swing_cls="LL") == "continuation"

    def test_pullback_lh_after_hh(self):
        z = _supply()
        z.swing_cls = "LH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "pullback"

    def test_pullback_hl_after_ll(self):
        z = _demand()
        z.swing_cls = "HL"
        assert classify_zone_role(z, prev_swing_cls="LL") == "pullback"

    def test_no_prev_unknown(self):
        z = _demand()
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="") == "unknown"

    def test_push_takes_priority(self):
        # Push flag overrides swing_cls classification
        z = _demand()
        z.is_push = True
        z.swing_cls = "HH"
        assert classify_zone_role(z, prev_swing_cls="HH") == "push"


class TestClassifyAgeBucket:
    def test_fresh(self):
        assert classify_age_bucket(5) == "fresh"

    def test_young(self):
        assert classify_age_bucket(30) == "young"

    def test_mature(self):
        assert classify_age_bucket(100) == "mature"

    def test_old(self):
        assert classify_age_bucket(250) == "old"

    def test_boundary_fresh_young(self):
        assert classify_age_bucket(10) == "fresh"
        assert classify_age_bucket(11) == "young"

    def test_boundary_young_mature(self):
        assert classify_age_bucket(50) == "young"
        assert classify_age_bucket(51) == "mature"

    def test_boundary_mature_old(self):
        assert classify_age_bucket(200) == "mature"
        assert classify_age_bucket(201) == "old"


class TestClassifyBiasAlignment:
    def test_with_daily_demand_bull(self):
        # Demand zone touch with bullish daily bias = with_daily
        assert classify_bias_alignment(is_supply=False, d_bias="HH_HL_bull_push") == "with_daily"

    def test_against_daily_demand_bear(self):
        # Demand zone touch with bearish daily = against
        assert classify_bias_alignment(is_supply=False, d_bias="LH_LL_bear_push") == "against_daily"

    def test_with_daily_supply_bear(self):
        # Supply zone touch with bearish daily = with_daily
        assert classify_bias_alignment(is_supply=True, d_bias="LH_LL_bear_push") == "with_daily"

    def test_against_daily_supply_bull(self):
        assert classify_bias_alignment(is_supply=True, d_bias="HH_HL_bull_push") == "against_daily"

    def test_at_transition(self):
        assert classify_bias_alignment(is_supply=False, d_bias="HH_HL_bull_push",
                                       is_transition=True) == "at_transition"

    def test_neutral_on_unknown(self):
        assert classify_bias_alignment(is_supply=False, d_bias="unknown") == "neutral"

    def test_neutral_on_compression(self):
        assert classify_bias_alignment(is_supply=False, d_bias="LH_HL_compression") == "neutral"


class TestClassifyTestCount:
    def test_first_touch(self):
        assert classify_test_count(0) == "first_touch"

    def test_retested_1(self):
        assert classify_test_count(1) == "retested_1"

    def test_retested_2plus(self):
        assert classify_test_count(2) == "retested_2plus"
        assert classify_test_count(5) == "retested_2plus"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v -k "TestClassifyZone or TestClassifyAge or TestClassifyBias or TestClassifyTest"`
Expected: FAIL

- [ ] **Step 3: Implement classification functions**

Add to `src/iora/diagnostics/opportunity_counter.py`:

```python
# Same-direction swing_cls pairs (continuation)
_SAME_DIR = {
    ("HH", "HH"), ("HL", "HL"), ("LL", "LL"), ("LH", "LH"),
    ("HH", "HL"), ("HL", "HH"),  # Both bullish
    ("LL", "LH"), ("LH", "LL"),  # Both bearish
}

# Import bias direction sets from bias_timeline (single source of truth)
from iora.diagnostics.bias_timeline import _BULLISH_BIASES, _BEARISH_BIASES


def classify_zone_role(
    zone,  # PushZone
    prev_swing_cls: str,
) -> str:
    """Classify zone's structural role.

    Returns: "push", "reversal", "continuation", "pullback", "unknown".
    Push and reversal are from zone flags. Continuation/pullback derived
    from swing_cls sequence with previous same-side zone.
    """
    if zone.is_push:
        return "push"
    if zone.is_reversal:
        return "reversal"
    if not prev_swing_cls or not zone.swing_cls:
        return "unknown"
    if (zone.swing_cls, prev_swing_cls) in _SAME_DIR:
        return "continuation"
    return "pullback"


def classify_age_bucket(age_bars: int) -> str:
    """Classify zone age into bucket. Age is in zone's own TF bars.

    fresh: 0-10, young: 11-50, mature: 51-200, old: 201+
    """
    if age_bars <= 10:
        return "fresh"
    if age_bars <= 50:
        return "young"
    if age_bars <= 200:
        return "mature"
    return "old"


def classify_bias_alignment(
    is_supply: bool,
    d_bias: str,
    is_transition: bool = False,
) -> str:
    """Classify whether a zone touch aligns with daily bias.

    Returns: "with_daily", "against_daily", "at_transition", "neutral".
    Demand + bullish = with_daily. Supply + bearish = with_daily.
    """
    if is_transition:
        return "at_transition"

    if d_bias in _BULLISH_BIASES:
        return "with_daily" if not is_supply else "against_daily"
    if d_bias in _BEARISH_BIASES:
        return "with_daily" if is_supply else "against_daily"
    return "neutral"


def classify_test_count(test_count: int) -> str:
    """Classify zone's test history at time of this touch.

    first_touch: test_count=0 (this is the first touch).
    retested_1: test_count=1 (been touched once before).
    retested_2plus: test_count>=2.
    """
    if test_count == 0:
        return "first_touch"
    if test_count == 1:
        return "retested_1"
    return "retested_2plus"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/opportunity_counter.py tests/diagnostics/test_opportunity_counter.py
git commit -m "feat(diagnostics): add zone role, age, bias, and test count classifiers"
```

---

### Task 4: OpportunityEvent dataclass and per-bar event detection

**Files:**
- Modify: `src/iora/diagnostics/opportunity_counter.py`
- Test: `tests/diagnostics/test_opportunity_counter.py`

- [ ] **Step 1: Write failing tests for `OpportunityEvent` and `detect_events`**

```python
# Add to tests/diagnostics/test_opportunity_counter.py
from iora.diagnostics.opportunity_counter import OpportunityEvent, detect_events
from iora.diagnostics.bias_timeline import BiasStateRecord
from iora.engine.push_zone_models import PushZoneTickState
from math import inf


class TestOpportunityEvent:
    def test_fields(self):
        evt = OpportunityEvent(
            timestamp=pd.Timestamp("2025-06-01"),
            zone_tf="H1", entry_tf="M5", tf_pair="M5@H1",
            touch_type="wick_touch", zone_side="demand",
            zone_role="push", age_bucket="fresh",
            bias_alignment="with_daily", test_count_cls="first_touch",
            zone_age_bars=5, zone_test_count=0,
            bias_strength=3, price_distance_at_touch=1.5,
        )
        assert evt.tf_pair == "M5@H1"
        assert evt.touch_type == "wick_touch"


class TestDetectEvents:
    def _make_bias_rec(self, d_bias="HH_HL_bull_push", strength=2, transition=False):
        return BiasStateRecord(
            timestamp=pd.Timestamp("2025-06-01"),
            d_bias=d_bias, d_bias_strength=strength,
            is_bias_transition=transition,
        )

    def test_detects_wick_touch(self):
        z = _demand(top=1.3000, bottom=1.2980)
        z.swing_cls = "HL"
        ts = PushZoneTickState()
        ts.demand_zones = [z]
        bias = self._make_bias_rec()

        events = detect_events(
            tick_states={"H1": ts},
            entry_tf="M5",
            high=1.3050, low=1.2990, close=1.3020,
            timestamp=pd.Timestamp("2025-06-01"),
            bias_rec=bias, atr=0.002, pip_size=0.0001,
            bar_idx=100, prev_swing_cls={"H1": {"demand": "HH"}},
        )
        assert len(events) == 1
        assert events[0].touch_type == "wick_touch"
        assert events[0].tf_pair == "M5@H1"
        assert events[0].bias_alignment == "with_daily"

    def test_detects_near_miss(self):
        z = _demand(top=1.3000, bottom=1.2980)
        ts = PushZoneTickState()
        ts.demand_zones = [z]
        bias = self._make_bias_rec()

        events = detect_events(
            tick_states={"H1": ts},
            entry_tf="M5",
            high=1.3050, low=1.3003, close=1.3020,
            timestamp=pd.Timestamp("2025-06-01"),
            bias_rec=bias, atr=0.002, pip_size=0.0001,
            bar_idx=100, prev_swing_cls={},
        )
        assert len(events) == 1
        assert events[0].touch_type == "near_miss"

    def test_no_events_when_price_far(self):
        z = _demand(top=1.3000, bottom=1.2980)
        ts = PushZoneTickState()
        ts.demand_zones = [z]
        bias = self._make_bias_rec()

        events = detect_events(
            tick_states={"H1": ts},
            entry_tf="M5",
            high=1.3100, low=1.3050, close=1.3080,
            timestamp=pd.Timestamp("2025-06-01"),
            bias_rec=bias, atr=0.002, pip_size=0.0001,
            bar_idx=100, prev_swing_cls={},
        )
        assert len(events) == 0

    def test_multiple_tfs_multiple_events(self):
        z_h1 = _demand(top=1.3000, bottom=1.2980)
        z_h4 = _supply(top=1.3100, bottom=1.3080)
        ts_h1 = PushZoneTickState()
        ts_h1.demand_zones = [z_h1]
        ts_h4 = PushZoneTickState()
        ts_h4.supply_zones = [z_h4]
        bias = self._make_bias_rec()

        events = detect_events(
            tick_states={"H1": ts_h1, "H4": ts_h4},
            entry_tf="M5",
            high=1.3090, low=1.2990, close=1.3020,
            timestamp=pd.Timestamp("2025-06-01"),
            bias_rec=bias, atr=0.002, pip_size=0.0001,
            bar_idx=100, prev_swing_cls={},
        )
        # Should detect H1 demand touch + H4 supply touch
        assert len(events) == 2
        tfs = {e.tf_pair for e in events}
        assert "M5@H1" in tfs
        assert "M5@H4" in tfs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v -k "TestOpportunity or TestDetect"`
Expected: FAIL

- [ ] **Step 3: Implement `OpportunityEvent` and `detect_events`**

Add to `src/iora/diagnostics/opportunity_counter.py`:

```python
from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class OpportunityEvent:
    """A single retest/near-miss/break-through event."""
    timestamp: pd.Timestamp
    zone_tf: str          # TF of the zone being touched
    entry_tf: str         # TF of the bar detecting the touch
    tf_pair: str          # "entry@context" notation
    touch_type: str       # wick_touch, body_close, near_miss, break_through
    zone_side: str        # "supply" or "demand"
    zone_role: str        # push, continuation, pullback, reversal, unknown
    age_bucket: str       # fresh, young, mature, old
    bias_alignment: str   # with_daily, against_daily, at_transition, neutral
    test_count_cls: str   # first_touch, retested_1, retested_2plus
    zone_age_bars: int    # Raw age in zone's TF bars
    zone_test_count: int  # Raw test count at time of event
    bias_strength: int    # Daily bias strength (1-3)
    price_distance_at_touch: float  # ATR-relative distance from close to zone midpoint
    replacement_count: int = 0        # Zone's replacement count at event time
    birth_bias_d: str = "unknown"     # Daily bias at zone creation
    birth_period_pattern: str = "unknown"  # Period pattern at zone creation
    birth_price_distance: float = 0.0  # ATR distance from zone to price at creation


# Valid TF pairs: entry@context
_TF_PAIRS: dict[str, list[str]] = {
    "M1": ["M5", "M15"],
    "M5": ["M15", "H1"],
    "M15": ["H1", "H4"],
    "H1": ["H4", "D1"],
}


def detect_events(
    tick_states: dict,  # {tf: PushZoneTickState}
    entry_tf: str,
    high: float,
    low: float,
    close: float,
    timestamp: pd.Timestamp,
    bias_rec,  # BiasStateRecord
    atr: float,
    pip_size: float,
    bar_idx: int,
    prev_swing_cls: dict,  # {tf: {side: last_swing_cls}}
) -> list[OpportunityEvent]:
    """Detect all opportunity events for one bar across all context TFs.

    For each valid TF pair (entry_tf@context_tf), checks all active zones
    on the context TF for touches, near-misses, and break-throughs.
    """
    context_tfs = _TF_PAIRS.get(entry_tf, [])
    events: list[OpportunityEvent] = []

    for ctx_tf in context_tfs:
        ts = tick_states.get(ctx_tf)
        if ts is None:
            continue

        for zone_list, side in [(ts.demand_zones, "demand"), (ts.supply_zones, "supply")]:
            for z in zone_list:
                touch = classify_touch(z, high, low, close)

                if touch is not None:
                    events.append(_build_event(
                        z, ctx_tf, entry_tf, touch, side,
                        timestamp, bias_rec, atr, close, prev_swing_cls,
                    ))
                elif is_near_miss(z, high, low, atr, pip_size):
                    events.append(_build_event(
                        z, ctx_tf, entry_tf, "near_miss", side,
                        timestamp, bias_rec, atr, close, prev_swing_cls,
                    ))

    return events


def _build_event(
    zone, ctx_tf: str, entry_tf: str, touch_type: str, side: str,
    timestamp: pd.Timestamp, bias_rec, atr: float, close: float,
    prev_swing_cls: dict,
) -> OpportunityEvent:
    """Build an OpportunityEvent from zone + bar context."""
    age_seconds = (timestamp - zone.origin_time).total_seconds()
    tf_seconds = _tf_to_seconds(ctx_tf)
    age_bars = int(age_seconds / tf_seconds) if tf_seconds > 0 else 0

    prev_cls = prev_swing_cls.get(ctx_tf, {}).get(side, "")
    zone_mid = (zone.top + zone.bottom) / 2.0
    price_dist = abs(close - zone_mid) / atr if atr > 0 else 0.0

    return OpportunityEvent(
        timestamp=timestamp,
        zone_tf=ctx_tf,
        entry_tf=entry_tf,
        tf_pair=f"{entry_tf}@{ctx_tf}",
        touch_type=touch_type,
        zone_side=side,
        zone_role=classify_zone_role(zone, prev_cls),
        age_bucket=classify_age_bucket(age_bars),
        bias_alignment=classify_bias_alignment(
            zone.is_supply, bias_rec.d_bias, bias_rec.is_bias_transition,
        ),
        test_count_cls=classify_test_count(zone.test_count),
        zone_age_bars=age_bars,
        zone_test_count=zone.test_count,
        bias_strength=bias_rec.d_bias_strength,
        price_distance_at_touch=price_dist,
        replacement_count=zone.replacement_count,
        birth_bias_d=zone.birth_bias_d,
        birth_period_pattern=zone.birth_period_pattern,
        birth_price_distance=zone.birth_price_distance,
    )


def _tf_to_seconds(tf: str) -> int:
    """Convert TF label to seconds per bar."""
    return {
        "M1": 60, "M5": 300, "M15": 900, "H1": 3600,
        "H4": 14400, "D1": 86400, "W1": 604800,
    }.get(tf, 3600)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_opportunity_counter.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/opportunity_counter.py tests/diagnostics/test_opportunity_counter.py
git commit -m "feat(diagnostics): add OpportunityEvent and per-bar event detection"
```

---

### Task 5: Opportunity runner

**Files:**
- Create: `src/iora/diagnostics/opportunity_runner.py`
- Test: `tests/diagnostics/test_opportunity_runner.py`

Combines zone engine + bias collection + opportunity detection in a single bar loop. Follows the bias_timeline_runner pattern but also collects events.

- [ ] **Step 1: Write failing integration test**

```python
# tests/diagnostics/test_opportunity_runner.py
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
        # Each TF pair should have touch type counts
        first = list(summary.values())[0]
        assert "wick_touch" in first or "total" in first

    def test_opportunity_matrix(self, gbpusd_opp):
        matrix = gbpusd_opp.opportunity_matrix()
        assert len(matrix) > 0
        assert "count" in matrix.columns
        assert "tf_pair" in matrix.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_opportunity_runner.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `opportunity_runner.py`**

```python
# src/iora/diagnostics/opportunity_runner.py
"""Opportunity Counter Runner — runs engine + bias + event detection in one pass.

Produces OpportunityResult with per-event records and aggregate statistics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.diagnostics.bias_timeline import collect_bias_state
from iora.diagnostics.bias_timeline_runner import _compute_atr
from iora.diagnostics.opportunity_counter import OpportunityEvent, detect_events


# Pip size lookup (mirrors trade_converter.py)
def _get_pip_size(symbol: str) -> float:
    symbol = symbol.upper()
    if symbol.endswith("JPY") or symbol in ("XAUUSD",):
        return 0.01
    if symbol in ("DE40", "US30", "US500", "US100", "UK100", "JP225"):
        return 1.0
    if symbol in ("BTCUSD", "ETHUSD"):
        return 1.0
    return 0.0001


@dataclass(slots=True)
class OpportunityResult:
    """Full opportunity counter output for one symbol."""
    symbol: str
    events: list[OpportunityEvent] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert events to DataFrame."""
        if not self.events:
            return pd.DataFrame()
        rows = []
        for e in self.events:
            rows.append({
                "timestamp": e.timestamp,
                "zone_tf": e.zone_tf,
                "entry_tf": e.entry_tf,
                "tf_pair": e.tf_pair,
                "touch_type": e.touch_type,
                "zone_side": e.zone_side,
                "zone_role": e.zone_role,
                "age_bucket": e.age_bucket,
                "bias_alignment": e.bias_alignment,
                "test_count_cls": e.test_count_cls,
                "zone_age_bars": e.zone_age_bars,
                "zone_test_count": e.zone_test_count,
                "bias_strength": e.bias_strength,
                "price_distance_at_touch": e.price_distance_at_touch,
                "replacement_count": e.replacement_count,
                "birth_bias_d": e.birth_bias_d,
                "birth_period_pattern": e.birth_period_pattern,
                "birth_price_distance": e.birth_price_distance,
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict[str, dict[str, int]]:
        """Summary counts per TF pair: touch types + bias alignment."""
        result: dict[str, dict[str, int]] = {}
        for e in self.events:
            if e.tf_pair not in result:
                result[e.tf_pair] = {
                    "wick_touch": 0, "body_close": 0,
                    "near_miss": 0, "break_through": 0, "total": 0,
                    "with_daily": 0, "against_daily": 0,
                    "at_transition": 0, "neutral": 0,
                }
            result[e.tf_pair][e.touch_type] = result[e.tf_pair].get(e.touch_type, 0) + 1
            result[e.tf_pair][e.bias_alignment] = result[e.tf_pair].get(e.bias_alignment, 0) + 1
            result[e.tf_pair]["total"] += 1
        return result

    def opportunity_matrix(self) -> pd.DataFrame:
        """Aggregate counts per dimension combination."""
        df = self.to_dataframe()
        if df.empty:
            return df
        group_cols = ["tf_pair", "touch_type", "bias_alignment",
                      "zone_role", "age_bucket", "test_count_cls"]
        matrix = (
            df.groupby(group_cols, observed=True)
            .agg(
                count=("timestamp", "count"),
                avg_zone_age=("zone_age_bars", "mean"),
                avg_bias_strength=("bias_strength", "mean"),
                avg_price_distance_at_touch=("price_distance_at_touch", "mean"),
            )
            .reset_index()
        )
        return matrix


def run_opportunity_counter(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> OpportunityResult:
    """Run zone engine + bias + opportunity detection in one pass.

    Uses base_tf as the entry TF. For all 8 spec TF pairs, call
    run_opportunity_counter_all_tfs() which loops over entry TFs.
    """
    return _run_single_entry_tf(data_by_tf, base_tf, symbol, period_depth)


def run_opportunity_counter_all_tfs(
    data_by_tf: dict[str, pd.DataFrame],
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> OpportunityResult:
    """Run opportunity counter for ALL entry TFs, merging results.

    Loops over M1, M5, M15, H1 as entry TFs (if data is available),
    producing events for all 8 spec TF pairs.
    """
    entry_tfs = ["M1", "M5", "M15", "H1"]
    all_events: list[OpportunityEvent] = []

    for entry_tf in entry_tfs:
        if entry_tf not in data_by_tf:
            continue
        result = _run_single_entry_tf(data_by_tf, entry_tf, symbol, period_depth)
        all_events.extend(result.events)

    return OpportunityResult(symbol=symbol, events=all_events)


def _run_single_entry_tf(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    symbol: str,
    period_depth: int,
) -> OpportunityResult:
    """Run opportunity detection for a single entry TF."""
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    base_df = data_by_tf[base_tf]
    atr_series = _compute_atr(base_df, period=14)
    pip_size = _get_pip_size(symbol)

    all_events: list[OpportunityEvent] = []
    prev_d_bias = ""

    # Track previous swing_cls per TF per side for zone role classification
    prev_swing_cls: dict[str, dict[str, str]] = {}

    bar_idx = 0
    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        # Get ATR for this bar
        atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
        if np.isnan(atr_val):
            atr_val = 0.002

        # Collect bias state
        bias_rec = collect_bias_state(
            state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
        )
        prev_d_bias = bias_rec.d_bias

        # Detect events
        events = detect_events(
            tick_states=state.tick_states,
            entry_tf=base_tf,
            high=ctx.high, low=ctx.low, close=ctx.close,
            timestamp=ctx.timestamp,
            bias_rec=bias_rec, atr=atr_val, pip_size=pip_size,
            bar_idx=bar_idx, prev_swing_cls=prev_swing_cls,
        )
        all_events.extend(events)

        # Update prev_swing_cls tracking
        for tf, ts in state.tick_states.items():
            if tf not in prev_swing_cls:
                prev_swing_cls[tf] = {"supply": "", "demand": ""}
            if ts.supply_zones and ts.supply_zones[-1].swing_cls:
                prev_swing_cls[tf]["supply"] = ts.supply_zones[-1].swing_cls
            if ts.demand_zones and ts.demand_zones[-1].swing_cls:
                prev_swing_cls[tf]["demand"] = ts.demand_zones[-1].swing_cls

        bar_idx += 1

    return OpportunityResult(symbol=symbol, events=all_events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_opportunity_runner.py -v --timeout=300`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/opportunity_runner.py tests/diagnostics/test_opportunity_runner.py
git commit -m "feat(diagnostics): add opportunity counter runner (Level 3)"
```

---

### Task 6: CLI script

**Files:**
- Create: `scripts/run_opportunity_count.py`

- [ ] **Step 1: Write CLI script**

```python
#!/usr/bin/env python
"""Run opportunity counter for a symbol and print summary.

Usage:
    python scripts/run_opportunity_count.py GBPUSD
    python scripts/run_opportunity_count.py GBPUSD --base-tf M5 --save-csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.opportunity_runner import (
    run_opportunity_counter, run_opportunity_counter_all_tfs,
)


def main():
    parser = argparse.ArgumentParser(description="Run opportunity counter")
    parser.add_argument("symbol", help="Symbol to analyze (e.g., GBPUSD)")
    parser.add_argument("--base-tf", default="M5", help="Base/entry timeframe (default: M5)")
    parser.add_argument("--tfs", default="M5,H1,H4,D1,W1", help="Comma-separated TFs")
    parser.add_argument("--save-csv", action="store_true", help="Save events to CSV")
    parser.add_argument("--all-tfs", action="store_true",
                        help="Run all entry TFs (M1,M5,M15,H1) for full 8-pair coverage")
    args = parser.parse_args()

    storage = ParquetStorage("data")
    tfs = [t.strip() for t in args.tfs.split(",")]

    data_by_tf = {}
    for tf in tfs:
        df = storage.load(args.symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  Loaded {tf}: {len(df)} bars")
        else:
            print(f"  {tf}: no data")

    if args.base_tf not in data_by_tf:
        print(f"Error: base TF {args.base_tf} has no data")
        sys.exit(1)

    if args.all_tfs:
        # Ensure all entry TFs are loaded for full coverage
        all_tfs = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]
        for tf in all_tfs:
            if tf not in data_by_tf:
                df = storage.load(args.symbol, tf)
                if df is not None and not df.empty:
                    data_by_tf[tf] = df
                    print(f"  Loaded {tf}: {len(df)} bars")
        print(f"\nRunning opportunity counter for {args.symbol} (ALL entry TFs)...")
        result = run_opportunity_counter_all_tfs(data_by_tf, symbol=args.symbol)
    else:
        print(f"\nRunning opportunity counter for {args.symbol} (entry TF: {args.base_tf})...")
        result = run_opportunity_counter(
            data_by_tf, base_tf=args.base_tf, symbol=args.symbol,
        )

    print(f"\n=== Opportunity Count: {args.symbol} ===")
    print(f"Total events: {len(result.events)}")

    summary = result.summary()
    for tf_pair, counts in sorted(summary.items()):
        print(f"\n{tf_pair}:")
        print(f"  Wick touches:    {counts.get('wick_touch', 0):>6}")
        print(f"  Body closes:     {counts.get('body_close', 0):>6}")
        print(f"  Near-misses:     {counts.get('near_miss', 0):>6}")
        print(f"  Break-throughs:  {counts.get('break_through', 0):>6}")
        print(f"  Total:           {counts.get('total', 0):>6}")
        print(f"  --- Bias alignment ---")
        print(f"  With daily:      {counts.get('with_daily', 0):>6}")
        print(f"  Against daily:   {counts.get('against_daily', 0):>6}")
        print(f"  At transition:   {counts.get('at_transition', 0):>6}")
        print(f"  Neutral:         {counts.get('neutral', 0):>6}")

    if args.save_csv:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{args.symbol.lower()}_opportunities.csv"
        df = result.to_dataframe()
        df.to_csv(out_path, index=False)
        print(f"\nSaved {len(df)} events to {out_path}")

        # Also save opportunity matrix
        matrix = result.opportunity_matrix()
        matrix_path = out_dir / f"{args.symbol.lower()}_opportunity_matrix.csv"
        matrix.to_csv(matrix_path, index=False)
        print(f"Saved matrix ({len(matrix)} combos) to {matrix_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `python scripts/run_opportunity_count.py GBPUSD`
Expected: Summary output with per-TF-pair counts.

- [ ] **Step 3: Commit**

```bash
git add scripts/run_opportunity_count.py
git commit -m "feat(diagnostics): add opportunity counter CLI script"
```

---

## Verification Checklist

After all tasks are complete:

1. `pytest tests/diagnostics/test_opportunity_counter.py -v` — all unit tests pass
2. `pytest tests/diagnostics/test_opportunity_runner.py -v --timeout=300` — integration test passes
3. `python scripts/run_opportunity_count.py GBPUSD` — produces output
4. No changes to existing engine files — purely additive (new files only)
5. All existing tests still pass: `pytest tests/diagnostics/ -v --timeout=300`
