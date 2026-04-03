"""Opportunity Counter Runner — runs engine + bias + event detection in one pass.

Produces OpportunityResult with per-event records and aggregate statistics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.diagnostics.bias_timeline import collect_bias_state
from iora.diagnostics.bias_timeline_runner import _compute_atr
from iora.diagnostics.opportunity_counter import OpportunityEvent, detect_events


def _get_pip_size(symbol: str) -> float:
    symbol = symbol.upper()
    if symbol.endswith("JPY") or symbol in ("XAUUSD",):
        return 0.01
    if symbol in ("DE40", "US30", "US500", "US100", "UK100", "JP225"):
        return 1.0
    if symbol in ("BTCUSD", "ETHUSD"):
        return 1.0
    return 0.0001


@dataclass(slots=True)
class OpportunityResult:
    """Full opportunity counter output for one symbol."""
    symbol: str
    events: list[OpportunityEvent] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.events:
            return pd.DataFrame()
        rows = []
        for e in self.events:
            rows.append({
                "timestamp": e.timestamp,
                "zone_tf": e.zone_tf,
                "entry_tf": e.entry_tf,
                "tf_pair": e.tf_pair,
                "touch_type": e.touch_type,
                "zone_side": e.zone_side,
                "zone_role": e.zone_role,
                "age_bucket": e.age_bucket,
                "bias_alignment": e.bias_alignment,
                "test_count_cls": e.test_count_cls,
                "zone_age_bars": e.zone_age_bars,
                "zone_test_count": e.zone_test_count,
                "bias_strength": e.bias_strength,
                "price_distance_at_touch": e.price_distance_at_touch,
                "replacement_count": e.replacement_count,
                "birth_bias_d": e.birth_bias_d,
                "birth_period_pattern": e.birth_period_pattern,
                "birth_price_distance": e.birth_price_distance,
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict[str, dict[str, int]]:
        """Summary counts per TF pair: touch types + bias alignment."""
        result: dict[str, dict[str, int]] = {}
        for e in self.events:
            if e.tf_pair not in result:
                result[e.tf_pair] = {
                    "wick_touch": 0, "body_close": 0,
                    "near_miss": 0, "break_through": 0, "total": 0,
                    "with_daily": 0, "against_daily": 0,
                    "at_transition": 0, "neutral": 0,
                }
            result[e.tf_pair][e.touch_type] = result[e.tf_pair].get(e.touch_type, 0) + 1
            result[e.tf_pair][e.bias_alignment] = result[e.tf_pair].get(e.bias_alignment, 0) + 1
            result[e.tf_pair]["total"] += 1
        return result

    def opportunity_matrix(self) -> pd.DataFrame:
        df = self.to_dataframe()
        if df.empty:
            return df
        group_cols = ["tf_pair", "touch_type", "bias_alignment",
                      "zone_role", "age_bucket", "test_count_cls"]
        matrix = (
            df.groupby(group_cols, observed=True)
            .agg(
                count=("timestamp", "count"),
                avg_zone_age=("zone_age_bars", "mean"),
                avg_bias_strength=("bias_strength", "mean"),
                avg_price_distance_at_touch=("price_distance_at_touch", "mean"),
            )
            .reset_index()
        )
        return matrix


def run_opportunity_counter(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> OpportunityResult:
    """Run zone engine + bias + opportunity detection in one pass.
    Uses base_tf as the entry TF."""
    return _run_single_entry_tf(data_by_tf, base_tf, symbol, period_depth)


def run_opportunity_counter_all_tfs(
    data_by_tf: dict[str, pd.DataFrame],
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
) -> OpportunityResult:
    """Run opportunity counter for ALL entry TFs, merging results."""
    entry_tfs = ["M1", "M5", "M15", "H1"]
    all_events: list[OpportunityEvent] = []

    for entry_tf in entry_tfs:
        if entry_tf not in data_by_tf:
            continue
        result = _run_single_entry_tf(data_by_tf, entry_tf, symbol, period_depth)
        all_events.extend(result.events)

    return OpportunityResult(symbol=symbol, events=all_events)


def _run_single_entry_tf(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    symbol: str,
    period_depth: int,
) -> OpportunityResult:
    """Run opportunity detection for a single entry TF."""
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    base_df = data_by_tf[base_tf]
    atr_series = _compute_atr(base_df, period=14)
    pip_size = _get_pip_size(symbol)

    all_events: list[OpportunityEvent] = []
    prev_d_bias = ""

    prev_swing_cls: dict[str, dict[str, str]] = {}

    bar_idx = 0
    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
        if np.isnan(atr_val):
            atr_val = 0.002

        bias_rec = collect_bias_state(
            state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
        )
        prev_d_bias = bias_rec.d_bias

        events = detect_events(
            tick_states=state.tick_states,
            entry_tf=base_tf,
            high=ctx.high, low=ctx.low, close=ctx.close,
            timestamp=ctx.timestamp,
            bias_rec=bias_rec, atr=atr_val, pip_size=pip_size,
            bar_idx=bar_idx, prev_swing_cls=prev_swing_cls,
        )
        all_events.extend(events)

        for tf, ts in state.tick_states.items():
            if tf not in prev_swing_cls:
                prev_swing_cls[tf] = {"supply": "", "demand": ""}
            if ts.supply_zones and ts.supply_zones[-1].swing_cls:
                prev_swing_cls[tf]["supply"] = ts.supply_zones[-1].swing_cls
            if ts.demand_zones and ts.demand_zones[-1].swing_cls:
                prev_swing_cls[tf]["demand"] = ts.demand_zones[-1].swing_cls

        bar_idx += 1

    return OpportunityResult(symbol=symbol, events=all_events)
