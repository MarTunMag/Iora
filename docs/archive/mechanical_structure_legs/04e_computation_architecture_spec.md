# Computation Architecture — Cascade vs Direct vs Hybrid

**System:** Iora  
**Date:** March 2026  
**Context:** Which data source and computation method produces the most accurate and fastest dynamic envelope for the conviction-based structural cascade.

---

## 1. The Three Approaches

### 1.1 Approach A — Cascading TF Averages (Current Spec)

Each parent TF's envelope uses its direct child TF's candles:

```
M5  envelope = avg of last 5 M1 candle highs/lows/closes
M15 envelope = avg of last 3 M5 candle highs/lows/closes
H1  envelope = avg of last 4 M15 candle highs/lows/closes
H4  envelope = avg of last 4 H1 candle highs/lows/closes
D   envelope = avg of last 6 H4 candle highs/lows/closes
```

**Update frequency:** Each envelope updates only when its child TF candle closes.
- M5 envelope: every 5 minutes (on M5 close)
- M15 envelope: every 15 minutes (on M15 close)
- H1 envelope: every 60 minutes (on H1 close)
- H4 envelope: every 4 hours
- D envelope: every 4 hours (on H4 close)

### 1.2 Approach B — Direct M1 Averages

Every parent TF's envelope uses raw M1 data with a window matching the parent period:

```
M5  envelope = avg of last 5 M1 candle highs/lows/closes
M15 envelope = avg of last 15 M1 candle highs/lows/closes
H1  envelope = avg of last 60 M1 candle highs/lows/closes
H4  envelope = avg of last 240 M1 candle highs/lows/closes
D   envelope = avg of last 1440 M1 candle highs/lows/closes
```

**Update frequency:** Every envelope updates on every M1 candle (every minute).

### 1.3 Approach C — Hybrid (Reconstructed Candles from M1)

Reconstruct each TF's candle values from M1 data in real time, then cascade those reconstructed candles:

```
Step 1: From M1 bars, reconstruct the CURRENT (still-forming) M5 candle:
  M5_building_high  = max(M1 highs within current M5 period)
  M5_building_low   = min(M1 lows within current M5 period)
  M5_building_close = latest M1 close

Step 2: Use the reconstructed M5 candle + previous closed M5 candles for M15 envelope:
  M15 envelope = avg of [prev_M5_candle_2, prev_M5_candle_1, CURRENT_M5_building]

Step 3: From reconstructed M5 candles, reconstruct current M15 candle:
  M15_building_high  = max(M5 highs within current M15 period)
  M15_building_low   = min(M5 lows within current M15 period)

Step 4: Use reconstructed M15 candle for H1 envelope:
  H1 envelope = avg of [prev_M15_3, prev_M15_2, prev_M15_1, CURRENT_M15_building]

... and so on up to Daily
```

**Update frequency:** Every envelope updates on every M1 candle (every minute), but using structurally correct candle values (max/min, not average).

---

## 2. Why Direct M1 (Approach B) Is Structurally Wrong

### 2.1 The Core Problem

The H1 candle's low is `min(60 M1 lows)` — the single worst M1 print in that hour. But `avg(60 M1 lows)` is the *typical* M1 floor. These are fundamentally different values:

```
EXAMPLE: 60 M1 candles within one H1 period

M1 lows: [1.2650, 1.2648, 1.2652, 1.2645, ..., 1.2600, ..., 1.2655, 1.2660]
                                                    ↑
                                              one spike low (wick)

H1 candle low = min(all) = 1.2600  ← the structural level (where stops were hit)
avg(60 M1 lows) = ~1.2648          ← the typical floor (48 pips higher!)
```

The structural level (1.2600) is where the market actually reached — where stops were triggered, where liquidity was taken. The average (1.2648) smooths that away. For structural analysis, the extreme matters more than the average of the parts.

### 2.2 What Direct M1 Averaging Actually Gives You

| Direct M1 window | What it IS | What it IS NOT |
|---|---|---|
| `avg(15 M1 lows)` | A 15-minute rolling average of M1 support levels | The M15 candle's low (which is the minimum, not average) |
| `avg(60 M1 lows)` | A 60-minute rolling average of M1 support levels | The H1 candle's low |
| `avg(240 M1 lows)` | A 4-hour rolling average of M1 support levels | The H4 candle's low |
| `avg(1440 M1 lows)` | A 24-hour rolling average of M1 support levels | The Daily candle's low |

These are just SMAs (simple moving averages) of M1 data at different lengths. They're valid technical indicators, but they don't measure what the cascade system needs — they don't capture the structural extremes that define swing highs and lows at each TF.

### 2.3 The Window Size Problem

`avg(1440 M1 lows)` for the Daily envelope would be a 1440-period SMA. This is extremely laggy — it takes hundreds of M1 bars for the average to respond meaningfully. The whole point of the dynamic envelope is to detect structural shifts early. A 1440-bar SMA defeats that purpose.

Compare:
- Cascading (Approach A): D envelope updates when H4 closes (every 4 hours). Uses 6 data points. Responsive to each H4 move.
- Direct M1 (Approach B): D envelope updates every minute but is a 1440-bar SMA. Takes ~700 bars to shift meaningfully. Extremely slow despite updating frequently.

**Frequent updates ≠ fast detection.** A 1440-bar SMA updating every minute is still a 1440-bar SMA.

---

## 3. Why Cascading (Approach A) Is Structurally Correct but Slow

### 3.1 The Structural Accuracy

Cascading preserves the correct candle anatomy at every level:

```
M5 candle high  = max(5 M1 highs)    ← real M5 high, where resistance was
M5 candle low   = min(5 M1 lows)     ← real M5 low, where support was
M5 candle close = last M1 close      ← real M5 settlement

M15 envelope    = avg of 3 actual M5 candle values
                = structurally meaningful at M15 level
```

Each level's envelope uses the genuine structural data from the level below. The M15 envelope knows where M5 support/resistance/commitment actually was — not a smoothed approximation.

### 3.2 The Speed Problem

The M15 envelope only updates when an M5 candle closes (every 5 minutes). The H1 envelope only updates when an M15 candle closes (every 15 minutes). The H4 envelope only updates every 60 minutes. The D envelope only updates every 4 hours.

This means: during the 4 hours between H4 closes, the D envelope is frozen. Even though M1 candles are printing every minute and could be telling you the Daily structure is shifting, the D envelope doesn't know.

---

## 4. Why Hybrid (Approach C) Is the Answer

### 4.1 The Best of Both

The hybrid approach reconstructs each TF's candle *in real time from M1 data*, then uses those reconstructed candles in the cascade. This gives you:

- **Structural accuracy:** each TF's high = max (not average) of its child highs. Preserves the meaning.
- **M1-speed updates:** every M1 bar updates the building candle at every TF, which updates every envelope.
- **Correct cascade:** each envelope uses genuine candle values, just with the current candle updated in real time rather than waiting for close.

### 4.2 How It Works — Step by Step

```
ON EVERY M1 CANDLE CLOSE:

STEP 1 — RECONSTRUCT M5 (current + history)
  current_M5_high  = max(M1 highs since last M5 open)
  current_M5_low   = min(M1 lows since last M5 open)
  current_M5_close = this M1 close
  
  M5 candles for M15 envelope = [closed_M5[-2], closed_M5[-1], current_M5_building]
  → M15 envelope updates with the LIVE M5 candle included

STEP 2 — RECONSTRUCT M15 (from reconstructed M5s)
  current_M15_high  = max(M5 highs since last M15 open)
                    = max(closed M5 highs in this period + current_M5_building_high)
  current_M15_low   = min(M5 lows since last M15 open)
  current_M15_close = current_M5_close (= latest M1 close)
  
  M15 candles for H1 envelope = [closed_M15[-3], closed_M15[-2], closed_M15[-1], current_M15_building]
  → H1 envelope updates with the LIVE M15 candle included

STEP 3 — RECONSTRUCT H1 (from reconstructed M15s)
  current_H1_high  = max(M15 highs since last H1 open)
  current_H1_low   = min(M15 lows since last H1 open)
  current_H1_close = current_M15_close
  
  H1 candles for H4 envelope = [closed_H1[-3], ..., closed_H1[-1], current_H1_building]
  → H4 envelope updates with the LIVE H1 candle included

STEP 4 — RECONSTRUCT H4 (from reconstructed H1s)
  current_H4_high  = max(H1 highs since last H4 open)
  current_H4_low   = min(H1 lows since last H4 open)
  current_H4_close = current_H1_close
  
  H4 candles for D envelope = [closed_H4[-5], ..., closed_H4[-1], current_H4_building]
  → D envelope updates with the LIVE H4 candle included

STEP 5 — RECONSTRUCT D (from reconstructed H4s)
  current_D_high   = max(H4 highs since last D open)
  current_D_low    = min(H4 lows since last D4 open)
  current_D_close  = current_H4_close

RESULT: Every TF's envelope is now updated on every M1 bar,
        using structurally correct max/min candle values,
        with the building (incomplete) candle included in real time.
```

### 4.3 The Critical Difference — Building Candle Inclusion

The key innovation of the hybrid over pure cascading: **the current (unfinished) candle at each TF is included in the envelope calculation, updated every M1 bar.**

```
CASCADING (Approach A):
  H1 envelope = avg of [closed_M15[-3], closed_M15[-2], closed_M15[-1]]
  → Only uses CLOSED M15 candles
  → The CURRENT M15 (still building) is excluded
  → Envelope is 0-15 minutes behind reality

HYBRID (Approach C):
  H1 envelope = avg of [closed_M15[-3], closed_M15[-2], closed_M15[-1], current_M15_building]
  → Includes the CURRENT M15, reconstructed from M1 data
  → The building M15's high/low/close update every M1 bar
  → Envelope is 0-1 minutes behind reality (M1 granularity)
```

For the H4 envelope, the difference is dramatic:
- Cascading: updates every 60 minutes (on H1 close)
- Hybrid: updates every minute (current H1 candle reconstructed from M1)

For the D envelope:
- Cascading: updates every 4 hours (on H4 close)
- Hybrid: updates every minute (current H4 candle reconstructed from M1 → H1 → M15 → M5)

---

## 5. Comparison Table — All Three Approaches

| Factor | A: Cascading | B: Direct M1 | C: Hybrid |
|---|---|---|---|
| **Structural accuracy** | Correct — uses actual candle H/L/C | Wrong — averages M1 data, loses structural extremes | Correct — reconstructs actual candle H/L/C from M1 |
| **Update speed** | Slow — waits for child TF close | Fast — every M1 bar | Fast — every M1 bar |
| **M15 envelope lag** | 0–5 min (waits for M5 close) | 0 (updates every M1) | 0–1 min (updates every M1 with live M5) |
| **H1 envelope lag** | 0–15 min (waits for M15 close) | 0 (but uses 60-bar SMA — very smoothed) | 0–1 min (updates every M1 with live M15) |
| **H4 envelope lag** | 0–60 min (waits for H1 close) | 0 (but uses 240-bar SMA — extremely smoothed) | 0–1 min (updates every M1 with live H1) |
| **D envelope lag** | 0–4 hours (waits for H4 close) | 0 (but uses 1440-bar SMA — practically useless) | 0–1 min (updates every M1 with live H4) |
| **CHoCH detection speed** | Fires on child TF close | Fires every minute but many false signals | Fires every minute with structural accuracy |
| **Noise at higher TFs** | Low — natural TF filtering | Very high — direct M1 data is noisy at H4/D scale | Low — TF reconstruction preserves hierarchy |
| **Computation cost** | Low — simple per-TF averages | Low — simple rolling averages | Medium — requires real-time candle reconstruction |
| **Pine Script feasibility** | Easy — current implementation | Easy — standard SMA | Moderate — needs candle building logic per TF |

---

## 6. Hybrid Implementation — Pine Script

### 6.1 The Candle Builder

```pine
//@version=6

// Build a parent-TF candle in real time from chart-TF bars
// Call on every bar — updates the "building" candle continuously

build_candle(string parent_tf) =>
    bool new_period = ta.change(time(parent_tf)) != 0
    
    var float bld_open  = na
    var float bld_high  = na
    var float bld_low   = na
    var float bld_close = na
    
    // Track last N closed candles for envelope calculation
    var float prev1_high  = na, var float prev1_low  = na, var float prev1_close = na
    var float prev2_high  = na, var float prev2_low  = na, var float prev2_close = na
    var float prev3_high  = na, var float prev3_low  = na, var float prev3_close = na
    var float prev4_high  = na, var float prev4_low  = na, var float prev4_close = na
    var float prev5_high  = na, var float prev5_low  = na, var float prev5_close = na
    
    if new_period
        // Shift history: push current building candle into closed history
        prev5_high := prev4_high, prev5_low := prev4_low, prev5_close := prev4_close
        prev4_high := prev3_high, prev4_low := prev3_low, prev4_close := prev3_close
        prev3_high := prev2_high, prev3_low := prev2_low, prev3_close := prev2_close
        prev2_high := prev1_high, prev2_low := prev1_low, prev2_close := prev1_close
        prev1_high := bld_high,   prev1_low := bld_low,   prev1_close := bld_close
        
        // Start new building candle
        bld_open  := open
        bld_high  := high
        bld_low   := low
        bld_close := close
    else
        // Update building candle with current bar
        bld_high  := math.max(nz(bld_high), high)
        bld_low   := math.min(nz(bld_low, 1e18), low)
        bld_close := close
    
    [bld_high, bld_low, bld_close,
     prev1_high, prev1_low, prev1_close,
     prev2_high, prev2_low, prev2_close,
     prev3_high, prev3_low, prev3_close,
     prev4_high, prev4_low, prev4_close,
     prev5_high, prev5_low, prev5_close]
```

### 6.2 The Envelope Calculator (Using Built Candles)

```pine
// Calculate envelope from N candles (closed + building)
// N = child-per-parent ratio (5 for M5, 3 for M15, 4 for H1/H4, 6 for D)

calc_envelope(int N, 
              float bld_hi, float bld_lo, float bld_cl,
              float p1_hi, float p1_lo, float p1_cl,
              float p2_hi, float p2_lo, float p2_cl,
              float p3_hi, float p3_lo, float p3_cl,
              float p4_hi, float p4_lo, float p4_cl,
              float p5_hi, float p5_lo, float p5_cl) =>
    
    // Collect available candles (building + up to N-1 closed)
    float sum_hi = 0.0, float sum_lo = 0.0, float sum_cl = 0.0
    int count = 0
    
    // Always include building candle
    if not na(bld_hi)
        sum_hi += bld_hi, sum_lo += bld_lo, sum_cl += bld_cl
        count += 1
    
    // Add closed candles up to N-1
    if count < N and not na(p1_hi)
        sum_hi += p1_hi, sum_lo += p1_lo, sum_cl += p1_cl, count += 1
    if count < N and not na(p2_hi)
        sum_hi += p2_hi, sum_lo += p2_lo, sum_cl += p2_cl, count += 1
    if count < N and not na(p3_hi)
        sum_hi += p3_hi, sum_lo += p3_lo, sum_cl += p3_cl, count += 1
    if count < N and not na(p4_hi)
        sum_hi += p4_hi, sum_lo += p4_lo, sum_cl += p4_cl, count += 1
    if count < N and not na(p5_hi)
        sum_hi += p5_hi, sum_lo += p5_lo, sum_cl += p5_cl, count += 1
    
    float env_ceil  = count > 0 ? sum_hi / count : na
    float env_floor = count > 0 ? sum_lo / count : na
    float env_mid   = count > 0 ? sum_cl / count : na
    
    [env_ceil, env_floor, env_mid]
```

### 6.3 Putting It Together — All TFs on M1 Chart

```pine
// Run on M1 chart — all TFs reconstructed and enveloped in real time

// Build candles for each parent TF
[m5_bh, m5_bl, m5_bc, m5_p1h, m5_p1l, m5_p1c, m5_p2h, m5_p2l, m5_p2c,
 m5_p3h, m5_p3l, m5_p3c, m5_p4h, m5_p4l, m5_p4c, m5_p5h, m5_p5l, m5_p5c] = build_candle("5")

[m15_bh, m15_bl, m15_bc, m15_p1h, m15_p1l, m15_p1c, m15_p2h, m15_p2l, m15_p2c,
 m15_p3h, m15_p3l, m15_p3c, m15_p4h, m15_p4l, m15_p4c, m15_p5h, m15_p5l, m15_p5c] = build_candle("15")

[h1_bh, h1_bl, h1_bc, h1_p1h, h1_p1l, h1_p1c, h1_p2h, h1_p2l, h1_p2c,
 h1_p3h, h1_p3l, h1_p3c, h1_p4h, h1_p4l, h1_p4c, h1_p5h, h1_p5l, h1_p5c] = build_candle("60")

[h4_bh, h4_bl, h4_bc, h4_p1h, h4_p1l, h4_p1c, h4_p2h, h4_p2l, h4_p2c,
 h4_p3h, h4_p3l, h4_p3c, h4_p4h, h4_p4l, h4_p4c, h4_p5h, h4_p5l, h4_p5c] = build_candle("240")

[d_bh, d_bl, d_bc, d_p1h, d_p1l, d_p1c, d_p2h, d_p2l, d_p2c,
 d_p3h, d_p3l, d_p3c, d_p4h, d_p4l, d_p4c, d_p5h, d_p5l, d_p5c] = build_candle("1D")

// Calculate envelopes (N = child-per-parent ratio)
[m5_ceil, m5_floor, m5_mid]   = calc_envelope(5, m5_bh, m5_bl, m5_bc, 
    m5_p1h, m5_p1l, m5_p1c, m5_p2h, m5_p2l, m5_p2c, m5_p3h, m5_p3l, m5_p3c,
    m5_p4h, m5_p4l, m5_p4c, na, na, na)

[m15_ceil, m15_floor, m15_mid] = calc_envelope(3, m15_bh, m15_bl, m15_bc,
    m15_p1h, m15_p1l, m15_p1c, m15_p2h, m15_p2l, m15_p2c, na, na, na,
    na, na, na, na, na, na)

[h1_ceil, h1_floor, h1_mid]   = calc_envelope(4, h1_bh, h1_bl, h1_bc,
    h1_p1h, h1_p1l, h1_p1c, h1_p2h, h1_p2l, h1_p2c, h1_p3h, h1_p3l, h1_p3c,
    na, na, na, na, na, na)

[h4_ceil, h4_floor, h4_mid]   = calc_envelope(4, h4_bh, h4_bl, h4_bc,
    h4_p1h, h4_p1l, h4_p1c, h4_p2h, h4_p2l, h4_p2c, h4_p3h, h4_p3l, h4_p3c,
    na, na, na, na, na, na)

[d_ceil, d_floor, d_mid]      = calc_envelope(6, d_bh, d_bl, d_bc,
    d_p1h, d_p1l, d_p1c, d_p2h, d_p2l, d_p2c, d_p3h, d_p3l, d_p3c,
    d_p4h, d_p4l, d_p4c, d_p5h, d_p5l, d_p5c)
```

---

## 7. But Also Test Direct M1 — As a Separate Signal

### 7.1 Why Test It Anyway

Direct M1 averaging is structurally different from the cascade — but that doesn't mean it's useless. It measures something else: the **momentum temperature** at different time horizons. While it can't replace the cascade for structural analysis, it may provide valuable supplementary information:

```
avg(15 M1 closes)   = 15-minute momentum direction
avg(60 M1 closes)   = 1-hour momentum direction
avg(240 M1 closes)  = 4-hour momentum direction

These are effectively SMAs of different lengths on the M1 chart.
When the short SMA crosses the long SMA → momentum shift signal.
This is standard SMA crossover — well-studied, known characteristics.
```

### 7.2 What Direct M1 Averages CAN Tell You

| Direct M1 average | What it measures | Useful for... |
|---|---|---|
| `avg(5 M1 closes)` vs `avg(15 M1 closes)` | M5-vs-M15 momentum alignment | Confirming that M5 momentum is shifting before M15 candle closes |
| `avg(15 M1 closes)` vs `avg(60 M1 closes)` | M15-vs-H1 momentum alignment | Detecting divergence between short and medium momentum |
| `avg(60 M1 closes)` vs `avg(240 M1 closes)` | H1-vs-H4 momentum alignment | Major momentum regime detection |
| All short averages above all long averages | Full bullish momentum alignment | Confirming impulsive phase (all TFs consumed) |
| Short averages crossing below long averages | Momentum regime change (top-down) | Early warning of structural shift (but not structural confirmation) |

### 7.3 The Direct M1 Averages as Momentum Confirmation Layer

```
THE PROPOSED FOUR-LAYER SYSTEM:

Layer 1: DIRECT M1 AVERAGES (momentum temperature)
  → avg(5), avg(15), avg(60), avg(240), avg(1440) M1 closes
  → Tells you: "which momentum regimes are bullish vs bearish"
  → Updates: every M1 bar
  → Use for: earliest possible momentum shift detection
  → NOT for: structural classification (HH/HL/LH/LL)

Layer 2: HYBRID CASCADE ENVELOPE (structural dynamics)
  → Reconstructed candles → cascaded averages (floor/mid/ceiling)
  → Tells you: "what is the dynamic structure at each TF"
  → Updates: every M1 bar (via candle reconstruction)
  → Use for: conviction assessment, CHoCH detection, leg transitions
  → THIS is the structural engine

Layer 3: PERIOD-LEVEL BREAKS (structural confirmation)
  → Previous-period high/low breaks (from iora_bos_choch.pine)
  → Tells you: "a confirmed structural level has been broken"
  → Updates: when breaks occur
  → Use for: confirming structural shift, parent propagation

Layer 4: ZONE-BASED CONFIRMATION (full context)
  → Colour-flip zones, classification, body-close breaks
  → Tells you: "the structural shift is confirmed with zone context"
  → Updates: when zones form
  → Use for: trade execution with SL/TP
```

---

## 8. Testing Protocol

### 8.1 What to Test

Build all three approaches and run them simultaneously on GBPUSD M1 chart. Compare:

| Test | What to measure | Expected outcome |
|---|---|---|
| **Detection speed** | Time between each approach's CHoCH signal and the confirmed structural event | Hybrid fastest, then Direct M1, then Cascading |
| **False signal rate** | How many CHoCH signals are reversed within 2 parent candles | Direct M1 highest (most noise), Cascading lowest, Hybrid in between |
| **Structural accuracy** | Does the CHoCH correctly predict the parent TF swing classification? | Cascade and Hybrid should agree >90%. Direct M1 may diverge on higher TFs. |
| **Conviction reliability** | When STRONG CHoCH fires, does the parent TF swing confirm? | Hybrid and Cascade >70%. Direct M1 STRONG may have more false positives. |
| **Combined value** | Does using Direct M1 as a momentum filter improve Hybrid CHoCH signals? | If Direct M1 momentum aligns with Hybrid CHoCH → higher win rate expected |

### 8.2 The Specific Comparison

For each H4 leg transition detected in replay:

```
LOG:
  T_direct:  time when Direct M1 avg(240 closes) crosses avg(60 closes) bearish
  T_hybrid:  time when Hybrid H4 envelope fires STRONG CHoCH
  T_cascade: time when Cascading H4 envelope fires STRONG CHoCH
  T_period:  time when H1 prev_hi breaks through H4 prev_hi (period-level)
  T_zone:    time when H1 zone forms and classifies as HH/LH
  T_actual:  time when the H4 candle closes and the swing is visually confirmed

EXPECTED ORDER:
  T_direct ≤ T_hybrid < T_cascade ≤ T_period ≤ T_zone < T_actual

IF T_direct is consistently 5-15 min before T_hybrid:
  → Direct M1 adds value as a pre-alert layer
  → Use it to activate monitoring mode before Hybrid CHoCH fires

IF T_direct fires but T_hybrid does NOT follow:
  → Direct M1 was a false signal (momentum shift without structural shift)
  → This is expected — momentum can shift without structure changing
  → The Hybrid correctly filtered it out

IF T_hybrid and T_cascade fire at the same time:
  → The building-candle inclusion in Hybrid didn't help for this event
  → This happens when the structural shift occurs exactly at a child-TF boundary
  → Hybrid's advantage is when shifts happen MID-candle
```

### 8.3 The Bar Replay Checklist

Run on GBPUSD and XAUUSD, minimum 5 trading days:

```
PER STRUCTURAL EVENT (H4 leg transition):

□ Record T_direct, T_hybrid, T_cascade, T_period, T_zone, T_actual
□ Note: did the event occur mid-candle or at candle boundary?
  (Hybrid advantage should be larger for mid-candle events)
□ Note: did Direct M1 give a false signal that Hybrid correctly filtered?
□ Note: did all four approaches agree on direction?
□ Note: conviction level (Strong/Weak/Pre) at each approach
□ Note: consumption state at time of each signal

AGGREGATE METRICS (across all events):

□ Average time advantage: Hybrid vs Cascade
□ Average time advantage: Direct M1 vs Hybrid  
□ False signal rate: Direct M1 (events where Direct M1 fired but Hybrid didn't)
□ Agreement rate: Hybrid vs Cascade (should be >90%)
□ Win rate: when Hybrid STRONG fires, does H4 swing confirm? (target >70%)
□ Win rate: when Direct M1 + Hybrid STRONG both agree? (target >80%)
```

---

## 9. Recommendation

### 9.1 Primary Engine: Hybrid (Approach C)

Use the hybrid approach as the structural detection engine. It gives you M1-speed updates with structurally correct candle values. The building-candle inclusion means you detect mid-candle structural shifts at higher TFs — exactly the "earlier" detection you're after.

### 9.2 Supplementary Layer: Direct M1 Averages

Run the direct M1 averages as a separate **momentum temperature** layer. Use them as a pre-alert: when the M1 momentum averages shift, activate monitoring mode for the hybrid cascade. If the hybrid CHoCH confirms → execute. If it doesn't → the momentum shift was noise.

### 9.3 Do Not Discard: Cascading (Approach A)

Keep the pure cascading approach as a **validation reference**. It's the simplest and most structurally pure. When Hybrid and Cascade disagree, investigate — the disagreement is usually informative (it means the building candle is showing something the closed candles haven't confirmed yet).

### 9.4 Final Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FOUR-LAYER DETECTION                     │
│                                                             │
│  Layer 1: Direct M1 momentum         → EARLIEST ALERT      │
│    avg(5/15/60/240/1440 M1 closes)     (momentum only)      │
│           ↓ if momentum shifts                              │
│  Layer 2: Hybrid cascade envelope    → STRUCTURAL DETECT    │
│    Reconstructed candles + cascade     (conviction-based)    │
│           ↓ if strong CHoCH fires                           │
│  Layer 3: Period-level breaks        → STRUCTURAL CONFIRM   │
│    prev_period high/low breaks         (objective levels)    │
│           ↓ if break exceeds parent                         │
│  Layer 4: Zone-based confirmation    → EXECUTE              │
│    Zone forms + classifies + retest    (full context)        │
│                                                             │
│  Speed:    1 fastest ──────────────────────── 4 most precise│
│  Noise:    1 most noise ──────────────────── 4 least noise  │
│  Use for:  1 alerting → 2 detecting → 3 confirming → 4 exe │
└─────────────────────────────────────────────────────────────┘
```

Test all four layers simultaneously in bar replay. The key metric is whether the combined system (1 alerts → 2 detects → 3 confirms → 4 executes) catches structural events earlier than any single layer while maintaining the same or lower false signal rate.
