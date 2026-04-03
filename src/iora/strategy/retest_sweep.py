"""Retest sweep runner — batch evaluation across configs.

Stage 1: Build candidates once per symbol (expensive).
Stage 2: Evaluate N configs cheaply per candidate set.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.strategy.retest_config import RetestConfig, ALL_TF_PAIRS
from iora.strategy.retest_candidate import RetestCandidate, build_retest_candidates
from iora.strategy.retest_engine import evaluate_retest_config, RetestResult


@dataclass(slots=True)
class SweepSummary:
    """Summary of a sweep run."""
    results: list[RetestResult] = field(default_factory=list)
    symbol: str = ""

    def top_by_sqn(self, n: int = 10) -> list[RetestResult]:
        ranked = sorted(
            [r for r in self.results if r.metrics.get("total_trades", 0) >= 30],
            key=lambda r: r.metrics.get("sqn", 0),
            reverse=True,
        )
        return ranked[:n]

    def top_by_expectancy(self, n: int = 10) -> list[RetestResult]:
        ranked = sorted(
            [r for r in self.results if r.metrics.get("total_trades", 0) >= 30],
            key=lambda r: r.metrics.get("avg_r", 0),
            reverse=True,
        )
        return ranked[:n]


def default_configs() -> list[RetestConfig]:
    """Generate default sweep configs covering priority TF pairs."""
    configs = []
    priority_pairs = ["H1@H4", "M15@H4", "M15@H1", "M5@H1"]

    for pair in priority_pairs:
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", age_filter="fresh_young"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", zone_role_filter="continuation"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", age_filter="fresh_young", zone_role_filter="continuation", min_bias_strength=2))
        for rr in [1.5, 2.0, 3.0]:
            configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", fixed_rr=rr))
        for sl in ["zone", "atr", "period"]:
            configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", sl_mode=sl))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", session_filter="london"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", touch_policy="first_touch"))
        configs.append(RetestConfig(tf_pair=pair, touch_type="wick_touch", bias_filter="with_daily", cascade_filter="require_htf_signal", cascade_lookback=20))

    return configs


def run_retest_sweep(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tfs: list[str],
    symbol: str,
    configs: list[RetestConfig] | None = None,
) -> SweepSummary:
    """Run full retest sweep for one symbol."""
    if configs is None:
        configs = default_configs()

    all_candidates: list[RetestCandidate] = []
    bar_data_by_entry_tf: dict[str, pd.DataFrame] = {}

    for entry_tf in entry_tfs:
        if entry_tf not in data_by_tf:
            continue
        candidates = build_retest_candidates(
            data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
        )
        all_candidates.extend(candidates)
        bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]

    results: list[RetestResult] = []
    for cfg in configs:
        bar_data = bar_data_by_entry_tf.get(cfg.entry_tf)
        result = evaluate_retest_config(
            candidates=all_candidates, config=cfg, symbol=symbol,
            bar_data=bar_data, all_candidates=all_candidates,
        )
        results.append(result)

    return SweepSummary(results=results, symbol=symbol)
