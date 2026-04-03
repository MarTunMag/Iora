"""Opportunity Counter — Level 3 diagnostics.

Counts retest events per TF pair per filter dimension.
No strategy, no trades — purely counting opportunities.
"""
from __future__ import annotations

# Import bias direction sets from bias_timeline (single source of truth)
from iora.diagnostics.bias_timeline import _BULLISH_BIASES, _BEARISH_BIASES


def classify_touch(
    zone,  # PushZone
    high: float,
    low: float,
    close: float,
) -> str | None:
    """Classify a bar's interaction with a zone.

    Returns: "wick_touch", "body_close", "break_through", or None (no interaction).

    - wick_touch: price entered zone but close stayed outside
    - body_close: close is inside zone boundaries
    - break_through: price entered zone AND close went through the other side
    """
    if zone.is_supply:
        entered = high >= zone.bottom
        if not entered:
            return None
        if close > zone.top:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close < zone.bottom
    else:  # demand
        entered = low <= zone.top
        if not entered:
            return None
        if close < zone.bottom:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close > zone.top


def is_near_miss(
    zone,  # PushZone
    high: float,
    low: float,
    atr: float,
    pip_size: float = 0.0001,
) -> bool:
    """Check if price came close to a zone without touching it.

    Threshold: max(min(0.25 * zone_thickness, 0.5 * ATR), 1.0 * pip_size).
    The pip floor prevents sub-pip thresholds on very thin zones.
    """
    zone_thickness = zone.top - zone.bottom
    threshold = max(min(0.25 * zone_thickness, 0.5 * atr), pip_size)

    if zone.is_supply:
        if high >= zone.bottom:
            return False
        distance = zone.bottom - high
    else:  # demand
        if low <= zone.top:
            return False
        distance = low - zone.top

    return distance <= threshold


# Same-direction swing_cls pairs (continuation)
_SAME_DIR = {
    ("HH", "HH"), ("HL", "HL"), ("LL", "LL"), ("LH", "LH"),
    ("HH", "HL"), ("HL", "HH"),  # Both bullish
    ("LL", "LH"), ("LH", "LL"),  # Both bearish
}


def classify_zone_role(zone, prev_swing_cls: str) -> str:
    """Classify zone's structural role.
    Returns: "push", "reversal", "continuation", "pullback", "unknown".
    """
    if zone.is_push:
        return "push"
    if zone.is_reversal:
        return "reversal"
    if not prev_swing_cls or not zone.swing_cls:
        return "unknown"
    if (zone.swing_cls, prev_swing_cls) in _SAME_DIR:
        return "continuation"
    return "pullback"


def classify_age_bucket(age_bars: int) -> str:
    """fresh: 0-10, young: 11-50, mature: 51-200, old: 201+"""
    if age_bars <= 10:
        return "fresh"
    if age_bars <= 50:
        return "young"
    if age_bars <= 200:
        return "mature"
    return "old"


def classify_bias_alignment(is_supply: bool, d_bias: str, is_transition: bool = False) -> str:
    """with_daily, against_daily, at_transition, neutral."""
    if is_transition:
        return "at_transition"
    if d_bias in _BULLISH_BIASES:
        return "with_daily" if not is_supply else "against_daily"
    if d_bias in _BEARISH_BIASES:
        return "with_daily" if is_supply else "against_daily"
    return "neutral"


def classify_test_count(test_count: int) -> str:
    """first_touch (0), retested_1 (1), retested_2plus (2+)."""
    if test_count == 0:
        return "first_touch"
    if test_count == 1:
        return "retested_1"
    return "retested_2plus"
