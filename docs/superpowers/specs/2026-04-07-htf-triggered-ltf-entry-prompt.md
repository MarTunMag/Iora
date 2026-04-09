# HTF-Triggered LTF Entry System — Complete Implementation Prompt

> **For:** Fresh Claude Code CLI chat
> **Date:** 2026-04-07
> **Goal:** Design spec → Implementation plan → Build → Sweep → Analyze

---

## READ FIRST (in order)

1. `CLAUDE.md` — project rules, structure, Python conventions
2. `docs/system/level4-spread-reality-analysis.md` — which configs survive spread
3. `docs/system/level4-findings-and-next-steps.md` — all validated findings + cascade model
4. `docs/system/level4-cross-tf-tp-deep-analysis.md` — dual-profile strategy
5. `docs/system/level4-v3-realistic-sweep-analysis.md` — TTL=0 findings
6. `docs/system/trading_concepts_reference.md` — YouTube concepts mapped to our system
7. `src/iora/strategy/retest_config.py` — all sweep dimensions
8. `src/iora/strategy/retest_engine.py` — simulation engine (~966 lines)
9. `src/iora/strategy/retest_candidate.py` — candidate builder + zone enrichment

---

## CONTEXT — What Works, What Doesn't, What's Untested

### Proven production config (spread=1.5p FX):
- **H1@H4 limit, top edge, partial TP (70% at rr=3.0, 30% at H1 zone), TTL=0**: SQN 24.14, PF 2.54, WR 54.6%, 3,747 trades over 16.5 years on GBPUSD
- H4 zone width gives 5+ pip SL → 1.5-pip spread is only ~30% of SL → survivable
- Push zones: 0% break-through rate across 13,870 interactions

### Tested and failed at real spread (specific configs only):
- M5@M15 limit at zone BOTTOM with spread=1.5p: SQN -11.72 (1.2 pip SL < 1.5 pip spread)
- M5@M15 limit at zone TOP WITHOUT partial: SQN -2.88 (26.5% WR too low)
- BUT: Live production running M5@M15 is profitable (+$100 on 2026-04-07)
- This means M5@M15 is NOT necessarily dead — the RIGHT config may work

### NEVER TESTED (critical gaps this project fills):
- **M5@M15 top edge + partial TP + spread** — NEVER RUN. H1@H4 went from SQN 1.61 → 24.14 with partial. Same transformation on M5@M15 is UNKNOWN.
- **M5@M15 with min_sl_pips floor + spread** — only tested at min_sl=5 briefly (SQN 6.30), never with partial TP
- **M1@M5 and M1@M15 with min_sl floor + partial** — never tested at all
- M15/M5 zones INSIDE H4 zones, triggered by H1@H4 retest
- The hypothesis: LTF zone inside H4 zone gets structural backing from H4 → same hold rate, tighter SL, better R:R

### IMPORTANT PRINCIPLE: Test everything. Assume nothing.
Do NOT label any config "dead" until it has been tested with ALL relevant parameters
(partial TP, min_sl floor, spread). A config that fails without partial may succeed with it.

### Learnings that MUST carry forward:
- TTL=0 (keep limits until zone breaks) doubles trade count
- Partial TP transforms marginal configs into strong ones
- Zone-top entry (where price first touches) is correct for live
- Spread MUST be modeled in every backtest (minimum spread_pips=1.5 for FX)
- HA trailing HURTS — don't use it
- BE buffer is marginal — keep at 0
- Against-daily bias works on H1@H4 (counter-trend pullbacks to zones)

---

## THE ENTRY MODEL TO BUILD

### New entry mode: `entry_mode="htf_triggered_ltf"`

Two sub-modes via `ltf_nesting` config field:

### Sub-mode 1: Static Nesting (`ltf_nesting="static"`)

```
H1 bar retests H4 zone (trigger fires on the entry_map timestamp)
  → At that bar, scan all live push zones on the LTF (M15 or M5)
  → Filter: LTF zone's price range falls INSIDE the H4 zone boundaries
    - For demand H4 zone: LTF demand zone with top <= H4 zone top AND bottom >= H4 zone bottom
    - For supply H4 zone: LTF supply zone with bottom >= H4 zone bottom AND top <= H4 zone top
    - LTF zone must be SAME SIDE as H4 zone (demand inside demand, supply inside supply)
  → Place limit at LTF zone TOP edge (where price first enters)
  → SL at LTF zone BOTTOM edge (full LTF zone width)
  → TP at next H4 opposing zone (same target as H1@H4 baseline)
```

**Data access:** At simulation time, the `RetestCandidate` already carries `zone_top`/`zone_bottom` for the H4 context zone. The LTF zones are accessible via `build_retest_candidates()` which runs the full pipeline — the `state.tick_states[ltf].supply_zones` and `.demand_zones` are available per bar. BUT the current `_simulate_with_bars()` only receives pre-filtered candidates and bar_data — it does NOT have access to the live zone state.

**Architecture decision needed:** Either:
- (a) Enrich RetestCandidate at build time with nested LTF zone info, OR
- (b) Pass the zone timeline into simulation so it can look up LTF zones at fill time

Option (a) is cleaner — add fields to RetestCandidate during `build_retest_candidates()`.

### Sub-mode 2: Dynamic Nesting (`ltf_nesting="dynamic"`)

```
H1 bar retests H4 zone (trigger fires)
  → Opens a "trigger window" on the entry TF (configurable bar count)
  → Within that window, track each bar on entry_tf (M15 or M5)
  → When a NEW push zone is BORN inside the H4 zone boundaries:
    → Place limit at the new LTF zone's TOP edge
    → SL at LTF zone BOTTOM edge
    → TP at next H4 opposing zone
  → Window closes when:
    → H4 zone body-close break (zone invalidated), OR
    → trigger_window_bars expired, OR
    → A trade from this trigger is already open (max_concurrent per trigger)
```

**Data access:** This requires bar-by-bar tracking within the simulation loop. The simulation needs to know:
1. Which H4 zones are currently "triggered" (H1 retested them)
2. On each bar, whether any new LTF zone was born inside a triggered H4 zone

**Architecture:** This needs a state machine inside `_simulate_with_bars()`:
- `_ActiveTrigger` dataclass: H4 zone boundaries, trigger_bar_idx, entry_tf, window_bars_remaining
- On each bar: check if any active trigger's H4 zone has a new LTF zone born inside it
- If yes: create a `_PendingLimit` at the LTF zone top

**Key data requirement:** The simulation needs the `ZoneTimeline` or equivalent zone-birth events per bar. Currently `build_retest_candidates` runs the engine and captures events, but `_simulate_with_bars` only gets the final candidate list. For dynamic nesting, we need zone birth events available per bar during simulation.

**Two options:**
1. Pre-compute a `zone_births_by_bar` dict from the zone timeline (mapping timestamp → list of new zones born on that bar, per TF)
2. Pass the full ZoneTimeline into the simulation

Option 1 is lighter — compute it in `build_retest_candidates` and pass alongside.

---

## NEW CONFIG FIELDS

Add to `RetestConfig`:

```python
# HTF-triggered LTF entry
ltf_nesting: str = "none"              # "none" (standard), "static", "dynamic"
trigger_tf_pair: str = "H1@H4"        # The HTF pair that provides the trigger
entry_tf_override: str = ""            # Override entry TF for LTF zone lookup ("M15", "M5", "M1")
                                       # Empty = derive from tf_pair's entry TF
trigger_window_bars: int = 48          # Dynamic mode: max entry-TF bars after trigger (48 M15 bars = 12h)
require_ltf_push: bool = False         # Only use LTF push zones (not continuation/reversal)
```

When `ltf_nesting != "none"`:
- `entry_mode` should be `"limit"` (we're placing limits at LTF zone edges)
- `limit_edge` should be `"top"` (where price first enters the LTF zone)
- `sl_mode` effectively becomes "ltf_zone" (SL at LTF zone boundary, not H4 zone boundary)
- The SL override happens by setting entry_price = LTF zone top and zone boundaries = LTF zone boundaries on the candidate before SL/TP computation

---

## NEW DATA STRUCTURES

### For static nesting:

Add to `RetestCandidate`:
```python
# Nested LTF zones (populated when ltf_nesting="static")
nested_ltf_zones: list[tuple[float, float, str, str]] = field(default_factory=list)
# Each: (zone_top, zone_bottom, zone_tf, zone_role)
# Sorted by proximity to price (nearest first)
```

Populated during `build_retest_candidates()` by scanning `state.tick_states[ltf_tf].demand_zones` + `.supply_zones` and filtering for zones geometrically inside the context zone.

### For dynamic nesting:

New dataclass for passing zone birth events:
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
    is_push: bool        # True if push zone (0% break-through)
```

Pre-computed dict: `zone_births: dict[pd.Timestamp, list[ZoneBirthEvent]]`

New state machine in simulation:
```python
@dataclass(slots=True)
class _ActiveTrigger:
    """H4 zone that has been triggered by an H1 retest."""
    h4_zone_top: float
    h4_zone_bottom: float
    h4_zone_side: str      # "demand" or "supply"
    trigger_bar_idx: int
    window_bars: int        # Max bars to keep window open
    candidate: RetestCandidate  # The original H1@H4 candidate (for TP computation)
    filled: bool = False    # Has a trade been opened from this trigger?
```

---

## SIMULATION FLOW CHANGES

### In `_simulate_with_bars()`:

```python
is_htf_triggered = config.ltf_nesting in ("static", "dynamic")

if is_htf_triggered:
    if config.ltf_nesting == "static":
        # Entry_map candidates already carry nested_ltf_zones
        # For each candidate at this bar:
        #   For each nested LTF zone:
        #     Create a modified candidate with:
        #       entry_price = LTF zone_top (demand) or zone_bottom (supply)
        #       zone_top/zone_bottom = LTF zone boundaries (for SL computation)
        #       Keep original opposing_zone_h4 for TP
        #     Place limit at LTF zone top edge
        pass

    elif config.ltf_nesting == "dynamic":
        # 1. Check if this bar triggers any new H4 retests → add to active_triggers
        # 2. For each active trigger:
        #    a. Check window expiry (bar_idx - trigger_bar_idx > window_bars)
        #    b. Check H4 zone break (body-close through boundary)
        #    c. Check if new LTF zone born inside H4 zone (from zone_births dict)
        #    d. If new zone found: place _PendingLimit at LTF zone top
        pass
```

### Key SL/TP override for both modes:

When a nested LTF zone is used for entry:
- **Entry:** limit at LTF zone TOP (demand) or BOTTOM (supply) — where price first enters
- **SL:** LTF zone BOTTOM (demand) or TOP (supply) — full LTF zone width
- **TP:** Next H4 opposing zone (from original H1@H4 candidate) — same structural target
- **Spread adjustment:** Applied on top of LTF limit entry price
- **min_sl_pips:** Applied to enforce minimum distance

This means R:R improves because SL shrinks (LTF zone = 3-8 pips vs H4 zone = 10-20 pips) while TP stays the same.

---

## SWEEP CONFIGURATION

### Sweep dimensions for GBPUSD with spread:

| Dimension | Values | Count |
|-----------|--------|-------|
| `trigger_tf_pair` | `"H1@H4"` | 1 |
| `entry_tf_override` | `"M15"`, `"M5"` | 2 |
| `ltf_nesting` | `"static"`, `"dynamic"` | 2 |
| `limit_edge` | `"top"` | 1 |
| `spread_pips` | `0`, `1.5` | 2 |
| `partial_tp` | `False`, `True` (70/30 rr=3.0) | 2 |
| `limit_ttl` | `0` | 1 |
| `bias_filter` | `"any"`, `"against_daily"` | 2 |
| `min_sl_pips` | `0`, `3`, `5` | 3 |
| `require_ltf_push` | `False`, `True` | 2 |
| `trigger_window_bars` | `48` (static ignores), `24`, `96` (dynamic only) | varied |

**Estimated configs:** ~96-144 configs

### CRITICAL ADDITION: Standalone M5@M15 configs that were NEVER TESTED

**Context:** Live production running M5@M15 is profitable (+$100 on 2026-04-07). The backtest
only tested M5@M15 bottom-edge and M5@M15 top-edge WITHOUT partial TP at spread=1.5p.
M5@M15 top-edge + partial TP + spread was NEVER RUN. H1@H4 went from SQN 1.61 (top, no
partial) to SQN 24.14 (top + partial). The same transformation on M5@M15 is unknown.

**DO NOT assume M5@M15 standalone is dead. TEST IT.**

Add these standalone configs to the sweep:

| Config | Description |
|--------|-------------|
| M5@M15 limit top partial TTL=0 spread=1.5 | **THE MISSING TEST** |
| M5@M15 limit top partial TTL=0 spread=1.5 min_sl=3 | With SL floor |
| M5@M15 limit top partial TTL=0 spread=1.5 min_sl=5 | With wider SL floor |
| M5@M15 limit top partial TTL=0 spread=0 | Baseline without spread |
| M5@M15 limit top no-partial TTL=0 spread=1.5 min_sl=3 | SL floor without partial |
| M5@M15 limit top no-partial TTL=0 spread=1.5 min_sl=5 | SL floor without partial |
| M5@M15 limit bottom partial TTL=0 spread=1.5 min_sl=5 | Bottom + partial + floor |
| M15@H1 limit top partial TTL=0 spread=1.5 | M15 standalone for comparison |
| M1@M5 limit top partial TTL=0 spread=1.5 min_sl=3 | Test M1 too — don't assume |
| M1@M15 limit top partial TTL=0 spread=1.5 min_sl=3 | Test M1@M15 too |

Also add M5@M15 with bias filters (against_daily, any) and push zone filter.

### Baseline comparison (include in same sweep):
- H1@H4 limit top partial TTL=0 spread=1.5 → SQN 24.14 (the known winner)
- H1@H4 limit top no-partial TTL=0 spread=1.5 → for comparison

### Success criteria:
1. Does ANY nested config beat H1@H4 direct on SQN at spread=1.5?
2. Does M15-inside-H4 have viable SL (3+ pips > 1.5 pip spread)?
3. Does M5-inside-H4 have viable SL? (test, don't assume)
4. Does dynamic nesting find MORE trades than static?
5. Does partial TP rescue marginal nested configs (like it did for H1@H4)?
6. Does `require_ltf_push=True` improve quality (push zones = 0% break)?
7. **NEW: Does M5@M15 standalone top+partial survive spread=1.5?** (never tested before!)
8. **NEW: Does min_sl_pips=3 or 5 rescue M5@M15 at real spread?**
9. **NEW: Are M1@M5 / M1@M15 viable with min_sl floor + partial?**
10. **NEW: How do standalone LTF configs compare to HTF-triggered LTF configs?**

---

## IMPLEMENTATION ORDER

### Phase 1: Config + Data Structures
1. Add new fields to `RetestConfig` (`ltf_nesting`, `trigger_tf_pair`, `entry_tf_override`, `trigger_window_bars`, `require_ltf_push`)
2. Add `nested_ltf_zones` to `RetestCandidate`
3. Add `ZoneBirthEvent` dataclass
4. Write tests for new config validation

### Phase 2: Static Nesting (Candidate Enrichment)
1. In `build_retest_candidates()`: when an H1@H4 retest event fires, scan LTF zones inside H4 zone
2. Populate `nested_ltf_zones` on the candidate
3. Write tests: known zone geometry → correct nesting detection

### Phase 3: Dynamic Nesting (Zone Birth Tracking)
1. In `build_retest_candidates()`: collect `zone_births` dict (timestamp → list of ZoneBirthEvent)
2. Return this alongside the candidate list (modify return type or add to a result container)
3. Write tests: zone birth events correctly captured at right timestamps

### Phase 4: Simulation Engine Changes
1. Add static nesting path in `_simulate_with_bars()`: expand nested LTF zones into pending limits
2. Add dynamic nesting path: `_ActiveTrigger` state machine, window management, zone birth lookup
3. Both paths: override candidate entry/SL to use LTF zone boundaries, keep H4 TP
4. Write tests: known scenarios with nested zones → correct trade entries and SL/TP

### Phase 5: Sweep Runner + Execution
1. Add HTF-triggered configs to sweep generator (`retest_sweep.py`)
2. Run full sweep on GBPUSD with spread=1.5p
3. Generate comparison CSV: nested configs vs H1@H4 baseline
4. Analyze results

### Phase 6: Analysis
1. Compare SQN, PF, WR, trade count, avg SL pips, avg R:R across all configs
2. Bucket by: static vs dynamic, M15 vs M5, with/without partial TP, with/without push filter
3. Answer the 6 success criteria questions above
4. Write findings to `docs/system/level4-htf-triggered-ltf-analysis.md`

---

## CRITICAL RULES

1. **Test everything, assume nothing.** Don't skip ANY timeframe because "it might not work." M5, M1, M15 — run them ALL. Let data decide. The user's live M5@M15 system is profitable, so our backtest "dead" conclusion was premature — we hadn't tested the right config.
2. **Spread in every backtest.** Minimum spread_pips=1.5 for FX. Include spread=0 for comparison only.
3. **Never call a config "dead" without testing all parameters.** Partial TP, min_sl floor, and bias filter can each transform a losing config into a winner. Test the full matrix.
4. **Follow existing patterns.** `@dataclass(slots=True)`, pipeline pattern, engine tick mutations.
5. **Run pytest after each phase.** All 340+ existing tests must pass before moving forward.
6. **Commit after each phase.** Small, clean commits with descriptive messages.
7. **No HA trailing.** It hurts. Don't add it to nested configs.
7. **TTL=0 always.** Keep limits until zone breaks. It doubles trade count.

---

## FILE CHANGES SUMMARY

| File | Changes |
|------|---------|
| `src/iora/strategy/retest_config.py` | Add 5 new fields |
| `src/iora/strategy/retest_candidate.py` | Add `nested_ltf_zones`, `ZoneBirthEvent`, zone birth collection |
| `src/iora/strategy/retest_engine.py` | Add `_ActiveTrigger`, static/dynamic paths in `_simulate_with_bars()` |
| `src/iora/strategy/retest_sweep.py` | Add HTF-triggered sweep configs |
| `tests/strategy/test_htf_triggered_ltf.py` | New test file for the feature |
| `scripts/run_htf_triggered_sweep.py` | New runner script |
| `docs/system/level4-htf-triggered-ltf-analysis.md` | Results analysis |

---

## QUESTIONS FOR THE DESKTOP CHAT

If anything is unclear during implementation, check with the user via the desktop Claude Code chat. Key questions that might arise:

1. Should dynamic nesting allow MULTIPLE LTF zones per trigger (multiple limits from one H4 retest)?
   - **Recommendation:** Yes, allow up to 3 per trigger. Each is an independent trade.
2. Should nested trades share the `max_concurrent=1` limit with non-nested trades?
   - **Recommendation:** Separate limit. One active nested trade per trigger window.
3. Should the H1@H4 trigger itself ALSO open a trade (original H1@H4 entry + nested LTF entry simultaneously)?
   - **Recommendation:** Test both. Add a `trigger_also_trades: bool` config flag.

---

## START

Begin by writing the design spec to `docs/superpowers/specs/2026-04-07-htf-triggered-ltf-entry-design.md`, then create the implementation plan, then build phase by phase. Run the sweep on GBPUSD and analyze.
