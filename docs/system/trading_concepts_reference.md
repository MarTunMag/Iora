# Trading Concepts Reference — YouTube Education Synthesis

> **Purpose:** Synthesized insights from 6 trading education videos, mapped to Iora's cascade zone system. These concepts validate and extend our data-proven approach.
>
> **Date:** 2026-04-04
> **Key insight:** Everything described in these videos — engulfing patterns, order blocks, supply/demand zones, liquidity sweeps, internal/external structure — maps directly to concepts Iora already detects mechanically. The videos confirm our approach is structurally sound and reveal terminology bridges between traditional SMC education and our system.

---

## Source Videos

| # | Topic | URL | Chars |
|---|-------|-----|------:|
| 1 | Tsutsumi/Engulfing Pattern — 4 strategies | [youtube.com/watch?v=1NSsM47ayUk](https://youtube.com/watch?v=1NSsM47ayUk) | 25,032 |
| 2 | Order Blocks vs Supply/Demand vs S/R | [youtube.com/watch?v=FjB8SRc0mi8](https://youtube.com/watch?v=FjB8SRc0mi8) | 15,483 |
| 3 | Supply/Demand + Liquidity Sweep + Candle Trigger | [youtube.com/watch?v=fVgEBJKK2Hk](https://youtube.com/watch?v=fVgEBJKK2Hk) | 31,320 |
| 4 | 3 Methods to Read Complex Market Structure | [youtube.com/watch?v=ZTd83Rwy89Q](https://youtube.com/watch?v=ZTd83Rwy89Q) | 15,862 |
| 5 | Mastering Market Structure (comprehensive) | [youtube.com/watch?v=ygleB1CLhUE](https://youtube.com/watch?v=ygleB1CLhUE) | 72,169 |
| 6 | Internal vs External Structure (NFX Academy) | [youtube.com/watch?v=FYQl8uouYHo](https://youtube.com/watch?v=FYQl8uouYHo) | 13,175 |
| 7 | Price Action in 3 Steps (Brett Go) | [youtube.com/watch?v=6nMqpn8O9NE](https://youtube.com/watch?v=6nMqpn8O9NE) | 32,828 |
| 8 | Quick Flip Scalper — Opening Range | [youtube.com/watch?v=XFtayhPIdEs](https://youtube.com/watch?v=XFtayhPIdEs) | 20,649 |
| 9 | Touch and Turn Scalper — Fibonacci | [youtube.com/watch?v=BifyQ6ppdLU](https://youtube.com/watch?v=BifyQ6ppdLU) | 17,550 |
| 10 | Daily Bias Checklist (Brett Go) | [youtube.com/watch?v=QyEhAuFem6Y](https://youtube.com/watch?v=QyEhAuFem6Y) | 45,850 |
| 11 | 4-Hour Range Scalping Strategy | [youtube.com/watch?v=O5eC5lY7ZXY](https://youtube.com/watch?v=O5eC5lY7ZXY) | 15,230 |
| 12 | Candle Closures — Validation Before Entry | [youtube.com/watch?v=JD_sWSjIiJE](https://youtube.com/watch?v=JD_sWSjIiJE) | 17,875 |

Full transcripts saved at `docs/system/youtube_references/`

---

## Concept Mapping: Video Education → Iora System

### 1. Engulfing/Tsutsumi Pattern = Multi-TF CHoCH Event

**From Video 1:** The Tsutsumi (engulfing) pattern is a 2-candle formation where the second candle completely engulfs the first, signaling a power shift between buyers and sellers.

**What it IS structurally:** An H1 engulfing at a supply zone = inside that H1 candle, M5/M15 was bullish → M5/M15 CHoCH occurred → M5/M15 pushed aggressively in the new direction, enough to engulf the previous H1 body. The candlestick pattern is the visual symptom on the parent TF. The CHoCH is the structural cause on the child TF.

**Iora equivalent:** M5 CHoCH inside a zone = the engulfing/hammer is FORMING on H1 (earliest signal). M15 CHoCH confirms = the pattern is CONFIRMED. H1 candle closes = the pattern is COMPLETE (visible to traditional traders). We detect steps 1 and 2 — traditional traders wait for step 3.

**Rejection quality scoring** measures the QUALITY of this CHoCH:
- Wick ratio = how strong was the rejection (hammer/pin bar quality)
- Body ratio = how aggressive was the follow-through (engulfing quality)
- Follow-through = did the next bar continue (confirmation)

### 2. Order Blocks = Push Zones (Origin of Institutional Flow)

**From Video 2:** An order block is the last candle that caused market inefficiency — where institutional traders likely made their decisions. Valid order blocks must: (1) create inefficiency/FVG, (2) break structure (BOS/CHoCH), (3) be unmitigated (untested).

**Iora equivalent:**
- Order block = **push zone** — the zone created at the HA run transition that initiated the structural move
- "Creates inefficiency" = the impulsive move away from the zone (the push)
- "Breaks structure" = BOS or CHoCH classification on the push
- "Unmitigated" = test_count == 0 or 1 (first retest is the highest conviction entry)
- Push zones have **0.000% break-through rate** across 13,870 interactions — they ARE the institutional order flow origin

**What Iora adds that order block theory doesn't:** quantified durability (push zones never break), birth pattern analysis (compression-born = most durable), and multi-TF cascade context (D1 push zone + H4 counter + M15 CHoCH).

### 3. Supply/Demand Zones = Our Zone Boxes

**From Videos 2, 3:** Supply/demand zones are areas of price imbalance where institutional buying/selling occurred. Four formation patterns: Drop-Base-Rally, Rally-Base-Drop, Drop-Base-Drop, Rally-Base-Rally.

**Iora equivalent:**
- Drop-Base-Rally = **demand push zone** (price dropped, based/consolidated, then rallied)
- Rally-Base-Drop = **supply push zone** (price rallied, based, then dropped)
- Drop-Base-Drop = **supply continuation zone** (downtrend continues through a base)
- Rally-Base-Rally = **demand continuation zone** (uptrend continues through a base)
- The "base" = the HA run transition period where the zone forms = **compression-born zones** (LH_HL birth pattern, 85-89 retests vs 37-45)

### 4. Liquidity Sweep = Wick Into Zone (The Retest Event)

**From Video 3:** Traders lose because they enter too early — at the exact moment liquidity is being collected. The liquidity sweep pushes price THROUGH a level, grabs stop-losses, then reverses. The smart entry is AFTER the sweep, with a confirmation candle.

**Iora equivalent:**
- Liquidity sweep = **wick_touch event** — price wicks into the zone, grabs the stops sitting behind it, then closes back outside
- "Enter after the sweep" = enter on the M5 CHoCH that confirms the sweep is done and price is reversing
- "Confirmation candle" = the M5/M15 CHoCH with rejection quality score >= 2
- The sweep data validated this: wick_touch entries have positive SQN, and M5 CHoCH inside a zone is the precision entry

**The 4-point checklist from Video 3:**
1. Strong departure from zone = push validation (boundary-break rule)
2. Clear base = compression-born zone (LH_HL birth pattern)
3. No prior retest = test_count <= 1 (unmitigated)
4. Higher TF alignment = D1 bias cascade + H4 CTR/WITH classification

### 5. Internal vs External Structure = M5/M15 vs H1/H4 Swings

**From Videos 4, 5, 6:** Market structure operates on two levels simultaneously:
- **External structure** (major swings) = the higher TF trend (H1/H4 swings making HH/HL or LH/LL)
- **Internal structure** (minor swings) = the lower TF moves WITHIN each external leg (M5/M15 swings)
- Internal CHoCH (iCHoCH) = early warning that the external trend may reverse
- External CHoCH (eCHoCH) = confirmed structural reversal
- Internal BOS builds the external leg — each M15 BOS continuation is one step in the H4 move

**Iora equivalent:**
- External = H1/H4 period tracker (BOS/CHoCH classification, trendlines connecting swing points)
- Internal = M5/M15 period tracker (CHoCH markers, zone flow direction)
- iCHoCH at a zone = M5 CHoCH inside H4 zone = earliest entry signal
- eCHoCH confirmation = H1 CHoCH = the structural reversal is confirmed
- Trendline break between iCHoCH and eCHoCH = the structural shift is real (from `iora_pivot_hl_trendlines.pine`)

**Video 6 (NFX Academy) key point:** Internal structure shows the pullbacks WITHIN the external trend. The internal CHoCH does NOT mean the external trend has changed — it means a pullback is starting. Only when the external structure breaks (eCHoCH) does the trend actually reverse. This maps exactly to: M15 CHoCH = intraday pullback starting (Trade Type 2: counter trade). H1/H4 CHoCH = structural reversal at D1 zone (cascade transition, Trade Type 1 resuming).

### 6. Trend Phases = The Cascade Cycle

**From Videos 4, 5:** Markets move in impulsive moves (strong directional pushes) and retracement moves (pullbacks before the next leg). Uptrends = HH + HL. Downtrends = LH + LL. Sideways = range/compression.

**Iora equivalent:**
- Impulsive move = D1 push (breaking LTF zones, making new HH/LL)
- Retracement move = H4 counter-trend (pulling back against D1 push, toward D1 zone)
- Each retracement creates zones that the next impulsive move will break through
- The cascade cycle: D1 push → H4 counter → intraday ride → D1 zone reversal → D1 push resumes

**Video 5 key insight:** "When you're moving with the trend, it's easy to make money. When you're moving against it, you will be consistently killed." This is exactly what the sweep data shows:
- H1@H4 with_daily SQN = -1.37 (trading WITH daily at H4 = those zones are being broken = you get killed)
- H1@H4 against_daily SQN = +1.12 (trading the pullback to H4 zones = you're WITH the retracement = profitable)
- H1@D1 with_daily SQN = +2.66 (trading WITH daily at D1 zones = you're with the major trend at the structural level = highest conviction)

### 7. Fair Value Gaps (FVG/IMB) — NOT YET IN IORA

**From Video 2:** Fair value gaps are price imbalances between candle wicks during impulsive moves. They act as magnets that pull price back. Smart traders use FVGs for precision entries.

**Current Iora status:** Not implemented. FVGs are the gaps between consecutive candles' wicks during a push. Adding FVG detection could:
- Enhance zone quality scoring (zones with FVGs = stronger institutional imbalance)
- Provide additional entry precision within zones (enter at the FVG inside the zone)
- Add a confluence layer to the scoring system

**Future consideration:** FVG detection is straightforward (compare high[1] vs low of 3 candles back). Could be added to the cascade zones indicator as a Phase 4 enhancement.

---

## What This Means For Our System

**We are NOT missing anything fundamental.** Every concept taught in these 6 videos — engulfing patterns, order blocks, supply/demand zones, liquidity sweeps, internal/external structure, trend phases — maps directly to something Iora already detects mechanically:

| Video Concept | Iora Mechanical Detection | Sweep Validation |
|--------------|--------------------------|------------------|
| Engulfing at zone | M5/M15 CHoCH inside zone | Reversal zones WR 42.2% |
| Order block (unmitigated) | Push zone, test_count <= 1 | Push zones 0% break-through |
| Supply/demand zone | HA-based zone creation | Zones hold 99.97% of the time |
| Liquidity sweep | Wick_touch event at zone | Wick_touch positive SQN across all pairs |
| Drop-Base-Rally | Compression-born push zone | Compression zones 2x more durable |
| Internal CHoCH | M5/M15 CHoCH marker | Body_close M5@M15 SQN 1.52 |
| External CHoCH | H1/H4 CHoCH (BOS/CHoCH classification) | H1@D1 with_daily SQN 2.66 |
| HTF alignment | D1 bias cascade + D-to-W relationship | Against_daily H1@H4 SQN 1.12 |
| Trend phases | Period tracker HH/HL/LH/LL | Retest #4-10 SQN 2.04 |

**What we need is NOT more concepts. We need:**
1. Cleaner visualization (reduce indicator clutter — ongoing)
2. Rejection quality scoring (filter CHoCH events by quality — in progress)
3. The entry connection: zone retest → liquidity sweep (wick into zone) → M5 CHoCH confirmation → enter with SL behind CHoCH zone
4. Trendline breaks as structural confirmation (from `iora_pivot_hl_trendlines.pine`)
5. Then run the sweep with these refined entries to validate with data

**The dots are already connected mechanically. The indicators need to show them clearly.**

---

## Additional Concepts From Videos 7-12

### 8. The 3-Step Execution Framework (Video 7 — Brett Go)

Brett's framework maps 1:1 to the cascade model:

| Brett's Step | What He Does | Iora Equivalent |
|-------------|-------------|----------------|
| Step 1: Direction | HTF bias on H4/D1 using HH/HL or LH/LL structure | D1 push zone bias from Cascade Bias indicator |
| Step 2: Location | Wait for price to reach a specific zone/POI. Set alerts. Don't go to LTF until price is there. | H4/D1 zone retest. Dashboard status "AT ZONE" |
| Step 3: Execution | Go to M5/M15, look for CHoCH/engulfing INSIDE the zone | M5 CHoCH inside H4 zone with rejection quality scoring |

His key principle: "You only go to step three once price has entered into the point of interest." This prevents overtrading — no LTF analysis until the HTF zone is in play.

### 9. Parent-TF Candle Range as Structure (Videos 8, 9, 11)

Three separate videos (different traders) all use the same concept: the first H4 candle's high/low defines the intraday range. Price action relative to these levels (break above = bullish, break below = bearish, touch and reject = retest entry) drives entries.

**This IS the parent-TF boundary finding from the sweep data:** median first H1 zone retest = 3.1 hours = one H4 candle. The H4 candle's range acts as structural support/resistance for intraday entries. Three independent sources (sweep data + two trading educators) confirming the same structural reality.

### 10. Daily Bias Checklist (Video 10 — Brett Go)

His specific pre-market checklist:
1. Mark Previous Day High (PDH) and Previous Day Low (PDL)
2. Mark equal highs/lows (liquidity pools — clustered stops)
3. Determine premium vs discount (above/below 50% of range)
4. Identify where liquidity sits (stops behind equal H/L)
5. Determine most likely target (where price gravitates)

**Iora equivalents already computed:**
- PDH/PDL = D1 period tracker `prev_hi` / `prev_lo` (already in the engine)
- Premium/discount = price position relative to D1 zone midpoints (computable)
- Liquidity targets = nearest zone boundaries where stops cluster
- Most likely target = next opposing zone (structural TP)

**What to add to the sweep as testable dimensions:**
- `near_pdh_pdl` filter: entry zone within 0.5 ATR of PDH or PDL
- `premium_discount` filter: longs in discount (below range 50%), shorts in premium
- Equal highs/lows detection as liquidity targets

### 11. Candle Closure Confirmation (Video 12)

Critical principle: never enter before a candle closes. Until closure, the candle can reverse.

**This explains the wick_touch vs body_close sweep results:**
- Wick_touch = candle CLOSED outside the zone = confirmed rejection (works on H1@H4, H1@D1)
- Body_close = candle CLOSED inside the zone = accumulation, not rejection (works on M5@M15 where accumulation precedes reversal)
- The closure IS the confirmation. On wider TF-gap pairs, the close outside confirms rejection. On adjacent pairs, the close inside confirms accumulation.

**Also explains BOS vs CHoCH detection:** BOS = close BEYOND the swing point (confirmed break). CHoCH = rejection FROM the swing point (wick but no close beyond = structure held). The close is what makes it real.

### 12. Liquidity Sweep Does NOT Always Mean Reversal (Video 10)

Brett's important caveat: sweeping a level doesn't guarantee reversal. Sometimes price sweeps and continues. The sweep just means "liquidity has been collected" — what happens next depends on whether supply or demand is stronger.

**This validates the bias filter finding:** H1@H4 against_daily SQN +1.12 works because the D1 bias (supply/demand imbalance) determines what happens after the sweep. Without bias alignment, the sweep might just be a continuation break.

---

## Consolidated Entry Model (All 12 Videos + Sweep Data)

The complete entry model, synthesized from all sources:

```
1. BIAS (from D1 structure — Videos 5, 7, 10)
   → D1 push zone establishes direction (HH/HL or LH/LL)
   → Mark PDH/PDL for intraday reference
   → Determine premium vs discount pricing

2. LOCATION (zone retest — Videos 1, 2, 3, 7)
   → Wait for price to reach H4/D1 zone (DON'T go to LTF before this)
   → The zone IS the order block (institutional flow origin, 0% break-through)
   → Set alerts — patience is the edge

3. SWEEP (liquidity grab — Videos 3, 10)
   → Price enters the zone and sweeps stops (wick_touch)
   → This is the liquidity collection event
   → Don't enter on the sweep — wait for confirmation

4. CONFIRMATION (CHoCH + closure — Videos 1, 6, 7, 12)
   → M5/M15 CHoCH inside the zone = reversal starting
   → Candle must CLOSE to confirm (no pre-close entries)
   → Rejection quality score >= 2 (wick ratio + body ratio + follow-through)
   → This IS the engulfing/hammer forming on H1

5. ENTRY (precision — Videos 3, 7, 8, 9)
   → Enter on the M5 CHoCH zone (the structural reversal point)
   → Or: buy/sell limit at the zone boundary (for push zones with 0% break-through)
   → SL behind the M5/M15 CHoCH zone (structural SL, 10-30 pips)
   → TP at next opposing zone on context TF (structural TP)

6. RIDE (continuation — Videos 4, 5, 6)
   → After entry, every downstream LTF zone in the reversal direction = valid continuation
   → Internal BOS (M15 BOS) = the push is extending, hold the trade
   → External CHoCH (H1 CHoCH at target zone) = the push is ending, exit
```

This is the same model described in the cascade template, the sweep analysis, and all 12 videos — just connected.
