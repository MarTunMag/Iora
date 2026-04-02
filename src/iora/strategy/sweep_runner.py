"""Sweep runner — batch strategy evaluation across configs and symbols.

Key optimization: zone timeline is built ONCE per symbol (expensive).
Strategy evaluation runs N times cheaply per timeline.

Metrics include: SQN, Sharpe, Sortino, Calmar, profit factor, expectancy,
max drawdown, streaks, breakdowns by direction/signal_type/struct_cls.
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.push_zone_strategy import evaluate_strategy
from iora.strategy.trade_converter import convert_trades, SweepTradeRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def compute_metrics(records: list[SweepTradeRecord]) -> dict:
    """Compute comprehensive metrics from a list of trade records.

    Returns a flat dict of metric_name → value, covering:
    - Basic counts and rates
    - R-multiple statistics
    - Risk-adjusted returns (Sharpe, Sortino, SQN, Calmar)
    - Drawdown analysis
    - Profit factor and expectancy
    - Win/loss streaks
    - Holding period stats
    - Breakdowns by direction, signal_type, struct_cls, zone_tf
    """
    n = len(records)
    if n == 0:
        return _empty_metrics()

    # --- Basic arrays ---
    pnl_arr = np.array([r.pnl_pips for r in records])
    r_arr = np.array([r.return_r for r in records])
    wins_mask = pnl_arr > 0
    losses_mask = pnl_arr <= 0

    n_wins = int(wins_mask.sum())
    n_losses = int(losses_mask.sum())
    win_pnl = pnl_arr[wins_mask]
    loss_pnl = pnl_arr[losses_mask]
    win_r = r_arr[wins_mask]
    loss_r = r_arr[losses_mask]

    # --- Cumulative equity curve (in pips) ---
    equity = np.cumsum(pnl_arr)
    running_max = np.maximum.accumulate(equity)
    drawdown = running_max - equity
    max_dd_pips = float(drawdown.max()) if len(drawdown) > 0 else 0.0

    # --- R-based equity curve ---
    equity_r = np.cumsum(r_arr)
    running_max_r = np.maximum.accumulate(equity_r)
    drawdown_r = running_max_r - equity_r
    max_dd_r = float(drawdown_r.max()) if len(drawdown_r) > 0 else 0.0

    # --- Profit factor ---
    gross_profit = float(win_pnl.sum()) if n_wins > 0 else 0.0
    gross_loss = float(abs(loss_pnl.sum())) if n_losses > 0 else 0.0
    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf") if gross_profit > 0 else 0.0
    )

    # --- Expectancy ---
    avg_win = float(win_pnl.mean()) if n_wins > 0 else 0.0
    avg_loss = float(loss_pnl.mean()) if n_losses > 0 else 0.0
    win_rate = n_wins / n
    expectancy_pips = win_rate * avg_win + (1 - win_rate) * avg_loss

    avg_win_r = float(win_r.mean()) if n_wins > 0 else 0.0
    avg_loss_r = float(loss_r.mean()) if n_losses > 0 else 0.0
    expectancy_r = win_rate * avg_win_r + (1 - win_rate) * avg_loss_r

    # --- Sharpe (R-based, annualized assuming ~252 trading days) ---
    r_std = float(r_arr.std(ddof=1)) if n > 1 else 0.0
    r_mean = float(r_arr.mean())
    sharpe = r_mean / r_std if r_std > 0 else 0.0

    # --- Sortino (downside deviation only) ---
    downside = r_arr[r_arr < 0]
    downside_std = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino = r_mean / downside_std if downside_std > 0 else 0.0

    # --- SQN (System Quality Number) ---
    sqn = (r_mean / r_std) * math.sqrt(n) if r_std > 0 else 0.0

    # --- Calmar (total R / max drawdown in R) ---
    total_r = float(equity_r[-1]) if len(equity_r) > 0 else 0.0
    calmar = total_r / max_dd_r if max_dd_r > 0 else 0.0

    # --- Streaks ---
    max_win_streak, max_loss_streak = _compute_streaks(pnl_arr)

    # --- Holding periods ---
    durations = [r.holding_period.total_seconds() / 3600 for r in records]
    avg_hold_hours = sum(durations) / len(durations) if durations else 0.0
    win_durations = [d for r, d in zip(records, durations) if r.is_winner]
    loss_durations = [d for r, d in zip(records, durations) if not r.is_winner]
    avg_win_hold = sum(win_durations) / len(win_durations) if win_durations else 0.0
    avg_loss_hold = sum(loss_durations) / len(loss_durations) if loss_durations else 0.0

    # --- Exit reason breakdown ---
    tp_hits = sum(1 for r in records if r.exit_reason == "tp_hit")
    sl_hits = sum(1 for r in records if r.exit_reason == "sl_hit")

    metrics: dict = {
        # Counts
        "total_trades": n,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate": win_rate,
        "tp_hits": tp_hits,
        "sl_hits": sl_hits,
        # PnL
        "total_pnl_pips": float(pnl_arr.sum()),
        "avg_pnl_pips": float(pnl_arr.mean()),
        "median_pnl_pips": float(np.median(pnl_arr)),
        "std_pnl_pips": float(pnl_arr.std(ddof=1)) if n > 1 else 0.0,
        "avg_win_pips": avg_win,
        "avg_loss_pips": avg_loss,
        "largest_win_pips": float(pnl_arr.max()),
        "largest_loss_pips": float(pnl_arr.min()),
        # R-multiples
        "total_r": total_r,
        "avg_r": r_mean,
        "median_r": float(np.median(r_arr)),
        "std_r": r_std,
        "avg_win_r": avg_win_r,
        "avg_loss_r": avg_loss_r,
        "largest_win_r": float(r_arr.max()),
        "largest_loss_r": float(r_arr.min()),
        # Risk-adjusted
        "sharpe": sharpe,
        "sortino": sortino,
        "sqn": sqn,
        "calmar": calmar,
        # Drawdown
        "max_dd_pips": max_dd_pips,
        "max_dd_r": max_dd_r,
        # Profitability
        "profit_factor": profit_factor,
        "expectancy_pips": expectancy_pips,
        "expectancy_r": expectancy_r,
        "gross_profit_pips": gross_profit,
        "gross_loss_pips": gross_loss,
        # Streaks
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        # Holding period
        "avg_hold_hours": avg_hold_hours,
        "avg_win_hold_hours": avg_win_hold,
        "avg_loss_hold_hours": avg_loss_hold,
    }

    # --- Breakdowns ---
    metrics.update(_direction_breakdown(records))
    metrics.update(_field_breakdown(records, "signal_type"))
    metrics.update(_field_breakdown(records, "struct_cls"))
    metrics.update(_field_breakdown(records, "zone_tf"))
    metrics.update(_field_breakdown(records, "exit_reason"))

    return metrics


def _empty_metrics() -> dict:
    """Return metrics dict for zero trades."""
    return {
        "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
        "tp_hits": 0, "sl_hits": 0,
        "total_pnl_pips": 0.0, "avg_pnl_pips": 0.0,
        "median_pnl_pips": 0.0, "std_pnl_pips": 0.0,
        "avg_win_pips": 0.0, "avg_loss_pips": 0.0,
        "largest_win_pips": 0.0, "largest_loss_pips": 0.0,
        "total_r": 0.0, "avg_r": 0.0, "median_r": 0.0, "std_r": 0.0,
        "avg_win_r": 0.0, "avg_loss_r": 0.0,
        "largest_win_r": 0.0, "largest_loss_r": 0.0,
        "sharpe": 0.0, "sortino": 0.0, "sqn": 0.0, "calmar": 0.0,
        "max_dd_pips": 0.0, "max_dd_r": 0.0,
        "profit_factor": 0.0, "expectancy_pips": 0.0, "expectancy_r": 0.0,
        "gross_profit_pips": 0.0, "gross_loss_pips": 0.0,
        "max_win_streak": 0, "max_loss_streak": 0,
        "avg_hold_hours": 0.0, "avg_win_hold_hours": 0.0,
        "avg_loss_hold_hours": 0.0,
    }


def _compute_streaks(pnl_arr: np.ndarray) -> tuple[int, int]:
    """Compute max consecutive win and loss streaks."""
    max_win = max_loss = 0
    cur_win = cur_loss = 0
    for p in pnl_arr:
        if p > 0:
            cur_win += 1
            cur_loss = 0
            max_win = max(max_win, cur_win)
        else:
            cur_loss += 1
            cur_win = 0
            max_loss = max(max_loss, cur_loss)
    return max_win, max_loss


def _direction_breakdown(records: list[SweepTradeRecord]) -> dict:
    """Win rate and count by direction (long/short)."""
    result: dict = {}
    for dir_val, label in [(1, "long"), (-1, "short")]:
        subset = [r for r in records if r.direction == dir_val]
        n = len(subset)
        wins = sum(1 for r in subset if r.is_winner)
        result[f"{label}_trades"] = n
        result[f"{label}_wins"] = wins
        result[f"{label}_win_rate"] = wins / n if n > 0 else 0.0
        result[f"{label}_avg_r"] = (
            sum(r.return_r for r in subset) / n if n > 0 else 0.0
        )
    return result


def _field_breakdown(records: list[SweepTradeRecord], field: str) -> dict:
    """Count and win rate by a categorical field."""
    from collections import Counter
    values = [getattr(r, field) for r in records]
    counts = Counter(values)
    result: dict = {}
    for val, count in counts.items():
        safe_val = str(val).lower().replace(" ", "_") if val else "none"
        wins = sum(1 for r in records if getattr(r, field) == val and r.is_winner)
        result[f"{field}_{safe_val}_n"] = count
        result[f"{field}_{safe_val}_wr"] = wins / count if count > 0 else 0.0
    return result


# ---------------------------------------------------------------------------
# Sweep functions
# ---------------------------------------------------------------------------

def run_sweep(
    timeline: list[ZoneTimelineBar],
    configs: list[StrategyConfig],
    symbol: str = "GBPUSD",
) -> pd.DataFrame:
    """Evaluate multiple configs against a single pre-built timeline.

    Args:
        timeline: Pre-built zone timeline (from build_zone_timeline).
        configs: List of strategy configs to evaluate.
        symbol: Trading symbol for pip/cost calculations.

    Returns:
        DataFrame with one row per config: config params + metrics.
    """
    if not configs:
        return pd.DataFrame()

    rows: list[dict] = []
    for i, cfg in enumerate(configs):
        result = evaluate_strategy(timeline, cfg, symbol=symbol)

        records = convert_trades(result.trades, symbol=symbol)
        metrics = compute_metrics(records)
        metrics["total_signals"] = len(result.signals)
        metrics["open_trades"] = len(result.open_trades)

        row = {**cfg.to_dict(), **metrics}
        rows.append(row)

        if (i + 1) % 50 == 0:
            logger.info("  Config %d/%d done (%d trades)",
                        i + 1, len(configs), metrics["total_trades"])

    return pd.DataFrame(rows)


def run_multi_symbol_sweep(
    timelines: dict[str, list[ZoneTimelineBar]],
    configs: list[StrategyConfig],
) -> pd.DataFrame:
    """Evaluate configs across multiple symbols using pre-built timelines.

    Args:
        timelines: Dict of symbol -> pre-built zone timeline.
        configs: List of strategy configs to evaluate.

    Returns:
        DataFrame with symbol + config params + metrics columns.
    """
    all_dfs: list[pd.DataFrame] = []

    for symbol, timeline in timelines.items():
        logger.info("Sweeping %s (%d bars, %d configs)",
                    symbol, len(timeline), len(configs))
        df = run_sweep(timeline, configs, symbol=symbol)
        df.insert(0, "symbol", symbol)
        all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)
