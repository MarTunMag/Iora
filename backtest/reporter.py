"""
Performance Reporter for Flint Backtest System.

Generates JSON reports, human-readable TXT summaries, and matplotlib charts
for backtest runs. Adapted from the Aris PerformanceReporter for the Flint
rule-based trading system.

Charts use a dark theme matching the Flint Dash viewer aesthetic.

Key capabilities:
- JSON report generation with full metrics breakdown
- Human-readable TXT summaries
- Charts: equity curve, drawdown, monthly heatmap, R distribution, exit analysis
- Windows-compatible PNG output (RGBA->RGB fix)
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import logging

import numpy as np
import pandas as pd

from flint.paths import REPORTS_DIR
from flint.backtest.metrics import PerformanceMetrics, TradeRecord, interpret_sqn

# Optional matplotlib for chart generation
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.colors as mcolors
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# Optional PIL for RGBA -> RGB conversion (fixes Windows Photos hanging on RGBA PNGs)
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dark theme colours (matches Flint Dash viewer)
# ---------------------------------------------------------------------------
_BG = "#0e1117"
_PANEL_BG = "#161b22"
_TEXT = "#c9d1d9"
_GRID = "#30363d"
_GREEN = "#3fb950"
_RED = "#f85149"
_BLUE = "#58a6ff"
_ORANGE = "#d29922"
_PURPLE = "#bc8cff"
_CYAN = "#39d2c0"


def _apply_dark_theme() -> None:
    """Apply Flint dark theme to matplotlib."""
    if not HAS_MATPLOTLIB:
        return
    plt.rcParams.update({
        "figure.facecolor": _BG,
        "axes.facecolor": _PANEL_BG,
        "axes.edgecolor": _GRID,
        "axes.labelcolor": _TEXT,
        "text.color": _TEXT,
        "xtick.color": _TEXT,
        "ytick.color": _TEXT,
        "grid.color": _GRID,
        "grid.alpha": 0.4,
        "legend.facecolor": _PANEL_BG,
        "legend.edgecolor": _GRID,
        "legend.labelcolor": _TEXT,
        "savefig.facecolor": _BG,
        "savefig.edgecolor": _BG,
        "font.size": 10,
    })


def _save_chart_png(fig: Any, path: Path, dpi: int = 120) -> None:
    """Save matplotlib figure as RGB PNG (Windows Photos compatible).

    Matplotlib Agg backend always produces RGBA. Windows Photos app
    can hang on RGBA PNGs. This converts to RGB with a dark background.
    """
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight",
                facecolor=_BG, edgecolor=_BG, transparent=False)
    plt.close(fig)

    # Convert RGBA -> RGB for Windows compatibility
    if HAS_PIL:
        try:
            img = PILImage.open(str(path))
            if img.mode == "RGBA":
                # Use dark background instead of white to match theme
                bg_rgb = tuple(int(_BG.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                rgb = PILImage.new("RGB", img.size, bg_rgb)
                rgb.paste(img, mask=img.split()[3])
                img.close()
                rgb.save(str(path), "PNG", optimize=True)
                rgb.close()
        except Exception as e:
            logger.warning("RGBA->RGB conversion failed: %s", e)


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

class PerformanceReporter:
    """Generate performance reports, text summaries, and charts for backtest runs.

    Example::

        from flint.backtest.reporter import PerformanceReporter
        from flint.backtest.metrics import PerformanceMetrics, TradeRecord

        reporter = PerformanceReporter()
        report = reporter.generate_report(
            metrics_result=metrics.calculate_all(),
            symbol="GBPUSD",
            run_name="growth_v1",
            trades=trade_list,
        )
        reporter.save_report(report, "GBPUSD_growth_v1.json")
        reporter.save_text_summary(report, "GBPUSD_growth_v1.txt")
        reporter.generate_all_charts(trade_list, 10_000.0, REPORTS_DIR / "charts")
    """

    def __init__(self, reports_dir: Path | None = None) -> None:
        self.reports_dir = Path(reports_dir) if reports_dir else REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        metrics_result: dict,
        symbol: str,
        run_name: str,
        trades: list[TradeRecord],
        initial_balance: float = 10_000.0,
    ) -> dict:
        """Build a full report dict from metrics and trade list.

        Args:
            metrics_result: Output of ``PerformanceMetrics.calculate_all()``.
            symbol: Instrument symbol (e.g. ``"GBPUSD"``).
            run_name: Human-readable run identifier.
            trades: List of ``TradeRecord`` dataclass instances.
            initial_balance: Starting account balance in dollars.

        Returns:
            Nested dict ready for JSON serialisation.
        """
        trades_df = self._trades_to_df(trades)
        advanced = self._calculate_advanced_metrics(metrics_result, trades_df, initial_balance)
        distribution = self._analyze_trade_distribution(trades_df)

        date_range = self._date_range_str(trades)

        report: dict[str, Any] = {
            "metadata": {
                "symbol": symbol,
                "run_name": run_name,
                "timestamp": datetime.now().isoformat(),
                "date_range": date_range,
                "initial_balance": initial_balance,
                "total_trades": metrics_result.get("total_trades", 0),
            },
            "core_metrics": {
                "total_r": metrics_result.get("total_r", 0.0),
                "total_trades": metrics_result.get("total_trades", 0),
                "win_rate": metrics_result.get("win_rate", 0.0),
                "profit_factor": metrics_result.get("profit_factor", 0.0),
                "expectancy": metrics_result.get("expectancy", 0.0),
                "sqn": metrics_result.get("sqn", 0.0),
                "sqn_interpretation": interpret_sqn(metrics_result.get("sqn", 0.0)),
                "sharpe_ratio": metrics_result.get("sharpe", 0.0),
                "sortino_ratio": metrics_result.get("sortino", advanced.get("sortino_ratio", 0.0)),
                "calmar_ratio": metrics_result.get("calmar", advanced.get("calmar_ratio", 0.0)),
            },
            "drawdown": {
                "max_drawdown_pct": metrics_result.get("max_drawdown_pct", 0.0),
                "max_drawdown_duration": metrics_result.get("max_drawdown_duration_trades", 0),
                "avg_drawdown_pct": advanced.get("avg_drawdown_pct", 0.0),
            },
            "returns": {
                "total_pnl": metrics_result.get("total_pnl", 0.0),
                "total_return_pct": advanced.get("total_return_pct", 0.0),
                "cagr": advanced.get("cagr", 0.0),
            },
            "trade_analysis": {
                "num_wins": metrics_result.get("num_wins", 0),
                "num_losses": metrics_result.get("num_losses", 0),
                "avg_win_r": metrics_result.get("avg_win_r", 0.0),
                "avg_loss_r": metrics_result.get("avg_loss_r", 0.0),
                "largest_win_r": metrics_result.get("largest_win_r", advanced.get("largest_win_r", 0.0)),
                "largest_loss_r": metrics_result.get("largest_loss_r", advanced.get("largest_loss_r", 0.0)),
                "avg_holding_hours": metrics_result.get("avg_holding_hours", 0.0),
                "max_win_streak": metrics_result.get("max_win_streak", advanced.get("max_win_streak", 0)),
                "max_loss_streak": metrics_result.get("max_loss_streak", advanced.get("max_loss_streak", 0)),
            },
            "monthly_performance": {
                "positive_months": advanced.get("positive_months", 0),
                "negative_months": advanced.get("negative_months", 0),
                "best_month_r": advanced.get("best_month_r", 0.0),
                "worst_month_r": advanced.get("worst_month_r", 0.0),
                "monthly_returns": advanced.get("monthly_returns", []),
            },
            "exit_reasons": distribution.get("by_exit_reason", {}),
            "time_distribution": {
                "by_entry_hour": distribution.get("by_entry_hour", {}),
                "by_day_of_week": distribution.get("by_day_of_week", {}),
            },
        }

        return report

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_report(self, report: dict, filename: str) -> Path:
        """Save report dict as JSON to ``REPORTS_DIR``.

        Args:
            report: Report dict from :meth:`generate_report`.
            filename: Target filename (e.g. ``"GBPUSD_growth_v1.json"``).

        Returns:
            Absolute path to the saved file.
        """
        filepath = self.reports_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as fh:
            json.dump(report, fh, indent=2, default=str)
        logger.info("Report saved: %s", filepath)
        return filepath

    def save_text_summary(self, report: dict, filename: str) -> Path:
        """Save a human-readable TXT summary to ``REPORTS_DIR``.

        Args:
            report: Report dict from :meth:`generate_report`.
            filename: Target filename (e.g. ``"GBPUSD_growth_v1.txt"``).

        Returns:
            Absolute path to the saved file.
        """
        text = self._format_text_summary(report)
        filepath = self.reports_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(text, encoding="utf-8")
        logger.info("Text summary saved: %s", filepath)
        return filepath

    # ------------------------------------------------------------------
    # Chart generation
    # ------------------------------------------------------------------

    def plot_equity_curve(
        self,
        trades: list[TradeRecord],
        initial_balance: float = 10_000.0,
        save_path: Path | None = None,
    ) -> None:
        """Plot equity curve over time.

        Args:
            trades: Trade records with ``pnl`` and ``exit_time``.
            initial_balance: Starting balance.
            save_path: If provided, save PNG to this path.
        """
        if not HAS_MATPLOTLIB or not trades:
            return
        _apply_dark_theme()

        times, balances = self._build_equity_series(trades, initial_balance)

        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(times, balances, linewidth=1.2, color=_BLUE)
        ax.fill_between(times, initial_balance, balances, alpha=0.10, color=_BLUE)
        ax.axhline(y=initial_balance, color=_GRID, linestyle="--", alpha=0.6)

        peak_idx = int(np.argmax(balances))
        ax.scatter([times[peak_idx]], [balances[peak_idx]], color=_GREEN, s=80, zorder=5,
                   label=f"Peak: ${balances[peak_idx]:,.0f}")

        ax.set_title("Equity Curve", fontsize=12, fontweight="bold")
        ax.set_ylabel("Balance ($)")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        if isinstance(times[0], (pd.Timestamp, datetime)):
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            fig.autofmt_xdate()
        ax.grid(True)
        ax.legend(loc="upper left")
        plt.tight_layout()

        if save_path:
            _save_chart_png(fig, Path(save_path))
        else:
            plt.show()

    def plot_drawdown(
        self,
        trades: list[TradeRecord],
        initial_balance: float = 10_000.0,
        save_path: Path | None = None,
    ) -> None:
        """Plot drawdown curve as percentage of initial balance.

        Args:
            trades: Trade records with ``pnl`` and ``exit_time``.
            initial_balance: Starting balance.
            save_path: If provided, save PNG to this path.
        """
        if not HAS_MATPLOTLIB or not trades:
            return
        _apply_dark_theme()

        _times, balances = self._build_equity_series(trades, initial_balance)
        balances_arr = np.array(balances)
        peaks = np.maximum.accumulate(balances_arr)
        dd_pct = np.where(peaks > 0, (balances_arr - peaks) / peaks * 100, 0.0)

        fig, ax = plt.subplots(figsize=(14, 4))
        ax.fill_between(range(len(dd_pct)), dd_pct, 0, color=_RED, alpha=0.35)
        ax.plot(dd_pct, color=_RED, linewidth=0.8)
        min_dd = float(dd_pct.min())
        ax.axhline(y=min_dd, color="#ff6b6b", linestyle="--", alpha=0.7,
                   label=f"Max DD: {min_dd:.1f}%")
        ax.set_title("Drawdown", fontsize=12, fontweight="bold")
        ax.set_ylabel("Drawdown (%)")
        ax.set_xlabel("Trade #")
        ax.grid(True)
        ax.legend(loc="lower left", fontsize=9)
        plt.tight_layout()

        if save_path:
            _save_chart_png(fig, Path(save_path))
        else:
            plt.show()

    def plot_monthly_returns(
        self,
        trades: list[TradeRecord],
        save_path: Path | None = None,
    ) -> None:
        """Plot monthly returns as a year x month heatmap.

        Args:
            trades: Trade records with ``return_r`` and ``exit_time``.
            save_path: If provided, save PNG to this path.
        """
        if not HAS_MATPLOTLIB or not trades:
            return
        _apply_dark_theme()

        df = self._trades_to_df(trades)
        if "exit_time" not in df.columns or df.empty:
            return

        df["exit_time"] = pd.to_datetime(df["exit_time"])
        df["year"] = df["exit_time"].dt.year
        df["month"] = df["exit_time"].dt.month

        pivot = df.pivot_table(values="return_r", index="year", columns="month",
                               aggfunc="sum", fill_value=0.0)
        # Ensure all 12 months present
        for m in range(1, 13):
            if m not in pivot.columns:
                pivot[m] = 0.0
        pivot = pivot[sorted(pivot.columns)]

        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        fig, ax = plt.subplots(figsize=(12, max(3, len(pivot) * 0.6 + 1)))

        # Diverging colormap: red-black-green
        vmax = max(abs(pivot.values.min()), abs(pivot.values.max()), 1.0)
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "flint_rg", [_RED, _PANEL_BG, _GREEN])

        im = ax.imshow(pivot.values, cmap=cmap, aspect="auto",
                       vmin=-vmax, vmax=vmax)

        ax.set_xticks(range(12))
        ax.set_xticklabels(month_labels)
        ax.set_yticks(range(len(pivot)))
        ax.set_yticklabels([str(y) for y in pivot.index])

        # Annotate cells
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                if val != 0:
                    colour = "#ffffff" if abs(val) > vmax * 0.5 else _TEXT
                    ax.text(j, i, f"{val:+.1f}", ha="center", va="center",
                            fontsize=8, color=colour)

        ax.set_title("Monthly Returns (R)", fontsize=12, fontweight="bold")
        fig.colorbar(im, ax=ax, label="R-multiples", shrink=0.8)
        plt.tight_layout()

        if save_path:
            _save_chart_png(fig, Path(save_path))
        else:
            plt.show()

    def plot_r_distribution(
        self,
        trades: list[TradeRecord],
        save_path: Path | None = None,
    ) -> None:
        """Plot histogram of R-multiples.

        Args:
            trades: Trade records with ``return_r``.
            save_path: If provided, save PNG to this path.
        """
        if not HAS_MATPLOTLIB or not trades:
            return
        _apply_dark_theme()

        returns_r = np.array([t.return_r for t in trades])

        fig, ax = plt.subplots(figsize=(10, 5))
        bins = np.arange(
            np.floor(returns_r.min()) - 0.5,
            np.ceil(returns_r.max()) + 1.0,
            0.5,
        )
        n, bin_edges, patches = ax.hist(returns_r, bins=bins, edgecolor=_GRID,
                                         linewidth=0.5, alpha=0.85)
        # Colour bars green/red
        for patch, left_edge in zip(patches, bin_edges):
            if left_edge + 0.25 >= 0:
                patch.set_facecolor(_GREEN)
            else:
                patch.set_facecolor(_RED)

        mean_r = float(returns_r.mean())
        ax.axvline(x=mean_r, color=_ORANGE, linestyle="--", linewidth=1.5,
                   label=f"Mean: {mean_r:+.2f} R")
        ax.axvline(x=0, color=_TEXT, linestyle="-", linewidth=0.5, alpha=0.5)

        ax.set_title("R-Multiple Distribution", fontsize=12, fontweight="bold")
        ax.set_xlabel("R-Multiple")
        ax.set_ylabel("Count")
        ax.grid(True, axis="y")
        ax.legend(loc="upper right")
        plt.tight_layout()

        if save_path:
            _save_chart_png(fig, Path(save_path))
        else:
            plt.show()

    def plot_exit_analysis(
        self,
        trades: list[TradeRecord],
        save_path: Path | None = None,
    ) -> None:
        """Plot breakdown of trades by exit reason.

        Shows a horizontal bar chart with count, average R, and total R per
        exit reason.

        Args:
            trades: Trade records with ``exit_reason`` and ``return_r``.
            save_path: If provided, save PNG to this path.
        """
        if not HAS_MATPLOTLIB or not trades:
            return
        _apply_dark_theme()

        df = self._trades_to_df(trades)
        if "exit_reason" not in df.columns or df.empty:
            return

        grouped = df.groupby("exit_reason")["return_r"].agg(["count", "mean", "sum"])
        grouped = grouped.sort_values("count", ascending=True)

        fig, axes = plt.subplots(1, 3, figsize=(14, max(3, len(grouped) * 0.5 + 1)))

        bar_colors = [_BLUE] * len(grouped)

        # Count
        axes[0].barh(grouped.index, grouped["count"], color=bar_colors, alpha=0.85)
        axes[0].set_title("Trade Count", fontsize=10, fontweight="bold")
        for i, v in enumerate(grouped["count"]):
            axes[0].text(v + 0.3, i, str(int(v)), va="center", fontsize=8, color=_TEXT)

        # Avg R
        colors_avg = [_GREEN if v >= 0 else _RED for v in grouped["mean"]]
        axes[1].barh(grouped.index, grouped["mean"], color=colors_avg, alpha=0.85)
        axes[1].set_title("Avg R", fontsize=10, fontweight="bold")
        axes[1].axvline(x=0, color=_TEXT, linewidth=0.5, alpha=0.5)

        # Total R
        colors_total = [_GREEN if v >= 0 else _RED for v in grouped["sum"]]
        axes[2].barh(grouped.index, grouped["sum"], color=colors_total, alpha=0.85)
        axes[2].set_title("Total R", fontsize=10, fontweight="bold")
        axes[2].axvline(x=0, color=_TEXT, linewidth=0.5, alpha=0.5)

        fig.suptitle("Exit Reason Analysis", fontsize=12, fontweight="bold", y=1.02)
        plt.tight_layout()

        if save_path:
            _save_chart_png(fig, Path(save_path))
        else:
            plt.show()

    def generate_all_charts(
        self,
        trades: list[TradeRecord],
        initial_balance: float = 10_000.0,
        output_dir: Path | None = None,
    ) -> list[Path]:
        """Generate and save all chart PNGs.

        Args:
            trades: Trade records.
            initial_balance: Starting balance.
            output_dir: Directory to save PNGs into. Defaults to
                ``REPORTS_DIR / "charts"``.

        Returns:
            List of saved file paths.
        """
        if not HAS_MATPLOTLIB:
            logger.warning("matplotlib not installed -- skipping chart generation")
            return []

        if not trades:
            logger.warning("No trades provided -- skipping chart generation")
            return []

        out = Path(output_dir) if output_dir else self.reports_dir / "charts"
        out.mkdir(parents=True, exist_ok=True)

        saved: list[Path] = []
        chart_methods: list[tuple[str, dict]] = [
            ("equity_curve", dict(trades=trades, initial_balance=initial_balance,
                                  save_path=out / "equity_curve.png")),
            ("drawdown", dict(trades=trades, initial_balance=initial_balance,
                              save_path=out / "drawdown.png")),
            ("monthly_returns", dict(trades=trades,
                                     save_path=out / "monthly_returns.png")),
            ("r_distribution", dict(trades=trades,
                                    save_path=out / "r_distribution.png")),
            ("exit_analysis", dict(trades=trades,
                                   save_path=out / "exit_analysis.png")),
        ]

        for name, kwargs in chart_methods:
            try:
                method = getattr(self, f"plot_{name}")
                method(**kwargs)
                path = kwargs["save_path"]
                if Path(path).exists():
                    saved.append(Path(path))
                    logger.info("Chart saved: %s", path)
            except Exception as exc:
                logger.warning("Chart '%s' failed: %s", name, exc)

        return saved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _trades_to_df(trades: list[TradeRecord]) -> pd.DataFrame:
        """Convert list of TradeRecord dataclasses to a DataFrame."""
        if not trades:
            return pd.DataFrame()
        return pd.DataFrame([asdict(t) for t in trades])

    @staticmethod
    def _build_equity_series(
        trades: list[TradeRecord],
        initial_balance: float,
    ) -> tuple[list, list[float]]:
        """Return (times, balances) including the initial point."""
        times = []
        balances: list[float] = []
        bal = initial_balance

        if trades and trades[0].entry_time is not None:
            times.append(trades[0].entry_time)
            balances.append(initial_balance)

        for t in trades:
            bal += t.pnl_dollars
            times.append(t.exit_time)
            balances.append(bal)

        # Fallback: use integer indices if no timestamps
        if not times:
            times = list(range(len(trades) + 1))
            bal = initial_balance
            balances = [initial_balance]
            for t in trades:
                bal += t.pnl_dollars
                balances.append(bal)

        return times, balances

    @staticmethod
    def _date_range_str(trades: list[TradeRecord]) -> str:
        """Return 'YYYY-MM-DD to YYYY-MM-DD' from trade list."""
        if not trades:
            return ""
        first = trades[0].entry_time
        last = trades[-1].exit_time
        fmt = "%Y-%m-%d"
        try:
            return f"{first.strftime(fmt)} to {last.strftime(fmt)}"
        except Exception as e:
            logger.warning("Date range formatting failed: %s", e)
            return f"{first} to {last}"

    @staticmethod
    def _calculate_advanced_metrics(
        metrics: dict,
        trades_df: pd.DataFrame,
        initial_balance: float,
    ) -> dict:
        """Calculate advanced metrics not in the base PerformanceMetrics output."""
        advanced: dict[str, Any] = {}

        if trades_df.empty:
            return advanced

        returns = trades_df["return_r"].values

        # Sortino & Calmar — use values from metrics.calculate_all() (no duplication)
        advanced["sortino_ratio"] = min(metrics.get("sortino", 0.0), 99.99)
        advanced["calmar_ratio"] = min(metrics.get("calmar", 0.0), 99.99)

        # Total return pct
        total_pnl = metrics.get("total_pnl", 0.0)
        total_return_pct = (total_pnl / initial_balance) * 100 if initial_balance > 0 else 0.0
        advanced["total_return_pct"] = float(total_return_pct)

        # CAGR
        if "exit_time" in trades_df.columns and "entry_time" in trades_df.columns:
            try:
                exit_times = pd.to_datetime(trades_df["exit_time"])
                entry_times = pd.to_datetime(trades_df["entry_time"])
                duration_days = (exit_times.max() - entry_times.min()).days
                duration_years = max(duration_days / 365.25, 0.01)
                total_return_frac = total_pnl / initial_balance if initial_balance > 0 else 0.0
                if total_return_frac > -1:
                    raw_cagr = ((1 + total_return_frac) ** (1 / duration_years) - 1) * 100
                    advanced["cagr"] = float(min(raw_cagr, 999.99))
                else:
                    advanced["cagr"] = 0.0
            except Exception as e:
                logger.warning("CAGR calculation failed: %s", e)
                advanced["cagr"] = 0.0
        else:
            advanced["cagr"] = 0.0

        # Largest win / loss (R)
        advanced["largest_win_r"] = float(returns.max()) if len(returns) > 0 else 0.0
        advanced["largest_loss_r"] = float(returns.min()) if len(returns) > 0 else 0.0

        # Win / loss streaks
        if len(returns) > 0:
            wins = (pd.Series(returns) > 0).astype(int)
            groups = (wins != wins.shift()).cumsum()
            streaks = wins.groupby(groups).agg(["sum", "count"])
            win_streaks = streaks[streaks["sum"] > 0]["count"].values
            loss_streaks = streaks[streaks["sum"] == 0]["count"].values
            advanced["max_win_streak"] = int(win_streaks.max()) if len(win_streaks) > 0 else 0
            advanced["max_loss_streak"] = int(loss_streaks.max()) if len(loss_streaks) > 0 else 0
        else:
            advanced["max_win_streak"] = 0
            advanced["max_loss_streak"] = 0

        # Monthly returns
        if "exit_time" in trades_df.columns:
            try:
                tmp = trades_df.copy()
                tmp["exit_time"] = pd.to_datetime(tmp["exit_time"])
                tmp = tmp.set_index("exit_time")
                monthly_r = tmp["return_r"].resample("ME").sum()
                advanced["monthly_returns"] = [
                    {"month": m.strftime("%Y-%m"), "r": float(r)}
                    for m, r in monthly_r.items()
                ]
                advanced["best_month_r"] = float(monthly_r.max()) if len(monthly_r) > 0 else 0.0
                advanced["worst_month_r"] = float(monthly_r.min()) if len(monthly_r) > 0 else 0.0
                advanced["positive_months"] = int((monthly_r > 0).sum())
                advanced["negative_months"] = int((monthly_r <= 0).sum())
            except Exception as e:
                logger.warning("Monthly returns calculation failed: %s", e)
                advanced["monthly_returns"] = []
                advanced["best_month_r"] = 0.0
                advanced["worst_month_r"] = 0.0
                advanced["positive_months"] = 0
                advanced["negative_months"] = 0
        else:
            advanced["monthly_returns"] = []
            advanced["best_month_r"] = 0.0
            advanced["worst_month_r"] = 0.0
            advanced["positive_months"] = 0
            advanced["negative_months"] = 0

        # Average drawdown
        if "pnl_dollars" in trades_df.columns:
            equity = initial_balance + trades_df["pnl_dollars"].cumsum().values
            peaks = np.maximum.accumulate(equity)
            dd = equity - peaks
            dd_pct = np.where(peaks > 0, dd / peaks * 100, 0.0)
            dd_periods = dd_pct[dd_pct < 0]
            advanced["avg_drawdown_pct"] = float(dd_periods.mean()) if len(dd_periods) > 0 else 0.0
        else:
            advanced["avg_drawdown_pct"] = 0.0

        return advanced

    @staticmethod
    def _analyze_trade_distribution(trades_df: pd.DataFrame) -> dict:
        """Analyze trade distribution by exit reason, hour, and day."""
        if trades_df.empty:
            return {}

        dist: dict[str, Any] = {}

        # By exit reason
        if "exit_reason" in trades_df.columns:
            grouped = trades_df.groupby("exit_reason")["return_r"].agg(["count", "mean", "sum"])
            dist["by_exit_reason"] = {
                reason: {
                    "count": int(vals["count"]),
                    "avg_r": round(float(vals["mean"]), 4),
                    "total_r": round(float(vals["sum"]), 2),
                }
                for reason, vals in grouped.to_dict("index").items()
            }

        # By entry hour
        if "entry_time" in trades_df.columns:
            try:
                tmp = trades_df.copy()
                tmp["entry_hour"] = pd.to_datetime(tmp["entry_time"]).dt.hour
                hour_g = tmp.groupby("entry_hour")["return_r"].agg(["count", "mean"])
                dist["by_entry_hour"] = {
                    int(h): {"count": int(vals["count"]), "avg_r": round(float(vals["mean"]), 4)}
                    for h, vals in hour_g.to_dict("index").items()
                }
            except Exception as e:
                logger.warning("Entry hour distribution failed: %s", e)

        # By day of week
        if "entry_time" in trades_df.columns:
            try:
                tmp = trades_df.copy()
                tmp["entry_dow"] = pd.to_datetime(tmp["entry_time"]).dt.dayofweek
                day_g = tmp.groupby("entry_dow")["return_r"].agg(["count", "mean"])
                day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                             "Friday", "Saturday", "Sunday"]
                dist["by_day_of_week"] = {
                    day_names[int(d)]: {"count": int(vals["count"]),
                                        "avg_r": round(float(vals["mean"]), 4)}
                    for d, vals in day_g.to_dict("index").items()
                }
            except Exception as e:
                logger.warning("Day of week distribution failed: %s", e)

        return dist

    def _format_text_summary(self, report: dict) -> str:
        """Build a human-readable text summary from a report dict."""
        meta = report.get("metadata", {})
        core = report.get("core_metrics", {})
        dd = report.get("drawdown", {})
        ret = report.get("returns", {})
        ta = report.get("trade_analysis", {})
        mp = report.get("monthly_performance", {})
        exits = report.get("exit_reasons", {})

        w = 70
        lines: list[str] = [
            "=" * w,
            f"FLINT BACKTEST REPORT",
            "=" * w,
            f"Symbol:          {meta.get('symbol', '')}",
            f"Run:             {meta.get('run_name', '')}",
            f"Date Range:      {meta.get('date_range', '')}",
            f"Generated:       {meta.get('timestamp', '')}",
            f"Initial Balance: ${meta.get('initial_balance', 0):,.2f}",
            "",
            "-" * w,
            "CORE METRICS",
            "-" * w,
            f"  SQN:             {core.get('sqn', 0):8.2f}  ({core.get('sqn_interpretation', '')})",
            f"  Sharpe Ratio:    {core.get('sharpe_ratio', 0):8.2f}",
            f"  Sortino Ratio:   {core.get('sortino_ratio', 0):8.2f}",
            f"  Calmar Ratio:    {core.get('calmar_ratio', 0):8.2f}",
            f"  Profit Factor:   {core.get('profit_factor', 0):8.2f}",
            f"  Win Rate:        {core.get('win_rate', 0)*100:7.1f}%",
            f"  Total R:         {core.get('total_r', 0):8.2f}",
            f"  Expectancy:      {core.get('expectancy', 0):8.4f} R/trade",
            "",
            "-" * w,
            "DRAWDOWN",
            "-" * w,
            f"  Max Drawdown:    {dd.get('max_drawdown_pct', 0):8.2f}%",
            f"  Max DD Duration: {dd.get('max_drawdown_duration', 0):8} trades",
            f"  Avg Drawdown:    {dd.get('avg_drawdown_pct', 0):8.2f}%",
            "",
            "-" * w,
            "RETURNS",
            "-" * w,
            f"  Total P&L:       ${ret.get('total_pnl', 0):>10,.2f}",
            f"  Total Return:    {ret.get('total_return_pct', 0):8.2f}%",
            f"  CAGR:            {ret.get('cagr', 0):8.2f}%",
            "",
            "-" * w,
            "TRADE STATISTICS",
            "-" * w,
            f"  Total Trades:    {core.get('total_trades', 0 if 'total_trades' not in ta else ta['total_trades']):>8}  "
            f"({ta.get('num_wins', 0)}W / {ta.get('num_losses', 0)}L)",
            f"  Avg Win:         {ta.get('avg_win_r', 0):+8.3f} R",
            f"  Avg Loss:        {ta.get('avg_loss_r', 0):+8.3f} R",
            f"  Largest Win:     {ta.get('largest_win_r', 0):+8.3f} R",
            f"  Largest Loss:    {ta.get('largest_loss_r', 0):+8.3f} R",
            f"  Avg Hold (hrs):  {ta.get('avg_holding_hours', 0):8.1f}",
            f"  Max Win Streak:  {ta.get('max_win_streak', 0):>8}",
            f"  Max Loss Streak: {ta.get('max_loss_streak', 0):>8}",
        ]

        # Monthly breakdown
        pos_m = mp.get("positive_months", 0)
        neg_m = mp.get("negative_months", 0)
        if pos_m + neg_m > 0:
            lines.extend([
                "",
                "-" * w,
                "MONTHLY PERFORMANCE",
                "-" * w,
                f"  Positive Months: {pos_m:>8}",
                f"  Negative Months: {neg_m:>8}",
                f"  Best Month:      {mp.get('best_month_r', 0):+8.2f} R",
                f"  Worst Month:     {mp.get('worst_month_r', 0):+8.2f} R",
            ])
            # Individual months
            monthly = mp.get("monthly_returns", [])
            if monthly:
                lines.append("")
                for m in monthly:
                    bar = "+" if m["r"] >= 0 else "-"
                    lines.append(f"    {m['month']}:  {m['r']:+7.2f} R  {bar * min(int(abs(m['r'])), 40)}")

        # Exit reason breakdown
        if exits:
            total_count = sum(v["count"] for v in exits.values())
            lines.extend([
                "",
                "-" * w,
                "EXIT REASONS",
                "-" * w,
            ])
            for reason, stats in sorted(exits.items(), key=lambda x: -x[1]["count"]):
                pct = stats["count"] / total_count * 100 if total_count > 0 else 0
                lines.append(
                    f"  {reason:20s}  {stats['count']:5d} ({pct:5.1f}%)  "
                    f"avg R={stats['avg_r']:+.4f}  total R={stats['total_r']:+.2f}"
                )

        lines.append("")
        lines.append("=" * w)

        return "\n".join(lines)
