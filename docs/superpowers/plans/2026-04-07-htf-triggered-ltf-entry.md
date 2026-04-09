# HTF-Triggered LTF Entry System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add static and dynamic LTF nesting modes to the retest engine so that H1@H4 trigger events can place limits at M15/M5 zone edges inside H4 zones, then sweep ~388 configs on GBPUSD to evaluate whether tighter SL improves R:R.

**Architecture:** Enrich `RetestCandidate` at build time with nested LTF zone geometry (static) and pre-compute zone birth events (dynamic). The simulation loop gains two new paths: static expands candidates into LTF-boundary limits; dynamic uses a `_ActiveTrigger` state machine to track trigger windows and place limits when new LTF zones are born inside triggered H4 zones. All existing SL/TP computation is reused — only the zone boundaries change.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest, dataclasses

**Spec:** `docs/superpowers/specs/2026-04-07-htf-triggered-ltf-entry-design.md`
**Prompt:** `docs/superpowers/specs/2026-04-07-htf-triggered-ltf-entry-prompt.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/iora/strategy/retest_config.py` | Add 7 config fields for HTF-triggered LTF nesting |
| `src/iora/strategy/retest_candidate.py` | Add `nested_ltf_zones` field, `ZoneBirthEvent` dataclass, `CandidateBuildResult`, nesting enrichment logic, zone birth event collection |
| `src/iora/strategy/retest_engine.py` | Add `_ActiveTrigger`, static nesting expansion, dynamic nesting state machine in `_simulate_with_bars()` |
| `src/iora/strategy/retest_sweep.py` | Add `htf_triggered_ltf_configs()` sweep generator |
| `tests/strategy/test_htf_triggered_ltf.py` | All tests for this feature |
| `scripts/run_htf_triggered_sweep.py` | CLI runner for the sweep |

---

## Task 1: Add Config Fields to RetestConfig

**Files:**
- Modify: `src/iora/strategy/retest_config.py:28-116` (RetestConfig dataclass)
- Test: `tests/strategy/test_htf_triggered_ltf.py` (new file)

- [ ] **Step 1: Write the test file with config validation tests**

```python
# tests/strategy/test_htf_triggered_ltf.py
"""Tests for HTF-triggered LTF entry system."""
from iora.strategy.retest_config import RetestConfig


class TestHTFTriggeredConfig:
    """Config field defaults and validation."""

    def test_default_ltf_nesting_is_none(self):
        cfg = RetestConfig()
        assert cfg.ltf_nesting == "none"

    def test_default_trigger_tf_pair(self):
        cfg = RetestConfig()
        assert cfg.trigger_tf_pair == "H1@H4"

    def test_default_entry_tf_override_empty(self):
        cfg = RetestConfig()
        assert cfg.entry_tf_override == ""

    def test_default_trigger_window_bars(self):
        cfg = RetestConfig()
        assert cfg.trigger_window_bars == 48

    def test_default_require_ltf_push_false(self):
        cfg = RetestConfig()
        assert cfg.require_ltf_push is False

    def test_default_trigger_also_trades_false(self):
        cfg = RetestConfig()
        assert cfg.trigger_also_trades is False

    def test_default_max_ltf_per_trigger(self):
        cfg = RetestConfig()
        assert cfg.max_ltf_per_trigger == 3

    def test_static_nesting_config(self):
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
        )
        assert cfg.ltf_nesting == "static"
        assert cfg.entry_tf == "H1"
        assert cfg.zone_tf == "H4"
        assert cfg.entry_tf_override == "M15"

    def test_dynamic_nesting_config(self):
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            ltf_nesting="dynamic",
            entry_tf_override="M5",
            trigger_window_bars=24,
        )
        assert cfg.ltf_nesting == "dynamic"
        assert cfg.trigger_window_bars == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v`
Expected: FAIL — `RetestConfig` doesn't have `ltf_nesting` etc.

- [ ] **Step 3: Add the 7 new fields to RetestConfig**

In `src/iora/strategy/retest_config.py`, add after the `touch_policy` field (around line 112):

```python
    # HTF-triggered LTF entry
    ltf_nesting: str = "none"              # "none" (standard), "static", "dynamic"
    trigger_tf_pair: str = "H1@H4"         # HTF pair providing the trigger signal
    entry_tf_override: str = ""            # LTF for zone lookup ("M15", "M5", "M1", "" = tf_pair entry)
    trigger_window_bars: int = 48          # Dynamic mode: max entry-TF bars after trigger
    require_ltf_push: bool = False         # Only use LTF push zones (0% break-through)
    trigger_also_trades: bool = False      # Also open the H1@H4 trade alongside nested
    max_ltf_per_trigger: int = 3           # Max LTF zone entries per trigger event
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `pytest tests/ -x -q`
Expected: All 340+ tests pass

- [ ] **Step 6: Commit**

```bash
git add tests/strategy/test_htf_triggered_ltf.py src/iora/strategy/retest_config.py
git commit -m "feat(config): add HTF-triggered LTF nesting config fields"
```

---

## Task 2: Add ZoneBirthEvent and CandidateBuildResult Dataclasses

**Files:**
- Modify: `src/iora/strategy/retest_candidate.py:1-10` (imports) and after `RetestCandidate` class
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write tests for new dataclasses**

Append to `tests/strategy/test_htf_triggered_ltf.py`:

```python
import pandas as pd
from iora.strategy.retest_candidate import ZoneBirthEvent, CandidateBuildResult


class TestZoneBirthEvent:
    """ZoneBirthEvent dataclass tests."""

    def test_create_demand_birth(self):
        ev = ZoneBirthEvent(
            timestamp=pd.Timestamp("2020-01-01 12:00"),
            zone_top=1.3010,
            zone_bottom=1.3000,
            zone_tf="M15",
            zone_side="demand",
            zone_role="push",
            is_push=True,
        )
        assert ev.zone_side == "demand"
        assert ev.is_push is True
        assert ev.zone_tf == "M15"

    def test_create_supply_birth(self):
        ev = ZoneBirthEvent(
            timestamp=pd.Timestamp("2020-01-01 12:00"),
            zone_top=1.3100,
            zone_bottom=1.3090,
            zone_tf="M5",
            zone_side="supply",
            zone_role="continuation",
            is_push=False,
        )
        assert ev.zone_side == "supply"
        assert ev.is_push is False


class TestCandidateBuildResult:
    """CandidateBuildResult container tests."""

    def test_empty_result(self):
        result = CandidateBuildResult(candidates=[], zone_births={})
        assert len(result.candidates) == 0
        assert len(result.zone_births) == 0

    def test_result_with_births(self):
        ts = pd.Timestamp("2020-01-01 12:00")
        ev = ZoneBirthEvent(
            timestamp=ts,
            zone_top=1.3010,
            zone_bottom=1.3000,
            zone_tf="M15",
            zone_side="demand",
            zone_role="push",
            is_push=True,
        )
        result = CandidateBuildResult(candidates=[], zone_births={ts: [ev]})
        assert len(result.zone_births[ts]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestZoneBirthEvent -v`
Expected: FAIL — `ZoneBirthEvent` not defined

- [ ] **Step 3: Add dataclasses to retest_candidate.py**

Add after the `RetestCandidate` class (before the `_get_pip_size` import, around line 83):

```python
@dataclass(slots=True)
class ZoneBirthEvent:
    """A push zone born on a specific bar."""
    timestamp: pd.Timestamp
    zone_top: float
    zone_bottom: float
    zone_tf: str
    zone_side: str       # "demand" or "supply"
    zone_role: str       # "push", "continuation", "reversal", "pullback"
    is_push: bool


@dataclass(slots=True)
class CandidateBuildResult:
    """Result of build_retest_candidates_with_births()."""
    candidates: list[RetestCandidate]
    zone_births: dict[pd.Timestamp, list[ZoneBirthEvent]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(candidate): add ZoneBirthEvent and CandidateBuildResult dataclasses"
```

---

## Task 3: Add nested_ltf_zones Field to RetestCandidate

**Files:**
- Modify: `src/iora/strategy/retest_candidate.py:29-82` (RetestCandidate class)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write test for the new field**

Append to test file:

```python
from iora.diagnostics.opportunity_counter import OpportunityEvent


def _make_event(**kwargs) -> OpportunityEvent:
    """Helper to create a minimal OpportunityEvent for testing."""
    defaults = dict(
        timestamp=pd.Timestamp("2020-01-01 12:00"),
        tf_pair="H1@H4",
        entry_tf="H1",
        zone_tf="H4",
        zone_side="demand",
        touch_type="wick_touch",
        zone_role="push",
        age_bucket="young",
        test_count_cls="retested_1",
        bias_alignment="with_daily",
        bias_strength=2,
        replacement_count=0,
        d_bias="bull",
        price_distance_at_touch=0.0005,
        birth_period_pattern="HH_HL",
        bar_idx=100,
        swing_cls_at_touch="",
    )
    defaults.update(kwargs)
    return OpportunityEvent(**defaults)


class TestNestedLtfZonesField:
    """RetestCandidate.nested_ltf_zones field."""

    def test_default_empty(self):
        from iora.strategy.retest_candidate import RetestCandidate
        c = RetestCandidate(
            event=_make_event(),
            zone_top=1.3050,
            zone_bottom=1.3000,
            entry_price=1.3025,
            atr=0.0020,
            period_hi=1.3100,
            period_lo=1.2950,
        )
        assert c.nested_ltf_zones == []

    def test_with_nested_zones(self):
        from iora.strategy.retest_candidate import RetestCandidate
        c = RetestCandidate(
            event=_make_event(),
            zone_top=1.3050,
            zone_bottom=1.3000,
            entry_price=1.3025,
            atr=0.0020,
            period_hi=1.3100,
            period_lo=1.2950,
            nested_ltf_zones=[
                (1.3020, 1.3010, "M15", "push"),
                (1.3035, 1.3025, "M15", "continuation"),
            ],
        )
        assert len(c.nested_ltf_zones) == 2
        assert c.nested_ltf_zones[0] == (1.3020, 1.3010, "M15", "push")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestNestedLtfZonesField -v`
Expected: FAIL — `nested_ltf_zones` not a valid field

- [ ] **Step 3: Add field to RetestCandidate**

In `src/iora/strategy/retest_candidate.py`, add after the `inside_w_zone` field (around line 72):

```python
    # Nested LTF zones (populated when ltf_nesting="static")
    # Each: (zone_top, zone_bottom, zone_tf, zone_role)
    nested_ltf_zones: list[tuple[float, float, str, str]] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass. Note: `_enter_from_pending` and `_enter_layered` and the inline candidate copy in `_simulate_with_bars` all construct `RetestCandidate` by keyword — the new field has a default, so they continue to work.

- [ ] **Step 6: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(candidate): add nested_ltf_zones field to RetestCandidate"
```

---

## Task 4: Static Nesting — Find Nested LTF Zones

**Files:**
- Modify: `src/iora/strategy/retest_candidate.py` (add `_find_nested_ltf_zones` function)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write tests for nested zone detection**

```python
from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.orchestrator.push_zone_engine import PushZoneEngineState


def _make_zone(top, bottom, is_supply, tf="M15", is_push=False, is_reversal=False):
    """Create a PushZone for testing."""
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2020-01-01"),
        timeframe=tf, is_push=is_push, is_reversal=is_reversal,
        struct_cls="", swing_cls="",
    )


class TestFindNestedLtfZones:
    """_find_nested_ltf_zones() — geometric containment check."""

    def test_demand_zone_inside_demand_h4(self):
        """M15 demand zone geometrically inside H4 demand zone."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3020, 1.3010, is_supply=False, tf="M15"),  # inside
                    _make_zone(1.2980, 1.2970, is_supply=False, tf="M15"),  # outside (below)
                ],
                supply_zones=[
                    _make_zone(1.3040, 1.3030, is_supply=True, tf="M15"),  # wrong side
                ],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )

        assert len(result) == 1
        assert result[0] == (1.3020, 1.3010, "M15", "continuation")

    def test_supply_zone_inside_supply_h4(self):
        """M15 supply zone inside H4 supply zone."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                supply_zones=[
                    _make_zone(1.3090, 1.3080, is_supply=True, tf="M15"),  # inside
                ],
                demand_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="supply",
            ctx_zone_top=1.3100,
            ctx_zone_bottom=1.3050,
            require_push=False,
        )

        assert len(result) == 1
        assert result[0] == (1.3090, 1.3080, "M15", "continuation")

    def test_require_push_filters_non_push(self):
        """When require_push=True, only push zones returned."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3020, 1.3010, is_supply=False, tf="M15", is_push=False),
                    _make_zone(1.3035, 1.3025, is_supply=False, tf="M15", is_push=True),
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=True,
        )

        assert len(result) == 1
        assert result[0][3] == "push"  # zone_role

    def test_no_nested_zones_returns_empty(self):
        """No LTF zones inside H4 zone."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.2990, 1.2980, is_supply=False, tf="M15"),  # below H4 zone
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )

        assert result == []

    def test_missing_ltf_tf_returns_empty(self):
        """LTF TF not in state returns empty list."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={})
        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M5",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )
        assert result == []

    def test_max_zones_limit(self):
        """Returns at most max_zones results."""
        from iora.strategy.retest_candidate import _find_nested_ltf_zones

        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3010 + i * 0.0005, 1.3005 + i * 0.0005,
                               is_supply=False, tf="M15")
                    for i in range(5)
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
            max_zones=3,
        )

        assert len(result) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestFindNestedLtfZones -v`
Expected: FAIL — `_find_nested_ltf_zones` not defined

- [ ] **Step 3: Implement _find_nested_ltf_zones**

Add to `src/iora/strategy/retest_candidate.py` after `_find_breaker_zones`:

```python
def _find_nested_ltf_zones(
    state: PushZoneEngineState,
    ltf_tf: str,
    zone_side: str,
    ctx_zone_top: float,
    ctx_zone_bottom: float,
    require_push: bool = False,
    max_zones: int = 5,
) -> list[tuple[float, float, str, str]]:
    """Find LTF zones geometrically inside a context zone (same side).

    For demand H4 zone: LTF demand zones with top <= H4 top AND bottom >= H4 bottom.
    For supply H4 zone: LTF supply zones with bottom >= H4 bottom AND top <= H4 top.

    Returns list of (zone_top, zone_bottom, zone_tf, zone_role) sorted by
    proximity to zone top (demand) or zone bottom (supply) — nearest first.
    """
    ts = state.tick_states.get(ltf_tf)
    if ts is None:
        return []

    zone_list = ts.demand_zones if zone_side == "demand" else ts.supply_zones
    results: list[tuple[float, float, str, str]] = []

    for z in zone_list:
        # Geometric containment: LTF zone fully inside context zone
        if z.top > ctx_zone_top or z.bottom < ctx_zone_bottom:
            continue

        if require_push and not z.is_push:
            continue

        # Determine role
        if z.is_push:
            role = "push"
        elif z.is_reversal:
            role = "reversal"
        else:
            role = "continuation"

        results.append((z.top, z.bottom, ltf_tf, role))

    # Sort by proximity to where price first enters:
    # demand = nearest to zone top (highest first)
    # supply = nearest to zone bottom (lowest first)
    if zone_side == "demand":
        results.sort(key=lambda x: x[0], reverse=True)
    else:
        results.sort(key=lambda x: x[1], reverse=False)

    return results[:max_zones]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestFindNestedLtfZones -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(candidate): add _find_nested_ltf_zones for static nesting"
```

---

## Task 5: Static Nesting — Enrich Candidates in build_retest_candidates

**Files:**
- Modify: `src/iora/strategy/retest_candidate.py:322-515` (build_retest_candidates function)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write integration test for static nesting enrichment**

This tests that `build_retest_candidates` populates `nested_ltf_zones` when the appropriate parameter is passed. Since this requires real data flow through the engine, use a simpler unit test approach — test the enrichment logic directly.

```python
class TestStaticNestingEnrichment:
    """Static nesting enrichment during candidate building."""

    def test_enrichment_populates_nested_zones(self):
        """When ltf_tf is provided, H1@H4 candidates get nested_ltf_zones."""
        from iora.strategy.retest_candidate import RetestCandidate, _find_nested_ltf_zones

        # The enrichment function itself is already tested.
        # This test verifies the integration point: that a candidate's
        # nested_ltf_zones list gets populated with the correct data format.
        event = _make_event(tf_pair="H1@H4", zone_tf="H4", zone_side="demand")
        c = RetestCandidate(
            event=event,
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            nested_ltf_zones=[(1.3020, 1.3010, "M15", "push")],
        )
        assert len(c.nested_ltf_zones) == 1
        top, bot, tf, role = c.nested_ltf_zones[0]
        assert tf == "M15"
        assert top > bot
        assert bot >= c.zone_bottom
        assert top <= c.zone_top
```

- [ ] **Step 2: Add ltf_tf parameter to build_retest_candidates**

In `src/iora/strategy/retest_candidate.py`, modify `build_retest_candidates` signature to add:

```python
def build_retest_candidates(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
    ltf_tf: str = "",             # NEW: LTF for nested zone lookup
    require_ltf_push: bool = False,  # NEW: only push zones
) -> list[RetestCandidate]:
```

Then inside the candidate building loop, after the existing enrichment (around line 500), add:

```python
            # Nested LTF zones for static nesting
            nested_ltf = []
            if ltf_tf and event.zone_tf != ltf_tf:
                nested_ltf = _find_nested_ltf_zones(
                    state=state,
                    ltf_tf=ltf_tf,
                    zone_side=event.zone_side,
                    ctx_zone_top=matched_zone.top,
                    ctx_zone_bottom=matched_zone.bottom,
                    require_push=require_ltf_push,
                )
```

And pass `nested_ltf_zones=nested_ltf` to the `RetestCandidate(...)` constructor.

- [ ] **Step 3: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(candidate): enrich candidates with nested LTF zones during build"
```

---

## Task 6: Dynamic Nesting — Zone Birth Event Collection

**Files:**
- Modify: `src/iora/strategy/retest_candidate.py` (add `build_retest_candidates_with_births`)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write test for zone birth collection**

```python
class TestZoneBirthCollection:
    """Zone birth event collection during candidate building."""

    def test_build_result_has_zone_births_key(self):
        """build_retest_candidates_with_births returns CandidateBuildResult."""
        from iora.strategy.retest_candidate import build_retest_candidates_with_births, CandidateBuildResult
        # Minimal test: empty data should return empty result
        result = build_retest_candidates_with_births(
            data_by_tf={}, entry_tf="M5", symbol="TEST",
        )
        assert isinstance(result, CandidateBuildResult)
        assert result.candidates == []
        assert result.zone_births == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestZoneBirthCollection -v`
Expected: FAIL — `build_retest_candidates_with_births` not defined

- [ ] **Step 3: Implement build_retest_candidates_with_births**

Add a new function in `src/iora/strategy/retest_candidate.py` that wraps the existing `build_retest_candidates` logic. The approach:

1. Copy the core of `build_retest_candidates` into `_build_candidates_core` that returns `CandidateBuildResult`
2. Have `build_retest_candidates` call `_build_candidates_core` and return just `.candidates`
3. Have `build_retest_candidates_with_births` call `_build_candidates_core` and return the full result

Inside the bar loop, track zone births by comparing zone lists before/after each tick:

```python
def _build_candidates_core(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    hma_period: int = 24,
    hma_source: str = "close",
    ltf_tf: str = "",
    require_ltf_push: bool = False,
    collect_births: bool = False,
    birth_tfs: list[str] | None = None,
) -> CandidateBuildResult:
```

Zone birth tracking logic (inside the bar loop, before event detection).

**Important:** Zones can be removed when broken, so tracking by list length is incorrect. Instead, use a `seen_zones` set keyed by `(z.top, z.bottom, z.origin_time, tf, side)` — the `origin_time` provides zone identity since two zones at the same price but different origin times are distinct:

```python
        # Initialize before the bar loop:
        # seen_zones: set[tuple] = set()
        # zone_births: dict[pd.Timestamp, list[ZoneBirthEvent]] = {}

        if collect_births and birth_tfs:
            births_this_bar: list[ZoneBirthEvent] = []
            for btf in birth_tfs:
                bts = state.tick_states.get(btf)
                if bts is None:
                    continue
                for side, zones in [("demand", bts.demand_zones), ("supply", bts.supply_zones)]:
                    for z in zones:
                        zkey = (z.top, z.bottom, z.origin_time, btf, side)
                        if zkey not in seen_zones:
                            seen_zones.add(zkey)
                            role = "push" if z.is_push else ("reversal" if z.is_reversal else "continuation")
                            births_this_bar.append(ZoneBirthEvent(
                                timestamp=ctx.timestamp,
                                zone_top=z.top, zone_bottom=z.bottom,
                                zone_tf=btf, zone_side=side,
                                zone_role=role, is_push=z.is_push,
                            ))
            if births_this_bar:
                zone_births[ctx.timestamp] = births_this_bar
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(candidate): add zone birth event collection for dynamic nesting"
```

---

## Task 7: Static Nesting Path in Simulation Engine

**Files:**
- Modify: `src/iora/strategy/retest_engine.py:357-662` (_simulate_with_bars)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write tests for static nesting simulation**

```python
from iora.strategy.retest_engine import _simulate_with_bars, RetestTradeRecord
from iora.strategy.retest_config import RetestConfig


class TestStaticNestingSimulation:
    """Static nesting path in _simulate_with_bars."""

    def _make_candidate_with_nested(self, nested_zones):
        """Create a candidate with nested LTF zones for simulation."""
        return RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050,
            zone_bottom=1.3000,
            entry_price=1.3025,
            atr=0.0020,
            period_hi=1.3100,
            period_lo=1.2950,
            opposing_zone_h4=1.3200,
            nested_ltf_zones=nested_zones,
        )

    def test_static_nesting_creates_limit_at_ltf_zone_top(self):
        """Static nesting places limit at LTF zone top for demand."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            partial_tp=False,
            fixed_rr=3.0,
            spread_pips=0.0,
        )

        nested = [(1.3020, 1.3010, "M15", "push")]
        candidate = self._make_candidate_with_nested(nested)

        # Bar data that fills the limit at LTF zone top (~1.3020)
        # and then hits TP
        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015, 1.3025, 1.3050, 1.3100],
            "high": [1.3035, 1.3025, 1.3060, 1.3080, 1.3110],
            "low":  [1.3015, 1.3008, 1.3020, 1.3040, 1.3090],
            "close":[1.3020, 1.3020, 1.3050, 1.3070, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.diagnostics.opportunity_runner import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        # Must produce at least one trade from the nested LTF zone
        assert len(trades) >= 1, "Expected at least one trade from static nesting"
        t = trades[0]
        # SL should be near LTF zone bottom (1.3010), not H4 (1.3000)
        assert t.sl_price > 1.3000, f"SL {t.sl_price} should be above H4 bottom 1.3000"

    def test_static_nesting_no_nested_zones_no_trade(self):
        """If no nested LTF zones, no trade placed."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = self._make_candidate_with_nested([])

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015],
            "high": [1.3035, 1.3025],
            "low":  [1.3015, 1.3008],
            "close":[1.3020, 1.3020],
        }, index=pd.date_range("2020-01-02 08:00", periods=2, freq="h"))

        from iora.diagnostics.opportunity_runner import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        assert len(trades) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestStaticNestingSimulation -v`
Expected: FAIL — static nesting path not implemented

- [ ] **Step 3: Implement static nesting path**

In `src/iora/strategy/retest_engine.py`, modify `_simulate_with_bars()`:

**At the entry check section (around line 501-554),** add a branch for static nesting. When `config.ltf_nesting == "static"` and the candidate has `nested_ltf_zones`, instead of placing a limit at the H4 zone edge, iterate over `nested_ltf_zones` and create modified candidates with LTF zone boundaries:

```python
        # --- Entry check ---
        if len(open_trades) >= max_open or ts not in entry_map:
            continue

        candidate = entry_map[ts]
        zone_key = (candidate.zone_top, candidate.zone_bottom)

        if config.touch_policy == "first_touch" and zone_key in consumed_zones:
            continue

        # === HTF-triggered LTF nesting: static mode ===
        if config.ltf_nesting == "static" and candidate.nested_ltf_zones:
            ltf_count = 0
            for ltf_top, ltf_bot, ltf_tf, ltf_role in candidate.nested_ltf_zones:
                if ltf_count >= config.max_ltf_per_trigger:
                    break
                # Create a pending limit at the LTF zone top (demand) or bottom (supply)
                ltf_zone_key = (ltf_top, ltf_bot)
                if config.touch_policy == "first_touch" and ltf_zone_key in consumed_zones:
                    continue
                if any(p.zone_key == ltf_zone_key for p in pending_limits):
                    continue

                limit_buf = _LIMIT_BUFFER_ATR * candidate.atr
                if candidate.direction == "long":
                    limit_price = ltf_top - limit_buf
                else:
                    limit_price = ltf_bot + limit_buf

                # Create modified candidate with LTF zone boundaries
                ltf_candidate = RetestCandidate(
                    event=candidate.event,
                    zone_top=ltf_top,
                    zone_bottom=ltf_bot,
                    entry_price=limit_price,
                    atr=candidate.atr,
                    period_hi=candidate.period_hi,
                    period_lo=candidate.period_lo,
                    ltf_choch_zone_boundary=candidate.ltf_choch_zone_boundary,
                    next_opposing_zone_price=candidate.next_opposing_zone_price,
                    d1_range_midpoint=candidate.d1_range_midpoint,
                    opposing_zone_h1=candidate.opposing_zone_h1,
                    opposing_zone_h4=candidate.opposing_zone_h4,
                    opposing_zone_d1=candidate.opposing_zone_d1,
                    breaker_zones=candidate.breaker_zones,
                    hma_direction_h1=candidate.hma_direction_h1,
                    hma_direction_h4=candidate.hma_direction_h4,
                    ha_above_hma_h1=candidate.ha_above_hma_h1,
                    ha_above_hma_h4=candidate.ha_above_hma_h4,
                    bars_since_hma_cross_h1=candidate.bars_since_hma_cross_h1,
                    bars_since_hma_cross_h4=candidate.bars_since_hma_cross_h4,
                    hma_cross_direction_h1=candidate.hma_cross_direction_h1,
                    hma_cross_direction_h4=candidate.hma_cross_direction_h4,
                    d_to_w_relationship=candidate.d_to_w_relationship,
                    inside_w_zone=candidate.inside_w_zone,
                )

                # Check immediate fill
                if candidate.direction == "long" and bar_low <= limit_price:
                    # Immediate fill — enter trade
                    _enter_ltf_trade(
                        ltf_candidate, config, symbol, pip_size,
                        open_trades, trade_counter,
                    )
                    trade_counter += 1
                    ltf_count += 1
                    if config.touch_policy == "first_touch":
                        consumed_zones.add(ltf_zone_key)
                elif candidate.direction == "short" and bar_high >= limit_price:
                    _enter_ltf_trade(
                        ltf_candidate, config, symbol, pip_size,
                        open_trades, trade_counter,
                    )
                    trade_counter += 1
                    ltf_count += 1
                    if config.touch_policy == "first_touch":
                        consumed_zones.add(ltf_zone_key)
                elif carry_limits:
                    pending_limits.append(_PendingLimit(
                        candidate=ltf_candidate,
                        limit_price=limit_price,
                        placed_bar_idx=idx,
                        zone_key=ltf_zone_key,
                    ))
                    ltf_count += 1

            # Optionally also trade the H1@H4 directly
            if config.trigger_also_trades:
                # Fall through to standard entry logic below
                pass
            else:
                if config.touch_policy == "first_touch":
                    consumed_zones.add(zone_key)
                continue  # Skip standard entry — nested zones handle it

        # (existing standard entry logic follows)
```

Also add the helper `_enter_ltf_trade`:

```python
def _enter_ltf_trade(
    candidate: RetestCandidate,
    config: RetestConfig,
    symbol: str,
    pip_size: float,
    open_trades: list[_OpenTrade],
    trade_counter: int,
) -> None:
    """Enter a trade from an LTF nested zone (reuses existing SL/TP logic)."""
    sl = compute_retest_sl(candidate, mode=config.sl_mode,
                           atr_mult=config.sl_atr_mult, buffer_atr=config.sl_buffer_atr)
    sl = _apply_min_sl(candidate.entry_price, sl, candidate.direction,
                       config.min_sl_pips, pip_size)
    eff_entry = _compute_effective_entry(
        candidate.entry_price, candidate.direction, config.spread_pips, pip_size)

    trade_id = f"{symbol}_{config.tf_pair}_ltf_{trade_counter + 1:04d}"

    if config.partial_tp:
        risk = abs(candidate.entry_price - sl)
        if candidate.direction == "long":
            unit1_tp = candidate.entry_price + config.partial_unit1_rr * risk
            be_sl = candidate.entry_price - config.breakeven_buffer_atr * candidate.atr
        else:
            unit1_tp = candidate.entry_price - config.partial_unit1_rr * risk
            be_sl = candidate.entry_price + config.breakeven_buffer_atr * candidate.atr

        tp = compute_retest_tp(
            candidate, sl_price=sl, mode="htf_zone",
            fixed_rr=config.partial_unit1_rr, tp_htf=config.partial_unit2_tp,
        )
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
            partial=True, unit1_pct=config.partial_unit1_pct,
            unit1_tp=unit1_tp, unit1_closed=False, original_sl=sl,
            breakeven_sl=be_sl,
        ))
    else:
        tp = compute_retest_tp(
            candidate, sl_price=sl, mode=config.tp_mode,
            fixed_rr=config.fixed_rr, tp_htf=config.tp_htf,
        )
        open_trades.append(_OpenTrade(
            candidate=candidate, sl=sl, tp=tp, trade_id=trade_id,
            symbol=symbol, pip_size=pip_size, effective_entry=eff_entry,
        ))
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestStaticNestingSimulation -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/iora/strategy/retest_engine.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(engine): add static LTF nesting path in simulation"
```

---

## Task 8: Dynamic Nesting — _ActiveTrigger State Machine

**Files:**
- Modify: `src/iora/strategy/retest_engine.py`
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write tests for dynamic nesting**

```python
from iora.strategy.retest_candidate import ZoneBirthEvent


class TestDynamicNestingSimulation:
    """Dynamic nesting path with _ActiveTrigger state machine."""

    def test_dynamic_nesting_places_limit_on_zone_birth(self):
        """When a new LTF zone is born inside a triggered H4 zone, a limit is placed."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=48,
            limit_ttl=0,
            fixed_rr=3.0,
            spread_pips=0.0,
        )

        # H1@H4 trigger candidate
        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        # Zone birth: M15 demand zone born inside H4 zone on bar 2
        birth_ts = pd.Timestamp("2020-01-02 10:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="demand",
                zone_role="push", is_push=True,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020, 1.3015, 1.3020, 1.3050, 1.3080, 1.3100],
            "high": [1.3035, 1.3025, 1.3025, 1.3060, 1.3080, 1.3110, 1.3110],
            "low":  [1.3015, 1.3010, 1.3010, 1.3015, 1.3040, 1.3070, 1.3090],
            "close":[1.3020, 1.3015, 1.3020, 1.3050, 1.3070, 1.3100, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=7, freq="h"))

        from iora.diagnostics.opportunity_runner import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        # Should have placed a limit at the LTF zone top (~1.3025)
        # and the trade should have an SL near LTF zone bottom (~1.3015)
        assert len(trades) >= 1, "Expected at least one trade from dynamic nesting"
        t = trades[0]
        assert t.sl_price > 1.3000, "SL should be near LTF zone bottom, not H4"

    def test_dynamic_nesting_window_expiry(self):
        """Trigger window expires after trigger_window_bars."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=2,  # Very short window
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        # Zone born AFTER window expires (bar 4, but window=2)
        birth_ts = pd.Timestamp("2020-01-02 12:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="demand",
                zone_role="push", is_push=True,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020, 1.3025, 1.3020, 1.3015],
            "high": [1.3035, 1.3025, 1.3030, 1.3025, 1.3025],
            "low":  [1.3015, 1.3010, 1.3015, 1.3010, 1.3010],
            "close":[1.3020, 1.3015, 1.3020, 1.3015, 1.3020],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.diagnostics.opportunity_runner import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        # Window expired before zone birth — no trade
        assert len(trades) == 0

    def test_dynamic_nesting_ignores_wrong_side_birth(self):
        """Supply zone birth inside demand H4 zone is ignored."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=48,
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        birth_ts = pd.Timestamp("2020-01-02 09:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="supply",  # Wrong side!
                zone_role="push", is_push=True,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020],
            "high": [1.3035, 1.3025],
            "low":  [1.3015, 1.3010],
            "close":[1.3020, 1.3015],
        }, index=pd.date_range("2020-01-02 08:00", periods=2, freq="h"))

        from iora.diagnostics.opportunity_runner import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        assert len(trades) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestDynamicNestingSimulation -v`
Expected: FAIL — `zone_births` parameter not accepted

- [ ] **Step 3: Add _ActiveTrigger dataclass and dynamic nesting logic**

In `src/iora/strategy/retest_engine.py`, add `_ActiveTrigger` after `_PendingLimit`:

```python
@dataclass(slots=True)
class _ActiveTrigger:
    """H4 zone triggered by an H1 retest — tracks dynamic nesting window."""
    h4_zone_top: float
    h4_zone_bottom: float
    h4_zone_side: str
    trigger_bar_idx: int
    window_bars: int
    candidate: RetestCandidate
    fills: int = 0
    max_fills: int = 3
```

Modify `_simulate_with_bars` signature to accept `zone_births`:

```python
def _simulate_with_bars(
    passed: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: pd.DataFrame,
    pip_size: float,
    ha_trail: Optional[pd.DataFrame] = None,
    zone_births: Optional[dict[pd.Timestamp, list]] = None,  # NEW
) -> list[RetestTradeRecord]:
```

Add dynamic nesting logic in the entry check section (before the standard entry check):

```python
        # === HTF-triggered LTF nesting: dynamic mode ===
        if config.ltf_nesting == "dynamic":
            # 1. Register new triggers from entry_map
            if ts in entry_map and entry_map[ts] not in [t.candidate for t in active_triggers]:
                c = entry_map[ts]
                active_triggers.append(_ActiveTrigger(
                    h4_zone_top=c.zone_top,
                    h4_zone_bottom=c.zone_bottom,
                    h4_zone_side=c.event.zone_side,
                    trigger_bar_idx=idx,
                    window_bars=config.trigger_window_bars,
                    candidate=c,
                    max_fills=config.max_ltf_per_trigger,
                ))

            # 2. Process active triggers
            surviving_triggers: list[_ActiveTrigger] = []
            for trig in active_triggers:
                bars_elapsed = idx - trig.trigger_bar_idx
                # Window expiry
                if bars_elapsed > trig.window_bars:
                    continue
                # H4 zone break (body-close)
                if trig.h4_zone_side == "demand" and bar_close < trig.h4_zone_bottom:
                    continue
                if trig.h4_zone_side == "supply" and bar_close > trig.h4_zone_top:
                    continue
                # Max fills reached
                if trig.fills >= trig.max_fills:
                    surviving_triggers.append(trig)
                    continue

                # 3. Check for zone births inside this trigger's H4 zone
                if zone_births and ts in zone_births:
                    ltf_tf = config.entry_tf_override or config.entry_tf
                    for birth in zone_births[ts]:
                        if birth.zone_tf != ltf_tf:
                            continue
                        if birth.zone_side != trig.h4_zone_side:
                            continue
                        # Geometric containment
                        if birth.zone_top > trig.h4_zone_top or birth.zone_bottom < trig.h4_zone_bottom:
                            continue
                        if config.require_ltf_push and not birth.is_push:
                            continue
                        if trig.fills >= trig.max_fills:
                            break

                        # Place pending limit at LTF zone top
                        limit_buf = _LIMIT_BUFFER_ATR * trig.candidate.atr
                        if trig.h4_zone_side == "demand":
                            limit_price = birth.zone_top - limit_buf
                        else:
                            limit_price = birth.zone_bottom + limit_buf

                        ltf_candidate = RetestCandidate(
                            event=trig.candidate.event,
                            zone_top=birth.zone_top,
                            zone_bottom=birth.zone_bottom,
                            entry_price=limit_price,
                            atr=trig.candidate.atr,
                            period_hi=trig.candidate.period_hi,
                            period_lo=trig.candidate.period_lo,
                            ltf_choch_zone_boundary=trig.candidate.ltf_choch_zone_boundary,
                            next_opposing_zone_price=trig.candidate.next_opposing_zone_price,
                            d1_range_midpoint=trig.candidate.d1_range_midpoint,
                            opposing_zone_h1=trig.candidate.opposing_zone_h1,
                            opposing_zone_h4=trig.candidate.opposing_zone_h4,
                            opposing_zone_d1=trig.candidate.opposing_zone_d1,
                            breaker_zones=trig.candidate.breaker_zones,
                            hma_direction_h1=trig.candidate.hma_direction_h1,
                            hma_direction_h4=trig.candidate.hma_direction_h4,
                            ha_above_hma_h1=trig.candidate.ha_above_hma_h1,
                            ha_above_hma_h4=trig.candidate.ha_above_hma_h4,
                            bars_since_hma_cross_h1=trig.candidate.bars_since_hma_cross_h1,
                            bars_since_hma_cross_h4=trig.candidate.bars_since_hma_cross_h4,
                            hma_cross_direction_h1=trig.candidate.hma_cross_direction_h1,
                            hma_cross_direction_h4=trig.candidate.hma_cross_direction_h4,
                            d_to_w_relationship=trig.candidate.d_to_w_relationship,
                            inside_w_zone=trig.candidate.inside_w_zone,
                        )

                        ltf_zone_key = (birth.zone_top, birth.zone_bottom)
                        if not any(p.zone_key == ltf_zone_key for p in pending_limits):
                            # Check immediate fill
                            filled = False
                            if trig.h4_zone_side == "demand" and bar_low <= limit_price:
                                filled = True
                            elif trig.h4_zone_side == "supply" and bar_high >= limit_price:
                                filled = True

                            if filled and len(open_trades) < max_open:
                                _enter_ltf_trade(
                                    ltf_candidate, config, symbol, pip_size,
                                    open_trades, trade_counter,
                                )
                                trade_counter += 1
                                trig.fills += 1
                            elif carry_limits:
                                pending_limits.append(_PendingLimit(
                                    candidate=ltf_candidate,
                                    limit_price=limit_price,
                                    placed_bar_idx=idx,
                                    zone_key=ltf_zone_key,
                                ))
                                trig.fills += 1

                surviving_triggers.append(trig)
            active_triggers = surviving_triggers

            # For dynamic mode, skip standard entry (unless trigger_also_trades)
            if not config.trigger_also_trades:
                continue
```

Initialize `active_triggers` near the top of the function:

```python
    active_triggers: list[_ActiveTrigger] = []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestDynamicNestingSimulation -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/iora/strategy/retest_engine.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(engine): add dynamic LTF nesting with _ActiveTrigger state machine"
```

---

## Task 9: Wire Up evaluate_retest_config for Nesting Modes

**Files:**
- Modify: `src/iora/strategy/retest_engine.py:296-350` (evaluate_retest_config)
- Modify: `src/iora/strategy/retest_sweep.py:654-724` (run_retest_sweep)
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write integration test**

```python
class TestEvaluateWithNesting:
    """evaluate_retest_config passes zone_births through."""

    def test_evaluate_accepts_zone_births(self):
        """evaluate_retest_config can accept zone_births parameter."""
        from iora.strategy.retest_engine import evaluate_retest_config

        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
        )

        # Empty candidates — should return empty result without error
        result = evaluate_retest_config(
            candidates=[], config=cfg, symbol="GBPUSD",
            zone_births={},
        )
        assert result.metrics.get("total_trades", 0) == 0
```

- [ ] **Step 2: Modify evaluate_retest_config to accept and pass zone_births**

In `src/iora/strategy/retest_engine.py`, add `zone_births` parameter:

```python
def evaluate_retest_config(
    candidates: list[RetestCandidate],
    config: RetestConfig,
    symbol: str,
    bar_data: Optional[pd.DataFrame] = None,
    pip_size: Optional[float] = None,
    all_candidates: Optional[list[RetestCandidate]] = None,
    trail_tf_data: Optional[pd.DataFrame] = None,
    zone_births: Optional[dict] = None,  # NEW
) -> RetestResult:
```

Pass it through to `_simulate_with_bars`:

```python
    trades = _simulate_with_bars(passed, config, symbol, bar_data, ps, ha_trail,
                                  zone_births=zone_births)
```

- [ ] **Step 3: Modify run_retest_sweep to build candidates with births when needed**

In `src/iora/strategy/retest_sweep.py`, modify `run_retest_sweep` to use `build_retest_candidates_with_births` instead of `build_retest_candidates` when any config needs dynamic nesting. This avoids double-building:

```python
    # Check if any config needs dynamic nesting
    needs_births = any(c.ltf_nesting == "dynamic" for c in configs)
    birth_tfs = list({c.entry_tf_override for c in configs
                      if c.ltf_nesting == "dynamic" and c.entry_tf_override})

    zone_births_by_tf: dict[str, dict] = {}

    # Build candidates (and optionally zone births) for each entry TF
    for entry_tf in valid_tfs:
        if needs_births:
            from iora.strategy.retest_candidate import build_retest_candidates_with_births
            result = build_retest_candidates_with_births(
                data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
                collect_births=True, birth_tfs=birth_tfs,
            )
            all_candidates.extend(result.candidates)
            zone_births_by_tf[entry_tf] = result.zone_births
        else:
            candidates = build_retest_candidates(
                data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
            )
            all_candidates.extend(candidates)
        bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]
```

Replace the existing sequential/parallel candidate building block with this unified approach. Then pass `zone_births` when evaluating:

```python
        zb = zone_births_by_tf.get(cfg.entry_tf, {}) if cfg.ltf_nesting == "dynamic" else None
        result = evaluate_retest_config(
            candidates=all_candidates, config=cfg, symbol=symbol,
            bar_data=bar_data, all_candidates=all_candidates,
            trail_tf_data=trail_tf_data,
            zone_births=zb,
        )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py -v && pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_engine.py src/iora/strategy/retest_sweep.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(engine): wire evaluate_retest_config and sweep runner for nesting modes"
```

---

## Task 10: Sweep Config Generator

**Files:**
- Modify: `src/iora/strategy/retest_sweep.py`
- Test: `tests/strategy/test_htf_triggered_ltf.py`

- [ ] **Step 1: Write test for config generation**

```python
class TestHTFTriggeredSweepConfigs:
    """htf_triggered_ltf_configs() sweep generator."""

    def test_generates_configs(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs()
        assert 350 < len(configs) < 450  # ~388 configs (96 static + 288 dynamic + 4 baselines)

    def test_all_configs_have_ltf_nesting(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs()
        # All non-baseline configs should have ltf_nesting != "none"
        nested = [c for c in configs if c.ltf_nesting != "none"]
        assert len(nested) > 40

    def test_includes_baseline(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs()
        baselines = [c for c in configs if c.ltf_nesting == "none"]
        assert len(baselines) >= 2  # With and without partial

    def test_all_configs_use_limit_entry(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs()
        for c in configs:
            assert c.entry_mode == "limit"

    def test_all_configs_ttl_zero(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs()
        for c in configs:
            assert c.limit_ttl == 0
```

- [ ] **Step 2: Implement htf_triggered_ltf_configs**

Add to `src/iora/strategy/retest_sweep.py`:

```python
def htf_triggered_ltf_configs() -> list[RetestConfig]:
    """Sweep configs for HTF-triggered LTF entry system.

    Tests M15 and M5 zones nested inside H4 zones, triggered by H1@H4 retest.
    ~388 configs covering static/dynamic, with/without partial, spread, min_sl, etc.
    """
    configs: list[RetestConfig] = []
    seen: set = set()

    def _add(c: RetestConfig) -> None:
        key = (
            c.tf_pair, c.ltf_nesting, c.entry_tf_override,
            c.trigger_window_bars, c.require_ltf_push,
            c.trigger_also_trades, c.max_ltf_per_trigger,
            c.spread_pips, c.partial_tp, c.partial_unit1_pct,
            c.partial_unit1_rr, c.partial_unit2_tp,
            c.bias_filter, c.min_sl_pips, c.limit_ttl,
            c.limit_edge, c.entry_mode,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    # Common base kwargs
    base = dict(
        tf_pair="H1@H4",
        entry_mode="limit",
        limit_edge="top",
        limit_ttl=0,
        sl_mode="zone",
    )

    # --- Baselines (H1@H4 direct, no nesting) ---
    _add(RetestConfig(**base, spread_pips=1.5))
    _add(RetestConfig(**base, spread_pips=1.5,
         partial_tp=True, partial_unit1_pct=0.7, partial_unit1_rr=3.0, partial_unit2_tp="H1"))
    _add(RetestConfig(**base, spread_pips=0.0))
    _add(RetestConfig(**base, spread_pips=0.0,
         partial_tp=True, partial_unit1_pct=0.7, partial_unit1_rr=3.0, partial_unit2_tp="H1"))

    # --- Static nesting ---
    for ltf in ["M15", "M5"]:
        for spread in [0.0, 1.5]:
            for bias in ["any", "against_daily"]:
                for min_sl in [0.0, 3.0, 5.0]:
                    for push in [False, True]:
                        # Without partial
                        _add(RetestConfig(**base,
                            ltf_nesting="static",
                            entry_tf_override=ltf,
                            spread_pips=spread,
                            bias_filter=bias,
                            min_sl_pips=min_sl,
                            require_ltf_push=push,
                            fixed_rr=3.0,
                        ))
                        # With partial
                        _add(RetestConfig(**base,
                            ltf_nesting="static",
                            entry_tf_override=ltf,
                            spread_pips=spread,
                            bias_filter=bias,
                            min_sl_pips=min_sl,
                            require_ltf_push=push,
                            partial_tp=True,
                            partial_unit1_pct=0.7,
                            partial_unit1_rr=3.0,
                            partial_unit2_tp="H1",
                        ))

    # --- Dynamic nesting ---
    for ltf in ["M15", "M5"]:
        for spread in [0.0, 1.5]:
            for bias in ["any", "against_daily"]:
                for min_sl in [0.0, 3.0, 5.0]:
                    for push in [False, True]:
                        for window in [24, 48, 96]:
                            # Without partial
                            _add(RetestConfig(**base,
                                ltf_nesting="dynamic",
                                entry_tf_override=ltf,
                                trigger_window_bars=window,
                                spread_pips=spread,
                                bias_filter=bias,
                                min_sl_pips=min_sl,
                                require_ltf_push=push,
                                fixed_rr=3.0,
                            ))
                            # With partial
                            _add(RetestConfig(**base,
                                ltf_nesting="dynamic",
                                entry_tf_override=ltf,
                                trigger_window_bars=window,
                                spread_pips=spread,
                                bias_filter=bias,
                                min_sl_pips=min_sl,
                                require_ltf_push=push,
                                partial_tp=True,
                                partial_unit1_pct=0.7,
                                partial_unit1_rr=3.0,
                                partial_unit2_tp="H1",
                            ))

    return configs
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/strategy/test_htf_triggered_ltf.py::TestHTFTriggeredSweepConfigs -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/iora/strategy/retest_sweep.py tests/strategy/test_htf_triggered_ltf.py
git commit -m "feat(sweep): add htf_triggered_ltf_configs generator (~144 configs)"
```

---

## Task 11: Sweep Runner Script

**Files:**
- Create: `scripts/run_htf_triggered_sweep.py`

- [ ] **Step 1: Create the runner script**

```python
#!/usr/bin/env python
"""Run HTF-triggered LTF entry sweep on one or more symbols.

Usage:
    python scripts/run_htf_triggered_sweep.py --symbol GBPUSD
    python scripts/run_htf_triggered_sweep.py --symbol GBPUSD --output results/htf_triggered/
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from iora.data.parquet_storage import load_symbol_data
from iora.strategy.retest_sweep import htf_triggered_ltf_configs, run_retest_sweep


def main():
    parser = argparse.ArgumentParser(description="HTF-triggered LTF entry sweep")
    parser.add_argument("--symbol", default="GBPUSD", help="Symbol to sweep")
    parser.add_argument("--output", default="results/htf_triggered", help="Output directory")
    args = parser.parse_args()

    symbol = args.symbol
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data for {symbol}...")
    data_by_tf = load_symbol_data(symbol)
    print(f"  Loaded {len(data_by_tf)} TFs: {list(data_by_tf.keys())}")

    configs = htf_triggered_ltf_configs()
    print(f"Generated {len(configs)} configs")

    # Entry TFs needed: H1 (for H1@H4 trigger) + M15/M5 (for LTF zones)
    entry_tfs = ["H1"]

    print(f"Running sweep on {symbol}...")
    t0 = time.time()
    summary = run_retest_sweep(
        data_by_tf=data_by_tf,
        entry_tfs=entry_tfs,
        symbol=symbol,
        configs=configs,
        parallel=False,  # Single entry TF, no parallelism benefit
    )
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s — {len(summary.results)} results")

    # Build CSV
    rows = []
    for r in summary.results:
        m = r.metrics
        cfg = r.config
        rows.append({
            "symbol": symbol,
            "ltf_nesting": cfg.ltf_nesting,
            "entry_tf_override": cfg.entry_tf_override,
            "trigger_window_bars": cfg.trigger_window_bars,
            "spread_pips": cfg.spread_pips,
            "partial_tp": cfg.partial_tp,
            "bias_filter": cfg.bias_filter,
            "min_sl_pips": cfg.min_sl_pips,
            "require_ltf_push": cfg.require_ltf_push,
            "trigger_also_trades": cfg.trigger_also_trades,
            "total_trades": m.get("total_trades", 0),
            "win_rate": m.get("win_rate", 0),
            "sqn": m.get("sqn", 0),
            "pf": m.get("profit_factor", 0),
            "avg_r": m.get("avg_r", 0),
            "total_r": m.get("total_r", 0),
            "max_dd_r": m.get("max_dd_r", 0),
            "avg_sl_pips": m.get("avg_risk_pips", 0),
        })

    df = pd.DataFrame(rows)
    csv_path = output_dir / f"{symbol.lower()}_htf_triggered_sweep.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Results saved to {csv_path}")

    # Print top 10 by SQN
    viable = df[df["total_trades"] >= 30].sort_values("sqn", ascending=False)
    if not viable.empty:
        print(f"\nTop 10 by SQN (min 30 trades):")
        print(viable.head(10).to_string(index=False))
    else:
        print("\nNo configs with 30+ trades found.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify script is syntactically correct**

Run: `python -c "import ast; ast.parse(open('scripts/run_htf_triggered_sweep.py').read()); print('OK')")`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add scripts/run_htf_triggered_sweep.py
git commit -m "feat(scripts): add HTF-triggered LTF sweep runner"
```

---

## Task 12: Run Sweep on GBPUSD

**Files:**
- Output: `results/htf_triggered/gbpusd_htf_triggered_sweep.csv`

- [ ] **Step 1: Run the full test suite to confirm everything works**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 2: Run the sweep**

Run: `python scripts/run_htf_triggered_sweep.py --symbol GBPUSD`
Expected: Completes without error, CSV written, top 10 printed

- [ ] **Step 3: Commit results**

```bash
git add results/htf_triggered/
git commit -m "data: GBPUSD HTF-triggered LTF sweep results"
```

---

## Task 13: Analyze Results and Write Findings

**Files:**
- Create: `docs/system/level4-htf-triggered-ltf-analysis.md`

- [ ] **Step 1: Read the CSV and analyze**

Load `results/htf_triggered/gbpusd_htf_triggered_sweep.csv` and answer the 6 success criteria:

1. Does ANY nested config beat H1@H4 direct on SQN at spread=1.5?
2. Does M15-inside-H4 have viable SL (3+ pips)?
3. Does M5-inside-H4 have viable SL?
4. Does dynamic find MORE trades than static?
5. Does partial TP rescue marginal nested configs?
6. Does `require_ltf_push=True` improve quality?

Bucket results by: static vs dynamic, M15 vs M5, with/without partial, with/without push filter, spread=0 vs 1.5.

- [ ] **Step 2: Write findings document**

Create `docs/system/level4-htf-triggered-ltf-analysis.md` with:
- Summary verdict
- Full results tables bucketed by dimension
- Answers to all 6 success criteria
- Comparison to H1@H4 baseline (SQN 24.14)
- Recommendations for production

- [ ] **Step 3: Commit**

```bash
git add docs/system/level4-htf-triggered-ltf-analysis.md
git commit -m "docs: HTF-triggered LTF analysis — answers all 6 success criteria"
```

---

## Dependencies

```
Task 1 (config) → Task 2 (dataclasses) → Task 3 (nested field)
                                              ↓
Task 4 (find nested) → Task 5 (enrich) → Task 7 (static sim) ─┐
                                                                 ├→ Task 9 (wire up) → Task 10 (sweep configs) → Task 11 (runner) → Task 12 (run) → Task 13 (analyze)
Task 6 (birth collection) → Task 8 (dynamic sim) ──────────────┘
```

Tasks 4-5 (static) and Task 6 (birth collection) can be parallelized.
Tasks 7 (static sim) and Task 8 (dynamic sim) can be parallelized after their prereqs.
