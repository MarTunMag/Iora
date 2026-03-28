# -*- coding: utf-8 -*-
"""
@file: storage_utils/data_loader.py
@brief: Data loading utilities for trading bot integration.

This module provides a simple interface for trading bots (e.g. Oriz)
to load historical data from the Mt5HistoricalData warehouse.

Can be copied to trading bot projects or imported directly if on PYTHONPATH.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


class Mt5DataLoader:
    """
    Load historical OHLCV data from Mt5HistoricalData warehouse.

    This class provides a simple interface to load data without needing
    to understand the internal storage structure.

    Usage:
        loader = Mt5DataLoader(r"C:\\Mt5HistoricalData\\data")
        df = loader.load("EURUSD", "H1")
        df = loader.load("EURUSD", "M15", start_date="2023-01-01", end_date="2024-01-01")
    """

    def __init__(self, data_root: str | None = None):
        """
        Initialize the data loader.

        Args:
            data_root: Path to the Mt5HistoricalData data directory.
        """
        if data_root is None:
            from iora.paths import WAREHOUSE_DIR

            data_root = str(WAREHOUSE_DIR)
        self.root = Path(data_root)
        if not self.root.exists():
            raise ValueError(f"Data directory not found: {self.root}")

    def load(
        self,
        symbol: str,
        timeframe: str,
        start_date: str | datetime | pd.Timestamp | None = None,
        end_date: str | datetime | pd.Timestamp | None = None,
        as_index: bool = True,
    ) -> pd.DataFrame | None:
        """
        Load OHLCV data for a symbol/timeframe.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD').
            timeframe: Timeframe string (e.g., 'H1', 'M15', 'D1').
            start_date: Optional start date filter (inclusive).
            end_date: Optional end date filter (inclusive).
            as_index: If True, sets 'time' as DatetimeIndex. If False, keeps as column.

        Returns:
            DataFrame with OHLCV data, or None if not found.
        """
        file_path = self.root / symbol.upper() / timeframe.upper() / "data.parquet"

        if not file_path.exists():
            return None

        df = pd.read_parquet(file_path)

        # Ensure time is datetime
        if "time" in df.columns and not pd.api.types.is_datetime64_any_dtype(
            df["time"]
        ):
            df["time"] = pd.to_datetime(df["time"])

        # Apply date filters
        if start_date is not None:
            start_ts = pd.Timestamp(start_date)
            df = df[df["time"] >= start_ts]

        if end_date is not None:
            end_ts = pd.Timestamp(end_date)
            df = df[df["time"] <= end_ts]

        # Set time as index if requested
        if as_index and "time" in df.columns:
            df.set_index("time", inplace=True)
            df.sort_index(inplace=True)

        return df

    def load_multiple_timeframes(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: str | datetime | None = None,
        end_date: str | datetime | None = None,
        as_index: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        Load multiple timeframes for a symbol.

        Args:
            symbol: Trading symbol.
            timeframes: List of timeframes to load.
            start_date: Optional start date filter.
            end_date: Optional end date filter.
            as_index: If True, sets 'time' as DatetimeIndex.

        Returns:
            Dictionary mapping timeframe to DataFrame.
        """
        result = {}
        for tf in timeframes:
            df = self.load(symbol, tf, start_date, end_date, as_index)
            if df is not None:
                result[tf] = df
        return result

    def get_available_symbols(self) -> list[str]:
        """
        Get list of all symbols with stored data.

        Returns:
            Sorted list of symbol names.
        """
        symbols = []
        for item in self.root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                symbols.append(item.name)
        return sorted(symbols)

    def get_available_timeframes(self, symbol: str) -> list[str]:
        """
        Get list of available timeframes for a symbol.

        Args:
            symbol: Trading symbol.

        Returns:
            Sorted list of timeframe strings.
        """
        symbol_dir = self.root / symbol.upper()
        if not symbol_dir.exists():
            return []

        timeframes = []
        for item in symbol_dir.iterdir():
            if item.is_dir() and (item / "data.parquet").exists():
                timeframes.append(item.name)
        return sorted(timeframes)

    def get_data_range(self, symbol: str, timeframe: str) -> dict | None:
        """
        Get the date range and bar count for a symbol/timeframe.

        Args:
            symbol: Trading symbol.
            timeframe: Timeframe string.

        Returns:
            Dictionary with start_date, end_date, bar_count, or None if not found.
        """
        file_path = self.root / symbol.upper() / timeframe.upper() / "data.parquet"
        if not file_path.exists():
            return None
        try:
            df = pd.read_parquet(file_path, columns=["time"])
        except Exception:
            return None
        if df.empty:
            return None
        if not pd.api.types.is_datetime64_any_dtype(df["time"]):
            df["time"] = pd.to_datetime(df["time"])
        return {
            "start_date": df["time"].min(),
            "end_date": df["time"].max(),
            "bar_count": len(df),
        }

    def get_manifest(self) -> dict | None:
        """
        Load the manifest file containing metadata for all stored data.

        Returns:
            Dictionary with manifest data, or None if not found.
        """
        import json

        manifest_path = self.root / "manifest.json"
        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_latest_bar(self, symbol: str, timeframe: str) -> pd.Series | None:
        """
        Get the most recent bar for a symbol/timeframe.

        Args:
            symbol: Trading symbol.
            timeframe: Timeframe string.

        Returns:
            Series with the latest bar data, or None if not found.
        """
        file_path = self.root / symbol.upper() / timeframe.upper() / "data.parquet"
        if not file_path.exists():
            return None
        try:
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(file_path)
            # Read only the last row group
            last_rg = pf.read_row_group(pf.metadata.num_row_groups - 1)
            df = last_rg.to_pandas()
            if df.empty:
                return None
            return df.iloc[-1]
        except Exception:
            # Fallback to full load
            df = self.load(symbol, timeframe, as_index=False)
            if df is None or df.empty:
                return None
            return df.iloc[-1]


# Convenience functions for direct import


def load_from_mt5_storage(
    symbol: str,
    timeframe: str,
    data_root: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    as_index: bool = True,
) -> pd.DataFrame | None:
    """
    Convenience function to load data from Mt5HistoricalData.

    Args:
        symbol: Trading symbol (e.g., 'EURUSD').
        timeframe: Timeframe string (e.g., 'H1').
        data_root: Path to Mt5HistoricalData data directory.
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        as_index: If True, sets 'time' as DatetimeIndex.

    Returns:
        DataFrame with OHLCV data.

    Example:
        from mt5_data_loader import load_from_mt5_storage
        df = load_from_mt5_storage("EURUSD", "H1", start_date="2023-01-01")
    """
    loader = Mt5DataLoader(data_root)
    return loader.load(symbol, timeframe, start_date, end_date, as_index)


def get_cascade_data(
    symbol: str,
    data_root: str | None = None,
    trigger_tf: str = "M15",
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Load all timeframes needed for cascade trading models.

    This loads: trigger_tf, H1, H4, D1, W1

    Args:
        symbol: Trading symbol.
        data_root: Path to Mt5HistoricalData data directory.
        trigger_tf: Trigger timeframe (e.g., 'M15', 'M5').
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        Dictionary with DataFrames for each timeframe.

    Example:
        from mt5_data_loader import get_cascade_data
        data = get_cascade_data("EURUSD", trigger_tf="M15")
        m15 = data['M15']
        h1 = data['H1']
    """
    loader = Mt5DataLoader(data_root)

    # Define cascade timeframes based on trigger
    if trigger_tf.upper() == "M5":
        timeframes = ["M5", "M15", "H1", "H4", "D1", "W1"]
    elif trigger_tf.upper() == "M1":
        timeframes = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]
    else:  # Default M15
        timeframes = ["M15", "H1", "H4", "D1", "W1"]

    return loader.load_multiple_timeframes(symbol, timeframes, start_date, end_date)
