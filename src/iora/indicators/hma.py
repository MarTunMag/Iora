"""Hull Moving Average (HMA) — responsive trend-following indicator.

HMA(period) = WMA(2 * WMA(close, period/2) - WMA(close, period), floor(sqrt(period)))
"""
from __future__ import annotations

from math import floor, sqrt

import numpy as np
import pandas as pd


def compute_wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted moving average with linear weights [1, 2, ..., period]."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True,
    )


def compute_hma(series: pd.Series, period: int) -> pd.Series:
    """Hull Moving Average."""
    half_period = max(period // 2, 1)
    sqrt_period = max(floor(sqrt(period)), 1)

    wma_half = compute_wma(series, half_period)
    wma_full = compute_wma(series, period)
    diff = 2.0 * wma_half - wma_full
    return compute_wma(diff, sqrt_period)


def compute_hma_direction(
    hma: pd.Series,
    atr: pd.Series,
    flat_threshold: float = 0.05,
) -> pd.Series:
    """HMA slope direction: +1 rising, -1 falling, 0 flat.

    Flat when abs(hma[i] - hma[i-1]) < flat_threshold * atr[i].
    """
    delta = hma.diff()
    threshold = flat_threshold * atr
    direction = pd.Series(0, index=hma.index, dtype=int)
    direction[delta > threshold] = 1
    direction[delta < -threshold] = -1
    return direction


def compute_ha_hma_cross(
    ha_close: pd.Series,
    hma: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Detect HA candle close crossing above/below HMA.

    Returns:
        ha_above_hma: bool Series — True when HA close > HMA
        cross_direction: int Series — +1 on bullish cross bar, -1 on bearish cross bar,
                         0 otherwise. Forward-filled so it persists until next cross.
    """
    _raw = ha_close > hma
    ha_above = pd.Series(np.where(pd.isna(_raw), False, _raw), index=ha_close.index, dtype=bool)

    # Cross event: transition in ha_above
    prev_vals = np.empty(len(ha_above), dtype=bool)
    prev_vals[0] = False
    prev_vals[1:] = ha_above.values[:-1]
    prev_above = pd.Series(prev_vals, index=ha_above.index)
    bullish_cross = ha_above & ~prev_above  # was below, now above
    bearish_cross = ~ha_above & prev_above  # was above, now below

    cross_raw = pd.Series(0, index=ha_close.index, dtype=int)
    cross_raw[bullish_cross] = 1
    cross_raw[bearish_cross] = -1

    # Forward-fill cross direction so it persists until next cross
    cross_direction = cross_raw.replace(0, np.nan).ffill().fillna(0).astype(int)

    return ha_above.fillna(False), cross_direction


def compute_bars_since_cross(
    cross_raw_direction: pd.Series,
) -> pd.Series:
    """Count bars since the last cross event.

    Args:
        cross_raw_direction: Series with +1/-1 on cross bars, 0 otherwise
            (the raw version BEFORE forward-fill).

    Returns:
        Series of int — bars since last non-zero value. 9999 if no cross yet.
    """
    is_cross = cross_raw_direction != 0
    # Group by cumulative cross count — each group starts at a cross event
    groups = is_cross.cumsum()
    # Within each group, count position from start
    bars_since = groups.groupby(groups).cumcount()
    # Before the first cross, set to 9999
    bars_since[groups == 0] = 9999
    return bars_since.astype(int)
