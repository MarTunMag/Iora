# Iora Trading Methodology — Single Source of Truth

**System:** Iora
**Date:** March 2026
**Author:** Marius Tunestveit Magnusson
**Purpose:** Complete mechanical trading methodology. Every entry, exit, stop, and management rule. Updated as modules are built and validated.
**Companion doc:** `MASTER_SPEC_iora_structural_detection.md` (detection architecture)

---

## TABLE OF CONTENTS

1. [Foundation Principles](#part-1--foundation-principles)
2. [Zone Classification](#part-2--zone-classification)
3. [Structure Propagation](#part-3--structure-propagation)
4. [Zone Counting & the 5+3 Exhaustion Model](#part-4--zone-counting--the-53-exhaustion-model)
5. [Zone Nesting & Terminal Classification](#part-5--zone-nesting--terminal-classification)
6. [Trendline Breaks & Push Completion](#part-6--trendline-breaks--push-completion)
7. [Terminal Exhaustion](#part-7--terminal-exhaustion)
8. [Conviction Envelope & Classification](#part-8--conviction-envelope--classification)
9. [Momentum Consumption Cascade](#part-9--momentum-consumption-cascade)
10. [Macro Bias Determination](#part-10--macro-bias-determination)
11. [The 1-2-3 Cascade Pattern](#part-11--the-1-2-3-cascade-pattern)
12. [Boundary Zones](#part-12--boundary-zones)
13. [The D-Level Cycle (5 Phases)](#part-13--the-d-level-cycle-5-phases)
14. [Zone Tracking & Reversal Targets](#part-14--zone-tracking--reversal-targets)
15. [Entry Models](#part-15--entry-models)
16. [Position Management](#part-16--position-management)
17. [The Complete Trading Workflow](#part-17--the-complete-trading-workflow)
18. [Live Checklists](#part-18--live-checklists)

---

## PART 1 — FOUNDATION PRINCIPLES

### 1.1 System Philosophy

Iora is a **fully mechanical, rule-based** structural detection and trading system. There are no discretionary elements. Every decision — entry, exit, stop, add-on — follows from timeframe-agnostic rules that repeat at every fractal level.

### 1.2 Timeframe Cascade

The system operates across a fixed cascade of timeframes linked by natural parent-child ratios:

```
M1 → M5 (5:1) → M15 (3:1) → H1 (4:1) → H4 (4:1) → D (6:1) → W (5:1) → MN (4:1)
```

**Parent structure = child zone comparisons.** This is the foundational rule. You never wait for a parent TF candle to close — you read parent structure by comparing sequential child TF zones in real time.

### 1.3 Four Detection Layers

Detection fires progressively, from earliest to most confirmed:

| Layer | Source | What It Detects | Speed |
|---|---|---|---|
| 1. M1 Momentum | SMA crossovers | Regime shift (pre-alert) | Earliest |
| 2. Conviction Envelope | 3-source dynamic avg | STRONG/WEAK/PRE CHoCH | Early |
| 3. Period-Level Breaks | Previous-period H/L | BOS / CHoCH objective | Real-time |
| 4. Zone-Based Confirmation | HA colour-flip zones | Full structural context | Confirmed |

**Trade on Layer 2+3 confluence. Manage with Layer 4.**

### 1.4 Core Price Source

**Line candles (raw OHLC) only.** No Heikin Ashi, no Renko, no smoothing. All computed levels sit at real executable prices. HA highs virtually equal real highs, so the envelope produces identical results — but we use line candles to keep everything clean and execution-safe.

### 1.5 Parameter-Free Design

All structural parameters derive from natural TF ratios. No user-tunable lookback lengths, no optimisation targets. The only user controls are TF enable/disable toggles and visual styling.

---

## PART 2 — ZONE CLASSIFICATION

### 2.1 The Rule

When a new zone fires (Heikin-Ashi colour flip on the zone detection system), compare it to the **previous zone of the same type** on the **same timeframe**.

### 2.2 Supply Zones (Bearish Flip)

```
New supply top > previous supply top  →  HH  (structural — trend continues up)
New supply top ≤ previous supply top  →  LH  (corrective — uptrend weakening)
```

### 2.3 Demand Zones (Bullish Flip)

```
New demand bot < previous demand bot  →  LL  (structural — trend continues down)
New demand bot ≥ previous demand bot  →  HL  (corrective — downtrend weakening)
```

### 2.4 Break Signals

| Zone breaks | Classification | Meaning |
|---|---|---|
| HH or LL zone breaks | **BOS** (Break of Structure) | Trend confirmed — continuation |
| LH or HL zone breaks | **CHoCH** (Change of Character) | Reversal signal |

**CHoCH = early warning. BOS = confirmation.** Both are tradeable; CHoCH offers the faster entry.

### 2.5 Streak Tracking & Resets

```
HH fires → resets LH count to 0, resets LL count to 0
LL fires → resets HL count to 0, resets HH count to 0
LH fires → resets HH count to 0 only
HL fires → resets LL count to 0 only
```

---

## PART 3 — STRUCTURE PROPAGATION

### 3.1 The Rule

**Parent TF structure IS the child TF zone sequence.**

```
D structure  = H4 zone comparisons (H4 HH/LH/HL/LL)
H4 structure = H1 zone comparisons (H1 HH/LH/HL/LL)
H1 structure = M15 zone comparisons (M15 HH/LH/HL/LL)
M15 structure = M5 zone comparisons (M5 HH/LH/HL/LL)
M5 structure  = M1 zone comparisons (M1 HH/LH/HL/LL)
```

### 3.2 Early Detection Principle

You do not wait for a parent TF zone to visually appear. The child TF zone comparison **IS** the parent structure event — happening now, not later.

Example: When H1 makes an HL instead of an LL, that IS the H4 HL. You don't need to wait for the H4 candle to close.

### 3.3 Propagation Direction

- **Detection propagates bottom-up:** M1 → M5 → M15 → H1 → H4 → D → W
- **Context flows top-down:** W → D → H4 → H1 → M15 → M5 → M1

You read structure from below. You interpret it from above.

---

## PART 4 — ZONE COUNTING & EW-AWARE EXHAUSTION MODEL

### 4.1 The Rule

Count unbroken zones at each TF. The count tells you where the trend is in its lifecycle. **But the exhaustion threshold is NOT always 5.** It depends on the Elliott Wave pattern detected within the impulse.

### 4.2 The Standard Count (Baseline)

```
Zones 1-4   → Impulse active (trend has room to run)
Zone 5      → Impulse exhausted (trend slowing, prepare for correction)
Zone 6 (A)  → First counter-trend zone (correction starting)
Zone 7 (B)  → Retest zone ("perfect retest" possible)
Zone 8 (C)  → Terminal zone — inside opposing parent zone
              (WILL be broken → reversal enters HERE)
```

### 4.3 EW Pattern Detection — Dynamic Exhaustion Threshold

The "5" in "5+3" is the DEFAULT. The actual impulse exhaustion threshold shifts based on the detected EW pattern:

#### 4.3.1 Wave Pivot Tracking

Track five wave pivots from the zone sequence within each impulse:

```
Bullish impulse:
  W1_top = first HH zone top    W1_bot = impulse origin (demand bottom)
  W2_bot = first HL zone bottom  (pullback after W1)
  W3_top = second HH zone top   (must exceed W1_top)
  W4_bot = second HL zone bottom (pullback after W3)
  W5_top = third HH zone top    (final push)

W1_range = W1_top - W1_bot
W3_range = W3_top - W2_bot
```

#### 4.3.2 Pattern Detection & Threshold Adjustment

| EW Pattern | Detection Rule | Impulse Threshold | Correction Depth |
|---|---|---|---|
| **Standard Impulse** | Default (no special conditions) | **5 zones** | 3 zones (A-B-C) |
| **Extended W3** | W3_range > 1.618 × W1_range | **7-9 zones** (W3 creates 2-3 extra zones) | 3 zones |
| **Extended W3+W5** | Both W3 and W5 extended | **9-11 zones** | 3 zones |
| **Diagonal** | W4 overlaps W1 territory (W4_bot < W1_top for bullish) | **3-4 zones** (early exhaustion) | 3 zones |
| **Running Flat** (correction) | B wave exceeds correction origin, C falls short | Next impulse = **aggressive** (Mode B) | 2 zones |
| **Expanded Flat** (correction) | B wave exceeds impulse extreme | B = **TRAP** (do not re-enter) | 3 zones |
| **Triangle** (correction) | TL convergence > 30% + correction phase | Resolution = prior impulse dir | 5 zones (A-B-C-D-E) |

#### 4.3.3 How to Use the Adjusted Threshold

```
Standard (threshold = 5):
  Zone 4: with-trend          Zone 5: prepare correction
  Zone 6: correction A        Zone 7: correction B
  Zone 8: terminal C

Extended W3 (threshold = 8):
  Zone 5: STILL IMPULSE       Zone 6: STILL IMPULSE (W3 sub-wave)
  Zone 7: impulse slowing     Zone 8: prepare correction
  Zone 9: correction A        Zone 10: correction B
  Zone 11: terminal C

Diagonal (threshold = 3):
  Zone 3: prepare correction  Zone 4: correction A
  Zone 5: correction B        Zone 6: terminal C
```

**The key rule:** when the EW pattern shifts the threshold, ALL downstream logic (terminal exhaustion, opposing nesting, boundary zones) uses the ADJUSTED threshold, not the fixed 5.

#### 4.3.4 Conviction Envelope Integration

The conviction envelope provides early detection of the EW pattern:

| Conviction Signal | EW Pattern Hint | Action |
|---|---|---|
| STRONG at zone 3 + gradient accelerating | Extended W3 likely | Hold — impulse has room |
| DEGRADING health at zone 3 + floor/ceil converging | Diagonal likely | Prepare early exit |
| STRONG conviction on counter-trend zone inside correction | Expanded Flat B wave (trap) | Do NOT re-enter impulse direction |
| Running Flat detected + all child TFs aligned | Next impulse will be aggressive | Enter Mode B on first signal |

#### 4.3.5 Fibonacci Projections from Wave Pivots

```
Wave 2 depth:     W1_bot + W1_range × (0.382 | 0.500 | 0.618)
Wave 3 target:    W2_bot + W1_range × (1.000 | 1.618 | 2.618)
Wave 4 depth:     W3_top - W3_range × (0.236 | 0.382)
Wave 5 target:    W4_bot + W1_range × (0.618 | 1.000)
Wave C target:    cor_B + A_range × (1.000 | 1.618)
```

Wave 5 must achieve at least 38.2% projection of W1 range AND must complete after end of W3. Both conditions required.

### 4.4 Reset Events

The zone count resets when:
- A new parent TF zone fires
- A new structural extreme forms (HH or LL on the current TF)
- EW pattern reclassification (threshold changes → recount relative to new threshold)

### 4.5 Fractal Repetition

```
Standard:   5+3 child zones = 1 complete parent push
Extended:   8+3 child zones = 1 complete parent push (extended W3)
Diagonal:   3+3 child zones = 1 complete parent push (early exhaustion)
Triangle:   5+5 child zones = 1 complete parent correction (5 correction waves)
```

### 4.6 Trading Implications (EW-Aware)

| Zone Count vs Threshold | Posture | Action |
|---|---|---|
| < threshold - 1 | With-trend | Trade BOS continuations |
| threshold - 1 | Caution | Check for extension or diagonal pattern |
| threshold | Exhausted | If EXTENDED: hold, raise threshold. If DIAGONAL: exit early. Otherwise: tighten stops. |
| threshold + 1 (A) | Counter-trend building | Prepare reversal setups |
| threshold + 2 (B) | Retest zone | Watch for Expanded Flat trap |
| threshold + 3 (C) | Terminal | Reversal entry zone — highest conviction |

When **all levels simultaneously reach their respective thresholds** = highest conviction reversal signal in the system.

### 4.7 EW Guardrails

1. **EW is an enhancer, not a gate.** If pattern = UNKNOWN, use standard 5+3.
2. **Never override zone breaks because of wave count.** Broken is broken.
3. **Do not count sub-waves below M15.** M5/M1 are execution-only TFs.
4. **Patterns can reclassify mid-wave.** IMPULSE at W2 may become DIAGONAL when W4 data arrives. Always use latest classification.
5. **Wave 4 can never break the end of Wave 1** (standard impulse). If it does → DIAGONAL.
6. **Wave 2 can never break the start of Wave 1.** If it does → impulse invalidated.

---

## PART 5 — ZONE NESTING & TERMINAL CLASSIFICATION

### 5.1 The Nesting Check

A child zone is **nested** inside a parent zone when:

```
child.top ≤ parent.top  AND  child.bot ≥ parent.bot
```

### 5.2 Nesting Classification

| Child Zone | Parent Zone | Direction | Signal |
|---|---|---|---|
| H1 supply | H4 supply | Same (both bearish) | Continuation — trend intact |
| H1 demand | H4 demand | Same (both bullish) | Continuation — trend intact |
| H1 supply | H4 demand | **Opposing** | **TERMINAL — H1 supply WILL break** |
| H1 demand | H4 supply | **Opposing** | **TERMINAL — H1 demand WILL break** |
| M5 @ M15 @ H1 | Triple nest, same dir | Same | **Highest conviction entry** |

### 5.3 The Opposing Nesting Rule

**This is the most important nesting rule:**

```
Child zone OPPOSING the parent zone it sits inside → child zone WILL be broken
```

The parent zone represents the larger force. The child zone going the other way is a correction that cannot hold. The parent absorbs the pressure and breaks it mechanically.

### 5.4 Trading Implication

Opposing nesting = **mechanical reversal signal**. When you see H1 zone #8 nested inside an opposing H4 zone, the H1 zone must break. Enter on the break setup.

---

## PART 6 — TRENDLINE BREAKS & PUSH COMPLETION

### 6.1 How Trendlines Are Built

- **Bearish TL:** Connects consecutive LH supply zone tops (descending resistance)
- **Bullish TL:** Connects consecutive HL demand zone bottoms (ascending support)

### 6.2 What Each Break Confirms

| TL that breaks | Confirms |
|---|---|
| M5 TL break | M15 sub-wave complete |
| M15 TL break | **H1 push complete** |
| H1 TL break | **H4 push complete** |
| H4 TL break | **D leg complete** |

### 6.3 Impulse vs Correction Trendlines

| TL Type | Connects | Break Means |
|---|---|---|
| **Impulse** (solid) | HH tops or LL bottoms | Potential reversal — trend push broke |
| **Correction** (dashed) | LH tops or HL bottoms | Trend resumes — pullback failed |

### 6.4 The M15 TL Break = Entry Gate

Most entries require an M15 TL break as prerequisite. It confirms the H1 sub-wave is complete, meaning the structural rotation is real, not just a wick.

---

## PART 7 — TERMINAL EXHAUSTION

### 7.1 The Rule

**H4 counter-zone beyond broken D level = terminal exhaustion = highest-level mechanical reversal signal.**

### 7.2 Bearish Terminal (Expect Bullish Reversal)

All four conditions must be true:

```
[x] D LL broken (daily structure bearish)
[x] H4 demand formed BELOW broken D LL
[x] 5+ unbroken H1 supply zones overhead
[x] H1 wave count shows 5+3 pattern
→ Terminal exhaustion confirmed
```

### 7.3 Bullish Terminal (Expect Bearish Reversal)

```
[x] D HH broken (daily structure bullish)
[x] H4 supply formed ABOVE broken D HH
[x] 5+ unbroken H1 demand zones below
[x] H1 wave count shows 5+3 pattern
→ Terminal exhaustion confirmed
```

### 7.4 H4 Zone Confirmation Cycle

The H4 counter-zone is NOT live immediately. It must complete the break-retest cycle:

```
1. H1 demand created at bottom (inside H4 demand)
2. Price pushes up → creates H1 supply #8
3. Price pushes back down → breaks that H1 demand
4. Pushdown reaches M15/M5 demand at the lowest point
→ H4 demand is now CONFIRMED LIVE
```

### 7.5 Early Detection Sequence

```
H1 zone count reaches 5      → first warning
H1 zone #6 forms (corr A)    → reversal starting
H1 zone #8 inside H4 zone    → confirmed terminal
M15 CHoCH inside H1 #8       → earliest entry opportunity
M1 CHoCH inside M5 @ terminal → execution trigger
```

---

## PART 8 — CONVICTION ENVELOPE & CLASSIFICATION

### 8.1 The Three-Source Envelope

For each parent TF, compute a rolling average of child-TF candle data over the natural period ratio:

```
dynamic_floor  = avg(child lows)    → structural floor
dynamic_mid    = avg(child closes)  → directional commitment
dynamic_ceil   = avg(child highs)   → structural ceiling
```

Window sizes (natural ratios): M5=5, M15=3, H1=4, H4=4, D=6, W=5, MN=4.

### 8.2 Conviction Classification

| Level | Condition | Meaning | Action |
|---|---|---|---|
| **STRONG** | Floor/ceil break + mid confirms + opposing source confirms | External event — leg transition | Propagate to parent TF. Trade it. |
| **WEAK** | Floor or ceil breaks but mid does NOT confirm | Internal event — sub-wave pullback | Don't chase. Wait for STRONG. |
| **PRE** | Mid stalling, floor/ceil intact | Momentum fading — prepare | Get ready. STRONG is approaching. |

### 8.3 The Discriminator

**The mid (avg closes) is always the discriminator.** Highs and lows can wick through levels — that's noise. When closes confirm, that's commitment. That's when you act.

### 8.4 Gradient Score (-6 to +6)

Per-source acceleration scoring:
```
+2 = accelerating (delta increasing in trend direction)
+1 = steady (delta positive, not increasing)
-1 = decelerating (delta shrinking)
-2 = reversing (delta flipped against trend)
```

Sum across floor + mid + ceil = gradient score (-6 to +6). Score swinging from -6 to +6 (or vice versa) = full reversal across all sources = maximum conviction.

### 8.5 Internal Health Monitoring

Track the sequence of WEAK CHoCH events within each leg:

```
HEALTHY       → No counter-trend weak events (0 counter-trend swings)
FIRST_CRACK   → First counter-trend weak swing (1 counter-trend swing)
DEGRADING     → Multiple counter-trend swings (2 counter-trend swings)
BROKEN        → Health exhausted (3+ counter-trend swings)
              → Predicts STRONG event 1-3 child candles ahead
```

With-trend WEAK events decrement the counter. Health degrades monotonically toward BROKEN, then the STRONG event fires.

---

## PART 9 — MOMENTUM CONSUMPTION CASCADE

### 9.1 The Concept

After a parent-TF structural shift (e.g., H4 CHoCH bearish), each child TF carries **residual momentum in the old direction**. These old-direction biases are consumed one by one, from fastest to slowest, through strong CHoCH flips.

### 9.2 The Bias Register

Every TF has a directional state:

```
TF_Bias:
    direction:    BULL | BEAR | NEUTRAL
    conviction:   STRONG | WEAK | PRE | NONE
    swing_count:  int (swings in current direction)
```

### 9.3 The Consumption Sequence (After H4 CHoCH Bearish)

```
AT H4 FLIP:
┌─────┬──────┬──────────┬─────────────┐
│ TF  │ Bias │ Aligned? │ Consumption │
├─────┼──────┼──────────┼─────────────┤
│ H4  │ BEAR │ —        │ JUST FLIPPED│
│ H1  │ BULL │ MISALIGN │ 0%          │
│ M15 │ BULL │ MISALIGN │ 0%          │
│ M5  │ BULL │ MISALIGN │ 0%          │
│ M1  │ BULL │ MISALIGN │ 0%          │
└─────┴──────┴──────────┴─────────────┘

PHASE 1: M1 flips → consumption 1/4
  M1 strong CHoCH bearish fires
  M1 bearish candles begin feeding M5 envelope bearish data
  M5 internal health: FIRST_CRACK

PHASE 2: M5 flips → consumption 2/4
  M5 strong CHoCH bearish fires
  M5 LH created, starts building M15 bearish structure
  M15 internal health: starting to crack

PHASE 3: M15 flips → consumption 3/4
  M15 strong CHoCH bearish fires
  M15 LH created, starts building H1 bearish structure
  H1 internal health: DEGRADING

PHASE 4: H1 flips → consumption 4/4 (FULL ALIGNMENT)
  H1 strong CHoCH bearish fires
  ALL child TFs aligned with H4 bearish
  → IMPULSIVE PHASE begins (maximum momentum)
```

### 9.4 Counter-Legs Are Mandatory, Not Reversals

**Critical understanding:** After each TF flips, it MUST produce a counter-leg (push in old direction) to create the LH/HL that the next TF up needs to confirm structure.

```
M5 flips bearish → M5 must pull back UP (creates M15 LH)
M15 flips bearish → M15 must pull back UP (creates H1 LH)
```

These counter-legs **look like reversals** but are structural necessity. They are where you **add to positions**, not where you exit.

### 9.5 Consumption Depth = Parent Classification

| Depth | TFs Flipped | Parent Move |
|---|---|---|
| Shallow (1-2/4) | M1, M5 | Parent pullback (HL or LH) |
| Medium (3/4) | M1, M5, M15 | Parent HL/LH confirmed |
| Deep (4/4) | All | Parent leg transition (HH/LL) |
| Overflow | All + exceeds parent | Grandparent event (D LH/HL from H4 move) |

### 9.6 Consumption Scoring Per TF

```
Old bias dominant, no signals:          0% consumed
PRE-CHoCH firing:                       25% consumed
Internal health FIRST_CRACK:            40% consumed
Internal health DEGRADING:              60% consumed
WEAK CHoCH against old direction:       75% consumed
Internal health BROKEN:                 85% consumed
STRONG CHoCH fires → bias FLIPS:        100% consumed
```

---

## PART 10 — MACRO BIAS DETERMINATION

### 10.1 The Rule

**M5 TL break + price at parent zone = macro bias confirmed.**

### 10.2 Bearish Confirmation (Flip to SHORT)

All must be true:
```
[x] M5 bullish TL broken (ascending support failed)
[x] (Optional: M1 bullish TL also broken)
[x] Price inside H4 supply OR D supply zone
[x] Terminal exhaustion (bullish) is NOT active
→ macro_bias = BEARISH (-1)
```

### 10.3 Bullish Confirmation (Flip to LONG)

All must be true:
```
[x] M5 bearish TL broken (descending resistance failed)
[x] (Optional: M1 bearish TL also broken)
[x] Price inside H4 demand OR D demand zone
[x] Terminal exhaustion (bearish) is NOT active
→ macro_bias = BULLISH (+1)
```

### 10.4 The Terminal Gate

```
Don't flip BULLISH when terminal_exhaustion_bear is active
  → H4 demand below D LL = bounces here are temporary traps

Don't flip BEARISH when terminal_exhaustion_bull is active
  → H4 supply above D HH = dips here are temporary traps
```

### 10.5 Bias Persistence

Once set, macro bias persists until the **opposite** confirmation fires. No timeout, no decay.

### 10.6 Limit Orders on Bias Confirmation

```
Bear confirmed → SHORT LIMIT at broken M5 demand top
                  SL: M1 supply top + spread buffer

Bull confirmed → LONG LIMIT at broken M5 supply bottom
                  SL: M1 demand bottom - spread buffer
```

---

## PART 11 — THE 1-2-3 CASCADE PATTERN

### 11.1 The Pattern

Three zones compressing = push ending. The pattern cascades through TFs, each level arming the next.

### 11.2 Bearish 1-2-3 (Rally Failing)

```
Zone 1: Demand (HL)  — pullback support
Zone 2: Supply (HH)  — rally high
Zone 3: Demand (HL)  — second pullback

Signal: Zone 3 demand top < Zone 2 supply bottom
→ Rally can't reach the last high → push is compressing → failing
```

### 11.3 Bullish 1-2-3 (Push Down Failing)

```
Zone 1: Supply (LH)  — pullback resistance
Zone 2: Demand (LL)  — push low
Zone 3: Supply (LH)  — second pullback

Signal: Zone 3 supply bottom > Zone 2 demand top
→ Push can't reach the last low → push is compressing → failing
```

### 11.4 The Cascade (Each Level Arms the Next)

```
D 1-2-3 fires (always active)
  → arms H4
    H4 1-2-3 fires (only inside D zone)
      → arms H1
        H1 1-2-3 fires (only inside H4 zone)
          → arms M15
            M15 1-2-3 fires (only inside H1 zone)
              → arms M5
                M5 1-2-3 fires (only inside M15 zone)
                  → ENTRY TRIGGER ARMED
```

### 11.5 Containment Rule

Each child 1-2-3 can only fire when price (close) is **inside** an active unbroken parent zone.

### 11.6 M1 CHoCH Add-On Entries

```
m5_cascade_bear_ready = true
  → Wait for M1 LL (proves push started)
    → Then M1 LH (CHoCH) = SHORT add-on entry
    → Entry: last M1 supply bottom
    → SL: last M1 supply top + spread

m5_cascade_bull_ready = true
  → Wait for M1 HH (proves push started)
    → Then M1 HL (CHoCH) = LONG add-on entry
    → Entry: last M1 demand top
    → SL: last M1 demand bottom - spread
```

---

## PART 12 — BOUNDARY ZONES

### 12.1 Definition

A boundary zone is the **structural decision box** — the range from the last unbroken zone edge to the structural extreme.

### 12.2 When Created

```
On H1 LL:  Boundary from H1 supply top (last unbroken) → down to H1 LL low
On H1 HH:  Boundary from H1 HH high → down to H1 demand bottom (last unbroken)
```

### 12.3 The Decision

```
Bearish boundary (supply top → LL low):
  Close ABOVE supply top  → boundary BROKEN → bearish invalidated
                          → H4 HH confirmed → reversal underway
  Price stays below       → boundary HOLDS → bearish trend intact

Bullish boundary (HH high → demand bottom):
  Close BELOW demand bottom → boundary BROKEN → bullish invalidated
                            → H4 LL confirmed → reversal underway
  Price stays above         → boundary HOLDS → bullish trend intact
```

### 12.4 Early Entry Before Boundary Break

```
H1 zones forming (building reversal structure)
  → M15 zones inside those H1 zones (refining direction)
    → M5 CHoCH inside M15 = boundary break is coming
      → M1 CHoCH = enter BEFORE the boundary visually breaks
```

### 12.5 Connection to H4 Zone Creation

After boundary break:
```
Terminal bottom:
  H4 demand confirmed below
  → Price pushes up into boundary zone
  → Boundary breaks → H4 HH → D LH
  → New H4 supply forms inside/near boundary zone
  → This H4 supply = reversal resistance = Phase D push origin
```

---

## PART 13 — THE D-LEVEL CYCLE (5 PHASES)

### 13.1 Overview

The complete cycle from terminal bottom to next D LL (bearish example — mirror for bullish).

### 13.2 Phase A — H4 Demand Confirmation

**What happens:**
- H1 demand created at bottom (inside H4 demand)
- Push up → H1 supply #8 created
- Push back down → breaks that H1 demand
- Pushdown reaches M15/M5 demand at lowest H1 demand bottom
- H4 demand confirmed as LIVE

**Mechanical entry:**
```
M15 demand @ H4 demand (nesting confirmed)
→ M1 CHoCH (HL) inside M5 @ this M15 demand
→ LONG ENTRY
SL: Below M15 demand bottom
TP: H1 supply that will create H4 CHoCH (mark as reversal target)
```

### 13.3 Phase B — Reversal Into Boundary

**What happens:**
- Price pushes up from confirmed H4 demand
- Into the reversal zone (H1 boundary zone from Phase A)
- H1 demand zones form (HL sequence = bullish)

**What to monitor:**
- H1: New demand zones forming (HL = bullish continuation)
- Boundary zone: Price approaching / entering
- M15: Demand zones inside H1 demand = continuation add-on entries

### 13.4 Phase C — H4 Supply at Reversal Zone

**What happens:**
- At the boundary zone, price reverses
- Creates new H4 supply inside/near boundary
- Confirms D LH (H4 supply top < prev D supply top)

**Mechanical entry:**
```
H1 supply @ boundary zone (last H1 supply before H4 HH)
→ M15 supply inside H1 supply
→ M1 CHoCH (LH) inside M5 supply at this level
→ SHORT ENTRY
SL: Above H4 supply top
TP: Previous H4 demand (or D LL target)
```

### 13.5 Phase D — Aggressive D LL Push

**What happens:**
- D LH confirmed → aggressive push down begins
- H1 supply zones break fast — no stair-step retests
- **Mode B continuation trading**: entries shift to M5/M15 supply zones directly

**Entries:**
```
M5/M15 supply zones during aggressive push = continuation shorts
No waiting for H1 retest — zones break too fast in Phase D
```

### 13.6 Phase E — New D LL

- M5/M15 → H1 supply chain pushes price to new D LL
- **Cycle restarts at Phase A**

### 13.7 Phase Identification

```
Terminal exhaustion active + H4 demand confirming     → Phase A
Price pushing up from H4 demand toward boundary       → Phase B
H4 supply forming at boundary / D LH confirming       → Phase C
D LH confirmed + aggressive push down                 → Phase D
New D LL printing                                      → Phase E → back to A
```

---

## PART 14 — ZONE TRACKING & REVERSAL TARGETS

### 14.1 The Rule

**Always track the last created zone at each level, on each side.** The zone that caused the CHoCH becomes the reversal target for the level above.

### 14.2 The CHoCH Zone = Reversal Target

```
H4 pushing down (making LLs)
  → H1 supply zones created as price descends
  → H1 makes an HL instead of LL
    → This H1 HL = H4 HL (CHoCH at H4 level)
    → The LAST H1 SUPPLY before this HL = reversal target
    → Longs exit here. Shorts enter here.
```

### 14.3 The Complete Tracking Cycle

```
STEP 1: IDENTIFY TERMINAL
  D LL broken + H4 demand below + H1 5+3
  → Terminal confirmed

STEP 2: ENTER LONG
  M15 demand @ H4 demand + M1 CHoCH (HL)
  → LONG ENTRY

STEP 3: MARK REVERSAL TARGET
  H1 supply that created H4 HL break
  → This is where you EXIT LONGS

STEP 4: RIDE TO TARGET
  Price pushes up through H1 zones
  → H4 HL → H4 HH (but below last H4 supply = D LH)
  → Approaching the marked H1 supply

STEP 5: EXIT LONGS AT D LH ZONE
  Price enters the marked H1 supply
  → EXIT LONGS (take profit)

STEP 6: ENTER SHORT
  Same zone: H1 supply = D LH reversal zone
  → M1 CHoCH (LH) inside M5 supply
  → SHORT ENTRY

STEP 7: RIDE D PUSH DOWN
  D LH confirmed → aggressive Phase D push
  → Mode B continuation shorts from M5/M15 supply

STEP 8: CHECK WEEKLY CONTEXT
  At new D LL: is this inside W demand?
  → YES = W HL → prepare for W-level reversal
  → NO = W continuation → ride further
```

---

## PART 15 — ENTRY MODELS

### 15.1 Model A — Terminal Reversal (Highest Conviction)

**When:** Terminal exhaustion confirmed (all 4 conditions from Part 7)

```
Setup:
  [x] D level broken
  [x] H4 counter-zone beyond D level
  [x] H1 zone count 5+3
  [x] Opposing nesting confirmed
  [x] Momentum consumption ≥ 2/4

Entry:
  M15 demand @ H4 demand (nesting)
  → M15 TL break confirms H1 push complete
  → M5 1-2-3 cascade armed
  → M1 CHoCH (HL) = EXECUTE

  Entry price: M5 demand low (or M1 CHoCH level)
  Stop loss: Below M1 supply bottom (tight) or M15 demand bottom (standard)
  Take profit: H1 supply (reversal target from Part 14)
```

### 15.2 Model B — Mode B Continuation (Phase D Aggressive)

**When:** D LH/HL confirmed, aggressive push underway

```
Setup:
  [x] D LH/HL confirmed (Phase D active)
  [x] H1 zones breaking without retests
  [x] All child TFs aligned (consumption 4/4)

Entry:
  M5/M15 supply zones during aggressive push
  No H1 retest needed — zones break too fast

  Entry price: M5/M15 zone edge
  Stop loss: Above/below the M5/M15 zone
  Take profit: Next major D level or H4 zone
```

### 15.3 Model C — 1-2-3 Cascade Add-On

**When:** M5 cascade armed, inside M15 zone

```
Setup:
  [x] D 1-2-3 → H4 1-2-3 → H1 1-2-3 → M15 1-2-3 → M5 1-2-3 cascade
  [x] Each level armed only inside parent zone

Entry:
  M1 CHoCH inside M5 at cascade point
  → SHORT: M1 LH after M1 LL inside M5 supply
  → LONG: M1 HL after M1 HH inside M5 demand

  Entry price: M1 zone edge
  Stop loss: M1 zone opposite edge + spread
  Take profit: Next TF zone or structural level
```

### 15.4 Model D — Macro Bias Limit Order

**When:** Macro bias flips (M5 TL break at parent zone)

```
Setup:
  [x] M5 TL break
  [x] Price inside H4/D zone
  [x] Terminal gate clear

Entry:
  BEAR → SHORT LIMIT at broken M5 demand top
  BULL → LONG LIMIT at broken M5 supply bottom

  Stop loss: M1 zone edge + spread
  Take profit: Next structural level
```

### 15.5 Entry Timing by Consumption Depth

| Timing | Consumption | Entry Point | Risk | Reward |
|---|---|---|---|---|
| **Early** (aggressive) | 2/4 flipped | M5 counter-leg top | Higher | Full consumption ride |
| **Standard** (balanced) | 3/4 flipped | M15 counter-leg top | Moderate | H1 flip + impulse |
| **Confirmation** (conservative) | 4/4 flipped | H1 counter-leg top (first LH) | Lower | Impulse phase only |

---

## PART 16 — POSITION MANAGEMENT

### 16.1 Stop Loss Rules

```
Terminal reversal (Model A):
  Tight:    Below M1 supply bottom (closest structure)
  Standard: Below M15 demand bottom (zone-based)
  Wide:     Below H4 demand bottom (structural — only for swing)

Continuation (Model B):
  Below/above the M5/M15 zone used for entry

Add-on (Model C):
  M1 zone opposite edge + spread buffer
```

### 16.2 Take Profit Targets

```
Primary target: The H1 supply/demand marked as reversal target (Part 14)
Secondary: Next H4 zone
Final: D level (for swing positions)
```

### 16.3 Add-On Rules

- Add to winners on M1 CHoCH inside M5 at M15 demand/supply retests
- Each add-on uses its own stop (M1 zone edge)
- Never add after zone count > 5 on entry TF

### 16.4 Exit Rules

```
Exit all at reversal target (H1 supply/demand)
Exit partial at H4 zone intermediate levels
Trailing stop: move to breakeven after H1 zone forms in profit direction
```

---

## PART 17 — THE COMPLETE TRADING WORKFLOW

### 17.1 Step 1 — Market Structure Assessment (Top-Down)

```
1. Check W structure (HH/HL/LH/LL)
2. Check D structure (built from H4 zones)
3. Check H4 structure (built from H1 zones)
4. Check H1 structure (built from M15 zones)
5. Identify macro bias (M5 TL break + parent zone)
```

### 17.2 Step 2 — Zone Counting & Exhaustion

```
1. Count unbroken zones at H1 (1-8)
2. Zone 5 = impulse done → prepare for correction
3. Zone 8 = terminal → reversal entering
4. Check opposing nesting (H1 inside opposing H4 = mechanical reversal)
```

### 17.3 Step 3 — Terminal Exhaustion Checklist

```
[x] D level broken? (HH/HL/LH/LL)
[x] H4 counter-zone formed beyond broken D level?
[x] 5+ H1 zones unbroken?
[x] H1 wave count at 5+3?
→ All four = terminal confirmed
```

### 17.4 Step 4 — Momentum Consumption Status

```
1. Which TFs have flipped? (M1/M5/M15/H1)
2. Which TF is currently consuming (cracking)?
3. What counter-leg must happen next?
4. Entry timing: shallow (2/4) vs standard (3/4) vs confirmation (4/4)
```

### 17.5 Step 5 — Reversal Target Identification

```
1. Mark H1 supply/demand that created H4 CHoCH
2. This becomes D LH/HL reversal zone
3. Longs exit here, shorts enter here (or vice versa)
```

### 17.6 Step 6 — Entry Signal Confirmation

```
[x] M15 demand/supply @ H4 zone (nesting check)
[x] M15 TL break (push completion confirmed)
[x] M5 CHoCH inside M15 (compression signal)
[x] M1 CHoCH inside M5 (execution trigger)
[x] 1-2-3 cascade armed at M5 level
→ EXECUTE
```

### 17.7 Step 7 — Position Management

```
Entry: M5 demand/supply + M1 CHoCH
Stop: M1 zone edge + spread
Target: Marked H1 supply/demand (reversal target)
Add-ons: M1 CHoCH at M15 retests
Exit: At reversal target → flip direction
```

---

## PART 18 — LIVE CHECKLISTS

### 18.1 Before You Trade

```
[ ] Identify which D zone (HH/HL/LH/LL) is active
[ ] Count H1 zones: 1-4 (impulse), 5 (exhausted), or 6-8 (terminal)?
[ ] Check H4 nesting: H1 inside H4 opposing direction?
[ ] What's the macro bias? (M5 TL break + parent zone)
[ ] Is terminal exhaustion active? (all four conditions)
[ ] Which phase of the D-level cycle? (A/B/C/D/E)
```

### 18.2 During the Setup

```
[ ] What TFs have flipped? (consumption 0/4 through 4/4)
[ ] What counter-leg is forming? (push in old direction = liquidity sweep, NOT reversal)
[ ] Mark the reversal target (H1 zone that caused H4 CHoCH)
[ ] Is 1-2-3 cascade arming? (D → H4 → H1 → M15 → M5)
```

### 18.3 At Entry

```
[ ] M15 demand/supply inside H4 zone (nesting confirmed)
[ ] M15 TL break fired (H1 push complete)
[ ] M5 1-2-3 cascade armed (three zones compressing)
[ ] M1 CHoCH inside M5 zone (execution confirmed)
[ ] Entry placed at M5 zone edge
[ ] Stop placed at M1 zone edge + spread buffer
```

### 18.4 At Exit / Flip

```
[ ] Price reaching marked H1 supply/demand (reversal target)
[ ] H4 HH/HL or LH/LL formed (structure shift confirmed)
[ ] Close longs/shorts at reversal target
[ ] Enter opposite direction via M1 CHoCH add-on (Model C)
[ ] For Phase D continuation: M5/M15 zones (Mode B entries)
```

### 18.5 Weekly Context Check

```
At new D extreme:
[ ] Is this inside W demand/supply from last W push?
  → YES = W HL/LH → prepare for W-level reversal
  → NO = W continuation → ride further
```

---

## APPENDIX A — TIMEFRAME RATIO REFERENCE

```
Parent → Child   Ratio   Envelope Window (N-1 closed + 1 building)
M5     → M1      5:1     avg(4 closed M1 + building M1)
M15    → M5      3:1     avg(2 closed M5 + building M5)
H1     → M15     4:1     avg(3 closed M15 + building M15)
H4     → H1      4:1     avg(3 closed H1 + building H1)
D      → H4      6:1     avg(5 closed H4 + building H4)
W      → D       5:1     avg(4 closed D + building D)
MN     → W       4:1     avg(3 closed W + building W)
```

## APPENDIX B — CONVICTION ASSESSMENT LOGIC

```
assess_conviction(floor_break, ceil_break, mid_against, mid_stall, floor_delta, ceil_delta, leg_dir):

  IF leg UP (check bearish events):
    floor_break AND mid_against AND ceil_delta ≤ 0  → STRONG, direction = -1
    floor_break (alone)                              → WEAK, direction = -1
    mid_stall AND ceil_delta ≤ 0                     → PRE, direction = -1

  IF leg DOWN (check bullish events):
    ceil_break AND mid_against AND floor_delta ≥ 0   → STRONG, direction = +1
    ceil_break (alone)                               → WEAK, direction = +1
    mid_stall AND floor_delta ≥ 0                    → PRE, direction = +1
```

## APPENDIX C — INTERNAL HEALTH STATE MACHINE

```
On WEAK CHoCH event:
  IF counter-trend: health = min(health + 1, 3)
    0 = HEALTHY → 1 = FIRST_CRACK → 2 = DEGRADING → 3 = BROKEN
  IF with-trend: health = max(health - 1, 0)

BROKEN (health = 3) → predicts STRONG event within 1-3 child candles
```

---

*This document is the single source of truth for the Iora trading methodology. Update as modules are built, validated, and refined through live testing.*
