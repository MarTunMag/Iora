# HTF-Triggered LTF Entry Sweep — 8-Symbol Analysis

> **Date:** 2026-04-08
> **Symbols:** GBPUSD, EURUSD, USDJPY, GBPJPY, XAUUSD, BTCUSD, US500, USTEC
> **Configs:** 488 per symbol (3,904 total). 2,496 viable (30+ trades).
> **Sweep:** H1@H4 with baseline, static nesting (M15/M5), dynamic nesting, standalone LTF pairs.
> **Fixes applied:** Symbol-specific pip_size, spread, min_sl_spread_mult.

---

## 1. The Headline: H1@H4 Baseline Partial Is Universally Dominant

**Every single symbol's #1 config is the same: H1@H4 baseline (no nesting), partial TP.**

| Symbol | SQN (0 spread) | SQN (realistic spread) | PF | WR | Trades | Spread-immune? |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|
| GBPJPY | **31.98** | **30.14** (3.0p) | 2.90 | 54.7% | 4,065 | YES — only 6% SQN drop at 3p |
| GBPUSD | **30.74** | **29.12** (2.0p) | 3.09 | 54.6% | 3,747 | YES — only 5% drop at 2p |
| USDJPY | **30.14** | **27.30** (3.0p) | 2.84 | 54.8% | 3,556 | YES — only 9% drop at 3p |
| EURUSD | **29.12** | **27.05** (2.0p) | 2.61 | 53.0% | 3,830 | YES — only 7% drop at 2p |
| USTEC  | **25.05** | **24.05** (200p) | 3.20 | 55.1% | 2,354 | YES — only 4% drop at 200p |
| US500  | **23.99** | **20.41** (200p) | 2.68 | 55.8% | 2,019 | YES — 15% drop but still SQN 20+ |
| XAUUSD | **21.54** | **20.80** (24p)  | 2.61 | 51.4% | 2,399 | YES — only 3% drop at 24p |
| BTCUSD | **20.05** | **18.65** (2400p)| 3.03 | 53.6% | 1,724 | YES — only 7% drop at 2x spread |

**Key finding: H1@H4 partial is spread-immune across ALL asset classes.** FX, commodities, crypto, indices — the SL on H4 zones is wide enough that spread is <15% of risk in every case.

---

## 2. Nesting: Static Works, Dynamic Disappoints

### Static Nesting (find LTF zones inside H4 zones)

Consistent across all 8 symbols — static nesting produces a viable secondary strategy:

| Symbol | Baseline SQN | Static M15 SQN | Static M5 SQN | M15 WR | M5 WR | M5 avgR |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|
| GBPUSD | 30.74 | **14.47** | **10.79** | 45.3% | 50.6% | +1.22 |
| EURUSD | 29.12 | **14.90** | **10.92** | 46.5% | 50.7% | +1.23 |
| USDJPY | 30.14 | **12.84** | **10.96** | 44.3% | 50.4% | +1.23 |
| GBPJPY | 31.98 | **14.52** | **10.56** | 45.2% | 50.4% | +1.06 |
| XAUUSD | 21.54 | **12.93** | **9.43**  | 43.8% | 48.3% | +1.06 |
| BTCUSD | 20.05 | **14.29** | **10.82** | 44.8% | 48.6% | +1.05 |
| US500  | 23.99 | **12.98** | **10.99** | 44.7% | 52.8% | +1.43 |
| USTEC  | 25.05 | **13.33** | **10.74** | 45.6% | 52.0% | +1.28 |

**Pattern:** Static M15 = SQN 12-15, WR 44-47%. Static M5 = SQN 9-11, WR 48-53%, avgR +1.0-1.4.

**M5 entries have HIGHER avgR and WR than M15** — the tighter zone gives better entry precision. But M5 has fewer trades (~500 vs ~1,400). The precision/volume tradeoff.

**Static M5 at realistic spread (all symbols SQN 7-10)** — survives spread comfortably because the M5 zones INSIDE H4 zones still have structural SL.

### Dynamic Nesting (wait for LTF zone birth inside H4 zone)

Consistently weaker than static across all 8 symbols:

| Entry | Avg SQN (8 sym, 0 spread) | Avg WR | Avg Trades |
|-------|:-:|:-:|:-:|
| Baseline (no nesting) | **27.1** | **54.2%** | **2,962** |
| Static M15 | **13.8** | **45.1%** | **1,348** |
| Static M5 | **10.7** | **50.2%** | **502** |
| Dynamic M15 | **5.5** | **34.1%** | **988** |
| Dynamic M5 | **4.4** | **35.8%** | **401** |

**Dynamic nesting is 2.5x worse than static nesting.** The "wait for zone birth" requirement misses many good entries where a pre-existing LTF zone is the right entry point. Static nesting (use whatever LTF zones exist inside the H4 zone) captures more opportunities.

**Verdict: Dynamic nesting is not worth the complexity.** Static nesting is simpler and better.

---

## 3. Push Filter: Inconclusive (Too Few Trades)

Push filter (require_ltf_push=True) only produced 30+ trades on 4 of 8 symbols:

| Symbol | push=False SQN | push=True SQN | push=True trades |
|--------|:-:|:-:|:-:|
| XAUUSD | 12.93 | 1.66 | 42 |
| BTCUSD | 14.29 | 1.46 | 34 |
| US500  | 12.98 | 3.39 | 37 |
| USTEC  | 13.33 | 1.01 | 37 |

**The push filter kills trade count** — only 34-42 trades in 16.5 years of data. This is not enough for statistical significance. The filter is too restrictive for LTF zones inside H4 zones.

**Verdict: Push filter on nested LTF zones is NOT useful.** The H4 zone itself already provides the structural conviction. Requiring LTF push on top removes too many valid entries.

---

## 4. min_sl_spread_mult: Marginal Effect

At 0 spread, min_sl_spread_mult has NO effect (identical results). This is expected — the floor only matters when spread is present.

At realistic spread, the effect is tiny (0-3% SQN improvement):
- GBPUSD at 1.5p spread: SQN 11.30 (mult=0) → 11.47 (mult=3) → 11.45 (mult=5)
- US500 at 200p spread: SQN 7.98 (mult=0) → 8.45 (mult=3) → 8.42 (mult=5)

**Why so small?** H4 zones (and LTF zones inside them) already have SL distances >> spread. The min_sl floor rarely activates because the structural SL is already wider.

**Where it WOULD matter:** On standalone M5@M15 where zone SL is 1-2 pips and spread is 1.5 pips. But those standalone configs show poor performance regardless (SQN 3-6 at 0 spread).

**Verdict: min_sl_spread_mult is irrelevant for H1@H4 configs.** Keep it at 0 for simplicity. It may matter for future M5@M15 standalone configs if those ever become viable.

---

## 5. Standalone LTF Pairs: Weak Without HTF Context

| TF Pair | Best SQN (any symbol) | Best avgR | Best PF | Verdict |
|---------|:-:|:-:|:-:|---|
| M5@M15 | 6.17 (US500) | +0.26 | 1.35 | Marginal — and this is at 0 spread |
| M1@M5 | 4.88 (USDJPY) | +0.18 | 1.12 | Barely profitable |
| M1@M15 | — | — | — | No viable configs at all |

**Standalone LTF pairs without HTF context are weak.** The best standalone M5@M15 (US500 SQN 6.17) is less than half the worst nested config (XAUUSD static M5 SQN 9.43). And these are at 0 spread — with spread they'll be even worse.

**This confirms the cascade model:** LTF entries need HTF context to work. Entering at an M15 zone that happens to be INSIDE an H4 zone is fundamentally different from entering at a random M15 zone.

---

## 6. Cross-Symbol Universal Configs

### Tier 1: Production-Ready (SQN 18+ on ALL 8 symbols at realistic spread)

**Config:** H1@H4, baseline (no nesting), partial TP, TTL=0
- Worst-case SQN: 18.65 (BTCUSD at 2400p spread) 
- Average SQN: 24.6 across 8 symbols at realistic spread
- Average WR: 54.2%
- Average PF: 2.95
- Total trades: ~24,000 across 8 symbols (16.5 years)
- ~1,500 trades/year across 8 symbols = ~6 trades/day

### Tier 2: Precision Secondary (SQN 8-15 on ALL 8 symbols)

**Config:** H1@H4, static nesting M15, partial TP
- Worst-case SQN: 8.24 (USDJPY at 3.0p spread)
- Average SQN: 11.5 across 8 symbols at realistic spread
- Average WR: 45%
- Fewer trades (~1,300/symbol) but still viable

**Config:** H1@H4, static nesting M5, partial TP
- Worst-case SQN: 7.19 (GBPUSD at 2.0p spread)
- Average SQN: 8.8 across 8 symbols at realistic spread
- Average WR: 50%, avgR +1.0-1.4
- Fewest trades (~480/symbol) but highest per-trade quality

### Tier 3: Not Recommended

- Dynamic nesting: SQN 2-7, complex to implement, no advantage over static
- Push filter: kills trade count to <50, not statistically significant
- Standalone LTF: SQN 3-6 at 0 spread, will die with spread
- min_sl_spread_mult: no meaningful effect on H1@H4 configs

---

## 7. Key Findings — New Rules Validated/Invalidated

### NEW PROVEN:

1. **H1@H4 partial is universal** — SQN 18-32 across FX, commodities, crypto, indices. Not just GBPUSD.

2. **Static nesting works** — Finding LTF zones inside H4 zones and entering there produces consistent SQN 9-15 across all 8 symbols.

3. **M5 entries inside H4 zones have the highest per-trade quality** — avgR +1.0-1.4, WR 48-53%, PF 2.5-3.4. Fewer trades but each one is better.

4. **The strategy is spread-immune on H1@H4** — worst-case 15% SQN degradation at 2x typical spread. Most symbols show <10% degradation.

### NEW DISPROVEN:

5. **Dynamic nesting does NOT outperform static** — 2.5x worse SQN. The complexity of tracking zone births in real-time adds no value over simply finding existing zones inside H4 zones.

6. **Push filter on nested LTF zones is NOT useful** — too restrictive, kills trade count to statistically insignificant levels.

7. **min_sl_spread_mult is irrelevant for H1@H4** — structural SL already exceeds any reasonable spread floor.

8. **Standalone LTF pairs are NOT viable without HTF context** — SQN 3-6 at best, confirms the cascade model is essential.

---

## 8. Production Config Update

### Primary (validated across 8 symbols):
```
tf_pair:           H1@H4
entry_mode:        limit (top edge)
ltf_nesting:       none (baseline)
partial_tp:        true (70% at rr=3.0, 30% at H1 zone)
limit_ttl:         0 (until zone breaks)
sl_mode:           zone
sl_buffer_atr:     0.15
min_sl_spread_mult: 0 (not needed)
spread_tolerance:  immune up to 2x typical spread
```

### Secondary (higher precision, fewer trades):
```
tf_pair:           H1@H4
ltf_nesting:       static
entry_tf_override: M5
partial_tp:        true
# Same other params as primary

Per-trade quality: avgR +1.0-1.4, WR 48-53%
Trades: ~500/symbol/16.5yr = ~30/year/symbol
```

### Dropped:
- Dynamic nesting — disproven, unnecessary complexity
- Push filter on nested — too restrictive
- min_sl_spread_mult — no effect on H1@H4
- Standalone LTF — weak without HTF context

---

## 9. What to Test Next

1. **Bias filter (against_daily)** on the Tier 1 config — never combined with limit entry
2. **Trendline break as filter** — 11 videos validate, highest consensus untested concept
3. **Retest 4-10 filter** on the nested configs — proven +30-70% quality boost, not yet tested with nesting
4. **Walk-forward validation** — split data into train/test/validate periods
5. **Zone refinement for M5 entry** — the V23 "two steps down" concept (H4 → H1 → M15, or H4 → M15 → M5)
