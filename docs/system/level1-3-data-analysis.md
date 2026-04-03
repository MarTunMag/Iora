# Retest Entry System — Levels 1-3 Data Analysis

> **Purpose:** Comprehensive analysis of Level 1 (Zone Audit), Level 2 (Bias Timeline), and Level 3 (Opportunity Counter) diagnostic data. These findings inform all Level 4 strategy design decisions.
>
> **Data periods:** M1: 0.7 yrs | M5: 1.7 yrs | M15: 4.4 yrs | H1: 16.5 yrs (XAUUSD: 27.9 yrs)
> **Symbols analyzed:** GBPUSD, EURUSD, USDJPY, XAUUSD, GBPJPY
> **Date produced:** 2026-04-03 (updated with full-depth all-TFs data)
> **TF pairs covered:** All 8 — M1@M5, M1@M15, M5@M15, M5@H1, M15@H1, M15@H4, H1@H4, H1@D1

---

## Table of Contents

1. [Level 2: Bias Timeline](#level-2-bias-timeline)
2. [Level 3: Opportunity Counter — Touch Types](#level-3-touch-types)
3. [Level 3: Opportunity Counter — Dimension Analysis](#level-3-dimension-analysis)
4. [Level 1: Zone Audit — Zone Lifecycle](#level-1-zone-lifecycle)
5. [All-TFs Full-Depth Analysis](#all-tfs-analysis)
6. [Cross-Level Insights](#cross-level-insights)
7. [Data Gaps and Known Issues](#data-gaps)
8. [Level 4 Design Implications](#level-4-implications)

---

## Level 2: Bias Timeline <a id="level-2-bias-timeline"></a>

### Bias Distribution

| Symbol | Bull (HH_HL) | Bear (LH_LL) | Compression (LH_HL) | Expansion (HH_LL) | Mixed/Unknown |
|--------|-------------|-------------|---------------------|-------------------|---------------|
| GBPUSD | 35.8% | 36.3% | 15.1% | 11.8% | 1.0% |
| EURUSD | 37.1% | 37.4% | 15.4% | 9.6% | 0.5% |
| XAUUSD | **47.4%** | 28.0% | 14.2% | 10.1% | 0.4% |

**Observations:**
- GBPUSD and EURUSD are balanced (bull ≈ bear), consistent with ranging FX pairs
- XAUUSD is heavily bull-biased (47% vs 28%) — reflects gold's multi-year uptrend in the data period
- Compression (15%) and expansion (10%) together account for ~25% — these are "uncertain" periods
- Mixed/unknown is negligible (<1%) after initial warmup

### D-to-W Relationship

| Symbol | Inside W Zone | Pullback | Continuation | Neutral |
|--------|--------------|----------|--------------|---------|
| GBPUSD | 33.0% | 26.3% | 20.7% | 20.0% |
| EURUSD | **42.8%** | 20.0% | 21.2% | 16.0% |
| XAUUSD | **45.1%** | 14.5% | 26.6% | 13.8% |

**Observations:**
- Price spends 33–45% of time inside weekly zones — significant confluence potential for Level 4
- EURUSD has the highest inside-zone rate (42.8%) — weekly zones are very active
- XAUUSD has the highest continuation rate (26.6%) — trending behavior
- "Neutral" (price away from any weekly zone) is the smallest bucket for XAUUSD (13.8%), meaning weekly zones are almost always relevant for gold

### Transition Frequency

| Symbol | Total M5 Bars | Transitions | Bars per Transition | Approx Hours |
|--------|--------------|-------------|--------------------:|-------------:|
| GBPUSD | 129,189 | 287 | 450 | ~37h |
| EURUSD | 129,208 | 278 | 465 | ~39h |
| XAUUSD | 127,821 | 285 | 448 | ~37h |

Bias transitions occur roughly every 1.5 trading days across all symbols. This is relatively frequent — Level 4 should consider transition events as potential entry/exit signals.

---

## Level 3: Opportunity Counter — Touch Types <a id="level-3-touch-types"></a>

### Touch Type Ratios (M5@H1)

| Symbol | Wick Touch | Body Close | Near-Miss | Break-Through | Total Events |
|--------|----------:|----------:|---------:|-------------:|------------:|
| GBPUSD | 12.3% | 74.5% | 13.1% | 0.024% | 171,028 |
| EURUSD | 11.6% | 75.9% | 12.5% | 0.022% | 194,739 |
| USDJPY | 12.1% | 75.1% | 12.8% | 0.030% | 166,095 |
| XAUUSD | 12.2% | 75.1% | 12.7% | 0.017% | 167,283 |
| GBPJPY | 12.7% | 74.0% | 13.3% | 0.027% | 195,759 |

**Key finding:** Ratios are remarkably consistent across all 5 symbols:
- **Body close dominates at ~75%** — this is NOT the clean retest we want for entries. It means on 3 out of 4 bars where price interacts with a zone, the bar's close is actually inside the zone.
- **Wick touch ≈ 12%** — this IS the clean entry signal (price wicks into zone, closes back out). Roughly 1 in 8 zone interactions.
- **Near-miss ≈ 13%** — almost as frequent as wick touches. Price respects zones even without entering them.
- **Break-through < 0.03%** — zones almost never fail on body-close-through. This validates the retest-entry thesis.

### Supply vs Demand Breakdown

| Side | Wick Touch % | Body Close % | Near-Miss % | Break-Through % |
|------|------------:|------------:|-----------:|-----------:|
| Supply | 11.6% | 75.9% | 12.5% | 0.027% |
| Demand | 12.8% | 73.9% | 13.3% | 0.021% |

Demand zones have a slightly higher wick touch rate (12.8% vs 11.6%) and slightly lower break-through rate (0.021% vs 0.027%). This suggests demand zones are marginally more reliable for retest entries.

### Per-Symbol Supply/Demand Wick Rates

| Symbol | Supply Wick % | Demand Wick % | Delta |
|--------|-------------:|-------------:|------:|
| GBPUSD | 12.0% | 12.7% | +0.7% |
| EURUSD | 11.5% | 11.7% | +0.2% |
| USDJPY | 11.5% | 12.7% | +1.2% |
| XAUUSD | 11.1% | **13.4%** | **+2.3%** |
| GBPJPY | 12.2% | **13.4%** | +1.2% |

**XAUUSD demand wick rate is the highest** (13.4%) — gold's demand zones produce the cleanest retests, consistent with the bull-trend-holds-demand theme from Level 1.

### Event Density

| Symbol | Events per 1000 M5 bars | Wick Touches per 1000 M5 bars |
|--------|------------------------:|-----------------------------:|
| GBPUSD | 1,324 | 163 |
| EURUSD | 1,507 | 175 |
| USDJPY | 1,286 | 155 |
| XAUUSD | 1,309 | 159 |
| GBPJPY | 1,515 | 193 |

There are ~160-193 wick touches per 1000 M5 bars, meaning roughly 1 wick touch event every 5-6 M5 bars. This is a high-frequency signal — Level 4 filtering must be aggressive to separate high-quality setups from noise.

---

## Level 3: Opportunity Counter — Dimension Analysis <a id="level-3-dimension-analysis"></a>

### Bias Alignment

| Symbol | With Daily | Against Daily | Neutral | At Transition |
|--------|----------:|-------------:|--------:|-------------:|
| GBPUSD | 30.7% | 38.4% | 30.7% | 0.3% |
| EURUSD | 31.7% | 41.7% | 26.3% | 0.2% |
| USDJPY | 32.2% | 38.8% | 28.7% | 0.3% |
| XAUUSD | 33.6% | 39.8% | 26.3% | 0.3% |
| GBPJPY | 34.7% | 37.8% | 27.2% | 0.2% |

**Against-daily touches consistently outnumber with-daily** (38-42% vs 31-35%). This makes sense: price moves against bias (pullback) before resuming trend, creating more counter-trend zone interactions. However, with-daily touches should have a higher success rate — Level 4 should test this hypothesis.

### Bias Alignment x Bias Strength (Wick Touches Only, All Symbols)

| Strength | Total Wicks | With Daily | Against Daily | Neutral |
|----------|----------:|----------:|-------------:|--------:|
| 1 | 38,431 | 10,043 (26%) | 11,539 (30%) | 16,597 (43%) |
| 2 | 33,840 | 10,014 (30%) | 11,217 (33%) | 12,396 (37%) |
| 3 | 36,608 | 17,792 (49%) | 18,816 (51%) | 0 (0%) |

**Key finding:** At strength 3, there is zero neutral — by definition, when all depth levels align, bias is clear. The with/against split at strength 3 is nearly 50/50 (49% vs 51%), meaning even in strong trends, counter-trend zone interactions are just as common.

### Zone Role Distribution

| Symbol | Push | Reversal | Continuation | Pullback | Unknown |
|--------|-----:|--------:|------------:|---------:|-------:|
| GBPUSD | 1.7% | 2.8% | 75.6% | 20.0% | 0.0% |
| EURUSD | 2.5% | 4.5% | 72.7% | 20.4% | 0.0% |
| USDJPY | 1.8% | 1.7% | 77.3% | 19.2% | 0.0% |
| XAUUSD | 2.3% | **7.9%** | 71.0% | 18.9% | 0.0% |
| GBPJPY | 0.8% | 2.0% | 75.3% | 22.0% | 0.0% |

- **Continuation zones dominate** (71-77%) — most structural swings continue the prevailing direction
- **Pullback ≈ 20%** — second most common, always present
- **Push and reversal are rare** (< 8% combined) — but potentially highest value per event
- **XAUUSD has 7.9% reversal** — highest across all symbols, likely due to sharper trend reversals in gold

### Zone Role x Bias Alignment (Wick Touches, Cross-Tab)

| Bias \ Role | Continuation | Pullback | Push | Reversal |
|-------------|------------:|---------:|-----:|---------:|
| Against daily | 29,415 | 9,534 | 492 | 2,131 |
| Neutral | 21,626 | 6,564 | 374 | 591 |
| With daily | 28,626 | 7,922 | 998 | 303 |
| At transition | 333 | 120 | 6 | 6 |

**Notable patterns:**
- **Push zones + with-daily = 998 wicks** — push zones are twice as likely to occur with-daily (998) vs against-daily (492). Makes sense: pushes happen in trend direction.
- **Reversal zones + against-daily = 2,131 wicks** — reversals happen overwhelmingly counter-trend. Only 303 reversals are with-daily.
- **Continuation + with-daily ≈ continuation + against-daily** (28.6k vs 29.4k) — continuation zones are direction-neutral in frequency.

### Age Bucket Distribution

| Symbol | Fresh (0-10) | Young (11-50) | Mature (51-200) | Old (201+) |
|--------|------------:|-------------:|---------------:|---------:|
| GBPUSD | 42.9% | 26.1% | 20.2% | 10.8% |
| EURUSD | 37.7% | 26.9% | 21.5% | 13.9% |
| USDJPY | 42.7% | 24.3% | 19.0% | 13.9% |
| XAUUSD | 41.1% | 29.6% | 19.1% | 10.2% |
| GBPJPY | 40.5% | 26.7% | 19.6% | 13.2% |

- **Fresh zones generate ~40% of all events** — the most active period for a zone
- **Decline is gradual**: ~27% young, ~20% mature, ~12% old
- This is consistent with Level 1 showing median H1 zone lifespan of ~100 bars (young/mature range)

### Wick Touch Price Distance by Age

| Age Bucket | Avg Distance (ATR) | Count |
|------------|-------------------:|------:|
| Fresh | 2.88 | 47,249 |
| Young | 3.27 | 28,353 |
| Mature | 3.47 | 21,105 |
| Old | 3.52 | 12,334 |

Wick touches on fresh zones are closer to the zone (2.88 ATR from midpoint) compared to old zones (3.52 ATR). This suggests fresh zones are "tighter" — price hasn't moved far from the zone, so the retest is more meaningful as a potential reversal point.

### Test Count Distribution

| Symbol | First Touch (0) | Retested 1 | Retested 2+ |
|--------|---------------:|----------:|-----------:|
| GBPUSD | 1.3% | 2.1% | 96.6% |
| EURUSD | 1.1% | 1.8% | 97.0% |
| USDJPY | 1.2% | 2.1% | 96.7% |
| XAUUSD | 1.2% | 2.0% | 96.8% |
| GBPJPY | 1.1% | 1.8% | 97.1% |

**97% of events are on zones already tested 2+ times.** First touches are extremely rare (1.1-1.3%). This means:
- Most zone interactions are on "proven" zones that have already been tested
- First-touch events, while rare, may be highest conviction (zone hasn't been weakened yet)
- Level 4 should track and weight first-touch entries separately

### First Touch Profile

| Dimension | Value |
|-----------|-------|
| Total first touches | 10,616 across 5 symbols |
| Touch type: near-miss | **97.9%** |
| Touch type: break-through | 2.0% |
| Touch type: wick_touch | **0.0%** |
| Touch type: body_close | 0.1% |
| Avg bias strength | 1.98 |
| Avg price distance | 2.81 ATR |

**Critical finding:** First touches are overwhelmingly near-misses (97.9%), with zero wick touches. This means by the time a zone has its first recorded interaction, price approaches but doesn't enter — the actual first retest (wick touch) comes later, when `test_count` is already ≥1. This is an artifact of how zones are created near current price — the first "event" is price pulling away slightly.

**Implication for Level 4:** `test_count == 1` (retested_1) is effectively the "first real retest" for entry purposes. First-touch events should be excluded from entry signals — they are near-misses during zone formation.

### Replacement Count Distribution

| Replacement Count | % of Events | Cumulative |
|------------------:|------------:|----------:|
| 0 (original) | 38.3% | 38.3% |
| 1 | 15.8% | 54.1% |
| 2 | 8.6% | 62.7% |
| 3 | 5.4% | 68.1% |
| 4 | 3.6% | 71.7% |
| 5-9 | 9.8% | 81.5% |
| 10-19 | 8.1% | 89.6% |
| 20+ | 10.4% | 100% |

- **38% of events occur on original (never-replaced) zones** — these are the "first" zone on that TF/side slot
- Long tail: 10% of events are on zones that have been replaced 20+ times
- Higher replacement count likely correlates with ranging/choppy conditions where zones keep forming and being superseded
- Level 4 could filter on `replacement_count <= 3` to focus on "fresh structural" zones

### Birth Period Pattern Distribution

| Pattern | % of Events | Meaning |
|---------|:----------:|---------|
| LH_LL | 42.7% | Zone born during bear push — bearish momentum at creation |
| HH_HL | 40.9% | Zone born during bull push — bullish momentum at creation |
| LH_HL | 8.6% | Zone born during compression — uncertain at creation |
| HH_LL | 7.2% | Zone born during expansion — volatile at creation |
| Mixed | 0.6% | Ambiguous period pattern |

Zones born during clear trending periods (LH_LL or HH_HL) account for 84% of all events. Zones born during compression/expansion are much rarer.

### Break-Through Rate by Zone Role

| Role | Break-Throughs | Total Touches | Rate |
|------|---------------:|--------------:|-----:|
| Push | 0 | 13,870 | **0.000%** |
| Reversal | 1 | 30,063 | 0.003% |
| Continuation | 112 | 582,527 | 0.019% |
| Pullback | 101 | 153,058 | **0.066%** |

- **Push zones never break through** — perfect holding rate across 13,870 interactions
- **Pullback zones are most fragile** at 0.066%, but still extremely rare
- All rates are below 0.1% — zones are very reliable as support/resistance levels

### Near-Miss to Wick Ratio by Zone Role

| Role | Wick Touches | Near-Misses | Ratio |
|------|------------:|------------:|------:|
| Push | 1,870 | 2,065 | 1.10 |
| Reversal | 3,031 | 3,187 | 1.05 |
| Continuation | 80,000 | 82,902 | 1.04 |
| Pullback | 24,140 | 27,230 | **1.13** |

Pullback zones have the highest near-miss ratio (1.13) — price respects them from further away, possibly indicating stronger supply/demand imbalance at pullback levels.

### High-Value Combinations (Wick Touch + With-Daily Bias)

Top 10 combos across all 5 symbols:

| Zone Role | Age Bucket | Count | Avg Bias Strength | Avg Price Dist (ATR) |
|-----------|-----------|------:|------------------:|--------------------:|
| Continuation | Fresh | 15,422 | 2.22 | 2.81 |
| Continuation | Young | 7,481 | 2.19 | 2.90 |
| Continuation | Mature | 4,880 | 2.27 | 2.95 |
| Pullback | Young | 3,441 | 2.23 | 3.32 |
| Pullback | Mature | 2,452 | 2.31 | 3.15 |
| Pullback | Fresh | 1,440 | 2.24 | 3.25 |
| Continuation | Old | 843 | 1.52 | 2.71 |
| Push | Young | 601 | 2.47 | 2.52 |
| Pullback | Old | 589 | 1.64 | 3.39 |
| Push | Mature | 219 | 2.44 | 3.58 |

**Fresh continuation + with-daily = 15,422 wick touches** — the single largest high-value bucket. This is the most common "good setup" in the data.

### Body Close Distance Profile

| Threshold | % of Body Closes Within |
|----------:|:----------------------:|
| 0.5 ATR | 19.1% |
| 1.0 ATR | 37.4% |
| 2.0 ATR | 65.3% |
| 5.0 ATR | 93.4% |

37% of body closes are within 1 ATR of the zone midpoint. These close-to-midpoint body closes could indicate strong zone interaction (not just price drifting through) and might be worth distinguishing from wider body closes in Level 4.

---

## Level 1: Zone Audit — Zone Lifecycle <a id="level-1-zone-lifecycle"></a>

### Zone Creation and Break Counts

| TF | GBPUSD Created | GBPUSD Broken | EURUSD Created | EURUSD Broken | XAUUSD Created | XAUUSD Broken |
|----|------:|------:|------:|------:|------:|------:|
| M5 | 31,973 | 31,948 | 32,031 | 32,008 | 31,970 | 31,956 |
| M15 | 10,620 | 10,595 | 10,772 | 10,751 | 10,470 | 10,435 |
| H1 | 2,763 | 2,727 | 2,759 | 2,731 | 2,610 | 2,581 |
| H4 | 653 | 620 | 651 | 613 | 643 | 620 |
| D1 | 106 | 91 | 108 | 88 | 113 | 84 |
| W1 | 24 | 20 | 20 | 15 | 24 | 12 |

Zone creation is remarkably consistent across symbols at the same TF. Higher TFs have proportionally fewer unbroken zones but they survive much longer.

### Average Retests Before Break (Zone Lifetime in Retests)

| TF | GBPUSD (S/D) | EURUSD (S/D) | XAUUSD (S/D) |
|----|:-----------:|:-----------:|:-----------:|
| M5 | 9.8 / 9.7 | 9.8 / 10.1 | 9.5 / 9.8 |
| M15 | 19.5 / 19.6 | 20.2 / 20.9 | 19.5 / 18.3 |
| H1 | 53.5 / 53.9 | 61.0 / 62.4 | 61.3 / 50.5 |
| H4 | 178.2 / 141.1 | 182.3 / 172.0 | 195.7 / 140.4 |
| D1 | 690 / 721 | 846 / 905 | 1,256 / 547 |
| W1 | 2,012 / 2,371 | 3,749 / 3,939 | 5,603 / 2,315 |

**Observations:**
- Zone lifetime scales roughly 2x per TF step (M5→M15→H1)
- H1 zones survive 50-62 retests on average — very durable
- H4 zones survive 140-196 retests — extremely durable
- **XAUUSD supply/demand asymmetry**: XAUUSD D1 supply survives 1,256 retests but D1 demand only 547 — because in a bull market, supply gets constantly tested (price keeps pushing up), while demand breaks less often (fewer deep pullbacks)

### Average Zones Alive (Concurrent Active Zones)

| TF | GBPUSD (S/D) | EURUSD (S/D) | XAUUSD (S/D) |
|----|:-----------:|:-----------:|:-----------:|
| M5 | 15.7 / 16.1 | 16.2 / 16.2 | 13.1 / 18.6 |
| M15 | 15.7 / 16.0 | 15.5 / 16.1 | 10.7 / 20.0 |
| H1 | 14.0 / 16.8 | 14.0 / 16.9 | **6.9 / 21.9** |
| H4 | 9.2 / 12.3 | 7.8 / 15.2 | **3.4 / 24.1** |
| D1 | 3.2 / 5.8 | 2.6 / 8.0 | **1.4 / 17.9** |

**XAUUSD supply/demand asymmetry is extreme at higher TFs:**
- H1: 6.9 supply vs 21.9 demand alive — gold shreds supply zones 3x faster than demand
- H4: 3.4 supply vs 24.1 demand — barely any supply zones survive
- D1: 1.4 supply vs 17.9 demand — almost no D1 supply exists at any given time

This has a direct Level 4 implication: for trending instruments like gold, **demand zone retests in bull trends are much more meaningful** than supply retests.

### H1 Zone Test Count Distribution

| Bucket | GBPUSD | EURUSD | XAUUSD |
|--------|-------:|-------:|-------:|
| 0-5 tests | 13.3% | 13.4% | 13.4% |
| 6-20 tests | 27.0% | 26.6% | 27.0% |
| 21-50 tests | 28.0% | 26.7% | 27.5% |
| 51-100 tests | 16.8% | 16.6% | 16.7% |
| 100+ tests | 15.2% | 16.9% | 15.7% |

Remarkably consistent across symbols. ~15% of H1 zones receive 100+ retests before breaking.

### Time to First Test (H1 Zones)

| Symbol | Avg Hours | Median Hours |
|--------|----------:|------------:|
| GBPUSD | 35.5h | **3.1h** |
| EURUSD | 23.6h | **3.1h** |
| XAUUSD | 21.5h | **3.1h** |

**Median time to first H1 zone test is exactly 3.1 hours** across all symbols. This means half of all H1 zones get their first retest within ~3 hours of creation — fast. The average is much higher (21-36h) due to long-tail outliers.

### Original vs Replaced Zones (H1)

| Symbol | Metric | Original (rc=0) | Replaced (rc>0) |
|--------|--------|:---------------:|:---------------:|
| GBPUSD | Avg lifespan | 35.9 bars | 2,577.6 bars |
| GBPUSD | Avg tests | 19.5 | 81.3 |
| GBPUSD | Count | 1,234 | 1,529 |
| EURUSD | Avg lifespan | 38.1 bars | 2,561.0 bars |
| EURUSD | Avg tests | 19.4 | 95.1 |
| XAUUSD | Avg lifespan | 38.9 bars | 2,468.4 bars |
| XAUUSD | Avg tests | 20.8 | 83.0 |

**Replaced zones live dramatically longer** (2,500+ bars vs ~37 bars) and accumulate 4x more retests. This is survivorship bias — zones that get replaced are older zones that weren't themselves broken yet. But it also means `replacement_count > 0` is a proxy for "mature, well-established zone."

### H1 Zone Lifetime by Birth Period Pattern

| Pattern | GBPUSD Avg Tests | EURUSD Avg Tests | XAUUSD Avg Tests |
|---------|:----------------:|:----------------:|:----------------:|
| HH_HL (bull push) | 52.0 | 64.0 | 50.6 |
| LH_LL (bear push) | 54.5 | 62.0 | 59.1 |
| LH_HL (compression) | **87.3** | **89.2** | **85.8** |
| HH_LL (expansion) | 37.5 | 38.1 | 45.3 |

**Zones born during compression survive the longest** (85-89 retests) — when the market is in a squeeze, zones formed are more likely to be structural. Zones born during expansion have the shortest life (37-45 retests) — volatile conditions produce less reliable zones.

---

## All-TFs Full-Depth Analysis <a id="all-tfs-analysis"></a>

> **Run date:** 2026-04-03. Each entry TF loaded its own full date range independently.
> **Runtime:** 46.4 minutes for 5 symbols, 8 TF pairs each. ~9M total events.

### Data Depth per Entry TF

| Entry TF | Period | Years | Bars | TF Pairs Produced |
|----------|--------|------:|-----:|-------------------|
| M1 | 2025-08 to 2026-04 | 0.7 | ~246k | M1@M5, M1@M15 |
| M5 | 2024-07 to 2026-04 | 1.7 | ~129k | M5@M15, M5@H1 |
| M15 | 2021-11 to 2026-04 | 4.4 | ~110k | M15@H1, M15@H4 |
| H1 | 2009-09 to 2026-04 | 16.5 | ~102k | H1@H4, H1@D1 |

XAUUSD H1 data extends to 1998 (27.9 years, 65k bars) — deepest dataset.

### Event Totals per TF Pair (All 5 Symbols)

| TF Pair | Total Events | Wick Touch | Body Close | Near-Miss | Break-Through | Wick % | Data Depth |
|---------|------------:|----------:|---------:|---------:|-------------:|-------:|:-----------|
| H1@D1 | 552,446 | 52,483 | 444,230 | 55,714 | 19 | 9.5% | 16.5 yrs |
| H1@H4 | 806,322 | 146,532 | 512,475 | 146,387 | 928 | 18.2% | 16.5 yrs |
| M15@H1 | 982,045 | 175,597 | 634,192 | 171,018 | 1,238 | 17.9% | 4.4 yrs |
| M15@H4 | 657,193 | 74,106 | 505,236 | 77,792 | 59 | 11.3% | 4.4 yrs |
| M5@M15 | 1,268,140 | 242,246 | 784,414 | 239,416 | 2,064 | 19.1% | 1.7 yrs |
| M5@H1 | 894,904 | 109,041 | 670,265 | 115,384 | 214 | 12.2% | 1.7 yrs |
| M1@M15 | 1,706,936 | 178,942 | 1,285,011 | 242,801 | 182 | 10.5% | 0.7 yrs |
| M1@M5 | 2,174,310 | 324,074 | 1,395,105 | 453,731 | 1,400 | 14.9% | 0.7 yrs |

**Key observations:**
- **Wick touch % varies significantly by TF pair** — not uniform like the single-TF M5@H1 analysis suggested
- **Adjacent-TF pairs have higher wick %** (M5@M15: 19.1%, H1@H4: 18.2%) vs skip-TF pairs (M15@H4: 11.3%, H1@D1: 9.5%)
- This makes sense: adjacent TFs have tighter zone-to-price relationships, producing cleaner wicks rather than deep body penetrations
- **H1@D1 has the lowest wick %** (9.5%) — D1 zones are so wide that entry bars (H1) close inside them 80% of the time

### Per-Symbol Wick Consistency

| TF Pair | GBPUSD | EURUSD | USDJPY | XAUUSD | GBPJPY | Total |
|---------|-------:|-------:|-------:|-------:|-------:|------:|
| H1@D1 | 10,871 | 11,691 | 10,840 | 7,583 | 11,498 | 52,483 |
| H1@H4 | 30,581 | 30,329 | 31,752 | 21,292 | 32,578 | 146,532 |
| M15@H1 | 35,115 | 34,969 | 33,453 | 33,514 | 38,546 | 175,597 |
| M15@H4 | 14,988 | 15,257 | 13,826 | 14,233 | 15,802 | 74,106 |
| M5@M15 | 47,858 | 49,855 | 44,248 | 46,666 | 53,619 | 242,246 |
| M5@H1 | 21,074 | 22,612 | 20,043 | 20,369 | 24,943 | 109,041 |
| M1@M15 | 33,293 | 35,517 | 33,368 | 35,321 | 41,443 | 178,942 |
| M1@M5 | 61,932 | 63,353 | 60,230 | 64,057 | 74,502 | 324,074 |

- **Cross-symbol consistency is excellent** — counts are within 10-15% of each other per pair (GBPJPY slightly higher, XAUUSD H1 slightly lower due to fewer trading hours)
- **XAUUSD H1@H4 is lower** (21,292 vs 30k+ for FX) despite 27.9 years of data — gold has fewer bars per year due to limited trading sessions pre-2010

### Statistical Depth Assessment

For Level 4 sweep significance, we need sufficient wick_touch events per dimension combo. Minimum threshold: **500 wick touches per cell** for meaningful parameter optimization.

| TF Pair | Total Wicks | Per Symbol Avg | Statistical Viability | Recommended Priority |
|---------|----------:|:----------:|:---------------------:|:-------------------:|
| H1@H4 | 146,532 | ~29k | Excellent (16.5 yrs) | **1st — primary** |
| M15@H4 | 74,106 | ~15k | Excellent (4.4 yrs) | **2nd — primary** |
| M15@H1 | 175,597 | ~35k | Excellent (4.4 yrs) | **3rd — primary** |
| M5@H1 | 109,041 | ~22k | Good (1.7 yrs) | **4th — secondary** |
| M5@M15 | 242,246 | ~48k | Good (1.7 yrs) | 5th — secondary |
| H1@D1 | 52,483 | ~10k | Good (16.5 yrs) | 6th — secondary |
| M1@M5 | 324,074 | ~65k | Limited (0.7 yrs) | 7th — tertiary |
| M1@M15 | 178,942 | ~36k | Limited (0.7 yrs) | 8th — tertiary |

**Priority rationale:**
- H1@H4 and M15@H4 combine deep history with meaningful zone TFs — H4 zones are structural and durable
- M15@H1 has excellent count and covers the intraday swing sweet spot
- M5@H1 was the original analysis pair and remains solid
- M1 pairs have only 0.7 years — too short for multi-regime validation; defer to later data accumulation

### Wick Touch Rate by TF Pair Structure

The wick touch % reveals a clear pattern based on the TF gap between entry and zone:

| Gap Type | TF Pairs | Avg Wick % | Interpretation |
|----------|----------|----------:|----------------|
| 1-step adjacent | M1@M5, M5@M15, H1@H4 | 17.4% | Tight relationship, clean wicks |
| 2-step gap | M1@M15, M5@H1, M15@H4 | 11.3% | Moderate gap, more body closes |
| 3-step gap | M15@H1 | 17.9% | Exception — M15 is good entry resolution for H1 zones |
| 4-step gap | H1@D1 | 9.5% | Wide gap, D1 zones too broad for H1 precision |

M15@H1 breaks the pattern because M15 provides enough resolution to wick-reject H1 zones cleanly, while M15@H4 drops to 11.3% because H4 zones are too wide for M15 precision. This suggests **zone width relative to entry bar size** is the key driver, not just TF distance.

### Zone Role Distribution by TF Pair (Wick Touches)

| TF Pair | Continuation | Pullback | Reversal | Push |
|---------|:-----------:|:-------:|:-------:|:---:|
| H1@D1 | 73% | 21% | 4% | 2% |
| H1@H4 | 72% | 25% | 2% | 1% |
| M15@H1 | 72% | 25% | 2% | 1% |
| M15@H4 | 73% | 20% | 4% | 3% |
| M5@M15 | 71% | 27% | 1% | 1% |
| M5@H1 | 73% | 22% | 3% | 2% |
| M1@M15 | 74% | 22% | 2% | 2% |
| M1@M5 | 72% | 25% | 1% | 1% |

**Remarkably stable across all TF pairs.** Continuation zones always dominate at 71-74%, pullback at 20-27%. The zone role distribution is a structural constant, not TF-dependent.

**Skip-TF pairs (H1@D1, M15@H4) show higher reversal %** (4% vs 1-2%) — when the zone is from a much higher TF, reversals at that zone are more structurally significant.

### Age Bucket Distribution by TF Pair (Wick Touches)

| TF Pair | Fresh | Young | Mature | Old |
|---------|:-----:|:-----:|:------:|:---:|
| H1@D1 | 37% | 36% | 16% | 12% |
| H1@H4 | 33% | 35% | 18% | 14% |
| M15@H1 | 40% | 27% | 21% | 12% |
| M15@H4 | 39% | 35% | 15% | 11% |
| M5@M15 | 39% | 33% | 13% | 15% |
| M5@H1 | 43% | 26% | 19% | 11% |
| M1@M15 | 43% | 31% | 12% | 14% |
| M1@M5 | 41% | 32% | 15% | 12% |

**H1@H4 is the outlier** with the most balanced distribution (33/35/18/14) — H4 zones persist long enough that young and mature zones contribute nearly as much as fresh. This validates H1@H4 as the best pair for studying zone aging effects.

### Test Count Classification (Wick Touches)

| TF Pair | Retested 1 | Retested 2+ |
|---------|:--------:|:--------:|
| H1@D1 | 3.0% | 97.0% |
| H1@H4 | 7.3% | 92.7% |
| M15@H1 | 6.9% | 93.1% |
| M15@H4 | 3.7% | 96.3% |
| M5@M15 | 7.6% | 92.4% |
| M5@H1 | 4.2% | 95.8% |
| M1@M15 | 3.4% | 96.6% |
| M1@M5 | 6.0% | 94.0% |

**Zero first-touch wick touches across ALL TF pairs** — confirming the M5@H1 finding is universal. "Retested 1" (first real retest) ranges from 3-8%, with adjacent-TF pairs having more (7-8%) because zones get their first retest faster on adjacent TFs.

### Bias Alignment by TF Pair (Wick Touches)

| TF Pair | With Daily | Against Daily | Neutral | At Transition |
|---------|:---------:|:------------:|:------:|:------------:|
| H1@D1 | 33% | 41% | 24% | 2% |
| H1@H4 | 27% | 43% | 27% | 3% |
| M15@H1 | 34% | 39% | 27% | 1% |
| M15@H4 | 27% | 43% | 29% | 1% |
| M5@M15 | 37% | 36% | 26% | 0% |
| M5@H1 | 35% | 38% | 27% | 0% |
| M1@M15 | 39% | 37% | 23% | 0% |
| M1@M5 | 40% | 36% | 24% | 0% |

**Critical insight: bias alignment direction FLIPS between LTF and HTF pairs:**
- **LTF pairs (M1@M5, M1@M15, M5@M15)**: with-daily > against-daily (37-40% vs 36-37%)
- **HTF pairs (H1@H4, M15@H4, H1@D1)**: against-daily > with-daily (41-43% vs 27-33%)

This makes structural sense: on higher TFs, price pulls back to zones more during counter-trend moves (retracements are larger), while on lower TFs, trend-aligned zone retests are slightly more common (micro-pullbacks within the trend).

**H1@H4 and H1@D1 have the highest at-transition %** (2-3%) — H1 bars are long enough to catch daily bias transitions, making these pairs best for transition-based entries.

### Break-Through Rate by TF Pair

| TF Pair | Break-Throughs | Rate | Interpretation |
|---------|:------------:|:----:|----------------|
| H1@D1 | 19 | 0.003% | D1 zones almost never break |
| M15@H4 | 59 | 0.009% | H4 zones extremely reliable |
| M5@H1 | 214 | 0.024% | H1 zones very reliable |
| M1@M5 | 1,400 | 0.064% | M5 zones less reliable (expected) |
| H1@H4 | 928 | 0.115% | H4 zones break more on H1 bars (wider bars) |
| M15@H1 | 1,238 | 0.126% | H1 zones break more on M15 bars |
| M5@M15 | 2,064 | 0.163% | M15 zones most fragile on M5 entry |

**Higher break rates on adjacent TF pairs** (H1@H4: 0.115%, M5@M15: 0.163%) vs skip-TF pairs (M15@H4: 0.009%, H1@D1: 0.003%). Adjacent-TF entry bars have enough price range to actually break through zones, while skip-TF entry bars are too small to push through the wider HTF zones. All rates remain well below 0.2%.

### High-Value Combinations: Wick Touch + With-Daily

| TF Pair | Total Wicks+WithDaily | Continuation | Pullback | Push | Reversal |
|---------|:--------:|:--------:|:--------:|:--------:|:--------:|
| M1@M5 | 129,098 | 93,224 | 33,126 | 2,513 | 235 |
| M5@M15 | 90,810 | 63,986 | 24,832 | 1,756 | 236 |
| M1@M15 | 70,275 | 51,797 | 16,296 | 1,940 | 242 |
| M15@H1 | 59,277 | 43,953 | 13,822 | 1,171 | 331 |
| H1@H4 | 39,134 | 29,213 | 9,048 | 379 | 494 |
| M5@H1 | 37,849 | 28,626 | 7,922 | 998 | 303 |
| M15@H4 | 20,060 | 15,253 | 3,671 | 606 | 530 |
| H1@D1 | 17,449 | 13,360 | 3,191 | 230 | 667 |

**All pairs have ample high-value events.** Even the smallest cell (H1@D1 push+with-daily = 230) exceeds the analysis threshold. The sweep engine will have strong statistical power across all TF pairs.

**Reversal zones at H1@D1 (667) and M15@H4 (530)** — these are the most "meaningful" reversals (against HTF structure + with daily bias). Worth tracking separately in the sweep.

### Deep Pairs: Wick + With-Daily by Age Bucket

| TF Pair | Fresh | Young | Mature | Old |
|---------|------:|------:|------:|----:|
| H1@D1 | 10,209 | 4,359 | 1,790 | 1,091 |
| H1@H4 | 14,501 | 17,922 | 3,865 | 2,846 |
| M15@H4 | 8,285 | 9,019 | 1,756 | 1,000 |

**H1@H4 young > fresh** (17,922 vs 14,501) — H4 zones take longer to establish, so the "sweet spot" for with-daily wick retests is young (11-50 bars), not fresh. This differs from the M5@H1 finding where fresh dominated. Level 4 age filters should be TF-pair-specific.

---

## Cross-Level Insights <a id="cross-level-insights"></a>

### 1. Zones Are Very Reliable

Level 1 shows zones survive 50-200+ retests at H1-H4. Level 3 confirms break-through rate is <0.03%. Combined: **the retest-entry approach has a strong statistical foundation.** The question isn't whether zones hold, but how to pick the best retests.

### 2. Wick Touch is the Signal, Body Close is Noise

75% of zone interactions are body closes (bar closes inside zone). Only 12% are wick touches (clean rejection). Level 4 must **filter for wick touches only** as entry signals. Body closes are deep penetrations and not entry-quality interactions.

### 3. Fresh Continuation + With-Daily is the Sweet Spot

The single largest high-value opportunity bucket is fresh continuation zones retested with daily bias alignment (15,422 wick touches across 5 symbols). This should be the "core" Level 4 entry signal.

### 4. First-Touch Events Are Near-Misses, Not Entries

97.9% of first-touch events are near-misses. True first retests are recorded at `test_count=1`. Level 4 should use `test_count >= 1` as a minimum filter, with `test_count == 1` as a "fresh retest" signal.

### 5. XAUUSD Shows How Trend Distorts Zone Dynamics

Gold's bull trend creates extreme supply/demand asymmetry: demand zones accumulate (21.9 avg alive at H1 vs 6.9 supply). Level 4 should factor in per-symbol trend character — for trending instruments, **only with-trend zone retests** (demand in bull market, supply in bear) should be considered high-confidence.

### 6. Compression-Born Zones Are Most Durable

Zones created during LH_HL compression survive longest (85-89 H1 retests). Level 4 should consider birth period pattern as a quality indicator — compression-born zones may represent stronger structural levels.

### 7. Bias Transitions Are Potential Entry Windows

With ~280 transitions per symbol over 21 months (roughly every 37 hours), transition events are frequent enough to be actionable. A bias transition from bearish to bullish while price is near a demand zone could be a high-conviction entry signal.

### 8. Weekly Zone Confluence is Common

Price spends 33-45% of time inside weekly zones. This is high enough that "inside_w_zone" should be a valid Level 4 filter — it applies to roughly 1/3 to 1/2 of all potential entries.

---

## Data Gaps and Known Issues <a id="data-gaps"></a>

### 1. ~~Only M5@H1 TF Pair Covered~~ RESOLVED

All 8 TF pairs now covered via `--all-tfs` runs (2026-04-03). Each entry TF loads its own full date range independently.

### 2. `birth_bias_d` Not Populated

All `birth_bias_d` values are "unknown". The Level 0 plan explicitly deferred this: *"Bias fields are populated later by Level 2 — for now they stay as 'unknown'."* The enrichment to set `birth_bias_d` at zone creation time was never wired up because Level 2 (bias computation) didn't exist when Level 0 was built.

**Action:** Wire up `birth_bias_d` enrichment in the push zone engine. During `_enrich_birth_metadata()`, compute the daily bias from the D1 tick state's period pattern and set it on the new zone. This is a small Level 0 enhancement that unlocks "birth bias vs current bias" analysis.

### 3. `birth_bias_w` Not Populated

Same as above — weekly context at zone creation is never set.

### 4. Zone Audit CSV Missing Some Fields

The zone audit CSV has `birth_period_pattern` and `birth_price_distance` but not `birth_bias_d` or `birth_bias_w` (due to Gap #2).

### 5. No Per-Zone Win/Loss Tracking Yet

Levels 1-3 count opportunities but don't track outcomes (did price reverse after the retest?). This is by design — Level 4 adds the strategy layer that defines entries and exits. Win/loss analysis requires Level 4 trade simulation.

---

## Level 4 Design Implications <a id="level-4-implications"></a>

Based on the data analysis above, the following recommendations should guide Level 4 strategy design:

### Entry Signal Definition
1. **Filter for `touch_type == "wick_touch"` only** — 75% body-close noise must be excluded
2. **Require `test_count >= 1`** — first-touch events are near-misses, not entries
3. **Prefer `test_count == 1` or `test_count == 2`** as "fresh retest" (untested further analysis once outcomes are tracked)

### Bias Filters
4. **Require `bias_alignment == "with_daily"`** as primary filter — these are trend-aligned retests
5. **Require `bias_strength >= 2`** — avg strength for high-value combos is 2.2; strength 1 is weak signal
6. **Consider `at_transition` as a separate signal class** — bias transitions near zones could be high-conviction

### Zone Quality Filters
7. **Prefer `age_bucket` in {"fresh", "young"}** — 69% of events, declining quality with age
8. **Prefer `zone_role` in {"continuation", "push"}** — continuation is the core signal; push zones never break through
9. **Consider `birth_period_pattern`** — compression-born zones (LH_HL) are most durable
10. **Consider `replacement_count <= 3`** — original and lightly-replaced zones are 68% of events

### Instrument-Specific Considerations
11. **For trending instruments (XAUUSD):** Only with-trend retests are high-confidence. Demand-in-bull, supply-in-bear.
12. **Supply/demand asymmetry matters:** Demand zones have slightly higher wick rate and lower break-through rate across all symbols.

### Cascade Logic
13. **HTF zones are most valuable as context** — H4/D1 zones survive hundreds of retests, providing reliable structural levels
14. **Weekly zone confluence (33-45% of time)** — `inside_w_zone` is a common and meaningful filter
15. **Near-miss/wick ratio is highest for pullback zones (1.13)** — price "respects" pullback zones from further away; consider wider entry zones

### Trendline Integration (Level 4+)
16. **Trendline break while pushing from a zone adds confluence** — noted from user's Pine indicator `iora_pivot_hl_trendlines.pine`
17. **Multi-TF trendline breaks** (e.g., H1 descending TL break + H1 zone retest) should be tested as additional cascade filter

### TF Pair Selection and Prioritization (from All-TFs Analysis)
18. **Start sweep with H1@H4** — deepest data (16.5 yrs), 146k wick touches, most balanced age distribution, 3% transition rate
19. **M15@H4 second** — 4.4 yrs depth, H4 zones are structural and rarely break (0.009%), strong skip-TF filtering
20. **M15@H1 and M5@H1 next** — intraday pairs with excellent wick counts; M15@H1 has the highest wick % (17.9%) despite being 3-step gap
21. **Defer M1 pairs** — only 0.7 yrs of data; insufficient for multi-regime validation; add when more M1 data accumulates
22. **Adjacent-TF pairs need tighter filters** — higher break-through rates (0.1-0.16%) and more noise; skip-TF pairs (M15@H4, H1@D1) are inherently cleaner

### TF-Pair-Specific Parameter Adjustments (from All-TFs Analysis)
23. **Age bucket preference varies by pair** — H1@H4 peaks at "young" not "fresh"; Level 4 age filters must be TF-pair-configurable
24. **Bias alignment direction flips** — LTF pairs favor with-daily, HTF pairs favor against-daily in raw counts; the sweep must test both directions per pair
25. **Wick % correlates with zone-width-to-bar-size ratio** — not just TF distance; this may inform dynamic zone sizing in Level 4
26. **Reversal zone signals at HTF pairs** — H1@D1 and M15@H4 have disproportionately more reversal wick touches with daily bias; these are rare (230-667 per pair) but potentially highest conviction
