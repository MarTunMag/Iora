# Prompt: HTF/LTF Layered Structure — Magnets, Push Zones & Entry Areas

---

## Who I Am

Marius, Norwegian solo developer building **Flint** — a Python/Dash trading strategy visualisation and automation system at `C:\Flint`. The active strategy is **Spring Leaf — Wave Navigator**, a multi-timeframe Heikin-Ashi supply/demand exhaustion system for forex (GBPUSD, EURUSD, XAUUSD) on ICMarkets Raw Spread MT5. I also build Pine Script v6 indicators under the name `iora_*.pine` for TradingView visual validation.

**Critical background:** A previous ML-based system collapsed from ~75% backtest to ~33% live due to data leakage and parity bugs. This drives the current approach: visual validation first, mechanical rules proven before any automation.

---

## What We're Building

A layered HTF→LTF structural framework that accurately identifies:

1. **Magnets** — where price is being pulled toward (HTF zones, liquidity pools, breaker targets)
2. **Push zones** — which zones are actively pushing price through timeframes (the supply/demand zones that drive BOS events)
3. **Reversal areas** — where price will reverse (terminal exhaustion, HTF counter-zones, breaker retests)
4. **Entry areas** — where to enter through nested LTF CHoCH confirmation at the right HTF zone
5. **Exit + re-entry areas** — where the current leg ends and the next begins (correction TL breaks, zone count gates)

The goal is to get the TF cascade right — so each timeframe's zones correctly push and pull the ones below it, and LTF events correctly confirm HTF structural shifts.

---

## The System Foundation (3 Indicator Specs)

### Indicator 1: Market Structure — BOS / CHoCH (`iora_structure.pine`)

**What it plots:** Horizontal structure lines classified as BOS (trend continuation, solid green) or CHoCH (reversal signal, dashed red), labeled with TF and internal/external prefix.

**Core concepts:**

Three market states per TF: Uptrend (HH after HH), Downtrend (LL after LL), Reversal/Neutral (CHoCH fired, BOS not yet confirmed).

**Internal vs External — the most important distinction:**
- Internal structure = zone breaks on the current TF (sub-swings within a trend)
- External structure = child TF detects parent TF zone broken (true structural boundary)
- Parent-child chain: M1→M5→M15→H1→H4→D→W→MN
- **Collapsing internal and external into one layer is the #1 cause of false signals**

**Detection rules:**
- Zone break = body close only (wicks = liquidity sweeps, not breaks)
- Supply broken: `close > zone.top` | Demand broken: `close < zone.bottom`
- Each TF maintains directional bias (+1 bullish, -1 bearish, 0 neutral)
- BOS vs CHoCH depends on pre-break bias (captured before the break updates it):
  - Bullish break + bullish/neutral pre-bias = BOS
  - Bullish break + bearish pre-bias = CHoCH
  - Bearish break + bearish/neutral pre-bias = BOS
  - Bearish break + bullish pre-bias = CHoCH

**External break detection:** Child TF body-closes through parent TF zone array. Fires thicker line with `e` prefix. External bias overrides internal. Provides cascade: M15 external break = H1 zone consumed, visible before H1 candle closes.

---

### Indicator 2: Supply & Demand Zones (`iora_zones.pine`)

**Zone creation:** HA color transitions via `request.security()` per TF.
- Red→Blue = Demand (sellers exhausted)
- Blue→Red = Supply (buyers exhausted)

**Zone boundaries (ORIZ spec):**
- Supply: top = OHLC high of blue run (structural extreme), bottom = HA low of transition candle (OB edge)
- Demand: top = HA high of transition candle (OB edge), bottom = OHLC low of red run (structural extreme)
- Run scanned backwards up to 50 bars for extreme

**Zone classification — one rule, every TF, every zone:**
- Supply: new top > prev supply top → HH (structural) | ≤ → LH (corrective)
- Demand: new bot < prev demand bot → LL (structural) | ≥ → HL (corrective)

**This classification feeds BOS/CHoCH:** HH or LL zone broken → BOS | LH or HL zone broken → CHoCH

**Zone lifecycle:** Created → Active (extends right) → Broken (body close through) → Deleted immediately. Also removed by expiry (50 bars M1-H4, 30 W, 20 MN) or count overflow (20 per type per TF).

**Cross-TF propagation:** H1 HH → H4 HH if top also > prev H4 supply top. Same logic H4→D, D→W, W→MN.

---

### Indicator 3: Breaker & Mitigation Blocks (merged into `iora_structure.pine`)

**Zone polarity flip:** When a zone is broken by external BOS, it flips polarity:
- Supply broken by bullish eBOS → Bullish breaker (support on retest from above)
- Demand broken by bearish eBOS → Bearish breaker (resistance on retest from below)

**Breaker block:** Forms on external HH/LL breaks only (structural, not corrective). Persists until retested (body close inside zone) or count overflow. Never removed by time decay.

**Breaker vs Mitigation distinction:**
- Breaker = full structural reversal (CHoCH + BOS) with liquidity sweep → strong, high conviction
- Mitigation = failure swing, no full structural break, no liquidity grab → moderate, one retest

**Persisted H4 zones:** On H4 eBOS, captures last unbroken H4 zone of opposite type. Provides reversal context/target.

**Complete lifecycle:** Created → Active → Broken → [If external HH/LL: Breaker created + persisted zone captured] or [If internal/non-HH/LL: deleted] → Breaker persists → Retested → Deleted.

---

## Zone Classification Rules (Standalone Reference)

When a new zone fires (HA color flip), compare to previous zone of same type on same TF:

**Supply (blue→red):** new top > prev top → HH | ≤ → LH
**Demand (red→blue):** new bot < prev bot → LL | ≥ → HL

**What it creates one level up:**
- H1 HH → H4 HH (if top > prev H4 supply top)
- H1 LL → H4 LL (if bot < prev H4 demand bot)
- H1 LH → H4 LH (if top < prev H4 supply top)
- H1 HL → H4 HL (if bot > prev H4 demand bot)
- Same logic H4→D, D→W, W→MN

**BOS vs CHoCH on break:** HH/LL zone breaks → BOS (confirmation) | LH/HL zone breaks → CHoCH (early warning)

---

## Early Confirmation Cascade — CHoCH-to-Structure Propagation

**Core insight:** An H1 CHoCH doesn't just confirm an H1 event — it IS the mechanism that creates H4 structure. Every HTF structural shift is built from LTF CHoCH events cascading upward.

### The Propagation Chain (Bottom-Up)

```
M1 CHoCH → confirms M5 sub-wave direction
  → M5 CHoCH → confirms M15 zone leg complete
    → M15 CHoCH → confirms H1 sub-wave complete (H1 push TL break)
      → H1 CHoCH → creates H4 structure (H4 HH/HL/LH/LL)
        → H4 structural event → creates D structure
```

**Key rule:** Don't wait for H4 HH to appear on chart. Detect it earlier through the H1 CHoCH that builds that H4 HH.

### H1 CHoCH → H4 HH (Bullish Structural Shift)

Bearish trend, H4 making LLs, price at terminal H4 demand:
1. H1 impulse down completes (5+ H1 supply zones, LH tops descending)
2. H1 first HL fires (CHoCH — correction starting)
3. H1 second HL fires (correction Wave B)
4. H1 HH fires (BOS — reversal confirmed). This H1 HH = H4 HH because H1 supply top > prev H4 supply top

**The early signal:** `H1 LH → H1 LH → H1 HL (CHoCH!) → H1 HH (BOS confirming reversal)`

### H4 Structure → D Structure

- H4 HH but supply top below prev D supply top → D LH confirmed (bearish impulse intact, rally was correction)
- H4 HL at D demand → D HL = potential W reversal signal

### M15 CHoCH → H1 Sub-Wave Completion

Each H1 zone is built from M15 sub-waves:
- M15 supply zones descend (LH→LH→LH = bearish push)
- M15 HL fires (CHoCH) → H1 demand about to form
- M15 CHoCH inside H1 zone = completion/retest signal

### M1 CHoCH → Earliest Entry Trigger

**Short entry after D LH confirmation:**
1. D LH confirmed → H1 makes new LH → M15 LH inside H1 supply → M5 LH → M1 LH (CHoCH) inside last M5 demand = ENTRY

**Long entry at terminal bottom:**
1. Terminal exhaustion confirmed → H1 HL (CHoCH) → H1 HH (BOS) → M15 HL inside H1 demand → M5 HL → M1 HL inside last M5 supply = ENTRY

### Complete Early Confirmation Table

| HTF Event | Confirmed Early By | Earliest Tradeable Signal |
|-----------|-------------------|--------------------------|
| H4 HH | H1 HH (supply top > prev H4 supply top) | M1 HL after H1 first HL |
| H4 LL | H1 LL (demand bot < prev H4 demand bot) | M1 LH after H1 first LH |
| H4 HL | H1 HL sequence inside H4 demand | M15 HL inside H1 demand @ H4 demand |
| H4 LH | H1 LH sequence inside H4 supply | M15 LH inside H1 supply @ H4 supply |
| D LH | H4 HH capped below D supply top | H1 CHoCH (first LH after H4 HH) |
| D HL | H4 LL floored above D demand bot | H1 CHoCH (first HL after H4 LL) |
| H1 leg complete | M15 CHoCH (opposing direction inside H1 zone) | M1 CHoCH after M5 CHoCH inside M15 |

### Trendline Cascade Confirmation

**Impulse TL** (trend continuation): connects LH supply tops (descending) or HL demand bots (ascending). Built from CHoCH events at one level below. Break = correction strong enough to threaten structure.

**Correction TL** (pullback within trend): connects HL demand bots (ascending correction) or LH supply tops (descending correction). Break = correction failed, trend impulse resumes.

### Universal Pattern

```
HTF structure shifts (detected via zone comparison)
  → LTF CHoCH confirms it early (nested inside relevant HTF zone)
    → One-level-lower CHoCH provides precision entry
      → M1 CHoCH is always the final execution trigger
```

---

## New Indicator: Structure Trendlines (`iora_structure_trendlines.pine`)

Just built — trendlines anchored to zone-confirmed swing points (HA color transitions) instead of every candle's high/low. Two layers per TF:
- **Internal trendlines** (dashed, thin) — sub-swing structure
- **External trendlines** (solid, thick) — structural boundaries

Pivots only fire on HA color transitions. OHLC prices for actual levels. HH/LH/HL/LL classification per swing. LH draws descending TL, HH breaks it. HL draws ascending TL, LL breaks it. Auto internal/external pairing via TF cascade.

Full spec at: `C:\Flint\docs\IORA_STRUCTURE_TRENDLINES_SPEC.md`

---

## Internal/External Structure Spec (Flint Implementation)

Full TF cascade spec saved at: `C:\Flint\docs\INTERNAL_EXTERNAL_STRUCTURE_SPEC.md`

**Architectural insight locked in:** External structure is confirmed at the moment of a zone-based CHoCH/BOS event (zero lag). Internal/external classification is a structural fact derived from the TF cascade (M1ext=M5int, M5ext=M15int, etc.) — not a tunable parameter.

**Implementation approach:** Zone-chain-based (no Pine Script lookback windows). Phase 1 pending: structure state, zone-based swing detection, BOS/CHoCH classification, chart overlay with bar-replay validation.

---

## Strategy Context: Spring Leaf — Wave Navigator

**Core thesis:** 5 impulse + 3 correction H1 unbroken zones = terminal exhaustion. H4 counter-zone (H4 demand below broken D LL) = terminal signal.

**Unified Sweep-Scalp-Growth Chain:** H1 BOS (sweep) → scalp hedge retracement to H1 zone → M1 CHoCH at H1 zone = one mechanical cycle.

**Zone count gates:** Zones 1-5 allow Growth entries, zone 6 is last entry, zones 7-8 hold-only, zone 8 inside H4 counter-zone = terminal (FLIP preparation).

**The core diagnosis for too many signals:** System skips the meso layer (H1 push/pullback cycle awareness) and jumps from macro context directly to M1 triggers.

**Fix sequence:** Validate macro (D+H4 direction) → add meso (H1 zone chain, BOS/CHoCH, zone count) → micro (M1 triggers only when both confirm).

**Context modes:** RIDE (with trend), FLIP (terminal reversal), SCALP (hedge), SKIP (no trade).

---

## Reference Images (Described for Context)

The following images were used in building the system. Describe what you understand if I reference them:

1. **BOS vs CHoCH orderflow shift diagram** — Shows bearish orderflow (LL→LH→LL→LH) shifting to bullish via CHoCH (HL breaks the LH pattern), then BOS confirms with HH
2. **CHoCH reversal vs BOS continuation (live chart)** — Split panel: left shows CHoCH reversal (bearish→bullish with supply/demand zones), right shows BOS continuation (bullish trend with ascending demand zones)
3. **BOS vs CHoCH with HTF supply/demand full cycle** — Shows complete cycle: bearish BOS continuation (LL→BOS→LL→BOS) → terminal LL → CHoCH (first HH) → bullish BOS continuation (HH→BOS→HH→BOS) with supply/demand zones at reversal points
4. **Valid vs invalid BOS/CHoCH on Gold H1** — TradingView Gold H1 chart with green checks (valid BOS) and red X marks (invalid/premature BOS calls), showing POI H1 zones and $$$ liquidity areas
5. **Breaker vs mitigation — break determines type** — Shows that a breaker block requires breaks on BOTH sides (above and below), while a mitigation block only has a break on one side (failure swing)
6. **Order block vs breaker block (bearish)** — Side by side: bearish OB (supply zone with liquidity sweep above) vs bearish breaker block (same zone after polarity flip, acting as resistance on retest)
7. **Mitigation block LH retest definition** — Shows H→LH pattern where the LH zone becomes a mitigation block when price returns to it, acting as support
8. **Mitigation block failure swing and FVG entry** — Detailed: failure swing creates mitigation block, FVG overlapping the mitigation block = strong entry confirmation
9. **Internal vs External BOS diagram** — Two-line chart: black line (external/parent swings) and cyan line (internal/child swings). Shows iBOS (internal, small green lines), eBOS (external, large green lines), iCHoCH (internal red), eCHoCH (external red). Key: internal structure moves within external structure
10. **Internal vs External BOS with trendlines** — Same diagram as #9 but with trendlines overlaid: ascending TL through external swing lows (thick), descending TLs through internal swing highs (thin). Shows how internal TL break = minor signal, external TL break = structural shift
11. **SMC mechanical entry models panorama** — Wide TradingView chart showing the complete SMC entry model sequence with annotated zones, BOS/CHoCH labels, and entry/exit points across a full market cycle

---

## What I Want to Work On in This Chat

I want to go through the HTF→LTF layered understanding in detail, so we can correctly identify:

1. **Which zones act as magnets** (pull price toward them) vs **which zones act as push zones** (drive price away from them) — and how this changes as the TF cascade updates
2. **How to read the current structural state across all TFs simultaneously** — D bias + H4 zone count + H1 push/correction phase + M15/M5 sub-wave position
3. **Where exactly the reversal areas are** — terminal exhaustion + H4 counter-zone + breaker retest targets
4. **The precise entry mechanics** — which LTF CHoCH at which HTF zone, with the full cascade confirmation
5. **Exit + re-entry logic** — when a leg ends (correction TL break), where the next entry forms (at the breaker/zone from the completed leg)

The end goal is a complete mechanical framework where every entry, exit, and reversal point is defined by the zone cascade — no discretion, no "it looks like it might reverse here." Every decision maps to a specific zone event at a specific TF level.

Let's start by walking through the HTF→LTF magnet and push zone logic — how D zones pull H4 price, how H4 zones push H1 legs, and how that creates the entry areas at M15/M5/M1.
