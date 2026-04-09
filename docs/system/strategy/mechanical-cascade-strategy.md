# Mechanical Cascade Strategy — Complete Ruleset

> **Date:** 2026-04-08
> **Sources:** 37 YouTube transcripts, 8-symbol sweep (3,904 configs), Rules 05/11 archive, TradingView chart analysis, leg architecture spec.
> **Purpose:** THE authoritative document for building and testing the automated cascade entry/exit system.

---

## 1. The Core Model — How Price Moves Through Structure

Price doesn't move randomly. It moves through a **nested cascade of push legs and correction legs**, where each timeframe's structure is built by the timeframe below it:

```
DAILY structure is built by H4 legs
  H4 structure is built by H1 legs
    H1 structure is built by M15 legs
      M15 structure is built by M5 legs
        M5 structure is built by M1 legs
```

**At every moment, each TF is either PUSHING (impulse) or CORRECTING (pullback).**

The key insight: **an impulse at one TF IS a correction at the TF above.** When D1 pushes down, the H4 pulls back (corrects) within that push. When the H4 correction ends and the D1 push resumes, the H1 pulls back within that H4 leg. All the way down.

---

## 2. The Six Layers — What Each TF Tells You

| TF | Role | What it tells you | Iora detection |
|---|---|---|---|
| **D1** | BIAS — overall direction | Which side to trade. D1 push zone = the trend. | D1 PeriodTracker trend (+1/-1), D1 push zone direction |
| **H4** | CONTEXT — where you are in the push | Is D1 pushing or correcting? H4 zone = where the pullback/push reaches. | H4 PeriodTracker, H4 zones, H4 trendlines |
| **H1** | STRUCTURE — the swing points | H1 zones count the push/correction waves. H1 supply #1-8 = the push is extending. | H1 zone counting, H1 BOS/CHoCH |
| **M15** | TRIGGER — when to enter/exit | M15 trendline break = H1 sub-wave complete. M15 CHoCH = reversal starting. | M15 push zones, M15 BOS/CHoCH |
| **M5** | EXECUTION — the ride | M5 zones = the waves you ride. Enter/exit at M5 zone edges. | M5 zones inside H4 context |
| **M1** | PRECISION — sniper entry | M1 CHoCH inside M5 zone = the exact turning point. | M1 CHoCH detection (future) |

---

## 3. Trendline Rules — The Structural Completion Signals

### 3.1 How Trendlines Are Built (from Rule 05)

| TL type | Connects | Meaning | Break means |
|---------|----------|---------|-------------|
| **Impulse TL** (solid) | HH tops or LL bottoms | The PUSH direction | **Potential reversal** — push exhausted |
| **Correction TL** (dashed) | LH tops or HL bottoms | The PULLBACK direction | **Trend resumes** — pullback failed |

**Critical distinction:** Impulse TL break ≠ correction TL break. They mean opposite things.

### 3.2 What Each TL Break Confirms

| TL that breaks | What it confirms | Action |
|---|---|---|
| M5 TL break | M15 sub-wave complete | Look for M15 zone entry |
| M15 TL break | **H1 push complete** | H1 wave done — prepare for reversal or continuation |
| H1 TL break | **H4 push complete** | H4 level reversal starting — major entry/exit signal |
| H4 TL break | **D1 leg complete** | Daily bias may be shifting — reassess everything |

### 3.3 Impulse vs Correction TL Cascade (from your charts)

```
EXAMPLE: D1 BEARISH (price pushing down)

H4 IMPULSE TL (descending, connecting LH supply tops):
  │
  ├── H4 CORRECTION TL (ascending, connecting HL demand bots):
  │     │
  │     ├── Correction TL breaks DOWN = H4 impulse RESUMES
  │     │   → New H4 push leg down (sell continuation)
  │     │   → Enter short at the H1 supply that caused the break
  │     │
  │     └── Correction TL HOLDS = H4 still correcting
  │         → Wait for price to reach H4 supply zone
  │
  └── Impulse TL breaks UP = POTENTIAL D1 REVERSAL
      → H4 push is done
      → The H1 zone that caused this break = reversal target
      → Enter long at M15 demand inside this H1 zone
      → TP at the last H4 supply zone
```

---

## 4. Zone Counting — The Push Completion Model (from your charts + Rule 11)

Your screenshots show the key insight: **count the H1 zones created during a push to know when it's exhausting.**

### 4.1 The 5+3 Wave Pattern

From your chart annotations: "8 H1 supply zones as we create our WEEKLY low. Can this be 5 impulse waves + 3 correction waves?"

```
H1 SUPPLY ZONES DURING D1/H4 PUSH DOWN:

Zone #1 (impulse)  ─── First push down from D1 supply
Zone #2 (impulse)  ─── Continuation, breaking H4 demand
Zone #3 (impulse)  ─── Deep push, approaching H4 support
Zone #4 (correction) ─ Pullback zone (H4 HL forming)
Zone #5 (impulse)  ─── Resumed push past Zone #3
Zone #6 (correction) ─ Shallow pullback
Zone #7 (correction) ─ Another pullback (H4 LH + H1 LH = correction waves starting)
Zone #8 (impulse)  ─── Terminal push (final extension)

REVERSAL SIGNAL: H1 supply trendline breaks
→ Zone #8 = the last push zone
→ The H1 demand created at the low = your long entry
→ TP = Zone #7 or #6 (the last unbroken H1 supply)
```

### 4.2 Zone Tracking — What We Already Detect

| What to track | How Iora detects it | Status |
|---|---|---|
| Last created H1 supply during push | Push zone birth events per TF | ✅ Implemented |
| H1 zone count | Zone counting in opportunity_counter.py | ✅ Implemented |
| H1 zone that caused H4 CHoCH | "The zone active when H4 makes HL" | ❌ Need attribution |
| H4 zone that caused D1 CHoCH | Same logic, one level up | ❌ Need attribution |
| Zone "freshness" (unbroken) | test_count tracking | ✅ Implemented |

### 4.3 The Reversal Target Rule (Rule 11)

```
The H1 zone that CAUSED the H4 CHoCH = your reversal target.

When H4 is pushing down and then H1 makes an HL (instead of LL):
  → This H1 HL = H4 HL (CHoCH at H4 level)
  → The last H1 SUPPLY zone before this HL = the reversal target
  → When price pushes back up here: EXIT longs, ENTER shorts
```

From your screenshot: "We need to mark our H1 reversal zone, where we when we now break our H1 Supply zone. As further indicated with the break of the last H1 - H1 supply zone trendline."

**This is the connection between trendline breaks and zone targets:**
1. H1 supply trendline breaks UP → the push down is over
2. The last unbroken H1 supply = the reversal target (TP for longs, entry for shorts)
3. The M15 demand at the bottom = the reversal entry (long entry)

---

## 5. The Complete Entry/Exit Flow — Mechanical Steps

### 5.1 LONG Entry (at terminal reversal)

```
PRE-CONDITIONS:
  □ D1 trend = bearish (D1 supply pushing down) OR at D1 demand zone
  □ H4 has pushed down (H4 making LLs)
  □ H1 supply count = 5+ zones (push is extended)
  □ H1 supply trendline exists (connecting LH supply tops)

TRIGGER:
  □ H1 supply TL breaks UP (M15 closes above projected TL)
  → This confirms: H1 push down is COMPLETE
  → The H4 HL is forming

ENTRY:
  □ M15 demand zone forms at or near the low
  □ M5 zones exist inside this M15 demand (zone refinement)
  □ Place buy limit at M5 demand zone edge (inside M15 demand, inside H4 demand)
  □ SL below the M5 zone (structural SL)
  □ Or SL below the M15 zone (wider, safer)
  □ Or SL below the H4 zone (widest, safest — push zones 0% break-through)

TP TARGETS (cascading):
  □ TP1 (70%): Fixed R:R 3.0 from SL (the scalp — locks profit)
  □ TP2 (30%): Last unbroken H1 supply zone (the reversal target from Rule 11)
  □ TP3 (optional): The H4 supply that started the push (if push continues)

MANAGEMENT:
  □ After TP1 hit: SL moves to breakeven
  □ Each M15 iBOS = the push is extending, hold
  □ Each H1 iBOS = major progress toward target, tighten trailing SL
  □ H1 eCHoCH at target supply = EXIT (push complete, reversal starting)
```

### 5.2 SHORT Entry (at reversal target)

```
PRE-CONDITIONS:
  □ Price has pushed UP into the H1 supply zone identified in 5.1
  □ This H1 supply = the reversal target (it caused the H4 CHoCH)
  □ D1 trend still bearish (this H4 HH is BELOW the last D1 supply = D1 LH)

TRIGGER:
  □ M15 CHoCH (or M15 demand TL breaks DOWN) inside the H1 supply
  → This confirms: the push up into the reversal zone is failing

ENTRY:
  □ M5 supply zone inside the H1 supply zone
  □ Sell limit at M5 supply zone edge
  □ SL above the H1 supply zone
  □ TP at M15 demand zone below (the zone where longs entered)
  □ Or TP at next D1 demand zone (full cascade ride)

This is the REVERSAL entry. It's the highest-conviction short because:
  - D1 bias is bearish (structural direction)
  - H4 has just completed its correction (pullback up is done)
  - H1 supply zone = proven resistance (it caused the prior CHoCH)
  - M15/M5 is confirming the reversal inside the zone
```

### 5.3 CONTINUATION Entry (riding the push)

```
PRE-CONDITIONS:
  □ D1 trend established (bearish or bullish)
  □ H4 correction TL exists (ascending HLs during bearish D1, or descending LHs during bullish D1)
  □ The correction TL breaks (H4 HL breaks = impulse resumes)

TRIGGER:
  □ H4 correction TL breaks
  → The correction is over, the D1 push resumes

ENTRY:
  □ H1 zone that caused the correction TL break = entry zone
  □ M15 inside that H1 zone = refined entry
  □ M5 inside that M15 = sniper entry
  □ SL above the H1 zone (for shorts) or below (for longs)
  □ TP at next H4 zone target (continuation target)
```

---

## 6. The TF Step-Down Decision Tree

This is the "two steps down" rule from V23 (JeaFx), mapped to our cascade:

```
STEP 1: DAILY — What's the bias?
  → D1 push zone direction = trade direction
  → D1 demand/supply zones = ultimate targets/reversals
  → D1 trend (HH/HL or LH/LL) = bull or bear

STEP 2: H4 — Where are we in the push?
  → Is D1 pushing? → H4 is the correction within that push
  → Is D1 correcting? → H4 is the impulse of that correction
  → H4 zones = the context zones (where price is heading)
  → H4 trendlines = push/correction structure

STEP 3: H1 — What's the structural count?
  → Count H1 zones in the current push direction
  → H1 zones 1-3 = early push (risky to counter)
  → H1 zones 4-7 = extended (look for terminal signals)
  → H1 zones 8+ = exhausted (terminal reversal likely)
  → H1 trendline break = push completion confirmed

STEP 4: M15 — What's the entry trigger?
  → M15 CHoCH = first sign of reversal
  → M15 TL break = H1 sub-wave complete
  → M15 demand/supply zones = the entry area
  → DON'T go to M15 until H1 gives you the signal

STEP 5: M5 — Where exactly to enter?
  → M5 zones INSIDE M15 zones = refined entry (zone refinement)
  → M5 zone edge = limit order placement
  → M5 structure (BOS/CHoCH) = real-time confirmation

STEP 6: M1 — Sniper precision (optional)
  → M1 CHoCH inside M5 zone = the exact turning point
  → M1 TL break = M5 sub-wave complete
  → Only use if you need tighter SL for better R:R
```

---

## 7. What We Need to Build — Implementation Requirements

### 7.1 Trendline Engine (Python — port from Pine)

**Source:** `tw_indicators/iora_structure/iora_pivot_hl_trendlines.pine`

**What to port:**
1. Pivot detection at each TF (swing highs/lows from period tracker data)
2. Trendline construction (connect latest two pivots, project forward)
3. Break detection (body close through projected TL price)
4. Break events (emit TrendlineBreakEvent with TF, impulse/correction type, break bar, break price)
5. "Which zone caused the break?" attribution (the last zone created before the break bar)

**New module:** `src/iora/engine/trendline_tick.py`

**New dataclass:**
```python
@dataclass(slots=True)
class TrendlineBreakEvent:
    tf: str                  # "M15", "H1", "H4"
    tl_type: str             # "impulse" or "correction"
    direction: str           # "bullish_break" or "bearish_break"
    break_bar: pd.Timestamp
    break_price: float
    projected_price: float   # Where the TL was at break time
    causing_zone_id: str     # The zone that caused the break
    anchor1_price: float     # TL anchor point 1
    anchor2_price: float     # TL anchor point 2
```

### 7.2 Zone Attribution ("Which Zone Caused the CHoCH?")

**Currently missing:** When H4 makes a CHoCH (HL breaks = new trend), we need to tag WHICH H1 zone was the last supply before that event.

**Implementation:** In `push_zone_tick.py`, when a CHoCH is classified, store the last zone on the opposite side as `choch_causing_zone`.

### 7.3 Cascade Direction State

**New module:** `src/iora/engine/cascade_state.py`

```python
@dataclass(slots=True) 
class CascadeState:
    # Per-TF trend
    d1_trend: int           # +1/-1/0
    h4_trend: int
    h1_trend: int
    m15_trend: int
    
    # Trendline state per TF
    h4_impulse_tl_broken: bool
    h4_correction_tl_broken: bool
    h1_impulse_tl_broken: bool
    h1_correction_tl_broken: bool
    m15_impulse_tl_broken: bool
    m15_correction_tl_broken: bool
    
    # Zone counting
    h1_push_zone_count: int    # How many H1 zones in current push
    
    # Reversal targets
    h1_reversal_target_zone: str  # The zone that caused H4 CHoCH
    h4_reversal_target_zone: str  # The zone that caused D1 CHoCH
    
    # Current phase
    phase: str  # "d1_push", "h4_correction", "h4_terminal", "reversal_entry", etc.
```

### 7.4 Sweep Dimensions for Cascade

New filter dimensions to test:

| Dimension | Values | What it tests |
|---|---|---|
| `tl_break_filter` | "any", "after_impulse_break", "after_correction_break" | Only enter after specific TL break type |
| `h1_zone_count_filter` | "any", "1-3", "4-7", "8+" | Only enter at specific push extension level |
| `reversal_target_entry` | True/False | Only enter at the zone identified as reversal target |
| `cascade_phase` | "push", "correction", "terminal", "reversal" | Only enter during specific cascade phase |

---

## 8. What We Can Test NOW vs What Needs Building

### BEING BUILT NOW (Phase B — cascade trendline engine):
- Trendline detection in Python (port from Pine) — **Layer 1 DONE**
- Zone attribution (which zone caused the CHoCH) — **Layer 2 DONE**
- Cascade direction state machine — **Layer 3 DONE**
- H1 zone counting in current push — **DONE**
- TL break events as sweep filter dimension — **In progress**
- EW-derived exhaustion signals (zone4 overlap zone1, wave3 extension) — **DONE**
- CHoCH conviction classification (strong/weak/pre) — **Being added**
- Momentum consumption count (child TFs flipping after parent CHoCH) — **Being added**

### ALSO IN CURRENT SWEEP (existing engine filters):
- `bias_filter` = "against_daily" / "with_daily" on H1@H4 limit partial
- `test_count_filter` = retest 4-10 on all configs
- `zone_role_filter` = "push" / "reversal" / "continuation"
- `age_filter` = "fresh" / "young" on nested configs

### FUTURE (Phase C):
- HL_Ladder child-confirmation pivot rule (see Section 8.1)
- Three-source envelope conviction (floor/mid/ceiling from 04a)
- Full hybrid computation architecture (04e)
- M1 precision entries
- Dynamic averages from 04b spec

### 8.1 Future Enhancement: HL_Ladder Child-Confirmation Pivots

**Source:** `docs/mt5_indicator/HL_Ladder.mq5` — custom MT5 indicator (7-level pivot detection)

**What it does that we don't:** The HL_Ladder confirms a parent-TF pivot only when a child-TF pivot appears AFTER it in time. For example, an H4 high is only confirmed when an H1 LOW forms after the H4 high's timestamp. This implements the leg architecture principle: "A high is only confirmed when the subsequent down-leg begins."

**Our current approach:** PeriodTracker confirms pivots on period close (when the H4 candle closes, its high becomes `prev_hi`). This can tag "swing highs" that aren't actually confirmed — the H4 candle closed but H1 hasn't started the down-leg yet.

**Impact if added:** More accurate pivot timestamps → more precise trendline anchors → better TL break detection → more precise H1 zone counting and EW overlap detection.

**When to add:** After the initial cascade sweep results. If zone counting or TL breaks show noise, this is the refinement to try.

### 8.2 Structural Specs Cross-Reference

| Spec | Key Concept | Status | Video Validation |
|---|---|---|---|
| **04c: Conviction I/E** | Strong CHoCH = external (all 3 sources confirm). Weak = liquidity sweep. Pre = momentum fading. | **Being added** to cascade state as `choch_conviction_filter` | V3, V5, V6, V13, V14, V15 (11+ videos) |
| **04d: Momentum Consumption** | After parent CHoCH, count child TFs flipping to new direction. All flipped = fully committed. | **Being added** as `min_consumption_count` | V7, V18 ("don't drop to LTF until HTF is clear") |
| **04b: Leg Architecture** | D1 high built by H4 up-legs built by H1 up-legs. Need opposing leg to confirm swing. | **Captured** by cascade phase + H1 zone counting. HL_Ladder confirmation rule is future enhancement. | V5, V6, V10 |
| **04a: Three-Source Envelope** | Floor (avg lows), Mid (avg closes), Ceiling (avg highs) — three sources diverging = compression, converging = trend. | **Future** — Pine-first feature, needs indicator port. | PTS-4, PTS-5 |
| **04e: Computation Architecture** | Hybrid per-bar computation combining dynamic averages with zone-based detection. | **Future** — architectural enhancement after core cascade validated. | N/A |
| **04: Period Level Structure** | Dynamic averages per TF as structural levels (support/resistance from averaged child-TF data). | **Partially captured** — PeriodTracker has the raw data. Dynamic averages not computed. | V10 (daily bias from swing range) |
| **EW Patterns** | Wave 4 overlap = exhaustion/diagonal. Wave 3 extension > 1.618 = strong trend. | **Being added** as `ew_overlap_filter` and `ew_extension_filter` | Your charts (8 H1 supply zones = 5+3 pattern) |

---

## 9. Expected Impact on Performance

| Enhancement | Expected WR impact | Expected SQN impact | Trade count impact | Source |
|---|---|---|---|---|
| Bias filter (against_daily) | +2-5% | +10-20% SQN | -30% trades | Sweep data |
| TL break trigger | +5-10% | +20-40% SQN | -50% trades | 11 videos |
| H1 zone count 5+ filter | +5-8% | +15-30% SQN | -60% trades | Your charts |
| Reversal target entry | +10-15% | +30-50% SQN | -70% trades | Rule 11 |
| **CHoCH conviction (strong_only)** | **+5-15%** | **+20-40% SQN** | **-40% trades** | **Spec 04c + 11 videos** |
| **Momentum consumption (count >= 2)** | **+3-8%** | **+10-20% SQN** | **-50% trades** | **Spec 04d + V7, V18** |
| **EW zone4 overlap (overlap_only)** | **+5-10%** | **+15-25% SQN** | **-70% trades** | **EW + your charts** |
| **EW wave3 extension (not_extended)** | **+2-5%** | **+5-15% SQN** | **-30% trades** | **EW rules** |
| Combined (best of above) | Potential 65-75% WR | Unknown — needs data | ~300-500 trades/year across 8 symbols |

**The tradeoff is clear:** each filter improves WR/SQN but reduces trade count. The question is whether the remaining trades have enough volume to be statistically significant and practically useful (~1-2/day across 8 symbols).

**This is exactly what the cascade sweep will answer.** All these dimensions are being tested in a single GBPUSD sweep run.

### 9.1 Filter Priority Ranking (by expected value)

Based on video consensus strength + structural logic:

1. **CHoCH conviction (strong_only)** — Highest value. Directly filters false breaks/liquidity sweeps. 11+ videos agree.
2. **TL break trigger** — Second highest. "Never enter on break alone, wait for retest + confirmation." 6 dedicated trendline videos.
3. **Cascade phase (h1_terminal)** — Third. Only enter when push is exhausted. Your charts validate.
4. **Momentum consumption (count >= 2)** — Fourth. "Don't drop to LTF until HTF is clear." Mechanized patience.
5. **EW zone4 overlap** — Fifth. Mechanical exhaustion detection. Novel but structurally sound.
6. **Bias filter (against_daily)** — Sixth. Already proven on market entries. Testing with limit.
7. **EW wave3 extension** — Seventh. Protective filter (don't counter strong trends). Useful but fewer trades affected.

---

## 10. Cross-Reference

| Document | What it covers |
|---|---|
| `mechanical-ruleset-validated.md` | Proven rules from sweep data (13 rules, 8 disproven) |
| `deep-system-audit-2026-04-07.md` | Full audit with 37 transcripts + spread model audit |
| `htf-triggered-sweep-analysis.md` | 8-symbol nesting sweep results (H1@H4 universal) |
| `superpowers/specs/2026-04-08-cascade-trendline-engine-spec.md` | Design spec for the cascade build (14 tasks) |
| `archive/concepts_v1/standalone_rules/05_TRENDLINE_BREAKS.md` | Original TL break rules (impulse vs correction) |
| `archive/concepts_v1/standalone_rules/11_ZONE_TRACKING_REVERSAL_TARGETS.md` | Zone tracking + reversal target identification |
| `mechanical_structure_legs/04b_leg_architecture_spec.md` | Leg anatomy and nested structure |
| `mechanical_structure_legs/04c_conviction_internal_external_spec.md` | CHoCH conviction (strong/weak/pre) — being added to sweep |
| `mechanical_structure_legs/04d_momentum_consumption_spec.md` | Momentum consumption cascade — being added to sweep |
| `mechanical_structure_legs/EW_PATTERNS.md` | Elliott Wave rules — zone4 overlap + wave3 extension being tested |
| `mt5_indicator/HL_Ladder.mq5` | Child-confirmation pivot rule — queued for future |
| `trading_concepts_reference.md` | 18 video concepts mapped to Iora |
| `youtube_references/trendline_concepts_summary.md` | 6 trendline video summary |
