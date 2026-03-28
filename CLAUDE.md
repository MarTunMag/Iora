# CLAUDE.md — Iora

> Read this file at the start of every session before touching any code.

---

## Project Overview

Iora is a TradingView Pine Script v6 project for building rule-based trading indicators and strategies. The project is starting fresh — strategy rules, system specs, and documentation will be built from scratch in `docs/system/`.

## Project Structure

```
tw_indicators/
  templates/                           Template indicators (reference/starting points)
    HA Engulfing Fib.pine              Heikin-Ashi engulfing with Fibonacci levels
    ha_supply_demand_zones.pine        HA-based supply/demand zone detection
    HTF Candles (M5 - 12MN).pine       Higher timeframe candle overlay
    spring_leaf_structure_v2.pine      Structure detection (legacy reference)

docs/
  pinescriptv6/                        Full Pine v6 reference (68 files)
  system/                              Strategy rules, specs, and system documentation (TBD)
```

### How to begin each session
1. Read this file
2. Read `docs/pinescriptv6/LLM_MANIFEST.md` for Pine v6 reference routing
3. Read any relevant strategy docs in `docs/system/` (once created)
4. Read the current indicator files before modifying
5. Build in layers — each layer compiles cleanly before the next

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
