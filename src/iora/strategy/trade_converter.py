"""Convert strategy trade dicts to SweepTradeRecord objects.

Uses a lightweight SweepTradeRecord dataclass that has NO external
dependencies (no flint/backtest imports). This allows the sweep runner
to work without flint on PYTHONPATH.

For full PerformanceMetrics integration, use to_flint_records() which
requires flint to be importable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Spec-driven pip size lookup
# ---------------------------------------------------------------------------

_SPECS_PATH = Path(__file__).resolve().parents[3] / "config" / "symbol_specifications.json"
_spec_cache: dict[str, dict] | None = None


def _load_specs() -> dict[str, dict]:
    """Load symbol specifications from config/symbol_specifications.json."""
    global _spec_cache
    if _spec_cache is not None:
        return _spec_cache
    if _SPECS_PATH.exists():
        with open(_SPECS_PATH) as f:
            data = json.load(f)
        _spec_cache = data.get("symbols", {})
    else:
        _spec_cache = {}
    return _spec_cache


def _get_pip_size(symbol: str) -> float:
    """Get pip size for a symbol from broker specifications.

    For 3/5-digit instruments (FX): pip = point * 10 (e.g., 0.00001 → 0.0001).
    For 2-digit instruments (metals, crypto, oil): pip = point (e.g., 0.01).
    For indices with 0-1 digits: pip = point.
    """
    symbol = symbol.upper()
    specs = _load_specs()
    if symbol in specs:
        s = specs[symbol]
        point = s.get("point", 0.0001)
        digits = s.get("digits", 5)
        # 3-digit (JPY pairs) and 5-digit (standard FX): pip = 10 * point
        # 2-digit or fewer (metals, crypto, oil, indices): pip = point
        if digits in (3, 5):
            return point * 10
        return point
    # Fallback for symbols not in specs
    if symbol.endswith("JPY"):
        return 0.01
    return 0.0001


def get_typical_spread_pips(symbol: str) -> float:
    """Get realistic typical spread in pips for a symbol.

    Uses broker specs as a floor, then applies minimums by instrument class.
    ECN snapshot spreads are often 0 or near-0 — not realistic for backtesting.
    """
    symbol = symbol.upper()
    specs = _load_specs()

    # Compute spec-based spread in pips
    spec_spread = 0.0
    if symbol in specs:
        s = specs[symbol]
        spread_points = s.get("spread", 0)
        point = s.get("point", 0.0001)
        digits = s.get("digits", 5)
        pip_size = point * 10 if digits in (3, 5) else point
        if pip_size > 0:
            spec_spread = spread_points * point / pip_size

    # Realistic minimums by instrument class
    if symbol in ("XAUUSD",):
        return max(spec_spread, 2.0)   # Gold: ~$0.20 typical
    if symbol in ("BTCUSD", "ETHUSD"):
        return max(spec_spread, 120.0)  # Crypto: ~$12 typical
    if symbol in ("XBRUSD", "XTIUSD"):
        return max(spec_spread, 3.0)    # Oil: ~$0.03 typical
    if symbol.endswith("JPY"):
        return max(spec_spread, 1.5)    # JPY pairs: 1.5 pips typical
    if symbol in ("DE40", "US30", "US500", "US100", "USTEC", "UK100", "JP225"):
        return max(spec_spread, 100.0)  # Indices: varies widely
    # Standard FX
    return max(spec_spread, 1.0)        # FX majors: ~1.0 pip typical


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
