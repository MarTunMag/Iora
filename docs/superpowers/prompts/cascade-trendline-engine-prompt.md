# Prompt: Build the Cascade Trendline Engine

Paste this into a fresh Claude Code CLI opened at C:\Iora

---

## PROMPT START

Read these files in order before writing any code:

1. `CLAUDE.md` — project rules (Python patterns, dataclass conventions, TF labels)
2. `docs/superpowers/specs/2026-04-08-cascade-trendline-engine-spec.md` — the design spec for what you're building
3. `docs/system/mechanical-cascade-strategy.md` — the full strategy this serves (read Section 3 for trendline rules, Section 4 for zone counting, Section 7 for implementation requirements)
4. `docs/archive/concepts_v1/standalone_rules/05_TRENDLINE_BREAKS.md` — original trendline break rules (impulse vs correction TL, what each break confirms)
5. `docs/archive/concepts_v1/standalone_rules/11_ZONE_TRACKING_REVERSAL_TARGETS.md` — zone tracking + reversal target identification (the "which zone caused the CHoCH" rule)
6. `src/iora/engine/push_zone_tick.py` — existing zone engine (BOS/CHoCH classification, push validation)
7. `src/iora/engine/push_zone_models.py` — PushZone, PeriodTracker, PushZoneTickState dataclasses
8. `src/iora/orchestrator/push_zone_engine.py` — how the engine is called per TF
9. `src/iora/orchestrator/pipeline.py` — the unified bar loop (where you'll wire new modules)
10. `src/iora/strategy/retest_config.py` — RetestConfig (where new filter fields go)
11. `src/iora/strategy/filter_funnel.py` — filter system (where new cascade filters go)
12. `src/iora/strategy/retest_engine.py` — sweep simulation engine (where cascade state feeds into candidate evaluation)
13. `src/iora/strategy/retest_sweep.py` — config generators (where cascade_sweep_configs goes)
14. `tw_indicators/iora_structure/iora_pivot_hl_trendlines.pine` — Pine reference implementation for trendline detection (TLState, checkBreak, pivot detection)

After reading all files, build the system in the task order from the spec (Tasks 1-14). Build in layers — each layer compiles and tests green before the next.

**Key patterns to follow:**
- All dataclasses use `@dataclass(slots=True)`
- Tick functions mutate state in place, return events/items
- Use `math.isnan()` for NaN checks
- Tests in `tests/` mirroring `src/iora/` structure
- Pipeline pattern: `init_*_state()` → per-bar `*_tick(state, ctx, config, bus)` calls
- TF labels: "M1", "M5", "M15", "H1", "H4", "D1", "W1"

**What you're building (3 layers):**

**Layer 1 — Trendline Detection** (`src/iora/engine/trendline_tick.py`):
- Uses PeriodTracker's `prev_highs[]` and `prev_lows[]` as confirmed pivots
- Two trendlines per TF: descending (connecting LH swing highs) and ascending (connecting HL swing lows)
- Break detection: body close through projected TL price (default), or wick (configurable)
- Classify as impulse or correction TL based on current trend direction
- Emit TrendlineBreakEvent on break (once per TL, reset when TL redrawn)

**Layer 2 — Zone Attribution** (enhance `push_zone_tick.py`):
- When BOS/CHoCH fires, find the last-created zone on the opposite side at the TF below
- Tag that zone as the "causing zone" for the structural event
- This identifies reversal targets: "the H1 zone that caused the H4 CHoCH"

**Layer 3 — Cascade State** (`src/iora/engine/cascade_state.py`):
- Per-bar state machine: D1 trend + H4 trend + TL break states + H1 zone count + phase
- Phase classification: d1_push, h4_correction, h1_extended, h1_terminal, at_reversal_target
- Read by sweep engine as filter dimensions

**Then wire into sweep:**
- New RetestConfig fields: cascade_phase_filter, tl_break_filter, h1_zone_count_filter, reversal_target_entry
- New filters in filter_funnel.py
- cascade_sweep_configs() generator in retest_sweep.py (~200-400 configs)
- run_cascade_sweep.py CLI runner
- Run GBPUSD sweep, analyze results

**Important context:**
- The existing HTF-triggered sweep (Tasks 1-13) is complete and working. 445+ tests pass. Don't break existing functionality.
- The symbol_specifications.json is already loaded for pip_size and spread. Use `_get_pip_size()` from `trade_converter.py`.
- The PeriodTracker already stores `prev_highs: list[float]` and `prev_lows: list[float]` with timestamps. These ARE your confirmed pivots — don't implement separate pivot detection.
- The Pine trendline indicator uses a `TLState` UDT with `checkBreak()` method. Study this for the break detection logic but implement in Python style (functions, not methods on UDTs).
- Existing tests are at 445+. Run `python -m pytest tests/ -x -q` to verify nothing breaks after each layer.

Start with Task 1 (TrendlineState + TrendlineBreakEvent dataclasses) and work through the tasks in order.

## PROMPT END
