# Iora Nested Zones — Indicator Spec

> File: `iora_nested_zones.pine`
> Pine Script v6 | Overlay indicator
> Limits: 100 boxes, 100 labels, 5000 calc bars

---

## Purpose

Detects when a **grandchild TF zone** forms geometrically inside a **parent TF zone** of the same type (supply inside supply, demand inside demand). This confirms the push direction — the grandchild zone is where the new parent-level leg originates.

Example: H4 supply exists. Price pulls back on H1. M15 supply forms inside the H4 supply. That M15 supply is the confirmed push zone — sellers are reasserting at the parent level. The indicator persists this M15 zone on the chart as a high-probability entry area.

**Same logic works bidirectionally**: M15 demand inside H4 demand confirms bullish push.

---

## TF Pairing — Skip-One-Level Auto-Assignment

The user selects a parent TF. The grandchild is auto-determined by skipping one level in the cascade:

| Parent | Child (skipped) | Grandchild |
|--------|----------------|------------|
| MN     | W              | D          |
| W      | D              | H4         |
| D      | H4             | H1         |
| H4     | H1             | M15        |
| H1     | M15            | M5         |
| M15    | M5             | M1         |

The "child" layer is the intermediate TF where the push/pullback cycle plays out. The grandchild zone forming inside the parent confirms the next push.

Up to **3 pairs** active simultaneously (6 `request.security()` calls max).

---

## Architecture (9 sections)

### S1 — Types

```
type ParentZone
    float   top         = 0.0      // OHLC extreme of the completed run
    float   bottom      = 0.0      // HA order-block edge
    bool    is_supply   = false    // true = supply, false = demand
    int     origin_time = 0        // when the zone fired
    bool    is_broken   = true     // body-close break tracking (default true = uninitialized, prevents matching)
```

Tracks the **most recent unbroken** supply AND demand per parent TF. When a new parent zone of the same type fires, it replaces the previous one and sets `is_broken = false`. When price body-closes through it, `is_broken` flips back to true. Default `is_broken = true` ensures uninitialized parent zones (top=0, bottom=0) cannot match grandchild zones.

```
type ConfirmedZone
    float   top         = na       // grandchild zone top
    float   bottom      = na       // grandchild zone bottom
    bool    is_supply   = false    // zone type (matches parent)
    int     origin_time = na       // grandchild zone origin time
    string  pair_label  = ""       // e.g. "M15 ▶ H4"
    box     bx          = na       // rendered box
    label   lbl         = na       // rendered label
    float   parent_top  = na       // parent zone top at confirmation time
    float   parent_bot  = na       // parent zone bottom at confirmation time
```

Persisted confirmed zones go into an `array<ConfirmedZone>`. Removed on body-close break OR parent zone break.

### S2 — Inputs

**Pairs** (3 max):

| Input | Type | Default | Group |
|-------|------|---------|-------|
| Pair 1 enabled | `input.bool` | `true` | Pairs |
| Pair 1 parent TF | `input.string` | `"1D"` | Pairs |
| Pair 2 enabled | `input.bool` | `true` | Pairs |
| Pair 2 parent TF | `input.string` | `"240"` (H4) | Pairs |
| Pair 3 enabled | `input.bool` | `false` | Pairs |
| Pair 3 parent TF | `input.string` | `"60"` (H1) | Pairs |

**Colors**:

| Input | Default | Group |
|-------|---------|-------|
| Pair 1 color | `#FFFFFF` (white) | Colors |
| Pair 2 color | `#26C6DA` (cyan) | Colors |
| Pair 3 color | `#FF6D00` (orange) | Colors |

**Style**:

| Input | Default | Group |
|-------|---------|-------|
| Doji Body % | `5.0` | Style |
| Max Confirmed Zones | `20` | Style |

Parent TF dropdown options: `["1M", "1W", "1D", "240", "60", "15"]` — M1 cannot be a parent (no grandchild below it), and M5 is excluded since M1 is the lowest TF we support.

### S3 — Helpers

**`tf_label(string tf)`** — converts Pine TF strings to display labels. Same as `iora_structure_trendlines.pine`.

**`grandchild_tf(string parent_tf)`** — auto-pairing lookup:

```
grandchild_tf(string parent_tf) =>
    switch parent_tf
        "1M"  => "1D"
        "1W"  => "240"
        "1D"  => "60"
        "240" => "15"
        "60"  => "5"
        "15"  => "1"
        => na
```

**Chart TF guard**: Both parent and grandchild must be strictly higher than chart TF. Uses `timeframe.in_seconds()` comparison.

### S4 — Zone Detection (`detect_zones()`)

Lightweight function for `request.security()`. Returns 4 values per TF. Uses the **same HA calculation, doji handling, and backward-scan for run extremes** as `ha_detect()` in `iora_zones.pine`, ensuring zones detected here align exactly with zones shown by that indicator.

**Output pattern differs from `ha_detect()`**: instead of returning a `fire` boolean + non-persistent values (as `ha_detect()` does), this function uses `var` persistence to produce a **step-function** output — values change only on transitions and stay constant between them. This enables clean edge detection in S6 (same pattern as `iora_structure_trendlines.pine`). Do not attempt to reuse `ha_detect()` directly — the output pattern is intentionally different.

```
detect_zones(float doji_pct) =>
    // HA calculation from OHLC (matches iora_zones.pine)
    float haC = (open + high + low + close) / 4.0
    float haO = float(na)
    haO := na(haO[1]) ? (open + close) / 2.0 : (nz(haO[1]) + nz(haC[1])) / 2.0
    float haH = math.max(high, math.max(haO, haC))
    float haL = math.min(low, math.min(haO, haC))

    // Color detection — no var persistence, computed fresh each bar
    bool is_blue = haC >= haO
    bool is_red  = haC < haO

    int max_run = math.min(50, bar_index)

    // Persistent step-function outputs
    var float last_ztop   = na
    var float last_zbot   = na
    var int   last_is_sup = 0    // 1 = supply, -1 = demand
    var int   last_origin = na

    // DEMAND: red → blue (red run completed)
    if is_blue and is_red[1]
        float run_lo_ohlc = low[1]
        int   ext_time    = time[1]
        int   k           = 2
        while k < max_run and is_red[k]
            if low[k] < run_lo_ohlc
                run_lo_ohlc := low[k]
                ext_time    := time[k]
            k += 1

        // Doji check on transition candle (HA range, not OHLC)
        float body = math.abs(haC - haO)
        float rng  = haH - haL
        bool  doji = rng > 0.0 and (body / rng * 100.0) < doji_pct

        last_ztop   := doji ? nz(haH, high) : nz(haH[1], high[1])
        last_zbot   := nz(run_lo_ohlc, low[1])
        last_is_sup := -1
        last_origin := nz(ext_time, time[1])

    // SUPPLY: blue → red (blue run completed)
    else if is_red and is_blue[1]
        float run_hi_ohlc = high[1]
        int   ext_time    = time[1]
        int   k           = 2
        while k < max_run and is_blue[k]
            if high[k] > run_hi_ohlc
                run_hi_ohlc := high[k]
                ext_time    := time[k]
            k += 1

        float body = math.abs(haC - haO)
        float rng  = haH - haL
        bool  doji = rng > 0.0 and (body / rng * 100.0) < doji_pct

        last_ztop   := nz(run_hi_ohlc, high[1])
        last_zbot   := doji ? nz(haL, low) : nz(haL[1], low[1])
        last_is_sup := 1
        last_origin := nz(ext_time, time[1])

    [last_ztop, last_zbot, last_is_sup, last_origin]
```

**Key alignment decisions (matching `iora_zones.pine`):**
- `doji_pct` passed as parameter (not captured global)
- `float haO = float(na)` — explicit typing
- `is_blue`/`is_red` computed fresh each bar (no `var` persistence)
- Doji range uses `haH - haL` (HA range), not `high - low` (OHLC range)
- Doji adjusts zone boundary (current vs previous candle HA extreme), not color state
- Backward scan (`while k < max_run`) for run extremes, matching established pattern
- `last_is_sup` uses `int` (1/-1) for clean security tuple return

### S5 — Data Requests

Up to 6 `request.security()` calls (2 per active pair):

```
// Pair 1: parent + grandchild
[p1_zt, p1_zb, p1_sup, p1_tm] = request.security(ticker.standard(syminfo.tickerid), pair1_parent_tf, detect_zones(i_doji_pct))
[g1_zt, g1_zb, g1_sup, g1_tm] = request.security(ticker.standard(syminfo.tickerid), pair1_gc_tf, detect_zones(i_doji_pct))
```

No `lookahead` or `gaps` parameters — matches the existing `iora_zones.pine` and `iora_structure.pine` call signatures (Pine defaults: `lookahead_off`, `gaps_off`). This ensures zone detection timing aligns exactly with the other indicators.

All 6 calls are always issued (Pine v6 requires `request.security()` at top level — no conditional calls). Pairs that are disabled or fail the chart TF guard simply don't process results.

### S6 — Edge Detection

Same step-function pattern as `iora_structure_trendlines.pine`:

```
bool p1_new = not na(p1_zt) and (na(p1_zt[1]) or p1_zt != p1_zt[1] or p1_zb != p1_zb[1])
```

A zone event fires when the top OR bottom changes (both change simultaneously on a real transition, but checking both covers edge cases). The edge boolean gates values into `_edge` variables.

### S7 — Nesting Engine

Per active pair, per bar:

**Step 1 — Update parent zones on edge detection:**

```
if parent_zone_edge_fired
    if is_supply
        parent_supply.top    := ztop
        parent_supply.bottom := zbot
        parent_supply.origin := origin_time
        parent_supply.is_broken := false
    else
        parent_demand.top    := ztop
        parent_demand.bottom := zbot
        parent_demand.origin := origin_time
        parent_demand.is_broken := false
```

**Step 2 — Check grandchild containment on grandchild edge detection:**

```
if grandchild_zone_edge_fired
    if grandchild_is_supply and not parent_supply.is_broken
        // Containment test: grandchild fits entirely within parent
        if gc_top <= parent_supply.top and gc_bot >= parent_supply.bottom
            → CREATE CONFIRMED ZONE
    else if grandchild_is_demand and not parent_demand.is_broken
        if gc_top <= parent_demand.top and gc_bot >= parent_demand.bottom
            → CREATE CONFIRMED ZONE
```

**Containment is strict**: the grandchild zone must fit entirely within the parent zone. Partial overlap does not count.

### S8 — Break Management

**On every bar, for each active pair:**

1. **Parent zone break check:**
   - Supply: `close > parent_supply.top` → mark broken, cascade to confirmed zones
   - Demand: `close < parent_demand.bottom` → mark broken, cascade to confirmed zones
   - Cascade: iterate `array<ConfirmedZone>`, any confirmed zone whose `parent_top` and `parent_bot` match the broken parent → delete box/label, remove from array

2. **Confirmed zone break check:**
   - Supply confirmed: `close > zone.top` → zone consumed, delete box/label, remove from array
   - Demand confirmed: `close < zone.bottom` → zone consumed, delete box/label, remove from array

3. **Max count enforcement:**
   - If `confirmed_zones.size() > max_confirmed`, remove oldest entries first (FIFO)

**Deletion is immediate** — no ghost styling, no broken-zone persistence. Matches your existing policy.

### S9 — State & Execution

Per pair, `var` state:

```
var ParentZone p1_sup = ParentZone.new()
var ParentZone p1_dem = ParentZone.new()
var array<ConfirmedZone> confirmed = array.new<ConfirmedZone>()
```

One `confirmed` array shared across all pairs. Each `ConfirmedZone` carries its `pair_label` so the pair context is preserved.

Main execution loop:
1. Edge detection (all 6 TFs)
2. Parent zone updates (3 pairs × 2 types)
3. Parent break checks (3 pairs × 2 types)
4. Grandchild containment checks (3 pairs)
5. Confirmed zone break checks (iterate array)
6. Box right-extension for surviving confirmed zones

---

## Visual Treatment

**Confirmed zone box:**
- Solid border, pair color, width 2
- Fill: pair color at 85% transparency
- Extends right every bar until removed
- `xloc = xloc.bar_time`

**Label:**
- `label.style_none` (text only)
- Positioned at right edge of zone, vertically centered
- Format: `"M15 ▶ H4 ↘ S"` or `"H1 ▶ D ↗ D"`
  - Grandchild TF ▶ Parent TF
  - ↘ for supply (bearish push), ↗ for demand (bullish push)
  - S/D for supply/demand
- Text color = pair color, `size.small`

**No visual treatment on parent zones.** This indicator only draws confirmed grandchild zones. Parent zones are visible via `iora_zones.pine` if loaded.

---

## Removal Rules

A confirmed zone is removed when **either** condition fires (whichever comes first):

1. **Body-close break**: `close > zone.top` (supply) or `close < zone.bottom` (demand)
2. **Parent invalidation**: the parent zone that contained the grandchild gets body-close broken

Removal = immediate deletion of box + label + array entry.

---

## Security Call Budget

| Calls | Purpose |
|-------|---------|
| 2 | Pair 1 (parent + grandchild) |
| 2 | Pair 2 (parent + grandchild) |
| 2 | Pair 3 (parent + grandchild) |
| **6** | **Total** (well under 40-call limit) |

All 6 calls are always issued (Pine v6 requirement). Pairs that are disabled or fail the chart TF guard simply don't process results.

---

## Relationship to Other Iora Indicators

| Indicator | What It Detects | What This Indicator Adds |
|-----------|----------------|-------------------------|
| `iora_zones.pine` | Zone creation + classification (HH/LH/HL/LL) | - |
| `iora_structure.pine` | BOS/CHoCH + breakers + persisted zones | - |
| `iora_structure_trendlines.pine` | Trendlines through zone-confirmed swings | - |
| **`iora_nested_zones.pine`** (this) | Grandchild zone inside parent zone | Persisted high-probability entry zones |

This indicator uses the same HA transition logic as the others but is fully standalone. It does not depend on any other indicator being loaded.

---

## Default Configuration

| Setting | Value |
|---------|-------|
| Pair 1 | D parent → H1 grandchild (white) |
| Pair 2 | H4 parent → M15 grandchild (cyan) |
| Pair 3 | off |
| Doji % | 5.0 |
| Max confirmed zones | 20 |
