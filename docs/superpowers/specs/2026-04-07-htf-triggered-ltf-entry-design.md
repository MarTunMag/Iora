# HTF-Triggered LTF Entry System — Design Spec

> **Date:** 2026-04-07
> **Status:** Design
> **Depends on:** Level 4 retest engine (complete), spread reality analysis (complete)

---

## 1. Problem Statement

The production config (H1@H4 limit, top edge, partial TP, TTL=0, spread=1.5p) delivers SQN 24.14 on GBPUSD. The SL is the full H4 zone width (~5-20 pips). The hypothesis: if we can find a **smaller LTF zone (M15 or M5) nested inside the H4 zone**, we get:

- **Tighter SL** (LTF zone = 1-8 pips vs H4 zone = 5-20 pips)
- **Same TP** (next H4 opposing zone)
- **Better R:R** (SL shrinks, TP stays)
- **Structural backing** from H4 zone (0% push zone break-through rate)

This has **never been tested**. M5@M15 standalone is dead at spread (SQN -11.72), but M5 zones *inside* H4 zones may survive because the H4 structural backing prevents break-through.

---

## 2. Entry Model

### New entry mode: `entry_mode="limit"` + `ltf_nesting != "none"`

The HTF-triggered LTF system is NOT a new entry_mode — it's an **overlay** on existing limit entry logic. The `ltf_nesting` config field activates it. When active:

1. The **trigger** is an H1@H4 retest event (H1 bar touches H4 zone)
2. The **entry** uses LTF zone boundaries instead of H4 zone boundaries
3. The **TP** stays at the H4-level opposing zone

### Sub-mode 1: Static Nesting (`ltf_nesting="static"`)

```
H1 bar retests H4 zone (trigger fires)
  → At that bar, scan all live push zones on LTF (M15 or M5)
  → Filter: LTF zone geometrically INSIDE H4 zone
    - Same side (demand inside demand, supply inside supply)
    - LTF zone top ≤ H4 zone top AND LTF zone bottom ≥ H4 zone bottom
  → Place limit at LTF zone TOP edge (where price first enters)
  → SL at LTF zone BOTTOM edge (full LTF zone width)
  → TP at next H4 opposing zone (from original H1@H4 candidate)
```

**Architecture decision: Option (a) — enrich at build time.** Populate `nested_ltf_zones` on `RetestCandidate` during `build_retest_candidates()`. This is cleaner than passing zone state into simulation because:
- The simulation loop stays stateless w.r.t. zone topology
- Same pattern as existing `breaker_zones` enrichment
- No new data flow paths needed

### Sub-mode 2: Dynamic Nesting (`ltf_nesting="dynamic"`)

```
H1 bar retests H4 zone (trigger fires)
  → Opens a "trigger window" (configurable bar count on entry TF)
  → Within window, track each bar on entry TF (M15 or M5)
  → When a NEW push zone is BORN inside the H4 zone:
    → Place limit at new LTF zone's TOP edge
    → SL at LTF zone BOTTOM edge
    → TP at next H4 opposing zone
  → Window closes when:
    → H4 zone body-close break, OR
    → trigger_window_bars expired, OR
    → Max fills per trigger reached
```

**Architecture decision: Option 1 — pre-compute `zone_births_by_bar` dict.** Collect zone birth events during `build_retest_candidates()` and pass alongside candidates. This is lighter than passing the full ZoneTimeline because:
- Only birth events matter (not the full zone lifecycle)
- Dict lookup is O(1) per bar in simulation
- Decouples the engine tick from simulation

---

## 3. Data Flow

### Current flow:
```
data_by_tf → build_retest_candidates() → list[RetestCandidate]
                                              ↓
                                   evaluate_retest_config()
                                              ↓
                                   _simulate_with_bars(passed, config, bar_data)
                                              ↓
                                   list[RetestTradeRecord]
```

### New flow (static):
```
data_by_tf → build_retest_candidates(ltf_tf="M15") → list[RetestCandidate]
              ├── enriches nested_ltf_zones on H1@H4 candidates
              └── scans state.tick_states["M15"].demand_zones/supply_zones
                                              ↓
                                   _simulate_with_bars()
                                   ├── detects ltf_nesting="static"
                                   ├── for each H1@H4 candidate with nested zones:
                                   │   creates modified candidates with LTF zone boundaries
                                   └── places limits at LTF zone top
```

### New flow (dynamic):
```
data_by_tf → build_retest_candidates(ltf_tf="M15")
              ├── list[RetestCandidate]
              └── zone_births: dict[Timestamp, list[ZoneBirthEvent]]
                                              ↓
                                   _simulate_with_bars(..., zone_births=zone_births)
                                   ├── detects ltf_nesting="dynamic"
                                   ├── when H1@H4 trigger fires → _ActiveTrigger created
                                   ├── each bar: check zone_births for LTF zone inside H4
                                   └── if found: place _PendingLimit at LTF zone top
```

### Key change to `build_retest_candidates` signature:

Currently returns `list[RetestCandidate]`. For dynamic mode, we need zone birth events too. Rather than changing the return type (which would break all callers), we:

1. Add a new function `build_retest_candidates_with_births()` that returns a `CandidateBuildResult` dataclass containing both candidates and zone births.
2. The existing `build_retest_candidates()` stays unchanged — it calls the new function and returns just the candidates.

```python
@dataclass(slots=True)
class CandidateBuildResult:
    candidates: list[RetestCandidate]
    zone_births: dict[pd.Timestamp, list[ZoneBirthEvent]]
```

---

## 4. New Config Fields

Added to `RetestConfig`:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `ltf_nesting` | `str` | `"none"` | `"none"`, `"static"`, `"dynamic"` |
| `trigger_tf_pair` | `str` | `"H1@H4"` | HTF pair providing the trigger signal |
| `entry_tf_override` | `str` | `""` | LTF for zone lookup (`"M15"`, `"M5"`, `"M1"`, or `""` = use tf_pair entry TF) |
| `trigger_window_bars` | `int` | `48` | Dynamic mode: max entry-TF bars after trigger |
| `require_ltf_push` | `bool` | `False` | Only use LTF push zones (0% break-through) |
| `trigger_also_trades` | `bool` | `False` | Also open the H1@H4 trade alongside nested LTF |
| `max_ltf_per_trigger` | `int` | `3` | Max LTF zone entries per trigger event |

---

## 5. New Data Structures

### On RetestCandidate (static nesting):

```python
nested_ltf_zones: list[tuple[float, float, str, str]] = field(default_factory=list)
# Each: (zone_top, zone_bottom, zone_tf, zone_role)
# Sorted by proximity to price (nearest first)
```

### ZoneBirthEvent (dynamic nesting):

```python
@dataclass(slots=True)
class ZoneBirthEvent:
    timestamp: pd.Timestamp
    zone_top: float
    zone_bottom: float
    zone_tf: str
    zone_side: str       # "demand" or "supply"
    zone_role: str       # "push", "continuation", "reversal", "pullback"
    is_push: bool
```

### _ActiveTrigger (simulation state machine):

```python
@dataclass(slots=True)
class _ActiveTrigger:
    h4_zone_top: float
    h4_zone_bottom: float
    h4_zone_side: str
    trigger_bar_idx: int
    window_bars: int
    candidate: RetestCandidate  # Original H1@H4 candidate (carries TP targets)
    fills: int = 0              # Trades opened from this trigger
    max_fills: int = 3
```

---

## 6. SL/TP Override Logic

When a nested LTF zone is used for entry (both modes):

| Component | Standard H1@H4 | HTF-triggered LTF |
|-----------|:-:|:-:|
| **Entry** | H4 zone top (limit) | LTF zone top (limit) |
| **SL** | H4 zone bottom - buffer | LTF zone bottom - buffer |
| **TP** | Next H4 opposing zone | Next H4 opposing zone (same) |
| **Spread** | Applied on entry price | Applied on entry price (same) |
| **min_sl_pips** | Enforced | Enforced (same) |

The override happens by creating a modified `RetestCandidate` with:
- `entry_price` = LTF zone top (demand) or bottom (supply)
- `zone_top` / `zone_bottom` = LTF zone boundaries
- All HTF opposing zone prices preserved from original candidate

This reuses all existing SL/TP computation (`compute_retest_sl`, `compute_retest_tp`) without changes.

---

## 7. Sweep Matrix

### Dimensions:

| Dimension | Values | Count |
|-----------|--------|:-----:|
| `trigger_tf_pair` | `"H1@H4"` | 1 |
| `entry_tf_override` | `"M15"`, `"M5"` | 2 |
| `ltf_nesting` | `"static"`, `"dynamic"` | 2 |
| `spread_pips` | `0`, `1.5` | 2 |
| `partial_tp` | `False`, `True` (70/30 rr=3.0) | 2 |
| `bias_filter` | `"any"`, `"against_daily"` | 2 |
| `min_sl_pips` | `0`, `3`, `5` | 3 |
| `require_ltf_push` | `False`, `True` | 2 |
| `trigger_window_bars` | `48` (static), `24`/`48`/`96` (dynamic) | varied |

**Static configs:** 2 × 1 × 2 × 2 × 2 × 3 × 2 = 96
**Dynamic configs:** 2 × 1 × 2 × 2 × 2 × 3 × 2 × 3 (window) = 144 (some overlap with static at window=48)
**Baseline comparison:** 2 (H1@H4 direct with/without partial)
**Total:** ~144 configs

### Baselines (always included):
- H1@H4 limit top partial TTL=0 spread=1.5 → SQN 24.14
- H1@H4 limit top no-partial TTL=0 spread=1.5

---

## 8. Success Criteria

1. Does ANY nested config beat H1@H4 direct (SQN 24.14) at spread=1.5?
2. Does M15-inside-H4 have viable SL (3+ pips > 1.5 pip spread)?
3. Does M5-inside-H4 have viable SL?
4. Does dynamic nesting find MORE trades than static?
5. Does partial TP rescue marginal nested configs?
6. Does `require_ltf_push=True` improve quality?

---

## 9. Open Questions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Multiple LTF zones per trigger? | Yes, up to `max_ltf_per_trigger=3` | Each is independent; more data points |
| Shared concurrent limit with non-nested? | Separate | Nested trades come from different zone boundaries |
| Trigger also opens H1@H4 trade? | Config flag `trigger_also_trades` | Test both; may want both simultaneously |

---

## 10. Files Changed

| File | Change Type | Description |
|------|:-----------:|-------------|
| `src/iora/strategy/retest_config.py` | Modify | Add 7 new fields |
| `src/iora/strategy/retest_candidate.py` | Modify | Add `nested_ltf_zones`, `ZoneBirthEvent`, `CandidateBuildResult`, zone birth collection, static nesting enrichment |
| `src/iora/strategy/retest_engine.py` | Modify | Add `_ActiveTrigger`, static/dynamic paths in `_simulate_with_bars()` |
| `src/iora/strategy/retest_sweep.py` | Modify | Add `htf_triggered_ltf_configs()` |
| `tests/strategy/test_htf_triggered_ltf.py` | Create | Tests for all new functionality |
| `scripts/run_htf_triggered_sweep.py` | Create | Runner script for the sweep |

---

## 11. Non-Goals

- No changes to the zone engine itself (push_zone_tick.py, push_zone_engine.py)
- No new entry_mode enum value — uses existing `"limit"` with `ltf_nesting` overlay
- No HA trailing (proven to hurt)
- No BE buffer optimization (marginal)
- TTL always 0 (proven best)
