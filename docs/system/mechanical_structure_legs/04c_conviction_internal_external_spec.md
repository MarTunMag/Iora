# Conviction-Based Internal/External Structure — Unified Specification

**System:** Iora  
**Date:** March 2026  
**Unifies:** `04_period_level_structure_spec_v2.md` (dynamic averages), `04a_candle_type_price_source_analysis.md` (three-source envelope), `04b_leg_architecture_spec.md` (leg cascade), `03_internal_external_structure_spec_lines.md` (zone-based I/E)  
**Core insight:** The three-source envelope conviction level (weak / strong / pre) IS the internal/external classifier. They are the same thing, measured from different angles.

---

## 1. The Unification

### 1.1 The Problem with Separate Systems

The previous specs defined internal/external structure through two separate mechanisms:

1. **Geometric:** internal = current TF's zone chain; external = parent TF's zone boundary. Binary — either the break reaches the parent level or it doesn't.
2. **Conviction:** weak/strong/pre CHoCH based on how many of the three envelope sources (floor, mid, ceiling) confirm. A confidence score.

These were treated as independent layers. But they're measuring the same thing:

**A weak CHoCH doesn't reach the parent TF because it lacks the commitment (closes) and range (ceiling/floor) to get there. A strong CHoCH reaches the parent TF precisely because all three sources — support, commitment, and resistance — have shifted together.**

The conviction level *predicts* whether the break will propagate externally. It's not a separate filter — it's the early detector of internal vs external.

### 1.2 The Unified Rule

```
PRE-CHoCH   →  INTERNAL WARNING
               The current TF's leg is losing momentum.
               Closes stalling, but floor/ceiling intact.
               The leg hasn't reversed yet — this is the exhaustion phase.
               At the parent TF: nothing visible yet. No structural event.
               At the current TF: the swing extreme is being SET (not yet confirmed).

WEAK CHoCH  →  INTERNAL EVENT (sub-wave reversal, contained within current leg)
               Floor or ceiling breaks, but closes don't confirm.
               This is a wick/sweep — liquidity taken, but direction not committed.
               At the parent TF: noise. No propagation.
               At the current TF: sub-wave complete. New internal swing.
               In leg terms: the current leg has a pullback, but the leg continues.

STRONG CHoCH → EXTERNAL EVENT (leg transition, creates parent TF structure)
               Floor/ceiling breaks AND closes confirm AND gradient aligns.
               This is commitment — not just a wick, the market has decided.
               At the parent TF: new swing confirmed. HH/HL/LH/LL classification fires.
               At the current TF: leg transition. Previous leg's extreme becomes
               the confirmed swing. New leg begins in opposite direction.
               In leg terms: the leg is OVER. New leg starts. Parent TF gets a new data point.
```

### 1.3 Why This Works Mechanically

The three envelope sources map directly to the structural requirements for parent-TF propagation:

| Source | What it tracks | Why it matters for propagation |
|---|---|---|
| **avg(lows) = floor** | Where buyers defend. Structural support. | If the floor breaks, the support base is gone. But without close confirmation, it might be a stop-hunt that snaps back. |
| **avg(closes) = mid** | Where the market settles. Directional commitment. | The close is where orders are actually filled for the period. If closes haven't shifted, the "break" is a wick — institutions didn't commit. No commitment = no parent-TF structure change. |
| **avg(highs) = ceiling** | Where sellers defend. Structural resistance. | If the ceiling also shifts, both boundaries have moved. The entire range has relocated. This is a genuine structural transition, not just noise at one boundary. |

**For a parent-TF swing to form, the child TF must relocate its entire range — not just poke through one side.** That relocation is exactly what "all three sources confirm" means.

---

## 2. The Conviction-Structure Matrix

### 2.1 Full Classification

Every CHoCH event at child TF X can now be classified simultaneously by conviction AND structural significance:

| Floor (avg lows) | Mid (avg closes) | Ceiling (avg highs) | Conviction | Structural class | What it is | Leg impact |
|---|---|---|---|---|---|---|
| Intact | Stalling | Intact | **Pre** | Internal warning | Momentum fading within current leg | None yet — leg continues but watch closely |
| Intact | Stalling | Breaking | **Pre+** | Internal early | Ceiling pressure building but floor holds | Sub-wave high forming. Leg approaching turn. |
| Breaking | Stalling | Intact | **Pre−** | Internal early | Floor weakening but ceiling holds | Sub-wave low forming. Wick territory. |
| Breaking | Intact (same dir) | Intact | **Weak** | Internal event | Floor swept but commitment unchanged | Liquidity grab. Internal swing marked. Leg continues. |
| Intact | Reversing | Breaking | **Weak+** | Internal event | Ceiling broken with commitment but floor holds | Internal BOS at current TF. New sub-wave started. Leg continues in same direction. |
| Breaking | Reversing | Intact | **Weak−** | Internal event | Floor broken with commitment but ceiling holds | Internal CHoCH at current TF. Sub-wave reversed. But the leg's range hasn't relocated — not external. |
| Breaking | Reversing | Breaking | **Strong** | **External event** | All three shifted. Range relocated. | **Leg transition.** Swing confirmed. Parent TF receives new structural data point. |
| Breaking fast | Reversing fast | Breaking fast | **Strong+** | **External displacement** | Violent range relocation. Large candle, no overlap. | **Impulsive leg transition.** High-conviction parent event. Often follows liquidity sweep. |

### 2.2 The Gradient Dimension

Beyond binary "breaking/intact", the *rate of change* of each source adds resolution:

```
GRADIENT SCORING (per source):

  Accelerating:  current delta > previous delta (same direction)  → +2
  Steady:        current delta ≈ previous delta                   → +1
  Decelerating:  current delta < previous delta (same direction)  → 0
  Flat:          delta ≈ 0                                        → -1
  Reversing:     delta changes sign                               → -2

AGGREGATE GRADIENT SCORE = floor_score + mid_score + ceil_score
  Range: -6 (all three reversing hard) to +6 (all three accelerating)

  +4 to +6:  Impulsive — strong external event likely
  +1 to +3:  Trending — external event possible, building
  -1 to +1:  Transitioning — internal events, watch for resolution
  -3 to -1:  Fading — leg exhaustion, pre-CHoCH territory
  -6 to -3:  Reversing — strong CHoCH in progress, external event firing
```

### 2.3 How This Maps to Leg Architecture (from 04b)

| Gradient score | Leg state | Parent TF impact |
|---|---|---|
| +4 to +6 (accelerating) | Mid-leg impulse. Peak momentum. | Parent leg extending. Building parent swing extreme. |
| +1 to +3 (trending) | Leg in progress, steady. | Parent leg continuing. Normal structural building. |
| 0 (transition) | Leg peak or trough forming. | Parent swing extreme being SET (not yet confirmed). |
| -1 to -3 (fading) | Leg exhausting. Pre-CHoCH. | Parent swing extreme nearly set. Expect leg transition. |
| -4 to -6 (reversing) | Leg transition in progress. Strong CHoCH. | Parent swing CONFIRMED. Classification fires. New parent leg begins. |

---

## 3. Internal Structure Through Weak CHoCH — The Detail Layer

### 3.1 Why Weak CHoCH Is Valuable (Not Just Noise)

Previous specs treated weak CHoCH as "don't propagate, monitor only." That's correct for parent-TF purposes, but weak CHoCH events are extremely valuable for understanding the *internal* leg structure:

```
WEAK CHoCH WITHIN AN H4 UP-LEG:

H4 is in UP-LEG (building Daily high).
Inside this H4 up-leg, H1 candles are printing.

H1 WEAK CHoCH bearish fires:
  → H1 floor broke (some H1 candle's low dropped below avg H1 lows)
  → BUT H1 closes didn't confirm (avg closes still rising or flat)
  → This means: the H1 had a wick down, took some liquidity, but bounced

STRUCTURAL MEANING:
  → An H1 sub-wave low has been marked (internal swing low)
  → The H4 up-leg is still intact (closes didn't shift)
  → The weak CHoCH creates an H4 INTERNAL HL
    (H1 dipped but the H4 leg didn't transition)
  → This H4 internal HL = a support level within the H4 up-leg
  → If ANOTHER weak CHoCH fires lower → H4 internal LL → the up-leg is weakening
  → If the next weak CHoCH fires higher → H4 internal HL rising → up-leg is healthy

TRACKING THESE INTERNAL SWINGS:
  → Weak CHoCH #1: H4 internal HL at 1.2640
  → Weak CHoCH #2: H4 internal HL at 1.2655 (higher → healthy)
  → Weak CHoCH #3: H4 internal HL at 1.2650 (lower than #2 → first internal LH/LL warning)
  → Weak CHoCH #4: H4 internal HL at 1.2635 (below #1 → internal LL → H4 up-leg FAILING)
    → This sequence of degrading internal HLs → pre-CHoCH at H4 → D high nearly set
```

### 3.2 Internal Swing Counting from Weak CHoCH

Each weak CHoCH marks an internal swing. By counting and comparing them, you get the internal structure of the current leg:

```
DURING H4 UP-LEG:

  Weak CHoCH bearish events (floor breaks, closes don't confirm):
  → Each one = an H4 internal swing low (pullback within the up-leg)
  
  Between weak CHoCH events (floor holds, ceiling pushes):
  → Each push = an H4 internal swing high (extension within the up-leg)

  SEQUENCE OF INTERNAL SWINGS:
    int_hi #1: 1.2670  (first push)
    int_lo #1: 1.2640  (weak CHoCH — pullback)
    int_hi #2: 1.2685  (HH — push continues) 
    int_lo #2: 1.2655  (weak CHoCH — HL — healthy pullback)
    int_hi #3: 1.2700  (HH — push continues)
    int_lo #3: 1.2650  (weak CHoCH — LL relative to #2!)
    int_hi #4: 1.2690  (LH relative to #3!)
    
    → Internal structure: HH → HL → HH → HL → HH → LL → LH
    → The internal HH/HL sequence broke at int_lo #3 (internal LL)
    → Internal CHoCH at H4 level → the H4 up-leg's structure has shifted
    → NEXT: expect STRONG CHoCH at H1 (all three confirm) → H4 LEG TRANSITION
    → ★ The internal degradation PREDICTED the external event before it fired ★
```

### 3.3 The Internal-to-External Escalation Path

```
ESCALATION SEQUENCE:

1. INTERNAL HEALTH DEGRADES (weak CHoCH quality worsens)
   → Internal HLs become LLs
   → Internal HHs become LHs
   → The leg's internal structure has broken down
   → PREDICTION: strong CHoCH (external event) is 1-3 child candles away

2. PRE-CHoCH FIRES (closes stall)
   → The commitment layer has stopped progressing
   → The leg is exhausted but hasn't reversed
   → PREDICTION: strong CHoCH is 1-2 child candles away

3. WEAK CHoCH FIRES (floor/ceiling breaks, closes don't confirm)
   → Boundary tested but commitment didn't shift
   → Could snap back (the leg survives) or follow through
   → KEY TEST: does the next child candle's CLOSE confirm the break?
     → NO: leg survives. Internal event only. Reset.
     → YES: escalation continues to step 4

4. STRONG CHoCH FIRES (all three confirm)
   → ★ EXTERNAL EVENT ★
   → Leg transition at current TF
   → Parent TF swing confirmed
   → New leg begins
```

---

## 4. The Close Average as the Decision Maker

### 4.1 Why `avg(closes)` Is the Key Discriminator

The floor and ceiling tell you about *extremes* — where price reached. But the close tells you about *commitment* — where the market chose to settle. This distinction is the entire basis of the internal/external split:

```
SCENARIO: H1 candles within an H4 up-leg

H1 #1: high = 1.2680, close = 1.2665, low = 1.2640
H1 #2: high = 1.2695, close = 1.2670, low = 1.2620  ← low DROPPED (floor break)
H1 #3: high = 1.2700, close = 1.2675, low = 1.2635  ← low still low

avg(lows) = (1.2640 + 1.2620 + 1.2635) / 3 = 1.2632 — FALLING (floor breaking)
avg(highs) = (1.2680 + 1.2695 + 1.2700) / 3 = 1.2692 — RISING (ceiling intact)  
avg(closes) = (1.2665 + 1.2670 + 1.2675) / 3 = 1.2670 — RISING (commitment UP)

VERDICT: WEAK CHoCH bearish (floor broke) → INTERNAL EVENT
  → The low on H1 #2 was a wick/sweep (close came back to 1.2670)
  → Closes are still rising → the H4 up-leg is intact
  → The 1.2620 low = internal swing low = H4 internal HL
  → But the LEG hasn't transitioned → no parent (Daily) structural event

NOW IMAGINE H1 #4:
  high = 1.2660, close = 1.2635, low = 1.2615

avg(lows) = drops further → floor STILL breaking
avg(highs) = (1.2695 + 1.2700 + 1.2660) / 3 = 1.2685 — NOW FALLING (ceiling breaking too)
avg(closes) = (1.2670 + 1.2675 + 1.2635) / 3 = 1.2660 — NOW FALLING (commitment SHIFTED)

VERDICT: STRONG CHoCH bearish (all three breaking) → EXTERNAL EVENT
  → The close on H1 #4 committed to the lower level
  → Closes are now falling → the H4 up-leg is OVER
  → H4 swing high = 1.2700 (peak of the up-leg)
  → Daily high candidate = 1.2700
  → ★ LEG TRANSITION → H4 DOWN-LEG begins ★
```

### 4.2 The Close Average's Role in Each Conviction Level

| Conviction level | `avg(closes)` behaviour | What it means structurally |
|---|---|---|
| **Pre** | Stalling (delta → 0 after trending) | Market is still positioned directionally but new candles aren't adding commitment. The institutional flow is pausing. |
| **Weak** | Unchanged (still trending with the leg) | The boundary break was a probe. Smart money tested the level but didn't commit. Orders filled at the extreme but the majority of volume stayed with the existing direction. |
| **Strong** | Reversing (delta flips sign) | Institutional commitment has shifted. The close — where the actual settlement happens — has moved to the other side. This is where real volume transitioned. |
| **Strong+** | Reversing with acceleration | Not just shifting — accelerating in the new direction. Displacement. Imbalance. The strongest possible external signal. |

### 4.3 The Close Average as Internal Swing Filter

A powerful filtering rule emerges: **only count internal swings (from weak CHoCH) when `avg(closes)` has made a measurable move since the last internal swing.**

```
FILTERING RULE:

Internal swing low #1 marked at time T1, avg(closes) = 1.2670
  → avg(closes) rises to 1.2685 → meaningful commitment move → valid interval
  
Internal swing low #2 marked at time T2, avg(closes) = 1.2672
  → avg(closes) only moved 1.2670 → 1.2672 → barely changed
  → This is noise, not a real internal swing
  → FILTER OUT — don't count this as internal structure

THRESHOLD: 
  Valid internal swing interval = avg(closes) moved ≥ 0.3 × avg(envelope_width)
  Where envelope_width = avg(highs) - avg(lows)
  
  This scales automatically with volatility:
  → High volatility: wider envelope → larger close move needed → fewer internal swings
  → Low volatility: narrow envelope → smaller close move needed → more granular internal swings
```

---

## 5. Unified Leg + Conviction State Model

### 5.1 The Combined State Per TF

Merging the leg architecture (04b) with conviction-based I/E:

```
TF_UnifiedState:
    # Leg state (from 04b)
    leg_direction:      UP | DOWN
    leg_number:         int
    leg_high:           float
    leg_low:            float
    building:           PARENT_HIGH | PARENT_LOW
    
    # Dynamic envelope (from 04a)
    dynamic_floor:      float    (avg child lows)
    dynamic_mid:        float    (avg child closes)
    dynamic_ceil:       float    (avg child highs)
    envelope_width:     float    (ceil - floor)
    
    # Gradients
    floor_delta:        float    (change in floor since last child candle)
    mid_delta:          float    (change in mid)
    ceil_delta:         float    (change in ceil)
    gradient_score:     int      (-6 to +6)
    
    # Conviction state
    conviction:         PRE | WEAK | STRONG | NONE
    conviction_side:    BULLISH | BEARISH | NONE
    
    # Internal structure (tracked via weak CHoCH events)
    internal_swings:    array    (list of internal swing highs and lows within current leg)
    internal_trend:     HH_HL | LH_LL | MIXED    (internal swing sequence health)
    
    # External propagation
    external_event:     NONE | BOS | CHoCH
    parent_classification: HH | HL | LH | LL | PENDING
```

### 5.2 State Update Flow — Every Child Candle Close

```
ON EACH NEW CHILD CANDLE CLOSE AT TF X:

1. UPDATE ENVELOPE
   → Recalculate avg(lows), avg(closes), avg(highs)
   → Compute deltas (change from previous values)
   → Compute gradient score

2. ASSESS CONVICTION
   → Check floor/mid/ceil break conditions
   → Classify: PRE | WEAK | STRONG | NONE
   
3. IF CONVICTION = WEAK:
   → Mark internal swing at the leg extreme
   → Compare to previous internal swing → classify HH/HL/LH/LL internally
   → Update internal_trend
   → Check: is internal_trend degrading? (HH/HL → HL/LL → LH/LL)
     → If degrading: flag PRE-EXTERNAL WARNING
   → NO parent propagation

4. IF CONVICTION = STRONG:
   → LEG TRANSITION
   → Confirm swing at current TF (the leg's extreme)
   → Classify swing: HH/HL/LH/LL vs previous leg's swing
   → PROPAGATE TO PARENT:
     → Compare leg extreme to parent TF's previous swing
     → Update parent's building state
     → Classify parent event: HH/HL/LH/LL
   → Start new leg (flip direction, reset counters)
   → Clear internal swings (new leg = fresh internal structure)

5. IF CONVICTION = PRE:
   → Update gradient score
   → Flag: "leg exhaustion at TF X, strong CHoCH expected within N child candles"
   → Estimate N from gradient deceleration rate
   → NO parent propagation yet

6. UPDATE LEG TRACKING
   → Track leg_high, leg_low (max/min of child candles in this leg)
   → Update building state (what this leg creates at parent TF)
```

### 5.3 The Internal Health Monitor

The sequence of weak CHoCH events tells you the internal "health" of the current leg — and this health predicts external events:

```
INTERNAL HEALTH SCORING:

  Within the current leg, track internal swings from weak CHoCH events.
  Score the sequence:

  ALL internal swings trending WITH the leg:
    → UP-LEG: internal HLs rising, internal HHs rising
    → Score: HEALTHY
    → Prediction: leg continues. No external event expected.
    → Parent TF impact: building state strengthening.

  FIRST internal swing AGAINST the leg:
    → UP-LEG: first internal LL (a weak CHoCH low that's below the previous)
    → Score: FIRST CRACK
    → Prediction: leg may be approaching exhaustion.
    → Parent TF impact: swing extreme nearly set.

  MULTIPLE internal swings AGAINST the leg:
    → UP-LEG: internal LL followed by internal LH
    → Score: DEGRADING
    → Prediction: strong CHoCH (external event) is 1-3 child candles away.
    → Parent TF impact: prepare for leg transition.

  INTERNAL TREND FULLY REVERSED:
    → UP-LEG: internal swings now in LH/LL sequence (bearish internal structure)
    → Score: BROKEN
    → Prediction: strong CHoCH is imminent or already firing.
    → Parent TF impact: leg transition confirmed or about to confirm.
```

---

## 6. Reading the Full Picture — Worked Examples

### 6.1 Example: Building a Daily LH, Reading It From M15

```
CONTEXT:
  Daily was in DOWN-LEG (building Weekly low).
  H4 up-leg started (building next Daily high).
  The question: will this Daily high be a HH or LH?

TRACKING AT H1 LEVEL (child of H4):
─────────────────────────────────────────────────────────────

H1 candle #1 (inside H4 up-leg):
  Envelope: floor rising, mid rising, ceiling rising
  Gradient: +5 (accelerating)
  Conviction: NONE (all trending, no breaks)
  Internal: no swings yet (first candle of leg)
  → H4 up-leg building. Strong start.

H1 candle #2:
  Envelope: floor rising, mid rising, ceiling rising
  Gradient: +4 (steady)
  Conviction: NONE
  Internal: no swings
  → H4 continues building upward.

H1 candle #3:
  Envelope: floor DROPS slightly, mid rising, ceiling rising
  Gradient: +2 (floor decelerated)
  Conviction: WEAK bearish (floor broke, mid didn't confirm)
  Internal: first internal swing low marked at H1 #3's low
  → H4 internal HL #1 created. Pullback within the up-leg.
  → H4 up-leg INTACT (mid still rising = no external event).

H1 candle #4:
  Envelope: floor recovering, mid rising, ceiling rising
  Gradient: +3 (recovering)
  Conviction: NONE (floor back above average)
  Internal: H1 #4's high = internal swing high → HH (above #2's high)
  → Healthy internal structure. H4 up-leg resumes after pullback.

H1 candle #5:
  Envelope: floor slight drop, mid rising, ceiling FLAT
  Gradient: +1 (ceiling stalling)
  Conviction: PRE bearish (ceiling flattening, mid stalling)
  Internal: —
  → ★ PRE-CHoCH WARNING ★
  → H4 up-leg's ceiling has stopped expanding. Exhaustion approaching.
  → The H4 high may be near its peak.
  → CHECK: H4 leg_high vs Daily prev_hi
    → H4 leg_high = 1.2690, Daily prev_hi = 1.2720
    → Gap: 30 pips. The H4 up-leg hasn't reached the Daily's last high.
    → IF the up-leg exhausts here → DAILY LH (failed to reach 1.2720)

H1 candle #6:
  Envelope: floor DROPS, mid DROPS, ceiling DROPS
  Gradient: -4 (all three reversing)
  Conviction: STRONG bearish (all three confirm)
  Internal: internal LL (below #3's low) — but this isn't just internal anymore
  → ★ EXTERNAL EVENT: H4 LEG TRANSITION ★
  → H4 swing high CONFIRMED at 1.2690 (peak of H1 #4)
  → H4 swing high 1.2690 < Daily prev_hi 1.2720
  → ★ DAILY LH CONFIRMED ★
  → H4 now enters DOWN-LEG → building next Daily low

THE CONVICTION PROGRESSION TOLD THE STORY:
  Candle #1-2: NONE (leg building, no events)
  Candle #3:   WEAK (internal pullback, leg intact)
  Candle #5:   PRE (exhaustion warning, leg approaching end)
  Candle #6:   STRONG (leg over, external event fires)

  You knew at candle #5 (PRE) that the Daily LH was likely,
  because the H4 leg_high (1.2690) hadn't reached Daily prev_hi (1.2720)
  and the ceiling had stopped expanding.
```

### 6.2 Example: Internal Degradation Predicting External Event

```
CONTEXT:
  H4 down-leg in progress (building Daily low).
  Monitoring H1 conviction for the H4 leg transition.

H1 INTERNAL SWING TRACKING WITHIN H4 DOWN-LEG:
─────────────────────────────────────────────────────────────

Phase 1 — Healthy internal structure:
  Weak CHoCH #1 (bullish): internal HL at 1.2640  
  Push down: internal LL at 1.2610
  Weak CHoCH #2 (bullish): internal HL at 1.2625  ← HL BELOW #1 → internal LL!
  
  → ★ FIRST CRACK: internal HL at 1.2625 < previous HL at 1.2640 ★
  → The pullback highs within the H4 down-leg are GETTING LOWER
  → Wait — that's expected in a down-leg (LH sequence internally)
  → Internal health: NORMAL for a down-leg (LH/LL = with-trend)

Phase 2 — Internal structure shifts:
  Push down: new low at 1.2590
  Weak CHoCH #3 (bullish): internal high at 1.2630  ← HIGHER than #2 (1.2625)!
  
  → ★ FIRST CRACK (for real): internal HH at 1.2630 > previous LH at 1.2625 ★
  → The pullback high EXCEEDED the previous pullback high
  → Internal structure within the H4 down-leg has printed HH
  → Internal trend: was LH/LL (with-trend) → now showing HH → MIXED

Phase 3 — Internal degradation:
  Push down: new low at 1.2600 ← HIGHER than previous low 1.2590!
  
  → Internal HL: 1.2600 > 1.2590
  → Internal HH: 1.2630 > 1.2625
  → Internal structure is now HH/HL = BULLISH internally
  → But H4 leg is DOWN → internal structure OPPOSES the leg direction
  → Internal health: DEGRADING
  → ★ PREDICTION: strong CHoCH (H4 leg transition) within 1-3 H1 candles ★

Phase 4 — Strong CHoCH fires:
  H1 candle: high = 1.2650 (breaks above all recent H1 highs)
  Envelope: floor RISING, mid RISING, ceiling RISING
  Gradient: +5
  Conviction: STRONG bullish
  
  → ★ EXTERNAL EVENT: H4 LEG TRANSITION (DOWN → UP) ★
  → H4 swing low confirmed at 1.2590
  → H4 classification: H4 HL (1.2590 > prev H4 swing low 1.2550)
  → Now building: next Daily high (H4 up-leg begins)

THE INTERNAL DEGRADATION PREDICTED THIS:
  Phase 1: internal LH/LL (normal for down-leg)     → "leg is healthy"
  Phase 2: first internal HH (counter-trend)         → "first crack"
  Phase 3: internal HH/HL (counter-trend trend)      → "leg is failing — 1-3 candles to transition"
  Phase 4: strong CHoCH fires                        → "confirmed, as predicted"
  
  The internal health monitor gave you 2-3 candles of warning
  before the external event fired.
```

---

## 7. The Conviction Cascade — Multi-TF Conviction Propagation

### 7.1 How Conviction at One Level Affects the Level Above

Conviction doesn't just classify events — it cascades. A strong CHoCH at M15 becomes the input that shifts the conviction assessment at H1:

```
M15 STRONG CHoCH bullish fires:
  → M15 leg transitions: DOWN → UP
  → M15 is now in UP-LEG
  → This FEEDS INTO H1's envelope calculation:
    → The next M15 candle that closes (as part of the H1 computation)
      will have a higher close, higher low, potentially higher high
    → H1's dynamic_mid (avg M15 closes) SHIFTS UPWARD
    → H1's dynamic_floor (avg M15 lows) SHIFTS UPWARD
  → IF this shift is enough to move H1 from WEAK/PRE to STRONG:
    → H1 STRONG CHoCH fires → H4 structural event
  → IF this shift only moves H1 to WEAK:
    → H1 internal swing marked → H4 internal HL/LH
    → H4 leg continues, with updated internal health
```

### 7.2 The Conviction Propagation Table

| Child TF conviction | Effect on parent envelope | Parent conviction likely to become... | Structural result |
|---|---|---|---|
| Child STRONG (with-trend to parent leg) | Parent mid accelerates, floor/ceil push further | Parent NONE or remains in-leg | Parent leg extends. Building state strengthens. |
| Child STRONG (counter-trend to parent leg) | Parent mid shifts against leg, floor or ceil breaks | Parent WEAK → possibly STRONG | Parent internal swing first (WEAK). If multiple children do this, escalates to STRONG. |
| Child WEAK (with-trend to parent leg) | Parent mid slightly extends | Parent NONE | Noise at child level. Parent unaffected. |
| Child WEAK (counter-trend to parent leg) | Parent mid stalls or shifts slightly | Parent PRE | Parent leg momentum fading. Not yet a structural event. |
| Child PRE (counter-trend) | Parent barely affected | Parent NONE | Too early for parent impact. Monitoring only. |

### 7.3 Multi-TF Conviction Snapshot

At any moment, reading conviction at every TF gives you the full structural story:

```
┌─────┬────────────┬──────────┬────────────────┬──────────────────────────────────┐
│ TF  │ Leg Dir    │ Convict. │ Internal Hlth  │ Reading                          │
├─────┼────────────┼──────────┼────────────────┼──────────────────────────────────┤
│ D   │ ▼ DOWN #2  │ NONE     │ LH/LL (ok)     │ D down-leg healthy, building W   │
│ H4  │ ▲ UP   #1  │ PRE ↓    │ HH/HL→LH (!)   │ H4 up-leg exhausting.            │
│     │            │          │                │ D LH likely (H4 hi < D prev_hi)  │
│ H1  │ ▼ DOWN #3  │ WEAK ↑   │ LL/LH→HL (!)   │ H1 down internals degrading.     │
│     │            │          │                │ H4 leg transition 1-3 candles.    │
│ M15 │ ▲ UP   #2  │ STRONG ↑ │ HH/HL (new)    │ M15 strong bullish. Feeding H1.  │
│     │            │          │                │ May break H1 ceiling → H1 CHoCH. │
│ M5  │ ▲ UP   #4  │ NONE     │ HH/HL (ok)     │ M5 up-leg steady, building M15.  │
│ M1  │ ▲ UP   #2  │ NONE     │ HH/HL (ok)     │ M1 up-leg steady, building M5.   │
└─────┴────────────┴──────────┴────────────────┴──────────────────────────────────┘

NARRATIVE:
"The M15 just fired a strong CHoCH bullish — this is the catalyst.
 It's feeding upward into H1, whose internal structure was already degrading
 (the down-leg's internal LH/LL had shifted to HL — counter-trend internals).
 H1 has WEAK bullish conviction now. One more confirming M15 candle
 could push H1 to STRONG → H4 leg transition.
 
 H4 is already showing PRE bearish (its up-leg is exhausting).
 But wait — H4 PRE is about the UP-leg exhausting, while the H1 conviction
 is bullish. That's actually consistent: the H4 up-leg is ending,
 and the H1 strong bullish CHoCH IS what confirms the H4 high.
 
 H4 high = the peak of the H4 up-leg = this H4 candle's high.
 H4 high < D prev_hi → Daily LH.
 
 Once H1 fires STRONG (confirming H4 leg transition):
 → H4 DOWN-LEG begins
 → Daily high is SET at H4 leg_high
 → Daily LH CONFIRMED
 → New H4 down-leg builds toward next Daily low"
```

---

## 8. Pine Script — Unified Conviction + Internal/External

### 8.1 The Core Assessment Function

```pine
// Unified conviction assessment — called on each child candle close
// Returns conviction level and internal/external classification

assess_conviction(float floor, float mid, float ceil,
                  float prev_floor, float prev_mid, float prev_ceil,
                  float child_low, float child_high, float child_close,
                  int leg_dir) =>
    
    // Deltas
    float fd = floor - prev_floor        // floor movement
    float md = mid - prev_mid            // mid movement  
    float cd = ceil - prev_ceil          // ceiling movement
    
    // Break detection
    bool floor_break = child_low < floor
    bool ceil_break  = child_high > ceil
    
    // Direction check relative to leg
    bool mid_with_leg    = (leg_dir > 0 and md > 0) or (leg_dir < 0 and md < 0)
    bool mid_against_leg = (leg_dir > 0 and md < 0) or (leg_dir < 0 and md > 0)
    bool mid_stalling    = math.abs(md) < math.abs(prev_mid) * 0.3
    
    // Conviction assessment
    string conviction = "NONE"
    string struct_class = "NONE"
    
    // Check for bearish signals (in a bullish leg)
    if leg_dir > 0
        if floor_break and mid_against_leg and cd < 0
            conviction := "STRONG"
            struct_class := "EXTERNAL"
        else if floor_break and not mid_against_leg
            conviction := "WEAK"
            struct_class := "INTERNAL"
        else if mid_stalling and not floor_break and cd <= 0
            conviction := "PRE"
            struct_class := "INTERNAL_WARNING"
    
    // Check for bullish signals (in a bearish leg)
    if leg_dir < 0
        if ceil_break and mid_against_leg and fd > 0
            conviction := "STRONG"
            struct_class := "EXTERNAL"
        else if ceil_break and not mid_against_leg
            conviction := "WEAK"
            struct_class := "INTERNAL"
        else if mid_stalling and not ceil_break and fd >= 0
            conviction := "PRE"
            struct_class := "INTERNAL_WARNING"
    
    // Gradient score
    int g_floor = fd > 0 ? (fd > prev_floor ? 2 : 1) : (fd < 0 ? (fd < prev_floor ? -2 : -1) : 0)
    int g_mid   = md > 0 ? (md > prev_mid   ? 2 : 1) : (md < 0 ? (md < prev_mid   ? -2 : -1) : 0)
    int g_ceil  = cd > 0 ? (cd > prev_ceil  ? 2 : 1) : (cd < 0 ? (cd < prev_ceil  ? -2 : -1) : 0)
    int gradient = g_floor + g_mid + g_ceil
    
    [conviction, struct_class, gradient]
```

### 8.2 Internal Health Tracker

```pine
// Track internal swings within current leg from weak CHoCH events
var float[] int_swing_highs = array.new_float(0)
var float[] int_swing_lows  = array.new_float(0)
var string  int_health      = "HEALTHY"

// On WEAK CHoCH in an up-leg (floor broke, internal swing low):
if conviction == "WEAK" and leg_dir > 0
    float new_low = child_low
    if array.size(int_swing_lows) > 0
        float prev_low = array.get(int_swing_lows, array.size(int_swing_lows) - 1)
        if new_low < prev_low
            // Internal LL in an up-leg = first crack
            int_health := int_health == "HEALTHY" ? "FIRST_CRACK" : "DEGRADING"
        else
            // Internal HL = healthy pullback
            int_health := int_health == "FIRST_CRACK" ? "RECOVERING" : int_health
    array.push(int_swing_lows, new_low)

// On STRONG CHoCH → leg transition → reset internals
if conviction == "STRONG"
    array.clear(int_swing_highs)
    array.clear(int_swing_lows)
    int_health := "HEALTHY"
```

---

## 9. Decision Framework — Putting It All Together

### 9.1 The Unified Signal Hierarchy

| Signal | Source | Structural meaning | Trading action |
|---|---|---|---|
| **PRE at execution TF** | avg(closes) stalling at M15/H1 | Current leg approaching exhaustion. Swing extreme nearly set. | Prepare. Calculate levels. Set alerts. |
| **Weak CHoCH at execution TF** | Floor/ceil breaks, closes don't confirm | Internal swing within current leg. Liquidity taken. | Mark internal level. Check internal health sequence. |
| **Internal health DEGRADING** | Sequence of weak CHoCH events shows counter-trend internals | The current leg's structure is breaking down from inside. External event predicted 1-3 candles. | High alert. Position sizing ready. Entry orders queued. |
| **Strong CHoCH at execution TF** | All three envelope sources confirm | Leg transition. External event. Parent TF swing confirmed. | Confirm classification (HH/HL/LH/LL). Check if parent event creates entry. |
| **Strong CHoCH + parent propagation** | Strong CHoCH at child exceeds parent period level | Multi-TF alignment. Structural shift at parent confirmed through child. | Execute entry if setup conditions met. |
| **Strong CHoCH + zone confirmation** | Strong CHoCH aligns with zone-based classification from spec 03 | Highest conviction. Three detection layers agree. | Full position. Highest conviction entry. |

### 9.2 What You Now Know at Every Moment

With conviction-based I/E tracking running at every TF, you can answer these questions mechanically:

```
"What is the internal health of the current H4 up-leg?"
→ Read H1 internal health: HEALTHY | FIRST_CRACK | DEGRADING | BROKEN

"Is the Daily going to make a HH or LH?"
→ Compare H4 leg_high to D prev_hi
→ Check H1 conviction: if PRE/DEGRADING with H4 leg_high < D prev_hi → D LH likely
→ If H1 NONE/HEALTHY with H4 leg_high approaching D prev_hi → D HH still possible

"When will the H4 leg transition?"
→ If H1 internal health = DEGRADING → 1-3 H1 candles
→ If H1 conviction = PRE → 1-2 H1 candles
→ If H1 conviction = WEAK → could snap back, but transition approaching
→ If H1 conviction = NONE, health = HEALTHY → leg continues, no transition expected

"Is this H1 pullback just internal or is the H4 leg over?"
→ H1 conviction = WEAK → internal. H4 leg continues. This is an H4 internal HL.
→ H1 conviction = STRONG → external. H4 leg OVER. This is the H4 swing extreme confirmation.

"Should I enter now or wait?"
→ If M15 STRONG + H1 internal health DEGRADING + H4 PRE → setup building, almost ready
→ If H1 STRONG fires → confirm H4 classification → entry on next M15 pullback
→ If only M15 WEAK → too early, internal event only. Wait.
```

---

## 10. Summary

The three-source envelope (avg lows, avg closes, avg highs) doesn't just measure confidence — it classifies every structural event as internal or external. The close average is the discriminator: if closes confirm the break, it's external (leg transition, parent TF receives structural event). If closes don't confirm, it's internal (sub-wave pullback within the current leg, parent TF unaffected).

By tracking the *sequence* of internal swings from weak CHoCH events, you monitor the health of each leg from inside — and when internal structure degrades (counter-trend HH/HL appearing inside a bearish leg, or LH/LL appearing inside a bullish leg), you predict the external event 1–3 child candles before it fires.

The conviction cascade propagates upward: child-TF strong CHoCH shifts the parent's envelope values, which may push the parent from WEAK to STRONG, creating a chain reaction through the timeframes. The speed of this cascade — M1 strong CHoCH → shifts M5 envelope → M5 strong CHoCH → shifts M15 envelope → ... → H4 structural event — gives you the earliest possible mechanical confirmation of parent-TF swings while naturally filtering out noise (weak CHoCH) from signal (strong CHoCH).
