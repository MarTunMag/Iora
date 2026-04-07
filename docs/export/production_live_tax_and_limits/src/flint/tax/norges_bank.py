"""
Norges Bank Exchange Rate Client.

Fetches official USD/NOK exchange rates from the Norges Bank SDMX-JSON API.
Implements local JSON file caching (one file per year) and weekend/holiday
fallback (walks backward up to 7 days for the nearest business day rate).
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from flint.paths import get_exchange_rate_cache_dir

logger = logging.getLogger(__name__)

# Norges Bank SDMX-JSON data endpoint for daily USD/NOK spot rate
_API_URL = (
    "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP"
    "?format=sdmx-json&startPeriod={start}&endPeriod={end}&detail=dataonly"
)

# Completed-year caches never expire; current-year caches expire after 24 h
_CACHE_MAX_AGE_SECONDS = 86_400


class ExchangeRateError(Exception):
    """Raised when an exchange rate cannot be obtained."""


class NorgesBankClient:
    """Fetches and caches USD/NOK exchange rates from Norges Bank."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or get_exchange_rate_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache: year -> dict[date_str, rate]
        self._rates: dict[int, dict[str, float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_rate(self, target_date: date) -> float:
        """
        Return the USD/NOK rate for *target_date*.

        If *target_date* falls on a weekend or holiday, the rate for the most
        recent preceding business day is returned (up to 7 days back).

        Raises ExchangeRateError if no rate can be found.
        """
        year_rates = self.get_rates_for_year(target_date.year)
        rate, _ = self._resolve_rate(target_date, year_rates)
        return rate

    def get_rate_with_date(self, target_date: date) -> tuple:
        """
        Return (rate, actual_date) — the rate and the business day it came from.
        """
        year_rates = self.get_rates_for_year(target_date.year)
        return self._resolve_rate(target_date, year_rates)

    def get_rates_for_year(self, year: int) -> dict[str, float]:
        """
        Return a dict mapping ``"YYYY-MM-DD"`` strings to USD/NOK rates for
        *year*.  Uses the local JSON cache when available.
        """
        if year in self._rates:
            return self._rates[year]

        cache_path = self._cache_path(year)
        if self._cache_is_valid(cache_path, year):
            rates = self._load_cache(cache_path)
            if rates:
                self._rates[year] = rates
                return rates

        rates = self._fetch_year(year)
        self._save_cache(cache_path, rates)
        self._rates[year] = rates
        return rates

    # ------------------------------------------------------------------
    # Rate resolution (weekend / holiday fallback)
    # ------------------------------------------------------------------

    def _resolve_rate(self, target_date: date, year_rates: dict[str, float]) -> tuple:
        """Walk backward up to 7 days to find a business-day rate."""
        for offset in range(8):
            d = target_date - timedelta(days=offset)
            key = d.isoformat()

            # If we cross into the previous year, load that year's rates too
            if d.year != target_date.year:
                prev_rates = self.get_rates_for_year(d.year)
                if key in prev_rates:
                    return prev_rates[key], d
            elif key in year_rates:
                return year_rates[key], d

        raise ExchangeRateError(
            f"No USD/NOK rate found for {target_date} " f"(looked back 7 days)"
        )

    # ------------------------------------------------------------------
    # Norges Bank API
    # ------------------------------------------------------------------

    def _fetch_year(self, year: int) -> dict[str, float]:
        """Fetch all daily USD/NOK rates for *year* from the Norges Bank API."""
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        url = _API_URL.format(start=start, end=end)

        logger.info("Fetching USD/NOK rates from Norges Bank for %d ...", year)
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ExchangeRateError(
                f"Norges Bank API request failed for {year}: {exc}"
            ) from exc

        return self._parse_sdmx_json(resp.json(), year)

    @staticmethod
    def _parse_sdmx_json(data: dict, year: int) -> dict[str, float]:
        """
        Parse the SDMX-JSON response into a date->rate mapping.

        Structure::

            data.dataSets[0].series["0:0:0:0"].observations
                {"0": [10.45], "1": [10.50], ...}

            data.structure.dimensions.observation[0].values
                [{"id": "2026-01-02"}, {"id": "2026-01-03"}, ...]
        """
        try:
            datasets = data["data"]["dataSets"]
            if not datasets:
                raise ExchangeRateError(f"Empty dataSets for {year}")

            series = datasets[0]["series"]
            # The series key is "0:0:0:0" for our single-series query
            series_key = next(iter(series))
            observations = series[series_key]["observations"]

            # Time periods are in the observation dimension
            time_periods = data["data"]["structure"]["dimensions"]["observation"][0][
                "values"
            ]

            rates: dict[str, float] = {}
            for idx_str, values in observations.items():
                idx = int(idx_str)
                if idx < len(time_periods):
                    period = time_periods[idx]["id"]
                    rate = float(values[0])
                    rates[period] = rate

            logger.info("Parsed %d USD/NOK rates for %d", len(rates), year)
            return rates

        except (KeyError, IndexError, StopIteration, TypeError) as exc:
            raise ExchangeRateError(
                f"Failed to parse Norges Bank SDMX-JSON for {year}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def _cache_path(self, year: int) -> Path:
        return self.cache_dir / f"usd_nok_{year}.json"

    def _cache_is_valid(self, path: Path, year: int) -> bool:
        if not path.exists():
            return False
        # Completed years: cache forever
        if year < date.today().year:
            return True
        # Current/future year: expire after 24 h
        age = time.time() - path.stat().st_mtime
        return age < _CACHE_MAX_AGE_SECONDS

    @staticmethod
    def _load_cache(path: Path) -> Optional[dict[str, float]]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Cache read failed (%s): %s", path, exc)
            return None

    def _save_cache(self, path: Path, rates: dict[str, float]) -> None:
        """Atomic write: write to temp file then rename."""
        try:
            fd, tmp = tempfile.mkstemp(dir=str(self.cache_dir), suffix=".tmp")
            try:
                with open(fd, "w", encoding="utf-8") as fh:
                    json.dump(rates, fh, indent=2, sort_keys=True)
                Path(tmp).replace(path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except OSError as exc:
            logger.warning("Cache write failed (%s): %s", path, exc)
