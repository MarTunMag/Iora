"""
Trendline feature extraction — flat bool/float features from TL engine state.

Extracts per-TF trendline active/broken flags and slope from TrendlineTickState.
"""

from __future__ import annotations

import math

import pandas as pd

from iora.engine.trendline_tick import TrendlineTickState, _interpolate_tl


def extract_tl_features_for_tf(
    tl_state: TrendlineTickState | None,
    close: float,
    bar_time: pd.Timestamp,
) -> dict[str, object]:
    """
    Extract flat TL features for a single TF.

    Returns dict with keys (no TF prefix — caller adds it):
        bull_tl_active, bear_tl_active,
        bull_tl_broken, bear_tl_broken,
        bull_tl_slope, bear_tl_slope,
        bull_tl_dist, bear_tl_dist,
        tl_history_count
    """
    if tl_state is None:
        return {
            "bull_tl_active": False,
            "bear_tl_active": False,
            "bull_tl_broken": False,
            "bear_tl_broken": False,
            "bull_tl_slope": math.nan,
            "bear_tl_slope": math.nan,
            "bull_tl_dist": math.nan,
            "bear_tl_dist": math.nan,
            "tl_history_count": 0,
        }

    # Active flags
    bull_active = tl_state.bull_active is not None
    bear_active = tl_state.bear_active is not None

    # Broken flags (edge — True for one bar only after break)
    bull_broken = tl_state.bull_broken
    bear_broken = tl_state.bear_broken

    # Slope and distance for active TLs
    bull_slope = math.nan
    bear_slope = math.nan
    bull_dist = math.nan
    bear_dist = math.nan

    if bull_active and tl_state.bull_active is not None:
        tl = tl_state.bull_active
        tl_price = _interpolate_tl(tl, bar_time)
        if tl_price is not None:
            bull_dist = close - tl_price  # positive = above TL
            # Slope: price change per second (normalized)
            dt = (tl.t2 - tl.t1).total_seconds()
            if dt > 0:
                bull_slope = (tl.p2 - tl.p1) / dt

    if bear_active and tl_state.bear_active is not None:
        tl = tl_state.bear_active
        tl_price = _interpolate_tl(tl, bar_time)
        if tl_price is not None:
            bear_dist = tl_price - close  # positive = below TL
            dt = (tl.t2 - tl.t1).total_seconds()
            if dt > 0:
                bear_slope = (tl.p2 - tl.p1) / dt

    history_count = len(tl_state.bull_history) + len(tl_state.bear_history)

    return {
        "bull_tl_active": bull_active,
        "bear_tl_active": bear_active,
        "bull_tl_broken": bull_broken,
        "bear_tl_broken": bear_broken,
        "bull_tl_slope": bull_slope,
        "bear_tl_slope": bear_slope,
        "bull_tl_dist": bull_dist,
        "bear_tl_dist": bear_dist,
        "tl_history_count": history_count,
    }
