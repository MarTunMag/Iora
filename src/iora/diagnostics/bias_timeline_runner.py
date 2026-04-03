"""Bias Timeline Runner — runs zone engine and collects per-bar bias state.

Follows zone_audit_runner.py pattern. Produces BiasTimelineResult
with per-bar BiasStateRecords.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import inf

import numpy as np
import pandas as pd

from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineState, PushZoneEngineConfig,
    init_push_zone_state, push_zone_engine_tick,
)
from iora.engine.events import EventBus
from iora.diagnostics.bias_timeline import BiasStateRecord, collect_bias_state


@dataclass(slots=True)
class BiasTimelineResult:
    """Full bias timeline output for one symbol."""
    symbol: str
    records: list[BiasStateRecord] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert records to DataFrame."""
        rows = []
        for r in self.records:
            rows.append({
                "timestamp": r.timestamp,
                "d_bias": r.d_bias,
                "d_bias_strength": r.d_bias_strength,
                "d_to_w_relationship": r.d_to_w_relationship,
                "h4_bias": r.h4_bias,
                "h4_vs_daily": r.h4_vs_daily,
                "h1_bias": r.h1_bias,
                "h1_vs_daily": r.h1_vs_daily,
                "nearest_w_supply_dist": r.nearest_w_supply_dist,
                "nearest_w_demand_dist": r.nearest_w_demand_dist,
                "nearest_d_supply_dist": r.nearest_d_supply_dist,
                "nearest_d_demand_dist": r.nearest_d_demand_dist,
                "is_bias_transition": r.is_bias_transition,
                "transition_from": r.transition_from,
                "transition_to": r.transition_to,
            })
        return pd.DataFrame(rows)

    def summary(self) -> dict:
        """Compute summary statistics."""
        total = len(self.records)
        if total == 0:
            return {"total_bars": 0, "transition_count": 0}

        transitions = [r for r in self.records if r.is_bias_transition]

        bias_counts: dict[str, int] = {}
        for r in self.records:
            bias_counts[r.d_bias] = bias_counts.get(r.d_bias, 0) + 1

        d_to_w_counts: dict[str, int] = {}
        for r in self.records:
            d_to_w_counts[r.d_to_w_relationship] = d_to_w_counts.get(r.d_to_w_relationship, 0) + 1

        return {
            "total_bars": total,
            "transition_count": len(transitions),
            "bias_distribution": bias_counts,
            "d_to_w_distribution": d_to_w_counts,
        }


def run_bias_timeline(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    symbol: str = "UNKNOWN",
    period_depth: int = 3,
    sample_every: int = 1,
) -> BiasTimelineResult:
    """Run zone engine and collect per-bar bias state.

    Args:
        data_by_tf: OHLC DataFrames keyed by TF label
        base_tf: Base timeframe for bar iteration
        symbol: Symbol name for labeling
        period_depth: Period tracker history depth
        sample_every: Collect bias state every N bars (1 = every bar).
    """
    tfs = list(data_by_tf.keys())
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()
    config = PushZoneEngineConfig()

    # Pre-compute ATR(14) from base TF data
    base_df = data_by_tf[base_tf]
    atr_series = _compute_atr(base_df, period=14)

    records: list[BiasStateRecord] = []
    prev_d_bias = ""
    bar_idx = 0

    for ctx in iter_bars(base_df, aligned_df, tfs):
        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()

        if bar_idx % sample_every == 0:
            atr_val = atr_series.iloc[ctx.idx] if ctx.idx < len(atr_series) else 0.002
            if np.isnan(atr_val):
                atr_val = 0.002  # Fallback during warm-up

            rec = collect_bias_state(
                state, ctx.timestamp, ctx.close, atr_val, prev_d_bias,
            )
            records.append(rec)
            prev_d_bias = rec.d_bias

        bar_idx += 1

    return BiasTimelineResult(symbol=symbol, records=records)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ATR(period) from OHLC DataFrame."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    return tr.rolling(window=period, min_periods=1).mean()
