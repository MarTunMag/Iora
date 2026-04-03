"""Shared fixtures for strategy tests."""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def small_engine_data() -> dict[str, pd.DataFrame]:
    """Minimal multi-TF data with known zone-forming price action."""
    n = 200
    timestamps = pd.date_range("2025-01-15 08:00", periods=n, freq="5min")
    np.random.seed(42)

    base = 1.2500
    moves = np.concatenate([
        np.linspace(0, 0.0200, 100),
        np.linspace(0.0200, 0.0100, 50),
        np.linspace(0.0100, 0.0250, 50),
    ])
    noise = np.random.normal(0, 0.0005, n)
    close = base + moves + noise
    high = close + np.abs(np.random.normal(0, 0.0008, n))
    low = close - np.abs(np.random.normal(0, 0.0008, n))
    open_ = np.roll(close, 1)
    open_[0] = base

    m5 = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "tick_volume": np.ones(n)},
        index=timestamps,
    )
    m5.index.name = "time"

    def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
        r = df.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min",
             "close": "last", "tick_volume": "sum"}
        ).dropna()
        r.index.name = "time"
        return r

    return {
        "M5": m5,
        "H1": resample_ohlc(m5, "1h"),
        "H4": resample_ohlc(m5, "4h"),
        "D1": resample_ohlc(m5, "1D"),
        "W1": resample_ohlc(m5, "1W"),
    }
