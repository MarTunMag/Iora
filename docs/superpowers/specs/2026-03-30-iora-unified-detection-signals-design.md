# Iora Unified Detection + Signal Engine — Design Spec

**Date:** 2026-03-30
**Author:** Marius Tunestveit Magnusson + Claude
**Status:** Reviewed
**Depends on:** `STRATEGY_iora_trading_methodology.md`, `MASTER_SPEC_iora_structural_detection.md`, Modules 1-4

---

## Problem

Four separate indicators (Envelope, Conviction, BOS/CHoCH v2, Legs+EW) each have their own dashboard and on-chart markers. This creates:

1. **Dashboard overlap** — 4 dashboards fighting for screen space, each showing the same TF rows with different columns
2. **No actionable signals** — all raw detection data exists but nothing synthesizes it into entry/exit decisions
3. **Missing computation layers** — zone tracking, zone counting, momentum consumption, 1-2-3 cascade, and trendline breaks are not yet implemented

## Solution

Collapse into **2 production indicators** with clean separation:

| Indicator | Purpose | Question it answers |
|-----------|---------|---------------------|
| **Detection Engine** | What IS happening | "H1 is in a bearish leg #3, EW EXTENDED pattern, 4/8 exhaustion" |
| **Signal Engine** | What to DO about it | "Model A SHORT armed, terminal active, consumption 3/4, enter on M1 LH" |

Existing Modules 1-4 move to `iora_structure/dev/` for debugging.

---

## File Organization

```
tw_indicators/
  iora_structure/
    iora_detection.pine          ← Production: unified detection
    iora_signals.pine            ← Production: unified signals
    dev/                         ← Development/debugging modules
      iora_envelope.pine         ← Module 1
      iora_conviction.pine       ← Module 2
      iora_bos_choch_v2.pine     ← Module 3
      iora_legs.pine             ← Module 4
```

---

## Shared Computation Preamble

Both indicators independently compute the same foundation (TradingView cannot share data between indicators). This is a well-defined block (~250 lines) identical in both files:

### request.security Calls (7 total per indicator)

```
M5:  request.security(syminfo.tickerid, "5",   [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
M15: request.security(syminfo.tickerid, "15",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
H1:  request.security(syminfo.tickerid, "60",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
H4:  request.security(syminfo.tickerid, "240", [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
D:   request.security(syminfo.tickerid, "1D",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
W:   request.security(syminfo.tickerid, "1W",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
MN:  request.security(syminfo.tickerid, "1M",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)
```

Budget: 7 calls per indicator × 2 indicators = 14 total (well under 40 limit).

**Note:** MN period-level breaks (in Detection Engine) can also use `ta.change(time("1M"))` at zero cost — no `request.security` needed. The MN `request.security` call is for envelope computation only.

### Envelope Computation

Three-source envelope per TF using array-based closed candle history:

| TF | Child | N (total window = closed + building) |
|----|-------|--------------------------------------|
| M5 | M1 (raw bars) | 5 (4 closed + 1 building) |
| M15 | M5 | 3 (2 closed + 1 building) |
| H1 | M15 | 4 (3 closed + 1 building) |
| H4 | H1 | 4 (3 closed + 1 building) |
| D | H4 | 6 (5 closed + 1 building) |
| W | D | 5 (4 closed + 1 building) |
| MN | W | 4 (3 closed + 1 building) |

Each produces: `env_ceil` (avg child highs), `env_mid` (avg child closes), `env_floor` (avg child lows).

### M1 Computation (from raw chart bars)

Since the chart timeframe is M1, M1 data comes directly from raw bars — no `request.security` needed:
- **M1 envelope:** `env_ceil = high`, `env_mid = close`, `env_floor = low` (single bar = trivial envelope)
- **M1 conviction:** Assessed using M1 envelope gradients (`ta.change(high)`, `ta.change(close)`, `ta.change(low)`)
- **M1 leg tracking:** Same `leg_transition()` logic using raw bar high/low as child data
- **M1 zones (Signal Engine only):** Created from M1 leg transitions. Zone top/bottom from M1 swing extremes. Used for SL placement (M1 zone edge + spread).
- **M1 CHoCH detection:** M1 STRONG conviction event = M1 CHoCH. This is the execution trigger for Entry Models A, C, and D.

### Gradients

`ta.change()` on each envelope source per TF. Used for conviction assessment.

### Conviction Classification

Per TF using `assess_conv()`:

| Level | Condition | Meaning |
|-------|-----------|---------|
| STRONG (3) | Floor/ceil break + mid confirms + opposing source confirms | External event — leg transition |
| WEAK (2) | Floor or ceil breaks, mid does NOT confirm | Internal event — sub-wave |
| PRE (1) | Mid stalling, floor/ceil intact | Momentum fading warning |

### Leg Tracking

Per TF (M1 through W) using `leg_transition()`:
- Leg transitions fire on STRONG conviction events (cv == 3)
- Tracks: direction (UP/DN), leg_number, building (PARENT_HIGH/PARENT_LOW), leg_high, leg_low, prev_leg_high, prev_leg_low
- Swing classification: HH (leg_high > prev_leg_high), LH, HL, LL
- **Zone inheritance:** When the Signal Engine creates a zone from a leg transition, the zone inherits the swing classification from the leg tracker (e.g., supply zone from an HH vs LH). This is critical for zone counting and 1-2-3 cascade detection.

---

## Indicator 1: Detection Engine

**File:** `iora_detection.pine`
**Overlay:** yes

### Layers (beyond shared preamble)

#### Layer 1: Period-Level Breaks

Reuses `track_period()` from Module 3 — uses `ta.change(time(tf))` (no extra request.security calls).

Per TF (M5 through MN):
- Tracks previous period high/low
- Detects first break of each level within current period
- Edge-detected break events

#### Layer 2: Swing State Machine

Per TF, fed by period-level breaks:
- Trend direction: UP (+1), DOWN (-1), NEUTRAL (0)
- Break event classification: BOS (continuation) or CHoCH (reversal)
- Swing classification: HH, LH, HL, LL
- Parent propagation: when child break exceeds parent prev-period level → eBOS+/eCHoCH+

#### Layer 3: EW Wave Tracking (M15+ TFs)

Per qualifying TF (M15, H1, H4, D):
- 5-phase state machine: INIT → BULL_IMPULSE → BULL_CORRECTION → BEAR_IMPULSE → BEAR_CORRECTION
- Bullish impulse pivots: W1 top/bot, W2 bot, W3 top, W4 bot, W5 top
- Bearish impulse pivots: W1 bot/top, W2 top, W3 bot, W4 top, W5 bot
- Correction pivots: cor_start, A, B, C levels
- Wave count derived from swing classifications (HH/HL/LH/LL sequence)

#### Layer 4: EW Pattern Classification

Per TF with active EW tracking:

**Motive patterns (impulse phases):**

| Pattern | Code | Detection |
|---------|------|-----------|
| IMPULSE | 1 | Default — no overlap, no extension |
| DIAGONAL | 2 | W4 overlaps W1 territory |
| EXTENDED | 3 | W3 > 1.618 × W1 range |

**Corrective patterns (correction phases):**

| Pattern | Code | Detection |
|---------|------|-----------|
| REG_FLAT | 4 | B retraces 90-110% of A |
| EXP_FLAT | 5 | B exceeds impulse origin |
| RUN_FLAT | 6 | B exceeds A, C falls short of origin |

Triangle detection (7/8/9) deferred — requires trendline data from Signal Engine.

#### Layer 5: Dynamic Exhaustion Threshold

Per TF, based on EW pattern:

| Pattern | Threshold | Rationale |
|---------|-----------|-----------|
| Standard (IMPULSE) | 5 | Normal 5-wave impulse |
| DIAGONAL | 3-4 | Early exhaustion, wedge forming |
| EXTENDED | 7-9 | W3 creates extra zones, more room |
| Correction | N/A | Zone counting pauses during correction |

### Dashboard (unified, replaces 4 separate dashboards)

Position: configurable (default Bottom Right)
Size: 8 columns × 8 rows (1 header + 7 data rows: M5/M15/H1/H4/D/W/MN)

| Col | Header | Source | Color Logic |
|-----|--------|--------|-------------|
| TF | Timeframe label | static | gray |
| Dir | Leg direction | leg_tracker | green=UP, red=DN |
| Swing | Last swing class | leg_tracker | HH/HL=green, LH/LL=red |
| Conv | Conviction level + side | conviction | STRG=bright, WEAK=faded, PRE=orange |
| Hlth | Internal health | conviction | OK=green, 1st=yellow, DEG=orange, BRK=red |
| EW | Wave count (W1-W5/A-C) | ew_tracker | bull=green, bear=red (M15+ only; M5 blank) |
| Pat | EW pattern name | ew_classifier | IMP=trend, DIAG=orange, corrections=purple |
| Exh | count/threshold | exhaustion | green→yellow→orange→red as count approaches threshold |

**Note:** EW wave tracking runs for M15, H1, H4, and D. M5 and W/MN rows show "—" in EW/Pat/Exh columns (M5 too noisy for EW per guardrail; W/MN have insufficient swing data on typical chart history).

### On-Chart Markers (all toggleable)

| Marker | Default | Shape | Location |
|--------|---------|-------|----------|
| CHoCH labels (H1+) | ON | label | above/below bar |
| BOS labels | OFF | label | above/below bar |
| Swing HH/HL/LH/LL | ON (H1) | plotshape triangle | above/below bar |
| EW wave labels | OFF | label W1-W5/A-C | at swing points |
| Envelope lines | OFF | step-line | overlay |
| Propagated (e+) labels | OFF | label | above/below bar |

### Inputs

```
Group "Structure Labels":
  i_show_choch:   bool = true     "Show CHoCH labels"
  i_show_bos:     bool = false    "Show BOS labels"
  i_show_propag:  bool = false    "Show propagated (e+) labels"
  i_struct_tf:    string = "H1"   "Minimum TF for structure labels" options=["M5","M15","H1","H4","D","W"]

Group "Swing Markers":
  i_swing_tf:     string = "H1"   "Show swing markers for" options=["M5","M15","H1","H4","D","W","None"]

Group "Elliott Wave":
  i_ew_labels:    bool = false    "Show EW wave labels"
  i_ew_fib:       bool = false    "Show Fibonacci projections"

Group "Envelope" (debugging):
  i_env_show:     bool = false    "Show envelope lines"
  i_env_tf:       string = "H1"  "Envelope TF to display"

Group "Dashboard":
  i_dash_on:      bool = true     "Show Dashboard"
  i_dash_pos:     string = "Bottom Right"
```

---

## Indicator 2: Signal Engine

**File:** `iora_signals.pine`
**Overlay:** yes

### Layers (beyond shared preamble)

#### Layer 1: Zone Creation & Tracking

Zones are created from leg transitions:

- **Supply zone** created when UP-leg ends (STRONG bearish conviction):
  - Top: `leg_high` (swing high)
  - Bottom: open of the candle at the swing high bar (or `leg_high - ATR * factor` as fallback)
  - Side: SUPPLY
  - TF: the TF where the leg transition fired

- **Demand zone** created when DOWN-leg ends (STRONG bullish conviction):
  - Top: open of the candle at the swing low bar (or `leg_low + ATR * factor` as fallback)
  - Bottom: `leg_low` (swing low)
  - Side: DEMAND
  - TF: the TF where the leg transition fired

- **Zone broken** when price closes through the zone body:
  - Supply broken: close > zone top
  - Demand broken: close < zone bottom
  - Broken zones deleted immediately (no ghost styling)

- **Storage:** Array of zone structs per TF, max 8 per TF per side. Oldest deleted when exceeding cap.

- **On-chart:** Box drawings for H1/H4/D zones (supply=red fill, demand=green fill, toggleable per TF)

#### Layer 2: Zone Counting

Per TF (primary focus: H1):

```
zone_count:     int    Count of unbroken zones in current impulse direction
zone_direction: int    +1=bullish impulse (demand zones counting), -1=bearish
zone_reset:     bool   Resets on CHoCH (swing classification LH after HH sequence, or HL after LL sequence)
```

Zone count interpretation:

| Count | Status | Action |
|-------|--------|--------|
| 1-4 | Impulse active | Trade with trend |
| 5 | Impulse exhausted | Prepare for correction (take partials) |
| 6-7 | Correction territory | Counter-trend zones forming |
| 8+ | Terminal | Reversal imminent |

EW-aware adjustment: if Detection Engine's EW pattern is EXTENDED → threshold shifts to 7-9. If DIAGONAL → threshold shifts to 3-4. Signal Engine recomputes EW internally (same shared preamble) to get the pattern.

#### Layer 3: Opposing Nesting Detection

Checks geometric containment:

```
H1 demand inside H4 supply:
  h1_demand_top < h4_supply_top AND h1_demand_bottom > h4_supply_bottom
  → opposing_nesting = true (bearish reversal signal)

H1 supply inside H4 demand:
  h1_supply_bottom > h4_demand_bottom AND h1_supply_top < h4_demand_top
  → opposing_nesting = true (bullish reversal signal)
```

Also checks H4 inside D for higher-TF nesting confirmation.

#### Layer 4: Momentum Consumption State Machine

Triggered by parent STRONG CHoCH (e.g., H4 flips bearish):

```
State per consumption cycle:
  parent_tf:        string    Which TF triggered the cycle
  parent_dir:       int       New direction of parent
  child_flipped:    map       {M1: bool, M5: bool, M15: bool, H1: bool}
  consumption_score: int      0-4 (count of flipped children)
  active:           bool      Cycle is running
```

Per child TF, consumption % derived from conviction state:

| State | % |
|-------|---|
| Old bias dominant, no signals | 0% |
| PRE-CHoCH firing | 25% |
| Internal health FIRST_CRACK | 40% |
| Internal health DEGRADING | 60% |
| WEAK CHoCH against old direction | 75% |
| Internal health BROKEN | 85% |
| STRONG CHoCH fires (bias flips) | 100% |

Consumption depth interpretation:

| Depth | Meaning | Entry Timing |
|-------|---------|--------------|
| 1/4 (M1 only) | Noise — too early | Wait |
| 2/4 (M1+M5) | Early signal | Aggressive entries only |
| 3/4 (M1+M5+M15) | Standard | Normal entries |
| 4/4 (all) | Full alignment | Confirmation entries, Mode B |

#### Layer 5: 1-2-3 Cascade Detection

Per TF, detect three-zone compression:

```
Bearish 1-2-3:
  zone_1: last demand (HL)
  zone_2: last supply (HH) — must be AFTER zone_1
  zone_3: last demand (HL) — must be AFTER zone_2
  Signal: zone_3.top < zone_2.bottom → compression confirmed

Bullish 1-2-3:
  zone_1: last supply (LH)
  zone_2: last demand (LL) — must be AFTER zone_1
  zone_3: last supply (LH) — must be AFTER zone_2
  Signal: zone_3.bottom > zone_2.top → compression confirmed
```

Cascade arming (each level gates the next):

```
D 1-2-3 fires         → always active
  H4 1-2-3 fires      → only when price inside D zone
    H1 1-2-3 fires    → only when price inside H4 zone
      M15 1-2-3 fires → only when price inside H1 zone
        M5 1-2-3 fires → only when price inside M15 zone
          → ENTRY TRIGGER ARMED
```

Containment check: child close must be within parent's unbroken zone boundaries.

Output: `cascade_armed_level` (highest TF where cascade is armed: "M5" = fully armed, "M15" = partially armed, etc.)

#### Layer 6: Terminal Exhaustion Gate

Binary state derived from 4 conditions:

```
terminal_active = (
    d_level_broken AND           // D HH/HL/LH/LL confirmed (from leg tracker)
    h4_counter_zone AND          // H4 zone formed beyond broken D level
    h1_zone_count >= ew_threshold AND  // H1 zone count meets EW-adjusted threshold
    opposing_nesting              // H1 zone inside opposing H4 zone
)
```

When terminal_active:
- Entry Model A becomes available
- Terminal gate blocks macro bias flips in the wrong direction

#### Layer 7: D-Level Cycle Phase

State machine derived from terminal gate + structure:

```
Phase A: terminal_active AND h4_demand_confirming
         (H4 demand inside terminal zone, price bouncing)

Phase B: h4_demand_confirmed AND price_pushing_toward_boundary
         (Price between H4 demand and boundary zone)

Phase C: price_at_boundary AND h4_supply_forming
         (H4 supply inside/near boundary, D LH/HL confirming)

Phase D: d_lh_or_hl_confirmed AND consumption_4_4
         (Aggressive push, all TFs aligned)

Phase E: new_d_extreme
         (New D LL/HH printing → cycle restarts at A)
```

#### Layer 8: Entry Model Signal Generation

Four entry models, each with specific conditions:

**Model A — Terminal Reversal (highest conviction):**

```
Conditions (ALL must be true):
  [x] terminal_active == true
  [x] consumption_score >= 2
  [x] M15 zone nested inside H4 zone (same side as reversal)
  [x] M15 trendline break confirms H1 push complete
  [x] M5 1-2-3 cascade armed (cascade_armed_level == "M5")
  [x] M1 STRONG CHoCH in reversal direction

Signal output:
  entry_model = "A"
  entry_dir   = reversal direction (+1 LONG / -1 SHORT)
  entry_price = M5 demand bottom (for LONG) or M5 supply top (for SHORT)
  sl_price    = M1 zone opposite edge + spread buffer
  tp_price    = H1 reversal target zone (the H1 supply/demand that caused H4 CHoCH)
```

**Model B — Mode B Continuation (Phase D):**

```
Conditions (ALL must be true):
  [x] d_cycle_phase == "D"
  [x] consumption_score == 4
  [x] M5 or M15 zone exists in push direction

Signal output:
  entry_model = "B"
  entry_dir   = push direction
  entry_price = M5/M15 zone edge
  sl_price    = above/below the M5/M15 zone
  tp_price    = next H4 zone or D level
```

**Model C — 1-2-3 Cascade Add-On:**

```
Conditions (ALL must be true):
  [x] cascade_armed_level == "M5" (fully armed cascade)
  [x] M1 STRONG CHoCH inside M5 zone at cascade point

Signal output:
  entry_model = "C"
  entry_dir   = cascade direction
  entry_price = M1 zone edge
  sl_price    = M1 zone opposite edge + spread
  tp_price    = next TF zone or structural level
```

**Model D — Macro Bias Limit Order:**

```
Conditions (ALL must be true):
  [x] M5 trendline break detected (ascending support broken for SHORT, descending resistance for LONG)
  [x] Price inside H4 or D zone
  [x] terminal_active == false (terminal gate clear — no trap)

Signal output:
  entry_model = "D"
  entry_dir   = bias direction
  entry_price = broken M5 zone edge (demand top for SHORT limit, supply bottom for LONG limit)
  sl_price    = M1 zone edge + spread
  tp_price    = next structural level
```

**Trendline Break Detection (M5 and M15):**

Both Model A (M15 TL break) and Model D (M5 TL break) require trendline detection. Implementation:
- **Ascending TL:** Connect last 2 swing lows (HL sequence) at the given TF. Break = close below the projected TL value.
- **Descending TL:** Connect last 2 swing highs (LH sequence) at the given TF. Break = close above the projected TL value.
- Uses the leg tracker's swing data (prev_leg_low/prev_leg_high + current leg_low/leg_high) — no additional `request.security` calls needed.
- Break is edge-detected (fires once on the bar that closes through).

### Signal Dashboard

Position: configurable (default Bottom Left — opposite corner from Detection Engine)
Layout: compact summary panel

**Top section — State Summary (2 columns × 3 rows = 6 fields):**

| Field | Value Example | Color Logic |
|-------|---------------|-------------|
| Phase | D (cycle phase) | A=green, B=blue, C=orange, D=red, E=gray |
| Terminal | ACTIVE | green=active, gray=inactive |
| Consumption | 3/4 ▼ | 0-1=gray, 2=yellow, 3=orange, 4=green |
| H1 Zones | 6/5 | green if < threshold, orange at threshold, red if > |
| Cascade | M5 ARMED | color of highest armed level |
| Bias | BEAR | green=BULL, red=BEAR, gray=NEUTRAL |

**Bottom section — Active Signal (when entry model fires):**

| Field | Value Example |
|-------|---------------|
| Model | A: SHORT |
| Entry | 1.3265 |
| SL | 1.3282 |
| TP | 1.3180 |
| R:R | 1:5.0 |

### On-Chart Markers

| Marker | Default | Visual |
|--------|---------|--------|
| H1 zone boxes | ON | Red fill (supply), green fill (demand), 85% transparent |
| H4 zone boxes | ON | Same colors, 70% transparent, thicker border |
| D zone boxes | OFF | Same colors, visible but large |
| M15 zone boxes | OFF | Faint, small |
| Entry signal (Model A) | ON | Large diamond (green=LONG, red=SHORT) |
| Entry signal (Model B) | ON | Blue arrow |
| Entry signal (Model C) | ON | Yellow triangle |
| Entry signal (Model D) | ON | Purple circle |
| SL line | ON | Red dashed line from signal bar |
| TP line | ON | Green dashed line from signal bar |
| Consumption meter | ON | In dashboard only |

### Inputs

```
Group "Zones":
  i_show_h1_zones:  bool = true     "Show H1 zones"
  i_show_h4_zones:  bool = true     "Show H4 zones"
  i_show_d_zones:   bool = false    "Show D zones"
  i_show_m15_zones: bool = false    "Show M15 zones"
  i_max_zones:      int = 8         "Max zones per TF per side"

Group "Signals":
  i_show_model_a:   bool = true     "Show Model A signals"
  i_show_model_b:   bool = true     "Show Model B signals"
  i_show_model_c:   bool = true     "Show Model C signals"
  i_show_model_d:   bool = true     "Show Model D signals"
  i_show_sl_tp:     bool = true     "Show SL/TP lines"

Group "Dashboard":
  i_dash_on:        bool = true     "Show Dashboard"
  i_dash_pos:       string = "Bottom Left"
```

---

## Data Flow Summary

```
                    ┌─────────────────────────┐
                    │    request.security ×6   │
                    │  M5 / M15 / H1 / H4 / D / W  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Shared Preamble       │
                    │  Envelope → Gradients   │
                    │  → Conviction → Legs    │
                    └──────┬─────────┬────────┘
                           │         │
              ┌────────────▼──┐  ┌───▼────────────────┐
              │  DETECTION    │  │  SIGNAL ENGINE      │
              │  ENGINE       │  │                     │
              │               │  │  Zone Creation      │
              │  Period Breaks│  │  Zone Counting      │
              │  Swing State  │  │  Opposing Nesting   │
              │  EW Tracking  │  │  Consumption SM     │
              │  EW Patterns  │  │  1-2-3 Cascade      │
              │  Exhaustion   │  │  Terminal Gate       │
              │               │  │  D-Level Phase      │
              │  ┌──────────┐ │  │  Entry Models A-D   │
              │  │Dashboard │ │  │                     │
              │  │Detection │ │  │  ┌───────────────┐  │
              │  └──────────┘ │  │  │Dashboard      │  │
              │               │  │  │Signals + Zones│  │
              └───────────────┘  │  └───────────────┘  │
                                 └─────────────────────┘
```

---

## Implementation Notes

### Pine Script v6 Constraints

- All variables explicitly typed
- No multiline ternaries
- No reserved keywords as variable names
- Zone boxes use `box.new()` / `box.delete()` — deleted immediately on break
- UDT for zone storage with `.copy()` for independent instances
- Field assignment via local variable (not `.get().field :=`)
- Max 500 labels, 500 boxes, 500 lines on chart — zone cleanup must be aggressive

### Zone UDT

```pine
type Zone
    float top
    float bottom
    int   side          // 1=DEMAND, -1=SUPPLY
    int   swing_class   // 1=HH, 2=LH, 3=LL, 4=HL (inherited from leg tracker)
    int   tf_idx        // 0=M1, 1=M5, 2=M15, 3=H1, 4=H4, 5=D, 6=W
    int   birth_bar     // bar_index when created
    bool  broken        // broken state
    box   bx            // chart box reference
```

### Consumption State UDT

```pine
type ConsumptionCycle
    string parent_tf      // TF that triggered the cycle (e.g., "H4")
    int    parent_dir     // +1 or -1
    bool   active         // cycle is running
    bool   m1_flipped
    bool   m5_flipped
    bool   m15_flipped
    bool   h1_flipped
    int    score          // 0-4
```

### Performance Considerations

- Zone array operations on every bar (checking broken state) — keep arrays small (max 8 per TF per side)
- Consumption state machine only activates on parent STRONG events — low overhead
- 1-2-3 cascade only evaluates when zone count changes — not every bar
- Dashboard only renders on `barstate.islast`

---

## What This Does NOT Include (Deferred)

1. **Triangle detection (EW patterns 7/8/9)** — requires trendline convergence data, complex. Can be added later using the M5/M15 trendline infrastructure.
2. **Automated order placement** — signals are visual (markers + dashboard). No `strategy.*` calls.
3. **W/MN zone tracking for entry signals** — W and MN appear in the Detection Engine dashboard for context, but entry signals only use D as the highest actionable TF. W context is used for the "Weekly Context Check" (strategy Part 18.5) shown in the Signal dashboard.
4. **Backtesting framework** — visual validation via TradingView Replay. No automated backtesting.
5. **Boundary zone drawing** — Boundary zones (strategy Part 12) are derived from the zone tracker implicitly (range from last unbroken zone edge to structural extreme). They are not drawn as separate boxes but the D-Level Cycle phase state machine uses them internally for Phase B/C detection.

---

## Build Sequence

### Phase 1: Detection Engine
Build `iora_detection.pine` by consolidating Modules 1-4 into a single file with the unified dashboard. Validate visually — should produce identical output to the 4 separate modules combined.

### Phase 2: Signal Engine Foundation
Build `iora_signals.pine` with shared preamble + zone creation/tracking + zone counting + zone boxes on chart. Validate: zones appear at correct swing points, break correctly, count correctly.

### Phase 3: Signal Engine State Machines
Add momentum consumption, 1-2-3 cascade detection, terminal gate, D-level cycle phase. Validate: states transition correctly on replay.

### Phase 4: Entry Models
Add Model A-D signal generation with on-chart markers and SL/TP lines. Validate: signals fire at correct locations per strategy doc rules.

### Phase 5: Cleanup
Move Modules 1-4 to `dev/` subfolder. Final validation with both production indicators on chart together.

---

## Validation Protocol

Per `MASTER_SPEC` Part 10:
- **Pairs:** GBPUSD, EURUSD, XAUUSD
- **Chart:** M1 with both indicators loaded
- **Method:** TradingView Replay, step through 2-3 trading sessions
- **Check per phase:**
  - Phase 1: Dashboard matches combined output of Modules 1-4
  - Phase 2: Zones appear at swing points, break when price closes through, count matches manual count
  - Phase 3: Consumption flips in correct sequence, cascade arms correctly, terminal gate fires when all 4 conditions met
  - Phase 4: Entry signals match strategy doc checklist (Part 18)
