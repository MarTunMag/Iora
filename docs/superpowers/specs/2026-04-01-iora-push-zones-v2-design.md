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

### Two kinds of count

1. **Creation count** (`count_num` on Zone UDT) — monotonic sequence number assigned at zone creation. Tracks the zone's position in the push cycle. Never changes after assignment. Used in zone labels (`#3`, `#5`).
2. **Unbroken count** (computed dynamically) — current number of live, unbroken same-side zones created since the last reset. Used for exhaustion evaluation in the dashboard and for exhaustion markers. Computed by filtering the zone array: count zones where `is_supply` matches and `origin_time >= last_reset_time`.

The creation count and unbroken count may differ when zones are broken/deleted mid-cycle. A zone labeled `#5` might be the 3rd unbroken zone if two earlier ones were broken. The label reflects creation order (structural context); the dashboard reflects current pressure (exhaustion state).

### State per TF

```
var int sup_count = 0       // creation counter for supply zones
var int dem_count = 0       // creation counter for demand zones
var int sup_reset_time = 0  // timestamp of last supply count reset
var int dem_reset_time = 0  // timestamp of last demand count reset
```

Bidirectional — supply and demand counters are fully independent.

### Count reset (two triggers)

**Trigger 1 — Parent TF fires same-side zone:**
- Parent H4 supply fires → reset H1 `sup_count` to 0, update `sup_reset_time`
- Parent H4 demand fires → reset H1 `dem_count` to 0, update `dem_reset_time`

**Trigger 2 — Same-TF structural invalidation (from Rule 3):**
- H1 makes new HH (bullish break) → reset H1 `sup_count` to 0 (bearish structure invalidated)
- H1 makes new LL (bearish break) → reset H1 `dem_count` to 0 (bullish structure invalidated)

HH/LL detection uses the existing `hi_txt == "HH"` / `lo_txt == "LL"` from `ha_detect()`, guarded by `is_sup` direction check (same guards as push validation).

Reset detection: `process()` receives `parent_fire` (bool) and `parent_is_sup` (bool) parameters for trigger 1. Trigger 2 uses the existing fire + hi_txt/lo_txt already passed to `process()`.

### Count increment

When a new child zone is created in `process()`:
- Supply zone → `sup_count += 1`, zone gets `count_num = sup_count`
- Demand zone → `dem_count += 1`, zone gets `count_num = dem_count`

**All zones count** — push, reversal, and normal zones all increment the counter. The 5+3 pattern tracks total structural pressure, not just push zones.

### Exhaustion evaluation

Exhaustion is evaluated using the **unbroken count** (dynamic), not the creation count:
- Compute: count zones in array where `is_supply` matches the side and `origin_time >= reset_time`
- Dashboard #S/#D columns show this unbroken count
- Dashboard cell color: white (1-4), yellow (5), red (8+)

### Exhaustion markers in labels

Labels use the **creation count** (`count_num`) for the number, with exhaustion markers based on the number itself:

| count_num | Meaning | Label marker |
|-----------|---------|-------------|
| 1-4 | Impulse active | count number only |
| 5 | Impulse exhausted | `⚠` suffix |
| 6-7 | Correction zones (A, B) | count number only |
| 8 | Terminal exhaustion | `✕` suffix |

Note: count-8 exhaustion marker (`✕`) and opposing-nesting terminal marker (`✕`) intentionally share the same symbol. At count 8, zones are typically the ones that end up opposing-nested — the convergence is meaningful, reinforcing the terminal signal.

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

### Skip filter (deferred)

Rule 4 includes a skip filter: "IF parent zone overlaps an opposing zone → weak signal, skip." This filter checks whether the parent zone is clean (no overlapping opposite-side zone eating into it). This is deferred to a future iteration — v2 fires nesting signals regardless of parent zone cleanliness. The rationale: the skip filter requires cross-checking the parent TF's zone array for opposing overlaps, adding complexity. The terminal signal without the filter is still directionally correct; the filter would improve signal quality but is not essential for the first working version.

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
               int sup_count_in, int dem_count_in,
               int sup_reset_time_in, int dem_reset_time_in) =>
```

Returns expanded tuple:
```pine
    [new_push_hi, new_push_lo, new_sup_count, new_dem_count, new_sup_reset_time, new_dem_reset_time]
```

The counting state (`sup_count`, `dem_count`, reset times) is passed in and returned, same pattern as `prev_push_hi`/`prev_push_lo` in v1.

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

**Note:** Push zone transparency (92% fill, 30% border, width 1) reflects the v1 values as iterated through user visual feedback. The v1 design spec originally specified 70%/0%/2, but the implementation was adjusted through multiple rounds of chart review. V2 preserves the user-approved values.

---

## Dashboard

Compact table with **6 columns** (`table.new()` must specify 6), one row per enabled TF:

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

### Parent wiring in S9

Each child TF's `process()` call receives the parent TF's zone array, fire signal, and fire side. The parent fire signal (`fN`) and side (`sN`) come from the same `request.security()` + edge detection already computed in S7/S8.

Example wiring for H1 (index 3, parent = H4, index 4):

```pine
if i_tf3_on
    // Parent = H4 (index 4). If H4 disabled, no counting/nesting.
    array<Zone> p3 = i_tf4_on ? zones4 : array.new<Zone>()
    bool pf3 = i_tf4_on ? f4 : false
    bool ps3 = i_tf4_on ? s4 : false
    [nph3, npl3, nsc3, ndc3, nsrt3, ndrt3] = zones3.process(f3, zt3, zb3, s3, tm3, h1s3, l1s3, hh3, ll3, trend3, i_tf3, ph3, pl3, p3, pf3, ps3, sc3, dc3, srt3, drt3)
    ph3 := nph3, pl3 := npl3, sc3 := nsc3, dc3 := ndc3, srt3 := nsrt3, drt3 := ndrt3
```

Full parent mapping for all 8 TFs:

| TF Index | TF | Parent Index | Parent TF | Parent zones | Parent fire | Parent side |
|----------|----|-------------|-----------|-------------|-------------|-------------|
| 7 | MN | — | none | empty array | false | false |
| 6 | W | 7 | MN | zones7 | f7 | s7 |
| 5 | D | 6 | W | zones6 | f6 | s6 |
| 4 | H4 | 5 | D | zones5 | f5 | s5 |
| 3 | H1 | 4 | H4 | zones4 | f4 | s4 |
| 2 | M15 | 3 | H1 | zones3 | f3 | s3 |
| 1 | M5 | 3 | H1 | zones3 | f3 | s3 |
| 0 | M1 | 2 | M15 | zones2 | f2 | s2 |

Note: M5 and M15 share the same parent (H1, index 3). This is correct per the natural mapping.

---

## Inputs

### New inputs (added to v1 inputs)

| Group | Input | Default |
|-------|-------|---------|
| Colors | Terminal Fill | `#9C27B0` @ 92% |
| Colors | Terminal Border | `#9C27B0` @ 30% |
| Display | Show Nesting Lines | `false` |

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
    1. Count reset (if parent fired same-side zone, or same-TF HH/LL)
    2. Expire + break check (body close)
    3. Create new zone (with count_num assigned)
    4. Push validation (boundary-break rule)
    5. Reversal zone tagging
    6. BOS/CHoCH classification
    7. Nesting check (against parent zone array)
    8. Terminal detection (opposing nesting)
    9. Label rendering (final pass — combines count, push/rev, BOS/CHoCH, nesting)
    10. Visual styling (colors/borders based on final classification)
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
