from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Heikin Ashi candles from OHLC.

    Returns a DataFrame with:
      open, high, low, close (HA)
      body_low, body_high
      direction: +1 bullish, -1 bearish
    """
    if df.empty:
        return pd.DataFrame()

    o = df["open"].astype(float).values
    h = df["high"].astype(float).values
    l = df["low"].astype(float).values
    c = df["close"].astype(float).values

    ha_close = (o + h + l + c) / 4.0
    ha_open = np.empty_like(ha_close)
    ha_open[0] = o[0]
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) * 0.5

    ha_high = np.maximum.reduce([h, ha_open, ha_close])
    ha_low = np.minimum.reduce([l, ha_open, ha_close])

    body_low = np.minimum(ha_open, ha_close)
    body_high = np.maximum(ha_open, ha_close)
    direction = np.where(ha_close >= ha_open, 1, -1).astype(int)

    out = pd.DataFrame(
        {
            "open": ha_open,
            "high": ha_high,
            "low": ha_low,
            "close": ha_close,
            "body_low": body_low,
            "body_high": body_high,
            "direction": direction,
        },
        index=df.index,
    )
    return out
