# Norwegian Tax Reporting System

**Status:** Live — generates Skatteetaten-compatible reports from trade ledger data
**Module:** `src/iki/tax/`
**CLI:** `python scripts/reporting/generate_tax_report.py --year 2026`
**Output:** `reports/tax/{year}/`

---

## Quick Start

```bash
# Generate tax report for 2026
python scripts/reporting/generate_tax_report.py --year 2026

# Filter to specific account
python scripts/reporting/generate_tax_report.py --year 2026 --account 52742894

# Exclude archived ledger directories
python scripts/reporting/generate_tax_report.py --year 2026 --no-archives

# Custom output directory
python scripts/reporting/generate_tax_report.py --year 2026 --output-dir reports/tax/custom/

# Verbose logging (shows API calls, trade counts, rate lookups)
python scripts/reporting/generate_tax_report.py --year 2026 -v
```

---

## Output Files

After running, the folder `reports/tax/{year}/` contains three files — everything your accountant needs:

```
reports/tax/2026/
  skatterapport_2026.txt    — Norwegian-language summary for accountant / Skatteetaten
  tax_trades_2026.csv       — One row per trade with NOK amounts (spreadsheet-friendly)
  tax_report_2026.json      — Full structured data (for accounting software import)
```

### skatterapport_2026.txt (Give this to your accountant)

Norwegian-language formatted report with 5 sections:

1. **SAMMENDRAG** — Total trades, wins/losses, gains/losses in NOK, commission, swap, estimated tax or loss carryforward
2. **SKATTEMELDINGEN** — Filing guidance: where to report ("Gevinst/tap ved realisasjon av andre finansielle produkter"), tax rate (22%), loss carryforward rules (skatteloven SS 14-6)
3. **PER SYMBOL** — Breakdown by trading instrument (BTCUSD, XAUUSD, etc.)
4. **PER MAANED** — Monthly P&L breakdown
5. **VALUTAKURSER** — Exchange rate source (Norges Bank), currency pair (USD/NOK), rate range used

### tax_trades_2026.csv (For verification / spreadsheet analysis)

One row per closed trade with columns:

| Column | Description |
|--------|-------------|
| exit_date | Date the trade closed |
| symbol | Trading instrument (e.g., BTCUSD) |
| direction | LONG or SHORT |
| position_size | Trade size in lots |
| entry_price, exit_price | Trade prices |
| exit_reason | TP_HIT, SL_HIT, TRAILING, EOD, COUNTER_SIGNAL, etc. |
| gross_pnl_usd | Gross P&L before costs (USD) |
| commission_usd | Trading commission (USD) |
| swap_usd | Overnight swap/rollover (USD) |
| net_pnl_usd | Net P&L after all costs (USD) |
| usd_nok_rate | Official Norges Bank USD/NOK rate used |
| rate_date | Business day the rate is from (may differ from exit_date for weekends) |
| gross_pnl_nok, commission_nok, swap_nok, net_pnl_nok | All amounts converted to NOK |

### tax_report_2026.json (Machine-readable, for software import)

```json
{
  "metadata": {
    "generated_at": "2026-03-01T13:20:50",
    "tax_year": 2026,
    "account_id": null,
    "exchange_rate_source": "Norges Bank",
    "currency_pair": "USD/NOK",
    "tax_rate": 0.22
  },
  "summary": { "total_trades": 390, "net_result_nok": -14812.08, ... },
  "per_symbol": { "BTCUSD": {...}, "DE40": {...}, ... },
  "per_month": { "2026-02": {...}, "2026-03": {...}, ... },
  "trades": [ { "trade_id": "...", "net_pnl_nok": ..., ... }, ... ]
}
```

---

## Architecture

### Data Flow

```
generate_tax_report.py --year 2026
         |
         v
   TaxReportGenerator(tax_year=2026)
         |
    +----|----+-----------+
    v         v           v
TradeLoader  NorgesBankClient  TaxCalculator
    |         |                |
    v         v                v
ledger/    Norges Bank API  Per-trade NOK
trades.json  + JSON cache    conversion
    |         |                |
    v         v                v
List[TaxTrade]  Dict[date,rate]  List[TaxTradeResult] + TaxSummary
                                       |
                              +--------|--------+
                              v        v        v
                           .json     .csv     .txt
                        (reports/tax/2026/)
```

### Module Structure

| Module | Path | Purpose |
|--------|------|---------|
| **NorgesBankClient** | `src/iki/tax/norges_bank.py` | Fetches USD/NOK rates from Norges Bank SDMX-JSON API |
| **TradeLoader** | `src/iki/tax/trade_loader.py` | Discovers accounts, loads closed trades from ledger files |
| **TaxCalculator** | `src/iki/tax/calculator.py` | Converts USD P&L to NOK, computes aggregates |
| **TaxReportGenerator** | `src/iki/tax/report_generator.py` | Orchestrates pipeline, writes JSON/CSV/TXT output |
| **CLI** | `scripts/reporting/generate_tax_report.py` | Command-line entry point |
| **Config** | `src/iki/config/__init__.py` | `get_tax_report_dir(year)`, `get_exchange_rate_cache_dir()` |

### Key Classes

**TaxTrade** — Normalized trade record loaded from ledger:
- trade_id, symbol, account_id, direction, entry/exit time+price, position_size
- gross_pnl_usd, commission_usd, swap_usd, net_pnl_usd, exit_reason

**TaxTradeResult** — TaxTrade enriched with NOK conversion:
- All TaxTrade fields + usd_nok_rate, rate_date, gross/commission/swap/net_pnl_nok

**TaxSummary** — Year-level aggregates:
- total/winning/losing trades, total gains/losses NOK, net result NOK
- total commission/swap NOK, estimated tax (22%) or loss carryforward
- per_symbol breakdown (Dict[str, SymbolSummary])
- per_month breakdown (Dict[str, MonthSummary])

---

## Exchange Rates

### Source
- **API:** Norges Bank SDMX-JSON (`data.norges-bank.no`)
- **Rate:** Daily official USD/NOK spot rate
- **Legal basis:** These are the rates Skatteetaten accepts for tax reporting

### Caching
- Cache location: `data/cache/norges_bank/usd_nok_{year}.json`
- Completed years (e.g., 2025): cached forever — rates don't change
- Current year: refetched if cache is >24 hours old
- Atomic writes to prevent corruption

### Weekend / Holiday Fallback
If a trade exits on a weekend or holiday (no rate published), the system walks backward up to 7 days to find the most recent business day rate. This is standard practice accepted by Skatteetaten.

Example: Trade exits Saturday March 7 → uses Friday March 6 rate.

---

## Trade Loading

### Sources Scanned
The loader discovers trades from:
- `data/live/execution/{account_type}_{account_id}/{symbol}/ledger/trades.json` (new structure)
- `data/live/accounts/{account_type}_{account_id}/{symbol}/ledger/trades.json` (legacy)
- `ledger_*_archive/` directories inside symbol dirs (if `--no-archives` not set)

### Filtering
- Only `status: "CLOSED"` trades are included
- Trades are assigned to tax year based on **exit_time** (not entry_time)
- Deduplicated by trade_id

### Null P&L Handling
- If `pnl_dollars` is null (pre-V7.3 archives): derived from `account_balance_after - account_balance_before`
- If `gross_pnl_dollars` is null: derived from `net_pnl + commission + abs(swap)`

---

## Tax Rules Applied

### Rate
- Forex/CFD gains: **22% alminnelig inntekt** (ordinary income)
- This is different from shares (37.84% with oppjusteringsfaktor)

### Reporting
- Report under: **"Gevinst/tap ved realisasjon av andre finansielle produkter"**
- Each trade converted to NOK at exit-date exchange rate
- Commission and swap deducted as costs

### Loss Carryforward
- If net result is negative: **loss carries forward indefinitely** (skatteloven SS 14-6)
- Reported as "Fradragsberettiget tap" in the skattemelding

### Gain Taxation
- If net result is positive: estimated tax = net_result * 0.22
- Actual tax may differ based on other income and deductions — consult regnskapsforer

---

## Handing the Folder to Your Accountant

### What to give them
1. The entire `reports/tax/2026/` folder (3 files)
2. Access to your Fiken/Tripletex accounting software (if set up)
3. List of additional deductions (VPS costs, hardware, software, internet)

### What they do with it
1. Review the `skatterapport_2026.txt` summary
2. Spot-check individual trades in the CSV if needed
3. Import the JSON into accounting software (or manually enter totals)
4. File the skattemelding with the correct amounts
5. Handle any additional deductions you provide

### What you do
1. Run the CLI command once per year (or quarterly for interim checks)
2. Review the summary output
3. Hand the folder to the accountant
4. Sign the skattemelding they prepare

---

## Tests

```bash
# Run all tax module tests
PYTHONPATH=src python -m pytest tests/unit/test_norges_bank.py tests/unit/test_tax_calculator.py -v
```

| Test File | Coverage |
|-----------|----------|
| `tests/unit/test_norges_bank.py` | SDMX-JSON parsing, weekend fallback, cache save/load/expiry, API mocking, error handling |
| `tests/unit/test_tax_calculator.py` | NOK conversion, gain/loss aggregation, 22% tax estimation, loss carryforward, per-symbol/month breakdown, null P&L derivation |

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `docs/scale-up/TAX_PLANNING_NORWAY.md` | Norwegian tax rules, entity structures, AS vs. individual comparison |
| `docs/scale-up/SKATTEPLANLEGGING_NORGE.md` | Same in Norwegian |
| `docs/scale-up/CORPORATE_EMPIRE_BLUEPRINT.md` | Corporate structure roadmap with recommended accounting firms |
| `docs/scale-up/SELSKAPSIMPERIET_PLAN.md` | Same in Norwegian |

---

*Created: 2026-03-01*
*Module: src/iki/tax/ | CLI: scripts/reporting/generate_tax_report.py*
*First report: 390 trades, 4 symbols, NOK -14,812.08 net (demo account)*
