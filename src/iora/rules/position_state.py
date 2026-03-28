"""
Position state tracker for the Rules layer.

Tracks open positions, lots, direction, max-lot state, and P&L.
Consumed by all rule modules to know current position context.

References: TRADING_RULES_SSOT.md sections 9c, 9d, 12.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class TradeMode(Enum):
    GROWTH = "growth"
    SCALP = "scalp"


class Direction(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class OpenTrade:
    """A single open trade within a position."""

    trade_id: int
    mode: TradeMode
    direction: Direction
    entry_price: float
    entry_time: pd.Timestamp
    lots: float
    sl_price: float
    tp_price: float | None = None
    rule_id: str = ""  # Which rule opened this trade


@dataclass
class PositionState:
    """
    Tracks all open trades and aggregate position state.

    This is mutable state that persists across bars.
    Rules read it to make entry/exit/add-on decisions.
    The trader layer mutates it when trades execute.
    """

    # All open trades
    trades: list[OpenTrade] = field(default_factory=list)

    # Trade ID counter
    _next_id: int = 0

    # Account state
    account_balance: float = 10_000.0  # Default, overridden by config
    risk_pct: float = 0.01  # 1% risk per trade

    # Broker limits (ICMarkets)
    max_lots_per_symbol: float = 100.0

    # Pip calculation (set per symbol)
    pip_size: float = 0.0001  # Default for most forex
    pip_value_per_lot: float = 10.0  # USD per pip per standard lot

    @property
    def growth_trades(self) -> list[OpenTrade]:
        return [t for t in self.trades if t.mode == TradeMode.GROWTH]

    @property
    def scalp_trades(self) -> list[OpenTrade]:
        return [t for t in self.trades if t.mode == TradeMode.SCALP]

    @property
    def net_direction(self) -> Direction:
        """Net direction of all open Growth trades."""
        growth = self.growth_trades
        if not growth:
            return Direction.FLAT
        return growth[0].direction  # All Growth trades same direction

    @property
    def total_lots(self) -> float:
        """Total lots across all open trades."""
        return sum(t.lots for t in self.trades)

    @property
    def growth_lots(self) -> float:
        return sum(t.lots for t in self.growth_trades)

    @property
    def scalp_lots(self) -> float:
        return sum(t.lots for t in self.scalp_trades)

    @property
    def at_max_lots(self) -> bool:
        return self.total_lots >= self.max_lots_per_symbol

    @property
    def growth_trade_count(self) -> int:
        """Number of open Growth trades."""
        return len(self.growth_trades)

    @property
    def max_lot_phase(self) -> str:
        """Current phase: 'building', 'cycling', 'full_scalp'."""
        if not self.at_max_lots:
            return "building"
        if self.growth_trade_count > 1:
            return "cycling"
        return "full_scalp"

    def worst_growth_trade(self, current_price: float) -> OpenTrade | None:
        """Growth trade furthest from current price -- candidate for rotation."""
        if not self.growth_trades:
            return None
        return max(self.growth_trades, key=lambda t: abs(t.entry_price - current_price))

    @property
    def is_flat(self) -> bool:
        return len(self.trades) == 0

    def calculate_lots(
        self, entry_price: float, sl_price: float
    ) -> float:
        """
        Calculate lot size for 1% risk.

        References: TRADING_RULES_SSOT.md section 12b.
        """
        risk_amount = self.account_balance * self.risk_pct
        sl_pips = abs(entry_price - sl_price) / self.pip_size
        if sl_pips <= 0:
            return 0.0
        lots = risk_amount / (sl_pips * self.pip_value_per_lot)
        # Cap at remaining capacity
        remaining = max(0.0, self.max_lots_per_symbol - self.total_lots)
        return min(lots, remaining)

    def open_trade(
        self,
        mode: TradeMode,
        direction: Direction,
        entry_price: float,
        entry_time: pd.Timestamp,
        sl_price: float,
        tp_price: float | None = None,
        lots: float | None = None,
        rule_id: str = "",
    ) -> OpenTrade | None:
        """
        Open a new trade. Returns the trade if opened, None if at max lots.
        If lots not specified, calculates from 1% risk.
        """
        if lots is None:
            lots = self.calculate_lots(entry_price, sl_price)
        if lots <= 0:
            return None

        trade = OpenTrade(
            trade_id=self._next_id,
            mode=mode,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            lots=lots,
            sl_price=sl_price,
            tp_price=tp_price,
            rule_id=rule_id,
        )
        self._next_id += 1
        self.trades.append(trade)
        return trade

    def close_trade(self, trade_id: int) -> OpenTrade | None:
        """Close a specific trade by ID. Returns the closed trade."""
        for i, t in enumerate(self.trades):
            if t.trade_id == trade_id:
                return self.trades.pop(i)
        return None

    def close_all(self, mode: TradeMode | None = None) -> list[OpenTrade]:
        """Close all trades, optionally filtered by mode."""
        if mode is None:
            closed = list(self.trades)
            self.trades.clear()
            return closed
        closed = [t for t in self.trades if t.mode == mode]
        self.trades = [t for t in self.trades if t.mode != mode]
        return closed

    def close_direction(self, direction: Direction) -> list[OpenTrade]:
        """Close all trades in a specific direction."""
        closed = [t for t in self.trades if t.direction == direction]
        self.trades = [t for t in self.trades if t.direction != direction]
        return closed

    def update_sl(self, trade_id: int, new_sl: float) -> bool:
        """
        Update SL for a trade. Only tightens (never loosens).

        References: TRADING_RULES_SSOT.md section 11b.
        """
        for t in self.trades:
            if t.trade_id == trade_id:
                if t.direction == Direction.LONG:
                    # For longs, SL moves UP (tighten = higher)
                    if new_sl > t.sl_price:
                        t.sl_price = new_sl
                        return True
                else:
                    # For shorts, SL moves DOWN (tighten = lower)
                    if new_sl < t.sl_price:
                        t.sl_price = new_sl
                        return True
                return False
        return False

    def trail_all_growth(self, new_sl: float) -> int:
        """Trail SL on all Growth trades. Returns count of trades updated."""
        count = 0
        for t in self.growth_trades:
            if self.update_sl(t.trade_id, new_sl):
                count += 1
        return count

    def check_sl_hits(self, bar_high: float, bar_low: float) -> list[OpenTrade]:
        """Check if any trades hit their SL on this bar. Returns hit trades."""
        hit = []
        for t in list(self.trades):
            if t.direction == Direction.LONG and bar_low <= t.sl_price:
                hit.append(t)
            elif t.direction == Direction.SHORT and bar_high >= t.sl_price:
                hit.append(t)
        for t in hit:
            self.trades.remove(t)
        return hit

    def check_tp_hits(
        self, bar_high: float, bar_low: float
    ) -> list[OpenTrade]:
        """Check if any trades hit their TP on this bar."""
        hit = []
        for t in list(self.trades):
            if t.tp_price is None:
                continue
            if t.direction == Direction.LONG and bar_high >= t.tp_price:
                hit.append(t)
            elif t.direction == Direction.SHORT and bar_low <= t.tp_price:
                hit.append(t)
        for t in hit:
            self.trades.remove(t)
        return hit
