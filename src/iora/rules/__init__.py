"""
Rules layer — Modular signal framework for Growth + Scalping modes.

All rules consume BarFeatures + PositionState and emit Signal objects.
Rules are registered in the SignalRegistry for batch evaluation.

Master reference: docs/TRADING_RULES_SSOT.md

NOTE: Rule implementations (growth_entry, scalp_hedge, sl_trailing, etc.)
are archived in rules/archive/ during the macro-only phase. They will be
restored when meso/micro layers are built.
"""

from iora.rules.signal import Signal, ENTRY, EXIT, HEDGE, ADD_ON, SL_MOVE, TP_TARGET, INFO
from iora.rules.registry import SignalRegistry, RuleConfig
from iora.rules.position_state import PositionState, TradeMode, Direction, OpenTrade

__all__ = [
    "Signal",
    "SignalRegistry",
    "RuleConfig",
    "PositionState",
    "TradeMode",
    "Direction",
    "OpenTrade",
    "ENTRY", "EXIT", "HEDGE", "ADD_ON", "SL_MOVE", "TP_TARGET", "INFO",
    "create_default_registry",
]


def create_default_registry() -> SignalRegistry:
    """Return an empty registry (no rules active during macro-only phase)."""
    return SignalRegistry()
