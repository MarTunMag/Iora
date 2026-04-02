# Candle Type & Price Source Analysis — Addendum to 04_period_level_structure_spec

**System:** Iora  
**Date:** March 2026  
**Context:** Evaluation of candle types and price sources for the intra-period dynamic average layer (Part A of the period-level structure spec)

---

## 1. Candle Type Evaluation

### 1.1 The Structural Requirement

The intra-period dynamic average system has one hard requirement: **a fixed, predictable number of child candles per parent period.** The rolling average window is the natural period ratio (5 M1s per M5, 3 M5s per M15, etc.). This ratio must be deterministic — the same number of child candles every parent period — or the averaging breaks.

### 1.2 Elimination by Architecture

| Candle type | Time-fixed? | Child-per-parent ratio deterministic? | Verdict |
|---|---|---|---|
| **Renko** | No — new brick only when price moves X pips | No — could be 0 bricks or 50 bricks per M5 | **Eliminated** |
| **Three Line Break** | No — new line only when price exceeds last N reversals | No — wildly variable per period | **Eliminated** |
| **Kagi** | No — reversal-based, creates new line on threshold reversal | No — unpredictable timing | **Eliminated** |
| **Range bars** | No — new bar when price moves fixed range | No — count varies with volatility | **Eliminated** |
| **Point & Figure** | No — box-based, time-agnostic | No — completely detached from time periods | **Eliminated** |
| **Line (raw OHLC)** | Yes — one candle per period, always | Yes — exactly N child candles per parent | **Candidate** |
| **Heikin Ashi** | Yes — one candle per period, always | Yes — exactly N child candles per parent | **Candidate** |

Only Line and Heikin Ashi survive.

### 1.3 Line vs Heikin Ashi — The Decision

For the dynamic average layer specifically, the computation is `avg(child_candle_lows)` and `avg(child_candle_highs)`. The question is whether Line or HA highs/lows produce better structural signals.

**HA high/low values vs real high/low values:**

```
HA_open  = (prev_HA_open + prev_HA_close) / 2    ← synthetic
HA_close = (open + high + low + close) / 4         ← synthetic average
HA_high  = max(high, HA_open, HA_close)            ← almost always = real high
HA_low   = min(low, HA_open, HA_close)             ← almost always = real low
```

Because HA_open and HA_close are averages that fall within the real high-low range, `HA_high` virtually always equals the real `high`, and `HA_low` virtually always equals the real `low`. **The dynamic floor and ceiling would compute to the same values regardless of candle type.**

**Therefore: Line candles.** Same computed averages, but with these advantages:

| Advantage | Why it matters |
|---|---|
| No synthetic computation | HA open depends on prior HA bar — creates a chain. Line is raw from the feed. |
| Real executable prices | Levels sit where orders actually fill. SL/TP at real levels. |
| No smoothing lag | HA smooths colour transitions by 1+ bar. Line detects flips immediately. |
| Parity-safe | No HA calculation to reproduce exactly between Pine, Python, and MQL5. |
| Already chosen | Spec 03 uses Line for zone creation. Consistency across the system. |

### 1.4 When Would Non-Line Make Sense?

HA candles only help if you need **colour/direction filtering** — i.e., "is this candle bullish or bearish?" HA excels here because its smoothed body eliminates single-candle colour noise.

But in the dynamic average system, direction is derived from the *slope of the average* — not from individual candle colour. The average itself IS the smoothing mechanism. Applying HA smoothing on top of averaging is double-smoothing, which adds lag without adding information.

**Verdict: Line candles. No contest for this specific application.**

---

## 2. The Real Design Question — Which Price to Average

The candle type question is resolved. But there's a deeper question that has more impact on signal quality: **which price value from each child candle should feed into the rolling average?**

The current spec uses `avg(highs)` for the dynamic ceiling and `avg(lows)` for the dynamic floor. But there are several alternative price sources, each encoding different structural information.

### 2.1 The Candidates

| Price source | Formula | What it represents |
|---|---|---|
| **High** | `candle.high` | Maximum reach of buyers in that period. Includes wicks. Captures liquidity sweeps. |
| **Low** | `candle.low` | Maximum reach of sellers. Includes wicks. Captures stop runs. |
| **Close** | `candle.close` | Where the market *settled*. Commitment price. Most stable directionally. |
| **Open** | `candle.open` | Where the period started. Useful for gap analysis but least informative for structure. |
| **HL2** | `(high + low) / 2` | Midpoint of the range. "Typical price" without close weighting. Centre of gravity of the candle. |
| **HLC3** | `(high + low + close) / 3` | Typical price with close weighting. Biases toward settlement. |
| **OHLC4** | `(open + high + low + close) / 4` | Full candle average. Smoothest single measure. |
| **Body midpoint** | `(open + close) / 2` | Centre of the body. Ignores wicks entirely. Pure commitment. |

### 2.2 What Each Average Tells You

When you compute a rolling average of N child candles using each source:

| avg(source) rising | What it means | Noise level | Lag | Best for... |
|---|---|---|---|---|
| **avg(lows) rising** | The structural floor is lifting. Each child candle's worst point is higher than prior candles'. Genuine support building. | Medium — wicks add noise | Zero — detects immediately | **Dynamic floor / support detection** |
| **avg(highs) rising** | The structural ceiling is lifting. Expansion in progress. New highs being made. | Medium — wicks add noise | Zero | **Dynamic ceiling / resistance detection** |
| **avg(closes) rising** | Market commitment is shifting higher. Regardless of wicks, the settlement is moving up. | Low — closes are the most stable price | Very low | **Directional bias / momentum** |
| **avg(HL2) rising** | The centre of each candle's range is moving up. Balanced structural shift. | Low | Very low | **Structural midpoint tracking** |
| **avg(body midpoint) rising** | Pure commitment range is shifting. No wick noise at all. | Lowest | Very low | **Trend strength confirmation** |

### 2.3 The Multi-Source Approach — Three Averages, Not One

Rather than choosing a single source, using **three complementary averages** provides a richer structural picture:

```
For each parent TF P, compute:

STRUCTURAL BOUNDARIES:
  dynamic_floor   = avg(child_lows)     ← where support sits
  dynamic_ceiling = avg(child_highs)    ← where resistance sits

DIRECTIONAL BIAS:
  dynamic_mid     = avg(child_closes)   ← where commitment sits
```

These three values together create a **dynamic envelope** around the current parent period's price action:

```
Price scale (vertical):
─────────────────────────────────────────
  dynamic_ceiling  ═══════════════  (avg highs — resistance)
     |
     |  ← expansion zone (ceiling to mid)
     |
  dynamic_mid      ═══════════════  (avg closes — commitment)
     |
     |  ← compression zone (mid to floor)
     |
  dynamic_floor    ═══════════════  (avg lows — support)
─────────────────────────────────────────
```

### 2.4 Structural Signals from the Three-Source Envelope

| dynamic_floor | dynamic_mid | dynamic_ceiling | Pattern | Interpretation |
|---|---|---|---|---|
| Rising | Rising | Rising | **Full bullish alignment** | All three lifting. Strong structural momentum up. Impulsive move. |
| Rising | Rising | Flat/falling | **Bullish compression** | Support rising, resistance capping. Coiling. Breakout imminent. |
| Rising | Flat | Rising | **Range expansion** | Floor and ceiling widening. Volatility increasing. Direction unclear. |
| Flat | Rising | Rising | **Bullish breakout** | Closes pushing into resistance. Support holding. HL structure. |
| Falling | Falling | Falling | **Full bearish alignment** | All three dropping. Strong bearish momentum. Impulsive move down. |
| Falling | Falling | Flat/rising | **Bearish compression** | Floor dropping, ceiling holding. Coiling for bearish continuation. |
| Flat | Falling | Falling | **Bearish breakout** | Closes pulling away from support. Resistance pressing down. LH structure. |
| Rising | Falling | Falling | **Divergence: floor vs direction** | Support technically rising but closes and highs falling. Likely a lower-high forming — the rising floor is a false signal. |
| Falling | Rising | Rising | **Divergence: floor weakening** | Closes and highs rising but lows dropping. Widening range. Exhaustion potential. |

### 2.5 Enhanced CHoCH Detection with Three Sources

The single-source CHoCH (Part A of the main spec) fires when `candle_low < dynamic_floor`. The three-source version adds gradient confirmation:

**Strong CHoCH (high conviction):**
```
CONDITIONS:
  1. candle_low < dynamic_floor        (floor broken)
  2. dynamic_mid was rising, now turns flat or falling  (commitment shifting)
  3. dynamic_ceiling was rising, now flat or falling    (expansion stalling)

SIGNAL: Intra-period CHoCH with full alignment
CONFIDENCE: High — all three sources confirm the directional shift
```

**Weak CHoCH (low conviction, watch only):**
```
CONDITIONS:
  1. candle_low < dynamic_floor        (floor broken)
  2. dynamic_mid still rising          (commitment hasn't shifted yet)
  3. dynamic_ceiling still rising      (expansion continues)

SIGNAL: Floor broken but direction not confirmed
CONFIDENCE: Low — likely a wick/sweep, not a structural shift
ACTION: Monitor but do not escalate to parent TF
```

**Pre-CHoCH warning (earliest possible alert):**
```
CONDITIONS:
  1. dynamic_floor still intact (not broken)
  2. dynamic_mid turns flat after rising  (commitment stalling)
  3. dynamic_ceiling turns flat after rising (expansion exhausting)

SIGNAL: Momentum fading — CHoCH likely incoming within 1-2 child candles
CONFIDENCE: Predictive — not confirmed yet
ACTION: Prepare. Calculate position size. Set alerts.
```

---

## 3. The Price Source Decision Matrix

| Use case | Best price source | Why |
|---|---|---|
| "Is the structural floor holding?" | `avg(lows)` | Lows are the actual support test points |
| "Is the structural ceiling being pushed?" | `avg(highs)` | Highs are the actual resistance test points |
| "Which direction is the market committed to?" | `avg(closes)` | Close = settlement = commitment. Most stable directional signal. |
| "Is the candle range expanding or contracting?" | `avg(highs) - avg(lows)` | The envelope width. Rising = expansion. Falling = compression. |
| "Is there wick noise or real commitment?" | `avg(closes)` vs `avg(highs/lows)` | If avg(closes) diverges from avg(highs) → the highs are wicks, not commitment. |
| "Where is the centre of gravity of current structure?" | `avg(HL2)` or `avg(closes)` | Both work. HL2 is symmetric, close is commitment-weighted. |
| "Should I escalate this to the parent TF?" | All three agreeing | Only propagate upward when floor + mid + ceiling all confirm the same direction. |

---

## 4. Implementation — Enhanced Dynamic Structure Function

### 4.1 Pine Script v6

```pine
// Enhanced dynamic structure: three-source envelope
// Returns floor (avg lows), ceiling (avg highs), mid (avg closes),
// plus CHoCH signals and gradient state

dynamic_structure_v2(string parent_tf, int N) =>
    bool new_parent = ta.change(time(parent_tf)) != 0
    
    var float[] c_highs  = array.new_float(N, na)
    var float[] c_lows   = array.new_float(N, na)
    var float[] c_closes = array.new_float(N, na)
    var int     c_count  = 0
    
    // Previous values for gradient detection
    var float prev_floor = na
    var float prev_ceil  = na
    var float prev_mid   = na
    
    if new_parent
        c_count := 0
        for i = 0 to N - 1
            array.set(c_highs, i, na)
            array.set(c_lows, i, na)
            array.set(c_closes, i, na)
    
    // Add new child candle
    int idx = math.min(c_count, N - 1)
    if c_count >= N
        for i = 0 to N - 2
            array.set(c_highs, i, array.get(c_highs, i + 1))
            array.set(c_lows, i, array.get(c_lows, i + 1))
            array.set(c_closes, i, array.get(c_closes, i + 1))
    array.set(c_highs, idx, high)
    array.set(c_lows, idx, low)
    array.set(c_closes, idx, close)
    c_count += 1
    
    // Compute averages
    float sum_hi = 0.0, float sum_lo = 0.0, float sum_cl = 0.0
    int valid = math.min(c_count, N)
    for i = 0 to valid - 1
        sum_hi += array.get(c_highs, i)
        sum_lo += array.get(c_lows, i)
        sum_cl += array.get(c_closes, i)
    
    float avg_ceil  = valid > 0 ? sum_hi / valid : na
    float avg_floor = valid > 0 ? sum_lo / valid : na
    float avg_mid   = valid > 0 ? sum_cl / valid : na
    
    // Gradients (direction of each average)
    float floor_delta = not na(prev_floor) ? avg_floor - prev_floor : 0.0
    float ceil_delta  = not na(prev_ceil)  ? avg_ceil - prev_ceil   : 0.0
    float mid_delta   = not na(prev_mid)   ? avg_mid - prev_mid     : 0.0
    
    // CHoCH detection — floor break with gradient context
    bool floor_break = valid >= 2 and low < avg_floor
    bool ceil_break  = valid >= 2 and high > avg_ceil
    
    // Conviction scoring
    // Strong CHoCH: floor breaks AND mid+ceil confirm
    bool strong_bearish_choch = floor_break and mid_delta <= 0 and ceil_delta <= 0
    bool strong_bullish_choch = ceil_break  and mid_delta >= 0 and floor_delta >= 0
    
    // Weak CHoCH: floor breaks but mid/ceil don't confirm
    bool weak_bearish_choch = floor_break and (mid_delta > 0 or ceil_delta > 0)
    bool weak_bullish_choch = ceil_break  and (mid_delta < 0 or floor_delta < 0)
    
    // Pre-CHoCH warning: mid stalling after directional run
    bool pre_bearish = not floor_break and mid_delta <= 0 and prev_mid > 0 and ceil_delta <= 0
    bool pre_bullish = not ceil_break  and mid_delta >= 0 and prev_mid < 0 and floor_delta >= 0
    
    // Envelope width (volatility measure)
    float envelope = avg_ceil - avg_floor
    
    // Save for next bar gradient
    prev_floor := avg_floor
    prev_ceil  := avg_ceil
    prev_mid   := avg_mid
    
    [avg_ceil, avg_floor, avg_mid, 
     strong_bearish_choch, strong_bullish_choch,
     weak_bearish_choch, weak_bullish_choch,
     pre_bearish, pre_bullish,
     floor_delta, ceil_delta, mid_delta, envelope]
```

### 4.2 Visualisation

```pine
// Three-line envelope per parent TF
plot(avg_floor, "M5 Floor",   color.new(#4CAF50, 30), style=plot.style_stepline, linewidth=1)
plot(avg_mid,   "M5 Mid",     color.new(#9E9E9E, 30), style=plot.style_stepline, linewidth=1)
plot(avg_ceil,  "M5 Ceiling", color.new(#F44336, 30), style=plot.style_stepline, linewidth=1)

// Fill between floor and ceiling for visual envelope
fill(floor_plot, ceil_plot, color.new(#E3F2FD, 85))

// CHoCH markers — sized by conviction
plotshape(strong_bearish_choch, "Strong CHoCH↓", shape.triangledown, location.abovebar, 
          color.red, size=size.normal)
plotshape(weak_bearish_choch,   "Weak CHoCH↓",   shape.triangledown, location.abovebar, 
          color.new(#F44336, 60), size=size.tiny)
plotshape(pre_bearish,          "Pre-CHoCH↓",    shape.diamond,      location.abovebar, 
          color.new(#FF9800, 40), size=size.tiny)

plotshape(strong_bullish_choch, "Strong CHoCH↑", shape.triangleup, location.belowbar, 
          color.green, size=size.normal)
plotshape(weak_bullish_choch,   "Weak CHoCH↑",   shape.triangleup, location.belowbar, 
          color.new(#4CAF50, 60), size=size.tiny)
plotshape(pre_bullish,          "Pre-CHoCH↑",    shape.diamond,      location.belowbar, 
          color.new(#FF9800, 40), size=size.tiny)
```

---

## 5. Why Not Use EMA Instead of SMA?

A valid question: the rolling average described is an SMA (simple moving average). Would an EMA (exponential moving average) work better?

| Factor | SMA | EMA |
|---|---|---|
| **Weighting** | Equal weight to all N child candles | More weight on recent candles |
| **Lag** | Slightly more lag (responds equally to all N candles) | Slightly less lag (reacts faster to latest candle) |
| **Noise response** | Averages out noise evenly | Amplifies the most recent candle's noise |
| **Interpretation** | "The average structural level over this parent period" — clean, intuitive | "A weighted recent structural level" — less intuitive as a structural reference |
| **Period-ratio alignment** | Window exactly matches parent-child ratio | EMA span doesn't map cleanly to a fixed number of candles |

**Recommendation: SMA.** The window is intentionally fixed at the parent-child ratio. This isn't a trend-following indicator where EMA responsiveness helps — it's a structural averaging system where the period ratio IS the logic. An EMA would weight the most recent child candle more, which introduces an arbitrary asymmetry that doesn't reflect the structural relationship.

However, **the gradient (delta) already provides recency sensitivity** — it measures the change between the current average and the previous. This captures how the latest child candle moved the average without introducing EMA weighting.

---

## 6. Updated Spec Summary

### 6.1 Final Architecture

```
CANDLE TYPE: Line (raw OHLC) — at all levels, for all computations

PRICE SOURCES (three-envelope):
  ├── avg(child_lows)    → dynamic floor    → structural support
  ├── avg(child_closes)  → dynamic mid      → directional commitment  
  └── avg(child_highs)   → dynamic ceiling  → structural resistance

CHoCH CONVICTION SCORING:
  ├── Strong: floor/ceiling breaks + mid confirms + gradient aligns
  ├── Weak:   floor/ceiling breaks + mid doesn't confirm
  └── Pre:    mid stalling + floor/ceiling intact (predictive warning)

PARENT PROPAGATION RULE:
  Only escalate to parent TF on STRONG CHoCH (all three sources agree)
  Weak CHoCH = monitor only, do not propagate
  Pre-CHoCH  = prepare only, do not act
```

### 6.2 The Three Layers — Updated with Three-Source Envelope

| Layer | Detection method | Price source | Confidence | Action |
|---|---|---|---|---|
| **Intra-period (Part A)** | Three-source envelope (avg highs, lows, closes) with gradient scoring | Line candle H/L/C | Low→Medium (depending on conviction) | Alert, prepare, size position |
| **Period-level (Part B)** | Previous-period high/low break with parent propagation | Line candle H/L (wick for detection, body for parent propagation) | Medium | Confirm structural shift, update trend state |
| **Zone-based (Spec 03)** | Colour-flip zone creation, classification, body-close break | Line candle O/H/L/C | High | Execute trade with SL/TP |
