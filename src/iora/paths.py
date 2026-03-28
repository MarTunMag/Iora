"""
Central path manager for the Iora trading system.

Single source of truth for all project paths. Every module that needs
a filesystem path should import from here instead of computing its own.

Works reliably whether the package is:
- Installed editable (pip install -e .)
- Imported via sys.path.insert from scripts
- Used in pytest
"""

from pathlib import Path

# Derive project root from this file's location: src/iora/paths.py -> src/ -> C:\Iora
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Data ──────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"  # OHLCV parquet files
META_DIR = DATA_DIR / "meta"  # manifest, symbol specs, etc.
WAREHOUSE_DIR = DATA_DIR / "warehouse"  # flat parquet (data_store format)

# ── Config ────────────────────────────────────────────────
CONFIG_DIR = PROJECT_ROOT / "config"
SETTINGS_FILE = CONFIG_DIR / "settings.yml"

# ── Output ────────────────────────────────────────────────
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"
