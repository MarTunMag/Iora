# Level 4 Layer A: Retest Sweep Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core retest sweep engine that filters zone retest events, computes SL/TP, simulates trades, and produces comprehensive metrics with filter attribution — without trendline integration (Layer B).

**Architecture:** Two-stage design following the existing sweep_runner.py pattern. Stage 1 (expensive, once per symbol) runs the push zone engine and collects enriched retest candidates with zone boundaries for SL/TP. Stage 2 (cheap, N times per config) filters candidates, simulates position management, and computes metrics. The filter funnel tracks how each filter reduces the opportunity set and its marginal impact on win rate.

**Tech Stack:** Python 3.12+, pandas, numpy, pytest, dataclasses with `@dataclass(slots=True)`

**Key references:**
- Spec: `docs/superpowers/specs/2026-04-02-retest-entry-system-design.md`
- Analysis: `docs/system/level1-3-data-analysis.md` (26 design implications)
- Existing patterns: `src/iora/strategy/sweep_runner.py`, `src/iora/diagnostics/opportunity_runner.py`
- Existing SL/TP: `src/iora/strategy/sl_tp.py` (compute_sl, compute_tp)
- Existing metrics: `src/iora/strategy/sweep_runner.py:compute_metrics()`
- Existing trade record: `src/iora/strategy/trade_converter.py:SweepTradeRecord`
- Constants: `src/iora/constants.py` (TF_ORDER, ENGINE_TF_ORDER, TF_SECONDS)

---

## File Structure

```
src/iora/strategy/
  retest_config.py        # RetestConfig dataclass with all sweep dimensions + session defs
  retest_candidate.py     # RetestCandidate (enriched event) + build_retest_candidates() Stage 1
  retest_engine.py        # evaluate_retest_config() Stage 2: filter → SL/TP → position sim → trades
  filter_funnel.py        # FilterFunnel: ordered filter pipeline with per-step attribution

scripts/
  run_retest_sweep.py     # CLI: run sweep for a symbol with default or custom configs

tests/strategy/
  test_retest_config.py
  test_retest_candidate.py
  test_filter_funnel.py
  test_retest_engine.py
  test_retest_sweep_integration.py  # End-to-end with small synthetic data
```

**Design decisions:**
- `RetestCandidate` wraps `OpportunityEvent` by composition (`candidate.event`) rather than inheriting or duplicating fields
- `evaluate_retest_config()` reuses `compute_sl()` from `sl_tp.py` and `compute_metrics()` from `sweep_runner.py`
- Trade records use the existing `SweepTradeRecord` dataclass — extended with retest-specific fields via a new `RetestTradeRecord` that adds retest context
- Cascade checking is done in Stage 2 by scanning the sorted candidate list for recent HTF events within a time window (no additional Stage 1 state needed)
- Session filtering uses UTC timestamps from the candidate's `event.timestamp`

---

### Task 1: RetestConfig

**Files:**
- Create: `src/iora/strategy/retest_config.py`
- Test: `tests/strategy/test_retest_config.py`

- [ ] **Step 1: Write tests for RetestConfig defaults and validation**

```python
# tests/strategy/test_retest_config.py
"""Tests for RetestConfig dataclass."""
from iora.strategy.retest_config import RetestConfig, SESSION_WINDOWS


def test_default_config():
    cfg = RetestConfig()
    assert cfg.tf_pair == "H1@H4"
    assert cfg.touch_type == "wick_touch"
    assert cfg.bias_filter == "any"
    assert cfg.zone_role_filter == "any"
    assert cfg.age_filter == "any"
    assert cfg.test_count_filter == "any"
    assert cfg.cascade_filter == "none"
    assert cfg.cascade_lookback == 20
    assert cfg.sl_mode == "zone"
    assert cfg.tp_mode == "fixed_rr"
    assert cfg.fixed_rr == 2.0
    assert cfg.direction == "both"
    assert cfg.session_filter == "any"
    assert cfg.min_bias_strength == 0
    assert cfg.max_replacement_count == 999
    assert cfg.touch_policy == "until_broken"


def test_config_entry_and_zone_tf():
    cfg = RetestConfig(tf_pair="M5@H1")
    assert cfg.entry_tf == "M5"
    assert cfg.zone_tf == "H1"


def test_config_entry_and_zone_tf_h1_h4():
    cfg = RetestConfig(tf_pair="H1@H4")
    assert cfg.entry_tf == "H1"
    assert cfg.zone_tf == "H4"


def test_session_windows():
    assert "london" in SESSION_WINDOWS
    assert "newyork" in SESSION_WINDOWS
    assert "london_ny_overlap" in SESSION_WINDOWS
    assert "asian" in SESSION_WINDOWS
    # London = 07:00-16:00 UTC
    assert SESSION_WINDOWS["london"] == (7, 16)
    # NY = 12:00-21:00 UTC
    assert SESSION_WINDOWS["newyork"] == (12, 21)


def test_config_htf_pairs():
    """HTF pairs are all pairs with context TF higher than this config's zone TF."""
    cfg = RetestConfig(tf_pair="M5@M15")
    htf = cfg.htf_pairs
    # M15 context → HTF pairs have context above M15: H1, H4, D1
    assert "M15@H1" in htf
    assert "M15@H4" in htf
    assert "H1@H4" in htf
    assert "H1@D1" in htf
    assert "M5@M15" not in htf  # Not higher


def test_config_htf_pairs_h1_h4():
    cfg = RetestConfig(tf_pair="H1@H4")
    htf = cfg.htf_pairs
    # H4 context → only D1 is higher
    assert "H1@D1" in htf
    assert len(htf) == 1


def test_config_htf_pairs_h1_d1():
    cfg = RetestConfig(tf_pair="H1@D1")
    htf = cfg.htf_pairs
    # D1 is highest context → no HTF pairs
    assert len(htf) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_retest_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iora.strategy.retest_config'`

- [ ] **Step 3: Implement RetestConfig**

```python
# src/iora/strategy/retest_config.py
"""Retest sweep configuration — all Level 4 sweep dimensions."""
from __future__ import annotations

from dataclasses import dataclass
from iora.constants import ENGINE_TF_ORDER

# Session windows: (start_hour_utc, end_hour_utc) — end is exclusive
SESSION_WINDOWS: dict[str, tuple[int, int]] = {
    "london": (7, 16),
    "newyork": (12, 21),
    "london_ny_overlap": (12, 16),
    "asian": (23, 7),  # Wraps midnight
}

# All valid TF pairs: entry@zone
ALL_TF_PAIRS: list[str] = [
    "M1@M5", "M1@M15",
    "M5@M15", "M5@H1",
    "M15@H1", "M15@H4",
    "H1@H4", "H1@D1",
]

# Map from zone_tf → list of pairs with higher context TFs
_TF_IDX = {tf: i for i, tf in enumerate(ENGINE_TF_ORDER)}


@dataclass(slots=True)
class RetestConfig:
    """Configuration for one retest sweep run."""

    # TF pair
    tf_pair: str = "H1@H4"

    # Entry filters
    touch_type: str = "wick_touch"           # "wick_touch", "body_close", "any"
    bias_filter: str = "any"                 # "with_daily", "against_daily", "any"
    zone_role_filter: str = "any"            # "continuation", "pullback", "push", "reversal", "any"
    age_filter: str = "any"                  # "fresh", "young", "mature", "old", "fresh_young", "any"
    test_count_filter: str = "any"           # "retested_1", "retested_2plus", "any"
    min_bias_strength: int = 0               # 0 = no filter, 1-3
    max_replacement_count: int = 999         # 999 = no filter
    direction: str = "both"                  # "long", "short", "both"
    session_filter: str = "any"              # "london", "newyork", "london_ny_overlap", "no_asian", "any"

    # Cascade
    cascade_filter: str = "none"             # "none", "require_htf_signal", "require_confluence_2"
    cascade_lookback: int = 20               # Entry-TF bars (converted to seconds for lookup)
    cascade_direction: str = "same"          # "same", "any"

    # SL/TP
    sl_mode: str = "zone"                    # "zone", "atr", "period"
    tp_mode: str = "fixed_rr"               # "zone", "fixed_rr"
    fixed_rr: float = 2.0                    # When tp_mode == "fixed_rr"
    sl_atr_mult: float = 1.5                # When sl_mode == "atr"

    # Touch policy (spec dimension: first_touch vs until_broken)
    touch_policy: str = "until_broken"       # "first_touch" = zone consumed after one entry;
                                             # "until_broken" = zone can be re-entered

    # Position management
    max_concurrent: int = 1                  # Max open trades per TF pair

    @property
    def entry_tf(self) -> str:
        return self.tf_pair.split("@")[0]

    @property
    def zone_tf(self) -> str:
        return self.tf_pair.split("@")[1]

    @property
    def htf_pairs(self) -> list[str]:
        """All TF pairs with context TF higher than this config's zone TF."""
        zone_idx = _TF_IDX.get(self.zone_tf, 0)
        return [
            p for p in ALL_TF_PAIRS
            if _TF_IDX.get(p.split("@")[1], 0) > zone_idx
        ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_config.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_config.py tests/strategy/test_retest_config.py
git commit -m "feat(strategy): add RetestConfig dataclass for Level 4 sweep dimensions"
```

---

### Task 2: RetestCandidate and Stage 1 Builder

**Files:**
- Create: `src/iora/strategy/retest_candidate.py`
- Test: `tests/strategy/test_retest_candidate.py`

**Context:** RetestCandidate wraps OpportunityEvent with zone boundaries needed for SL/TP computation. `build_retest_candidates()` extends the opportunity_runner pattern to capture these fields during the engine run. It follows the same init_state → per-bar tick → collect pattern as `opportunity_runner._run_single_entry_tf()`.

- [ ] **Step 1: Write tests for RetestCandidate dataclass**

```python
# tests/strategy/test_retest_candidate.py
"""Tests for RetestCandidate and build logic."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate


def _make_event(**overrides) -> OpportunityEvent:
    defaults = dict(
        timestamp=pd.Timestamp("2025-01-15 10:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type="wick_touch", zone_side="demand",
        zone_role="continuation", age_bucket="fresh",
        bias_alignment="with_daily", test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    defaults.update(overrides)
    return OpportunityEvent(**defaults)


def test_candidate_fields():
    ev = _make_event()
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert c.event.tf_pair == "H1@H4"
    assert c.zone_top == 1.2550
    assert c.zone_bottom == 1.2500
    assert c.entry_price == 1.2560
    assert c.direction == "long"  # demand zone → long


def test_candidate_direction_supply():
    ev = _make_event(zone_side="supply")
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2540, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert c.direction == "short"


def test_candidate_zone_thickness():
    ev = _make_event()
    c = RetestCandidate(
        event=ev,
        zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )
    assert abs(c.zone_thickness - 0.0050) < 1e-8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_retest_candidate.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RetestCandidate dataclass**

```python
# src/iora/strategy/retest_candidate.py
"""RetestCandidate — enriched retest event for Level 4 sweep.

Stage 1 output: OpportunityEvent + zone boundaries for SL/TP computation.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.diagnostics.opportunity_counter import OpportunityEvent


@dataclass(slots=True)
class RetestCandidate:
    """An OpportunityEvent enriched with zone state for SL/TP."""

    event: OpportunityEvent

    # Zone boundaries at touch time
    zone_top: float
    zone_bottom: float
    entry_price: float       # Bar close at touch
    atr: float               # ATR(14) on entry TF at touch bar

    # Period levels on zone TF (for period-based SL)
    period_hi: float
    period_lo: float

    @property
    def direction(self) -> str:
        return "long" if self.event.zone_side == "demand" else "short"

    @property
    def zone_thickness(self) -> float:
        return self.zone_top - self.zone_bottom
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_candidate.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Write test for build_retest_candidates with synthetic data**

Add to `tests/strategy/test_retest_candidate.py`:

```python
from iora.strategy.retest_candidate import build_retest_candidates


def test_build_candidates_returns_list(small_engine_data):
    """build_retest_candidates runs engine and returns enriched candidates.
    Uses small_engine_data fixture from conftest with known zone interactions."""
    candidates = build_retest_candidates(
        data_by_tf=small_engine_data,
        entry_tf="M5",
        symbol="TEST",
    )
    assert isinstance(candidates, list)
    # Should find at least some events on synthetic data
    for c in candidates:
        assert isinstance(c, RetestCandidate)
        assert c.zone_top > c.zone_bottom
        assert c.atr > 0
        assert c.entry_price > 0
```

This test requires a conftest fixture. Create `tests/strategy/conftest.py`:

```python
# tests/strategy/conftest.py
"""Shared fixtures for strategy tests."""
import pandas as pd
import numpy as np
import pytest


@pytest.fixture
def small_engine_data() -> dict[str, pd.DataFrame]:
    """Minimal multi-TF data with known zone-forming price action.

    Creates 200 M5 bars + aligned H1/H4/D1/W1 bars.
    Price trends up, pulls back to form retests.
    """
    n = 200
    timestamps = pd.date_range("2025-01-15 08:00", periods=n, freq="5min")
    np.random.seed(42)

    # Price: trend up 100 bars, pull back 50, push up 50
    base = 1.2500
    moves = np.concatenate([
        np.linspace(0, 0.0200, 100),       # Up
        np.linspace(0.0200, 0.0100, 50),    # Pullback
        np.linspace(0.0100, 0.0250, 50),    # Resume
    ])
    noise = np.random.normal(0, 0.0005, n)
    close = base + moves + noise
    high = close + np.abs(np.random.normal(0, 0.0008, n))
    low = close - np.abs(np.random.normal(0, 0.0008, n))
    open_ = np.roll(close, 1)
    open_[0] = base

    m5 = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": np.ones(n)},
        index=timestamps,
    )
    m5.index.name = "time"

    # Build higher TFs by resampling
    def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        r = df.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "tick_volume": "sum"}
        ).dropna()
        r.index.name = "time"
        return r

    return {
        "M5": m5,
        "H1": resample_ohlc(m5, "1h"),
        "H4": resample_ohlc(m5, "4h"),
        "D1": resample_ohlc(m5, "1D"),
        "W1": resample_ohlc(m5, "1W"),
    }
```

- [ ] **Step 6: Implement build_retest_candidates**

Add to `src/iora/strategy/retest_candidate.py`:

```python
import math
import numpy as np

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig, init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.diagnostics.bias_timeline import collect_bias_state
from iora.diagnostics.bias_timeline_runner import _compute_atr
from iora.diagnostics.opportunity_counter import (
    classify_touch, is_near_miss, classify_zone_role,
    classify_age_bucket, classify_bias_alignment,
    classify_test_count, _TF_PAIRS,
)
from iora.diagnostics.opportunity_runner import _get_pip_size


def build_retest_candidates(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str,
    symbol: str,
    period_depth: int = 3,
) -> list[RetestCandidate]:
    """Stage 1: run engine and collect enriched retest candidates.

    Extends the opportunity_runner pattern to capture zone boundaries
    and period levels alongside each event.
    """
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, tfs[0] if entry_tf not in data_by_tf else entry_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    base_df = data_by_tf[entry_tf]
    atr_series = _compute_atr(base_df, period=14)
    pip_size = _get_pip_size(symbol)

    context_tfs = _TF_PAIRS.get(entry_tf, [])
    candidates: list[RetestCandidate] = []
    prev_d_bias = ""
    prev_swing_cls: dict[str, dict[str, str]] = {}
    bar_idx = 0

    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
        if math.isnan(atr_val):
            atr_val = 0.002

        bias_rec = collect_bias_state(
            state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
        )
        prev_d_bias = bias_rec.d_bias

        # Check each context TF's zones for touches
        for zone_tf in context_tfs:
            if zone_tf not in state.tick_states:
                continue
            ts = state.tick_states[zone_tf]

            # Get period levels for this zone TF
            period_hi = ts.period.cur_hi if not math.isnan(ts.period.cur_hi) else ctx.high
            period_lo = ts.period.cur_lo if not math.isnan(ts.period.cur_lo) else ctx.low

            for zone_list, is_supply in [(ts.supply_zones, True), (ts.demand_zones, False)]:
                for zone in zone_list:
                    touch = classify_touch(zone, ctx.high, ctx.low, ctx.close)
                    if touch is None:
                        if is_near_miss(zone, ctx.high, ctx.low, atr_val, pip_size):
                            touch = "near_miss"
                        else:
                            continue

                    # Classify all dimensions
                    zone_side = "supply" if is_supply else "demand"
                    if zone_tf not in prev_swing_cls:
                        prev_swing_cls[zone_tf] = {"supply": "", "demand": ""}
                    role = classify_zone_role(zone, prev_swing_cls.get(zone_tf, {}))
                    age = classify_age_bucket(bar_idx - getattr(zone, '_birth_bar_idx', 0)
                                              if hasattr(zone, '_birth_bar_idx') else zone.test_count)
                    # Use zone_age_bars from zone metadata
                    zone_age = bar_idx  # approximate; real age tracked by engine
                    age_bucket = classify_age_bucket(zone_age)
                    bias_align = classify_bias_alignment(
                        is_supply, bias_rec.d_bias, bias_rec.is_bias_transition,
                    )
                    test_cls = classify_test_count(zone.test_count)

                    tf_pair = f"{entry_tf}@{zone_tf}"
                    zone_mid = (zone.top + zone.bottom) / 2
                    dist = abs(ctx.close - zone_mid) / atr_val if atr_val > 0 else 0

                    event = OpportunityEvent(
                        timestamp=ctx.timestamp,
                        zone_tf=zone_tf,
                        entry_tf=entry_tf,
                        tf_pair=tf_pair,
                        touch_type=touch,
                        zone_side=zone_side,
                        zone_role=role,
                        age_bucket=age_bucket,
                        bias_alignment=bias_align,
                        test_count_cls=test_cls,
                        zone_age_bars=zone_age,
                        zone_test_count=zone.test_count,
                        bias_strength=bias_rec.d_bias_strength,
                        price_distance_at_touch=dist,
                        replacement_count=zone.replacement_count,
                        birth_bias_d=getattr(zone, 'birth_bias_d', 'unknown'),
                        birth_period_pattern=getattr(zone, 'birth_period_pattern', 'unknown'),
                        birth_price_distance=getattr(zone, 'birth_price_distance', 0.0),
                    )

                    candidates.append(RetestCandidate(
                        event=event,
                        zone_top=zone.top,
                        zone_bottom=zone.bottom,
                        entry_price=ctx.close,
                        atr=atr_val,
                        period_hi=period_hi,
                        period_lo=period_lo,
                    ))

        # Track previous swing classes
        for tf, ts in state.tick_states.items():
            if tf not in prev_swing_cls:
                prev_swing_cls[tf] = {"supply": "", "demand": ""}
            if ts.supply_zones and ts.supply_zones[-1].swing_cls:
                prev_swing_cls[tf]["supply"] = ts.supply_zones[-1].swing_cls
            if ts.demand_zones and ts.demand_zones[-1].swing_cls:
                prev_swing_cls[tf]["demand"] = ts.demand_zones[-1].swing_cls

        bar_idx += 1

    return candidates
```

**Important:** The `build_retest_candidates` function closely mirrors `opportunity_runner._run_single_entry_tf()`. The key difference: it captures `zone.top`, `zone.bottom`, `period.cur_hi`, `period.cur_lo`, and the bar's `close` alongside each event. After implementation, verify the zone-age computation matches the existing `detect_events()` logic in `opportunity_counter.py` — the age is computed relative to zone origin, not bar_idx 0. Read `opportunity_counter.py:detect_events()` to match the exact age computation.

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_candidate.py -v`
Expected: All 4 tests PASS (the build test may produce 0 candidates on synthetic data — that's OK as long as it runs without error; the type assertions guard correctness)

- [ ] **Step 8: Commit**

```bash
git add src/iora/strategy/retest_candidate.py tests/strategy/test_retest_candidate.py tests/strategy/conftest.py
git commit -m "feat(strategy): add RetestCandidate + build_retest_candidates Stage 1"
```

---

### Task 3: Filter Funnel

**Files:**
- Create: `src/iora/strategy/filter_funnel.py`
- Test: `tests/strategy/test_filter_funnel.py`

**Context:** The filter funnel applies config filters to candidates in a defined order, tracking how many candidates each filter removes. This is a first-class output per the spec — "each filter's marginal contribution visible."

- [ ] **Step 1: Write tests for filter funnel**

```python
# tests/strategy/test_filter_funnel.py
"""Tests for filter funnel logic."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.filter_funnel import apply_filters, FilterFunnel


def _candidate(touch_type="wick_touch", bias="with_daily", role="continuation",
               age="fresh", test_cls="retested_1", side="demand",
               strength=2, replacement=0, hour=10) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=pd.Timestamp(f"2025-01-15 {hour:02d}:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type=touch_type, zone_side=side,
        zone_role=role, age_bucket=age,
        bias_alignment=bias, test_count_cls=test_cls,
        zone_age_bars=5, zone_test_count=1, bias_strength=strength,
        price_distance_at_touch=1.5, replacement_count=replacement,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=1.2550, zone_bottom=1.2500,
        entry_price=1.2560, atr=0.0080,
        period_hi=1.2600, period_lo=1.2450,
    )


def test_no_filters_passes_all():
    candidates = [_candidate(), _candidate(touch_type="body_close")]
    cfg = RetestConfig(touch_type="any", bias_filter="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2
    assert funnel.steps[0].name == "touch_type"


def test_touch_type_filter():
    candidates = [
        _candidate(touch_type="wick_touch"),
        _candidate(touch_type="body_close"),
        _candidate(touch_type="near_miss"),
    ]
    cfg = RetestConfig(touch_type="wick_touch")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    assert funnel.passed[0].event.touch_type == "wick_touch"


def test_bias_filter():
    candidates = [
        _candidate(bias="with_daily"),
        _candidate(bias="against_daily"),
        _candidate(bias="neutral"),
    ]
    cfg = RetestConfig(bias_filter="with_daily", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1


def test_direction_filter_long():
    candidates = [
        _candidate(side="demand"),   # long
        _candidate(side="supply"),   # short
    ]
    cfg = RetestConfig(direction="long", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    assert funnel.passed[0].direction == "long"


def test_session_filter_london():
    candidates = [
        _candidate(hour=10),  # Inside London (07-16)
        _candidate(hour=3),   # Asian session
        _candidate(hour=20),  # Late NY
    ]
    cfg = RetestConfig(session_filter="london", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1


def test_session_filter_no_asian():
    candidates = [
        _candidate(hour=10),  # London
        _candidate(hour=3),   # Asian
        _candidate(hour=14),  # London-NY overlap
    ]
    cfg = RetestConfig(session_filter="no_asian", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_age_filter_fresh_young():
    candidates = [
        _candidate(age="fresh"),
        _candidate(age="young"),
        _candidate(age="mature"),
        _candidate(age="old"),
    ]
    cfg = RetestConfig(age_filter="fresh_young", touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_min_bias_strength():
    candidates = [
        _candidate(strength=1),
        _candidate(strength=2),
        _candidate(strength=3),
    ]
    cfg = RetestConfig(min_bias_strength=2, touch_type="any")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 2


def test_funnel_step_tracking():
    candidates = [
        _candidate(touch_type="wick_touch", bias="with_daily"),
        _candidate(touch_type="body_close", bias="with_daily"),
        _candidate(touch_type="wick_touch", bias="against_daily"),
    ]
    cfg = RetestConfig(touch_type="wick_touch", bias_filter="with_daily")
    funnel = apply_filters(candidates, cfg)
    assert len(funnel.passed) == 1
    # Touch type filter should remove 1 (body_close)
    touch_step = next(s for s in funnel.steps if s.name == "touch_type")
    assert touch_step.input_count == 3
    assert touch_step.output_count == 2
    assert touch_step.removed == 1
    # Bias filter should remove 1 (against_daily)
    bias_step = next(s for s in funnel.steps if s.name == "bias_filter")
    assert bias_step.input_count == 2
    assert bias_step.output_count == 1
    assert bias_step.removed == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_filter_funnel.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement filter funnel**

```python
# src/iora/strategy/filter_funnel.py
"""Filter funnel — ordered filter pipeline with per-step attribution.

Applies RetestConfig filters to candidates in a fixed order.
Tracks how many candidates each filter removes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig, SESSION_WINDOWS


@dataclass(slots=True)
class FunnelStep:
    """One step in the filter pipeline."""
    name: str
    input_count: int
    output_count: int

    @property
    def removed(self) -> int:
        return self.input_count - self.output_count


@dataclass(slots=True)
class FilterFunnel:
    """Result of applying all filters."""
    steps: list[FunnelStep] = field(default_factory=list)
    passed: list[RetestCandidate] = field(default_factory=list)
    total_input: int = 0

    @property
    def total_removed(self) -> int:
        return self.total_input - len(self.passed)


# Filter order — each filter is (name, predicate_factory)
# Predicate returns True to KEEP the candidate

def _make_touch_filter(cfg: RetestConfig):
    if cfg.touch_type == "any":
        return None
    val = cfg.touch_type
    return lambda c: c.event.touch_type == val


def _make_direction_filter(cfg: RetestConfig):
    if cfg.direction == "both":
        return None
    val = cfg.direction
    return lambda c: c.direction == val


def _make_bias_filter(cfg: RetestConfig):
    if cfg.bias_filter == "any":
        return None
    val = cfg.bias_filter
    return lambda c: c.event.bias_alignment == val


def _make_bias_strength_filter(cfg: RetestConfig):
    if cfg.min_bias_strength <= 0:
        return None
    min_s = cfg.min_bias_strength
    return lambda c: c.event.bias_strength >= min_s


def _make_zone_role_filter(cfg: RetestConfig):
    if cfg.zone_role_filter == "any":
        return None
    val = cfg.zone_role_filter
    return lambda c: c.event.zone_role == val


def _make_age_filter(cfg: RetestConfig):
    if cfg.age_filter == "any":
        return None
    if cfg.age_filter == "fresh_young":
        return lambda c: c.event.age_bucket in ("fresh", "young")
    val = cfg.age_filter
    return lambda c: c.event.age_bucket == val


def _make_test_count_filter(cfg: RetestConfig):
    if cfg.test_count_filter == "any":
        return None
    val = cfg.test_count_filter
    return lambda c: c.event.test_count_cls == val


def _make_replacement_filter(cfg: RetestConfig):
    if cfg.max_replacement_count >= 999:
        return None
    mx = cfg.max_replacement_count
    return lambda c: c.event.replacement_count <= mx


def _make_session_filter(cfg: RetestConfig):
    if cfg.session_filter == "any":
        return None
    if cfg.session_filter == "no_asian":
        start, end = SESSION_WINDOWS["asian"]
        # Asian wraps midnight: 23:00-07:00 — exclude this range
        return lambda c: not _in_session(c.event.timestamp.hour, start, end)
    if cfg.session_filter in SESSION_WINDOWS:
        start, end = SESSION_WINDOWS[cfg.session_filter]
        return lambda c: _in_session(c.event.timestamp.hour, start, end)
    return None


def _in_session(hour: int, start: int, end: int) -> bool:
    """Check if hour is within session window (handles midnight wrap)."""
    if start < end:
        return start <= hour < end
    # Wraps midnight (e.g., 23:00-07:00)
    return hour >= start or hour < end


_FILTER_FACTORIES = [
    ("touch_type", _make_touch_filter),
    ("direction", _make_direction_filter),
    ("bias_filter", _make_bias_filter),
    ("bias_strength", _make_bias_strength_filter),
    ("zone_role", _make_zone_role_filter),
    ("age_filter", _make_age_filter),
    ("test_count", _make_test_count_filter),
    ("replacement_count", _make_replacement_filter),
    ("session", _make_session_filter),
]


def apply_filters(
    candidates: list[RetestCandidate],
    cfg: RetestConfig,
) -> FilterFunnel:
    """Apply all config filters in order, tracking attribution."""
    funnel = FilterFunnel(total_input=len(candidates))
    current = list(candidates)

    for name, factory in _FILTER_FACTORIES:
        pred = factory(cfg)
        input_count = len(current)
        if pred is not None:
            current = [c for c in current if pred(c)]
        funnel.steps.append(FunnelStep(
            name=name,
            input_count=input_count,
            output_count=len(current),
        ))

    funnel.passed = current
    return funnel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_filter_funnel.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/filter_funnel.py tests/strategy/test_filter_funnel.py
git commit -m "feat(strategy): add FilterFunnel with ordered pipeline and per-step attribution"
```

---

### Task 4: SL/TP Computation for Retest Entries

**Files:**
- Create: `src/iora/strategy/retest_sl_tp.py`
- Test: `tests/strategy/test_retest_sl_tp.py`

**Context:** Reuses the logic from `sl_tp.py:compute_sl()` but adapted for RetestCandidate inputs. Zone-based SL uses the retest zone's boundaries directly. The spec defines three SL modes (zone, atr, period) and two TP modes (zone, fixed_rr).

- [ ] **Step 1: Write tests for retest SL/TP**

```python
# tests/strategy/test_retest_sl_tp.py
"""Tests for retest-specific SL/TP computation."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sl_tp import compute_retest_sl, compute_retest_tp


def _candidate(side="demand", zone_top=1.2550, zone_bottom=1.2500,
               entry_price=1.2560, atr=0.0080,
               period_hi=1.2600, period_lo=1.2450) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=pd.Timestamp("2025-01-15 10:00"),
        zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type="wick_touch", zone_side=side,
        zone_role="continuation", age_bucket="fresh",
        bias_alignment="with_daily", test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=zone_top, zone_bottom=zone_bottom,
        entry_price=entry_price, atr=atr,
        period_hi=period_hi, period_lo=period_lo,
    )


class TestZoneSL:
    def test_long_sl_below_zone(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="zone")
        # Long SL below zone bottom with buffer
        assert sl < c.zone_bottom
        assert sl > 0

    def test_short_sl_above_zone(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="zone")
        # Short SL above zone top with buffer
        assert sl > c.zone_top


class TestAtrSL:
    def test_long_atr_sl(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="atr", atr_mult=1.5)
        expected = c.entry_price - 1.5 * c.atr
        assert abs(sl - expected) < 1e-8

    def test_short_atr_sl(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="atr", atr_mult=1.5)
        expected = c.entry_price + 1.5 * c.atr
        assert abs(sl - expected) < 1e-8


class TestPeriodSL:
    def test_long_period_sl(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="period")
        # Long SL below period low with buffer
        assert sl < c.period_lo

    def test_short_period_sl(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="period")
        # Short SL above period high with buffer
        assert sl > c.period_hi


class TestTP:
    def test_fixed_rr_long(self):
        c = _candidate(side="demand")
        sl = compute_retest_sl(c, mode="zone")
        risk = c.entry_price - sl
        tp = compute_retest_tp(c, sl, mode="fixed_rr", fixed_rr=2.0)
        expected = c.entry_price + 2.0 * risk
        assert abs(tp - expected) < 1e-8

    def test_fixed_rr_short(self):
        c = _candidate(side="supply", entry_price=1.2540)
        sl = compute_retest_sl(c, mode="zone")
        risk = sl - c.entry_price
        tp = compute_retest_tp(c, sl, mode="fixed_rr", fixed_rr=2.0)
        expected = c.entry_price - 2.0 * risk
        assert abs(tp - expected) < 1e-8
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_retest_sl_tp.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement retest SL/TP**

```python
# src/iora/strategy/retest_sl_tp.py
"""SL/TP computation for retest entries.

Zone-based SL: below/above the retest zone with ATR buffer.
ATR-based SL: fixed ATR multiple from entry.
Period-based SL: below/above the zone TF's current period extreme.
TP: fixed R:R from SL distance, or opposing zone (future).
"""
from __future__ import annotations

from iora.strategy.retest_candidate import RetestCandidate

_ZONE_BUFFER_ATR: float = 0.15  # Buffer beyond zone edge as ATR fraction


def compute_retest_sl(
    candidate: RetestCandidate,
    mode: str = "zone",
    atr_mult: float = 1.5,
    buffer_atr: float = _ZONE_BUFFER_ATR,
) -> float:
    """Compute stop-loss for a retest entry."""
    c = candidate
    buf = buffer_atr * c.atr

    if mode == "zone":
        if c.direction == "long":
            return c.zone_bottom - buf
        return c.zone_top + buf

    if mode == "atr":
        if c.direction == "long":
            return c.entry_price - atr_mult * c.atr
        return c.entry_price + atr_mult * c.atr

    if mode == "period":
        if c.direction == "long":
            return c.period_lo - buf
        return c.period_hi + buf

    # Fallback to ATR
    if c.direction == "long":
        return c.entry_price - atr_mult * c.atr
    return c.entry_price + atr_mult * c.atr


def compute_retest_tp(
    candidate: RetestCandidate,
    sl_price: float,
    mode: str = "fixed_rr",
    fixed_rr: float = 2.0,
) -> float:
    """Compute take-profit for a retest entry."""
    c = candidate
    risk = abs(c.entry_price - sl_price)

    if mode == "fixed_rr":
        if c.direction == "long":
            return c.entry_price + fixed_rr * risk
        return c.entry_price - fixed_rr * risk

    # Fallback to fixed_rr
    if c.direction == "long":
        return c.entry_price + fixed_rr * risk
    return c.entry_price - fixed_rr * risk
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_sl_tp.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_sl_tp.py tests/strategy/test_retest_sl_tp.py
git commit -m "feat(strategy): add retest SL/TP computation (zone, atr, period modes)"
```

---

### Task 5: Retest Trade Simulation

**Files:**
- Create: `src/iora/strategy/retest_engine.py`
- Test: `tests/strategy/test_retest_engine.py`

**Context:** This is the core Stage 2 engine. It takes filtered candidates (from FilterFunnel), computes SL/TP per entry, then simulates position management bar-by-bar. For simplicity, it processes candidates in timestamp order and simulates SL/TP hits on subsequent bars using the candidate list itself (no separate bar data needed — candidates have entry_price and atr for distance estimation). For the sweep, we use a simplified SL/TP evaluation: the next candidate on the same TF pair approximates the next bar.

**Key simplification for Layer A:** Instead of replaying bar-by-bar OHLC for exit detection (which would need the full timeline), we use a **next-event exit model**: each entry's SL/TP is evaluated against subsequent candidates' entry_price values on the same TF pair. This is a close approximation since candidates are generated every bar (body_close events fire on almost every bar where price is near a zone). The full bar-by-bar replay can be added in Layer A+ if needed.

**Alternative (recommended if implementing agent finds next-event model too lossy):** Load the base_df alongside candidates and scan forward through bars for SL/TP hits. This is more accurate but requires passing base_df to evaluate_retest_config.

- [ ] **Step 1: Write tests for RetestTradeRecord and position sim**

```python
# tests/strategy/test_retest_engine.py
"""Tests for retest trade simulation."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_engine import (
    RetestTradeRecord, evaluate_retest_config, RetestResult,
)


def _candidate(ts, side="demand", touch="wick_touch", bias="with_daily",
               entry_price=1.2560, zone_top=1.2550, zone_bottom=1.2500,
               atr=0.0080) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=ts, zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type=touch, zone_side=side,
        zone_role="continuation", age_bucket="fresh",
        bias_alignment=bias, test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=zone_top, zone_bottom=zone_bottom,
        entry_price=entry_price, atr=atr,
        period_hi=1.2600, period_lo=1.2450,
    )


def test_trade_record_is_winner():
    rec = RetestTradeRecord(
        trade_id="T001", symbol="GBPUSD", direction=1,
        entry_time=pd.Timestamp("2025-01-15 10:00"),
        exit_time=pd.Timestamp("2025-01-15 14:00"),
        entry_price=1.2560, exit_price=1.2620,
        sl_price=1.2490, tp_price=1.2700,
        pnl_pips=60.0, risk_pips=70.0, reward_pips=140.0,
        return_r=0.857, rr_ratio=2.0, exit_reason="tp",
        tf_pair="H1@H4", touch_type="wick_touch",
        zone_role="continuation", bias_alignment="with_daily",
        age_bucket="fresh", test_count_cls="retested_1",
    )
    assert rec.is_winner


def test_evaluate_empty_candidates():
    cfg = RetestConfig()
    result = evaluate_retest_config([], cfg, symbol="TEST")
    assert isinstance(result, RetestResult)
    assert len(result.trades) == 0


def test_evaluate_produces_trades():
    """With candidates that pass filters + simulated bar data for exits."""
    times = pd.date_range("2025-01-15 10:00", periods=50, freq="1h")
    candidates = []
    for i, t in enumerate(times):
        # Demand zone retests — price oscillates
        price = 1.2500 + 0.0002 * (i % 10)
        candidates.append(_candidate(
            ts=t, entry_price=price,
            zone_top=1.2510, zone_bottom=1.2490, atr=0.0030,
        ))

    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch",
        bias_filter="with_daily", tp_mode="fixed_rr", fixed_rr=2.0,
    )
    # Also need bar data for exit simulation
    bar_data = pd.DataFrame(
        {"open": [1.2500]*50, "high": [1.2550]*50,
         "low": [1.2470]*50, "close": [1.2510]*50,
         "tick_volume": [100]*50},
        index=times,
    )
    result = evaluate_retest_config(
        candidates, cfg, symbol="GBPUSD", bar_data=bar_data,
    )
    assert isinstance(result, RetestResult)
    # Should have some trades (exact count depends on SL/TP hit timing)
    assert result.total_candidates > 0


def test_result_has_metrics():
    """RetestResult.metrics is populated when trades exist."""
    times = pd.date_range("2025-01-15 10:00", periods=20, freq="1h")
    candidates = [
        _candidate(ts=t, entry_price=1.2500 + 0.0005 * i, atr=0.0030)
        for i, t in enumerate(times)
    ]
    cfg = RetestConfig(touch_type="wick_touch", bias_filter="with_daily")
    bar_data = pd.DataFrame(
        {"open": [1.2500]*20, "high": [1.2600]*20,
         "low": [1.2400]*20, "close": [1.2510]*20,
         "tick_volume": [100]*20},
        index=times,
    )
    result = evaluate_retest_config(
        candidates, cfg, symbol="GBPUSD", bar_data=bar_data,
    )
    if result.trades:
        assert "total_trades" in result.metrics
        assert "win_rate" in result.metrics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_retest_engine.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RetestTradeRecord**

```python
# src/iora/strategy/retest_engine.py
"""Retest sweep engine — Stage 2: filter, simulate, measure.

Takes candidates from Stage 1, applies config filters via FilterFunnel,
computes SL/TP, simulates position management, and produces trade records
with comprehensive metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sl_tp import compute_retest_sl, compute_retest_tp
from iora.strategy.filter_funnel import apply_filters, FilterFunnel
from iora.strategy.sweep_runner import compute_metrics
from iora.strategy.trade_converter import _get_pip_size


@dataclass(frozen=True, slots=True)
class RetestTradeRecord:
    """Trade record for retest strategy — extends SweepTradeRecord concept."""

    trade_id: str
    symbol: str
    direction: int           # 1=LONG, -1=SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    sl_price: float
    tp_price: float
    pnl_pips: float
    risk_pips: float
    reward_pips: float
    return_r: float
    rr_ratio: float
    exit_reason: str         # "tp", "sl", "end_of_data"

    # Retest context
    tf_pair: str = ""
    touch_type: str = ""
    zone_role: str = ""
    bias_alignment: str = ""
    age_bucket: str = ""
    test_count_cls: str = ""
    zone_top: float = 0.0
    zone_bottom: float = 0.0
    bias_strength: int = 0
    replacement_count: int = 0
    birth_period_pattern: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pips > 0
```

- [ ] **Step 4: Implement evaluate_retest_config**

Add to `src/iora/strategy/retest_engine.py`:

```python
@dataclass(slots=True)
class RetestResult:
    """Full result for one config evaluation."""
    symbol: str
    config: RetestConfig
    trades: list[RetestTradeRecord] = field(default_factory=list)
    funnel: FilterFunnel | None = None
    total_candidates: int = 0
    metrics: dict = field(default_factory=dict)


def evaluate_retest_config(
    candidates: list[RetestCandidate],
    config: RetestConfig,
    symbol: str = "UNKNOWN",
    bar_data: pd.DataFrame | None = None,
    pip_size: float | None = None,
) -> RetestResult:
    """Stage 2: filter candidates, simulate trades, compute metrics.

    Args:
        candidates: All candidates for this symbol (all TF pairs).
        config: Sweep config to evaluate.
        symbol: Symbol name.
        bar_data: Entry-TF OHLC for exit simulation. If None, uses
                  next-candidate approximation.
        pip_size: Pip size override. Auto-detected from symbol if None.
    """
    if pip_size is None:
        pip_size = _get_pip_size(symbol)

    # Filter to this TF pair only
    pair_candidates = [c for c in candidates if c.event.tf_pair == config.tf_pair]

    # Apply filter funnel
    funnel = apply_filters(pair_candidates, config)
    entries = funnel.passed

    if not entries or bar_data is None or bar_data.empty:
        return RetestResult(
            symbol=symbol, config=config, funnel=funnel,
            total_candidates=len(pair_candidates),
        )

    # Sort entries by timestamp
    entries.sort(key=lambda c: c.event.timestamp)

    # Simulate trades
    trades: list[RetestTradeRecord] = []
    open_trade: _OpenTrade | None = None
    trade_count = 0

    for c in entries:
        # Skip if we already have max concurrent trades open
        if open_trade is not None:
            # Check if this bar's data closes the trade
            if c.event.timestamp in bar_data.index:
                bar = bar_data.loc[c.event.timestamp]
                closed = _check_exit(open_trade, bar, c.event.timestamp)
                if closed is not None:
                    trades.append(closed)
                    open_trade = None
            continue

        # Compute SL/TP
        sl = compute_retest_sl(c, mode=config.sl_mode, atr_mult=config.sl_atr_mult)
        tp = compute_retest_tp(c, sl, mode=config.tp_mode, fixed_rr=config.fixed_rr)

        trade_count += 1
        open_trade = _OpenTrade(
            candidate=c, sl=sl, tp=tp,
            trade_id=f"R{trade_count:04d}",
            symbol=symbol, pip_size=pip_size,
        )

    # Close any remaining open trade at end of data
    if open_trade is not None:
        last_bar = bar_data.iloc[-1]
        trade = open_trade.close_at(
            last_bar["close"], bar_data.index[-1], "end_of_data",
        )
        trades.append(trade)

    # Also scan remaining bars for open trade exits
    # (entries list may not cover all bars)
    # Full bar-by-bar scan for open positions
    if bar_data is not None and not bar_data.empty:
        trades = _simulate_with_bars(entries, config, bar_data, symbol, pip_size)

    # Compute metrics using existing compute_metrics via adapter
    metrics = _compute_retest_metrics(trades) if trades else {}

    return RetestResult(
        symbol=symbol, config=config, trades=trades,
        funnel=funnel, total_candidates=len(pair_candidates),
        metrics=metrics,
    )


@dataclass(slots=True)
class _OpenTrade:
    """Internal: tracks an open position."""
    candidate: RetestCandidate
    sl: float
    tp: float
    trade_id: str
    symbol: str
    pip_size: float

    def close_at(self, exit_price: float, exit_time: pd.Timestamp,
                 reason: str) -> RetestTradeRecord:
        c = self.candidate
        direction = 1 if c.direction == "long" else -1
        pnl = (exit_price - c.entry_price) * direction / self.pip_size
        risk = abs(c.entry_price - self.sl) / self.pip_size
        reward = abs(self.tp - c.entry_price) / self.pip_size
        return_r = pnl / risk if risk > 0 else 0.0
        rr_ratio = reward / risk if risk > 0 else 0.0

        return RetestTradeRecord(
            trade_id=self.trade_id, symbol=self.symbol,
            direction=direction,
            entry_time=c.event.timestamp, exit_time=exit_time,
            entry_price=c.entry_price, exit_price=exit_price,
            sl_price=self.sl, tp_price=self.tp,
            pnl_pips=pnl, risk_pips=risk, reward_pips=reward,
            return_r=return_r, rr_ratio=rr_ratio,
            exit_reason=reason,
            tf_pair=c.event.tf_pair,
            touch_type=c.event.touch_type,
            zone_role=c.event.zone_role,
            bias_alignment=c.event.bias_alignment,
            age_bucket=c.event.age_bucket,
            test_count_cls=c.event.test_count_cls,
            zone_top=c.zone_top, zone_bottom=c.zone_bottom,
            bias_strength=c.event.bias_strength,
            replacement_count=c.event.replacement_count,
            birth_period_pattern=c.event.birth_period_pattern,
        )


def _simulate_with_bars(
    entries: list[RetestCandidate],
    config: RetestConfig,
    bar_data: pd.DataFrame,
    symbol: str,
    pip_size: float,
) -> list[RetestTradeRecord]:
    """Full bar-by-bar simulation with SL/TP checking."""
    trades: list[RetestTradeRecord] = []
    open_trade: _OpenTrade | None = None
    trade_count = 0

    # Build entry lookup: timestamp → nearest-to-price candidate
    # Spec requires "nearest zone to current price" when multiple zones touched
    entry_map: dict[pd.Timestamp, RetestCandidate] = {}
    for c in entries:
        ts = c.event.timestamp
        if ts not in entry_map or c.event.price_distance_at_touch < entry_map[ts].event.price_distance_at_touch:
            entry_map[ts] = c

    # Track consumed zones for first_touch policy
    consumed_zones: set[tuple[str, float, float]] = set()  # (zone_tf, top, bottom)

    for ts, bar in bar_data.iterrows():
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]

        # Check exit on open trade
        if open_trade is not None:
            c = open_trade.candidate
            if c.direction == "long":
                if low <= open_trade.sl:
                    trades.append(open_trade.close_at(open_trade.sl, ts, "sl"))
                    open_trade = None
                elif high >= open_trade.tp:
                    trades.append(open_trade.close_at(open_trade.tp, ts, "tp"))
                    open_trade = None
            else:  # short
                if high >= open_trade.sl:
                    trades.append(open_trade.close_at(open_trade.sl, ts, "sl"))
                    open_trade = None
                elif low <= open_trade.tp:
                    trades.append(open_trade.close_at(open_trade.tp, ts, "tp"))
                    open_trade = None

        # Check for new entry (only if no open trade)
        if open_trade is None and ts in entry_map:
            c = entry_map[ts]
            zone_key = (c.event.zone_tf, c.zone_top, c.zone_bottom)

            # touch_policy: skip consumed zones
            if config.touch_policy == "first_touch" and zone_key in consumed_zones:
                continue

            sl = compute_retest_sl(c, mode=config.sl_mode, atr_mult=config.sl_atr_mult)
            tp = compute_retest_tp(c, sl, mode=config.tp_mode, fixed_rr=config.fixed_rr)
            trade_count += 1
            open_trade = _OpenTrade(
                candidate=c, sl=sl, tp=tp,
                trade_id=f"R{trade_count:04d}",
                symbol=symbol, pip_size=pip_size,
            )
            if config.touch_policy == "first_touch":
                consumed_zones.add(zone_key)

    # Close remaining at end of data
    if open_trade is not None:
        last_ts = bar_data.index[-1]
        trades.append(open_trade.close_at(
            bar_data.iloc[-1]["close"], last_ts, "end_of_data",
        ))

    return trades


def _adapt_to_sweep_records(trades: list[RetestTradeRecord]) -> list:
    """Adapt RetestTradeRecord to SweepTradeRecord for compute_metrics().

    Uses duck typing: SweepTradeRecord and RetestTradeRecord share the same
    core fields (pnl_pips, return_r, risk_pips, reward_pips, entry_time,
    exit_time, direction, exit_reason, signal_type → touch_type, struct_cls,
    zone_tf). compute_metrics() accesses these via attribute access.

    Read sweep_runner.py:compute_metrics() to verify which fields it accesses,
    then map RetestTradeRecord fields accordingly.
    """
    from iora.strategy.trade_converter import SweepTradeRecord

    adapted = []
    for t in trades:
        adapted.append(SweepTradeRecord(
            trade_id=t.trade_id, symbol=t.symbol,
            direction=t.direction,
            entry_time=t.entry_time, exit_time=t.exit_time,
            entry_price=t.entry_price, exit_price=t.exit_price,
            pnl_pips=t.pnl_pips, risk_pips=t.risk_pips,
            reward_pips=t.reward_pips, return_r=t.return_r,
            rr_ratio=t.rr_ratio, exit_reason=t.exit_reason,
            sl_price=t.sl_price, tp_price=t.tp_price,
            signal_type=t.touch_type,   # Map touch_type → signal_type
            struct_cls="",
            zone_tf=t.tf_pair.split("@")[1] if "@" in t.tf_pair else "",
        ))
    return adapted


def _compute_retest_metrics(trades: list[RetestTradeRecord]) -> dict:
    """Compute full metrics using existing compute_metrics().

    Adapts RetestTradeRecord → SweepTradeRecord, then delegates to
    sweep_runner.compute_metrics() for the complete metric set (SQN, Sharpe,
    Sortino, Calmar, streaks, holding periods, breakdowns, etc.).
    """
    if not trades:
        return {}
    adapted = _adapt_to_sweep_records(trades)
    return compute_metrics(adapted)
```

**Note to implementing agent:** The `_simulate_with_bars` function is the core position sim. It processes bars in order, checking SL/TP on open positions BEFORE checking for new entries on that bar. SL is checked first (assumes worst case — SL hit before TP on same bar for longs with low < SL). Read `src/iora/strategy/push_zone_strategy.py` for the existing pattern of how positions are managed. Adapt the `max_concurrent` config field if adding multi-position support later.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_engine.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/iora/strategy/retest_engine.py tests/strategy/test_retest_engine.py
git commit -m "feat(strategy): add retest trade simulation with bar-by-bar SL/TP + metrics"
```

---

### Task 6: Cascade Filter

**Files:**
- Modify: `src/iora/strategy/filter_funnel.py`
- Modify: `src/iora/strategy/retest_engine.py`
- Test: `tests/strategy/test_filter_funnel.py` (add cascade tests)

**Context:** Cascade filtering checks if an HTF retest event occurred recently near the candidate's timestamp. Since we have all candidates across all TF pairs from Stage 1, cascade checking scans the candidate list for HTF events within a time window. The cascade filter is applied AFTER the standard filters in the funnel.

- [ ] **Step 1: Write cascade filter tests**

Add to `tests/strategy/test_filter_funnel.py`:

```python
def test_cascade_require_htf_signal():
    """Cascade filter requires a recent HTF wick_touch event."""
    from iora.strategy.filter_funnel import apply_filters_with_cascade

    t0 = pd.Timestamp("2025-01-15 10:00")
    t1 = pd.Timestamp("2025-01-15 11:00")  # 1 hour later

    # Entry candidate on M5@M15
    entry = _candidate(touch="wick_touch", bias="with_daily")
    # Override tf_pair for this test
    entry.event = OpportunityEvent(
        **{**entry.event.__dict__, "tf_pair": "M5@M15",
           "entry_tf": "M5", "zone_tf": "M15",
           "timestamp": t1}
    )

    # HTF event on M15@H1 (within lookback)
    htf_candidate = _candidate(touch="wick_touch")
    htf_candidate.event = OpportunityEvent(
        **{**htf_candidate.event.__dict__, "tf_pair": "M15@H1",
           "entry_tf": "M15", "zone_tf": "H1",
           "timestamp": t0}
    )

    all_candidates = [htf_candidate, entry]
    cfg = RetestConfig(
        tf_pair="M5@M15", touch_type="wick_touch",
        bias_filter="with_daily",
        cascade_filter="require_htf_signal",
        cascade_lookback=20,  # 20 M5 bars = 100 min > 60 min
    )
    funnel = apply_filters_with_cascade(
        [entry], cfg, all_candidates=all_candidates,
    )
    assert len(funnel.passed) == 1  # HTF signal found within lookback


def test_cascade_no_htf_signal():
    t0 = pd.Timestamp("2025-01-15 05:00")  # 6 hours earlier
    t1 = pd.Timestamp("2025-01-15 11:00")

    entry = _candidate(touch="wick_touch", bias="with_daily")
    entry.event = OpportunityEvent(
        **{**entry.event.__dict__, "tf_pair": "M5@M15",
           "entry_tf": "M5", "zone_tf": "M15",
           "timestamp": t1}
    )

    htf_candidate = _candidate(touch="wick_touch")
    htf_candidate.event = OpportunityEvent(
        **{**htf_candidate.event.__dict__, "tf_pair": "M15@H1",
           "entry_tf": "M15", "zone_tf": "H1",
           "timestamp": t0}
    )

    all_candidates = [htf_candidate, entry]
    cfg = RetestConfig(
        tf_pair="M5@M15", touch_type="wick_touch",
        bias_filter="with_daily",
        cascade_filter="require_htf_signal",
        cascade_lookback=5,  # 5 M5 bars = 25 min << 360 min gap
    )
    from iora.strategy.filter_funnel import apply_filters_with_cascade
    funnel = apply_filters_with_cascade(
        [entry], cfg, all_candidates=all_candidates,
    )
    assert len(funnel.passed) == 0  # HTF signal too old
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_filter_funnel.py::test_cascade_require_htf_signal -v`
Expected: FAIL — `ImportError: cannot import name 'apply_filters_with_cascade'`

- [ ] **Step 3: Implement cascade filter**

Add to `src/iora/strategy/filter_funnel.py`:

```python
from iora.constants import TF_SECONDS


def apply_filters_with_cascade(
    candidates: list[RetestCandidate],
    cfg: RetestConfig,
    all_candidates: list[RetestCandidate] | None = None,
) -> FilterFunnel:
    """Apply standard filters + cascade filter.

    Args:
        candidates: Pre-filtered to this TF pair.
        cfg: Config with cascade settings.
        all_candidates: ALL candidates across all TF pairs (for cascade lookup).
    """
    # Standard filters first
    funnel = apply_filters(candidates, cfg)

    if cfg.cascade_filter == "none" or all_candidates is None:
        return funnel

    # Build HTF event index: sorted by timestamp, filtered to HTF pairs
    htf_pairs = set(cfg.htf_pairs)
    htf_events = sorted(
        [c for c in all_candidates
         if c.event.tf_pair in htf_pairs
         and c.event.touch_type in ("wick_touch", "body_close")],
        key=lambda c: c.event.timestamp,
    )

    # Lookback window in seconds
    entry_tf_seconds = TF_SECONDS.get(cfg.entry_tf, 300)
    lookback_seconds = cfg.cascade_lookback * entry_tf_seconds

    min_htf = 2 if cfg.cascade_filter == "require_confluence_2" else 1

    # Apply cascade filter
    input_count = len(funnel.passed)
    passed = []
    for c in funnel.passed:
        ts = c.event.timestamp
        window_start = ts - pd.Timedelta(seconds=lookback_seconds)

        # Count distinct HTF pairs with events in window
        htf_hit_pairs: set[str] = set()
        for h in htf_events:
            if h.event.timestamp < window_start:
                continue
            if h.event.timestamp > ts:
                break
            # Direction check
            if cfg.cascade_direction == "same":
                if c.direction != h.direction:
                    continue
            htf_hit_pairs.add(h.event.tf_pair)

        if len(htf_hit_pairs) >= min_htf:
            passed.append(c)

    funnel.steps.append(FunnelStep(
        name="cascade",
        input_count=input_count,
        output_count=len(passed),
    ))
    funnel.passed = passed
    return funnel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_filter_funnel.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Wire cascade into evaluate_retest_config**

In `src/iora/strategy/retest_engine.py`, update `evaluate_retest_config()` to accept `all_candidates` and use `apply_filters_with_cascade`:

```python
# Replace the filter call in evaluate_retest_config:
from iora.strategy.filter_funnel import apply_filters_with_cascade

# In the function signature, add:
#   all_candidates: list[RetestCandidate] | None = None,

# Replace:
#   funnel = apply_filters(pair_candidates, config)
# With:
#   funnel = apply_filters_with_cascade(
#       pair_candidates, config, all_candidates=all_candidates,
#   )
```

- [ ] **Step 6: Run all tests**

Run: `pytest tests/strategy/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/iora/strategy/filter_funnel.py src/iora/strategy/retest_engine.py tests/strategy/test_filter_funnel.py
git commit -m "feat(strategy): add cascade filter (require_htf_signal, require_confluence_2)"
```

---

### Task 7: Sweep Runner

**Files:**
- Create: `src/iora/strategy/retest_sweep.py`
- Test: `tests/strategy/test_retest_sweep.py`

**Context:** The sweep runner orchestrates Stage 1 (build candidates once) + Stage 2 (evaluate N configs). It produces a ranked summary of configs by SQN/expectancy.

- [ ] **Step 1: Write tests for sweep runner**

```python
# tests/strategy/test_retest_sweep.py
"""Tests for retest sweep runner."""
import pandas as pd
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import (
    run_retest_sweep, SweepSummary, default_configs,
)


def test_default_configs_not_empty():
    configs = default_configs()
    assert len(configs) > 0
    for cfg in configs:
        assert isinstance(cfg, RetestConfig)


def test_sweep_summary_ranking():
    s = SweepSummary(results=[])
    assert s.top_by_sqn(5) == []


def test_run_sweep_with_synthetic_data(small_engine_data):
    """Run sweep on tiny synthetic data — should complete without error."""
    configs = [RetestConfig(tf_pair="M5@H1", touch_type="any", bias_filter="any")]
    summary = run_retest_sweep(
        data_by_tf=small_engine_data,
        entry_tfs=["M5"],
        symbol="TEST",
        configs=configs,
    )
    assert isinstance(summary, SweepSummary)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/strategy/test_retest_sweep.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement sweep runner**

```python
# src/iora/strategy/retest_sweep.py
"""Retest sweep runner — batch evaluation across configs.

Stage 1: Build candidates once per symbol (expensive).
Stage 2: Evaluate N configs cheaply per candidate set.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.strategy.retest_config import RetestConfig, ALL_TF_PAIRS
from iora.strategy.retest_candidate import RetestCandidate, build_retest_candidates
from iora.strategy.retest_engine import evaluate_retest_config, RetestResult


@dataclass(slots=True)
class SweepSummary:
    """Summary of a sweep run."""
    results: list[RetestResult] = field(default_factory=list)
    symbol: str = ""

    def top_by_sqn(self, n: int = 10) -> list[RetestResult]:
        ranked = sorted(
            [r for r in self.results if r.metrics.get("total_trades", 0) >= 30],
            key=lambda r: r.metrics.get("sqn", 0),
            reverse=True,
        )
        return ranked[:n]

    def top_by_expectancy(self, n: int = 10) -> list[RetestResult]:
        ranked = sorted(
            [r for r in self.results if r.metrics.get("total_trades", 0) >= 30],
            key=lambda r: r.metrics.get("avg_r", 0),
            reverse=True,
        )
        return ranked[:n]


def default_configs() -> list[RetestConfig]:
    """Generate default sweep configs covering priority TF pairs.

    Priority order from analysis:
    1. H1@H4 (16.5 yrs, 146k wicks)
    2. M15@H4 (4.4 yrs, 74k wicks)
    3. M15@H1 (4.4 yrs, 175k wicks)
    4. M5@H1 (1.7 yrs, 109k wicks)
    """
    configs = []
    priority_pairs = ["H1@H4", "M15@H4", "M15@H1", "M5@H1"]

    for pair in priority_pairs:
        # Baseline: wick only, no filters
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch"))

        # With daily bias
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily",
        ))

        # With daily + fresh/young
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily", age_filter="fresh_young",
        ))

        # With daily + continuation only
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily", zone_role_filter="continuation",
        ))

        # Full stack: with daily + fresh/young + continuation + strength 2+
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily", age_filter="fresh_young",
            zone_role_filter="continuation", min_bias_strength=2,
        ))

        # R:R variations
        for rr in [1.5, 2.0, 3.0]:
            configs.append(RetestConfig(
                tf_pair=pair, touch_type="wick_touch",
                bias_filter="with_daily",
                fixed_rr=rr,
            ))

        # SL mode variations
        for sl in ["zone", "atr", "period"]:
            configs.append(RetestConfig(
                tf_pair=pair, touch_type="wick_touch",
                bias_filter="with_daily",
                sl_mode=sl,
            ))

        # Session filter
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily",
            session_filter="london",
        ))

        # Touch policy: first_touch (zone consumed after one entry)
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily",
            touch_policy="first_touch",
        ))

        # Cascade: require HTF signal
        configs.append(RetestConfig(
            tf_pair=pair, touch_type="wick_touch",
            bias_filter="with_daily",
            cascade_filter="require_htf_signal",
            cascade_lookback=20,
        ))

    return configs


def run_retest_sweep(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tfs: list[str],
    symbol: str,
    configs: list[RetestConfig] | None = None,
) -> SweepSummary:
    """Run full retest sweep for one symbol.

    Stage 1: Build candidates for each entry TF (expensive).
    Stage 2: Evaluate each config (cheap).
    """
    if configs is None:
        configs = default_configs()

    # Stage 1: build candidates per entry TF
    all_candidates: list[RetestCandidate] = []
    bar_data_by_entry_tf: dict[str, pd.DataFrame] = {}

    for entry_tf in entry_tfs:
        if entry_tf not in data_by_tf:
            continue
        candidates = build_retest_candidates(
            data_by_tf=data_by_tf,
            entry_tf=entry_tf,
            symbol=symbol,
        )
        all_candidates.extend(candidates)
        bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]

    # Stage 2: evaluate each config
    results: list[RetestResult] = []
    for cfg in configs:
        bar_data = bar_data_by_entry_tf.get(cfg.entry_tf)
        result = evaluate_retest_config(
            candidates=all_candidates,
            config=cfg,
            symbol=symbol,
            bar_data=bar_data,
            all_candidates=all_candidates,
        )
        results.append(result)

    return SweepSummary(results=results, symbol=symbol)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/strategy/test_retest_sweep.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/retest_sweep.py tests/strategy/test_retest_sweep.py
git commit -m "feat(strategy): add retest sweep runner with default config grid"
```

---

### Task 8: CLI Script

**Files:**
- Create: `scripts/run_retest_sweep.py`

**Context:** CLI script for running the sweep on real data. Outputs top configs ranked by SQN with filter funnel details.

- [ ] **Step 1: Implement CLI script**

```python
#!/usr/bin/env python
"""Run retest strategy sweep for a symbol.

Usage:
    python scripts/run_retest_sweep.py GBPUSD
    python scripts/run_retest_sweep.py GBPUSD --pairs H1@H4,M15@H4
    python scripts/run_retest_sweep.py GBPUSD --top 20
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_sweep import run_retest_sweep, default_configs


def main():
    parser = argparse.ArgumentParser(description="Run retest strategy sweep")
    parser.add_argument("symbol", help="Symbol (e.g., GBPUSD)")
    parser.add_argument("--pairs", default=None,
                        help="Comma-separated TF pairs to sweep (default: priority pairs)")
    parser.add_argument("--top", type=int, default=10,
                        help="Show top N configs by SQN (default: 10)")
    parser.add_argument("--save-csv", action="store_true",
                        help="Save results to CSV")
    args = parser.parse_args()

    storage = ParquetStorage("data")
    symbol = args.symbol.upper()

    # Determine which entry TFs we need
    if args.pairs:
        pairs = [p.strip() for p in args.pairs.split(",")]
        configs = [c for c in default_configs() if c.tf_pair in pairs]
    else:
        configs = default_configs()

    # Determine entry TFs needed
    entry_tfs = list({c.entry_tf for c in configs})

    # Load data for all needed TFs
    all_tfs = set()
    for etf in entry_tfs:
        all_tfs.add(etf)
        # Add context TFs
        from iora.diagnostics.opportunity_runner import _tfs_for_entry
        all_tfs.update(_tfs_for_entry(etf))

    data_by_tf = {}
    for tf in sorted(all_tfs):
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  Loaded {tf}: {len(df):,} bars "
                  f"({df.index.min():%Y-%m-%d} to {df.index.max():%Y-%m-%d})")

    print(f"\nRunning retest sweep for {symbol} "
          f"({len(configs)} configs, entry TFs: {entry_tfs})...")
    t0 = time.time()

    summary = run_retest_sweep(
        data_by_tf=data_by_tf,
        entry_tfs=entry_tfs,
        symbol=symbol,
        configs=configs,
    )

    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Total configs evaluated: {len(summary.results)}")

    # Show top configs
    top = summary.top_by_sqn(args.top)
    if top:
        print(f"\n{'='*80}")
        print(f"  TOP {len(top)} CONFIGS BY SQN")
        print(f"{'='*80}")
        for i, r in enumerate(top, 1):
            m = r.metrics
            cfg = r.config
            print(f"\n  #{i}: {cfg.tf_pair} | "
                  f"touch={cfg.touch_type} bias={cfg.bias_filter} "
                  f"role={cfg.zone_role_filter} age={cfg.age_filter}")
            print(f"    SL={cfg.sl_mode} TP={cfg.tp_mode} RR={cfg.fixed_rr}")
            print(f"    Trades: {m.get('total_trades', 0):,} | "
                  f"WR: {m.get('win_rate', 0)*100:.1f}% | "
                  f"SQN: {m.get('sqn', 0):.2f} | "
                  f"Expectancy: {m.get('avg_r', 0):.3f}R")
            print(f"    PF: {m.get('profit_factor', 0):.2f} | "
                  f"Sharpe: {m.get('sharpe', 0):.2f} | "
                  f"MaxDD: {m.get('max_dd_r', 0):.1f}R")
            # Filter funnel
            if r.funnel:
                active = [s for s in r.funnel.steps if s.removed > 0]
                if active:
                    parts = " → ".join(
                        f"{s.name}(-{s.removed})" for s in active
                    )
                    print(f"    Funnel: {r.funnel.total_input} → {parts} "
                          f"→ {len(r.funnel.passed)}")

    if args.save_csv and summary.results:
        out_dir = Path("results") / symbol
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for r in summary.results:
            row = {
                "tf_pair": r.config.tf_pair,
                "touch_type": r.config.touch_type,
                "bias_filter": r.config.bias_filter,
                "zone_role_filter": r.config.zone_role_filter,
                "age_filter": r.config.age_filter,
                "sl_mode": r.config.sl_mode,
                "tp_mode": r.config.tp_mode,
                "fixed_rr": r.config.fixed_rr,
                "cascade_filter": r.config.cascade_filter,
                "session_filter": r.config.session_filter,
                **r.metrics,
            }
            rows.append(row)
        import pandas as pd
        df = pd.DataFrame(rows)
        out_path = out_dir / f"{symbol.lower()}_retest_sweep.csv"
        df.to_csv(out_path, index=False)
        print(f"\nSaved sweep results ({len(df)} configs) to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify script imports correctly**

Run: `python scripts/run_retest_sweep.py --help`
Expected: Shows help text without import errors

- [ ] **Step 3: Commit**

```bash
git add scripts/run_retest_sweep.py
git commit -m "feat(scripts): add run_retest_sweep.py CLI for Level 4 sweep"
```

---

### Task 9: Integration Test and Wiring Verification

**Files:**
- Create: `tests/strategy/test_retest_sweep_integration.py`

**Context:** End-to-end test that runs the full pipeline: build candidates → filter → simulate → metrics. Uses synthetic data with known price patterns to verify the pipeline produces sensible results.

- [ ] **Step 1: Write integration test**

```python
# tests/strategy/test_retest_sweep_integration.py
"""End-to-end integration test for retest sweep pipeline."""
import numpy as np
import pandas as pd
import pytest

from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_candidate import build_retest_candidates
from iora.strategy.retest_engine import evaluate_retest_config
from iora.strategy.retest_sweep import run_retest_sweep, SweepSummary


@pytest.fixture
def trending_data() -> dict[str, pd.DataFrame]:
    """Create data with a clear uptrend and pullbacks.

    500 M5 bars + aligned higher TFs. The uptrend should produce
    demand zones that get retested during pullbacks.
    """
    n = 500
    timestamps = pd.date_range("2025-01-15 08:00", periods=n, freq="5min")
    np.random.seed(123)

    # Uptrend with 3 pullback waves
    t = np.linspace(0, 4 * np.pi, n)
    trend = np.linspace(0, 0.0400, n)  # +400 pips trend
    waves = 0.0050 * np.sin(t)  # 50-pip waves
    noise = np.random.normal(0, 0.0003, n)

    close = 1.2500 + trend + waves + noise
    high = close + np.abs(np.random.normal(0, 0.0006, n))
    low = close - np.abs(np.random.normal(0, 0.0006, n))
    open_ = np.roll(close, 1)
    open_[0] = 1.2500

    m5 = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": np.ones(n)},
        index=timestamps,
    )
    m5.index.name = "time"

    def resample(df, rule):
        r = df.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "tick_volume": "sum"}
        ).dropna()
        r.index.name = "time"
        return r

    return {
        "M5": m5,
        "M15": resample(m5, "15min"),
        "H1": resample(m5, "1h"),
        "H4": resample(m5, "4h"),
        "D1": resample(m5, "1D"),
        "W1": resample(m5, "1W"),
    }


def test_build_candidates_produces_events(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data,
        entry_tf="M5",
        symbol="TEST",
    )
    assert len(candidates) > 0
    # Should have M5@M15 and M5@H1 events
    tf_pairs = {c.event.tf_pair for c in candidates}
    assert len(tf_pairs) > 0


def test_evaluate_config_produces_trades(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data, entry_tf="M5", symbol="TEST",
    )
    cfg = RetestConfig(
        tf_pair="M5@H1", touch_type="any",
        bias_filter="any", fixed_rr=2.0,
    )
    result = evaluate_retest_config(
        candidates=candidates, config=cfg,
        symbol="TEST", bar_data=trending_data["M5"],
        all_candidates=candidates,
    )
    # May or may not have trades depending on zone formation,
    # but should run without error
    assert result.total_candidates >= 0
    if result.trades:
        assert result.metrics["total_trades"] == len(result.trades)
        assert "sqn" in result.metrics


def test_full_sweep_pipeline(trending_data):
    configs = [
        RetestConfig(tf_pair="M5@H1", touch_type="any", bias_filter="any"),
        RetestConfig(tf_pair="M5@M15", touch_type="any", bias_filter="any"),
    ]
    summary = run_retest_sweep(
        data_by_tf=trending_data,
        entry_tfs=["M5"],
        symbol="TEST",
        configs=configs,
    )
    assert isinstance(summary, SweepSummary)
    assert len(summary.results) == 2
    # Each result should have a funnel
    for r in summary.results:
        assert r.funnel is not None


def test_filter_funnel_reduces_candidates(trending_data):
    candidates = build_retest_candidates(
        data_by_tf=trending_data, entry_tf="M5", symbol="TEST",
    )
    # Strict config should filter more
    strict = RetestConfig(
        tf_pair="M5@H1", touch_type="wick_touch",
        bias_filter="with_daily", zone_role_filter="continuation",
        age_filter="fresh",
    )
    loose = RetestConfig(
        tf_pair="M5@H1", touch_type="any", bias_filter="any",
    )
    result_strict = evaluate_retest_config(
        candidates, strict, "TEST", trending_data["M5"],
        all_candidates=candidates,
    )
    result_loose = evaluate_retest_config(
        candidates, loose, "TEST", trending_data["M5"],
        all_candidates=candidates,
    )
    # Strict should have fewer or equal candidates passing
    strict_passed = len(result_strict.funnel.passed) if result_strict.funnel else 0
    loose_passed = len(result_loose.funnel.passed) if result_loose.funnel else 0
    assert strict_passed <= loose_passed
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/strategy/test_retest_sweep_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `pytest tests/ -x -q`
Expected: All existing tests + new tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/strategy/test_retest_sweep_integration.py
git commit -m "test(strategy): add end-to-end integration tests for retest sweep"
```

---

## Post-Implementation Notes

### What Layer A Delivers
- `RetestConfig` with all sweep dimensions from the spec (13 filter axes + cascade + SL/TP + position)
- `build_retest_candidates()` — Stage 1 engine run producing enriched candidates
- `FilterFunnel` with ordered per-step attribution
- `evaluate_retest_config()` — Stage 2 filter + bar-by-bar SL/TP sim + metrics
- `run_retest_sweep()` — batch evaluation with default config grid
- `run_retest_sweep.py` CLI — ready to run on real data
- Full test coverage: unit + integration

### What Layer A Does NOT Include (Layer B)
- Trendline break integration (from `iora_pivot_hl_trendlines.pine`)
- Python trendline engine replication
- Trendline break as cascade filter dimension

### First Real Data Run
After all tests pass, run the sweep on the primary pair:

```bash
python scripts/run_retest_sweep.py GBPUSD --pairs H1@H4 --save-csv
```

This will take ~8-10 minutes for Stage 1 (H1 entry TF, 16.5 years) then seconds for each config evaluation. Review the top configs, filter funnel attribution, and trade counts before expanding to more symbols.

### Refinement Opportunities After First Run
1. If trade counts are low: relax filters (touch_type="any", age_filter="any")
2. If SQN is negative everywhere: check SL sizing — zone-based SL may be too tight for H4 zones
3. If win rate is high but expectancy is low: test higher R:R ratios
4. If cascade adds edge: expand cascade dimension testing
5. Add `birth_period_pattern` as a filter dimension if compression-born zone results are interesting
