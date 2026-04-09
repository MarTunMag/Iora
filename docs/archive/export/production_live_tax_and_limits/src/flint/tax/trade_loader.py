"""
Trade Loader for Tax Reporting.

Discovers account directories, loads closed trades from ledger files
(trades.json / trades.csv), normalises them into TaxTrade records, and
filters by tax year (based on exit_time).
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from flint.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TaxTrade:
    """Normalised trade record for tax calculation."""

    trade_id: str
    symbol: str
    account_id: int
    direction: str  # "LONG" or "SHORT"
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    position_size: float
    gross_pnl_usd: float
    commission_usd: float
    swap_usd: float
    net_pnl_usd: float
    exit_reason: str


class TradeLoader:
    """Load closed trades from the ledger file system."""

    def __init__(
        self,
        account_id: Optional[int] = None,
        include_archives: bool = True,
    ):
        self.account_id = account_id
        self.include_archives = include_archives

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, tax_year: int) -> List[TaxTrade]:
        """
        Return all closed trades whose *exit_time* falls in *tax_year*,
        sorted by exit_time.
        """
        account_dirs = self._discover_account_dirs()
        if not account_dirs:
            logger.warning("No account directories found")
            return []

        trades: List[TaxTrade] = []
        seen_ids: set = set()

        for acct_dir in account_dirs:
            acct_id = self._extract_account_id(acct_dir)
            if acct_id is None:
                continue
            if self.account_id is not None and acct_id != self.account_id:
                continue

            symbol_dirs = self._discover_symbol_dirs(acct_dir)
            for sym_dir in symbol_dirs:
                loaded = self._load_symbol_trades(sym_dir, acct_id)
                for t in loaded:
                    if t.trade_id in seen_ids:
                        continue
                    if t.exit_time.year == tax_year:
                        seen_ids.add(t.trade_id)
                        trades.append(t)

        trades.sort(key=lambda t: t.exit_time)
        logger.info("Loaded %d closed trades for tax year %d", len(trades), tax_year)
        return trades

    # ------------------------------------------------------------------
    # Account / directory discovery
    # ------------------------------------------------------------------

    def _discover_account_dirs(self) -> List[Path]:
        """Scan both ``data/live/execution/`` and ``data/live/accounts/``."""
        dirs: List[Path] = []
        for parent_name in ("execution", "accounts"):
            parent = PROJECT_ROOT / "data" / "live" / parent_name
            if parent.is_dir():
                for child in parent.iterdir():
                    if child.is_dir() and (
                        "demo_" in child.name or "live_" in child.name
                    ):
                        dirs.append(child)
        return dirs

    def _discover_symbol_dirs(self, account_dir: Path) -> List[Path]:
        """Return symbol sub-directories (including archives if enabled)."""
        dirs: List[Path] = []
        for child in account_dir.iterdir():
            if not child.is_dir():
                continue
            name = child.name.lower()
            # Skip non-symbol directories
            if name in ("portfolio", "account_info.json"):
                continue
            if name.startswith("_archive_") and not self.include_archives:
                continue
            # Check if it contains a ledger subdirectory
            if (child / "ledger").is_dir():
                dirs.append(child)
            # Also check archive ledger directories inside symbol dirs
            if self.include_archives:
                for sub in child.iterdir():
                    if (
                        sub.is_dir()
                        and sub.name.startswith("ledger_")
                        and sub.name.endswith("_archive")
                    ):
                        dirs.append(child)
                        break
        return dirs

    @staticmethod
    def _extract_account_id(acct_dir: Path) -> Optional[int]:
        """Parse account ID from directory name like ``demo_52742894``."""
        name = acct_dir.name
        for prefix in ("demo_", "live_"):
            if name.startswith(prefix):
                try:
                    return int(name[len(prefix) :])
                except ValueError:
                    pass
        return None

    # ------------------------------------------------------------------
    # Trade loading
    # ------------------------------------------------------------------

    def _load_symbol_trades(self, symbol_dir: Path, account_id: int) -> List[TaxTrade]:
        """Load trades from a symbol directory's ledger (JSON preferred)."""
        trades: List[TaxTrade] = []

        # Primary: trades.json
        json_path = symbol_dir / "ledger" / "trades.json"
        if json_path.is_file():
            trades.extend(self._load_json(json_path, account_id))

        # Also load from archive ledger directories
        if self.include_archives:
            for sub in symbol_dir.iterdir():
                if (
                    sub.is_dir()
                    and sub.name.startswith("ledger_")
                    and sub.name.endswith("_archive")
                ):
                    archive_json = sub / "trades.json"
                    archive_csv = sub / "trades.csv"
                    if archive_json.is_file():
                        trades.extend(self._load_json(archive_json, account_id))
                    elif archive_csv.is_file():
                        trades.extend(self._load_csv(archive_csv, account_id))

        # Fallback: trades.csv (if no JSON)
        if not trades:
            csv_path = symbol_dir / "ledger" / "trades.csv"
            if csv_path.is_file():
                trades.extend(self._load_csv(csv_path, account_id))

        return trades

    def _load_json(self, path: Path, default_account_id: int) -> List[TaxTrade]:
        """Parse trades.json and return closed TaxTrade records."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return []

        raw_trades = data.get("trades", [])
        results: List[TaxTrade] = []

        for t in raw_trades:
            if t.get("status", "").upper() != "CLOSED":
                continue
            if not t.get("exit_time"):
                continue
            parsed = self._normalise_trade(t, default_account_id)
            if parsed is not None:
                results.append(parsed)

        return results

    def _load_csv(self, path: Path, default_account_id: int) -> List[TaxTrade]:
        """Parse trades.csv and return closed TaxTrade records."""
        results: List[TaxTrade] = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if row.get("status", "").upper() != "CLOSED":
                        continue
                    if not row.get("exit_time"):
                        continue
                    parsed = self._normalise_trade(row, default_account_id)
                    if parsed is not None:
                        results.append(parsed)
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
        return results

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalise_trade(
        self, raw: dict, default_account_id: int
    ) -> Optional[TaxTrade]:
        """Convert a raw trade dict (from JSON or CSV) into a TaxTrade."""
        try:
            entry_time = self._parse_datetime(raw.get("entry_time", ""))
            exit_time = self._parse_datetime(raw.get("exit_time", ""))
            if entry_time is None or exit_time is None:
                return None

            position_size = self._to_float(raw.get("position_size"))
            commission = self._to_float(raw.get("commission", 0))
            swap = self._to_float(raw.get("swap", 0))

            # Net P&L — try pnl_dollars first, then net_pnl
            net_pnl = self._to_float(raw.get("pnl_dollars"))
            if net_pnl is None:
                net_pnl = self._to_float(raw.get("net_pnl"))
            if net_pnl is None:
                # Derive from balance change
                bal_before = self._to_float(raw.get("account_balance_before"))
                bal_after = self._to_float(raw.get("account_balance_after"))
                if bal_before is not None and bal_after is not None:
                    net_pnl = bal_after - bal_before
                else:
                    net_pnl = 0.0

            # Gross P&L
            gross_pnl = self._to_float(raw.get("gross_pnl_dollars"))
            if gross_pnl is None:
                gross_pnl = self._to_float(raw.get("gross_pnl"))
            if gross_pnl is None:
                # Derive: gross = net + commission + abs(swap)
                gross_pnl = net_pnl + abs(commission) + abs(swap)

            account_id = self._to_int(raw.get("account_id")) or default_account_id

            return TaxTrade(
                trade_id=str(raw.get("trade_id", "")),
                symbol=str(raw.get("symbol", "")).upper(),
                account_id=account_id,
                direction=str(raw.get("direction", "")).upper(),
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=self._to_float(raw.get("entry_price", 0)),
                exit_price=self._to_float(raw.get("exit_price", 0)),
                position_size=position_size if position_size is not None else 0.0,
                gross_pnl_usd=gross_pnl,
                commission_usd=commission,
                swap_usd=swap,
                net_pnl_usd=net_pnl,
                exit_reason=str(raw.get("exit_reason", "")),
            )

        except Exception as exc:
            logger.warning(
                "Failed to normalise trade %s: %s",
                raw.get("trade_id", "?"),
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        s = str(value)
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _to_float(value) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_int(value) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
