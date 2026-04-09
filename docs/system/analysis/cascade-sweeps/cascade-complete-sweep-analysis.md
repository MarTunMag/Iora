# Cascade Complete Sweep Analysis — GBPUSD + EURUSD

> **Date:** 2026-04-09
> **Sweep versions:** Phase 1 (101 configs) + Phase 4 V2 (130 configs per symbol)
> **Symbols:** GBPUSD, EURUSD
> **Engine:** Trendline detection, cascade state, FVG, breaker zones, structural FVG, conviction, consumption

---

## 1. Cross-Symbol Consistency Check

**The critical test: does each filter show the SAME direction on both symbols?**

| Filter | GBPUSD Direction | EURUSD Direction | Consistent? |
|---|---|---|---|
| h4_correction phase | PF 4.06 (best phase) | PF 3.10 (best phase) | **YES** |
| against_daily bias | PF 3.37 (+0.40 over any) | PF 2.75 (-0.01 over any) | **MIXED** — helps GBPUSD a lot, neutral on EURUSD |
| with_daily bias | PF 3.04 (+0.07) | PF 3.13 (+0.37) | **MIXED** — helps EURUSD more |
| h4_correction + against_daily | PF 5.40 (best combo) | PF 2.68 (below baseline!) | **NO** — GBPUSD-specific |
| h4_correction + with_daily | PF 5.09 | PF 2.69 | **NO** — GBPUSD-specific |
| Candle FVG at entry | Slightly worse (-0.14 PF) | Slightly worse (-0.11 PF) | **YES** (both negative) |
| Pivot cascade depth>=4 | PF 3.08 (+0.11) | PF 2.95 (+0.19) | **YES** (marginal positive) |
| Breaker zone | PF 2.99 (+0.02) | PF 2.77 (+0.01) | **YES** (no effect) |
| Structural FVG inside_gap | PF 3.28 (+0.31) | PF 2.84 (+0.08) | **YES** (mild positive) |

### Verdict on Cross-Symbol Consistency

**Universally consistent (same on both symbols):**
- h4_correction is the best cascade phase on BOTH symbols
- Candle FVG at entry does NOT help (slightly negative on both)
- Breaker zone filter has NO effect
- Pivot cascade depth marginally positive on both
- Structural FVG inside_gap mildly positive on both

**NOT consistent (symbol-specific):**
- against_daily bias: strong on GBPUSD (+0.40 PF), neutral on EURUSD
- h4_correction + bias: extraordinary on GBPUSD (PF 5.40), poor on EURUSD (PF 2.68)

**This means h4_correction is a REAL signal. The bias direction effect is symbol-specific.**

---

## 2. Dimension-by-Dimension Verdict

### PROVEN (data confirms, cross-symbol consistent):

| # | Dimension | Value | Cross-Symbol Evidence |
|---|---|---|---|
| 1 | **h4_correction phase** | PF 3.1-4.1 | Best phase on both symbols. Trades during H4 pullback with correction TL intact. |
| 2 | **TL break detection (fixed)** | 2,364-2,851 trades | Was 2 trades before fix. Now meaningful filter. Correction break slightly outperforms impulse. |
| 3 | **h1_terminal phase** | PF 2.6-2.9, ~500 trades | Now fires (was 0). Moderate quality at terminal push exhaustion. |

### MARGINALLY POSITIVE (small improvement, consistent):

| # | Dimension | Value | Evidence |
|---|---|---|---|
| 4 | **Pivot cascade depth>=4** | PF +0.1-0.2 | 4+ TFs confirming same direction. Small but consistent improvement. |
| 5 | **Structural FVG inside_gap** | PF +0.1-0.3 | Entering inside unfilled structural gap. Mildly positive on both symbols. |
| 6 | **EW not_extended** | PF +0.05 | Filtering out extended wave 3 moves. Very marginal. |

### NOT USEFUL (no effect or negative):

| # | Dimension | Value | Evidence |
|---|---|---|---|
| 7 | **Candle FVG at entry** | PF -0.1 | Slightly WORSE on both symbols. Candle FVGs don't predict zone quality. |
| 8 | **Breaker zone filter** | PF +0.02 | Zero effect. Nearly all zones are near breakers (too common to filter). |
| 9 | **CHoCH conviction** | PF 0.00 | No difference between strong_only and weak_only at H1 resolution. |
| 10 | **Momentum consumption** | PF 0.00 | Binary at H1 resolution (jumps from 0 to 3). |
| 11 | **TL break lookback** | PF 0.00 | All lookback values identical (sticky flag already captures it). |
| 12 | **EW overlap filter** | Inconclusive | overlap_only: 53 trades (too few). no_overlap marginally positive. |

### SYMBOL-SPECIFIC (not universal):

| # | Dimension | GBPUSD | EURUSD |
|---|---|---|---|
| 13 | **against_daily bias** | PF +0.40, WR +2.4% | PF -0.01, WR -0.2% |
| 14 | **h4_correction + against_daily** | PF 5.40, WR 60.0% | PF 2.68, WR 48.9% |
| 15 | **h4_correction + with_daily** | PF 5.09, WR 51.3% | PF 2.69, WR 52.1% |

---

## 3. M1@M5 Investigation

**M1@M5 produced negative SQN on both symbols:**

| Symbol | Trades | WR | PF | SQN | avgR |
|---|---|---|---|---|---|
| GBPUSD | 2,671 | 31.5% | 0.92 | -2.01 | -0.054 |
| EURUSD | 2,193 | 30.6% | 0.88 | -2.72 | -0.080 |

**NOTE:** avg_winner_r and avg_loser_r are ALL ZERO across the entire sweep. This is a metric computation bug — the cascade sweep runner uses `avg_winner_r` but `compute_metrics()` outputs `avg_win_r`. Also `max_drawdown_r` should be `max_dd_r`. These 3 metrics are being lost. Fix needed in `run_cascade_sweep.py` line 240-242.

**Why M1@M5 shows negative SQN — possible causes:**
1. **Spread is baked into the entry** — at M5 zone resolution, the zone width may be smaller than spread
2. **The partial TP R:R calculation uses the spread-shifted entry** — risk appears larger than actual
3. **M1 zones inside M5 zones may be too noisy** — the nesting picks up zones that aren't structurally meaningful
4. **The cascade filters (phase, TL break) are calibrated for H1@H4, not M1@M5** — the phase classification may not translate

**This needs deeper investigation:** Run a diagnostic on M1@M5 specifically — what's the average SL distance in pips? If SL is <2 pips on GBPUSD, spread alone kills it (same M5@M15 problem from the original audit).

---

## 4. Metric Key Bug — Must Fix

The cascade sweep runner has key mismatches with `compute_metrics()`:

| Runner uses | compute_metrics outputs | Status |
|---|---|---|
| `max_drawdown_r` | `max_dd_r` | ALL ZEROS — broken |
| `avg_winner_r` | `avg_win_r` | ALL ZEROS — broken |
| `avg_loser_r` | `avg_loss_r` | ALL ZEROS — broken |

**Fix in `scripts/run_cascade_sweep.py` line 240-242:**
```python
"max_drawdown_r": m.get("max_dd_r", 0),    # was max_drawdown_r
"avg_winner_r": m.get("avg_win_r", 0),      # was avg_winner_r  
"avg_loser_r": m.get("avg_loss_r", 0),      # was avg_loser_r
```

After fixing, re-run at least GBPUSD to get maxDD, avg winner/loser for full analysis.

---

## 5. Production Config Tiers (Updated)

### Tier 1: High Volume Production (universal, 8 symbols)

```
H1@H4 baseline, partial TP, no cascade filters
SQN: 17-18 | PF: 2.76-2.97 | WR: 50.6-52.2%
Trades: ~2,800-3,000/symbol/16.5yr
~170-180 trades/year/symbol = ~1,400/year across 8 symbols
```

### Tier 2: Quality Filter (universal, tested on 2 symbols)

```
H1@H4, cascade_phase = h4_correction, no bias filter
SQN: 6.8-7.0 | PF: 3.10-4.06 | WR: 52.0-53.9%
Trades: 330-370/symbol/16.5yr
~20-22 trades/year/symbol = ~170/year across 8 symbols
```

### Tier 3: GBPUSD-Specific High Quality

```
H1@H4, cascade_phase = h4_correction, bias = against_daily
PF: 5.40 | WR: 60.0% | avgR: +1.80
165 trades/16.5yr = ~10/year
DO NOT use on EURUSD (PF drops to 2.68)
```

### Dropped from Production:

- M1@M5 cascade: negative SQN on both symbols
- Candle FVG filter: slightly negative
- Breaker zone filter: no effect
- CHoCH conviction: no effect at H1 resolution
- Momentum consumption: no effect at H1 resolution

---

## 6. What To Test Next

| Priority | Test | Why |
|---|---|---|
| 1 | **Fix metric key bug + re-run GBPUSD** | Need maxDD, avg winner/loser for proper risk assessment |
| 2 | **Run 6 more symbols** (USDJPY, GBPJPY, XAUUSD, BTCUSD, US500, USTEC) | Validate h4_correction universality |
| 3 | **Investigate M1@M5 failure** — print avg SL pips | Is spread killing it, or is the model wrong? |
| 4 | **Test child_pivot SL mode** (Phase 5) | The fractal SL/TP model needs testing |
| 5 | **Walk-forward validation** | Split data to verify in-sample vs out-of-sample |
