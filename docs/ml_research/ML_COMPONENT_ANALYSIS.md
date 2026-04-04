# ML Component Analysis — Should Iora Add Machine Learning?

> **Purpose:** Research findings on whether to add ML to Iora's mechanical signal engine.
> **Date:** 2026-04-04 (updated with Level 4 sweep outcome data)
> **Status:** Research only — no code changes. ML is a Phase 2 optimization, not a Phase 1 necessity. The mechanical system has a validated edge (SQN 2.66 on GBPUSD H1@D1).
> **Context:** Iora's push zone engine produces fully mechanical, rule-based signals. The Level 4 expanded sweep (410 configs, 481k trades on GBPUSD alone, 16.5 years of H1 data) has validated a structural cascade model where D1 push zones establish bias and H4 counter-trend pullbacks provide entry zones. The mechanical system works without ML. This document evaluates whether and when ML would add value on top.
>
> **Empirical data sources:**
> - `docs/system/level1-3-data-analysis.md` — zone behavior (9M events, 8 TF pairs, 5 symbols)
> - `docs/system/level4-expanded-sweep-analysis.md` — trade outcomes (481k trades, 410 configs, GBPUSD)
> - `docs/system/level4-sweep-analysis.md` — initial 56-config sweep (5 symbols, 270k trades)

---

## 1. The Question

Iora's push zone engine produces entry signals through deterministic rules:
HA color-run transitions → push/reversal zone creation → boundary-break validation → BOS/CHoCH classification → nesting detection → entry signals.

The signal matrix backtester tests these signals across configurable dimensions:
- Nesting TF pairs (M1→M5, M5→M15, M15→H1, etc.)
- Signal types (push, reversal, terminal)
- Structure filters (BOS-only, CHoCH-only, any)
- HTF trend alignment
- SL/TP modes (zone-based, structure-based, fixed R:R)
- 38 symbols across forex, metals, crypto, indices, energy

Should any part of this pipeline include an ML component? If so, where, when, and how?

---

## 2. ML Approaches Evaluated

### 2.1 Meta-Labeling (Lopez de Prado)

**What it is:** A two-layer architecture from *Advances in Financial Machine Learning* (2018).

- **Layer 1 (Primary Model):** Your existing rule-based system generates directional signals (buy/sell). This is the push zone engine with its nesting-based entry models.
- **Layer 2 (Meta Model):** A secondary ML model learns WHEN the primary model's signals are worth taking. It outputs a probability (0.0–1.0) representing confidence that the primary signal will be profitable.

The meta-model does NOT predict direction. It only answers: *"Given that a demand push zone fired inside an M5 parent with BOS alignment, should we actually take this trade, and how much should we bet?"*

**How it improves precision without sacrificing recall:**
The mechanical system is designed for **high recall** — catch most real opportunities, even at the cost of false positives. The meta-model acts as a **precision filter**, learning which signals are actually profitable. The combined system achieves higher F1 than either alone.

**Relevance to Iora:** This is the most natural ML addition. The push zone engine stays exactly as designed. ML sits on top as a gatekeeper + position sizer.

---

### 2.2 Triple Barrier Method (Labeling)

**What it is:** Three barriers set around each trade entry:

| Barrier | Type | Description |
|---------|------|-------------|
| Upper | Profit-take | Price rises X ATRs above entry |
| Lower | Stop-loss | Price falls Y ATRs below entry |
| Vertical | Time expiry | N bars pass without hitting upper or lower |

Labels assigned by which barrier is hit first:
- **+1** if upper barrier hit first (profitable)
- **-1** if lower barrier hit first (losing)
- **0** if time barrier hit (inconclusive)

Barriers are set dynamically using volatility (ATR), not fixed pips.

**Extensions:**
- **Quadruple barrier:** Adding a trailing stop condition
- **Quintuple barrier:** Adding a trend filter or volatility regime gate
- These are practitioner extensions, not formal standards

**Relevance to Iora:** This is how you CREATE labeled datasets for training the meta-model. Every historical push zone signal gets labeled: did it hit TP, SL, or expire? The signal matrix backtester already produces this data — each trade has a known outcome, SL/TP mode, and full context snapshot.

---

### 2.3 Bar-by-Bar ML Classification

**What it is:** Train a classifier (Random Forest, XGBoost, LSTM) on per-bar features to predict next-bar direction or multi-bar outcome.

**Common models:**
- **Random Forest:** Robust baseline, handles noisy features, built-in feature importance. Good for meta-labeling.
- **XGBoost/LightGBM:** Generally best for tabular financial data. Fast, handles missing values. Favored in 2024-2025 research.
- **LSTM/GRU:** For sequence patterns. Higher overfitting risk, harder to interpret.
- **Transformers:** Emerging for financial time series. Very data-hungry. Research-grade, not production-ready for systematic trading.

**Relevance to Iora:** NOT recommended as a primary signal generator. HA run-transitions, push boundary-breaks, and BOS/CHoCH are deterministic — ML adds zero value to detecting them. But ML on top of zone context features (nesting depth, zone age, exhaustion count, trend alignment, period level proximity) could improve signal filtering.

---

### 2.4 Regime Detection

**What it is:** Classify market state into regimes (trending/ranging/volatile) using Hidden Markov Models (HMM) or clustering.

**Why it's compelling:**
- Well-established, interpretable
- Low overfitting risk (few parameters)
- 2024-2025 research shows HMM + ensemble methods improve risk-adjusted returns
- Practical outcome: when "ranging" detected → reduce position sizes or pause entries; when "trending" → be more aggressive

**Relevance to Iora:** The push zone engine already has regime-like signals — exhaustion counts indicate zone saturation, terminal zones flag opposing nesting, and HTF trend state from period tracking shows structural direction. An HMM on D/W data could provide an independent confirmation layer. This would be the FIRST ML addition if we go this route.

---

## 3. Where ML Could Sit in the Iora Pipeline

```
Push Zone Engine (MECHANICAL — no ML)
    │
    ├─ HA Computation ──────── NO ML (deterministic: open/close averaging)
    ├─ Run Transition ──────── NO ML (deterministic: color flip edge detection)
    ├─ Zone Creation ───────── NO ML (deterministic: ORIZ spec boundaries)
    ├─ Boundary-Break ──────── NO ML (deterministic: did run make new extreme?)
    ├─ Push/Reversal Tag ───── NO ML (deterministic: push base → reversal zone)
    ├─ Period Tracking ─────── NO ML (deterministic: prev period hi/lo breaks)
    ├─ BOS/CHoCH ───────────── NO ML (deterministic: push direction vs trend)
    ├─ Nesting Detection ───── NO ML (deterministic: child inside parent zone?)
    └─ Terminal Classification  NO ML (deterministic: opposing nest)
          │
          ▼
    Signal emitted (direction, zone, nesting context, dashboard state)
          │
          ▼
    ┌─────────────────────────────────────────────────────┐
    │  ML LAYER (optional, added after validation)        │
    │                                                     │
    │  1. Regime Filter (HMM on D/W)                     │  ← "Is this a trending market?"
    │  2. Meta-Label Filter (XGBoost)                     │  ← "Is this signal worth taking?"
    │  3. Position Sizer (confidence → lots)              │  ← "How much should we bet?"
    │  4. Zone Quality Scorer (RF)                        │  ← "How likely is this zone to hold?"
    │  5. Nesting Quality Scorer (RF)                     │  ← "Does this nesting combo work here?"
    │                                                     │
    └─────────────────────────────────────────────────────┘
          │
          ▼
    Final Decision: TAKE / SKIP / REDUCE SIZE
```

**Critical constraint:** ML NEVER replaces the mechanical engine. It sits downstream as a filter and sizer. The push zone engine remains deterministic and explainable.

---

## 4. Arguments FOR Adding ML

### 4.1 Adaptive Signal Filtering
The mechanical system will generate false positives — a demand zone fires inside a parent but price blows through it. A meta-model trained on historical outcomes can learn which feature combinations predict failure. Features available at signal time, **now validated by Level 1-3 empirical data**:

| Feature | Type | Empirical Finding | ML Value |
|---------|------|-------------------|----------|
| Zone role (push/reversal/continuation/pullback) | Categorical | Push zones: 0.000% break-through rate (13,870 interactions). Pullback: 0.066% (most fragile). Continuation: 72-77% of all events. | **High** — role strongly predicts zone durability |
| Zone age bucket (fresh/young/mature/old) | Ordinal | Fresh = 40% of events, but H1@H4 peaks at "young" not "fresh". Age preference is TF-pair-dependent. | **High** — but must be TF-pair-aware |
| Zone test count | Integer | 97% of events are on zones tested 2+. First-touch = 97.9% near-misses. `test_count==1` is the true first retest. | **High** — test count is a strong quality proxy |
| Birth period pattern | Categorical | Compression-born zones survive 85-89 retests (vs 37-45 for expansion-born). 84% of zones born during clear trending periods. | **High** — birth context predicts durability |
| Bias alignment (with/against daily) | Categorical | Direction **flips by TF pair**: LTF pairs favor with-daily (40%), HTF pairs favor against-daily (43%). Not a simple filter. | **High** — but interaction with TF pair is critical |
| Bias strength (1-3) | Ordinal | At strength 3: 49/51 with/against split with zero neutral. Strength 1: 43% neutral. | **Medium** — clarifies conviction but doesn't predict direction |
| Replacement count | Integer | 38% are original (rc=0). Replaced zones live 70x longer (2,500 vs 37 bars). rc>0 is a proxy for "mature, established." | **Medium** — survivorship signal |
| Birth price distance (ATR) | Float | Fresh zones: avg 2.88 ATR. Old zones: 3.52 ATR. Closer = more meaningful retest. | **Medium** — distance decay is gradual |
| TF pair (entry@context) | Categorical | Wick % varies 9.5-19.1%. Adjacent pairs: cleaner wicks. Skip-TF pairs: fewer break-throughs. | **High** — TF pair structure affects signal quality |
| Session / time of day | Categorical | Not yet measured in Level 3 (Level 4 sweep dimension). Expect strong signal for forex, weak for crypto. | **Unknown** — must wait for Level 4 |
| Spread at signal time | Float | Not captured in Level 3 (Level 4 feature). | **Unknown** — must wait for Level 4 |
| D-to-W relationship | Categorical | Price inside W zone 33-45% of time. XAUUSD continuation 26.6% vs GBPUSD 20.7%. | **Medium** — weekly context is frequent enough to be useful |
| Supply/demand asymmetry | Float | XAUUSD: 6.9 supply vs 21.9 demand alive at H1. Trend distorts zone population. | **High for trending assets** — must be asset-aware |

### 4.2 Position Sizing Optimization
Converting binary signals into confidence-weighted bets is the single highest-impact ML application. Instead of fixed lot size per signal, the meta-model outputs probability → Kelly fraction → lot size.
- Confidence 0.8 → full size
- Confidence 0.5 → half size
- Confidence < 0.3 → skip

### 4.3 Zone Quality Scoring
Not all zones are equal. **Level 1-3 data now quantifies this:**

| Zone Characteristic | Empirical Quality Signal |
|--------------------|-----------------------|
| Push zone | 0.000% break-through across 13,870 interactions — perfect hold rate |
| Continuation zone | 0.019% break-through — extremely reliable (582k interactions) |
| Pullback zone | 0.066% break-through — most fragile but still <0.1% |
| Compression-born (LH_HL) | 85-89 avg retests before break (vs 37-45 for expansion-born) |
| Replacement count 0 | "Original" zone, 38% of events — structural first-mover |
| Replacement count >0 | Survived replacement — proven durability (4x more retests on avg) |
| Near-miss/wick ratio | Pullback zones: 1.13 (price respects from further away). Push: 1.10. |

A simple RF with these 7 features could output a quality score (0-1) that influences position sizing. The empirical data provides clear feature importance ranking before any ML training begins.

### 4.4 Regime Awareness
The push zone engine doesn't know if we're in a trending or ranging market at the macro level. An HMM on D/W data provides this context with minimal overfitting risk.

### 4.5 Nesting Combo Optimization
The signal matrix tests many nesting combinations. **Level 3 data now provides the priority ranking:**

| TF Pair | Wick Touches | Data Depth | Statistical Viability | Priority |
|---------|----------:|:-----------|:---------------------:|:--------:|
| H1@H4 | 146,532 | 16.5 yrs | Excellent | **1st** |
| M15@H1 | 175,597 | 4.4 yrs | Excellent | 2nd |
| M15@H4 | 74,106 | 4.4 yrs | Excellent | 3rd |
| M5@H1 | 109,041 | 1.7 yrs | Good | 4th |
| M5@M15 | 242,246 | 1.7 yrs | Good | 5th |
| H1@D1 | 52,483 | 16.5 yrs | Good | 6th |

ML could learn which TF pair works best per asset class and regime — e.g., "for XAUUSD in trending regime, H1@H4 continuation retests outperform M5@M15." The data depth (16.5 years for H1) makes this viable for walk-forward validation.

### 4.6 Cross-Asset Pattern Recognition
With 38 symbols across 5 asset classes, ML can detect asset-specific patterns. **Level 1-3 already reveals one:**

- **XAUUSD supply/demand asymmetry is extreme:** H1 has 6.9 supply zones alive vs 21.9 demand (3:1 ratio). At H4: 3.4 vs 24.1. At D1: 1.4 vs 17.9. Gold's bull trend destroys supply zones and accumulates demand.
- **FX pairs are balanced:** GBPUSD H1 supply/demand is 14.0/16.8 — nearly symmetric.
- **Cross-symbol wick consistency is excellent:** counts are within 10-15% across FX pairs per TF pair. XAUUSD is the outlier (fewer H1 bars pre-2010).

ML could learn: "for trending assets (XAUUSD, BTCUSD), only with-trend zone retests are high-confidence; for ranging assets (EURUSD), both directions are viable." This is a simple classification problem once Level 4 outcome data exists.

### 4.7 Bias Transition Entry Timing (NEW — from Level 2 data)
Bias transitions occur every ~37 hours across all symbols (remarkably consistent). Level 3 shows 2-3% of H1@H4 wick touches happen at transition bars. ML could learn whether transition-adjacent entries (within N bars of a bias flip) have different outcomes than mid-trend entries. This is a timing feature that the mechanical system can flag but not optimize.

### 4.8 CHoCH Rejection Quality Scoring (NEW — from candlestick-CHoCH insight)

A reversal candlestick pattern (hammer, engulfing, shooting star) on a parent TF IS the same structural event as a child-TF CHoCH, viewed at different granularity. An H1 hammer at a demand zone = M5/M15 CHoCH occurred inside the zone. The candlestick pattern is the visual symptom; the CHoCH is the structural cause.

Not all CHoCHs are equal. ML features for CHoCH quality:
- **Wick rejection ratio** at CHoCH bar: `wick_into_zone / total_range` (high = hammer/pin bar on parent TF = strong rejection)
- **Body momentum ratio**: `abs(close - open) / total_range` (high = engulfing-like momentum shift)
- **Follow-through confirmation**: next bar continues reversal direction (engulfing confirmation)
- **Compression-born CHoCH**: zone created during range squeeze before the reversal move = institutional accumulation

These features are captured mechanically (OHLC ratios at CHoCH bars) and could be used by the meta-labeler to distinguish high-quality reversals (score 2-3) from noise (score 0-1). The mechanical system uses a threshold filter; ML could learn the optimal weighting of wick ratio vs body ratio vs follow-through per TF pair and asset class.

Reference: `docs/system/level4-expanded-sweep-analysis.md` Section 22, `docs/candlestick_patterns/candlestick_reversal_patterns.webp`

---

## 5. Arguments AGAINST Adding ML

### 4.9 PDH/PDL Proximity + Premium/Discount Pricing (NEW — from trading education)

From Video 10 (Brett Go's daily bias checklist): entries near the previous day high/low (PDH/PDL) have the highest structural significance because these are the most-watched levels. Premium/discount pricing (entry above or below the 50% level of the D1 range) determines whether you're buying cheap or selling expensive.

ML features:
- **PDH/PDL distance** (ATR units): `abs(entry_price - d1_prev_hi) / atr` and `abs(entry_price - d1_prev_lo) / atr`. Smaller = more significant.
- **Premium/discount** (binary): entry above D1 range midpoint = premium, below = discount. Longs in discount + shorts in premium = aligned with institutional logic.
- Both computed from data already available on RetestCandidate (`period_hi`, `period_lo`, D1 zone context).

These are simple, interpretable features that add structural significance context without complexity.

Reference: `docs/system/trading_concepts_reference.md` Section 10

---

## 5. Arguments AGAINST Adding ML

### 5.1 Overfitting — The Dominant Problem
Financial data has an estimated signal-to-noise ratio of ~0.05 (Lopez de Prado). 95% of apparent patterns are noise. A model with 50 features trained on 3 years of M15 data WILL find "patterns" that are pure randomness.

With typical forex data (250 trading days/year × 5 years = 1250 daily bars), the degrees of freedom for a 50-feature model are dangerously thin. Walk-forward validation mitigates but does not eliminate this risk.

### 5.2 Black Box Problem
If the meta-model rejects a push zone entry, you cannot explain WHY to a human trader. This is particularly problematic for a system built on structural logic where the human expects to understand zone nesting and BOS/CHoCH classification. SHAP values help but add significant complexity.

### 5.3 The System Isn't Fully Built Yet
**This remains the strongest argument against ML right now**, though significant progress has been made.

**What's done (Levels 0-3):**
1. ~~Be ported from Pine to Python~~ ✅ Push zone engine ported and validated
2. ~~Generate signals on historical data~~ ✅ ~9M events across 5 symbols, 8 TF pairs, up to 16.5 years
3. Those signals need to be labeled (triple barrier or zone-based SL/TP outcomes) — **NOT YET (Level 4)**
4. ~~The signal matrix needs to be swept — which combos produce enough signals?~~ ✅ All 8 TF pairs have 500+ wick touches per dimension combo
5. You need 500+ labeled signal events minimum per model/config — **NOT YET (Level 4 outcomes required)**

**What's missing (Level 4):**
- The retest entry engine that converts zone interactions into actual trades with SL/TP
- Trade outcome labeling (win/loss/expire per signal)
- The filter attribution funnel showing which filters add edge
- Walk-forward validation of mechanical configs before ML can sit on top

ML is closer than before but still premature. The diagnostic data tells us WHERE the opportunities are; Level 4 tells us which ones are PROFITABLE. ML needs the latter.

### 5.4 Complexity Cost
For a solo developer, ML adds significant maintenance burden:
- Retraining pipelines (walk-forward, periodic)
- Feature store maintenance
- Model monitoring for drift
- Debugging when ML and rules disagree
- Infrastructure for model versioning
- A/B testing framework

### 5.5 Regime Changes
A model trained on 2020-2024 data has never seen the specific conditions of 2025-2026. Interest rate environments, geopolitical events, and market microstructure changes can invalidate learned patterns overnight.

### 5.6 Curve Fitting Disguised as "Learning"
The most insidious risk. A model with 100+ features will find "patterns" that are pure noise. Walk-forward testing can mask this if the look-ahead window is too short. The only real defense is extreme parsimony (few features, simple models).

---

## 6. When ML Makes Sense vs When It Doesn't

### ML Works Better When:

| Condition | Why | Iora Status (updated 2026-04-03) |
|-----------|-----|-------------|
| Many labeled trade events (500+) | Enough data for meaningful training | **ALMOST** — 146k H1@H4 wick touches exist, but outcomes not yet labeled (need Level 4) |
| High-frequency data (M1, tick) | More data points reduce overfitting | YES — M1 through H1 data available (M1: 245k bars, H1: 102k bars over 16.5 yrs) |
| Position sizing is the question | Converting binary → continuous bets | FUTURE — after mechanical validated |
| Regime detection needed | HMMs are low-risk, interpretable | **READY** — 21 yrs D1 data available. Level 2 bias timeline shows bull/bear/compression/expansion distribution. |
| The edge is statistical (many small bets) | Law of large numbers applies | **YES** — H1@H4 alone produces 146k wick touches across 5 symbols |
| Cross-asset patterns exist | ML finds what humans miss across 38 symbols | **CONFIRMED** — XAUUSD supply/demand asymmetry (6.9:21.9 at H1) vs balanced FX pairs proves asset-specific patterns exist |

### Rule-Based Works Better When:

| Condition | Why | Iora Status (updated 2026-04-03) |
|-----------|-----|-------------|
| Clear structural logic | Push zones, BOS/CHoCH have precise definitions | YES — this IS the system |
| Explainability required | Need to know WHY each trade is taken | YES — for visual validation |
| Small trade count per config | Not enough data to train ML | **RESOLVED for most pairs** — all 8 TF pairs have 500+ events per dimension combo |
| System still being built | ML on unstable rules is useless | **PARTIALLY** — Levels 0-3 complete, Level 4 in design |

---

## 7. Specific ML Questions for Iora's Architecture

### Can ML detect push zones better than rules?
**No, and it shouldn't try.** HA run-transitions are deterministic — the HA candle either changed color or it didn't. Boundary-break validation is a simple comparison. ML adds zero value here.

### Can ML improve BOS/CHoCH classification?
**No.** BOS and CHoCH are deterministic — the push direction either matches the trend state or it doesn't. Period tracking is a simple comparison of highs/lows. Rules handle this correctly.

### Can ML classify zone quality?
**Yes — and Level 1-3 data now provides the feature importance ranking before training:**

| Feature | Empirical Signal Strength | Training Data Available |
|---------|:------------------------:|:----------------------:|
| Zone role (push/continuation/pullback) | **Very strong** — push 0.000% break, pullback 0.066% | 13,870 push + 582k continuation + 153k pullback interactions |
| Birth period pattern | **Strong** — compression-born: 85-89 retests vs expansion: 37-45 | All zones have `birth_period_pattern` populated |
| Zone age (TF-pair-adjusted) | **Strong but non-linear** — H1@H4 peaks at "young", M5@H1 peaks at "fresh" | Full age distribution per TF pair |
| Test count | **Strong** — first-touch is near-miss, test_count≥1 is real entry | 97% of events have test_count 2+, 7% have exactly 1 |
| Replacement count | **Medium** — replaced zones are 4x more durable (survivorship) | 38% rc=0, long tail to 20+ |
| Near-miss/wick ratio | **Medium** — pullback zones: 1.13, push: 1.10 | Per-role ratios stable across symbols |

A simple RF with these 6 features could produce a meaningful quality score. **The data exists now** — what's missing is the outcome labels from Level 4 to train against (did the zone hold on this specific retest, or did price blow through after the wick?).

### Can ML predict which nesting combos work best?
**Yes — and the data depth now makes this viable:**

- H1@H4: 146k wick touches over 16.5 years — enough for decade-level walk-forward validation
- M15@H4: 74k wick touches over 4.4 years — multi-regime coverage
- Cross-symbol consistency is excellent (within 10-15%) — patterns are structural, not symbol-specific

After Level 4 produces outcome labels, an XGBoost model with (TF_pair, zone_role, age_bucket, bias_alignment, regime_state) as features could predict optimal TF pair per asset class per regime.

### Can ML predict which zones hold vs break?
**Empirically more promising than initially thought.** Level 3 data shows break-through rates vary significantly by zone role (0.000% for push vs 0.066% for pullback) and by TF pair structure (adjacent-TF: 0.1-0.16% vs skip-TF: 0.003-0.009%). These are not random — they reflect structural properties ML can learn from. Features: zone role, TF gap, birth pattern, age, bias alignment. Walk-forward validation essential with 16.5 years of H1 data available.

### Can ML optimize cross-asset allocation?
**Promising for Phase 3+.** With 38 symbols producing independent signal streams, ML could learn optimal capital allocation across assets and strategies. This is portfolio-level ML, not signal-level.

### Can RL optimize entry timing within a zone?
**Research-grade problem, not practical for Iora.** RL in trading faces sparse rewards, non-stationary environments, and simulation-to-live gaps. Requires millions of episodes. Not near-term.

---

## 8. Recommendation: Phased Approach

### Phase 0: Build the Mechanical System (no ML)

**Status: 80% complete (2026-04-03)**

| Step | Status | Detail |
|------|:------:|--------|
| Port push_zones_v2 to Python | ✅ Done | Push zone engine with HA detection, push/reversal, BOS/CHoCH, nesting |
| Remove age-based zone expiry | ✅ Done | Zones live until body-close broken, soft cap 30 per TF/side |
| Enrich zone birth metadata | ✅ Done | birth_price_distance, birth_period_pattern, replacement_count, test_count |
| Level 1: Zone Activity Audit | ✅ Done | Zone lifecycle stats across 5 symbols, all TFs |
| Level 2: Bias State Timeline | ✅ Done | Per-bar D/H4/H1 bias, D-to-W relationship, transition detection |
| Level 3: Opportunity Counter | ✅ Done | ~9M events, 8 TF pairs, full-depth per-TF data ranges |
| Level 4: Retest strategy sweep | ⬜ Next | Entry engine, cascade logic, filter funnel, SL/TP, outcomes |
| Wire up `birth_bias_d/w` | ⬜ Pending | Small enhancement to enrich daily/weekly bias at zone creation |
| Run sweep across 38 symbols | ⬜ Pending | After Level 4 engine is built |
| **Collect labeled trade data** | ⬜ Pending | Every Level 4 entry signal logged with full context + outcome |

**Data available for Phase 0 completion:**
- M1: 245k bars (1.5 yrs) | M5: 129k bars (3 yrs) | M15: 110k bars (4.4 yrs) | H1: 102k bars (16.5 yrs)
- 38 symbols in parquet: forex, metals, crypto, indices, energy
- All diagnostic CSVs in results/{SYMBOL}/ for analysis

### Phase 1: AFTER LEVEL 4 VALIDATION — Regime Detection

**Readiness: HIGH (data exists, model is simple)**

- **What:** HMM on D/W data classifying trending/ranging/volatile
- **Why first:** Lowest overfitting risk, most interpretable, independent of signal quality
- **Input:** D/W OHLCV + ATR + push zone exhaustion state + bias state from Level 2
- **Output:** Regime state (0/1/2) consumed by position sizer
- **Data available:** 21 years of D1 data for FX, 14 years for XAUUSD — far exceeds the 3+ year minimum
- **Model:** 2-3 state HMM, retrained quarterly
- **Integration:** Regime state becomes an additional filter dimension in the Level 4 sweep
- **Empirical validation hook:** Level 2 already shows bias distribution (35-37% bull/bear for FX, 47% bull for XAUUSD). The HMM should roughly align with these structural bias states — if it doesn't, the regime detection is adding noise, not signal.

### Phase 2: AFTER 500+ LABELED SIGNALS — Meta-Labeling

**Readiness: MEDIUM (features identified, data exists, outcomes missing)**

- **What:** XGBoost meta-model filtering push zone retest entry signals
- **Why second:** Needs labeled outcome data from Level 4 sweep
- **Input features ranked by empirical signal strength (from Level 1-3 data):**

| Priority | Feature | Why (empirical basis) |
|:--------:|---------|----------------------|
| 1 | Zone role | Push: 0% break-through. Pullback: 0.066%. Strongest durability signal. |
| 2 | TF pair structure | Adjacent-TF: 0.1-0.16% break. Skip-TF: 0.003-0.009%. 10-50x difference. |
| 3 | Birth period pattern | Compression-born: 85-89 retests. Expansion-born: 37-45. 2x durability gap. |
| 4 | Zone age bucket | TF-pair-dependent peak (young for H1@H4, fresh for M5@H1). Non-linear. |
| 5 | Bias alignment | Direction flips by TF pair. LTF: with-daily 40%. HTF: against-daily 43%. |
| 6 | Bias strength | Strength 3: zero neutral, 49/51 with/against. Clear conviction signal. |
| 7 | Test count | test_count≥1 is real entry. 97% are retested 2+. First-touch = near-miss. |
| 8 | Replacement count | rc=0 is structural first-mover. rc>0 = proven survivor. |
| 9 | D-to-W relationship | Inside W zone 33-45% of time. Structural ceiling/floor context. |
| 10 | Birth price distance | Fresh: 2.88 ATR. Old: 3.52 ATR. Gradual decay. |
| 11 | Session / time of day | Not yet measured — Level 4 sweep dimension. Likely strong for forex. |
| 12 | Supply/demand asymmetry | Asset-specific: XAUUSD 3:1 demand bias at H1. |
| 13 | Regime state (Phase 1) | HMM output. Independent confirmation layer. |

- **Output:** Probability (0-1) → position size via Kelly fraction
- **Minimum data:** 500 labeled signal events per strategy config. **H1@H4 alone has 146k wick touches — even after Level 4 filtering, expect thousands of labeled events.**
- **Model:** XGBoost with <15 features (top 10 from table above + regime), purged k-fold CV, walk-forward validation using 16.5 years of H1 data for robust train/test splits

### Phase 3: OPTIONAL — Zone Quality Scoring + Cross-Asset Optimization

**Readiness: MEDIUM-HIGH (zone characteristics quantified, asset patterns confirmed)**

- **What:** RF scoring zone hold/break probability; portfolio-level allocation across 38 symbols
- **Why third:** Supplements meta-labeling with zone-specific and portfolio-level intelligence
- **Input — zone quality features (from Level 1 data):**
  - Zone role (push/continuation/pullback — break-through rates now quantified)
  - Birth period pattern (compression vs expansion — 2x durability gap)
  - Age at retest (TF-pair-specific optimal age known)
  - Test count at retest (proven zones vs fresh)
  - Replacement count (structural position)
  - Near-miss/wick ratio for this zone (1.04-1.13 range, role-dependent)
  - Supply/demand population at zone's TF (asymmetry indicator)
- **Input — cross-asset features (from Level 1-3 cross-symbol analysis):**
  - Per-symbol trend character (bull-biased like XAUUSD vs balanced like EURUSD)
  - Per-symbol zone population dynamics (supply/demand ratio at each TF)
  - Cross-symbol correlation state
- **Output:** Quality score (0-1) per zone; allocation weights per symbol
- **Minimum data:** 1000+ zone-test events per asset class (available: H1@H4 has 21-32k per FX symbol, 21k for XAUUSD)

### NEVER:
- Replace push zone detection with ML
- Use ML for HA run-transition detection
- Use ML for BOS/CHoCH classification
- Use RL for entry timing (research-grade, not production)
- Add ML before Level 4 mechanical sweep is validated with positive expectancy
- Train on insufficient data (<500 labeled events per config)
- Assume features are TF-pair-independent (age, bias alignment flip by pair)

---

## 9. Infrastructure Requirements (Future)

When Phase 1+ begins, Iora will need:

```
src/iora/ml/                            # New module (Phase 1+)
├── regime_detector.py                  # HMM regime classification
├── meta_labeler.py                     # XGBoost signal filter
├── zone_scorer.py                      # RF zone quality
├── nesting_scorer.py                   # Nesting combo effectiveness per TF pair
├── feature_store.py                    # Feature extraction at signal time
├── labeler.py                          # Triple barrier labeling from Level 4 outcomes
├── trainer.py                          # Walk-forward training pipeline
├── feature_importance.py               # SHAP analysis + empirical feature ranking validation
└── models/                             # Serialized model artifacts
    ├── regime_hmm_v1.pkl
    ├── meta_xgb_v1.pkl
    └── zone_rf_v1.pkl

# ML reads from existing diagnostic outputs:
results/{SYMBOL}/                       # Level 1-3 CSVs (zone audit, bias timeline, opportunities)
results/{SYMBOL}/*_alltfs_matrix.csv    # Full-depth opportunity matrices per TF pair
docs/system/level1-3-data-analysis.md   # Empirical findings that guide feature selection
```

**New dependencies (Phase 1+ only):**
- `hmmlearn` — Hidden Markov Models
- `xgboost` or `lightgbm` — gradient boosting
- `scikit-learn` — preprocessing, cross-validation
- `shap` — model explainability (optional but recommended — validate that ML feature importance aligns with empirical findings from Level 1-3)

**These are NOT added now.** They go into requirements.txt only when Phase 1 begins.

**Validation principle:** When ML feature importance (SHAP) disagrees with empirical findings (Level 1-3 data), investigate before trusting the ML. If SHAP says "zone role doesn't matter" but Level 1-3 shows 0% vs 0.066% break-through rates, the model is likely overfitting to noise in other features.

---

## 10. Data Collection Strategy (Start Now)

Even though ML is Phase 1+, we should **design for it now** by ensuring the signal matrix backtester captures everything needed for future labeling.

### What Level 4 entry signals must capture (for both mechanical sweep AND future ML):

```python
@dataclass
class EntrySignal:
    # === ENTRY IDENTITY ===
    symbol: str                       # "GBPUSD", "XAUUSD", etc.
    entry_time: pd.Timestamp
    tf_pair: str                      # "H1@H4", "M5@H1", etc.
    direction: str                    # "long", "short"

    # === ZONE CONTEXT (from Level 0 metadata) ===
    zone: PushZone                    # The entry zone (carries all birth metadata)
    zone_tf: str                      # "M1", "M5", "M15", "H1"
    context_tf: str                   # "M5", "M15", "H1", "H4", "D1"
    signal_type: str                  # "push", "reversal", "continuation", "pullback"
    struct_cls: str                   # "BOS", "CHoCH", ""
    touch_type: str                   # "wick_touch", "body_close"

    # === ZONE QUALITY FEATURES (empirically validated — Section 4.3) ===
    zone_role: str                    # "push" (0% break), "continuation" (0.019%), "pullback" (0.066%)
    zone_age_bars: int                # Bars since zone formed (on zone's own TF)
    zone_age_bucket: str              # "fresh", "young", "mature", "old" — peak varies by TF pair
    zone_test_count: int              # Prior retests — test_count≥1 is real entry
    zone_replacement_count: int       # 0 = original, >0 = survived replacement(s)
    zone_birth_pattern: str           # "HH_HL", "LH_LL", "LH_HL" (compression = most durable), "HH_LL"
    zone_birth_price_dist_atr: float  # ATR distance from zone to price at creation (fresh: 2.88, old: 3.52)
    zone_thickness_atr: float         # Zone thickness / ATR ratio

    # === BIAS CONTEXT (from Level 2) ===
    d_bias: str                       # Daily bias label (HH_HL_bull_push, LH_LL_bear_push, etc.)
    d_bias_strength: int              # 1-3 (strength 3: zero neutral, 49/51 split)
    d_to_w_relationship: str          # "continuation", "pullback", "inside_zone", "neutral"
    bias_alignment: str               # "with_daily", "against_daily", "neutral", "at_transition"
    is_bias_transition: bool          # True if bias flipped on this bar (~every 37h)
    h4_vs_daily: str                  # "with", "against", "neutral"
    h1_vs_daily: str                  # "with", "against", "neutral"

    # === HTF ZONE PROXIMITY (from Level 2) ===
    nearest_w_supply_dist_atr: float  # Distance to nearest W supply (negative if inside)
    nearest_w_demand_dist_atr: float  # Distance to nearest W demand (negative if inside)
    nearest_d_supply_dist_atr: float  # Distance to nearest D supply
    nearest_d_demand_dist_atr: float  # Distance to nearest D demand
    inside_w_zone: bool               # True if price inside W zone (33-45% of time)

    # === CASCADE CONTEXT ===
    cascade_state: str                # "inside_htf_zone", "recent_htf_retest", "none"
    cascade_htf_pair: str | None      # Which HTF pair triggered cascade, if any
    cascade_htf_direction: str | None # Direction of HTF signal

    # === NESTING CONTEXT ===
    parent_zone: PushZone | None      # Parent TF zone containing this one
    nesting_depth: int                # How many TF layers deep
    opposing_nest: bool               # Terminal — opposing direction nesting

    # === MULTI-TF STATE ===
    trend_by_tf: dict[str, int]       # {M5: +1, M15: +1, H1: -1, H4: -1, D: -1}
    zone_counts: dict[str, tuple]     # {M5: (3, 2), H1: (1, 4)} → (sup, dem) — asymmetry indicator
    period_levels: dict[str, list]    # {H1: [1.2650, 1.2580, 1.2510], ...} — 3-deep history

    # === TIMING ===
    session: str                      # "london", "ny", "asian", "off", "london_ny_overlap"
    day_of_week: int                  # 0=Mon, 4=Fri
    hour: int                         # 0-23 UTC
    spread_pips: float                # Spread at signal time
    atr_value: float                  # Current ATR(14) of entry TF

    # === TRADE EXECUTION ===
    entry_price: float
    sl_price: float
    tp_price: float
    sl_mode: str                      # "zone", "atr", "period"
    tp_mode: str                      # "zone", "fixed_rr"
    risk_pips: float
    reward_pips: float

    # === OUTCOME (filled after trade closes — REQUIRED for ML training) ===
    outcome: int | None               # +1 (TP hit), -1 (SL hit), 0 (expired)
    outcome_bars: int | None          # Bars to outcome
    max_favorable: float | None       # Max favorable excursion (MFE)
    max_adverse: float | None         # Max adverse excursion (MAE)
    pnl_pips: float | None
    hold_time_minutes: int | None     # Duration of trade
```

**Every field above is either already computed by Levels 0-3 or is a direct derivative.** The Level 4 entry engine just needs to snapshot the existing state at signal time. This costs nothing to capture and becomes the complete training dataset for Phase 1+.

**Feature-to-ML-phase mapping:**

| Feature Group | Mechanical Sweep (Phase 0) | Regime (Phase 1) | Meta-Label (Phase 2) | Zone Quality (Phase 3) |
|---------------|:-------------------------:|:-----------------:|:--------------------:|:---------------------:|
| Zone role, age, test count | Filter dimension | — | Input feature | Input feature |
| Bias alignment, strength | Filter dimension | Validation target | Input feature | — |
| D-to-W relationship, W zone proximity | Filter dimension | — | Input feature | — |
| Birth period pattern | — | — | Input feature | Input feature |
| Session, day of week | Filter dimension | — | Input feature | — |
| Cascade state | Filter dimension | — | Input feature | — |
| Zone counts (asymmetry) | — | — | Input feature | Input feature |
| Regime state | — | Output | Input feature | — |
| Outcome, MFE, MAE | Metric computation | — | Training label | Training label |

---

## 11. Signal Matrix → ML Training Pipeline

The Level 4 sweep naturally produces the dataset ML needs:

```
Level 4 Sweep (Phase 0)
    │
    ├── 38 symbols × 8 TF pairs × sweep dimensions
    │     H1@H4: 16.5 yrs, ~29k wick touches per symbol
    │     M15@H4: 4.4 yrs, ~15k wick touches per symbol
    │     M5@H1: 1.7 yrs, ~22k wick touches per symbol
    │
    ├── Each run produces: list[EntrySignal] with full context + outcomes
    │     (see Section 10 for complete field list)
    │
    ├── Filter attribution funnel per config
    │     (which filters add edge vs just reduce count)
    │
    └── Aggregate → labeled_signals.parquet
              │
              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  ML Training Pipeline (Phase 1+)                       │
        │                                                         │
        │  1. Load labeled_signals.parquet                        │
        │  2. Validate features vs Level 1-3 empirical findings   │
        │     (e.g., push zone 0% break-through should show up   │
        │      as dominant feature importance)                    │
        │  3. Purged k-fold cross-validation                      │
        │     (H1@H4: 16.5 yrs allows decade-level folds)        │
        │  4. Walk-forward train/test                             │
        │     (train 2009-2019, test 2020-2023, validate 2024+)  │
        │  5. SHAP analysis — compare to empirical feature rank   │
        │  6. Model selection                                     │
        │  7. Integration back into sweep as additional filter    │
        │                                                         │
        └─────────────────────────────────────────────────────────┘
              │
              ▼
        Re-run sweep WITH ML filter
        → Compare: mechanical-only vs ML-enhanced
        → Per symbol, per asset class, per regime
        → Per TF pair (ML may add more value to some pairs than others)
```

The key insight: **the Level 4 sweep IS the ML data factory.** Every swept configuration produces labeled training data with full context snapshots. The diagnostic data from Levels 1-3 provides the empirical feature importance baseline — ML should confirm these findings, not contradict them. If ML disagrees with the empirical data, the model is likely overfitting.

**Expected training dataset sizes (from Level 3 data):**

| TF Pair | Wick Touches (5 symbols) | After typical Level 4 filtering (~30% survive) | Walk-forward viable? |
|---------|------------------------:|-----------------------------------------------:|:--------------------:|
| H1@H4 | 146,532 | ~44k labeled signals | **Yes** — decade-level folds possible |
| M15@H1 | 175,597 | ~53k labeled signals | **Yes** — multi-year folds |
| M15@H4 | 74,106 | ~22k labeled signals | **Yes** — multi-year folds |
| M5@H1 | 109,041 | ~33k labeled signals | **Yes** — but only 1.7 yrs depth |
| M5@M15 | 242,246 | ~73k labeled signals | **Yes** — high count compensates for short period |
| H1@D1 | 52,483 | ~16k labeled signals | **Yes** — 16.5 yrs depth |

All TF pairs exceed the 500-event minimum by orders of magnitude. The constraint is no longer data volume — it's having Level 4 outcome labels.

---

## 12. Decision Summary (updated 2026-04-03)

| Question | Answer |
|----------|--------|
| Should we add ML now? | **No.** Complete Level 4 mechanical sweep first. Levels 0-3 are done. |
| Should we design for ML? | **Yes — and we already are.** Level 4 EntrySignal captures all features ML needs (Section 10). |
| Do we have enough data? | **Yes for features.** ~9M events, 146k H1@H4 wick touches, 16.5 years of H1 data. **No for outcomes** — Level 4 must produce labeled trades first. |
| What's the first ML addition? | Regime detection (HMM on D/W). 21 years of D1 data available. Bias distribution from Level 2 provides validation target. |
| What's the highest-impact ML? | Meta-labeling for position sizing. Feature importance already ranked by empirical data (Section 8, Phase 2 table). |
| Should ML replace the rules? | **Never.** ML filters and sizes. Rules generate and explain. |
| When do we start ML? | After Level 4 sweep produces positive-expectancy mechanical configs with 500+ labeled trades. |
| How does the Level 4 sweep help ML? | Every swept config produces labeled training data with 30+ context features already captured. |
| Can ML help with cross-asset allocation? | **Confirmed viable.** XAUUSD supply/demand asymmetry (3:1 at H1) proves asset-specific patterns exist. ML can learn asset-class-specific adjustments. |
| What's the empirical validation principle? | ML feature importance (SHAP) must align with Level 1-3 findings. Disagreement = likely overfitting. |

---

## 13. Sources

- Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
- Lopez de Prado, M. (2020). *Machine Learning for Asset Managers*. Cambridge University Press.
- Hudson & Thames — Meta-Labeling implementation and signal efficacy studies
- QuantConnect Community — Meta-labeling limitations discussion
- MDPI (2024) — Enhanced GA-driven triple barrier for crypto markets
- ScienceDirect (2024) — Backtest overfitting in the ML era
- SSGA (2025) — Decoding market regimes with machine learning
- QuantInsti (2025) — Regime-adaptive trading with HMM + Random Forest
- Springer (2025) — Crypto trading with triple barrier + deep learning
- MDPI (2025) — Adaptive event-driven labeling with meta-learning
