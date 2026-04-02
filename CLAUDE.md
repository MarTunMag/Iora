# CLAUDE.md — Iora

> Read this file at the start of every session before touching any code.

---

## Project Overview

Iora is a multi-layer trading system with:
1. **Pine Script v6 indicators** — TradingView-based zone detection, structure tracking, push zones
2. **Python engine** — bar-by-bar pipeline replicating Pine logic for backtesting, signal generation, and automation
3. **Flask visualization** — lightweight chart viewer for trade overlay and backtest reporting

The Python engine is the primary development focus. Pine indicators serve as reference implementations and visual validation tools.

## Project Structure

```
src/iora/
  engine/                              Core tick-level logic (stateless per-bar functions)
    ha_pivots.py                       HA run-transition detection (zone fire events)
    push_zone_models.py                PushZone, PeriodTracker, PushZoneTickState dataclasses
    push_zone_tick.py                  Per-TF per-bar: zone creation, breaks, push validation, BOS/CHoCH
    zone_tick.py                       Fractal zone tick (legacy zone system)
    models.py                          BarContext, FractalZone, EventBus, EventID
    events.py                          EventBus implementation
  orchestrator/                        Multi-TF orchestration (calls engine/ per TF)
    push_zone_engine.py                Push zone engine: period tracking, nesting, count resets
    zone_engine.py                     Fractal zone engine (legacy)
    pipeline.py                        Unified pipeline: all engines in one bar loop
    signal_engine.py                   Signal layer: rules + position management
  data/                                Data loading and alignment
    tf_alignment.py                    Multi-TF alignment (merge_asof, edge detection, period boundaries)
    parquet_storage.py                 Parquet file loader (data/raw/{SYMBOL}/{YEAR}/)
    bar_iterator.py                    Bar-by-bar iterator over aligned data
  indicators/                          Indicator computations (heikin_ashi, etc.)
  rules/                               Entry/exit signal rules
  features/                            Feature extraction from engine state

tw_indicators/                         Pine Script v6 indicators
  iora_zones/                          Push zone indicators (reference implementations)
    iora_push_zones_v2.pine            Push zones with BOS/CHoCH (Python reference)
  system/                              System indicators (structure, zones, BOS/CHoCH)

docs/
  pinescriptv6/                        Full Pine v6 reference (68 files)
  system/                              Strategy rules, specs, and system documentation
  superpowers/specs/                   Design specs
  superpowers/plans/                   Implementation plans

data/raw/                              38 symbols in parquet format (MT5 export)
scripts/                               Verification and utility scripts
tests/                                 pytest test suite
```

### How to begin each session
1. Read this file
2. For Pine work: read `docs/pinescriptv6/LLM_MANIFEST.md` for v6 reference routing
3. For Python work: read relevant specs in `docs/superpowers/specs/`
4. Read the current files before modifying
5. Build in layers — each layer compiles cleanly before the next

---

## Rules for Writing Python

- Python 3.12+, pandas, numpy, pytest
- All dataclasses use `@dataclass(slots=True)`
- Follow existing patterns: engine tick functions mutate state in place, return broken/created items
- Pipeline pattern: `init_*_state()` → per-bar `*_tick(state, ctx, config, bus)` calls
- `BarContext` carries OHLC + `htf` dict (per-TF aligned data) + `edges` dict (fire edge flags)
- TF labels: `"M1"`, `"M5"`, `"M15"`, `"H1"`, `"H4"`, `"D1"`, `"W1"`, `"MN1"`
- TF order defined in `iora.constants`: `TF_ORDER`, `ENGINE_TF_ORDER` (without MN1)
- Three break standards: push validation (wick/body), zone breaks (body-close), period breaks (wick)
- Use `math.isnan()` for NaN checks, not `x != x` idiom
- Tests in `tests/` mirroring `src/iora/` structure

---

## Rules for Writing Pine Script

**Always follow these — no exceptions:**

- Always `//@version=6`
- All variables explicitly typed (`float`, `int`, `bool`, `string`, `color` — no implicit typing)
- No multiline ternaries — single line or wrap in parentheses
- No reserved keywords as variable names (`range`, `time`, `close`, `open`, `high`, `low`, `volume`, `bar_index`, etc.)
- `request.security()` calls bundled as tuples — max 40 total per script
- Timeframe strings: minutes as numbers (`"60"` not `"1H"`), days `"1D"`, weeks `"1W"`, months `"1M"`
- UDT fields explicitly typed with defaults
- Use `.copy()` when cloning UDT instances — never bare assignment for independent copies
- No semicolons as statement separators — one statement per line
- Broken zones deleted immediately — never styled as "ghost" zones
- Field assignment on `.get()` result: store in local variable first (`FractalZone zref = arr.get(j)` then `zref.bx := na`)

---

## Pine Script v6 Reference

Full v6 docs in `docs/pinescriptv6/`. Route via `docs/pinescriptv6/LLM_MANIFEST.md`.

| Topic | File |
|-------|------|
| Execution model, var/varip | `concepts/execution_model.md` |
| Common errors (50+) | `concepts/common_errors.md` |
| Type system & qualifiers | `reference/types.md` |
| Keywords (var, type, enum, method) | `reference/keywords.md` |
| Methods & dot notation | `concepts/methods.md` |
| Objects & UDTs | `concepts/objects.md` |
| Timeframes | `concepts/timeframes.md` |
| request.security & multi-TF | `reference/functions/request.md` |
| TA functions | `reference/functions/ta.md` |
| Drawing (line, box, label) | `reference/functions/drawing.md` |
| Collections (array, map, matrix) | `reference/functions/collections.md` |
| Colors & display | `visuals/colors.md` |

---

## Known Pine v6 Gotchas

1. **Multiline ternaries** — Keep on one line or wrap in parentheses
2. **`range` is reserved** — Use `zoneRange`, `priceRange`, etc.
3. **Tuple unpacking** — Must match return count exactly
4. **Series vs Simple** — Built-in functions need `simple` params; use `input.int()` not runtime conditionals
5. **Timeframe strings** — `"1"`, `"5"`, `"15"`, `"60"`, `"240"`, `"1D"`, `"1W"`, `"1M"` (not `"1H"`)
6. **request.security() limit** — Hard cap 40 calls. Use tuple returns to batch.
7. **Object reference** — Use `.copy()` for independent copies
8. **max_bars_back** — Set explicitly for `series[dynamic_int]`
9. **Collections in request.security()** — Avoid (memory explosion). Return scalars.
10. **var inside if** — Initializes on first `true`, not bar 0
11. **Field assignment on .get()** — `zones.get(j).bx := na` fails. Store in local variable first.
