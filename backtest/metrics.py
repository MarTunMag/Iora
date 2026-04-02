"""
Performance Metrics Calculator for the Flint Trading System.

Calculates comprehensive trading performance metrics including SQN, Sharpe,
Sortino, Calmar, drawdown, R-multiples, win/loss streaks, monthly/weekly/daily
returns, and profit factor.

Adapted from the Aris PerformanceMetrics engine with additional ratios,
streak tracking, dataclass-based TradeRecord, and granular return breakdowns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from flint.paths import REPORTS_DIR  # noqa: F401 — available for consumers


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TradeRecord:
    """Immutable record representing a single completed trade."""

    trade_id: str
    symbol: str
    direction: int  # 1 = LONG, -1 = SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    position_size: float  # lots
    pnl_dollars: float
    return_r: float  # P&L expressed in R-multiples
    exit_reason: str
    sl_price: float
    tp_price: float

    # Extended fields for automation
    timeframe: str = ""            # e.g. "M15", "H1"
    mode: str = ""                 # "growth" or "scalp"
    cost_dollars: float = 0.0     # total transaction cost paid
    parent_trade_id: str | None = None  # for add-on entries in Growth mode

    # Derived convenience --------------------------------------------------

    @property
    def is_winner(self) -> bool:
        return self.pnl_dollars > 0.0

    @property
    def is_loser(self) -> bool:
        return self.pnl_dollars < 0.0

    @property
    def holding_period(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time


# ---------------------------------------------------------------------------
# Performance metrics engine
# ---------------------------------------------------------------------------

class PerformanceMetrics:
    """
    Pure-calculation performance metrics engine.

    Accepts a list of :class:`TradeRecord` objects and exposes methods to
    compute a comprehensive set of trading statistics.  No file I/O is
    performed inside this class.

    Usage::

        trades: list[TradeRecord] = [...]
        pm = PerformanceMetrics(trades, initial_balance=10_000.0)
        summary = pm.calculate_all()
        equity  = pm.get_equity_curve()
        monthly = pm.get_monthly_returns()
        stats   = pm.get_trade_statistics()
    """

    def __init__(
        self,
        trades: list[TradeRecord],
        initial_balance: float = 10_000.0,
        risk_free_rate: float = 0.0,
    ) -> None:
        self._trades = sorted(trades, key=lambda t: t.exit_time)
        self._initial_balance = initial_balance
        self._risk_free_rate = risk_free_rate

        # Pre-compute arrays once
        self._pnl = np.array([t.pnl_dollars for t in self._trades], dtype=np.float64)
        self._r = np.array([t.return_r for t in self._trades], dtype=np.float64)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_all(self) -> dict[str, Any]:
        """Return a comprehensive dict of all performance metrics."""
        n = len(self._trades)
        if n == 0:
            return self._empty_metrics()

        wins_mask = self._pnl > 0
        losses_mask = self._pnl < 0
        wins_r = self._r[wins_mask]
        losses_r = self._r[losses_mask]
        wins_pnl = self._pnl[wins_mask]
        losses_pnl = self._pnl[losses_mask]

        num_wins = int(wins_mask.sum())
        num_losses = int(losses_mask.sum())
        win_rate = num_wins / n

        total_r = float(self._r.sum())
        total_pnl = float(self._pnl.sum())

        gross_profit = float(wins_pnl.sum()) if num_wins > 0 else 0.0
        gross_loss = float(np.abs(losses_pnl).sum()) if num_losses > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        expectancy = float(self._r.mean())

        avg_win_r = float(wins_r.mean()) if num_wins > 0 else 0.0
        avg_loss_r = float(losses_r.mean()) if num_losses > 0 else 0.0

        max_dd_pct, max_dd_duration = self._calculate_max_drawdown()
        win_streak, loss_streak = self._calculate_streaks()

        avg_holding = self._avg_holding_hours()

        return {
            # Core ratios
            "sqn": self._calculate_sqn(),
            "sharpe": self._calculate_sharpe(),
            "sortino": self._calculate_sortino(),
            "calmar": self._calculate_calmar(),
            # Drawdown
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_duration_trades": max_dd_duration,
            # Win / loss
            "win_rate": win_rate,
            "num_wins": num_wins,
            "num_losses": num_losses,
            "total_trades": n,
            # R-multiples
            "avg_win_r": avg_win_r,
            "avg_loss_r": avg_loss_r,
            "largest_win_r": float(self._r.max()),
            "largest_loss_r": float(self._r.min()),
            "total_r": total_r,
            "expectancy": expectancy,
            # Dollar P&L
            "total_pnl": total_pnl,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "largest_win_pnl": float(self._pnl.max()),
            "largest_loss_pnl": float(self._pnl.min()),
            # Streaks
            "max_win_streak": win_streak,
            "max_loss_streak": loss_streak,
            # Holding
            "avg_holding_hours": avg_holding,
        }

    def get_equity_curve(self) -> pd.DataFrame:
        """
        Build an equity curve DataFrame indexed by trade exit time.

        Columns: ``equity``, ``drawdown``, ``drawdown_pct``.
        """
        if len(self._trades) == 0:
            return pd.DataFrame(columns=["equity", "drawdown", "drawdown_pct"])

        cumulative = np.cumsum(self._pnl) + self._initial_balance
        peak = np.maximum.accumulate(cumulative)
        dd = cumulative - peak
        dd_pct = np.where(peak > 0, dd / peak * 100.0, 0.0)

        idx = pd.DatetimeIndex([t.exit_time for t in self._trades], name="exit_time")
        return pd.DataFrame(
            {"equity": cumulative, "drawdown": dd, "drawdown_pct": dd_pct},
            index=idx,
        )

    def get_monthly_returns(self) -> pd.DataFrame:
        """
        Monthly aggregated returns.

        Returns a DataFrame with columns:
        ``pnl``, ``return_pct``, ``num_trades``, ``total_r``.
        """
        return self._resample_returns("ME")

    def get_weekly_returns(self) -> pd.DataFrame:
        """Weekly aggregated returns (same columns as monthly)."""
        return self._resample_returns("W")

    def get_daily_returns(self) -> pd.DataFrame:
        """Daily aggregated returns (same columns as monthly)."""
        return self._resample_returns("D")

    def get_trade_statistics(self) -> dict[str, Any]:
        """Detailed per-direction and per-exit-reason breakdown."""
        if len(self._trades) == 0:
            return {}

        df = self._trades_to_df()

        wins = df[df["pnl_dollars"] > 0]
        losses = df[df["pnl_dollars"] < 0]
        longs = df[df["direction"] == 1]
        shorts = df[df["direction"] == -1]

        def _direction_stats(sub: pd.DataFrame) -> dict[str, Any]:
            if len(sub) == 0:
                return {"count": 0, "pnl": 0.0, "win_rate": 0.0, "total_r": 0.0}
            w = sub[sub["pnl_dollars"] > 0]
            return {
                "count": len(sub),
                "pnl": float(sub["pnl_dollars"].sum()),
                "win_rate": len(w) / len(sub),
                "total_r": float(sub["return_r"].sum()),
            }

        # Per exit-reason breakdown
        exit_reasons: dict[str, dict[str, Any]] = {}
        for reason, grp in df.groupby("exit_reason"):
            exit_reasons[str(reason)] = _direction_stats(grp)

        # Per symbol breakdown
        symbol_stats: dict[str, dict[str, Any]] = {}
        for sym, grp in df.groupby("symbol"):
            symbol_stats[str(sym)] = _direction_stats(grp)

        win_streak, loss_streak = self._calculate_streaks()

        return {
            "total_trades": len(df),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "breakeven_trades": len(df) - len(wins) - len(losses),
            "win_rate": len(wins) / len(df) if len(df) > 0 else 0.0,
            # Dollar
            "avg_win_pnl": float(wins["pnl_dollars"].mean()) if len(wins) > 0 else 0.0,
            "avg_loss_pnl": float(losses["pnl_dollars"].mean()) if len(losses) > 0 else 0.0,
            "largest_win_pnl": float(df["pnl_dollars"].max()),
            "largest_loss_pnl": float(df["pnl_dollars"].min()),
            # R
            "avg_win_r": float(wins["return_r"].mean()) if len(wins) > 0 else 0.0,
            "avg_loss_r": float(losses["return_r"].mean()) if len(losses) > 0 else 0.0,
            "largest_win_r": float(df["return_r"].max()),
            "largest_loss_r": float(df["return_r"].min()),
            # Streaks
            "max_win_streak": win_streak,
            "max_loss_streak": loss_streak,
            # Direction
            "long_stats": _direction_stats(longs),
            "short_stats": _direction_stats(shorts),
            # Breakdowns
            "by_exit_reason": exit_reasons,
            "by_symbol": symbol_stats,
        }

    # ------------------------------------------------------------------
    # Ratio calculations
    # ------------------------------------------------------------------

    def _calculate_sqn(self) -> float:
        """System Quality Number: sqrt(N) * mean(R) / std(R)."""
        if len(self._r) == 0:
            return 0.0
        std = float(self._r.std(ddof=1)) if len(self._r) > 1 else 0.0
        if std == 0.0:
            return 0.0
        return float(np.sqrt(len(self._r)) * self._r.mean() / std)

    def _calculate_sharpe(self) -> float:
        """Annualised Sharpe ratio using actual trading frequency."""
        if len(self._r) < 2:
            return 0.0
        mean_r = float(self._r.mean()) - self._risk_free_rate
        std_r = float(self._r.std(ddof=1))
        if std_r == 0.0:
            return 0.0
        # Use actual trading frequency for annualization
        first = self._trades[0].exit_time
        last = self._trades[-1].exit_time
        duration_days = max((last - first).total_seconds() / 86400, 1.0)
        trades_per_year = len(self._trades) / (duration_days / 365.25)
        return float(mean_r / std_r * np.sqrt(max(trades_per_year, 1.0)))

    def _calculate_sortino(self) -> float:
        """
        Sortino ratio -- like Sharpe but only penalises downside volatility.

        Uses R-multiples.  Annualised using actual trading frequency.
        """
        if len(self._r) < 2:
            return 0.0
        mean_r = float(self._r.mean()) - self._risk_free_rate
        downside = self._r[self._r < 0]
        if len(downside) < 2:
            return float("inf") if mean_r > 0 else 0.0
        downside_std = float(downside.std(ddof=1))
        if downside_std == 0.0:
            return 0.0
        # Use actual trading frequency for annualization
        first = self._trades[0].exit_time
        last = self._trades[-1].exit_time
        duration_days = max((last - first).total_seconds() / 86400, 1.0)
        trades_per_year = len(self._trades) / (duration_days / 365.25)
        return float(mean_r / downside_std * np.sqrt(max(trades_per_year, 1.0)))

    def _calculate_calmar(self) -> float:
        """
        Calmar ratio: annualised return / max drawdown.

        Uses dollar P&L relative to initial balance.
        """
        if len(self._trades) == 0 or self._initial_balance <= 0:
            return 0.0

        # Total return as a fraction of initial balance
        total_return = float(self._pnl.sum()) / self._initial_balance

        # Duration in years
        first_exit = self._trades[0].exit_time
        last_exit = self._trades[-1].exit_time
        duration_days = max((last_exit - first_exit).total_seconds() / 86400, 1.0)
        years = duration_days / 365.25
        annualised_return = ((1 + total_return) ** (1 / years) - 1) if years > 0 and total_return > -1 else 0.0

        max_dd_pct, _ = self._calculate_max_drawdown()
        abs_dd = abs(max_dd_pct)
        if abs_dd == 0.0:
            return float("inf") if annualised_return > 0 else 0.0
        return float(annualised_return * 100.0 / abs_dd)

    # ------------------------------------------------------------------
    # Drawdown
    # ------------------------------------------------------------------

    def _calculate_max_drawdown(self) -> tuple[float, int]:
        """
        Maximum drawdown in percent (of running peak equity) and duration
        in number of trades.

        Returns:
            (max_drawdown_pct, max_drawdown_duration_trades)
            max_drawdown_pct is negative (e.g. -12.5 means 12.5% drawdown).
        """
        if len(self._pnl) == 0:
            return 0.0, 0

        cumulative = np.cumsum(self._pnl) + self._initial_balance
        peak = np.maximum.accumulate(cumulative)
        dd_pct = np.where(peak > 0, (cumulative - peak) / peak * 100.0, 0.0)

        max_dd_pct = float(dd_pct.min())

        # Duration: longest consecutive stretch below the high-water mark
        in_dd = dd_pct < 0
        if not in_dd.any():
            max_dur = 0
        else:
            transitions = np.diff(np.concatenate(([0], in_dd.astype(int), [0])))
            starts = np.where(transitions == 1)[0]
            ends = np.where(transitions == -1)[0]
            max_dur = int((ends - starts).max()) if len(starts) > 0 else 0

        return max_dd_pct, max_dur

    # ------------------------------------------------------------------
    # Streaks
    # ------------------------------------------------------------------

    def _calculate_streaks(self) -> tuple[int, int]:
        """Return (max_win_streak, max_loss_streak)."""
        max_win = 0
        max_loss = 0
        cur_win = 0
        cur_loss = 0

        for pnl in self._pnl:
            if pnl > 0:
                cur_win += 1
                cur_loss = 0
                max_win = max(max_win, cur_win)
            elif pnl < 0:
                cur_loss += 1
                cur_win = 0
                max_loss = max(max_loss, cur_loss)
            else:
                # Breakeven resets both streaks
                cur_win = 0
                cur_loss = 0

        return max_win, max_loss

    # ------------------------------------------------------------------
    # Resampled returns helper
    # ------------------------------------------------------------------

    def _resample_returns(self, freq: str) -> pd.DataFrame:
        """
        Aggregate trade P&L into period buckets.

        Args:
            freq: Pandas offset alias (``"ME"``, ``"W"``, ``"D"``).

        Returns:
            DataFrame with columns ``pnl``, ``return_pct``, ``num_trades``,
            ``total_r``, indexed by period.
        """
        if len(self._trades) == 0:
            return pd.DataFrame(columns=["pnl", "return_pct", "num_trades", "total_r"])

        df = self._trades_to_df()
        df = df.set_index("exit_time")

        agg = df.resample(freq).agg(
            pnl=pd.NamedAgg(column="pnl_dollars", aggfunc="sum"),
            num_trades=pd.NamedAgg(column="pnl_dollars", aggfunc="count"),
            total_r=pd.NamedAgg(column="return_r", aggfunc="sum"),
        )
        # Return pct relative to initial balance
        agg["return_pct"] = agg["pnl"] / self._initial_balance * 100.0
        agg["num_trades"] = agg["num_trades"].astype(int)

        return agg[["pnl", "return_pct", "num_trades", "total_r"]]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _trades_to_df(self) -> pd.DataFrame:
        """Convert trade records to a DataFrame."""
        rows = [
            {
                "trade_id": t.trade_id,
                "symbol": t.symbol,
                "direction": t.direction,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "position_size": t.position_size,
                "pnl_dollars": t.pnl_dollars,
                "return_r": t.return_r,
                "exit_reason": t.exit_reason,
                "sl_price": t.sl_price,
                "tp_price": t.tp_price,
            }
            for t in self._trades
        ]
        return pd.DataFrame(rows)

    def _avg_holding_hours(self) -> float:
        """Average trade holding period in hours."""
        if len(self._trades) == 0:
            return 0.0
        total_seconds = sum(t.holding_period.total_seconds() for t in self._trades)
        return total_seconds / len(self._trades) / 3600.0

    @staticmethod
    def _empty_metrics() -> dict[str, Any]:
        """Return a zeroed-out metrics dict."""
        return {
            "sqn": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_duration_trades": 0,
            "win_rate": 0.0,
            "num_wins": 0,
            "num_losses": 0,
            "total_trades": 0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "largest_win_r": 0.0,
            "largest_loss_r": 0.0,
            "total_r": 0.0,
            "expectancy": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "largest_win_pnl": 0.0,
            "largest_loss_pnl": 0.0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "avg_holding_hours": 0.0,
        }


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------

def interpret_sqn(sqn: float) -> str:
    """
    Interpret a System Quality Number value.

    Thresholds (Van Tharp):
        < 1.6   Poor
        1.6-1.9 Below Average
        2.0-2.4 Average
        2.5-2.9 Good
        3.0-5.0 Excellent
        > 5.0   Holy Grail
    """
    if sqn < 1.6:
        return "Poor"
    elif sqn < 2.0:
        return "Below Average"
    elif sqn < 2.5:
        return "Average"
    elif sqn < 3.0:
        return "Good"
    elif sqn < 5.0:
        return "Excellent"
    else:
        return "Holy Grail"


def validate_baseline_targets(
    metrics: dict[str, Any],
    targets: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Validate calculated metrics against baseline performance targets.

    Default targets:
        - SQN >= 2.0 (Average or better)
        - total_r >= 100
        - win_rate >= 0.40
        - max_drawdown_pct > -20.0 (i.e. shallower than 20%)
        - profit_factor >= 1.5
        - sortino >= 1.0

    Args:
        metrics: Dict returned by :meth:`PerformanceMetrics.calculate_all`.
        targets: Optional override dict (metric_name -> target_value).

    Returns:
        Dict with ``all_passed``, per-metric ``results``, and
        ``sqn_interpretation``.
    """
    default_targets: dict[str, float] = {
        "sqn": 2.0,
        "total_r": 100.0,
        "win_rate": 0.40,
        "max_drawdown_pct": -20.0,
        "profit_factor": 1.5,
        "sortino": 1.0,
    }
    if targets is not None:
        default_targets.update(targets)

    # Metrics where *higher* (less negative) is better but the value is
    # negative (drawdown).
    higher_is_better_negative = {"max_drawdown_pct"}

    results: dict[str, dict[str, Any]] = {}
    for metric, target in default_targets.items():
        actual = metrics.get(metric, 0.0)
        if metric in higher_is_better_negative:
            passed = actual > target  # e.g. -10 > -20 is good
        else:
            passed = actual >= target
        results[metric] = {
            "target": target,
            "actual": actual,
            "passed": passed,
            "difference": actual - target,
        }

    all_passed = all(r["passed"] for r in results.values())

    return {
        "all_passed": all_passed,
        "results": results,
        "sqn_interpretation": interpret_sqn(metrics.get("sqn", 0.0)),
    }
