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
    """Lightweight trade record for sweep results. No external deps."""

    trade_id: str
    symbol: str
    direction: int          # 1=LONG, -1=SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pips: float
    return_r: float         # P&L in R-multiples
    exit_reason: str
    sl_price: float
    tp_price: float
    zone_tf: str = ""
    signal_type: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pips > 0

    @property
    def holding_period(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time


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

        # Risk in pips for R-multiple
        risk_pips = abs(t["entry_price"] - t["sl_price"]) / pip_size
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
            return_r=return_r,
            exit_reason=t["exit_reason"],
            sl_price=t["sl_price"],
            tp_price=t["tp_price"],
            zone_tf=t.get("zone_tf", ""),
            signal_type=t.get("signal_type", ""),
        ))

    return records
