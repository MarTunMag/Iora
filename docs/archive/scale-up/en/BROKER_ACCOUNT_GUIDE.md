# Broker Account Opening Guide

**Purpose:** Practical step-by-step for opening trading accounts at each broker mentioned in the Scale-Up Roadmap. KYC requirements, timelines, and gotchas.

**Disclaimer:** Requirements change. Verify directly with each broker before applying.

---

## Table of Contents

1. [ICMarkets (Current + Additional Accounts)](#1-icmarkets)
2. [Pepperstone](#2-pepperstone)
3. [Interactive Brokers (IBKR)](#3-interactive-brokers)
4. [FP Markets](#4-fp-markets)
5. [Global Prime](#5-global-prime)
6. [Darwinex](#6-darwinex)
7. [General KYC Document Checklist](#7-general-kyc-checklist)
8. [Corporate Account Requirements](#8-corporate-account-requirements)

---

## 1. ICMarkets

**Website:** icmarkets.com
**Status:** Current primary broker. Additional accounts needed at Phase 1 ($500K+).

### Personal Account (Already Open)

You already have one. For additional accounts under the same name:

- ICMarkets allows multiple accounts under one profile
- Log into Client Area > Open Additional Account
- No new KYC required if profile already verified
- Choose: Raw Spread (cTrader) or Raw Spread (MT5) — use MT5 for V2 bots
- Base currency: USD (matches P&L tracking)

### Opening a New ICMarkets Account (If Needed)

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Register at icmarkets.com | 5 min |
| 2 | Complete personal details form | 10 min |
| 3 | Upload KYC documents (see checklist below) | 5 min |
| 4 | Wait for verification | 1-3 business days |
| 5 | Fund account (bank transfer, credit card, Skrill, Neteller) | 0-3 business days |
| 6 | Download MT5, log in with credentials | 5 min |

### Account Types

| Type | Spread | Commission | Best For |
|------|--------|------------|----------|
| Raw Spread (MT5) | From 0.0 pip | $3.50/side/lot (forex) | V2 bots |
| Raw Spread (cTrader) | From 0.0 pip | $3.00/side/lot | Manual trading |
| Standard | From 1.0 pip | $0 | Not recommended for algo |

### ICMarkets KYC Requirements

| Document | Accepted |
|----------|----------|
| **Photo ID** | Passport (preferred), national ID card, driver's license |
| **Proof of address** | Bank statement, utility bill, government letter — dated within 3 months |

### Key Details for V2 Bots

- **Leverage:** Up to 1:500 (non-AU) or 1:30 (AU retail, ASIC)
- **MT5 server:** Use the server closest to your VPS (e.g., ICMarketsEU-MT5)
- **Expert Advisors:** Enabled by default on all account types
- **VPS:** ICMarkets offers free VPS if you trade 15+ lots/month (you will exceed this)
- **Max lot sizes:** Refer to `src/iki/utils/market_mechanics.py` — BTCUSD=10, indices=50-100, forex=100-200

### Norwegian-Specific Notes

- ICMarkets is regulated by CySEC (Cyprus) for EU/EEA clients, not Finanstilsynet
- Norwegian clients fall under CySEC investor protection (EUR 20,000 insurance)
- No Norwegian tax reporting — you must self-report all trades to Skatteetaten

---

## 2. Pepperstone

**Website:** pepperstone.com
**When:** Phase 2 ($2M+) — secondary broker for counterparty risk reduction
**Regulation:** FCA (UK) + ASIC (Australia) + CySEC + DFSA + SCB

### Opening Process

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Register at pepperstone.com | 5 min |
| 2 | Complete application (personal + financial details) | 15 min |
| 3 | Knowledge assessment (basic trading quiz) | 5 min |
| 4 | Upload KYC documents | 5 min |
| 5 | Verification | 1-2 business days |
| 6 | Fund account | 0-3 business days |
| 7 | Download MT5, configure bots | 15 min |

### Account Types

| Type | Spread | Commission | Best For |
|------|--------|------------|----------|
| Razor (MT5) | From 0.0 pip | $3.50/side/lot (forex) | V2 bots |
| Standard | From 1.0 pip | $0 | Not recommended |

### Key Considerations

- Razor account has near-identical execution model to ICMarkets Raw Spread
- FIX API available (useful for Phase 3+ institutional connectivity)
- Supports MT5 Expert Advisors
- Norwegian clients likely under CySEC or SCB entity
- Commission structure matches ICMarkets ($7/lot round-turn on forex)

### Parity Check Before Going Live

Before running V2 bots on Pepperstone, verify:
- [ ] Symbol names match (e.g., XAUUSD vs GOLD — Pepperstone may differ)
- [ ] Pip sizes match (check `get_pip_size()` in market_mechanics.py)
- [ ] Commission matches what's configured
- [ ] Spread during active hours is comparable to ICMarkets
- [ ] MT5 server timezone (UTC offset) matches expectations

---

## 3. Interactive Brokers (IBKR)

**Website:** interactivebrokers.com
**When:** Phase 2-3 ($2M+) — institutional bridge, no per-position lot limits
**Regulation:** SEC/FINRA (US), FCA (UK), MNB (Hungary for EU), and many more

### Why IBKR Is Different

- **Not MT5** — uses Trader Workstation (TWS) or their Python API
- **No per-position lot limits** — uses margin-based limits instead
- **Multi-asset** — stocks, options, futures, forex, bonds in one account
- **FIX API** available for institutional connectivity
- V2 bots would need an adapter layer (Python API → IBKR)

### Opening Process

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Apply at interactivebrokers.com | 10 min |
| 2 | Complete detailed application (financial profile, trading experience, income/net worth) | 20-30 min |
| 3 | Upload KYC documents | 5 min |
| 4 | W-8BEN tax form (for non-US persons) | 5 min |
| 5 | Verification | 2-5 business days |
| 6 | Fund account (bank transfer — wire preferred for large amounts) | 1-3 business days |
| 7 | Download TWS or set up IB Gateway for API | 15 min |

### Account Types

| Type | Min Deposit | Best For |
|------|-------------|----------|
| Individual | $0 (no minimum) | Personal trading |
| Organization/Entity | $0 | When you have a trading AS |
| Advisor | $0 | If managing multiple accounts |

### Norwegian-Specific

- For EU/EEA clients: IBKR Ireland or IBKR Central Europe (Hungary)
- Supports Norwegian kroner (NOK) as base currency — but USD recommended for consistency
- Automatically reports to some tax authorities — verify if Norway is included
- Norwegian withholding tax on US dividends: 15% (under tax treaty, vs 30% default)

### Technical Integration for V2

The V2 signal generation is already Python-native (`V2SignalProvider`). To connect to IBKR:

```
V2SignalProvider (generates signals)
    |
    v
IBKR Adapter (new code needed)
    |
    v
IB API (ibapi Python package) or ib_insync
    |
    v
IBKR TWS / IB Gateway
```

**Key work needed:**
- [ ] Build order execution adapter (translate V2 signals to IBKR orders)
- [ ] Handle symbol mapping (IBKR uses different naming: EUR.USD, not EURUSD)
- [ ] Handle order types (IBKR has more granular order types than MT5)
- [ ] Build position monitoring (IBKR PnL vs MT5 PnL tracking)

---

## 4. FP Markets

**Website:** fpmarkets.com
**When:** Phase 2 ($2M+) — alternative ECN broker
**Regulation:** ASIC (Australia) + CySEC

### Opening Process

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Register at fpmarkets.com | 5 min |
| 2 | Complete application | 10 min |
| 3 | Upload KYC documents | 5 min |
| 4 | Verification | 1-2 business days |
| 5 | Fund + download MT5 | Same day |

### Key Details

- Raw ECN account: from 0.0 pip spread, $3/side/lot commission
- MT5 support with Expert Advisors
- Good algo-trading reputation
- Australian-regulated entity may offer higher leverage than EU-regulated

---

## 5. Global Prime

**Website:** globalprime.com
**When:** Phase 2 ($2M+) — DMA execution, algo-friendly
**Regulation:** ASIC (Australia) + VFSC (Vanuatu)

### Key Details

- Direct Market Access (DMA) — orders go straight to liquidity providers
- MT5 support
- FIX API available (Phase 3+)
- Execution quality reports available (transparency on fills)
- Similar commission structure to ICMarkets

---

## 6. Darwinex

**Website:** darwinex.com
**When:** Phase 2-3 — unique model: trade and attract capital simultaneously
**Regulation:** FCA (UK)

### Why Darwinex Is Interesting

- You trade your own capital AND your strategy becomes a "Darwin" (trackable asset)
- If your Darwin performs well, Darwinex Capital allocates up to EUR 4M to your strategy
- Revenue: you earn performance fees on allocated capital (15-20%)
- This is essentially a lightweight way to manage external capital without forming a fund

### Opening Process

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Register at darwinex.com | 5 min |
| 2 | Complete application + KYC | 15 min |
| 3 | Verification | 1-3 business days |
| 4 | Open MT5 account + connect to DarwinAPI | 10 min |
| 5 | Build track record (3-6 months minimum for capital allocation) | 3-6 months |

### Key Consideration

- Track record must show risk-adjusted returns (not just high returns with high DD)
- V2's 86.1% WR and low MDD (-2% to -6.4%) would likely qualify for allocation
- Platform takes a cut of performance fees (typically 20% of the 15-20% you earn)

---

## 7. General KYC Document Checklist

Prepare these documents before opening any new broker account:

### Personal Account

| Document | Details | Format |
|----------|---------|--------|
| **Passport** | Valid, not expired. Front page scan/photo | PDF, JPG, PNG (under 5MB) |
| **National ID** (alternative) | Norwegian national ID card | Same |
| **Proof of address** | Utility bill, bank statement, or official letter. Must show full name + address. Dated within 3 months | Same |
| **Tax ID** | Norwegian personnummer (11 digits) — some brokers ask for this | Text |
| **Source of funds** | Bank statement showing salary/savings. Required for larger deposits | PDF |

### Tips

- Scan/photograph in good lighting with all corners visible
- Color copies only (no black and white)
- English translations may be required for Norwegian documents
- Some brokers accept digital bank statements (screenshot of nettbank)
- For deposits > $25,000: some brokers require additional source-of-funds documentation

---

## 8. Corporate Account Requirements

When you have a trading AS, the requirements expand significantly:

### Additional Documents

| Document | Details |
|----------|---------|
| **Firmaattest** | Company registration certificate from Bronnoysundregistrene |
| **Vedtekter** | Articles of association |
| **Styre/styreleder ID** | Passport + proof of address for all directors |
| **Beneficial ownership** | Proof of who owns >25% (you, via Holding AS) |
| **Board resolution** | Minutes authorizing the account opening |
| **Financial statements** | Most recent annual accounts (arsregnskap) |

### Timeline

Corporate accounts take longer:
- Application: 30-60 min (more detailed forms)
- Verification: 3-10 business days (manual review)
- Some brokers require a phone/video call with compliance

### Which Brokers Support Corporate Accounts

| Broker | Corporate Support | Notes |
|--------|-------------------|-------|
| ICMarkets | Yes | Standard for business clients |
| Pepperstone | Yes | Good institutional onboarding |
| IBKR | Yes (Organization account) | Best for institutional entities |
| FP Markets | Yes | Standard process |
| Global Prime | Yes | Apply via business form |
| Darwinex | Yes (DarwinIA for funds) | More complex setup |

---

## Priority Order for Account Opening

| Priority | Broker | When | Why |
|----------|--------|------|-----|
| 1 | ICMarkets (2nd account) | When symbols start hitting max_lot on >20% of trades | Zero infrastructure change, immediate capacity increase |
| 2 | Pepperstone | Phase 2 ($2M+) or for counterparty diversification | Similar execution model, easy migration |
| 3 | IBKR | Phase 2-3 | Bridge to institutional, no lot limits, requires code work |
| 4 | Darwinex | Optional at any phase | Build track record for capital allocation |
| 5 | FP Markets / Global Prime | Phase 2+ if more broker diversity needed | Additional ECN options |

---

*Created: 2026-03-01*
*Verify all requirements directly with each broker before applying.*
