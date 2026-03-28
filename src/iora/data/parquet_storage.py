from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ParquetLayout:
    symbol: str
    timeframe: str
    year: int

    @property
    def filename(self) -> str:
        return f"{self.symbol}_{self.timeframe}_{self.year}.parquet"


class ParquetStorage:
    """
    Loads OHLCV parquet files laid out as:

        data/raw/{SYMBOL}/{YEAR}/{SYMBOL}_{TF}_{YEAR}.parquet
    """

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    def list_symbols(self) -> list[str]:
        raw_dir = self.base_dir / "raw"
        if not raw_dir.exists():
            return []
        return sorted(
            [
                p.name
                for p in raw_dir.iterdir()
                if p.is_dir() and not p.name.startswith(".")
            ]
        )

    @staticmethod
    def _year_from_filename(fp: Path) -> int:
        """Extract year from filename like EURUSD_H1_2024.parquet."""
        try:
            return int(fp.stem.rsplit("_", 1)[-1])
        except (ValueError, IndexError):
            return 0  # include file if year can't be parsed

    def get_latest_timestamp(
        self, symbol: str, timeframe: str
    ) -> pd.Timestamp | None:
        symbol_dir = self.base_dir / "raw" / symbol
        if not symbol_dir.exists():
            return None
        files = sorted(symbol_dir.rglob(f"{symbol}_{timeframe}_*.parquet"))
        if not files:
            return None
        # Only read the last (most recent year) file
        try:
            dfp = pd.read_parquet(files[-1])
        except Exception:
            return None
        if not isinstance(dfp.index, pd.DatetimeIndex):
            if "time" in dfp.columns:
                dfp = dfp.set_index(pd.to_datetime(dfp["time"], utc=False))
            elif "timestamp" in dfp.columns:
                dfp = dfp.set_index(pd.to_datetime(dfp["timestamp"], utc=False))
            else:
                try:
                    dfp.index = pd.to_datetime(dfp.index)
                except (ValueError, TypeError):
                    return None
        return dfp.index.max() if not dfp.empty else None

    def load(
        self,
        symbol: str,
        timeframe: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        symbol_dir = self.base_dir / "raw" / symbol
        if not symbol_dir.exists():
            return pd.DataFrame()

        files = sorted(symbol_dir.rglob(f"{symbol}_{timeframe}_*.parquet"))
        if not files:
            return pd.DataFrame()

        # Filter files by year range from filename to avoid loading unnecessary files
        if start_date is not None:
            start_year = pd.Timestamp(start_date).year
            files = [f for f in files if self._year_from_filename(f) >= start_year - 1]
        if end_date is not None:
            end_year = pd.Timestamp(end_date).year
            files = [f for f in files if self._year_from_filename(f) <= end_year]

        # Build pyarrow filters for predicate pushdown when index is stored as column
        pa_filters = None
        if start_date is not None or end_date is not None:
            try:
                import pyarrow.parquet as pq

                parts = []
                if start_date is not None:
                    parts.append(("time", ">=", pd.Timestamp(start_date)))
                if end_date is not None:
                    end_ts = pd.Timestamp(end_date)
                    # If date-only (midnight), include the full day
                    if end_ts.hour == 0 and end_ts.minute == 0 and end_ts.second == 0:
                        end_ts = end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
                    parts.append(("time", "<=", end_ts))
                pa_filters = parts
            except ImportError:
                pa_filters = None

        dfs: list[pd.DataFrame] = []
        for fp in files:
            try:
                dfp = pd.read_parquet(fp, filters=pa_filters)
            except (FileNotFoundError, PermissionError, OSError):
                continue
            except TypeError:
                # filters not supported (e.g. index-only time column) — fallback
                try:
                    dfp = pd.read_parquet(fp)
                except Exception as e:
                    logger.warning(f"Failed to read {fp} without filters: {e}")
                    continue
            except Exception as e:
                logger.warning(f"Unexpected error reading {fp}: {e}")
                continue

            # Ensure DatetimeIndex
            if not isinstance(dfp.index, pd.DatetimeIndex):
                if "time" in dfp.columns:
                    dfp = dfp.set_index(pd.to_datetime(dfp["time"], utc=False)).drop(
                        columns=["time"]
                    )
                elif "timestamp" in dfp.columns:
                    dfp = dfp.set_index(
                        pd.to_datetime(dfp["timestamp"], utc=False)
                    ).drop(columns=["timestamp"])
                else:
                    # Best-effort: try parse index
                    try:
                        dfp.index = pd.to_datetime(dfp.index)
                    except (ValueError, TypeError):
                        continue

            dfs.append(dfp)

        if not dfs:
            if files:
                logger.error("All %d parquet files failed to load for %s/%s", len(files), symbol, timeframe)
            return pd.DataFrame()

        df = pd.concat(dfs, axis=0)
        df = df[~df.index.duplicated(keep="last")].sort_index()

        if start_date is not None:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date is not None:
            end_ts = pd.to_datetime(end_date)
            if end_ts.hour == 0 and end_ts.minute == 0 and end_ts.second == 0:
                end_ts = end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            df = df[df.index <= end_ts]

        # Normalize column names we rely on
        df.columns = [str(c).lower() for c in df.columns]
        return df
