# Iora Unified Detection + Signal Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 4 separate Pine Script indicators with 2 production indicators — a Detection Engine (structural state) and a Signal Engine (entry/exit signals).

**Architecture:** Two independent overlay indicators sharing the same computation preamble (7 `request.security` calls each). Detection Engine consolidates envelope + conviction + legs + structure + EW. Signal Engine adds zones + consumption + cascade + terminal gate + 4 entry models.

**Tech Stack:** Pine Script v6, TradingView, `request.security` with lookahead, UDTs, arrays, box/label/line drawing.

**Spec:** `docs/superpowers/specs/2026-03-30-iora-unified-detection-signals-design.md`

**Coding rules:** `CLAUDE.md` (root) — always `//@version=6`, explicit types, no multiline ternaries, no reserved keywords, `request.security` tuples max 40, field assignment via local variable not `.get().field :=`, broken zones deleted immediately.

**Pine v6 reference:** `docs/pinescriptv6/LLM_MANIFEST.md` for routing. Key files: `reference/functions/request.md`, `reference/functions/collections.md`, `reference/functions/drawing.md`, `concepts/objects.md`.

**Validation:** Paste each completed indicator into TradingView on GBPUSD M1 chart. Each task ends with "compiles cleanly" as the baseline, plus visual checks noted per task.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tw_indicators/iora_structure/iora_detection.pine` | CREATE | Unified detection: envelope + conviction + legs + period breaks + swing state + EW + dashboard |
| `tw_indicators/iora_structure/iora_signals.pine` | CREATE | Unified signals: preamble + zones + counting + consumption + cascade + terminal + D-cycle + entry models + dashboard |
| `tw_indicators/iora_structure/dev/iora_envelope.pine` | MOVE | Module 1 → dev/ |
| `tw_indicators/iora_structure/dev/iora_conviction.pine` | MOVE | Module 2 → dev/ |
| `tw_indicators/iora_structure/dev/iora_bos_choch_v2.pine` | MOVE | Module 3 → dev/ |
| `tw_indicators/iora_structure/dev/iora_legs.pine` | MOVE | Module 4 → dev/ |

---

## Task 1: Detection Engine — Shared Preamble (request.security + envelope + gradients)

**Files:**
- Create: `tw_indicators/iora_structure/iora_detection.pine`
- Reference: `tw_indicators/iora_structure/iora_conviction.pine` (copy envelope pattern)

This task creates the indicator shell with `request.security` calls, envelope computation for all 8 TFs (M1-MN), and gradient computation. This is the foundation everything else builds on.

- [ ] **Step 1: Create indicator shell with inputs**

Create `iora_detection.pine` with `//@version=6`, `indicator("Iora Detection Engine", overlay=true)`, and all input groups from the spec:
- Structure Labels group (i_show_choch, i_show_bos, i_show_propag, i_struct_tf)
- Swing Markers group (i_swing_tf)
- Elliott Wave group (i_ew_labels, i_ew_fib)
- Envelope group (i_env_show, i_env_tf)
- Dashboard group (i_dash_on, i_dash_pos)

- [ ] **Step 2: Add 7 request.security calls**

Copy the tuple pattern from `iora_conviction.pine` lines 29-34. Add MN:
```pine
[m5o,  m5h,  m5l,  m5c,  m5t,  m5tc]  = request.security(syminfo.tickerid, "5",   [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[m15o, m15h, m15l, m15c, m15t, m15tc] = request.security(syminfo.tickerid, "15",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[h1o,  h1h,  h1l,  h1c,  h1t,  h1tc]  = request.security(syminfo.tickerid, "60",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[h4o,  h4h,  h4l,  h4c,  h4t,  h4tc]  = request.security(syminfo.tickerid, "240", [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[d_o,  d_h,  d_l,  d_c,  d_t,  d_tc]  = request.security(syminfo.tickerid, "1D",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[w_o,  w_h,  w_l,  w_c,  w_t,  w_tc]  = request.security(syminfo.tickerid, "1W",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
[mn_o, mn_h, mn_l, mn_c, mn_t, mn_tc] = request.security(syminfo.tickerid, "1M",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
```

Add new-period detection booleans for all 7 TFs.

- [ ] **Step 3: Add envelope computation for all 8 TFs**

Copy the envelope computation from `iora_conviction.pine` lines 47-158. Add MN envelope (child=W, N=4: 3 closed + 1 building). M1 envelope is trivial: `m1_env_ceil = high`, `m1_env_mid = close`, `m1_env_floor = low`.

- [ ] **Step 4: Add gradient computation for all 8 TFs**

Copy from `iora_conviction.pine` lines 164-190. Add M1 gradients (`ta.change(high)`, `ta.change(close)`, `ta.change(low)`) and MN gradients.

- [ ] **Step 5: Validate — paste into TradingView**

Expected: compiles cleanly on GBPUSD M1. No visual output yet (no plots/dashboard). No errors.

---

## Task 2: Detection Engine — Conviction + Leg Tracking (all 8 TFs)

**Files:**
- Modify: `tw_indicators/iora_structure/iora_detection.pine`
- Reference: `tw_indicators/iora_structure/iora_conviction.pine` (conviction pattern), `tw_indicators/iora_structure/iora_legs.pine` (leg transition pattern)

- [ ] **Step 1: Add helper functions**

Copy `assess_conv()` and `src_grad()` from `iora_conviction.pine` lines 197-233. Copy `leg_transition()` from `iora_legs.pine` lines 178-222.

- [ ] **Step 2: Add M1 conviction + leg state**

M1 uses raw bar data as child:
```pine
var int m1_leg = 0
if m1_leg == 0 and nz(m1_mid_d) != 0.0
    m1_leg := nz(m1_mid_d) > 0.0 ? 1 : -1
bool m1_fbrk = false  // M1 has no child — floor break = price < env_floor (self)
bool m1_cbrk = false  // same — ceil break = price > env_ceil (self)
// M1 conviction uses previous bar's envelope as reference
bool m1_fbrk2 = low < nz(m1_env_floor[1])
bool m1_cbrk2 = high > nz(m1_env_ceil[1])
```
Then assess_conv and leg_transition for M1 using raw high/low as child data.

- [ ] **Step 3: Add M5 through W conviction + leg state**

Copy the per-TF conviction + leg blocks from `iora_legs.pine`. Each TF follows the same pattern: conviction assessment → leg_transition() → update state.

Health tracking per TF (from `iora_conviction.pine` pattern): track WEAK events, increment counter on counter-trend, decrement on with-trend.

- [ ] **Step 4: Add MN conviction + leg state (new code)**

MN has no existing module to copy from — write from scratch following the same pattern as the other TFs. Child = W (`w_l`/`w_h`), parent envelope window N=4 (3 closed + 1 building monthly candle). Use the same `assess_conv()` → `leg_transition()` flow. Test that MN conviction fires on weekly closes.

- [ ] **Step 5: Validate — paste into TradingView**

Expected: compiles cleanly. Still no visual output. Verify no errors.

---

## Task 3: Detection Engine — Period-Level Breaks + Swing State Machine

**Files:**
- Modify: `tw_indicators/iora_structure/iora_detection.pine`
- Reference: `tw_indicators/iora_structure/iora_bos_choch_v2.pine` (track_period + swing_state pattern)

- [ ] **Step 1: Add track_period() function**

Copy from `iora_bos_choch_v2.pine`. This function uses `ta.change(time(tf))` to detect period boundaries and track prev_hi/prev_lo/first break times per TF.

- [ ] **Step 2: Add swing_state() function**

Copy from `iora_bos_choch_v2.pine`. Takes period-level break data + parent hi/lo, returns trend direction, break event, swing classification, BOS/CHoCH type, propagation flag.

- [ ] **Step 3: Call track_period for all 7 TFs (M5-MN)**

```pine
[m5_phi, m5_phit, m5_plo, m5_plot, m5_hbrk, m5_lbrk] = track_period("5")
[m15_phi, ...] = track_period("15")
// ... through MN
[mn_phi, mn_phit, mn_plo, mn_plot, mn_hbrk, mn_lbrk] = track_period("1M")
```

- [ ] **Step 4: Call swing_state for all 7 TFs with parent propagation**

Parent mapping: M5→M15, M15→H1, H1→H4, H4→D, D→W, W→MN, MN→none.

- [ ] **Step 5: Add CHoCH/BOS label drawing**

Copy label drawing logic from `iora_bos_choch_v2.pine`. Gate by `i_show_choch`, `i_show_bos`, `i_show_propag`, and `i_struct_tf` (minimum TF filter). Only draw on bars where break event fires (edge-detected).

- [ ] **Step 6: Add swing marker plotshapes**

For the selected `i_swing_tf`, draw HH/HL/LH/LL triangles at transition points. Copy pattern from `iora_legs.pine` lines 492-498.

- [ ] **Step 7: Validate — paste into TradingView**

Expected: compiles. CHoCH labels visible for H1+ on chart. Swing markers for H1. Compare visually against Module 3 (load both, check same events fire at same bars).

---

## Task 4: Detection Engine — EW Wave Tracking + Pattern Classification + Dashboard

**Files:**
- Modify: `tw_indicators/iora_structure/iora_detection.pine`
- Reference: `tw_indicators/iora_structure/iora_legs.pine` (EW state machine), `docs/system/mechanical_structure_legs/EW_PATTERNS.md`

- [ ] **Step 1: Add EW state variables for 4 TFs (M15, H1, H4, D)**

Each TF gets its own set: `ew_phase`, `ew_imp_cnt`, `ew_cor_cnt`, bull/bear impulse pivots (W1-W5), correction pivots (A/B/C). Use a naming convention: `m15_ew_phase`, `h1_ew_phase`, `h4_ew_phase`, `d_ew_phase`.

- [ ] **Step 2: Add EW state machine logic per TF**

Adapt the EW state machine from `iora_legs.pine` lines 330-470. Instead of one muxed TF, run the state machine 4 times using each TF's leg data (dir, lnum, swc, fired, lhi, llo, phi, plo).

The key mapping: leg transition `fired` + `swc` (swing class) drives the wave count. HH in bull phase = impulse continuation. LH = potential correction transition. Mirror for bear.

- [ ] **Step 3: Add EW pattern classification per TF**

Adapt from `iora_legs.pine` lines 474-540. Run for each of the 4 EW TFs. Each produces `ew_pattern` (0-9).

- [ ] **Step 4: Add dynamic exhaustion threshold per TF**

```pine
// Per TF: threshold based on pattern
int m15_ew_thr = m15_ew_pat == 2 ? 4 : m15_ew_pat == 3 ? 8 : 5
int h1_ew_thr  = h1_ew_pat  == 2 ? 4 : h1_ew_pat  == 3 ? 8 : 5
int h4_ew_thr  = h4_ew_pat  == 2 ? 4 : h4_ew_pat  == 3 ? 8 : 5
int d_ew_thr   = d_ew_pat   == 2 ? 4 : d_ew_pat   == 3 ? 8 : 5
```

- [ ] **Step 5: Add optional EW wave labels**

When `i_ew_labels` is true, draw W1/W2/.../A/B/C labels at swing points for each tracked TF. Gate by `ew_fired` per TF.

- [ ] **Step 6: Add optional Fibonacci projection lines**

When `i_ew_fib` is true, draw W3 target (1.618x W1) and W5 target (1.0x W1 from W4) lines. Adapt from `iora_legs.pine` lines 500-540.

- [ ] **Step 7: Build the unified dashboard**

8 columns × 8 rows (1 header + 7 data: M5/M15/H1/H4/D/W/MN):

```
TF | Dir | Swing | Conv | Hlth | EW | Pat | Exh
```

Use `table.new()` with position from `i_dash_pos`. Only render on `barstate.islast`. Color logic per spec:
- Dir: green=UP, red=DN
- Swing: HH/HL=green shades, LH/LL=red shades
- Conv: STRG=bright, WEAK=faded, PRE=orange
- Hlth: OK=green, 1st=yellow, DEG=orange, BRK=red
- EW: wave count (W1-W5/A-C), bull=green, bear=red. M5/W/MN show "—"
- Pat: IMP=trend color, DIAG=orange, corrections=purple
- Exh: count/threshold with green→red gradient

Helper functions for cell text/color (adapt from existing modules' dashboard helpers).

- [ ] **Step 8: Add optional envelope lines (debugging)**

When `i_env_show` is true, plot step-lines for the selected `i_env_tf`'s floor/mid/ceil. Copy pattern from `iora_envelope.pine`.

- [ ] **Step 9: Validate — paste into TradingView**

Expected: compiles. Unified dashboard shows all 7 TFs with Dir/Swing/Conv/Hlth columns populated. EW/Pat/Exh columns populated for M15/H1/H4/D. CHoCH labels and swing markers visible. Compare against Modules 1-4 loaded side by side — dashboard should show equivalent data.

- [ ] **Step 10: Commit**

```bash
git add tw_indicators/iora_structure/iora_detection.pine
git commit -m "feat: Detection Engine — unified indicator replacing Modules 1-4"
```

---

## Task 5: Signal Engine — Shared Preamble + Zone UDT + Zone Creation

**Files:**
- Create: `tw_indicators/iora_structure/iora_signals.pine`
- Reference: `tw_indicators/iora_structure/iora_detection.pine` (copy preamble)

- [ ] **Step 1: Create indicator shell**

`//@version=6`, `indicator("Iora Signal Engine", overlay=true, max_boxes_count=500, max_labels_count=500, max_lines_count=500)`. Add all Signal Engine inputs from spec (Zones, Signals, Dashboard groups).

- [ ] **Step 2: Copy shared preamble**

Copy the entire preamble from `iora_detection.pine`: request.security calls, envelope computation, gradients, conviction helpers, M1/M5-MN conviction + leg tracking. This is identical code (~400-500 lines).

- [ ] **Step 3: Define Zone UDT**

```pine
type Zone
    float top       = na
    float bottom    = na
    int   side      = 0
    int   swing_cls = 0
    int   tf_idx    = 0
    int   birth_bar = 0
    bool  broken    = false
    box   bx        = na
```

- [ ] **Step 4: Create zone arrays (per TF per side)**

```pine
var array<Zone> m1_sup  = array.new<Zone>(0)
var array<Zone> m1_dem  = array.new<Zone>(0)
var array<Zone> m5_sup  = array.new<Zone>(0)
var array<Zone> m5_dem  = array.new<Zone>(0)
// ... through D
var array<Zone> d_sup   = array.new<Zone>(0)
var array<Zone> d_dem   = array.new<Zone>(0)
```

- [ ] **Step 5: Add zone creation logic**

On each TF's leg transition (`fired == true`):

**Zone body computation:** The zone body represents the order block — the candle body at the swing extreme. Since the leg transition fires on the CURRENT bar (when STRONG conviction confirms), not the bar where the swing extreme formed, we use the HTF candle open from `request.security` as a proxy:
- Supply (UP→DOWN): `top = leg_high`, `bottom = max(child_open, child_close)` where child is the HTF building candle (e.g., `m15o` for M15). This approximates the candle body at the swing high. If child data is unavailable, fallback: `bottom = leg_high - (leg_high - leg_low) * 0.3`.
- Demand (DOWN→UP): `bottom = leg_low`, `top = min(child_open, child_close)`. Fallback: `top = leg_low + (leg_high - leg_low) * 0.3`.

Steps:
- If previous direction was UP (now flipping DOWN) → create SUPPLY zone:
  - `top = leg_high`, `bottom` from HTF candle body (see above)
  - `side = -1`, `swing_cls` from leg tracker's swing classification
  - Draw box if enabled for this TF
- If previous direction was DOWN (now flipping UP) → create DEMAND zone:
  - `bottom = leg_low`, `top` from HTF candle body
  - `side = 1`, `swing_cls` from leg tracker
  - Draw box if enabled

**Known limitation:** Zone bodies are approximate since we don't track the exact bar_index of the swing extreme. This can be refined later by storing swing bar indices in the leg tracker.

Cap arrays at `i_max_zones` (default 8) — delete oldest when exceeded.

- [ ] **Step 6: Add zone break checking**

Every bar, iterate over all zone arrays. For each unbroken zone:
- Supply: if `close > zone.top` → mark broken, `box.delete(zone.bx)`, remove from array
- Demand: if `close < zone.bottom` → mark broken, `box.delete(zone.bx)`, remove from array

- [ ] **Step 7: Validate — paste into TradingView**

Expected: compiles. H1/H4 zone boxes appear on chart at swing points. Red = supply, green = demand. Boxes disappear when price closes through them. Verify zones form at correct structural swing points by comparing with Detection Engine's swing markers.

---

## Task 6: Signal Engine — Zone Counting + Opposing Nesting

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add zone counting per TF**

Track count of unbroken zones in current impulse direction:
```pine
var int h1_zone_cnt = 0
var int h1_zone_dir = 0  // +1=counting demand (bullish), -1=counting supply (bearish)
```

On zone creation at H1:
- If swing_cls is HH or HL (bullish swings) and `h1_zone_dir >= 0`: increment count
- If swing_cls is LL or LH (bearish swings) and `h1_zone_dir <= 0`: increment count
- On CHoCH (direction flip from HH→LH or LL→HL): reset count to 1, flip direction

Same pattern for H4 and D zone counting.

- [ ] **Step 2: Add H1 EW state machine for exhaustion threshold**

The Signal Engine needs EW pattern classification to adjust zone count thresholds. EW is NOT part of the shared preamble — it must be added explicitly here. Implement a simplified version that only tracks H1 (the primary zone counting TF):

1. Add H1 EW state variables: `h1_ew_phase`, `h1_ew_imp_cnt`, bull/bear pivots (W1-W5)
2. Add the 5-phase state machine driven by H1 leg transitions (same logic as Detection Engine Task 4 Step 2, but only for H1)
3. Add H1 EW pattern classification (IMPULSE/DIAGONAL/EXTENDED — same as Detection Engine Task 4 Step 3, only for H1)
4. Derive threshold:

```pine
int h1_ew_pat = ... // from pattern classification above
int h1_ew_thr = h1_ew_pat == 2 ? 4 : h1_ew_pat == 3 ? 8 : 5
```

This adds ~80 lines. Only H1 is tracked (not M15/H4/D) since H1 is the primary zone counting timeframe.

- [ ] **Step 3: Add opposing nesting detection**

Check H1 zones inside opposing H4 zones:
```pine
bool opp_nesting = false
// Check: is there an H1 demand zone geometrically inside an H4 supply zone?
for int i = 0 to math.min(h1_dem.size() - 1, 3)
    Zone hd = h1_dem.get(i)
    for int j = 0 to math.min(h4_sup.size() - 1, 3)
        Zone hs = h4_sup.get(j)
        if hd.top < hs.top and hd.bottom > hs.bottom
            opp_nesting := true
// Mirror: H1 supply inside H4 demand
for int i = 0 to math.min(h1_sup.size() - 1, 3)
    Zone hs2 = h1_sup.get(i)
    for int j = 0 to math.min(h4_dem.size() - 1, 3)
        Zone hd2 = h4_dem.get(j)
        if hs2.bottom > hd2.bottom and hs2.top < hd2.top
            opp_nesting := true
```

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles. Internally the zone count and nesting state are tracked. No new visual output yet (will show in dashboard later). Verify no errors.

---

## Task 7: Signal Engine — Momentum Consumption State Machine

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Define ConsumptionCycle UDT and state**

```pine
type ConsumptionCycle
    string parent_tf  = ""
    int    parent_dir = 0
    bool   active     = false
    bool   m1_flip    = false
    bool   m5_flip    = false
    bool   m15_flip   = false
    bool   h1_flip    = false
    int    score      = 0

var ConsumptionCycle consume = ConsumptionCycle.new()
```

- [ ] **Step 2: Trigger on parent STRONG CHoCH**

When H4 conviction fires STRONG (h4_cv == 3):
```pine
if h4_cv == 3
    consume.parent_tf  := "H4"
    consume.parent_dir := h4_sd
    consume.active     := true
    consume.m1_flip    := false
    consume.m5_flip    := false
    consume.m15_flip   := false
    consume.h1_flip    := false
    consume.score      := 0
```

Also trigger on D STRONG CHoCH (creates a new cycle that supersedes H4).

- [ ] **Step 3: Track child flips**

Each bar when cycle is active:
```pine
if consume.active
    if not consume.m1_flip and m1_cv == 3 and m1_sd == consume.parent_dir
        consume.m1_flip := true
        consume.score   := consume.score + 1
    if not consume.m5_flip and m5_cv == 3 and m5_sd == consume.parent_dir
        consume.m5_flip := true
        consume.score   := consume.score + 1
    if not consume.m15_flip and m15_cv == 3 and m15_sd == consume.parent_dir
        consume.m15_flip := true
        consume.score    := consume.score + 1
    if not consume.h1_flip and h1_cv == 3 and h1_sd == consume.parent_dir
        consume.h1_flip := true
        consume.score   := consume.score + 1
```

- [ ] **Step 4: Track per-TF consumption percentage**

For the Signal Dashboard, compute granular consumption per child TF:
```pine
// Per-TF: 0=dormant, 25=PRE, 40=1st_crack, 60=degrading, 75=WEAK, 85=broken, 100=flipped
int m1_cons_pct = consume.m1_flip ? 100 : (m1_cv == 1 and m1_sd == consume.parent_dir ? 25 : ...)
```

Use the conviction level + health state from the shared preamble to derive the percentage per the spec's table.

- [ ] **Step 5: Validate — paste into TradingView**

Expected: compiles. Consumption state tracked internally. Will be visible in dashboard (Task 10).

---

## Task 8: Signal Engine — 1-2-3 Cascade Detection

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add per-TF 1-2-3 detection function**

```pine
// Returns true if 3-zone compression detected at this TF
// bear_123: zone_3 demand top < zone_2 supply bottom
// bull_123: zone_3 supply bottom > zone_2 demand top
detect_123(array<Zone> sup_arr, array<Zone> dem_arr) =>
    bool bear = false
    bool bull = false
    // Bearish: need demand-supply-demand sequence with compression
    if dem_arr.size() >= 2 and sup_arr.size() >= 1
        Zone d1 = dem_arr.get(1)  // older demand
        Zone s1 = sup_arr.get(0)  // latest supply
        Zone d2 = dem_arr.get(0)  // latest demand
        if s1.birth_bar > d1.birth_bar and d2.birth_bar > s1.birth_bar
            bear := d2.top < s1.bottom
    // Bullish: need supply-demand-supply sequence with compression
    if sup_arr.size() >= 2 and dem_arr.size() >= 1
        Zone s1b = sup_arr.get(1)
        Zone d1b = dem_arr.get(0)
        Zone s2b = sup_arr.get(0)
        if d1b.birth_bar > s1b.birth_bar and s2b.birth_bar > d1b.birth_bar
            bull := s2b.bottom > d1b.top
    [bear, bull]
```

- [ ] **Step 2: Run 1-2-3 detection for D, H4, H1, M15, M5**

```pine
[d_123_bear,  d_123_bull]  = detect_123(d_sup, d_dem)
[h4_123_bear, h4_123_bull] = detect_123(h4_sup, h4_dem)
[h1_123_bear, h1_123_bull] = detect_123(h1_sup, h1_dem)
[m15_123_bear, m15_123_bull] = detect_123(m15_sup, m15_dem)
[m5_123_bear, m5_123_bull] = detect_123(m5_sup, m5_dem)
```

- [ ] **Step 3: Add cascade arming with containment check**

```pine
// Containment: is current close inside any unbroken zone at parent TF?
is_inside_zone(array<Zone> zones) =>
    bool inside = false
    for int i = 0 to math.min(zones.size() - 1, 7)
        Zone z = zones.get(i)
        if not z.broken and close >= z.bottom and close <= z.top
            inside := true
    inside

// Cascade arming — bearish direction
bool d_armed_bear  = d_123_bear
bool h4_armed_bear = d_armed_bear and h4_123_bear and is_inside_zone(d_sup)
bool h1_armed_bear = h4_armed_bear and h1_123_bear and is_inside_zone(h4_sup)
bool m15_armed_bear = h1_armed_bear and m15_123_bear and is_inside_zone(h1_sup)
bool m5_armed_bear = m15_armed_bear and m5_123_bear and is_inside_zone(m15_sup)

// Mirror for bullish
bool d_armed_bull  = d_123_bull
bool h4_armed_bull = d_armed_bull and h4_123_bull and is_inside_zone(d_dem)
// ... etc

// Output: highest armed level
string cascade_level = m5_armed_bear or m5_armed_bull ? "M5" : m15_armed_bear or m15_armed_bull ? "M15" : h1_armed_bear or h1_armed_bull ? "H1" : h4_armed_bear or h4_armed_bull ? "H4" : d_armed_bear or d_armed_bull ? "D" : "—"
int cascade_dir = m5_armed_bear ? -1 : m5_armed_bull ? 1 : 0
```

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles. Cascade state tracked internally. Will be visible in dashboard (Task 10).

---

## Task 9: Signal Engine — Terminal Gate + D-Level Cycle Phase + Trendline Breaks

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add trendline break detection for M5 and M15**

```pine
// Trendline: connect last 2 swing lows (ascending) or highs (descending)
// Break: close crosses through the projected TL value
// Uses leg tracker's prev_leg_low/high + current values

// M5 ascending TL (bullish support)
var float m5_tl_bull_y1 = na
var float m5_tl_bull_y2 = na
var int   m5_tl_bull_x1 = na
var int   m5_tl_bull_x2 = na
// Update on M5 HL swing (swing_cls == 4)
if m5_fired and m5_swc == 4
    m5_tl_bull_y1 := m5_plo  // previous swing low
    m5_tl_bull_x1 := bar_index[math.max(m5_lnum * 5, 1)]  // approximate bar of prev swing
    m5_tl_bull_y2 := m5_llo  // current swing low
    m5_tl_bull_x2 := bar_index

// Project TL to current bar and check break
float m5_tl_bull_proj = na
if not na(m5_tl_bull_x1) and not na(m5_tl_bull_x2) and m5_tl_bull_x2 > m5_tl_bull_x1
    float slope = (m5_tl_bull_y2 - m5_tl_bull_y1) / (m5_tl_bull_x2 - m5_tl_bull_x1)
    m5_tl_bull_proj := m5_tl_bull_y2 + slope * (bar_index - m5_tl_bull_x2)
bool m5_tl_bull_break = not na(m5_tl_bull_proj) and close < m5_tl_bull_proj and close[1] >= nz(m5_tl_bull_proj[1])

// Same pattern for M5 descending TL (bearish resistance) — using LH swings
// Same pattern for M15 ascending + descending TLs
```

Implement all 4 trendlines: m5_bull, m5_bear, m15_bull, m15_bear.

- [ ] **Step 2: Add terminal exhaustion gate**

```pine
// D level broken: check if D leg tracker has a confirmed swing (swc != 0)
bool d_level_broken = d_swc != 0  // D HH/HL/LH/LL has been confirmed

// H4 counter-zone beyond D level:
// If D direction is DOWN (bearish) → need H4 demand below D's prev_lo
// If D direction is UP (bullish) → need H4 supply above D's prev_hi
bool h4_counter = false
if d_dir < 0 and h4_dem.size() > 0
    Zone z = h4_dem.get(0)
    h4_counter := z.bottom < nz(d_plo)
else if d_dir > 0 and h4_sup.size() > 0
    Zone z = h4_sup.get(0)
    h4_counter := z.top > nz(d_phi)

// H1 zone count meets EW-adjusted threshold
bool h1_count_met = h1_zone_cnt >= h1_ew_thr

// Terminal gate
bool terminal_active = d_level_broken and h4_counter and h1_count_met and opp_nesting
```

- [ ] **Step 3: Add D-Level cycle phase state machine**

The D-cycle phases track the progression AFTER a terminal exhaustion event. The phases use separate conditions — `terminal_active` is the entry gate for Phase A, but subsequent phases use their own tracking state since `terminal_active` may turn off as conditions change.

```pine
var int d_cycle_phase = 0     // 0=unknown, 1=A, 2=B, 3=C, 4=D, 5=E
var bool d_cycle_running = false
var float d_cycle_boundary_hi = na   // boundary zone top (from terminal)
var float d_cycle_boundary_lo = na   // boundary zone bottom

// Phase A entry: terminal exhaustion first fires
if terminal_active and not d_cycle_running
    d_cycle_phase := 1
    d_cycle_running := true
    // Mark boundary zone: range from last unbroken H1 zone edge to the structural extreme
    if d_dir < 0  // bearish terminal → boundary is the resistance above
        d_cycle_boundary_hi := nz(d_phi)
        d_cycle_boundary_lo := h1_sup.size() > 0 ? h1_sup.get(0).bottom : nz(d_phi)
    else
        d_cycle_boundary_lo := nz(d_plo)
        d_cycle_boundary_hi := h1_dem.size() > 0 ? h1_dem.get(0).top : nz(d_plo)

// Phase transitions (only when cycle is running)
if d_cycle_running
    if d_cycle_phase == 1
        // A → B: H4 counter-zone confirmed (h4_counter already tracks this)
        if h4_counter
            d_cycle_phase := 2
    else if d_cycle_phase == 2
        // B → C: price enters boundary zone
        bool in_boundary = close >= d_cycle_boundary_lo and close <= d_cycle_boundary_hi
        if in_boundary
            d_cycle_phase := 3
    else if d_cycle_phase == 3
        // C → D: D LH/HL confirmed (new D swing in reversal direction)
        if d_fired and d_swc != 0
            d_cycle_phase := 4
    else if d_cycle_phase == 4
        // D → E: new D extreme prints (D swing in push direction)
        if d_fired and ((d_dir < 0 and d_swc == 3) or (d_dir > 0 and d_swc == 1))
            d_cycle_phase := 5
    else if d_cycle_phase == 5
        // E → A: cycle restarts if new terminal fires
        d_cycle_running := false
        d_cycle_phase := 0
```

**Note:** Phase detection will be refined during visual validation. The boundary zone tracking is approximate — it uses the last D extreme and H1 zone edges at cycle start.

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles. All state machines running internally. No new visual output yet.

---

## Task 10a: Signal Engine — Entry Models A + B

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add M15 nesting check helper**

```pine
// Is there an M15 zone nested inside an H4 zone on the reversal side?
// LONG reversal: M15 demand inside H4 demand
// SHORT reversal: M15 supply inside H4 supply
is_m15_nested_h4(int reversal_dir) =>
    bool nested = false
    array<Zone> m15_z = reversal_dir > 0 ? m15_dem : m15_sup
    array<Zone> h4_z  = reversal_dir > 0 ? h4_dem  : h4_sup
    for int i = 0 to math.min(m15_z.size() - 1, 3)
        Zone mz = m15_z.get(i)
        for int j = 0 to math.min(h4_z.size() - 1, 3)
            Zone hz = h4_z.get(j)
            if mz.top <= hz.top and mz.bottom >= hz.bottom
                nested := true
    nested
```

- [ ] **Step 2: Add Entry Model A signal (Terminal Reversal)**

```pine
// Model A: Terminal Reversal
int reversal_dir = d_dir < 0 ? 1 : d_dir > 0 ? -1 : 0  // opposite of D direction
bool m15_tl_brk = reversal_dir > 0 ? m15_tl_bear_break : m15_tl_bull_break  // M15 TL break in reversal direction
bool model_a = terminal_active and consume.score >= 2 and is_m15_nested_h4(reversal_dir) and m15_tl_brk and (cascade_dir == reversal_dir and cascade_level == "M5") and m1_cv == 3 and m1_sd == reversal_dir

var bool model_a_prev = false
bool model_a_fire = model_a and not model_a_prev
model_a_prev := model_a
```

- [ ] **Step 3: Add Entry Model B signal (Mode B Continuation)**

```pine
// Model B: Mode B Continuation — D-cycle Phase D push with full consumption
bool model_b = d_cycle_phase == 4 and consume.score == 4 and (m5_fired or m15_fired)

var bool model_b_prev = false
bool model_b_fire = model_b and not model_b_prev
model_b_prev := model_b
```

Where `m5_fired`/`m15_fired` are booleans for M5/M15 period breaks firing on this bar (from signal preamble conviction state).

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles cleanly. No visual output yet for Models A/B (plotshape added in Task 10c).

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): entry models A (terminal reversal) + B (mode B continuation)"
```

---

## Task 10b: Signal Engine — Entry Models C + D

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add zone-containment helper**

```pine
// Is the current price inside a zone from the given array?
is_inside_zone(array<Zone> zones) =>
    bool inside = false
    for int i = 0 to math.min(zones.size() - 1, 3)
        Zone z = zones.get(i)
        if close >= z.bottom and close <= z.top
            inside := true
    inside
```

- [ ] **Step 2: Add Entry Model C signal (1-2-3 Cascade Add-On)**

```pine
// Model C: 1-2-3 Cascade Add-On — M5 cascade fires while inside aligned zone
int cascade_add_dir = cascade_dir
bool in_zone_c = cascade_add_dir > 0 ? (is_inside_zone(m15_dem) or is_inside_zone(h1_dem)) : (is_inside_zone(m15_sup) or is_inside_zone(h1_sup))
bool model_c = cascade_level == "M5" and m1_cv == 3 and m1_sd == cascade_add_dir and in_zone_c

var bool model_c_prev = false
bool model_c_fire = model_c and not model_c_prev
model_c_prev := model_c
```

- [ ] **Step 3: Add Entry Model D signal (Macro Bias Limit Order)**

```pine
// Model D: Macro Bias Limit Order — M5 TL break inside H4/D zone, no terminal
bool m5_tl_brk_d = d_dir > 0 ? m5_tl_bull_break : m5_tl_bear_break
bool in_zone_d = d_dir > 0 ? (is_inside_zone(h4_dem) or is_inside_zone(d_dem)) : (is_inside_zone(h4_sup) or is_inside_zone(d_sup))
bool model_d = m5_tl_brk_d and in_zone_d and not terminal_active

var bool model_d_prev = false
bool model_d_fire = model_d and not model_d_prev
model_d_prev := model_d
```

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles cleanly.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): entry models C (cascade add-on) + D (macro bias limit)"
```

---

## Task 10c: Signal Engine — SL/TP Computation + On-Chart Signal Lines

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Add shared signal state variables**

```pine
var float sig_entry = na
var float sig_sl    = na
var float sig_tp    = na
var int   sig_model = 0
var int   sig_dir   = 0
```

- [ ] **Step 2: Add entry/SL/TP computation for each model**

On signal fire, compute entry price, SL, TP from zone edges:
```pine
if model_a_fire
    sig_model := 1
    sig_dir   := reversal_dir
    if reversal_dir > 0 and m5_dem.size() > 0
        Zone ez = m5_dem.get(0)
        sig_entry := ez.bottom
    else if reversal_dir < 0 and m5_sup.size() > 0
        Zone ez = m5_sup.get(0)
        sig_entry := ez.top
    if m1_sup.size() > 0 and reversal_dir > 0
        Zone sz = m1_sup.get(0)
        sig_sl := sz.top + syminfo.mintick * 10
    if reversal_dir > 0 and h1_sup.size() > 0
        Zone tz = h1_sup.get(0)
        sig_tp := tz.bottom
```
Repeat equivalent blocks for Models B/C/D with appropriate zone sources and directions.

- [ ] **Step 3: Add on-chart signal markers (plotshape)**

```pine
plotshape(model_a_fire and sig_dir > 0,  "Model A Long",  shape.diamond,    location.belowbar, #26A69A, size=size.normal)
plotshape(model_a_fire and sig_dir < 0,  "Model A Short", shape.diamond,    location.abovebar, #EF5350, size=size.normal)
plotshape(model_b_fire and sig_dir > 0,  "Model B Long",  shape.arrowup,    location.belowbar, #42A5F5, size=size.small)
plotshape(model_b_fire and sig_dir < 0,  "Model B Short", shape.arrowdown,  location.abovebar, #42A5F5, size=size.small)
plotshape(model_c_fire and sig_dir > 0,  "Model C Long",  shape.triangleup, location.belowbar, #FFCA28, size=size.tiny)
plotshape(model_c_fire and sig_dir < 0,  "Model C Short", shape.triangledown, location.abovebar, #FFCA28, size=size.tiny)
plotshape(model_d_fire and sig_dir > 0,  "Model D Long",  shape.circle,     location.belowbar, #AB47BC, size=size.small)
plotshape(model_d_fire and sig_dir < 0,  "Model D Short", shape.circle,     location.abovebar, #AB47BC, size=size.small)
```

- [ ] **Step 4: Add SL/TP lines on signal fire**

```pine
var line sl_ln = na
var line tp_ln = na
if model_a_fire or model_b_fire or model_c_fire or model_d_fire
    if not na(sl_ln)
        line.delete(sl_ln)
    if not na(tp_ln)
        line.delete(tp_ln)
    if not na(sig_sl)
        sl_ln := line.new(bar_index, sig_sl, bar_index + 50, sig_sl, color=color.new(#EF5350, 30), style=line.style_dashed, width=1)
    if not na(sig_tp)
        tp_ln := line.new(bar_index, sig_tp, bar_index + 50, sig_tp, color=color.new(#26A69A, 30), style=line.style_dashed, width=1)
```

- [ ] **Step 5: Validate — paste into TradingView**

Expected: compiles. Signal markers appear on chart at structural points. SL/TP dashed lines drawn from signal bars. Use TradingView Replay on GBPUSD M1.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): SL/TP computation + on-chart plotshape markers + SL/TP lines"
```

---

## Task 10d: Signal Engine — Signal Dashboard

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine`

- [ ] **Step 1: Build the Signal Dashboard table**

Position from `i_dash_pos` (default Bottom Left). Two sections:

**Top: State Summary** (2 columns × 3 rows):
```
Phase: D        | Terminal: ACTIVE
Consumption: 3/4| H1 Zones: 6/5
Cascade: M5     | Bias: BEAR
```

**Bottom: Active Signal** (when any model fires):
```
Model: A SHORT  | R:R: 1:5.0
Entry: 1.3265   | SL: 1.3282
TP: 1.3180      |
```

Use `table.new()` with border styling matching Detection Engine dashboard.

- [ ] **Step 2: Add R:R computation**

```pine
float rr_ratio = not na(sig_entry) and not na(sig_sl) and not na(sig_tp) ? math.abs(sig_tp - sig_entry) / math.abs(sig_sl - sig_entry) : na
```

Display as `"1:" + str.tostring(rr_ratio, "#.#")` in dashboard.

- [ ] **Step 3: Validate — paste into TradingView**

Expected: compiles. Signal dashboard shows in Bottom Left. Full integration check:
- Zones appear at swings and disappear when broken
- Consumption counter increments as TFs flip
- Terminal gate fires when all 4 conditions met
- Model A fires at terminal reversal points
- Dashboard state summary reflects current engine state
- Active signal section populates when models fire

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): signal dashboard with state summary + active signal display"
```

---

## Task 11: Cleanup — Move Dev Modules + Final Validation

**Files:**
- Move: `iora_structure/iora_envelope.pine` → `iora_structure/dev/`
- Move: `iora_structure/iora_conviction.pine` → `iora_structure/dev/`
- Move: `iora_structure/iora_bos_choch_v2.pine` → `iora_structure/dev/`
- Move: `iora_structure/iora_legs.pine` → `iora_structure/dev/`

- [ ] **Step 1: Create dev directory and move files**

```bash
mkdir -p tw_indicators/iora_structure/dev
mv tw_indicators/iora_structure/iora_envelope.pine tw_indicators/iora_structure/dev/
mv tw_indicators/iora_structure/iora_conviction.pine tw_indicators/iora_structure/dev/
mv tw_indicators/iora_structure/iora_bos_choch_v2.pine tw_indicators/iora_structure/dev/
mv tw_indicators/iora_structure/iora_legs.pine tw_indicators/iora_structure/dev/
```

- [ ] **Step 2: Final validation — both indicators on GBPUSD M1**

Load both `iora_detection.pine` and `iora_signals.pine` on GBPUSD M1 chart. Check:
- Two dashboards, no overlap (Bottom Right + Bottom Left)
- Detection: Dir/Swing/Conv/Hlth/EW/Pat/Exh all populated for each TF
- Signal: Phase/Terminal/Consumption/Zones/Cascade/Bias all showing
- Zones appear and break correctly
- Structure labels (CHoCH) match the Detection Engine's swing markers
- No TradingView errors or warnings

- [ ] **Step 3: Replay validation on EURUSD and XAUUSD**

Repeat the same visual checks on EURUSD M1 and XAUUSD M1 using TradingView Replay. Look for:
- Different volatility profiles producing different EW patterns
- Zone counts reaching 5+ on XAUUSD (high momentum pair)
- Consumption state machine activating correctly on trend changes

- [ ] **Step 4: Commit cleanup**

```bash
git add tw_indicators/iora_structure/dev/
git add -u tw_indicators/iora_structure/
git commit -m "chore: move Modules 1-4 to dev/, production uses Detection + Signal Engine"
```
