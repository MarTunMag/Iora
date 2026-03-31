# Iora Push Zones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified Pine Script v6 indicator that detects HA supply/demand zones across 8 TFs, classifies them as Push/Reversal/Normal with boundary-break validation, and overlays BOS/CHoCH structure classification.

**Architecture:** Single-file indicator built in layers. Copies `ha_detect()` from `iora_zones.pine` template and `track_period()` from `iora_bos_choch.pine` verbatim. Adds push validation (boundary-break rule), reversal tagging, BOS/CHoCH classification, and a dashboard — all in the `process()` method. Each layer compiles cleanly before the next.

**Tech Stack:** Pine Script v6, TradingView

**Spec:** `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md`

---

## File Structure

Single file: `tw_indicators/iora_zones/iora_push_zones.pine`

| Section | Content | Source |
|---------|---------|--------|
| S1 | Inputs (zone detection, timeframes, zone age, colors, dashboard) | New, based on `iora_zones.pine` template inputs + push/reversal color inputs |
| S2 | Zone UDT (extended with `is_push`, `is_reversal`, `struct_cls`, `swing_cls`, `lbl`) | New, based on spec Zone UDT |
| S3 | Helpers (`tf_max_age`, `tf_label`) | Copied from `iora_zones.pine` template |
| S4 | `ha_detect()` — HA zone detection + sequence tracking | Copied verbatim from `iora_zones.pine` template (lines 85–165) |
| S5 | `track_period()` — period high/low tracking + break detection | Copied verbatim from `iora_bos_choch.pine` (lines 45–84) |
| S6 | Zone management (`delete_zone`, `process` with push/reversal/BOS-CHoCH) | New — core logic |
| S7 | Data requests (8 `request.security()` calls) | Based on `iora_zones.pine` template pattern |
| S8 | Edge detection (zone fires + structure breaks + trend state) | New |
| S9 | `track_period()` calls (8 TFs) + zone arrays + per-TF execution | New |
| S10 | Dashboard table | New |

**Reference files to read before each task:**
- `tw_indicators/iora_zones/templates/iora_zones.pine` — base HA zone indicator (314 lines)
- `tw_indicators/iora_zones/iora_bos_choch.pine` — `track_period()` function (255 lines)
- `tw_indicators/system/iora_zones_push_self.pine` — prior push zone indicator (381 lines, for push tagging pattern)
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` — design spec
- `CLAUDE.md` — Pine v6 rules (always)

**Testing approach:** Pine Script has no unit tests. Each task produces a compilable indicator. Paste into TradingView Pine Editor and verify:
1. No compilation errors
2. Zones render correctly on chart
3. Push/reversal tags appear on expected zones
4. Dashboard shows correct state

---

## Task 1: Scaffold — Indicator + Inputs + UDT + Helpers + Core Functions

**Files:**
- Create: `tw_indicators/iora_zones/iora_push_zones.pine`

**Read first:**
- `tw_indicators/iora_zones/templates/iora_zones.pine` (all) — copy inputs pattern, `ha_detect()`, helpers
- `tw_indicators/iora_zones/iora_bos_choch.pine` (lines 45–84) — copy `track_period()`
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` (lines 17–63) — Zone UDT, function specs
- `CLAUDE.md` — Pine v6 rules

This task creates the entire file skeleton: indicator declaration, all inputs, the Zone UDT, helper functions, and both core detection functions. No zone management or execution yet — just the building blocks.

- [ ] **Step 1: Write indicator declaration + S1 Inputs**

```pine
//@version=6
indicator("Iora Push Zones", overlay = true, max_boxes_count = 500, max_labels_count = 500, calc_bars_count = 2000)

// =============================================================================
// S1 — INPUTS
// =============================================================================

string GRP_ZONE  = "Zone Detection"
float  i_doji    = input.float(5.0, "Doji Body %", group = GRP_ZONE, minval = 0.1, maxval = 50.0, tooltip = "Max body/range % to classify as doji candle")

string GRP_TF    = "Timeframes"
bool   i_tf0_on  = input.bool(false, "M1",     group = GRP_TF, inline = "t0")
string i_tf0     = input.timeframe("1",   "",  group = GRP_TF, inline = "t0")
bool   i_tf1_on  = input.bool(false, "M5",     group = GRP_TF, inline = "t1")
string i_tf1     = input.timeframe("5",   "",  group = GRP_TF, inline = "t1")
bool   i_tf2_on  = input.bool(false, "M15",    group = GRP_TF, inline = "t2")
string i_tf2     = input.timeframe("15",  "",  group = GRP_TF, inline = "t2")
bool   i_tf3_on  = input.bool(true,  "H1",     group = GRP_TF, inline = "t3")
string i_tf3     = input.timeframe("60",  "",  group = GRP_TF, inline = "t3")
bool   i_tf4_on  = input.bool(true,  "H4",     group = GRP_TF, inline = "t4")
string i_tf4     = input.timeframe("240", "",  group = GRP_TF, inline = "t4")
bool   i_tf5_on  = input.bool(true,  "D",      group = GRP_TF, inline = "t5")
string i_tf5     = input.timeframe("1D",  "",  group = GRP_TF, inline = "t5")
bool   i_tf6_on  = input.bool(false, "W",      group = GRP_TF, inline = "t6")
string i_tf6     = input.timeframe("1W",  "",  group = GRP_TF, inline = "t6")
bool   i_tf7_on  = input.bool(false, "MN",     group = GRP_TF, inline = "t7")
string i_tf7     = input.timeframe("1M",  "",  group = GRP_TF, inline = "t7")

string GRP_AGE   = "Zone Age (max bars per TF)"
int    i_age_m1  = input.int(50, "M1",  group = GRP_AGE, minval = 1)
int    i_age_m5  = input.int(50, "M5",  group = GRP_AGE, minval = 1)
int    i_age_m15 = input.int(50, "M15", group = GRP_AGE, minval = 1)
int    i_age_h1  = input.int(50, "H1",  group = GRP_AGE, minval = 1)
int    i_age_h4  = input.int(50, "H4",  group = GRP_AGE, minval = 1)
int    i_age_d   = input.int(50, "D",   group = GRP_AGE, minval = 1)
int    i_age_w   = input.int(30, "W",   group = GRP_AGE, minval = 1)
int    i_age_mn  = input.int(20, "MN",  group = GRP_AGE, minval = 1)

string GRP_CLR   = "Colors"
color  i_sup_bg     = input.color(color.new(#FF4444, 85), "Supply Fill",        group = GRP_CLR, inline = "s")
color  i_sup_br     = input.color(color.new(#FF4444, 20), "Border",             group = GRP_CLR, inline = "s")
color  i_dem_bg     = input.color(color.new(#2196F3, 85), "Demand Fill",        group = GRP_CLR, inline = "d")
color  i_dem_br     = input.color(color.new(#2196F3, 20), "Border",             group = GRP_CLR, inline = "d")
color  i_push_sup_bg = input.color(color.new(#FF4444, 70), "Push Supply Fill",  group = GRP_CLR, inline = "ps")
color  i_push_sup_br = input.color(color.new(#FF4444, 0),  "Border",            group = GRP_CLR, inline = "ps")
color  i_push_dem_bg = input.color(color.new(#2196F3, 70), "Push Demand Fill",  group = GRP_CLR, inline = "pd")
color  i_push_dem_br = input.color(color.new(#2196F3, 0),  "Border",            group = GRP_CLR, inline = "pd")
color  i_rev_bg      = input.color(color.new(#FFB300, 75), "Reversal Fill",     group = GRP_CLR, inline = "rv")
color  i_rev_br      = input.color(color.new(#FFB300, 0),  "Border",            group = GRP_CLR, inline = "rv")
bool   i_labels      = input.bool(true, "Show Zone Labels", group = GRP_CLR)

string GRP_DASH  = "Dashboard"
bool   i_dash    = input.bool(true, "Show Dashboard", group = GRP_DASH)
string i_dash_pos = input.string("Bottom Left", "Position", options = ["Top Left", "Top Right", "Bottom Left", "Bottom Right"], group = GRP_DASH)
```

Note: D default is `true` (intentional divergence from template which has `false`).

- [ ] **Step 2: Write S2 Zone UDT**

```pine
// =============================================================================
// S2 — TYPES
// =============================================================================

type Zone
    float   top          = 0.0
    float   bottom       = 0.0
    bool    is_supply    = false
    int     origin_time  = 0
    box     bx
    bool    is_push      = false
    bool    is_reversal  = false
    string  struct_cls   = ""
    string  swing_cls    = ""
```

Labels are embedded in the box via `box.set_text()` — no separate `label` object needed.

- [ ] **Step 3: Write S3 Helpers**

Copy `tf_max_age()` and `tf_label()` verbatim from `iora_zones.pine` template (lines 66–74).

```pine
// =============================================================================
// S3 — HELPERS
// =============================================================================

tf_max_age(string tf) =>
    int sec = timeframe.in_seconds(tf)
    int out = sec <= 60 ? i_age_m1 : sec <= 300 ? i_age_m5 : sec <= 900 ? i_age_m15 : sec <= 3600 ? i_age_h1 : sec <= 14400 ? i_age_h4 : sec <= 86400 ? i_age_d : sec <= 604800 ? i_age_w : i_age_mn
    out

tf_label(string tf) =>
    int sec = timeframe.in_seconds(tf)
    string out = sec <= 60 ? "M1" : sec <= 300 ? "M5" : sec <= 900 ? "M15" : sec <= 3600 ? "H1" : sec <= 14400 ? "H4" : sec <= 86400 ? "D" : sec <= 604800 ? "W" : "MN"
    out
```

- [ ] **Step 4: Write S4 `ha_detect()`**

Copy verbatim from `iora_zones.pine` template (lines 85–165). No changes.

- [ ] **Step 5: Write S5 `track_period()`**

Copy verbatim from `iora_bos_choch.pine` (lines 45–84). No changes to the function itself.

- [ ] **Step 6: Add placeholder sections S6–S10 so the file compiles**

Add empty stubs so the indicator compiles and can be pasted into TradingView for a smoke test:

```pine
// =============================================================================
// S6 — ZONE MANAGEMENT (placeholder)
// =============================================================================

method delete_zone(array<Zone> zones, int idx) =>
    Zone z = zones.get(idx)
    if not na(z.bx)
        box.delete(z.bx)
    zones.remove(idx)

// =============================================================================
// S7 — DATA REQUESTS
// =============================================================================

string _base_sym = ticker.standard(syminfo.tickerid)

[f0_raw, zt0, zb0, s0, tm0, hh0, ll0, hht0, llt0, h1s0, l1s0] = request.security(_base_sym, i_tf0, ha_detect(i_doji))
[f1_raw, zt1, zb1, s1, tm1, hh1, ll1, hht1, llt1, h1s1, l1s1] = request.security(_base_sym, i_tf1, ha_detect(i_doji))
[f2_raw, zt2, zb2, s2, tm2, hh2, ll2, hht2, llt2, h1s2, l1s2] = request.security(_base_sym, i_tf2, ha_detect(i_doji))
[f3_raw, zt3, zb3, s3, tm3, hh3, ll3, hht3, llt3, h1s3, l1s3] = request.security(_base_sym, i_tf3, ha_detect(i_doji))
[f4_raw, zt4, zb4, s4, tm4, hh4, ll4, hht4, llt4, h1s4, l1s4] = request.security(_base_sym, i_tf4, ha_detect(i_doji))
[f5_raw, zt5, zb5, s5, tm5, hh5, ll5, hht5, llt5, h1s5, l1s5] = request.security(_base_sym, i_tf5, ha_detect(i_doji))
[f6_raw, zt6, zb6, s6, tm6, hh6, ll6, hht6, llt6, h1s6, l1s6] = request.security(_base_sym, i_tf6, ha_detect(i_doji))
[f7_raw, zt7, zb7, s7, tm7, hh7, ll7, hht7, llt7, h1s7, l1s7] = request.security(_base_sym, i_tf7, ha_detect(i_doji))

// =============================================================================
// S8 — EDGE DETECTION
// =============================================================================

bool f0 = f0_raw and not f0_raw[1]
bool f1 = f1_raw and not f1_raw[1]
bool f2 = f2_raw and not f2_raw[1]
bool f3 = f3_raw and not f3_raw[1]
bool f4 = f4_raw and not f4_raw[1]
bool f5 = f5_raw and not f5_raw[1]
bool f6 = f6_raw and not f6_raw[1]
bool f7 = f7_raw and not f7_raw[1]

// =============================================================================
// S9 — ZONE ARRAYS + EXECUTION (placeholder — no process() yet)
// =============================================================================

var array<Zone> zones0 = array.new<Zone>()
var array<Zone> zones1 = array.new<Zone>()
var array<Zone> zones2 = array.new<Zone>()
var array<Zone> zones3 = array.new<Zone>()
var array<Zone> zones4 = array.new<Zone>()
var array<Zone> zones5 = array.new<Zone>()
var array<Zone> zones6 = array.new<Zone>()
var array<Zone> zones7 = array.new<Zone>()
```

- [ ] **Step 7: Compile check — paste into TradingView**

Verify: no compilation errors. Indicator loads but shows nothing (no `process()` calls yet).

- [ ] **Step 8: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones.pine
git commit -m "feat(push-zones): scaffold indicator with inputs, UDT, ha_detect, track_period"
```

---

## Task 2: Basic Zone Management — Zones Render on Chart

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones.pine`

**Read first:**
- `tw_indicators/iora_zones/templates/iora_zones.pine` (lines 172–275) — `process()` method, zone execution pattern
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` (lines 17–36) — Zone UDT fields used in process

This task adds the basic `process()` method (expire, break-check, create zone) and wires up all 8 TFs. After this task, zones appear on chart identical to `iora_zones.pine` — no push/reversal logic yet.

- [ ] **Step 1: Write `process()` method in S6 — basic zone management**

Replace the placeholder S6 with the full zone management method. This handles:
1. Expire zones older than `max_ms`
2. Break check: body-close only (`close > z.top` for supply, `close < z.bottom` for demand)
3. Create new zone on fire with label

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, float seq_hh_val, float seq_ll_val, int trend_val, string tf_str) =>
    int tf_ms  = timeframe.in_seconds(tf_str) * 1000
    int max_ms = tf_max_age(tf_str) * tf_ms

    // 1. Expire + break check
    if zones.size() > 0
        for i = zones.size() - 1 to 0
            Zone z = zones.get(i)
            bool expired = (time - z.origin_time) > max_ms
            if expired
                zones.delete_zone(i)
                continue
            bool broken = z.is_supply ? (close > z.top) : (close < z.bottom)
            if broken
                zones.delete_zone(i)

    // 2. Create new zone
    bool valid = not na(ztop) and not na(zbot) and not na(z_time) and ztop > zbot
    if fire and (time - z_time) < max_ms and valid
        string cls     = is_sup ? hi_txt : lo_txt
        string lbl_txt = i_labels ? tf_label(tf_str) + (is_sup ? " S " : " D ") + cls : na
        color  bg_clr  = is_sup ? i_sup_bg : i_dem_bg
        color  br_clr  = is_sup ? i_sup_br : i_dem_br
        color  tx_clr  = is_sup ? color.new(#FF4444, 0) : color.new(#2196F3, 0)
        box new_box    = box.new(z_time, ztop, z_time + tf_ms * 6, zbot, xloc = xloc.bar_time, extend = extend.right, bgcolor = bg_clr, border_color = br_clr, border_width = 1, text = lbl_txt, text_size = size.tiny, text_color = tx_clr, text_halign = text.align_right, text_valign = text.align_top)
        zones.push(Zone.new(ztop, zbot, is_sup, z_time, new_box, false, false, "", cls))
```

Note: `process()` signature includes `seq_hh_val`, `seq_ll_val`, `trend_val` parameters that are unused in this task but needed in Task 3. This avoids changing the signature later.

- [ ] **Step 2: Wire up S9 — per-TF execution calls**

Replace the placeholder S9 with actual `process()` calls. Each TF passes its edge-detected fire, zone data, seq values, and a placeholder `0` for trend (will be wired in Task 4).

```pine
// S9 — ZONE ARRAYS + EXECUTION
if i_tf0_on
    zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, hh0, ll0, 0, i_tf0)
if i_tf1_on
    zones1.process(f1, zt1, zb1, s1, tm1, h1s1, l1s1, hh1, ll1, 0, i_tf1)
if i_tf2_on
    zones2.process(f2, zt2, zb2, s2, tm2, h1s2, l1s2, hh2, ll2, 0, i_tf2)
if i_tf3_on
    zones3.process(f3, zt3, zb3, s3, tm3, h1s3, l1s3, hh3, ll3, 0, i_tf3)
if i_tf4_on
    zones4.process(f4, zt4, zb4, s4, tm4, h1s4, l1s4, hh4, ll4, 0, i_tf4)
if i_tf5_on
    zones5.process(f5, zt5, zb5, s5, tm5, h1s5, l1s5, hh5, ll5, 0, i_tf5)
if i_tf6_on
    zones6.process(f6, zt6, zb6, s6, tm6, h1s6, l1s6, hh6, ll6, 0, i_tf6)
if i_tf7_on
    zones7.process(f7, zt7, zb7, s7, tm7, h1s7, l1s7, hh7, ll7, 0, i_tf7)
```

- [ ] **Step 3: Compile check — paste into TradingView**

Verify:
- No compilation errors
- Zones render on chart (supply = red boxes, demand = blue boxes)
- Labels show `TF S/D HH/LH/HL/LL` text
- Zones disappear when body closes through them
- Enable H1, H4, D and verify multi-TF zones appear

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones.pine
git commit -m "feat(push-zones): add basic zone management — zones render on chart"
```

---

## Task 3: Push Validation + Reversal Tagging

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones.pine` — S6 `process()` method, S8 edge detection

**Read first:**
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` (lines 67–131) — Push validation rules, boundary-break, reversal tagging, break standards
- `tw_indicators/system/iora_zones_push_self.pine` (lines 205–248) — prior push tagging pattern (for reference, but this version adds boundary-break validation)

This is the core new logic. Adds push validation with boundary-break rule and reversal zone tagging inside `process()`.

- [ ] **Step 1: Add per-TF push state variables in S8**

These are `var` state that persists across bars, one set per TF. Add after edge detection:

```pine
// Per-TF push state — boundary-break validation
var float prev_push_hi0 = na, var float prev_push_lo0 = na
var float prev_push_hi1 = na, var float prev_push_lo1 = na
var float prev_push_hi2 = na, var float prev_push_lo2 = na
var float prev_push_hi3 = na, var float prev_push_lo3 = na
var float prev_push_hi4 = na, var float prev_push_lo4 = na
var float prev_push_hi5 = na, var float prev_push_lo5 = na
var float prev_push_hi6 = na, var float prev_push_lo6 = na
var float prev_push_hi7 = na, var float prev_push_lo7 = na
```

Wait — these can't be passed by reference to `process()` since Pine doesn't support that. The `process()` method needs to return the updated values, or the push state needs to live inside `process()` via `var`. But `process()` is a method on `array<Zone>` — each TF calls it with different state.

Better approach: use `var` arrays or manage push state outside `process()`. Since `process()` is called once per TF per bar, and push state is per-TF, the cleanest Pine v6 pattern is to pass push extremes in and get updated values back via tuple return.

Update `process()` signature to accept and return push extreme state:

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, float seq_hh_val, float seq_ll_val, int trend_val, string tf_str, float prev_push_hi, float prev_push_lo) =>
    // ... existing expire/break/create logic ...

    // 3. Push validation (after zone creation)
    float new_push_hi = prev_push_hi
    float new_push_lo = prev_push_lo

    // Bearish push: demand fires with LL, tag supply as PUSH
    if fire and not is_sup and lo_txt == "LL"
        bool boundary_ok = na(prev_push_lo) or seq_ll_val < prev_push_lo
        if boundary_ok and zones.size() > 0
            // Tag most recent supply as PUSH
            for i = zones.size() - 1 to 0
                Zone z = zones.get(i)
                if z.is_supply
                    z.is_push := true
                    // Restyle push supply
                    if not na(z.bx)
                        z.bx.set_bgcolor(i_push_sup_bg)
                        z.bx.set_border_color(i_push_sup_br)
                        z.bx.set_border_width(2)
                        string ptxt = i_labels ? tf_label(tf_str) + " S PUSH" : na
                        z.bx.set_text(ptxt)
                    break
            // Tag most recent demand as REVERSAL (the trigger zone just created)
            for i = zones.size() - 1 to 0
                Zone z = zones.get(i)
                if not z.is_supply
                    z.is_reversal := true
                    if not na(z.bx)
                        z.bx.set_bgcolor(i_rev_bg)
                        z.bx.set_border_color(i_rev_br)
                        z.bx.set_border_width(2)
                        string rtxt = i_labels ? tf_label(tf_str) + " D REV" : na
                        z.bx.set_text(rtxt)
                    break
            new_push_lo := seq_ll_val

    // Bullish push: supply fires with HH, tag demand as PUSH
    if fire and is_sup and hi_txt == "HH"
        bool boundary_ok = na(prev_push_hi) or seq_hh_val > prev_push_hi
        if boundary_ok and zones.size() > 0
            // Tag most recent demand as PUSH
            for i = zones.size() - 1 to 0
                Zone z = zones.get(i)
                if not z.is_supply
                    z.is_push := true
                    // Restyle push demand
                    if not na(z.bx)
                        z.bx.set_bgcolor(i_push_dem_bg)
                        z.bx.set_border_color(i_push_dem_br)
                        z.bx.set_border_width(2)
                        string ptxt = i_labels ? tf_label(tf_str) + " D PUSH" : na
                        z.bx.set_text(ptxt)
                    break
            // Tag most recent supply as REVERSAL (the trigger zone just created)
            for i = zones.size() - 1 to 0
                Zone z = zones.get(i)
                if z.is_supply
                    z.is_reversal := true
                    if not na(z.bx)
                        z.bx.set_bgcolor(i_rev_bg)
                        z.bx.set_border_color(i_rev_br)
                        z.bx.set_border_width(2)
                        string rtxt = i_labels ? tf_label(tf_str) + " S REV" : na
                        z.bx.set_text(rtxt)
                    break
            new_push_hi := seq_hh_val

    [new_push_hi, new_push_lo]
```

- [ ] **Step 2: Update S9 execution to capture returned push state**

Each TF's `process()` call now returns `[new_push_hi, new_push_lo]`. Use `var` state per TF:

```pine
var float ph0 = na, var float pl0 = na
var float ph1 = na, var float pl1 = na
var float ph2 = na, var float pl2 = na
var float ph3 = na, var float pl3 = na
var float ph4 = na, var float pl4 = na
var float ph5 = na, var float pl5 = na
var float ph6 = na, var float pl6 = na
var float ph7 = na, var float pl7 = na

if i_tf0_on
    [nph0, npl0] = zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, hh0, ll0, 0, i_tf0, ph0, pl0)
    ph0 := nph0
    pl0 := npl0
// ... repeat for tf1–tf7 ...
```

- [ ] **Step 3: Compile check — paste into TradingView**

Verify:
- No compilation errors
- Normal zones still render correctly
- On LL events: most recent supply zone turns to push styling (brighter red, thick border, "S PUSH" label)
- On HH events: most recent demand zone turns to push styling (brighter blue, thick border, "D PUSH" label)
- Reversal zones appear in amber with "D REV" / "S REV" labels
- Push zones that didn't break the previous boundary remain normal
- First HH/LL auto-qualifies (bootstrap)
- Three break standards are in effect (see spec "Break standards" section): push validation uses wick/body exceedance (`seq_ll < prev_push_lo`), zone breaks use body-close only (`close > z.top`), and `track_period()` uses wick-based (`high > prev_hi`) for trend detection

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones.pine
git commit -m "feat(push-zones): add push validation with boundary-break rule + reversal tagging"
```

---

## Task 4: BOS/CHoCH Classification + Trend Tracking

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones.pine` — S8 (edge detection), S6 (`process()`), S9 (execution)

**Read first:**
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` (lines 135–172) — BOS/CHoCH classification rules, trend tracking, cascading TF view

This task adds `track_period()` calls for each TF, trend state tracking via period break edge detection, and BOS/CHoCH classification at push-validation time inside `process()`.

- [ ] **Step 1: Add `track_period()` calls + trend edge detection in S8**

Add `track_period()` calls **before** the trend edge detection in S8 (not in S9), because Pine runs top-to-bottom and trend edge detection reads `track_period()` output on the same bar. These calls are ungated (run for all 8 TFs regardless of `i_tfN_on`) because `track_period()` uses internal `var` state that must accumulate continuously. This is harmless for disabled TFs.

```pine
// S8 — PERIOD TRACKING + TREND STATE
[tp0_hi, tp0_hi_t, tp0_lo, tp0_lo_t, tp0_hi_brk, tp0_lo_brk] = track_period(i_tf0)
[tp1_hi, tp1_hi_t, tp1_lo, tp1_lo_t, tp1_hi_brk, tp1_lo_brk] = track_period(i_tf1)
[tp2_hi, tp2_hi_t, tp2_lo, tp2_lo_t, tp2_hi_brk, tp2_lo_brk] = track_period(i_tf2)
[tp3_hi, tp3_hi_t, tp3_lo, tp3_lo_t, tp3_hi_brk, tp3_lo_brk] = track_period(i_tf3)
[tp4_hi, tp4_hi_t, tp4_lo, tp4_lo_t, tp4_hi_brk, tp4_lo_brk] = track_period(i_tf4)
[tp5_hi, tp5_hi_t, tp5_lo, tp5_lo_t, tp5_hi_brk, tp5_lo_brk] = track_period(i_tf5)
[tp6_hi, tp6_hi_t, tp6_lo, tp6_lo_t, tp6_hi_brk, tp6_lo_brk] = track_period(i_tf6)
[tp7_hi, tp7_hi_t, tp7_lo, tp7_lo_t, tp7_hi_brk, tp7_lo_brk] = track_period(i_tf7)
```

- [ ] **Step 2: Add trend state via edge detection (immediately after track_period calls)**

Edge-detect `track_period()` break events. Use `na→timestamp` transition:

```pine
// Per-TF trend state
var int trend0 = 0, var int trend1 = 0, var int trend2 = 0, var int trend3 = 0
var int trend4 = 0, var int trend5 = 0, var int trend6 = 0, var int trend7 = 0

// Edge-detect period breaks: na→timestamp means break just happened
if not na(tp0_hi_brk) and na(tp0_hi_brk[1])
    trend0 := 1
if not na(tp0_lo_brk) and na(tp0_lo_brk[1])
    trend0 := -1
// ... repeat for trend1–trend7 with tp1–tp7 ...
```

- [ ] **Step 3: Add BOS/CHoCH classification inside `process()` push validation**

After tagging a push zone, classify it:

```pine
// Inside bearish push validation (after tagging supply as PUSH):
string scls = ""
if trend_val == -1
    scls := "BOS"
else if trend_val == 1
    scls := "CHoCH"
z.struct_cls := scls
// Update push label to include struct_cls
string suffix = scls != "" ? "-" + scls : ""
string ptxt = i_labels ? tf_label(tf_str) + " S PUSH" + suffix : na
z.bx.set_text(ptxt)

// Same pattern for bullish push validation
```

- [ ] **Step 4: Update S9 execution to pass trend state**

Replace the `0` trend placeholder with actual trend values:

```pine
if i_tf0_on
    [nph0, npl0] = zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, hh0, ll0, trend0, i_tf0, ph0, pl0)
    ph0 := nph0
    pl0 := npl0
// ... repeat for tf1–tf7 ...
```

- [ ] **Step 5: Compile check — paste into TradingView**

Verify:
- Push zone labels now show `S PUSH-BOS` or `D PUSH-CHoCH` (or `S PUSH` / `D PUSH` when trend is uninitialized)
- BOS appears when push direction matches trend
- CHoCH appears when push direction opposes trend
- Reversal labels unchanged (`D REV` / `S REV`)
- Normal zones unchanged

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones.pine
git commit -m "feat(push-zones): add BOS/CHoCH classification with trend tracking via track_period"
```

---

## Task 5: Dashboard

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones.pine` — add S10

**Read first:**
- `docs/superpowers/specs/2026-03-31-iora-push-zones-design.md` (lines 239–249) — Dashboard spec
- `tw_indicators/iora_zones/iora_mechanical_zones.pine` — reference for dashboard table pattern (if needed)

This task adds the compact dashboard table showing TF, Trend, Push state, and zone counts per enabled TF.

- [ ] **Step 1: Write dashboard position helper**

```pine
// =============================================================================
// S10 — DASHBOARD
// =============================================================================

dash_position(string pos) =>
    string out = pos == "Top Left" ? position.top_left : pos == "Top Right" ? position.top_right : pos == "Bottom Right" ? position.bottom_right : position.bottom_left
    out
```

- [ ] **Step 2: Write dashboard rendering logic**

Count enabled TFs, build table with header + one row per enabled TF:

```pine
if i_dash and barstate.islast
    // Count enabled TFs for table rows
    int tf_count = 0
    if i_tf0_on
        tf_count += 1
    if i_tf1_on
        tf_count += 1
    // ... repeat for tf2–tf7 ...

    if tf_count > 0
        var table dash = table.new(dash_position(i_dash_pos), 4, tf_count + 1, bgcolor = color.new(#1a1a2e, 10), border_color = color.new(#ffffff, 80), border_width = 1, frame_color = color.new(#ffffff, 80), frame_width = 1)

        // Header row
        table.cell(dash, 0, 0, "TF",    text_size = size.tiny, text_color = color.white)
        table.cell(dash, 1, 0, "Trend",  text_size = size.tiny, text_color = color.white)
        table.cell(dash, 2, 0, "Push",   text_size = size.tiny, text_color = color.white)
        table.cell(dash, 3, 0, "Zones",  text_size = size.tiny, text_color = color.white)

        int row = 1

        // Helper: find active push info from zone array
        // For each enabled TF, add a row
        if i_tf0_on
            string trend_txt = trend0 == 1 ? "BULL" : trend0 == -1 ? "BEAR" : "—"
            color  trend_clr = trend0 == 1 ? color.green : trend0 == -1 ? color.red : color.gray
            // Count supply/demand zones
            int sc0 = 0
            int dc0 = 0
            string push_txt = "—"
            for i = 0 to zones0.size() - 1
                Zone z = zones0.get(i)
                if z.is_supply
                    sc0 += 1
                else
                    dc0 += 1
                if z.is_push
                    string side = z.is_supply ? "S" : "D"
                    string suffix = z.struct_cls != "" ? "-" + z.struct_cls : ""
                    push_txt := side + " PUSH" + suffix
            table.cell(dash, 0, row, tf_label(i_tf0), text_size = size.tiny, text_color = color.white)
            table.cell(dash, 1, row, trend_txt,        text_size = size.tiny, text_color = trend_clr)
            table.cell(dash, 2, row, push_txt,          text_size = size.tiny, text_color = color.yellow)
            table.cell(dash, 3, row, str.tostring(sc0) + "S " + str.tostring(dc0) + "D", text_size = size.tiny, text_color = color.white)
            row += 1
        // ... repeat for tf1–tf7 ...
```

Since this is highly repetitive (8 TFs), extract a helper function `dash_row()` that takes a zone array, trend value, tf string, table reference, and row number:

```pine
dash_row(table tbl, int row_num, string tf_str, int trend_val, array<Zone> zones) =>
    string trend_txt = trend_val == 1 ? "BULL" : trend_val == -1 ? "BEAR" : "—"
    color  trend_clr = trend_val == 1 ? color.green : trend_val == -1 ? color.red : color.gray
    int sc = 0
    int dc = 0
    string push_txt = "—"
    if zones.size() > 0
        for i = 0 to zones.size() - 1
            Zone z = zones.get(i)
            if z.is_supply
                sc += 1
            else
                dc += 1
            if z.is_push
                string side = z.is_supply ? "S" : "D"
                string suffix = z.struct_cls != "" ? "-" + z.struct_cls : ""
                push_txt := side + " PUSH" + suffix
    table.cell(tbl, 0, row_num, tf_label(tf_str), text_size = size.tiny, text_color = color.white)
    table.cell(tbl, 1, row_num, trend_txt,          text_size = size.tiny, text_color = trend_clr)
    table.cell(tbl, 2, row_num, push_txt,            text_size = size.tiny, text_color = color.yellow)
    table.cell(tbl, 3, row_num, str.tostring(sc) + "S " + str.tostring(dc) + "D", text_size = size.tiny, text_color = color.white)
    row_num + 1
```

Then the main dashboard block becomes:

```pine
if i_dash and barstate.islast
    int tf_count = (i_tf0_on ? 1 : 0) + (i_tf1_on ? 1 : 0) + (i_tf2_on ? 1 : 0) + (i_tf3_on ? 1 : 0) + (i_tf4_on ? 1 : 0) + (i_tf5_on ? 1 : 0) + (i_tf6_on ? 1 : 0) + (i_tf7_on ? 1 : 0)
    if tf_count > 0
        var table dash = table.new(dash_position(i_dash_pos), 4, tf_count + 1, bgcolor = color.new(#1a1a2e, 10), border_color = color.new(#ffffff, 80), border_width = 1, frame_color = color.new(#ffffff, 80), frame_width = 1)
        table.cell(dash, 0, 0, "TF",    text_size = size.tiny, text_color = color.white)
        table.cell(dash, 1, 0, "Trend",  text_size = size.tiny, text_color = color.white)
        table.cell(dash, 2, 0, "Push",   text_size = size.tiny, text_color = color.white)
        table.cell(dash, 3, 0, "Zones",  text_size = size.tiny, text_color = color.white)
        int row = 1
        if i_tf0_on
            row := dash_row(dash, row, i_tf0, trend0, zones0)
        if i_tf1_on
            row := dash_row(dash, row, i_tf1, trend1, zones1)
        if i_tf2_on
            row := dash_row(dash, row, i_tf2, trend2, zones2)
        if i_tf3_on
            row := dash_row(dash, row, i_tf3, trend3, zones3)
        if i_tf4_on
            row := dash_row(dash, row, i_tf4, trend4, zones4)
        if i_tf5_on
            row := dash_row(dash, row, i_tf5, trend5, zones5)
        if i_tf6_on
            row := dash_row(dash, row, i_tf6, trend6, zones6)
        if i_tf7_on
            row := dash_row(dash, row, i_tf7, trend7, zones7)
```

- [ ] **Step 3: Compile check — paste into TradingView**

Verify:
- Dashboard appears in Bottom Left (default position)
- One row per enabled TF
- TF column shows M1/M5/.../MN
- Trend column shows BULL/BEAR/— with correct colors
- Push column shows active push classification or —
- Zones column shows supply/demand counts

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones.pine
git commit -m "feat(push-zones): add dashboard with trend, push state, and zone counts"
```

---

## Verification Checklist

After all 5 tasks are complete, do a final visual verification in TradingView:

- [ ] Indicator compiles without errors
- [ ] Normal zones: red supply, blue demand, with HH/LH/HL/LL labels
- [ ] Push zones: brighter fill, thick border, "S PUSH-BOS" / "D PUSH-CHoCH" labels
- [ ] Push only tagged when boundary-break rule passes (new extreme > previous push extreme)
- [ ] First HH/LL auto-qualifies as push (bootstrap)
- [ ] Reversal zones: amber fill, "D REV" / "S REV" labels, at base of push sequence
- [ ] Zones deleted on body-close break (wicks don't break)
- [ ] Dashboard shows correct state per TF
- [ ] Test with H1+H4+D enabled: cascading structure visible
- [ ] Toggle TFs on/off: only enabled TFs show zones and dashboard rows
