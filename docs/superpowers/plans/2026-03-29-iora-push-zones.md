# Push Zone Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two push zone indicators that identify the last unbroken HA supply/demand zone responsible for creating the most recent structural extreme (HH/LL).

**Architecture:** Both indicators share the same `ha_detect()` zone detection core from `iora_v1/iora_zones.pine`. Indicator 1 (self-TF) uses sequence tracking from within `ha_detect` to identify new HH/LL events. Indicator 2 (cross-TF) uses `track_period()` from `iora_bos_choch.pine` to track structure on the next-higher TF while detecting zones on the lower TF.

**Tech Stack:** Pine Script v6, TradingView

---

## File Structure

| File | Responsibility |
|------|---------------|
| `tw_indicators/system/iora_zones_push_self.pine` | **Indicator 1** — Same-TF push zones. Zone detection + HH/LL tracking on same TF. Push = last unbroken zone when that TF's own HA sequence prints new HH/LL. |
| `tw_indicators/system/iora_zones_push_cross.pine` | **Indicator 2** — Cross-TF push zones. Zones detected on lower TF, structure tracked on next-higher TF via `track_period()`. Push = last unbroken zone on lower TF when higher TF's previous extreme is broken. |

## Shared Mechanics (both indicators)

- **Zone UDT:** `type Zone { float top, float bottom, bool is_supply, int origin_time, box bx, bool is_push }`
- **HA detection:** `ha_detect()` from `iora_v1/iora_zones.pine` pattern (ORIZ spec boundaries)
- **Body-close break rule:** `close > zone.top` (supply) or `close < zone.bottom` (demand) — wicks are liquidity sweeps
- **Broken zones deleted immediately** — no ghost styling
- **Push highlight:** Push zones get thicker border (width 2) and brighter fill color
- **Default TFs:** H1 + H4 enabled, others off
- **`request.security()`** on `ticker.standard(syminfo.tickerid)` for raw OHLC
- **Edge-detection:** `fire = f_raw and not f_raw[1]`
- **`calc_bars_count = 500`** on all security calls

## Key Pine v6 Rules (from CLAUDE.md)

- `//@version=6` always
- All variables explicitly typed
- No multiline ternaries
- No reserved keywords as variable names
- `request.security()` max 40 total — Indicator 1 uses 8, Indicator 2 uses 6
- Timeframe strings: `"5"`, `"15"`, `"60"`, `"240"`, `"1D"`, `"1W"`, `"1M"`
- Field assignment on `.get()` — store in local variable first
- Use `.copy()` for independent UDT copies

---

## Task 1: Build `iora_zones_push_self.pine` — Scaffold + Types + Inputs

**Files:**
- Create: `tw_indicators/system/iora_zones_push_self.pine`

- [ ] **Step 1: Create file with indicator header, Zone UDT, and all inputs**

```pine
//@version=6
indicator("Iora Push Zones (Self-TF)", overlay = true, max_boxes_count = 500, max_labels_count = 500, calc_bars_count = 2000)

// S1 — TYPES
type Zone
    float   top       = 0.0
    float   bottom    = 0.0
    bool    is_supply = false
    int     origin_time = 0
    box     bx
    bool    is_push   = false

// S1 — INPUTS
string GRP_ZONE  = "Zone Detection"
float  i_doji    = input.float(5.0, "Doji Body %", group = GRP_ZONE, minval = 0.1, maxval = 50.0)

string GRP_TF    = "Timeframes"
bool   i_tf0_on  = input.bool(false, "M5",     group = GRP_TF, inline = "t0")
string i_tf0     = input.timeframe("5",   "",  group = GRP_TF, inline = "t0")
bool   i_tf1_on  = input.bool(false, "M15",    group = GRP_TF, inline = "t1")
string i_tf1     = input.timeframe("15",  "",  group = GRP_TF, inline = "t1")
bool   i_tf2_on  = input.bool(false, "M30",    group = GRP_TF, inline = "t2")
string i_tf2     = input.timeframe("30",  "",  group = GRP_TF, inline = "t2")
bool   i_tf3_on  = input.bool(true,  "H1",     group = GRP_TF, inline = "t3")
string i_tf3     = input.timeframe("60",  "",  group = GRP_TF, inline = "t3")
bool   i_tf4_on  = input.bool(true,  "H4",     group = GRP_TF, inline = "t4")
string i_tf4     = input.timeframe("240", "",  group = GRP_TF, inline = "t4")
bool   i_tf5_on  = input.bool(false, "D",      group = GRP_TF, inline = "t5")
string i_tf5     = input.timeframe("1D",  "",  group = GRP_TF, inline = "t5")
bool   i_tf6_on  = input.bool(false, "W",      group = GRP_TF, inline = "t6")
string i_tf6     = input.timeframe("1W",  "",  group = GRP_TF, inline = "t6")
bool   i_tf7_on  = input.bool(false, "MN",     group = GRP_TF, inline = "t7")
string i_tf7     = input.timeframe("1M",  "",  group = GRP_TF, inline = "t7")

string GRP_AGE   = "Zone Age (max bars per TF)"
int    i_age_m5  = input.int(50, "M5",  group = GRP_AGE, minval = 1)
int    i_age_m15 = input.int(50, "M15", group = GRP_AGE, minval = 1)
int    i_age_m30 = input.int(50, "M30", group = GRP_AGE, minval = 1)
int    i_age_h1  = input.int(50, "H1",  group = GRP_AGE, minval = 1)
int    i_age_h4  = input.int(50, "H4",  group = GRP_AGE, minval = 1)
int    i_age_d   = input.int(50, "D",   group = GRP_AGE, minval = 1)
int    i_age_w   = input.int(30, "W",   group = GRP_AGE, minval = 1)
int    i_age_mn  = input.int(20, "MN",  group = GRP_AGE, minval = 1)

string GRP_CLR   = "Colors"
color  i_sup_bg  = input.color(color.new(#FF4444, 85), "Supply Fill",   group = GRP_CLR)
color  i_sup_br  = input.color(color.new(#FF4444, 20), "Supply Border", group = GRP_CLR)
color  i_dem_bg  = input.color(color.new(#2196F3, 85), "Demand Fill",   group = GRP_CLR)
color  i_dem_br  = input.color(color.new(#2196F3, 20), "Demand Border", group = GRP_CLR)
color  i_push_sup_bg = input.color(color.new(#FF4444, 70), "Push Supply Fill",   group = GRP_CLR)
color  i_push_sup_br = input.color(color.new(#FF4444, 0),  "Push Supply Border", group = GRP_CLR)
color  i_push_dem_bg = input.color(color.new(#2196F3, 70), "Push Demand Fill",   group = GRP_CLR)
color  i_push_dem_br = input.color(color.new(#2196F3, 0),  "Push Demand Border", group = GRP_CLR)
bool   i_labels  = input.bool(true, "Show Zone Labels", group = GRP_CLR)
```

- [ ] **Step 2: Verify file compiles (just inputs + types, no logic yet)**

Paste into TradingView Pine Editor, confirm no errors.

---

## Task 2: Add `ha_detect()` + helpers to self-TF indicator

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_self.pine`

- [ ] **Step 1: Add helper functions after inputs**

```pine
// S2 — HELPERS
tf_max_age(string tf) =>
    int sec = timeframe.in_seconds(tf)
    int out = sec <= 300 ? i_age_m5 : sec <= 900 ? i_age_m15 : sec <= 1800 ? i_age_m30 : sec <= 3600 ? i_age_h1 : sec <= 14400 ? i_age_h4 : sec <= 86400 ? i_age_d : sec <= 604800 ? i_age_w : i_age_mn
    out

tf_label(string tf) =>
    int sec = timeframe.in_seconds(tf)
    string out = sec <= 300 ? "M5" : sec <= 900 ? "M15" : sec <= 1800 ? "M30" : sec <= 3600 ? "H1" : sec <= 14400 ? "H4" : sec <= 86400 ? "D" : sec <= 604800 ? "W" : "MN"
    out
```

- [ ] **Step 2: Add `ha_detect()` function**

Copy from `iora_v1/iora_zones.pine` lines 85–165 (the trimmed 11-value return version). This includes:
- HA candle computation from raw OHLC
- Blue/red run detection
- ORIZ spec zone boundaries (Supply: top=OHLC high, bottom=HA low; Demand: top=HA high, bottom=OHLC low)
- Sequence HH/LL tracking with classification text (`hi1_txt`, `lo1_txt`)
- Returns: `[fire, ztop, zbot, is_sup, zt_origin, seq_hh, seq_ll, seq_hh_time, seq_ll_time, hi1_txt, lo1_txt]`

- [ ] **Step 3: Verify compiles**

---

## Task 3: Add zone management with push detection to self-TF indicator

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_self.pine`

- [ ] **Step 1: Add `delete_zone` method**

```pine
// S3 — ZONE MANAGEMENT
method delete_zone(array<Zone> zones, int idx) =>
    Zone z = zones.get(idx)
    if not na(z.bx)
        box.delete(z.bx)
    zones.remove(idx)
```

- [ ] **Step 2: Add `process` method with push zone tagging**

The `process` method handles:
1. Expire old zones (age > max_ms)
2. Body-close break detection → delete broken zones
3. Create new zone on `fire` event
4. **Push detection**: When `hi1_txt == "HH"` (new HH event on this TF), scan all unbroken demand zones, tag the most recent one as push. When `lo1_txt == "LL"`, scan all unbroken supply zones, tag the most recent one as push.

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, string tf_str, bool new_hh, bool new_ll) =>
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
        zones.push(Zone.new(ztop, zbot, is_sup, z_time, new_box, false))

    // 3. Push zone tagging — on new HH/LL event
    // Reset all push flags first
    if (new_hh or new_ll) and zones.size() > 0
        for i = 0 to zones.size() - 1
            Zone z = zones.get(i)
            if z.is_push
                z.is_push := false
                // Revert to normal styling
                color bg = z.is_supply ? i_sup_bg : i_dem_bg
                color br = z.is_supply ? i_sup_br : i_dem_br
                if not na(z.bx)
                    z.bx.set_bgcolor(bg)
                    z.bx.set_border_color(br)
                    z.bx.set_border_width(1)

    // Tag the most recent unbroken zone in the push direction
    if new_hh and zones.size() > 0
        // New HH → last unbroken demand zone is the push
        for i = zones.size() - 1 to 0
            Zone z = zones.get(i)
            if not z.is_supply
                z.is_push := true
                if not na(z.bx)
                    z.bx.set_bgcolor(i_push_dem_bg)
                    z.bx.set_border_color(i_push_dem_br)
                    z.bx.set_border_width(2)
                    string ptxt = i_labels ? tf_label(tf_str) + " D " + "PUSH" : na
                    z.bx.set_text(ptxt)
                break

    if new_ll and zones.size() > 0
        // New LL → last unbroken supply zone is the push
        for i = zones.size() - 1 to 0
            Zone z = zones.get(i)
            if z.is_supply
                z.is_push := true
                if not na(z.bx)
                    z.bx.set_bgcolor(i_push_sup_bg)
                    z.bx.set_border_color(i_push_sup_br)
                    z.bx.set_border_width(2)
                    string ptxt = i_labels ? tf_label(tf_str) + " S " + "PUSH" : na
                    z.bx.set_text(ptxt)
                break
```

- [ ] **Step 3: Verify compiles**

---

## Task 4: Add data requests + execution to self-TF indicator

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_self.pine`

- [ ] **Step 1: Add request.security calls (8 total)**

```pine
// S4 — DATA REQUESTS (8 calls on raw OHLC)
string _base_sym = ticker.standard(syminfo.tickerid)

[f0_raw, zt0, zb0, s0, tm0, hh0, ll0, hht0, llt0, h1s0, l1s0] = request.security(_base_sym, i_tf0, ha_detect(i_doji), calc_bars_count = 500)
[f1_raw, zt1, zb1, s1, tm1, hh1, ll1, hht1, llt1, h1s1, l1s1] = request.security(_base_sym, i_tf1, ha_detect(i_doji), calc_bars_count = 500)
[f2_raw, zt2, zb2, s2, tm2, hh2, ll2, hht2, llt2, h1s2, l1s2] = request.security(_base_sym, i_tf2, ha_detect(i_doji), calc_bars_count = 500)
[f3_raw, zt3, zb3, s3, tm3, hh3, ll3, hht3, llt3, h1s3, l1s3] = request.security(_base_sym, i_tf3, ha_detect(i_doji), calc_bars_count = 500)
[f4_raw, zt4, zb4, s4, tm4, hh4, ll4, hht4, llt4, h1s4, l1s4] = request.security(_base_sym, i_tf4, ha_detect(i_doji), calc_bars_count = 500)
[f5_raw, zt5, zb5, s5, tm5, hh5, ll5, hht5, llt5, h1s5, l1s5] = request.security(_base_sym, i_tf5, ha_detect(i_doji), calc_bars_count = 500)
[f6_raw, zt6, zb6, s6, tm6, hh6, ll6, hht6, llt6, h1s6, l1s6] = request.security(_base_sym, i_tf6, ha_detect(i_doji), calc_bars_count = 500)
[f7_raw, zt7, zb7, s7, tm7, hh7, ll7, hht7, llt7, h1s7, l1s7] = request.security(_base_sym, i_tf7, ha_detect(i_doji), calc_bars_count = 500)
```

- [ ] **Step 2: Add edge-detection + new HH/LL detection**

```pine
// Edge-detect zone fires
bool f0 = f0_raw and not f0_raw[1]
bool f1 = f1_raw and not f1_raw[1]
// ... (all 8)

// New HH/LL edge-detect: hi1_txt changes to "HH" or lo1_txt changes to "LL"
// We detect when the sequence extreme LEVEL changes (new extreme posted)
var float prev_hh0 = na
bool new_hh0 = not na(hh0) and hh0 != prev_hh0 and h1s0 == "HH"
if not na(hh0)
    prev_hh0 := hh0

var float prev_ll0 = na
bool new_ll0 = not na(ll0) and ll0 != prev_ll0 and l1s0 == "LL"
if not na(ll0)
    prev_ll0 := ll0
// ... (repeat for all 8 TFs)
```

**Important:** The HH/LL detection must use edge-detection on the `seq_hh`/`seq_ll` values. When `seq_hh` changes AND `hi1_txt == "HH"`, that's a new HH event. Same for `seq_ll` changing AND `lo1_txt == "LL"`.

- [ ] **Step 3: Add zone arrays + execution loop**

```pine
// S5 — ZONE ARRAYS + EXECUTION
var array<Zone> zones0 = array.new<Zone>()
var array<Zone> zones1 = array.new<Zone>()
// ... (all 8)

if i_tf0_on
    zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, i_tf0, new_hh0, new_ll0)
if i_tf1_on
    zones1.process(f1, zt1, zb1, s1, tm1, h1s1, l1s1, i_tf1, new_hh1, new_ll1)
// ... (all 8)
```

- [ ] **Step 4: Verify compiles in TradingView**

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/system/iora_zones_push_self.pine
git commit -m "feat(zones): add iora_zones_push_self.pine — same-TF push zone detection"
```

---

## Task 5: Build `iora_zones_push_cross.pine` — Scaffold + Types + Inputs

**Files:**
- Create: `tw_indicators/system/iora_zones_push_cross.pine`

- [ ] **Step 1: Create file with indicator header, Zone UDT, and inputs**

Same structure as self-TF but with 6 TF pairings instead of 8 independent TFs:

```pine
//@version=6
indicator("Iora Push Zones (Cross-TF)", overlay = true, max_boxes_count = 500, max_labels_count = 500, calc_bars_count = 2000)

type Zone
    float   top       = 0.0
    float   bottom    = 0.0
    bool    is_supply = false
    int     origin_time = 0
    box     bx
    bool    is_push   = false
```

TF pairing inputs — each pairing has a toggle, and the zone TF + structure TF are fixed:

| Pairing | Zone TF (lower) | Structure TF (higher) | Label |
|---------|-----------------|----------------------|-------|
| 0 | M5 ("5") | M15 ("15") | M5→M15 |
| 1 | M15 ("15") | H1 ("60") | M15→H1 |
| 2 | H1 ("60") | H4 ("240") | H1→H4 |
| 3 | H4 ("240") | D ("1D") | H4→D |
| 4 | D ("1D") | W ("1W") | D→W |
| 5 | W ("1W") | MN ("1M") | W→MN |

```pine
string GRP_TF    = "TF Pairings (Zone → Structure)"
bool   i_p0_on   = input.bool(false, "M5 → M15",  group = GRP_TF)
bool   i_p1_on   = input.bool(false, "M15 → H1",  group = GRP_TF)
bool   i_p2_on   = input.bool(true,  "H1 → H4",   group = GRP_TF)
bool   i_p3_on   = input.bool(true,  "H4 → D",    group = GRP_TF)
bool   i_p4_on   = input.bool(false, "D → W",     group = GRP_TF)
bool   i_p5_on   = input.bool(false, "W → MN",    group = GRP_TF)
```

Zone age, color inputs same as self-TF.

- [ ] **Step 2: Verify compiles**

---

## Task 6: Add `ha_detect()` + `track_period()` + helpers to cross-TF indicator

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_cross.pine`

- [ ] **Step 1: Add helpers (`tf_max_age`, `tf_label`)**

Same as Task 2 Step 1.

- [ ] **Step 2: Add `ha_detect()` function**

Same as Task 2 Step 2 (11-value return from `iora_v1/iora_zones.pine`).

- [ ] **Step 3: Add `track_period()` function from `iora_bos_choch.pine`**

```pine
// S3 — STRUCTURE TRACKING (runs on chart TF, no extra security calls)
track_period(string tf) =>
    bool new_period = ta.change(time(tf)) != 0
    var float cur_hi   = na
    var int   cur_hi_t = na
    var float cur_lo   = na
    var int   cur_lo_t = na
    var float prev_hi   = na
    var int   prev_hi_t = na
    var float prev_lo   = na
    var int   prev_lo_t = na
    var int   hi_brk_t  = na
    var int   lo_brk_t  = na

    if new_period
        prev_hi   := cur_hi
        prev_hi_t := cur_hi_t
        prev_lo   := cur_lo
        prev_lo_t := cur_lo_t
        cur_hi    := high
        cur_hi_t  := time
        cur_lo    := low
        cur_lo_t  := time
        hi_brk_t  := na
        lo_brk_t  := na
    else
        if high >= nz(cur_hi)
            cur_hi   := high
            cur_hi_t := time
        if low <= nz(cur_lo, 1e18)
            cur_lo   := low
            cur_lo_t := time

    if na(hi_brk_t) and not na(prev_hi) and high > prev_hi
        hi_brk_t := time
    if na(lo_brk_t) and not na(prev_lo) and low < prev_lo
        lo_brk_t := time

    [prev_hi, prev_hi_t, prev_lo, prev_lo_t, hi_brk_t, lo_brk_t]
```

- [ ] **Step 4: Verify compiles**

---

## Task 7: Add zone management with cross-TF push detection

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_cross.pine`

- [ ] **Step 1: Add `delete_zone` and `process` methods**

The `process` method is similar to self-TF but push detection is driven by the higher TF's break events instead of same-TF HH/LL:

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, string tf_str, bool htf_hi_broken, bool htf_lo_broken) =>
```

- `htf_hi_broken`: edge-detected event when higher TF's previous high is first broken → last unbroken demand zone on lower TF = bullish push
- `htf_lo_broken`: edge-detected event when higher TF's previous low is first broken → last unbroken supply zone on lower TF = bearish push

The push tagging logic is identical to self-TF (Task 3 Step 2), just with different trigger signals.

- [ ] **Step 2: Verify compiles**

---

## Task 8: Add data requests + execution to cross-TF indicator

**Files:**
- Modify: `tw_indicators/system/iora_zones_push_cross.pine`

- [ ] **Step 1: Add request.security calls for zone TFs (6 total)**

```pine
// S5 — DATA REQUESTS (6 calls for zone detection on lower TFs)
string _base_sym = ticker.standard(syminfo.tickerid)

[f0_raw, zt0, zb0, s0, tm0, hh0, ll0, hht0, llt0, h1s0, l1s0] = request.security(_base_sym, "5",   ha_detect(i_doji), calc_bars_count = 500)
[f1_raw, zt1, zb1, s1, tm1, hh1, ll1, hht1, llt1, h1s1, l1s1] = request.security(_base_sym, "15",  ha_detect(i_doji), calc_bars_count = 500)
[f2_raw, zt2, zb2, s2, tm2, hh2, ll2, hht2, llt2, h1s2, l1s2] = request.security(_base_sym, "60",  ha_detect(i_doji), calc_bars_count = 500)
[f3_raw, zt3, zb3, s3, tm3, hh3, ll3, hht3, llt3, h1s3, l1s3] = request.security(_base_sym, "240", ha_detect(i_doji), calc_bars_count = 500)
[f4_raw, zt4, zb4, s4, tm4, hh4, ll4, hht4, llt4, h1s4, l1s4] = request.security(_base_sym, "1D",  ha_detect(i_doji), calc_bars_count = 500)
[f5_raw, zt5, zb5, s5, tm5, hh5, ll5, hht5, llt5, h1s5, l1s5] = request.security(_base_sym, "1W",  ha_detect(i_doji), calc_bars_count = 500)
```

- [ ] **Step 2: Add track_period calls for structure TFs (no extra security calls)**

```pine
// S6 — STRUCTURE TRACKING on higher TFs (runs on chart TF)
[m15_hi, m15_hi_t, m15_lo, m15_lo_t, m15_hi_brk, m15_lo_brk] = track_period("15")
[h1_hi,  h1_hi_t,  h1_lo,  h1_lo_t,  h1_hi_brk,  h1_lo_brk]  = track_period("60")
[h4_hi,  h4_hi_t,  h4_lo,  h4_lo_t,  h4_hi_brk,  h4_lo_brk]  = track_period("240")
[dy_hi,  dy_hi_t,  dy_lo,  dy_lo_t,  dy_hi_brk,  dy_lo_brk]  = track_period("1D")
[wk_hi,  wk_hi_t,  wk_lo,  wk_lo_t,  wk_hi_brk,  wk_lo_brk]  = track_period("1W")
[mn_hi,  mn_hi_t,  mn_lo,  mn_lo_t,  mn_hi_brk,  mn_lo_brk]  = track_period("1M")
```

- [ ] **Step 3: Add edge-detection for zone fires AND structure breaks**

```pine
// Edge-detect zone fires
bool f0 = f0_raw and not f0_raw[1]
// ... (all 6)

// Edge-detect structure breaks (first break of previous period high/low)
// These are already edge-detected by track_period (hi_brk_t goes from na to a value)
var int prev_m15_hi_brk = na
bool m15_hi_just_broke = not na(m15_hi_brk) and na(prev_m15_hi_brk)
prev_m15_hi_brk := m15_hi_brk

var int prev_m15_lo_brk = na
bool m15_lo_just_broke = not na(m15_lo_brk) and na(prev_m15_lo_brk)
prev_m15_lo_brk := m15_lo_brk
// ... (repeat for h1, h4, dy, wk, mn)
```

**Important edge-detection note:** `track_period` returns `hi_brk_t` which transitions from `na` to a timestamp once. We edge-detect by comparing current vs previous value: `not na(brk_t) and na(prev_brk_t)`.

- [ ] **Step 4: Add zone arrays + execution loop**

```pine
var array<Zone> zones0 = array.new<Zone>()
// ... (all 6)

if i_p0_on
    zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, "5", m15_hi_just_broke, m15_lo_just_broke)
if i_p1_on
    zones1.process(f1, zt1, zb1, s1, tm1, h1s1, l1s1, "15", h1_hi_just_broke, h1_lo_just_broke)
if i_p2_on
    zones2.process(f2, zt2, zb2, s2, tm2, h1s2, l1s2, "60", h4_hi_just_broke, h4_lo_just_broke)
if i_p3_on
    zones3.process(f3, zt3, zb3, s3, tm3, h1s3, l1s3, "240", dy_hi_just_broke, dy_lo_just_broke)
if i_p4_on
    zones4.process(f4, zt4, zb4, s4, tm4, h1s4, l1s4, "1D", wk_hi_just_broke, wk_lo_just_broke)
if i_p5_on
    zones5.process(f5, zt5, zb5, s5, tm5, h1s5, l1s5, "1W", mn_hi_just_broke, mn_lo_just_broke)
```

- [ ] **Step 5: Verify compiles in TradingView**

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/system/iora_zones_push_cross.pine
git commit -m "feat(zones): add iora_zones_push_cross.pine — cross-TF push zone detection"
```

---

## Task 9: Visual verification + final commit

- [ ] **Step 1: Load both indicators on a chart (e.g., GBPUSD M15)**

Enable H1 + H4 on both indicators. Verify:
- Zones appear correctly with ORIZ spec boundaries
- Broken zones get deleted (not styled as ghosts)
- Push zones are highlighted with thicker border and brighter fill
- Labels show TF + S/D + PUSH for push zones
- No compilation errors or runtime warnings

- [ ] **Step 2: Compare self-TF vs cross-TF**

On the same chart, the self-TF push zones should highlight based on same-TF HH/LL events, while cross-TF should highlight based on higher-TF structure breaks. They should mostly agree but differ in timing.

- [ ] **Step 3: Final commit if any adjustments needed**

```bash
git add tw_indicators/system/iora_zones_push_self.pine tw_indicators/system/iora_zones_push_cross.pine
git commit -m "fix(zones): visual adjustments to push zone indicators"
```
