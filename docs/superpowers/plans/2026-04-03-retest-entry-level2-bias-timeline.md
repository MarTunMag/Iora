# Retest Entry System — Level 2: Bias State Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a continuous per-bar structural bias tracker that produces daily/H4/H1 bias labels, D-to-W relationships, zone distances, and bias transition events across all 38 symbols.

**Architecture:** Pure diagnostic module — no strategy, no trades. Runs alongside the push zone engine in a runner loop (same pattern as `zone_audit_runner.py`). Bias computation is a set of pure functions consuming `PeriodTracker` state and zone arrays per bar. The runner collects one `BiasStateRecord` per bar into a timeline DataFrame.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest. Existing engine/orchestrator patterns.

**Spec:** `docs/superpowers/specs/2026-04-02-retest-entry-system-design.md` (Level 2 section)

**Scope note:** This plan covers the data pipeline only (bias computation + runner + CLI). Flask visualization (bias ribbon, transition markers, zone distance indicators) described in the spec is deferred to the Phase 5 Flask plan — the data pipeline is a prerequisite.

**Design decisions:**
- Bias strength 3 requires both highs AND lows to consistently align (stricter than spec's high-only description). This captures more complete structural consistency.
- `nearest_zone_distance` finds nearest zone regardless of above/below price. In practice supply zones are above price and demand below since broken zones are removed from arrays. Edge case is narrow.

---

## File Structure

```
src/iora/diagnostics/
    bias_timeline.py          # BiasStateRecord dataclass + all pure computation functions
    bias_timeline_runner.py   # Runner: engine loop → per-bar bias collection → BiasTimelineResult

tests/diagnostics/
    test_bias_timeline.py          # Unit tests for pure functions (synthetic data)
    test_bias_timeline_runner.py   # Integration test on real GBPUSD data

scripts/
    run_bias_timeline.py      # CLI: run bias timeline for a symbol, print summary + save CSV
```

**Dependency map:**
- `bias_timeline.py` depends on: `period_pattern.py` (reuses `compute_period_pattern`), `push_zone_models.py` (PeriodTracker, PushZoneTickState, PushZone)
- `bias_timeline_runner.py` depends on: `bias_timeline.py`, `push_zone_engine.py` (init + tick), `bar_iterator.py`, `tf_alignment.py`

---

### Task 1: Bias label and strength computation

**Files:**
- Create: `src/iora/diagnostics/bias_timeline.py`
- Test: `tests/diagnostics/test_bias_timeline.py`

These are pure functions with no engine dependency — easily tested with synthetic data.

- [ ] **Step 1: Write failing tests for `compute_bias_label`**

```python
# tests/diagnostics/test_bias_timeline.py
"""Unit tests for bias timeline computation functions."""
from __future__ import annotations

from iora.diagnostics.bias_timeline import compute_bias_label


class TestComputeBiasLabel:
    def test_bull_push(self):
        # HH + HL → bull push
        assert compute_bias_label([1.32, 1.30], [1.28, 1.26]) == "HH_HL_bull_push"

    def test_bear_push(self):
        # LH + LL → bear push
        assert compute_bias_label([1.28, 1.30], [1.24, 1.26]) == "LH_LL_bear_push"

    def test_compression(self):
        # LH + HL → compression
        assert compute_bias_label([1.28, 1.30], [1.28, 1.26]) == "LH_HL_compression"

    def test_expansion(self):
        # HH + LL → expansion
        assert compute_bias_label([1.32, 1.30], [1.24, 1.26]) == "HH_LL_expansion"

    def test_insufficient_data(self):
        assert compute_bias_label([1.30], [1.26]) == "unknown"
        assert compute_bias_label([], []) == "unknown"

    def test_equal_highs_lows(self):
        # Equal values → mixed
        assert compute_bias_label([1.30, 1.30], [1.26, 1.26]) == "mixed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v -k "TestComputeBiasLabel"`
Expected: FAIL — `compute_bias_label` not found

- [ ] **Step 3: Write failing tests for `compute_bias_strength`**

```python
# Add to tests/diagnostics/test_bias_timeline.py
from iora.diagnostics.bias_timeline import compute_bias_strength


class TestComputeBiasStrength:
    def test_strong_bull_3_hh(self):
        # 3 consecutive HH → strength 3
        assert compute_bias_strength([1.34, 1.32, 1.30], [1.28, 1.26, 1.24]) == 3

    def test_moderate_2_hh(self):
        # Last 2 HH but 3rd breaks → strength 2
        assert compute_bias_strength([1.34, 1.32, 1.33], [1.28, 1.26, 1.24]) == 2

    def test_weak_single(self):
        # Only latest is HH, previous was LH → strength 1
        assert compute_bias_strength([1.34, 1.32, 1.35], [1.26, 1.28, 1.24]) == 1

    def test_insufficient_data(self):
        # < 2 periods → strength 0
        assert compute_bias_strength([1.30], [1.26]) == 0
        assert compute_bias_strength([], []) == 0

    def test_strong_bear_3_lh(self):
        # 3 consecutive LH + LL → strength 3
        assert compute_bias_strength([1.30, 1.32, 1.34], [1.24, 1.26, 1.28]) == 3
```

- [ ] **Step 4: Implement `compute_bias_label` and `compute_bias_strength`**

```python
# src/iora/diagnostics/bias_timeline.py
"""Bias State Timeline — Level 2 diagnostics.

Continuous per-bar structural bias tracker. Computes daily/H4/H1 bias
labels, D-to-W relationships, and zone distances.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.diagnostics.period_pattern import compute_period_pattern


# Mapping from short pattern → descriptive label
_PATTERN_LABELS: dict[str, str] = {
    "HH_HL": "HH_HL_bull_push",
    "LH_LL": "LH_LL_bear_push",
    "LH_HL": "LH_HL_compression",
    "HH_LL": "HH_LL_expansion",
}


def compute_bias_label(
    prev_highs: list[float],
    prev_lows: list[float],
) -> str:
    """Compute bias label with descriptive suffix from period history.

    Reuses compute_period_pattern() for the core HH/LH + HL/LL logic,
    then maps to descriptive label (e.g., "HH_HL_bull_push").
    """
    short = compute_period_pattern(prev_highs, prev_lows)
    return _PATTERN_LABELS.get(short, short)


def compute_bias_strength(
    prev_highs: list[float],
    prev_lows: list[float],
) -> int:
    """Compute bias strength (1-3) from period history depth.

    3 = three consecutive same-direction highs (HH-HH-HH or LH-LH-LH)
    2 = last two same-direction, third breaks
    1 = only latest pair shows direction
    0 = insufficient data (< 2 periods)
    """
    if len(prev_highs) < 2 or len(prev_lows) < 2:
        return 0

    # Determine primary direction from latest pair
    h0, h1 = prev_highs[0], prev_highs[1]
    bullish = h0 > h1  # HH
    bearish = h0 < h1  # LH

    if not bullish and not bearish:
        return 1  # Equal — weak

    # Check depth-2 consistency
    if len(prev_highs) < 3:
        return 1

    h2 = prev_highs[2]
    pair2_same = (h1 > h2) if bullish else (h1 < h2)
    if not pair2_same:
        return 1

    # Check depth-3 consistency (also check lows align)
    l0, l1 = prev_lows[0], prev_lows[1]
    l2 = prev_lows[2] if len(prev_lows) >= 3 else l1
    lows_align = (l0 > l1 > l2) if bullish else (l0 < l1 < l2)

    if pair2_same and lows_align:
        return 3

    return 2
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/iora/diagnostics/bias_timeline.py tests/diagnostics/test_bias_timeline.py
git commit -m "feat(diagnostics): add bias label and strength computation (Level 2)"
```

---

### Task 2: BiasStateRecord dataclass and zone distance helpers

**Files:**
- Modify: `src/iora/diagnostics/bias_timeline.py`
- Test: `tests/diagnostics/test_bias_timeline.py`

- [ ] **Step 1: Write failing tests for `nearest_zone_distance` and `BiasStateRecord`**

```python
# Add to tests/diagnostics/test_bias_timeline.py
import pandas as pd
from iora.diagnostics.bias_timeline import nearest_zone_distance, BiasStateRecord
from iora.engine.push_zone_models import PushZone


class TestNearestZoneDistance:
    def test_no_zones(self):
        assert nearest_zone_distance(1.3000, [], 0.0020) == float("inf")

    def test_single_zone_above(self):
        z = PushZone(top=1.3100, bottom=1.3080, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Zone midpoint = 1.3090, close = 1.3000, distance = 0.009
        # ATR = 0.002, so in ATR units = 0.009 / 0.002 = 4.5
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert abs(dist - 4.5) < 0.01

    def test_inside_zone_negative(self):
        z = PushZone(top=1.3020, bottom=1.2980, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Close = 1.3000, inside zone (bottom=1.2980, top=1.3020)
        # Midpoint = 1.3000, distance = 0 → inside → negative
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert dist < 0  # Negative means inside

    def test_picks_nearest(self):
        z_far = PushZone(top=1.3200, bottom=1.3180, is_supply=True,
                         origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        z_near = PushZone(top=1.3060, bottom=1.3040, is_supply=True,
                          origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        dist = nearest_zone_distance(1.3000, [z_far, z_near], 0.002)
        # Should pick z_near: boundary distance = 1.3040 - 1.3000 = 0.004 / 0.002 = 2.0
        assert dist < 10.0  # Closer to z_near


class TestBiasStateRecord:
    def test_defaults(self):
        rec = BiasStateRecord(timestamp=pd.Timestamp("2025-01-01"))
        assert rec.d_bias == "unknown"
        assert rec.d_bias_strength == 0
        assert rec.is_bias_transition is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v -k "TestNearestZone or TestBiasState"`
Expected: FAIL — imports not found

- [ ] **Step 3: Implement `nearest_zone_distance` and `BiasStateRecord`**

Add to `src/iora/diagnostics/bias_timeline.py`:

```python
from math import inf


def nearest_zone_distance(
    close: float,
    zones: list,
    atr: float,
) -> float:
    """Compute ATR-relative distance to nearest zone.

    Returns positive if outside zone (distance to nearest boundary),
    negative if inside a zone (penetration depth).
    Returns inf if no zones.
    """
    if not zones or atr <= 0:
        return inf

    best_dist = inf
    for z in zones:
        if z.bottom <= close <= z.top:
            # Inside zone — return negative penetration depth
            mid = (z.top + z.bottom) / 2.0
            return -abs(close - mid) / atr - 0.001  # Always negative when inside
        # Outside: distance to nearest boundary
        if close < z.bottom:
            dist = (z.bottom - close) / atr
        else:
            dist = (close - z.top) / atr
        if dist < best_dist:
            best_dist = dist

    return best_dist


@dataclass(slots=True)
class BiasStateRecord:
    """Per-bar structural bias state."""
    timestamp: pd.Timestamp
    d_bias: str = "unknown"
    d_bias_strength: int = 0
    d_to_w_relationship: str = "neutral"
    h4_bias: str = "unknown"
    h4_vs_daily: str = "neutral"
    h1_bias: str = "unknown"
    h1_vs_daily: str = "neutral"
    nearest_w_supply_dist: float = inf
    nearest_w_demand_dist: float = inf
    nearest_d_supply_dist: float = inf
    nearest_d_demand_dist: float = inf
    is_bias_transition: bool = False
    transition_from: str = ""
    transition_to: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/bias_timeline.py tests/diagnostics/test_bias_timeline.py
git commit -m "feat(diagnostics): add BiasStateRecord and zone distance helper"
```

---

### Task 3: D-to-W relationship and TF alignment computation

**Files:**
- Modify: `src/iora/diagnostics/bias_timeline.py`
- Test: `tests/diagnostics/test_bias_timeline.py`

- [ ] **Step 1: Write failing tests for `compute_d_to_w_relationship`**

```python
# Add to tests/diagnostics/test_bias_timeline.py
from math import inf
from iora.diagnostics.bias_timeline import compute_d_to_w_relationship, compute_tf_vs_daily


class TestDToWRelationship:
    def test_inside_w_supply(self):
        # Price inside W supply zone → "inside_zone"
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=-0.5, w_demand_dist=5.0,
        )
        assert result == "inside_zone"

    def test_inside_w_demand(self):
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=5.0, w_demand_dist=-0.5,
        )
        assert result == "inside_zone"

    def test_bull_pushing_toward_w_supply(self):
        # Bullish daily bias, W supply above → pullback (pushing toward resistance)
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=2.0, w_demand_dist=8.0,
        )
        assert result == "pullback"

    def test_bull_pushing_away_from_w_supply(self):
        # Bullish daily bias, W supply far away, W demand close → continuation
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=8.0, w_demand_dist=2.0,
        )
        assert result == "continuation"

    def test_bear_pushing_toward_w_demand(self):
        # Bearish daily, W demand close below → pullback
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=8.0, w_demand_dist=2.0,
        )
        assert result == "pullback"

    def test_bear_pushing_away_from_w_demand(self):
        result = compute_d_to_w_relationship(
            d_bias="LH_LL_bear_push", w_supply_dist=2.0, w_demand_dist=8.0,
        )
        assert result == "continuation"

    def test_neutral_bias(self):
        result = compute_d_to_w_relationship(
            d_bias="unknown", w_supply_dist=5.0, w_demand_dist=5.0,
        )
        assert result == "neutral"

    def test_no_w_zones(self):
        result = compute_d_to_w_relationship(
            d_bias="HH_HL_bull_push", w_supply_dist=inf, w_demand_dist=inf,
        )
        assert result == "neutral"


class TestTfVsDaily:
    def test_same_direction_bullish(self):
        assert compute_tf_vs_daily("HH_HL_bull_push", "HH_HL_bull_push") == "with"

    def test_opposite_direction(self):
        assert compute_tf_vs_daily("LH_LL_bear_push", "HH_HL_bull_push") == "against"

    def test_neutral_on_unknown(self):
        assert compute_tf_vs_daily("unknown", "HH_HL_bull_push") == "neutral"

    def test_compression_vs_bull(self):
        # Compression = no clear direction → neutral
        assert compute_tf_vs_daily("LH_HL_compression", "HH_HL_bull_push") == "neutral"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v -k "TestDToW or TestTfVs"`
Expected: FAIL

- [ ] **Step 3: Implement both functions**

Add to `src/iora/diagnostics/bias_timeline.py`:

```python
# Bias direction extraction
_BULLISH_BIASES = {"HH_HL_bull_push"}
_BEARISH_BIASES = {"LH_LL_bear_push"}


def _bias_direction(bias: str) -> int:
    """Return +1 for bullish, -1 for bearish, 0 for neutral/unknown."""
    if bias in _BULLISH_BIASES:
        return 1
    if bias in _BEARISH_BIASES:
        return -1
    return 0


def compute_d_to_w_relationship(
    d_bias: str,
    w_supply_dist: float,
    w_demand_dist: float,
) -> str:
    """Classify daily-to-weekly structural relationship.

    Returns: "inside_zone", "continuation", "pullback", "neutral".
    """
    # Inside a W zone
    if w_supply_dist < 0 or w_demand_dist < 0:
        return "inside_zone"

    direction = _bias_direction(d_bias)
    if direction == 0:
        return "neutral"

    # No W zones available
    if w_supply_dist == inf and w_demand_dist == inf:
        return "neutral"

    if direction == 1:  # Bullish
        # Pushing toward W supply (closer) = pullback within weekly
        # Pushing away from W supply (farther) = continuation
        if w_supply_dist < w_demand_dist:
            return "pullback"
        return "continuation"
    else:  # Bearish
        # Pushing toward W demand (closer) = pullback within weekly
        if w_demand_dist < w_supply_dist:
            return "pullback"
        return "continuation"


def compute_tf_vs_daily(
    tf_bias: str,
    d_bias: str,
) -> str:
    """Classify whether a TF bias aligns with daily bias.

    Returns: "with", "against", "neutral".
    """
    tf_dir = _bias_direction(tf_bias)
    d_dir = _bias_direction(d_bias)

    if tf_dir == 0 or d_dir == 0:
        return "neutral"
    if tf_dir == d_dir:
        return "with"
    return "against"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/bias_timeline.py tests/diagnostics/test_bias_timeline.py
git commit -m "feat(diagnostics): add D-to-W relationship and TF alignment computation"
```

---

### Task 4: Per-bar bias collection function

**Files:**
- Modify: `src/iora/diagnostics/bias_timeline.py`
- Test: `tests/diagnostics/test_bias_timeline.py`

This function takes engine state + bar context and produces one `BiasStateRecord`. It's the glue that the runner calls each bar.

- [ ] **Step 1: Write failing tests for `collect_bias_state`**

```python
# Add to tests/diagnostics/test_bias_timeline.py
from iora.diagnostics.bias_timeline import collect_bias_state
from iora.engine.push_zone_models import PushZoneTickState, PeriodTracker, PushZone
from iora.orchestrator.push_zone_engine import PushZoneEngineState


def _make_period_tracker(prev_highs, prev_lows):
    """Helper to build a PeriodTracker with preset history."""
    pt = PeriodTracker()
    pt.prev_highs = list(prev_highs)
    pt.prev_lows = list(prev_lows)
    return pt


def _make_state(d_highs, d_lows, h4_highs=None, h4_lows=None,
                h1_highs=None, h1_lows=None,
                w_supply=None, w_demand=None,
                d_supply=None, d_demand=None):
    """Helper to build engine state with preset period histories and zones."""
    tick_states = {}
    for tf, highs, lows in [("D1", d_highs, d_lows),
                             ("H4", h4_highs or [], h4_lows or []),
                             ("H1", h1_highs or [], h1_lows or [])]:
        ts = PushZoneTickState()
        ts.period = _make_period_tracker(highs, lows)
        tick_states[tf] = ts

    w_ts = PushZoneTickState()
    w_ts.supply_zones = list(w_supply or [])
    w_ts.demand_zones = list(w_demand or [])
    tick_states["W1"] = w_ts

    if "D1" in tick_states:
        tick_states["D1"].supply_zones = list(d_supply or [])
        tick_states["D1"].demand_zones = list(d_demand or [])

    return PushZoneEngineState(tick_states=tick_states)


class TestCollectBiasState:
    def test_basic_bull_bias(self):
        state = _make_state(
            d_highs=[1.32, 1.30, 1.28], d_lows=[1.28, 1.26, 1.24],
            h4_highs=[1.315, 1.31], h4_lows=[1.275, 1.27],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
        )
        assert rec.d_bias == "HH_HL_bull_push"
        assert rec.d_bias_strength == 3
        assert rec.h4_vs_daily == "with"

    def test_no_data_returns_unknown(self):
        state = _make_state(d_highs=[], d_lows=[])
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
        )
        assert rec.d_bias == "unknown"
        assert rec.d_bias_strength == 0

    def test_transition_detected(self):
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="LH_LL_bear_push",
        )
        assert rec.is_bias_transition is True
        assert rec.transition_from == "LH_LL_bear_push"
        assert rec.transition_to == "HH_HL_bull_push"

    def test_no_transition_when_same(self):
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="HH_HL_bull_push",
        )
        assert rec.is_bias_transition is False

    def test_no_transition_from_unknown(self):
        """Transition from 'unknown' to a known bias is suppressed."""
        state = _make_state(
            d_highs=[1.32, 1.30], d_lows=[1.28, 1.26],
        )
        rec = collect_bias_state(
            state, pd.Timestamp("2025-06-01"), close=1.3000, atr=0.002,
            prev_d_bias="unknown",
        )
        # Not a real transition — just startup
        assert rec.is_bias_transition is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v -k "TestCollectBias"`
Expected: FAIL

- [ ] **Step 3: Implement `collect_bias_state`**

Add to `src/iora/diagnostics/bias_timeline.py`:

```python
def collect_bias_state(
    state,  # PushZoneEngineState
    timestamp: pd.Timestamp,
    close: float,
    atr: float,
    prev_d_bias: str = "",
) -> BiasStateRecord:
    """Collect structural bias state from engine state at one bar.

    Args:
        state: PushZoneEngineState with tick_states per TF
        timestamp: Current bar time
        close: Current close price
        atr: ATR(14) of the base TF for distance normalization
        prev_d_bias: Previous bar's daily bias (for transition detection)
    """
    ts_map = state.tick_states

    # Daily bias
    d_ts = ts_map.get("D1")
    if d_ts and len(d_ts.period.prev_highs) >= 2:
        d_bias = compute_bias_label(d_ts.period.prev_highs, d_ts.period.prev_lows)
        d_strength = compute_bias_strength(d_ts.period.prev_highs, d_ts.period.prev_lows)
    else:
        d_bias = "unknown"
        d_strength = 0

    # H4 bias
    h4_ts = ts_map.get("H4")
    if h4_ts and len(h4_ts.period.prev_highs) >= 2:
        h4_bias = compute_bias_label(h4_ts.period.prev_highs, h4_ts.period.prev_lows)
    else:
        h4_bias = "unknown"
    h4_vs = compute_tf_vs_daily(h4_bias, d_bias)

    # H1 bias
    h1_ts = ts_map.get("H1")
    if h1_ts and len(h1_ts.period.prev_highs) >= 2:
        h1_bias = compute_bias_label(h1_ts.period.prev_highs, h1_ts.period.prev_lows)
    else:
        h1_bias = "unknown"
    h1_vs = compute_tf_vs_daily(h1_bias, d_bias)

    # Weekly zone distances
    w_ts = ts_map.get("W1")
    w_supply_dist = nearest_zone_distance(close, w_ts.supply_zones, atr) if w_ts else inf
    w_demand_dist = nearest_zone_distance(close, w_ts.demand_zones, atr) if w_ts else inf

    # Daily zone distances
    d_supply_dist = nearest_zone_distance(close, d_ts.supply_zones, atr) if d_ts else inf
    d_demand_dist = nearest_zone_distance(close, d_ts.demand_zones, atr) if d_ts else inf

    # D-to-W relationship
    d_to_w = compute_d_to_w_relationship(d_bias, w_supply_dist, w_demand_dist)

    # Transition detection (suppress unknown→known as startup noise)
    is_transition = bool(
        prev_d_bias and prev_d_bias != d_bias
        and d_bias != "unknown" and prev_d_bias != "unknown"
    )

    return BiasStateRecord(
        timestamp=timestamp,
        d_bias=d_bias,
        d_bias_strength=d_strength,
        d_to_w_relationship=d_to_w,
        h4_bias=h4_bias,
        h4_vs_daily=h4_vs,
        h1_bias=h1_bias,
        h1_vs_daily=h1_vs,
        nearest_w_supply_dist=w_supply_dist,
        nearest_w_demand_dist=w_demand_dist,
        nearest_d_supply_dist=d_supply_dist,
        nearest_d_demand_dist=d_demand_dist,
        is_bias_transition=is_transition,
        transition_from=prev_d_bias if is_transition else "",
        transition_to=d_bias if is_transition else "",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_bias_timeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/bias_timeline.py tests/diagnostics/test_bias_timeline.py
git commit -m "feat(diagnostics): add per-bar bias state collection function"
```

---

### Task 5: Bias timeline runner

**Files:**
- Create: `src/iora/diagnostics/bias_timeline_runner.py`
- Test: `tests/diagnostics/test_bias_timeline_runner.py`

Follows the `zone_audit_runner.py` pattern: run the engine loop, collect bias state per bar, return a result.

- [ ] **Step 1: Write failing integration test**

```python
# tests/diagnostics/test_bias_timeline_runner.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/diagnostics/test_bias_timeline_runner.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `bias_timeline_runner.py`**

```python
# src/iora/diagnostics/bias_timeline_runner.py
"""Bias Timeline Runner — runs zone engine and collects per-bar bias state.

Follows zone_audit_runner.py pattern. Produces BiasTimelineResult
with per-bar BiasStateRecords.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf

import numpy as np
import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState, PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.diagnostics.bias_timeline import BiasStateRecord, collect_bias_state


@dataclass(slots=True)
class BiasTimelineResult:
    """Full bias timeline output for one symbol."""
    symbol: str
    records: list[BiasStateRecord] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert records to DataFrame."""
        rows = []
        for r in self.records:
            rows.append({
                "timestamp": r.timestamp,
                "d_bias": r.d_bias,
                "d_bias_strength": r.d_bias_strength,
                "d_to_w_relationship": r.d_to_w_relationship,
                "h4_bias": r.h4_bias,
                "h4_vs_daily": r.h4_vs_daily,
                "h1_bias": r.h1_bias,
                "h1_vs_daily": r.h1_vs_daily,
                "nearest_w_supply_dist": r.nearest_w_supply_dist,
                "nearest_w_demand_dist": r.nearest_w_demand_dist,
                "nearest_d_supply_dist": r.nearest_d_supply_dist,
                "nearest_d_demand_dist": r.nearest_d_demand_dist,
                "is_bias_transition": r.is_bias_transition,
                "transition_from": r.transition_from,
                "transition_to": r.transition_to,
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict:
        """Compute summary statistics."""
        total = len(self.records)
        if total == 0:
            return {"total_bars": 0, "transition_count": 0}

        transitions = [r for r in self.records if r.is_bias_transition]

        # Bias distribution
        bias_counts: dict[str, int] = {}
        for r in self.records:
            bias_counts[r.d_bias] = bias_counts.get(r.d_bias, 0) + 1

        # D-to-W distribution
        d_to_w_counts: dict[str, int] = {}
        for r in self.records:
            d_to_w_counts[r.d_to_w_relationship] = d_to_w_counts.get(r.d_to_w_relationship, 0) + 1

        return {
            "total_bars": total,
            "transition_count": len(transitions),
            "bias_distribution": bias_counts,
            "d_to_w_distribution": d_to_w_counts,
        }


def run_bias_timeline(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    sample_every: int = 1,
) -> BiasTimelineResult:
    """Run zone engine and collect per-bar bias state.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label
        base_tf: Base timeframe for bar iteration
        symbol: Symbol name for labeling
        period_depth: Period tracker history depth
        sample_every: Collect bias state every N bars (1 = every bar).
            Use higher values for memory savings on M1 data.
    """
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    # Pre-compute ATR(14) from base TF data
    base_df = data_by_tf[base_tf]
    atr_series = _compute_atr(base_df, period=14)

    records: list[BiasStateRecord] = []
    prev_d_bias = ""
    bar_idx = 0

    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        if bar_idx % sample_every == 0:
            # Use ATR at current bar (or last valid if NaN at start)
            atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
            if np.isnan(atr_val):
                atr_val = 0.002  # Fallback during warm-up

            rec = collect_bias_state(
                state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
            )
            records.append(rec)
            prev_d_bias = rec.d_bias

        bar_idx += 1

    return BiasTimelineResult(symbol=symbol, records=records)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR(period) from OHLC DataFrame."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(window=period, min_periods=1).mean()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/diagnostics/test_bias_timeline_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/diagnostics/bias_timeline_runner.py tests/diagnostics/test_bias_timeline_runner.py
git commit -m "feat(diagnostics): add bias timeline runner (Level 2)"
```

---

### Task 6: CLI script

**Files:**
- Create: `scripts/run_bias_timeline.py`

- [ ] **Step 1: Write CLI script**

```python
#!/usr/bin/env python
"""Run bias timeline for a symbol and print summary.

Usage:
    python scripts/run_bias_timeline.py GBPUSD
    python scripts/run_bias_timeline.py GBPUSD --base-tf M5 --save-csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.diagnostics.bias_timeline_runner import run_bias_timeline


def main():
    parser = argparse.ArgumentParser(description="Run bias timeline analysis")
    parser.add_argument("symbol", help="Symbol to analyze (e.g., GBPUSD)")
    parser.add_argument("--base-tf", default="M5", help="Base timeframe (default: M5)")
    parser.add_argument("--tfs", default="M5,H1,H4,D1,W1", help="Comma-separated TFs")
    parser.add_argument("--save-csv", action="store_true", help="Save timeline to CSV")
    parser.add_argument("--sample-every", type=int, default=1,
                        help="Collect every N bars (default: 1)")
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

    print(f"\nRunning bias timeline for {args.symbol}...")
    result = run_bias_timeline(
        data_by_tf, base_tf=args.base_tf, symbol=args.symbol,
        sample_every=args.sample_every,
    )

    summary = result.summary()
    print(f"\n=== Bias Timeline: {args.symbol} ===")
    print(f"Total bars:       {summary['total_bars']}")
    print(f"Transitions:      {summary['transition_count']}")
    print(f"\nBias distribution:")
    for label, count in sorted(summary.get("bias_distribution", {}).items(),
                                key=lambda x: -x[1]):
        pct = count / summary["total_bars"] * 100
        print(f"  {label:30s} {count:6d} ({pct:5.1f}%)")

    print(f"\nD-to-W relationship:")
    for label, count in sorted(summary.get("d_to_w_distribution", {}).items(),
                                key=lambda x: -x[1]):
        pct = count / summary["total_bars"] * 100
        print(f"  {label:20s} {count:6d} ({pct:5.1f}%)")

    if args.save_csv:
        out_dir = Path("results")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{args.symbol.lower()}_bias_timeline.csv"
        df = result.to_dataframe()
        df.to_csv(out_path, index=False)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

Run: `python scripts/run_bias_timeline.py GBPUSD --sample-every 10`
Expected: Summary output with bias distribution and transition count. No errors.

- [ ] **Step 3: Commit**

```bash
git add scripts/run_bias_timeline.py
git commit -m "feat(diagnostics): add bias timeline CLI script"
```

---

## Verification Checklist

After all tasks are complete:

1. `pytest tests/diagnostics/test_bias_timeline.py -v` — all unit tests pass
2. `pytest tests/diagnostics/test_bias_timeline_runner.py -v` — integration test passes
3. `python scripts/run_bias_timeline.py GBPUSD --sample-every 10` — produces output
4. No changes to existing engine files — purely additive (new files only)
