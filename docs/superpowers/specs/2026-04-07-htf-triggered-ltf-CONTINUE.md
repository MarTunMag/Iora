# HTF-Triggered LTF Entry System — CONTINUATION PROMPT

> **For:** Fresh Claude Code CLI chat (previous session died mid-execution)
> **Date:** 2026-04-07
> **Status:** Plan + spec + test file exist. ZERO implementation code written yet.

---

## WHAT TO DO

### Step 1: Read these files (in order)
1. `CLAUDE.md` — project rules
2. `docs/superpowers/specs/2026-04-07-htf-triggered-ltf-entry-design.md` — the full design spec
3. `docs/superpowers/plans/2026-04-07-htf-triggered-ltf-entry.md` — the 13-task implementation plan
4. `docs/superpowers/specs/2026-04-07-htf-triggered-ltf-entry-prompt.md` — full context (what works, what doesn't, what's untested, YouTube synthesis, sweep dimensions)

### Step 2: Check current state
- Run `git status` — you'll see untracked spec/plan/test files, no code changes
- Run `grep -r "ltf_nesting" src/` — will return nothing (no implementation yet)
- The test file `tests/strategy/test_htf_triggered_ltf.py` exists but will fail (no code to test)

### Step 3: Execute the plan
Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to execute the 13-task plan at `docs/superpowers/plans/2026-04-07-htf-triggered-ltf-entry.md`.

**Start from Task 1.** Nothing has been implemented yet.

The plan has 13 tasks:
1. Add config fields to RetestConfig
2. Add ZoneBirthEvent and CandidateBuildResult dataclasses
3. Add nested_ltf_zones field to RetestCandidate
4. Static nesting — _find_nested_ltf_zones function
5. Static nesting — enrich candidates in build_retest_candidates
6. Dynamic nesting — zone birth event collection
7. Static nesting path in simulation engine
8. Dynamic nesting — _ActiveTrigger state machine
9. Wire evaluate_retest_config and sweep runner for nesting
10. Sweep config generator — htf_triggered_ltf_configs
11. Standalone LTF configs (M5@M15, M1@M5, M1@M15 with partial + min_sl)
12. CLI runner script
13. Run sweep on GBPUSD and analyze results

Tasks 4+5 can run in parallel with Task 6. Tasks 7+8 can run in parallel.

### Step 4: After sweep completes
Write analysis to `docs/system/level4-htf-triggered-ltf-analysis.md` answering these questions:
1. Does ANY nested config beat H1@H4 direct (SQN 24.14) at spread=1.5?
2. Does M15-inside-H4 have viable SL (3+ pips > 1.5 pip spread)?
3. Does M5-inside-H4 have viable SL?
4. Does dynamic nesting find MORE trades than static?
5. Does partial TP rescue marginal nested configs?
6. Does require_ltf_push=True improve quality?
7. **Does M5@M15 standalone top+partial survive spread=1.5?** (NEVER TESTED BEFORE)
8. **Does min_sl_pips=3 or 5 rescue M5@M15 at real spread?**
9. **Are M1@M5 / M1@M15 viable with min_sl floor + partial?**
10. **How do standalone LTF configs compare to HTF-triggered LTF configs?**

---

## CRITICAL CONTEXT

### What's proven:
- H1@H4 limit, top edge, partial TP (70% at rr=3.0), TTL=0, spread=1.5p → SQN 24.14
- Push zones: 0% break-through rate across 13,870 interactions
- Partial TP transforms marginal configs into strong (H1@H4 went from SQN 1.61 → 24.14)

### What's NOT dead (test it):
- M5@M15 standalone with top edge + partial TP + spread was NEVER TESTED
- Live production running M5@M15 is profitable (+$100 on 2026-04-07)
- M5@M15 bottom edge at spread IS dead (SQN -11.72) — but top+partial is unknown
- M1 timeframes with min_sl floor — never tested at all

### Rules:
- Test everything, assume nothing. No config is "dead" until tested with full parameter matrix
- Spread=1.5p in every FX backtest
- TTL=0 always (doubles trade count)
- No HA trailing (hurts performance)
- Follow existing patterns: @dataclass(slots=True), pipeline pattern
- Run pytest after each task — all 340+ existing tests must still pass
- Commit after each task with descriptive messages

---

## GAP ANALYSIS — 4 Config Dimensions to ADD to the Plan

The video transcript audit found 4 high-value concepts that EVERY professional educator teaches
but are NOT yet in our sweep. Add these as sweep dimensions — they're low code effort.

### 1. `min_rr_ratio` pre-filter (CRITICAL — every video insists on this)
Every single video says: skip trades below 3:1 R:R. Our sweep takes every valid candidate
regardless of R:R. Add a pre-filter in `_simulate_with_bars()`:
```python
min_rr_ratio: float = 0.0  # 0.0 = no filter, 2.0, 3.0
```
After SL/TP computation, reject candidates where `(TP_distance / SL_distance) < min_rr_ratio`.
**Sweep values:** 0.0, 2.0, 3.0

### 2. `tp_target_tf` for nested entries
Nested LTF entries could target H1 opposing zone (closer, higher WR) or H4 opposing zone
(further, higher R:R). RetestCandidate already carries opposing_zone_h1 and opposing_zone_h4.
```python
tp_target_tf: str = "H4"  # "H1", "H4", "D1" — for nested entries only
```
**Sweep values:** "H1", "H4"

### 3. `session_filter` on nested entries
London/NY sessions have institutional volume. Asian session entries may be noise.
Already in RetestConfig as `session_filter` field. Just include it in the nested sweep.
**Sweep values:** "any", "london_ny_overlap", "no_asian"

### 4. `entry_refinement` within LTF zone (Fibonacci 50% vs zone top)
Videos teach entering at 50%-61.8% of the zone, not just the edge. Simple price calc:
`entry = zone_bottom + (zone_top - zone_bottom) * 0.5` for demand.
```python
entry_refinement: str = "zone_top"  # "zone_top", "zone_50pct"
```
**Sweep values:** "zone_top", "zone_50pct"

**Add these 4 fields to RetestConfig in Task 1, add to the sweep generator in Task 10,
and include in the sweep dimensions. They're each 3-10 lines of code.**

---

## IF ANYTHING IS UNCLEAR

The design spec and plan are comprehensive. But if you hit ambiguity:

1. **Multiple LTF zones per trigger:** Allow up to 3 (max_ltf_per_trigger config field)
2. **Concurrent limits:** Nested trades have their own tracking separate from standard trades
3. **trigger_also_trades:** Config flag — when True, the H1@H4 trigger ALSO opens its own trade alongside nested LTF entries
4. **Zone identity for dynamic nesting:** Use (zone_top, zone_bottom, origin_time) tuple + seen_zones set — NOT prev_zone_counts (the plan addresses this explicitly)

---

## START

Read the design spec, then execute the plan from Task 1. Go.
