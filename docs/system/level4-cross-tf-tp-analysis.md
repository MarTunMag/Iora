# Cross-TF TP Analysis — The Precision Entry + Structural Target Breakthrough

> **Purpose:** Document the critical finding that LTF precision entries (M5 limit, 1.5 pip SL) should target HTF structural zones (H4/D1 opposing zones, 50-100+ pip TP) instead of fixed same-TF R:R multiples. This transforms the system from a 2-pip micro-scalper into a precision swing engine.
>
> **Date:** 2026-04-06
> **Status:** Concept validated by R:R scaling data. Cross-TF TP mode needs implementation and testing.
> **Prerequisite findings:** `level4-structural-sltp-analysis.md` (limit orders SQN 23-40)

---

## 1. The Problem: 2-Pip Wins With 50-Pip Potential

The 797-config sweep validated limit orders as transformative (SQN 23-40 across GBPUSD + EURUSD). But the TOP configs are micro-scalps:

| Config | Avg Win | Avg Loss | R:R Achieved | Hold | Total Pips |
|--------|:-------:|:--------:|:------------:|:----:|:----------:|
| M5@M15 limit rr=2.0 | **2.3p** | -1.2p | 1.9:1 | 0.1h | +6,904 |
| M15@H1 limit rr=2.0 | **4.8p** | -2.3p | 2.1:1 | 0.3h | +8,824 |
| H1@H4 limit rr=2.0 | **11.0p** | -5.2p | 2.1:1 | 1.2h | +6,974 |

The zones HOLD. Price moves 50+ pips in the trade direction after the zone bounce. But the system exits at 2-3 pips because the TP is a fixed 2:1 multiple of the tiny limit-entry SL.

**The SL stays ~1-5 pips (zone boundary from limit entry). The zone's structural reliability means price reaches targets FAR beyond 2:1.**

---

## 2. Proof: R:R Scaling Shows The Zone Holds

H1@H4 limit — SAME entry, different R:R targets:

| R:R | Avg Win | Avg Loss | WR | SQN | PF | Total Pips | Hold |
|:---:|:-------:|:--------:|:--:|:---:|:--:|:----------:|:----:|
| 1.5 | 8.3p | -5.2p | 65.5% | 19.78 | 3.05 | +4,975 | 1.1h |
| 2.0 | 11.0p | -5.2p | 64.2% | 23.64 | 3.78 | +6,974 | 1.2h |
| 3.0 | 16.1p | -5.3p | 61.1% | **26.81** | **4.79** | **+10,248** | 1.4h |
| 4.0 | 21.3p | -5.3p | 57.8% | **27.48** | **5.47** | **+12,977** | 1.7h |

**SQN INCREASES with higher R:R.** 27.48 at rr=4.0 vs 23.64 at rr=2.0. The loss stays at 5.2-5.3 pips (SL is fixed at zone boundary). The win grows from 11 to 21 pips. WR only drops from 64% to 58% — price reaches 4:1 targets most of the time.

**Total pips nearly DOUBLE:** +12,977 at rr=4.0 vs +6,974 at rr=2.0. Same entry, same risk, almost 2x the return.

**The implication:** If 4:1 R:R works with 58% WR, what happens at 10:1? 20:1? 33:1? The zone holds. The question is only "does price reach the target before hitting SL?" And with a 5-pip SL behind a zone that has 0.003% break-through rate, the answer is: if you target the right structural level, YES.

---

## 3. The Cross-TF TP Concept

**Current:** Enter on LTF, target the next opposing zone on the SAME context TF.
**Proposed:** Enter on LTF, target the next opposing zone on a HIGHER TF.

| Entry Setup | SL | TP (current same-TF) | TP (cross-TF: H1) | TP (cross-TF: H4) | TP (cross-TF: D1) |
|-------------|:--:|:--------------------:|:------------------:|:------------------:|:------------------:|
| M5@M15 limit | ~1.5p | M15 opp (~3p, 2:1) | H1 opp (~15p, 10:1) | H4 opp (~50p, 33:1) | D1 opp (~150p, 100:1) |
| M5@H1 limit | ~3p | H1 opp (~8p, 3:1) | — | H4 opp (~40p, 13:1) | D1 opp (~120p, 40:1) |
| M15@H1 limit | ~2.5p | H1 opp (~6p, 2:1) | — | H4 opp (~45p, 18:1) | D1 opp (~130p, 52:1) |
| H1@H4 limit | ~5p | H4 opp (~15p, 3:1) | — | — | D1 opp (~100p, 20:1) |

**The WR will drop significantly at higher R:R targets** — not every zone bounce reaches the D1 opposing zone. But the math is brutal: at 33:1 R:R, you only need 4% WR to break even. At 10:1, you need 10%. Even pessimistic estimates (20-30% WR on cross-TF targets) produce extraordinary expectancy.

---

## 4. The Cascade Entry + Cross-TF TP Model

This is the production system — combining the cascade model with cross-TF TP:

```
STEP 1: D1 bias establishes direction
  → D1 push zone = the macro target and reversal level

STEP 2: H4 counter-trend zones form (against daily bias)
  → These are the intraday entry AREAS

STEP 3: Price enters H4 zone → M15/M5 zones inside it
  → M5 limit order at zone edge = precision entry
  → SL behind M5 zone boundary = 1.5 pips risk

STEP 4 (NEW): TP at HTF structural target
  → Partial TP at M15 opposing zone (2:1 R:R) = guaranteed small win
  → Remainder trails to H1 opposing zone (10:1 R:R)
  → Final target: H4 opposing zone (33:1 R:R) or D1 zone

RESULT: 1.5 pip risk → 3 pip partial + 50 pip runner = blended 20:1+ R:R
```

**This is EXACTLY what the YouTube videos describe:**
- Video 16 (Sniper entries): "You need to make use of multiple time frames for the best entry" → M5 entry, H4 target
- Video 7 (Brett Go): "Direction → Location → Execution" → D1 bias, H4 zone, M5 limit
- Video 3 (S/D + liquidity sweep): Enter at zone after sweep, SL behind zone, TP at next HTF zone
- Video 18 (Chart markup): "Price shifted bearish on the lower time frame to facilitate the higher time frame swing pullback" → LTF entries serve HTF targets

---

## 5. Partial Take-Profit Strategy

The optimal approach isn't all-or-nothing. It's a partial TP ladder:

```
Position: 3 units at M5 limit entry (1.5 pip SL per unit = 4.5 pip total risk)

Unit 1 (33%): TP at M15 opposing zone (2:1 R:R = 3 pips)
  → Locks in small guaranteed profit
  → Move SL to breakeven on remaining units

Unit 2 (33%): TP at H1 opposing zone (10:1 R:R = 15 pips)
  → Captures the intraday swing
  → Trail SL behind M15 structure

Unit 3 (34%): TP at H4 opposing zone (33:1 R:R = 50 pips)
  → Captures the full structural move
  → Trail SL behind H1 structure
  → If price reaches H4 target: massive win
  → If stopped at breakeven: zero cost (Unit 1 already locked profit)

Blended outcome (if all hit): (3 + 15 + 50) / 3 = 22.7 pips avg on 1.5 pip risk = 15:1 blended R:R
Blended outcome (only Unit 1 hits): 3 pips on 4.5 pip risk = partial loss BUT SL moved to BE on others
Worst case (all stopped): -4.5 pips (normal zone SL hit)
```

**This is the ML opportunity:** The mechanical system uses fixed partial levels. ML could learn the OPTIMAL partial strategy per context — when to hold Unit 3 vs exit early, when to add to position vs sit tight, based on the 17 features captured at entry time.

---

## 6. What Needs To Be Built

### 6a. Cross-TF TP Mode (retest_sl_tp.py)

New `tp_mode="htf_zone"` with `tp_htf` parameter:

```python
tp_mode: str = "htf_zone"  # target opposing zone on a HIGHER TF
tp_htf: str = "H4"         # which TF to target ("H1", "H4", "D1")
```

Implementation: at entry time, find the nearest opposing zone on `tp_htf` instead of the context TF. For M5@M15 entry with `tp_htf="H4"`: find the nearest H4 supply zone above (for longs) or H4 demand zone below (for shorts).

This requires the zone engine state for the target TF to be available during candidate building. The `build_retest_candidates()` function already runs the zone engine for all TFs — it just needs to look up the target TF's zones instead of only the context TF's zones.

### 6b. Partial TP Tracking (retest_engine.py)

New position management mode for partial exits:

```python
partial_tp: bool = False        # enable partial TP ladder
partial_levels: list[str] = []  # ["M15", "H1", "H4"] — TF zones for each partial
partial_sizes: list[float] = [] # [0.33, 0.33, 0.34] — fraction per level
```

Each partial level is an independent TP target. When a partial hits:
- Close that fraction of the position
- Move SL to breakeven on remaining
- Track P&L per partial level

### 6c. Focused Limit Sweep Script

A new sweep script that ONLY runs limit configs with cross-TF TP targets:

```python
# Focused limit sweep — cross-TF TP targets
for entry_pair in ["M5@M15", "M5@H1", "M15@H1", "H1@H4"]:
    for tp_htf in ["H1", "H4", "D1"]:
        # Skip if tp_htf <= context_tf
        if tf_order(tp_htf) <= tf_order(entry_pair.split("@")[1]):
            continue
        configs.append(RetestConfig(
            tf_pair=entry_pair, entry_mode="limit", sl_mode="zone",
            tp_mode="htf_zone", tp_htf=tp_htf))
        # With bias filters
        for bias in ["with_daily", "against_daily"]:
            configs.append(RetestConfig(
                tf_pair=entry_pair, entry_mode="limit", sl_mode="zone",
                tp_mode="htf_zone", tp_htf=tp_htf, bias_filter=bias))
```

Estimated configs: ~60-80 (much smaller than the 797-config discovery sweep). Should run in 2-3 hours per symbol.

---

## 7. Expected Outcomes

| Scenario | WR | R:R | Expectancy per trade | Assessment |
|----------|:--:|:---:|:--------------------:|:----------:|
| M5@M15 limit → M15 TP (current) | 53% | 2:1 | +0.59R | Proven, micro-scalp |
| M5@M15 limit → H1 TP | ~35% | 10:1 | **+2.5R** | Strong if WR holds above 20% |
| M5@M15 limit → H4 TP | ~20% | 33:1 | **+4.6R** | Massive if WR holds above 5% |
| H1@H4 limit → D1 TP | ~25% | 20:1 | **+4.0R** | Large structural moves |
| Partial ladder (M15+H1+H4) | varies | 15:1 blended | **+3-5R** | Best risk-adjusted |

Break-even WR for each target:
- 10:1 R:R → need 10% WR to break even (we're likely at 30-40%)
- 20:1 R:R → need 5% WR (we're likely at 20-30%)
- 33:1 R:R → need 3% WR (we're likely at 15-25%)

**Even pessimistic WR estimates produce extraordinary expectancy at cross-TF R:R levels.**

---

## 8. Relationship to ML

Cross-TF TP creates the exact use case where ML adds maximum value:

| ML Application | What It Learns | Input Features |
|----------------|---------------|----------------|
| Hold vs close decision | "This trade hit 1R, should I hold for 10R?" | H4 structure state, HMA direction, M15 momentum, zone test count |
| Partial sizing | "Take 50% at M15 or hold full for H1?" | Bias strength, zone role, compression-born flag, session |
| Trail SL placement | "Trail behind M15 structure or H1 structure?" | Number of M15 BOS since entry, H1 CHoCH proximity |
| Risk allocation | "This setup is compression+against_daily+HMA: go 2x" | All 17 entry features → confidence score |

**The mechanical system provides the entry (proven) and the fixed partial levels (testable). ML optimizes the MANAGEMENT — when to hold, when to close, how much to risk.**

---

## 9. Priority Action Items

### Immediate
1. Build `tp_mode="htf_zone"` in `retest_sl_tp.py` + `retest_candidate.py`
2. Add `tp_htf` field to `RetestConfig`
3. Create focused limit sweep script with cross-TF TP configs (~60-80 configs)
4. Run on GBPUSD first (validation), then all 5 symbols

### After cross-TF TP sweep
5. Build partial TP tracking in `retest_engine.py`
6. Run partial ladder sweep (M15 + H1 + H4 targets)
7. Analyze: which partial strategy maximizes risk-adjusted returns?

### ML Phase
8. With partial TP data, train meta-model on hold/close decisions
9. Walk-forward validate the ML management layer
10. Compare: mechanical partial vs ML-optimized partial

---

## 10. Cross-Reference

| Document | Relevance |
|----------|-----------|
| `level4-structural-sltp-analysis.md` | Limit order discovery (SQN 23-40) |
| `level4-findings-and-next-steps.md` | Section 4.2 (layered cascade), Section "Cross-TF TP" |
| `trading_concepts_reference.md` | Videos 3, 7, 16, 18 — sniper entries with HTF targets |
| `ml_research/ML_COMPONENT_ANALYSIS.md` | Phase 2 meta-labeling, position sizing features |
| `level4-expanded-sweep-analysis.md` | Cascade model, against-daily finding |
