# Iora Intraday Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `iora_intraday.pine` — a Pine Script v6 indicator that computes multi-TF structural state (D/H4/H1/M15/M5/M1), context mode (RIDE/FLIP/SCALP/SKIP), entry cascade triggers, and a dashboard table.

**Architecture:** Single-file layered build. 9 sections (S1–S9) matching existing Iora indicator conventions. Each task adds one section and compiles cleanly before the next. The indicator replicates HA zone detection internally (Pine can't share arrays between indicators), then builds the decision layer on top.

**Tech Stack:** Pine Script v6, TradingView overlay indicator.

**Spec:** `docs/superpowers/specs/2026-03-28-iora-intraday-design.md`

**Reference Code:**
- `tw_indicators/system/iora_structure.pine` — ha_detect(), manage_zones(), check_external_break(), bias tracking pattern
- `tw_indicators/system/iora_zones.pine` — ha_detect() with sequence tracking, zone array management
- `CLAUDE.md` — Pine v6 rules (no implicit typing, no multiline ternaries, no reserved keywords, etc.)

---

## File Structure

Single file, built incrementally:

- **Create:** `tw_indicators/system/iora_intraday.pine`

No other files created or modified. Existing indicators are untouched.

---

### Task 1: Scaffold — S1 Types + S2 Inputs + indicator header

**Files:**
- Create: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Create the file with indicator header, S1 Types, and S2 Inputs**

```pine
//@version=6
indicator("Iora Intraday", overlay = true, max_labels_count = 500, max_lines_count = 500, calc_bars_count = 5000)

// =============================================================================
// S1 — TYPES
// =============================================================================

type LightZone
    float   top         = 0.0
    float   bottom      = 0.0
    bool    is_supply   = false
    bool    is_hh_or_ll = false
    string  label_txt   = ""
    int     origin_time = 0
    bool    is_broken   = false
    int     break_time  = 0

type TFState
    int     bias            = 0
    int     prev_bias       = 0
    float   last_sup_top    = na
    float   last_sup_bot    = na
    float   last_dem_top    = na
    float   last_dem_bot    = na
    string  last_sup_cls    = ""
    string  last_dem_cls    = ""
    float   prev_sup_top    = na
    float   prev_dem_bot    = na
    string  last_event      = ""
    int     last_event_dir  = 0
    int     last_event_time = na
    int     zone_count      = 0

// =============================================================================
// S2 — INPUTS
// =============================================================================

string GRP_ZONE = "Zone Detection"
float  i_doji   = input.float(5.0, "Doji Body %", group = GRP_ZONE, minval = 0.1, maxval = 50.0)

string GRP_AGE   = "Zone Age (max bars per TF)"
int    i_age_m1  = input.int(50, "M1",  group = GRP_AGE, minval = 1)
int    i_age_m5  = input.int(50, "M5",  group = GRP_AGE, minval = 1)
int    i_age_m15 = input.int(50, "M15", group = GRP_AGE, minval = 1)
int    i_age_h1  = input.int(50, "H1",  group = GRP_AGE, minval = 1)
int    i_age_h4  = input.int(50, "H4",  group = GRP_AGE, minval = 1)
int    i_age_d   = input.int(50, "D",   group = GRP_AGE, minval = 1)

string GRP_DISP  = "Display"
bool   i_dash    = input.bool(true, "Show Dashboard", group = GRP_DISP)
string i_dash_pos = input.string("Top Right", "Dashboard Position", options = ["Top Right", "Top Left", "Bottom Right", "Bottom Left"], group = GRP_DISP)
bool   i_signals = input.bool(true, "Show Entry Signals", group = GRP_DISP)
bool   i_roles   = input.bool(true, "Show Zone Roles", group = GRP_DISP)
```

- [ ] **Step 2: Add helper functions (tf_max_age, tf_label) below S2**

```pine
// =============================================================================
// S2b — HELPERS
// =============================================================================

tf_max_age(string tf) =>
    int sec = timeframe.in_seconds(tf)
    int out = sec <= 60 ? i_age_m1 : sec <= 300 ? i_age_m5 : sec <= 900 ? i_age_m15 : sec <= 3600 ? i_age_h1 : sec <= 14400 ? i_age_h4 : i_age_d
    out

tf_label(string tf) =>
    int sec = timeframe.in_seconds(tf)
    string out = sec <= 60 ? "M1" : sec <= 300 ? "M5" : sec <= 900 ? "M15" : sec <= 3600 ? "H1" : sec <= 14400 ? "H4" : "D"
    out
```

- [ ] **Step 3: Add a temporary debug plot so the script compiles**

```pine
// TEMP — remove after S3 is added
plot(close, "debug", display = display.none)
```

- [ ] **Step 4: Verify compilation**

Copy the full file content to TradingView Pine Editor. Click "Add to chart" on any M1 chart. Expected: compiles without errors. No visual output except the indicator name in the chart panel.

If compilation fails, check for: implicit typing, reserved keyword use, missing field defaults on UDTs.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): scaffold S1 types + S2 inputs"
```

---

### Task 2: S3 — HA Detection + Data Requests

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

**Reference:** `iora_structure.pine:99-179` for the base `ha_detect()`. This task copies that function and extends the return tuple from 7 to 9 values.

- [ ] **Step 1: Add ha_detect() function after S2b helpers**

Copy `ha_detect()` from `iora_structure.pine` (lines 99-179). Apply these modifications in order:

**Step 1a:** Copy the function verbatim.

**Step 1b:** Add two new `var float` declarations and `max_bars_back` calls for ALL `var` variables. Place immediately after the existing `var` declarations block (after line ~118):
```pine
    var float out_prev_sup = na
    var float out_prev_dem = na
    // max_bars_back on all var series (required inside request.security)
    max_bars_back(prev_run_hi, 5000)
    max_bars_back(prev_run_lo, 5000)
    max_bars_back(haO, 5000)
    max_bars_back(out_prev_sup, 5000)
    max_bars_back(out_prev_dem, 5000)
```

**Step 1c:** In the DEMAND block (red→blue), BEFORE `prev_run_lo := run_lo_ohlc`, add:
```pine
        out_prev_dem := prev_run_lo
```

**Step 1d:** In the SUPPLY block (blue→red), BEFORE `prev_run_hi := run_hi_ohlc`, add:
```pine
        out_prev_sup := prev_run_hi
```

**Step 1e:** Change the return tuple from 7 to 9 values:
```pine
    [fire, ztop, zbot, is_sup, zt_origin, hi1_txt, lo1_txt, out_prev_sup, out_prev_dem]
```

Section header:
```pine
// =============================================================================
// S3 — HA DETECTION (extended — adds prev_sup_top, prev_dem_bot for cross-TF)
// =============================================================================
```

- [ ] **Step 2: Add 6 request.security() calls after ha_detect()**

```pine
string _base_sym = ticker.standard(syminfo.tickerid)

[fd_raw,  ztd,  zbd,  sd,  tmd,  hid,  lod,  psd,  pdd]  = request.security(_base_sym, "1D",  ha_detect(i_doji))
[fh4_raw, zth4, zbh4, sh4, tmh4, hih4, loh4, psh4, pdh4] = request.security(_base_sym, "240", ha_detect(i_doji))
[fh1_raw, zth1, zbh1, sh1, tmh1, hih1, loh1, psh1, pdh1] = request.security(_base_sym, "60",  ha_detect(i_doji))
[fm15_raw,ztm15,zbm15,sm15,tmm15,him15,lom15,psm15,pdm15] = request.security(_base_sym, "15",  ha_detect(i_doji))
[fm5_raw, ztm5, zbm5, sm5, tmm5, him5, lom5, psm5, pdm5]  = request.security(_base_sym, "5",   ha_detect(i_doji))
[fm1_raw, ztm1, zbm1, sm1, tmm1, him1, lom1, psm1, pdm1]  = request.security(_base_sym, "1",   ha_detect(i_doji))

// Edge detection — fire only once per HTF event
bool fd   = fd_raw   and not fd_raw[1]
bool fh4  = fh4_raw  and not fh4_raw[1]
bool fh1  = fh1_raw  and not fh1_raw[1]
bool fm15 = fm15_raw and not fm15_raw[1]
bool fm5  = fm5_raw  and not fm5_raw[1]
bool fm1  = fm1_raw  and not fm1_raw[1]
```

- [ ] **Step 3: Replace debug plot with fire event debug plots**

Remove the temporary `plot(close, ...)` line. Add:
```pine
// TEMP debug — shows zone fire events per TF
plotchar(fd,   "D fire",   "D", location.abovebar, size = size.tiny, display = display.none)
plotchar(fh4,  "H4 fire",  "4", location.abovebar, size = size.tiny, display = display.none)
plotchar(fh1,  "H1 fire",  "1", location.abovebar, size = size.tiny, display = display.none)
plotchar(fm15, "M15 fire", "F", location.abovebar, size = size.tiny, display = display.none)
plotchar(fm5,  "M5 fire",  "5", location.abovebar, size = size.tiny, display = display.none)
plotchar(fm1,  "M1 fire",  "m", location.abovebar, size = size.tiny, display = display.none)
```

- [ ] **Step 4: Verify compilation**

TradingView Pine Editor → "Add to chart" on M1. Expected: compiles, fire chars appear above bars on HA transitions. Check that H1 and H4 fires appear at correct moments (compare to `iora_zones.pine` running on same chart).

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S3 ha_detect + 6 request.security calls"
```

---

### Task 3: S4 — Zone State Management

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

**Reference:** `iora_structure.pine:210-275` for `manage_zones()` method.

- [ ] **Step 1: Add manage_zones() method and 6 zone arrays**

Copy `manage_zones()` from `iora_structure.pine:210-275`. Apply these 3 changes:

1. **Remove `tf_idx` from parameter list:** Change `manage_zones(..., string tf_str, int tf_idx)` to `manage_zones(..., string tf_str)`
2. **Remove `tf_idx` from `LightZone.new()` call:** On line ~250, change `LightZone.new(ztop, zbot, is_sup, is_hh_ll, cls_txt, z_time, false, 0, tf_idx)` to `LightZone.new(ztop, zbot, is_sup, is_hh_ll, cls_txt, z_time, false, 0)`
3. **Keep everything else:** Expiry check, body-close break detection, new zone push, count overflow (20/20 cap) — all identical to reference.

The method signature after changes:
```pine
method manage_zones(array<LightZone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, string tf_str) =>
```

Return tuple unchanged: `[did_break, brk_is_supply, brk_is_hh_or_ll, brk_label, brk_price, brk_origin, brk_top, brk_bot]`.

```pine
// =============================================================================
// S4 — ZONE STATE MANAGEMENT
// =============================================================================

var array<LightZone> zones_d   = array.new<LightZone>()
var array<LightZone> zones_h4  = array.new<LightZone>()
var array<LightZone> zones_h1  = array.new<LightZone>()
var array<LightZone> zones_m15 = array.new<LightZone>()
var array<LightZone> zones_m5  = array.new<LightZone>()
var array<LightZone> zones_m1  = array.new<LightZone>()
```

- [ ] **Step 2: Add TFState instances and zone fire → TFState update logic**

```pine
var TFState st_d   = TFState.new()
var TFState st_h4  = TFState.new()
var TFState st_h1  = TFState.new()
var TFState st_m15 = TFState.new()
var TFState st_m5  = TFState.new()
var TFState st_m1  = TFState.new()
```

For each TF, on fire event, update TFState fields per spec S4:
```pine
if fd
    if sd
        st_d.prev_sup_top := st_d.last_sup_top
        st_d.last_sup_top := ztd
        st_d.last_sup_bot := zbd
        st_d.last_sup_cls := hid
    else
        st_d.prev_dem_bot := st_d.last_dem_bot
        st_d.last_dem_top := ztd
        st_d.last_dem_bot := zbd
        st_d.last_dem_cls := lod
    st_d.zone_count += 1
// repeat for fh4, fh1, fm15, fm5, fm1
```

- [ ] **Step 3: Wire manage_zones() execution for all 6 TFs**

```pine
[brkd,  brkd_sup,  brkd_hh,  brkd_lbl,  brkd_px,  brkd_org,  brkd_t,  brkd_b]  = zones_d.manage_zones(fd,   ztd,   zbd,   sd,   tmd,   hid,   lod,   "1D")
[brkh4, brkh4_sup, brkh4_hh, brkh4_lbl, brkh4_px, brkh4_org, brkh4_t, brkh4_b] = zones_h4.manage_zones(fh4,  zth4,  zbh4,  sh4,  tmh4,  hih4,  loh4,  "240")
[brkh1, brkh1_sup, brkh1_hh, brkh1_lbl, brkh1_px, brkh1_org, brkh1_t, brkh1_b] = zones_h1.manage_zones(fh1,  zth1,  zbh1,  sh1,  tmh1,  hih1,  loh1,  "60")
[brkm15,brkm15_sup,brkm15_hh,brkm15_lbl,brkm15_px,brkm15_org,brkm15_t,brkm15_b] = zones_m15.manage_zones(fm15, ztm15, zbm15, sm15, tmm15, him15, lom15, "15")
[brkm5, brkm5_sup, brkm5_hh, brkm5_lbl, brkm5_px, brkm5_org, brkm5_t, brkm5_b] = zones_m5.manage_zones(fm5,  ztm5,  zbm5,  sm5,  tmm5,  him5,  lom5,  "5")
[brkm1, brkm1_sup, brkm1_hh, brkm1_lbl, brkm1_px, brkm1_org, brkm1_t, brkm1_b] = zones_m1.manage_zones(fm1,  ztm1,  zbm1,  sm1,  tmm1,  him1,  lom1,  "1")
```

- [ ] **Step 4: Add broken zone cleanup (same pattern as iora_structure.pine S9)**

```pine
method remove_broken(array<LightZone> zones) =>
    if zones.size() > 0
        for i = zones.size() - 1 to 0
            LightZone z = zones.get(i)
            if z.is_broken
                zones.remove(i)

// (called at end of script, after all break detection is done)
```

- [ ] **Step 5: Verify compilation**

TradingView → compile. Expected: same fire events as before, plus zone arrays now populating and breaking. No visual change yet (zones are lightweight, no boxes).

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S4 zone state management + TFState population"
```

---

### Task 4: S5 — Bias + Structure Detection

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

**Reference:** `iora_structure.pine:312-579` for bias tracking, BOS/CHoCH classification, external break detection, and cross-TF propagation.

- [ ] **Step 1: Add internal break → bias update logic**

After the `manage_zones()` calls, add bias tracking for each TF. Pattern per TF:

```pine
// =============================================================================
// S5 — BIAS + STRUCTURE DETECTION
// =============================================================================

// --- Internal breaks: update bias from own-TF zone breaks ---
if brkd
    st_d.prev_bias := st_d.bias
    int d_dir = brkd_sup ? 1 : -1
    st_d.last_event := (st_d.prev_bias == 0 or d_dir == st_d.prev_bias) ? "iBOS" : "iCHoCH"
    st_d.last_event_dir := d_dir
    st_d.last_event_time := time
    st_d.bias := d_dir
// repeat for brkh4, brkh1, brkm15, brkm5, brkm1
```

- [ ] **Step 2: Add check_external_break() function**

Copy `check_external_break()` from `iora_structure.pine:462-491`. No modifications needed — it takes an `array<LightZone>` and checks for body-close breaks.

- [ ] **Step 3: Wire external break detection for 5 child→parent pairs**

```pine
// --- External breaks: child checks parent zones ---
[ebrkm1,  ebrkm1_sup,  ebrkm1_hh,  _,_,_,_,_] = check_external_break(zones_m5)
[ebrkm5,  ebrkm5_sup,  ebrkm5_hh,  _,_,_,_,_] = check_external_break(zones_m15)
[ebrkm15, ebrkm15_sup, ebrkm15_hh, _,_,_,_,_] = check_external_break(zones_h1)
[ebrkh1,  ebrkh1_sup,  ebrkh1_hh,  _,_,_,_,_] = check_external_break(zones_h4)
[ebrkh4,  ebrkh4_sup,  ebrkh4_hh,  _,_,_,_,_] = check_external_break(zones_d)
```

On external break, update TFState (external overrides internal):
```pine
if ebrkm1
    int dir = ebrkm1_sup ? 1 : -1
    st_m1.prev_bias := st_m1.bias
    st_m1.last_event := (st_m1.prev_bias == 0 or dir == st_m1.prev_bias) ? "eBOS" : "eCHoCH"
    st_m1.last_event_dir := dir
    st_m1.last_event_time := time
    st_m1.bias := dir
    st_m1.zone_count := 0
// repeat for ebrkm5, ebrkm15, ebrkh1, ebrkh4
```

- [ ] **Step 4: Add cross-TF propagation (H1→H4, H4→D early detection)**

```pine
// --- Cross-TF propagation: H1 zone fires → check against H4 boundaries ---
// HH/LL = BOS (trend continues), LH/HL = CHoCH (reversal signal)
if fh1 and not na(st_h4.prev_sup_top) and not na(st_h4.prev_dem_bot)
    if sh1
        // H1 supply fired — compare top to prev H4 supply top
        st_h4.prev_bias := st_h4.bias
        if zth1 > st_h4.prev_sup_top
            // H4 HH detected early (new high exceeded previous)
            int h4_dir = 1
            st_h4.last_event := (st_h4.prev_bias == 0 or h4_dir == st_h4.prev_bias) ? "iBOS" : "iCHoCH"
            st_h4.last_event_dir := h4_dir
            st_h4.last_event_time := time
            st_h4.bias := h4_dir
            st_h1.zone_count := 0
        else
            // H4 LH detected early (high failed to exceed previous)
            int h4_dir = 1
            st_h4.last_event := (st_h4.prev_bias == 0 or h4_dir == st_h4.prev_bias) ? "iBOS" : "iCHoCH"
            st_h4.last_event_dir := h4_dir
            st_h4.last_event_time := time
            // LH does NOT update bias — it's a corrective event, not a structural one
    else
        // H1 demand fired — compare bot to prev H4 demand bot
        st_h4.prev_bias := st_h4.bias
        if zbh1 < st_h4.prev_dem_bot
            // H4 LL detected early (new low exceeded previous)
            int h4_dir = -1
            st_h4.last_event := (st_h4.prev_bias == 0 or h4_dir == st_h4.prev_bias) ? "iBOS" : "iCHoCH"
            st_h4.last_event_dir := h4_dir
            st_h4.last_event_time := time
            st_h4.bias := h4_dir
            st_h1.zone_count := 0
        else
            // H4 HL detected early (low held above previous)
            int h4_dir = -1
            st_h4.last_event := (st_h4.prev_bias == 0 or h4_dir == st_h4.prev_bias) ? "iBOS" : "iCHoCH"
            st_h4.last_event_dir := h4_dir
            st_h4.last_event_time := time
            // HL does NOT update bias — corrective event

// Same pattern for H4→D propagation
if fh4 and not na(st_d.prev_sup_top) and not na(st_d.prev_dem_bot)
    if sh4
        st_d.prev_bias := st_d.bias
        if zth4 > st_d.prev_sup_top
            int d_dir = 1
            st_d.last_event := (st_d.prev_bias == 0 or d_dir == st_d.prev_bias) ? "iBOS" : "iCHoCH"
            st_d.last_event_dir := d_dir
            st_d.last_event_time := time
            st_d.bias := d_dir
            st_h4.zone_count := 0
        else
            int d_dir = 1
            st_d.last_event := (st_d.prev_bias == 0 or d_dir == st_d.prev_bias) ? "iBOS" : "iCHoCH"
            st_d.last_event_dir := d_dir
            st_d.last_event_time := time
    else
        st_d.prev_bias := st_d.bias
        if zbh4 < st_d.prev_dem_bot
            int d_dir = -1
            st_d.last_event := (st_d.prev_bias == 0 or d_dir == st_d.prev_bias) ? "iBOS" : "iCHoCH"
            st_d.last_event_dir := d_dir
            st_d.last_event_time := time
            st_d.bias := d_dir
            st_h4.zone_count := 0
        else
            int d_dir = -1
            st_d.last_event := (st_d.prev_bias == 0 or d_dir == st_d.prev_bias) ? "iBOS" : "iCHoCH"
            st_d.last_event_dir := d_dir
            st_d.last_event_time := time
```

- [ ] **Step 5: Verify compilation + validate bias visually**

Add temporary debug plots for bias:
```pine
plot(st_d.bias,  "D bias",  display = display.status_line)
plot(st_h4.bias, "H4 bias", display = display.status_line)
plot(st_h1.bias, "H1 bias", display = display.status_line)
```

Compare bias values against `iora_structure.pine`'s BOS/CHoCH events on the same chart. They should match.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S5 bias + structure detection (internal, external, cross-TF)"
```

---

### Task 5: S6 — Zone Counters + Exhaustion Clock

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Add H4 zone counter variables and counting logic**

```pine
// =============================================================================
// S6 — ZONE COUNTERS + EXHAUSTION CLOCK
// =============================================================================

var int h4_impulse_count   = 0
var int h4_correction_count = 0

// H4 zone counter — relative to D bias
if fh4
    if st_d.bias == -1
        if sh4
            h4_impulse_count += 1
        else
            h4_correction_count += 1
    else if st_d.bias == 1
        if not sh4
            h4_impulse_count += 1
        else
            h4_correction_count += 1

int h4_zone_count = h4_impulse_count + h4_correction_count
```

Reset H4 counters on D structural event (already handled in S5 cross-TF — add counter reset there):
```pine
// In S5 H4→D propagation block, add:
h4_impulse_count := 0
h4_correction_count := 0
```

- [ ] **Step 2: Add H1 zone counter variables and counting logic**

```pine
var int h1_impulse_count   = 0
var int h1_correction_count = 0

if fh1
    if st_h4.bias == -1
        if sh1
            h1_impulse_count += 1
        else
            h1_correction_count += 1
    else if st_h4.bias == 1
        if not sh1
            h1_impulse_count += 1
        else
            h1_correction_count += 1

int h1_zone_count = h1_impulse_count + h1_correction_count
```

Reset H1 counters when H4 structural event fires (in S5 H1→H4 propagation and external break blocks):
```pine
h1_impulse_count := 0
h1_correction_count := 0
```

- [ ] **Step 3: Add H1 phase detection**

```pine
var string h1_phase = ""

// Phase updates on both internal and external H1 events
bool h1_is_bos = st_h1.last_event == "iBOS" or st_h1.last_event == "eBOS"
bool h1_is_choch = st_h1.last_event == "iCHoCH" or st_h1.last_event == "eCHoCH"

if h1_is_bos and st_h1.last_event_dir == st_h4.bias
    h1_phase := "impulse"
else if h1_is_choch and st_h1.last_event_dir != st_h4.bias
    h1_phase := "correction"
// External BOS/CHoCH are treated the same — a structural event is a structural event
// regardless of whether it was detected internally or via parent zone break
```

- [ ] **Step 4: Add terminal detection + counter-zone proximity**

```pine
bool h1_terminal = h1_zone_count >= 8 or (h1_impulse_count >= 5 and h1_correction_count >= 3)

// Counter-zone proximity: H4 demand/supply beyond D structural level
bool at_counter_zone = false
if h1_zone_count >= 6
    if st_h4.bias == -1 and not na(st_h4.last_dem_bot) and not na(st_d.last_dem_bot)
        at_counter_zone := st_h4.last_dem_bot < st_d.last_dem_bot and close >= st_h4.last_dem_bot and close <= st_h4.last_dem_top
    else if st_h4.bias == 1 and not na(st_h4.last_sup_top) and not na(st_d.last_sup_top)
        at_counter_zone := st_h4.last_sup_top > st_d.last_sup_top and close >= st_h4.last_sup_bot and close <= st_h4.last_sup_top
```

- [ ] **Step 5: Verify compilation + add debug plots**

```pine
plot(h4_zone_count,  "H4 count",  display = display.status_line)
plot(h1_zone_count,  "H1 count",  display = display.status_line)
plot(h1_terminal ? 1 : 0, "H1 terminal", display = display.status_line)
```

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S6 zone counters + exhaustion clock"
```

---

### Task 6: S7 — Context Mode

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Add context mode computation**

```pine
// =============================================================================
// S7 — CONTEXT MODE
// =============================================================================

// No `var` — these are recomputed every bar from the state tuple
string context_mode = "SKIP"
int    context_dir  = 0

// FLIP (highest priority)
bool flip_conditions = h1_terminal and at_counter_zone and st_h1.last_event == "iCHoCH" and st_h1.last_event_dir != st_h4.bias
if flip_conditions
    context_mode := "FLIP"
    context_dir  := st_h4.bias == -1 ? 1 : -1

// RIDE
else if st_d.bias != 0 and st_h4.bias == st_d.bias and h4_zone_count <= 5 and h1_phase == "correction"
    context_mode := "RIDE"
    context_dir  := st_d.bias

// SCALP
else if st_h1.last_event == "iBOS" and (time - st_h1.last_event_time) < 3600000 * 4
    context_mode := "SCALP"
    context_dir  := st_h1.last_event_dir * -1

// SKIP (default)
else
    context_mode := "SKIP"
    context_dir  := 0
```

Note: SCALP window is 4 hours (4 * 3600000 ms). This prevents stale H1 BOS events from triggering SCALP mode indefinitely.

- [ ] **Step 2: Verify compilation + debug**

```pine
// TEMP debug
plotchar(context_mode == "RIDE", "RIDE",  "R", location.bottom, color.green, display = display.all)
plotchar(context_mode == "FLIP", "FLIP",  "F", location.bottom, color.orange, display = display.all)
plotchar(context_mode == "SCALP","SCALP", "S", location.bottom, color.teal, display = display.all)
```

- [ ] **Step 3: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S7 context mode (RIDE/FLIP/SCALP/SKIP)"
```

---

### Task 7: S8 — Entry Cascade

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Add containment check helper**

```pine
// =============================================================================
// S8 — ENTRY CASCADE
// =============================================================================

is_inside(float price, float zone_bot, float zone_top) =>
    not na(price) and not na(zone_bot) and not na(zone_top) and price >= zone_bot and price <= zone_top
```

- [ ] **Step 2: Add cascade state variables**

```pine
var int    cascade_step = 0
var string cascade_mode = ""
var int    cascade_dir  = 0
var string prev_context = "SKIP"

// Reset cascade on mode change
if context_mode != prev_context
    cascade_step := 0
    cascade_mode := ""
    cascade_dir  := 0
prev_context := context_mode
```

- [ ] **Step 3: Add RIDE SHORT cascade (5 steps)**

```pine
if context_mode == "RIDE" and context_dir == -1
    // Step 1: H1 LH fires during correction
    if cascade_step == 0 and fh1 and sh1 and st_h1.last_sup_cls == "LH" and h1_phase == "correction"
        cascade_step := 1
        cascade_mode := "RIDE"
        cascade_dir  := -1

    // Step 2: H1 LH overlaps H4 supply
    if cascade_step == 1 and is_inside(st_h1.last_sup_top, st_h4.last_sup_bot, st_h4.last_sup_top)
        cascade_step := 2

    // Step 3: M15 LH inside H1 supply
    if cascade_step == 2 and fm15 and sm15 and st_m15.last_sup_cls == "LH" and is_inside(st_m15.last_sup_top, st_h1.last_sup_bot, st_h1.last_sup_top)
        cascade_step := 3

    // Step 4: M5 LH inside M15 demand (correction failing)
    if cascade_step == 3 and fm5 and sm5 and st_m5.last_sup_cls == "LH" and is_inside(st_m5.last_sup_top, st_m15.last_dem_bot, st_m15.last_dem_top)
        cascade_step := 4

    // Step 5: M1 CHoCH (LH) inside M5 demand — ENTRY
    if cascade_step == 4 and fm1 and sm1 and st_m1.last_sup_cls == "LH" and is_inside(st_m1.last_sup_top, st_m5.last_dem_bot, st_m5.last_dem_top)
        cascade_step := 5
```

- [ ] **Step 4: Add RIDE LONG cascade**

```pine
if context_mode == "RIDE" and context_dir == 1
    // Step 1: H1 HL fires during correction
    if cascade_step == 0 and fh1 and not sh1 and st_h1.last_dem_cls == "HL" and h1_phase == "correction"
        cascade_step := 1
        cascade_mode := "RIDE"
        cascade_dir  := 1

    // Step 2: H1 HL overlaps H4 demand
    if cascade_step == 1 and is_inside(st_h1.last_dem_bot, st_h4.last_dem_bot, st_h4.last_dem_top)
        cascade_step := 2

    // Step 3: M15 HL inside H1 demand
    if cascade_step == 2 and fm15 and not sm15 and st_m15.last_dem_cls == "HL" and is_inside(st_m15.last_dem_bot, st_h1.last_dem_bot, st_h1.last_dem_top)
        cascade_step := 3

    // Step 4: M5 HL inside M15 supply (correction pullback failing — buyers rejecting M15 supply)
    if cascade_step == 3 and fm5 and not sm5 and st_m5.last_dem_cls == "HL" and is_inside(st_m5.last_dem_bot, st_m15.last_sup_bot, st_m15.last_sup_top)
        cascade_step := 4

    // Step 5: M1 CHoCH (HL) inside M5 supply — ENTRY
    if cascade_step == 4 and fm1 and not sm1 and st_m1.last_dem_cls == "HL" and is_inside(st_m1.last_dem_bot, st_m5.last_sup_bot, st_m5.last_sup_top)
        cascade_step := 5
```

- [ ] **Step 5: Add FLIP LONG cascade**

```pine
if context_mode == "FLIP" and context_dir == 1
    // Step 1: H1 HL at counter-zone
    if cascade_step == 0 and fh1 and not sh1 and st_h1.last_dem_cls == "HL" and at_counter_zone
        cascade_step := 1
        cascade_mode := "FLIP"
        cascade_dir  := 1

    // Step 2: H1 HH fires (BOS confirms)
    if cascade_step == 1 and st_h1.last_event == "iBOS" and st_h1.last_event_dir == 1
        cascade_step := 2

    // Steps 3-5: same as RIDE LONG steps 3-5
    if cascade_step == 2 and fm15 and not sm15 and st_m15.last_dem_cls == "HL" and is_inside(st_m15.last_dem_bot, st_h1.last_dem_bot, st_h1.last_dem_top)
        cascade_step := 3
    if cascade_step == 3 and fm5 and not sm5 and st_m5.last_dem_cls == "HL" and is_inside(st_m5.last_dem_bot, st_m15.last_sup_bot, st_m15.last_sup_top)
        cascade_step := 4
    if cascade_step == 4 and fm1 and not sm1 and st_m1.last_dem_cls == "HL" and is_inside(st_m1.last_dem_bot, st_m5.last_sup_bot, st_m5.last_sup_top)
        cascade_step := 5
```

- [ ] **Step 6: Add FLIP SHORT cascade**

```pine
if context_mode == "FLIP" and context_dir == -1
    // Step 1: H1 LH at counter-zone
    if cascade_step == 0 and fh1 and sh1 and st_h1.last_sup_cls == "LH" and at_counter_zone
        cascade_step := 1
        cascade_mode := "FLIP"
        cascade_dir  := -1

    // Step 2: H1 LL fires (BOS confirms)
    if cascade_step == 1 and st_h1.last_event == "iBOS" and st_h1.last_event_dir == -1
        cascade_step := 2

    // Step 3: M15 LH inside H1 supply
    if cascade_step == 2 and fm15 and sm15 and st_m15.last_sup_cls == "LH" and is_inside(st_m15.last_sup_top, st_h1.last_sup_bot, st_h1.last_sup_top)
        cascade_step := 3

    // Step 4: M5 LH inside M15 demand (correction failing)
    if cascade_step == 3 and fm5 and sm5 and st_m5.last_sup_cls == "LH" and is_inside(st_m5.last_sup_top, st_m15.last_dem_bot, st_m15.last_dem_top)
        cascade_step := 4

    // Step 5: M1 CHoCH (LH) inside M5 demand — ENTRY
    if cascade_step == 4 and fm1 and sm1 and st_m1.last_sup_cls == "LH" and is_inside(st_m1.last_sup_top, st_m5.last_dem_bot, st_m5.last_dem_top)
        cascade_step := 5
```

- [ ] **Step 7: Add SCALP cascade (3 steps)**

```pine
if context_mode == "SCALP"
    int scalp_dir = context_dir
    if cascade_step == 0
        cascade_step := 1
        cascade_mode := "SCALP"
        cascade_dir  := scalp_dir

    // Step 2: price inside H1 zone
    if cascade_step == 1
        bool in_zone = scalp_dir == -1 ? is_inside(close, st_h1.last_dem_bot, st_h1.last_dem_top) : is_inside(close, st_h1.last_sup_bot, st_h1.last_sup_top)
        if in_zone
            cascade_step := 2

    // Step 3: M1 CHoCH opposing BOS direction
    if cascade_step == 2 and fm1
        bool m1_trigger = scalp_dir == -1 ? (sm1 and st_m1.last_sup_cls == "LH") : (not sm1 and st_m1.last_dem_cls == "HL")
        if m1_trigger
            cascade_step := 3
```

- [ ] **Step 8: Add entry signal output + plotshape**

```pine
// Entry signal fires on final cascade step
// IMPORTANT: max_step must be at global scope — it is referenced by the dashboard (S9)
int max_step = cascade_mode == "SCALP" ? 3 : 5
bool entry_fire = cascade_step >= max_step

var int    entry_dir   = 0
var float  entry_price = na
var string entry_mode  = ""

if entry_fire
    entry_dir   := cascade_dir
    entry_price := cascade_dir == 1 ? st_m1.last_dem_top : st_m1.last_sup_bot
    entry_mode  := cascade_mode
    cascade_step := 0  // reset for next cascade

// Visual markers
plotshape(i_signals and entry_fire and entry_dir == 1,  "Long Entry",  shape.triangleup,   location.belowbar, color.new(#4CAF50, 0), size = size.small)
plotshape(i_signals and entry_fire and entry_dir == -1, "Short Entry", shape.triangledown, location.abovebar, color.new(#F44336, 0), size = size.small)
```

- [ ] **Step 9: Add Phase 1 exit signals**

```pine
// Exit signal 1: M15 CHoCH opposing inside H1 zone
bool m15_opposing = st_m15.last_event == "iCHoCH" and st_m15.last_event_dir != st_h1.bias
bool m15_inside_h1 = st_h1.bias == -1 ? is_inside(close, st_h1.last_dem_bot, st_h1.last_dem_top) : is_inside(close, st_h1.last_sup_bot, st_h1.last_sup_top)
bool exit_m15 = m15_opposing and m15_inside_h1

// Exit signal 2: H1 impulse exhausting
bool exit_exhaust = h1_impulse_count >= 5 and h1_phase == "correction"

plotshape(i_signals and exit_m15,     "M15 Exit",     shape.xcross, location.abovebar, color.new(#FFD600, 0), size = size.tiny)
plotshape(i_signals and exit_exhaust, "Exhaust Exit",  shape.xcross, location.abovebar, color.new(#F44336, 0), size = size.tiny)
```

- [ ] **Step 10: Verify compilation**

TradingView → compile on M1 chart. Expected: entry triangles appear when the full cascade completes. Debug context chars from S7 should show mode is active when entries fire.

- [ ] **Step 11: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S8 entry cascade + exit signals"
```

---

### Task 8: S9 — Dashboard Table

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Add dashboard table creation**

```pine
// =============================================================================
// S9 — DASHBOARD TABLE
// =============================================================================

var table dash = na

if i_dash
    string pos = switch i_dash_pos
        "Top Right"    => position.top_right
        "Top Left"     => position.top_left
        "Bottom Right" => position.bottom_right
        "Bottom Left"  => position.bottom_left
        => position.top_right

    if na(dash)
        dash := table.new(pos, 4, 8, border_width = 1)
```

- [ ] **Step 2: Add header row**

```pine
    if barstate.islast and not na(dash)
        // Header
        table.cell(dash, 0, 0, "Layer", bgcolor = color.new(#424242, 0), text_color = color.white, text_size = size.tiny)
        table.cell(dash, 1, 0, "Bias",  bgcolor = color.new(#424242, 0), text_color = color.white, text_size = size.tiny)
        table.cell(dash, 2, 0, "Count", bgcolor = color.new(#424242, 0), text_color = color.white, text_size = size.tiny)
        table.cell(dash, 3, 0, "Phase", bgcolor = color.new(#424242, 0), text_color = color.white, text_size = size.tiny)
```

- [ ] **Step 3: Add helper functions for bias text + color (at global scope, BEFORE the `if barstate.islast` block)**

```pine
bias_text(int b) =>
    string out = b == 1 ? "BULL ▲" : b == -1 ? "BEAR ▼" : "—"
    out

bias_color(int b) =>
    color out = b == 1 ? color.new(#4CAF50, 0) : b == -1 ? color.new(#F44336, 0) : color.new(#9E9E9E, 0)
    out
```

- [ ] **Step 4: Add TF rows (D, H4, H1, M15, M5, M1)**

```pine
        // D row
        table.cell(dash, 0, 1, "D",   text_size = size.tiny)
        table.cell(dash, 1, 1, bias_text(st_d.bias),  text_color = bias_color(st_d.bias), text_size = size.tiny)
        table.cell(dash, 2, 1, "—",   text_size = size.tiny)
        table.cell(dash, 3, 1, "—",   text_size = size.tiny)

        // H4 row
        table.cell(dash, 0, 2, "H4",  text_size = size.tiny)
        table.cell(dash, 1, 2, bias_text(st_h4.bias), text_color = bias_color(st_h4.bias), text_size = size.tiny)
        table.cell(dash, 2, 2, str.tostring(h4_zone_count) + "/8", text_size = size.tiny)
        string h4_phase = h4_zone_count >= 8 ? "terminal" : (st_h4.last_event_dir == st_d.bias ? "impulse" : "correction")
        table.cell(dash, 3, 2, h4_phase, text_size = size.tiny)

        // H1 row
        table.cell(dash, 0, 3, "H1",  text_size = size.tiny)
        table.cell(dash, 1, 3, bias_text(st_h1.bias), text_color = bias_color(st_h1.bias), text_size = size.tiny)
        table.cell(dash, 2, 3, str.tostring(h1_impulse_count) + "i+" + str.tostring(h1_correction_count) + "c", text_size = size.tiny)
        string h1_disp = h1_terminal ? "TERMINAL" : h1_phase
        table.cell(dash, 3, 3, h1_disp, text_color = h1_terminal ? color.new(#FF6D00, 0) : color.white, text_size = size.tiny)

        // M15 row
        bool m15_nested = is_inside(st_m15.last_sup_top, st_h1.last_sup_bot, st_h1.last_sup_top) or is_inside(st_m15.last_dem_bot, st_h1.last_dem_bot, st_h1.last_dem_top)
        table.cell(dash, 0, 4, "M15", text_size = size.tiny)
        table.cell(dash, 1, 4, bias_text(st_m15.bias), text_color = bias_color(st_m15.bias), text_size = size.tiny)
        table.cell(dash, 2, 4, "—",   text_size = size.tiny)
        table.cell(dash, 3, 4, m15_nested ? "nested" : "—", text_size = size.tiny)

        // M5 row
        table.cell(dash, 0, 5, "M5",  text_size = size.tiny)
        table.cell(dash, 1, 5, bias_text(st_m5.bias), text_color = bias_color(st_m5.bias), text_size = size.tiny)
        table.cell(dash, 2, 5, "—",   text_size = size.tiny)
        table.cell(dash, 3, 5, "—",   text_size = size.tiny)

        // M1 row
        string m1_phase = cascade_step >= max_step ? "TRIGGER" : "waiting"
        table.cell(dash, 0, 6, "M1",  text_size = size.tiny)
        table.cell(dash, 1, 6, bias_text(st_m1.bias), text_color = bias_color(st_m1.bias), text_size = size.tiny)
        table.cell(dash, 2, 6, "—",   text_size = size.tiny)
        table.cell(dash, 3, 6, m1_phase, text_color = m1_phase == "TRIGGER" ? color.new(#FFD600, 0) : color.white, text_size = size.tiny)
```

- [ ] **Step 5: Add MODE row**

```pine
        // MODE row
        string mode_txt = context_mode
        if context_mode == "RIDE"
            mode_txt := context_dir == 1 ? "RIDE LONG" : "RIDE SHORT"
        else if context_mode == "FLIP"
            mode_txt := context_dir == 1 ? "FLIP LONG" : "FLIP SHORT"
        else if context_mode == "SCALP"
            mode_txt := context_dir == 1 ? "SCALP LONG" : "SCALP SHORT"

        color mode_bg = switch context_mode
            "RIDE"  => color.new(#4CAF50, 70)
            "FLIP"  => color.new(#FF6D00, 70)
            "SCALP" => color.new(#26C6DA, 70)
            => color.new(#9E9E9E, 70)

        table.cell(dash, 0, 7, "MODE", bgcolor = mode_bg, text_size = size.tiny)
        table.cell(dash, 1, 7, mode_txt, bgcolor = mode_bg, text_size = size.tiny)
        table.cell(dash, 2, 7, "", bgcolor = mode_bg, text_size = size.tiny)
        string step_txt = cascade_step > 0 ? str.tostring(cascade_step) + "/" + str.tostring(max_step) : "—"
        table.cell(dash, 3, 7, step_txt, bgcolor = mode_bg, text_size = size.tiny)
```

- [ ] **Step 6: Remove all temporary debug plots from previous tasks**

Search for all lines containing `// TEMP` or `display = display.status_line` or `display = display.none` debug plots added in Tasks 2-6. Remove them. The dashboard replaces all debug output.

- [ ] **Step 7: Move broken zone cleanup to end of script**

Ensure `remove_broken()` calls for all 6 zone arrays are the very last lines:
```pine
zones_d.remove_broken()
zones_h4.remove_broken()
zones_h1.remove_broken()
zones_m15.remove_broken()
zones_m5.remove_broken()
zones_m1.remove_broken()
```

- [ ] **Step 8: Final compilation verify**

TradingView → compile on M1 chart. Expected:
- Dashboard table visible in selected corner
- All 6 TF rows showing bias + count + phase
- MODE row showing current context mode
- Entry/exit plotshapes firing when cascade completes
- No debug artifacts remaining

- [ ] **Step 9: Commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): S9 dashboard table + cleanup debug plots"
```

---

### Task 9: Final Validation + Cleanup

**Files:**
- Modify: `tw_indicators/system/iora_intraday.pine`

- [ ] **Step 1: Code review pass — CLAUDE.md compliance**

Check every line for:
- All variables explicitly typed (`float`, `int`, `bool`, `string`, `color`)
- No multiline ternaries (single line or wrapped in parentheses)
- No reserved keywords as variable names (`range`, `time`, `close`, etc.)
- No semicolons as statement separators
- `.get()` results stored in local variables before field assignment
- `request.security()` count = 6 (no accidental additions)
- All UDT fields have explicit defaults

- [ ] **Step 2: Verify on GBPUSD M1 chart**

Add indicator to GBPUSD M1 chart (ICMarkets or similar). Check:
- Dashboard populates with non-na values after sufficient history loads
- H4/H1 bias matches `iora_structure.pine` BOS/CHoCH events
- Zone counts increment on zone fire events
- Context mode changes are visible and logical
- No Pine runtime errors in the console

- [ ] **Step 3: Verify on XAUUSD M1 chart**

Repeat Step 2 on Gold. Different volatility profile — check that zone counts don't overflow and dashboard values stay reasonable.

- [ ] **Step 4: Final commit**

```bash
git add tw_indicators/system/iora_intraday.pine
git commit -m "feat(intraday): final validation pass — CLAUDE.md compliance + chart tested"
```
