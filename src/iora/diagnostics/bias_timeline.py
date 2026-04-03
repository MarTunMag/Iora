"""Bias State Timeline — Level 2 diagnostics.

Continuous per-bar structural bias tracker. Computes daily/H4/H1 bias
labels, D-to-W relationships, and zone distances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf

import pandas as pd

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


def nearest_zone_distance(
    close: float,
    zones: list,
    atr: float,
) -> float:
    """Compute ATR-relative distance to nearest zone.

    Returns positive if outside zone (distance to nearest boundary),
    negative if inside a zone (penetration depth).
    Returns inf if no zones.
    """
    if not zones or atr <= 0:
        return inf

    best_dist = inf
    for z in zones:
        if z.bottom <= close <= z.top:
            # Inside zone — return negative penetration depth
            mid = (z.top + z.bottom) / 2.0
            return -abs(close - mid) / atr - 0.001  # Always negative when inside
        # Outside: distance to nearest boundary
        if close < z.bottom:
            dist = (z.bottom - close) / atr
        else:
            dist = (close - z.top) / atr
        if dist < best_dist:
            best_dist = dist

    return best_dist


# Bias direction extraction
_BULLISH_BIASES = {"HH_HL_bull_push"}
_BEARISH_BIASES = {"LH_LL_bear_push"}


def _bias_direction(bias: str) -> int:
    """Return +1 for bullish, -1 for bearish, 0 for neutral/unknown."""
    if bias in _BULLISH_BIASES:
        return 1
    if bias in _BEARISH_BIASES:
        return -1
    return 0


def compute_d_to_w_relationship(
    d_bias: str,
    w_supply_dist: float,
    w_demand_dist: float,
) -> str:
    """Classify daily-to-weekly structural relationship.

    Returns: "inside_zone", "continuation", "pullback", "neutral".
    """
    if w_supply_dist < 0 or w_demand_dist < 0:
        return "inside_zone"

    direction = _bias_direction(d_bias)
    if direction == 0:
        return "neutral"

    if w_supply_dist == inf and w_demand_dist == inf:
        return "neutral"

    if direction == 1:  # Bullish
        if w_supply_dist < w_demand_dist:
            return "pullback"
        return "continuation"
    else:  # Bearish
        if w_demand_dist < w_supply_dist:
            return "pullback"
        return "continuation"


def compute_tf_vs_daily(
    tf_bias: str,
    d_bias: str,
) -> str:
    """Classify whether a TF bias aligns with daily bias.

    Returns: "with", "against", "neutral".
    """
    tf_dir = _bias_direction(tf_bias)
    d_dir = _bias_direction(d_bias)

    if tf_dir == 0 or d_dir == 0:
        return "neutral"
    if tf_dir == d_dir:
        return "with"
    return "against"


@dataclass(slots=True)
class BiasStateRecord:
    """Per-bar structural bias state."""
    timestamp: pd.Timestamp
    d_bias: str = "unknown"
    d_bias_strength: int = 0
    d_to_w_relationship: str = "neutral"
    h4_bias: str = "unknown"
    h4_vs_daily: str = "neutral"
    h1_bias: str = "unknown"
    h1_vs_daily: str = "neutral"
    nearest_w_supply_dist: float = field(default_factory=lambda: inf)
    nearest_w_demand_dist: float = field(default_factory=lambda: inf)
    nearest_d_supply_dist: float = field(default_factory=lambda: inf)
    nearest_d_demand_dist: float = field(default_factory=lambda: inf)
    is_bias_transition: bool = False
    transition_from: str = ""
    transition_to: str = ""
