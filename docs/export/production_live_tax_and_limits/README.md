## Flint export: Tax reporting + broker lot limits

This folder is a **copy-ready export** of the pieces needed to bring:
- the **Norwegian tax reporting system** (reports + CLI), and
- **ICMarkets per-symbol max lot / volume constraints**

into a separate “production live” repo.

### What’s included

#### Tax reporting (production-ready)
- `src/flint/tax/` — tax pipeline (trade loading → Norges Bank FX rates → NOK conversion → JSON/CSV/TXT reports)
- `scripts/reporting/generate_tax_report.py` — CLI entry point
- `src/flint/paths.py` — path SSOT used by tax generator (output + cache dirs)
- `docs/reporting/TAX_REPORTING_SYSTEM.md` — full usage + output format documentation
- `docs/scale-up/en/TAX_PLANNING_NORWAY.md` — background tax planning doc

#### Broker constraints / max lots (ICMarkets)
- `data/meta/symbol_specifications.json` — extracted MT5 broker symbol specs (includes `volume_min`, `volume_max`, `volume_step`)
- `src/flint/market_mechanics.py` — SSOT helpers:
  - `get_broker_volume_min(symbol)` / `get_broker_volume_max(symbol)`
  - `get_max_lot(symbol)` hardcoded fallback values (plus notes)
- `docs/TRADING_RULES_SSOT.md` — “max lot cycling” rule behavior (conceptual rules)
- `src/flint/position_state.py` — position state including `max_lots_per_symbol` + max-lot lifecycle phases

### Max lot SSOT (recommended)

- **Primary truth (live / broker-validated):**
  - `data/meta/symbol_specifications.json` → `volume_max`
- **Fallback / guardrails (code-level):**
  - `src/flint/market_mechanics.py` → `MAX_LOT_SIZES`

In live execution, prefer MT5-provided values when available; keep hardcoded
fallbacks to prevent order rejection if broker metadata is unavailable.

### Quick usage

From the target repo root (after copying this folder’s contents into place):

```bash
python scripts/reporting/generate_tax_report.py --year 2026
python scripts/reporting/generate_tax_report.py --year 2026 --account 52742894
python scripts/reporting/generate_tax_report.py --year 2026 --no-archives
```

