# Deep System Audit — 2026-04-07

> **Scope:** All validated findings, 37 YouTube transcripts, spread model audit, gap analysis.
> **Principle:** Data speaks, not assumptions. Nothing labeled "dead" unless fully tested.
> **Updated:** Added 6 trendline/pivot videos (V19-V24), symbol-specific min_sl finding.

---

## Phase 1: Transcript Deep Review — 37 Videos (31 original + 6 trendline)

### Master Concept Table

| Concept | Sources (Videos) | Iora Status |
|---------|-----------------|-------------|
| **HTF bias → LTF entry (top-down)** | 5, 6, 7, 10, 13, 14, 15, 16, 18, PTS-7, PTS-10 | Implemented (D1 bias cascade) — tested in sweep |
| **Zone retest entry (S/D zones)** | 1, 2, 3, 5, 6, 11, 17, PTS-1, PTS-5, PTS-6, PTS-11 | Implemented (limit at zone edge) — validated SQN 21-44 |
| **Order blocks = Push zones** | 2, 15, PTS-2 | Implemented — 0% break-through validated |
| **Liquidity sweep → confirmation** | 3, 10, 13, 14, PTS-1, PTS-2, PTS-9, PTS-11 | Partially implemented (wick_touch detection). CHoCH confirmation = untested in sweep |
| **Internal vs external structure** | 4, 5, 6, internal_external_structure | Implemented (M5/M15 vs H1/H4 period trackers). Cascade trigger being built (Tasks 7-13) |
| **Candle close confirmation** | 1, 12, 15 | Implemented (body_close vs wick_touch touch types). Validated in sweep |
| **Engulfing/hammer = CHoCH on LTF** | 1, 3, PTS-3, PTS-8b | Implemented (M5 CHoCH inside zone). Rejection quality scoring built |
| **Opening range / H4 candle as structure** | 8, 9, 11 | NOT implemented. Untested. Matches H4 boundary finding in sweep data |
| **Session timing (London/NY)** | 8, 13, PTS-9 | Tested — marginal/neutral. Default session=any |
| **Premium/discount filter** | 6, 10, 16 | Tested — SQN 1.88, marginal. Not in core strategy |
| **PDH/PDL as liquidity targets** | 10, 16, 18 | Tested — SQN 1.75, marginal. Not in core strategy |
| **FVG / Fair Value Gap** | 2, PTS-2 | NOT implemented. Future consideration |
| **Trendline bounce + break** | PTS-4, PTS-5, 16 | Pine indicator built (`iora_pivot_hl_trendlines.pine`). NOT in Python engine or sweep |
| **DRD / Optimal Trade Entry (Fib)** | PTS-1, PTS-6 | NOT implemented. Fibonacci 50-61.8% confluence with zones |
| **AME (Accumulation/Manipulation/Expansion)** | PTS-1, PTS-2, PTS-9 | Partially mapped to compression-born zones. Not explicitly tested |
| **Partial TP / trail** | 5, 6, 17 | Implemented — H1@H4 partial SQN 24.14 validated |
| **Set and forget** | 3, 6 | Implemented (limit → SL/TP, no intervention) |
| **Minimum R:R threshold (2:1-3:1)** | 3, 6, 16, 17, PTS-5, PTS-6, PTS-11 | Implemented (fixed_rr config parameter) |
| **Zone freshness / unmitigated** | 2, 3, 15, 17, PTS-2, PTS-11 | Implemented (test_count filter). test_count 4-10 SQN 2.04 |
| **Wyckoff accumulation/distribution** | 4 | Partially mapped (compression-born zones). Not explicitly tested |
| **Failed breakout / stop hunt reversal** | PTS-9 | NOT implemented. Maps to wick_touch at zone + reversal |

| **Trendline as context/inducement** | V19, V20, V21, V22, V24 | Pine built (`iora_pivot_hl_trendlines.pine`). NOT in Python engine |
| **TL break → retest at S/D zone = entry** | V19, V20, V21, V22, V24 | NOT implemented. Key gap for Level 4+ |
| **Short-term TL on pullback within zone** | V22, V24 | NOT implemented. Maps to local CHoCH within zone retest |
| **Zone refinement (HTF→LTF 2 steps down)** | V23 | Being built (Tasks 7-13). "Two steps down" rule matches our TF pairs |
| **TL touch points as TP targets (A/B/C)** | V19 | NOT implemented. Novel structural TP concept |
| **Breaker block at TL breakout** | V22 | Designed (cascade layered). Not built |
| **4 entry methods (anticipate→swing break)** | V24 | Partially (limit=aggressive, market=conservative). Not configurable |
| **Real structure overrides trendlines** | V20, V22 | Implemented (BOS/CHoCH). Trendlines are supplementary |

### Cross-Cutting Consensus (20+ sources agree)

1. **HTF first, always** — Never look at LTF until HTF picture is clear
2. **Wait for price at the zone** — No entries in "the middle of nowhere"
3. **Candle must CLOSE** — No pre-close entries
4. **Minimum 2:1 R:R** — 3:1 preferred
5. **Fresh/unmitigated zones** — First retest highest conviction
6. **Liquidity sweep precedes reversal** — Enter AFTER the sweep, not during
7. **Break of structure required** — Zone alone not enough, needs BOS/CHoCH context

---

## Phase 2: Data Insight Audit

### A. TESTED AND PROVEN (data confirms)

| Config | Spread | SQN | PF | WR | Trades | Evidence |
|--------|:------:|:---:|:--:|:--:|:------:|----------|
| **H1@H4 limit top+partial** | 1.5p | **24.14** | **2.54** | 54.6% | 3,747 | Best overall. Spread-immune (SQN 23.70 at 2p) |
| **H1@H4 limit bottom** | 1.5p | **21.95** | **2.25** | ~55% | 3,614 | Production-grade |
| **M15@H1 limit bottom+min_sl=5p** | 1.5p | **14.46** | **1.67** | ~60% | 3,606 | Secondary config |
| **M5@M15 limit rr=3.0 TTL=0** | 0p | **44.61** | **3.28** | 52.6% | 6,493 | Fantasy (no spread) |
| **H1@D1 with_daily** | market | **2.66** | — | — | — | Best bias alignment for D1 zones |
| **H1@H4 against_daily** | market | **1.12** | — | — | — | Counter-trend pullbacks work |
| M5@M15→H1 TP (cross-TF) | 0p | **8.9 avg** | **3.2-4.0** | 12% | 1,600/sym | Consistent across 5 symbols |
| Retest 4-10 filter | — | **+30-70%** AvgR | — | — | — | Proven quality multiplier |
| TTL=0 vs TTL=1 | — | **44.6 vs 39.4** | — | — | +4,091 trades | Doubles trade count, higher SQN |
| Push zones | — | **0% break-through** | — | — | 13,870 events | Highest structural conviction |
| Compression-born zones | — | **2x durability** | — | — | — | 85-89 retests vs 37-45 |

### B. TESTED AND FAILED — But Fully Tested?

| Config | Result | Partial TP? | min_sl? | Top edge? | TTL=0? | Verdict |
|--------|--------|:-----------:|:-------:|:---------:|:------:|---------|
| **M5@M15 bottom, spread=1.5p** | SQN -11.72 | NO | NO | NO | YES | **INCOMPLETE — needs retest** |
| **M5@M15 bottom+min_sl=5p, spread=1.5p** | SQN 6.30 | NO | YES | NO | YES | **INCOMPLETE — partial TP untested** |
| **M5@M15 top edge** | SQN -2.88 | NO | NO | YES | — | **INCOMPLETE — partial+min_sl untested** |
| **PDH/PDL proximity** | SQN 1.75 | — | — | — | — | Marginal, probably dead |
| **Premium/discount** | SQN 1.88 | — | — | — | — | Marginal, probably dead |
| **Session filters (FX)** | Neutral | — | — | — | — | Not useful as standalone |
| **HA trailing** | Reduced AvgR | — | — | — | — | Confirmed dead — hurts performance |
| **BE buffer** | Marginal | — | — | — | — | Confirmed dead — not worth complexity |
| **sl=atr** | Never best | — | — | — | — | Keep as fallback only |
| **H1@H4 with_daily** | SQN -1.37 | — | — | — | — | Confirmed dead for H4 zones |

**Critical: M5@M15 is NOT fully tested.** The "dead" verdict was based on bottom-edge entry without partial TP and without the spread model being verified. See spread audit below — the backtest may be overstating spread cost. M5@M15 with partial TP + min_sl=5p + corrected spread has never been run.

### C. NEVER TESTED (gaps)

| Gap | TF Pair | Details | Priority |
|-----|---------|---------|:--------:|
| **M5@M15 top+partial+min_sl=5p** | M5@M15 | The full-feature config. Never run. | HIGH |
| **M1@M5 anything** | M1@M5 | Zero sweep results | MEDIUM |
| **M1@M15 anything** | M1@M15 | Zero sweep results | LOW |
| **HTF-triggered LTF nesting** | Multiple | Being built (Tasks 7-13) | HIGH |
| **Limit + against_daily (H1@H4)** | H1@H4 | Best market filter + best entry mode | HIGH |
| **Limit + reversal zones** | Multiple | Reversal 42.2% WR → potential 80%+ with limit | MEDIUM |
| **Limit + compression-born** | Multiple | 2x durability + precision entry | MEDIUM |
| **Cascade layered (breaker zones)** | Multiple | Multi-layer limits inside HTF zone | HIGH |
| **HMA direction filter** | Multiple | Designed but not built or tested | MEDIUM |
| **Trendline break as entry trigger** | Multiple | Pine built, not in Python engine | MEDIUM |
| **FVG detection** | Multiple | Not implemented at all | LOW |
| **Walk-forward validation** | All | In-sample vs out-of-sample not done | HIGH |
| **Fibonacci golden zone confluence** | Multiple | 50-61.8% alignment with zones | LOW |
| **Opening range strategy** | Intraday | H4 candle high/low as structure | MEDIUM |

### D. Spread Model Audit — CRITICAL FINDING

#### The Code

```python
# retest_engine.py line 819
def _compute_effective_entry(entry_price, direction, spread_pips, pip_size):
    spread_cost = spread_pips * pip_size
    if direction == "long":
        return entry_price + spread_cost  # Buy at ask
    return entry_price - spread_cost      # Sell at bid
```

**How it's used:** `eff_entry` replaces `entry_price` in all P&L calculations (via `_entry_for_pnl` property). SL and TP remain at their original prices.

#### Traced Example: GBPUSD Demand Zone

```
Zone: top=1.3010, bottom=1.3000
Limit entry at top: entry_price = 1.3010
SL (zone mode): 1.3000 - 0.15*ATR = 1.29985
Spread: 1.5 pips = 0.00015

BACKTEST:
  Fill condition: bar_low (BID) ≤ 1.3010
  eff_entry = 1.3010 + 0.00015 = 1.30115
  Risk = 1.30115 - 1.29985 = 13.0 pips
  If SL hit: loss = -13.0 pips

LIVE MT5 (buy limit at 1.3010):
  Fill condition: ASK ≤ 1.3010 → BID = 1.30085
  Entry = 1.3010 (ASK = limit price)
  Risk = 1.3010 - 1.29985 = 11.5 pips
  If SL hit: loss = -11.5 pips
```

#### Finding: Backtest is Systematically Pessimistic

**For limit orders, the spread is applied twice:**

1. The backtest fills the limit when BID reaches the zone edge (bar_low ≤ entry_price)
2. Then adds spread on top of that BID-based entry price
3. But in live MT5, a buy limit at that price fills at ASK = limit_price, with no additional spread cost — the spread is inherent in the BID/ASK gap at exit

**Impact by TF pair:**

| TF Pair | Typical SL | Spread (1.5p) | Overstatement | Impact |
|---------|:----------:|:-------------:|:-------------:|--------|
| M5@M15 | 1.2 pips | 1.5 pips | **125%** overstated risk | MASSIVE — may flip verdict |
| M15@H1 | 3-5 pips | 1.5 pips | **30-50%** overstated | Significant |
| H1@H4 | 5-10 pips | 1.5 pips | **15-30%** overstated | Moderate but configs still pass |
| H1@D1 | 10-20 pips | 1.5 pips | **7-15%** overstated | Minimal |

**However — compensating factors in live:**
- Slippage: limit orders during fast moves may not fill at exact price
- Variable spreads: spread widens during news/volatility (can reach 5-10 pips)
- Requotes and partial fills
- The pessimism acts as a safety margin

#### Verdict

**The model is a reasonable conservative approximation.** It overstates cost by ~1 spread per trade, but this provides a safety margin for real-world execution. The key implication is:

1. **Configs that pass the spread test are CONSERVATIVELY profitable** — they'll likely perform better in live
2. **M5@M15 with min_sl=5p (SQN 6.30 in backtest)** may actually be viable in live (real risk is lower)
3. **Do NOT "fix" the model** — instead, use JoMa's `spread_at_fill` data to calibrate
4. **Once JoMa has 100+ trades logged:** Compare backtest predicted P&L vs live actual P&L to measure the exact pessimism

#### Alternative: More Accurate Model

If we wanted exact spread modeling for limit orders:
```python
# Instead of shifting entry, shift exit triggers
# For longs: SL triggers when BID hits SL (same as now)
#            TP triggers when BID hits TP (same as now)
#            But entry IS the limit price (no spread added)
# The spread cost is inherent in: you bought at ASK, but SL/TP
# trigger on BID which is spread-below ASK
```

This would require restructuring the P&L calculation. Not worth it until we have live calibration data.

---

## Phase 3: Summary Statistics

### What We've Swept (Total Coverage)

| Sweep Version | Configs | Symbols | Trades | Key Addition |
|:---:|:---:|:---:|:---:|---|
| V1 (56 configs) | 56 | GBPUSD | ~100K | Baseline market entry |
| V2 (410→498) | 498 | GBPUSD | ~600K | Limit orders, structural SL/TP |
| V3 (108) | 108 | GBPUSD | ~700K | TTL=0, BE buffer, HA trail |
| Cross-TF TP (54) | 54 | 5 symbols | ~40K | Dual-profile (scalp + swing) |
| Spread sweep (125) | 125 | GBPUSD | ~800K | Spread 0-3p, min_sl, sl_buffer |

**Total: ~2.2M simulated trades across ~785 unique configs.**

### What's Proven vs What's Assumed

| Statement | Status | Evidence |
|-----------|:------:|----------|
| Limit orders transform performance | PROVEN | SQN 23+ vs SQN 1 (market entry) |
| H1@H4 is spread-immune | PROVEN | SQN 24.14 at 1.5p, 23.70 at 2.0p |
| Push zones never break | PROVEN | 0% break-through, 13,870 interactions |
| TTL=0 doubles trade count | PROVEN | 2,402 → 6,493 trades, higher SQN |
| Partial TP is transformative | PROVEN | SQN 1.61 → 24.14 on H1@H4 |
| Against_daily best for H4 | PROVEN | SQN 1.12 vs -1.37 |
| With_daily best for D1 | PROVEN | SQN 2.66 |
| Retest 4-10 improves quality | PROVEN | +30-70% AvgR consistently |
| M5@M15 is dead at real spread | **ASSUMED** | Tested incomplete — see Phase 2B |
| Spread model is correct | **NUANCED** | Pessimistic by ~1 spread — see Phase 2D |
| Cross-TF TP is universal | PROVEN | SQN 8.5-9.6 across 5 symbols |
| HA trail helps | DISPROVEN | Reduces AvgR across all configs |
| BE buffer helps | DISPROVEN | Marginal improvement, not worth complexity |

---

## Phase 4: Recommendations — What to Test Next

### Priority 1: Highest Impact, Existing Engine

| # | Test | Why | Effort |
|---|------|-----|:------:|
| 1 | **M5@M15 top+partial+min_sl=5p** at spread=1.0p and 1.5p | Never run. The full-feature M5@M15 config. May revive M5@M15. | Low — existing engine, new config |
| 2 | **Limit + against_daily on H1@H4** | Best market filter (SQN 1.12) + best entry mode (SQN 24.14). Never combined. | Low |
| 3 | **Walk-forward validation** | No out-of-sample testing done. Split 2009-2019 train / 2020-2023 test / 2024-2026 validate. | Medium |
| 4 | **Spread model calibration from JoMa** | Once JoMa logs 100+ trades with `spread_at_fill`, compare predicted vs actual P&L. | Medium (needs JoMa data) |

### Priority 2: High Impact, Needs New Code (Tasks 7-13)

| # | Test | Why | Effort |
|---|------|-----|:------:|
| 5 | **HTF-triggered LTF nesting** | The cascade model from all videos. Tasks 7-13 in progress. | In progress |
| 6 | **Cascade layered (breaker zones)** | Multi-layer limits inside HTF zones. Designed, not built. | High |
| 7 | **Trendline break in Python engine** | Pine reference built. **11 videos validate** (5 original + 6 trendline). TL break at S/D zone = highest-consensus untested concept. | Medium |

### Priority 3: Medium Impact, New Features

| # | Test | Why | Effort |
|---|------|-----|:------:|
| 8 | **HMA direction filter** | HA-cross-HMA as trigger event. Designed, not built. | Medium |
| 9 | **Opening range (H4 candle structure)** | 3 independent videos + sweep data confirm H4 boundary alignment. | Medium |
| 10 | **FVG detection** | 2 videos mention as quality enhancer. Easy to compute. | Low |

### Priority 4: Low Impact / Speculative

| # | Test | Why | Effort |
|---|------|-----|:------:|
| 11 | M1@M5 / M1@M15 TF pairs | Zero data. Spread will likely kill M1. | Low effort, low expectation |
| 12 | Fibonacci golden zone confluence | Nice to have, low video consensus on exact rules | Medium |
| 13 | Session-aware entry timing (London CHoCH at zone) | Session alone is neutral, but combined with zone contact may help | Medium |

### What NOT to Test (Proven Dead)

- HA trailing — confirmed to hurt all configs
- BE buffer — marginal, adds complexity
- sl=atr — never outperforms zone SL with limit
- H1@H4 with_daily — SQN -1.37, structurally wrong
- Session filters as standalone — neutral/negative

---

## Phase 5: Trendline & Pivot Rules (Videos 19-24)

### What 6 Trendline Videos Agree On

1. **Trendlines are context, NOT entry signals** — Draw them to identify where liquidity/orders accumulate (retail stops + breakout entries), but don't trade from them directly. (V20 JeaFx: "Trend lines are best used to identify inducements where traders are going to be drawn into positions")

2. **Never enter on break alone** — All 6 videos emphasize: wait for retest + confirmation. False breakouts are the #1 trap. (V22: "A break alone is NOT enough — need extra confirmation")

3. **S/D zone at trendline intersection = highest probability** — 5/6 videos use zones as the actual entry mechanism with trendlines providing timing. Broken trendline acts as resistance; zone reinforces selling/buying pressure. (V21 LutaMarkets: "The intersection of broken trendline + supply zone = high probability entry")

4. **Real structure (HH/HL, LH/LL) overrides trendlines** — A trendline can break while the trend remains intact. Always check the structural high/low. (V20: "A trend line does not actually determine the trend direction of the market")

5. **Zone refinement 1-2 TFs down** — V23 (JeaFx) specific rule: "Two steps down" max (4H→1H→30m, D→4H→1H). One step usually enough. Over-refinement leads to missed trades.

6. **4 entry methods from aggressive to conservative** — V24 (Day Trading Addict): (1) Anticipate breakout at double bottom, (2) Enter on break, (3) Wait for candle close, (4) Wait for swing break. Beginners use #3-4.

### What This Means For Iora

**Already have:**
- Push zones = S/D zones = order blocks (0% break-through validated)
- BOS/CHoCH = structural break confirmation
- Multi-TF alignment (cascade model)
- Zone retest detection
- Trendlines in Pine (`iora_pivot_hl_trendlines.pine`)

**Key gaps to fill:**

| Gap | What | Implementation | Priority |
|-----|------|---------------|:--------:|
| **TL break → zone entry trigger** | When a trendline breaks AND price retests a zone at that broken TL level, this is the highest-conviction entry | Add trendline break events to Python engine. Use as filter dimension in sweep. | HIGH |
| **Short-term TL on pullback in zone** | Draw mini trendline on the pullback WITHIN a zone retest. Break of that mini TL = entry trigger. | This IS a local CHoCH/BOS within the zone. May already be captured by M5 CHoCH detection. Verify. | MEDIUM |
| **TL touch points as TP (A/B/C)** | V19: Label trendline touch points oldest→newest. After break, they become staged TP targets. | New concept: structural TP from pivot history, not just opposing zones. | MEDIUM |
| **Breaker at TL breakout** | V22: Zone that caused the TL break becomes a breaker block. Retest of this breaker = entry. | Maps to cascade layered model. Already designed. | HIGH (in Tasks 7-13) |
| **Inducement detection** | V20: Trendlines identify WHERE retail orders accumulate (stops + breakouts). Smart money targets these. | Conceptual — would need order flow proxy. Low priority for mechanical system. | LOW |

### Symbol-Specific min_sl Finding (Added from Code Audit)

**`min_sl_pips=5` is wrong as a universal setting.** "5 pips" means:
- GBPUSD: 0.00050 price move (reasonable)
- XAUUSD: $0.50 on $3,000 gold = 0.017% (absurdly tight)
- BTCUSD: $0.50 on $84,000 BTC = 0.0006% (meaningless — spread alone is $12)

**Fix:** Replace with `min_sl_spread_mult` — SL must be at least Nx the symbol's typical spread. Sweep at [2x, 3x, 5x]. This auto-scales across all 38 symbols.

Also: `_get_pip_size()` in `trade_converter.py` is hardcoded and gets XBRUSD, XTIUSD wrong. Must load from `config/symbol_specifications.json`.

---

## Appendix: Video Source Cross-Reference

| Video | Key Concept for Iora | Validation Status |
|-------|---------------------|:--:|
| 1 (Tsutsumi/Engulfing) | Engulfing = M5 CHoCH inside zone | Implemented |
| 2 (OB vs S/D) | OB = push zone + FVG | Push zones implemented, FVG missing |
| 3 (S/D + Liquidity) | 4-point zone qualification + sweep confirmation | Implemented except sweep→CHoCH chain |
| 4 (Complex Structure) | Wyckoff + impulsive/retracement phases | Partially (period tracker) |
| 5 (Market Structure) | Internal vs external + correction phases | Implemented |
| 6 (Internal/External) | LTF CHoCH ≠ trend change, only pullback | Key cascade insight — in Tasks 7-13 |
| 7 (3-Step Framework) | Direction→Location→Execution = cascade model | Validated by sweep data |
| 8 (Opening Range) | First H4 candle = intraday structure | NOT implemented |
| 9 (Touch and Turn) | Range edge limit entry | Conceptually matches limit orders |
| 10 (Daily Bias) | PDH/PDL + premium/discount + liquidity targets | Tested — marginal as standalone |
| 11 (4H Range) | H4 candle breakout + pullback | NOT implemented |
| 12 (Candle Closures) | Close = confirmation, wick = rejection | Implemented (touch_type) |
| 13 (Liquidity + Timing) | Session + sweep = expansion | Session neutral, sweep works |
| 14 (Spotting Liquidity) | Liquidity as additional confluence | Partially implemented |
| 15 (Smart Money Traps) | OB after CHoCH + LTF refined entry | Core cascade model |
| 16 (Sniper Entries) | Full top-down + confluence stacking | Validates cascade |
| 17 (S/D Masterclass) | Zone quality scoring + depth/time filters | Quality scoring built |
| 18 (Chart Markup) | Clean charts + 4H→15m→5m execution | Validates cascade flow |
| PTS 1-11 | Reinforce all above concepts | Consistent with main series |
| 19 (TL Break Strategy) | TL break→retest, touch points as TP (A/B/C) | Novel TP concept. NOT implemented |
| 20 (TL as Inducement) | TL = liquidity trap, S/D zones = real entries | Validates zones > trendlines |
| 21 (TL+S/D Combo) | TL break + S/D intersection = sniper entry | Key gap for Python engine |
| 22 (TL Master Strategy) | Bounce + breakout, breaker blocks at TL, multi-TF | Validates cascade + breaker concept |
| 23 (Zone Refinement) | HTF→LTF "two steps down" for sniper R:R | EXACTLY Tasks 7-13 |
| 24 (4 Entry Methods) | Anticipate→immediate→candle close→swing break | Configurable aggressiveness concept |

**37 transcripts from 8+ independent traders all converge on the same principles.** Every core concept maps to something Iora already detects mechanically. The remaining gaps are: FVG, trendline breaks in Python, opening range, and the cascade trigger chain (being built).
