# Iora Fractal Zones — Indicator Design Spec

> **Date:** 2026-03-31
> **Parent docs:** `docs/iora_zones/trading_system_spec.html`, `trading_system_spec_addendum_a.html`, `trading_system_spec_addendum_b_extended.html`
> **Output file:** `tw_indicators/iora_zones/iora_fractal_zones.pine`
> **Build approach:** Layered — each layer compiles independently for TradingView Replay validation

---

## 1. Purpose

Visualize the Fractal Push/Pull Trading System on a TradingView chart. The indicator creates zones from Heikin-Ashi color transitions, classifies them (HH/LH/HL/LL), tracks zone lifecycle, runs the Universal Triplet Engine (6 instances of a 4-state machine), draws trendlines with two-layer confirmation, and displays a dashboard with triplet states and composite bias.

## 2. Architecture — Layered Build

| Layer | What it adds | Can compile standalone |
|-------|--------------|-----------------------|
| L1 | HA transition detection, ORIZ zone boxes, HH/LH/HL/LL classification labels | Yes |
| L2 | Universal Triplet Engine — 4-state machine, role-based zone recoloring | Yes (builds on L1) |
| L3 | Trendlines (push → continuation), magnet lines, TL break detection | Yes (builds on L1+L2) |
| L4 | Dashboard — triplet states, composite bias, targets, pullback depth, TL/zone signal | Yes (builds on L1+L2+L3) |

Each layer is a contiguous section in the file, guarded by `bool i_layer_X` inputs so any layer can be toggled off for debugging.

## 3. Data Architecture

### 3.1 request.security() Layout

**HA ticker:** `ticker.heikinashi(syminfo.tickerid)` — for HA OHLC (color transition detection).
**Regular ticker:** `syminfo.tickerid` — for OHLC (zone boundary extremes) and `time` (new-period detection).

| TF | Call 1 (HA) | Call 2 (Regular) |
|----|-------------|------------------|
| H4 | `[haO, haH, haL, haC]` | `[O, H, L, C, time]` |
| D  | `[haO, haH, haL, haC]` | `[O, H, L, C, time]` |
| W  | `[haO, haH, haL, haC]` | `[O, H, L, C, time]` |
| MN | `[haO, haH, haL, haC]` | `[O, H, L, C, time]` |
| H1 | `[haO, haH, haL, haC]` | `[O, H, L, C, time]` |

**Total: 10 request.security() calls** (5 TFs × 2). Well under the 40-call limit. Future expansion to M15/M5/M1 adds 6 more = 16 total.

**Timeframe strings:** `"60"`, `"240"`, `"1D"`, `"1W"`, `"1M"` (per CLAUDE.md rules).

### 3.2 Inputs

```
Group: Zones
  bool i_zone_h1   = true     "Show H1 zones"
  bool i_zone_h4   = true     "Show H4 zones"
  bool i_zone_d    = true     "Show D zones"
  bool i_zone_w    = true     "Show W zones"
  bool i_zone_mn   = true     "Show MN zones"
  int  i_max_zones = 20       "Max zones per TF per side"

Group: Triplet Engine
  bool i_triplets  = true     "Enable triplet state machine"
  bool i_show_t1   = true     "Show T1 (MN→W→D)"
  bool i_show_t2   = true     "Show T2 (W→D→H4)"
  bool i_show_t3   = true     "Show T3 (D→H4→H1)"
  bool i_show_t4   = false    "Show T4 (H4→H1→M15)" — off by default, needs M15 data

Group: Trendlines
  bool i_trendlines = true    "Show trendlines"
  bool i_magnets    = true    "Show magnet lines"

Group: Dashboard
  bool   i_dash     = true    "Show dashboard"
  string i_dash_pos = "Bottom Right"

Group: Layers (debug)
  bool i_layer_1 = true       "L1: Zones + classification"
  bool i_layer_2 = true       "L2: Triplet engine + roles"
  bool i_layer_3 = true       "L3: Trendlines + magnets"
  bool i_layer_4 = true       "L4: Dashboard"
```

### 3.3 New-Period Detection

Per TF: `bool XX_new = ta.change(XX_t) != 0` — detects when a new candle opens on that TF.

## 4. Layer 1 — Zone Creation & Classification

### 4.1 Zone UDT

```
type FractalZone
    float   top          // zone upper boundary (ORIZ)
    float   bottom       // zone lower boundary (ORIZ)
    int     side         // +1 demand, -1 supply
    int     cls          // 1=HH, 2=LH, 3=LL, 4=HL
    int     role         // 0=unassigned, 1=push, 2=continuation, 3=pullback, 4=reversal
    string  tf_str       // "H1", "H4", "D", "W", "MN"
    int     birth_bar    // bar_index at creation
    int     max_age      // TF-specific: 50 for H1-H4, 30 for W, 20 for MN
    box     bx           // drawn box (na if TF hidden)
    label   lbl          // drawn label (na if TF hidden)
```

### 4.2 HA Run Tracking (per TF, `var` persistent)

```
var int   XX_ha_dir     = 0     // current HA color: +1 blue, -1 red
var float XX_run_hi     = na    // highest OHLC high during current HA run
var float XX_run_lo     = na    // lowest OHLC low during current HA run
var float XX_prev_s_top = na    // previous supply top (for HH/LH)
var float XX_prev_d_bot = na    // previous demand bottom (for HL/LL)
```

On each new period for TF XX:
1. Compute HA direction: `ha_dir_now = haC >= haO ? 1 : -1`
2. Update run extremes: `run_hi = math.max(run_hi, ohlcH)`, `run_lo = math.min(run_lo, ohlcL)`
3. If `ha_dir_now != XX_ha_dir` → transition detected → create zone

### 4.3 Zone Creation on HA Transition

**Doji check:** If transition candle `math.abs(haC - haO) / (haH - haL) < 0.05`, use current candle's HA extreme instead of previous.

**ORIZ boundaries:**
- **Supply (blue→red):** `top = run_hi` (highest OHLC high of blue run), `bottom = haL` of transition candle
- **Demand (red→blue):** `top = haH` of transition candle, `bottom = run_lo` (lowest OHLC low of red run)

**Validation:** `top > bottom`, else skip.

**Classification:**
- Supply: `new_top > prev_s_top` → HH (cls=1), else → LH (cls=2)
- Demand: `new_bottom < prev_d_bot` → LL (cls=3), else → HL (cls=4)
- Update `prev_s_top` / `prev_d_bot` after classification.

**Zone arrays:** Per TF, two arrays: `array<FractalZone> XX_sup`, `array<FractalZone> XX_dem`. New zone pushed to front (`.unshift()`). If array size > `i_max_zones`, oldest removed (`.pop()` + delete box/label).

**Zone label format:** `{TF} {S|D} {HH|LH|HL|LL}` — role suffix `[PUSH]` etc. added by Layer 2.

**After transition:** Reset run tracking: `run_hi = ohlcH`, `run_lo = ohlcL`, `XX_ha_dir = ha_dir_now`.

### 4.4 Zone Break Detection (every bar)

Per zone in every array:
- Supply broken: `close > zone.top` (body close above supply top)
- Demand broken: `close < zone.bottom` (body close below demand bottom)
- **Wicks do NOT break zones** — only body close counts.
- On break: delete box, delete label, remove from array. Immediate deletion, no ghost zones.

### 4.5 Zone Expiry (every bar)

- `bar_index - zone.birth_bar > zone.max_age` → delete and remove.
- Max age per TF: H1=50, H4=50, D=50, W=30, MN=20 (per spec).

### 4.6 Zone Colors (Layer 1 defaults, overridden by Layer 2 roles)

| TF | Color |
|----|-------|
| H1 | `#AB47BC` purple |
| H4 | `#FF7043` orange |
| D  | `#FFCA28` gold |
| W  | `#42A5F5` blue |
| MN | `#78909C` gray-blue |

Supply/demand distinguished by box border: supply = red-tinted, demand = blue-tinted. TF color used for fill.

## 5. Layer 2 — Universal Triplet Engine

### 5.1 TripletState UDT

```
type TripletState
    string  id              // "T1" through "T6"
    int     state           // 1=PUSHING, 2=CONTINUING, 3=PULLING_BACK, 4=REVERSING
    int     direction       // +1 bullish, -1 bearish (parent's direction)
    int     push_idx        // index of push zone in child's zone array (-1 = none)
    int     push_side       // +1 demand push, -1 supply push
    float   push_target     // parent zone boundary being pushed toward
    float   pb_target       // push zone edge (magnet for pullbacks)
    float   parent_lh_top   // parent's LH supply top (for reversal detection)
    float   parent_hl_bot   // parent's HL demand bottom (for reversal detection)
    bool    grand_choch     // grandchild CHoCH detected
    bool    grand_break     // grandchild broke parent structure
    bool    compression     // child oscillating at parent boundary
    int     push_fail_cnt   // count of failed body-close attempts at parent boundary
    int     tl_hold_cnt     // count of times child TL held on pullback
```

### 5.2 Six Instances

```
var TripletState t1 = TripletState.new("T1", ...)  // MN → W → D
var TripletState t2 = TripletState.new("T2", ...)  // W  → D → H4
var TripletState t3 = TripletState.new("T3", ...)  // D  → H4 → H1
var TripletState t4 = TripletState.new("T4", ...)  // H4 → H1 → M15 (future)
var TripletState t5 = TripletState.new("T5", ...)  // H1 → M15 → M5 (future)
var TripletState t6 = TripletState.new("T6", ...)  // M15 → M5 → M1 (future)
```

### 5.3 State Transition Function

One function, called for each triplet on every new zone event:

```
update_triplet(TripletState ts,
               array<FractalZone> parent_sup, array<FractalZone> parent_dem,
               array<FractalZone> child_sup, array<FractalZone> child_dem,
               array<FractalZone> grand_sup, array<FractalZone> grand_dem,
               bool child_new_zone, int child_zone_cls, int child_zone_side,
               bool grand_new_zone, int grand_zone_cls)
```

**Transition logic (per Addendum A.2):**

```
IF child_new_zone:
  IF zone inside parent's current zone:
    IF same direction as ts.direction:
      IF ts.push_idx == -1 → ts.state = PUSHING, record push zone
      IF ts.push_idx >= 0 AND extends HH/LL → ts.state = CONTINUING
    IF counter to ts.direction:
      ts.state = PULLING_BACK, record pullback zone

  IF pullback resolution A (price reaches push zone):
    ts.state = PUSHING (new cycle, new push zone)
  IF pullback resolution B (last pullback zone body-close broken):
    ts.state = PUSHING (extending without full retrace)

IF grand_new_zone:
  IF grand CHoCH against child's direction:
    ts.grand_choch = true
  IF grand breaks parent structural zone (LH/HL):
    ts.state = REVERSING
    ts.grand_break = true
```

**Compression detection (Addendum B Rule 3):**
```
IF child pushes to parent zone boundary AND fails body-close:
  ts.push_fail_cnt += 1
IF child pulls back to TL AND holds:
  ts.tl_hold_cnt += 1
IF ts.push_fail_cnt >= 2 AND ts.tl_hold_cnt >= 2:
  ts.compression = true
```

### 5.4 Zone Role Recoloring

When a triplet assigns a role to a child zone, the zone's box color is overridden:

| Role | Color | Source |
|------|-------|--------|
| Push | `#4CAF50` green | Spec CSS `--accent-push` |
| Continuation | `#FF9800` orange | Spec CSS `--accent-cont` |
| Pullback | `#9C27B0` purple | Spec CSS `--accent-pullback` |
| Reversal | `#E91E63` pink | Spec CSS `--accent-reversal` |

Zone label updated to include role suffix: `D S LH [PULL]`, `H4 D HL [PUSH]`, etc.

### 5.5 "Inside Parent Zone" Check

A child zone is "inside" the parent zone if:
- Child zone `top <= parent zone top` AND `bottom >= parent zone bottom`

This uses the most recent active parent zone of the relevant type (supply or demand, depending on parent direction).

## 6. Layer 3 — Trendlines & Magnet Lines

### 6.1 Trendline Construction (per triplet)

When a push zone exists and continuation zone(s) follow:

- **Bullish TL:** `line` from push zone demand `bottom` at `birth_bar` → latest continuation zone demand `bottom` at `birth_bar`. Extended right.
- **Bearish TL:** `line` from push zone supply `top` at `birth_bar` → latest continuation zone supply `top` at `birth_bar`. Extended right.

Line redrawn when new continuation zone added (delete old line, create new).

### 6.2 Trendline Break Detection

Project TL value at current bar:
```
slope = (anchor2_price - anchor1_price) / (anchor2_bar - anchor1_bar)
projected = anchor2_price + slope * (bar_index - anchor2_bar)
```

Break: `close < projected` (bullish TL) or `close > projected` (bearish TL) where `close[1]` was on the other side.

### 6.3 Two-Layer Confirmation (Addendum B.7)

| TL State | Zone State | Signal | Visual |
|----------|-----------|--------|--------|
| Intact | Intact | `HOLDING` | Solid TL, solid zone |
| Broken | Intact | `WARNING` | Dashed TL (yellow), zone unchanged |
| Broken | Broken | `REVERSED` | Dashed TL, zone deleted |
| Intact | Broken | `BREAKOUT` | Solid TL, zone deleted |

TL color: `#FFEB3B` yellow (spec `--accent-trendline`). On break: line style → `line.style_dotted`, transparency increased.

### 6.4 Magnet Lines

When triplet state = PULLING_BACK:
- Horizontal dashed line at push zone's far edge (the magnet price)
- Color: white, 50% transparency, `line.style_dashed`
- Extends right until pullback resolves

### 6.5 Drawing Budget

| Element | Max count | Limit |
|---------|-----------|-------|
| Zone boxes | 5 TFs × 20 × 2 sides = 200 | 500 |
| Zone labels | 200 | 500 |
| Trendlines | 4 triplets × 1 = 4 | 500 |
| Magnet lines | 4 triplets × 1 = 4 | 500 |
| Break markers | ~20 labels | 500 |
| **Total** | ~200 boxes, ~220 labels, ~8 lines | **All within limits** |

## 7. Layer 4 — Dashboard

### 7.1 Layout

Table in input-selectable corner. 2 columns, 10 rows.

| Row | Col 0 | Col 1 |
|-----|-------|-------|
| 0 | `Fractal Push/Pull v0.1` | (header) |
| 1 | `T1: MN→W→D` | State + direction |
| 2 | `T2: W→D→H4` | State + direction |
| 3 | `T3: D→H4→H1` | State + direction |
| 4 | `T4: H4→H1→M15` | State + direction (if enabled) |
| 5 | Separator | — |
| 6 | `Composite` | Alignment level + direction |
| 7 | `Target` | Current magnet price |
| 8 | `PB Depth` | % toward push zone |
| 9 | `Signal` | TL/Zone confirmation status |

### 7.2 State Display

Each triplet row shows: `{STATE} {↑|↓}` with color coding:
- PUSHING: green
- CONTINUING: green (brighter)
- PULLING BACK: orange
- REVERSING: red
- COMPRESSION: yellow (overrides state color)

### 7.3 Composite Bias (Addendum A.6 Step 5)

```
IF all active triplets same direction + PUSHING/CONTINUING:
  "FULL ALIGN {↑|↓}" — green/red
IF higher triplets (T1-T2) aligned, lower (T3+) may differ:
  "PARTIAL {↑|↓}" — yellow
IF higher triplets PULLING_BACK or REVERSING:
  "CONFLICT" — gray
```

### 7.4 Pullback Depth

```
depth = abs(continuation_extreme - close) / abs(continuation_extreme - push_zone_edge) * 100
```

Displayed as `PB: 62%` with color gradient (green at 0%, red at 100%).

### 7.5 Signal Row

Shows the two-layer confirmation status for the most relevant triplet:
- `D: HOLDING` (green) — TL intact + zone intact
- `D: WARNING` (yellow) — TL broken + zone intact
- `D: REVERSED` (red) — TL broken + zone broken
- `D: BREAKOUT` (white) — TL intact + zone broken

## 8. Implementation Constraints

### 8.1 Pine Script v6 Rules (from CLAUDE.md)

- `//@version=6` always
- All variables explicitly typed
- No multiline ternaries
- No reserved keywords as variable names
- Timeframe strings: `"60"` not `"1H"`, `"240"` not `"4H"`
- UDT fields explicitly typed with defaults
- `.copy()` for independent UDT copies
- Field assignment on `.get()`: store in local variable first
- One statement per line, no semicolons
- Broken zones deleted immediately, never ghost styled

### 8.2 Known Pine Limitations

- `request.security()` hard cap 40 — we use 10, future max 16
- Drawing object limits: 500 boxes, 500 labels, 500 lines — we stay under 220 each
- No inter-indicator UDT/array communication — everything in one file
- `var` inside `if` initializes on first `true`, not bar 0 — init all vars at top level

## 9. v0.1 Scope

**In scope:**
- Zone creation from HA transitions (H1, H4, D, W, MN)
- ORIZ boundaries with doji handling
- HH/LH/HL/LL classification
- Zone lifecycle (break by body close, expiry, overflow)
- Triplet engine T1-T3 (MN→W→D, W→D→H4, D→H4→H1)
- Role-based zone recoloring
- Trendlines with two-layer confirmation
- Magnet lines during pullbacks
- Dashboard with triplet states, composite bias, targets

**Out of scope (future):**
- T4-T6 (requires M15/M5/M1 data — 6 more security calls)
- Execution rules (entry/SL/TP) — spec Section 10 PENDING
- Position management — spec Section 11 PENDING
- Compression auto-detection visual markers (dashboard shows state, but on-chart markers deferred)
- Grandchild two-layer confirmation for reversal (v0.1 uses single-layer: child breaks parent structure directly)
