"""StrategyConfig — all sweep dimensions for push zone strategy evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for a single strategy evaluation run."""

    entry_tf: str = "M5"
    parent_tf: str = "H1"
    require_nesting: bool = True

    signal_types: set[str] = field(default_factory=lambda: {"push", "reversal"})
    struct_filter: str = "any"
    htf_trend_filter: str = "none"
    htf_trend_tf: str = "H4"
    max_zone_count: int = 0
    no_trade_zones: bool = True

    sl_mode: str = "zone"
    tp_mode: str = "zone"
    fixed_rr: float = 2.0
    sl_period_depth: int = 1

    position_mode: str = "single"
    direction: str = "both"

    risk_per_trade_pct: float = 1.0
    max_concurrent: int = 1

    def to_dict(self) -> dict:
        return {
            "entry_tf": self.entry_tf,
            "parent_tf": self.parent_tf,
            "require_nesting": self.require_nesting,
            "signal_types": sorted(self.signal_types),
            "struct_filter": self.struct_filter,
            "htf_trend_filter": self.htf_trend_filter,
            "htf_trend_tf": self.htf_trend_tf,
            "max_zone_count": self.max_zone_count,
            "no_trade_zones": self.no_trade_zones,
            "sl_mode": self.sl_mode,
            "tp_mode": self.tp_mode,
            "fixed_rr": self.fixed_rr,
            "sl_period_depth": self.sl_period_depth,
            "position_mode": self.position_mode,
            "direction": self.direction,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_concurrent": self.max_concurrent,
        }


def make_preset(name: str) -> StrategyConfig:
    if name == "aggressive":
        return StrategyConfig(
            require_nesting=False,
            signal_types={"push", "reversal", "terminal", "normal"},
            no_trade_zones=False,
            htf_trend_filter="none",
        )
    elif name == "conservative":
        return StrategyConfig(
            require_nesting=True,
            signal_types={"push", "reversal"},
            htf_trend_filter="with_trend",
            htf_trend_tf="H4",
            no_trade_zones=True,
        )
    elif name == "default":
        return StrategyConfig()
    else:
        raise ValueError(f"Unknown preset: {name!r}")
