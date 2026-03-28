"""
Signal — Core signal data model for the rules layer.

A Signal is the output of a Rule evaluation. It carries everything needed
for visualization, backtesting, and live execution.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class Signal:
    """A trading signal emitted by a rule."""

    time: pd.Timestamp
    rule_id: str           # e.g. "cascade_m5_peak", "growth_trend_entry"
    signal_type: str       # ENTRY, EXIT, HEDGE, ADD_ON, SL_MOVE, TP_TARGET, INFO
    direction: str         # "bull" | "bear"
    tf: str                # TF where signal originates (e.g. "M1")
    parent_tf: str         # HTF context (e.g. "M5" for M1→M5 cascade)
    price: float           # Signal price level
    sl_price: float | None = None
    tp_price: float | None = None
    confidence: int = 1    # 1=early/speculative, 5=fully confirmed
    mode: str = "both"     # "growth", "scalping", "both"
    details: str = ""      # Human-readable description

    # Visualization metadata
    viz_priority: int = 2  # 1=must show, 2=important, 3=informational
    viz_shape: str = "circle"
    viz_color: str = "#FFFFFF"
    viz_size: int = 1


# Signal types
ENTRY = "ENTRY"
EXIT = "EXIT"
HEDGE = "HEDGE"
ADD_ON = "ADD_ON"
SL_MOVE = "SL_MOVE"
TP_TARGET = "TP_TARGET"
INFO = "INFO"
