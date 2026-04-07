# Aris Scale-Up Roadmap: Private Trader to Imperium

**Purpose:** Map the full journey from private algo trader compounding personal capital through to institutional-scale operation, capital diversification, and impact-driven enterprise building.

**Current State:** 14 V2 bots live on ICMarkets, 3-tier risk allocation, 59 features, 86.1% WR backtest.

---

## Table of Contents

1. [Phase 0: Compounding Foundation (Current → $500K)](#phase-0-compounding-foundation)
2. [Phase 1: Lot-Cap Saturation & Multi-Account ($500K → $2M)](#phase-1-lot-cap-saturation)
3. [Phase 2: Multi-Broker Diversification ($2M → $10M)](#phase-2-multi-broker-diversification)
4. [Phase 3: Prime-of-Prime & Entity Formation ($10M → $50M)](#phase-3-prime-of-prime)
5. [Phase 4: Institutional Prime Brokerage ($50M → $500M)](#phase-4-institutional-prime-brokerage)
6. [Phase 5: Build Your Own Infrastructure ($500M+)](#phase-5-build-your-own-infrastructure)
7. [Capital Diversification Strategy](#capital-diversification-strategy)
8. [The Imperium Vision](#the-imperium-vision)
9. [Current ICMarkets Lot Caps (Reference)](#current-lot-caps)

---

## Phase 0: Compounding Foundation

**Capital range:** Current → $500K
**Timeline:** Let compound do the work. The bots are the engine.

### What Happens Here
- 14 bots compound capital at 1.0/0.75/0.5% risk per trade
- Position sizes grow naturally with account equity
- No structural changes needed — the system works as-is
- Focus: monitor live vs backtest parity, collect data, prove the edge is real

### Key Milestones
- **$50K:** First meaningful equity base. Positions are large enough for decent R-multiples in dollar terms.
- **$100K:** Begin hitting min-lot constraints less often on indices. All 14 symbols actively contributing.
- **$250K:** Some symbols (BTCUSD at 10 lots max, DE40/UK100 at 50 lots) start approaching lot caps on larger trades.
- **$500K:** Multiple symbols regularly hitting lot caps. Effective risk drops below target because position size is capped. **This is the trigger to begin Phase 1.**

### Bottleneck Detection
When `calculate_position_size()` returns `max_lot` instead of the calculated size, you're leaving edge on the table. The system logs this — monitor for:
```
Calculated: 15.2 lots → Capped at: 10.0 lots (BTCUSD)
```
When this happens on >20% of trades for a symbol, that symbol is "saturated."

### Actions
- [ ] Build lot-cap saturation monitor (alert when >20% of trades hit max_lot)
- [ ] Track effective risk vs target risk per symbol
- [ ] Begin tax planning — consult accountant about trading company structure

---

## Phase 1: Lot-Cap Saturation

**Capital range:** $500K → $2M
**Trigger:** Multiple symbols regularly capping at max lots

### The Problem
ICMarkets enforces per-position max lots:

| Symbol | Max Lots | Approx Capital at Saturation (1% risk) |
|--------|----------|----------------------------------------|
| BTCUSD | 10 | ~$200K-500K (depends on ATR) |
| DE40 | 50 | ~$1M-2M |
| UK100 | 50 | ~$1M-2M |
| NZDUSD | 50 | ~$1M-2M |
| XAGUSD | 50 | ~$800K-1.5M |
| EURJPY | 100 | ~$2M-4M |
| GBPJPY | 100 | ~$2M-4M |
| XAUUSD | 100 | ~$2M-4M |
| US500 | 100 | ~$3M-5M |
| EURUSD | 200 | ~$5M-10M |
| GBPUSD | 200 | ~$5M-10M |
| USDJPY | 200 | ~$5M-10M |

### Strategy A: Multiple ICMarkets Accounts
**Simplest first move. Zero infrastructure change.**

- Open 2-3 ICMarkets accounts under same name/entity
- Run identical bot instances on each account
- Each account gets its own MT5 instance + bot fleet
- Effectively multiplies lot caps by account count
- ICMarkets allows multiple accounts — this is standard practice

**Implementation:**
```
Account 1: 14 bots (original)
Account 2: 14 bots (clone — same models, same config)
Account 3: 14 bots (clone)
= 3x lot capacity per symbol
```

**Pros:** Zero code change, same broker, same conditions
**Cons:** Manual capital management across accounts, 3x commission, 3x monitoring

### Strategy B: Split Fleet Across Accounts
Instead of cloning all 14 bots, split by saturation level:

```
Account 1: High-saturation symbols (BTCUSD, DE40, UK100, XAGUSD, NZDUSD)
Account 2: Medium-saturation (XAUUSD, EURJPY, GBPJPY, US500, USTEC, US30)
Account 3: Low-saturation (EURUSD, GBPUSD, USDJPY) — these hit 200-lot cap last
```

Allocate more capital to accounts with symbols that saturate first.

### Strategy C: Increase Symbol Coverage
Add more symbols to spread capital across more instruments:
- Additional forex: AUDUSD, USDCHF, USDCAD, AUDNZD, EURGBP
- Additional indices: JP225 (Nikkei), HK50 (Hang Seng), AU200 (ASX)
- Additional metals: XPTUSD (Platinum)
- Commodities: USOIL, UKOIL, NATGAS

Each new symbol = additional lot capacity. Train V2 models for new symbols using same pipeline.

### Strategy D: Multiple Timeframe Models
Currently M5 only. Add:
- M15 entry model (different entry timing, different lot allocation)
- H1 swing model (larger TP/SL, fewer trades, bigger size per trade)

Different timeframes = uncorrelated entries = more capacity without lot conflicts.

### Actions for Phase 1
- [ ] Open 2nd ICMarkets account
- [ ] Build fleet orchestrator (manages bots across multiple MT5 instances)
- [ ] Add 5-10 new symbols to V2 training pipeline
- [ ] Explore M15/H1 model variants
- [ ] Establish trading company (tax efficiency, liability protection)

---

## Phase 2: Multi-Broker Diversification

**Capital range:** $2M → $10M
**Trigger:** 3+ ICMarkets accounts approaching saturation OR desire for counterparty risk reduction

### Why Multiple Brokers
1. **Counterparty risk** — never have all capital at one broker
2. **Aggregate lot limits** — each broker has independent limits
3. **Execution diversity** — different liquidity pools, different fills
4. **Regulatory protection** — spread across jurisdictions

### Broker Selection Criteria
| Requirement | Why |
|-------------|-----|
| Raw spread / ECN account | Matches ICMarkets execution model |
| MT5 support | V2 bots run on MT5 |
| FIX API available | Future institutional connectivity |
| Same symbols available | Parity with existing fleet |
| Low latency to broker server | Execution quality |
| Segregated client funds | Safety |

### Candidate Brokers (Tier 1 Retail/Semi-Institutional)
| Broker | Strengths | Lot Limits | Notes |
|--------|-----------|------------|-------|
| **Pepperstone** | Raw spread, MT5, FIX API | 100-200 lots | Australian + UK regulated |
| **FP Markets** | ECN, MT5, good for algos | 100+ lots | Australian regulated |
| **Global Prime** | DMA, FIX API | Similar to ICMarkets | Algo-friendly |
| **Interactive Brokers** | Institutional-grade API, multi-asset | Very high limits | Different platform (not MT5) — requires adapter |
| **Darwinex** | Algo-focused, can become a "Darwin" fund | Varies | Capital allocation program for proven strategies |

### Capital Allocation Across Brokers
```
ICMarkets:   40% ($800K-4M)  — Primary, proven execution
Pepperstone: 30% ($600K-3M)  — Secondary, independent liquidity
IBKR:        20% ($400K-2M)  — Institutional bridge, multi-asset exposure
Reserve:     10% ($200K-1M)  — Cash buffer / new broker onboarding
```

### Interactive Brokers — The Bridge to Institutional

IBKR deserves special attention because it's the natural bridge between retail and institutional:
- **No per-position lot limits** for most instruments (uses margin-based limits instead)
- **FIX API** for institutional-grade connectivity
- **Prime Broker services** for funds starting ~$500K+
- **Multi-asset:** Stocks, options, futures, forex, bonds — all in one account
- **Lower margin costs** than retail brokers as account size grows

**Trade-off:** Not MT5 — would need to build a bot adapter layer (Python API is excellent though, and our V2 signal generation is already Python-native).

### Actions for Phase 2
- [ ] Open Pepperstone + IBKR accounts
- [ ] Build broker-agnostic execution layer (abstract away MT5 dependency)
- [ ] Build cross-broker risk aggregator (total exposure monitoring)
- [ ] Adapt V2SignalProvider to output signals for IBKR API
- [ ] Legal: formalize trading company, accounting, tax strategy

---

## Phase 3: Prime-of-Prime & Entity Formation

**Capital range:** $10M → $50M
**Trigger:** Retail brokers can't efficiently handle your flow; seeking institutional liquidity

### Entity Structure Decision

At this capital level, entity structure matters enormously:

#### Option A: Family Office (Recommended First)
- **What:** Legal entity managing your own/family capital
- **Regulation:** Generally exempt from SEC registration (in US) or equivalent
- **Flexibility:** Maximum — no investor disclosures, no external reporting
- **Tax:** Can optimize structure (holding company → trading subsidiary → property subsidiary)
- **Best for:** Private capital compounding without outside investors

```
Aris Holdings (Parent)
├── Aris Trading Ltd (algo trading operations)
├── Aris Property Ltd (real estate investments)
├── Aris Ventures Ltd (equity/startup investments)
└── Aris Foundation (philanthropic arm — tax deductible)
```

#### Option B: Hedge Fund (When Taking Outside Capital)
- **What:** Pooled investment vehicle with external investors
- **Regulation:** SEC registration required above $150M AUM (US); FCA (UK); varies by jurisdiction
- **Structure:** Typically LP/GP with 2/20 fee model (2% management + 20% performance)
- **Min practical AUM:** $10M-50M to justify operational costs ($100K-300K/year overhead)
- **Best for:** When you want to manage other people's money alongside your own

#### Option C: Both (The Power Move)
- Family office manages personal capital (no regulation)
- Hedge fund as separate entity takes outside capital
- Shared infrastructure (same bots, same models, same team)
- Family office allocates to the fund as an investor

### Prime-of-Prime (PoP) Access

At $10M+, you qualify for PoP providers:

| PoP Provider | Min Capital | What You Get |
|--------------|-------------|--------------|
| **IS Prime** | ~$1M-5M | FCA-regulated, Tier-1 bank liquidity, low-latency FIX |
| **Advanced Markets** | ~$1M | DMA, institutional-grade spreads |
| **CFH Clearing** | ~$2M | Multi-asset liquidity, prime-of-prime clearing |
| **Invast Global** | ~$5M | Direct market access, Tier-1 aggregation |

**What PoP gives you:**
- Direct access to Tier-1 bank liquidity (Goldman, JPM, Citi, Barclays)
- Much higher lot limits (or no per-trade limits — margin-based only)
- Better spreads than retail (0.0-0.1 pip on majors)
- FIX API connectivity (industry standard for institutional trading)
- No "retail broker" in the chain

### Infrastructure Evolution
```
BEFORE (Retail):
  Bot → MT5 → ICMarkets → Liquidity Provider

AFTER (PoP):
  Bot → FIX Engine → PoP → Tier-1 Banks (multiple)
                         → Non-bank market makers
                         → ECN pools
```

### Actions for Phase 3
- [ ] Engage corporate lawyer — establish holding company + trading subsidiary
- [ ] Engage tax advisor — optimize cross-entity capital flows
- [ ] Apply to 2-3 PoP providers for quotes
- [ ] Build FIX API execution engine (replace MT5 dependency)
- [ ] Hire: DevOps engineer (infrastructure), compliance consultant
- [ ] Decide: family office only vs. hedge fund structure

---

## Phase 4: Institutional Prime Brokerage

**Capital range:** $50M → $500M
**Trigger:** Volume and AUM justify direct prime broker relationship

### Tier-1 Prime Broker Requirements
| Requirement | Typical Threshold |
|-------------|-------------------|
| AUM | $50M-500M minimum (varies by PB) |
| Monthly volume | $10B+ notional preferred |
| Entity type | Regulated fund or family office |
| Track record | 2-3+ years audited performance |
| Infrastructure | FIX connectivity, risk systems, compliance |

### Prime Broker Benefits
- **Direct bank relationships** — trade with Goldman, JPM, Citi, etc. directly
- **Cross-margining** — portfolio-level margin instead of per-position
- **Securities lending** — if expanding into equities
- **Capital introduction** — PB introduces you to allocators/investors
- **Financing** — leverage on portfolio level at institutional rates
- **Custody** — institutional-grade asset custody
- **No lot limits** — margin-based exposure limits only

### Multi-Prime Strategy
Never use a single prime broker (Lehman lesson):
```
Primary PB:    Goldman Sachs (40% of flow)
Secondary PB:  Morgan Stanley (30% of flow)
Tertiary PB:   Interactive Brokers Prime (20% of flow)
Reserve:       Separate custody (10% cash/bonds)
```

### Technology at This Scale
| Component | Purpose |
|-----------|---------|
| **OMS** (Order Management System) | Central order routing, allocation, compliance |
| **EMS** (Execution Management System) | Smart order routing, algo execution, multi-venue |
| **Risk Engine** | Real-time portfolio risk, correlation monitoring, VaR |
| **FIX Gateway** | Multi-PB connectivity |
| **Data Infrastructure** | Co-located servers, tick data, alternative data |
| **Compliance System** | Audit trail, regulatory reporting, position limits |

### Actions for Phase 4
- [ ] Engage prime broker relationships (start conversations at $25M+)
- [ ] Build OMS/EMS (or license: FlexTrade, TradingScreen, etc.)
- [ ] Hire: Head of trading, risk manager, compliance officer
- [ ] Get fund audited (required for institutional credibility)
- [ ] Establish multi-prime setup
- [ ] Consider: co-location at NY4/LD4 for execution quality

---

## Phase 5: Build Your Own Infrastructure

**Capital range:** $500M+
**Trigger:** Volume justifies owning the infrastructure stack

### Option A: Own Brokerage / Market Maker
At $500M+ AUM with proven execution needs, building your own prime-of-prime or market-making entity becomes viable:

- **Own liquidity aggregator** — connect directly to 20+ Tier-1 banks and ECNs
- **Internal crossing** — match orders across your own funds/accounts before going to market (reduces market impact)
- **Market making** — provide liquidity to retail/institutional clients, earn spread
- **White-label** — license your technology stack to other funds

```
Aris Capital (Parent)
├── Aris Execution Services (own prime-of-prime / market maker)
│   ├── FIX connections to 20+ banks
│   ├── Smart Order Router
│   └── Internal crossing engine
├── Aris Alpha Fund (your algo strategies)
├── Aris Systematic Fund (external capital)
└── Aris Technology (license tech to others)
```

### Option B: Multi-Strategy Expansion
Your V2 edge is HA Fibonacci + LightGBM. At this scale, diversify the alpha generation:

| Strategy Class | Description | Capital Allocation |
|----------------|-------------|-------------------|
| **V2 Core** (current) | M5 HA-fib entries, 14 symbols | 30% |
| **V2 Extended** | New symbols, new timeframes (M15/H1/H4) | 20% |
| **Statistical Arbitrage** | Cross-pair mean reversion, cointegration | 15% |
| **Macro Systematic** | Trend-following on rates, commodities, equities | 15% |
| **Alternative Data** | Sentiment, flow, positioning-based signals | 10% |
| **Cash / Fixed Income** | Yield on reserves, risk-off allocation | 10% |

### Option C: Technology Licensing
Your V2 pipeline (feature generation → training → deployment → live execution) is a product:
- License the platform to other traders/funds
- SaaS model: data pipeline + model training + execution
- Revenue diversification beyond trading PnL

---

## Capital Diversification Strategy

**Principle:** Trading generates the capital. Diversification preserves and multiplies it.

### The Capital Waterfall

```
Trading Profits
    │
    ├── 50% → Reinvest in Trading (compound the edge)
    │          └── More capital = more lots = more absolute return
    │
    ├── 20% → Real Estate
    │          ├── Commercial property (cash flow)
    │          ├── Residential development
    │          └── Land banking
    │
    ├── 15% → Equities & Private Markets
    │          ├── Index funds (passive)
    │          ├── Tech/growth equity (active)
    │          ├── Startup investments (angel/VC)
    │          └── Private equity co-investments
    │
    ├── 10% → Cash & Bonds (liquidity buffer)
    │          ├── Treasury bonds
    │          ├── Corporate bonds
    │          └── Money market
    │
    └── 5% → Foundation / Giving
               └── See "Imperium Vision" below
```

### Diversification by Capital Level

| Capital | Trading % | Property | Equities | Cash/Bonds | Foundation |
|---------|-----------|----------|----------|------------|------------|
| $0-1M | 90% | 0% | 5% | 5% | 0% |
| $1M-10M | 70% | 10% | 10% | 8% | 2% |
| $10M-50M | 50% | 20% | 15% | 10% | 5% |
| $50M-500M | 40% | 25% | 18% | 10% | 7% |
| $500M+ | 30% | 25% | 20% | 10% | 15% |

As capital grows, reduce trading concentration (even though it's the highest-return asset) because:
1. Lot caps create diminishing returns at scale
2. Single-strategy risk increases with concentration
3. Diversified assets provide uncorrelated returns
4. Property and equities compound independently of trading edge

### Real Estate Strategy
| Phase | Capital Deployed | Strategy |
|-------|------------------|----------|
| Early ($1M-5M) | $100K-500K | Residential buy-to-let, 1-3 properties |
| Growth ($5M-20M) | $1M-4M | Small commercial, residential portfolios |
| Scale ($20M-100M) | $5M-25M | Development projects, commercial portfolios |
| Institutional ($100M+) | $25M+ | REITs, development partnerships, land |

### Equity & Venture Strategy
| Phase | Strategy |
|-------|----------|
| Early | Index funds (S&P 500, global), some individual tech stocks |
| Growth | Add angel investments (5-10 startups at $25K-100K each) |
| Scale | VC fund co-investments, private equity, pre-IPO allocations |
| Institutional | Launch own venture arm, direct investments, board seats |

---

## The Imperium Vision

### Core Philosophy
> Money is the tool. Freedom is the goal. Impact is the purpose.

The trading bots create the engine. Everything else flows from that engine's output.

### Enterprise Structure (Full Vision)

```
IMPERIUM HOLDINGS
│
├── ARIS CAPITAL (Trading & Investment)
│   ├── Algorithmic Trading (V2 bots + future strategies)
│   ├── Hedge Fund (external capital)
│   ├── Execution Services (own prime/market maker)
│   └── Technology Licensing (SaaS)
│
├── ARIS PROPERTY
│   ├── Residential portfolios
│   ├── Commercial portfolios
│   └── Development projects
│
├── ARIS VENTURES
│   ├── Startup investments
│   ├── Technology ventures
│   └── Equity portfolio management
│
├── ARIS OPERATIONS
│   ├── Trading infrastructure
│   ├── Data centers
│   └── Shared services (legal, accounting, HR)
│
└── ARIS FOUNDATION (Non-Profit)
    ├── Free Training Programs (see below)
    ├── Public Infrastructure
    ├── Education
    └── Health & Wellbeing
```

### The Workplace Vision

Once capital sustains it, build organizations where:

| Element | Standard | Aris Standard |
|---------|----------|-----------------|
| Work day | 8 hours grinding | 8 hours total: 5hr work + 2hr self-development + 1hr fitness |
| Training | "Watch this video" | Professional courses, certifications, mentors — fully funded |
| Fitness | "Gym membership discount" | On-site gym, personal trainers, group classes — all paid |
| Pay | "Competitive" | Genuinely above-market. People shouldn't stress about money |
| Growth | "Career ladder" | Real skill development — coding, trading, leadership, creativity |
| Purpose | "Shareholder value" | Building things that make the world measurably better |

### Public Impact

What "doing good" looks like at scale:

| Capital Level | Impact Capacity |
|---------------|-----------------|
| $10M+ | Fund scholarships, sponsor community programs |
| $50M+ | Build free training centers, fund local infrastructure |
| $100M+ | Establish foundation with permanent endowment |
| $500M+ | Large-scale public projects — housing, education, healthcare |
| $1B+ | Systemic change — fund policy research, build institutions |

The key insight: **you don't need to wait for billions.** Start the foundation early (even at 2% of profits), let it compound alongside the trading capital, and scale the impact as the capital grows.

---

## Current Lot Caps (Reference)

From `src/iki/utils/market_mechanics.py` (SSOT):

| Symbol | Max Lots | Asset Class | Risk Tier |
|--------|----------|-------------|-----------|
| BTCUSD | 10 | Crypto | T1 (1.0%) |
| NZDUSD | 50 | Forex | T3 (0.5%) |
| XAGUSD | 50 | Metal | T2 (0.75%) |
| DE40 | 50 | Index | T1 (1.0%) |
| UK100 | 50 | Index | T1 (1.0%) |
| EURJPY | 100 | Forex JPY | T2 (0.75%) |
| GBPJPY | 100 | Forex JPY | T3 (0.5%) |
| XAUUSD | 100 | Metal | T2 (0.75%) |
| US500 | 100 | Index | T1 (1.0%) |
| USTEC | 100 | Index | T1 (1.0%) |
| US30 | 100 | Index | T2 (0.75%) |
| EURUSD | 200 | Forex Major | T3 (0.5%) |
| GBPUSD | 200 | Forex Major | T3 (0.5%) |
| USDJPY | 200 | Forex JPY | T3 (0.5%) |

**First symbol to saturate:** BTCUSD (10 lots) — monitor this one first.

---

## Decision Framework

At each capital milestone, ask:

1. **Are any symbols lot-capped on >20% of trades?** → Scale horizontally (more accounts/brokers)
2. **Is counterparty risk concentrated?** → Diversify brokers
3. **Is the entity structure tax-optimal?** → Restructure if needed
4. **Are we leaving edge on the table?** → Add symbols, timeframes, strategies
5. **Is capital concentration too high in trading?** → Diversify into property/equities
6. **Can we start giving back yet?** → Fund the foundation

---

## Key Risk Considerations

| Risk | Mitigation |
|------|------------|
| Edge decay | Continuous monitoring, retrain models, Phase 5 diversification |
| Broker insolvency | Multi-broker, segregated funds, max 40% at any single entity |
| Regulatory change | Multi-jurisdiction entities, legal counsel |
| Key-person risk (you) | Document everything, build team, automate operations |
| Market regime change | Multi-strategy diversification, cash reserves |
| Technology failure | Redundant infrastructure, multi-DC deployment |
| Over-leveraging at scale | Strict risk allocation, independent risk function |

---

## Immediate Next Steps (Priority Order)

1. **Monitor lot-cap saturation** — build the alert (code change)
2. **Tax/legal consultation** — understand optimal entity structure for your jurisdiction
3. **2nd ICMarkets account** — simplest scaling move when saturation hits
4. **New symbol training** — expand fleet from 14 to 20+ symbols
5. **IBKR account** — start exploring institutional-grade execution
6. **Start the foundation** — even at 1-2%, begin the habit of giving

---

*Created: 2026-03-01*
*This is a living document. Update as capital milestones are reached.*
