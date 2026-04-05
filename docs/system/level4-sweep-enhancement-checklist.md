# Level 4 Sweep Enhancement Checklist

> **Purpose:** Comprehensive checklist of ALL sweep dimensions, configs, and data insights that must be tested to let the data speak. No guesswork — test everything, let outcomes decide.
>
> **Source:** Derived from `docs/system/level1-3-data-analysis.md` (716 lines of empirical findings) + Level 4 sweep gap analysis.
>
> **Date:** 2026-04-04 (updated: structural SL/TP + limit orders + PDH/PDL + premium/discount added)
> **Status:** Checklist — items marked ✅ are tested, ⬜ remain. 498 configs in current sweep.
> **GBPUSD expanded sweep results:** `docs/system/level4-expanded-sweep-analysis.md`
> **New in latest sweep:** structural SL/TP, limit order entries, PDH/PDL proximity, premium/discount alignment, parallelized execution

---

## 1. TF Pair Coverage

The current sweep only tests 4 of 8 available TF pairs.

| TF Pair | Data Depth | Wick Touches (5 sym) | Current Status | Action |
|---------|:-----------|---------------------:|:--------------:|--------|
| H1@H4 | 16.5 yrs | 146,532 | ✅ Tested | — |
| M15@H4 | 4.4 yrs | 74,106 | ✅ Tested | — |
| M15@H1 | 4.4 yrs | 175,597 | ✅ Tested | — |
| M5@H1 | 1.7 yrs | 109,041 | ✅ Tested | — |
| M5@M15 | 1.7 yrs | 242,246 | ✅ TESTED (expanded sweep) | **Body_close wins (SQN 1.52, 5,868 trades) — wick_touch is negative** |
| H1@D1 | 16.5 yrs | 52,483 | ✅ TESTED (expanded sweep) | **Winner for GBPUSD — SQN 2.66 with with_daily + rr=3.0** |
| M1@M5 | 0.7 yrs | 324,074 | ⬜ NOT tested | Add — most events total, but limited data depth |
| M1@M15 | 0.7 yrs | 178,942 | ⬜ NOT tested | Add — low priority due to 0.7 yr depth |

**Why M5@M15 matters:** Adjacent-TF pair with highest wick touch count (242k) and highest wick % (19.1%). M15 zones are structural enough to be meaningful, and M5 bars provide precise entry resolution. This could be the best intraday pair.

**Why H1@D1 matters:** D1 zones have 0.003% break-through rate (19 breaks in 552k events). Reversal zones at D1 level with daily bias = potentially highest conviction setups. 16.5 years of data. Skip-TF pairs (H1@D1, M15@H4) show higher reversal % (4% vs 1-2%).

---

## 2. Touch Type

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `touch_type="wick_touch"` | ✅ All configs | 12% of events, clean rejection signal | — |
| `touch_type="body_close"` | ⬜ NOT tested | 75% of events — dismissed as "noise" without outcome data | **Must test.** A body_close in an H1 zone by M5 is natural — price sits in the zone, accumulates, then reverses from inside. Could be valid entries. |
| `touch_type="any"` | ⬜ NOT tested | Combined wick + body_close | Add — see if including body_close improves trade count without destroying edge |

**Why body_close matters:** An M5 candle closing inside an H1 demand zone is structurally normal — the zone is wide relative to the entry bar. Price may reverse from the middle or bottom of the zone, not from the edge. Filtering to wick-only may be throwing away valid entries where price penetrated deeper before reversing. The data from Level 1-3 was about zone interaction frequency, not trade outcomes. Only Level 4 can tell us if body-close entries are profitable.

---

## 3. Bias Alignment

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `bias_filter="with_daily"` | ✅ Tested | 27-40% of wicks (varies by TF pair) | — |
| `bias_filter="any"` | ✅ Tested (baseline) | Unfiltered | — |
| `bias_filter="against_daily"` | ⬜ NOT tested | **43% of H1@H4 wicks** — dominates HTF pairs | **Must test.** Counter-trend pullbacks to HTF zones could be the best mean-reversion entries. The data shows MORE interactions happen against-daily at H1@H4 than with-daily. |
| `bias_filter="at_transition"` | ⬜ NOT tested | 2-3% of H1@H4 wicks, transitions every ~37h | **Must test.** Small count but potentially highest conviction — bias flipping while price is at a zone. |

**Critical insight from Level 1-3:** Bias alignment direction FLIPS between LTF and HTF pairs:
- LTF pairs (M1@M5, M5@M15): with-daily > against-daily (40% vs 36%)
- HTF pairs (H1@H4, H1@D1): against-daily > with-daily (43% vs 27%)

This means with_daily might be the WRONG filter for H1@H4. The data says more zone interactions happen counter-trend. Testing against_daily on HTF pairs and with_daily on LTF pairs separately is critical.

---

## 4. Zone Role

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `zone_role_filter="continuation"` | ✅ Tested | 72-77% of events, 0.019% break-through | — |
| `zone_role_filter="any"` | ✅ Tested (baseline) | Unfiltered | — |
| `zone_role_filter="push"` | ⬜ NOT tested | **0.000% break-through across 13,870 interactions** | **Must test.** Zero breaks = perfect hold rate. Low volume (~1-3% of events) but potentially extreme conviction. If push zone retests have even moderate win rate, the R-multiple could be exceptional because the zone never fails. |
| `zone_role_filter="pullback"` | ⬜ NOT tested | 20-27% of events, 0.066% break (highest fragility) | Add — test whether pullback zone retests have a different character |
| `zone_role_filter="reversal"` | ⬜ NOT tested | 1-4% of events. Skip-TF pairs (H1@D1, M15@H4) have 4% reversal rate. 230-667 reversal wicks with daily bias per HTF pair. | **Must test for HTF pairs.** Rare but structurally significant — a reversal at a D1 zone with bias alignment is a major structural event. |

**Why push zones at 0% break-through is a potential edge:**
Push zones are created at the start of a structural move — where institutional order flow initiated. They never break through. This means if you enter on a push zone retest, the zone itself provides a reliable floor/ceiling. Even with a moderate win rate, the SL (zone boundary) is almost never hit by a zone break-through. The risk is that price moves away from the zone slowly (time stop / SL from distance), not that the zone fails.

---

## 5. Zone Age

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `age_filter="fresh_young"` | ✅ Tested | 67-69% of events | — |
| `age_filter="any"` | ✅ Tested (baseline) | Unfiltered | — |
| `age_filter="fresh"` | ⬜ NOT tested | 33-43% of events. M5@H1 peaks at fresh, but H1@H4 peaks at young. | Add — test fresh-only to see if it improves or hurts |
| `age_filter="young"` | ⬜ NOT tested | 26-36% of events. **H1@H4 has young > fresh (35% vs 33%)** — the sweet spot for H4 zones is bars 11-50, not 0-10. | **Must test for H1@H4.** The data says young zones are more active than fresh at this TF pair. |
| `age_filter="mature"` | ⬜ NOT tested | 15-21% of events | Add — compression-born zones may be disproportionately mature |
| `age_filter="old"` | ⬜ NOT tested | 11-15% of events. Replaced zones live 2,500+ bars (many are "old"). | Add — old zones that survived are proven structural levels |

**TF-pair-specific age preference:**

| TF Pair | Peak Age | Empirical Basis |
|---------|----------|-----------------|
| M5@H1, M5@M15 | Fresh (43%, 39%) | Lower TF zones are most active immediately |
| H1@H4 | **Young (35% > Fresh 33%)** | H4 zones need time to establish significance |
| H1@D1 | **Young (36% > Fresh 37%)** nearly equal | D1 zones are wide, take time for meaningful retests |
| M15@H4 | **Young (35% > Fresh 39%)** close | H4 zones again peak young-ish |

Age filters must be tested per TF pair, not globally.

---

## 6. Retest Timing

Level 1 data shows precise retest timing patterns that are NOT currently used as sweep dimensions.

| Finding | Data | Current Status | Action |
|---------|------|:--------------:|--------|
| Median time to first H1 zone test: **3.1 hours** | Consistent across GBPUSD, EURUSD, XAUUSD | ⬜ NOT used | **Add as filter/analysis dimension.** If median first retest is 3.1h, entries within 1-5 hours of zone creation have a specific character. |
| Avg time to first H1 zone test: 21-36 hours | Long tail — some zones don't get retested for days | ⬜ NOT used | The gap between median (3.1h) and avg (21-36h) suggests two populations: quick retests and delayed retests. These may have different win rates. |
| M5 zones: ~10 retests before break | Level 1 lifecycle data | ⬜ NOT used | M5 zones live for ~10 retests. Test whether retest #1-3 vs #4-7 vs #8-10 have different outcomes. |
| H1 zones: ~53-62 retests before break | Level 1 lifecycle data | ⬜ NOT used | Which retests are most profitable — early (1-10), mid (10-30), late (30+)? |
| H4 zones: ~140-196 retests before break | Level 1 lifecycle data | ⬜ NOT used | H4 zones are extremely durable. Are the first 20 retests better than retests 100+? |

**What to add:**
- `time_since_creation` bucketed filter: "0-3h", "3-12h", "12h-3d", "3d+" for H1 zones
- `retest_number` filter: "1-3", "4-10", "10-20", "20+" — which retest of a zone is most profitable?
- These need new fields in RetestConfig and corresponding filter steps in filter_funnel.py

---

## 7. Birth Period Pattern

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| Birth pattern filter | ⬜ NOT available in RetestConfig | Compression-born zones survive **85-89 retests** vs expansion-born **37-45 retests** (2x durability) | **Must add.** New field `birth_pattern_filter` in RetestConfig with values: "compression" (LH_HL), "trending" (HH_HL or LH_LL), "expansion" (HH_LL), "any" |

**Why this matters:** Compression-born zones are 2x more durable than expansion-born. If you only enter on compression-born zone retests, you're entering on the most structurally reliable zones. The zone is more likely to hold, meaning your SL (zone boundary) is more likely to protect you.

84% of zones are born during clear trending periods (HH_HL or LH_LL). Only 8.6% are compression-born (LH_HL). So this is a quality filter that reduces volume significantly but could dramatically improve conviction.

---

## 8. Replacement Count

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `max_replacement_count=999` (no filter) | ✅ Default | — | — |
| `max_replacement_count=0` (original only) | ⬜ NOT tested | 38.3% of events. Original zones: avg 37 bars lifespan, 19.5 tests. | Add — are original zones better entries because they're structural first-movers? |
| `max_replacement_count=3` | ⬜ NOT tested | 68.1% of events (cumulative rc 0-3) | **Add — recommended by Level 1-3 analysis** |
| Require `replacement_count > 0` | ⬜ NOT tested | 61.7% of events. Replaced zones: avg 2,500+ bars lifespan, 81-95 tests. Proven survivors. | Add — test whether zones that survived replacement are better entries than original zones |

---

## 9. Direction (Long / Short)

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `direction="both"` | ✅ All configs | — | — |
| `direction="long"` | ⬜ NOT tested | Earlier M5@H1 sweep showed 88% WR long vs 56% short. XAUUSD has extreme demand bias (21.9 alive at H1 vs 6.9 supply). | **Must test.** If longs consistently outperform shorts, a long-only system could have significantly higher SQN. |
| `direction="short"` | ⬜ NOT tested | Same — test whether shorts have edge or are just noise | Must test separately |

**XAUUSD specifically:** With 21.9 demand zones alive vs 6.9 supply at H1, demand zone retests (long entries) are structurally dominant. Testing `direction="long"` on XAUUSD should show strong results if the zone retest thesis is correct.

---

## 10. Session Filtering

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `session_filter="london"` | ✅ Tested | 07:00-16:00 UTC | — |
| `session_filter="any"` | ✅ Tested (baseline) | Unfiltered | — |
| `session_filter="newyork"` | ⬜ NOT tested | 12:00-21:00 UTC | Add |
| `session_filter="london_ny_overlap"` | ⬜ NOT tested | 12:00-16:00 UTC — highest liquidity window | **Add — expected to show strongest edge for forex** |
| `session_filter="no_asian"` | ⬜ NOT tested | Exclude 23:00-07:00 UTC, keep London + NY | Add — removes low-liquidity hours without restricting to single session |

**For crypto (BTCUSD, ETHUSD):** Session filters may not apply (24/7 market). Test with `session_filter="any"` only.

---

## 11. Cascade Logic

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `cascade_filter="require_htf_signal"` | ✅ Tested (lookback=20) | — | — |
| `cascade_filter="none"` | ✅ Tested (baseline) | — | — |
| `cascade_filter="require_htf_signal"` lookback=[5,10,50] | ⬜ NOT tested | Only lookback=20 tested | Add — test sensitivity to lookback window |
| `cascade_filter="require_confluence_2"` | ⬜ NOT tested | Requires 2+ HTF pairs active | Add — highest conviction cascade |
| `inside_htf_zone` state | ⬜ NOT available | Price currently inside HTF zone vs recently touched | **Add as new cascade state.** "Inside" = price is sitting in the HTF zone right now. Stronger signal than "recently touched and moved away." Needs code addition. |
| `cascade_direction="any"` | ⬜ NOT tested | Currently only "same" direction tested | Add — test whether opposite-direction HTF signals also provide value (counter-trend cascade) |

---

## 12. SL/TP Modes

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `sl_mode="zone"` | ✅ Tested | SL at zone boundary + buffer | — |
| `sl_mode="atr"` | ✅ Tested | 1.5 ATR from entry | — |
| `sl_mode="period"` | ✅ Tested | SL at period tracker level | — |
| `tp_mode="fixed_rr"` 1.5/2.0/3.0 | ✅ Tested | Fixed R:R multiples | — |
| `tp_mode="zone"` (opposing zone) | ⬜ NOT available | TP at next opposing zone (nearest supply for longs, nearest demand for shorts) | **Must add.** Zone-based TP is structurally logical — exit where the next structural resistance/support is. Needs code addition in retest_sl_tp.py. |
| `tp_mode="period"` (period hi/lo) | ⬜ NOT available | TP at the period tracker's previous high/low | Add — structural TP based on period levels |
| `tp_mode="htf_zone"` (HTF zone) | ⬜ NOT available | TP at the next HTF zone boundary (e.g., enter at H1 zone, TP at H4 zone) | Add — cascaded TP target |
| SL ATR multiples: [1.0, 2.0, 2.5] | ⬜ NOT tested | Only 1.5x tested | Add — test sensitivity to ATR multiple |
| Trailing SL | ⬜ NOT available | Move SL to breakeven after 1R, trail by ATR | Add later — needs code addition |

---

## 13. Touch Policy

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `touch_policy="until_broken"` | ✅ Tested (default) | Zone re-enterable until price breaks through | — |
| `touch_policy="first_touch"` | ✅ Tested | Zone consumed after one entry | — |
| Retest number filter | ⬜ NOT available | Enter only on retest #1-3, or only on retest #5+, etc. | **Add.** Level 1 shows zones survive 10-196 retests depending on TF. Which retest number is most profitable? |

---

## 14. Inside Weekly Zone

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| `inside_w_zone` filter | ⬜ NOT available | Price inside weekly zone 33-45% of time. EURUSD: 42.8%, XAUUSD: 45.1%. | **Must add.** New boolean filter in RetestConfig. Weekly zones act as structural ceilings/floors. Entries while inside a W zone may have different outcomes than entries in open space. Needs bias timeline data to be available to the filter. |
| `d_to_w_relationship` filter | ⬜ NOT available | Continuation (20-27%), pullback (14-26%), inside_zone (33-45%), neutral (14-20%) | Add — test whether "continuation" entries (daily pushing away from W zone) outperform "pullback" entries (daily pushing toward W zone) |

---

## 15. Supply/Demand Asymmetry (Instrument-Specific)

| Config | Current Status | Empirical Basis | Action |
|--------|:--------------:|-----------------|--------|
| Long-only on trending instruments | ⬜ NOT tested | XAUUSD: 6.9 supply vs 21.9 demand alive at H1. Bull trend = demand retests are high-confidence. | **Test `direction="long"` on XAUUSD specifically.** Compare to `direction="both"`. |
| Supply-only filter for bear instruments | ⬜ NOT tested | Mirrored logic for bearish instruments | Add when bear-trending instruments are identified |
| Per-symbol zone population context | ⬜ NOT available | Supply/demand ratio at zone's TF as a feature | Future — feed into ML |

---

## 16. Combination Configs NOT Yet Tested

These are specific multi-filter combinations from Level 1-3 insights that should be tested as complete configs:

| # | Config Description | Empirical Basis | Priority |
|---|-------------------|-----------------|:--------:|
| 1 | H1@H4 + against_daily + continuation + young | HTF pairs favor against-daily (43%), young > fresh at H1@H4, continuation is 72% | **HIGH** |
| 2 | H1@H4 + push zone only + any bias | Push zones: 0% break-through. Test raw push retest edge. | **HIGH** |
| 3 | H1@D1 + reversal + with_daily | D1 reversal zones with daily bias = 667 events, structurally significant | **HIGH** |
| 4 | M5@M15 + with_daily + fresh + wick_touch | Adjacent pair, highest wick %, LTF favors with-daily | **HIGH** |
| 5 | H1@H4 + compression-born only | Compression zones survive 2x longer (85-89 retests) | HIGH (needs new filter) |
| 6 | H1@H4 + body_close + with_daily | Body close in H4 zone = price sitting in zone, may accumulate | **HIGH** |
| 7 | H1@H4 + at_transition | Bias flipping while at a zone, 3% of H1@H4 wicks | MEDIUM (low count) |
| 8 | M15@H4 + reversal + against_daily | Skip-TF pair with 4% reversal rate, counter-trend | MEDIUM |
| 9 | Any pair + rc=0 (original zones only) | 38% of events, structural first-movers | MEDIUM |
| 10 | Any pair + no_asian + direction=long | Combined session + direction filter | MEDIUM |
| 11 | H1@H4 + old zones only | Zones that survived 200+ bars = proven structural levels | MEDIUM |
| 12 | H1@H4 + retest #1 only (test_count==1) | First real retest = 7.3% of wicks, freshest reaction | MEDIUM |

---

## 17. Parent-TF Candle Boundary Timing

**Insight:** The 3.1-hour median to first H1 zone retest aligns almost exactly with one H4 candle period. This suggests H1 zones get retested when the H4 candle that was forming during zone creation closes and the next H4 candle opens. This is multi-TF candle formation mechanics — price revisits zones at parent-TF bar boundaries.

**What needs to be measured (Level 1 enhancement):**

| Zone TF | Expected Parent Boundary | Need To Measure |
|---------|--------------------------|-----------------|
| M5 | M15 close/open (~15 min) | Median/avg time to first M5 zone retest |
| M15 | H1 close/open (~60 min) | Median/avg time to first M15 zone retest |
| H1 | H4 close/open (~240 min / 3.1h ✅ confirmed) | Already measured |
| H4 | D1 close/open (~24h) | Median/avg time to first H4 zone retest |
| D1 | W1 close/open (~5 days) | Median/avg time to first D1 zone retest |

If the pattern holds (median first retest ≈ parent TF candle period), it confirms that zone retests are driven by parent-TF bar completion mechanics, not random price action.

**New sweep dimension:**

| Config | Status | Description |
|--------|:------:|-------------|
| `at_parent_tf_boundary` filter | ⬜ Needs code | Entry must occur within N entry-TF bars of a parent-TF candle open/close. E.g., for H1@H4 entries: entry within 2 H1 bars of an H4 candle boundary. |
| Retest timing buckets relative to parent TF | ⬜ Needs code | "0-1 parent bars", "1-2 parent bars", "2-4 parent bars", "4+ parent bars" since zone creation |

This is a structural timing signal, not just an arbitrary time window. Test whether retests that happen at parent-TF boundaries have different outcomes from retests at random times within the parent TF bar.

---

## 17b. HMA Direction Filter + HA-HMA Cross Signal (IN PROGRESS)

**New sweep dimensions:**

| Config | Status | Description |
|--------|:------:|-------------|
| `hma_filter="with_hma"` | ⬜ Building | Entry direction must match HMA slope (HMA rising = long only, falling = short only) |
| `hma_filter="with_hma"` + period 12 vs 24 | ⬜ Building | Test HMA(12) and HMA(24) on H1 and H4 |
| `hma_cross_trigger` | ⬜ Building | HA candle closes above/below HMA = early momentum signal. Only look for LTF entries within N bars of this cross event. |
| HMA TF: H1 vs H4 | ⬜ Building | Which TF's HMA provides the best direction filter for LTF entries |

**HA-HMA Cross as entry trigger:**
- H1 HA close above H1 HMA(24) after being below = bullish trigger → go long on M1/M5/M15
- H1 HA close below H1 HMA(24) after being above = bearish trigger → go short on M1/M5/M15
- H4 HA close above H4 HMA(12) = stronger/slower signal (covers more intraday)
- Combined with limit orders at breaker zones = HMA-triggered cascade entries

**Test configs:**
```
For pair in all_pairs:
    # HMA direction filter only
    hma_filter="with_hma", hma_tf="H1", hma_period=24
    hma_filter="with_hma", hma_tf="H4", hma_period=12
    hma_filter="with_hma", hma_tf="H4", hma_period=24

    # HMA cross trigger (event-based, not just directional)
    hma_cross_trigger=True, hma_tf="H1", hma_period=24
    hma_cross_trigger=True, hma_tf="H4", hma_period=12

    # Combined with limit entries
    entry_mode="limit", hma_filter="with_hma", hma_tf="H1", hma_period=24
    entry_mode="cascade_layered", hma_filter="with_hma", hma_tf="H4", hma_period=12
```

---

## 18. New Code Required

These items need code changes before they can be swept:

| Item | Where | Complexity | Description |
|------|-------|:----------:|-------------|
| `birth_pattern_filter` | RetestConfig + filter_funnel.py | Small | New field: "compression", "trending", "expansion", "any". Filter on `zone.birth_period_pattern`. |
| `inside_w_zone` filter | RetestConfig + filter_funnel.py + candidate enrichment | Medium | Needs weekly zone proximity from bias timeline to be available on RetestCandidate. |
| `d_to_w_relationship` filter | RetestConfig + filter_funnel.py | Medium | Same data source as inside_w_zone. |
| `inside_htf_zone` cascade state | filter_funnel.py cascade logic | Medium | Check if price is currently inside (not just recently touched) an HTF zone. |
| `tp_mode="zone"` | retest_sl_tp.py | Medium | Find nearest opposing zone at context TF, use as TP. Needs zone engine state at entry time. |
| `tp_mode="period"` | retest_sl_tp.py | Small | TP at period tracker hi/lo. Period levels already on RetestCandidate. |
| `retest_number` filter | RetestConfig + filter_funnel.py | Small | Filter on `zone.test_count` ranges (1-3, 4-10, 10+). |
| `time_since_creation` filter | RetestConfig + filter_funnel.py | Small | Compute age in hours from zone creation to retest event. Bucket and filter. |
| `at_parent_tf_boundary` filter | RetestConfig + filter_funnel.py | Medium | Check if retest occurs within N entry-TF bars of parent-TF candle boundary. Needs TF boundary detection (exists in tf_alignment.py). |
| Median retest time per zone TF | zone_audit_runner.py | Small | Measure median/avg first retest time for M5, M15, H4, D1 zones (currently only H1 measured at 3.1h). Validate parent-TF boundary alignment pattern. |
| SL ATR multiplier sweep | retest_sl_tp.py | Tiny | Already parameterized as `sl_atr_mult`. Just add configs with different values. |

---

## 19. PDH/PDL Proximity + Premium/Discount + Equal H/L (From Video Education)

Reference: `docs/system/trading_concepts_reference.md` — Videos 7, 10 (Brett Go bias checklist)

Three simple dimensions derived from data we already compute:

| Dimension | What It Is | How To Compute | Iora Data Source |
|-----------|-----------|---------------|-----------------|
| `near_pdh_pdl` | Entry zone is within 0.5 ATR of previous day high or low | `abs(entry_price - period_hi) < 0.5 * atr` OR `abs(entry_price - period_lo) < 0.5 * atr` | `RetestCandidate.period_hi`, `period_lo`, `atr` — already on the candidate |
| `premium_discount` | Is entry in the upper half (premium) or lower half (discount) of the D1 range? Longs in discount = higher conviction, shorts in premium = higher conviction | `mid = (d1_zone_top + d1_zone_bottom) / 2; if entry_price < mid → "discount" else "premium"` | Needs D1 zone boundaries on the candidate (from bias timeline) |
| `equal_hl_nearby` | Are there clustered swing highs/lows near the entry? (liquidity pool = stops sitting there) | Multiple zones with similar boundaries (within 0.2 ATR) at the same TF | Zone engine state — scan for zones with boundaries within threshold |

**Why these matter (from Video 10):**
- PDH/PDL = the most-watched levels by all traders. Entries near these levels have the highest structural significance.
- Premium/discount = buying cheap (discount) and selling expensive (premium) aligns with institutional logic.
- Equal H/L = liquidity pools where stops cluster. Price gravitates toward these levels (sweep them), then reverses.

**Implementation:**
- `near_pdh_pdl`: New boolean filter in RetestConfig. Check if `period_hi` or `period_lo` on D1 is within 0.5 ATR of entry price. Simple — data already on the candidate.
- `premium_discount`: New filter: "premium", "discount", "any". Needs D1 range context (nearest D1 supply top + D1 demand bottom → compute midpoint). May need to add D1 zone context to the candidate during building.
- `equal_hl_nearby`: More complex — requires scanning zone boundaries for clusters. Lower priority. Add as Phase 4.

---

## 20. Summary: Test Count

| Category | Tested | Not Tested | Total |
|----------|:------:|:----------:|:-----:|
| TF Pairs | 4 | 4 | 8 |
| Touch Types | 1 (wick) | 2 (body_close, any) | 3 |
| Bias Alignment | 2 (with, any) | 2 (against, transition) | 4 |
| Zone Role | 2 (continuation, any) | 3 (push, pullback, reversal) | 5 |
| Age Bucket | 2 (fresh_young, any) | 4 (fresh, young, mature, old) | 6 |
| Direction | 1 (both) | 2 (long, short) | 3 |
| Session | 2 (london, any) | 3 (ny, overlap, no_asian) | 5 |
| Cascade | 2 (htf_signal, none) | 3 (confluence_2, lookback variants, inside_htf) | 5 |
| SL Modes | 3 (zone, atr, period) | 1+ (atr multiplier variants) | 4+ |
| TP Modes | 1 (fixed_rr) | 3 (zone, period, htf_zone) | 4 |
| Birth Pattern | 0 | 4 (compression, trending, expansion, any) | 4 |
| Replacement Count | 1 (999/none) | 3 (0, 3, >0) | 4 |
| Inside W Zone | 0 | 2 (inside, not_inside) | 2 |
| D-to-W Relationship | 0 | 4 (continuation, pullback, inside, neutral) | 4 |
| Touch Policy | 2 (first, until_broken) | 1 (retest_number) | 3 |
| Retest Timing | 0 | 4 (0-3h, 3-12h, 12h-3d, 3d+) | 4 |

**Current coverage: 56 configs testing ~22 dimensions.**
**Full coverage needed: ~200+ configs testing ~64 dimensions.**

Not all combinations need to be tested — many will have too few trades. But every dimension should have at least a baseline config to establish whether it matters.

---

## 21. Run Order

**Phase 1 (no code changes needed):**
Add configs to `default_configs()` for all existing filter dimensions not yet tested:
- body_close touch type
- against_daily and at_transition bias
- push, pullback, reversal zone roles
- fresh, young, mature, old age (individual)
- long-only, short-only direction
- newyork, london_ny_overlap, no_asian session
- confluence_2 cascade, lookback 5/10/50
- replacement_count 0, 3
- M5@M15 and H1@D1 TF pairs
- ATR SL multiplier 1.0, 2.0, 2.5

**Phase 2 (small code additions):**
- birth_pattern_filter
- retest_number filter
- time_since_creation filter
- tp_mode="zone" and tp_mode="period"

**Phase 3 (medium code additions):**
- inside_w_zone filter
- d_to_w_relationship filter
- inside_htf_zone cascade state

Run each phase across all 5 symbols. Analyze results. Each phase informs the next.
