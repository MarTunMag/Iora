"""Bias State Timeline — Level 2 diagnostics.

Continuous per-bar structural bias tracker. Computes daily/H4/H1 bias
labels, D-to-W relationships, and zone distances.
"""
from __future__ import annotations

from iora.diagnostics.period_pattern import compute_period_pattern


# Mapping from short pattern → descriptive label
_PATTERN_LABELS: dict[str, str] = {
    "HH_HL": "HH_HL_bull_push",
    "LH_LL": "LH_LL_bear_push",
    "LH_HL": "LH_HL_compression",
    "HH_LL": "HH_LL_expansion",
}


def compute_bias_label(
    prev_highs: list[float],
    prev_lows: list[float],
) -> str:
    """Compute bias label with descriptive suffix from period history.

    Reuses compute_period_pattern() for the core HH/LH + HL/LL logic,
    then maps to descriptive label (e.g., "HH_HL_bull_push").
    """
    short = compute_period_pattern(prev_highs, prev_lows)
    return _PATTERN_LABELS.get(short, short)


def compute_bias_strength(
    prev_highs: list[float],
    prev_lows: list[float],
) -> int:
    """Compute bias strength (1-3) from period history depth.

    3 = three consecutive same-direction highs AND lows align
    2 = last two same-direction, third breaks or lows don't fully align
    1 = only latest pair shows direction
    0 = insufficient data (< 2 periods)
    """
    if len(prev_highs) < 2 or len(prev_lows) < 2:
        return 0

    # Determine primary direction from latest pair
    h0, h1 = prev_highs[0], prev_highs[1]
    bullish = h0 > h1  # HH
    bearish = h0 < h1  # LH

    if not bullish and not bearish:
        return 1  # Equal — weak

    l0, l1 = prev_lows[0], prev_lows[1]

    # Check depth-2 consistency
    if len(prev_highs) < 3 or len(prev_lows) < 3:
        return 1

    h2 = prev_highs[2]
    l2 = prev_lows[2]

    pair2_highs_same = (h1 > h2) if bullish else (h1 < h2)
    lows_align = (l0 > l1 > l2) if bullish else (l0 < l1 < l2)

    if pair2_highs_same and lows_align:
        return 3

    # Either highs or lows show depth-2 alignment (but not both)
    if pair2_highs_same or lows_align:
        return 2

    return 1
