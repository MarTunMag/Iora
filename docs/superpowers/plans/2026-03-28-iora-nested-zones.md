# Iora Nested Zones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Pine Script v6 indicator that detects grandchild TF zones forming inside parent TF zones of the same type, persisting them as high-probability entry areas.

**Architecture:** Single-file Pine Script indicator (`iora_nested_zones.pine`) with 9 sections matching the existing Iora convention (S1-S9). Zone detection reuses the same HA transition + backward-scan logic as `iora_zones.pine` but with step-function outputs for edge detection. Up to 3 configurable parent-grandchild TF pairs, 6 `request.security()` calls.

**Tech Stack:** Pine Script v6, TradingView

**Spec:** `docs/superpowers/specs/2026-03-28-iora-nested-zones-design.md`

**Reference files:**
- `tw_indicators/system/iora_zones.pine` — zone detection pattern (`ha_detect()`)
- `tw_indicators/iora_structure_trendlines.pine` — step-function + edge detection pattern
- `CLAUDE.md` — Pine v6 rules (explicit typing, no reserved keywords, timeframe strings, etc.)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `tw_indicators/system/iora_nested_zones.pine` | Create | The complete indicator |

Single file — Pine Script indicators are self-contained. No tests (Pine has no test framework; validation is done in TradingView Replay).

---

### Task 1: Scaffold — indicator declaration, UDTs, inputs (S1-S2)

**Files:**
- Create: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Create file with indicator declaration and S1 Types**

```pine
//@version=6
indicator("Iora Nested Zones", overlay = true, max_boxes_count = 100, max_labels_count = 100, calc_bars_count = 5000)

// =============================================================================
// S1 — TYPES
// =============================================================================

type ParentZone
    float   top         = 0.0
    float   bottom      = 0.0
    bool    is_supply   = false
    int     origin_time = 0
    bool    is_broken   = true

type ConfirmedZone
    float   top         = na
    float   bottom      = na
    bool    is_supply   = false
    int     origin_time = na
    string  pair_label  = ""
    box     bx          = na
    label   lbl         = na
    float   parent_top  = na
    float   parent_bot  = na
```

- [ ] **Step 2: Add S2 Inputs**

```pine
// =============================================================================
// S2 — INPUTS
// =============================================================================

string GRP_PAIR = "Pairs"
bool   i_p1_on  = input.bool(true,  "Pair 1",    group = GRP_PAIR, inline = "p1")
string i_p1_tf  = input.string("1D", "",          group = GRP_PAIR, inline = "p1", options = ["1M", "1W", "1D", "240", "60", "15"])
bool   i_p2_on  = input.bool(true,  "Pair 2",    group = GRP_PAIR, inline = "p2")
string i_p2_tf  = input.string("240", "",         group = GRP_PAIR, inline = "p2", options = ["1M", "1W", "1D", "240", "60", "15"])
bool   i_p3_on  = input.bool(false, "Pair 3",    group = GRP_PAIR, inline = "p3")
string i_p3_tf  = input.string("60", "",          group = GRP_PAIR, inline = "p3", options = ["1M", "1W", "1D", "240", "60", "15"])

string GRP_CLR = "Colors"
color  i_p1_clr = input.color(#FFFFFF, "Pair 1",  group = GRP_CLR)
color  i_p2_clr = input.color(#26C6DA, "Pair 2",  group = GRP_CLR)
color  i_p3_clr = input.color(#FF6D00, "Pair 3",  group = GRP_CLR)

string GRP_STY = "Style"
float  i_doji_pct  = input.float(5.0, "Doji Body %",        group = GRP_STY, minval = 0.1, maxval = 50.0)
int    i_max_zones = input.int(20,    "Max Confirmed Zones", group = GRP_STY, minval = 1, maxval = 50)
```

- [ ] **Step 3: Verify the file compiles**

Open in TradingView Pine Editor → Add to chart. Expected: compiles with no errors, empty overlay (no output yet).

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): scaffold indicator with UDTs and inputs (S1-S2)"
```

---

### Task 2: Helpers and zone detection function (S3-S4)

**Files:**
- Modify: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Add S3 Helpers**

```pine
// =============================================================================
// S3 — HELPERS
// =============================================================================

tf_label(string tf) =>
    switch tf
        "1M"  => "MN"
        "1W"  => "W"
        "1D"  => "D"
        "240" => "H4"
        "60"  => "H1"
        "15"  => "M15"
        "5"   => "M5"
        "1"   => "M1"
        => tf

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

- [ ] **Step 2: Resolve grandchild TF strings for all 3 pairs**

Add after helpers, before S4:

```pine
string p1_gc_tf = grandchild_tf(i_p1_tf)
string p2_gc_tf = grandchild_tf(i_p2_tf)
string p3_gc_tf = grandchild_tf(i_p3_tf)
```

- [ ] **Step 3: Add chart TF guard**

```pine
int chart_s = timeframe.in_seconds()

bool p1_ok = i_p1_on and timeframe.in_seconds(i_p1_tf) > chart_s and (not na(p1_gc_tf) ? timeframe.in_seconds(p1_gc_tf) > chart_s : false)
bool p2_ok = i_p2_on and timeframe.in_seconds(i_p2_tf) > chart_s and (not na(p2_gc_tf) ? timeframe.in_seconds(p2_gc_tf) > chart_s : false)
bool p3_ok = i_p3_on and timeframe.in_seconds(i_p3_tf) > chart_s and (not na(p3_gc_tf) ? timeframe.in_seconds(p3_gc_tf) > chart_s : false)
```

- [ ] **Step 4: Add S4 zone detection function**

This is the core zone detection matching `iora_zones.pine` HA logic with step-function output. Copy the `detect_zones()` function exactly as specified in the spec (S4 section). Key points:
- `float haO = float(na)` — explicit typing
- `is_blue`/`is_red` computed fresh each bar (no `var`)
- Doji range uses `haH - haL` (HA range)
- Backward scan with `while k < max_run`
- `var` persistence on outputs only (`last_ztop`, `last_zbot`, `last_is_sup`, `last_origin`)
- Returns `[last_ztop, last_zbot, last_is_sup, last_origin]`

```pine
// =============================================================================
// S4 — ZONE DETECTION
// =============================================================================

detect_zones(float doji_pct) =>
    float haC = (open + high + low + close) / 4.0
    float haO = float(na)
    haO := na(haO[1]) ? (open + close) / 2.0 : (nz(haO[1]) + nz(haC[1])) / 2.0
    float haH = math.max(high, math.max(haO, haC))
    float haL = math.min(low, math.min(haO, haC))

    bool is_blue = haC >= haO
    bool is_red  = haC < haO

    int max_run = math.min(50, bar_index)

    var float last_ztop   = na
    var float last_zbot   = na
    var int   last_is_sup = 0
    var int   last_origin = na

    if is_blue and is_red[1]
        float run_lo_ohlc = low[1]
        int   ext_time    = time[1]
        int   k           = 2
        while k < max_run and is_red[k]
            if low[k] < run_lo_ohlc
                run_lo_ohlc := low[k]
                ext_time    := time[k]
            k += 1

        float body = math.abs(haC - haO)
        float rng  = haH - haL
        bool  doji = rng > 0.0 and (body / rng * 100.0) < doji_pct

        last_ztop   := doji ? nz(haH, high) : nz(haH[1], high[1])
        last_zbot   := nz(run_lo_ohlc, low[1])
        last_is_sup := -1
        last_origin := nz(ext_time, time[1])

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

- [ ] **Step 5: Verify compiles**

Open in TradingView Pine Editor → Save. Expected: compiles with no errors.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): add helpers and zone detection function (S3-S4)"
```

---

### Task 3: Data requests and edge detection (S5-S6)

**Files:**
- Modify: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Add S5 data requests**

Add the base symbol and 6 `request.security()` calls. All 6 are always issued (Pine v6 requirement). Use `ticker.standard(syminfo.tickerid)` matching `iora_zones.pine`. No `lookahead` or `gaps` parameters.

```pine
// =============================================================================
// S5 — DATA REQUESTS
// =============================================================================

string _base_sym = ticker.standard(syminfo.tickerid)

[p1_zt, p1_zb, p1_sup, p1_tm] = request.security(_base_sym, i_p1_tf,  detect_zones(i_doji_pct))
[g1_zt, g1_zb, g1_sup, g1_tm] = request.security(_base_sym, na(p1_gc_tf) ? "1" : p1_gc_tf,  detect_zones(i_doji_pct))
[p2_zt, p2_zb, p2_sup, p2_tm] = request.security(_base_sym, i_p2_tf,  detect_zones(i_doji_pct))
[g2_zt, g2_zb, g2_sup, g2_tm] = request.security(_base_sym, na(p2_gc_tf) ? "1" : p2_gc_tf,  detect_zones(i_doji_pct))
[p3_zt, p3_zb, p3_sup, p3_tm] = request.security(_base_sym, i_p3_tf,  detect_zones(i_doji_pct))
[g3_zt, g3_zb, g3_sup, g3_tm] = request.security(_base_sym, na(p3_gc_tf) ? "1" : p3_gc_tf,  detect_zones(i_doji_pct))
```

**Note on `na` TF handling:** `request.security()` requires a `simple string` TF — it cannot be `na`. If `grandchild_tf()` returns `na` (invalid parent), use `"1"` as a fallback TF. The `p*_ok` guard ensures results from invalid pairs are never processed.

- [ ] **Step 2: Add S6 edge detection**

Edge detection for all 6 TF streams (3 parents + 3 grandchildren). A new zone event fires when top OR bottom changes from the previous bar.

```pine
// =============================================================================
// S6 — EDGE DETECTION
// =============================================================================

bool p1_new = not na(p1_zt) and (na(p1_zt[1]) or p1_zt != p1_zt[1] or p1_zb != p1_zb[1])
bool g1_new = not na(g1_zt) and (na(g1_zt[1]) or g1_zt != g1_zt[1] or g1_zb != g1_zb[1])
bool p2_new = not na(p2_zt) and (na(p2_zt[1]) or p2_zt != p2_zt[1] or p2_zb != p2_zb[1])
bool g2_new = not na(g2_zt) and (na(g2_zt[1]) or g2_zt != g2_zt[1] or g2_zb != g2_zb[1])
bool p3_new = not na(p3_zt) and (na(p3_zt[1]) or p3_zt != p3_zt[1] or p3_zb != p3_zb[1])
bool g3_new = not na(g3_zt) and (na(g3_zt[1]) or g3_zt != g3_zt[1] or g3_zb != g3_zb[1])
```

- [ ] **Step 3: Verify compiles**

Expected: compiles, still no visual output.

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): add data requests and edge detection (S5-S6)"
```

---

### Task 4: Nesting engine — parent tracking + containment check (S7)

**Files:**
- Modify: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Add S9 state instances (needed before S7 logic)**

Declare the `var` state for all 3 pairs and the shared confirmed array. Place this after S6.

```pine
// =============================================================================
// S9 — STATE
// =============================================================================

var ParentZone p1_sup_z = ParentZone.new()
var ParentZone p1_dem_z = ParentZone.new()
var ParentZone p2_sup_z = ParentZone.new()
var ParentZone p2_dem_z = ParentZone.new()
var ParentZone p3_sup_z = ParentZone.new()
var ParentZone p3_dem_z = ParentZone.new()
var array<ConfirmedZone> confirmed = array.new<ConfirmedZone>()
```

- [ ] **Step 2: Add S7 nesting engine — helper method for parent update**

Create a method on `ParentZone` to update it when a new zone of the matching type fires:

```pine
// =============================================================================
// S7 — NESTING ENGINE
// =============================================================================

method update_parent(ParentZone pz, float ztop, float zbot, int origin) =>
    pz.top         := ztop
    pz.bottom      := zbot
    pz.origin_time := origin
    pz.is_broken   := false
```

- [ ] **Step 3: Add helper function to create a confirmed zone**

```pine
create_confirmed(float ztop, float zbot, bool is_sup, int origin, string pair_lbl, color clr, float p_top, float p_bot, array<ConfirmedZone> arr, int max_z) =>
    string gc_tf_lbl  = str.substring(pair_lbl, 0, str.pos(pair_lbl, " "))
    string arrow      = is_sup ? " ↘ S" : " ↗ D"
    string full_label = pair_lbl + arrow
    float  mid_price  = (ztop + zbot) / 2.0
    box    bx  = box.new(time, ztop, time, zbot, xloc = xloc.bar_time, border_color = clr, border_width = 2, border_style = line.style_solid, bgcolor = color.new(clr, 85))
    label  lbl = label.new(time, mid_price, full_label, xloc = xloc.bar_time, style = label.style_none, textcolor = clr, size = size.small)
    ConfirmedZone cz = ConfirmedZone.new(ztop, zbot, is_sup, origin, pair_lbl, bx, lbl, p_top, p_bot)
    arr.push(cz)
    if arr.size() > max_z
        ConfirmedZone old = arr.shift()
        if not na(old.bx)
            box.delete(old.bx)
        if not na(old.lbl)
            label.delete(old.lbl)
```

- [ ] **Step 4: Add per-pair nesting logic**

For each active pair: update parents on parent edge, check grandchild containment on grandchild edge.

```pine
// --- Pair 1 ---
if p1_ok
    if p1_new
        if p1_sup > 0
            p1_sup_z.update_parent(p1_zt, p1_zb, p1_tm)
        else if p1_sup < 0
            p1_dem_z.update_parent(p1_zt, p1_zb, p1_tm)
    if g1_new
        bool gc_is_sup = g1_sup > 0
        bool gc_is_dem = g1_sup < 0
        if gc_is_sup and not p1_sup_z.is_broken
            if g1_zt <= p1_sup_z.top and g1_zb >= p1_sup_z.bottom
                string lbl = tf_label(p1_gc_tf) + " ▶ " + tf_label(i_p1_tf)
                create_confirmed(g1_zt, g1_zb, true, g1_tm, lbl, i_p1_clr, p1_sup_z.top, p1_sup_z.bottom, confirmed, i_max_zones)
        if gc_is_dem and not p1_dem_z.is_broken
            if g1_zt <= p1_dem_z.top and g1_zb >= p1_dem_z.bottom
                string lbl = tf_label(p1_gc_tf) + " ▶ " + tf_label(i_p1_tf)
                create_confirmed(g1_zt, g1_zb, false, g1_tm, lbl, i_p1_clr, p1_dem_z.top, p1_dem_z.bottom, confirmed, i_max_zones)

// --- Pair 2 ---
if p2_ok
    if p2_new
        if p2_sup > 0
            p2_sup_z.update_parent(p2_zt, p2_zb, p2_tm)
        else if p2_sup < 0
            p2_dem_z.update_parent(p2_zt, p2_zb, p2_tm)
    if g2_new
        bool gc_is_sup = g2_sup > 0
        bool gc_is_dem = g2_sup < 0
        if gc_is_sup and not p2_sup_z.is_broken
            if g2_zt <= p2_sup_z.top and g2_zb >= p2_sup_z.bottom
                string lbl = tf_label(p2_gc_tf) + " ▶ " + tf_label(i_p2_tf)
                create_confirmed(g2_zt, g2_zb, true, g2_tm, lbl, i_p2_clr, p2_sup_z.top, p2_sup_z.bottom, confirmed, i_max_zones)
        if gc_is_dem and not p2_dem_z.is_broken
            if g2_zt <= p2_dem_z.top and g2_zb >= p2_dem_z.bottom
                string lbl = tf_label(p2_gc_tf) + " ▶ " + tf_label(i_p2_tf)
                create_confirmed(g2_zt, g2_zb, false, g2_tm, lbl, i_p2_clr, p2_dem_z.top, p2_dem_z.bottom, confirmed, i_max_zones)

// --- Pair 3 ---
if p3_ok
    if p3_new
        if p3_sup > 0
            p3_sup_z.update_parent(p3_zt, p3_zb, p3_tm)
        else if p3_sup < 0
            p3_dem_z.update_parent(p3_zt, p3_zb, p3_tm)
    if g3_new
        bool gc_is_sup = g3_sup > 0
        bool gc_is_dem = g3_sup < 0
        if gc_is_sup and not p3_sup_z.is_broken
            if g3_zt <= p3_sup_z.top and g3_zb >= p3_sup_z.bottom
                string lbl = tf_label(p3_gc_tf) + " ▶ " + tf_label(i_p3_tf)
                create_confirmed(g3_zt, g3_zb, true, g3_tm, lbl, i_p3_clr, p3_sup_z.top, p3_sup_z.bottom, confirmed, i_max_zones)
        if gc_is_dem and not p3_dem_z.is_broken
            if g3_zt <= p3_dem_z.top and g3_zb >= p3_dem_z.bottom
                string lbl = tf_label(p3_gc_tf) + " ▶ " + tf_label(i_p3_tf)
                create_confirmed(g3_zt, g3_zb, false, g3_tm, lbl, i_p3_clr, p3_dem_z.top, p3_dem_z.bottom, confirmed, i_max_zones)
```

- [ ] **Step 5: Verify compiles and produces boxes**

Open in TradingView on an M15 chart with defaults (D + H4 pairs). Use Replay mode to step through bars. Expected: confirmed zone boxes appear when grandchild zones form inside parent zones.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): add nesting engine with parent tracking and containment (S7, S9)"
```

---

### Task 5: Break management and box extension (S8)

**Files:**
- Modify: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Add S8 break management — parent zone breaks**

Insert after the S7 nesting logic. Check each parent zone for body-close breaks and cascade to confirmed zones.

```pine
// =============================================================================
// S8 — BREAK MANAGEMENT
// =============================================================================

// Parent zone break checks
if p1_ok
    if not p1_sup_z.is_broken and close > p1_sup_z.top
        p1_sup_z.is_broken := true
    if not p1_dem_z.is_broken and close < p1_dem_z.bottom
        p1_dem_z.is_broken := true
if p2_ok
    if not p2_sup_z.is_broken and close > p2_sup_z.top
        p2_sup_z.is_broken := true
    if not p2_dem_z.is_broken and close < p2_dem_z.bottom
        p2_dem_z.is_broken := true
if p3_ok
    if not p3_sup_z.is_broken and close > p3_sup_z.top
        p3_sup_z.is_broken := true
    if not p3_dem_z.is_broken and close < p3_dem_z.bottom
        p3_dem_z.is_broken := true
```

- [ ] **Step 2: Add confirmed zone break checks + parent cascade + box extension**

Iterate the confirmed array in reverse (for safe removal). Check body-close breaks on confirmed zones AND parent invalidation. Extend surviving boxes to current bar.

```pine
// Confirmed zone break checks + parent cascade + box extension
if confirmed.size() > 0
    for j = confirmed.size() - 1 to 0
        ConfirmedZone cz = confirmed.get(j)
        bool cz_broken = false

        // Body-close break on confirmed zone itself
        if cz.is_supply and close > cz.top
            cz_broken := true
        else if not cz.is_supply and close < cz.bottom
            cz_broken := true

        // Parent invalidation: check if the parent zone that contained this confirmed zone is now broken
        // Match by parent_top and parent_bot against all parent zones
        if not cz_broken
            if p1_ok
                if cz.is_supply and p1_sup_z.is_broken and cz.parent_top == p1_sup_z.top and cz.parent_bot == p1_sup_z.bottom
                    cz_broken := true
                if not cz.is_supply and p1_dem_z.is_broken and cz.parent_top == p1_dem_z.top and cz.parent_bot == p1_dem_z.bottom
                    cz_broken := true
            if p2_ok and not cz_broken
                if cz.is_supply and p2_sup_z.is_broken and cz.parent_top == p2_sup_z.top and cz.parent_bot == p2_sup_z.bottom
                    cz_broken := true
                if not cz.is_supply and p2_dem_z.is_broken and cz.parent_top == p2_dem_z.top and cz.parent_bot == p2_dem_z.bottom
                    cz_broken := true
            if p3_ok and not cz_broken
                if cz.is_supply and p3_sup_z.is_broken and cz.parent_top == p3_sup_z.top and cz.parent_bot == p3_sup_z.bottom
                    cz_broken := true
                if not cz.is_supply and p3_dem_z.is_broken and cz.parent_top == p3_dem_z.top and cz.parent_bot == p3_dem_z.bottom
                    cz_broken := true

        if cz_broken
            if not na(cz.bx)
                box.delete(cz.bx)
            if not na(cz.lbl)
                label.delete(cz.lbl)
            confirmed.remove(j)
        else
            // Extend box and reposition label to current bar
            if not na(cz.bx)
                box.set_right(cz.bx, time)
            if not na(cz.lbl)
                label.set_x(cz.lbl, time)
```

- [ ] **Step 3: Verify compiles and break behavior works**

In TradingView Replay:
1. Step through until a confirmed zone appears
2. Continue stepping until price body-closes through it → box should disappear immediately
3. Test parent invalidation: find a case where the parent zone gets broken → confirmed zones inside it should also disappear

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): add break management and box extension (S8)"
```

---

### Task 6: Final validation and cleanup

**Files:**
- Modify: `tw_indicators/system/iora_nested_zones.pine`

- [ ] **Step 1: Add section comment headers for S9**

The state declarations were added in Task 4. Ensure the S9 section comment is properly placed above them and all section numbers are in order (S1-S9).

- [ ] **Step 2: Verify Pine v6 compliance against CLAUDE.md rules**

Check the complete file against these rules:
- `//@version=6` present
- All variables explicitly typed (`float`, `int`, `bool`, `string`, `color`)
- No multiline ternaries (single line or wrapped in parentheses)
- No reserved keywords as variable names (`range`, `time`, `close`, etc.)
- Timeframe strings use correct format (`"60"` not `"1H"`, `"240"` not `"4H"`)
- UDT fields explicitly typed with defaults
- One statement per line (no semicolons as separators)
- Field assignment on `.get()` result stored in local variable first

- [ ] **Step 3: Full TradingView Replay validation**

Test on M15 chart (default pairs: D→H1, H4→M15):
1. Confirmed supply zones appear when H1/M15 supply forms inside D/H4 supply
2. Confirmed demand zones appear when H1/M15 demand forms inside D/H4 demand
3. Boxes extend right correctly
4. Labels show correct format (e.g., "H1 ▶ D ↘ S")
5. Body-close break removes confirmed zones
6. Parent zone break cascades to remove confirmed zones
7. Max zone count enforced (oldest removed when exceeded)
8. Disabling a pair stops new confirmations for that pair

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/system/iora_nested_zones.pine
git commit -m "feat(nested-zones): final cleanup and validation pass"
```
