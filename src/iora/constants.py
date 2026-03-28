"""
Canonical constants for the Flint trading system.

Single source of truth for timeframe ordering, candle types, and display config.
All other modules import from here — never define TF lists locally.
"""

from __future__ import annotations

# Canonical TF ordering: lowest to highest resolution
TF_ORDER: list[str] = ["M1", "M5", "M15", "H1", "H4", "D1", "W1", "MN1"]

# Engine TF order (no MN1 — engine doesn't process monthly bars)
ENGINE_TF_ORDER: list[str] = [tf for tf in TF_ORDER if tf != "MN1"]

# Display order: highest to lowest (for HTF sorting, overlay rendering)
TF_ORDER_HTF_FIRST: list[str] = list(reversed(TF_ORDER))

# Which TFs can be selected as base chart timeframe
BASE_TF_OPTIONS: list[str] = TF_ORDER[:]

# Which TFs appear in zone overlay toggles
ZONE_TF_OPTIONS: list[str] = TF_ORDER_HTF_FIRST[:]

# Which TFs appear in trendline overlay toggles (no MN1)
TL_TF_OPTIONS: list[str] = [tf for tf in TF_ORDER_HTF_FIRST if tf != "MN1"]

# Valid candle types
VALID_CANDLE_TYPES: set[str] = {"ohlc", "hollow", "ha", "line", "bars"}
VALID_HTF_CANDLE_TYPES: set[str] = {"ohlc", "ha"}

# ── Viewer constants (TF hierarchy, lookback, durations) ─────────────────

# Bar counts per TF — generous for replay scrollback, practical for HTFs
SMART_LOOKBACK: dict[str, int] = {
    "M1": 6000,
    "M5": 6000,
    "M15": 6000,
    "M30": 6000,
    "H1": 6000,
    "H4": 6000,
    "D1": 2000,
    "W1": 500,
    "MN1": 300,
}

# Parent TF for structure analysis (child → parent mapping)
TF_PARENT: dict[str, str] = {
    "M1": "M5", "M5": "M15", "M15": "H1", "M30": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1", "W1": "MN1",
}

# Derived: canonical child TF for each parent. M30 excluded (M15 wins as canonical H1 child).
TF_CHILD: dict[str, str] = {v: k for k, v in TF_PARENT.items() if k != "M30"}
# Result: {'M5':'M1', 'M15':'M5', 'H1':'M15', 'H4':'H1', 'D1':'H4', 'W1':'D1', 'MN1':'W1'}

# Approximate duration of each TF candle in seconds (for HTF candle rendering)
TF_SECONDS: dict[str, int] = {
    "12M": 365 * 86400, "6M": 182 * 86400, "3M": 91 * 86400,
    "MN1": 30 * 86400, "W1": 7 * 86400, "D1": 86400,
    "H4": 4 * 3600, "H1": 3600, "M30": 30 * 60,
    "M15": 900, "M5": 300, "M1": 60,
}


def get_sub_tf(tf: str) -> str | None:
    """Resolve sub-TF (one level below child). M30 special case: use M15 as sub (spec §2.1)."""
    sub = TF_CHILD.get(tf)
    if sub is None and tf == "M30":
        return "M15"
    return sub
