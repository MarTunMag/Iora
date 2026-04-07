"""
Tax Report Generator — Orchestrates the full pipeline and writes output files.

Produces three output files:
  - tax_report_{year}.json   — structured data (metadata, summary, trades)
  - tax_trades_{year}.csv    — one row per trade for spreadsheet import
  - skatterapport_{year}.txt — Norwegian-language formatted report for accountant
"""

from __future__ import annotations

import csv
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from flint.paths import get_tax_report_dir
from flint.tax.calculator import TaxCalculator, TaxSummary, TaxTradeResult
from flint.tax.norges_bank import NorgesBankClient
from flint.tax.trade_loader import TradeLoader

logger = logging.getLogger(__name__)


class TaxReportGenerator:
    """End-to-end tax report pipeline."""

    def __init__(
        self,
        tax_year: int,
        account_id: Optional[int] = None,
        include_archives: bool = True,
        output_dir: Optional[Path] = None,
    ):
        self.tax_year = tax_year
        self.account_id = account_id
        self.include_archives = include_archives
        self.output_dir = (
            Path(output_dir) if output_dir else get_tax_report_dir(tax_year)
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def generate(self) -> Tuple[List[TaxTradeResult], TaxSummary]:
        """Run the full pipeline: load trades, fetch rates, calculate NOK."""
        loader = TradeLoader(
            account_id=self.account_id,
            include_archives=self.include_archives,
        )
        trades = loader.load(self.tax_year)

        if not trades:
            logger.warning("No trades found for tax year %d", self.tax_year)
            return [], TaxSummary(tax_year=self.tax_year)

        client = NorgesBankClient()
        calculator = TaxCalculator(client=client)
        return calculator.calculate(trades, self.tax_year)

    def save(
        self,
        results: List[TaxTradeResult],
        summary: TaxSummary,
    ) -> Dict[str, Path]:
        """Write JSON, CSV, and TXT reports. Returns dict of output paths."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        paths = {}
        paths["json"] = self._write_json(results, summary)
        paths["csv"] = self._write_csv(results)
        paths["txt"] = self._write_txt(results, summary)

        for fmt, path in paths.items():
            logger.info("Wrote %s report: %s", fmt.upper(), path)

        return paths

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------

    def _write_json(self, results: List[TaxTradeResult], summary: TaxSummary) -> Path:
        path = self.output_dir / f"tax_report_{self.tax_year}.json"
        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "tax_year": self.tax_year,
                "account_id": self.account_id,
                "exchange_rate_source": "Norges Bank",
                "currency_pair": "USD/NOK",
                "tax_rate": 0.22,
            },
            "summary": summary.to_dict(),
            "per_symbol": {
                k: v.to_dict() for k, v in sorted(summary.per_symbol.items())
            },
            "per_month": {k: v.to_dict() for k, v in sorted(summary.per_month.items())},
            "trades": [r.to_dict() for r in results],
        }
        self._atomic_write_json(path, data)
        return path

    # ------------------------------------------------------------------
    # CSV output
    # ------------------------------------------------------------------

    def _write_csv(self, results: List[TaxTradeResult]) -> Path:
        path = self.output_dir / f"tax_trades_{self.tax_year}.csv"
        fieldnames = [
            "exit_date",
            "symbol",
            "direction",
            "position_size",
            "entry_price",
            "exit_price",
            "exit_reason",
            "gross_pnl_usd",
            "commission_usd",
            "swap_usd",
            "net_pnl_usd",
            "usd_nok_rate",
            "rate_date",
            "gross_pnl_nok",
            "commission_nok",
            "swap_nok",
            "net_pnl_nok",
        ]

        rows = []
        for r in results:
            exit_dt = r.exit_time[:10] if len(r.exit_time) >= 10 else r.exit_time
            rows.append(
                {
                    "exit_date": exit_dt,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "position_size": r.position_size,
                    "entry_price": r.entry_price,
                    "exit_price": r.exit_price,
                    "exit_reason": r.exit_reason,
                    "gross_pnl_usd": round(r.gross_pnl_usd, 2),
                    "commission_usd": round(r.commission_usd, 2),
                    "swap_usd": round(r.swap_usd, 2),
                    "net_pnl_usd": round(r.net_pnl_usd, 2),
                    "usd_nok_rate": round(r.usd_nok_rate, 4),
                    "rate_date": r.rate_date,
                    "gross_pnl_nok": round(r.gross_pnl_nok, 2),
                    "commission_nok": round(r.commission_nok, 2),
                    "swap_nok": round(r.swap_nok, 2),
                    "net_pnl_nok": round(r.net_pnl_nok, 2),
                }
            )

        self._atomic_write_csv(path, fieldnames, rows)
        return path

    # ------------------------------------------------------------------
    # TXT output (Norwegian language)
    # ------------------------------------------------------------------

    def _write_txt(self, results: List[TaxTradeResult], summary: TaxSummary) -> Path:
        path = self.output_dir / f"skatterapport_{self.tax_year}.txt"
        lines = self._format_norwegian_report(results, summary)
        self._atomic_write_text(path, "\n".join(lines))
        return path

    def _format_norwegian_report(
        self, results: List[TaxTradeResult], summary: TaxSummary
    ) -> List[str]:
        s = summary
        lines: List[str] = []
        sep = "=" * 72

        # Header
        lines.append(sep)
        lines.append(f"  SKATTERAPPORT {self.tax_year}")
        lines.append("  Algoritmisk Valutahandel (Forex/CFD)")
        lines.append(f"  Generert: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        if self.account_id:
            lines.append(f"  Konto: {self.account_id}")
        lines.append(sep)
        lines.append("")

        # ---- Sammendrag ----
        lines.append("1. SAMMENDRAG")
        lines.append("-" * 40)
        lines.append(f"  Antall handler:            {s.total_trades:>8}")
        lines.append(f"  Vinnende handler:          {s.winning_trades:>8}")
        lines.append(f"  Tapende handler:           {s.losing_trades:>8}")
        lines.append("")
        lines.append(f"  Totale gevinster (NOK):    {s.total_gains_nok:>12,.2f}")
        lines.append(f"  Totale tap (NOK):          {s.total_losses_nok:>12,.2f}")
        lines.append(f"  Nettoresultat (NOK):       {s.net_result_nok:>12,.2f}")
        lines.append("")
        lines.append(f"  Total provisjon (NOK):     {s.total_commission_nok:>12,.2f}")
        lines.append(f"  Total swap (NOK):          {s.total_swap_nok:>12,.2f}")
        lines.append("")

        if s.estimated_tax_nok > 0:
            lines.append(f"  Estimert skatt (22%):      {s.estimated_tax_nok:>12,.2f}")
        else:
            lines.append(
                f"  Fremforbart tap:           {s.loss_carryforward_nok:>12,.2f}"
            )
        lines.append("")

        # ---- Skattemeldingen ----
        lines.append("2. SKATTEMELDINGEN")
        lines.append("-" * 40)
        lines.append("  Rapporteres under:")
        lines.append("    Gevinst/tap ved realisasjon av andre finansielle produkter")
        lines.append("")
        lines.append("  Valutahandel (forex) og CFD-kontrakter beskattes som")
        lines.append("  alminnelig inntekt med 22% skattesats.")
        lines.append("")
        if s.net_result_nok > 0:
            lines.append(f"  Skattepliktig gevinst:     {s.net_result_nok:>12,.2f} NOK")
        else:
            lines.append(
                f"  Fradragsberettiget tap:    {abs(s.net_result_nok):>12,.2f} NOK"
            )
            lines.append("  Tap kan fremfores til senere ar (skatteloven SS 14-6).")
        lines.append("")
        lines.append("  Provisjon og swap er allerede trukket fra i nettoresultatet.")
        lines.append("  Ytterligere fradrag (VPS, datautstyr, programvare) kan")
        lines.append("  rapporteres separat etter avtale med regnskapsforer.")
        lines.append("")

        # ---- Per Symbol ----
        lines.append("3. PER SYMBOL")
        lines.append("-" * 40)
        lines.append(
            f"  {'Symbol':<10} {'Handler':>7} {'Gevinst NOK':>14} "
            f"{'Tap NOK':>14} {'Netto NOK':>14}"
        )
        lines.append("  " + "-" * 59)
        for sym in sorted(s.per_symbol.keys()):
            ps = s.per_symbol[sym]
            lines.append(
                f"  {ps.symbol:<10} {ps.total_trades:>7} "
                f"{ps.total_gains_nok:>14,.2f} {ps.total_losses_nok:>14,.2f} "
                f"{ps.net_result_nok:>14,.2f}"
            )
        lines.append("")

        # ---- Per Maaned ----
        lines.append("4. PER MAANED")
        lines.append("-" * 40)
        lines.append(
            f"  {'Maaned':<10} {'Handler':>7} {'Gevinst NOK':>14} "
            f"{'Tap NOK':>14} {'Netto NOK':>14}"
        )
        lines.append("  " + "-" * 59)
        for month_key in sorted(s.per_month.keys()):
            pm = s.per_month[month_key]
            lines.append(
                f"  {pm.month:<10} {pm.total_trades:>7} "
                f"{pm.total_gains_nok:>14,.2f} {pm.total_losses_nok:>14,.2f} "
                f"{pm.net_result_nok:>14,.2f}"
            )
        lines.append("")

        # ---- Valutakurser ----
        lines.append("5. VALUTAKURSER")
        lines.append("-" * 40)
        lines.append("  Kilde: Norges Bank (offisielle daglige valutakurser)")
        lines.append("  Valutapar: USD/NOK")
        lines.append("  Ved helg/helligdag brukes siste virkedag.")
        lines.append("  API: data.norges-bank.no")
        lines.append("")

        if results:
            rates_used = sorted(set((r.rate_date, r.usd_nok_rate) for r in results))
            lines.append(f"  Antall unike kursdager brukt: {len(rates_used)}")
            if rates_used:
                min_rate = min(r[1] for r in rates_used)
                max_rate = max(r[1] for r in rates_used)
                lines.append(f"  Laveste kurs:  {min_rate:.4f}")
                lines.append(f"  Hoyeste kurs:  {max_rate:.4f}")
        lines.append("")

        # ---- Footer ----
        lines.append(sep)
        lines.append("  Denne rapporten er generert automatisk fra handelsloggen.")
        lines.append("  Kontroller tallene med regnskapsforer for skattemeldingen.")
        lines.append(sep)
        lines.append("")

        return lines

    # ------------------------------------------------------------------
    # Atomic file writers
    # ------------------------------------------------------------------

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._atomic_write_text(path, content)

    def _atomic_write_csv(
        self, path: Path, fieldnames: List[str], rows: List[dict]
    ) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.output_dir), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _atomic_write_text(self, path: Path, content: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.output_dir), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            Path(tmp).replace(path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
