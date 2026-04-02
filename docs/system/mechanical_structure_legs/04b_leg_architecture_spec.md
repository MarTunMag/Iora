# Leg Architecture — How Child-TF Legs Build Parent-TF Structural Swings

**System:** Iora  
**Date:** March 2026  
**Depends on:** `04_period_level_structure_spec_v2.md` (dynamic averages + period levels), `03_internal_external_structure_spec_lines.md` (zone-based confirmation)  
**Purpose:** Mechanically map the up-legs and down-legs at each TF that *build* the parent TF's HH/HL/LH/LL — and at every moment know which leg is in progress, which leg must come next, and what the completion of each leg means for every TF above it.

---

## 1. The Core Principle — Swings Are Built from Legs

A "swing high" at any TF is not a single event. It's the **culmination of a sequence of child-TF legs**:

```
DAILY HIGH is built by:
  H4 UP-LEG (H4 candles making higher highs)
    ← built by H1 UP-LEGs within each H4 up-candle
      ← built by M15 UP-LEGs within each H1 up-candle
        ← built by M5 UP-LEGs within each M15 up-candle
          ← built by M1 UP-LEGs within each M5 up-candle

DAILY HIGH IS CONFIRMED when:
  H4 stops making higher highs → H4 DOWN-LEG begins
    ← confirmed by H1 making lower highs/lower lows
      ← confirmed by M15 making lower highs/lower lows
        ... all the way down to M1
```

The Daily high doesn't exist as a confirmed structural event until the H4 candles *stop pushing up and start pushing down*. And you detect that H4 reversal through the H1 reversal, which you detect through the M15 reversal, all the way down.

**This is what the dynamic averages give you in real time:** when the H4 dynamic ceiling (avg of H1 highs) stops rising and starts falling, the Daily high is being set. When the H4 dynamic floor (avg of H1 lows) starts falling, the Daily low leg has begun.

---

## 2. Leg Anatomy — The Minimum Viable Swing

### 2.1 What Constitutes a "Leg"

A leg at TF X is a **directional sequence of child-TF candles** that produces a swing at TF X. The minimum structure of any swing requires:

```
MINIMUM VIABLE SWING HIGH at TF X:
  1. UP-LEG:   ≥2 child candles with rising dynamic ceiling
  2. PEAK:     child candle where dynamic ceiling stops rising
  3. DOWN-LEG: ≥1 child candle with dynamic ceiling falling
               (this DOWN-LEG confirms the PEAK retroactively)

MINIMUM VIABLE SWING LOW at TF X:
  1. DOWN-LEG: ≥2 child candles with falling dynamic floor
  2. TROUGH:   child candle where dynamic floor stops falling
  3. UP-LEG:   ≥1 child candle with dynamic floor rising
               (this UP-LEG confirms the TROUGH retroactively)
```

**The critical insight:** You need the *opposing leg* to confirm the swing. A high is only confirmed as a high when the subsequent down-leg begins. A low is only confirmed when the subsequent up-leg begins. This is true at every TF.

### 2.2 The Leg Sequence That Builds a Parent Swing

To build a complete parent-TF swing (e.g., a Daily high), the child TF must execute a specific leg sequence:

```
BUILDING A DAILY HIGH:
──────────────────────────────────────────────────────

H4 LEG 1 (UP):    H4 candles push higher
                   → H4 dynamic ceiling rising
                   → This is the "impulse leg" building the Daily high
                   → Inside this H4 up-leg:
                     H1 LEG 1a (UP):   H1 highs rising → H4 HH forming
                     H1 LEG 1b (DOWN): H1 highs falling → H4 pullback (H4 HL)
                     H1 LEG 1c (UP):   H1 highs rising again → H4 HH continuation
                     ... repeating until H4 up-leg exhausts

H4 LEG 2 (DOWN):  H4 candles start pushing lower
                   → H4 dynamic ceiling falling
                   → ★ THIS CONFIRMS THE DAILY HIGH ★
                   → The highest H4 high from LEG 1 = the Daily high
                   → Inside this H4 down-leg:
                     H1 LEG 2a (DOWN): H1 lows falling → H4 LL forming
                     H1 LEG 2b (UP):   H1 lows rising → H4 pullback (H4 LH)
                     H1 LEG 2c (DOWN): H1 lows falling again → H4 LL continuation
                     ... this H4 down-leg IS building the Daily low

H4 LEG 3 (UP):    H4 candles push higher again
                   → H4 dynamic ceiling rising again
                   → ★ THIS CONFIRMS THE DAILY LOW ★
                   → The lowest H4 low from LEG 2 = the Daily low
                   → Now: does this new H4 up-leg exceed the Daily high from LEG 1?
                     → YES: Daily HH forming
                     → NO:  Daily LH forming
```

### 2.3 The Nested Leg Structure

Every leg at one level contains a complete leg sequence at the level below:

```
DAILY: ──── UP-LEG ────────────────────── DOWN-LEG ──────────────── UP-LEG ─────
              │                              │                         │
H4:    ─ up ─ dn ─ up ─ up ─ dn ─     ─ dn ─ up ─ dn ─ dn ─     ─ up ─ dn ─ up
              │                              │                         │
H1:    multiple H1 legs per H4 leg    multiple H1 legs per H4     multiple H1 legs
              │                              │                         │
M15:   multiple M15 legs per H1       multiple M15 legs per H1    ...
              │                              │
M5:    multiple M5 legs per M15       ...
              │
M1:    multiple M1 legs per M5
```

**At any given moment, you are simultaneously in:**
- An M1 leg (up or down)
- An M5 leg (up or down)
- An M15 leg (up or down)
- An H1 leg (up or down)
- An H4 leg (up or down)
- A Daily leg (up or down)

**And each leg at each level is building a swing at the level above it.**

---

## 3. Leg State Tracking — The Real-Time Model

### 3.1 Per-TF Leg State

For each TF, track the current leg and what it's building:

```
LegState:
    tf:                 string     (e.g., "H4")
    parent_tf:          string     (e.g., "D")
    current_direction:  UP | DOWN  (which way this TF's leg is going)
    leg_number:         int        (sequential leg count since last parent swing)
    
    # What this leg is building at the parent level
    building:           PARENT_HIGH | PARENT_LOW
    
    # The extremes of the current leg
    leg_high:           float      (highest child-candle high in this leg)
    leg_low:            float      (lowest child-candle low in this leg)
    
    # Comparison to previous leg at same TF
    prev_leg_high:      float
    prev_leg_low:       float
    
    # Classification of this leg's swing (once confirmed)
    swing_class:        HH | LH | HL | LL | PENDING
    
    # Dynamic averages within this leg
    dynamic_ceil:       float      (avg of child highs)
    dynamic_floor:      float      (avg of child lows)
    dynamic_mid:        float      (avg of child closes)
```

### 3.2 Leg Transitions

A leg transition occurs when the dynamic average reverses direction — detected through the three-source envelope from the candle type spec:

**UP-LEG → DOWN-LEG transition (confirmed by child TF):**
```
DETECTION:
  Strong: dynamic_ceil starts falling AND dynamic_mid turns AND dynamic_floor breaks
  Medium: dynamic_ceil starts falling AND dynamic_mid turns
  Early:  dynamic_ceil flattens after rising (pre-CHoCH from spec 04a)

ON TRANSITION:
  1. CONFIRM SWING HIGH at this TF
     → swing_high = leg_high (the max high during the up-leg)
     → Classify: HH if leg_high > prev_leg_high, LH if leg_high < prev_leg_high
  
  2. PROPAGATE TO PARENT
     → If this swing high > parent TF's last swing high:
       → Parent TF swing high is being RAISED (parent HH building)
     → If this swing high < parent TF's last swing high:
       → Parent TF swing high is CAPPED (parent LH forming)
  
  3. UPDATE PARENT BUILDING STATE
     → This TF was building: PARENT_HIGH
     → Now building: PARENT_LOW (the down-leg creates the parent's low)
  
  4. START NEW DOWN-LEG
     → leg_number += 1
     → current_direction = DOWN
     → Reset leg_high/leg_low
```

**DOWN-LEG → UP-LEG transition (mirror logic):**
```
DETECTION:
  Strong: dynamic_floor starts rising AND dynamic_mid turns AND dynamic_ceil breaks
  Medium: dynamic_floor starts rising AND dynamic_mid turns
  Early:  dynamic_floor flattens after falling

ON TRANSITION:
  1. CONFIRM SWING LOW at this TF
     → swing_low = leg_low (the min low during the down-leg)
     → Classify: HL if leg_low > prev_leg_low, LL if leg_low < prev_leg_low
  
  2. PROPAGATE TO PARENT
     → If this swing low < parent TF's last swing low:
       → Parent TF swing low is being EXTENDED (parent LL building)
     → If this swing low > parent TF's last swing low:
       → Parent TF swing low is HOLDING (parent HL forming)
  
  3. UPDATE PARENT BUILDING STATE
     → This TF was building: PARENT_LOW
     → Now building: PARENT_HIGH (the up-leg creates the parent's high)
  
  4. START NEW UP-LEG
     → leg_number += 1
     → current_direction = UP
     → Reset leg_high/leg_low
```

---

## 4. The Full Cascade — What Each Leg Tells You About Every TF Above

### 4.1 Reading the Current State

At any moment, the leg state at each TF tells you exactly what's happening at every level:

```
EXAMPLE SNAPSHOT:

M1:  UP-LEG #3      → building M5 high
M5:  UP-LEG #2      → building M15 high  
M15: DOWN-LEG #4    → building H1 low
H1:  DOWN-LEG #2    → building H4 low
H4:  UP-LEG #3      → building D high
D:   DOWN-LEG #1    → building W low

READING THIS:
─────────────────────────────────────────────────────────
"The Weekly is making its low (D down-leg #1).
 The Daily is still pushing up (H4 up-leg #3 building the D high).
 But within that D high-building, the H1 is pulling back (H1 down-leg #2).
 Within that H1 pullback, the M15 is deep into its down-leg (#4).
 But at M5 level, a new up-leg has started (#2).
 And M1 is pushing up within that M5 up-leg (#3).
 
 THE M1/M5 UP-LEGS ARE THE EARLIEST SIGNAL THAT:
 → The M15 down-leg is exhausting
 → The H1 pullback is about to end
 → The H4 up-leg will resume
 → The Daily high is still being built
 
 WHAT NEEDS TO HAPPEN NEXT:
 → M5 up-leg needs to break M15 dynamic ceiling → M15 up-leg starts
 → M15 up-leg needs to break H1 dynamic ceiling → H1 up-leg starts
 → H1 up-leg continues building the H4 HH
 → H4 HH caps below D prev_hi → D LH confirmed
 → OR H4 HH exceeds D prev_hi → D HH confirmed"
```

### 4.2 The "Legs Needed" Framework

For any parent TF swing to be confirmed, a specific sequence of child-TF legs must complete. This creates a checklist of "legs needed":

**To confirm a DAILY HIGH:**
```
REQUIRED LEGS:
  ✓ H4 UP-LEG (≥1 complete, with H4 dynamic ceiling was rising)
  ✓ H4 DOWN-LEG begins (H4 dynamic ceiling starts falling)
    ✓ Confirmed by: H1 DOWN-LEG starts (H1 dynamic ceiling falling)
      ✓ Confirmed by: M15 DOWN-LEG starts (M15 making lower highs)
        ✓ Confirmed by: M5 DOWN-LEG starts (M5 dynamic ceiling breaks)

DAILY HIGH = the highest H4 high from the H4 UP-LEG
CONFIDENCE increases with each nested confirmation level
```

**To confirm a DAILY LOW (after the Daily high is set):**
```
REQUIRED LEGS:
  ✓ H4 DOWN-LEG (≥1 complete, with H4 dynamic floor was falling)
  ✓ H4 UP-LEG begins (H4 dynamic floor starts rising)
    ✓ Confirmed by: H1 UP-LEG starts (H1 dynamic floor rising)
      ✓ Confirmed by: M15 UP-LEG starts (M15 making higher lows)
        ✓ Confirmed by: M5 UP-LEG starts (M5 dynamic floor breaks up)

DAILY LOW = the lowest H4 low from the H4 DOWN-LEG
NOW: the classification question — is the next move a Daily HH or Daily LH?
```

**To classify the DAILY HIGH as HH or LH:**
```
AFTER DAILY LOW IS CONFIRMED:
  H4 UP-LEG resumes (building toward new Daily high)
  
  AS H4 MAKES NEW HIGHS:
    → Compare H4 leg_high to Daily prev_hi (the last confirmed Daily high)
    
    IF H4 leg_high > Daily prev_hi:
      → DAILY HH IS FORMING
      → The up-leg has exceeded the previous Daily high
      → This will be confirmed when the subsequent H4 DOWN-LEG begins
    
    IF H4 leg_high < Daily prev_hi AND H4 up-leg starts exhausting:
      → DAILY LH IS FORMING
      → The up-leg failed to reach the previous Daily high
      → Detected when: H4 dynamic ceiling flattens below Daily prev_hi
      → Earliest detection: H1 starts making LH within the H4 up-leg
        → Confirmed: M15 starts making LH within the H1
          → Earliest: M5 dynamic ceiling < H1 prev_hi while H1 dynamic ceiling < H4 prev_hi
```

### 4.3 The Classification Cascade — Every Swing Explained

**H1 LL (below previous H1 LL) → what does this create?**
```
H1 LL confirmed (H1 dynamic floor broke, new low below prev H1 swing low)
  → Compare to H4 context:
    → IF H1 LL > prev H4 swing low:
      → H4 HL forming (the H4 is pulling back but holding above its last low)
      → This H4 HL, once confirmed, will become the base for the next H4 up-leg
      → That H4 up-leg builds toward: H4 HH or H4 LH
        → If H4 HH > prev D high → D HH
        → If H4 HH < prev D high → D LH
    
    → IF H1 LL < prev H4 swing low:
      → H4 LL forming (the H4 low is being broken → new H4 leg down)
      → This extends the D's down-leg
      → D LOW is still being built
      → Next expected: H1 HL → H4 HL → H4 up-leg → to build D's next high
```

**H4 HH (above previous H4 HH, but below Daily prev high) → what does this create?**
```
H4 HH confirmed (H4 dynamic ceiling broke up, new high above prev H4 swing high)
  → Compare to Daily context:
    → H4 HH < Daily prev_hi:
      → ★ DAILY LH IS CONFIRMED ★
      → The H4 pushed up but couldn't reach the previous Daily high
      → This means: the Daily's up-leg was weaker than the previous one
      → BEARISH at Daily level
      → Next expected: H4 down-leg → builds toward new Daily low
        → If new Daily low < prev Daily low → Daily LL (bearish continuation)
        → If new Daily low > prev Daily low → Daily HL (range/accumulation)
    
    → H4 HH > Daily prev_hi:
      → DAILY HH IS FORMING (but not confirmed until subsequent down-leg begins)
      → BULLISH at Daily level
      → Confirmation: H4 starts DOWN-LEG (H4 dynamic ceiling falls)
        → Confirmed by: H1 makes LH sequence within the H4 down-leg
```

**M15 HH (inside an H1 up-leg, inside an H4 down-leg) → reading the nested state:**
```
M15 HH (M15 dynamic ceiling broke up, new high above prev M15 swing high)
  → M15 is in UP-LEG → building H1 high
    → But H1 is in DOWN-LEG → building H4 low
      → So this M15 HH is a COUNTER-TREND rally within the H1 down-leg
      → It's building an H1 LH (pullback high within the H1's bearish move)
      
      → IF this M15 HH exceeds H1 dynamic ceiling:
        → H1 dynamic ceiling broken → H1 DOWN-LEG may be ending
        → Potential H1 CHoCH → H4 low might be confirmed
        → CHECK: does the H1 up-leg that follows break H4 dynamic ceiling?
          → If yes: H4 down-leg is ending → Daily high building resumes
          → If no: H1 LH (failed rally) → H4 down-leg continues
      
      → IF this M15 HH stays below H1 dynamic ceiling:
        → H1 LH confirmed → H1 down-leg continues → building H4 low
        → Expect: M15 DOWN-LEG next → deeper into H1's bearish structure
```

---

## 5. The Liquidity Leg — Understanding Why the Push Up Must Happen

### 5.1 The Mechanical Necessity of Counter-Legs

Every down-leg creates a liquidity requirement for the next up-leg, and vice versa. This isn't just structural — it's mechanical:

```
H4 DOWN-LEG COMPLETES (building Daily low):
  → H4 has been making lower lows
  → Each H4 LL created SHORT positions that placed STOP-LOSSES above
  → Those stops sit at: H4 LH levels, H1 swing highs, M15 swing highs
  
  NOW: For the market to move up (build the Daily's next high):
  → It must SWEEP those stops → this IS the up-leg's fuel
  → The up-leg is mechanically driven by stop-loss triggering
  
  THEREFORE:
  → The up-leg MUST reach at least the nearest significant LH
  → The number and depth of H1/M15 highs created during the down-leg
     = the TARGETS for the up-leg
  → This is why you can predict the minimum extent of the next leg
```

### 5.2 Mapping Liquidity Targets per Leg

As each leg progresses, it creates liquidity targets for the opposing leg:

```
DURING H4 DOWN-LEG:
  Track all H1 swing highs (LH levels) created:
    H1 LH #1: 1.2650  ← first pullback high during H4 down-leg
    H1 LH #2: 1.2630  ← second pullback high (lower = bearish structure)
    H1 LH #3: 1.2610  ← third pullback high

  These LH levels = LIQUIDITY POOLS (stops sitting above each)
  
WHEN H4 UP-LEG BEGINS:
  MINIMUM TARGET: H1 LH #3 (1.2610) — nearest liquidity
  MEDIUM TARGET:  H1 LH #2 (1.2630) — deeper liquidity
  MAXIMUM TARGET: H1 LH #1 (1.2650) — full sweep
  BREAKOUT:       Above H1 LH #1 = the H4 CHoCH → structure reversal

  Each target reached = more fuel consumed
  IF all H1 LH levels swept → H4 down-leg's structure fully invalidated
  → Expect: H4 HH attempt (potential Daily HH or LH depending on Daily context)
```

### 5.3 The Down-to-Up Transition — Step by Step with Dynamic Averages

```
SCENARIO: H4 down-leg has been building the Daily low.
          Now watching for the transition to the H4 up-leg.

STEP 1 — EARLIEST (M1/M5 level):
  M1 candles stop making lower lows → M5 dynamic floor flattens
  M1 candles start making higher lows → M5 dynamic floor rises
  → ★ M5 INTRA-PERIOD CHoCH BULLISH ★
  → "The smallest structural unit has flipped. Watch for propagation."

STEP 2 — M5 → M15 PROPAGATION:
  M5 dynamic floor rising → M5 up-leg confirmed
  M5 dynamic ceiling breaks upward → M5 HH
  IF M5 HH > M15 dynamic ceiling → M15 ceiling broken from inside
  → ★ M15 LEG TRANSITION: DOWN → UP ★
  → M15 swing low confirmed (the trough of the M15 down-leg)
  → Classify: M15 HL (if above prev M15 swing low) or M15 LL

STEP 3 — M15 → H1 PROPAGATION:
  M15 up-leg continues → M15 dynamic ceiling rising
  M15 makes HH → M15 pushing past resistance
  IF M15 HH > H1 dynamic ceiling → H1 ceiling broken
  → ★ H1 LEG TRANSITION: DOWN → UP ★
  → H1 swing low confirmed = H4 LOW CANDIDATE
  → Classify: H1 HL or H1 LL
  → Compare H1 swing low to H4 context:
    → H1 HL > prev H4 swing low → H4 HL forming (H4 pullback holding)
    → H1 LL < prev H4 swing low → H4 LL (H4 bearish continuation)

STEP 4 — H1 → H4 PROPAGATION:
  H1 up-leg → H1 dynamic ceiling rising → building toward H1 HH
  H1 HH confirmed → breaks H4 dynamic ceiling
  → ★ H4 LEG TRANSITION: DOWN → UP ★
  → H4 swing low confirmed = DAILY LOW CANDIDATE
  → Classify: H4 HL or H4 LL
  → Compare H4 swing low to Daily context:
    → H4 HL > prev D swing low → D HL forming (Daily pullback holding, bullish)
    → H4 LL < prev D swing low → D LL (Daily bearish continuation)

STEP 5 — H4 → DAILY PROPAGATION:
  H4 up-leg → H4 dynamic ceiling rising → building toward H4 HH
  H4 HH confirmed
  → Compare to Daily context:
    → H4 HH > Daily prev_hi → ★ DAILY HH FORMING ★ (bullish at Daily)
    → H4 HH < Daily prev_hi → ★ DAILY LH CONFIRMED ★ (bearish at Daily)
  
  DAILY HIGH CONFIRMED when:
  → H4 starts next DOWN-LEG (H4 dynamic ceiling falls)
    → All the way down through H1 → M15 → M5 → M1 confirming
```

---

## 6. The Leg Expectation Model — "What Comes Next"

### 6.1 After Every Leg Transition, You Know What Must Happen

This is the mechanical prediction framework — after each transition, the system tells you what legs are *required* before the next parent-TF swing can confirm:

```
STATE: H4 swing low just confirmed. H4 UP-LEG beginning.
       Daily was in DOWN-LEG (building Daily low).
       Daily low now CANDIDATES (may be confirmed by H4 up-leg).

REQUIRED LEG SEQUENCE:
──────────────────────────────────────────────────────

1. H4 UP-LEG must produce at least one H1 HH
   → This H1 HH attempt targets the H1 LH liquidity created during the H4 down-leg
   → MONITOR: dynamic_ceil(H4) — must be rising
   → INSIDE: H1 must complete: UP-LEG → DOWN-LEG → UP-LEG (minimum swing sequence)

2. H4 UP-LEG's high determines the DAILY classification:
   → Track: H4 leg_high vs Daily prev_hi
   → IF leg_high approaches Daily prev_hi:
     → DECISION POINT — will it break or fail?
     → Watch H1 dynamic averages for exhaustion:
       → H1 dynamic ceiling flattening near Daily prev_hi = exhaustion = Daily LH likely
       → H1 dynamic ceiling accelerating through Daily prev_hi = momentum = Daily HH likely

3. AFTER H4 UP-LEG EXHAUSTS → H4 DOWN-LEG begins:
   → ★ DAILY HIGH NOW CONFIRMED ★
   → Classification: HH if leg_high > Daily prev_hi, LH if leg_high < Daily prev_hi
   
4. H4 DOWN-LEG then builds toward the NEXT DAILY LOW:
   → Cycle continues
```

### 6.2 The Complete Expectation Table

At any moment, given the current leg state at each TF, you know what's expected:

| Current state | What's being built | What confirms it | What comes after | Classification depends on... |
|---|---|---|---|---|
| H4 UP-LEG, D was in DOWN-LEG | Daily low (confirmation) + next Daily high | H4 ceiling starts falling (up-leg ends) | H4 DOWN-LEG (builds next Daily low) | Whether H4 HH exceeds D prev_hi (HH) or fails (LH) |
| H4 DOWN-LEG, D was in UP-LEG | Daily high (confirmation) + next Daily low | H4 floor starts rising (down-leg ends) | H4 UP-LEG (builds next Daily high) | Whether H4 LL drops below D prev_lo (LL) or holds (HL) |
| H1 UP-LEG inside H4 UP-LEG | H4 high (building) | H1 ceiling starts falling (H1 up-leg ends, creates H1 swing high) | H1 DOWN-LEG (H4 pullback = H4 HL) | Whether H1 HH exceeds H4 prev_hi (H4 HH) or fails (H4 LH) |
| H1 DOWN-LEG inside H4 UP-LEG | H4 pullback (H4 HL) | H1 floor starts rising (H1 down-leg ends) | H1 UP-LEG (resumes H4 push higher) | Whether H1 LL drops below H4 dynamic floor (H4 up-leg broken) or holds (H4 HL confirmed) |
| M15 UP-LEG inside H1 DOWN-LEG | H1 pullback high (H1 LH) | M15 ceiling starts falling | M15 DOWN-LEG (resumes H1 push lower) | Whether M15 HH exceeds H1 dynamic ceiling (H1 CHoCH) or fails (H1 LH, bearish continues) |
| M5 UP-LEG inside M15 DOWN-LEG | M15 pullback (M15 LH) | M5 ceiling starts falling | M5 DOWN-LEG (resumes M15 push lower) | Whether M5 HH exceeds M15 dynamic ceiling (M15 CHoCH) or fails |

### 6.3 The Nested Expectation — Full Depth Example

```
CURRENT STATE:
  D:   DOWN-LEG #2  → building W low
  H4:  UP-LEG #1   → building D high (which will be D LH or D HH)
  H1:  DOWN-LEG #3 → H4 pullback (H4 HL forming)
  M15: UP-LEG #2   → H1 rally attempt (H1 LH forming?)
  M5:  UP-LEG #4   → M15 high building
  M1:  DOWN-LEG #1 → M5 pullback

WHAT THIS MEANS — READ BOTTOM-UP:

"M1 is pulling back (DOWN-LEG #1) within an M5 that's been pushing up (#4).
 This M5 up-leg is building the M15 high.
 The M15 up-leg (#2) is a RALLY within an H1 that's been falling (#3).
 This is an H1 pullback — creating an H1 LH.
 The H1 down-leg (#3) is creating an H4 pullback — an H4 HL.
 The H4 up-leg (#1) is building the next Daily high.
 The Daily is in a down-leg (#2), building the Weekly low."

WHAT TO EXPECT NEXT:

1. NEAREST: M1 down-leg exhausts → M5 resumes up → M15 high forms
   → Does M15 HH exceed H1 dynamic ceiling?
     → NO: H1 LH confirmed → H1 down-leg continues → H4 HL deepens
     → YES: H1 CHoCH → H1 up-leg starts → H4 up-leg RESUMES

2. IF H1 CHoCH (up-leg starts):
   → H1 makes HH → does it exceed H4 dynamic ceiling?
     → NO: H4 LH → H4 up-leg was weak → D might not make a significant high
     → YES: H4 HH → does it exceed D prev_hi?
       → NO: ★ D LH CONFIRMED ★ → bearish at Daily → expect D down-leg to resume
       → YES: ★ D HH FORMING ★ → bullish at Daily → expect continuation

3. THE DECISION TREE FROM HERE HAS EXACTLY 4 TERMINAL OUTCOMES:
   a. M15 fails to break H1 ceiling → H1 continues down → H4 breaks HL → 
      H4 UP-LEG FAILS → D high was a D LH → strongly bearish
   b. M15 breaks H1 ceiling → H1 up → H4 continues → H4 HH < D prev_hi → 
      D LH → moderately bearish
   c. M15 breaks H1 ceiling → H1 up → H4 continues → H4 HH > D prev_hi → 
      D HH → bullish
   d. M15 breaks H1 ceiling → H1 up → but H1 HH < H4 ceiling → H4 LH → 
      H4 UP-LEG weakening → uncertain, watch next H4 down-leg
```

---

## 7. Detecting the Daily Candle's Internal Structure in Real Time

### 7.1 A New Daily Candle Opens — What You Know Immediately

```
NEW DAILY CANDLE OPENS (00:00 GMT):
─────────────────────────────────────────────────────
  D prev_hi = yesterday's high
  D prev_lo = yesterday's low
  D prev_close = yesterday's close

  ALSO OPENING (potentially):
  → New H4 (if the D open aligns with an H4 boundary)
  → New H1 (always — 00:00 is an H1 boundary)
  → New M15, M5, M1 (always)

  FROM YESTERDAY'S STRUCTURE YOU KNOW:
  → D trend direction (HH/HL = bullish, LH/LL = bearish)
  → Last D swing high, swing low
  → H4 leg state carried over (which H4 leg was in progress at yesterday's close)
  → H1/M15/M5 leg states carried over
```

### 7.2 Building Today's Daily High/Low — The Live Tracking

```
AS THE DAY PROGRESSES:

HOUR 0-1 (first H1 candle):
  → 4 M15 candles print
  → dynamic_floor(H1) and dynamic_ceil(H1) get initial values
  → Compare to D prev_hi and D prev_lo:
    → If first H1's highs > D prev close → bullish open, likely building toward D high
    → If first H1's lows < D prev close → bearish open, likely building toward D low

HOUR 1-4 (first H4 candle completes):
  → H4_prev_hi / H4_prev_lo now set (from the first H4 of the day)
  → dynamic_floor(D) = avg of H4 lows so far (1 data point)
  → Low confidence, but direction established

HOUR 4-8 (second H4 candle):
  → dynamic_floor(D) = avg of 2 H4 lows → direction emerging
  → dynamic_ceil(D) = avg of 2 H4 highs → ceiling behaviour
  
  KEY MOMENT: Is the second H4's high > first H4's high?
    → YES: dynamic_ceil(D) rising → D is BUILDING ITS HIGH in the first half
    → NO:  dynamic_ceil(D) falling → D high may already be SET (from H4 #1)

HOUR 8-16 (H4 candles 3 and 4):
  → dynamic_floor(D) has 3-4 data points → reliable
  → dynamic_ceil(D) has 3-4 data points → reliable
  
  TYPICAL DAILY PATTERN:
    → H4 #1-2: Build toward daily high (ceil rising)
    → H4 #3-4: Pull back (ceil falling, floor falling)
    → H4 #5-6: Either rally (ceil rising again = daily HH attempt)
                or continue falling (daily low being built)

HOUR 16-24 (H4 candles 5 and 6):
  → By now: daily high and low are usually both identifiable
  → The dynamic averages show clearly:
    → Where the daily high was (the peak of dynamic_ceil)
    → Where the daily low was (the trough of dynamic_floor)
    → What leg the day is ending in (the final directional push)
```

### 7.3 Multi-Day Structural Classification

The per-day leg tracking feeds directly into multi-day structural classification:

```
DAY 1: D high = 1.2700, D low = 1.2620
DAY 2: D high = 1.2680, D low = 1.2640
        → D LH (1.2680 < 1.2700) and D HL (1.2640 > 1.2620)
        → Compression / inside day → range narrowing

DAY 3: D high = 1.2720, D low = 1.2600
        → D HH (1.2720 > 1.2700) and D LL (1.2600 < 1.2620)
        → Expansion / outside day → breakout

DAY 4: D high = 1.2710, D low = 1.2630
        → D LH (1.2710 < 1.2720) and D HL (1.2630 > 1.2600)
        → First failure to make HH → potential D CHoCH forming
        → ★ DETECTED INTRA-DAY: H4 up-leg failed to exceed D3's high
          → H4 dynamic ceiling flattened below 1.2720
          → Confirmed by H1 making LH sequence below 1.2720
          → EARLIEST SIGNAL: M15 dynamic ceiling < 1.2720 while M15 was in up-leg
            → Detected perhaps 6-8 hours before the day closed
```

---

## 8. The Unified Leg Dashboard

### 8.1 Table Specification

A dashboard showing the current leg state at every TF simultaneously:

```
┌─────┬───────────┬─────┬──────────────┬────────────┬───────────────┬────────────────┐
│ TF  │ Leg Dir   │ Leg#│ Building     │ Leg Ext.   │ vs Parent     │ Classification │
├─────┼───────────┼─────┼──────────────┼────────────┼───────────────┼────────────────┤
│ D   │ ▼ DOWN #2 │  2  │ W Low        │ 1.2600     │ > W prev_lo   │ W HL forming   │
│ H4  │ ▲ UP   #1 │  1  │ D High       │ 1.2680     │ < D prev_hi   │ D LH forming   │
│ H1  │ ▼ DOWN #3 │  3  │ H4 Low (HL)  │ 1.2635     │ > H4 prev_lo  │ H4 HL forming  │
│ M15 │ ▲ UP   #2 │  2  │ H1 High (LH) │ 1.2658     │ < H1 prev_hi  │ H1 LH forming  │
│ M5  │ ▲ UP   #4 │  4  │ M15 High     │ 1.2656     │ < M15 dyn_ceil│ Within M15 leg │
│ M1  │ ▼ DOWN #1 │  1  │ M5 Low (HL)  │ 1.2648     │ > M5 dyn_floor│ M5 HL forming  │
└─────┴───────────┴─────┴──────────────┴────────────┴───────────────┴────────────────┘

NARRATIVE: 
"Building D LH — H4 pushing up but capped below yesterday's high.
 H1 pulling back (leg #3 = deep pullback). M15 rallying within H1 pullback.
 If M15 fails to break H1 ceiling → H1 down continues → H4 HL at risk.
 If M15 breaks H1 ceiling → H1 resumes up → H4 HH attempt → still D LH unless it exceeds D prev_hi."

NEXT LEG EXPECTED:
  M1: UP (to continue M5 up-leg) — IMMINENT
  M5: DOWN (pullback) then UP (resume M15 push) — within 15-30min
  M15: DOWN (confirm H1 LH) then UP or DOWN decides H1 fate — within 1-2hrs
```

### 8.2 Signal Priority

The dashboard gives you a clear priority for which TF to watch:

```
ALWAYS WATCH THE TF WHERE THE DECISION POINT IS.

The "decision TF" is the lowest TF where the current leg determines
a CLASSIFICATION at a TF you trade from (usually H4 or D).

In the example above:
  → M15 is the decision TF
  → Because: M15 breaks H1 ceiling → determines H4 fate → determines D classification
  → Everything below M15 (M5, M1) is noise unless it cascades through M15
  → Everything above M15 is waiting for M15's outcome
```

---

## 9. Implementation — Pine Script Leg Tracker

### 9.1 Core Leg State Variables

```pine
// Per-TF leg tracking
var int    h4_leg_dir    = 0     // +1 = up, -1 = down, 0 = neutral
var int    h4_leg_num    = 0     // sequential leg number
var float  h4_leg_high   = na    // highest high in current leg
var float  h4_leg_low    = na    // lowest low in current leg
var float  h4_prev_leg_h = na    // previous leg's high
var float  h4_prev_leg_l = na    // previous leg's low
var string h4_building   = ""    // "D_HIGH" or "D_LOW"
var string h4_swing_cls  = ""    // "HH", "LH", "HL", "LL", ""

// Repeat for each TF: d_, h1_, m15_, m5_, m1_
```

### 9.2 Leg Transition Detection

```pine
// Using dynamic averages from spec 04a
// When dynamic ceiling direction changes → leg transition

detect_leg_transition(float dyn_ceil, float dyn_floor, float dyn_mid,
                      float prev_dyn_ceil, float prev_dyn_floor) =>
    
    bool ceil_was_rising  = prev_dyn_ceil > 0  // previous gradient
    bool ceil_now_falling = dyn_ceil < prev_dyn_ceil
    bool floor_was_falling = prev_dyn_floor < 0
    bool floor_now_rising  = dyn_floor > prev_dyn_floor
    
    // UP→DOWN transition: ceiling was rising, now falling
    bool up_to_down = ceil_was_rising and ceil_now_falling
    
    // DOWN→UP transition: floor was falling, now rising  
    bool down_to_up = floor_was_falling and floor_now_rising
    
    [up_to_down, down_to_up]
```

### 9.3 Swing Classification on Transition

```pine
// When UP→DOWN detected at H4 level:
if h4_up_to_down
    // Swing high confirmed at the peak of the up-leg
    h4_prev_leg_h := h4_leg_high  // save for next comparison
    
    // Classify
    h4_swing_cls := h4_leg_high > h4_prev_leg_h ? "HH" : "LH"
    
    // Compare to parent (Daily)
    string d_impact = ""
    if h4_leg_high > d_prev_hi
        d_impact := "D HH forming"
    else
        d_impact := "D LH forming"
    
    // Transition
    h4_leg_dir := -1  // now in down-leg
    h4_leg_num += 1
    h4_building := "D_LOW"
    h4_leg_high := na
    h4_leg_low := low
```

---

## 10. Integration — How Legs Connect to Entries

### 10.1 The Entry Timing Rule

```
ENTER WHEN:
  1. The parent TF classification is determined
     (e.g., D LH confirmed because H4 HH < D prev_hi)
  
  2. The first child-TF leg in the NEW direction begins
     (e.g., H4 DOWN-LEG starts after the D LH)
  
  3. The grandchild TF completes its first pullback in that direction
     (e.g., H1 makes first HL in the H4 down-leg)
  
  4. The execution TF (M5/M1) starts a new leg in the trade direction
     after the grandchild pullback
     (e.g., M5 UP-LEG starts → this is the entry for SHORT
      because the M5 up = H1 LH = the pullback you short from)

WAIT — that's a SELL entry on an M5 UP-LEG?
  YES. The M5 up-leg inside the H1 down-leg is the PULLBACK.
  You sell the top of the M5 up-leg = the H1 LH.
  Confirmed when: M5 up-leg transitions to M5 down-leg
                   = M5 dynamic ceiling breaks = ENTRY.
```

### 10.2 Leg Architecture Mapped to Trade Setup

```
TRADE: SHORT after D LH confirmation

LEG ARCHITECTURE:
  D:   DOWN-LEG resumes after D LH     ← your directional bias
  H4:  DOWN-LEG #1 (first new push)    ← your trade timeframe
  H1:  DOWN-LEG → UP-LEG → DOWN-LEG   ← your setup structure
       ↑ impulse   ↑ pullback  ↑ entry
  M15: tracks the H1 pullback progress ← your timing
  M5:  UP-LEG peak = the exact entry   ← your execution
       (M5 up-leg transitions to down = you enter short)

SL:  Above the H1 LH (the top of the H1 pullback up-leg)
TP1: Last H1 LL (nearest structural low)  
TP2: H4 swing low (the previous H4 down-leg's extreme)
TP3: D swing low (the Daily's previous low — full ride)
```

---

## 11. Summary

Every parent-TF swing is built from a specific sequence of child-TF legs. By tracking the current leg direction and number at every TF simultaneously, you always know: what you're building (parent high or low), what the classification will be (HH/LH/HL/LL depending on whether the current leg exceeds the parent's previous extreme), what legs must complete before the parent swing is confirmed, and where the liquidity targets sit for the next opposing leg.

The dynamic averages from Part A detect leg transitions in real time. Each transition simultaneously confirms a swing at the current TF and updates the building state at the parent TF. The cascade runs M1 → M5 → M15 → H1 → H4 → D → W → MN, with each level's transition providing progressively earlier detection of the parent event.

**The practical result:** you see a new Daily candle open, track 4–6 H4 legs building its high and low, classify each leg as it completes, and know whether the Daily will print HH/LH/HL/LL hours before the Daily candle closes — all from the mechanical cascade of child-TF dynamic average transitions.
