# src/iora/strategy/push_zone_strategy.py
"""Push zone strategy evaluator.

Replays a ZoneTimeline bar-by-bar, applying StrategyConfig filters
and SL/TP computation to generate EntrySignals and simulate trades.

Key design: this is CHEAP to run. The expensive push zone engine
already ran once to build the timeline. This function just replays
the recorded state with different filter/SL/TP configurations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.push_zone_models import PushZone
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.entry_signal import EntrySignal
from iora.strategy.signal_filters import apply_all_filters
from iora.strategy.sl_tp import compute_sl, compute_tp

# Parent TF mapping for nesting lookup
_PARENT_TF: dict[str, str] = {
    "M1": "M15", "M5": "H1", "M15": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1", "W1": "MN1",
}

# HTF TFs for no-trade zone filtering
_HTF_TFS: set[str] = {"D1", "W1", "MN1"}

# Default ATR estimate (used when no ATR data available)
_DEFAULT_ATR: dict[str, float] = {
    "M1": 0.00015, "M5": 0.0004, "M15": 0.0007,
    "H1": 0.0015, "H4": 0.003, "D1": 0.008,
}


@dataclass(slots=True)
class StrategyResult:
    """Output of a strategy evaluation run."""
    signals: list[EntrySignal]
    trades: list[dict]        # Completed trades (entry + exit)
    open_trades: list[dict]   # Still open at end of timeline


@dataclass(slots=True)
class _OpenPosition:
    """Internal tracker for an open position."""
    signal: EntrySignal
    sl_price: float
    tp_price: float
    entry_bar_idx: int
    max_favorable: float  # For trailing (future use)


def evaluate_strategy(
    timeline: list[ZoneTimelineBar],
    config: StrategyConfig,
    symbol: str = "GBPUSD",
    pip_size: float = 0.0001,
) -> StrategyResult:
    """Replay zone timeline with given config, produce signals and trades.

    Args:
        timeline: Per-bar zone state from build_zone_timeline().
        config: Strategy configuration (filters, SL/TP, direction).
        symbol: Trading symbol (for cost/pip calculations).
        pip_size: Pip size for the symbol.

    Returns:
        StrategyResult with signals, completed trades, and open trades.
    """
    signals: list[EntrySignal] = []
    trades: list[dict] = []
    position: _OpenPosition | None = None

    for bar_idx, bar in enumerate(timeline):
        # --- 1. Check SL/TP on open position ---
        if position is not None:
            exit_result = _check_exit(position, bar, pip_size)
            if exit_result is not None:
                trades.append(exit_result)
                position = None

        # --- 2. Process zone fires for new entries ---
        if position is None:  # Single position mode
            for zone in bar.fires:
                # Only process zones on the entry TF
                if zone.timeframe != config.entry_tf:
                    continue

                direction = "short" if zone.is_supply else "long"

                # Determine signal type
                signal_type = _classify_signal(zone)

                # Find parent zone for nesting
                parent_tf = config.parent_tf
                parent_zone, nesting_depth = _find_parent(
                    bar, zone, parent_tf, direction,
                )

                # Get HTF trend
                htf_trend = bar.trend_by_tf.get(config.htf_trend_tf, 0)

                # Get zone count for entry TF
                counts = bar.zone_counts_by_tf.get(config.entry_tf, (0, 0))
                zone_count = counts[0] if zone.is_supply else counts[1]

                # Collect HTF zones for no-trade filter
                htf_zones = _collect_htf_zones(bar)

                # Apply all filters
                passed, _ = apply_all_filters(
                    signal_type=signal_type,
                    struct_cls=zone.struct_cls,
                    direction=direction,
                    parent_zone=parent_zone,
                    nesting_depth=nesting_depth,
                    htf_trend=htf_trend,
                    zone_count=zone_count,
                    entry_price=bar.close,
                    htf_zones=htf_zones,
                    config=config,
                )
                if not passed:
                    continue

                # Compute SL/TP
                all_zones = _flatten_zones(bar)
                atr = _estimate_atr(config.entry_tf)
                period_lvls = bar.period_levels_by_tf.get(
                    parent_tf, {"highs": [], "lows": []},
                )

                sl = compute_sl(
                    direction=direction,
                    entry_price=bar.close,
                    mode=config.sl_mode,
                    zones=all_zones,
                    atr=atr,
                    period_levels=period_lvls,
                    period_depth=config.sl_period_depth,
                    pip_size=pip_size,
                )
                tp = compute_tp(
                    direction=direction,
                    entry_price=bar.close,
                    sl_price=sl,
                    mode=config.tp_mode,
                    zones=all_zones,
                    atr=atr,
                    period_levels=period_lvls,
                    period_depth=config.sl_period_depth,
                    fixed_rr=config.fixed_rr,
                )

                risk_pips = abs(bar.close - sl) / pip_size
                reward_pips = abs(tp - bar.close) / pip_size

                sig = EntrySignal(
                    zone=zone,
                    zone_tf=config.entry_tf,
                    signal_type=signal_type,
                    struct_cls=zone.struct_cls,
                    direction=direction,
                    parent_zone=parent_zone,
                    parent_tf=parent_tf,
                    nesting_depth=nesting_depth,
                    opposing_nest=zone.is_terminal,
                    trend_by_tf=dict(bar.trend_by_tf),
                    period_levels=dict(bar.period_levels_by_tf),
                    zone_counts=dict(bar.zone_counts_by_tf),
                    exhaustion={},  # Populated in future versions
                    sl_price=sl,
                    tp_price=tp,
                    risk_pips=risk_pips,
                    reward_pips=reward_pips,
                    entry_time=bar.timestamp,
                    entry_price=bar.close,
                )
                signals.append(sig)

                position = _OpenPosition(
                    signal=sig,
                    sl_price=sl,
                    tp_price=tp,
                    entry_bar_idx=bar_idx,
                    max_favorable=bar.close,
                )
                break  # Single position: stop after first entry

    # Handle still-open position at end of timeline
    open_trades: list[dict] = []
    if position is not None and timeline:
        last_bar = timeline[-1]
        open_trades.append({
            "entry_time": position.signal.entry_time,
            "entry_price": position.signal.entry_price,
            "direction": position.signal.direction,
            "sl_price": position.sl_price,
            "tp_price": position.tp_price,
            "current_price": last_bar.close,
            "exit_reason": "end_of_data",
        })

    return StrategyResult(
        signals=signals,
        trades=trades,
        open_trades=open_trades,
    )


# --- Internal helpers ---

def _classify_signal(zone: PushZone) -> str:
    """Classify zone into signal type."""
    if zone.is_terminal:
        return "terminal"
    if zone.is_reversal:
        return "reversal"
    if zone.is_push:
        return "push"
    return "normal"


def _find_parent(
    bar: ZoneTimelineBar,
    child_zone: PushZone,
    parent_tf: str,
    direction: str,
) -> tuple[PushZone | None, int]:
    """Find parent zone containing child zone's price range."""
    parent_zones = bar.zones_by_tf.get(parent_tf, [])
    for pz in parent_zones:
        # Parent must be same-side (supply parent for short child, etc.)
        if direction == "short" and pz.is_supply:
            if pz.contains_price(child_zone.top) or pz.contains_price(child_zone.bottom):
                return pz, 1
        elif direction == "long" and not pz.is_supply:
            if pz.contains_price(child_zone.top) or pz.contains_price(child_zone.bottom):
                return pz, 1
    return None, 0


def _collect_htf_zones(bar: ZoneTimelineBar) -> list[PushZone]:
    """Collect D1/W1/MN1 zones for no-trade filtering."""
    result: list[PushZone] = []
    for tf in _HTF_TFS:
        result.extend(bar.zones_by_tf.get(tf, []))
    return result


def _flatten_zones(bar: ZoneTimelineBar) -> list[PushZone]:
    """Flatten all zones across all TFs into a single list."""
    result: list[PushZone] = []
    for zones in bar.zones_by_tf.values():
        result.extend(zones)
    return result


def _estimate_atr(tf: str) -> float:
    """Get default ATR estimate for a timeframe.

    In production, ATR should come from the data. This fallback
    provides reasonable estimates for GBPUSD-class instruments.
    """
    return _DEFAULT_ATR.get(tf, 0.0010)


def _check_exit(
    pos: _OpenPosition,
    bar: ZoneTimelineBar,
    pip_size: float,
) -> dict | None:
    """Check if SL or TP was hit on this bar. Returns trade dict or None."""
    sig = pos.signal
    direction = sig.direction

    # Update max favorable
    if direction == "long":
        pos.max_favorable = max(pos.max_favorable, bar.high)
        # SL hit: low touches or crosses SL
        if bar.low <= pos.sl_price:
            return _make_trade(sig, pos.sl_price, bar.timestamp, "sl_hit", pip_size)
        # TP hit: high touches or crosses TP
        if bar.high >= pos.tp_price:
            return _make_trade(sig, pos.tp_price, bar.timestamp, "tp_hit", pip_size)
    else:
        pos.max_favorable = min(pos.max_favorable, bar.low)
        # SL hit: high touches or crosses SL
        if bar.high >= pos.sl_price:
            return _make_trade(sig, pos.sl_price, bar.timestamp, "sl_hit", pip_size)
        # TP hit: low touches or crosses TP
        if bar.low <= pos.tp_price:
            return _make_trade(sig, pos.tp_price, bar.timestamp, "tp_hit", pip_size)

    return None


def _make_trade(
    sig: EntrySignal,
    exit_price: float,
    exit_time: pd.Timestamp,
    exit_reason: str,
    pip_size: float,
) -> dict:
    """Build a completed trade dict."""
    if sig.direction == "long":
        pnl_pips = (exit_price - sig.entry_price) / pip_size
    else:
        pnl_pips = (sig.entry_price - exit_price) / pip_size

    return {
        # Core trade fields
        "entry_time": sig.entry_time,
        "exit_time": exit_time,
        "entry_price": sig.entry_price,
        "exit_price": exit_price,
        "direction": sig.direction,
        "sl_price": sig.sl_price,
        "tp_price": sig.tp_price,
        "exit_reason": exit_reason,
        "pnl_pips": pnl_pips,
        "risk_pips": sig.risk_pips,
        "reward_pips": sig.reward_pips,
        "rr_ratio": sig.rr_ratio,
        # Signal classification
        "signal_type": sig.signal_type,
        "struct_cls": sig.struct_cls,
        "zone_tf": sig.zone_tf,
        "parent_tf": sig.parent_tf,
        "nesting_depth": sig.nesting_depth,
        "opposing_nest": sig.opposing_nest,
        # Zone context
        "zone_top": sig.zone.top,
        "zone_bottom": sig.zone.bottom,
        "zone_is_push": sig.zone.is_push,
        "zone_is_reversal": sig.zone.is_reversal,
        "zone_is_terminal": sig.zone.is_terminal,
        "zone_swing_cls": sig.zone.swing_cls,
        "zone_count": sig.zone.count_num,
        # Trend state at entry
        "trend_by_tf": dict(sig.trend_by_tf),
        # Zone counts at entry
        "zone_counts": dict(sig.zone_counts),
    }
