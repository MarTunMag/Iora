# Iora Structural Detection System — Master Specification

**System:** Iora  
**Date:** March 2026  
**Author:** Marius Tunestveit Magnusson  
**Purpose:** Unified reference for building the modular Pine Script v6 structural detection system. This document captures the complete design evolution, all architectural decisions, and the modular build plan.

---

## PART 1 — SYSTEM OVERVIEW

### 1.1 What This System Does

Detects structural swings (HH, HL, LH, LL) at every timeframe from M1 to Monthly, using a four-layer detection cascade that fires progressively earlier — from minutes ahead (momentum layer) to seconds ahead (hybrid envelope) to real-time (period-level breaks) to confirmed (zone-based). Each layer adds confidence while the fastest layers give preparation time.

### 1.2 The Four Detection Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    FOUR-LAYER DETECTION                     │
│                                                             │
│  Layer 1: Direct M1 momentum         → EARLIEST ALERT      │
│    SMA crossovers of M1 closes         (momentum regime)    │
│           ↓ if momentum shifts                              │
│  Layer 2: Hybrid cascade envelope    → STRUCTURAL DETECT    │
│    Live building candles + 3-source    (conviction-based)   │
│    envelope (floor/mid/ceiling)        (I/E classification) │
│           ↓ if strong CHoCH fires                           │
│  Layer 3: Period-level breaks        → STRUCTURAL CONFIRM   │
│    prev_period high/low breaks         (objective levels)   │
│    (iora_bos_choch.pine)                                    │
│           ↓ if break exceeds parent                         │
│  Layer 4: Zone-based confirmation    → EXECUTE              │
│    Colour-flip zones + classification  (full context)       │
│    (existing Iora zone system)                              │
│                                                             │
│  Speed:    1 fastest ──────────────────────── 4 most precise│
│  Noise:    1 most noise ──────────────────── 4 least noise  │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Core Principles

- **Line candles (raw OHLC)** for all computations. No Heikin Ashi, no Renko, no smoothing. Zones and levels sit at real executable prices.
- **Parameter-free.** Window sizes derived from natural parent-child TF ratios (5 M1s per M5, 3 M5s per M15, 4 M15s per H1, etc.). No tunable lookback lengths.
- **Parent-child cascade.** Every structural event at TF X simultaneously creates or updates structure at parent TF X+1. Detection propagates bottom-up; context flows top-down.
- **Conviction-based internal/external.** The three-source envelope (avg highs, avg closes, avg lows) doesn't just measure confidence — it classifies each event as internal (weak CHoCH: closes don't confirm) or external (strong CHoCH: all three sources confirm → parent TF structural event).

---

## PART 2 — THE DESIGN EVOLUTION (Key Questions & Answers)

### 2.1 Starting Point

**Q:** How can we use the `iora_bos_choch` indicator's period high/low breaks to get the earliest confirmation of HH/HL/LH/LL — through child-TF broken highs/lows? E.g., an M15 high CHoCH confirms the H1 high; through the M5 high CHoCH we understand the M15.

**A → Spec 04:** Period-level structure. Each TF has a previous-period high and low (objective, parameter-free). When a child-TF break exceeds the parent TF's previous-period level, the parent TF's structure has shifted — detected at child-TF speed with zero lag. A per-TF state machine tracks swing sequences (HH/HL/LH/LL) and classifies breaks as BOS or CHoCH.

### 2.2 Dynamic Averages

**Q:** Could we run an average candle high/low check using e.g. avg 5×M1 candles, to get the dynamically moving low (if we move up through the M1 candles), to get the CHoCH of the M5 HL at the earliest point — even faster, non-lagging structural information?

**A → Spec 04 Part A:** Yes. For each parent TF, compute a rolling average of child-TF candle lows (dynamic floor), highs (dynamic ceiling). Window = natural period ratio (5 for M5, 3 for M15, etc.). When the rising floor breaks → intra-period CHoCH detected *before* the parent candle closes.

**Key insight that emerged:** Instead of one average, use a **three-source envelope** — avg(lows) for the structural floor, avg(closes) for directional commitment, avg(highs) for the structural ceiling. This enables conviction scoring:
- **Strong CHoCH:** floor breaks AND closes AND ceiling all confirm → propagate to parent TF
- **Weak CHoCH:** floor breaks but closes still going the other way → likely a wick/sweep, don't propagate
- **Pre-CHoCH:** closes stalling, floor/ceiling intact → momentum fading, prepare but don't act

### 2.3 Candle Type

**Q:** What candle type would be best? Line? HA? Three Line Break? Renko?

**A → Spec 04a:** Line (raw OHLC). Price-based candles (Renko, Three Line Break, Kagi, Range bars) are eliminated because they break the fixed parent-child period ratios. HA vs Line is a non-question for the dynamic floor/ceiling: `HA_high` virtually always equals the real `high`, so the computed averages are identical. Line wins by default — no synthetic computation, real executable prices, no smoothing lag, parity-safe across Pine/Python/MQL5.

### 2.4 Leg Architecture

**Q:** Can we through the parent-child cascade accurately get the internal highs/lows of the daily candle through understanding that when the H4 creates a high, then the H1 and TFs down create lows, then see the H4 dynamic high move down and break — getting the earliest confirmation of the daily low? And understand the legs needed to be created up and down the cascades.

**A → Spec 04b:** Every parent-TF swing is built from a specific sequence of child-TF legs (up-leg → down-leg → up-leg). By tracking the current leg direction and number at every TF simultaneously, you always know: what you're building (parent high or low), what the classification will be (HH/LH/HL/LL depending on whether the current leg exceeds the parent's previous extreme), what legs must complete before the parent swing is confirmed, and where the liquidity targets sit for the next opposing leg.

### 2.5 Conviction as Internal/External Classifier

**Q:** Could we use weak/strong/pre CHoCH to better understand the internal/external details? The avg(closes) addition would help.

**A → Spec 04c:** The conviction level IS the internal/external classifier. They're the same thing measured from different angles. A weak CHoCH doesn't reach the parent TF because it lacks commitment (closes don't confirm). A strong CHoCH reaches the parent TF precisely because all three sources shifted. The close average is the discriminator: if closes confirm the break, it's external (leg transition, parent gets structural event); if closes don't confirm, it's internal (sub-wave pullback, parent unaffected).

**Critical addition:** Internal health monitoring. Track the *sequence* of weak CHoCH events within each leg. When internal swings degrade (counter-trend HH/HL appearing inside a bearish leg), predict the external event 1–3 child candles before it fires.

### 2.6 Momentum Consumption

**Q:** We should be able to see when each TF's momentum gets eaten up — as we see the lows/highs consumed after an H4 CHoCH, then H1 BOS, M15 BOS, etc., with the M1 strong CHoCH confirming the H4 HH, biases shifting, understanding that M1 highs need to be broken to create M5 LH, then M5 LL, then M5 LH CHoCH to make M15 LH, etc., pushing down from the daily HH/LH, creating the needed legs.

**A → Spec 04d:** After any parent-TF structural shift, each child TF carries residual momentum in the old direction. Those biases are consumed one by one, from M1 upward, through strong CHoCH flips. Each flip requires a counter-leg (a push in the old direction that creates the LH/HL needed for the next TF to build new-direction structure). These counter-legs aren't reversals — they're the mechanical requirement for structure to propagate upward. Track consumption % per TF (0% = old bias dominant, 100% = flipped). Consumption depth predicts parent classification: shallow (1–2 TFs flip) = parent pullback; deep (all flip) = parent leg transition.

### 2.7 Computation Architecture

**Q:** Should we use cascading TF averages (M5×3 for M15), or direct M1 data (M1×1440 for daily, M1×60 for H1)?

**A → Spec 04e:** Neither pure approach — use a **hybrid**. Direct M1 averaging is structurally wrong: `avg(60 M1 lows)` ≠ H1 candle low (which is `min(60 M1 lows)`, not the average). But pure cascading is slow (D envelope only updates every 4 hours on H4 close). The hybrid reconstructs each TF's candle from M1 data in real time (high = max, low = min, close = latest), then cascades those reconstructed candles into the envelopes. M1-speed updates with structurally correct candle values.

**Key discovery:** The existing `HTF_Candles__M5_-_12MN_.pine` indicator already does this via `request.security(syminfo.tickerid, "TF", [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)`. With lookahead on, this returns the BUILDING candle's current OHLC — no manual M1 reconstruction needed.

Also run direct M1 SMA crossovers as a separate **momentum temperature** layer (Layer 1 in the four-layer system). These are valid trend indicators, just not structural detectors.

---

## PART 3 — THE TIMEFRAME CASCADE

### 3.1 Parent-Child Relationships

| Child TF | Parent TF | Ratio | Meaning |
|---|---|---|---|
| M1 | M5 | 5:1 | 5 M1 periods build one M5 |
| M5 | M15 | 3:1 | 3 M5 periods build one M15 |
| M15 | H1 | 4:1 | 4 M15 periods build one H1 |
| H1 | H4 | 4:1 | 4 H1 periods build one H4 |
| H4 | D | 6:1 | 6 H4 periods build one D (24h) |
| D | W | 5:1 | 5 D periods build one W |
| W | MN | ~4:1 | ~4 W periods build one MN |

### 3.2 Cascade Direction

- **Bottom-up (execution):** M1 CHoCH → confirms M5 direction → M5 CHoCH → confirms M15 leg complete → ... → H4 structural event → creates D structure
- **Top-down (context):** MN → W → D → H4 → H1 → M15 → M5 → M1

### 3.3 Propagation Rule

When a child-TF break exceeds the parent TF's previous-period level, it simultaneously confirms a parent-TF structural event. The cascade can chain: a single strong move on M1 can propagate M5 → M15 → H1 → H4 in real time.

---

## PART 4 — THREE-SOURCE ENVELOPE & CONVICTION

### 4.1 The Three Sources

| Source | Computation | Structural meaning |
|---|---|---|
| **Dynamic floor** | avg(child candle lows) | Structural support — where buyers defend |
| **Dynamic mid** | avg(child candle closes) | Directional commitment — where the market settles |
| **Dynamic ceiling** | avg(child candle highs) | Structural resistance — where sellers defend |

### 4.2 Conviction Classification

| Floor | Mid (closes) | Ceiling | Conviction | Structural class |
|---|---|---|---|---|
| Breaking | Reversing | Breaking | **STRONG** | External event — leg transition, parent TF receives structural data |
| Breaking | Same direction | Intact | **WEAK** | Internal event — liquidity grab, sub-wave swing marked, leg continues |
| Intact | Stalling | Intact | **PRE** | Internal warning — momentum fading, prepare but don't act |

### 4.3 Internal Health Monitoring

Track the sequence of internal swings from weak CHoCH events within each leg:
- **HEALTHY:** internal swings trending with the leg (HH/HL in up-leg)
- **FIRST_CRACK:** first internal swing against the leg (internal LL in up-leg)
- **DEGRADING:** multiple counter-trend internal swings
- **BROKEN:** internal trend fully reversed → strong CHoCH (external event) imminent (1–3 child candles)

### 4.4 The Close Average as Discriminator

The `avg(closes)` is the key that separates internal from external. If closes confirm the break → institutional commitment has shifted → external event → parent TF structure changes. If closes don't confirm → the break was a probe/sweep → internal event → parent TF unaffected.

---

## PART 5 — LEG ARCHITECTURE

### 5.1 Legs Build Parent Swings

Every parent-TF swing high is built by a sequence of child-TF up-legs and confirmed when the first child-TF down-leg begins. Every parent-TF swing low is the mirror.

### 5.2 Leg State Per TF

```
LegState:
    direction:      UP | DOWN
    leg_number:     int (sequential count since last parent swing)
    building:       PARENT_HIGH | PARENT_LOW
    leg_high:       float (max child high in this leg)
    leg_low:        float (min child low in this leg)
    prev_leg_high:  float
    prev_leg_low:   float
```

### 5.3 Counter-Legs Are Required

After a parent-TF shift (e.g., H4 CHoCH bearish), each child TF must create counter-legs (pushes in the old direction) to build the LH/HL structure needed for the new direction to propagate upward. These counter-legs are not reversals — they're the structural mechanism of propagation.

---

## PART 6 — MOMENTUM CONSUMPTION

### 6.1 Bias Register

After a parent-TF shift, each child TF carries residual momentum in the old direction. Track consumption per TF:
- 0%: old bias dominant, NONE conviction
- 25%: PRE conviction (momentum fading)
- 40–60%: WEAK CHoCH firing (internal events, health degrading)
- 75–85%: approaching STRONG CHoCH
- 100%: FLIPPED — bias aligned with parent

### 6.2 Consumption Depth = Parent Classification

- **Shallow** (1–2 TFs flip): parent pullback (HL/LH)
- **Medium** (3 TFs flip): significant correction (confirmed HL/LH)
- **Deep** (all TFs flip): parent leg transition (impulsive HH/LL)
- **Overflow** (exceeds parent level): grandparent structural event

---

## PART 7 — EXISTING CODE ASSETS

### 7.1 `iora_bos_choch.pine` (Iora Structure Levels)

- Tracks previous-period high/low for M5, M15, M30, H1, H4, D, W, MN, QT, HY, YR
- Detects exact bar where price first breaks each level
- Draws lines from extreme bar to break bar (or extends right if unbroken)
- ✗ suffix on broken levels
- **Key function:** `track_period(string tf)` → returns `[prev_hi, prev_hi_t, prev_lo, prev_lo_t, hi_brk_t, lo_brk_t]`
- **What it lacks:** BOS/CHoCH classification, swing sequence tracking, parent propagation

### 7.2 `HTF_Candles__M5_-_12MN_.pine` (HTF Candle Plotter)

- Draws building candles for all TFs from M5 to 12MN as background boxes with wicks
- Uses `request.security(syminfo.tickerid, TF, [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)`
- **Critical for hybrid approach:** `lookahead=barmerge.lookahead_on` gives the BUILDING candle's live OHLC — high = current max, low = current min, close = latest close. This eliminates manual M1 reconstruction for the hybrid envelope.
- Supports M5, M15, M30, H1, H4, D, W, MN, 3M, 6M, 12M
- History tracking with configurable depth per TF
- Badge labels with anti-overlap logic

### 7.3 Existing Iora Zone System (referenced, not uploaded)

- `ha_supply_demand_zones.pine` — base zone detection with 8-TF support
- `spring_leaf_wave_navigator.pine` — zone tick, BOS/CHoCH detection, nested containment, sequence counting, wave state machine, boundary zones, HTF phase, dashboard table, push trendlines

---

## PART 8 — MODULAR BUILD PLAN

### Module 1: Hybrid Envelope Engine (`iora_envelope.pine`)

**Purpose:** Compute the three-source dynamic envelope for each TF using live building candles.

**Inputs:**
- `request.security` with `lookahead=barmerge.lookahead_on` for each TF (pattern from HTF Candles indicator)
- Previous N closed candles' OHLC (stored in arrays/vars)

**Outputs per TF:**
- `dynamic_floor` (avg of last N child candle lows, including building candle)
- `dynamic_mid` (avg of last N child candle closes, including building candle)
- `dynamic_ceil` (avg of last N child candle highs, including building candle)
- `floor_delta`, `mid_delta`, `ceil_delta` (gradients)
- `gradient_score` (-6 to +6)

**Key implementation note:** Use `request.security` with lookahead to get building candle OHLC directly — no manual M1 max/min reconstruction needed. For each parent TF, store the last N-1 closed child candle OHLC values, then combine with the live building candle for the envelope calculation.

### Module 2: Conviction Classifier (`iora_conviction.pine`)

**Purpose:** Assess conviction level (STRONG/WEAK/PRE/NONE) from the envelope data. Classify each event as internal or external.

**Inputs:** Envelope values + gradients from Module 1, current leg direction from Module 4.

**Outputs per TF:**
- `conviction` (STRONG/WEAK/PRE/NONE)
- `conviction_side` (BULLISH/BEARISH/NONE)
- `struct_class` (EXTERNAL/INTERNAL/INTERNAL_WARNING/NONE)
- `internal_health` (HEALTHY/FIRST_CRACK/DEGRADING/BROKEN)

**Logic:**
- STRONG: floor/ceiling breaks AND mid (closes) confirms AND gradient aligns → EXTERNAL
- WEAK: floor/ceiling breaks, mid doesn't confirm → INTERNAL (mark internal swing)
- PRE: mid stalling, floor/ceiling intact → INTERNAL_WARNING

### Module 3: Period-Level Breaks (`iora_bos_choch.pine` v2)

**Purpose:** Extend the existing indicator with swing state machine, BOS/CHoCH classification, and parent propagation.

**Additions to existing code:**
- Per-TF swing tracking: `last_swing_high`, `last_swing_low`, `prev_swing_high`, `prev_swing_low`
- Swing classification: HH/LH/HL/LL by comparing to previous same-type swing
- BOS/CHoCH labels at break points based on trend state and classification
- Parent propagation: when break exceeds parent's prev-period level → eBOS+/eCHoCH+ label
- Wick break for detection, body-close for parent propagation (configurable)

### Module 4: Leg Tracker (`iora_legs.pine`)

**Purpose:** Track the current leg direction and number at each TF. Detect leg transitions from strong CHoCH events.

**Inputs:** Conviction from Module 2 (STRONG events trigger leg transitions).

**State per TF:**
- `leg_direction` (UP/DOWN)
- `leg_number` (sequential since last parent swing)
- `building` (PARENT_HIGH/PARENT_LOW)
- `leg_high`, `leg_low` (extremes of current leg)
- `prev_leg_high`, `prev_leg_low` (for classification)

**On STRONG CHoCH:** Transition leg, confirm swing at current TF, classify (HH/HL/LH/LL), propagate to parent, start new leg, reset internal swings.

### Module 5: Momentum Consumption Tracker (`iora_consumption.pine`)

**Purpose:** After a parent-TF structural shift, track which child TFs have flipped and which still carry old-direction momentum.

**Inputs:** Bias state per TF (from Module 4 leg direction), conviction per TF (from Module 2), internal health per TF (from Module 2).

**Outputs:**
- Per-TF: bias direction, aligned with parent (yes/no), consumption % (0–100)
- Aggregate: total child TFs flipped (0/4), current consumption phase
- Next expected: which counter-leg must happen, at which TF

### Module 6: Direct M1 Momentum Layer (`iora_momentum.pine`)

**Purpose:** Run SMA crossovers of M1 close data as the fastest possible momentum-shift detection. Pre-alert layer for the structural cascade.

**Implementation:**
- `avg(5 M1 closes)`, `avg(15 M1 closes)`, `avg(60 M1 closes)`, `avg(240 M1 closes)`
- Short SMA crossing below long SMA → bearish momentum regime
- All short above all long → full bullish momentum alignment

**Use:** Alert layer only. Activates monitoring for structural cascade. Never trade on momentum alone.

### Module 7: Dashboard (`iora_dashboard.pine`)

**Purpose:** Unified table showing per-TF state: leg direction, conviction, internal health, consumption %, classification, next expected event.

**Format:**
```
┌─────┬───────┬──────────┬──────────┬──────────┬─────────────────┐
│ TF  │ Leg   │ Convict. │ Int.Hlth │ Consumed │ Building        │
├─────┼───────┼──────────┼──────────┼──────────┼─────────────────┤
│ D   │ ▼ #2  │ NONE     │ LH/LL ok │ PARENT   │ W Low           │
│ H4  │ ▲ #1  │ PRE ↓    │ DEGRAD   │ SOURCE   │ D High (LH?)    │
│ H1  │ ▼ #3  │ WEAK ↑   │ 1ST_CRK  │ 40%      │ H4 Low          │
│ M15 │ ▲ #2  │ STRONG ↑ │ HEALTHY  │ 100% ✓   │ H1 High         │
│ M5  │ ▲ #4  │ NONE     │ HEALTHY  │ 100% ✓   │ M15 High        │
│ M1  │ ▼ #1  │ NONE     │ —        │ 100% ✓   │ M5 Low          │
└─────┴───────┴──────────┴──────────┴──────────┴─────────────────┘
```

---

## PART 9 — HYBRID IMPLEMENTATION WITH `request.security`

### 9.1 The Shortcut from HTF Candles Indicator

The `HTF_Candles__M5_-_12MN_.pine` already demonstrates the pattern:

```pine
[m5o, m5h, m5l, m5c, m5t, m5tc] = request.security(
    syminfo.tickerid, "5", 
    [open, high, low, close, time, time_close], 
    lookahead=barmerge.lookahead_on
)
```

With `lookahead=barmerge.lookahead_on`:
- `m5h` = the current M5 candle's HIGH so far (updates every chart bar)
- `m5l` = the current M5 candle's LOW so far (updates every chart bar)
- `m5c` = the current M5 candle's CLOSE so far (= latest chart bar close)
- `ta.change(m5t) != 0` = detects when a new M5 period opens

**This gives us the building candle's live OHLC at every TF, every chart bar.** The entire `build_candle()` function from spec 04e is replaced by a single `request.security` call.

### 9.2 Envelope From Building Candles

```pine
// For M15 envelope (N=3 M5 candles):
// Store last 2 closed M5 candles + use live building M5

var float m5_closed_1_hi = na, var float m5_closed_1_lo = na, var float m5_closed_1_cl = na
var float m5_closed_2_hi = na, var float m5_closed_2_lo = na, var float m5_closed_2_cl = na

if ta.change(m5t) != 0   // new M5 period → previous M5 just closed
    m5_closed_2_hi := m5_closed_1_hi
    m5_closed_2_lo := m5_closed_1_lo
    m5_closed_2_cl := m5_closed_1_cl
    m5_closed_1_hi := m5h[1]    // previous bar's M5 high = the closed M5's high
    m5_closed_1_lo := m5l[1]
    m5_closed_1_cl := m5c[1]

// M15 envelope = avg of [closed_M5_2, closed_M5_1, building_M5]
float m15_env_ceil  = (nz(m5_closed_2_hi) + nz(m5_closed_1_hi) + m5h) / 3
float m15_env_floor = (nz(m5_closed_2_lo) + nz(m5_closed_1_lo) + m5l) / 3
float m15_env_mid   = (nz(m5_closed_2_cl) + nz(m5_closed_1_cl) + m5c) / 3
```

This updates every chart bar (M1 on an M1 chart) using structurally correct candle values (max/min, not averaged M1 data), with the live building candle included.

### 9.3 Same Pattern for All TFs

```pine
// H1 envelope: N=4 M15 candles (3 closed + 1 building)
// H4 envelope: N=4 H1 candles (3 closed + 1 building)
// D envelope:  N=6 H4 candles (5 closed + 1 building)
// W envelope:  N=5 D candles (4 closed + 1 building)
```

Each uses the same `request.security` + shift-on-period-change pattern.

---

## PART 10 — VALIDATION PROTOCOL

### 10.1 Bar Replay Checklist (per structural event)

Run on GBPUSD, EURUSD, XAUUSD — minimum 5 trading days per pair.

For each H4 leg transition:
- Record detection time at each layer (momentum, hybrid, period-level, zone)
- Note: mid-candle or candle-boundary event?
- Note: did momentum layer give false signal that hybrid filtered?
- Note: consumption state at each layer's signal time
- Note: conviction level (Strong/Weak/Pre) at each layer

### 10.2 Aggregate Metrics

- Average time advantage: Hybrid vs Cascading (per TF)
- False signal rate: momentum layer vs hybrid
- Conviction reliability: when STRONG fires, does parent swing confirm? (target >70%)
- Consumption prediction: does consumption depth predict parent classification? (target >65%)
- Internal health prediction: does DEGRADING predict STRONG within 3 candles? (target >60%)

---

## PART 11 — DOCUMENT INVENTORY

| Document | Content | Status |
|---|---|---|
| `04_period_level_structure_spec_v2.md` | Dynamic averages (Part A) + period-level breaks (Part B) + three-layer cascade | Complete |
| `04a_candle_type_price_source_analysis.md` | Line candle decision + three-source envelope + conviction scoring + Pine pseudocode | Complete |
| `04b_leg_architecture_spec.md` | Leg anatomy + nested structure + leg expectation model + entry timing | Complete |
| `04c_conviction_internal_external_spec.md` | Conviction as I/E classifier + internal health monitoring + close average as discriminator | Complete |
| `04d_momentum_consumption_spec.md` | Bias register + consumption sequence + counter-legs + consumption dashboard | Complete |
| `04e_computation_architecture_spec.md` | Cascade vs Direct M1 vs Hybrid comparison + hybrid implementation + testing protocol | Complete |
| `iora_bos_choch.pine` | Period high/low tracking + break detection (v1 — no classification) | Existing code |
| `HTF_Candles__M5_-_12MN_.pine` | Building candle visualisation with `request.security` + lookahead | Existing code — reuse pattern for hybrid |
| `03_internal_external_structure_spec_lines.md` | Zone-based internal/external structure (Layer 4 reference) | Existing spec |
| `02_early_confirmation_cascade.md` | CHoCH-to-structure propagation rules (original cascade concept) | Existing spec |

---

## PART 12 — BUILD ORDER

### Phase 1: Core Engine (Modules 1–2)

Build the hybrid envelope engine and conviction classifier first. These are the heart of the system — everything else reads from them.

**Deliverable:** A single Pine Script indicator that plots dynamic floor/mid/ceiling for M5/M15/H1/H4/D, marks conviction events (Strong/Weak/Pre) with shapes, and shows conviction on a dashboard table.

### Phase 2: Period-Level Enhancement (Module 3)

Extend `iora_bos_choch.pine` with the swing state machine, BOS/CHoCH classification, and parent propagation labels.

**Deliverable:** Enhanced `iora_bos_choch.pine` v2 with iBOS/iCHoCH/eBOS+/eCHoCH+ labels.

### Phase 3: Leg Tracking + Consumption (Modules 4–5)

Build the leg tracker and consumption monitor. These read from Modules 1–2 and provide the "what comes next" framework.

**Deliverable:** Dashboard table showing per-TF leg state, consumption %, and next expected event.

### Phase 4: Momentum Layer (Module 6)

Add the direct M1 SMA momentum layer as a pre-alert system.

**Deliverable:** Separate lightweight indicator with SMA crossover signals.

### Phase 5: Integration + Validation

Wire all modules together. Run bar replay validation on GBPUSD/EURUSD/XAUUSD. Measure timing advantages and false signal rates.

**Deliverable:** Complete validated system with performance metrics.
