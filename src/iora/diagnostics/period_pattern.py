"""Compute period pattern from PeriodTracker history."""
from __future__ import annotations


def compute_period_pattern(
    prev_highs: list[float],
    prev_lows: list[float],
) -> str:
    """Derive structural pattern from the last 2 period highs and lows.

    Returns one of: "HH_HL", "LH_LL", "LH_HL", "HH_LL", "mixed", "unknown".
    prev_highs[0] is most recent, prev_highs[1] is the one before.
    """
    if len(prev_highs) < 2 or len(prev_lows) < 2:
        return "unknown"

    h0, h1 = prev_highs[0], prev_highs[1]
    l0, l1 = prev_lows[0], prev_lows[1]

    hh = h0 > h1
    lh = h0 < h1
    hl = l0 > l1
    ll = l0 < l1

    if hh and hl:
        return "HH_HL"
    if lh and ll:
        return "LH_LL"
    if lh and hl:
        return "LH_HL"
    if hh and ll:
        return "HH_LL"
    return "mixed"
