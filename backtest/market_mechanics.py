"""
Market Mechanics Module - Single Source of Truth

This module centralizes all market-specific configurations for:
- Minimum lot sizes
- Risk tiers
- Pip calculations
- Transaction costs

All modules (backtesting, live trading, optimization) MUST import from this module
to ensure consistent behavior across the entire Flint trading system.

Usage:
    from flint.backtest.market_mechanics import (
        get_min_lot,
        get_risk_percent,
        get_pip_size,
        get_pip_value_per_lot,
        get_spread_pips,
        calculate_position_size,
        AssetClass,
    )
"""

from __future__ import annotations

import json
import logging
import math
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from flint.paths import META_DIR

logger = logging.getLogger(__name__)


# =============================================================================
# BROKER SPECIFICATIONS (loaded from symbol_specifications.json)
# =============================================================================

@lru_cache(maxsize=1)
def _load_broker_specs() -> dict[str, Any]:
    """Load broker specs from symbol_specifications.json (cached)."""
    specs_path = META_DIR / "symbol_specifications.json"
    if specs_path.exists():
        with open(specs_path) as f:
            data = json.load(f)
        specs = data.get("symbols", {})
        logger.debug(f"Loaded broker specs for {len(specs)} symbols from {specs_path}")
        return specs

    logger.warning("symbol_specifications.json not found — using hardcoded defaults")
    return {}


def get_broker_spec(symbol: str, field: str, default: Any = None) -> Any:
    """Get a field from broker specs for a symbol.

    Args:
        symbol: Trading symbol (case-insensitive).
        field: Spec field name (e.g., 'spread', 'volume_min', 'tick_value').
        default: Fallback if symbol or field not found.

    Returns:
        Spec value or default.
    """
    specs = _load_broker_specs()
    sym_spec = specs.get(symbol.upper(), {})
    return sym_spec.get(field, default)


def get_broker_spread_price(symbol: str) -> float:
    """Get spread in price units from broker specs.

    The JSON 'spread' field is in points. Convert to price:
    spread_price = raw_spread * point.

    Returns:
        Spread in the same units as price (e.g., 0.00012 for EURUSD).
    """
    specs = _load_broker_specs()
    sym_spec = specs.get(symbol.upper(), {})
    if not sym_spec:
        # Fallback: hardcoded pips * pip_size
        return get_spread_pips(symbol) * get_pip_size(symbol)

    raw_spread = sym_spec.get("spread", 0)
    point = sym_spec.get("point", sym_spec.get("tick_size", 0))

    if raw_spread > 0 and point > 0:
        return raw_spread * point
    return get_spread_pips(symbol) * get_pip_size(symbol)


def get_broker_volume_min(symbol: str) -> float:
    """Get minimum lot size from broker specs."""
    val = get_broker_spec(symbol, "volume_min")
    if val is not None and val > 0:
        return val
    return get_min_lot(symbol)


def get_broker_volume_max(symbol: str) -> float:
    """Get maximum lot size from broker specs."""
    val = get_broker_spec(symbol, "volume_max")
    if val is not None and val > 0:
        return val
    return get_max_lot(symbol)


def get_broker_tick_value(symbol: str) -> float:
    """Get tick_value from broker specs (USD profit per tick per lot)."""
    val = get_broker_spec(symbol, "tick_value")
    if val is not None and val > 0:
        return val
    # Fallback: derive from pip_value and pip/tick ratio
    return get_pip_value_per_lot(symbol)


def get_cost_in_r(symbol: str, atr: float, sl_mult: float) -> float:
    """Compute round-trip transaction cost as a fraction of 1R.

    Cost = spread + slippage, all in price units.

    The bid-ask spread IS the full round-trip cost (entry at ask, exit at bid
    or vice versa), so we do NOT double it.

    Spread values come from TYPICAL_SPREAD_PRICE (research-validated ICMarkets
    averages with ~50% buffer), NOT from broker snapshot spreads.

    Args:
        symbol: Trading symbol.
        atr: ATR value at entry (same units as price).
        sl_mult: SL multiplier (e.g., 1.0 means SL = 1 ATR).

    Returns:
        Cost in R units (e.g., 0.05 means each trade costs 0.05R).
    """
    if atr <= 0 or sl_mult <= 0:
        return 0.0

    symbol_upper = symbol.upper()

    # Spread in price units — prefer research-validated typical values
    if symbol_upper in TYPICAL_SPREAD_PRICE:
        spread_price = TYPICAL_SPREAD_PRICE[symbol_upper]
    else:
        # Fallback: broker specs (snapshot, less reliable)
        spread_price = get_broker_spread_price(symbol)

    # Slippage in price units (per-symbol estimate)
    pip_size = get_pip_size(symbol_upper)
    slippage_price = get_slippage_pips(symbol_upper) * pip_size

    # Total cost in price units (spread is full round-trip, NOT doubled)
    cost_price = spread_price + slippage_price

    # SL distance in price units
    sl_distance = sl_mult * atr

    # Cost as fraction of 1R
    if sl_distance > 0:
        return cost_price / sl_distance
    return 0.0


# =============================================================================
# ASSET CLASSIFICATION
# =============================================================================


class AssetClass(Enum):
    """Asset class enumeration for categorization."""
    FOREX_MAJOR = "forex_major"
    FOREX_CROSS = "forex_cross"
    FOREX_JPY = "forex_jpy"
    METAL = "metal"
    INDEX = "index"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


# Symbol to asset class mapping
SYMBOL_ASSET_CLASS: dict[str, AssetClass] = {
    # Forex Majors (USD base or quote)
    "EURUSD": AssetClass.FOREX_MAJOR,
    "GBPUSD": AssetClass.FOREX_MAJOR,
    "AUDUSD": AssetClass.FOREX_MAJOR,
    "NZDUSD": AssetClass.FOREX_MAJOR,
    "USDCHF": AssetClass.FOREX_MAJOR,
    "USDCAD": AssetClass.FOREX_MAJOR,
    # Forex Crosses
    "EURGBP": AssetClass.FOREX_CROSS,
    "EURAUD": AssetClass.FOREX_CROSS,
    "EURCHF": AssetClass.FOREX_CROSS,
    "GBPAUD": AssetClass.FOREX_CROSS,
    "GBPNZD": AssetClass.FOREX_CROSS,
    "AUDNZD": AssetClass.FOREX_CROSS,
    "CADCHF": AssetClass.FOREX_CROSS,
    "USDMXN": AssetClass.FOREX_CROSS,
    "USDTRY": AssetClass.FOREX_CROSS,
    "USDZAR": AssetClass.FOREX_CROSS,
    # JPY Pairs (special pip size)
    "USDJPY": AssetClass.FOREX_JPY,
    "EURJPY": AssetClass.FOREX_JPY,
    "GBPJPY": AssetClass.FOREX_JPY,
    "CADJPY": AssetClass.FOREX_JPY,
    "AUDJPY": AssetClass.FOREX_JPY,
    "NZDJPY": AssetClass.FOREX_JPY,
    # Metals
    "XAUUSD": AssetClass.METAL,
    "XAGUSD": AssetClass.METAL,
    "XPTUSD": AssetClass.METAL,
    # Indices (ICMarkets CFDs)
    "US500": AssetClass.INDEX,
    "US30": AssetClass.INDEX,
    "USTEC": AssetClass.INDEX,
    "DE40": AssetClass.INDEX,
    "UK100": AssetClass.INDEX,
    "F40": AssetClass.INDEX,
    "HK50": AssetClass.INDEX,
    "JP225": AssetClass.INDEX,
    # Commodities (energy)
    "XBRUSD": AssetClass.COMMODITY,
    "XNGUSD": AssetClass.COMMODITY,
    "XTIUSD": AssetClass.COMMODITY,
    # Crypto
    "BTCUSD": AssetClass.CRYPTO,
    "ETHUSD": AssetClass.CRYPTO,
}


def get_asset_class(symbol: str) -> AssetClass:
    """Get the asset class for a symbol.

    Args:
        symbol: Trading symbol (e.g., 'EURUSD', 'XAUUSD')

    Returns:
        AssetClass enum value
    """
    symbol = symbol.upper()
    if symbol in SYMBOL_ASSET_CLASS:
        return SYMBOL_ASSET_CLASS[symbol]

    # Fallback detection
    if symbol.endswith("JPY"):
        return AssetClass.FOREX_JPY
    if symbol.startswith("XAU") or symbol.startswith("XAG") or symbol.startswith("XPT"):
        return AssetClass.METAL
    if symbol.startswith("XBR") or symbol.startswith("XNG") or symbol.startswith("XTI"):
        return AssetClass.COMMODITY
    if symbol in ["BTC", "ETH"] or "BTC" in symbol or "ETH" in symbol:
        return AssetClass.CRYPTO

    return AssetClass.FOREX_MAJOR  # Default


# =============================================================================
# MINIMUM LOT SIZES
# =============================================================================

# ICMarkets minimum lot sizes by symbol
MIN_LOT_SIZES: dict[str, float] = {
    # Indices require 0.1 minimum lot
    "US500": 0.1,
    "US30": 0.1,
    "USTEC": 0.1,
    "DE40": 0.1,
    "UK100": 0.1,
    "F40": 0.1,
    "HK50": 0.1,
    "JP225": 0.1,
    # All others use 0.01
}

DEFAULT_MIN_LOT = 0.01

# =============================================================================
# MAXIMUM LOT SIZES (Per-Symbol Broker Limits)
# =============================================================================

# ICMarkets maximum lot sizes by symbol
# CRITICAL: These must match broker limits to prevent order rejections
MAX_LOT_SIZES: dict[str, float] = {
    # Forex Majors - high liquidity
    "EURUSD": 200.0,
    "GBPUSD": 200.0,
    "USDJPY": 200.0,
    # Forex Crosses - medium liquidity
    "EURJPY": 100.0,
    "GBPJPY": 100.0,
    "NZDUSD": 50.0,
    # Metals
    "XAUUSD": 100.0,
    "XAGUSD": 50.0,
    # Crypto - CRITICAL: Broker limit is 10, not 100!
    "BTCUSD": 10.0,
    "ETHUSD": 10.0,
    # Forex Crosses
    "EURGBP": 100.0,
    "EURAUD": 100.0,
    "GBPAUD": 100.0,
    "NZDJPY": 100.0,
    "CADJPY": 100.0,
    "AUDJPY": 100.0,
    "AUDNZD": 100.0,
    "CADCHF": 100.0,
    "GBPNZD": 100.0,
    "EURCHF": 100.0,
    # Exotics - lower liquidity
    "USDMXN": 50.0,
    "USDTRY": 50.0,
    "USDZAR": 50.0,
    # Indices
    "US500": 100.0,
    "USTEC": 100.0,
    "US30": 100.0,
    "DE40": 50.0,
    "UK100": 50.0,
    "F40": 50.0,
    "HK50": 50.0,
    "JP225": 50.0,
    # Additional metals / commodities
    "XPTUSD": 50.0,
    "XNGUSD": 200.0,
}

DEFAULT_MAX_LOT = 100.0  # Default maximum position size


def get_min_lot(symbol: str) -> float:
    """Get the minimum lot size for a symbol.

    ICMarkets enforces:
    - 0.1 lot minimum for indices (US500, US30, USTEC, DE40, UK100)
    - 0.01 lot minimum for forex, metals, crypto

    Args:
        symbol: Trading symbol

    Returns:
        Minimum lot size (0.01 or 0.1)
    """
    return MIN_LOT_SIZES.get(symbol.upper(), DEFAULT_MIN_LOT)


def get_max_lot(symbol: str | None = None) -> float:
    """Get maximum lot size for a symbol.

    CRITICAL: Per-symbol limits prevent order rejections from broker.
    For example, BTCUSD has a broker limit of 10 lots, not 100.

    Args:
        symbol: Trading symbol (optional for backwards compatibility)

    Returns:
        Maximum lot size for the symbol
    """
    if symbol is None:
        return DEFAULT_MAX_LOT
    return MAX_LOT_SIZES.get(symbol.upper(), DEFAULT_MAX_LOT)


# =============================================================================
# RISK TIERS (3-Tier Allocation — Updated 2026-03-01)
# =============================================================================

# 3-Tier Risk Allocation (2026-03-01)
#
# Based on loss correlation analysis (docs/reference/RISK_ALLOCATION_ANALYSIS.md):
#   - Forex MDD 2.2x higher than indices (4.87% vs 2.25%)
#   - JPY cluster 63-68% co-occurring loss correlation
#   - Only 9 extreme losses (>-1.5R) out of 4,436 total — all forex
#
# Tier 1 (1.0%):  Low MDD, low correlation — Indices + Crypto
# Tier 2 (0.75%): Moderate MDD or correlation — Metals + US30 + EURJPY
# Tier 3 (0.5%):  High MDD + high correlation — JPY pairs + GBPUSD, EURUSD, NZDUSD
#
# Total risk exposure: 10.5% (vs 14.0% uniform)
# Worst-case fleet DD reduction: ~40%
#
RISK_TIERS: dict[AssetClass, float] = {
    AssetClass.FOREX_MAJOR: 0.005,   # 0.5% - Tier 3: High MDD forex (GBPUSD, EURUSD, NZDUSD)
    AssetClass.FOREX_CROSS: 0.005,   # 0.5% - Tier 3: Default for crosses
    AssetClass.FOREX_JPY: 0.005,     # 0.5% - Tier 3: JPY cluster (highest correlation)
    AssetClass.METAL: 0.0075,        # 0.75% - Tier 2: Moderate MDD
    AssetClass.INDEX: 0.010,         # 1.0% - Tier 1: Low MDD, low correlation
    AssetClass.CRYPTO: 0.010,        # 1.0% - Tier 1: Low correlation (weekend-isolated)
    AssetClass.COMMODITY: 0.0075,    # 0.75% - Tier 2: Energy commodities
}

# Symbol-specific risk overrides (deviation from asset class tier)
# See docs/reference/RISK_ALLOCATION_ANALYSIS.md for full rationale
RISK_OVERRIDES: dict[str, float] = {
    # Tier 2 overrides (0.75%): symbols that differ from their asset class default
    "US30": 0.0075,     # Index but Tier 2: max loss -1.329R (highest among indices)
    "EURJPY": 0.0075,   # JPY but Tier 2: MDD -2.6% (lower than other JPY pairs)
}


def get_risk_percent(symbol: str, ignore_overrides: bool = False) -> float:
    """Get the risk percentage for a symbol.

    3-Tier Allocation (2026-03-01):
      Tier 1 (1.0%): BTCUSD, US500, DE40, USTEC, UK100
      Tier 2 (0.75%): XAUUSD, XAGUSD, US30, EURJPY
      Tier 3 (0.5%): USDJPY, GBPUSD, GBPJPY, EURUSD, NZDUSD

    See docs/reference/RISK_ALLOCATION_ANALYSIS.md for rationale.

    Args:
        symbol: Trading symbol
        ignore_overrides: If True, skip RISK_OVERRIDES and use tier-based risk.
                         Used by backtest engine to ensure all symbols can trade.

    Returns:
        Risk percentage as decimal (e.g., 0.010 for 1.0%)
    """
    if not ignore_overrides and symbol in RISK_OVERRIDES:
        return RISK_OVERRIDES[symbol]

    asset_class = get_asset_class(symbol)
    return RISK_TIERS.get(asset_class, 0.005)


# =============================================================================
# PIP CALCULATIONS
# =============================================================================

# Pip sizes by symbol (the price movement that equals 1 pip)
PIP_SIZES: dict[str, float] = {
    # Forex Majors (4 decimal places, pip = 0.0001)
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "AUDUSD": 0.0001,
    "NZDUSD": 0.0001,
    "USDCHF": 0.0001,
    "USDCAD": 0.0001,
    "EURGBP": 0.0001,
    # JPY Pairs (2 decimal places, pip = 0.01)
    "USDJPY": 0.01,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
    "CADJPY": 0.01,
    "AUDJPY": 0.01,
    "NZDJPY": 0.01,
    # Forex Crosses (additional)
    "EURCHF": 0.0001,
    "EURAUD": 0.0001,
    "GBPAUD": 0.0001,
    "GBPNZD": 0.0001,
    "AUDNZD": 0.0001,
    "CADCHF": 0.0001,
    # Exotics
    "USDMXN": 0.0001,
    "USDTRY": 0.0001,
    "USDZAR": 0.0001,
    # Metals
    "XAUUSD": 0.01,    # Gold: 1 cent = 1 pip
    "XAGUSD": 0.001,   # Silver: 0.1 cent = 1 pip
    "XPTUSD": 0.01,    # Platinum: 1 cent = 1 pip (like gold)
    # Indices
    "US500": 0.1,      # S&P 500
    "US30": 1.0,       # Dow Jones
    "USTEC": 0.1,      # Nasdaq 100
    "DE40": 0.1,       # DAX
    "UK100": 0.1,      # FTSE 100
    "F40": 0.1,        # CAC 40
    "HK50": 0.1,       # Hang Seng
    "JP225": 1.0,      # Nikkei 225
    # Commodities
    "XTIUSD": 0.01,    # WTI Crude: 1 cent = 1 pip
    "XBRUSD": 0.01,    # Brent Crude: 1 cent = 1 pip
    "XNGUSD": 0.0001,  # Natural Gas: 4 decimal places
    # Crypto
    "BTCUSD": 0.01,    # Bitcoin: 1 cent = 1 pip
    "ETHUSD": 0.01,    # Ethereum: 1 cent = 1 pip
}


def get_pip_size(symbol: str) -> float:
    """Get the pip size (smallest price increment considered a pip) for a symbol.

    Args:
        symbol: Trading symbol

    Returns:
        Pip size (e.g., 0.0001 for EURUSD, 0.01 for USDJPY)
    """
    symbol = symbol.upper()
    if symbol in PIP_SIZES:
        return PIP_SIZES[symbol]

    # Fallback
    if symbol.endswith("JPY"):
        return 0.01
    return 0.0001


# Pip value per standard lot (USD profit per pip movement per lot)
PIP_VALUES_PER_LOT: dict[str, float] = {
    # Forex Majors - $10 per pip per lot
    "EURUSD": 10.0,
    "GBPUSD": 10.0,
    "AUDUSD": 10.0,
    "NZDUSD": 10.0,
    "USDCHF": 10.0,  # Approximately, varies with rate
    "USDCAD": 7.50,  # Approximately, varies with rate
    "EURGBP": 12.50, # GBP-denominated, varies
    # JPY Pairs - ~$6.50 per pip per lot (varies with USDJPY rate)
    "USDJPY": 6.50,
    "EURJPY": 6.50,
    "GBPJPY": 6.50,
    "CADJPY": 6.50,
    "AUDJPY": 6.50,
    "NZDJPY": 6.50,
    # Metals
    "XAUUSD": 1.0,   # $1 per pip per lot (100 oz)
    "XAGUSD": 5.0,   # $5 per pip per lot (5000 oz)
    # Indices - $1 per point per lot (ICMarkets CFD)
    # Note: pip_size=0.1 means $0.10 per pip, but position sizing
    # errors cancel with P&L calculation for correct results
    "US500": 1.0,
    "US30": 1.0,
    "USTEC": 1.0,
    "DE40": 1.0,     # EUR-denominated
    "UK100": 1.0,    # GBP-denominated
    # Additional indices
    "F40": 1.0,      # CAC 40: ~€1 per 0.01 move per lot ≈ $1.08, use 1.0
    "HK50": 1.30,    # Hang Seng: ~$1.28 per 0.01 move per lot
    "JP225": 6.70,   # Nikkei: ~$6.67 per 1.0 move per lot
    # Additional metals
    "XPTUSD": 0.10,  # Platinum: $0.10 per 0.01 per lot
    # Commodities
    "XTIUSD": 1.0,   # WTI: $1 per pip per lot
    "XBRUSD": 1.0,   # Brent: $1 per pip per lot
    "XNGUSD": 10.0,  # Natural Gas: ~$10 per 0.001 per lot
    # Additional forex crosses
    "EURCHF": 10.0,  # CHF-denominated, ~$10
    "EURAUD": 6.50,  # AUD-denominated, varies
    "GBPAUD": 6.50,  # AUD-denominated, varies
    "GBPNZD": 6.00,  # NZD-denominated, varies
    "AUDNZD": 6.00,  # NZD-denominated, varies
    "CADCHF": 10.0,  # CHF-denominated, ~$10
    # Exotics (quote currency varies, approximate USD equivalents)
    "USDMXN": 0.55,  # MXN-denominated, ~$0.55 per pip per lot
    "USDTRY": 0.30,  # TRY-denominated, ~$0.30 per pip per lot
    "USDZAR": 0.55,  # ZAR-denominated, ~$0.55 per pip per lot
    # Crypto - 1 lot = 1 unit (1 BTC or 1 ETH)
    # For 1 lot: $1 price move = $1 P&L, and pip=0.01, so pip_value = 0.01
    "BTCUSD": 0.01,  # $0.01 per pip per lot (1 BTC contract, pip=$0.01)
    "ETHUSD": 0.01,  # $0.01 per pip per lot (1 ETH contract, pip=$0.01)
}


def get_pip_value_per_lot(symbol: str) -> float:
    """Get the USD value per pip per standard lot.

    This is crucial for position sizing:
    Position = Risk($) / (Stop(pips) x pip_value_per_lot)

    Args:
        symbol: Trading symbol

    Returns:
        USD per pip per lot
    """
    symbol = symbol.upper()
    if symbol in PIP_VALUES_PER_LOT:
        return PIP_VALUES_PER_LOT[symbol]

    # Fallback
    if symbol.endswith("JPY"):
        return 6.50
    return 10.0


# =============================================================================
# TRANSACTION COSTS
# =============================================================================

# Spread in pips by symbol (ICMarkets Raw Spread, typical values)
# NOTE: For cost calculation, prefer TYPICAL_SPREAD_PRICE below (avoids pip conversion).
SPREADS_PIPS: dict[str, float] = {
    "EURUSD": 0.1,
    "GBPUSD": 0.2,
    "USDJPY": 0.2,
    "AUDUSD": 0.2,
    "NZDUSD": 0.3,
    "USDCHF": 0.2,
    "USDCAD": 0.3,
    "EURGBP": 0.3,
    "EURJPY": 0.4,
    "GBPJPY": 0.5,
    "CADJPY": 0.4,
    "XAUUSD": 1.0,    # 10 cents
    "XAGUSD": 2.0,    # 0.2 cents
    "US500": 0.4,
    "US30": 1.5,
    "USTEC": 1.0,
    "DE40": 1.0,
    "UK100": 1.0,
    "F40": 1.5,
    "HK50": 8.0,
    "JP225": 9.0,
    # Forex crosses (additional)
    "EURCHF": 0.6,
    "EURAUD": 1.0,
    "GBPAUD": 1.5,
    "GBPNZD": 2.5,
    "AUDNZD": 1.5,
    "CADCHF": 1.0,
    "AUDJPY": 0.5,
    "NZDJPY": 0.6,
    # Exotics
    "USDMXN": 50.0,
    "USDTRY": 100.0,
    "USDZAR": 80.0,
    # Metals
    "XPTUSD": 6.0,
    # Commodities
    "XTIUSD": 0.5,
    "XBRUSD": 0.5,
    "XNGUSD": 4.0,
    # Crypto
    "BTCUSD": 10.0,   # ~$10 spread
    "ETHUSD": 5.0,
}

# =============================================================================
# TYPICAL SPREADS IN PRICE UNITS (Research-Validated)
# =============================================================================
#
# Source: ICMarkets Raw Spread account avg spreads (icmarkets.com, bestbrokers.com,
#         compareforexbrokers.com, myfxbook.com) — researched 2026-03-08.
#
# Values include ~50% buffer over average to be conservative for backtesting.
# The user prefers slightly higher costs in training for more robust live signals.
#
# Units: same as instrument price (e.g., 0.00005 for GBPUSD = $0.00005 per unit).
# This avoids pip conversion issues across different instrument types.
#
TYPICAL_SPREAD_PRICE: dict[str, float] = {
    # --- Forex Majors (avg raw spread -> buffered) ---
    "EURUSD": 0.00003,   # avg 0.02 pips, buffered ~0.3 pips
    "GBPUSD": 0.00005,   # avg 0.23 pips, buffered ~0.5 pips
    "USDJPY": 0.003,     # avg 0.14 pips, buffered ~0.3 pips
    "AUDUSD": 0.00003,   # avg 0.03 pips, buffered ~0.3 pips
    "NZDUSD": 0.00007,   # avg 0.38 pips, buffered ~0.7 pips
    "USDCHF": 0.00004,   # avg 0.19 pips, buffered ~0.4 pips
    "USDCAD": 0.00005,   # avg 0.25 pips, buffered ~0.5 pips
    # --- Forex Crosses ---
    "EURGBP": 0.00005,   # avg 0.27 pips, buffered ~0.5 pips
    "EURCHF": 0.00010,   # avg 0.61 pips, buffered ~1.0 pips
    "EURAUD": 0.00013,   # avg 0.80 pips, buffered ~1.3 pips
    "GBPAUD": 0.00016,   # avg 1.06 pips, buffered ~1.6 pips
    "GBPNZD": 0.00028,   # avg 1.98 pips, buffered ~2.8 pips
    "AUDNZD": 0.00015,   # avg 1.0 pips, buffered ~1.5 pips
    "CADCHF": 0.00010,   # avg 0.6 pips, buffered ~1.0 pips
    # --- Exotics (wide spreads) ---
    "USDMXN": 0.0050,    # avg ~35 pips, buffered ~50 pips
    "USDTRY": 0.0100,    # avg ~70 pips, buffered ~100 pips
    "USDZAR": 0.0080,    # avg ~55 pips, buffered ~80 pips
    # --- JPY Pairs (spread in yen) ---
    "EURJPY": 0.005,     # avg 0.30 pips, buffered ~0.5 pips
    "GBPJPY": 0.013,     # avg 0.82 pips, buffered ~1.3 pips
    "USDJPY": 0.003,     # (duplicate, kept for clarity)
    "CADJPY": 0.008,     # avg 0.48 pips, buffered ~0.8 pips
    "AUDJPY": 0.008,     # avg 0.50 pips, buffered ~0.8 pips
    "NZDJPY": 0.010,     # avg 0.60 pips, buffered ~1.0 pips
    # --- Metals (spread in USD) ---
    "XAUUSD": 0.20,      # avg ~$0.09, buffered ~$0.20 (20 cents/oz)
    "XAGUSD": 0.04,      # avg ~$0.03, buffered ~$0.04 (4 cents/oz)
    "XPTUSD": 6.00,      # avg ~$4.75, buffered ~$6.00 (HIGH: thin market)
    # --- Indices (spread in index points, commission-free) ---
    "US500": 0.80,       # avg 0.49 pts, buffered ~0.8 pts
    "US30": 2.00,        # avg 1.41 pts, buffered ~2.0 pts
    "USTEC": 2.50,       # avg 1.81 pts, buffered ~2.5 pts
    "DE40": 2.00,        # avg 1.34 pts, buffered ~2.0 pts
    "UK100": 3.00,       # avg 2.13 pts, buffered ~3.0 pts
    "F40": 1.50,         # avg 0.75 pts, buffered ~1.5 pts
    "HK50": 12.00,       # avg 8.17 pts, buffered ~12.0 pts
    "JP225": 12.00,      # avg 8.86 pts, buffered ~12.0 pts
    # --- Commodities (spread in USD) ---
    "XTIUSD": 0.05,      # avg $0.034, buffered ~$0.05 (WTI crude)
    "XBRUSD": 0.05,      # avg $0.034, buffered ~$0.05 (Brent crude)
    "XNGUSD": 0.006,     # avg $0.004, buffered ~$0.006 (natural gas)
    # --- Crypto (spread in USD) ---
    "BTCUSD": 15.00,     # avg $12.01, buffered ~$15.00
    "ETHUSD": 4.00,      # avg $2.90, buffered ~$4.00
}

# Commission per lot round-turn (both sides)
COMMISSION_PER_LOT: float = 7.0  # $7 round-turn ($3.50 per side)

# Per-symbol slippage estimates in pips (round-trip)
SLIPPAGE_PIPS: dict[str, float] = {
    # Forex majors — tight
    "EURUSD": 0.3, "GBPUSD": 0.4, "USDJPY": 0.3, "AUDUSD": 0.4,
    "USDCAD": 0.4, "USDCHF": 0.4, "NZDUSD": 0.5,
    # Forex crosses — slightly wider
    "EURGBP": 0.5, "EURJPY": 0.5, "GBPJPY": 0.7, "EURCHF": 0.5,
    "EURAUD": 0.6, "GBPAUD": 0.7, "GBPNZD": 0.8, "AUDNZD": 0.6,
    "CADCHF": 0.5, "CADJPY": 0.5, "AUDJPY": 0.5, "NZDJPY": 0.5,
    # Exotics — wider
    "USDMXN": 5.0, "USDTRY": 10.0, "USDZAR": 8.0,
    # Metals
    "XAUUSD": 1.0, "XAGUSD": 1.5, "XPTUSD": 1.0,
    # Indices — in points
    "US500": 0.3, "US30": 2.0, "USTEC": 1.0, "DE40": 1.0,
    "UK100": 1.0, "F40": 1.0, "JP225": 5.0, "HK50": 5.0,
    # Energy
    "XTIUSD": 0.03, "XBRUSD": 0.03, "XNGUSD": 0.003,
    # Crypto
    "BTCUSD": 5.0, "ETHUSD": 2.0,
}
DEFAULT_SLIPPAGE_PIPS: float = 0.5


def get_slippage_pips(symbol: str) -> float:
    """Get estimated slippage in pips for a symbol."""
    return SLIPPAGE_PIPS.get(symbol.upper(), DEFAULT_SLIPPAGE_PIPS)

# Commission-free symbols (cost embedded in spread)
COMMISSION_FREE_SYMBOLS: set[str] = {
    "US500", "US30", "USTEC", "DE40", "UK100", "F40", "HK50", "JP225",
}


def get_spread_pips(symbol: str) -> float:
    """Get the typical spread in pips for a symbol.

    Args:
        symbol: Trading symbol

    Returns:
        Spread in pips
    """
    return SPREADS_PIPS.get(symbol.upper(), 0.5)


def get_commission_per_lot(symbol: str) -> float:
    """Get commission per lot round-turn.

    Indices are commission-free (cost embedded in spread).

    Args:
        symbol: Trading symbol

    Returns:
        Commission in USD per lot
    """
    if symbol.upper() in COMMISSION_FREE_SYMBOLS:
        return 0.0
    return COMMISSION_PER_LOT


# =============================================================================
# POSITION SIZING
# =============================================================================

def calculate_position_size(
    balance: float,
    stop_distance_pips: float,
    symbol: str,
    risk_override: float | None = None,
) -> tuple[float, bool]:
    """Calculate position size based on risk management rules.

    Uses the formula:
    Position = Risk($) / (Stop(pips) x pip_value_per_lot)

    Enforces:
    - Minimum lot size (0.01 or 0.1 depending on symbol)
    - Maximum lot size (100)
    - Rounding to 2 decimal places (0.01 lot steps)

    Args:
        balance: Account balance in USD
        stop_distance_pips: Stop loss distance in pips
        symbol: Trading symbol
        risk_override: Optional override for risk percentage (decimal)

    Returns:
        Tuple of (position_size, is_valid)
        is_valid is False if position < min_lot
    """
    if stop_distance_pips <= 0 or balance <= 0:
        return 0.0, False

    # Get parameters
    risk_pct = risk_override if risk_override else get_risk_percent(symbol)
    pip_value = get_pip_value_per_lot(symbol)
    min_lot = get_min_lot(symbol)
    max_lot = get_max_lot(symbol)  # Per-symbol max lot (BTCUSD=10, etc.)

    # Calculate position
    risk_dollars = balance * risk_pct
    position = risk_dollars / (stop_distance_pips * pip_value)

    # Round to 2 decimal places (0.01 lot steps)
    position = round(position, 2)

    # Check minimum
    if position < min_lot:
        return position, False  # Invalid - below minimum

    # Cap at maximum
    if position > max_lot:
        position = max_lot

    return position, True


def calculate_position_size_mt5(
    balance: float,
    entry_price: float,
    stop_loss: float,
    symbol: str,
    mt5_symbol_info: Any,
    risk_override: float | None = None,
) -> tuple[float, bool, str]:
    """Calculate position size using MT5 symbol info (trade_tick_value, trade_tick_size).

    This is the CORRECT method for indices/CFDs where contract specifications
    differ from standard Forex pip calculations.

    Formula:
        price_distance = abs(entry - sl)
        ticks = price_distance / trade_tick_size
        risk_per_lot = ticks * trade_tick_value
        lots = risk_amount / risk_per_lot

    Args:
        balance: Account balance in USD
        entry_price: Entry price
        stop_loss: Stop loss price
        symbol: Trading symbol
        mt5_symbol_info: MT5 symbol_info_t object (from mt5.symbol_info())
        risk_override: Optional override for risk percentage (decimal)

    Returns:
        Tuple of (position_size, is_valid, error_message)
        is_valid is False if position < min_lot or calculation failed
    """
    if balance <= 0:
        return 0.0, False, "Invalid balance"

    if mt5_symbol_info is None:
        return 0.0, False, "MT5 symbol info not available"

    # Get risk percentage
    risk_pct = risk_override if risk_override else get_risk_percent(symbol)
    risk_dollars = balance * risk_pct

    # SECURITY: Defensive null/zero checks for MT5 symbol info properties
    # Broker can return None or 0 for these values in edge cases (market closed, symbol disabled)
    try:
        tick_value = getattr(mt5_symbol_info, "trade_tick_value", None)
        tick_size = getattr(mt5_symbol_info, "trade_tick_size", None)
        volume_min = getattr(mt5_symbol_info, "volume_min", None)
        volume_max = getattr(mt5_symbol_info, "volume_max", None)
        volume_step = getattr(mt5_symbol_info, "volume_step", None)
    except (AttributeError, TypeError) as e:
        return 0.0, False, f"MT5 symbol info access error: {e}"

    # Validate tick_value and tick_size (prevent division by zero)
    if tick_value is None or tick_size is None:
        return 0.0, False, f"MT5 returned None: tick_value={tick_value}, tick_size={tick_size}"

    if tick_size <= 0 or tick_value <= 0:
        return 0.0, False, f"Invalid tick_size={tick_size} or tick_value={tick_value}"

    # Validate volume parameters with safe defaults
    if volume_min is None or volume_min <= 0:
        volume_min = get_min_lot(symbol)  # Fallback to our config
    if volume_max is None or volume_max <= 0:
        volume_max = get_max_lot(symbol)  # Per-symbol max lot
    if volume_step is None or volume_step <= 0:
        volume_step = 0.01  # Safe default

    # Calculate price distance
    price_distance = abs(entry_price - stop_loss)
    if price_distance <= 0:
        return 0.0, False, "Invalid stop loss distance"

    # Calculate number of ticks
    ticks = price_distance / tick_size

    # Calculate risk per lot for this specific distance
    risk_per_lot = ticks * tick_value

    if risk_per_lot <= 0:
        return 0.0, False, f"Invalid risk_per_lot={risk_per_lot}"

    # Calculate position size
    lots = risk_dollars / risk_per_lot

    # Normalize to broker's volume step
    if volume_step > 0:
        # Round down to nearest step
        lots = math.floor(lots / volume_step) * volume_step
        # Round to appropriate decimals based on volume_step
        decimals = len(str(volume_step).split(".")[-1]) if "." in str(volume_step) else 0
        lots = round(lots, decimals)

    # Enforce min/max
    min_lot = max(volume_min, get_min_lot(symbol))
    max_lot_val = min(volume_max, get_max_lot(symbol))  # Per-symbol max lot

    if lots < min_lot:
        return lots, False, f"Position {lots:.2f} < min_lot {min_lot:.2f}"

    if lots > max_lot_val:
        lots = max_lot_val

    return lots, True, "OK"


def calculate_pnl_dollars(
    direction: int,
    entry_price: float,
    exit_price: float,
    lots: float,
    tick_value: float,
    tick_size: float,
) -> float:
    """Calculate P&L in USD using MT5 tick-based math.

    This is the SSOT for P&L calculation. Both live engine and any future
    reconciliation code should use this function.

    Formula:
        price_diff = (exit - entry) * direction
        ticks = price_diff / tick_size
        pnl = ticks * tick_value * lots

    Args:
        direction: 1 for LONG, -1 for SHORT.
        entry_price: Entry price.
        exit_price: Exit price.
        lots: Position size in lots.
        tick_value: MT5 trade_tick_value (USD per tick per lot).
        tick_size: MT5 trade_tick_size (price per tick).

    Returns:
        P&L in USD. Positive = profit, negative = loss.
    """
    if tick_size <= 0 or tick_value <= 0:
        return 0.0

    price_diff = (exit_price - entry_price) * direction
    ticks = price_diff / tick_size
    return ticks * tick_value * lots
