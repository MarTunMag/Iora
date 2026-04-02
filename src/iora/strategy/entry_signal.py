"""EntrySignal — immutable snapshot of full system state at entry time."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.engine.push_zone_models import PushZone


@dataclass(frozen=True, slots=True)
class EntrySignal:
    """Captures every dimension of system state when a trade entry fires."""

    zone: PushZone
    zone_tf: str
    signal_type: str      # "push", "reversal", "terminal", "normal"
    struct_cls: str        # "BOS", "CHoCH", ""
    direction: str         # "long", "short"

    parent_zone: PushZone | None
    parent_tf: str
    nesting_depth: int
    opposing_nest: bool

    trend_by_tf: dict[str, int]
    period_levels: dict[str, dict]
    zone_counts: dict[str, tuple]
    exhaustion: dict[str, bool]

    sl_price: float
    tp_price: float
    risk_pips: float
    reward_pips: float
    entry_time: pd.Timestamp
    entry_price: float

    @property
    def rr_ratio(self) -> float:
        if self.risk_pips <= 0:
            return 0.0
        return self.reward_pips / self.risk_pips

    def to_dict(self) -> dict:
        return {
            "zone_tf": self.zone_tf,
            "signal_type": self.signal_type,
            "struct_cls": self.struct_cls,
            "direction": self.direction,
            "parent_tf": self.parent_tf,
            "nesting_depth": self.nesting_depth,
            "opposing_nest": self.opposing_nest,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "risk_pips": self.risk_pips,
            "reward_pips": self.reward_pips,
            "rr_ratio": self.rr_ratio,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "zone_top": self.zone.top,
            "zone_bottom": self.zone.bottom,
            "zone_is_push": self.zone.is_push,
            "zone_is_reversal": self.zone.is_reversal,
            "zone_is_terminal": self.zone.is_terminal,
            "zone_swing_cls": self.zone.swing_cls,
        }
