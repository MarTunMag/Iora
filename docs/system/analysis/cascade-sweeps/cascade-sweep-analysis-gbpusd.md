# GBPUSD Cascade Sweep Analysis — v2 (with TL fix + CHoCH conviction + consumption)

**Date:** 2026-04-08
**Symbol:** GBPUSD, H1@H4, 102,517 H1 bars (~16.5 years)
**Configs:** 95 (v1 had 74)
**Viable (30+ trades):** 68 of 88 rows

---

## Critical Bug Fix This Run

**Push trendline pivot detection was broken in v1.** The code used `len(prev_highs) > prev_count` to detect new pivots, but `PeriodTracker.prev_highs` caps at `history_depth=3`. After 3 period closes, new pivots never registered.

| Metric | v1 (broken) | v2 (fixed) |
|--------|------------|------------|
| TL break events total | 4 | 67,428 |
| h4_correction_tl_break bars | 16 (0.0%) | 34,754 (33.9%) |
| h1_terminal bars | 0 | 1,208 (1.2%) |
| at_reversal_target bars | 0 | 17 |
| H1 impulse TL broken bars | 0 | 39,946 (39.0%) |

**All v1 results for TL break / terminal / reversal target were invalid.** v2 is the first valid cascade sweep.

---

## 1. Phase Distribution (What the Cascade Engine Sees)

| Phase | Bars | % | Description |
|-------|------|---|-------------|
| d1_push | 59,179 | 57.7% | D1 and H4 aligned |
| h4_correction_tl_break | 34,754 | 33.9% | H4 correcting, correction TL broke |
| h4_correction | 6,233 | 6.1% | H4 correcting, TL intact |
| h1_extended | 2,337 | 2.3% | 5+ H1 zones in push direction |
| h1_terminal | 1,208 | 1.2% | H1 impulse TL broke + 5+ zones |
| at_reversal_target | 17 | 0.0% | Price near CHoCH-causing zone |

---

## 2. Cascade Phase Filter — Does It Help?

| Phase | Trades | WR | PF | avgR | SQN |
|-------|--------|----|----|------|-----|
| any (baseline) | 2,968 | 52.2% | 2.97 | +0.94 | 18.19 |
| d1_push | 2,362 | 52.7% | 3.06 | +0.96 | 16.40 |
| **h4_correction** | **457** | **54.0%** | **4.30** | **+1.45** | **8.13** |
| h4_correction_tl_break | 1,779 | 51.8% | 3.07 | +1.00 | 14.44 |
| h1_extended | 37 | 51.4% | 2.65 | +0.73 | 1.87 |
| **h1_terminal** | **41** | **51.2%** | **3.85** | **+1.62** | **2.51** |

**YES.** `h4_correction` has PF 4.30 (+45% over baseline) with 457 trades. `h1_terminal` has PF 3.85 with avgR +1.62 but only 41 trades.

### h4_correction + bias combinations

| Bias | Trades | WR | PF | avgR | SQN |
|------|--------|----|----|------|-----|
| any | 457 | 54.0% | 4.30 | +1.45 | 8.13 |
| against_daily | **199** | **60.8%** | **5.46** | **+1.76** | **6.73** |
| with_daily | 143 | 56.6% | **6.01** | **+2.01** | 5.55 |

**h4_correction + with_daily = PF 6.01, avgR +2.01** (best per-trade in entire sweep).
**h4_correction + against_daily = PF 5.46, WR 60.8%** (best win rate).

Both are excellent. Counter-intuitively, BOTH bias directions improve during H4 corrections.

---

## 3. CHoCH Conviction Filter — Does It Help?

| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| any (baseline) | 2,968 | 52.2% | 2.97 | +0.94 |
| strong_only | 2,684 | 51.8% | 2.95 | +0.93 |
| weak_only | 2,471 | 51.8% | 2.99 | +0.94 |

**NO significant impact at this level.** Strong vs weak CHoCH conviction doesn't discriminate well for H1@H4 entries. Both capture ~85-90% of trades with nearly identical metrics.

With against_daily bias:
| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| any | 1,699 | 54.6% | 3.37 | +1.07 |
| strong_only | 1,526 | 54.6% | 3.43 | +1.07 |
| weak_only | 1,380 | 55.0% | 3.48 | +1.11 |

Weak_only actually edges out slightly. This suggests the "don't enter on weak CHoCH" rule doesn't apply to zone retests — the zone is the entry signal, not the CHoCH itself.

**Special case: h1_terminal + strong_only** = 32 trades, PF 4.08, avgR +1.83 (vs 41/3.85/+1.62 with any). CHoCH conviction helps in terminal phases.

---

## 4. Consumption Count — Does It Help?

| min_mc | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| 0 (any) | 2,968 | 52.2% | 2.97 | +0.94 |
| 1 | 2,628 | 51.7% | 2.97 | +0.93 |
| 2 | 2,628 | 51.7% | 2.97 | +0.93 |
| 3 | 2,628 | 51.7% | 2.97 | +0.93 |

**NO impact.** min_mc=1/2/3 all produce identical results. This confirms the debug finding: at H1 entry resolution, child TFs flip from 0→3 simultaneously. Consumption count needs M5/M15 entry TF to discriminate.

---

## 5. TL Break Filter — Does It Help?

| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| any (baseline) | 2,968 | 52.2% | 2.97 | +0.94 |
| after_impulse_break | 2,364 | 52.3% | 3.06 | +0.98 |
| after_correction_break | 2,795 | 52.0% | 3.01 | +0.96 |

**Marginal.** `after_impulse_break` slightly improves PF (3.06 vs 2.97) by filtering out 600 trades. The TL break state captures most of the market (80-94% of trades pass), so it's not a strong discriminator alone.

With against_daily bias:
| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| after_impulse + against | 1,394 | 55.2% | 3.49 | +1.11 |
| after_correction + against | 1,626 | 54.9% | 3.45 | +1.09 |

Both improve slightly over `any + against` (3.37). Impulse break + against_daily = best combo.

---

## 6. EW Filters — Do They Help?

### Extension filter
| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| any | 2,968 | 52.2% | 2.97 | +0.94 |
| not_extended | 2,773 | 52.4% | 3.02 | +0.95 |
| extended | 370 | 50.5% | 3.27 | +1.13 |

`extended` has higher avgR (+1.13) but lower WR. `not_extended + against_daily` = PF 3.56, WR 55.7%.
`extended + with_daily` = PF 6.31, avgR +1.98, 94 trades (best PF in entire sweep!).

### Overlap filter
| Filter | Trades | WR | PF | avgR |
|--------|--------|----|----|------|
| no_overlap | 2,943 | 52.1% | 2.95 | +0.93 |
| overlap_only | 53 | 52.8% | 4.97 | +1.99 |

`overlap_only` has PF 4.97 but only 53 trades. EW overlap detection works but fires too rarely.

---

## 7. Best Combined Configs

### By Profit Factor (30+ trades)
| # | Config | Trades | WR | PF | avgR |
|---|--------|--------|----|----|------|
| 1 | extended + with_daily | 94 | 59.6% | **6.31** | +1.98 |
| 2 | h4_correction + with_daily | 143 | 56.6% | **6.01** | +2.01 |
| 3 | h4_correction + against_daily | 199 | **60.8%** | **5.46** | +1.76 |
| 4 | h4_correction (any bias) | 457 | 54.0% | 4.30 | +1.45 |
| 5 | h1_terminal + strong_choch | 32 | 50.0% | 4.08 | +1.83 |
| 6 | h1_terminal (any) | 41 | 51.2% | 3.85 | +1.62 |

### Production Candidate
**h4_correction + against_daily**: PF 5.46, WR 60.8%, 199 trades (12/year), avgR +1.76

This means: Enter H4 zones in counter-trend during H4 pullbacks against D1, with against-daily bias. The pullback creates a zone retest opportunity at better prices, and the D1 trend resumes.

### High-Volume Production Candidate
**h4_correction_tl_break + against_daily**: PF 3.42, WR 54.1%, 973 trades (59/year), avgR +1.12

More trades per year with solid metrics. The correction TL breaking means the H4 pullback is ending.

---

## 8. What Needs More Work

1. **Consumption count**: Binary at H1 entry. Needs M15/M5 entry TF to be useful.
2. **CHoCH conviction**: Doesn't discriminate for zone retests (the entry is the zone, not the CHoCH). Only useful in h1_terminal phase.
3. **Reversal target**: Only 18 trades — zone attribution captures too few zones. The CHoCH-causing zone often gets broken before retest.
4. **at_reversal_target phase**: Only 17 bars — too rare. The zone proximity + terminal requirement is too strict.

---

## 9. Key Findings vs v1

| Finding | v1 (broken TL) | v2 (fixed) |
|---------|----------------|------------|
| h4_correction + against_daily | PF 3.66, 1,071 trades | **PF 5.46, 199 trades** |
| h4_correction + with_daily | PF 3.56, 742 trades | **PF 6.01, 143 trades** |
| h4_correction (any) | PF 3.20, 1,958 trades | **PF 4.30, 457 trades** |
| h1_terminal | 0 trades | **41 trades, PF 3.85** |
| TL break filter viable | No (3 trades) | **Yes (2,364 trades)** |

The TL fix dramatically changed the phase distribution. With correct trendlines:
- `h4_correction` now means "H4 correcting with correction TL still intact" (true pullback)
- `h4_correction_tl_break` captures the bulk of the old `h4_correction` trades
- The true pullback (`h4_correction`) has exceptional quality (PF 4.3-6.0)
