# Iora Fractal Zones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Pine Script v6 indicator that visualizes the Fractal Push/Pull Trading System — HA-transition zones with ORIZ boundaries, HH/LH/HL/LL classification, Universal Triplet Engine (4-state machine × 3 instances), trendlines, and dashboard.

**Architecture:** Single-file layered indicator. L1: zone detection + classification. L2: triplet state machine + role coloring. L3: trendlines + magnet lines. L4: dashboard. Each layer is a contiguous section guarded by a `bool i_layer_X` input toggle so it can compile and be visually validated independently.

**Tech Stack:** Pine Script v6, TradingView overlay indicator, `request.security()` for multi-TF data (10 calls: 5 TFs × 2 for HA + OHLC).

**Spec:** `docs/superpowers/specs/2026-03-31-iora-fractal-zones-design.md`
**Pine v6 rules:** `CLAUDE.md` — all variables explicitly typed, no multiline ternaries, no reserved keywords, timeframe strings as `"60"` not `"1H"`, UDT fields with explicit defaults, `.copy()` for UDT clones, store `.get()` result in local var before field assignment.

**Validation:** No automated test framework for Pine Script. Each task ends with "compile in TradingView" as the verification step. Visual validation against the GBPUSD charts in `docs/iora_zones/images/`.

---

## File Structure

Single file — all code lives in:

- **Create:** `tw_indicators/iora_zones/iora_fractal_zones.pine`

The file is organized into clearly commented sections matching the layers. No other files are created or modified.

---

## Task 1: Scaffold — Inputs, request.security(), New-Period Detection

**Files:**
- Create: `tw_indicators/iora_zones/iora_fractal_zones.pine`

This task creates the file with the indicator declaration, all inputs, all 10 `request.security()` calls, and new-period detection booleans. No zone logic yet — just the data foundation.

- [ ] **Step 1: Write indicator header + inputs**

```pine
//@version=6
indicator("Iora Fractal Zones", overlay=true, max_boxes_count=500, max_labels_count=500, max_lines_count=500)

// =============================================================================
// === INPUTS
// =============================================================================

// --- Zones ---
bool   i_zone_h1   = input.bool(true,           "Show H1 zones",              group="Zones")
bool   i_zone_h4   = input.bool(true,           "Show H4 zones",              group="Zones")
bool   i_zone_d    = input.bool(true,           "Show D zones",               group="Zones")
bool   i_zone_w    = input.bool(true,           "Show W zones",               group="Zones")
bool   i_zone_mn   = input.bool(true,           "Show MN zones",              group="Zones")
int    i_max_zones = input.int(20,              "Max zones per TF per side",  group="Zones", minval=4, maxval=40)

// --- Triplet Engine ---
bool   i_triplets  = input.bool(true,           "Enable triplet engine",      group="Triplet Engine")
bool   i_show_t1   = input.bool(true,           "T1 (MN→W→D)",               group="Triplet Engine")
bool   i_show_t2   = input.bool(true,           "T2 (W→D→H4)",               group="Triplet Engine")
bool   i_show_t3   = input.bool(true,           "T3 (D→H4→H1)",              group="Triplet Engine")

// --- Trendlines ---
bool   i_trendlines = input.bool(true,          "Show trendlines",            group="Trendlines")
bool   i_magnets    = input.bool(true,          "Show magnet lines",          group="Trendlines")

// --- Dashboard ---
bool   i_dash      = input.bool(true,           "Show dashboard",             group="Dashboard")
string i_dash_pos  = input.string("Bottom Right","Position",                  group="Dashboard", options=["Top Left","Top Right","Bottom Left","Bottom Right"])

// --- Layers (debug) ---
bool   i_layer_1   = input.bool(true,           "L1: Zones + classification", group="Layers")
bool   i_layer_2   = input.bool(true,           "L2: Triplet engine + roles", group="Layers")
bool   i_layer_3   = input.bool(true,           "L3: Trendlines + magnets",   group="Layers")
bool   i_layer_4   = input.bool(true,           "L4: Dashboard",              group="Layers")
```

- [ ] **Step 2: Write request.security() calls**

```pine
// =============================================================================
// === REQUEST.SECURITY — 5 TFs × 2 CALLS = 10 TOTAL
// =============================================================================

string ha_tkr = ticker.heikinashi(syminfo.tickerid)

// --- H1 ---
[h1_ha_o, h1_ha_h, h1_ha_l, h1_ha_c] = request.security(ha_tkr,              "60",  [open, high, low, close], lookahead=barmerge.lookahead_on)
[h1_o, h1_h, h1_l, h1_c, h1_t]       = request.security(syminfo.tickerid,    "60",  [open, high, low, close, time], lookahead=barmerge.lookahead_on)

// --- H4 ---
[h4_ha_o, h4_ha_h, h4_ha_l, h4_ha_c] = request.security(ha_tkr,              "240", [open, high, low, close], lookahead=barmerge.lookahead_on)
[h4_o, h4_h, h4_l, h4_c, h4_t]       = request.security(syminfo.tickerid,    "240", [open, high, low, close, time], lookahead=barmerge.lookahead_on)

// --- D ---
[d_ha_o, d_ha_h, d_ha_l, d_ha_c]     = request.security(ha_tkr,              "1D",  [open, high, low, close], lookahead=barmerge.lookahead_on)
[d_o, d_h, d_l, d_c, d_t]            = request.security(syminfo.tickerid,    "1D",  [open, high, low, close, time], lookahead=barmerge.lookahead_on)

// --- W ---
[w_ha_o, w_ha_h, w_ha_l, w_ha_c]     = request.security(ha_tkr,              "1W",  [open, high, low, close], lookahead=barmerge.lookahead_on)
[w_o, w_h, w_l, w_c, w_t]            = request.security(syminfo.tickerid,    "1W",  [open, high, low, close, time], lookahead=barmerge.lookahead_on)

// --- MN ---
[mn_ha_o, mn_ha_h, mn_ha_l, mn_ha_c] = request.security(ha_tkr,              "1M",  [open, high, low, close], lookahead=barmerge.lookahead_on)
[mn_o, mn_h, mn_l, mn_c, mn_t]       = request.security(syminfo.tickerid,    "1M",  [open, high, low, close, time], lookahead=barmerge.lookahead_on)
```

- [ ] **Step 3: Write new-period detection**

```pine
// =============================================================================
// === NEW-PERIOD DETECTION
// =============================================================================

bool h1_new  = ta.change(h1_t)  != 0
bool h4_new  = ta.change(h4_t)  != 0
bool d_new   = ta.change(d_t)   != 0
bool w_new   = ta.change(w_t)   != 0
bool mn_new  = ta.change(mn_t)  != 0
```

- [ ] **Step 4: Compile**

Paste into TradingView Pine Editor. Expected: compiles with no errors, no visual output yet (no plots/drawings). The indicator loads on chart without error.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): scaffold — inputs, request.security, new-period detection"
```

---

## Task 2: L1a — FractalZone UDT + Zone Arrays

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add the UDT definition and per-TF zone arrays. No zone creation yet.

- [ ] **Step 1: Write FractalZone UDT**

```pine
// =============================================================================
// === L1: ZONE UDT + ARRAYS
// =============================================================================

type FractalZone
    float   top       = na
    float   bottom    = na
    int     side      = 0      // +1 demand, -1 supply
    int     cls       = 0      // 1=HH, 2=LH, 3=LL, 4=HL
    int     role      = 0      // 0=unassigned, 1=push, 2=cont, 3=pullback, 4=reversal
    string  tf_str    = ""
    int     birth_bar = 0
    int     max_age   = 50
    bool    is_nested = false  // fully contained inside parent-TF zone
    bool    is_terminal = false // opposing nest — zone WILL be broken
    string  nested_in = ""     // parent TF if nested (e.g., "H4")
    bool    is_rev_target = false // reversal target (Rule 11)
    box     bx        = na
    label   lbl       = na
```

- [ ] **Step 2: Write per-TF zone arrays**

```pine
var array<FractalZone> h1_sup  = array.new<FractalZone>(0)
var array<FractalZone> h1_dem  = array.new<FractalZone>(0)
var array<FractalZone> h4_sup  = array.new<FractalZone>(0)
var array<FractalZone> h4_dem  = array.new<FractalZone>(0)
var array<FractalZone> d_sup   = array.new<FractalZone>(0)
var array<FractalZone> d_dem   = array.new<FractalZone>(0)
var array<FractalZone> w_sup   = array.new<FractalZone>(0)
var array<FractalZone> w_dem   = array.new<FractalZone>(0)
var array<FractalZone> mn_sup  = array.new<FractalZone>(0)
var array<FractalZone> mn_dem  = array.new<FractalZone>(0)
```

- [ ] **Step 3: Write last-created zone trackers (Rule 11)**

```pine
// =============================================================================
// === L1: LAST-CREATED ZONE TRACKING (Rule 11 — reversal target identification)
// =============================================================================

var int h1_last_sup_bar  = -1
var int h1_last_dem_bar  = -1
var int h4_last_sup_bar  = -1
var int h4_last_dem_bar  = -1
var int d_last_sup_bar   = -1
var int d_last_dem_bar   = -1
var int w_last_sup_bar   = -1
var int w_last_dem_bar   = -1
var int mn_last_sup_bar  = -1
var int mn_last_dem_bar  = -1
```

These store the `birth_bar` of the most recently created zone per TF per side. Updated in Task 4 when zones are created.

- [ ] **Step 4: Compile**

Expected: compiles, no visual output. UDT, arrays, and trackers declared.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L1a — FractalZone UDT, zone arrays, last-zone trackers"
```

---

## Task 3: L1b — HA Run Tracking + Zone Creation Function

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add per-TF HA run tracking variables and the `create_zone()` function. Also add zone color constants.

- [ ] **Step 1: Write zone color constants**

```pine
// =============================================================================
// === L1: ZONE COLORS
// =============================================================================

color Z_CLR_H1  = #AB47BC
color Z_CLR_H4  = #FF7043
color Z_CLR_D   = #FFCA28
color Z_CLR_W   = #42A5F5
color Z_CLR_MN  = #78909C
color Z_CLR_SUP = #ff4444
color Z_CLR_DEM = #2196f3
```

- [ ] **Step 2: Write HA run tracking vars (per TF)**

```pine
// =============================================================================
// === L1: HA RUN TRACKING (per TF)
// =============================================================================

// H1
var int   h1_ha_dir     = 0
var float h1_run_hi     = na
var float h1_run_lo     = na
var float h1_prev_s_top = na
var float h1_prev_d_bot = na

// H4
var int   h4_ha_dir     = 0
var float h4_run_hi     = na
var float h4_run_lo     = na
var float h4_prev_s_top = na
var float h4_prev_d_bot = na

// D
var int   d_ha_dir      = 0
var float d_run_hi      = na
var float d_run_lo      = na
var float d_prev_s_top  = na
var float d_prev_d_bot  = na

// W
var int   w_ha_dir      = 0
var float w_run_hi      = na
var float w_run_lo      = na
var float w_prev_s_top  = na
var float w_prev_d_bot  = na

// MN
var int   mn_ha_dir     = 0
var float mn_run_hi     = na
var float mn_run_lo     = na
var float mn_prev_s_top = na
var float mn_prev_d_bot = na
```

- [ ] **Step 3: Write create_zone() function**

This function creates a FractalZone, draws the box + label, pushes to array, enforces max count.

```pine
// =============================================================================
// === L1: ZONE CREATION FUNCTION
// =============================================================================

create_zone(array<FractalZone> arr, float ztop, float zbot, int side, int cls, string tf_str, int max_age_bars, bool show, color fill_clr, int max_z) =>
    if ztop > zbot
        FractalZone z = FractalZone.new()
        z.top       := ztop
        z.bottom    := zbot
        z.side      := side
        z.cls       := cls
        z.tf_str    := tf_str
        z.birth_bar := bar_index
        z.max_age   := max_age_bars
        color border_clr = side < 0 ? Z_CLR_SUP : Z_CLR_DEM
        if show and i_layer_1
            z.bx := box.new(bar_index, ztop, bar_index + 50, zbot, border_color=color.new(border_clr, 40), bgcolor=color.new(fill_clr, 88), border_width=1, extend=extend.right)
            string cls_str = cls == 1 ? "HH" : cls == 2 ? "LH" : cls == 3 ? "LL" : "HL"
            string side_str = side < 0 ? "S" : "D"
            string lbl_txt = tf_str + " " + side_str + " " + cls_str
            z.lbl := label.new(bar_index, side < 0 ? ztop : zbot, lbl_txt, style=(side < 0 ? label.style_label_down : label.style_label_up), color=color.new(fill_clr, 60), textcolor=color.white, size=size.tiny)
        arr.unshift(z)
        if arr.size() > max_z
            FractalZone old = arr.pop()
            if not na(old.bx)
                box.delete(old.bx)
            if not na(old.lbl)
                label.delete(old.lbl)
```

- [ ] **Step 4: Compile**

Expected: compiles, no visual output yet (function defined but not called).

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L1b — HA run tracking vars + create_zone function"
```

---

## Task 4: L1c — Zone Creation on HA Transitions (All 5 TFs)

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add the per-TF HA transition detection + zone creation logic. This is where zones actually appear on chart.

- [ ] **Step 1: Write helper function for HA transition processing**

```pine
// =============================================================================
// === L1: HA TRANSITION PROCESSING
// =============================================================================

// Process one TF's HA data. Returns [fired, side, cls, ztop, zbot]
// fired: true if a zone was created this bar
// Must be called with the TF's HA + OHLC data and run-tracking vars.
// Note: Pine v6 cannot pass var references, so we use this as logic reference
// and inline per TF below.
```

- [ ] **Step 2: Write zone creation for H4 (template for all TFs)**

This is the first TF. Once it works visually, we replicate for the other 4.

```pine
// =============================================================================
// === L1: ZONE CREATION — H4
// =============================================================================

bool h4_zone_fired = false
int  h4_zone_side  = 0
int  h4_zone_cls   = 0

if h4_new and not na(h4_ha_c)
    int h4_ha_dir_now = h4_ha_c >= h4_ha_o ? 1 : -1
    // Update run extremes
    h4_run_hi := na(h4_run_hi) ? h4_h : math.max(h4_run_hi, h4_h)
    h4_run_lo := na(h4_run_lo) ? h4_l : math.min(h4_run_lo, h4_l)
    // Check for transition
    if h4_ha_dir != 0 and h4_ha_dir_now != h4_ha_dir
        float h4_ha_range = h4_ha_h - h4_ha_l
        bool h4_is_doji = h4_ha_range > 0 ? (math.abs(h4_ha_c - h4_ha_o) / h4_ha_range < 0.05) : true
        if h4_ha_dir > 0 and h4_ha_dir_now < 0
            // Blue→Red = SUPPLY
            float s_top = h4_run_hi
            float s_bot = h4_is_doji ? h4_ha_l : h4_ha_l
            int s_cls = not na(h4_prev_s_top) ? (s_top > h4_prev_s_top ? 1 : 2) : 1
            h4_prev_s_top := s_top
            create_zone(h4_sup, s_top, s_bot, -1, s_cls, "H4", 50, i_zone_h4, Z_CLR_H4, i_max_zones)
            h4_zone_fired := true
            h4_zone_side  := -1
            h4_zone_cls   := s_cls
            h4_last_sup_bar := bar_index
        else if h4_ha_dir < 0 and h4_ha_dir_now > 0
            // Red→Blue = DEMAND
            float d_bot = h4_run_lo
            float d_top = h4_is_doji ? h4_ha_h : h4_ha_h
            int d_cls = not na(h4_prev_d_bot) ? (d_bot < h4_prev_d_bot ? 3 : 4) : 4
            h4_prev_d_bot := d_bot
            create_zone(h4_dem, d_top, d_bot, 1, d_cls, "H4", 50, i_zone_h4, Z_CLR_H4, i_max_zones)
            h4_zone_fired := true
            h4_zone_side  := 1
            h4_zone_cls   := d_cls
            h4_last_dem_bar := bar_index
        // Reset run tracking
        h4_run_hi := h4_h
        h4_run_lo := h4_l
    h4_ha_dir := h4_ha_dir_now
```

- [ ] **Step 3: Compile and visually verify H4 zones**

Load on GBPUSD M15 chart. Expected: H4 supply (red border) and demand (blue border) zone boxes appear at HA color transitions. Labels show "H4 S HH", "H4 D HL" etc. Compare with reference images in `docs/iora_zones/images/06_h4_push_zones_pullback_into_daily_lh_supply.png`.

- [ ] **Step 4: Replicate for H1, D, W, MN**

Same pattern as H4, substituting the appropriate variables. Key differences:
- H1: `h1_ha_*`, `h1_*`, `h1_new`, max_age=50, color=`Z_CLR_H1`, show=`i_zone_h1`
- D: `d_ha_*`, `d_*`, `d_new`, max_age=50, color=`Z_CLR_D`, show=`i_zone_d`
- W: `w_ha_*`, `w_*`, `w_new`, max_age=30, color=`Z_CLR_W`, show=`i_zone_w`
- MN: `mn_ha_*`, `mn_*`, `mn_new`, max_age=20, color=`Z_CLR_MN`, show=`i_zone_mn`

Each TF needs its own `XX_zone_fired`, `XX_zone_side`, `XX_zone_cls` output booleans for L2.

- [ ] **Step 5: Compile and visually verify all TFs**

Expected: zones for all 5 TFs appear. D zones should match `docs/iora_zones/images/02_daily_push_zones_extreme_hh_ll_annotated.png`. W/MN zones appear less frequently. Toggle individual TFs off via inputs to verify each works independently.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L1c — zone creation on HA transitions for all 5 TFs"
```

---

## Task 5: L1d — Zone Break Detection + Expiry

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add per-bar zone break checking and age-based expiry.

- [ ] **Step 1: Write check_zone_breaks function**

```pine
// =============================================================================
// === L1: ZONE BREAK DETECTION + EXPIRY
// =============================================================================

check_zone_breaks(array<FractalZone> zones, bool is_supply) =>
    int i = zones.size() - 1
    while i >= 0
        FractalZone z = zones.get(i)
        bool brk = is_supply ? close > z.top : close < z.bottom
        bool expired = bar_index - z.birth_bar > z.max_age
        if brk or expired
            if not na(z.bx)
                box.delete(z.bx)
            if not na(z.lbl)
                label.delete(z.lbl)
            zones.remove(i)
        i -= 1
```

- [ ] **Step 2: Write zone nesting detection function (Rule 04)**

```pine
// =============================================================================
// === L1: ZONE NESTING DETECTION (Rule 04)
// =============================================================================

check_nesting(FractalZone child, array<FractalZone> parent_sup, array<FractalZone> parent_dem, string parent_tf) =>
    for int i = 0 to math.max(parent_sup.size() - 1, 0)
        if i < parent_sup.size()
            FractalZone p = parent_sup.get(i)
            if child.top <= p.top and child.bottom >= p.bottom
                child.is_nested := true
                child.nested_in := parent_tf
                // Opposing: child demand inside parent supply = terminal
                child.is_terminal := child.side > 0
                break
    if not child.is_nested
        for int i = 0 to math.max(parent_dem.size() - 1, 0)
            if i < parent_dem.size()
                FractalZone p = parent_dem.get(i)
                if child.top <= p.top and child.bottom >= p.bottom
                    child.is_nested := true
                    child.nested_in := parent_tf
                    // Opposing: child supply inside parent demand = terminal
                    child.is_terminal := child.side < 0
                    break
    // Update label if nested
    if child.is_nested and not na(child.lbl)
        string cls_str = child.cls == 1 ? "HH" : child.cls == 2 ? "LH" : child.cls == 3 ? "LL" : "HL"
        string side_str = child.side < 0 ? "S" : "D"
        string suffix = child.is_terminal ? " [TERM]" : " @" + parent_tf
        label.set_text(child.lbl, child.tf_str + " " + side_str + " " + cls_str + suffix)
        if child.is_terminal
            box.set_border_style(child.bx, line.style_dotted)
```

Call nesting after zone creation (after all TF zone blocks):
```pine
// Check nesting: H1→H4, H4→D, D→W, W→MN
if h1_zone_fired
    FractalZone newest_h1 = h1_zone_side < 0 ? h1_sup.get(0) : h1_dem.get(0)
    check_nesting(newest_h1, h4_sup, h4_dem, "H4")
if h4_zone_fired
    FractalZone newest_h4 = h4_zone_side < 0 ? h4_sup.get(0) : h4_dem.get(0)
    check_nesting(newest_h4, d_sup, d_dem, "D")
if d_zone_fired
    FractalZone newest_d = d_zone_side < 0 ? d_sup.get(0) : d_dem.get(0)
    check_nesting(newest_d, w_sup, w_dem, "W")
if w_zone_fired
    FractalZone newest_w = w_zone_side < 0 ? w_sup.get(0) : w_dem.get(0)
    check_nesting(newest_w, mn_sup, mn_dem, "MN")
```

- [ ] **Step 3: Call break/expiry for all 10 arrays**

```pine
if i_layer_1
    check_zone_breaks(h1_sup, true)
    check_zone_breaks(h1_dem, false)
    check_zone_breaks(h4_sup, true)
    check_zone_breaks(h4_dem, false)
    check_zone_breaks(d_sup, true)
    check_zone_breaks(d_dem, false)
    check_zone_breaks(w_sup, true)
    check_zone_breaks(w_dem, false)
    check_zone_breaks(mn_sup, true)
    check_zone_breaks(mn_dem, false)
```

- [ ] **Step 4: Compile and verify**

Use TradingView Replay. Step forward through bars. Expected: zones disappear when price body-closes through them. Wicks through zones should NOT delete them. Zones also disappear after their max age in bars. Nested zones show `@H4` or `[TERM]` suffixes. Terminal zones have dotted borders.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L1d — zone break detection + age expiry"
```

---

## Task 6: L2a — TripletState UDT + Instances

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add the TripletState UDT and the 3 active instances (T1-T3).

- [ ] **Step 1: Write TripletState UDT**

```pine
// =============================================================================
// === L2: TRIPLET STATE UDT + INSTANCES
// =============================================================================

type TripletState
    string     id              = ""
    int        state           = 0      // 0=INIT, 1=PUSHING, 2=CONTINUING, 3=PULLING_BACK, 4=REVERSING
    int        direction       = 0      // +1 bullish, -1 bearish
    int        push_bar        = -1     // birth_bar of push zone
    int        push_side       = 0      // +1 demand, -1 supply
    float      push_target     = na     // parent zone boundary
    float      pb_target       = na     // push zone edge (magnet)
    float      parent_zone_top = na
    float      parent_zone_bot = na
    float      parent_lh_top   = na     // for reversal detection
    float      parent_hl_bot   = na     // for reversal detection
    bool       grand_choch     = false
    bool       grand_break     = false
    bool       compression     = false
    bool       failed_reversal = false
    int        push_fail_cnt   = 0
    int        tl_hold_cnt     = 0
    array<int> cont_bars       = na
    array<int> pb_bars         = na
    int        reversal_bar    = -1
```

- [ ] **Step 2: Write instance initialization**

```pine
var TripletState t1 = TripletState.new()
t1.id := "T1"
if barstate.isfirst
    t1.cont_bars := array.new<int>(0)
    t1.pb_bars   := array.new<int>(0)

var TripletState t2 = TripletState.new()
t2.id := "T2"
if barstate.isfirst
    t2.cont_bars := array.new<int>(0)
    t2.pb_bars   := array.new<int>(0)

var TripletState t3 = TripletState.new()
t3.id := "T3"
if barstate.isfirst
    t3.cont_bars := array.new<int>(0)
    t3.pb_bars   := array.new<int>(0)
```

- [ ] **Step 3: Compile**

Expected: compiles, no visual change. UDT and instances declared.

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L2a — TripletState UDT + T1/T2/T3 instances"
```

---

## Task 7: L2b — Triplet State Machine Functions

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add the three core triplet functions: `reset_triplet()`, `update_child()`, `update_grandchild()` and the per-bar pullback resolution check.

- [ ] **Step 1: Write find_zone_by_bar helper**

```pine
// =============================================================================
// === L2: TRIPLET ENGINE FUNCTIONS
// =============================================================================

// Find a zone in an array by its birth_bar. Returns the zone or na-filled zone.
find_zone_by_bar(array<FractalZone> arr, int target_bar) =>
    FractalZone result = FractalZone.new()
    bool found = false
    for int i = 0 to math.max(arr.size() - 1, 0)
        if i < arr.size()
            FractalZone z = arr.get(i)
            if z.birth_bar == target_bar
                result := z
                found  := true
    result
```

- [ ] **Step 2: Write reset_triplet()**

```pine
reset_triplet(TripletState ts, FractalZone parent_zone) =>
    ts.direction       := parent_zone.side > 0 ? 1 : -1
    ts.parent_zone_top := parent_zone.top
    ts.parent_zone_bot := parent_zone.bottom
    if parent_zone.cls == 2
        ts.parent_lh_top := parent_zone.top
    if parent_zone.cls == 4
        ts.parent_hl_bot := parent_zone.bottom
    ts.state           := 0
    ts.push_bar        := -1
    ts.push_side       := 0
    ts.grand_choch     := false
    ts.grand_break     := false
    ts.compression     := false
    ts.failed_reversal := false
    ts.push_fail_cnt   := 0
    ts.tl_hold_cnt     := 0
    ts.reversal_bar    := -1
    ts.push_target     := ts.direction > 0 ? parent_zone.top : parent_zone.bottom
    ts.pb_target       := na
    if not na(ts.cont_bars)
        ts.cont_bars.clear()
    if not na(ts.pb_bars)
        ts.pb_bars.clear()
```

- [ ] **Step 3: Write update_child()**

```pine
update_child(TripletState ts, FractalZone child_zone, array<FractalZone> child_sup, array<FractalZone> child_dem) =>
    bool inside_parent = child_zone.top >= ts.parent_zone_bot and child_zone.bottom <= ts.parent_zone_top
    bool same_dir = (ts.direction > 0 and child_zone.side > 0) or (ts.direction < 0 and child_zone.side < 0)
    bool counter = not same_dir and child_zone.side != 0
    if ts.state == 0 and inside_parent and same_dir
        ts.state     := 1
        ts.push_bar  := child_zone.birth_bar
        ts.push_side := child_zone.side
        ts.pb_target := ts.direction > 0 ? child_zone.bottom : child_zone.top
        child_zone.role := 1
    else if (ts.state == 1 or ts.state == 2) and same_dir
        // Check extends structure: new HH (cls==1) or new LL (cls==3)
        bool extends = (ts.direction > 0 and child_zone.cls == 1) or (ts.direction < 0 and child_zone.cls == 3)
        if extends
            ts.state := 2
            if not na(ts.cont_bars)
                ts.cont_bars.push(child_zone.birth_bar)
            child_zone.role := 2
    else if (ts.state == 1 or ts.state == 2) and counter
        ts.state := 3
        if not na(ts.pb_bars)
            ts.pb_bars.push(child_zone.birth_bar)
        child_zone.role := 3
    else if ts.state == 3 and counter
        if not na(ts.pb_bars)
            ts.pb_bars.push(child_zone.birth_bar)
        child_zone.role := 3
```

- [ ] **Step 4: Write update_grandchild()**

```pine
update_grandchild(TripletState ts, FractalZone grand_zone) =>
    if ts.state == 1 or ts.state == 2
        bool choch = (ts.direction > 0 and grand_zone.cls == 2) or (ts.direction < 0 and grand_zone.cls == 4)
        if choch
            ts.grand_choch := true
    if ts.state == 3
        // Grand CHoCH against pullback = pullback exhaustion signal
        bool pb_exhaust = (ts.direction > 0 and grand_zone.cls == 4) or (ts.direction < 0 and grand_zone.cls == 2)
        if pb_exhaust
            ts.grand_choch := true
    // Reversal: grand breaks parent structure
    if ts.direction > 0 and grand_zone.side < 0 and not na(ts.parent_hl_bot)
        if close < ts.parent_hl_bot
            ts.state      := 4
            ts.grand_break := true
    if ts.direction < 0 and grand_zone.side > 0 and not na(ts.parent_lh_top)
        if close > ts.parent_lh_top
            ts.state      := 4
            ts.grand_break := true
```

- [ ] **Step 5: Write per-bar pullback resolution check**

```pine
check_pullback_resolution(TripletState ts, array<FractalZone> child_sup, array<FractalZone> child_dem) =>
    if ts.state == 3 and not na(ts.pb_target)
        // Resolution A: price reaches push zone
        bool reached = (ts.direction > 0 and close <= ts.pb_target) or (ts.direction < 0 and close >= ts.pb_target)
        if reached and ts.grand_choch
            ts.state      := 1
            ts.push_bar   := -1
            ts.grand_choch := false
            if not na(ts.cont_bars)
                ts.cont_bars.clear()
            if not na(ts.pb_bars)
                ts.pb_bars.clear()
        // Resolution B: last pullback zone broken
        if not reached and not na(ts.pb_bars) and ts.pb_bars.size() > 0
            int last_pb_bar = ts.pb_bars.last()
            array<FractalZone> pb_arr = ts.direction > 0 ? child_sup : child_dem
            for int i = 0 to math.max(pb_arr.size() - 1, 0)
                if i < pb_arr.size()
                    FractalZone pz = pb_arr.get(i)
                    if pz.birth_bar == last_pb_bar
                        bool broken = (ts.direction > 0 and close > pz.top) or (ts.direction < 0 and close < pz.bottom)
                        if broken and ts.grand_choch
                            ts.state      := 1
                            ts.push_bar   := -1
                            ts.grand_choch := false
                            if not na(ts.cont_bars)
                                ts.cont_bars.clear()
                            if not na(ts.pb_bars)
                                ts.pb_bars.clear()
```

- [ ] **Step 6: Compile**

Expected: compiles, no visual change yet (functions defined but not wired to zone events).

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L2b — triplet state machine functions"
```

---

## Task 8: L2c — Wire Triplet Engine to Zone Events + Role Recoloring

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Connect the triplet functions to actual zone creation events. Add role-based recoloring of zone boxes.

- [ ] **Step 1: Write event dispatch**

After all zone creation blocks (Task 4) and before zone break detection (Task 5), add:

```pine
// =============================================================================
// === L2: TRIPLET EVENT DISPATCH
// =============================================================================

if i_layer_2 and i_triplets
    // --- T1: MN → W → D ---
    // Parent reset: MN zone fires
    if mn_zone_fired and mn_sup.size() > 0 and mn_zone_side < 0
        FractalZone pz = mn_sup.get(0)
        reset_triplet(t1, pz)
    if mn_zone_fired and mn_dem.size() > 0 and mn_zone_side > 0
        FractalZone pz = mn_dem.get(0)
        reset_triplet(t1, pz)
    // Child update: W zone fires
    if w_zone_fired
        FractalZone cz = w_zone_side < 0 ? w_sup.get(0) : w_dem.get(0)
        update_child(t1, cz, w_sup, w_dem)
    // Grandchild update: D zone fires
    if d_zone_fired
        FractalZone gz = d_zone_side < 0 ? d_sup.get(0) : d_dem.get(0)
        update_grandchild(t1, gz)

    // --- T2: W → D → H4 ---
    if w_zone_fired and w_sup.size() > 0 and w_zone_side < 0
        FractalZone pz = w_sup.get(0)
        reset_triplet(t2, pz)
    if w_zone_fired and w_dem.size() > 0 and w_zone_side > 0
        FractalZone pz = w_dem.get(0)
        reset_triplet(t2, pz)
    if d_zone_fired
        FractalZone cz = d_zone_side < 0 ? d_sup.get(0) : d_dem.get(0)
        update_child(t2, cz, d_sup, d_dem)
    if h4_zone_fired
        FractalZone gz = h4_zone_side < 0 ? h4_sup.get(0) : h4_dem.get(0)
        update_grandchild(t2, gz)

    // --- T3: D → H4 → H1 ---
    if d_zone_fired and d_sup.size() > 0 and d_zone_side < 0
        FractalZone pz = d_sup.get(0)
        reset_triplet(t3, pz)
    if d_zone_fired and d_dem.size() > 0 and d_zone_side > 0
        FractalZone pz = d_dem.get(0)
        reset_triplet(t3, pz)
    if h4_zone_fired
        FractalZone cz = h4_zone_side < 0 ? h4_sup.get(0) : h4_dem.get(0)
        update_child(t3, cz, h4_sup, h4_dem)
    if h1_zone_fired
        FractalZone gz = h1_zone_side < 0 ? h1_sup.get(0) : h1_dem.get(0)
        update_grandchild(t3, gz)

    // --- Per-bar pullback resolution ---
    check_pullback_resolution(t1, w_sup, w_dem)
    check_pullback_resolution(t2, d_sup, d_dem)
    check_pullback_resolution(t3, h4_sup, h4_dem)
```

- [ ] **Step 2: Write reversal target marking (Rule 11)**

After event dispatch, when a triplet transitions to PULLING_BACK, mark the last push-direction zone as the reversal target:

```pine
// =============================================================================
// === L2: REVERSAL TARGET MARKING (Rule 11)
// =============================================================================

mark_reversal_target(TripletState ts, array<FractalZone> child_sup, array<FractalZone> child_dem) =>
    if ts.state == 3  // PULLING_BACK
        // Last zone in push direction before pullback = reversal target
        array<FractalZone> push_arr = ts.direction > 0 ? child_dem : child_sup
        if push_arr.size() > 0
            // Find latest zone that is NOT a pullback zone
            for int i = 0 to math.max(push_arr.size() - 1, 0)
                if i < push_arr.size()
                    FractalZone z = push_arr.get(i)
                    if z.role == 1 or z.role == 2  // push or continuation
                        if not z.is_rev_target
                            z.is_rev_target := true
                            if not na(z.bx)
                                box.set_border_style(z.bx, line.style_dotted)
                            if not na(z.lbl)
                                string cls_str = z.cls == 1 ? "HH" : z.cls == 2 ? "LH" : z.cls == 3 ? "LL" : "HL"
                                string side_str = z.side < 0 ? "S" : "D"
                                string role_str = z.role == 1 ? "PUSH" : "CONT"
                                label.set_text(z.lbl, "★ " + z.tf_str + " " + side_str + " " + cls_str + " [" + role_str + "]")
                        break

if i_layer_2 and i_triplets
    mark_reversal_target(t1, w_sup, w_dem)
    mark_reversal_target(t2, d_sup, d_dem)
    mark_reversal_target(t3, h4_sup, h4_dem)
```

- [ ] **Step 3: Write role recoloring function**

```pine
// =============================================================================
// === L2: ROLE RECOLORING + REVERSAL TARGET VISUAL
// =============================================================================

color ROLE_PUSH = #4CAF50
color ROLE_CONT = #FF9800
color ROLE_PULL = #9C27B0
color ROLE_REV  = #E91E63

recolor_zone(FractalZone z) =>
    if not na(z.bx) and z.role > 0
        color rc = z.role == 1 ? ROLE_PUSH : z.role == 2 ? ROLE_CONT : z.role == 3 ? ROLE_PULL : ROLE_REV
        box.set_bgcolor(z.bx, color.new(rc, 80))
        box.set_border_color(z.bx, color.new(rc, 30))
        if not na(z.lbl)
            string cls_str = z.cls == 1 ? "HH" : z.cls == 2 ? "LH" : z.cls == 3 ? "LL" : "HL"
            string side_str = z.side < 0 ? "S" : "D"
            string role_str = z.role == 1 ? "PUSH" : z.role == 2 ? "CONT" : z.role == 3 ? "PULL" : "REV"
            label.set_text(z.lbl, z.tf_str + " " + side_str + " " + cls_str + " [" + role_str + "]")
            label.set_color(z.lbl, color.new(rc, 50))
```

- [ ] **Step 4: Apply recoloring after dispatch**

After the event dispatch block, iterate all zone arrays and recolor any zone with role > 0:

```pine
// Recolor zones that received roles
if i_layer_2 and i_triplets
    for int i = 0 to math.max(w_sup.size() - 1, 0)
        if i < w_sup.size()
            recolor_zone(w_sup.get(i))
    for int i = 0 to math.max(w_dem.size() - 1, 0)
        if i < w_dem.size()
            recolor_zone(w_dem.get(i))
    for int i = 0 to math.max(d_sup.size() - 1, 0)
        if i < d_sup.size()
            recolor_zone(d_sup.get(i))
    for int i = 0 to math.max(d_dem.size() - 1, 0)
        if i < d_dem.size()
            recolor_zone(d_dem.get(i))
    for int i = 0 to math.max(h4_sup.size() - 1, 0)
        if i < h4_sup.size()
            recolor_zone(h4_sup.get(i))
    for int i = 0 to math.max(h4_dem.size() - 1, 0)
        if i < h4_dem.size()
            recolor_zone(h4_dem.get(i))
    for int i = 0 to math.max(h1_sup.size() - 1, 0)
        if i < h1_sup.size()
            recolor_zone(h1_sup.get(i))
    for int i = 0 to math.max(h1_dem.size() - 1, 0)
        if i < h1_dem.size()
            recolor_zone(h1_dem.get(i))
```

- [ ] **Step 5: Compile and verify**

Expected: zones now show role-based colors. Push zones = green, continuation = orange, pullback = purple. Labels show `[PUSH]`, `[CONT]`, `[PULL]` suffixes. Reversal target zones show `★` prefix and dotted border. Compare with GBPUSD walkthrough from Addendum B — H4 D HL should be green [PUSH], H4 continuation demands should be orange [CONT], D LH S pullback zones should be purple [PULL].

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L2c — wire triplet engine + role recoloring + reversal targets"
```

---

## Task 9: L3 — Trendlines + Magnet Lines

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add trendline drawing from push → continuation zones, trendline break detection, and magnet lines during pullbacks.

- [ ] **Step 1: Write per-triplet trendline state vars**

```pine
// =============================================================================
// === L3: TRENDLINES + MAGNET LINES
// =============================================================================

// T1 trendline
var line t1_tl     = na
var bool t1_tl_brk = false

// T2 trendline
var line t2_tl     = na
var bool t2_tl_brk = false

// T3 trendline
var line t3_tl     = na
var bool t3_tl_brk = false

// Magnet lines
var line t1_mag = na
var line t2_mag = na
var line t3_mag = na

// Reversal target lines (Rule 11)
var line t1_rev = na
var line t2_rev = na
var line t3_rev = na

color TL_CLR     = #FFEB3B
color MAG_CLR    = color.white
color REV_CLR    = #E040FB   // magenta for reversal targets
```

- [ ] **Step 2: Write trendline update function**

```pine
update_trendline(TripletState ts, line tl_ref, array<FractalZone> child_sup, array<FractalZone> child_dem) =>
    line new_tl = tl_ref
    bool broken = false
    if i_layer_3 and i_trendlines and ts.push_bar >= 0 and not na(ts.cont_bars) and ts.cont_bars.size() > 0
        // Find push zone
        array<FractalZone> push_arr = ts.push_side > 0 ? child_dem : child_sup
        FractalZone push_z = find_zone_by_bar(push_arr, ts.push_bar)
        // Find latest continuation zone
        int last_cont_bar = ts.cont_bars.last()
        FractalZone cont_z = find_zone_by_bar(push_arr, last_cont_bar)
        if not na(push_z.top) and not na(cont_z.top) and cont_z.birth_bar > push_z.birth_bar
            float y1 = ts.direction > 0 ? push_z.bottom : push_z.top
            float y2 = ts.direction > 0 ? cont_z.bottom : cont_z.top
            int x1 = push_z.birth_bar
            int x2 = cont_z.birth_bar
            // Delete old line
            if not na(new_tl)
                line.delete(new_tl)
            new_tl := line.new(x1, y1, x2, y2, color=color.new(TL_CLR, 20), width=2, extend=extend.right)
            // Check break
            if x2 > x1
                float slope = (y2 - y1) / (x2 - x1)
                float projected = y2 + slope * (bar_index - x2)
                bool brk = ts.direction > 0 ? (close < projected and close[1] >= nz(projected[1])) : (close > projected and close[1] <= nz(projected[1]))
                if brk
                    broken := true
                    line.set_style(new_tl, line.style_dotted)
                    line.set_color(new_tl, color.new(TL_CLR, 60))
    else
        if not na(new_tl)
            line.delete(new_tl)
            new_tl := na
    [new_tl, broken]
```

- [ ] **Step 3: Write magnet line update function**

```pine
update_magnet(TripletState ts, line mag_ref) =>
    line new_mag = mag_ref
    if i_layer_3 and i_magnets and ts.state == 3 and not na(ts.pb_target)
        if na(new_mag)
            new_mag := line.new(bar_index - 1, ts.pb_target, bar_index, ts.pb_target, color=color.new(MAG_CLR, 50), style=line.style_dashed, width=1, extend=extend.right)
        else
            line.set_y1(new_mag, ts.pb_target)
            line.set_y2(new_mag, ts.pb_target)
    else
        if not na(new_mag)
            line.delete(new_mag)
            new_mag := na
    new_mag
```

- [ ] **Step 4: Write reversal target line function (Rule 11)**

```pine
update_rev_target_line(TripletState ts, line rev_ref, array<FractalZone> child_sup, array<FractalZone> child_dem) =>
    line new_rev = rev_ref
    if i_layer_3 and ts.state == 3
        // Find the is_rev_target zone
        array<FractalZone> push_arr = ts.direction > 0 ? child_dem : child_sup
        float rev_price = na
        for int i = 0 to math.max(push_arr.size() - 1, 0)
            if i < push_arr.size()
                FractalZone z = push_arr.get(i)
                if z.is_rev_target
                    rev_price := ts.direction > 0 ? z.top : z.bottom
                    break
        if not na(rev_price)
            if na(new_rev)
                new_rev := line.new(bar_index - 1, rev_price, bar_index, rev_price, color=color.new(REV_CLR, 40), style=line.style_dashed, width=2, extend=extend.right)
            else
                line.set_y1(new_rev, rev_price)
                line.set_y2(new_rev, rev_price)
        else
            if not na(new_rev)
                line.delete(new_rev)
                new_rev := na
    else
        if not na(new_rev)
            line.delete(new_rev)
            new_rev := na
    new_rev
```

- [ ] **Step 5: Call trendline + magnet + reversal target updates**

```pine
if i_layer_3
    [t1_tl_new, t1_tl_b] = update_trendline(t1, t1_tl, w_sup, w_dem)
    t1_tl     := t1_tl_new
    t1_tl_brk := t1_tl_b

    [t2_tl_new, t2_tl_b] = update_trendline(t2, t2_tl, d_sup, d_dem)
    t2_tl     := t2_tl_new
    t2_tl_brk := t2_tl_b

    [t3_tl_new, t3_tl_b] = update_trendline(t3, t3_tl, h4_sup, h4_dem)
    t3_tl     := t3_tl_new
    t3_tl_brk := t3_tl_b

    t1_mag := update_magnet(t1, t1_mag)
    t2_mag := update_magnet(t2, t2_mag)
    t3_mag := update_magnet(t3, t3_mag)

    t1_rev := update_rev_target_line(t1, t1_rev, w_sup, w_dem)
    t2_rev := update_rev_target_line(t2, t2_rev, d_sup, d_dem)
    t3_rev := update_rev_target_line(t3, t3_rev, h4_sup, h4_dem)
```

- [ ] **Step 6: Compile and verify**

Expected: yellow trendlines drawn from push zones through continuation zones. Dashed white magnet lines appear when triplet is in pullback state. Magenta dashed reversal target lines appear during pullbacks (Rule 11). TL goes dotted on break. Compare with reference images showing D and H4 trendlines.

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L3 — trendlines + magnets + reversal targets + break detection"
```

---

## Task 10: L4 — Dashboard

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

Add the dashboard table showing triplet states, composite bias, targets, and signal status.

- [ ] **Step 1: Write state-to-string helpers**

```pine
// =============================================================================
// === L4: DASHBOARD
// =============================================================================

state_str(int s) =>
    string r = switch s
        1 => "PUSHING"
        2 => "CONTINUING"
        3 => "PULLING BACK"
        4 => "REVERSING"
        => "INIT"
    r

state_clr(int s) =>
    color r = switch s
        1 => #4CAF50
        2 => #66BB6A
        3 => #FF9800
        4 => #E91E63
        => #546E7A
    r

dir_arrow(int d) =>
    string r = d > 0 ? " ↑" : d < 0 ? " ↓" : ""
    r
```

- [ ] **Step 2: Write dashboard table**

```pine
if i_layer_4 and i_dash and barstate.islast
    string tbl_pos = switch i_dash_pos
        "Top Left"     => position.top_left
        "Top Right"    => position.top_right
        "Bottom Left"  => position.bottom_left
        =>                position.bottom_right

    var table dash = na
    if not na(dash)
        table.delete(dash)

    int rows = 12
    dash := table.new(tbl_pos, 2, rows, bgcolor=color.new(#0D1117, 10), border_width=1, border_color=color.new(#3A3A5A, 50), frame_width=1, frame_color=color.new(#3A3A5A, 30))

    color hdr_bg  = color.new(#0D1117, 0)
    color hdr_txt = color.new(#58A6FF, 0)
    color cell_bg = color.new(#161B22, 0)
    string sz     = size.tiny

    // Row 0: Header
    table.cell(dash, 0, 0, "Fractal Push/Pull v0.1", text_color=hdr_txt, bgcolor=hdr_bg, text_size=sz)
    table.cell(dash, 1, 0, "", bgcolor=hdr_bg, text_size=sz)

    // Row 1: T1
    table.cell(dash, 0, 1, "T1: MN→W→D", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 1, state_str(t1.state) + dir_arrow(t1.direction), text_color=state_clr(t1.state), bgcolor=cell_bg, text_size=sz)

    // Row 2: T2
    table.cell(dash, 0, 2, "T2: W→D→H4", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 2, state_str(t2.state) + dir_arrow(t2.direction), text_color=state_clr(t2.state), bgcolor=cell_bg, text_size=sz)

    // Row 3: T3
    table.cell(dash, 0, 3, "T3: D→H4→H1", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 3, state_str(t3.state) + dir_arrow(t3.direction), text_color=state_clr(t3.state), bgcolor=cell_bg, text_size=sz)

    // Row 4: Separator
    table.cell(dash, 0, 4, "", bgcolor=hdr_bg, text_size=sz)
    table.cell(dash, 1, 4, "", bgcolor=hdr_bg, text_size=sz)

    // Row 5: Composite bias
    bool all_same = t1.direction == t2.direction and t2.direction == t3.direction and t1.direction != 0
    bool all_push = (t1.state == 1 or t1.state == 2) and (t2.state == 1 or t2.state == 2) and (t3.state == 1 or t3.state == 2)
    bool higher_aligned = t1.direction == t2.direction and t1.direction != 0 and (t1.state == 1 or t1.state == 2) and (t2.state == 1 or t2.state == 2)
    string comp_str = all_same and all_push ? "FULL ALIGN" + dir_arrow(t1.direction) : higher_aligned ? "PARTIAL" + dir_arrow(t1.direction) : "CONFLICT"
    color comp_clr = all_same and all_push ? (t1.direction > 0 ? #4CAF50 : #EF5350) : higher_aligned ? #FF9800 : #546E7A
    table.cell(dash, 0, 5, "Composite", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 5, comp_str, text_color=color.new(comp_clr, 0), bgcolor=cell_bg, text_size=sz)

    // Row 6: Target (nearest magnet)
    float target = na
    string target_lbl = "—"
    if t3.state == 3 and not na(t3.pb_target)
        target := t3.pb_target
        target_lbl := "D push @ " + str.tostring(t3.pb_target, format.mintick)
    else if t2.state == 3 and not na(t2.pb_target)
        target := t2.pb_target
        target_lbl := "W push @ " + str.tostring(t2.pb_target, format.mintick)
    table.cell(dash, 0, 6, "Target", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 6, target_lbl, text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)

    // Row 7: Pullback depth
    string pb_str = "—"
    if t3.state == 3 and not na(t3.pb_target) and not na(t3.push_target)
        float total_range = math.abs(t3.push_target - t3.pb_target)
        float current_depth = ts.direction > 0 ? math.abs(t3.push_target - close) : math.abs(close - t3.push_target)
        float pct = total_range > 0 ? current_depth / total_range * 100 : 0
        pb_str := "PB: " + str.tostring(pct, "#") + "%"
    table.cell(dash, 0, 7, "Depth", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 7, pb_str, text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)

    // Row 8: Signal (TL/zone status for T3)
    string sig_str = "—"
    if t3_tl_brk
        sig_str := "WARNING (TL broken)"
    else if t3.state == 4
        sig_str := "REVERSED"
    else if t3.state == 1 or t3.state == 2
        sig_str := "HOLDING"
    table.cell(dash, 0, 8, "Signal", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    color sig_clr = t3_tl_brk ? #FF9800 : t3.state == 4 ? #EF5350 : #4CAF50
    table.cell(dash, 1, 8, sig_str, text_color=color.new(sig_clr, 0), bgcolor=cell_bg, text_size=sz)

    // Row 9: Separator
    table.cell(dash, 0, 9, "", bgcolor=hdr_bg, text_size=sz)
    table.cell(dash, 1, 9, "", bgcolor=hdr_bg, text_size=sz)

    // Row 10: Alignment grid (momentum consumption concept)
    // Direction per TF derived from triplet where each TF is child
    int h1_dir = t3.direction
    int h4_dir = t3.direction  // H4 is grandchild of T2, child influence from T3
    int d_dir  = t2.direction
    int w_dir  = t1.direction
    int mn_dir = t1.direction > 0 ? -1 : (t1.direction < 0 ? 1 : 0)  // parent = opposite of child push
    string align_str = "H1:" + dir_arrow(h1_dir) + " H4:" + dir_arrow(h4_dir) + " D:" + dir_arrow(d_dir) + " W:" + dir_arrow(w_dir)
    table.cell(dash, 0, 10, "Alignment", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 10, align_str, text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)

    // Row 11: Reversal target (Rule 11)
    string rev_str = "—"
    if t3.state == 3
        array<FractalZone> rev_arr = t3.direction > 0 ? h4_dem : h4_sup
        for int i = 0 to math.max(rev_arr.size() - 1, 0)
            if i < rev_arr.size()
                FractalZone rz = rev_arr.get(i)
                if rz.is_rev_target
                    string r_side = rz.side < 0 ? "S" : "D"
                    string r_cls = rz.cls == 1 ? "HH" : rz.cls == 2 ? "LH" : rz.cls == 3 ? "LL" : "HL"
                    rev_str := "H4 " + r_side + " " + r_cls + " @ " + str.tostring(rz.top, format.mintick) + "-" + str.tostring(rz.bottom, format.mintick)
                    break
    else if t2.state == 3
        array<FractalZone> rev_arr = t2.direction > 0 ? d_dem : d_sup
        for int i = 0 to math.max(rev_arr.size() - 1, 0)
            if i < rev_arr.size()
                FractalZone rz = rev_arr.get(i)
                if rz.is_rev_target
                    string r_side = rz.side < 0 ? "S" : "D"
                    string r_cls = rz.cls == 1 ? "HH" : rz.cls == 2 ? "LH" : rz.cls == 3 ? "LL" : "HL"
                    rev_str := "D " + r_side + " " + r_cls + " @ " + str.tostring(rz.top, format.mintick) + "-" + str.tostring(rz.bottom, format.mintick)
                    break
    table.cell(dash, 0, 11, "Rev Target", text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=sz)
    table.cell(dash, 1, 11, rev_str, text_color=color.new(REV_CLR, 0), bgcolor=cell_bg, text_size=sz)
```

- [ ] **Step 3: Fix pullback depth reference**

Note: the pullback depth block has a typo — `ts.direction` should be `t3.direction`. Fix:
```pine
        float current_depth = t3.direction > 0 ? math.abs(t3.push_target - close) : math.abs(close - t3.push_target)
```

- [ ] **Step 4: Compile and verify**

Expected: dashboard appears in bottom-right corner showing T1/T2/T3 states, composite bias, target price, pullback depth %, signal status, alignment grid (H1/H4/D/W arrows), and reversal target zone (if any triplet is pulling back). Compare triplet states with the GBPUSD walkthrough from Addendum B — T2 should show PULLING BACK ↓, T3 should show PUSHING ↓.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): L4 — dashboard with triplet states + composite bias"
```

---

## Task 11: Final Visual Validation + Polish

**Files:**
- Modify: `tw_indicators/iora_zones/iora_fractal_zones.pine`

End-to-end validation on GBPUSD, fix any visual issues.

- [ ] **Step 1: Load on GBPUSD M15 with all layers on**

Compare against all reference images in `docs/iora_zones/images/`. Check:
- Zone boxes appear at HA transitions with correct ORIZ boundaries
- HH/LH/HL/LL classification matches visible structure
- Push zones (green) align with the origin of parent structural moves
- Continuation zones (orange) stack in the push direction
- Pullback zones (purple) move counter to parent direction
- Trendlines connect push → continuation zones
- Magnet lines appear during pullbacks
- Dashboard shows correct triplet states

- [ ] **Step 2: Test layer toggles**

Disable each layer via inputs:
- L1 off: no zones at all
- L2 off: zones show TF colors (no role recoloring)
- L3 off: no trendlines or magnets
- L4 off: no dashboard

- [ ] **Step 3: Test TF toggles**

Disable each TF. Verify zones for that TF disappear without affecting others.

- [ ] **Step 4: Fix any compilation or visual issues found**

Address any Pine v6 errors, misaligned zones, incorrect classifications, or rendering issues.

- [ ] **Step 5: Final commit**

```bash
git add tw_indicators/iora_zones/iora_fractal_zones.pine
git commit -m "feat(fractal-zones): visual polish + validation pass"
```

---

## Summary

| Task | Layer | What | Est. complexity |
|------|-------|------|-----------------|
| 1 | Scaffold | Inputs + security calls + new-period | Low |
| 2 | L1a | UDT + arrays + last-zone trackers (Rule 11) | Low |
| 3 | L1b | HA run tracking + create_zone() | Medium |
| 4 | L1c | Zone creation for all 5 TFs + last-zone updates | Medium |
| 5 | L1d | Break detection + expiry + nesting detection (Rule 04) | Medium |
| 6 | L2a | TripletState UDT + instances | Low |
| 7 | L2b | State machine functions | High |
| 8 | L2c | Wire dispatch + reversal targets (Rule 11) + role recoloring | High |
| 9 | L3 | Trendlines + magnets + reversal target lines + break detection | Medium |
| 10 | L4 | Dashboard + alignment grid + reversal target display | Medium |
| 11 | — | Visual validation + polish | Medium |
