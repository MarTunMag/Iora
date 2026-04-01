# Iora Push Zones v2 — Design Spec

**Date:** 2026-04-01
**File:** `tw_indicators/iora_zones/iora_push_zones_v2.pine`
**Base:** `tw_indicators/iora_zones/templates/iora_push_zones.pine` (v1 frozen copy)
**Rules:** `docs/concepts/standalone_rules/03_ZONE_COUNTING.md`, `04_ZONE_NESTING.md`

---

## Overview

Extends the push zones indicator with two major features:

1. **Zone Counting** — number each zone per TF per side (supply/demand independently) since the last parent TF same-side zone fire. Exhaustion signals at count 5 and 8 (5+3 terminal).
2. **Zone Nesting** — detect when a child zone is fully contained inside a parent zone. Same-direction = continuation. Opposing direction = terminal (zone WILL be broken).

All existing push/reversal/BOS/CHoCH functionality is preserved.

---

## Zone UDT

```pine
type Zone
    float   top          = 0.0
    float   bottom       = 0.0
    bool    is_supply    = false
    int     origin_time  = 0
    box     bx
    bool    is_push      = false
    bool    is_reversal  = false
    string  struct_cls   = ""      // "BOS" or "CHoCH"
    string  swing_cls    = ""      // "HH", "LH", "HL", "LL"
    int     count_num    = 0       // zone count # within parent cycle (1-8+)
    bool    is_terminal  = false   // opposing nesting detected
```

- `count_num`: assigned at zone creation. Incremented per-side count since last parent TF same-side zone fire.
- `is_terminal`: set when opposing nesting is detected. Drives distinct visual styling.

Both fields are bidirectional — supply and demand tracked independently.

---

## Natural Parent-Child TF Mapping

Fixed mapping, no configuration needed:

| Child TF | Natural Parent TF |
|----------|------------------|
| M1 (`"1"`) | M15 (`"15"`) |
| M5 (`"5"`) | H1 (`"60"`) |
| M15 (`"15"`) | H1 (`"60"`) |
| H1 (`"60"`) | H4 (`"240"`) |
| H4 (`"240"`) | D (`"1D"`) |
| D (`"1D"`) | W (`"1W"`) |
| W (`"1W"`) | MN (`"1M"`) |
| MN (`"1M"`) | *(no parent)* |

**Edge case — parent TF disabled:** If the parent TF is not enabled in inputs, the child TF gets no counting and no nesting detection. Dashboard shows "—" for count columns. No guessing or skipping levels.

Helper function:
```pine
tf_parent(string tf) =>
    string out = tf == "1" ? "15" : tf == "5" ? "60" : tf == "15" ? "60" : tf == "60" ? "240" : tf == "240" ? "1D" : tf == "1D" ? "1W" : tf == "1W" ? "1M" : ""
    out
```

---

## Zone Counting Logic

### State per TF

```
var int sup_count = 0   // supply zones since last parent supply fire
var int dem_count = 0   // demand zones since last parent demand fire
```

Bidirectional — supply and demand counters are fully independent.

### Count reset

When the parent TF fires a new zone, reset the child's same-side counter:
- Parent H4 supply fires → reset H1 `sup_count` to 0
- Parent H4 demand fires → reset H1 `dem_count` to 0

Reset detection: `process()` receives `parent_fire` (bool) and `parent_is_sup` (bool) parameters. When `parent_fire` is true, reset the matching counter.

### Count increment

When a new child zone is created in `process()`:
- Supply zone → `sup_count += 1`, zone gets `count_num = sup_count`
- Demand zone → `dem_count += 1`, zone gets `count_num = dem_count`

**All zones count** — push, reversal, and normal zones all increment the counter. The 5+3 pattern tracks total structural pressure, not just push zones.

### Exhaustion markers

| Count | Meaning | Label marker |
|-------|---------|-------------|
| 1-4 | Impulse active | count number only |
| 5 | Impulse exhausted | `⚠` suffix |
| 6-7 | Correction zones (A, B) | count number only |
| 8 | Terminal exhaustion | `✕` suffix |

---

## Zone Nesting Detection

### When to check

After a new zone is created in `process()`, check if it's fully contained inside any zone in the parent TF's zone array.

### Containment rule

```
child.top ≤ parent.top  AND  child.bot ≥ parent.bot
```

Both edges must be inside. Partial overlap does not count as nesting.

### Direction classification

| Child | Inside Parent | Direction | Signal |
|-------|--------------|-----------|--------|
| Supply | Supply | Same | Continuation — stair-step, trend intact |
| Demand | Demand | Same | Continuation — stair-step, trend intact |
| Supply | Demand | **Opposing** | **Terminal — this child zone WILL be broken** |
| Demand | Supply | **Opposing** | **Terminal — this child zone WILL be broken** |

### Actions on detection

**Same-direction nesting:**
- Label appends parent context: `(in H4 S)` or `(in H4 S CHoCH)` if parent is a push zone
- No special styling — normal or push colors apply

**Opposing-direction nesting (terminal):**
- `is_terminal = true`
- Distinct color: muted purple/magenta (`#9C27B0`) at 92% fill, 30% border transparency
- Label includes terminal marker: `H1 S #8 ✕ (in H4 D)`
- This is the "this zone WILL be broken" signal from Rule 4

### Nesting search

Iterate the parent zone array. If multiple parent zones contain the child (overlapping parents), use the **smallest** parent (tightest fit = smallest `top - bottom`) — most specific context.

When no parent exists (MN, or parent TF disabled), pass an empty array — nesting check naturally finds nothing.

### Optional visual connectors

Input toggle: `Show Nesting Lines`, default `false`.

When enabled and nesting is detected: draw a `line` from the child zone's structural edge to the parent zone's nearest boundary. Simple vertical line, same color as the nesting relationship (parent color for continuation, terminal color for opposing).

---

## process() Signature

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time,
               string hi_txt, string lo_txt, float seq_hh_val, float seq_ll_val,
               int trend_val, string tf_str, float prev_push_hi, float prev_push_lo,
               array<Zone> parent_zones, bool parent_fire, bool parent_is_sup,
               int sup_count_in, int dem_count_in) =>
```

Returns expanded tuple:
```pine
    [new_push_hi, new_push_lo, new_sup_count, new_dem_count]
```

The counting state (`sup_count`, `dem_count`) is passed in and returned, same pattern as `prev_push_hi`/`prev_push_lo` in v1.

---

## Label Format

Labels combine TF, side, count, push/reversal status, structure classification, and nesting context.

### Normal zones (when visible via toggle)

```
H1 S #3
H1 D #2
```

### Push zones

```
H1 S #4 LL ▼ BOS
H4 D #1 HH ◆ CHoCH
```

### Reversal zones

```
H1 D #3 REV ⚐
```

### With nesting context (appended)

```
H1 S #3 (in H4 S)                    — continuation nesting
H1 S #5 LL ▼ BOS (in H4 S CHoCH)     — push zone nested in parent push
H1 S #8 ✕ (in H4 D)                  — terminal opposing nesting
```

### Exhaustion markers

- Count 5 gets `⚠` after the number
- Count 8 gets `✕` after the number (unless already terminal from nesting — no double marker)

### Unicode fallback

If TradingView doesn't render ▼ ▲ ◆ ⚐ ⚠ ✕, fall back to: `v`, `^`, `*`, `F`, `!`, `X`.

Labels remain `size.tiny`, right-aligned at top of zone box.

---

## Visual Styling

| Zone Type | Fill | Border | Width |
|-----------|------|--------|-------|
| Normal Supply | `#FF4444` @ 85% | `#FF4444` @ 20% | 1 |
| Normal Demand | `#2196F3` @ 85% | `#2196F3` @ 20% | 1 |
| Push Supply | `#FF4444` @ 92% | `#FF4444` @ 30% | 1 |
| Push Demand | `#2196F3` @ 92% | `#2196F3` @ 30% | 1 |
| Reversal | `#FFB300` @ 92% | `#FFB300` @ 30% | 1 |
| **Terminal** | **`#9C27B0` @ 92%** | **`#9C27B0` @ 30%** | **1** |

Normal zones hidden by default (toggle `Show Normal Zones`, default off).

---

## Dashboard

Compact table, one row per enabled TF:

| Column | Content | Source |
|--------|---------|--------|
| TF | Timeframe label | Static |
| Trend | BULL / BEAR / — | `track_period()` break direction |
| Push | Active push classification (e.g., `S LL ▼ BOS`) | Push zone state |
| #S | Supply count (e.g., `3`) | `sup_count` — yellow at 5, red at 8 |
| #D | Demand count (e.g., `7`) | `dem_count` — yellow at 5, red at 8 |
| Zones | Supply/demand total (e.g., `2S 1D`) | Zone array sizes |

---

## Execution Order (Critical)

**S9 must process TFs from highest to lowest:** MN → W → D → H4 → H1 → M15 → M5 → M1.

This ensures the parent TF's zone array is populated before the child TF checks nesting against it. V1 processes M1→MN (index 0→7); v2 reverses to index 7→0.

The `if i_tfN_on` gate blocks still apply — disabled TFs are skipped.

---

## Inputs

### New inputs (added to v1 inputs)

| Group | Input | Default |
|-------|-------|---------|
| Colors | Terminal Fill | `#9C27B0` @ 92% |
| Colors | Terminal Border | `#9C27B0` @ 30% |
| Colors | Show Nesting Lines | `false` |

All v1 inputs preserved unchanged.

---

## Data Flow Summary

```
request.security() x8          track_period() x8
    │                               │
    ▼                               ▼
ha_detect() ──► zone fire    prev hi/lo + break times
    │                               │
    ▼                               ▼
edge-detect ──► new HH/LL   edge-detect ──► BOS/CHoCH
    │                               │
    └───────────┬───────────────────┘
                ▼
    process() per TF (HIGH → LOW order):
    1. Count reset (if parent fired same-side zone)
    2. Expire + break check (body close)
    3. Create new zone (with count_num assigned)
    4. Nesting check (against parent zone array)
    5. Terminal detection (opposing nesting)
    6. Push validation (boundary-break rule)
    7. Reversal zone tagging
    8. BOS/CHoCH classification
    9. Visual styling + labels (combining all classifications)
```

---

## File Structure

Single file: `tw_indicators/iora_zones/iora_push_zones_v2.pine`

| Section | Content |
|---------|---------|
| S1 | Inputs (v1 + terminal color, nesting lines toggle) |
| S2 | Types (Zone UDT with count_num, is_terminal) |
| S3 | Helpers (`tf_max_age`, `tf_label`, `tf_parent`) |
| S4 | `ha_detect()` — zone detection (unchanged) |
| S5 | `track_period()` — structure tracking (unchanged) |
| S6 | Zone management (`process` with counting + nesting + push/reversal/BOS-CHoCH) |
| S7 | Data requests (8 `request.security()` calls) |
| S8 | Edge detection (zone fires + HH/LL + structure breaks + trend) |
| S9 | Zone arrays + execution (8 TFs, HIGH→LOW order, with parent array wiring) |
| S10 | Dashboard (with #S, #D columns) |

Estimated ~650-700 lines.

---

## Pine v6 Rules (from CLAUDE.md)

- `//@version=6` always
- All variables explicitly typed
- No multiline ternaries
- No reserved keywords as variable names
- `request.security()` max 40 — this indicator uses 8
- Timeframe strings: `"1"`, `"5"`, `"15"`, `"60"`, `"240"`, `"1D"`, `"1W"`, `"1M"`
- Field assignment on `.get()` — store in local variable first
- Broken zones deleted immediately — no ghost styling
- Body-close break rule for zone breaks
- Wick or body exceedance for push validation (boundary-break rule)
