# Iora Cascade Zones — New Indicator Template

> **Purpose:** Template and specification for a unified Pine Script indicator that visualizes the structural cascade model validated by the Level 4 sweep data.
>
> **Date:** 2026-04-04
> **Builds on:** `iora_push_zones_v2.pine` (zone detection) + `iora_pivot_hl_trendlines.pine` (structural pivots/trendlines)
> **Validated by:** `docs/system/level4-expanded-sweep-analysis.md` (SQN 2.66 on GBPUSD H1@D1)

---

## What This Indicator Needs To Show

The sweep data validated a specific structural cascade. The indicator must make this cascade VISIBLE so you can:
1. See the D1 push zone bias (where price is heading)
2. See the H4 counter-trend zones (where intraday entries live)
3. See the intraday push/pull within the H4 counter (where to enter and ride)
4. See the cycle transitions (when D1 push resumes, when H4 counter ends)

---

## Indicator Architecture

### Option A: Single Unified Indicator
One indicator that shows all layers. Simpler to use, but may hit TradingView's `request.security()` limit (max 40 calls) if showing all TFs.

### Option B: Two-Indicator System (Recommended)
Split into two focused indicators that work together:

**Indicator 1: Iora Cascade Bias** — The structural context (D1/W1/MN1)
- D1 push zones with HH/LL labels (the primary bias)
- W1 push zones (where D1 is heading toward or pulling from)
- Monthly candle extreme markers (the macro target)
- D-to-W relationship label (continuation / pullback / inside / neutral)
- Bias ribbon showing D1 trend direction over time

**Indicator 2: Iora Cascade Zones** — The entry layer (H4/H1/M15/M5)
- H4 zones with counter-trend / with-trend classification
- H1/M15 structure inside zones (for tighter SL identification)
- Push / continuation / pullback / reversal zone labels
- Parent-TF candle boundary markers (H4/D1 open/close at zone levels)
- Cascade transition signals (H4 counter reaching D1 zone, push resuming)

---

## Indicator 1: Iora Cascade Bias

### What It Shows

```
┌─────────────────────────────────────────────────────┐
│  PRICE CHART                                         │
│                                                      │
│  ████████████  D1 SUPPLY push zone (last LH)         │
│  ░░░░░░░░░░░░  (red fill, "D PUSH-S" label)         │
│                  ← HH/LH/HL/LL label on zone        │
│                                                      │
│        price moves between D1 zones                  │
│                                                      │
│  ░░░░░░░░░░░░  D1 DEMAND push zone (last HL)        │
│  ████████████  (blue fill, "D PUSH-D" label)         │
│                                                      │
│  ════════════  W1 DEMAND level (wide dashed line)    │
│                  ← "W PUSH-D" label                  │
│                                                      │
│  - - - - - -   MN high/low markers (dotted)          │
│                  ← "MN HH" or "MN LL" label          │
│                                                      │
├─────────────────────────────────────────────────────┤
│  BIAS RIBBON (below chart)                           │
│  ▓▓▓▓▓▓▓▓▒▒▒▒▒▒▒▒▓▓▓▓▓▓▓▓▒▒▒▒▒▒                   │
│  green = bull push  red = bear push                  │
│  yellow = compression  gray = expansion              │
│  ▼ transition markers at bias flips                  │
│                                                      │
│  D-to-W: [PULLBACK] or [CONTINUATION] label          │
└─────────────────────────────────────────────────────┘
```

### Data Sources (from push_zones_v2 logic)

| Component | Source | request.security() calls |
|-----------|--------|:------------------------:|
| D1 push zones | HA detection on D1 bars | 1 tuple call |
| D1 period tracking (HH/LL/LH/HL) | Period tracker on D1 | included in D1 tuple |
| W1 push zones | HA detection on W1 bars | 1 tuple call |
| W1 period tracking | Period tracker on W1 | included in W1 tuple |
| MN1 high/low | request.security() for MN OHLC | 1 tuple call |
| D1 bias computation | From D1 period pattern (HH_HL, LH_LL, etc.) | computed from D1 data |
| D-to-W relationship | Price position relative to W1 zones | computed |

**Total request.security() calls: ~3** (D1, W1, MN1 tuples). Well within the 40 limit.

### Key Inputs

```
Group: Bias Zones
  bool  show_d1_zones    = true      // D1 push/reversal zones
  bool  show_w1_zones    = true      // W1 push zones (lines only, not boxes)
  bool  show_mn_levels   = true      // Monthly HH/LL markers
  int   d1_zones_keep    = 3         // How many D1 zones per side to show

Group: Bias Display
  bool  show_bias_ribbon = true      // Color-coded bias strip below chart
  bool  show_d_to_w      = true      // D-to-W relationship label
  bool  show_transitions = true      // Vertical markers at bias flips
  bool  show_hh_ll_labels = true     // HH/HL/LH/LL on zone creation

Group: Colors
  color d1_supply_fill   = red(85)
  color d1_supply_border = red(20)
  color d1_demand_fill   = blue(85)
  color d1_demand_border = blue(20)
  color w1_supply_color  = red(50)   // W zones shown as lines, not boxes
  color w1_demand_color  = blue(50)
  color mn_color         = gray(40)  // Monthly level markers
```

### Zone Lifecycle (from sweep findings)
- D1 zones live until body-close broken (no age expiry)
- Show last 3 per side (configurable)
- Push zones get "PUSH" label + HH/HL/LH/LL classification
- The LAST push zone that made the HH or LL is highlighted (thicker border / brighter color) — this is the primary bias zone

---

## Indicator 2: Iora Cascade Zones — The Intraday Execution Layer

### The Core Problem This Solves

The Cascade Bias (Indicator 1) tells you WHERE (D1 zones) and WHICH DIRECTION (daily push / weekly context). But you need to see HOW the intraday builds the daily candles — the M15/H1 pushes and reversals that create each leg, each H4 candle, each daily move. You need to see:

1. When M15/H1 zones push in one direction → breaking previous zones → building the H4 candle's body
2. When the intraday CHoCH happens → M15/H1 zones on the other side start holding → bias flip
3. Whether the current intraday push is WITH the D1 bias (continuation) or AGAINST it (counter/pullback toward D1 zone)
4. Where to enter: M5 body_close inside M15 zone, or H1 wick at H4 zone
5. Where the structural SL sits (M15/H1 level inside the zone — NOT the full zone boundary)

### Two Trade Types From The Same Cascade

**Trade Type 1: Push trades (with daily bias)**
```
D1 DEMAND push zone holds
    → H4 pushes higher (new H4 demand zones form)
    → M15/H1 zones break UPWARD (supply zones get broken, new demand forms)
    → Each M15 BOS upward = riding the D1 push direction
    → ENTRY: M5 body_close inside M15 demand zone, or H1 wick at H4 demand
    → SL: M15 structure below the entry zone
    → TP: 3:1 from structural SL (or next H4 supply zone)
```

**Trade Type 2: Counter trades (H4 counter toward D1 zone)**
```
D1 SUPPLY push zone exists above (the target/reversal zone)
    → Intraday M15/H1 CHoCH occurs — bias flips UPWARD against D1 bearish push
    → H4 counter-trend demand zones form → price pushes UP toward D1 supply
    → M15/H1 zones push upward, breaking previous supply zones along the way
    → ENTRY: when M15 CHoCH confirms the counter has started
    → RIDE: until price reaches the D1 supply zone (target)
    → EXIT: at D1 zone, expect reversal back in D1 push direction
```

**The transition between types:**
```
Price reaches D1 zone → reversal expected
    → M15/H1 CHoCH occurs IN the D1 push direction (e.g., CHoCH bearish at D1 supply)
    → H4 counter zones start BREAKING
    → Intraday is now pushing WITH D1 bias again
    → Switch from Trade Type 2 (counter) to Trade Type 1 (push)
    → The cycle restarts
```

### What It Shows On The Chart

```
┌─────────────────────────────────────────────────────────────┐
│  PRICE CHART                                                 │
│                                                              │
│  ═══════  D1 SUPPLY zone boundary (from Cascade Bias)        │
│           ← "AT D1 ZONE" marker when price is here           │
│                                                              │
│  ████  H4 SUPPLY zone (CTR to D1 bull bias)                  │
│  ████  orange border, "H4 CTR-S" label                       │
│        ↕ M15 pivot line inside (SL reference)                │
│                                                              │
│  ┄┄┄  M15 zones pushing upward (building H4 counter leg)     │
│  ┄┄┄  thin boxes, green = demand holding, red = supply broken │
│  ★ CHoCH marker where M15 bias flipped                       │
│       ← "M15 CHoCH ▲" or "M15 CHoCH ▼" label                │
│                                                              │
│  ████  H1 zone inside H4 zone (structural SL level)          │
│  ████  thin border, subtle fill                              │
│        ← "SL" label on the structural level                  │
│                                                              │
│  ┄┄┄  M15 zones pushing downward (with D1 push direction)    │
│  ┄┄┄  supply zones holding, demand zones breaking             │
│  ★ CHoCH marker where M15 bias flipped back                  │
│                                                              │
│  ████  H4 DEMAND zone (WITH D1 bull bias)                    │
│  ████  blue border, "H4 WITH-D" label                        │
│                                                              │
│  ═══════  D1 DEMAND zone boundary (from Cascade Bias)        │
│                                                              │
│  ▼ Parent-TF boundary markers (H4/D1 candle open/close)      │
│  ★ Cascade transition (intraday CHoCH at D1 zone =           │
│    the D1 push is resuming)                                  │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  ENTRY DASHBOARD (compact table)                             │
│  ┌──────────┬─────────┬──────────┬─────────────────┐        │
│  │ D1 Bias  │ H4 Dir  │ M15 Bias │ Status          │        │
│  │ BEAR ▼   │ CTR ▲   │ PUSH ▲   │ RIDING COUNTER  │        │
│  └──────────┴─────────┴──────────┴─────────────────┘        │
│                                                              │
│  Status values:                                              │
│  RIDING PUSH    = M15 pushing WITH D1 bias                   │
│  RIDING COUNTER = M15 pushing AGAINST D1 (toward D1 zone)    │
│  AT D1 ZONE     = price inside D1 zone, expect reversal      │
│  CHoCH PENDING  = M15 bias just flipped, watching for conf.  │
│  NO SETUP       = M15 bias unclear or between zones          │
└─────────────────────────────────────────────────────────────┘
```

### Key Intraday Elements

**M15/H1 CHoCH Detection:**
The most important intraday signal. CHoCH = Change of Character = the first push zone that goes AGAINST the previous intraday trend. Detected from the period tracker: when M15 makes a lower high (LH) after a sequence of HH → that's a bearish CHoCH. When M15 makes a higher low (HL) after a sequence of LL → bullish CHoCH.

- CHoCH in D1 push direction at a D1 zone = cascade transition (Trade Type 1 starting)
- CHoCH against D1 push direction = H4 counter starting (Trade Type 2 starting)
- Draw as ★ marker with directional arrow and label

**M15 Zone Flow:**
Show M15 zones as thin, subtle boxes (not as visually heavy as H4 zones). The important thing is which ones are HOLDING vs BREAKING:
- If M15 demand zones hold while supply zones break → bullish intraday push
- If M15 supply zones hold while demand zones break → bearish intraday push
- The direction of the M15 push tells you whether you're in a push trade or counter trade

**H1 Structure Inside H4 Zones (SL Reference):**
When price enters an H4 zone, show the H1 structural level inside it — the most recent H1 HA pivot. This is where the tighter SL goes. The sweep showed sl=atr (1.5x) gives SQN 1.83 with 16h hold time vs 659h with full zone SL. The H1 structural level is the data-informed version of this tighter SL.

**BOS/CHoCH Event Tracking:**
From `iora_bos_choch.pine` logic — track period highs/lows per TF and detect:
- BOS (Break of Structure): push continues, new HH or LL made → trend continues
- CHoCH: push reversal, first LH after HH or first HL after LL → trend may be reversing

Show on M15 and H1 levels. H4 BOS/CHoCH comes from the Cascade Bias or is re-computed.

### Data Sources

| Component | Source | request.security() calls |
|-----------|--------|:------------------------:|
| H4 push zones + period tracking | HA detection on H4 bars | 1 tuple call |
| H1 push zones + period tracking | HA detection on H1 bars | 1 tuple call |
| M15 push zones + period tracking | HA detection on M15 bars | 1 tuple call |
| M15 CHoCH detection | Period tracker on M15 | included in M15 tuple |
| H1 structural pivots (SL ref) | HA pivots on H1 | included in H1 tuple |
| M5 zones (optional, for entry precision) | HA detection on M5 bars | 1 tuple call |
| D1 bias (for CTR/WITH classification) | Period tracker on D1 | 1 tuple call |

**Total request.security() calls: ~5** (H4, H1, M15, M5, D1). Well within limit.

### Key Inputs

```
Group: Entry Zones
  bool  show_h4_zones    = true      // H4 zones (primary entry zones)
  bool  show_h1_zones    = true      // H1 zones (structure inside H4)
  bool  show_m15_zones   = false     // M15 zones (optional precision)
  bool  show_m5_zones    = false     // M5 zones (optional scalp)
  int   h4_zones_keep    = 5         // H4 zones per side to show

Group: Counter-Trend Classification
  bool  classify_ctr     = true      // Label zones as "CTR" (counter) or "WITH" (aligned)
  bool  show_sl_structure = true     // Show M15/H1 structural levels inside zones

Group: Cycle Markers
  bool  show_parent_boundary = true  // H4/D1 candle open/close markers at zones
  bool  show_cascade_transition = true  // Signal when H4 counter reaches D1 zone
  bool  show_reversal_expect = true  // "Reversal expected" when price approaches D1

Group: Dashboard
  bool  show_dashboard   = true
  string dash_position   = "Bottom Right"
```

### Zone Classification Logic

For each H4 zone, determine its relationship to the D1 bias:

```
// D1 bias direction from period tracker
d1_bias_bull = (d1_period_hi > d1_prev_period_hi)  // HH = bullish push

// H4 zone classification
if h4_zone.is_supply AND d1_bias_bull
    → "H4 CTR-S" (counter-trend supply — price pulling back up,
       this supply zone is AGAINST the D1 bullish push)
    → This is WHERE you look for shorts riding the counter toward D1 demand

if h4_zone.is_demand AND d1_bias_bull
    → "H4 WITH-D" (with-trend demand — aligned with D1 bullish push)
    → This is WHERE the D1 push launched from

if h4_zone.is_supply AND NOT d1_bias_bull
    → "H4 WITH-S" (with-trend supply — aligned with D1 bearish push)

if h4_zone.is_demand AND NOT d1_bias_bull
    → "H4 CTR-D" (counter-trend demand — price pulling back down,
       against D1 bearish push)
```

### Structural SL Inside Zones

When price enters an H4 zone, show the M15/H1 structural levels inside it:
- The most recent M15 HA pivot high/low inside the zone boundaries
- This becomes the tighter SL reference (instead of the full H4 zone boundary)
- Visual: thin horizontal line inside the zone box, labeled "SL ref"

### Cascade Transition Detection

Detect when the H4 counter-trend push reaches the D1 push zone:
1. Price enters the D1 push zone (from Indicator 1)
2. The most recent H4 zone was counter-trend ("CTR")
3. Signal: "Cascade transition — expect D1 push to resume"
4. Visual: star marker or vertical line at the bar where price enters D1 zone

---

---

## How Intraday Builds The Daily — The Execution Logic

This is the core understanding that the indicators must make visible:

**Each daily candle is built by intraday pushes:**
```
DAILY CANDLE (e.g., bearish day — close below open)
    │
    ├── Asian session: M15 pushes up (H4 counter-trend), creates demand zones
    │   → M15 CHoCH upward starts the counter move
    │   → H1 zones form as price pushes up
    │   → TRADE TYPE 2: ride the M15 push upward toward D1 supply
    │
    ├── London open: Price reaches D1 supply zone area
    │   → M15 CHoCH downward at/near D1 supply
    │   → "AT D1 ZONE" status → expect reversal
    │   → TRADE TYPE TRANSITION: counter → push
    │
    ├── London/NY: M15 pushes down (D1 push direction)
    │   → Breaks H4 counter-trend demand zones from Asian session
    │   → Creates new supply zones, each lower than previous (LH sequence)
    │   → TRADE TYPE 1: ride the M15 push downward with D1 bias
    │
    └── NY close: Daily candle closes bearish
        → The D1 push zone extended further (or new push zone created)
        → H4/H1 zones from the day's move remain as structure
        → Tomorrow: cycle may repeat, or D1 CHoCH if the push exhausts
```

**What the indicator needs to show at M15 level:**
- The M15 CHoCH markers that START each push/counter leg
- The M15 zones that are currently HOLDING (the entry zones for the current push direction)
- The M15 zones that just BROKE (confirmation that the push is valid — structure broke in the push direction)
- The H1 structural level inside the active H4 zone (where SL goes)
- The D1 zone boundary (where reversal is expected)

**The M15 CHoCH is the trigger. The H4 zone is the context. The D1 zone is the target/reversal.**

### Sweep Data That Validates This Model

| What The Sweep Found | What It Means For Intraday Execution |
|---------------------|--------------------------------------|
| H1@H4 against_daily SQN 1.12 | The H4 counter-trend push (Trade Type 2) has a validated edge |
| H1@D1 with_daily SQN 2.66 | Trading at D1 zones with daily bias (Trade Type 1 at D1 reversal point) has the strongest edge |
| Body_close M5@M15 SQN 1.52 | M5 candles closing inside M15 zones = accumulation before the push continues |
| Retest #4-10 SQN 2.04 | Zone needs 1-2 parent-TF candles — the M15 zone needs 1-2 H1 candles before the retest entry is reliable |
| sl=atr SQN 1.83, 16h hold | Tighter SL (H1 structure inside zone) = viable intraday trades, not multi-week swings |
| Reversal zones WR 42.2% | M15/H1 CHoCH zones (reversal) = highest per-trade conviction |

---

## What To Reuse From Existing Indicators

| Existing Code | What To Take | From File |
|--------------|-------------|-----------|
| HA detection + run tracking | Core zone creation logic (all TFs) | `iora_push_zones_v2.pine` |
| Period tracking (prev hi/lo, trend) | BOS/CHoCH, HH/LL classification | `iora_push_zones_v2.pine` |
| Push/reversal/nesting | Zone classification | `iora_push_zones_v2.pine` |
| Zone box drawing + labels | Visual rendering | `iora_push_zones_v2.pine` |
| Dashboard table | Status display | `iora_push_zones_v2.pine` |
| BOS/CHoCH period structure labels | HH/HL/LH/LL on chart (the structure visible in screenshots) | `templates/iora/iora_bos_choch.pine` |
| Pivot HL detection | Structural swing points for trendlines | `iora_pivot_hl_trendlines.pine` |
| 2-anchor adaptive trendlines | TL drawing + extension + break detection | `iora_pivot_hl_trendlines.pine` |
| TL break detection (close/wick) | Confluence signal at zone retests | `iora_pivot_hl_trendlines.pine` |

### What's NEW (not in any existing indicator)

1. **Counter-trend vs with-trend zone classification** — comparing H4 zone direction to D1 bias
2. **D-to-W relationship computation** — price position relative to W1 zones
3. **Bias ribbon** — continuous color strip showing D1 bias state
4. **Cascade transition detection** — H4 counter reaching D1 zone
5. **Structural SL reference** — M15/H1 pivots inside H4 zones
6. **Monthly candle extreme markers** — MN HH/LL levels
7. **Parent-TF candle boundary markers** — H4/D1 open/close at zone levels
8. **Internal vs External structure separation** — M5/M15 (internal) vs H1/H4 (external) swing structure
9. **Structural trendlines** — connecting H1/H4 swing points, break detection as confluence
10. **Breaker zones** — CHoCH zones that become opposite-side levels (highest conviction retests)
11. **M5 CHoCH precision entry** — M5 internal reversal inside H1/M15 zone inside H4 zone

---

## Internal vs External Structure Model

Reference: `docs/system/images/structure_bos_choch/09_internal_vs_external_bos_ibos_ebos.png` and `14_*`, `15_*`

The diagrams show TWO levels of structure operating simultaneously:

```
EXTERNAL STRUCTURE (H1/H4 swings — the "black zigzag")
│
│  eBoS → eBoS → eBoS (external trend continues)
│                        → eCHoCH (external reversal — major structural shift)
│
│  Trendlines connect external swing points
│  Trendline break = structural shift confirmed
│
├── INTERNAL STRUCTURE (M5/M15 swings — the "cyan zigzag")
│   │
│   │  iBoS → iBoS → iBoS (internal pushes building the external leg)
│   │                        → iCHoCH (internal reversal — early warning)
│   │
│   │  The iCHoCH is the FIRST sign that the external trend may reverse
│   │  It happens BEFORE the eCHoCH
│   │  It happens INSIDE a zone (the zone where the reversal starts)
│   │
│   └── When iCHoCH is followed by eCHoCH = full structural confirmation
│       When iCHoCH fails and eBoS continues = false alarm (internal noise)
```

**How this maps to TF pairs:**

| Structure Level | TFs | What It Shows |
|----------------|-----|---------------|
| External | H1/H4 swings | The major structural legs — D1 push, H4 counter |
| Internal | M5/M15 swings | The intraday moves building each external leg |
| Trendlines | Drawn along H1/H4 external swings | Structural support/resistance lines |

**Why this matters for entries:**
- External eCHoCH at D1 zone = the highest conviction signal (full structural reversal at a structural level)
- Internal iCHoCH at H4 zone = early entry signal (intraday has reversed, waiting for external confirmation)
- Trendline break between the iCHoCH and eCHoCH = the structural shift is real, not just noise
- M5 iCHoCH inside an M15/H1 zone = precision entry point with tightest possible SL

---

## Breaker Zones (CHoCH Zones)

Reference: `docs/system/images/structure_bos_choch/03_bos_vs_choch_htf_supply_demand_full_cycle.jpg`

When a CHoCH occurs, the zone that was created at/near the CHoCH point becomes a **breaker zone**:

```
BEARISH TREND: price makes LH → LL → BOS → LH → LL → BOS
                                                        │
    Zone X was demand (support during the downtrend)     │
                                                        │
    CHoCH occurs — price breaks above the LH             │
                                                        │
    Zone X is now BROKEN as demand — it becomes a        │
    BREAKER ZONE (acts as supply/resistance on retest)   │
                                                        ▼
    When price retests Zone X from above → high conviction SHORT
    (the zone that used to hold as demand now acts as supply)
```

**Breaker zone = the most validated retest entry.** The sweep data showed reversal zones at 42.2% WR and +0.267R — breaker zones are the specific subset of reversal zones that have already proven they can break structure. They should be even higher conviction.

**Implementation:** When a zone's CHoCH event is confirmed (the period tracker detects the structural break), mark that zone as a breaker. On retest, it trades as the OPPOSITE side — former demand acts as supply, former supply acts as demand.

---

## M5 CHoCH Precision Entry

The tightest possible entry: M5 internal CHoCH inside a higher TF zone.

```
H4 CTR-D zone holds (H4 counter-trend demand)
    │
    ├── H1 zone exists inside H4 zone (SL reference)
    │
    ├── M15 zone exists inside H1 zone
    │
    └── M5 makes iCHoCH UPWARD inside the M15/H1 zone
        │
        ├── M5 was making LL → LL → LL (pushing down into the zone)
        │
        └── M5 makes HL instead of LL → iCHoCH bullish
            │
            ├── ENTRY: at the M5 HL zone (demand zone created at the CHoCH)
            ├── SL: below the M5 HL zone (tightest structural SL possible)
            ├── TP: 3:1 from M5 SL, or the H4 supply zone above
            │
            └── Confluence stack:
                ✓ D1 bias direction (from Cascade Bias)
                ✓ H4 CTR zone holding (structural context)
                ✓ H1 structure inside zone (intermediate confirmation)
                ✓ M15 zone flow direction (intraday push)
                ✓ M5 iCHoCH (precision timing — the reversal just started)
                ✓ Trendline break (if M5/M15 breaks a descending TL at the zone)
```

**This is the full cascade stacked entry.** Every layer confirms. The SL is at the M5 structural level (maybe 5-15 pips on FX) instead of the H4 zone boundary (100+ pips). The R:R explodes.

---

## Enhanced Entry Model (Complete)

```
D1 zone provides bias (from Cascade Bias)
    │
    ├── EXTERNAL: H4 counter-trend zone provides entry area
    │   └── H1 trendline connects external swing points
    │       └── H1 trendline break confirms structural shift
    │
    ├── INTERNAL: M15 CHoCH confirms intraday reversal direction
    │   └── M15 breaker zone marks the transition point
    │       └── M5 iCHoCH inside the M15/H1 zone = precision entry
    │
    ├── SL: below/above the M5 CHoCH zone (tightest structural SL)
    ├── TP: 3:1 from M5 SL, or next H4/D1 zone boundary
    │
    └── Confluence score (how many layers confirm):
        1 = zone only (weakest)
        2 = zone + bias alignment
        3 = zone + bias + CHoCH
        4 = zone + bias + CHoCH + trendline break
        5 = zone + bias + CHoCH + TL break + M5 precision (strongest)
```

---

## Build Order

### Phase 1: Iora Cascade Bias (D1/W1/MN context) ✅ BUILT
Already working — D1/W1/MN zones, bias ribbon, D→W relationship.

### Phase 2: Iora Cascade Zones — Intraday Execution Layer (CURRENT)

**2a. H4 zones with CTR/WITH classification** ✅ BUILT

**2b. M15 zone flow + CHoCH detection** ✅ BUILT (v2)
- M15 zones with thin boxes
- M15 CHoCH markers (★) with directional labels
- CHoCH at D1 zone = cascade transition

**2c. H1 structural SL inside zones** ✅ BUILT (v2)
- H1 zone inside H4 zone → SL reference line

**2d. Dashboard + status** ✅ BUILT (v2)
- D1 Bias | H4 Dir | M15 Bias | Status

### Phase 3: Trendlines + Internal/External Structure (NEXT)

**3a. Structural trendlines on H1/H4 (external structure):**
1. Port pivot HL trendline logic from `iora_pivot_hl_trendlines.pine`
2. Draw descending TL along H1/H4 LH sequence, ascending TL along HL sequence
3. Detect trendline breaks (close-based from the pivot indicator)
4. Label TL breaks at the break bar — "TL BRK ▲" or "TL BRK ▼"
5. TL break + zone retest = highest conviction confluence signal
6. Keep broken TLs visible briefly (configurable history) so you can see where the break happened

**3b. M5 CHoCH precision entry with rejection quality scoring (internal structure):**
7. Add M5 zone detection (request.security for M5 TF)
8. Add M5 period tracking + CHoCH detection (same logic as M15 CHoCH)
9. Draw M5 CHoCH markers ONLY when they occur inside an active M15/H1/H4 zone — don't clutter with all M5 CHoCH events
10. M5 CHoCH inside a zone + in the zone's expected direction = entry signal
11. The M5 CHoCH zone becomes the entry zone with SL at its structural level

**3b-ii. Rejection quality scoring on CHoCH events (M5 and M15):**

A CHoCH is not just a binary event — its QUALITY determines conviction. A reversal candlestick pattern on a higher TF (hammer, engulfing, shooting star) is the SAME structural event as the LTF CHoCH, just viewed at different granularity:

- An H1 hammer at a demand zone = M5/M15 pushed DOWN (bearish BOS), then M5/M15 CHoCH occurred (first HL), then M5/M15 pushed back UP. The H1 candle closes with the long lower wick.
- An H1 engulfing at a supply zone = M5/M15 was bullish, then CHoCH occurred, then pushed aggressively down, engulfing the previous H1 body.

The candlestick pattern IS the multi-TF CHoCH aggregated into one parent-TF bar. Instead of detecting candlestick patterns (visual heuristics), detect the CHoCH quality (the underlying mechanics):

12. **Wick rejection ratio** at CHoCH bar: `wick_into_zone / total_range`
    - High ratio (>0.6) = hammer/pin bar forming on parent TF = strong institutional rejection
    - Low ratio (<0.3) = weak rejection, may fail
13. **Body momentum ratio** at CHoCH bar: `abs(close - open) / total_range`
    - High ratio (>0.5) = engulfing-like momentum = aggressive follow-through
    - Low ratio (<0.2) = doji/indecision = weak reversal
14. **Follow-through confirmation**: does the NEXT bar after CHoCH continue in the reversal direction?
    - Yes = engulfing confirmation (strong)
    - No = failed reversal (filter out)
15. Combine into a **rejection quality score** (0-3):
    - +1 if wick_ratio > 0.5 (strong rejection wick)
    - +1 if body_ratio > 0.4 (strong momentum body)
    - +1 if follow-through confirmed (next bar continues direction)
    - Score 0 = skip, Score 1 = weak, Score 2 = good, Score 3 = strong
16. Only show M5 CHoCH markers when rejection_quality >= 2 (configurable threshold)
    - This dramatically reduces clutter — only high-quality reversals show up
    - The "u" markers flooding the chart are the score 0-1 events that should be hidden

**Candlestick pattern equivalence table:**

| Candlestick Pattern | What It Is Structurally | CHoCH Quality Score |
|--------------------|-----------------------|:-------------------:|
| Hammer / Pin Bar | Long wick into zone, body closes outside = strong rejection | wick_ratio high → Score 2-3 |
| Bullish Engulfing | CHoCH + aggressive body covering previous bar = momentum shift | body_ratio high + follow-through → Score 2-3 |
| Morning Star | 3-bar: push into zone, doji/small body (accumulation), then push out = CHoCH with base | Compression-born CHoCH → Score 2+ |
| Shooting Star | Mirror of hammer at supply zone | wick_ratio high → Score 2-3 |
| Bearish Engulfing | Mirror of bullish engulfing at supply | body_ratio high + follow-through → Score 2-3 |
| Evening Star | Mirror of morning star at supply | Compression-born CHoCH → Score 2+ |
| Doji inside zone | Price accumulating, no direction yet = CHoCH pending | Score 0-1, wait for follow-through |

Reference: `docs/candlestick_patterns/candlestick_reversal_patterns.webp`

**3c. Breaker zone detection and marking:**
12. When a CHoCH occurs on M15/H1/H4, find the zone that was active at/near the CHoCH point
13. Mark that zone as a "BREAKER" — it now trades as the opposite side
14. Visual: distinct color/style for breaker zones (e.g., dashed border, "BRK" label)
15. On retest of a breaker zone → strongest entry signal
16. Former demand that got broken → now acts as supply (breaker supply)
17. Former supply that got broken → now acts as demand (breaker demand)

**3d. Confluence scoring:**
18. On each entry signal (M5 CHoCH at a zone), count how many layers confirm
19. Display confluence count on the dashboard or as a label at the entry bar
20. 1-2 = low conviction, 3-4 = good, 5 = maximum confluence

### Phase 4: Refinement
After all phases work together:
1. Tune visual hierarchy — trendlines should be subtle, CHoCH markers prominent
2. Add input toggles for each layer (show_trendlines, show_m5_choch, show_breakers)
3. Performance optimization — M5 data adds significant bar count
4. Test on multiple symbols and TFs
5. Compare visual entries against sweep data — do the confluence-5 entries match the SQN 2.66 setups?

---

## Active Files (Post-Cleanup)

```
tw_indicators/
  iora_zones/
    iora_push_zones_v2.pine          ← Reference: zone detection logic to reuse
  iora_structure/
    iora_pivot_hl_trendlines.pine    ← Reference: pivot/trendline logic for Phase 3
  IORA_CASCADE_INDICATOR_TEMPLATE.md ← This file

  archive/                           ← All superseded indicators preserved here
    gold_system_v1/
    v1_indicators/
    v1_structure/
    v1_system/
    v1_templates/
```

---

## Connection to Python Engine

The indicator logic maps directly to existing Python modules:

| Indicator Component | Python Module | Status |
|--------------------|---------------|:------:|
| D1 zone detection | `push_zone_tick.py` + `push_zone_engine.py` | ✅ Exists |
| Period tracking / bias | `bias_timeline.py` | ✅ Exists |
| D-to-W relationship | `bias_timeline.py` (d_to_w_relationship field) | ✅ Exists |
| Zone retest detection | `opportunity_counter.py` | ✅ Exists |
| Internal/external CHoCH | `push_zone_tick.py` (BOS/CHoCH per TF) | ✅ Exists |
| Structural SL levels (H1 inside H4) | Needs: pivot detection inside zones | ⬜ New |
| Trendlines + break detection | `xtf_trendline.py` + `trendline_tick.py` (exists but different approach) | ⚠️ Needs adaptation to pivot-HL style |
| Breaker zone detection | Needs: CHoCH zone flip logic in zone engine | ⬜ New |
| M5 CHoCH precision entry | Needs: M5 period tracking + CHoCH in opportunity/strategy layer | ⬜ New |
| Confluence scoring | Needs: count of confirming layers at entry time | ⬜ New (strategy layer) |

When the indicator shows something on the chart, the Python engine should produce the same data for backtesting. The visual validation on TradingView confirms the Python engine's output is correct.

### New Python modules needed for Phase 3:

```
src/iora/engine/
  pivot_sl.py                    # H1 pivot detection inside H4 zones → SL reference
  breaker_zone.py                # CHoCH zone flip: demand→supply, supply→demand

src/iora/strategy/
  confluence_scorer.py           # Count confirming layers at entry (1-5 score)
  # retest_config.py             # Add: confluence_min, trendline_required, breaker_only filters
```
