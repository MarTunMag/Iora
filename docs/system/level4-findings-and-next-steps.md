# Iora Strategy — Consolidated Findings & Next Steps

> **Purpose:** Cement all validated findings, sweep results, video education insights, and remaining work items into one reference document. This is the master document for strategy development going forward.
>
> **Date:** 2026-04-05
> **Status:** GBPUSD validated. 4 symbols pending. Strategy refinement ongoing.

---

## 1. What We've Built

| Level | Module | Status | Key Output |
|-------|--------|:------:|------------|
| 0 | Zone engine (no age expiry, birth metadata) | ✅ Done | Push zones with 0% break-through rate |
| 1 | Zone audit (lifecycle analysis) | ✅ Done | Zone population dynamics, retest patterns |
| 2 | Bias timeline (D1/H4/H1 structural state) | ✅ Done | Continuous bias + D-to-W relationship |
| 3 | Opportunity counter (retest event counting) | ✅ Done | ~9M events, 8 TF pairs, 16.5 years |
| 4a | Retest sweep — basic (56→410 configs) | ✅ Done | SQN 2.66 baseline on H1@D1 |
| 4b | Structural SL/TP + limit orders (498 configs) | ✅ GBPUSD | **SQN 23.64 with limit orders** |
| 4c | Cascade indicators (Pine Script) | ✅ Built | Cascade Bias + Cascade Zones v3 |
| 4d | Cross-symbol validation | ⬜ Pending | EURUSD, USDJPY, XAUUSD, GBPJPY |

---

## 2. The Validated Edge — GBPUSD Results (601,843 trades, 498 configs)

### Tier 1: Limit Order Strategies (The Breakthrough)

| Strategy | Trades | WR | SQN | PF | AvgR | Hold | MaxDD |
|----------|:------:|:--:|:---:|:--:|:----:|:----:|:-----:|
| H1@H4 limit sl=zone rr=2.0 | 1,347 | 64.2% | 23.64 | 3.78 | 0.927 | 1.2h | 7R |
| M5@H1 limit sl=zone rr=2.0 | 382 | 69.9% | 15.56 | 4.89 | 1.097 | 0.1h | 4R |
| M15@H4 limit sl=zone rr=2.0 | 247 | 69.2% | 12.20 | 4.57 | 1.077 | 0.3h | 3R |
| H1@D1 limit sl=zone rr=2.0 | 106 | 67.9% | 7.59 | 4.13 | 1.038 | 1.1h | 3R |

### Why Limit Orders Transform Everything
- Entry at zone edge (zone_bottom + 0.1*ATR for longs) instead of bar close
- SL distance shrinks from full zone width to ~0.25 ATR
- Same TP target → R:R explodes from ~1:1 to ~4:1 effective
- Natural fill filter — only the deepest zone penetrations trigger
- Resolution in minutes, not days

### Key Risk: Execution Assumptions
The simulation assumes perfect fills at limit price with zero spread/slippage. In live trading:
- 2-pip spread on a 5-pip risk = 40% of risk eaten by costs
- Slippage at zone edges during volatile moves could miss fills or worsen entry
- **Must model realistic execution costs before going live**

---

## 3. What The Data Proved (Cross-Referenced With Education)

### 3.1 Zones Are Institutional Order Blocks
- **Data:** Push zones: 0% break-through across 13,870 interactions
- **Video confirmation:** Order blocks = last candle before an impulsive move (Video 2, 15). Unmitigated order blocks are the highest conviction zones.
- **Our equivalent:** Push zones = order blocks. The HA run-transition that creates the zone IS the institutional order flow initiation.
- **Limit order thesis:** Placing limit orders at push zone edges = buying/selling exactly where institutions placed their orders. 86.7% WR on M5@H1 push+limit (15 trades — needs more data).

### 3.2 The Cascade Model Is Structurally Sound
- **Data:** H1@D1 with_daily SQN 2.66 (D1 zones as bias), H1@H4 against_daily SQN 1.12 (H4 counter-trend pullbacks)
- **Video confirmation:** Top-down analysis = HTF bias → wait for zone retest → LTF confirmation (Videos 7, 10, 16, 18). "You only go to step three once price has entered into the point of interest" (Brett Go, Video 7).
- **Our cascade:** D1 push zone (bias) → H4 counter-trend (entry area) → M15/M5 CHoCH (precision timing) → limit order at zone edge (execution)

### 3.3 Liquidity Sweeps = Zone Retests
- **Data:** Wick_touch events have positive SQN across all TF pairs. Body_close works for adjacent-TF pairs (M5@M15 SQN 1.52).
- **Video confirmation:** Liquidity sweep = price pushes through a level, grabs stop-losses, then reverses (Videos 3, 13, 14). "You lose because you are entering at the wrong time when there's no liquidity" (Brett Go, Video 13).
- **Our equivalent:** wick_touch = the sweep event. The limit order at the zone edge enters AFTER the sweep grabs the stops — you're entering where institutional orders are resting, not where retail stops are being hunted.

### 3.4 Internal vs External Structure = M5/M15 vs H1/H4
- **Data:** Body_close M5@M15 SQN 1.52 (internal accumulation), reversal zones WR 42.2% (structural inflection)
- **Video confirmation:** Internal BOS builds the external leg. Internal CHoCH = early warning. External CHoCH = confirmed reversal (Videos 6, 15, 18). "Price shifted bearish on the lower time frame to facilitate the higher time frame swing pullback" (Video 18).
- **Our cascade zones indicator** detects both: M15 CHoCH (internal) and H1/H4 BOS/CHoCH (external) with rejection quality scoring.

### 3.5 Candlestick Patterns = Multi-TF CHoCH Events
- **Data:** Reversal zones WR 42.2%, compression-born zones 2x more durable
- **Video confirmation:** Engulfing = the second candle engulfs the first, signaling power shift (Video 1). Pin bar/hammer = strong rejection wick (Videos 1, 3).
- **Our detection:** M5 CHoCH inside a zone = the H1 candlestick pattern is FORMING. We detect at step 1 (M5 CHoCH). Traditional traders wait for step 3 (H1 candle close). Rejection quality scoring (wick ratio, body ratio, follow-through) measures pattern strength.

### 3.6 Session Timing Matters for Liquidity
- **Data:** Session filters were marginal in sweep results
- **Video confirmation:** London open = liquidity enters the market. Asian session = consolidation/accumulation. NY = continuation or reversal of London move. The first H4 candle (opening range) defines intraday structure (Videos 8, 9, 11, 13).
- **Our H4 candle boundary finding:** Median first H1 zone retest = 3.1 hours = one H4 candle. Zone retests align with H4 candle boundaries — structurally meaningful timing.
- **What to test:** Not just session filters, but session-aware entry timing — London open CHoCH at an H4 zone could be the highest-conviction intraday entry.

### 3.7 Chart Clarity = Trading Clarity
- **Video confirmation:** "Your charts look like a bloody war zone. There's indicators everywhere. There is no clear structure." (Video 18). Clean charts with clear zones, bias, and one confirmation signal = the path to consistent execution.
- **Our indicator challenge:** The Cascade Zones v3 is still cluttered. M15 zones as lines (not boxes), shortened labels, M5 CHoCH filtered by rejection quality — these cleanup items are essential for practical use.

---

## 4. What's NOT Yet Tested (Gaps To Fill)

### 4.1 Cascade Trigger Model (HIGHEST PRIORITY)

**Current state:** Each TF pair is tested independently. H1@H4 limit doesn't know about D1 context.

**What's needed:** `entry_mode="cascade"` where:
1. HTF context zone must be active (price INSIDE the D1 zone)
2. THEN look for entry TF zone retest WITHIN the context zone
3. Entry only fires when both conditions are met

**From Video 16 (sniper entries):** "You need to make use of multiple time frames. Start from the higher time frames, identify the trend direction, then go down to the lower time frames for entry confirmation."

**From Video 18 (chart markup):** "If I jump down to my 15-minute time frame right now, I should see price creating lower highs and lower lows" — you only look at the 15m AFTER the HTF tells you to.

**Implementation:** New cascade entry mode in the sweep engine that chains D1 trigger → H4 zone active → M15/M5 limit order at zone edge. The D1 zone being active is the precondition for looking at ANY lower TF.

### 4.2 Layered Cascade Limit Orders (HIGHEST POTENTIAL)

**Concept:** When a context zone (H1/H4/D1) is retested, place limit orders at the **breaker zones** inside it — the LTF zones that were BROKEN during the HTF zone's creation push. These breaker zones flip from support→resistance (or resistance→support) and become the precision retest levels where price will reach as it retraces back into the HTF zone.

**Why breaker zones specifically:**
The H1 demand zone was created by a push that moved price UP. During that push, price broke through M15/M5/M1 supply zones. Those broken supply zones are now **breaker demand zones** — former resistance that now acts as support. When price retraces back into the H1 zone, it will reach these breaker levels because they're the structural points where the push originated. We KNOW price will return to them because that's how retests work — and the zones that broke during the push are exactly where institutional orders are resting.

**The layered cascade limit model:**

```
H1 DEMAND zone created by a bullish push
    │
    │  During the push, price broke through these LTF zones:
    │  (these are now BREAKER zones — former supply → now demand)
    │
    │  ┌─── H1 zone top ───────────────────────┐
    │  │                                         │
    │  │  BRK M15 supply top                     │ ← Buy limit #1 (shallowest retest)
    │  │  (was M15 resistance, now flipped)       │    SL options below
    │  │                                         │
    │  │  BRK M5 supply top                      │ ← Buy limit #2 (deeper retest)
    │  │  (was M5 resistance, now flipped)        │
    │  │                                         │
    │  │  BRK M1 supply top                      │ ← Buy limit #3 (deepest — liquidity sweep)
    │  │  (was M1 resistance, now flipped)        │
    │  │                                         │
    │  └─── H1 zone bottom ────────────────────┘
    │
    │  TP for ALL layers: next H1 supply zone (the HTF structural target)
```

**R:R explosion with breaker zones:**

```
Example: H1 demand zone, TP = next H1 supply (100 pips above)

Layer       | Entry at BRK zone  | SL A (own)  | SL B (HTF)  | TP      | R:R A  | R:R B
BRK M15 lim | M15 brk top        | ~20 pips    | ~35 pips     | 100 pip | 5:1    | 3:1
BRK M5 lim  | M5 brk top         | ~8 pips     | ~28 pips     | 108 pip | 13:1   | 4:1
BRK M1 lim  | M1 brk top         | ~3 pips     | ~25 pips     | 113 pip | 37:1   | 5:1
```

**SL Options (test all three):**

**Option A: SL behind each breaker zone's own boundary**
- Tightest SL per layer → maximum R:R per position
- M5 breaker fails (price pushes through) → stopped on M5 layer
- But M15 and H1 layers still valid (HTF zone hasn't broken)
- Highest R:R but higher stop-out rate on tight layers
- Best for: maximizing individual layer R:R

**Option B: SL behind the HTF zone boundary for ALL layers**
- All layers share the same SL (H1 zone bottom)
- Only stopped out if the entire HTF thesis fails
- H1 zones have 0% break-through → this SL almost never gets hit
- Lower R:R per position but maximum protection
- Best for: capital preservation with position sizing across layers

**Option C: Hybrid — tight SL with HTF backstop**
- Enter at M5 breaker with SL behind M5 breaker (tight)
- If M5 holds and price moves in favor → move SL to breakeven
- If M5 breaks but H1 still holds → re-enter at M15 breaker with SL behind M15
- Aggressive on precision layers, safe on wider layers
- Best for: adaptive position management

**Fill logic:**
- Price retraces after the H1 zone creation
- It returns to the breaker zones because those are where the push originated
- BRK M15 limit fills first (shallowest retracement) → position 1 active
- BRK M5 limit fills deeper → position 2 added
- BRK M1 limit fills at the deepest point → position 3 (maximum precision, the true liquidity sweep)
- If price only reaches BRK M15 → 1 position at 5:1+ RR
- If price reaches BRK M1 → 3 positions with combined 15:1+ average RR

**What the data already confirms:**
- Push zones 0% break-through → the H1 zone WILL hold as the backstop
- Retest #4-10 = sweet spot → the breaker zones inside the H1 zone have been tested enough
- Limit orders SQN 23.64 with single-layer entry → multi-layer on the same thesis should compound
- M5@H1 limit already showed 69.9% WR → the M5 layer IS reaching and filling
- Breaker zones in the sweep showed 42.2% WR as reversal zones → with limit orders at the breaker boundary, this should improve significantly

**From YouTube education (Videos 3, 14, 15, 16):**
- "Smart money enters at the order block AFTER the liquidity grab" → the BRK M1 limit IS the smart money entry at the deepest level
- "90% of retail traders enter too early and get stopped out. The order block is where institutions enter AFTER the trap" (Video 15) → the breaker zone IS the order block that flipped
- "Top-down analysis: weekly → daily → H4 → M15 → entry" (Video 16) → each breaker layer IS a TF level in the top-down cascade
- "Sniper entries use multiple time frames for the best entry" → each layer IS a sniper entry at increasing precision

**Implementation needed:**
- New `entry_mode="cascade_layered"` in RetestConfig
- When a context zone fires, find the LTF zones that were BROKEN during the push (breaker zones)
- Place limit orders at each breaker zone's top (demand) or bottom (supply) with small buffer
- SL mode options: "own" (behind each breaker), "htf" (behind HTF zone), "hybrid" (tight with HTF backstop)
- TP shared: the HTF structural target (next opposing zone on context TF)
- Track each layer independently: fill rate, WR, SQN, P&L
- Report combined portfolio P&L across all layers
- Position sizing: each layer gets a fraction of total risk (e.g., 0.33R per layer = 1R total if all 3 fill)

### 4.3 HMA Direction Filter + HA Cross Signal (IN PROGRESS — building now)

**Concept:** Add HMA(12) or HMA(24) on H4 and/or H1 as a trend direction filter. Only take M5@M15 or M1@M5 retest trades in the HMA direction.

**Enhanced concept — HA candle cross over HMA as an early signal:**
When the H1 or H4 Heikin-Ashi candle CLOSES above the HMA (after being below) = early bullish signal. When HA closes below HMA (after being above) = early bearish signal. This HA-cross-HMA event on H1/H4 becomes the TRIGGER to start looking for downstream LTF entries (M1/M5/M15).

**Why this could work:**
- HMA is responsive (less lag than SMA/EMA) so it catches trend changes early
- The HA candle already smooths noise — HA + HMA alignment is double-filtered direction
- HA closing over a falling/flattening HMA = momentum shift — the structure is changing
- This gives an earlier signal than waiting for a full CHoCH on the same TF
- Downstream LTF entries in the HMA cross direction = riding the new momentum early

**Sweep dimensions to test:**
- `hma_filter="with_hma"` — entry direction must match HMA slope direction (HMA rising = long only, HMA falling = short only)
- `hma_cross_trigger="ha_above"` or `"ha_below"` — only enter on downstream TFs when the HTF HA candle has recently crossed above/below the HMA
- HMA periods: 12 and 24 (test both)
- HMA TFs: H1 and H4 (test both as the direction filter TF)

**Implementation:**
- Compute HMA(12) and HMA(24) on H4 and H1 bars
- Compute HA candle close on H4 and H1 (already exists in the zone engine)
- Detect HA cross events: HA close crosses above HMA = bullish trigger, below = bearish
- New filter: `hma_filter` in RetestConfig
- New trigger: `hma_cross_trigger` — only look for LTF entries within N bars of the HTF HA-HMA cross event
- Test across all TF pairs with limit and cascade_layered entry modes

**Cross-reference with validated findings:**
- H1@H4 against_daily SQN 1.12 → the "against daily" pullback may coincide with HA crossing below HMA (the pullback starts) then HA crossing back above (the pullback ends, resume push)
- The HA-HMA cross on H4 could replace or supplement the bias_filter — it's a momentum-based bias rather than structure-based
- Test both independently AND combined: does HMA cross + bias alignment produce higher conviction than either alone?

**Note:** This adds a lagging indicator to a structural system. The bias filter (from period tracker HH/HL/LH/LL) is already a trend direction signal based on structure, not indicators. HMA might add value as a confirmation, or it might just reduce trades without improving quality. The HA-cross-HMA variant is more interesting because it's an EVENT (a specific moment in time) rather than just a directional filter. Test and let the data decide.

### 4.3 Untested Limit Order Combinations

These specific combinations haven't been tested but are implied by the validated findings:

| # | Combination | Why | Expected Impact |
|---|------------|-----|-----------------|
| 1 | limit + against_daily (H1@H4) | Against-daily wins on H1@H4 market entry. Limit should amplify it. | Could be the best intraday config |
| 2 | limit + reversal zones | Reversal zones = 42.2% WR (market). With limit = potential 80%+ WR | High conviction, low volume |
| 3 | limit + compression-born | Compression zones = 2x durability. Limit at compression zone edge = highest structural conviction | Quality filter |
| 4 | limit + retest_number="4-10" | Retests 4-10 = SQN 2.04 (market). Zone has proven itself. | Timing filter |
| 5 | limit + body_close on M5@M15 | Body_close SQN 1.52. With limit at the zone bottom instead of bar close = even better entry | Adjacent-TF specific |
| 6 | cascade + limit | HTF trigger → LTF limit order at zone edge | The full cascade model |

### 4.4 Spread/Slippage Sensitivity

**Critical before going live.** The limit order configs have very tight SL distances (~0.25 ATR). Model:
- 1-pip spread impact on each TF pair
- 2-pip spread impact (volatile conditions)
- Slippage at zone edges (1-2 pips adverse)
- How much does each reduce WR and SQN?

### 4.5 Walk-Forward Validation

Split the 16.5-year H1 dataset:
- Train: 2009-2019 (10 years)
- Test: 2020-2023 (3 years, includes COVID + rate hikes)
- Validate: 2024-2026 (2 years, current regime)

Do the limit order configs hold out-of-sample?

### 4.6 Cross-Symbol Validation (4 Symbols Pending)

Run EURUSD, USDJPY, XAUUSD, GBPJPY with the 498-config sweep. Key questions:
- Does the limit order effect hold across all symbols?
- Is the push zone 86.7% WR consistent cross-symbol?
- Which TF pair wins per symbol (H1@H4 vs M15@H4 vs M5@H1)?
- Does XAUUSD show the expected long bias (demand zone dominance)?

---

## 5. Sweep Configurations — What Works, What Doesn't

### 5.1 What WORKS (Keep and Expand)

| Dimension | Best Value | Evidence |
|-----------|-----------|---------|
| Entry mode | **limit** | SQN 23.64 vs 1.01 (market). Transforms every metric. |
| SL mode | **zone** (with limit entry) | 64-70% WR, 3-7R MaxDD. Structural SL works but higher DD. |
| TP mode | **fixed_rr=2.0** (with limit) | R:R is effectively 4:1+ because limit entry tightens risk. |
| Touch type | **wick_touch** (H1@H4, H1@D1) | Clean rejection signal. |
| Touch type | **body_close** (M5@M15) | Accumulation inside adjacent-TF zones. |
| Bias | **against_daily** (H1@H4) | SQN 1.12 vs -1.37 (with_daily). Counter-trend pullbacks work. |
| Bias | **with_daily** (H1@D1) | SQN 2.66. At D1 structural levels, trade WITH the trend. |
| Zone role | **push** | 0% break-through. Highest conviction with limit orders. |
| Age | **fresh/young** (LTF pairs) | Most active period. |
| Age | **young** (H1@H4) | H4 zones peak at young, not fresh. |
| Retest # | **4-10** (D1 zones) | SQN 2.04. Zone needs to prove itself. |
| Time since | **12h-3d** (D1 zones) | One parent-TF cycle = sweet spot. |
| Parent TF | **0-1 bars** | Retests at parent-TF boundaries = structural moments. |
| Birth pattern | **compression** | 2x durability, 40.5% WR vs 29-33%. |
| W zone context | **outside** (H1@D1) | D1 zones in open space have room to run. |
| W zone context | **inside** (H1@H4) | Weekly confluence adds structural support. |

### 5.2 What DOESN'T Work (Deprioritize)

| Dimension | Finding | Action |
|-----------|---------|--------|
| PDH/PDL proximity | SQN 1.75 best — marginal | Don't include in core strategy |
| Premium/discount | SQN 1.88 best — marginal | Don't include in core strategy |
| Session filters | Neutral to slightly positive for FX, destroys XAUUSD | Default to session=any |
| Cascade (HTF recent touch) | No benefit for GBPUSD | Replace with cascade TRIGGER model (4.1) |
| sl=atr | Never the best option | Keep as fallback only |

### 5.3 What Needs More Testing

| Dimension | Status | What's Needed |
|-----------|--------|---------------|
| Limit + against_daily | ⬜ Not tested | High priority — could be best intraday config |
| Limit + reversal zones | ⬜ Not tested | High conviction overlay |
| Limit + compression-born | ⬜ Not tested | Quality filter |
| Cascade trigger model | ⬜ Not built | HTF active → LTF limit execution |
| HMA direction filter | ⬜ Not built | H4 HMA(12/24) as trend confirmation |
| Spread/slippage modeling | ⬜ Not built | Critical for live viability |
| Walk-forward validation | ⬜ Not done | In-sample vs out-of-sample |
| Cross-symbol (4 symbols) | ⬜ Not run | Validate limit effect universally |

---

## 6. The Strategy — Simplified from All Sources

### The 6-Step Execution Model

Synthesized from sweep data + 18 YouTube videos + cascade model:

```
STEP 1: BIAS (D1 structure — Videos 5, 7, 10, 18)
  → Identify D1 push zone direction (HH/HL = bullish, LH/LL = bearish)
  → Mark D1 supply/demand zones (the primary bias + target/reversal levels)
  → Note D-to-W relationship (continuation/pullback/inside/neutral)
  → This tells you WHERE price is heading

STEP 2: WAIT FOR LOCATION (H4 zone — Videos 3, 7, 14, 16)
  → Wait for price to reach an H4 zone (counter-trend or with-trend)
  → DO NOT go to lower TF before price is at the zone
  → Set alerts at zone boundaries
  → This tells you WHERE to look for entries

STEP 3: LIQUIDITY SWEEP (zone penetration — Videos 3, 13, 14, 15)
  → Price enters the zone and sweeps stops (wick_touch or body_close)
  → This is the liquidity collection event
  → Smart money is filling orders at these levels
  → Wait for confirmation — don't enter on the sweep itself

STEP 4: CONFIRMATION (M15/M5 CHoCH — Videos 1, 6, 12, 15)
  → M5/M15 CHoCH inside the zone = reversal is starting
  → Candle must CLOSE to confirm (no pre-close entries — Video 12)
  → Rejection quality ≥ 2 (wick ratio + body ratio + follow-through)
  → This IS the H1 hammer/engulfing forming — you see it first

STEP 5: EXECUTION (limit order at zone edge — sweep validated)
  → Place limit order at zone_bottom + 0.1*ATR (longs)
  → Or zone_top - 0.1*ATR (shorts)
  → SL behind the zone boundary (zone SL mode)
  → TP at 2:1 R:R from SL
  → Fill = trade active. No fill = move on.

STEP 6: MANAGEMENT (ride or exit — Videos 4, 5, 6)
  → If in profit: hold until TP or trail with M15 BOS continuation
  → If at D1 zone target: expect reversal — tighten or exit
  → If H4 counter zones start breaking: the push is resuming — exit counter trades
  → Internal BOS = hold. External CHoCH = exit.
```

### Alternative: Pure Limit at Push Zones

For the highest-conviction, lowest-frequency approach:
- Find push zones (order blocks) on H4/D1
- Place limit orders at the zone edge
- SL behind the zone boundary
- TP at 2:1 R:R
- No confirmation needed — push zones have 0% break-through
- 86.7% WR (small sample — needs validation)

---

## 7. Indicator Status

### Cascade Bias (Indicator 1) — ✅ Working
- D1/W1/MN zones with HH/HL/LH/LL labels
- Bias ribbon below chart
- D→W relationship label
- Transition markers

### Cascade Zones (Indicator 2) — Needs Cleanup
**Working:**
- H4 zones with CTR/WITH classification
- M15 CHoCH detection with rejection quality scoring
- H1 SL reference inside H4 zones
- Trendlines on H1/H4
- M5 CHoCH precision entry (filtered by confluence)
- Breaker zone detection
- Confluence scoring dashboard (N/6)

**Needs improvement:**
- M15 zones still too visually heavy — convert to lines
- Zone labels too long — shorten to ~12 chars
- M5 CHoCH markers too frequent — raise confluence threshold
- Visual hierarchy needs clearer layering (H4 prominent, H1 moderate, M15 subtle)

---

## 8. YouTube Education Reference

All 18 transcripts saved at `docs/system/youtube_references/`

| # | Video | Key Concept | Iora Equivalent |
|---|-------|-------------|-----------------|
| 1 | Engulfing pattern | Tsutsumi/engulfing = power shift | M5 CHoCH inside zone = engulfing forming on H1 |
| 2 | Order blocks vs S/D | OB = last candle before inefficiency, unmitigated | Push zone (0% break-through, test_count ≤ 1) |
| 3 | S/D + liquidity sweep | Wait for sweep, then confirmation candle | Wick_touch at zone → M5 CHoCH confirms → limit entry |
| 4 | Complex market structure | Dow theory, 3 market phases, BOS/CHoCH | Period tracker HH/HL/LH/LL + trend classification |
| 5 | Mastering market structure | Move with trend, internal/external | D1 push (external) + H4 counter (internal/pullback) |
| 6 | Internal vs external BOS | iBOS/iCHoCH vs eBOS/eCHoCH | M5/M15 (internal) vs H1/H4 (external) swings |
| 7 | Price action 3 steps | Direction → Location → Execution | D1 bias → H4 zone → M5 CHoCH entry |
| 8 | Quick flip scalper | Opening range high/low as structure | H4 candle range = parent-TF boundary (3.1h finding) |
| 9 | Touch and turn scalper | Fibonacci + opening range | Zone retest entry = touch and turn |
| 10 | Daily bias checklist | PDH/PDL, premium/discount, liquidity targets | Period tracker prev_hi/lo, D1 zone midpoint |
| 11 | 4-hour range strategy | First H4 candle defines intraday range | H4 candle boundaries as structural levels |
| 12 | Candle closures | Never enter before close | Wick_touch = confirmed rejection, body_close = accumulation |
| 13 | Liquidity + timing | London open sweep, Asian consolidation | Session timing + zone retest at session open |
| 14 | Spotting liquidity | Stops behind equal H/L, trendlines | Liquidity pools at zone boundaries |
| 15 | Smart money trap + OB | OB at market shift, avoid retail traps | Push zone at CHoCH = entry, retail enters too early |
| 16 | Sniper entries (top-down) | Weekly → Daily → H4 → M15 → entry | D1 bias → H4 zone → M15 CHoCH → M5 limit |
| 17 | S/D mastery (5 pillars) | Zone quality, entry/exit, why zones work/fail | Zone quality scoring (birth pattern, test count, age) |
| 18 | Chart markup process | Daily → H4 → M15, clean structure | Cascade bias (D1) → cascade zones (H4/M15) |

---

## 9. ML Readiness Assessment

**Current status:** ML is Phase 2 optimization. The mechanical system works (SQN 23.64 with limit orders).

**What ML would add:**
1. **Per-symbol config optimization** — automatically learn GBPUSD = H1@H4 limit, XAUUSD = M5@H1 limit+with_daily
2. **Position sizing** — Kelly fraction from meta-label probability (convert SQN 23 to even higher Sharpe)
3. **Regime detection** — when to scale down (ranging markets) vs scale up (trending)
4. **Rejection quality optimization** — learn optimal wick ratio / body ratio thresholds per TF pair

**What ML is NOT needed for:**
- Zone detection (deterministic, 0% break-through)
- Bias direction (period tracker, validated)
- Entry timing (limit orders at zone edge, validated)
- The cascade logic itself (structural, explainable)

**Full ML spec:** `docs/ml_research/ML_COMPONENT_ANALYSIS.md`

---

## 10. Priority Action Items (When Back from Cabin)

### CRITICAL: Cross-TF TP (The Next Breakthrough)

The current system enters with LTF precision (M5 limit, 1.5 pip SL) but exits at a fixed R:R on the SAME TF (2:1 = 3 pip TP). This captures only the micro-bounce.

**What the cascade model actually implies:** Enter on M5 with M5-level SL, but target the NEXT HTF ZONE as TP.

| Entry | SL | TP (current) | TP (cross-TF) | R:R current | R:R cross-TF |
|-------|:--:|:------------:|:-------------:|:-----------:|:------------:|
| M5@M15 limit | 1.5p | M15 opp (3p) | H1 opp (15p) | 2:1 | 10:1 |
| M5@M15 limit | 1.5p | M15 opp (3p) | H4 opp (50p) | 2:1 | 33:1 |
| M5@H1 limit | 3p | H1 opp (8p) | H4 opp (40p) | 3:1 | 13:1 |
| H1@H4 limit | 5p | H4 opp (15p) | D1 opp (100p) | 3:1 | 20:1 |

**Implementation:** New `tp_mode="htf_zone"` that targets the opposing zone on a HIGHER TF than the context TF. For M5@M15 entries, the TP is at the next H1 or H4 supply/demand. The `next_opposing_zone_price` already exists on RetestCandidate — it just needs to look at a HIGHER TF's zones instead of the context TF's zones.

**This is where ML enters:** Partial TP at the context-TF zone (guaranteed small win), trail remainder to HTF zone (potential large win). ML learns the optimal partial/trail strategy per context.

### Immediate (Day 1)
1. Run 4-symbol sweep (EURUSD, USDJPY, XAUUSD, GBPJPY) with `--parallel-symbols 2`
2. Analyze cross-symbol results — does limit effect hold?
3. Clean up Cascade Zones indicator (M15 as lines, short labels, M5 CHoCH filtering)

### Short-term (Week 1)
4. Add cascade trigger mode: `entry_mode="cascade"` (HTF active → LTF limit)
5. Test limit + against_daily, limit + reversal, limit + compression-born
6. Add HMA(12/24) direction filter and test
7. Model spread/slippage impact on limit configs

### Medium-term (Week 2-3)
8. Walk-forward validation (2009-2019 train, 2020-2023 test, 2024+ validate)
9. Build Flask visualization for trade overlay + equity curve
10. Expand to 38 symbols for portfolio-level validation
11. Begin ML Phase 1 (regime detection HMM on D/W data)

### Long-term
12. Live paper trading with the validated configs
13. ML Phase 2 (meta-labeling for position sizing)
14. Full automation via Python engine

---

## 11. Document Index

All system documentation:

| Document | Purpose |
|----------|---------|
| `docs/system/level1-3-data-analysis.md` | Zone behavior: 9M events, 8 TF pairs, 5 symbols |
| `docs/system/level4-sweep-analysis.md` | Initial 56-config sweep (5 symbols, 270k trades) |
| `docs/system/level4-expanded-sweep-analysis.md` | 410-config GBPUSD analysis + cascade model + candlestick-CHoCH |
| `docs/system/level4-structural-sltp-analysis.md` | 498-config structural SL/TP + limit orders (GBPUSD) |
| **`docs/system/level4-findings-and-next-steps.md`** | **THIS DOCUMENT — master reference** |
| `docs/system/level4-sweep-enhancement-checklist.md` | Sweep gaps checklist (20 sections) |
| `docs/system/trading_concepts_reference.md` | 18 YouTube video synthesis + concept mapping |
| `docs/ml_research/ML_COMPONENT_ANALYSIS.md` | ML phased approach with empirical features |
| `tw_indicators/IORA_CASCADE_INDICATOR_TEMPLATE.md` | Indicator architecture + build phases |
| `docs/superpowers/specs/2026-04-02-retest-entry-system-design.md` | Original system spec (4-level architecture) |
