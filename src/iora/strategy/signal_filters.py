# src/iora/strategy/signal_filters.py
"""Signal filter functions for push zone strategy.

Each filter returns (pass: bool, reason: str). Reason is empty if passed.
Composable — apply_all_filters chains them per StrategyConfig.
"""
from __future__ import annotations

from iora.engine.push_zone_models import PushZone
from iora.strategy.strategy_config import StrategyConfig


def filter_signal_type(
    signal_type: str, allowed: set[str],
) -> tuple[bool, str]:
    """Check if signal type is in allowed set."""
    if signal_type in allowed:
        return True, ""
    return False, f"signal_type '{signal_type}' not in {sorted(allowed)}"


def filter_struct(
    struct_cls: str, struct_filter: str,
) -> tuple[bool, str]:
    """Check structure classification filter."""
    if struct_filter == "any":
        return True, ""
    if struct_filter == "bos_only" and struct_cls != "BOS":
        return False, f"struct_filter=bos_only but got '{struct_cls}'"
    if struct_filter == "choch_only" and struct_cls != "CHoCH":
        return False, f"struct_filter=choch_only but got '{struct_cls}'"
    return True, ""


def filter_direction(
    signal_direction: str, config_direction: str,
) -> tuple[bool, str]:
    """Check if signal direction matches config direction filter."""
    if config_direction == "both":
        return True, ""
    if signal_direction == config_direction:
        return True, ""
    return False, f"direction '{signal_direction}' blocked by filter '{config_direction}'"


def filter_nesting(
    require_nesting: bool,
    parent_zone: PushZone | None,
    nesting_depth: int,
) -> tuple[bool, str]:
    """Check nesting requirement."""
    if not require_nesting:
        return True, ""
    if parent_zone is not None and nesting_depth > 0:
        return True, ""
    return False, "nesting required but no parent zone"


def filter_htf_trend(
    direction: str, htf_trend: int, htf_filter: str,
) -> tuple[bool, str]:
    """Check HTF trend alignment.

    Args:
        direction: "long" or "short"
        htf_trend: +1 (bull), -1 (bear), 0 (neutral)
        htf_filter: "with_trend", "counter_allowed", "none"
    """
    if htf_filter == "none" or htf_filter == "counter_allowed":
        return True, ""

    if htf_filter == "with_trend":
        if direction == "long" and htf_trend > 0:
            return True, ""
        if direction == "short" and htf_trend < 0:
            return True, ""
        if htf_trend == 0:
            return False, f"htf_trend=0 (neutral) blocks {direction} (with_trend)"
        return False, f"htf_trend={htf_trend} blocks {direction} (with_trend)"

    return True, ""


def filter_zone_count(
    current_count: int, max_count: int,
) -> tuple[bool, str]:
    """Check if zone count exceeds max (0 = disabled)."""
    if max_count == 0:
        return True, ""
    if current_count <= max_count:
        return True, ""
    return False, f"zone_count {current_count} > max {max_count}"


def filter_no_trade_zone(
    enabled: bool,
    entry_price: float,
    htf_zones: list[PushZone],
    direction: str,
) -> tuple[bool, str]:
    """Check if price is inside an opposing HTF zone (D/W).

    For long entries: blocked if inside a supply zone.
    For short entries: blocked if inside a demand zone.
    """
    if not enabled:
        return True, ""

    opposing_supply = direction == "long"
    for z in htf_zones:
        if z.is_supply == opposing_supply and z.contains_price(entry_price):
            return False, f"inside opposing {z.timeframe} {'supply' if z.is_supply else 'demand'} zone"

    return True, ""


def apply_all_filters(
    *,
    signal_type: str,
    struct_cls: str,
    direction: str,
    parent_zone: PushZone | None,
    nesting_depth: int,
    htf_trend: int,
    zone_count: int,
    entry_price: float,
    htf_zones: list[PushZone],
    config: StrategyConfig,
) -> tuple[bool, list[str]]:
    """Apply all filters from StrategyConfig. Returns (all_pass, failure_reasons)."""
    failures: list[str] = []

    checks = [
        filter_signal_type(signal_type, config.signal_types),
        filter_struct(struct_cls, config.struct_filter),
        filter_direction(direction, config.direction),
        filter_nesting(config.require_nesting, parent_zone, nesting_depth),
        filter_htf_trend(direction, htf_trend, config.htf_trend_filter),
        filter_zone_count(zone_count, config.max_zone_count),
        filter_no_trade_zone(config.no_trade_zones, entry_price, htf_zones, direction),
    ]

    for passed, reason in checks:
        if not passed:
            failures.append(reason)

    return len(failures) == 0, failures
