"""
Backtest Evaluator — Bridge signal engine output to TradeRecord metrics.

Converts SignalEngineOutput.trade_log (event dicts) into TradeRecord objects
with costs applied, then runs PerformanceMetrics for analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

import pandas as pd

from flint.backtest.costs import CostCalculator
from flint.backtest.market_mechanics import get_pip_size, get_pip_value_per_lot
from flint.backtest.metrics import PerformanceMetrics, TradeRecord

logger = logging.getLogger(__name__)


def match_trades(
    trade_log: list[dict],
    symbol: str,
    last_close: float,
) -> list[TradeRecord]:
    """Match trade_log open/close events into completed TradeRecord objects.

    Args:
        trade_log: Event dicts from SignalEngineOutput.trade_log.
        symbol: Trading symbol (for pip/cost calculations).
        last_close: Last bar's close price (for force-closing open trades).

    Returns:
        List of completed TradeRecord objects with costs applied.
    """
    pip_size = get_pip_size(symbol)
    pip_value = get_pip_value_per_lot(symbol)
    cost_calc = CostCalculator(symbol)

    # Track open trades by trade_id
    pending: dict[int, dict] = {}
    completed: list[TradeRecord] = []

    for event in trade_log:
        action = event["action"]

        if action in ("ENTRY", "ADD_ON", "HEDGE"):
            tid = event["trade_id"]
            pending[tid] = {
                "entry_time": event["time"],
                "entry_price": event["price"],
                "direction": event["direction"],
                "sl": event.get("sl", event["price"]),
                "lots": event["lots"],
                "trade_id": tid,
                "rule_id": event.get("rule_id", ""),
                "mode": "scalp" if action == "HEDGE" else "growth",
                "entry_context": event.get("entry_context"),
            }

        elif action == "EXIT":
            # EXIT closes ALL pending growth trades at exit price
            exit_time = event["time"]
            exit_price = event["price"]
            to_close = [
                tid for tid, info in pending.items()
                if info["mode"] == "growth"
            ]
            for tid in to_close:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, exit_time, exit_price, "rule_exit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "SL_HIT":
            tid = event["trade_id"]
            if tid in pending:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, event["time"], event["sl_price"], "sl_hit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "TP_HIT":
            tid = event["trade_id"]
            if tid in pending:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, event["time"], event["tp_price"], "tp_hit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "SL_MOVE":
            # Update SL on ALL pending growth trades
            new_sl = event["new_sl"]
            for info in pending.values():
                if info["mode"] == "growth":
                    info["sl"] = new_sl

    # Force-close any remaining open trades
    for tid, info in pending.items():
        now = info["entry_time"]  # Fallback timestamp
        record = _build_trade_record(
            info, now, last_close, "end_of_data",
            symbol, pip_size, pip_value, cost_calc,
        )
        completed.append(record)

    return completed


def _build_trade_record(
    info: dict,
    exit_time: pd.Timestamp,
    exit_price: float,
    exit_reason: str,
    symbol: str,
    pip_size: float,
    pip_value: float,
    cost_calc: CostCalculator,
) -> TradeRecord:
    """Build a TradeRecord from a pending trade info dict + exit details."""
    entry_price = info["entry_price"]
    lots = info["lots"]
    direction_int = -1 if info["direction"] == "bear" else 1
    sl_price = info["sl"]

    # Raw P&L (before costs)
    if direction_int == 1:  # LONG
        pnl_raw = (exit_price - entry_price) / pip_size * pip_value * lots
    else:  # SHORT
        pnl_raw = (entry_price - exit_price) / pip_size * pip_value * lots

    # Cost — single call, commission is already round-trip
    cost = cost_calc.calculate_total_cost(info["entry_time"], lots)
    pnl_dollars = pnl_raw - cost.total_dollars

    # R-multiple
    risk_pips = abs(entry_price - sl_price) / pip_size
    risk_dollars = risk_pips * pip_value * lots
    return_r = pnl_dollars / risk_dollars if risk_dollars > 0 else 0.0

    return TradeRecord(
        trade_id=str(info["trade_id"]),
        symbol=symbol,
        direction=direction_int,
        entry_time=info["entry_time"],
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        position_size=lots,
        pnl_dollars=pnl_dollars,
        return_r=return_r,
        exit_reason=exit_reason,
        sl_price=sl_price,
        tp_price=0.0,
        timeframe="M15",
        mode=info["mode"],
        cost_dollars=cost.total_dollars,
    )


@dataclass
class EvaluationResult:
    """Complete evaluation output."""
    trades: list[TradeRecord]
    metrics: dict
    trade_contexts: list[dict | None]
    signal_type_breakdown: dict
    raw_trade_log: list[dict]


def evaluate_trades(
    signal_output: "SignalEngineOutput",
    symbol: str,
    initial_balance: float = 1_000.0,
    last_close: float = 0.0,
) -> EvaluationResult:
    """Run full evaluation: match trades, calculate metrics, build breakdown.

    Args:
        signal_output: Output from run_signal_engine().
        symbol: Trading symbol.
        initial_balance: Starting account balance.
            IMPORTANT: Must match the account_balance passed to run_signal_engine()
            for position sizing and metrics to be consistent.
        last_close: Last bar's close price for force-closing open trades.

    Returns:
        EvaluationResult with trades, metrics, contexts, and breakdown.
    """
    trade_log = signal_output.trade_log

    # Match trades
    trades = match_trades(trade_log, symbol, last_close)

    # Extract contexts (aligned with trades by trade_id)
    contexts = _extract_contexts(trade_log, trades)

    # Calculate metrics
    metrics = {}
    if trades:
        pm = PerformanceMetrics(trades, initial_balance=initial_balance)
        metrics = pm.calculate_all()

    # Build breakdown
    breakdown = _build_breakdown(trades, contexts)

    return EvaluationResult(
        trades=trades,
        metrics=metrics,
        trade_contexts=contexts,
        signal_type_breakdown=breakdown,
        raw_trade_log=trade_log,
    )


def _extract_contexts(
    trade_log: list[dict], trades: list[TradeRecord]
) -> list[dict | None]:
    """Extract entry_context dicts aligned with the trades list."""
    ctx_map: dict[str, dict] = {}
    for event in trade_log:
        if event["action"] in ("ENTRY", "ADD_ON", "HEDGE"):
            ctx = event.get("entry_context")
            if ctx is not None:
                ctx_map[str(event["trade_id"])] = ctx
    return [ctx_map.get(t.trade_id) for t in trades]


def _classify_zone_tf(ctx: dict | None) -> str:
    """Determine highest-TF zone the price was in at entry."""
    if ctx is None:
        return "no_context"
    if ctx.get("d1_price_in_supply") or ctx.get("d1_price_in_demand"):
        return "D1_zone"
    if ctx.get("h4_price_in_supply") or ctx.get("h4_price_in_demand"):
        return "H4_zone"
    if ctx.get("h1_price_in_supply") or ctx.get("h1_price_in_demand"):
        return "H1_zone"
    if ctx.get("m15_price_in_supply") or ctx.get("m15_price_in_demand"):
        return "M15_only"
    return "no_zone"


def _build_breakdown(
    trades: list[TradeRecord],
    contexts: list[dict | None],
) -> dict:
    """Group trades by multiple dimensions and calculate per-group metrics."""
    breakdown: dict[str, dict] = {}

    # Dimension: zone TF
    groups_zone: dict[str, list[TradeRecord]] = {}
    for trade, ctx in zip(trades, contexts):
        key = _classify_zone_tf(ctx)
        groups_zone.setdefault(key, []).append(trade)
    breakdown["by_zone_tf"] = {
        k: _group_metrics(v) for k, v in groups_zone.items()
    }

    # Dimension: exit reason
    groups_exit: dict[str, list[TradeRecord]] = {}
    for trade in trades:
        groups_exit.setdefault(trade.exit_reason, []).append(trade)
    breakdown["by_exit_reason"] = {
        k: _group_metrics(v) for k, v in groups_exit.items()
    }

    # Dimension: direction
    groups_dir: dict[str, list[TradeRecord]] = {}
    for trade in trades:
        key = "long" if trade.direction == 1 else "short"
        groups_dir.setdefault(key, []).append(trade)
    breakdown["by_direction"] = {
        k: _group_metrics(v) for k, v in groups_dir.items()
    }

    # Dimension: bias alignment
    groups_bias: dict[str, list[TradeRecord]] = {}
    for trade, ctx in zip(trades, contexts):
        if ctx is None:
            key = "no_context"
        else:
            d1_bias = ctx.get("d1_bias", 0)
            aligned = (trade.direction == 1 and d1_bias == 1) or \
                      (trade.direction == -1 and d1_bias == -1)
            key = "aligned" if aligned else "counter"
        groups_bias.setdefault(key, []).append(trade)
    breakdown["by_bias_alignment"] = {
        k: _group_metrics(v) for k, v in groups_bias.items()
    }

    return breakdown


def _group_metrics(trades: list[TradeRecord]) -> dict:
    """Calculate summary metrics for a group of trades."""
    if not trades:
        return {"count": 0}
    r_values = [t.return_r for t in trades]
    winners = [t for t in trades if t.is_winner]
    holding_hours = [
        t.holding_period.total_seconds() / 3600 for t in trades
    ]
    return {
        "count": len(trades),
        "win_rate": len(winners) / len(trades),
        "avg_r": sum(r_values) / len(r_values),
        "total_r": sum(r_values),
        "avg_holding_hours": sum(holding_hours) / len(holding_hours),
        "best_r": max(r_values),
        "worst_r": min(r_values),
    }
