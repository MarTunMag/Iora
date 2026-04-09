"""
Central path manager for the Flint trading system.

Single source of truth for all project paths. Every module that needs
a filesystem path should import from here instead of computing its own.

Works reliably whether the package is:
- Installed editable (pip install -e .)
- Imported via sys.path.insert from scripts
- Used in pytest
"""

from pathlib import Path

# Derive project root from this file's location: src/flint/paths.py -> src/ -> C:\Flint
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Data ──────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"  # OHLCV parquet files
META_DIR = DATA_DIR / "meta"  # manifest, symbol specs, etc.
WAREHOUSE_DIR = DATA_DIR / "warehouse"  # flat parquet (data_store format)
CACHE_DIR = DATA_DIR / "cache"  # exchange rate cache, etc.
TRADES_DIR = DATA_DIR / "trades"  # future: trade execution logs

# ── Config ────────────────────────────────────────────────
CONFIG_DIR = PROJECT_ROOT / "config"
BROKER_CONFIG = CONFIG_DIR / "broker" / "accounts.yaml"
SETTINGS_FILE = CONFIG_DIR / "settings.yml"

# ── Output ────────────────────────────────────────────────
REPORTS_DIR = PROJECT_ROOT / "reports"  # tax reports, trade summaries
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

# ── Helpers ───────────────────────────────────────────────


def get_tax_report_dir(year: int) -> Path:
    """Get the directory for tax reports for a given year."""
    return REPORTS_DIR / "tax" / str(year)


def get_exchange_rate_cache_dir() -> Path:
    """Get the directory for cached Norges Bank exchange rates."""
    return CACHE_DIR / "norges_bank"
