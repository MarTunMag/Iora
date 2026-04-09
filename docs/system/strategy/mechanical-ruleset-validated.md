# Mechanical Ruleset — Validated

> **Date:** 2026-04-07
> **Source:** Deep system audit of 2.2M simulated trades, 785 configs, 31 YouTube transcripts, spread model audit.
> **Principle:** Every rule here has data behind it. No assumptions, no "should work."

---

## Proven Rules (data confirms)

### Rule 1: Limit orders at zone edges are the primary edge
- **Description:** Place pending limit orders at zone boundaries instead of market entries at bar close. Zone-bottom + 0.1*ATR for demand (longs), zone-top - 0.1*ATR for supply (shorts).
- **Evidence:** SQN 23.64 (limit) vs 1.01 (market). Every metric transforms: WR 64-70%, PF 3-5, MaxDD 3-7R.
- **Mechanism:** Entry at zone edge tightens risk (SL = zone width + buffer), explodes R:R to effective 4:1+, and acts as natural fill filter (only deep penetrations trigger).

### Rule 2: H1@H4 with top-edge entry + partial TP is the production config
- **Description:** Limit entry at H4 zone top (demand) or bottom (supply), with partial TP: 70% at rr=3.0, 30% at next H1 zone.
- **Evidence:** SQN 24.14, PF 2.54, WR 54.6%, 3,747 trades at 1.5p spread. Nearly spread-immune (SQN 23.70 at 2.0p spread).
- **Why it works:** H4 zones have 5+ pip SL, so 1.5p spread is <30% of risk. Top edge gets more fills. Partial TP locks early profit.

### Rule 3: TTL=0 (until zone breaks) for limit orders
- **Description:** Keep pending limit orders active until the zone is body-close broken, not just same-bar.
- **Evidence:** Doubles trade count (2,402→6,493), higher SQN (39.4→44.6), doubles Total R. WR drops slightly (63.7%→52.6%) but volume overwhelms.
- **Live note:** Requires order lifecycle management — zone-break cancellation, stale limit replacement.

### Rule 4: Push zones are the highest conviction zones
- **Description:** Zones born at HA run transitions that create BOS/CHoCH events. These are "order blocks" in SMC terminology.
- **Evidence:** 0.000% break-through rate across 13,870 interactions. Compression-born push zones are 2x more durable.
- **Video consensus:** 8+ videos describe order blocks identically.

### Rule 5: Against-daily bias for H4 zones, with-daily for D1 zones
- **Description:** At H4 zones, trade the counter-trend pullback (price retracing against D1 push). At D1 zones, trade with the major trend.
- **Evidence:** H1@H4 against_daily SQN +1.12 vs with_daily SQN -1.37. H1@D1 with_daily SQN +2.66.
- **Why:** H4 counter-zones ARE the pullback destination. Trading "with daily" at H4 means those zones are being broken. D1 zones are the structural reversal — trade WITH the trend there.

### Rule 6: Retest 4-10 is the quality multiplier
- **Description:** Zones that have been retested 4-10 times are "proven" — they hold more reliably than fresh or heavily-tested zones.
- **Evidence:** +30-70% improvement in AvgR and PF consistently across all TF pairs and symbols. GBPUSD M5@M15→D1 AvgR +2.83→+4.85, PF 6.32.
- **Why:** The zone has demonstrated it holds under 4-10 tests. It's not yet exhausted (>10 tests shows degradation).

### Rule 7: Partial TP is transformative
- **Description:** Split position into Unit 1 (scalp) and Unit 2 (runner). Unit 1 TP at fixed R:R, move SL to breakeven, Unit 2 targets HTF zone.
- **Evidence:** H1@H4 went from SQN 1.61 to 24.14 with partial TP. The scalp portion locks profit; the runner gets a free shot at 10:1+ R:R.
- **Video consensus:** 5+ videos describe partial exit strategies.

### Rule 8: Zone SL mode with limit entries
- **Description:** SL behind the zone boundary (zone_bottom - 0.15*ATR for longs). Combined with limit entry at zone edge, this gives very tight structural risk.
- **Evidence:** 64-70% WR, 3-7R MaxDD. Never outperformed by ATR SL.
- **Logic:** If price breaks the zone, the thesis is invalidated. The SL is structural, not arbitrary.

### Rule 9: Cross-TF TP is universally profitable
- **Description:** M5 entry targeting H1/H4/D1 opposing zone. 12% WR but 2.2R+ average expectancy.
- **Evidence:** SQN 8.5-9.6 across all 5 symbols (GBPUSD, EURUSD, USDJPY, XAUUSD, GBPJPY). Remarkably consistent.
- **Note:** 12% WR is mathematically superior to 65% WR scalp in total return (+1.31R/trade vs +0.95R/trade). Psychologically brutal but mechanically sound.

### Rule 10: M15@H1 with min_sl=5p is the secondary config
- **Description:** Same limit mechanism on H1 zones with a 5-pip SL floor to survive spread.
- **Evidence:** SQN 14.46, PF 1.67 at 1.5p spread. The min_sl floor widens SL enough that spread is manageable.

### Rule 11: H1@H4 partial is universally profitable across all asset classes (NEW — 2026-04-08)
- **Description:** H1@H4 limit + partial TP works on FX, commodities, crypto, and indices.
- **Evidence:** 8-symbol sweep: SQN 18-32 at realistic spread. Worst case BTCUSD SQN 18.65 at 2400p spread. GBPJPY best at SQN 30.14 at 3.0p spread. All 8/8 symbols profitable.
- **This is the most universally validated config in the system.**

### Rule 12: Static nesting (LTF zones inside H4 zones) is viable cross-symbol (NEW — 2026-04-08)
- **Description:** Find existing M15 or M5 zones inside an active H4 zone, enter at those LTF zone edges.
- **Evidence:** 8-symbol sweep: Static M15 SQN 12-15, Static M5 SQN 9-11 across all 8 symbols. M5 entries have highest per-trade quality (avgR +1.0-1.4, WR 48-53%).
- **Key insight:** M5 entries inside H4 zones have HIGHER WR and avgR than M15 entries — precision wins.

### Rule 13: LTF entries REQUIRE HTF context (NEW — 2026-04-08)
- **Description:** Standalone M5@M15, M1@M5, M1@M15 without HTF zone context are weak.
- **Evidence:** Best standalone SQN 6.17 (US500 M5@M15 at 0 spread). Vs worst nested SQN 9.43 (XAUUSD static M5). The HTF zone provides the structural conviction that makes LTF entries work.

---

## Probable Rules (data suggests, needs more testing)

### Rule P1: M5@M15 may be viable with full feature set
- **Description:** M5@M15 with top edge + partial TP + min_sl=5p + TTL=0 has never been tested as a combined config.
- **Evidence:** Individual pieces work — partial TP transforms H1@H4 (SQN 1.6→24.1), min_sl=5p helps M15@H1 (SQN 14.5), top edge gets more fills. Spread model audit shows backtest is pessimistic by ~1 spread per trade.
- **Gap:** The full combination has never been swept. Also: spread at real 1.0p (common on EURUSD) vs 1.5p may flip the verdict.
- **Required test:** Single sweep: M5@M15, limit_edge=top, partial_tp=True, min_sl=5p, TTL=0, spread=0.5/1.0/1.5p.

### Rule P2: Limit + against_daily on H1@H4 may be the best intraday config
- **Description:** Combining the best entry mode (limit SQN 23.64) with the best market filter (against_daily SQN 1.12).
- **Evidence:** Both proven independently. Never combined in a sweep.
- **Required test:** H1@H4 limit + bias_filter=against_daily, with and without partial TP.

### Rule P3: Cascade layered limits (breaker zones inside HTF zones) should compound
- **Description:** When HTF zone retested, place limits at the LTF zones broken during the HTF zone's creation push.
- **Evidence:** Push zones 0% break-through (the HTF zone holds as backstop). M5@H1 limit 69.9% WR (the M5 layer IS reaching and filling). Multi-layer = multiple entries at different precision levels.
- **Required test:** Needs new engine mode (cascade_layered). Designed in findings doc but not built.

### Rule P4: Trendline breaks add structural confirmation
- **Description:** LTF trendline break between iCHoCH and eCHoCH confirms the structural shift is real.
- **Evidence:** Pine indicator built and visually validated. 5+ videos describe trendline breaks as confirmation. No Python engine implementation or sweep data.
- **Required test:** Add trendline break detection to Python engine, sweep as a filter dimension.

---

### Rule P5: Trendline break at S/D zone intersection = highest-consensus untested entry
- **Description:** When a trendline breaks AND price retests a zone at that broken TL level, enter with confirmation.
- **Evidence:** 11 videos from 8 independent traders agree on this specific pattern. No sweep data (trendlines not in Python engine).
- **Gap:** Port `iora_pivot_hl_trendlines.pine` to Python engine. Add trendline break events as a filter/trigger dimension.
- **Required test:** Add TL break detection → sweep as filter on existing TF pairs.

### Rule P6: Zone refinement (HTF→LTF) dramatically improves R:R
- **Description:** Drop 1-2 TFs to find smaller zones inside HTF zones. Same trade, same target, but 3x-6x better R:R.
- **Evidence:** V23 (JeaFx) shows 1.9R→6.25R improvement. Tasks 7-13 are implementing this exact concept.
- **Gap:** Tasks 7-13 sweep running now. Results pending.
- **Note:** "Two steps down" rule: 4H→1H→30m, D→4H→1H, 30m→15m→5m. Don't over-refine.

---

## Untested Hypotheses (no data yet)

### Hypothesis 1: HTF-triggered LTF nesting
- **Description:** HTF zone active (price inside D1/H4 zone) → find/create LTF zones inside it → limit entry at LTF zone edge.
- **Source:** Core concept from 11+ videos. "You only go to step three once price has entered into the point of interest" (Brett Go).
- **Status:** Tasks 1-6 complete (config fields, birth events, static+dynamic nesting). Tasks 7-13 pending (simulation engine, sweep).
- **Required test:** Complete Tasks 7-13, run sweep.

### Hypothesis 2: Opening range structure
- **Description:** First H4 candle of the session defines intraday support/resistance. Breakout + pullback = entry.
- **Source:** Videos 8, 9, 11 (3 independent traders). Matches H4 boundary finding in sweep data (median first H1 zone retest = 3.1h = one H4 candle).
- **Required test:** New engine feature — H4 candle high/low as dynamic S/R.

### Hypothesis 3: HMA cross as trigger event
- **Description:** HA candle closing above/below HMA(12/24) on H4 = momentum shift event → start looking for LTF entries.
- **Source:** Designed in findings doc. No video consensus (indicator-based, not structural).
- **Required test:** Compute HMA on H4/H1, add as filter/trigger dimension in sweep.

### Hypothesis 4: FVG detection as zone quality enhancer
- **Description:** Zones created with Fair Value Gaps (price imbalances between candle wicks) are stronger.
- **Source:** Videos 2, PTS-2. "Order blocks MUST contain an FVG — no FVG = not a valid OB."
- **Required test:** Add FVG detection (compare high[1] vs low[3] during pushes). Test as quality filter.

### Hypothesis 5: M1@M5 precision entries
- **Description:** M1 entries at M5 zone edges for maximum precision.
- **Source:** Implied by the fractal nature of the system. Zero data.
- **Required test:** Run basic sweep. Expectation: spread will likely kill it (tighter than M5@M15).

---

## Disproven Rules (data rejects)

### Disproven 1: HA trailing improves swing trades
- **Evidence:** HA trail on M5/M15/H1 all REDUCE AvgR. The HA reversal fires before Unit 2 TP is reached — cuts winners short.
- **Fully tested?** YES — tested across all TF pairs with multiple trail TFs. Confirmed dead.

### Disproven 2: Breakeven buffer improves partial TP
- **Evidence:** BE buffer reduces BE stops but doesn't improve blended outcome. Trades saved from BE eventually hit original SL.
- **Fully tested?** YES — tested 0.0/0.1/0.25/0.5 buffer. Confirmed dead.

### Disproven 3: Trading WITH daily bias at H4 zones
- **Evidence:** SQN -1.37. At H4 zones, "with daily" means the zone is being broken (the daily push goes through it).
- **Fully tested?** YES — clear structural explanation for failure.

### Disproven 4: ATR-based SL outperforms zone SL (with limit)
- **Evidence:** Never the best option in any config with limit entry. Zone SL is structural; ATR SL is arbitrary.
- **Fully tested?** YES.

### Disproven 5: Session filters as standalone
- **Evidence:** Neutral to slightly positive for FX, actively harmful for XAUUSD. Not enough edge to justify reduced trade count.
- **Fully tested?** Mostly — tested as simple filter. NOT tested as timing trigger (London CHoCH at zone).

### Disproven 6: Dynamic nesting outperforms static (NEW — 2026-04-08)
- **Evidence:** 8-symbol sweep: Dynamic M15 avg SQN 5.5 vs Static M15 avg SQN 13.8. Dynamic is 2.5x worse across ALL symbols.
- **Why:** Waiting for zone birth misses entries at pre-existing LTF zones. Static nesting uses whatever zones exist inside the H4 zone — simpler and captures more opportunities.
- **Fully tested?** YES — 8 symbols, multiple entry TFs, with and without spread.

### Disproven 7: Push filter on nested LTF zones (NEW — 2026-04-08)
- **Evidence:** Only 34-42 trades across 16.5 years when push filter active. Too few for statistical significance. SQN 1.0-3.4 on the few that exist.
- **Why:** Requiring LTF push on zones inside H4 zones is too restrictive. The H4 zone IS the structural conviction.
- **Fully tested?** YES — 4 of 8 symbols had enough trades to evaluate. All worse than no-push.

### Disproven 8: min_sl_spread_mult matters for H1@H4 (NEW — 2026-04-08)
- **Evidence:** 0-3% SQN difference across mult=0,2,3,5 at all spread levels. H4 zone SL already exceeds any spread floor.
- **Note:** May matter for standalone M5@M15 (untested), but irrelevant for the production H1@H4 config.

---

## Video Concepts Not Yet Mechanized

| Concept | Source Videos | Potential Implementation | Priority |
|---------|:---:|---|:---:|
| **TL break at S/D zone = entry** | V19-V24 (6 videos), PTS-4, PTS-5, 16 | Port `iora_pivot_hl_trendlines.pine` to Python. TL break event + zone intersection = sweep dimension. **11 videos validate this concept.** | **HIGH** |
| **Short-term TL on pullback in zone** | V22, V24 | Mini trendline on the pullback WITHIN a zone retest. Break = entry trigger. May already be captured by M5 CHoCH detection — verify. | HIGH |
| **TL touch points as TP (A/B/C)** | V19 | Label TL touch points oldest→newest. After break, they become staged TP targets. Novel structural TP beyond "next opposing zone." | MEDIUM |
| **Breaker block at TL breakout** | V22 | Zone that caused the TL break becomes a breaker. Retest = entry. Maps to cascade layered model. | HIGH (in Tasks 7-13) |
| **Zone refinement "two steps down"** | V23 | Already being built in Tasks 7-13. Rule: 4H→1H→30m, D→4H→1H, 30m→15m→5m. Don't over-refine. | In Progress |
| **4 entry aggressiveness levels** | V24 | (1) Anticipate at double bottom, (2) Immediate on break, (3) Candle close, (4) Swing break. Could map to configurable `entry_aggressiveness` in RetestConfig. | MEDIUM |
| **FVG detection** | 2, PTS-2 | `high[2] vs low[0]` gap during pushes = FVG. Add to zone birth metadata. | Medium |
| **Opening range (H4 candle)** | 8, 9, 11 | Track first H4 candle H/L per session. Use as dynamic S/R. | Medium |
| **Fibonacci golden zone** | PTS-1, PTS-6 | 50-61.8% retracement alignment with zone boundaries. | Low |
| **Wyckoff spring/UTAD** | 4 | Maps to liquidity sweep at zone + reversal. Already partially captured by wick_touch. | Low |
| **AME pattern** | PTS-1, PTS-2, PTS-9 | Range → false breakout → expansion. Maps to compression-born zones. Already captured. | Low |
| **DRD entry model** | PTS-1 | Displacement-Retracement-Displacement. Similar to BOS→zone→BOS chain. Already in cascade concept. | Low |
| **9 EMA scalp** | PTS-9 | Simple but indicator-based. Low priority for structural system. | Very Low |
| **Stop hunt of stop hunters** | PTS-9 | Re-entry after SL hit by extended sweep. Novel but low consensus. | Very Low |

### Symbol-Specific min_sl (Critical Implementation Fix)

**`min_sl_pips=5` must be replaced with `min_sl_spread_mult`.** Fixed pip counts are meaningless across different asset classes:

| Symbol | Spread | "5 pips" = | Correct min_sl at 3x spread |
|--------|:------:|:----------:|:---------------------------:|
| EURUSD | ~1.0p | 0.00050 | 3.0p (0.00030) |
| GBPJPY | ~4.0p | 0.050 | 12.0p (0.120) |
| XAUUSD | ~12p | $0.50 | 36p ($3.60) |
| BTCUSD | ~120p | $0.50 | 360p ($36.00) |
| XBRUSD | ~0.1p | $0.50 | 0.3p ($0.03) |

Formula: `min_sl = max(zone_sl, spread * min_sl_spread_mult)`
Sweep dimension: `min_sl_spread_mult` at [2, 3, 5]

---

## The Production System — Validated Config

### Primary: H1@H4 Limit + Partial TP
```
tf_pair:           H1@H4
entry_mode:        limit
limit_edge:        top
limit_ttl:         0 (until zone breaks)
sl_mode:           zone
sl_buffer_atr:     0.15
tp_mode:           fixed_rr
partial_tp:        true
partial_unit1_pct: 0.70
partial_unit1_rr:  3.0
partial_unit2_tp:  H1  (next opposing H1 zone)
spread_tolerance:  immune up to 3.0 pips

Validated metrics (GBPUSD, 1.5p spread):
  SQN: 24.14 | PF: 2.54 | WR: 54.6% | Trades: 3,747
  ~227 trades/year/symbol = ~4.5 trades/week
```

### Secondary: M15@H1 Limit + min_sl Floor
```
tf_pair:           M15@H1
entry_mode:        limit
limit_edge:        bottom
limit_ttl:         0
sl_mode:           zone
min_sl_pips:       5.0
tp_mode:           fixed_rr
fixed_rr:          3.0
spread_tolerance:  viable at 1.5 pips

Validated metrics (GBPUSD, 1.5p spread):
  SQN: 14.46 | PF: 1.67 | Trades: 3,606
```

### Pending Validation: M5@M15 Full-Feature
```
tf_pair:           M5@M15
entry_mode:        limit
limit_edge:        top
limit_ttl:         0
sl_mode:           zone
min_sl_pips:       5.0
partial_tp:        true
partial_unit1_pct: 0.70
partial_unit1_rr:  3.0
partial_unit2_tp:  H1
spread:            test at 0.5/1.0/1.5p

Status: NEVER TESTED as combined config.
Individual pieces all show promise.
Live M5@M15 reportedly profitable (JoMa) — backtest "dead" verdict may be wrong.
```

---

## Calibration Needed: JoMa Live Data

Once JoMa logs 100+ trades with enhanced LiveTradeRecord:

1. **Spread calibration:** Compare `spread_at_fill` distribution vs fixed 1.5p assumption
2. **Slippage impact:** Compare `limit_price` vs `entry_price` for actual slippage
3. **P&L parity:** Compare backtest predicted return_r vs live actual return_r
4. **Zone metadata correlation:** Which `touch_type`, `zone_role`, `age_bucket` produce best live results?
5. **MAE/MFE analysis:** Are our SL/TP distances optimal, or leaving money on the table?

**This is the #1 priority for validating/invalidating the mechanical ruleset against live reality.**
