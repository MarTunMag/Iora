"""
Transaction Cost Calculator for Flint backtesting.

Calculates realistic trading costs including spread, commission, and slippage.
Implements session-based spread multipliers and death zone penalties.

Adapted from Aris CostCalculator — removes YAML config dependency,
imports cost data directly from market_mechanics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from flint.backtest.market_mechanics import (
    COMMISSION_FREE_SYMBOLS,
    TYPICAL_SPREAD_PRICE,
    get_commission_per_lot,
    get_pip_size,
    get_pip_value_per_lot,
    get_slippage_pips,
    get_spread_pips,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session spread multipliers (relative to TYPICAL_SPREAD_PRICE)
# ---------------------------------------------------------------------------
SESSION_MULTIPLIERS: dict[str, float] = {
    "overlap": 0.8,   # London/NY overlap 12:00-16:00 UTC — tightest
    "london": 1.0,    # London 07:00-12:00 UTC — baseline
    "ny": 1.2,        # New York 16:00-21:00 UTC — slightly wider
    "asian": 1.5,     # Asian 01:00-07:00 UTC — widest regular
}

# Death zone: 23:00-01:00 UTC — rollover, extreme spread widening
DEATH_ZONE_MULTIPLIER: float = 10.0

# Default slippage fallback (used only if get_slippage_pips not available)
_FALLBACK_SLIPPAGE_PIPS: float = 0.5

# ICMarkets commission per side per standard lot (USD)
COMMISSION_PER_SIDE: float = 3.50


# ---------------------------------------------------------------------------
# CostBreakdown dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Full cost breakdown for a single trade entry."""

    spread_price: float      # spread in price units (same as instrument price)
    spread_pips: float       # spread converted to pips
    commission_dollars: float # round-turn commission in USD
    commission_pips: float   # commission expressed in pips
    slippage_price: float    # estimated slippage in price units
    total_pips: float        # spread_pips + commission_pips + slippage_pips
    total_dollars: float     # total cost in USD


# ---------------------------------------------------------------------------
# CostCalculator
# ---------------------------------------------------------------------------

class CostCalculator:
    """
    Calculate transaction costs for backtesting.

    Features:
    - Research-validated TYPICAL_SPREAD_PRICE (with ~50 % buffer)
    - Session-based spread multipliers (overlap/london/NY/asian)
    - Death zone penalty (23:00-01:00 UTC = 10x spread)
    - CEILING rounding for ICMarkets commission ($3.50/side/lot)
    - Commission-free indices (cost embedded in spread)
    - Optional slippage estimate

    Example::

        calc = CostCalculator("EURUSD")
        cost = calc.calculate_total_cost(
            timestamp=pd.Timestamp("2024-01-15 14:30"),
            position_size=0.01,
        )
        print(f"Total: {cost.total_pips:.2f} pips  (${cost.total_dollars:.2f})")
    """

    def __init__(self, symbol: str) -> None:
        self.symbol: str = symbol.upper()

        # Symbol parameters from market_mechanics (single source of truth)
        self.pip_size: float = get_pip_size(self.symbol)
        self.pip_value_per_lot: float = get_pip_value_per_lot(self.symbol)

        # Base spread in price units — prefer TYPICAL_SPREAD_PRICE
        if self.symbol in TYPICAL_SPREAD_PRICE:
            self.base_spread_price: float = TYPICAL_SPREAD_PRICE[self.symbol]
        else:
            # Fallback: convert pip-based spread to price units
            self.base_spread_price = get_spread_pips(self.symbol) * self.pip_size

        # Commission
        self.commission_per_side: float = (
            0.0 if self.symbol in COMMISSION_FREE_SYMBOLS else COMMISSION_PER_SIDE
        )

        # Slippage (price units) — per-symbol estimate
        self.slippage_price: float = get_slippage_pips(self.symbol) * self.pip_size

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_total_cost(
        self,
        timestamp: pd.Timestamp | datetime,
        position_size: float,
        include_slippage: bool = True,
    ) -> CostBreakdown:
        """
        Calculate total transaction cost for a trade.

        Args:
            timestamp: Trade entry time (UTC assumed).
            position_size: Position size in lots.
            include_slippage: Whether to include slippage estimate.

        Returns:
            CostBreakdown dataclass with full breakdown.
        """
        # Spread (price units, session-adjusted)
        spread_price = self.get_spread(timestamp)
        spread_pips = spread_price / self.pip_size if self.pip_size > 0 else 0.0

        # Commission (round-turn, USD)
        commission_dollars = self._calculate_commission_dollars(position_size)
        # Convert commission to pips
        if self.pip_value_per_lot > 0 and position_size > 0:
            commission_pips = commission_dollars / (self.pip_value_per_lot * position_size)
        else:
            commission_pips = 0.0

        # Slippage
        slippage_price = self.slippage_price if include_slippage else 0.0
        slippage_pips = slippage_price / self.pip_size if self.pip_size > 0 else 0.0

        # Totals
        total_pips = spread_pips + commission_pips + slippage_pips
        total_dollars = self._pips_to_dollars(total_pips, position_size)

        return CostBreakdown(
            spread_price=spread_price,
            spread_pips=spread_pips,
            commission_dollars=commission_dollars,
            commission_pips=commission_pips,
            slippage_price=slippage_price,
            total_pips=total_pips,
            total_dollars=total_dollars,
        )

    def get_spread(self, timestamp: pd.Timestamp | datetime) -> float:
        """
        Get session-adjusted spread in price units for *timestamp*.

        Session windows (UTC):
            - Death zone:  23:00 - 01:00  (10x multiplier)
            - Asian:       01:00 - 07:00  (1.5x)
            - London:      07:00 - 12:00  (1.0x — baseline)
            - Overlap:     12:00 - 16:00  (0.8x — tightest)
            - New York:    16:00 - 21:00  (1.2x)
            - Late NY:     21:00 - 23:00  (1.5x — treated as asian)

        Returns:
            Spread in price units (same as instrument price).
        """
        hour: int = timestamp.hour

        # Death zone: 23:00-01:00 UTC
        if hour >= 23 or hour < 1:
            return self.base_spread_price * DEATH_ZONE_MULTIPLIER

        # Session-based multipliers
        if 12 <= hour < 16:
            mult = SESSION_MULTIPLIERS["overlap"]
        elif 7 <= hour < 12:
            mult = SESSION_MULTIPLIERS["london"]
        elif 16 <= hour < 21:
            mult = SESSION_MULTIPLIERS["ny"]
        else:
            # 01:00-07:00 and 21:00-23:00
            mult = SESSION_MULTIPLIERS["asian"]

        return self.base_spread_price * mult

    def get_cost_summary(
        self,
        timestamp: pd.Timestamp | datetime,
        position_size: float = 0.01,
    ) -> str:
        """Return a human-readable cost summary string."""
        c = self.calculate_total_cost(timestamp, position_size)
        return (
            f"Cost Summary for {self.symbol}\n"
            f"Position Size: {position_size} lots\n"
            f"Timestamp: {timestamp}\n"
            f"\n"
            f"Breakdown:\n"
            f"  Spread:      {c.spread_pips:.2f} pips  (price: {c.spread_price:.6f})\n"
            f"  Commission:  {c.commission_pips:.2f} pips  (${c.commission_dollars:.2f})\n"
            f"  Slippage:    {c.slippage_price / self.pip_size:.2f} pips\n"
            f"  {'─' * 37}\n"
            f"  Total:       {c.total_pips:.2f} pips\n"
            f"  In Dollars:  ${c.total_dollars:.2f}"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_commission_dollars(self, position_size: float) -> float:
        """
        Calculate round-turn commission in USD.

        ICMarkets charges $3.50 per side per standard lot, proportional
        to position size (0.01 lots = $0.035 per side = $0.07 round-turn).

        Commission-free symbols (indices) return 0.
        """
        if pd.isna(position_size) or position_size <= 0:
            logger.error("Invalid position size for commission: %s", position_size)
            return 0.0

        if self.commission_per_side == 0.0:
            return 0.0

        # Proportional commission: $3.50 per side per standard lot
        # Round-turn = 2 sides
        return self.commission_per_side * position_size * 2

    def _pips_to_dollars(self, pips: float, position_size: float) -> float:
        """Convert pips to USD for a given position size."""
        return pips * self.pip_value_per_lot * position_size


# ---------------------------------------------------------------------------
# Utility: session statistics
# ---------------------------------------------------------------------------

def calculate_session_stats(
    df: pd.DataFrame,
    calculator: CostCalculator,
) -> pd.DataFrame:
    """
    Calculate spread statistics by trading session.

    Args:
        df: DataFrame with a DatetimeIndex (UTC timestamps).
        calculator: CostCalculator instance for the symbol.

    Returns:
        DataFrame with columns: session, mean, min, max, count
        showing spread_pips distribution per session.
    """
    # Work on a copy to avoid mutating the caller's DataFrame
    tmp = df.copy()
    tmp["hour"] = tmp.index.hour
    tmp["spread_pips"] = tmp.index.map(
        lambda ts: calculator.get_spread(ts) / calculator.pip_size
        if calculator.pip_size > 0
        else 0.0
    )

    def _classify_session(hour: int) -> str:
        if hour >= 23 or hour < 1:
            return "Death Zone"
        if 12 <= hour < 16:
            return "Overlap"
        if 7 <= hour < 12:
            return "London"
        if 16 <= hour < 21:
            return "NY"
        return "Asian"

    tmp["session"] = tmp["hour"].map(_classify_session)

    session_stats: pd.DataFrame = (
        tmp.groupby("session")["spread_pips"]
        .agg(
            mean="mean",
            min="min",
            max="max",
            count="count",
        )
        .reset_index()
    )

    return session_stats
