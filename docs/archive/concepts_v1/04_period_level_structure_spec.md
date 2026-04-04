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

This spec defines a **simpler, earlier layer** that uses nothing but the **actual candle high and low of each closed period** — the same levels the `iora_bos_choch.pine` indicator already draws on chart. When a child TF's previous-period high or low is broken, that break event *is* the earliest mechanical confirmation that the parent TF is printing a new structural swing (HH, HL, LH, or LL).

The two approaches are not competing — they are complementary layers:

| Layer | Input | Confirms | Speed |
|---|---|---|---|
| **Period-level structure** (this spec) | Raw prev-period high/low | Earliest possible structural shift detection | Fastest — fires on the break candle itself |
| **Zone-based structure** (spec 03) | Zone chain comparison | Zone-classified swing (HH/LH/HL/LL with zone context) | Slightly later — requires zone creation + classification |

Period-level fires first. Zone-based confirms with richer context. Together they give both speed and precision.

---

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
| D | W | 5:1 | 5 D periods build one W period |
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

**This is the earliest possible structural confirmation.**

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

This is the same chain from spec 03, but now grounded in observable period levels rather than zone chains:

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

**You can literally see the cascade on chart.** The ✗ marks on each TF's levels tell you the structural story in real time.

---

## 5. Early Confirmation Cascade — Period-Level Version

### 5.1 The Full Cascade (Bottom-Up)

```
M1 price breaks M1_prev_hi
  → M1 internal: new M1 swing forming
    → IF exceeds M5_prev_hi:
      → M5 internal: new M5 swing confirmed early
        → IF exceeds M15_prev_hi:
          → M15 internal: new M15 swing confirmed early
            → IF exceeds H1_prev_hi:
              → H1 internal: new H1 swing confirmed early
                → IF exceeds H4_prev_hi:
                  → H4 internal: new H4 swing confirmed early
                    → IF exceeds D_prev_hi:
                      → D structural event confirmed
```

Each level checks: does my break also exceed my parent's level? If yes, the event propagates up immediately.

### 5.2 Earliest Confirmation Table (Period-Level)

| Parent event to detect | Confirmed when child TF... | Earliest signal (chart TF) |
|---|---|---|
| **M15 HH** | M5 high break exceeds M15_prev_hi | M1 high break exceeding M5_prev_hi in same direction |
| **H1 HH** | M15 high break exceeds H1_prev_hi | M5 high break exceeding M15_prev_hi in same direction |
| **H1 LL** | M15 low break drops below H1_prev_lo | M5 low break dropping below M15_prev_lo in same direction |
| **H4 HH** | H1 high break exceeds H4_prev_hi | M15 high break exceeding H1_prev_hi in same direction |
| **H4 LL** | H1 low break drops below H4_prev_lo | M15 low break dropping below H1_prev_lo in same direction |
| **D HH** | H4 high break exceeds D_prev_hi | H1 high break exceeding H4_prev_hi in same direction |
| **D LL** | H4 low break drops below D_prev_lo | H1 low break dropping below H4_prev_lo in same direction |
| **W HH** | D high break exceeds W_prev_hi | H4 high break exceeding D_prev_hi in same direction |
| **W LL** | D low break drops below W_prev_lo | H4 low break dropping below D_prev_lo in same direction |

### 5.3 The Key Insight for Entries

The **M1/M5 CHoCH that breaks the child TF's previous-period level in the direction of the parent event** is the earliest mechanical entry trigger. You don't wait for the parent TF candle to close. You don't wait for a zone to form. You enter on the child-TF break that *builds* the parent-TF swing.

---

## 6. Combining with Zone-Based Confirmation

Period-level detection fires first. Zone-based confirmation adds context. The two-layer approach:

### 6.1 Layer 1: Period-Level Alert (Fast)

```
EVENT: H1_prev_hi broken, break exceeds H4_prev_hi
SIGNAL: Potential H4 HH forming — structural shift at H4 detected early
ACTION: Flag for attention, begin monitoring zone behaviour
```

### 6.2 Layer 2: Zone-Based Confirmation (Precise)

```
CONFIRM: H1 supply zone forms at the break point
         Zone top > previous H4 supply zone top
         Zone classified as HH
         Body-close retest of previous H1 demand holds (HL)
ACTION: Trade is confirmed — entry mechanics engage
```

### 6.3 Disagreement Handling

| Period says... | Zone says... | Interpretation |
|---|---|---|
| H4 high broken (HH) | No zone formed yet | Impulse move — zone will form on the pullback. Period-level is correct but entry waits for zone. |
| H4 high broken (HH) | Zone forms but classifies as LH (below prev H4 supply) | False break / liquidity sweep. The wick exceeded the level but the zone (body-based) didn't confirm. Structural shift NOT confirmed. |
| No H4 break | Zone classifies as HH via chain comparison | Internal structure advanced without breaking the period level. Zone-based is more nuanced here — trust the zone classification. |
| H4 high broken (HH) | Zone confirms HH | Full alignment. Highest conviction signal. |

**Rule of thumb:** Period-level for speed, zone-level for conviction. Never trade on period-level alone without zone confirmation. But *monitor* period-level breaks to get positioned ahead of the zone confirmation.

---

## 7. Indicator Enhancement Spec

### 7.1 Current State (`iora_bos_choch.pine` v1)

The indicator draws previous-period high/low lines with break detection (✗ suffix). No structural classification.

### 7.2 Proposed Enhancement — v2

Add the structural state machine (§2) and cross-TF propagation (§3) to the indicator:

**New outputs per TF:**

| Output | Description |
|---|---|
| Break direction label | `▲` (high break) or `▼` (low break) at the break bar |
| Swing classification | `HH` / `LH` / `HL` / `LL` label at the confirmed swing point |
| BOS / CHoCH label | At the break bar: `iBOS`, `iCHoCH`, `eBOS+`, `eCHoCH+` |
| Trend state background | Optional: subtle background tint indicating current TF trend direction |

**Cross-TF propagation visual:**

When a child-TF break exceeds a parent-TF level, draw a **connecting line** from the child break bar to the parent level line, and label the parent level with the confirmed structural event (`H4 HH via H1 break` etc.).

### 7.3 Implementation Approach (Pine Script v6)

```
// Pseudocode for structural state machine
var int    m15_trend = 0   // +1 bullish, -1 bearish, 0 neutral
var float  m15_last_sh = na  // last swing high
var float  m15_last_sl = na  // last swing low
var float  m15_prev_sh = na  // swing high before last
var float  m15_prev_sl = na  // swing low before last

// On M15 high break:
if not na(m15_hi_brk) and na(m15_hi_brk[1])   // first bar of break
    // Confirm swing low (lowest prev_lo since last swing high)
    m15_prev_sl := m15_last_sl
    m15_last_sl := m15_lowest_since_sh  // tracked separately
    string trough_class = m15_last_sl > m15_prev_sl ? "HL" : "LL"
    
    // Classify this high break
    bool exceeds_prev = m15_hi > m15_last_sh
    string break_type = ""
    if m15_trend == 1    // was bullish
        break_type := exceeds_prev ? "iBOS" : "iCHoCH"
    else if m15_trend == -1  // was bearish
        break_type := exceeds_prev ? "iCHoCH" : "iBOS"  
    
    // Check parent propagation
    if m15_hi > h1_prev_hi
        break_type := str.replace(break_type, "i", "e") + "+"
    
    // Update state
    m15_prev_sh := m15_last_sh
    m15_last_sh := m15_hi
```

### 7.4 State Tracking Detail — Lowest/Highest Since Last Swing

The swing detection requires tracking the extreme value between confirmed swings:

```
var float m15_lowest_since_sh = na   // lowest prev_lo since last confirmed swing high
var float m15_highest_since_sl = na  // highest prev_hi since last confirmed swing low

// Reset on each new M15 period
if ta.change(time("15")) != 0
    if m15_lo < nz(m15_lowest_since_sh, 1e18)
        m15_lowest_since_sh := m15_lo
    if m15_hi > nz(m15_highest_since_sl, 0)
        m15_highest_since_sl := m15_hi
```

When a high break confirms a swing low, `m15_lowest_since_sh` becomes that swing low, and the tracker resets. Mirror logic for low breaks confirming swing highs.

---

## 8. The Universal Entry Model — Period-Level Edition

### 8.1 The Template

Every entry follows the same fractal pattern, now expressed in period-level terms:

```
1. DETECT:  Parent TF period level broken → structural shift flagged
2. CONFIRM: Zone forms at break level, classified consistently (HH/HL/LH/LL)
3. WAIT:    Child TF pulls back → child TF period level breaks in opposite direction (retracement)
4. TRIGGER: Grandchild TF period break in the original direction → entry

SL:  Beyond the child TF swing that created the retracement
TP:  Next parent TF period level in the trade direction
```

### 8.2 Concrete Example — Long After H4 CHoCH

```
1. DETECT:  H1 high break exceeds H4_prev_hi → H4 HH forming (CHoCH in bearish H4)
2. CONFIRM: H1 supply zone forms, classified HH. Previous H1 demand holds (HL).
3. WAIT:    M15 pulls back → M15_prev_lo broken (M15 retracement)
4. TRIGGER: M5_prev_hi broken in bullish direction during the M15 pullback
            → ENTRY at M5 high break price
            → SL below the M15 swing low that formed during the pullback  
            → TP at next H4_prev_hi (or H4 supply zone if available)
```

### 8.3 Concrete Example — Short After D LH Confirmation

```
1. DETECT:  H4 high break, but H4_prev_hi < D_prev_hi → H4 HH capped below D level = D LH forming
2. CONFIRM: H4 supply zone forms below D supply. H1 begins making LH sequence.
3. WAIT:    H1 makes first LH (H1_prev_hi not exceeded). M15 pulls back up → M15_prev_hi broken
4. TRIGGER: M5_prev_lo broken in bearish direction during the M15 pullback
            → ENTRY at M5 low break price
            → SL above the M15 swing high that formed during the pullback
            → TP at next H4_prev_lo (or H4 demand zone)
```

---

## 9. Period-Level vs Zone-Level — Decision Matrix

| Question | Use period-level | Use zone-level |
|---|---|---|
| "Has structure shifted?" | ✓ Fastest answer | — |
| "Is the shift confirmed?" | — | ✓ Zone classification + retest |
| "Where do I enter?" | — | ✓ Zone boundary gives precise level |
| "Where is my SL?" | ✓ Previous period extreme is clean | ✓ Zone boundary is precise |
| "Where is my TP?" | ✓ Next parent period level | ✓ Next zone + breaker levels |
| "What's the trend?" | ✓ Period swing sequence (HH/HL or LH/LL) | ✓ Zone chain direction |
| "Am I in impulse or correction?" | — | ✓ Zone chain count (1–5 vs 6–8) |
| "Is this a terminal move?" | — | ✓ Zone count ≥ 5 + exhaustion signals |

**Summary:** Period-level answers "what just happened?" faster. Zone-level answers "what does it mean?" more richly. Use both.

---

## 10. Validation — Bar Replay Checklist

### 10.1 Period-Level Accuracy

On GBPUSD M5 chart with M5 + M15 + H1 + H4 levels enabled:

1. **Break detection timing.** When M15 high line shows ✗, does it fire on the exact bar that exceeded it? (Should be immediate — no lag.)
2. **Cascade propagation.** When M15 high break exceeds H1 high → does the H1 line also show ✗ on the same bar or within the same candle?
3. **Swing classification.** Track manually: after a high break, is the confirmed swing low (lowest low between the two swing highs) correctly identified? Is it classified HH/LH/HL/LL correctly?
4. **BOS/CHoCH accuracy.** In a clear bullish H1 sequence, does a low break below the last HL correctly flag as CHoCH?

### 10.2 Cross-Layer Agreement

5. **Period-level HH matches zone-level HH.** When the period state machine says "H1 HH", does the zone chain also classify the corresponding supply zone as HH? (Should agree in >80% of cases. Disagreements = §6.3 rules apply.)
6. **Period-level CHoCH precedes zone-level CHoCH.** The period break should fire before or simultaneously with the zone-based classification. It should never fire *after*.
7. **No false cascades.** A wick-only break of the parent level (no body close through) should NOT be counted as a structural event at the parent level. Validate that the `high > prev_hi` condition in the Pine code correctly uses the candle high (wick), and decide if this needs tightening to body-close only for parent propagation.

### 10.3 Wick vs Body — The Open Question

The `iora_bos_choch.pine` indicator currently uses `high > prev_hi` for break detection — this includes wicks. For **internal** structure, wick breaks are appropriate (they show liquidity was taken). For **external** structure propagation, there are two schools:

| Approach | Pro | Con |
|---|---|---|
| **Wick break = propagation** | Fastest detection. Catches aggressive institutional moves. | More false signals. Wick-only breaks are often liquidity sweeps, not structural shifts. |
| **Body-close break = propagation** | Fewer false signals. Aligns with zone-based confirmation (which uses body close). | Slower. Misses fast reversals where the wick IS the structural event. |

**Recommended:** Use wick break for **detection** (flag the event), body-close break for **confirmation** (propagate to parent). This mirrors the two-layer approach: period-level (wick) detects early, zone-level (body close) confirms.

---

## 11. Integration with Existing Specs

| This spec section | Maps to... |
|---|---|
| §2 State machine | `03_spec` §4.1 StructureState (now with period-level input instead of zone-only) |
| §3 Cross-TF propagation | `03_spec` §4.4 check_cross_tf_propagation + `02_cascade` §1 bottom-up chain |
| §4 Internal/external definition | `03_spec` §3 TF cascade (same hierarchy, different detection input) |
| §5 Early confirmation table | `02_cascade` §7 complete table (now period-level timing) |
| §6 Zone combination | New — bridges this spec and `03_spec` into a two-layer system |
| §7 Indicator enhancement | Extends `iora_bos_choch.pine` with structural classification |
| §8 Entry model | `02_cascade` §5 M1 CHoCH entries (now expressed in period-level terms) |

---

## 12. Summary — The Three-Sentence Version

Every TF has a previous-period high and low. When a child TF breaks its previous-period level and that break exceeds the parent TF's previous-period level, the parent TF's structure has shifted — detected at child-TF speed with zero lag. Combine this fast detection layer with zone-based confirmation for both speed and precision in the Iora system.
