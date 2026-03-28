"""
Signal Engine -- Stateful bar-by-bar signal processing.

Wraps the pipeline's engine ticks with per-bar feature extraction,
rule processing, and position state tracking. The same code path
serves chart visualization, backtesting, and live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.rules.signal import Signal, ENTRY, EXIT, ADD_ON, HEDGE, SL_MOVE, TP_TARGET
from iora.rules.position_state import PositionState, Direction, TradeMode

from iora.orchestrator.pipeline import (
    PipelineConfig, PipelineOutput,
    _classify_structure_breaks,
    _tick_structure_and_cascade,
    _collect_outputs,
)
from iora.orchestrator.zone_engine import (
    ZoneConfig, init_zone_state, zone_engine_tick,
)
from iora.orchestrator.structure_engine import (
    StructureConfig, init_structure_state,
)
from iora.engine.early_cascade import (
    EarlyCascadeState, early_cascade_tick, inject_early_anchors,
)
from iora.engine.events import EventBus
from iora.engine.models import EventID
from iora.engine.macro_bias import MacroBiasTickState
from iora.engine.cycle_sm import CycleTickState
from iora.engine.cascade_tracker import init_cascade_state
from iora.engine.htf_bias import init_htf_bias_state
from iora.data.tf_alignment import TF_ORDER, build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.features.composite import extract_bar_features
from iora.rules import create_default_registry
from iora.rules.sweep_state import SweepStateTracker

# Fields captured from BarFeatures at trade entry for diagnostic analysis
CONTEXT_FIELDS = [
    "d1_price_in_supply", "d1_price_in_demand",
    "h4_price_in_supply", "h4_price_in_demand",
    "h1_price_in_supply", "h1_price_in_demand",
    "m15_price_in_supply", "m15_price_in_demand",
    "d1_nearest_supply_price", "d1_nearest_demand_price",
    "h4_nearest_supply_price", "h4_nearest_demand_price",
    "h1_nearest_supply_price", "h1_nearest_demand_price",
    "d1_bias", "h4_bias", "h1_bias",
    "d_phase", "w_phase",
    "d_hh", "d_ll", "d_lh", "d_hl",
    "w_hh", "w_ll", "w_lh", "w_hl",
    "choch_bull", "choch_bear",
    "bos_bull", "bos_bear",
    "h1_bos_bull", "h1_bos_bear",
    "h1_choch_bull", "h1_choch_bear",
    "wave_label", "wave_phase",
    "ub_h1_sup", "ub_h1_dem",
    "ub_h4_sup", "ub_h4_dem",
    "ub_d_sup", "ub_d_dem",
    "context_mode", "context_detail",
]


@dataclass
class SignalEngineState:
    """Mutable state tracked across bars by the signal engine."""
    last_htf_break_time: pd.Timestamp | None = None
    last_htf_break_bars: int = 999
    growth_entry_bar: int = 999

    def increment_bars(self) -> None:
        if self.last_htf_break_bars < 9999:
            self.last_htf_break_bars += 1
        if self.growth_entry_bar < 9999:
            self.growth_entry_bar += 1


def execute_signals(
    signals: list[Signal],
    position: PositionState,
    state: SignalEngineState,
    bar_features: object | None = None,
) -> list[dict]:
    """Dispatch signals to PositionState. Returns trade log entries."""
    log: list[dict] = []

    for sig in signals:
        if sig.signal_type == ENTRY:
            direction = Direction.SHORT if sig.direction == "bear" else Direction.LONG
            trade = position.open_trade(
                mode=TradeMode.GROWTH, direction=direction,
                entry_price=sig.price, entry_time=sig.time,
                sl_price=sig.sl_price or sig.price,
                tp_price=sig.tp_price, rule_id=sig.rule_id,
            )
            if trade is not None:
                state.growth_entry_bar = 0
                log_entry = {
                    "time": sig.time, "action": "ENTRY",
                    "direction": sig.direction, "price": sig.price,
                    "sl": sig.sl_price, "lots": trade.lots,
                    "trade_id": trade.trade_id, "rule_id": sig.rule_id,
                }
                if bar_features is not None:
                    log_entry["entry_context"] = {
                        f: getattr(bar_features, f, None) for f in CONTEXT_FIELDS
                    }
                log.append(log_entry)

        elif sig.signal_type == EXIT:
            closed = position.close_all(TradeMode.GROWTH)
            if closed:
                state.growth_entry_bar = 999
                log.append({
                    "time": sig.time, "action": "EXIT",
                    "direction": sig.direction, "price": sig.price,
                    "closed_count": len(closed),
                    "closed_lots": sum(t.lots for t in closed),
                })

        elif sig.signal_type == ADD_ON:
            direction = Direction.SHORT if sig.direction == "bear" else Direction.LONG
            trade = position.open_trade(
                mode=TradeMode.GROWTH, direction=direction,
                entry_price=sig.price, entry_time=sig.time,
                sl_price=sig.sl_price or sig.price,
                tp_price=sig.tp_price, rule_id=sig.rule_id,
            )
            if trade is not None:
                log_entry = {
                    "time": sig.time, "action": "ADD_ON",
                    "direction": sig.direction, "price": sig.price,
                    "sl": sig.sl_price, "lots": trade.lots,
                    "trade_id": trade.trade_id, "rule_id": sig.rule_id,
                }
                if bar_features is not None:
                    log_entry["entry_context"] = {
                        f: getattr(bar_features, f, None) for f in CONTEXT_FIELDS
                    }
                log.append(log_entry)

        elif sig.signal_type == HEDGE:
            direction = Direction.SHORT if sig.direction == "bear" else Direction.LONG
            trade = position.open_trade(
                mode=TradeMode.SCALP, direction=direction,
                entry_price=sig.price, entry_time=sig.time,
                sl_price=sig.sl_price or sig.price,
                tp_price=sig.tp_price, rule_id=sig.rule_id,
            )
            if trade is not None:
                log_entry = {
                    "time": sig.time, "action": "HEDGE",
                    "direction": sig.direction, "price": sig.price,
                    "sl": sig.sl_price, "lots": trade.lots,
                    "trade_id": trade.trade_id, "rule_id": sig.rule_id,
                }
                if bar_features is not None:
                    log_entry["entry_context"] = {
                        f: getattr(bar_features, f, None) for f in CONTEXT_FIELDS
                    }
                log.append(log_entry)

        elif sig.signal_type == SL_MOVE:
            if sig.price is not None:
                count = position.trail_all_growth(sig.price)
                if count > 0:
                    log.append({
                        "time": sig.time, "action": "SL_MOVE",
                        "new_sl": sig.price, "trades_updated": count,
                    })

    return log


@dataclass
class SignalEngineOutput:
    """Complete output from signal engine run."""
    pipeline: PipelineOutput
    signals: list[Signal]
    trade_log: list[dict]
    final_position: PositionState
    context_series: list[dict] = field(default_factory=list)
    features_series: list[dict] = field(default_factory=list)


def run_signal_engine(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    pipeline_config: PipelineConfig | None = None,
    account_balance: float = 10_000.0,
    risk_pct: float = 0.01,
    disabled_rules: list[str] | None = None,
) -> SignalEngineOutput:
    """
    Run the full pipeline + signal layer in one bar-by-bar pass.
    """
    if pipeline_config is None:
        pipeline_config = PipelineConfig(macro_bias_on=False, cycle_on=False)

    zone_config = ZoneConfig(
        doji_pct=pipeline_config.doji_pct,
        lookback=pipeline_config.lookback,
        ub_exhaust_threshold=pipeline_config.ub_exhaust_threshold,
    )
    structure_config = StructureConfig(
        doji_pct=pipeline_config.doji_pct,
        lookback=pipeline_config.lookback,
        tl_history=pipeline_config.tl_history,
    )

    aligned_df, _ = build_aligned_multi_tf(
        data_by_tf, base_tf, pipeline_config.doji_pct,
    )
    base_df = data_by_tf[base_tf]
    tf_list = [tf for tf in TF_ORDER if tf in data_by_tf]

    # Initialize engine states (same as run_pipeline)
    zone_state = init_zone_state(tf_list)
    structure_state = init_structure_state(tf_list)
    early_cascade_state = EarlyCascadeState()
    cascade_state = init_cascade_state(tf_list)
    htf_bias_state = init_htf_bias_state()
    bus = EventBus()
    structure_breaks: list = []

    # Initialize signal layer
    registry = create_default_registry()
    if disabled_rules:
        for rule_id in disabled_rules:
            registry.disable(rule_id)
    position = PositionState(
        account_balance=account_balance,
        risk_pct=risk_pct,
    )
    engine_state = SignalEngineState()
    sweep_tracker = SweepStateTracker()
    all_signals: list[Signal] = []
    all_trade_log: list[dict] = []
    context_series: list[dict] = []
    features_series: list[dict] = []

    for ctx in iter_bars(base_df, aligned_df, tf_list):
        ev_offset = len(bus)

        # Steps 1-5: Engine ticks (same as pipeline)
        zone_engine_tick(zone_state, ctx, zone_config, bus)
        _classify_structure_breaks(bus, ev_offset, structure_breaks)

        # Early cascade: detect parent-TF structural shifts via child-TF CHoCH
        early_anchors = early_cascade_tick(
            early_cascade_state, zone_state.zone_states,
            ctx.timestamp, bus,
        )
        if early_anchors:
            inject_early_anchors(
                early_anchors, structure_state.xtf_tl_states,
            )

        _tick_structure_and_cascade(
            structure_state, zone_state, cascade_state,
            htf_bias_state, ctx, structure_config, bus, ev_offset,
        )

        # Step 6: Track HTF breaks from events
        bar_events = bus.peek()[ev_offset:]
        for e in bar_events:
            if (e.id == EventID.ZONE_BREAK
                    and e.timeframe in ("D1", "H4", "W1")):
                engine_state.last_htf_break_time = ctx.timestamp
                engine_state.last_htf_break_bars = 0

        # Step 7: Extract features
        features = extract_bar_features(
            timestamp=ctx.timestamp,
            close=ctx.close,
            open_=ctx.open_,
            high=ctx.high,
            low=ctx.low,
            zone_state=zone_state,
            canopy_tl_states=structure_state.tl_states,
            d_structure=structure_state.d_structure,
            w_structure=structure_state.w_structure,
            h4_push=structure_state.h4_push,
            wave_sm=structure_state.wave_sm,
            ew=structure_state.ew,
            macro_bias=0,
            cycle_label="",
            bar_events=bar_events,
            htf_bias=htf_bias_state,
        )

        # Collect context mode per bar
        context_series.append({
            "time": ctx.timestamp,
            "mode": features.context_mode,
            "detail": features.context_detail,
        })
        # Collect micro-layer features for Pulse Panel
        features_series.append({
            "time": ctx.timestamp,
            "m15_in_sup": features.m15_price_in_supply,
            "m15_in_dem": features.m15_price_in_demand,
            "m5_in_sup": features.m5_price_in_supply,
            "m5_in_dem": features.m5_price_in_demand,
            "m1_choch_bull": features.m1_choch_bull,
            "m1_choch_bear": features.m1_choch_bear,
            "m5_choch_bull": features.m5_choch_bull,
            "m5_choch_bear": features.m5_choch_bear,
            "d_phase": features.d_phase,
            "h4_push_phase": features.h4_push_phase,
            "h4_push_count": features.h4_push_count,
            "wave_label": features.wave_label,
        })

        # Steps 8-9: Check SL/TP hits
        sl_hits = position.check_sl_hits(ctx.high, ctx.low)
        for t in sl_hits:
            all_trade_log.append({
                "time": ctx.timestamp, "action": "SL_HIT",
                "direction": t.direction.value,
                "sl_price": t.sl_price, "lots": t.lots,
                "trade_id": t.trade_id,
            })
            if t.mode == TradeMode.GROWTH and position.is_flat:
                engine_state.growth_entry_bar = 999

        tp_hits = position.check_tp_hits(ctx.high, ctx.low)
        for t in tp_hits:
            all_trade_log.append({
                "time": ctx.timestamp, "action": "TP_HIT",
                "direction": t.direction.value,
                "tp_price": t.tp_price, "lots": t.lots,
                "trade_id": t.trade_id,
            })

        # Step 10: Process rules
        bar_signals = registry.evaluate_all(
            features=features,
            position=position,
            bars_since_htf_break=engine_state.last_htf_break_bars,
            bars_since_growth_entry=engine_state.growth_entry_bar,
            sweep_state=sweep_tracker,
        )

        # Step 11: Execute signals
        if bar_signals:
            log_entries = execute_signals(
                bar_signals, position, engine_state,
                bar_features=features,
            )
            all_signals.extend(bar_signals)
            all_trade_log.extend(log_entries)

        # Tick sweep state tracker (reads signals this bar + features)
        sweep_tracker.tick(features, bar_signals if bar_signals else [])

        # Add sweep chain state (after tick so it reflects current bar)
        features_series[-1].update({
            "sweep_confirmed": sweep_tracker.sweep_confirmed,
            "h1_bos_fired": sweep_tracker.h1_bos_fired,
            "chain_count": sweep_tracker.chain_count,
            "push_direction": sweep_tracker.push_direction,
        })

        # Age recency counters
        engine_state.increment_bars()

    # Collect pipeline output
    pipeline_output = _collect_outputs(
        zone_state, structure_state,
        MacroBiasTickState(), CycleTickState(),
        cascade_state, htf_bias_state,
        structure_breaks, tf_list,
    )

    return SignalEngineOutput(
        pipeline=pipeline_output,
        signals=all_signals,
        trade_log=all_trade_log,
        final_position=position,
        context_series=context_series,
        features_series=features_series,
    )
