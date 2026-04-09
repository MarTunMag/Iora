# M1-M5 Mechanical Signal-Flip System Spec

> **Date:** 2026-04-09
> **Status:** PROVEN — M5@M15 signal-flip validated (82.5% WR, PF 36.92, 32K trades on GBPUSD)
> **Discovery:** Fixed SL/TP was the wrong exit mechanism for micro-TF. Signal-flip (every exit IS the next entry) unlocked the structural edge.
> **Baseline results:** `docs/system/m5m15-signal-flip-baseline-results.md`

---

## 1. The Core Problem (Why Fixed SL/TP Fails at M1@M5)

The cascade sweep proved H1@H4 works (PF 2.97-5.40, WR 50-60%). But M1@M5 is consistently negative on both GBPUSD and EURUSD across ALL cascade filter combinations.

**Root cause (updated 2026-04-09):** The `min_sl_spread_mult=3.0` floor in `retest_sweep.py` artificially widens every SL to at least 4.5 pips (spread × 3). The M1@M5 diagnostic showed `avg_sl_pips = 6.00` — meaning natural zone SLs are being inflated. This:
- Distorts R:R (a 2-pip zone gets a 4.5-pip SL → inflated risk)
- Distorts WR (wider SL = fewer hits, but SL is no longer at the structural level)
- Hides the real edge (the 31.5% WR is artificially *improved* by the floor)

Additionally, at M5 zone resolution, zone width is often 1-3 pips. With GBPUSD spread of ~1.0-1.5 pips:
- A 2-pip zone SL means the spread consumes 50-75% of the risk distance
- The R:R calculation is structurally broken — the "risk" is mostly spread, not price movement
- This is NOT an entry quality problem — it's an exit mechanism problem

**Critical for all future M1@M5 testing:** Set `min_sl_spread_mult=0.0` and `min_sl_pips=0.0` to see the true zone-boundary SL data.

**The fix:** Replace fixed SL/TP with **structural signal-based exits**. The M1 HA run-transition that created the zone IS the signal. When the opposite signal fires, that's the exit. Spread is paid once per flip, and the exit distance is variable (structural), not fixed.

---

## 2. Structural Concepts (From Reference Images)

### 2.1 Internal vs External Structure (iBOS / eBOS)

From images `09_internal_vs_external_bos_ibos_ebos.png` and `14/15_trendline` variants:

**External structure** = the HTF swing points. An **eBOS** breaks the most recent swing high/low — this is the REAL trend continuation. An **eCHoCH** breaks the opposite direction — this is the REAL trend reversal.

**Internal structure** = the LTF pullback swings WITHIN the external trend. An **iBOS** breaks a pullback swing — it's an internal continuation. An **iCHoCH** = internal reversal (start of a pullback within the main trend).

**How this maps to our TFs:**
| Concept | Our Implementation | TF Example |
|---|---|---|
| External structure | H4/D1 pivots + trendlines | H4 HH/HL/LH/LL sequence |
| Internal structure | H1/M15 pivots + trendlines | M15 pullback within H4 trend |
| Entry structure | M5 zones, M1 signal-flip | M1 HA transition inside M5 zone |

**Key insight from images 14-15:** Trendlines drawn on internal structure (connecting pivot lows during a pullback) create the **correction trendline**. When this TL breaks, the internal correction is over and the external trend resumes. This IS the `h4_correction` phase that our cascade sweep proved as the #1 filter.

### 2.2 BOS vs CHoCH (Orderflow Shift)

From images `01_bos_vs_choch_orderflow_shift_diagram.webp` and `02_choch_reversal_vs_bos_continuation_live.png`:

- **BOS** = Break of Structure = trend continuation. In bearish: price makes new LL (breaks prior LL). In bullish: new HH (breaks prior HH).
- **CHoCH** = Change of Character = trend reversal. In bearish: price breaks the LH instead of making new LL. In bullish: price breaks the HL instead of making new HH.

From image `04_valid_vs_invalid_bos_choch_gold_h1.jpg` (Gold H1):
- Valid BOS: must have a clean swing structure (not just a wick poke)
- POI (Point of Interest) = the zone created at the origin of the move that caused the BOS/CHoCH
- Valid entry = retest of the POI after the BOS/CHoCH

### 2.3 HTF Supply/Demand Full Cycle

From image `03_bos_vs_choch_htf_supply_demand_full_cycle.jpg`:

The full cycle shows:
1. Price at HTF demand zone → bullish BOS series (HL→HH→HL→HH)
2. Price reaches HTF supply zone → CHoCH (fails to make HH, breaks HL)
3. Bearish BOS series begins (LH→LL→LH→LL)
4. Price reaches HTF demand zone → cycle repeats

**This IS our cascade model:** The M15 zones push price between H1/H4 period Hi/Lo levels. The M5 flip within an M15 zone, confirmed by M1 HA transition = the entry. The cycle reversal = the exit.

### 2.4 Block Types (Order Block → Breaker → Mitigation)

From block_type images:

**Order Block (OB):** The last opposite-direction candle before the impulsive move. In our system = the push zone origin candle.

**Breaker Block:** An order block that gets broken through. The zone that held (was supply) becomes the new support reference on retest. In our system = a broken zone that gets retested from the other side.

**Mitigation Block:** A "failure swing" — price makes H, then LH, then retests the LH level. The LH zone becomes a mitigation block. Key condition: the original H must NOT be broken. In our system = a zone at a lower high that acts as resistance on retest.

From image `04_breaker_vs_mitigation_break_determines_type.jpg`:
- **If the zone's origin level gets broken** → it becomes a BREAKER block (polarity flip)
- **If the zone's origin level holds** → it stays a MITIGATION block (resistance/support that hasn't flipped)

**Critical for M1-M5:** The zone classification (order block, breaker, mitigation) tells us WHETHER to enter. The M1 signal-flip tells us WHEN to enter/exit.

---

## 3. The M1-M5 Signal-Flip Architecture

### 3.1 Timeframe Hierarchy

```
D1/W1    = Directional bias (which side of the market)
H4       = Structural trend (external structure: HH/HL or LH/LL)  
H1       = Period levels (previous H1 Hi/Lo = targets + boundaries)
M15      = Internal structure + zone context (where price pushes to/from)
M5       = Zone flip detection (HA run-transition creates the zone)
M1       = Signal precision (HA transition = exact entry/exit timing)
```

### 3.2 Entry Logic (Signal-Flip Model)

**SELL signal fires when ALL conditions met:**

1. **HTF context (H4/D1):** Bearish bias — H4 making LH/LL or at/near H4 supply
2. **M15 context:** Price is at or near an M15 supply zone (or has just created one)
3. **M5 zone flip:** An M5 supply zone fires (HA run-transition: blue→red on M5)
4. **M1 confirmation:** An M1 supply zone fires inside or near the M5 supply zone
5. **No conflicting HTF demand below:** The nearest H1/H4 demand level is far enough away to provide room

**The entry price** = the M1 zone edge (supply top for sells, demand bottom for buys)

### 3.3 Exit Logic (Signal-Flip)

**NO FIXED SL. NO FIXED TP.**

Instead:
- **Exit SELL** when: M1 demand zone fires (HA transition: red→blue on M1)
- This M1 demand zone simultaneously = **new BUY entry**
- The trade flips direction immediately

**Optional structural SL (safety net):**
- If no M1 opposite signal fires and price breaks the M5 zone top (for sells) or bottom (for buys) = emergency exit
- This is the "structure says you're wrong" level — the zone that justified the entry has been violated

### 3.4 Position Sizing

Since there's no fixed SL, R:R is measured differently:
- **Risk = distance from entry to M5 zone boundary** (the structural invalidation level)
- **Reward = measured on close** (when the opposite M1 signal fires)
- The actual P&L per flip is variable — some flips are +0.5 pips, some are +15 pips
- What matters is the **aggregate edge over N flips**

### 3.5 Filter Dimensions to Test

From our proven H1@H4 cascade findings, adapted to M1@M5:

| Filter | How it applies at M1@M5 | Priority |
|---|---|---|
| **M15 correction phase** | Is the M15 trendline intact? (correction TL not broken) | HIGH — proved universal at H1@H4 |
| **Against H4 bias** | Is the M5 zone against the H4 daily direction? (counter-trend retest) | MEDIUM — proved on GBPUSD |
| **H1 period level proximity** | Is the M5 zone near a previous H1 Hi/Lo? | MEDIUM — period levels are targets |
| **Zone classification** | Is this an order block, breaker, or mitigation block? | HIGH — determines zone quality |
| **M15 trendline break** | Has the M15 correction/impulse TL just broken? | HIGH — proved at H1@H4 |
| **Pivot cascade depth** | How many TFs confirm the same direction? | LOW — marginal at H1@H4 |
| **Zone age** | How old is the M5 zone being entered? | TEST — fresh vs stale |
| **HTF level break context** | Was H4 Lo/Hi or DY Lo/Hi broken before this zone formed? | HIGH — liquidity sweep signal |
| **Zone-above-zone spatial** | Is this M15 D HL sitting above an unbroken H1 demand? | HIGH — institutional support below |
| **M15 HL/LH sequence state** | Is M15 currently in HH/HL mode or LH/LL mode? | HIGH — internal trend direction |
| **Divergence confirmation** | Did M15 DIV+ (longs) or DIV- (shorts) fire at nearby pivot? | MEDIUM — reversal quality signal |

---

## 4. What the JoMa Indicators Already Provide

### joma_zones_levels.pine
- M1/M5/M15/H1/H4 zone detection via HA run-transition (**S5-S9**)
- Zone management with age-based expiry and body-close break detection (**S6**)
- HH/LL/LH/HL sequence tracking per TF (**S5 ha_detect** outputs `hi1_txt`, `lo1_txt`)
- HTF period Hi/Lo levels with break detection: M15, H1, H4, Daily, Weekly, Monthly, Quarterly (**S11-S13**)
- Break markers ("X" suffix) on period levels when violated

### joma_pivots_trendlines.pine
- Multi-TF pivot detection with configurable levels: M15/H1/H4/D1/W1 (**main**)
- HH/LH/LL/HL classification per pivot per TF (**classifyHi/classifyLo**)
- Trendline construction with 2-anchor system (**TLState UDT**)
- Trendline break detection (close or wick configurable) with history (**checkBreak method**)
- Divergence markers (pivot makes higher high but TL suggests lower) (**addAnchor**)
- Auto-scaling TL history to manage drawing limits (**_maxTLHist**)

### What's MISSING (needs to be built in Python engine):
1. **Signal-flip exit mode** — the simulation loop needs to check for opposite zone fire events instead of SL/TP
2. **Zone classification** — order block vs breaker vs mitigation block detection
3. **Internal vs external BOS/CHoCH distinction** — currently we track BOS/CHoCH but don't separate internal/external
4. **M15 correction phase at M1@M5 resolution** — the cascade phase needs to run on M15 instead of H4
5. **Period level proximity scoring** — how close is the entry zone to the nearest HTF Hi/Lo

---

## 5. Implementation Layers

### Layer 1: Signal-Flip Simulation Engine
- Add `exit_mode: str = "signal_flip"` to `RetestConfig`
- In `_simulate_with_bars`: instead of SL/TP price checks, check for opposite-direction zone fire events
- Track: entry price, exit price (opposite signal), flip count, time between flips
- New metrics: avg_flip_pips, avg_flip_duration, flip_count, net_after_spread

### Layer 2: Zone Classification
- Detect order blocks (last opposite candle before impulse)
- Detect breaker blocks (zone broken through, then retested from opposite side)
- Detect mitigation blocks (failure swing retest — LH/HL zone where the extreme holds)
- Classification rule from image 04: break = breaker, no break = mitigation

### Layer 2.5: Structural Sequence Filters (From XAUUSD Live Chart Analysis)

**Context:** On the 2026-04-09 XAUUSD M5 chart with JoMa indicators, we observed:
1. DY Lo X broke → liquidity sweep complete
2. H4 Lo established at ~4697 → new structural low
3. H1 D LL zone formed at ~4700-4715 → institutional demand absorbed selling
4. M15 descending trendline broke → internal correction over
5. M15 now making HH/HL sequence → internal trend bullish
6. Every M15 D HL zone above the H1 demand = mechanical long entry

This structural sequence needs 4 new filter dimensions:

```python
# Dimension 1: HTF Level Break Context
htf_level_break_context: str = "any"
# "after_dy_lo_x"     = DY Lo was broken within last N bars
# "after_dy_hi_x"     = DY Hi was broken
# "after_h4_lo_x"     = H4 Lo was broken
# "after_h4_hi_x"     = H4 Hi was broken
# "after_h1_lo_x"     = H1 Lo was broken
# "after_h1_hi_x"     = H1 Hi was broken
# "any"               = no filter

# Dimension 2: Zone-Above-Zone Spatial Check
zone_spatial_context: str = "any"
# "m15_hl_above_htf_demand"  = M15 D HL sitting above unbroken H1/H4 demand
# "m15_lh_below_htf_supply"  = M15 S LH sitting below unbroken H1/H4 supply
# "first_htf_zone_after_break" = First H1/H4 zone created after HTF level break
# "any"                      = no filter

# Dimension 3: M15 Trendline State at Entry
m15_tl_state: str = "any"
# "after_correction_break"  = M15 descending TL broke (bearish correction over → buy)
#                             or M15 ascending TL broke (bullish correction over → sell)
# "impulse_intact"          = M15 impulse TL still holding (trend continuation)
# "any"                     = no filter

# Dimension 4: Divergence Confirmation
m15_divergence: str = "any"
# "with_div"   = M15 DIV+ fired at nearby pivot low (for longs)
#                or M15 DIV- fired at nearby pivot high (for shorts)
# "no_div"     = no divergence at nearby pivot
# "any"        = no filter
```

**Implementation notes:**
- HTF level break context uses PeriodTracker's existing `hi_brk_t`/`lo_brk_t` timestamps
- Zone spatial check compares zone positions against the live zone array (unbroken HTF zones)
- M15 TL state uses push_trendline's existing break detection
- Divergence uses the joma_pivots_trendlines divergence logic (pivot vs TL slope disagree)

**The mechanical entry rule from the chart:**
```
LONG when ALL:
  1. HTF level break: H4 Lo X or DY Lo X occurred (liquidity grabbed)
  2. H1 D zone created (LL or HL — demand absorbed selling)
  3. M15 TL break: descending M15 correction TL broke
  4. M15 in HL mode: internal structure bullish
  5. Entry at: M15 D HL zone edge (M1/M5 signal-flip inside)

MIRRORED SHORT when ALL:
  1. HTF level break: H4 Hi X or DY Hi X occurred
  2. H1 S zone created (HH or LH)
  3. M15 TL break: ascending M15 correction TL broke
  4. M15 in LH mode: internal structure bearish
  5. Entry at: M15 S LH zone edge (M1/M5 signal-flip inside)
```

### Layer 3: Internal/External Structure Split
- External = H4+ pivots (the macro trend)
- Internal = M15/H1 pivots within H4 swings (the pullback structure)
- Trendlines on internal structure = correction TLs
- Trendlines on external structure = impulse TLs
- Break of correction TL = pullback over, trend resumes (this is `h4_correction`)

### Layer 4: M15-Resolution Cascade Filters
- Port the proven H1@H4 cascade dimensions to M15@H1:
  - `m15_correction` phase (M15 correction TL intact while H1 makes new swing)
  - Period level proximity (M15 entry near H1 Hi/Lo or H4 Hi/Lo)
  - Zone role (is it an OB, breaker, or mitigation block?)
  - Trendline break recency on M15

### Layer 5: Full Sweep
- Run signal-flip on GBPUSD M1@M5 with each filter dimension
- Compare against the old fixed SL/TP M1@M5 results
- If signal-flip WR > 45% and PF > 1.5, we have a viable micro-TF system
- Then run all 8 symbols to validate universality

---

## 6. The Trading Cycle (Putting It All Together)

```
PHASE 1: HTF BIAS (D1/H4)
  D1 making HH/HL → bullish bias
  H4 at or pulling back from H4 demand → looking for longs
  
PHASE 2: M15 CONTEXT  
  M15 correction TL is intact (pullback in progress)
  M15 zone fires near H1 demand level → zone is relevant
  M15 zone is classified as ORDER BLOCK or MITIGATION BLOCK
  
PHASE 3: M5 ZONE FLIP
  M5 demand zone fires (HA blue-to-red transition ends, new red-to-blue begins)
  This M5 zone is INSIDE or ADJACENT to the M15 demand zone
  
PHASE 4: M1 ENTRY SIGNAL  
  M1 demand zone fires inside the M5 demand zone
  → ENTER LONG at M1 zone bottom edge
  
PHASE 5: M1 EXIT / FLIP
  Wait for M1 SUPPLY zone to fire (HA blue-to-red transition on M1)
  → EXIT LONG + ENTER SHORT simultaneously
  
  If M5 zone top is broken before M1 supply fires:
  → EMERGENCY EXIT (structural invalidation)
  
PHASE 6: REPEAT
  The short entry from Phase 5 runs until the next M1 demand fires
  → EXIT SHORT + ENTER LONG
  The cycle continues until HTF context changes
```

---

## 7. Success Criteria

For this system to be production-ready:

| Metric | Minimum | Target | Notes |
|---|---|---|---|
| Win Rate | > 45% | > 50% | Signal-flip should improve from 30-32% |
| Profit Factor | > 1.3 | > 1.8 | Must overcome spread cost per flip |
| Avg Flip Pips | > 2x spread | > 3x spread | Each flip must capture enough to pay spread |
| Flip Rate | < 20/day | 5-15/day | Too many flips = spread death |
| Max Consecutive Losses | < 15 | < 10 | Psychology limit |
| Net After Spread | > 0 | > 2 pips/day avg | The bottom line |
| Cross-Symbol Consistency | 5+ of 8 symbols profitable | All 8 | Universal edge required |

---

## 8. Relationship to H1@H4 System

The M1-M5 signal-flip system and the H1@H4 cascade system are **complementary, not competing:**

- **H1@H4** = lower frequency (10-170 trades/year/symbol), higher per-trade quality (PF 3-5)
  - Used for: swing trades, position building, TP targets for M1-M5
  - Provides: directional bias, structural targets (H4 Hi/Lo, D1 Hi/Lo)
  
- **M1@M5** = higher frequency (5-15 flips/day), lower per-trade quality but higher volume
  - Used for: intraday mechanical execution, always-in-market model
  - Provides: precise entries/exits, signal-flip P&L accumulation

Running BOTH simultaneously = the dual-profile approach. H1@H4 sets context, M1@M5 executes within that context.
