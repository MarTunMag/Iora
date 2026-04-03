"""Opportunity Counter — Level 3 diagnostics.

Counts retest events per TF pair per filter dimension.
No strategy, no trades — purely counting opportunities.
"""
from __future__ import annotations


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
