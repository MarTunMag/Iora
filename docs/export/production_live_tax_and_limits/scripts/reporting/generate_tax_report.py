#!/usr/bin/env python3
"""
CLI entry point for Norwegian tax report generation.

Usage:
    python scripts/reporting/generate_tax_report.py --year 2026
    python scripts/reporting/generate_tax_report.py --year 2026 --account 52742894
    python scripts/reporting/generate_tax_report.py --year 2026 --no-archives
    python scripts/reporting/generate_tax_report.py --year 2026 --output-dir reports/tax/custom/
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure flint package is importable (works without pip install -e .)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from flint.tax import TaxReportGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Generate Norwegian tax report from trade ledger data."
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Tax year to report on (e.g. 2026)",
    )
    parser.add_argument(
        "--account",
        type=int,
        default=None,
        help="Filter to a specific MT5 account ID",
    )
    parser.add_argument(
        "--no-archives",
        action="store_true",
        help="Exclude archived ledger directories",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Custom output directory (default: reports/tax/{year}/)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    output_dir = Path(args.output_dir) if args.output_dir else None

    generator = TaxReportGenerator(
        tax_year=args.year,
        account_id=args.account,
        include_archives=not args.no_archives,
        output_dir=output_dir,
    )

    print(f"\nGenerating tax report for {args.year}...")
    if args.account:
        print(f"  Account filter: {args.account}")
    print()

    results, summary = generator.generate()

    if not results:
        print(f"No closed trades found for tax year {args.year}.")
        print(
            "Check that ledger files exist under data/live/execution/ or data/live/accounts/"
        )
        sys.exit(0)

    paths = generator.save(results, summary)

    # Print summary
    print("=" * 60)
    print(f"  TAX REPORT {args.year} -- SUMMARY")
    print("=" * 60)
    print(f"  Total trades:        {summary.total_trades}")
    print(f"  Winning / Losing:    {summary.winning_trades} / {summary.losing_trades}")
    print()
    print(f"  Total gains (NOK):   {summary.total_gains_nok:>12,.2f}")
    print(f"  Total losses (NOK):  {summary.total_losses_nok:>12,.2f}")
    print(f"  Net result (NOK):    {summary.net_result_nok:>12,.2f}")
    print()
    if summary.estimated_tax_nok > 0:
        print(f"  Estimated tax (22%): {summary.estimated_tax_nok:>12,.2f}")
    else:
        print(f"  Loss carryforward:   {summary.loss_carryforward_nok:>12,.2f}")
    print()
    print("  Output files:")
    for fmt, path in paths.items():
        print(f"    {fmt.upper():>4}: {path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
