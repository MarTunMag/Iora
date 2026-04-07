# Scale-Up Documentation Index

**Purpose:** Master reading guide for the Aris scale-up planning documents. Start here.

**Current state:** 14 V2 bots live on demo. Preparing for real-money trading and eventual corporate scaling.

---

## Document Map

### Core Documents (English)

| # | Document | What It Covers | Read When |
|---|----------|---------------|-----------|
| 1 | [Scale-Up Roadmap](en/SCALE_UP_ROADMAP.md) | Phases 0-5: compounding to institutional. Lot caps, multi-broker, prime brokerage, capital waterfall, diversification strategy, imperium vision | You want the big picture of the entire journey |
| 2 | [Tax Planning Norway](en/TAX_PLANNING_NORWAY.md) | Norwegian tax for forex/CFD: individual vs ENK vs AS, holding structure, fritaksmetoden, wealth tax, reporting obligations, recommended strategy by capital level | Before going real-money or forming any entity |
| 3 | [Corporate Empire Blueprint](en/CORPORATE_EMPIRE_BLUEPRINT.md) | 9 entities to create, 40+ Norwegian advisory/consulting firms to engage, delegation matrix, phase-based rollout, hires vs outsource | When you start thinking about entity formation or hiring |

### Operational Guides (English)

| # | Document | What It Covers | Read When |
|---|----------|---------------|-----------|
| 4 | [Broker Account Guide](en/BROKER_ACCOUNT_GUIDE.md) | Step-by-step account opening for ICMarkets, Pepperstone, IBKR, FP Markets, Global Prime, Darwinex. KYC documents, timelines, corporate accounts, parity checks | Opening a new broker account or preparing for multi-broker |
| 5 | [Insurance & Risk Register](en/INSURANCE_RISK_REGISTER.md) | Phase-based insurance matrix, policy descriptions (D&O, key-man, cyber, property), risk register, Norwegian providers, action checklists | Forming an AS, hiring, or acquiring property |
| 6 | [Scale-Up Triggers](en/SCALE_UP_TRIGGERS.md) | Exact conditions for each phase transition (lot-cap saturation, capital thresholds, edge decay), how to measure, monitoring checklists | Monitoring live performance and deciding when to scale |
| 7 | [Advisor Shortlist](en/ADVISOR_SHORTLIST.md) | Prioritized "call these first" list by phase. Accountant, lawyer, tax, insurance, property, security. Quick reference card | You need to contact a professional and don't want to read the full Blueprint |

### Samme dokumenter (Norsk)

| # | Dokument | Innhold |
|---|----------|---------|
| 1 | [Oppskaleringsveikart](no/OPPSKALERING_VEIKART.md) | Fase 0-5, lot-tak, flermegler, kapitalfoss, imperiumvisjon |
| 2 | [Skatteplanlegging Norge](no/SKATTEPLANLEGGING_NORGE.md) | Skatt for forex/CFD, privatperson vs ENK vs AS, holding, fritaksmetoden, formuesskatt |
| 3 | [Selskapsimperiet Plan](no/SELSKAPSIMPERIET_PLAN.md) | 9 selskaper, 40+ norske rådgivningsfirmaer, delegeringsmatrise, fasebasert utrulling |

### Naming (Not Decided Yet)

| Document | What It Covers |
|----------|---------------|
| [Naming Themes](naming/NAMING_THEMES.md) | 10 name themes explored: Kaizen, Meridian, Pneuma, Umbra, Apex, Indre Kraft, Sentient, Aether, Praxis, Stille. Evaluation matrix + decision framework |
| [Hybrid Structures](naming/HYBRID_STRUCTURES.md) | 3 core structures (Shadow Architect, Breath of Life, Mind-Body Empire) + 10 cross-pollinated hybrids + 30-row matrix + full name glossary + additional holding name alternatives |
| [Shortlist & Availability](naming/SHORTLIST.md) | Decision template: pick top 3, check Bronnøysund + domain + trademark availability, fill in full structure. Ready to use when you want to decide |

**Status:** Names are exploratory. No decisions made. When ready, use the Shortlist template to narrow down and check availability.

---

## Reading Order by Situation

### "I'm about to go from demo to real money"
1. **Tax Planning** (en/ or no/) — understand reporting obligations from trade #1
2. **Scale-Up Roadmap** Phase 0 section — what to monitor during compounding
3. **Scale-Up Triggers** — set up weekly monitoring checklist
4. Ensure the tax reporting module works: `python scripts/reporting/generate_tax_report.py`

### "I'm considering forming a company (AS)"
1. **Tax Planning** sections 3, 5, 7, 10 — AS mechanics, holding structure, comparison, strategy by level
2. **Corporate Empire Blueprint** sections 1-2, 5 Phase B — which entities first
3. **Advisor Shortlist** Phase B — who to call first (lawyer + accountant)
4. **Insurance & Risk Register** Phase B — D&O insurance at AS formation
5. **Broker Account Guide** section 8 — corporate account requirements

### "I hit lot caps / need more capacity"
1. **Scale-Up Triggers** — confirm the trigger is actually met (>20% saturation)
2. **Scale-Up Roadmap** Phase 1 — multi-account, fleet split, new symbols, multi-TF
3. **Broker Account Guide** — how to open 2nd account or new broker
4. **Scale-Up Roadmap** Phase 2 — multi-broker, IBKR bridge

### "I want to pick company names"
1. **Naming Themes** — explore 10 themes, read evaluation matrix
2. **Hybrid Structures** — see how different names combine across entities
3. **Shortlist & Availability** — fill in the template, check brreg.no + Patentstyret + domains

### "I need an accountant / lawyer / advisor"
1. **Advisor Shortlist** — prioritized "call these first" with contact info and what to ask
2. **Corporate Empire Blueprint** section 3 — full list with detailed pros/cons (if you want depth)

### "I need insurance / risk management"
1. **Insurance & Risk Register** — phase-based matrix, policy descriptions, Norwegian providers
2. **Advisor Shortlist** Phase B — insurance broker recommendation (Soderberg & Partners)

---

## Immediate Checklist: Demo to Real

Priority actions for the transition from demo to real-money trading:

### Before First Real Trade
- [ ] Decide: trade as privatperson or form AS first?
  - If capital < NOK 500K and no liability concerns: privatperson is fine (22% tax)
  - If capital > NOK 500K or want protection: consider Holding AS + Trading AS
  - See Tax Planning section 10 for decision matrix
- [ ] Find an accountant (regnskapsforer) comfortable with forex/financial instruments
  - Candidates: Leinonen Norway, ybiN AS (see Blueprint section 3.1)
- [ ] Understand reporting obligations: each closed trade must be converted to NOK
- [ ] Verify the tax module works end-to-end on demo trade data
- [ ] Set up a dedicated record-keeping system (MT5 trade exports + tax pipeline)

### After Going Real
- [ ] Export MT5 trade history monthly (or automate)
- [ ] Run tax report quarterly to stay ahead of year-end
- [ ] Monitor lot-cap saturation (log when calculate_position_size hits max_lot)
- [ ] Track effective risk vs target risk per symbol
- [ ] Keep demo running in parallel for first 1-3 months (parity monitoring)

### At NOK 500K Trading Capital
- [ ] Consult accountant about AS formation timing
- [ ] Consult forretningsadvokat (CMS Kluge or SANDS recommended for Phase B)
- [ ] Engage skatteradgiver for holding structure design
- [ ] Consider 2nd ICMarkets account if symbols are saturating

### Entity Formation (When Ready)
- [ ] Register Holding AS (NOK 30,000 capital + NOK 6,825 fee via Altinn)
- [ ] Register Trading AS as subsidiary of Holding
- [ ] Open business bank account (DNB, Nordea, or Sbanken bedrift)
- [ ] Set up accounting software (Fiken recommended for small AS)
- [ ] Transfer trading capital to AS
- [ ] Set up salary payments (minimum for social security rights)
- [ ] Trademark search for chosen holding name (Patentstyret, NOK 2,900)

---

## Cross-References

| Topic | Where to Find It |
|-------|-----------------|
| Tax module code | `src/iki/tax/` (report_generator.py, norges_bank.py, calculator.py, trade_loader.py) |
| Tax module docs | `docs/reference/TAX_REPORTING_SYSTEM.md` |
| Risk allocation | `docs/reference/RISK_ALLOCATION_ANALYSIS.md` |
| Market mechanics (SSOT) | `src/iki/utils/market_mechanics.py` (lot caps, risk tiers) |
| Live engine | `scripts/live/run.py` |
| Fleet results | `docs/reference/V2_PHASE4_FLEET_RESULTS.md` |

---

## Document Maintenance

- EN and NO versions should stay in sync. When updating one, update the other.
- Naming docs are brainstorming material — update freely, no sync obligation.
- This INDEX.md should be updated when new scale-up docs are added.
- Tax rates should be verified annually (current: 2025/2026 rates).

---

*Last updated: 2026-03-01*
