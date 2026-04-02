# Momentum Consumption & Bias Flip Cascade — Iora Specification

**System:** Iora  
**Date:** March 2026  
**Depends on:** `04c_conviction_internal_external_spec.md` (conviction-based I/E), `04b_leg_architecture_spec.md` (leg cascade), `04_period_level_structure_spec_v2.md` (dynamic averages + period levels)  
**Purpose:** Track how each TF's existing momentum (its current high/low bias) gets consumed and flipped after a parent-TF structural shift — creating a real-time checklist of which TFs have flipped, which still carry old-direction momentum, and what breaks are needed at each level to build the required legs for the new parent-TF swing.

---

## 1. The Core Concept — Momentum as Inventory

### 1.1 What "Momentum" Means at Each TF

Every TF at any moment has a **directional inventory** — its existing highs and lows that represent the current bias:

```
AFTER H4 HAS BEEN IN AN UP-LEG (building Daily high):

Each TF below H4 has accumulated BULLISH INVENTORY:
  H1:  series of HH/HL → each H1 high is a bullish data point
  M15: series of HH/HL → each M15 high is bullish momentum
  M5:  series of HH/HL → each M5 high is micro-bullish momentum
  M1:  series of HH/HL → raw bullish momentum

This inventory = "the highs that were created during the up-leg"
These highs are simultaneously:
  → Structural levels (resistance on the way back down)
  → Liquidity pools (stops sitting below each high's corresponding HL)
  → Momentum that must be CONSUMED before the new direction fully takes hold
```

### 1.2 What "Eating Up" Means

When the H4 leg transitions (strong CHoCH fires, H4 starts down-leg), the market doesn't instantly become bearish at every TF. Each TF still carries its bullish inventory. The new bearish direction must **eat through** each TF's bullish bias, one by one, from the fastest TF upward:

```
H4 STRONG CHoCH bearish fires (H4 UP-LEG → DOWN-LEG):
  → H4 is now bearish
  → But at this exact moment:
    H1:  may still be in UP-LEG (last H1 candle was bullish)
    M15: may still be in UP-LEG  
    M5:  may still be in UP-LEG
    M1:  may still be in UP-LEG
    
  THESE BULLISH BIASES MUST BE CONSUMED:
    First:  M1 must flip bearish (M1 strong CHoCH bearish)
    Then:   M5 must flip bearish (fed by M1 bearish candles)
    Then:   M15 must flip bearish (fed by M5 bearish legs)
    Then:   H1 must flip bearish (fed by M15 bearish legs)
    
  EACH FLIP = one TF's bullish momentum consumed
  WHEN ALL HAVE FLIPPED: the H4 down-leg is fully established
```

### 1.3 Why This Matters for Trading

The momentum consumption sequence tells you:

- **Where you are in the transition:** "M1 and M5 have flipped bearish, but M15 is still bullish" → the transition is halfway through. M15 must flip before the H1 bearish leg can build.
- **What to expect next:** "M15 still bullish means we need to see M15 make an LH, then an LL, to flip M15. That LH is the pullback you can short from."
- **When the new leg is fully loaded:** "All TFs from M1 through H1 are now bearish-biased → the H4 down-leg is fully committed → this IS the Daily's down push."
- **Where the counter-moves come from:** "M5 just flipped bullish while M15/H1 are bearish → this is a pullback within the bearish structure, not a reversal. The M5 bullish momentum will be consumed by M15's bearish bias."

---

## 2. The Bias Register — Per-TF Directional State

### 2.1 The Bias Register Structure

For each TF, maintain a bias state that captures the current directional inventory:

```
TF_Bias:
    tf:                string     (e.g., "M15")
    direction:         BULL | BEAR | NEUTRAL
    conviction:        STRONG | WEAK | PRE | NONE
    
    # The "inventory" — existing highs/lows that carry the current bias
    last_swing_high:   float      (highest confirmed swing high in current bias)
    last_swing_low:    float      (lowest confirmed swing low in current bias)
    swing_count:       int        (how many swings have been made in current direction)
    
    # Flip tracking
    flipped_from:      BULL | BEAR | NONE   (what direction it flipped FROM)
    flip_bar:          int        (bar index where the flip occurred)
    flip_conviction:   STRONG | WEAK        (conviction of the flip event)
    
    # Parent alignment
    aligned_with_parent: bool     (is this TF's bias the same as its parent's?)
    parent_bias:       BULL | BEAR
```

### 2.2 Bias Flip Events

A TF's bias flips when a **strong CHoCH** fires at that TF (from the conviction system in 04c):

```
BIAS FLIP RULES:

1. STRONG CHoCH bearish at TF X:
   → TF X direction changes: BULL → BEAR
   → TF X flipped_from = BULL
   → TF X swing_count resets to 0
   → All accumulated bullish swings become "consumed inventory"
   → Parent alignment rechecked

2. STRONG CHoCH bullish at TF X:
   → TF X direction changes: BEAR → BULL
   → TF X flipped_from = BEAR
   → TF X swing_count resets to 0
   → All accumulated bearish swings become "consumed inventory"

3. WEAK CHoCH at TF X:
   → NO BIAS FLIP (this is internal — the bias holds)
   → But: marks internal swing within the current bias
   → Internal swing counter increments
   → If internal swings start degrading (from 04c internal health):
     → Bias is WEAKENING but not yet flipped
```

---

## 3. The Consumption Sequence — After a Parent-TF Shift

### 3.1 The Full Sequence After H4 CHoCH Bearish

```
═══════════════════════════════════════════════════════════════════
TRIGGER: H4 STRONG CHoCH BEARISH (H4 up-leg → down-leg)
         H4 bias flips: BULL → BEAR
         Daily high candidate set at H4 leg_high
═══════════════════════════════════════════════════════════════════

BIAS REGISTER AT THE MOMENT OF H4 FLIP:

┌─────┬──────┬────────────┬─────────────────────────────────────┐
│ TF  │ Bias │ Aligned?   │ Status                              │
├─────┼──────┼────────────┼─────────────────────────────────────┤
│ H4  │ BEAR │ —          │ JUST FLIPPED. Down-leg starting.    │
│ H1  │ BULL │ ✗ MISALIGN │ Still carrying bullish momentum.    │
│ M15 │ BULL │ ✗ MISALIGN │ Still carrying bullish momentum.    │
│ M5  │ BULL │ ✗ MISALIGN │ Still carrying bullish momentum.    │
│ M1  │ BULL │ ✗ MISALIGN │ Still carrying bullish momentum.    │
└─────┴──────┴────────────┴─────────────────────────────────────┘

CONSUMPTION PROGRESS: 0/4 child TFs flipped (H1, M15, M5, M1 all still bull)

═══════════════════════════════════════════════════════════════════
PHASE 1: M1 FLIPS (fastest TF, first to consume)
═══════════════════════════════════════════════════════════════════

What happens:
  → M1 candles start printing lower highs, lower lows
  → M1 dynamic ceiling falls, dynamic mid (closes) drops
  → M1 strong CHoCH bearish fires
  → M1 bias: BULL → BEAR

What this creates:
  → M1 bearish candles feed M5's dynamic envelope
  → M5 dynamic ceiling starts to feel pressure (M1 highs getting lower)
  → M5 is still BULL but its internal health begins degrading
    (M1 bearish candles = counter-trend data points within M5's bullish leg)

Bias Register update:
┌─────┬──────┬────────────┬─────────────────────────────────────┐
│ M1  │ BEAR │ ✓ ALIGNED  │ Flipped. Feeding M5 bearish data.   │
│ M5  │ BULL │ ✗ MISALIGN │ Internal health: FIRST_CRACK         │
│ M15 │ BULL │ ✗ MISALIGN │ Not yet affected.                    │
│ H1  │ BULL │ ✗ MISALIGN │ Not yet affected.                    │
└─────┴──────┴────────────┴─────────────────────────────────────┘
CONSUMPTION: 1/4 flipped

═══════════════════════════════════════════════════════════════════
PHASE 2: M5 FLIPS (M1 bearish momentum eats M5 bullish bias)
═══════════════════════════════════════════════════════════════════

What happens:
  → M1 bearish candles accumulate inside M5
  → M5 dynamic_floor breaks (avg M1 lows falling)
  → M5 dynamic_mid drops (avg M1 closes shifting bearish)
  → M5 dynamic_ceil drops (avg M1 highs getting lower)
  → M5 strong CHoCH bearish fires
  → M5 bias: BULL → BEAR

What this creates:
  → M5 LH confirmed (the M5 high that DIDN'T get broken = the last bullish extreme)
    → ★ THIS M5 LH IS THE FIRST STRUCTURAL MARKER OF THE NEW BEARISH LEG ★
  → M5 starts making LL → M5 bearish legs feed M15

  → M5 needs to make: LH (done) → LL (next) → LH → LL
    to build the M15's bearish leg

What the M5 LH means:
  → The M5 high that was previously a HH (during the bullish phase)
    is now the M5 LH — the first high of the new bearish structure
  → This M5 LH = the level where bullish M5 momentum was CAPPED
  → Liquidity above this level = the stops from the new M5 shorts
  → If price pushes back above this M5 LH → M5 bullish bias may reassert
    (the consumption failed at M5 level)

Bias Register update:
┌─────┬──────┬────────────┬─────────────────────────────────────┐
│ M1  │ BEAR │ ✓ ALIGNED  │ Established bearish.                │
│ M5  │ BEAR │ ✓ ALIGNED  │ JUST FLIPPED. M5 LH created.       │
│ M15 │ BULL │ ✗ MISALIGN │ Internal health: starting to crack  │
│ H1  │ BULL │ ✗ MISALIGN │ Barely affected yet.                │
└─────┴──────┴────────────┴─────────────────────────────────────┘
CONSUMPTION: 2/4 flipped

═══════════════════════════════════════════════════════════════════
PHASE 3: M15 FLIPS (M5 bearish momentum eats M15 bullish bias)
═══════════════════════════════════════════════════════════════════

What happens:
  → M5 bearish legs (LH → LL → LH → LL) build within M15
  → M15 dynamic envelope shifts bearish (all three sources)
  → M15 strong CHoCH bearish fires
  → M15 bias: BULL → BEAR

What this creates:
  → M15 LH confirmed → the first structural high of the bearish M15 sequence
  → M15 starts making LL → building H1's bearish leg
  → This M15 LH was created by the M5 pullback (M5 made an up-leg → M5 HH/HL
    but that M5 HH was BELOW the previous M15 high → M15 LH)

  THE M5 PULLBACK (UP-LEG) WAS THE LIQUIDITY PUSH:
  → After M5 flipped bearish and made LL, the M5 up-leg that followed
    was the "push up that needs to happen" — the counter-move
  → This M5 up-leg CONSUMED the bearish M1 stops below
  → And CREATED the M15 LH (its high was capped below M15's old high)
  → ★ THE PUSH UP THAT CONFIRMS THE M15 LH IS ITSELF A LEG
      NEEDED FOR THE BEARISH STRUCTURE TO PROPAGATE ★

Bias Register update:
┌─────┬──────┬────────────┬─────────────────────────────────────┐
│ M1  │ BEAR │ ✓ ALIGNED  │ Multiple bearish cycles completed.  │
│ M5  │ BEAR │ ✓ ALIGNED  │ LH→LL sequence established.         │
│ M15 │ BEAR │ ✓ ALIGNED  │ JUST FLIPPED. M15 LH created.      │
│ H1  │ BULL │ ✗ MISALIGN │ Internal health: DEGRADING           │
└─────┴──────┴────────────┴─────────────────────────────────────┘
CONSUMPTION: 3/4 flipped

═══════════════════════════════════════════════════════════════════
PHASE 4: H1 FLIPS (M15 bearish momentum eats H1 bullish bias)
═══════════════════════════════════════════════════════════════════

What happens:
  → M15 bearish legs accumulate inside H1
  → H1 dynamic envelope shifts bearish
  → H1 strong CHoCH bearish fires
  → H1 bias: BULL → BEAR

What this creates:
  → H1 LH confirmed → the first H1 high in the new bearish sequence
  → H1 starts making LL → building H4's bearish leg
  → ★ ALL CHILD TFs NOW ALIGNED WITH H4 BEARISH ★
  → The H4 down-leg is fully loaded — every TF from M1 to H1 is pushing down
  → This is the IMPULSIVE phase of the H4 down-leg

  H4 DOWN-LEG STATUS:
  → Building: Daily low
  → All children aligned: YES
  → Momentum: MAXIMUM (all inventory consumed, all TFs pushing same direction)

Bias Register update:
┌─────┬──────┬────────────┬─────────────────────────────────────┐
│ M1  │ BEAR │ ✓ ALIGNED  │ Fully committed.                    │
│ M5  │ BEAR │ ✓ ALIGNED  │ Fully committed.                    │
│ M15 │ BEAR │ ✓ ALIGNED  │ Fully committed.                    │
│ H1  │ BEAR │ ✓ ALIGNED  │ JUST FLIPPED. Full alignment.       │
└─────┴──────┴────────────┴─────────────────────────────────────┘
CONSUMPTION: 4/4 flipped — FULLY CONSUMED ★
```

### 3.2 The Required Counter-Legs (The Pushes That Must Happen)

Each phase above includes **counter-legs** — pushes in the OLD direction that are required for the NEW direction to create structure. These counter-legs are not reversals — they're the mechanism that creates the LH/HL needed for structural propagation:

```
THE COUNTER-LEGS IN THE CONSUMPTION SEQUENCE:

Phase 1 (M1 flips):
  → M1 bearish runs, then M1 pulls back UP
  → This M1 up-pullback creates the M5 LH (M1 high < prev M1 high = M5 LH candidate)
  → WITHOUT this M1 pullback, M5 can't create its LH → M5 can't flip

Phase 2 (M5 flips):
  → M5 makes LL, then M5 pulls back UP
  → This M5 up-pullback creates the M15 LH
  → This M5 pullback IS the "push up that needs to happen"
  → It sweeps the M1 bearish stops → providing liquidity for the next push down
  → WITHOUT this M5 pullback, M15 can't create its LH → M15 can't flip

Phase 3 (M15 flips):
  → M15 makes LL, then M15 pulls back UP
  → This M15 up-pullback creates the H1 LH
  → This is a LARGER "push up" — visible on the chart as a meaningful rally
  → It sweeps M5 bearish stops, M1 bearish stops → gathering liquidity
  → WITHOUT this M15 pullback, H1 can't create its LH → H1 can't flip

Phase 4 (H1 flips):
  → H1 makes LL, then H1 pulls back UP
  → This H1 up-pullback creates the H4's internal LH
  → This is the LARGEST counter-move — looks like a "reversal" to inexperienced eyes
  → It sweeps M15 stops, M5 stops, M1 stops → massive liquidity gathered
  → This liquidity FUELS the next H1 push down → building toward the Daily low
```

### 3.3 The Pattern — Alternating Push-Down and Push-Up

```
THE RHYTHM:

Push DOWN (creates LL) → Push UP (creates LH) → Push DOWN (creates LL) → ...

Each push-down at TF X:
  → Consumes TF X's bullish momentum
  → Creates TF X's LL (bearish continuation)
  → Builds toward parent TF's bearish leg

Each push-up at TF X:
  → Creates the LH needed for TF X+1 to recognize bearish structure
  → Sweeps TF X's bearish stops (provides liquidity for next push down)
  → Looks like a reversal but ISN'T — it's structural necessity

THE PUSH UP IS NOT OPTIONAL:
  → Without the push up, there's no LH
  → Without the LH, the next TF up can't confirm bearish structure
  → Without that confirmation, the parent TF's bearish leg isn't established
  → The push up is the MECHANISM of bearish propagation, not opposition to it
```

---

## 4. The Consumption Dashboard — Real-Time Tracking

### 4.1 The Register Table (Live)

At any moment, this table shows the complete consumption state:

```
PARENT EVENT: H4 CHoCH BEARISH (building Daily low)
CONSUMPTION TARGET: All child TFs must flip to BEAR

┌─────┬──────────┬──────────┬──────────┬──────────────┬───────────────────────┐
│ TF  │ Bias     │ Aligned? │ Consumed │ Next Needed  │ Status                │
├─────┼──────────┼──────────┼──────────┼──────────────┼───────────────────────┤
│ H4  │ ▼ BEAR   │ PARENT   │ ★ SOURCE │ —            │ Down-leg in progress  │
│ H1  │ ▲ BULL   │ ✗ NO     │ 0%       │ H1 LH+LL    │ Bullish momentum      │
│     │          │          │          │              │ must be consumed      │
│ M15 │ ▲ BULL   │ ✗ NO     │ 0%       │ M15 LH+LL   │ Waiting for H1 shift  │
│ M5  │ ▼ BEAR   │ ✓ YES    │ 100%     │ M5 LH→LL    │ Flipped. Making LL.   │
│     │          │          │          │ (in progress)│ Building M15 leg.     │
│ M1  │ ▼ BEAR   │ ✓ YES    │ 100%     │ —            │ Fully consumed.       │
└─────┴──────────┴──────────┴──────────┴──────────────┴───────────────────────┘

CONSUMPTION PROGRESS: ██████░░░░░░░░░░ 2/4 (M1 ✓, M5 ✓, M15 pending, H1 pending)

CURRENT PHASE: M5 bearish legs building → creating M15 LH
NEXT EXPECTED: M5 pulls back UP (creates M15 LH) → M5 pushes DOWN (creates M15 LL)
               → M15 strong CHoCH → M15 flips → feeds H1
```

### 4.2 Consumption Percentage

Each TF's consumption can be estimated by its conviction state and internal health:

```
CONSUMPTION SCORING PER TF:

  Bias still aligned with OLD direction, conviction NONE:      0% consumed
  Bias old direction, but PRE-CHoCH firing:                   25% consumed
  Bias old direction, internal health FIRST_CRACK:             40% consumed
  Bias old direction, internal health DEGRADING:               60% consumed
  Bias old direction, WEAK CHoCH against it fired:             75% consumed
  Bias old direction, internal health BROKEN:                  85% consumed
  STRONG CHoCH fires → bias FLIPS:                            100% consumed
```

### 4.3 The "Next Needed" Column — What Must Happen at Each TF

For each unflipped TF, the dashboard shows the specific structural events needed:

```
H1 STILL BULLISH — WHAT'S NEEDED TO FLIP:

1. H1 needs to make LH (a high that's lower than its last high)
   → Created by: M15 push UP that fails to reach H1's last swing high
   → This M15 push is the COUNTER-LEG (the push up that must happen)
   → Detected when: M15 strong CHoCH bearish fires after the M15 push
     AND the M15 high < H1 last swing high → H1 LH created

2. H1 needs to make LL (a low that's below its last low)
   → Created by: M15 bearish leg that pushes below H1's last swing low
   → Detected when: M15 LL breaks H1 dynamic floor → H1 floor broken

3. H1 needs mid (closes) to shift bearish
   → The confirming condition: avg(H1 closes) = avg(M15 closes) reverses
   → This is the COMMITMENT SHIFT — when it happens, H1 is consumed

STEPS 1 + 2 + 3 together = H1 STRONG CHoCH bearish = H1 FLIPS
```

---

## 5. The Reverse Consumption — When Highs Get Eaten During Bullish Shift

### 5.1 Mirror Logic for Bullish Consumption

Everything in §3 applies in mirror for a bullish shift:

```
TRIGGER: H4 STRONG CHoCH BULLISH (H4 down-leg → up-leg)
         H4 bias flips: BEAR → BULL
         Daily low candidate set at H4 leg_low

WHAT GETS CONSUMED: Each TF's BEARISH inventory (existing lows)

Phase 1: M1 flips BULL
  → M1 highs break → M1 HH created → M1 starts making HL
  → M1 HL = counter-leg (push DOWN) that creates M5's HL

Phase 2: M5 flips BULL
  → M5 makes HH → then M5 pulls back DOWN (creates M15 HL)
  → M5 pullback sweeps M1 bullish stops below → liquidity for next push up
  → M5 HL = the level where bearish M5 momentum was FLOORED

Phase 3: M15 flips BULL
  → M15 makes HH → then M15 pulls back DOWN (creates H1 HL)
  → M15 pullback = larger counter-move → sweeps M5 stops → fuels next push

Phase 4: H1 flips BULL
  → All TFs now BULL → fully aligned → impulsive phase of H4 up-leg
  → Building toward Daily high (D HH or D LH depending on D context)
```

### 5.2 The Counter-Legs in Bullish Consumption

```
EACH PULL-DOWN IN A BULLISH CONSUMPTION IS:

1. A necessary structural event (creates the HL needed for the next TF to confirm HH/HL)
2. A liquidity sweep (sweeps the bullish stops from the previous push up)
3. NOT a reversal — it's the mechanism that BUILDS the bullish structure

When M15 pulls back DOWN after M15 HH:
  → Creates H1 HL (if the M15 low stays above H1's last swing low)
  → Sweeps M5 stops (placed below M5 HLs during the M5 bullish phase)
  → Gathers liquidity for the next M15 push UP
  → The next M15 push UP, fueled by this liquidity, creates the H1 HH attempt
  → If H1 HH > H4 dynamic ceiling → H4 structure shift → Daily high building
```

---

## 6. The Decision Point — Confirming the HTF High/Low

### 6.1 When Consumption Stalls (The Make-or-Break Moment)

Sometimes the consumption sequence stalls — a TF refuses to flip. This is the decision point:

```
SCENARIO: After H4 CHoCH bearish, M1 and M5 have flipped bearish.
          But M15 is resisting — its bullish bias is strong.

What's happening:
  → M5 bearish legs are pushing into M15, but M15's bullish structure holds
  → M5 makes LL → but M15 dynamic floor doesn't break
  → M5 pushes down → but M15's avg(closes) stays bullish
  → The M15 bullish momentum is ABSORBING the M5 bearish pressure

Two outcomes:

OUTCOME A — M15 eventually flips:
  → More M5 bearish legs accumulate
  → M15 internal health degrades (FIRST_CRACK → DEGRADING → BROKEN)
  → M15 strong CHoCH bearish fires
  → Consumption resumes → H1 is next

OUTCOME B — M15 holds and M5 flips BACK to bullish:
  → M5 strong CHoCH bullish fires (counter to the H4 bearish direction)
  → M5 bias: BEAR → BULL (re-alignment with the old M15 bullish bias)
  → ★ CONSUMPTION FAILURE AT M15 LEVEL ★
  → The bearish momentum from H4 was not strong enough to eat through M15

  WHAT THIS MEANS:
  → The H4 bearish push was a CORRECTION, not an impulse
  → The H4 may form an H4 HL (not an H4 LL)
  → The Daily structure remains bullish (the Daily high attempt continues)
  → RE-EVALUATE: was the H4 CHoCH a real structural shift or a deep pullback?
```

### 6.2 Consumption Depth = Parent Classification

How deep the consumption goes tells you what the parent TF is doing:

| Consumption depth | Child TFs flipped | What it means | Parent TF classification |
|---|---|---|---|
| **Shallow** (only M1/M5 flip) | 1–2 of 4 | The parent's leg was a minor pullback. Limited structural damage. | Parent internal event only. Parent HL or LH (shallow). |
| **Medium** (M1/M5/M15 flip) | 3 of 4 | The parent's leg was a significant correction. Multiple TFs restructured. | Parent HL or LH confirmed. The correction is real but not a reversal. |
| **Deep** (all child TFs flip) | 4 of 4 | Full momentum consumption. Every TF committed to the new direction. | Parent leg transition confirmed. Parent HH/LL in progress. The move is impulsive. |
| **Overflow** (exceeds parent and reaches grandparent) | All children + parent exceeds grandparent level | The structural shift propagates to the grandparent TF. | Grandparent structural event. D LH/HL or D HH/LL confirmed. |

```
EXAMPLES:

After H4 CHoCH bearish:
  → Only M1+M5 flip → "H4 is just doing a shallow correction"
    → H4 down-leg is weak → expect H4 HL → H4 up-leg resumes
    → Daily high building continues

  → M1+M5+M15 flip but H1 holds → "H4 correction is real but controlled"
    → H4 LH confirmed (H4 high was lower than previous)
    → H1 bullish bias absorbs the remaining downward pressure
    → Expect H4 HL soon → H4 resumes bullish toward Daily high

  → ALL flip (M1+M5+M15+H1) → "H4 down-leg is fully loaded"
    → H4 is making a committed push down
    → Building toward Daily low
    → Classification depends on how far the H4 LL extends relative to D prev_lo

  → ALL flip + H4 LL < D prev_lo → "Daily LL"
    → The consumption overflowed — the Daily structure itself has shifted
    → Weekly structure event forming
```

---

## 7. The Complete Cycle — From Daily HH to Daily LL (or LH to HL)

### 7.1 Full Cycle with Consumption Tracking

```
═══════════════════════════════════════════════════════════════════
PHASE A: BUILDING THE DAILY HIGH
═══════════════════════════════════════════════════════════════════

H4 up-leg in progress. All child TFs (H1/M15/M5/M1) gradually flip BULLISH.

Consumption register fills up bullish:
  M1 → BULL ✓
  M5 → BULL ✓  (after M1 bullish legs create M5 HH/HL sequence)
  M15 → BULL ✓ (after M5 bullish legs create M15 HH/HL)
  H1 → BULL ✓  (after M15 bullish legs create H1 HH/HL)

When fully consumed BULL → impulsive push up → Daily high being SET.

═══════════════════════════════════════════════════════════════════
PHASE B: DAILY HIGH SET — H4 LEG TRANSITION
═══════════════════════════════════════════════════════════════════

H4 strong CHoCH bearish fires. H4 up-leg → down-leg.
Daily high = H4 leg high.

NOW: is this Daily high a HH or LH?
  → Compare H4 leg_high to D prev_hi
  → HH if exceeded, LH if failed to reach

CONSUMPTION BEGINS (bearish):
  All child TFs were BULL → now need to flip to BEAR
  This is the "eating up" of the bullish momentum

═══════════════════════════════════════════════════════════════════
PHASE C: CONSUMING BULLISH MOMENTUM (building the push down)
═══════════════════════════════════════════════════════════════════

Phase C.1: M1 flips BEAR
  → M1 strong CHoCH bearish → M1 LH created
  → The M1 LH = first structural marker of bearish structure
  → M1 makes LL → feeds M5 bearish data

Phase C.2: M5 flips BEAR
  → M5 strong CHoCH bearish → M5 LH created
  → M5 makes LL → BUT THEN M5 PUSHES BACK UP (counter-leg)
  → This M5 up-push = the liquidity sweep
  → M5 up-push HIGH = the M15 LH candidate
  → M5 up-push CANNOT exceed M15's last high (if it does → M15 holds bull)

Phase C.3: M15 flips BEAR
  → M15 strong CHoCH bearish → M15 LH confirmed
  → M15 makes LL → feeds H1 bearish data
  → M15 pushes back UP → this M15 counter-leg = H1 LH candidate
  → M15 counter-leg HIGH < H1 last swing high → H1 LH forming

Phase C.4: H1 flips BEAR
  → H1 strong CHoCH bearish → H1 LH confirmed
  → All child TFs now BEAR → full alignment
  → H4 down-leg fully loaded → impulsive push toward Daily low

═══════════════════════════════════════════════════════════════════
PHASE D: BUILDING THE DAILY LOW
═══════════════════════════════════════════════════════════════════

All TFs aligned BEAR → impulsive down push.
H4 makes LL after LL → extending the Daily down-leg.

At some point: M1 flips BULL (earliest signal of exhaustion).
Then M5 flips BULL. Then M15. Then H1.

When H1 flips BULL → H4 strong CHoCH bullish → H4 down-leg → up-leg.
Daily low = H4 leg low.

NOW: is this Daily low a HL or LL?
  → Compare H4 leg_low to D prev_lo
  → HL if held above, LL if broke below

═══════════════════════════════════════════════════════════════════
PHASE E: CONSUMING BEARISH MOMENTUM (building the push up)
═══════════════════════════════════════════════════════════════════

Same sequence as Phase C but in reverse:
  M1 flips BULL → M5 flips BULL → M15 flips BULL → H1 flips BULL
  Each flip creates the HL needed for the next TF to confirm HH/HL
  Each counter-leg (push down) sweeps bullish stops → fuels next push up
  When fully consumed → H4 up-leg impulsive → building next Daily high

═══════════════════════════════════════════════════════════════════
PHASE F: DAILY CLASSIFICATION
═══════════════════════════════════════════════════════════════════

NOW you have both a Daily high and a Daily low.
Compare to previous Daily swings:

  Daily high = HH or LH (from Phase B)
  Daily low = HL or LL (from Phase D)

  HH + HL → Daily BULLISH structure (BOS) → expect continuation up
  HH + LL → Daily EXPANSION (outside day) → direction from close
  LH + HL → Daily COMPRESSION (inside day) → coiling
  LH + LL → Daily BEARISH structure (BOS or CHoCH) → expect continuation down
  LH + HL → Daily RANGE → accumulation or distribution

→ CYCLE REPEATS (Phase A or the bearish equivalent)
```

---

## 8. The Consumption Map — Visual Specification

### 8.1 Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  MOMENTUM CONSUMPTION — POST H4 CHoCH BEARISH                   │
│  Target: Daily Low | D prev_lo: 1.2550                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  M1  ████████████████████████████████████████  100% BEAR ✓      │
│  M5  ██████████████████████████████░░░░░░░░░░   75% BEAR ~      │
│       ↑ M5 LL done, M5 counter-leg (push up) in progress        │
│       → M5 push-up target: last M5 LH @ 1.2645                  │
│       → M5 push-up HIGH will create M15 LH                      │
│  M15 █████████████░░░░░░░░░░░░░░░░░░░░░░░░░░   40% degrading   │
│       ↑ Internal health: FIRST_CRACK                             │
│       → Waiting for M5 to complete counter-leg                   │
│  H1  ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   10% PRE          │
│       ↑ Dynamic mid stalling. Ceiling flat.                      │
│       → Not yet affected by M15 shift                            │
│                                                                  │
│  NEXT EVENT: M5 counter-leg completes (push up → M5 LH)         │
│  THEN:       M5 resumes down → M15 floor breaks → M15 flips     │
│  ESTIMATED:  2-3 M5 candles (10-15 min)                          │
│                                                                  │
│  LIQUIDITY MAP:                                                  │
│  ── 1.2680 ── H1 last swing high (major liq above) ────────     │
│  ── 1.2660 ── M15 last swing high (liq above) ─────────────     │
│  ── 1.2645 ── M5 LH (nearest liq above — push-up target) ─     │
│  ~~ 1.2630 ~~ current price ~~~~~~~~~~~~~~~~~~~~~~~~~~~~────     │
│  ── 1.2610 ── M5 last swing low (support below) ───────────     │
│  ── 1.2590 ── M15 last swing low (deeper support) ─────────     │
│  ── 1.2550 ── D prev_lo (Daily LL level) ──────────────────     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 What the Trader Sees and Does

```
READING THE DASHBOARD:

"M1 and M5 have flipped bearish — the fastest TFs are consumed.
 M5 is at 75% — it's doing its counter-leg (push up) right now.
 This push up will top out below M15's last high (1.2660),
 creating the M15 LH.
 
 M15 is at 40% — internal health cracking. Once M5's counter-leg
 completes and M5 resumes down, M15 will break.
 
 H1 is at 10% — barely affected. Its bullish momentum is thick.
 It will take M15 flipping + M15 making LL + M15 counter-leg +
 M15 LL again before H1 starts to crack.
 
 TRADING DECISION:
 → The push up on M5 right now is NOT a buy signal.
 → It's the counter-leg needed for bearish structure to propagate.
 → SHORT ENTRY: when M5's counter-leg tops out and M5 resumes down.
 → Entry: M5 dynamic ceiling breaks downward (strong CHoCH bearish on M1)
 → SL: above the M5 counter-leg high (which will become M15 LH)
 → TP1: M5 swing low (1.2610)
 → TP2: M15 swing low (1.2590)
 → TP3: D prev_lo (1.2550) — if full consumption completes"
```

---

## 9. Pine Script — Bias Register & Consumption Tracker

### 9.1 Per-TF Bias State

```pine
// Bias register — tracks direction and consumption status per TF
var int    m1_bias  = 0    // +1 = bull, -1 = bear, 0 = neutral
var int    m5_bias  = 0
var int    m15_bias = 0
var int    h1_bias  = 0
var int    h4_bias  = 0

var float  m1_consumption  = 0.0   // 0.0 to 1.0
var float  m5_consumption  = 0.0
var float  m15_consumption = 0.0
var float  h1_consumption  = 0.0

// Parent event tracking
var int    parent_target_dir = 0    // the direction all children must flip to
var string parent_event      = ""   // e.g., "H4_CHOCH_BEAR"
```

### 9.2 Consumption Update Logic

```pine
// Called on each bar — updates consumption percentage per TF
update_consumption(int tf_bias, int target_dir, string conviction, 
                   string int_health) =>
    float pct = 0.0
    if tf_bias == target_dir
        pct := 1.0  // fully consumed — bias matches target
    else
        // Estimate based on conviction and internal health
        if conviction == "STRONG"
            pct := 0.95  // about to flip
        else if int_health == "BROKEN"
            pct := 0.85
        else if conviction == "WEAK"
            pct := 0.75
        else if int_health == "DEGRADING"
            pct := 0.60
        else if int_health == "FIRST_CRACK"
            pct := 0.40
        else if conviction == "PRE"
            pct := 0.25
        else
            pct := 0.10  // not yet affected
    pct
```

### 9.3 Counter-Leg Detection

```pine
// Detect when a TF is in its counter-leg (pushing against the consumption direction)
// This is the "push up that needs to happen" for bearish consumption
// or the "push down that needs to happen" for bullish consumption

is_counter_leg(int tf_bias, int parent_target_dir, int tf_leg_dir) =>
    // Counter-leg = TF bias has already flipped to target
    //               but current leg direction is AGAINST target
    //               (the pullback that creates the LH/HL)
    tf_bias == parent_target_dir and tf_leg_dir != parent_target_dir
```

---

## 10. Integration — How Consumption Connects to Everything

### 10.1 Consumption → Conviction (from 04c)

| Consumption % at TF X | Conviction likely at TF X | Structural meaning |
|---|---|---|
| 0–25% | NONE at TF X | TF X's old bias is dominant. No structural shift visible. |
| 25–40% | PRE at TF X | TF X's momentum is fading. The envelope is stalling. |
| 40–60% | WEAK at TF X (internal events firing) | Internal swings appearing against the leg. Sub-waves shifting. |
| 60–85% | WEAK → STRONG boundary | Internal health degrading. Close to flipping. |
| 85–100% | STRONG at TF X | The flip is happening or has happened. External event fires. |

### 10.2 Consumption → Leg Architecture (from 04b)

| Consumption state | Leg state | What's happening |
|---|---|---|
| 0/4 flipped | Parent leg just started. No children consumed. | New parent leg is "empty" — hasn't propagated down yet. |
| 1/4 flipped (M1 only) | M1 in new direction, rest in old. | Earliest structural shift. Most will see this as noise. |
| 2/4 flipped (M1+M5) | M5 creating first structural legs in new direction. | The new direction is building. Counter-legs creating LH/HL at M15. |
| 3/4 flipped (M1+M5+M15) | M15 legs building H1 structure. | Serious momentum shift. H1 is the last holdout. |
| 4/4 flipped (all) | All children aligned. | Impulsive phase. Maximum momentum. The parent's leg is fully committed. |

### 10.3 Consumption → Entry Timing

```
ENTRY RULES BASED ON CONSUMPTION:

EARLY ENTRY (aggressive):
  → Enter when 2/4 TFs have flipped
  → Entry on M5 counter-leg top (when M5 up-leg exhausts after M5 flip)
  → Higher risk: M15 and H1 still carry old momentum — could reverse the setup
  → SL: above M15 last swing high (the old bias level that must hold)
  → Reward: catch the full consumption from M15 through H1

STANDARD ENTRY (balanced):
  → Enter when 3/4 TFs have flipped
  → Entry on M15 counter-leg top (when M15 up-leg exhausts after M15 flip)
  → Moderate risk: only H1 still carrying old momentum
  → SL: above H1 last swing high
  → Reward: catch the H1 flip and the impulsive phase

CONFIRMATION ENTRY (conservative):
  → Enter when 4/4 TFs have flipped
  → Entry on H1 counter-leg top (first H1 LH after full consumption)
  → Low risk: all TFs aligned, momentum is maximum
  → SL: above the H1 LH (tight stop)
  → Reward: ride the impulsive phase (smaller but higher probability)
```

---

## 11. Summary

After any parent-TF structural shift, each child TF carries residual momentum in the old direction. These old-direction biases are consumed one by one, from the fastest TF (M1) upward, through a sequence of strong CHoCH flips. Each flip requires a counter-leg — a push in the old direction that creates the LH or HL needed for the next TF to build its new-direction structure. These counter-legs are not reversals; they are the mechanical requirement for bearish (or bullish) structure to propagate upward through the timeframe cascade.

By tracking the consumption percentage at each TF (using conviction level and internal health as proxies), you know at every moment: how much of the old momentum has been eaten, which TF is currently being consumed, what counter-leg must happen next, and when all TFs will align for the impulsive phase. The consumption depth predicts the parent classification: shallow consumption (1–2 TFs flip) = parent pullback (HL/LH); deep consumption (all TFs flip) = parent leg transition (HH/LL); overflow consumption (exceeds parent level) = grandparent structural event.
