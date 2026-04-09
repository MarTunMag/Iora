"""
Norwegian Tax Reporting Module for Algorithmic Trading.

Converts USD-denominated trade P&L to NOK using official Norges Bank exchange
rates and generates Skatteetaten-compatible tax reports.

Usage:
    from flint.tax import TaxReportGenerator

    generator = TaxReportGenerator(tax_year=2026)
    results, summary = generator.generate()
    paths = generator.save(results, summary)
"""

from flint.tax.norges_bank import NorgesBankClient, ExchangeRateError
from flint.tax.trade_loader import TradeLoader, TaxTrade
from flint.tax.calculator import TaxCalculator, TaxTradeResult, TaxSummary
from flint.tax.report_generator import TaxReportGenerator

__all__ = [
    "TaxReportGenerator",
    "NorgesBankClient",
    "ExchangeRateError",
    "TaxCalculator",
    "TaxTradeResult",
    "TaxSummary",
    "TradeLoader",
    "TaxTrade",
]
