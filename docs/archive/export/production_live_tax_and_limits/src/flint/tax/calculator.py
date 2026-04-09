"""
Tax Calculator — NOK conversion and aggregate tax math.

Converts each trade's USD P&L to NOK using the exit-date exchange rate,
then aggregates into a TaxSummary with gains, losses, per-symbol, per-month
breakdowns, and estimated tax at 22%.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from flint.tax.norges_bank import NorgesBankClient
from flint.tax.trade_loader import TaxTrade

logger = logging.getLogger(__name__)

# Norwegian capital income tax rate for forex/CFD
_TAX_RATE = 0.22


@dataclass(slots=True)
class TaxTradeResult:
    """A TaxTrade enriched with NOK-converted amounts."""

    # Original trade fields
    trade_id: str
    symbol: str
    account_id: int
    direction: str
    entry_time: str  # ISO string
    exit_time: str  # ISO string
    entry_price: float
    exit_price: float
    position_size: float
    gross_pnl_usd: float
    commission_usd: float
    swap_usd: float
    net_pnl_usd: float
    exit_reason: str

    # NOK conversion fields
    usd_nok_rate: float
    rate_date: str  # The business day the rate is from (may differ from exit date)
    gross_pnl_nok: float
    commission_nok: float
    swap_nok: float
    net_pnl_nok: float

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "account_id": self.account_id,
            "direction": self.direction,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "gross_pnl_usd": round(self.gross_pnl_usd, 2),
            "commission_usd": round(self.commission_usd, 2),
            "swap_usd": round(self.swap_usd, 2),
            "net_pnl_usd": round(self.net_pnl_usd, 2),
            "exit_reason": self.exit_reason,
            "usd_nok_rate": round(self.usd_nok_rate, 4),
            "rate_date": self.rate_date,
            "gross_pnl_nok": round(self.gross_pnl_nok, 2),
            "commission_nok": round(self.commission_nok, 2),
            "swap_nok": round(self.swap_nok, 2),
            "net_pnl_nok": round(self.net_pnl_nok, 2),
        }


@dataclass(slots=True)
class SymbolSummary:
    """Per-symbol aggregate."""

    symbol: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_gains_nok: float = 0.0
    total_losses_nok: float = 0.0
    net_result_nok: float = 0.0
    total_commission_nok: float = 0.0
    total_swap_nok: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_gains_nok": round(self.total_gains_nok, 2),
            "total_losses_nok": round(self.total_losses_nok, 2),
            "net_result_nok": round(self.net_result_nok, 2),
            "total_commission_nok": round(self.total_commission_nok, 2),
            "total_swap_nok": round(self.total_swap_nok, 2),
        }


@dataclass(slots=True)
class MonthSummary:
    """Per-month aggregate."""

    month: str = ""  # "YYYY-MM"
    total_trades: int = 0
    total_gains_nok: float = 0.0
    total_losses_nok: float = 0.0
    net_result_nok: float = 0.0

    def to_dict(self) -> dict:
        return {
            "month": self.month,
            "total_trades": self.total_trades,
            "total_gains_nok": round(self.total_gains_nok, 2),
            "total_losses_nok": round(self.total_losses_nok, 2),
            "net_result_nok": round(self.net_result_nok, 2),
        }


@dataclass(slots=True)
class TaxSummary:
    """Year-level tax aggregates."""

    tax_year: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_gains_nok: float = 0.0
    total_losses_nok: float = 0.0
    net_result_nok: float = 0.0
    total_commission_nok: float = 0.0
    total_swap_nok: float = 0.0
    estimated_tax_nok: float = 0.0
    loss_carryforward_nok: float = 0.0
    per_symbol: dict[str, SymbolSummary] = field(default_factory=dict)
    per_month: dict[str, MonthSummary] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tax_year": self.tax_year,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_gains_nok": round(self.total_gains_nok, 2),
            "total_losses_nok": round(self.total_losses_nok, 2),
            "net_result_nok": round(self.net_result_nok, 2),
            "total_commission_nok": round(self.total_commission_nok, 2),
            "total_swap_nok": round(self.total_swap_nok, 2),
            "estimated_tax_nok": round(self.estimated_tax_nok, 2),
            "loss_carryforward_nok": round(self.loss_carryforward_nok, 2),
            "per_symbol": {k: v.to_dict() for k, v in sorted(self.per_symbol.items())},
            "per_month": {k: v.to_dict() for k, v in sorted(self.per_month.items())},
        }


class TaxCalculator:
    """Convert trades to NOK and compute tax aggregates."""

    def __init__(self, client: NorgesBankClient = None):
        self.client = client or NorgesBankClient()

    def calculate(
        self, trades: list[TaxTrade], tax_year: int
    ) -> tuple[list[TaxTradeResult], TaxSummary]:
        """
        Convert each trade to NOK and return (results, summary).

        Args:
            trades: Closed trades (already filtered by year).
            tax_year: The tax year for the summary.

        Returns:
            Tuple of (list of per-trade results, aggregate summary).
        """
        results: List[TaxTradeResult] = []
        summary = TaxSummary(tax_year=tax_year)

        sym_agg: Dict[str, SymbolSummary] = defaultdict(SymbolSummary)
        month_agg: Dict[str, MonthSummary] = defaultdict(MonthSummary)

        for trade in trades:
            exit_date = trade.exit_time.date()
            rate, rate_date = self.client.get_rate_with_date(exit_date)

            gross_nok = trade.gross_pnl_usd * rate
            commission_nok = trade.commission_usd * rate
            swap_nok = trade.swap_usd * rate
            net_nok = trade.net_pnl_usd * rate

            result = TaxTradeResult(
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                account_id=trade.account_id,
                direction=trade.direction,
                entry_time=trade.entry_time.isoformat(),
                exit_time=trade.exit_time.isoformat(),
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                position_size=trade.position_size,
                gross_pnl_usd=trade.gross_pnl_usd,
                commission_usd=trade.commission_usd,
                swap_usd=trade.swap_usd,
                net_pnl_usd=trade.net_pnl_usd,
                exit_reason=trade.exit_reason,
                usd_nok_rate=rate,
                rate_date=rate_date.isoformat(),
                gross_pnl_nok=gross_nok,
                commission_nok=commission_nok,
                swap_nok=swap_nok,
                net_pnl_nok=net_nok,
            )
            results.append(result)

            # ---- Aggregate into summary ----
            summary.total_trades += 1
            summary.total_commission_nok += commission_nok
            summary.total_swap_nok += swap_nok

            if net_nok >= 0:
                summary.winning_trades += 1
                summary.total_gains_nok += net_nok
            else:
                summary.losing_trades += 1
                summary.total_losses_nok += net_nok  # negative

            # Per-symbol
            ss = sym_agg[trade.symbol]
            ss.symbol = trade.symbol
            ss.total_trades += 1
            ss.total_commission_nok += commission_nok
            ss.total_swap_nok += swap_nok
            if net_nok >= 0:
                ss.winning_trades += 1
                ss.total_gains_nok += net_nok
            else:
                ss.losing_trades += 1
                ss.total_losses_nok += net_nok
            ss.net_result_nok += net_nok

            # Per-month
            month_key = trade.exit_time.strftime("%Y-%m")
            ms = month_agg[month_key]
            ms.month = month_key
            ms.total_trades += 1
            if net_nok >= 0:
                ms.total_gains_nok += net_nok
            else:
                ms.total_losses_nok += net_nok
            ms.net_result_nok += net_nok

        # Finalize summary
        summary.net_result_nok = summary.total_gains_nok + summary.total_losses_nok
        if summary.net_result_nok > 0:
            summary.estimated_tax_nok = summary.net_result_nok * _TAX_RATE
            summary.loss_carryforward_nok = 0.0
        else:
            summary.estimated_tax_nok = 0.0
            summary.loss_carryforward_nok = abs(summary.net_result_nok)

        summary.per_symbol = dict(sym_agg)
        summary.per_month = dict(month_agg)

        logger.info(
            "Tax calculation complete: %d trades, net NOK %.2f, estimated tax NOK %.2f",
            summary.total_trades,
            summary.net_result_nok,
            summary.estimated_tax_nok,
        )
        return results, summary
