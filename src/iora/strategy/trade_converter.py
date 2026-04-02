"""Convert strategy trade dicts to SweepTradeRecord objects.

Uses a lightweight SweepTradeRecord dataclass that has NO external
dependencies (no flint/backtest imports). This allows the sweep runner
to work without flint on PYTHONPATH.

For full PerformanceMetrics integration, use to_flint_records() which
requires flint to be importable.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# Pip sizes for common symbols (avoids flint dependency)
_PIP_SIZES: dict[str, float] = {}
_DEFAULT_PIP_SIZE = 0.0001
_JPY_PIP_SIZE = 0.01


def _get_pip_size(symbol: str) -> float:
    """Get pip size for a symbol without flint dependency."""
    symbol = symbol.upper()
    if symbol in _PIP_SIZES:
        return _PIP_SIZES[symbol]
    if symbol.endswith("JPY") or symbol in ("XAUUSD",):
        return _JPY_PIP_SIZE
    if symbol in ("DE40", "US30", "US500", "US100", "UK100", "JP225"):
        return 1.0
    if symbol in ("BTCUSD", "ETHUSD"):
        return 1.0
    return _DEFAULT_PIP_SIZE


@dataclass(frozen=True, slots=True)
class SweepTradeRecord:
    """Comprehensive trade record for sweep results. No external deps.

    Captures full entry context so post-hoc analysis can answer
    when, where, why, and how each trade won or lost.
    """

    # Core trade fields
    trade_id: str
    symbol: str
    direction: int          # 1=LONG, -1=SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pips: float
    risk_pips: float
    reward_pips: float
    return_r: float         # P&L in R-multiples
    rr_ratio: float         # Planned reward:risk
    exit_reason: str
    sl_price: float
    tp_price: float

    # Signal classification (WHY did we enter?)
    signal_type: str = ""   # "push", "reversal", "terminal", "normal"
    struct_cls: str = ""    # "BOS", "CHoCH", ""
    zone_tf: str = ""       # Entry zone timeframe
    parent_tf: str = ""     # Parent zone timeframe
    nesting_depth: int = 0
    opposing_nest: bool = False

    # Zone context (WHERE did we enter?)
    zone_top: float = 0.0
    zone_bottom: float = 0.0
    zone_is_push: bool = False
    zone_is_reversal: bool = False
    zone_is_terminal: bool = False
    zone_swing_cls: str = ""  # "HH", "LH", "HL", "LL"
    zone_count: int = 0

    @property
    def is_winner(self) -> bool:
        return self.pnl_pips > 0

    @property
    def holding_period(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time

    @property
    def direction_str(self) -> str:
        return "long" if self.direction == 1 else "short"


def convert_trades(
    trades: list[dict],
    symbol: str,
) -> list[SweepTradeRecord]:
    """Convert strategy result trade dicts to SweepTradeRecord objects.

    Args:
        trades: Trade dicts from StrategyResult.trades.
        symbol: Trading symbol.

    Returns:
        List of SweepTradeRecord objects.
    """
    pip_size = _get_pip_size(symbol)

    records: list[SweepTradeRecord] = []
    for i, t in enumerate(trades):
        direction_int = 1 if t["direction"] == "long" else -1
        pnl_pips = t["pnl_pips"]

        # Risk/reward from trade dict (already computed by strategy)
        risk_pips = t.get("risk_pips", 0.0)
        reward_pips = t.get("reward_pips", 0.0)
        rr_ratio = t.get("rr_ratio", 0.0)
        return_r = pnl_pips / risk_pips if risk_pips > 0 else 0.0

        records.append(SweepTradeRecord(
            trade_id=f"pz_{i:04d}",
            symbol=symbol,
            direction=direction_int,
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            pnl_pips=pnl_pips,
            risk_pips=risk_pips,
            reward_pips=reward_pips,
            return_r=return_r,
            rr_ratio=rr_ratio,
            exit_reason=t["exit_reason"],
            sl_price=t["sl_price"],
            tp_price=t["tp_price"],
            # Signal classification
            signal_type=t.get("signal_type", ""),
            struct_cls=t.get("struct_cls", ""),
            zone_tf=t.get("zone_tf", ""),
            parent_tf=t.get("parent_tf", ""),
            nesting_depth=t.get("nesting_depth", 0),
            opposing_nest=t.get("opposing_nest", False),
            # Zone context
            zone_top=t.get("zone_top", 0.0),
            zone_bottom=t.get("zone_bottom", 0.0),
            zone_is_push=t.get("zone_is_push", False),
            zone_is_reversal=t.get("zone_is_reversal", False),
            zone_is_terminal=t.get("zone_is_terminal", False),
            zone_swing_cls=t.get("zone_swing_cls", ""),
            zone_count=t.get("zone_count", 0),
        ))

    return records
