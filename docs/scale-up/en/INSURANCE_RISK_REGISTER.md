# Insurance & Risk Register

**Purpose:** Central register of insurance policies needed at each phase of the scale-up. Maps coverage types to business risks with Norwegian-specific providers and cost estimates.

**Principle:** Insurance is the cost of protecting the empire. Under-insuring is a gamble with asymmetric downside.

**Disclaimer:** Costs are estimates as of 2026. Get quotes from brokers for actual pricing.

---

## Table of Contents

1. [Phase-Based Insurance Matrix](#1-phase-based-insurance-matrix)
2. [Policy Descriptions](#2-policy-descriptions)
3. [Risk Register](#3-risk-register)
4. [Norwegian Insurance Providers](#4-norwegian-insurance-providers)
5. [Action Checklist](#5-action-checklist)

---

## 1. Phase-Based Insurance Matrix

| Policy | Phase A (Demo/Real Start) | Phase B (AS Formation) | Phase C (Diversification) | Phase D (Full Empire) |
|--------|:---:|:---:|:---:|:---:|
| **Personal liability (ansvar)** | Recommended | Required | Required | Required |
| **D&O (styreansvar)** | -- | Required | Required | Required |
| **Key-man (nokkelperson)** | -- | Recommended | Required | Required |
| **Professional liability (profesjonsansvar)** | -- | -- | If consulting | Required |
| **Cyber insurance** | -- | Recommended | Required | Required |
| **Property insurance (eiendom)** | -- | -- | When Eiendom AS holds assets | Required |
| **Business interruption** | -- | -- | Recommended | Required |
| **Workers' comp (yrkesskadeforsikring)** | -- | When hiring (legally required) | Required | Required |
| **Employer liability (arbeidsgiveransvar)** | -- | When hiring | Required | Required |
| **General liability (bedriftsansvar)** | -- | Recommended | Required | Required |
| **Crime / fidelity** | -- | -- | When external capital | Required |

---

## 2. Policy Descriptions

### D&O Insurance (Styreansvarsforsikring)

**What it covers:** Personal liability of directors and officers for claims arising from their decisions in running the company. Board members can be held personally liable in Norway for negligence, breach of duty, or wrongful acts.

**Why you need it:** The moment you form an AS and sit as styreleder, you are personally exposed. A creditor, employee, or tax authority can pursue you personally for board decisions.

| Detail | Value |
|--------|-------|
| When to get | Phase B — at AS formation |
| Coverage needed | NOK 2-10M (scale with company value) |
| Estimated annual cost | NOK 5,000-20,000 (small AS), NOK 20,000-100,000 (larger group) |
| Key exclusions | Fraud, criminal acts, known prior claims |

---

### Key-Man Insurance (Nokkelpersonforsikring)

**What it covers:** Pays the company a lump sum if the key person (you) dies or becomes permanently disabled. Compensates for lost revenue, hiring costs, and business disruption.

**Why you need it:** You ARE the business. If you're incapacitated, the bots can run for a while, but strategy evolution, model retraining, and capital allocation decisions stop. This policy buys time.

| Detail | Value |
|--------|-------|
| When to get | Phase B-C |
| Coverage needed | 2-3x annual trading profit or NOK 5-20M |
| Estimated annual cost | NOK 5,000-25,000 (depends on age, health, coverage) |
| Tax treatment | Premiums deductible for the company. Payout to company is taxable |

---

### Cyber Insurance (Cyberforsikring)

**What it covers:** Financial losses from cyberattacks — data breaches, ransomware, unauthorized access, business interruption due to IT incidents.

**Why you need it:** Your trading infrastructure handles real money. A compromised server could lead to stolen broker credentials, manipulated trades, or drained accounts. Algo trading systems are high-value targets.

| Detail | Value |
|--------|-------|
| When to get | Phase B (recommended), Phase C (required) |
| Coverage needed | NOK 2-10M |
| Estimated annual cost | NOK 10,000-50,000 (depends on revenue, IT setup) |
| Key requirements | Must have basic security controls in place (MFA, patching, backups) |

**Pairs with:** Annual penetration testing from cybersecurity firm (see Blueprint section 3.5).

---

### Professional Liability (Profesjonsansvarsforsikring)

**What it covers:** Claims arising from professional advice or services you provide. Relevant if Aris Consulting AS advises external clients, or if the hedge fund (Asset Management AS) faces investor claims.

| Detail | Value |
|--------|-------|
| When to get | Phase C-D (when serving external clients/investors) |
| Coverage needed | NOK 5-20M |
| Estimated annual cost | NOK 15,000-75,000 |

---

### Property Insurance (Eiendomsforsikring)

**What it covers:** Physical damage to buildings and contents — fire, water, storm, vandalism, theft. Also covers loss of rental income during repairs.

| Detail | Value |
|--------|-------|
| When to get | Phase C — first property acquisition |
| Coverage needed | Full replacement value of property |
| Estimated annual cost | 0.05-0.15% of property value (NOK 5,000-15,000 per NOK 10M property) |
| Key requirement | Building inspection (tilstandsrapport) before policy |

---

### Business Interruption (Driftsavbruddsforsikring)

**What it covers:** Lost revenue when business operations are disrupted — server failure, natural disaster, office damage, supplier failure.

| Detail | Value |
|--------|-------|
| When to get | Phase C (recommended) |
| Coverage needed | 6-12 months of operating costs + expected trading revenue |
| Estimated annual cost | NOK 10,000-30,000 |

---

### Workers' Compensation (Yrkesskadeforsikring)

**What it covers:** Injuries and occupational diseases suffered by employees during work. **Legally required in Norway** for all employers under yrkesskadeforsikringsloven.

| Detail | Value |
|--------|-------|
| When to get | First employee hire (legally required) |
| Estimated annual cost | NOK 1,000-5,000 per employee (depends on industry risk class) |
| Legal basis | Yrkesskadeforsikringsloven (mandatory, no exceptions) |

---

### General Business Liability (Bedriftsansvar)

**What it covers:** Third-party claims for bodily injury or property damage caused by your business operations. Broad catch-all policy.

| Detail | Value |
|--------|-------|
| When to get | Phase B (recommended with any AS) |
| Coverage needed | NOK 5-10M |
| Estimated annual cost | NOK 3,000-15,000 |

---

### Crime / Fidelity Insurance (Underslag / Utroskapsforsikring)

**What it covers:** Losses from employee theft, fraud, or dishonesty. Also covers external fraud attempts.

| Detail | Value |
|--------|-------|
| When to get | Phase D (when managing external capital or significant employee count) |
| Coverage needed | NOK 5-20M |
| Estimated annual cost | NOK 10,000-50,000 |

---

## 3. Risk Register

The insurance policies above mitigate these operational risks:

| Risk | Likelihood | Impact | Mitigation (Insurance) | Mitigation (Non-Insurance) |
|------|-----------|--------|----------------------|---------------------------|
| **Personal liability as board member** | Medium | Very High | D&O insurance | Proper board governance, minutes |
| **Founder incapacitation** | Low | Critical | Key-man insurance | Document everything, train team, automate |
| **Cyberattack on trading infra** | Medium | Very High | Cyber insurance | Pen-testing, MFA, monitoring, backups |
| **Broker insolvency** | Low | High | (Not insurable) | Multi-broker, max 40% per broker |
| **Algorithm malfunction** | Medium | High | Business interruption | Kill switches, position limits, monitoring |
| **Employee theft/fraud** | Low | High | Crime insurance | Segregation of duties, audit trails |
| **Property damage** | Low | Medium-High | Property insurance | Building inspections, maintenance |
| **Employee injury** | Low | Medium | Workers' comp (mandatory) | Safety procedures |
| **Professional negligence claim** | Low | High | Professional liability | Clear contracts, disclaimers |
| **Tax dispute with Skatteetaten** | Medium | Medium-High | (Not insurable) | Professional accountant, clean records, tax advisor |
| **Edge decay / strategy failure** | Medium | High | (Not insurable) | Diversification, retraining, new strategies |

### Non-Insurable Risks (Manage Operationally)

| Risk | Management Strategy |
|------|-------------------|
| Edge decay | Continuous OOS monitoring, model retraining, strategy diversification |
| Broker insolvency | Multi-broker, segregated funds, max 40% at single entity |
| Regulatory change | Multi-jurisdiction, legal counsel, compliance monitoring |
| Market regime shift | Multi-strategy, cash reserves, defensive positioning |
| Tax reclassification | Professional skatteradgiver, clean documentation, defensible position |

---

## 4. Norwegian Insurance Providers

### Insurance Brokers (Recommended First Contact)

An insurance broker (forsikringsmegler) shops across multiple insurers for you. Better coverage, better prices, independent advice.

| Firm | Specialty | Contact |
|------|-----------|---------|
| **Soderberg & Partners** | Nordic's largest independent broker. Corporate + personal | soderbergpartners.no |
| **Marsh Norway** | Global broker. Corporate risk for mid/large companies | marsh.com |
| **Aon Norway** | Global broker. Cyber and D&O specialty | aon.com |
| **Pareto Forsikringsmegling** | Norwegian firm. SME focus | pareto.no |

### Direct Insurers

| Insurer | Strengths |
|---------|-----------|
| **Gjensidige** | Largest Norwegian P&C insurer. Full corporate range |
| **If Skadeforsikring** | Nordic leader. Strong cyber and D&O products |
| **Tryg** | Nordic presence. Good SME packages |
| **Codan / AIG** | International specialty lines (D&O, cyber, professional liability) |
| **Storebrand** | Life and pension (key-man insurance) |

### Recommended Approach

1. **Phase B:** Contact Soderberg & Partners. Ask for a corporate insurance package for a small AS. Get D&O + general liability + cyber at minimum.
2. **Phase C:** Add property insurance when Eiendom AS acquires first property. Add key-man. Review coverage annually.
3. **Phase D:** Engage Marsh or Aon for full-spectrum corporate risk program. Add crime, professional liability, and increased coverage limits.

---

## 5. Action Checklist

### Phase A (Now — Demo/Real Start)
- [ ] Review personal contents insurance (innboforsikring) — covers your home office equipment
- [ ] Ensure personal liability insurance (ansvarsforsikring) is active on your home policy
- [ ] No commercial insurance needed yet

### Phase B (AS Formation)
- [ ] Contact Soderberg & Partners or Gjensidige for corporate insurance quote
- [ ] Get D&O insurance (styreansvarsforsikring) immediately at AS formation
- [ ] Get general business liability (bedriftsansvar)
- [ ] Evaluate cyber insurance (recommended if trading real money > NOK 100K)
- [ ] If hiring: get mandatory yrkesskadeforsikring before first employee starts

### Phase C (Diversification)
- [ ] Add key-man insurance (nokkelpersonforsikring) for yourself
- [ ] Add property insurance when Eiendom AS acquires first property
- [ ] Add business interruption insurance
- [ ] Annual insurance review with broker — adjust coverage to match growth
- [ ] If consulting externally: add professional liability

### Phase D (Full Empire)
- [ ] Full corporate risk program with Marsh or Aon
- [ ] Crime/fidelity insurance (especially for Asset Management AS with external capital)
- [ ] Increased D&O limits (NOK 20M+)
- [ ] Quarterly risk register review with compliance team

---

*Created: 2026-03-01*
*Review and update annually, or at each phase transition.*
