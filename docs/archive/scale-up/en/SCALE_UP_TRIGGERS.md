# Scale-Up Trigger Definitions & Monitoring

**Purpose:** Define the exact conditions that trigger each phase transition, how to measure them, and what action to take. Connects the Scale-Up Roadmap to live monitoring.

**SSOT Reference:** Lot caps and risk tiers live in `src/iki/utils/market_mechanics.py`.

---

## Table of Contents

1. [Trigger Summary](#1-trigger-summary)
2. [Phase 0 → Phase 1 Triggers](#2-phase-0-to-1)
3. [Phase 1 → Phase 2 Triggers](#3-phase-1-to-2)
4. [Phase 2 → Phase 3 Triggers](#4-phase-2-to-3)
5. [General Health Triggers](#5-general-health-triggers)
6. [How to Measure](#6-how-to-measure)
7. [Monitoring Checklist](#7-monitoring-checklist)

---

## 1. Trigger Summary

| Transition | Primary Trigger | Secondary Triggers | Action |
|------------|----------------|-------------------|--------|
| Phase 0 → 1 | Lot-cap saturation >20% on any symbol | Capital > $500K | Open 2nd account, expand fleet |
| Phase 1 → 2 | 3+ accounts approaching saturation OR capital > $2M | Counterparty concentration > 80% | Add brokers, build execution layer |
| Phase 2 → 3 | Capital > $10M OR retail brokers can't handle flow | Entity complexity warrants restructuring | PoP access, formalize holding structure |
| Any phase | Edge decay detected | WR drop >10pp, AvgR drop >50% | Pause scaling, diagnose, retrain |

---

## 2. Phase 0 → Phase 1 Triggers

### Trigger 2.1: Lot-Cap Saturation

**Definition:** A symbol is "saturated" when >20% of its trades hit the max lot size, meaning `calculate_position_size()` returns `max_lot` instead of the calculated value.

**How to measure:**

From live trade logs, for each symbol over a rolling 30-day window:

```
saturation_rate = (trades_at_max_lot / total_trades) * 100
```

**Threshold:** Symbol saturation > 20% → that symbol is capacity-constrained.

**Current max lot sizes (from market_mechanics.py):**

| Symbol | Max Lots | Approx Capital at Saturation (1% risk, 1.0x ATR SL) |
|--------|----------|------------------------------------------------------|
| BTCUSD | 10 | ~$200K-500K (first to saturate) |
| NZDUSD | 50 | ~$1M-2M |
| XAGUSD | 50 | ~$800K-1.5M |
| DE40 | 50 | ~$1M-2M |
| UK100 | 50 | ~$1M-2M |
| EURJPY | 100 | ~$2M-4M |
| GBPJPY | 100 | ~$2M-4M |
| XAUUSD | 100 | ~$2M-4M |
| US500 | 100 | ~$3M-5M |
| USTEC | 100 | ~$3M-5M |
| US30 | 100 | ~$3M-5M |
| EURUSD | 200 | ~$5M-10M |
| GBPUSD | 200 | ~$5M-10M |
| USDJPY | 200 | ~$5M-10M |

**First symbol to saturate:** BTCUSD (10 lots). Monitor this one first.

**Action when triggered:**
1. Open 2nd ICMarkets account (zero infrastructure change)
2. Clone bot fleet for saturated symbols to 2nd account
3. Split capital allocation between accounts

### Trigger 2.2: Effective Risk Below Target

**Definition:** When lot capping causes effective risk to drop below target risk, you're leaving edge on the table.

**How to measure:**

```
effective_risk = (position_lots * pip_value * SL_pips) / account_equity
target_risk = RISK_TIERS[symbol]  # 1.0%, 0.75%, or 0.5%

risk_gap = target_risk - effective_risk
```

**Threshold:** If `risk_gap > 0.2%` consistently (30+ trades), the symbol is under-deployed.

### Trigger 2.3: Capital Threshold

**Definition:** Account equity crosses $500K.

**Action when triggered:**
- Review lot-cap saturation metrics
- Begin tax/legal consultation (see ADVISOR_SHORTLIST.md)
- Prepare for 2nd account opening (see BROKER_ACCOUNT_GUIDE.md)

---

## 3. Phase 1 → Phase 2 Triggers

### Trigger 3.1: Multi-Account Saturation

**Definition:** 3+ ICMarkets accounts are approaching saturation (>15% of trades at max_lot across any account).

**Action when triggered:**
- Add a second broker (Pepperstone recommended — similar execution model)
- Build broker-agnostic execution layer
- Build cross-broker risk aggregator

### Trigger 3.2: Counterparty Concentration

**Definition:** >80% of total trading capital is at a single broker.

**Threshold:** When total capital > $2M, no single broker should hold more than 60%.

**Action when triggered:**
- Distribute capital across 2-3 brokers (see Roadmap Phase 2 allocation)
- Target: Primary 40%, Secondary 30%, Tertiary 20%, Reserve 10%

### Trigger 3.3: Capital Threshold

**Definition:** Total trading capital crosses $2M.

**Action when triggered:**
- Open accounts at 1-2 additional brokers
- Formalize trading company (AS) if not already done
- Engage skatteradgiver for holding structure design

---

## 4. Phase 2 → Phase 3 Triggers

### Trigger 4.1: Retail Broker Limitations

**Definition:** Retail brokers collectively can't handle your flow — fills are degrading, spreads widening on your order sizes, or broker-imposed restrictions appear.

**How to detect:**
- Average slippage increasing over time
- Fill rates dropping below 95%
- Broker communications about position limits or account restrictions

### Trigger 4.2: Capital Threshold

**Definition:** Total AUM crosses $10M.

**Action when triggered:**
- Apply to 2-3 Prime-of-Prime providers
- Engage corporate lawyer for holding structure formalization
- Begin FIX API development
- Consider hedge fund structure if taking external capital

---

## 5. General Health Triggers (Any Phase)

These triggers indicate problems rather than growth. They pause or reverse scaling.

### Trigger 5.1: Edge Decay

**Definition:** Live performance significantly underperforms backtest expectations.

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Win Rate | Drop > 5pp from backtest | Drop > 10pp from backtest | Pause new capital, investigate |
| Avg R | Drop > 25% from backtest | Drop > 50% from backtest | Stop scaling, retrain models |
| Max Drawdown | > 2x backtest MDD | > 3x backtest MDD | Reduce position sizes |
| SQN | Drop below 2.5 | Drop below 1.5 | Full strategy review |

**Measurement period:** Rolling 100 trades per symbol minimum.

### Trigger 5.2: Correlation Spike

**Definition:** Loss correlation between symbols increases significantly, indicating concentrated risk.

**How to detect:** When 4+ symbols have losing trades on the same day, more than 3x per month.

**Action:** Review risk allocation, reduce correlated symbol exposure.

### Trigger 5.3: Regime Change

**Definition:** Market volatility regime shifts significantly (ATR doubles or halves for extended period).

**How to detect:** Monitor 20-day rolling ATR vs training-period ATR.

**Action:** Consider volatility-regime TP/SL adjustment (Phase 5 optimization, currently parked).

---

## 6. How to Measure

### From Live Trade Logs

The live engine logs all trades. To check saturation:

```python
# Pseudocode for lot-cap saturation check
from iki.utils.market_mechanics import get_max_lot

def check_saturation(trade_log_df, symbol, window_days=30):
    """Check what % of trades hit max_lot for a symbol."""
    max_lot = get_max_lot(symbol)
    recent = trade_log_df[
        (trade_log_df['symbol'] == symbol) &
        (trade_log_df['date'] >= cutoff_date)
    ]
    if len(recent) == 0:
        return 0.0

    at_max = (recent['volume'] >= max_lot * 0.99).sum()  # 99% threshold
    return at_max / len(recent) * 100
```

### From Market Mechanics SSOT

Current lot caps and risk tiers are always in `src/iki/utils/market_mechanics.py`:

```python
from iki.utils.market_mechanics import (
    get_max_lot,
    get_risk_percent,
    get_symbol_config,
    print_symbol_config,
)

# Check a symbol's config
print_symbol_config('BTCUSD')

# Get max lot
max_lot = get_max_lot('BTCUSD')  # Returns 10.0

# Get risk percent
risk_pct = get_risk_percent('BTCUSD')  # Returns 0.01 (1.0%)
```

### Quick Manual Check

If you want a rough sense of when saturation will hit, use:

```
estimated_saturation_capital = (max_lot * pip_value * SL_pips) / risk_percent
```

Where `SL_pips` is the typical SL size in pips for that symbol (from recent ATR).

---

## 7. Monitoring Checklist

### Weekly (During Phase 0)
- [ ] Check: any trades hit max_lot this week? (grep live logs for "Capped at")
- [ ] Check: account equity vs last week (growth tracking)
- [ ] Check: any symbol WR diverging > 5pp from backtest?

### Monthly
- [ ] Calculate: lot-cap saturation rate per symbol (30-day window)
- [ ] Calculate: effective risk vs target risk per symbol
- [ ] Review: live WR vs backtest WR by symbol
- [ ] Review: capital distribution across accounts/brokers

### Quarterly
- [ ] Full performance review (use @performance-analyst)
- [ ] Compare live AvgR to backtest baseline
- [ ] Evaluate: are any Phase transition triggers met?
- [ ] Review: insurance coverage still adequate? (see INSURANCE_RISK_REGISTER.md)
- [ ] Review: tax situation and entity structure timing (see TAX_PLANNING_NORWAY.md)

### At Capital Milestones
- [ ] $50K: First meaningful base. Verify all systems working correctly.
- [ ] $100K: All symbols contributing. Check min-lot constraints.
- [ ] $250K: BTCUSD approaching saturation. Begin planning 2nd account.
- [ ] $500K: Phase 1 trigger likely met. Execute Phase 1 actions.
- [ ] $1M: Multiple symbols saturating. Tax/legal consultation urgent.
- [ ] $2M: Phase 2 evaluation. Multi-broker needed.

---

## Future Enhancement: Automated Trigger Dashboard

When the monitoring system matures, build a trigger dashboard that:

1. Reads live trade logs daily
2. Calculates saturation rate per symbol
3. Calculates effective risk vs target
4. Checks for edge decay (rolling WR, AvgR)
5. Alerts when any trigger threshold is breached
6. Outputs: "PHASE 1 TRIGGER MET — BTCUSD lot-cap saturation at 23% (threshold: 20%)"

**Implementation location:** Could be added to `scripts/reporting/` or as a new `scripts/monitoring/scale_up_triggers.py`.

---

*Created: 2026-03-01*
*Triggers are derived from Scale-Up Roadmap phases. Update when phase definitions change.*
