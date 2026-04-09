# Internal / External Structure via Period High/Low Breaks — Iora Specification

**System:** Iora  
**Date:** March 2026  
**Status:** Specification — ready for implementation + bar-replay validation  
**Prerequisite indicator:** `iora_bos_choch.pine` (Iora Structure Levels)  
**Supersedes:** Lookback-window swing detection (UAlgo `len=8`/`len=30`)  
**Complements:** `03_internal_external_structure_spec_lines.md` (zone-based approach)

---

## 0. Design Intent

The zone-based internal/external spec (`03`) defines structure through colour-flip zone chains. That approach is powerful but requires zone computation before structure can be assessed.

This spec defines **two faster layers** that use nothing but raw candle data to detect structural shifts at the earliest mechanically possible moment:

| Layer | Input | Confirms | Speed |
|---|---|---|---|
| **Intra-period dynamic average** (§A) | Rolling avg of child-TF highs/lows within current parent period | Structural direction change *before the parent candle closes* | Fastest — fires mid-candle |
| **Period-level structure** (§1–§5) | Raw prev-period high/low | Structural shift once a full period level breaks | Fast — fires on the break candle |
| **Zone-based structure** (spec 03) | Zone chain comparison | Zone-classified swing with full context | Slightly later — requires zone creation + classification |

Intra-period detects the shift while the candle is still forming. Period-level confirms it once the level breaks. Zone-based confirms with richer context. Three layers, fastest to most precise.

---

# PART A — INTRA-PERIOD DYNAMIC AVERAGE DETECTION

## A.1. The Core Idea

Every parent-TF candle is built from a fixed number of child-TF candles:

| Parent TF | Child TF | Children per parent | Rolling window |
|---|---|---|---|
| M5 | M1 | 5 | avg of last 5 M1 candle lows/highs |
| M15 | M5 | 3 | avg of last 3 M5 candle lows/highs |
| H1 | M15 | 4 | avg of last 4 M15 candle lows/highs |
| H4 | H1 | 4 | avg of last 4 H1 candle lows/highs |
| D | H4 | 6 | avg of last 6 H4 candle lows/highs |
| W | D | 5 | avg of last 5 D candle lows/highs |

As the child candles print within a parent period, you can compute a **rolling average of the child candle lows** (the "dynamic floor") and a **rolling average of the child candle highs** (the "dynamic ceiling").

When price is trending up within the parent period, each child candle's low tends to be higher than the previous — the avg-low is rising. The moment a new child candle's low breaks *below* this rising average → the upward structural momentum within that parent period has broken. That is the **earliest possible CHoCH signal** at the parent TF level — detected before the parent candle even closes.

## A.2. The Dynamic Floor and Ceiling

### A.2.1 Definitions

For a parent TF P with child TF C (where N child candles build one parent candle):

```
dynamic_floor(P)  = rolling average of the last N child-TF candle LOWS
dynamic_ceil(P)   = rolling average of the last N child-TF candle HIGHS
```

These values update on every new child-TF candle close.

### A.2.2 What They Represent

| Metric | When rising | When falling | When flat |
|---|---|---|---|
| `dynamic_floor` | Bullish momentum inside P — each child candle's low is higher than prior lows. The parent TF is building an upward leg. | Bearish pressure inside P — child candle lows are dropping. The parent TF's upward leg is failing. | Consolidation — no directional bias inside P. |
| `dynamic_ceil` | Continued push higher — child candle highs keep expanding. | Bearish momentum inside P — each child high is lower. The parent TF is building a downward leg. | Resistance holding — price capped. |

### A.2.3 The Intra-Period CHoCH Signal

**Bullish-to-bearish CHoCH (within parent period P):**

```
CONDITIONS:
  1. dynamic_floor(P) has been rising for ≥2 consecutive child candles
     (i.e., child_lo[0] > child_lo[1] > child_lo[2] — building HL sequence)
  2. New child candle closes with low < dynamic_floor(P)
     (the rising floor is broken)

SIGNAL: Intra-period CHoCH bearish at parent TF P
MEANING: The structural momentum that was building P's bullish leg has broken.
         P is now more likely to print a high-side reversal (LH or swing high).
```

**Bearish-to-bullish CHoCH (within parent period P):**

```
CONDITIONS:
  1. dynamic_ceil(P) has been falling for ≥2 consecutive child candles
     (i.e., child_hi[0] < child_hi[1] < child_hi[2] — building LH sequence)
  2. New child candle closes with high > dynamic_ceil(P)
     (the falling ceiling is broken)

SIGNAL: Intra-period CHoCH bullish at parent TF P
MEANING: The structural momentum that was building P's bearish leg has broken.
         P is now more likely to print a low-side reversal (HL or swing low).
```

### A.2.4 Why Average and Not Just "Lowest Low"

Using the average rather than just tracking the lowest single child-candle low provides two advantages:

1. **Noise filtering.** A single anomalous M1 wick doesn't break the dynamic floor — it takes enough child candles pulling the average down to trigger the signal. The average naturally smooths out single-candle noise without any lag parameter.

2. **Momentum encoding.** The average captures the *rate* of structural change. If 4 out of 5 M1 candles have rising lows and only 1 dips, the average stays up. If 3 out of 5 have falling lows, the average drops — signalling that the majority of the child candles within this parent period are printing bearish structure.

3. **Parameter-free.** The window size isn't arbitrary — it's the natural child-to-parent ratio (5 for M5, 3 for M15, 4 for H1, etc.). No tuning required.

## A.3. The Directional Gradient

Beyond the simple CHoCH signal, the *slope* of the dynamic floor/ceiling gives gradient information:

```
floor_gradient = (dynamic_floor[current] - dynamic_floor[prev_child]) / dynamic_floor[prev_child]
ceil_gradient  = (dynamic_ceil[current] - dynamic_ceil[prev_child]) / dynamic_ceil[prev_child]
```

| floor_gradient | ceil_gradient | Interpretation |
|---|---|---|
| Positive & rising | Positive & rising | Strong bullish momentum — impulsive move up |
| Positive & flattening | Positive & flattening | Bullish exhaustion — approach expected swing high |
| Turns negative | Still positive | CHoCH signal — floor broken while ceiling holds. Swing high likely confirmed. |
| Negative & falling | Negative & falling | Strong bearish momentum — impulsive move down |
| Negative & flattening | Negative & flattening | Bearish exhaustion — approach expected swing low |
| Still negative | Turns positive | CHoCH signal — ceiling broken while floor holds. Swing low likely confirmed. |

This gradient is not a separate indicator — it's a derived property of the dynamic floor/ceiling that provides confidence weighting on the CHoCH signal.

## A.4. Cascading the Intra-Period Signal Upward

The intra-period CHoCH at one level feeds into the next level up, creating a cascade that's even faster than the period-level cascade:

```
INTRA-PERIOD CASCADE (Bottom-Up):

M1 candle prints
  → Updates dynamic_floor(M5) and dynamic_ceil(M5)
    → IF dynamic_floor(M5) breaks downward:
      → M5 intra-period CHoCH bearish
        → This M5 candle (still forming!) is likely to close bearish
          → Updates dynamic_floor(M15) on M5 close
            → IF dynamic_floor(M15) breaks downward:
              → M15 intra-period CHoCH bearish
                → Updates dynamic_floor(H1) on M15 close
                  → IF dynamic_floor(H1) breaks downward:
                    → H1 intra-period CHoCH bearish
                      → H4 structural shift is beginning
                        → DETECTED WHILE H4 CANDLE IS IN ITS FIRST HOUR
```

**The key timing advantage:** The period-level approach (Part B) requires the full M5 period to close before checking if `M5_prev_hi` is broken. The intra-period approach detects the structural shift *within* that M5 period, potentially 2–4 M1 candles before the M5 close.

## A.5. Combining Intra-Period with Period-Level

| Signal | What fires | When | Confidence | Action |
|---|---|---|---|---|
| **Intra-period CHoCH** | Dynamic floor/ceiling breaks within parent period | Before parent candle closes | Lower — the parent candle might recover | **Alert** — begin monitoring. Prepare for entry. |
| **Period-level break** | Child TF breaks parent's prev-period high/low | After parent candle has closed and new period begins | Medium — objective level broken | **Confirm** — structural shift confirmed at this TF. |
| **Period-level break + parent propagation** | Break exceeds grandparent level | Same bar as period-level break | High — multi-TF alignment | **Confirm + escalate** — structural shift at parent TF. |
| **Zone-based confirmation** | Zone forms and classifies consistently | After zone creation + classification | Highest — full context | **Execute** — enter the trade. |

### A.5.1 The Typical Sequence in Real Time

```
T+0:   M1 candle prints with low < dynamic_floor(M5)
        → ALERT: M5 intra-period CHoCH bearish
        → "The M5 candle that's currently forming is likely printing a bearish swing"

T+2m:  Next M1 confirms — dynamic_floor(M5) continues falling
        → STRENGTHEN: Intra-period signal not reversed

T+5m:  M5 candle closes. New M5 opens.
        → PERIOD-LEVEL: M5_prev_lo is now set. Watch for break.

T+8m:  M5 low breaks M5_prev_lo
        → CONFIRM: M5 LL (or HL) confirmed via period-level break
        → CHECK PARENT: Does this break exceed M15_prev_lo?
          → If yes: M15 structural event confirmed early

T+15m: M15 candle closes. Zone forms.
        → ZONE CONFIRM: Zone classified as LL/HL with full context
        → FULL ALIGNMENT: Intra-period + period-level + zone all agree
        → ENTRY MECHANICS ENGAGE
```

## A.6. Identifying HH / HL / LH / LL Intra-Period

The dynamic averages don't just detect CHoCH — they classify the parent TF's structural swing type in real time:

### A.6.1 When a New Parent Period Opens

At the open of each new parent TF period, compare the child candle behaviour to the *previous* parent period's swing:

```
NEW H1 PERIOD OPENS (also coincides with M15 and potentially M5/H4/D opens):

Previous H1 period stats:
  prev_H1_hi = 1.2680 (the high of last H1 candle)
  prev_H1_lo = 1.2620 (the low of last H1 candle)
  prev_swing_hi = 1.2700 (last confirmed H1 swing high)
  prev_swing_lo = 1.2600 (last confirmed H1 swing low)

As new M15 candles print within this H1:
  Track dynamic_floor(H1) = avg of M15 lows
  Track dynamic_ceil(H1)  = avg of M15 highs

CLASSIFICATION (as data accumulates):
  IF dynamic_ceil(H1) > prev_H1_hi AND rising
    → This H1 is making a HIGHER HIGH relative to last H1
    → IF prev_swing_hi was already a HH: continuation (BOS pattern)
    → IF prev_swing_hi was a LH: this is a CHoCH (HH breaking the LH sequence)

  IF dynamic_floor(H1) > prev_H1_lo AND rising
    → This H1's low is forming ABOVE last H1's low
    → HIGHER LOW forming — bullish structure

  IF dynamic_ceil(H1) < prev_H1_hi AND falling
    → This H1 is failing to exceed last H1's high
    → LOWER HIGH forming — bearish structure

  IF dynamic_floor(H1) < prev_H1_lo AND falling
    → This H1's low is dropping BELOW last H1's low
    → LOWER LOW forming — bearish continuation
```

### A.6.2 The Multi-TF Open Confluence

When multiple parent TFs open simultaneously (e.g., a new H1 that also starts a new H4, or a new D that also starts a new W), you can classify at multiple levels from the very first child candles:

```
MONDAY 00:00 GMT — New D, new W (if Monday), potentially new MN/QT

First M15 candle prints:
  → Updates dynamic_floor(H1) — but only 1 data point, low confidence
  → No H1 classification yet

First H1 closes (01:00):
  → dynamic_floor(H4) gets first data point
  → dynamic_floor(D) gets first data point
  → H1 candle high/low compared to prev H1 → preliminary H1 classification

Second H1 closes (02:00):
  → dynamic_floor(H4) = avg of 2 H1 lows → direction emerging
  → IF both H1 lows are > prev_H4_lo: early signal of H4 HL forming
  → IF both H1 lows are < prev_H4_lo: early signal of H4 LL forming

Third H1 closes (03:00):
  → dynamic_floor(H4) = avg of 3 H1 lows → trend clearer
  → Now have enough data to detect intra-period CHoCH at H4
  → IF first 2 H1 lows were rising, but 3rd breaks below average:
    → H4 intra-period CHoCH — the bullish momentum within this H4 is failing
```

### A.6.3 Complete Classification Table

| dynamic_ceil vs prev period | dynamic_floor vs prev period | Classification | Structural meaning |
|---|---|---|---|
| Rising above prev_hi | Rising above prev_lo | **HH forming** | Strong bullish — new swing high exceeding previous, supported by higher lows |
| Rising above prev_hi | Flat or near prev_lo | **HH forming (weak support)** | Bullish extension but floor not confirmed — could be a wick/sweep |
| Flat or below prev_hi | Rising above prev_lo | **HL forming** | Bullish pullback — low is higher but high hasn't exceeded → potential continuation |
| Falling below prev_hi | Rising above prev_lo | **HL forming (compression)** | Contracting range — coiling for breakout. Direction TBD by which side breaks first |
| Falling below prev_hi | Falling below prev_lo | **LL forming** | Strong bearish — new swing low below previous, with lower highs confirming |
| Falling below prev_hi | Flat or near prev_lo | **LH forming** | Bearish — high failing to reach previous, low holding → distributing |
| Rising above prev_hi | Falling below prev_lo | **Outside bar / expansion** | Both sides exceeded — volatile. Wait for resolution. Classification from the close side. |
| Flat near prev_hi | Flat near prev_lo | **Inside bar / compression** | No structural change yet. Indecision. |

## A.7. Pine Script Implementation — Intra-Period Averages

### A.7.1 Core Function

```pine
//@version=6

// Dynamic floor/ceiling for a parent TF using child-TF candles
// N = number of child candles per parent period (5 for M5, 3 for M15, etc.)

dynamic_structure(string parent_tf, int N) =>
    bool new_parent = ta.change(time(parent_tf)) != 0
    
    // Rolling arrays of child candle highs and lows within current parent period
    var float[] child_highs = array.new_float(N, na)
    var float[] child_lows  = array.new_float(N, na)
    var int     child_count = 0
    
    if new_parent
        // Reset for new parent period
        child_count := 0
        for i = 0 to N - 1
            array.set(child_highs, i, na)
            array.set(child_lows, i, na)
    
    // Shift and add new child candle data
    if child_count < N
        array.set(child_highs, child_count, high)
        array.set(child_lows, child_count, low)
        child_count += 1
    else
        // Slide window: drop oldest, add newest
        for i = 0 to N - 2
            array.set(child_highs, i, array.get(child_highs, i + 1))
            array.set(child_lows, i, array.get(child_lows, i + 1))
        array.set(child_highs, N - 1, high)
        array.set(child_lows, N - 1, low)
    
    // Compute averages (only over populated slots)
    float sum_hi = 0.0
    float sum_lo = 0.0
    int   valid  = 0
    for i = 0 to N - 1
        if not na(array.get(child_highs, i))
            sum_hi += array.get(child_highs, i)
            sum_lo += array.get(child_lows, i)
            valid  += 1
    
    float avg_hi = valid > 0 ? sum_hi / valid : na
    float avg_lo = valid > 0 ? sum_lo / valid : na
    
    // CHoCH detection: current candle breaks the average
    bool floor_break = not na(avg_lo) and valid >= 2 and low < avg_lo
    bool ceil_break  = not na(avg_hi) and valid >= 2 and high > avg_hi
    
    [avg_hi, avg_lo, floor_break, ceil_break, child_count]
```

### A.7.2 Usage for Each Parent TF

```pine
// On M1 chart:
[m5_ceil,  m5_floor,  m5_floor_brk,  m5_ceil_brk,  m5_cnt]  = dynamic_structure("5",   5)
[m15_ceil, m15_floor, m15_floor_brk, m15_ceil_brk, m15_cnt] = dynamic_structure("15",  3)
[h1_ceil,  h1_floor,  h1_floor_brk,  h1_ceil_brk,  h1_cnt]  = dynamic_structure("60",  4)
[h4_ceil,  h4_floor,  h4_floor_brk,  h4_ceil_brk,  h4_cnt]  = dynamic_structure("240", 4)
[d_ceil,   d_floor,   d_floor_brk,   d_ceil_brk,   d_cnt]   = dynamic_structure("1D",  6)
```

### A.7.3 Visualisation

```pine
// Plot dynamic floors/ceilings as stepped lines
plot(m5_floor,  "M5 Floor",  color.new(#78909C, 40), style=plot.style_stepline)
plot(m5_ceil,   "M5 Ceil",   color.new(#78909C, 40), style=plot.style_stepline)
plot(m15_floor, "M15 Floor", color.new(#90A4AE, 20), style=plot.style_stepline)
plot(m15_ceil,  "M15 Ceil",  color.new(#90A4AE, 20), style=plot.style_stepline)

// CHoCH markers
plotshape(m5_floor_brk,  "M5 CHoCH↓",  shape.triangledown, location.belowbar, color.red,   size=size.tiny)
plotshape(m5_ceil_brk,   "M5 CHoCH↑",  shape.triangleup,   location.abovebar, color.green, size=size.tiny)
plotshape(m15_floor_brk, "M15 CHoCH↓", shape.triangledown, location.belowbar, color.orange, size=size.small)
plotshape(m15_ceil_brk,  "M15 CHoCH↑", shape.triangleup,   location.abovebar, color.teal,   size=size.small)
```

## A.8. The Full Three-Layer Cascade — Worked Example

```
SCENARIO: Bearish H4 trend (LH/LL). Price at terminal H4 demand. Reversal beginning.

═══════════════════════════════════════════════════════════════════
LAYER 1 — INTRA-PERIOD (fastest, lowest confidence)
═══════════════════════════════════════════════════════════════════

09:01  M1 #1 of current M5: low = 1.2500 (near H4 demand bot)
09:02  M1 #2: low = 1.2505  → M5 dynamic_floor = avg(1.2500, 1.2505) = 1.2502
09:03  M1 #3: low = 1.2512  → M5 dynamic_floor = avg(1.2500, 1.2505, 1.2512) = 1.2506
09:04  M1 #4: low = 1.2518  → M5 dynamic_floor = 1.2509 — RISING (bullish within M5)
09:05  M1 #5: low = 1.2525  → M5 dynamic_floor = 1.2512 — STILL RISING

       ★ SIGNAL: M5 dynamic_floor rising, dynamic_ceil rising
       ★ CLASSIFICATION: M5 is building bullish momentum at the H4 demand

09:06  New M5 opens. M1 #1: low = 1.2530 → even higher
       M5_prev_lo = 1.2500 (from last M5 period)
       This M5's first M1 low (1.2530) > M5_prev_lo → M5 HL forming
       
       MEANWHILE: M15 dynamic_floor updating with each M5 close:
         Last 3 M5 lows: [1.2510, 1.2500, 1.2530]
         M15 dynamic_floor = 1.2513 — was 1.2505 last check → RISING

       ★ SIGNAL: M15 intra-period floor rising
       ★ CLASSIFICATION: M15 is forming HL — bullish at M15 level
       ★ THIS IS DETECTED 10 MINUTES INTO THE H1 CANDLE

═══════════════════════════════════════════════════════════════════
LAYER 2 — PERIOD-LEVEL (medium speed, medium confidence)  
═══════════════════════════════════════════════════════════════════

09:15  M15 closes. New M15 period opens.
       M15_prev_hi = 1.2545, M15_prev_lo = 1.2498
       
09:20  M5 high = 1.2550 → 1.2550 > M15_prev_hi (1.2545)
       → M15 HIGH BREAK confirmed
       → Check parent: 1.2550 > H1_prev_hi (1.2540)?
         → YES → H1 HIGH BREAK via M15 cascade
       → Check grandparent: 1.2550 > H4_prev_hi (1.2580)?
         → NO → Not yet an H4 event

       ★ SIGNAL: M15 high broken, H1 high broken (via cascade)
       ★ H1 structural shift detected at M5 speed

═══════════════════════════════════════════════════════════════════
LAYER 3 — ZONE-BASED (slowest, highest confidence)
═══════════════════════════════════════════════════════════════════

09:30  H1 zone forms at the reversal point:
       → H1 demand zone: top = 1.2530, bot = 1.2498
       → Classified HL (demand bot 1.2498 > prev demand bot 1.2460)
       → H1 CHoCH confirmed (HL in bearish sequence)
       
       → Compare to H4: demand bot 1.2498 > prev H4 demand bot 1.2450
         → H4 HL forming — H4 structural shift via zone classification

       ★ SIGNAL: Full zone confirmation — H1 CHoCH, H4 HL forming
       ★ ENTRY MECHANICS ENGAGE

═══════════════════════════════════════════════════════════════════
TIMING COMPARISON
═══════════════════════════════════════════════════════════════════

Layer 1 (intra-period): Signal at 09:06   — 24 minutes ahead of zone
Layer 2 (period-level): Signal at 09:20   — 10 minutes ahead of zone
Layer 3 (zone-based):   Signal at 09:30   — full confirmation

All three agree: bullish structural shift at H1, H4 HL forming.
Layer 1 gave you 24 minutes to prepare.
```

---

# PART B — PERIOD-LEVEL STRUCTURE (UNCHANGED FROM V1)

## 1. What `iora_bos_choch.pine` Gives Us

The indicator tracks, for each enabled timeframe (M5 through Yearly), the **previous closed period's high and low** — and detects the exact bar where price first breaks each level.

### 1.1 The `track_period` Function — What It Produces

For each TF, the function outputs six values:

| Output | Meaning |
|---|---|
| `prev_hi` | The highest price reached during the **previous completed** period |
| `prev_hi_t` | The bar timestamp where that high was printed |
| `prev_lo` | The lowest price reached during the previous completed period |
| `prev_lo_t` | The bar timestamp where that low was printed |
| `hi_brk_t` | The bar timestamp where price first exceeds `prev_hi` (high break) — `na` if unbroken |
| `lo_brk_t` | The bar timestamp where price first drops below `prev_lo` (low break) — `na` if unbroken |

### 1.2 Why These Are the Right Structural Levels

These levels are:

- **Objective** — no parameters, no lookback length, no smoothing. The previous M15 high is the previous M15 high. Period.
- **Universal** — every TF from M5 to Yearly follows the same logic.
- **Anchored to real price** — these are actual candle highs and lows, not synthetic (HA) or smoothed values.
- **Self-resetting** — each new period starts fresh. No stale levels accumulating.
- **Break-detected in real time** — the indicator fires on the exact bar that price exceeds the level. Zero lag.

### 1.3 What the Indicator Currently Does NOT Do

The indicator draws levels and marks them broken (✗), but it does not currently:

- Classify breaks as BOS vs CHoCH
- Track the *sequence* of breaks to determine trend state (HH/HL vs LH/LL)
- Propagate child-TF breaks upward to confirm parent-TF structure
- Compare the break level to the parent TF's previous high/low

**This spec defines all of the above.**

---

## 2. Structural State Machine — Per Timeframe

### 2.1 Core State

For each active TF, maintain the following state:

```
TF_Structure:
    trend_direction:   BULLISH | BEARISH | NEUTRAL
    last_swing_high:   float   (the prev-period high that was most recently confirmed as a swing high)
    last_swing_low:    float   (the prev-period low that was most recently confirmed as a swing low)
    prev_swing_high:   float   (the swing high before last_swing_high)
    prev_swing_low:    float   (the swing low before last_swing_low)
    swing_class:       HH | LH  (classification of last_swing_high)
    trough_class:      HL | LL  (classification of last_swing_low)
```

### 2.2 How Swings Are Identified

A **swing high** at TF X is confirmed when the TF X period's high is not exceeded by the *next* period at TF X — i.e., the subsequent period's high is lower. At that point, the previous period's high becomes a confirmed swing high.

But here is the key shortcut the `iora_bos_choch` approach enables: **you don't need to wait for the next period to fail to exceed the high.** Instead, you detect the swing *retroactively* the moment the opposite-side level breaks:

- A **swing high is confirmed** the moment a subsequent period's LOW breaks the previous period's low. The highest unbroken `prev_hi` between the last swing low and this new low break becomes the confirmed swing high.
- A **swing low is confirmed** the moment a subsequent period's HIGH breaks the previous period's high. The lowest unbroken `prev_lo` between the last swing high and this new high break becomes the confirmed swing low.

This mirrors how traditional swing detection works, but uses the period boundaries as the structural anchors rather than pivot-point lookbacks.

### 2.3 Swing Classification

Once a new swing high is confirmed, classify it:

```
IF new_swing_high > prev_swing_high → HH (Higher High)
IF new_swing_high < prev_swing_high → LH (Lower High)
IF new_swing_high == prev_swing_high → EH (Equal High — treat as liquidity level)
```

Once a new swing low is confirmed, classify it:

```
IF new_swing_low > prev_swing_low → HL (Higher Low)
IF new_swing_low < prev_swing_low → LL (Lower Low)
IF new_swing_low == prev_swing_low → EL (Equal Low — treat as liquidity level)
```

### 2.4 BOS vs CHoCH from Sequence

The *sequence* of swing classifications determines BOS and CHoCH events:

| Current trend | New event | Classification | Signal |
|---|---|---|---|
| BULLISH (HH/HL sequence) | New swing high > prev swing high | HH | **BOS** — trend continues |
| BULLISH (HH/HL sequence) | New swing low > prev swing low | HL | **BOS** — pullback holding higher |
| BULLISH (HH/HL sequence) | New swing low < prev swing low | LL | **CHoCH** — first structural failure |
| BULLISH (HH/HL sequence) | New swing high < prev swing high | LH | **CHoCH confirmed** — reversal in progress |
| BEARISH (LH/LL sequence) | New swing low < prev swing low | LL | **BOS** — trend continues |
| BEARISH (LH/LL sequence) | New swing high < prev swing high | LH | **BOS** — pullback holding lower |
| BEARISH (LH/LL sequence) | New swing high > prev swing high | HH | **CHoCH** — first structural failure |
| BEARISH (LH/LL sequence) | New swing low > prev swing low | HL | **CHoCH confirmed** — reversal in progress |

**The critical distinction:** In a bullish trend, the CHoCH fires when the *last swing low* (HL) is broken — that HL was the "protected" level. It doesn't matter that price hasn't yet made a LH; the LL is enough to signal the structural failure.

---

## 3. Cross-TF Propagation — The Cascade

This is the core innovation: **a child TF's period high/low break IS the parent TF's structural event, detected early.**

### 3.1 The Parent-Child Relationship

Each TF has a natural parent:

| Child TF | Parent TF | Period ratio | Meaning |
|---|---|---|---|
| M1 | M5 | 5:1 | 5 M1 periods build one M5 period |
| M5 | M15 | 3:1 | 3 M5 periods build one M15 period |
| M15 | H1 | 4:1 | 4 M15 periods build one H1 period |
| H1 | H4 | 4:1 | 4 H1 periods build one H4 period |
| H4 | D | 6:1 | 6 H4 periods build one D period (24h) |
| D | W | 5:1 | 5 D periods build one D period |
| W | MN | ~4:1 | ~4 W periods build one MN period |

### 3.2 The Propagation Rule

**When a child TF break exceeds the parent TF's previous-period level, it simultaneously confirms a parent TF structural event.**

Concretely:

```
IF M5_prev_hi is broken
  AND the break price > M15_prev_hi
    → M15 high is also broken
      → This is an M15-level structural event, detected at M5 speed

IF M15_prev_hi is broken
  AND the break price > H1_prev_hi
    → H1 high is also broken
      → This is an H1-level structural event, detected at M15 speed

IF H1_prev_hi is broken
  AND the break price > H4_prev_hi
    → H4 high is also broken
      → This is an H4-level structural event, detected at H1 speed
```

**And the cascade can chain:** A single strong candle on M1 can break M5 high → which exceeds M15 high → which exceeds H1 high → confirming an H4 structural event in real time.

### 3.3 The Full Cascade Table

| Child TF break | Exceeds parent level? | Parent TF event confirmed | Earliest detection of... |
|---|---|---|---|
| M5 high broken | > M15 prev_hi | M15 HH/LH swing forming | M15 structural shift |
| M5 low broken | < M15 prev_lo | M15 LL/HL swing forming | M15 structural shift |
| M15 high broken | > H1 prev_hi | H1 HH/LH swing forming | H1 structural shift |
| M15 low broken | < H1 prev_lo | H1 LL/HL swing forming | H1 structural shift |
| H1 high broken | > H4 prev_hi | H4 HH/LH swing forming | H4 structural shift |
| H1 low broken | < H4 prev_lo | H4 LL/HL swing forming | H4 structural shift |
| H4 high broken | > D prev_hi | D HH/LH swing forming | D structural shift |
| H4 low broken | < D prev_lo | D LL/HL swing forming | D structural shift |
| D high broken | > W prev_hi | W HH/LH swing forming | W structural shift |
| D low broken | < W prev_lo | W LL/HL swing forming | W structural shift |

### 3.4 Why This Is Earlier Than Zone-Based Detection

The zone-based approach (spec 03) requires:
1. A colour flip to create the zone
2. The zone to be classified (HH/LH/HL/LL) by comparing to the previous same-type zone
3. A body-close through that zone to confirm the break

The period-level approach requires only:
1. Price exceeds the previous period's high or low

Step 1 of the period-level approach happens *before* step 1 of the zone-based approach. The high/low break fires the moment price exceeds the level — which is mechanically before any zone can form at that level and then be broken.

**And the intra-period approach (Part A) fires even earlier** — it detects the directional shift *before the period that gets broken has even closed*.

### 3.5 Example: Detecting an H4 HH Through H1 Period Breaks

```
Context: H4 bearish trend (LH/LL sequence). Price reaches terminal H4 demand.

Bar-by-bar on H1 chart:
─────────────────────────────────────────

H1 period N:    high = 1.2650, low = 1.2580
H1 period N+1:  high = 1.2620, low = 1.2555
                 → 1.2555 < prev_lo (1.2580) → H1 LOW BREAK
                 → But 1.2555 > H4_prev_lo (1.2500) → no H4 propagation
                 → H1 swing high confirmed at 1.2650

H1 period N+2:  high = 1.2610, low = 1.2540
                 → 1.2540 < prev_lo (1.2555) → H1 LOW BREAK (continuation)
                 → H1 LL confirmed (1.2540 < 1.2555)
                 → H1 BOS bearish

H1 period N+3:  high = 1.2590, low = 1.2570
                 → No breaks. Consolidation.

H1 period N+4:  high = 1.2660, low = 1.2575
                 → 1.2660 > prev_hi (1.2590) → H1 HIGH BREAK
                 → H1 swing low confirmed at lowest low in the sequence
                 → H1 swing low = 1.2540 → HL (above prev swing low 1.2500)
                 → H1 CHoCH! (HL in a bearish sequence)

H1 period N+5:  high = 1.2700, low = 1.2640
                 → 1.2700 > prev_hi (1.2660) → H1 HIGH BREAK
                 → H1 HH confirmed (1.2700 > 1.2650)
                 → H1 BOS bullish

                 NOW CHECK PARENT:
                 → 1.2700 > H4_prev_hi (1.2680)?
                 → YES → H4 HIGH BREAK confirmed through H1 cascade
                 → H4 HH detected (1.2700 > prev H4 swing high)
                 → H4 CHoCH! (HH in a bearish H4 sequence)

                 The H4 candle hasn't even closed yet.
                 But the H4 structural shift is mechanically confirmed.

HOW INTRA-PERIOD (PART A) DETECTED THIS EVEN EARLIER:
                 
                 During H1 period N+4:
                   M15 candles within this H1 were printing:
                   M15 #1: high = 1.2620, low = 1.2575
                   M15 #2: high = 1.2645, low = 1.2595  → dynamic_ceil(H1) rising
                   M15 #3: high = 1.2655, low = 1.2610  → dynamic_ceil(H1) still rising
                   M15 #4: high = 1.2660, low = 1.2620  → dynamic_ceil(H1) = 1.2645

                   At M15 #2 (09:30, 30min into the H1):
                   → dynamic_ceil(H1) = avg(1.2620, 1.2645) = 1.2632
                   → 1.2632 > prev_H1_hi (1.2590)
                   → ★ INTRA-PERIOD SIGNAL: H1 is making a new high
                   → Detected 30 minutes before the H1 candle closed!
```

---

## 4. Internal vs External — Redefined Through Period Levels

### 4.1 The Clean Definition

| Term | Period-level definition |
|---|---|
| **Internal structure** | The sequence of period high/low breaks on the **current TF** — the swings that build the current TF's trend |
| **External structure** | The **parent TF's** period high/low — the level that, when broken, escalates the event to the parent TF |
| **Internal BOS (iBOS)** | Current TF period break that continues the current TF trend (HH in bullish, LL in bearish) |
| **Internal CHoCH (iCHoCH)** | Current TF period break that violates the current TF trend (LL in bullish, HH in bearish) |
| **External BOS (eBOS / BOS+)** | Current TF period break that *also exceeds the parent TF's period level*, continuing the parent TF trend |
| **External CHoCH (eCHoCH / CHoCH+)** | Current TF period break that *also exceeds the parent TF's period level*, violating the parent TF trend |

### 4.2 The Equivalence Chain

```
M1 internal structure  =  sequence of M1 prev-period breaks
M1 external structure  =  M5 prev-period level
                       =  M5 internal structure

M5 internal structure  =  sequence of M5 prev-period breaks
M5 external structure  =  M15 prev-period level
                       =  M15 internal structure

M15 internal structure =  sequence of M15 prev-period breaks
M15 external structure =  H1 prev-period level
                       =  H1 internal structure

H1 internal structure  =  sequence of H1 prev-period breaks
H1 external structure  =  H4 prev-period level
                       =  H4 internal structure

H4 internal structure  =  sequence of H4 prev-period breaks
H4 external structure  =  D prev-period level
                       =  D internal structure
```

### 4.3 Visual on Chart

With `iora_bos_choch.pine` enabled at M15 + H1 + H4:

- The **M15 Hi / M15 Lo** lines = M15 internal structure levels
- The **H1 Hi / H1 Lo** lines = M15 *external* structure = H1 internal structure
- The **H4 Hi / H4 Lo** lines = H1 *external* structure = H4 internal structure

When the M15 high breaks and the break price exceeds the H1 high line → that's an **eBOS+** or **eCHoCH+** at M15 level, simultaneously confirming an H1 internal event.

**With Part A overlays added:** The dynamic floor/ceiling step-lines sit *between* the period levels — the dynamic M15 floor shows you the M15 is making HL *before* the M15 period closes and the M15 Lo line gets set.

---

## 5. Early Confirmation Cascade — Complete Three-Layer Version

### 5.1 The Full Cascade (Bottom-Up, All Three Layers)

```
LAYER 1 — INTRA-PERIOD:
  M1 candle prints with low > dynamic_floor(M5)
    → M5 dynamic floor still rising
      → M5 dynamic ceil rising + exceeding M15 dynamic ceil
        → M15 dynamic ceil rising → "H1 is likely to make a new high"
          → EARLIEST STRUCTURAL SIGNAL (mid-candle, before any period closes)

LAYER 2 — PERIOD-LEVEL:
  M5 period closes → M5_prev_hi set
    → Next M5 breaks M5_prev_hi
      → Break > M15_prev_hi → M15 level broken
        → Break > H1_prev_hi → H1 level broken
          → Break > H4_prev_hi → H4 structural event
            → CONFIRMED STRUCTURAL SHIFT (period boundary crossed)

LAYER 3 — ZONE-BASED:
  Zone forms at the break point → classified HH/LH/HL/LL
    → Cross-TF zone comparison confirms parent TF classification
      → Retest of opposing zone holds → entry mechanics engage
        → FULL CONTEXT CONFIRMATION (zone + classification + retest)
```

### 5.2 Timing Advantage at Each Level

| Parent event | Zone-based detection | Period-level detection | Intra-period detection | Time gained |
|---|---|---|---|---|
| **M15 HH** | M15 zone forms + classifies (~15–30 min) | M5 breaks M15_prev_hi (~5–10 min) | M5 dynamic ceil > M15 prev_hi (~2–3 min) | 12–27 min |
| **H1 HH** | H1 zone forms + classifies (~1–2 hrs) | M15 breaks H1_prev_hi (~15–30 min) | M15 dynamic ceil > H1 prev_hi (~5–15 min) | 45 min–1.75 hrs |
| **H4 HH** | H4 zone forms + classifies (~4–8 hrs) | H1 breaks H4_prev_hi (~1–2 hrs) | H1 dynamic ceil > H4 prev_hi (~15–45 min) | 3–7 hrs |
| **D HH** | D zone forms + classifies (~1–2 days) | H4 breaks D_prev_hi (~4–8 hrs) | H4 dynamic ceil > D prev_hi (~1–4 hrs) | 12–44 hrs |

---

## 6. Combining All Three Layers — Decision Framework

### 6.1 Signal Progression

| Layer | Fires when... | Confidence | Use for... |
|---|---|---|---|
| **Intra-period** | Dynamic floor/ceiling breaks or exceeds parent level | Low–Medium | Early alerting. Position sizing preparation. Stop-loss planning. |
| **Period-level** | Prev-period high/low broken, optionally exceeding parent level | Medium | Structural confirmation. Trend direction update. Entry preparation. |
| **Zone-based** | Zone forms, classifies, and body-close retest holds | High | Trade execution. Full entry with SL/TP mechanics. |

### 6.2 Agreement Matrix

| Intra-period says... | Period-level says... | Zone says... | Interpretation |
|---|---|---|---|
| Floor rising (HL forming) | H1 high broken (HH) | H1 zone classifies HH | **Full alignment** — highest conviction. Execute. |
| Floor rising (HL forming) | H1 high broken (HH) | No zone yet | **Impulse in progress** — zone will form on pullback. Prepare entry. |
| Floor rising (HL forming) | No period break yet | N/A | **Early signal only** — monitor. Don't act. |
| Floor broken (LL forming) | H1 high broken (HH) | Zone classifies LH | **Divergence** — intra-period says the HH is failing. The zone classification (LH) is more reliable. Fade or skip. |
| Flat / no signal | H1 high broken (HH) | Zone classifies HH | **Normal confirmation** — just missed the intra-period signal. Still valid. |
| Floor broken (LL forming) | H1 low broken (LL) | Zone classifies LL | **Full alignment bearish** — highest conviction short. |

### 6.3 The Golden Rule

**Never trade on intra-period alone.** It's a preparation layer, not an execution layer. Always wait for at least period-level confirmation before entering. Use intra-period to get ready early — find your zone, calculate your position size, set your alerts — so that when period-level or zone-based confirmation fires, you execute immediately without hesitation.

---

## 7. Wick vs Body — Resolved for Each Layer

| Layer | Break detection method | Rationale |
|---|---|---|
| **Intra-period** | Candle high/low (wick) | This is a detection/alerting layer. Wicks show where liquidity was taken. Even a wick-only break changes the dynamic average. Appropriate for early alerting. |
| **Period-level (internal)** | Candle high/low (wick) — as currently coded in `iora_bos_choch.pine` | Internal structure tracks all price action. Wick breaks of internal levels are valid structural events. |
| **Period-level (parent propagation)** | Body close preferred | For escalating to parent TF, require body close beyond parent level. Wick-only = liquidity sweep, not structural shift. |
| **Zone-based** | Body close only | Consistent with spec 03. Body close through zone = confirmed break. |

---

## 8. Implementation Priority

### Phase 1: Intra-Period Averages (New Pine Indicator)

Build `iora_dynamic_structure.pine`:
- Computes dynamic floor/ceiling for M5, M15, H1, H4, D
- Plots step-lines on chart
- Marks intra-period CHoCH with shapes
- Dashboard table showing current classification at each TF

### Phase 2: Enhanced `iora_bos_choch.pine` (v2)

Add to existing indicator:
- Swing state machine (§2) tracking HH/HL/LH/LL per TF
- BOS/CHoCH labels at break points
- Parent propagation labels (eBOS+/eCHoCH+)
- Cross-TF connecting visuals

### Phase 3: Three-Layer Integration

Combine intra-period + period-level + zone-based into unified dashboard:
- Signal progression timeline per TF
- Agreement/divergence alerts
- Entry readiness scoring

---

## 9. Validation — Bar Replay Checklist

### 9.1 Intra-Period Accuracy (Part A)

On GBPUSD M1 chart with M5 + M15 + H1 dynamic overlays:

1. **Floor/ceiling direction.** When you visually see M1 candles making higher lows within an M5 period, does the M5 dynamic floor plot as rising? (Must match.)
2. **CHoCH timing.** When the M5 dynamic floor breaks, does the M5 candle that eventually closes show a bearish reversal? (Should agree >70% of the time. <70% = the average needs adjustment, possibly EMA instead of SMA or a minimum child-count threshold.)
3. **Parent propagation.** When M5 dynamic ceil exceeds M15_prev_hi, does the M15 period that eventually closes confirm a new M15 high? (Should agree >60%. Lower rate acceptable — this is a leading indicator.)
4. **False signal rate.** How many intra-period CHoCH signals are reversed within the same parent period? (Acceptable if <40%. If higher, require ≥3 child candles before signalling rather than ≥2.)

### 9.2 Period-Level Accuracy (Part B)

5. **Break detection timing.** When M15 high line shows ✗, does it fire on the exact bar that exceeded it?
6. **Cascade propagation.** When M15 high break exceeds H1 high → does the H1 line also show ✗ on the same bar?
7. **Swing classification.** After a high break, is the confirmed swing low correctly identified and classified?
8. **BOS/CHoCH accuracy.** In a clear bullish H1 sequence, does a low break below the last HL correctly flag as CHoCH?

### 9.3 Cross-Layer Agreement

9. **Intra-period precedes period-level.** The intra-period signal should fire before the period-level break in >80% of cases.
10. **Period-level precedes zone-level.** The period break should fire before or simultaneously with zone-based classification.
11. **No false cascades.** A wick-only break of the parent level should NOT propagate if using body-close rule for parent propagation.
12. **Full alignment = high win rate.** When all three layers agree, the subsequent price move in the signalled direction should hold >65% of the time.

---

## 10. Integration with Existing Specs

| This spec section | Maps to... |
|---|---|
| Part A (intra-period averages) | **New** — not in any existing spec. Adds the fastest detection layer. |
| §A.6 HH/HL/LH/LL classification | `02_cascade` §7 (complete table) — now with intra-period timing added |
| §A.8 three-layer cascade | `02_cascade` §1 + `03_spec` §3 — unified into single progression |
| §2 State machine | `03_spec` §4.1 StructureState (now with period-level input) |
| §3 Cross-TF propagation | `03_spec` §4.4 + `02_cascade` §1 (bottom-up chain) |
| §4 Internal/external definition | `03_spec` §3 (same hierarchy, different detection input) |
| §6 Three-layer decision framework | **New** — bridges all three detection methods |
| §7 Wick vs body resolution | `03_spec` §5 validation (now resolved per layer) |

---

## 11. Summary — The Three Layers in One Sentence Each

**Intra-period:** Track the rolling average of child-TF candle highs/lows within each parent period — when the average breaks direction, the parent TF's structural swing is already forming, detected before the parent candle closes.

**Period-level:** When a child TF breaks its previous-period high/low and that break exceeds the parent TF's previous-period level, the parent TF's structure has shifted — detected at child-TF speed with zero lag.

**Zone-based:** When a colour-flip zone forms and classifies consistently with the period-level and intra-period signals, full structural context is confirmed — execute with precision.
