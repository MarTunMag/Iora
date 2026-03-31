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
    float   top       = na    // zone upper boundary (ORIZ)
    float   bottom    = na    // zone lower boundary (ORIZ)
    int     side      = 0     // +1 demand, -1 supply
    int     cls       = 0     // 1=HH, 2=LH, 3=LL, 4=HL
    int     role      = 0     // 0=unassigned, 1=push, 2=continuation, 3=pullback, 4=reversal
    string  tf_str    = ""    // "H1", "H4", "D", "W", "MN"
    int     birth_bar = 0     // bar_index at creation
    int     max_age   = 50    // TF-specific: 50 for H1-D, 30 for W, 20 for MN
    bool    is_nested = false // fully contained inside a parent-TF zone
    bool    is_terminal = false // opposing nest — this zone WILL be broken
    string  nested_in = ""   // parent TF string if nested (e.g., "H4")
    bool    is_rev_target = false // marked as reversal target by Rule 11
    box     bx        = na    // drawn box (na if TF hidden)
    label   lbl       = na    // drawn label (na if TF hidden)
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
- Max age per TF: H1=50, H4=50, D=50 (grouped with sub-daily per spec "M1–H4"), W=30, MN=20.

### 4.6 Zone Nesting Detection (per zone creation)

When a new child-TF zone is created, check if it is fully contained inside any active parent-TF zone (Rule 04):

```
child.top <= parent.top  AND  child.bot >= parent.bot
```

Both edges must be inside — partial overlap does NOT count as nesting (this is stricter than the triplet engine's overlap check in 5.12).

**Nesting hierarchy:** H1 checks H4, H4 checks D, D checks W, W checks MN.

**Classification:**
- **Same-direction nest** (child supply inside parent supply, or child demand inside parent demand) → continuation signal. Zone label gets `@{parent_tf}` suffix (e.g., `H1 S LH @H4`).
- **Opposing-direction nest** (child supply inside parent demand, or child demand inside parent supply) → terminal signal. The child zone **will be broken** because the parent force overwhelms it. Zone gets `is_terminal = true` and label gets `[TERM]` suffix.

**Skip filter:** If the parent zone overlaps an opposing zone at the same TF (e.g., a parent demand has an active supply zone whose bottom < parent top), the nesting signal is weak → skip the nesting label.

### 4.7 Reversal Target Zone Identification (Rule 11)

When the triplet engine marks a zone's role as push (1) or continuation (2), that zone becomes a candidate reversal target. When a triplet enters PULLING_BACK, the engine scans the child push-direction array for the most recent push/continuation zone and flags it with `is_rev_target = true`. No separate per-TF tracker variables are needed — the role-based scan in `mark_reversal_target()` (Section 5.11) handles identification directly.

### 4.8 Zone Colors (Layer 1 defaults, overridden by Layer 2 roles)

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
    string  id              = ""    // "T1" through "T6"
    int     state           = 0     // 0=INIT, 1=PUSHING, 2=CONTINUING, 3=PULLING_BACK, 4=REVERSING
    int     direction       = 0     // +1 bullish, -1 bearish (derived from parent's last zone)
    int     push_bar        = -1    // birth_bar of push zone (-1 = none)
    int     push_side       = 0     // +1 demand push, -1 supply push
    float   push_target     = na    // parent zone boundary being pushed toward
    float   pb_target       = na    // push zone edge (magnet for pullbacks)
    float   parent_zone_top = na    // the parent zone that produced parent's last HH/LL — top
    float   parent_zone_bot = na    // same zone — bottom
    float   parent_lh_top   = na    // parent's LH supply top (reversal detection)
    float   parent_hl_bot   = na    // parent's HL demand bottom (reversal detection)
    bool    grand_choch     = false // grandchild CHoCH detected
    bool    grand_break     = false // grandchild broke parent structure
    bool    compression     = false // child oscillating at parent boundary
    bool    failed_reversal = false // child built HL→HH but failed to break parent zone, then collapsed
    int     push_fail_cnt   = 0    // count of failed body-close attempts at parent boundary
    int     tl_hold_cnt     = 0    // count of times child TL held on pullback
    // Zone role tracking — by birth_bar (stable across array mutations)
    array<int> cont_bars    = na    // birth_bars of continuation zones (init with array.new<int>())
    array<int> pb_bars      = na    // birth_bars of pullback zones (init with array.new<int>())
    int     reversal_bar    = -1    // birth_bar of reversal zone
```

**Direction derivation:** When the parent creates a new zone, direction is set from the parent zone type:
- Parent last zone = supply → `direction = -1` (bearish for child)
- Parent last zone = demand → `direction = +1` (bullish for child)

**Zone referencing strategy:** TripletState references zones by `birth_bar` (not array index). Array indices shift when zones are added (`.unshift()`) or removed (break/expiry). `birth_bar` is stable — it never changes after zone creation. To find a zone by `birth_bar`, scan the relevant array: `for z in array: if z.birth_bar == target_bar → found`. This is O(n) but arrays are small (max 20 per side). The `cont_bars` and `pb_bars` arrays use `array.new<int>()` at construction time (Pine v6 does not allow array literals as UDT defaults — initialize in the `var` declaration block).

### 5.2 Six Instances

```
var TripletState t1 = TripletState.new("T1", ...)  // MN → W → D
var TripletState t2 = TripletState.new("T2", ...)  // W  → D → H4
var TripletState t3 = TripletState.new("T3", ...)  // D  → H4 → H1
var TripletState t4 = TripletState.new("T4", ...)  // H4 → H1 → M15 (future)
var TripletState t5 = TripletState.new("T5", ...)  // H1 → M15 → M5 (future)
var TripletState t6 = TripletState.new("T6", ...)  // M15 → M5 → M1 (future)
```

### 5.3 Event Dispatch

When a new zone fires on TF X, determine which triplets are affected and in what role:

```
ON new_zone(tf X, zone Z):
  FOR each triplet T in [t1, t2, t3, t4]:
    IF X == T.parent_tf → call reset_triplet(T, Z)
    IF X == T.child_tf  → call update_child(T, Z)
    IF X == T.grand_tf  → call update_grandchild(T, Z)
```

**Order matters:** Process parent resets first (they clear state), then child updates (they set state), then grandchild confirmations (they modify state). Within each category, process from highest triplet (T1) to lowest (T4).

### 5.4 Parent Reset — `reset_triplet(T, Z)`

When the parent creates a new zone, the triplet resets entirely (per Addendum A.8):

```
reset_triplet(TripletState ts, FractalZone parent_zone):
  // Derive direction from parent zone type
  ts.direction = parent_zone.side > 0 ? 1 : -1   // demand = bullish, supply = bearish

  // Record parent zone boundaries
  ts.parent_zone_top = parent_zone.top
  ts.parent_zone_bot = parent_zone.bottom

  // Update structural levels for reversal detection
  IF parent_zone.cls == 2 (LH):  ts.parent_lh_top = parent_zone.top
  IF parent_zone.cls == 4 (HL):  ts.parent_hl_bot = parent_zone.bottom

  // Clear child state — fresh cycle begins
  ts.state = 0 (INIT — waiting for first child zone)
  ts.push_bar = -1
  ts.cont_bars.clear()
  ts.pb_bars.clear()
  ts.reversal_bar = -1
  ts.grand_choch = false
  ts.grand_break = false
  ts.compression = false
  ts.failed_reversal = false
  ts.push_fail_cnt = 0
  ts.tl_hold_cnt = 0
  ts.push_target = ts.direction > 0 ? parent_zone.top : parent_zone.bottom
  ts.pb_target = na
```

### 5.5 Child Update — `update_child(T, Z)`

```
update_child(TripletState ts, FractalZone child_zone,
             array<FractalZone> child_sup, array<FractalZone> child_dem):

  bool inside_parent = child_zone.top <= ts.parent_zone_top
                   AND child_zone.bottom >= ts.parent_zone_bot
  bool same_dir = (ts.direction > 0 AND child_zone.side > 0)   // bullish + demand
               OR (ts.direction < 0 AND child_zone.side < 0)   // bearish + supply
  bool counter  = NOT same_dir

  IF ts.state == 0 (INIT) AND inside_parent AND same_dir:
    // First child zone in parent's direction inside parent zone = push zone
    ts.state = 1 (PUSHING)
    ts.push_bar = child_zone.birth_bar
    ts.push_side = child_zone.side
    ts.pb_target = ts.direction > 0 ? child_zone.bottom : child_zone.top
    assign child_zone.role = 1 (push)

  ELSE IF (ts.state == 1 OR ts.state == 2) AND same_dir:
    // Additional zone in same direction extending HH/LL = continuation
    IF extends_structure(child_zone, ts):  // new HH or new LL
      ts.state = 2 (CONTINUING)
      ts.cont_bars.push(child_zone.birth_bar)
      assign child_zone.role = 2 (continuation)

  ELSE IF (ts.state == 1 OR ts.state == 2) AND counter:
    // Zone counter to parent direction = pullback begins
    ts.state = 3 (PULLING_BACK)
    ts.pb_bars.push(child_zone.birth_bar)
    assign child_zone.role = 3 (pullback)

  ELSE IF ts.state == 3 AND counter:
    // Additional pullback zone — deeper pullback
    ts.pb_bars.push(child_zone.birth_bar)
    assign child_zone.role = 3 (pullback)

  ELSE IF ts.state == 3 AND same_dir:
    // Zone in parent's direction while pulling back
    // This zone is not assigned a role yet — it may become the new push zone
    // if pullback resolution is confirmed (per-bar checks in 5.7).
    // Leave role = 0 (unassigned) until resolution triggers.
```

### 5.6 Grandchild Update — `update_grandchild(T, Z)`

```
update_grandchild(TripletState ts, FractalZone grand_zone):

  // CHoCH detection: grandchild creates zone counter to child's current push
  IF ts.state == 1 OR ts.state == 2:  // child is pushing/continuing
    IF grand_zone classifies as LH (cls=2) AND ts.direction > 0:
      ts.grand_choch = true  // early warning: child push exhausting
    IF grand_zone classifies as HL (cls=4) AND ts.direction < 0:
      ts.grand_choch = true

  IF ts.state == 3:  // child is pulling back
    // Grand CHoCH against pullback direction = pullback exhaustion signal
    IF grand_zone is CHoCH vs pullback direction:
      ts.grand_choch = true  // needed for pullback resolution confirmation

  // Reversal detection: grandchild breaks parent structural zone
  IF ts.direction > 0 AND grand_zone.side < 0:  // bearish grand zone
    IF close < ts.parent_hl_bot:  // body close below parent HL demand
      ts.state = 4 (REVERSING)
      ts.grand_break = true
      // Find the child zone that drove the break → mark as reversal
  IF ts.direction < 0 AND grand_zone.side > 0:  // bullish grand zone
    IF close > ts.parent_lh_top:  // body close above parent LH supply
      ts.state = 4 (REVERSING)
      ts.grand_break = true
```

### 5.7 Per-Bar Checks (Pullback Resolution + Compression)

Run every bar, not just on zone creation:

```
FOR each active triplet T where T.state == 3 (PULLING_BACK):

  // Resolution A: price reaches push zone
  IF ts.direction > 0 AND close <= ts.pb_target:  // pullback down reached push demand
    IF ts.grand_choch:  // grandchild confirmation required (Addendum A.2)
      ts.state = 0 (INIT — next same-direction zone becomes new push)
      reset push/cont/pb tracking, keep parent zone
  IF ts.direction < 0 AND close >= ts.pb_target:
    IF ts.grand_choch:
      ts.state = 0 (INIT — next same-direction zone becomes new push)

  // Resolution B: last pullback zone body-close broken
  IF ts.pb_bars.size() > 0:
    last_pb = find zone where birth_bar == ts.pb_bars.last()
    IF ts.direction > 0 AND close > last_pb.top:  // broke bearish pullback zone
      IF ts.grand_choch:  // grandchild confirmation required
        ts.state = 0 (INIT — extending without full retrace, next zone = new push)
    IF ts.direction < 0 AND close < last_pb.bottom:
      IF ts.grand_choch:
        ts.state = 0 (INIT — extending)

  // Compression detection (Addendum B Rule 3)
  // Tracked via push_fail_cnt and tl_hold_cnt (updated in trendline layer)
  IF ts.push_fail_cnt >= 2 AND ts.tl_hold_cnt >= 2:
    ts.compression = true
```

### 5.8 Cascade Propagation

When a triplet changes state, adjacent triplets may be affected (Addendum A.4):

```
// Downward: when T(n) enters PUSHING, T(n+1) re-evaluates direction
propagate_direction_down(TripletState t_changed, TripletState t_below):
  // t_below's parent TF is t_changed's child TF
  // The new child zone that started the push becomes t_below's parent zone
  // t_below resets via reset_triplet() — this happens naturally when the
  // child zone fires and is also t_below's parent TF

// Upward: when T(n) enters REVERSING, T(n-1) is notified
propagate_reversal_up(TripletState t_changed, TripletState t_above):
  // t_changed's reversal means t_above's grandchild broke parent structure
  // This is handled by update_grandchild() — when the reversal zone fires,
  // it is a zone event on t_above's grandchild TF
  // No explicit propagation needed if dispatch (5.3) correctly routes events

// Key insight: cascade propagation is handled implicitly by the event dispatch
// in 5.3 — each zone event is routed to ALL triplets where that TF participates.
// A zone on D affects T1 (as grandchild), T2 (as child), T3 (as parent).
// This IS the cascade connectivity.
```

### 5.9 Failed Reversal Detection (Addendum B Rule 2)

```
// Detect: child built HL→HH but failed to break parent zone, then child TL breaks
IF ts.state was 3 (PULLING_BACK) with child pushing counter:
  AND child built structure (HL → HH if bullish counter-push)
  AND child failed to body-close break parent zone
  AND child ascending TL subsequently broken:
    ts.failed_reversal = true
    // Signal: enter parent direction with increased conviction
    // Target = push zone (magnet)
```

### 5.10 Signal Hierarchy (Addendum B Rule 4)

The grandchild CHoCH is not a single binary — it exists on a confidence hierarchy:

The hierarchy is expressed in triplet-relative terms (applies to any T1-T6 instance):

| Level | Signal (triplet-relative) | Example for T3 (D→H4→H1) | Action |
|-------|---------------------------|---------------------------|--------|
| 1 | Grandchild CHoCH | H1 CHoCH | Flag only — do not act |
| 2 | Grandchild structural (HL/LH) | H1 HL or LH | Prepare — tighten stops |
| 3 | Child structural event | H4 structural event | Alert — ready to act |
| 4 | Child zone holds/breaks | H4 zone holds/breaks | Confirm — high confidence |
| 5 | Child TL break | H4 TL break | Confirmed direction change |
| 6 | Parent zone break (body close) | D zone break | Maximum conviction |

For v0.1, the dashboard displays the highest confirmed level per triplet. The `grand_choch` boolean in TripletState is set at level 1-2; `grand_break` is set at level 4+. Levels 3-5 are detected by combining child zone events with trendline state from Layer 3.

### 5.11 Reversal Target Marking (Rule 11)

When a triplet enters PULLING_BACK (state=3), the last-created child zone in the push direction **before** the pullback began is marked as the reversal target:

```
IF ts transitions to PULLING_BACK:
  // The CHoCH zone = reversal target for the parent level
  last_push_dir_zone = last created child zone on push side
  last_push_dir_zone.is_rev_target = true
  // Visual: dotted border on zone box, "★" prefix on label
```

This is the zone that price must reach or break for the current structural cycle to complete. It becomes the TP target for trades aligned with the pullback direction, and the entry zone for trades in the parent direction.

When the triplet resets (parent zone fires), all `is_rev_target` flags on child zones are cleared.

### 5.12 Zone Role Recoloring

When a triplet assigns a role to a child zone, the zone's box color is overridden:

| Role | Color | Source |
|------|-------|--------|
| Push | `#4CAF50` green | Spec CSS `--accent-push` |
| Continuation | `#FF9800` orange | Spec CSS `--accent-cont` |
| Pullback | `#9C27B0` purple | Spec CSS `--accent-pullback` |
| Reversal | `#E91E63` pink | Spec CSS `--accent-reversal` |

Zone label updated to include role suffix: `D S LH [PULL]`, `H4 D HL [PUSH]`, etc.

A zone may participate in multiple triplets with different roles (e.g., a D zone is child in T2 and parent in T3). The displayed role uses the **highest triplet** where the zone is a child — that is its primary structural role.

### 5.12 "Inside Parent Zone" Check

A child zone is "inside" the parent zone if:
- Child zone overlaps with parent zone: `child.top >= parent.bottom AND child.bottom <= parent.top`

This is an overlap check, not full containment — per the walkthrough (E4), child zones can be created at the parent boundary with partial overlap, and these still qualify as "inside."

**Which parent zone?** The triplet tracks `parent_zone_top` and `parent_zone_bot` — set when `reset_triplet()` fires on parent zone creation. This is specifically "the parent zone that produced the parent's last HH/LL" (spec Section 4a). It is NOT just "any active parent zone" — it is the one recorded in the triplet state.

## 6. Layer 3 — Trendlines & Magnet Lines

### 6.1 Trendline Construction (per triplet)

When a push zone exists and continuation zone(s) follow:

- **Bullish TL:** `line` from push zone demand `bottom` at `birth_bar` → latest continuation zone demand `bottom` at `birth_bar`. Extended right.
- **Bearish TL:** `line` from push zone supply `top` at `birth_bar` → latest continuation zone supply `top` at `birth_bar`. Extended right.

Line redrawn when new continuation zone added (delete old line, create new).

**Finding push/continuation zones:** L3 reads from the TripletState: `ts.push_bar` identifies the push zone by its `birth_bar`; `ts.cont_bars` identifies continuation zones by their `birth_bar`s. L3 scans the child zone arrays to find zones matching these birth_bars, then uses their `birth_bar` and price levels as trendline anchor points. If a referenced zone has been deleted (broken/expired — no matching birth_bar found in the array), the trendline is also deleted.

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

Table in input-selectable corner. 2 columns, dynamic row count (based on enabled triplets).

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
| 10 | Separator | — |
| 11 | `Alignment` | Per-TF bias alignment grid (from momentum consumption concept) |
| 12 | `Rev Target` | Current reversal target zone + price (from Rule 11) |

### 7.2 State Display

Each triplet row shows: `{STATE} {↑|↓}` with color coding:
- PUSHING: green
- CONTINUING: green (brighter)
- PULLING BACK: orange
- REVERSING: red
- COMPRESSION: yellow (overrides state color)

### 7.3 Composite Bias (Addendum A.6 Step 5)

v0.1 evaluates T1-T3 only (T4 optional). Composite formula:

```
IF all enabled triplets same direction + PUSHING/CONTINUING:
  "FULL ALIGN {↑|↓}" — green/red
IF higher triplets (T1-T2) aligned, T3 may differ:
  "PARTIAL {↑|↓}" — yellow
IF T1 or T2 PULLING_BACK or REVERSING:
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

### 7.6 Alignment Grid (from Momentum Consumption concept)

Shows per-TF directional alignment using the triplet states as a proxy for bias:

```
H1: ↑  H4: ↑  D: ↓  W: ↓  MN: ↓
```

Direction derived from the triplet where each TF is the child:
- H1 direction from T3 (D→H4→H1)
- H4 direction from T3 child or T2 grandchild
- D direction from T2 (W→D→H4) or T1 grandchild
- W direction from T1 (MN→W→D)
- MN: always from T1 parent direction

Color: green if aligned with composite bias, red if opposed, gray if INIT.

### 7.7 Reversal Target Row (from Rule 11)

Shows the nearest reversal target zone identified by the triplet engine:

```
Rev Target: H4 S LH @ 1.2650-1.2680
```

Derived from the `is_rev_target` flagged zone in the most active triplet (T3 preferred, fallback T2).

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
- Zone nesting detection with terminal flagging and skip filter (Rule 04)
- Triplet engine T1-T3 (MN→W→D, W→D→H4, D→H4→H1)
- Role-based zone recoloring
- Reversal target marking on CHoCH zones (Rule 11)
- Trendlines with two-layer confirmation
- Magnet lines during pullbacks
- Reversal target lines (horizontal, from Rule 11 marked zones)
- Dashboard with triplet states, composite bias, targets
- Dashboard alignment grid (momentum consumption concept)
- Dashboard reversal target display

**Out of scope (future):**
- T4-T6 (requires M15/M5/M1 data — 6 more security calls)
- Execution rules (entry/SL/TP) — spec Section 10 PENDING
- Position management — spec Section 11 PENDING
- Compression auto-detection visual markers (dashboard shows state, but on-chart markers deferred)
- Grandchild two-layer confirmation for reversal (v0.1 uses single-layer: child breaks parent structure directly)
