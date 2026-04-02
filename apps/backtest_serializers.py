"""Backtest serialization helpers — convert sweep results to LW Charts JSON.

Converts SweepTradeRecord objects and metrics dicts to the JSON structures
expected by TradingView Lightweight Charts: markers, price lines, area series.

Functions
---------
serialize_trade_markers   Trade records → LW Charts marker list (2 per trade)
serialize_trade_lines     Trade records → SL/TP horizontal price lines
serialize_equity_curve    Cumulative PnL area series
serialize_equity_curve_r  Cumulative R-multiple area series
serialize_metrics_summary Flat metrics dict → sectioned display dict
serialize_trade_detail    Single SweepTradeRecord → full detail dict
serialize_sweep_row       Config dict + metrics dict → sweep comparison row
"""
from __future__ import annotations

import pandas as pd

from iora.strategy.trade_converter import SweepTradeRecord

# LW Charts color constants
_COLOR_WIN = "#26a69a"   # green
_COLOR_LOSS = "#ef5350"  # red


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ts(t) -> int:
    """Convert pandas Timestamp to Unix seconds integer for LW Charts."""
    if isinstance(t, pd.Timestamp):
        return int(t.timestamp())
    return int(pd.Timestamp(t).timestamp())


# ---------------------------------------------------------------------------
# Trade markers
# ---------------------------------------------------------------------------

def serialize_trade_markers(records: list[SweepTradeRecord]) -> list[dict]:
    """Convert trade records to LW Charts marker format.

    Each trade produces two markers:
    - Entry: arrowUp (long) or arrowDown (short), positioned below/above bar
    - Exit:  circle, positioned above/below bar (opposite of entry)

    Color is green (#26a69a) for winners, red (#ef5350) for losers.
    """
    markers: list[dict] = []
    for rec in records:
        color = _COLOR_WIN if rec.is_winner else _COLOR_LOSS

        if rec.direction == 1:
            entry_shape = "arrowUp"
            entry_position = "belowBar"
            exit_position = "aboveBar"
        else:
            entry_shape = "arrowDown"
            entry_position = "aboveBar"
            exit_position = "belowBar"

        entry_marker = {
            "time": _ts(rec.entry_time),
            "position": entry_position,
            "color": color,
            "shape": entry_shape,
            "text": f"Entry {rec.direction_str.upper()} | {rec.signal_type} | {rec.trade_id}",
        }
        exit_marker = {
            "time": _ts(rec.exit_time),
            "position": exit_position,
            "color": color,
            "shape": "circle",
            "text": f"Exit {rec.exit_reason} | {rec.pnl_pips:+.1f} pips | {rec.return_r:+.2f}R",
        }
        markers.append(entry_marker)
        markers.append(exit_marker)

    return markers


# ---------------------------------------------------------------------------
# Trade SL/TP lines
# ---------------------------------------------------------------------------

def serialize_trade_lines(records: list[SweepTradeRecord]) -> list[dict]:
    """Convert trade SL/TP levels to horizontal price line dicts.

    Each trade produces two lines:
    - SL line at sl_price (red, #ef5350)
    - TP line at tp_price (green, #26a69a)

    Each line carries the entry_time as its anchor time so the chart can
    position it on the correct bar.
    """
    lines: list[dict] = []
    for rec in records:
        entry_ts = _ts(rec.entry_time)
        lines.append({
            "price": rec.sl_price,
            "color": _COLOR_LOSS,
            "time": entry_ts,
            "trade_id": rec.trade_id,
            "label": "SL",
        })
        lines.append({
            "price": rec.tp_price,
            "color": _COLOR_WIN,
            "time": entry_ts,
            "trade_id": rec.trade_id,
            "label": "TP",
        })
    return lines


# ---------------------------------------------------------------------------
# Equity curves
# ---------------------------------------------------------------------------

def serialize_equity_curve(records: list[SweepTradeRecord]) -> list[dict]:
    """Build cumulative PnL series for LW Charts area chart.

    Returns a list of {"time": int, "value": float} dicts sorted by
    exit_time (ascending). Values are cumulative pnl_pips.
    """
    if not records:
        return []

    sorted_records = sorted(records, key=lambda r: r.exit_time)
    result: list[dict] = []
    cumulative: float = 0.0
    for rec in sorted_records:
        cumulative += rec.pnl_pips
        result.append({
            "time": _ts(rec.exit_time),
            "value": round(cumulative, 4),
        })
    return result


def serialize_equity_curve_r(records: list[SweepTradeRecord]) -> list[dict]:
    """Build cumulative R-multiple series for LW Charts area chart.

    Returns a list of {"time": int, "value": float} dicts sorted by
    exit_time (ascending). Values are cumulative return_r.
    """
    if not records:
        return []

    sorted_records = sorted(records, key=lambda r: r.exit_time)
    result: list[dict] = []
    cumulative: float = 0.0
    for rec in sorted_records:
        cumulative += rec.return_r
        result.append({
            "time": _ts(rec.exit_time),
            "value": round(cumulative, 4),
        })
    return result


# ---------------------------------------------------------------------------
# Metrics summary
# ---------------------------------------------------------------------------

def serialize_metrics_summary(metrics: dict) -> dict:
    """Organize flat metrics dict into display sections.

    Sections:
    - overview:      core trade counts, win rate, profitability
    - risk_adjusted: Sharpe, Sortino, SQN, Calmar
    - pnl:           P&L in pips and R-multiples
    - drawdown:      max drawdown in pips and R
    - streaks:       win/loss streaks and holding times
    """
    def _get(key: str, default=None):
        return metrics.get(key, default)

    overview = {
        "total_trades": _get("total_trades", 0),
        "wins": _get("wins", 0),
        "losses": _get("losses", 0),
        "win_rate": _get("win_rate", 0.0),
        "tp_hits": _get("tp_hits", 0),
        "sl_hits": _get("sl_hits", 0),
        "profit_factor": _get("profit_factor", 0.0),
        "expectancy_pips": _get("expectancy_pips", 0.0),
        "expectancy_r": _get("expectancy_r", 0.0),
    }

    risk_adjusted = {
        "sqn": _get("sqn", 0.0),
        "sharpe": _get("sharpe", 0.0),
        "sortino": _get("sortino", 0.0),
        "calmar": _get("calmar", 0.0),
    }

    pnl = {
        "total_pnl_pips": _get("total_pnl_pips", 0.0),
        "avg_pnl_pips": _get("avg_pnl_pips", 0.0),
        "median_pnl_pips": _get("median_pnl_pips", 0.0),
        "avg_win_pips": _get("avg_win_pips", 0.0),
        "avg_loss_pips": _get("avg_loss_pips", 0.0),
        "largest_win_pips": _get("largest_win_pips", 0.0),
        "largest_loss_pips": _get("largest_loss_pips", 0.0),
        "gross_profit_pips": _get("gross_profit_pips", 0.0),
        "gross_loss_pips": _get("gross_loss_pips", 0.0),
        "total_r": _get("total_r", 0.0),
        "avg_r": _get("avg_r", 0.0),
        "avg_win_r": _get("avg_win_r", 0.0),
        "avg_loss_r": _get("avg_loss_r", 0.0),
        "largest_win_r": _get("largest_win_r", 0.0),
        "largest_loss_r": _get("largest_loss_r", 0.0),
    }

    drawdown = {
        "max_dd_pips": _get("max_dd_pips", 0.0),
        "max_dd_r": _get("max_dd_r", 0.0),
    }

    streaks = {
        "max_win_streak": _get("max_win_streak", 0),
        "max_loss_streak": _get("max_loss_streak", 0),
        "avg_hold_hours": _get("avg_hold_hours", 0.0),
        "avg_win_hold_hours": _get("avg_win_hold_hours", 0.0),
        "avg_loss_hold_hours": _get("avg_loss_hold_hours", 0.0),
    }

    return {
        "overview": overview,
        "risk_adjusted": risk_adjusted,
        "pnl": pnl,
        "drawdown": drawdown,
        "streaks": streaks,
    }


# ---------------------------------------------------------------------------
# Trade detail
# ---------------------------------------------------------------------------

def serialize_trade_detail(record: SweepTradeRecord) -> dict:
    """Serialize all fields from a single SweepTradeRecord to a JSON-safe dict.

    Timestamps are converted to Unix seconds integers.
    Derived properties (is_winner, direction_str, holding_period) are
    also included for convenience.
    """
    return {
        # Core trade fields
        "trade_id": record.trade_id,
        "symbol": record.symbol,
        "direction": record.direction,
        "direction_str": record.direction_str,
        "entry_time": _ts(record.entry_time),
        "exit_time": _ts(record.exit_time),
        "entry_price": record.entry_price,
        "exit_price": record.exit_price,
        "pnl_pips": record.pnl_pips,
        "risk_pips": record.risk_pips,
        "reward_pips": record.reward_pips,
        "return_r": record.return_r,
        "rr_ratio": record.rr_ratio,
        "exit_reason": record.exit_reason,
        "sl_price": record.sl_price,
        "tp_price": record.tp_price,
        # Signal classification
        "signal_type": record.signal_type,
        "struct_cls": record.struct_cls,
        "zone_tf": record.zone_tf,
        "parent_tf": record.parent_tf,
        "nesting_depth": record.nesting_depth,
        "opposing_nest": record.opposing_nest,
        # Zone context
        "zone_top": record.zone_top,
        "zone_bottom": record.zone_bottom,
        "zone_is_push": record.zone_is_push,
        "zone_is_reversal": record.zone_is_reversal,
        "zone_is_terminal": record.zone_is_terminal,
        "zone_swing_cls": record.zone_swing_cls,
        "zone_count": record.zone_count,
        # Derived properties
        "is_winner": record.is_winner,
        "holding_period_hours": record.holding_period.total_seconds() / 3600.0,
    }


# ---------------------------------------------------------------------------
# Sweep row
# ---------------------------------------------------------------------------

def serialize_sweep_row(config_dict: dict, metrics: dict) -> dict:
    """Combine config parameters and metrics into a single sweep comparison row.

    Config keys take precedence on collision so sweep dimensions (e.g.
    entry_model, rr_ratio) are always the config values, not computed ones.
    Metrics are merged in first, then config overwrites.
    """
    row: dict = {}
    row.update(metrics)
    row.update(config_dict)
    return row
