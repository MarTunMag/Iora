"""Retest sweep runner — batch evaluation across configs.

Stage 1: Build candidates once per symbol (expensive).
Stage 2: Evaluate N configs cheaply per candidate set.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pandas as pd

from iora.strategy.retest_config import RetestConfig, ALL_TF_PAIRS
from iora.strategy.retest_candidate import (
    RetestCandidate,
    CandidateBuildResult,
    build_retest_candidates,
    build_retest_candidates_with_births,
)
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
    """Generate expanded sweep configs covering all dimensions.

    Phase 1 expansion: ~200+ configs testing all existing filter dimensions.
    Informed by 56-config sweep findings (level4-sweep-analysis.md).
    """
    configs: list[RetestConfig] = []
    seen: set[str] = set()

    def _add(c: RetestConfig) -> None:
        """Deduplicate configs by their full field signature."""
        key = (
            c.tf_pair, c.touch_type, c.bias_filter, c.zone_role_filter,
            c.age_filter, c.test_count_filter, c.min_bias_strength,
            c.max_replacement_count, c.direction, c.session_filter,
            c.cascade_filter, c.cascade_lookback, c.cascade_direction,
            c.entry_mode, c.sl_mode, c.tp_mode, c.fixed_rr, c.sl_atr_mult,
            c.tp_htf,
            c.partial_tp, c.partial_unit1_pct, c.partial_unit1_rr, c.partial_unit2_tp,
            c.touch_policy, c.max_concurrent,
            c.birth_pattern_filter, c.retest_number_filter,
            c.time_since_creation_filter, c.parent_tf_boundary_filter,
            c.inside_w_zone_filter, c.d_to_w_filter,
            c.near_pdh_pdl, c.premium_discount,
            c.layered_sl_mode,
            c.hma_filter, c.hma_cross_trigger, str(c.hma_cross_lookback),
            c.hma_period, c.hma_source,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    # All TF pairs (including new M5@M15 and H1@D1)
    all_pairs = ["H1@H4", "M15@H4", "M15@H1", "M5@H1", "M5@M15", "H1@D1"]

    # ── Section A: Per-pair baselines (wick_touch, the proven default) ────
    for pair in all_pairs:
        # Unfiltered baseline
        _add(RetestConfig(tf_pair=pair))
        # With-daily bias (the original sweep baseline)
        _add(RetestConfig(tf_pair=pair, bias_filter="with_daily"))
        # Full stack: bias + age + role
        _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", age_filter="fresh_young"))
        _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", zone_role_filter="continuation"))
        _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", age_filter="fresh_young",
             zone_role_filter="continuation", min_bias_strength=2))

    # ── Section B: Touch type baselines — HIGHEST PRIORITY GAP ────────────
    for pair in all_pairs:
        for touch in ["body_close", "any"]:
            _add(RetestConfig(tf_pair=pair, touch_type=touch))
            _add(RetestConfig(tf_pair=pair, touch_type=touch, bias_filter="with_daily"))

    # ── Section C: Bias filter — HIGHEST PRIORITY GAP ─────────────────────
    for pair in all_pairs:
        # Against-daily (43% of H1@H4 wicks — dominates HTF pairs)
        _add(RetestConfig(tf_pair=pair, bias_filter="against_daily"))
        # At-transition (2-3% of wicks, highest conviction)
        _add(RetestConfig(tf_pair=pair, bias_filter="at_transition"))

    # ── Section D: Zone role (push, pullback, reversal) ───────────────────
    for pair in all_pairs:
        for role in ["push", "pullback", "reversal"]:
            _add(RetestConfig(tf_pair=pair, zone_role_filter=role))

    # ── Section E: Individual age buckets ─────────────────────────────────
    for pair in all_pairs:
        for age in ["fresh", "young", "mature", "old"]:
            _add(RetestConfig(tf_pair=pair, age_filter=age))

    # ── Section F: Direction (long / short) — IMPORTANT ───────────────────
    for pair in all_pairs:
        for direction in ["long", "short"]:
            _add(RetestConfig(tf_pair=pair, direction=direction))

    # ── Section G: RR sweep (3.0 won 4/5, test 4.0 and 5.0) ─────────────
    for pair in all_pairs:
        for rr in [1.5, 2.0, 3.0, 4.0, 5.0]:
            _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", fixed_rr=rr))

    # ── Section H: SL modes ───────────────────────────────────────────────
    for pair in all_pairs:
        for sl in ["zone", "atr", "period"]:
            _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", sl_mode=sl))
        # ATR multiplier variants
        for mult in [1.0, 2.0, 2.5]:
            _add(RetestConfig(tf_pair=pair, sl_mode="atr", sl_atr_mult=mult))

    # ── Section I: Session filters (low priority — any wins 4/5) ─────────
    for pair in all_pairs:
        for sess in ["london", "london_ny_overlap", "no_asian"]:
            _add(RetestConfig(tf_pair=pair, session_filter=sess))

    # ── Section J: Touch policy ───────────────────────────────────────────
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, bias_filter="with_daily", touch_policy="first_touch"))

    # ── Section K: Cascade variations ─────────────────────────────────────
    for pair in all_pairs:
        # Original htf_signal with different lookbacks
        for lb in [5, 10, 20, 50]:
            _add(RetestConfig(tf_pair=pair, cascade_filter="require_htf_signal",
                 cascade_lookback=lb))
        # Confluence-2
        _add(RetestConfig(tf_pair=pair, cascade_filter="require_confluence_2",
             cascade_lookback=20))

    # ── Section L: Replacement count ──────────────────────────────────────
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, max_replacement_count=0))  # original only
        _add(RetestConfig(tf_pair=pair, max_replacement_count=3))

    # ── Section M: Key combination configs (from checklist §16) ───────────

    # M1: H1@H4 + against_daily + continuation + young
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="against_daily",
         zone_role_filter="continuation", age_filter="young"))
    # M2: H1@H4 + push zone only + any bias
    _add(RetestConfig(tf_pair="H1@H4", zone_role_filter="push"))
    # M3: H1@D1 + reversal + with_daily
    _add(RetestConfig(tf_pair="H1@D1", bias_filter="with_daily",
         zone_role_filter="reversal"))
    # M4: M5@M15 + with_daily + fresh + wick_touch
    _add(RetestConfig(tf_pair="M5@M15", bias_filter="with_daily",
         age_filter="fresh"))
    # M5: H1@H4 + body_close + any bias
    _add(RetestConfig(tf_pair="H1@H4", touch_type="body_close"))
    # M6: H1@H4 + body_close + with_daily
    _add(RetestConfig(tf_pair="H1@H4", touch_type="body_close",
         bias_filter="with_daily"))
    # M7: H1@H4 + body_close + against_daily
    _add(RetestConfig(tf_pair="H1@H4", touch_type="body_close",
         bias_filter="against_daily"))
    # M8: H1@H4 + at_transition
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="at_transition"))
    # M9: M15@H4 + reversal + against_daily
    _add(RetestConfig(tf_pair="M15@H4", bias_filter="against_daily",
         zone_role_filter="reversal"))
    # M10: H1@H4 + against_daily + rr=3.0
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="against_daily", fixed_rr=3.0))
    # M11: H1@H4 + against_daily + rr=4.0
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="against_daily", fixed_rr=4.0))
    # M12: H1@H4 + against_daily + rr=5.0
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="against_daily", fixed_rr=5.0))
    # M13: H1@H4 + old zones only (proven structural levels)
    _add(RetestConfig(tf_pair="H1@H4", age_filter="old"))
    # M14: All pairs + direction=long + rr=3.0
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, direction="long", fixed_rr=3.0))
        _add(RetestConfig(tf_pair=pair, direction="short", fixed_rr=3.0))
    # M15: Against-daily on all pairs with rr=3.0 (Cohort A test)
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, bias_filter="against_daily", fixed_rr=3.0))
    # M16: H1@H4 + against_daily + continuation
    _add(RetestConfig(tf_pair="H1@H4", bias_filter="against_daily",
         zone_role_filter="continuation"))
    # M17: XAUUSD-targeted: M5@H1 + with_daily + continuation + long
    _add(RetestConfig(tf_pair="M5@H1", bias_filter="with_daily",
         zone_role_filter="continuation", direction="long"))
    # M18: Cohort A minimal: H1@H4 + any + any + rr=3.0 + sl=zone
    _add(RetestConfig(tf_pair="H1@H4", fixed_rr=3.0, sl_mode="zone"))
    # M19: H1@D1 + with_daily + rr=3.0
    _add(RetestConfig(tf_pair="H1@D1", bias_filter="with_daily", fixed_rr=3.0))
    # M20: H1@D1 + against_daily
    _add(RetestConfig(tf_pair="H1@D1", bias_filter="against_daily"))
    # M21: M5@M15 + any + rr=3.0 (fast intraday baseline)
    _add(RetestConfig(tf_pair="M5@M15", fixed_rr=3.0))
    # M22: H1@H4 + push + with_daily
    _add(RetestConfig(tf_pair="H1@H4", zone_role_filter="push",
         bias_filter="with_daily"))
    # M23: H1@H4 + push + against_daily
    _add(RetestConfig(tf_pair="H1@H4", zone_role_filter="push",
         bias_filter="against_daily"))

    # ── Section N-pre: TP mode = period (Phase 2d) ──────────────────────
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, tp_mode="period", sl_mode="zone"))
        _add(RetestConfig(tf_pair=pair, tp_mode="period", sl_mode="zone",
             bias_filter="with_daily"))

    # ── Section N: Birth pattern filter (Phase 2a) ────────────────────────
    for pair in all_pairs:
        for bp in ["compression", "trending", "expansion"]:
            _add(RetestConfig(tf_pair=pair, birth_pattern_filter=bp))
    # Compression + with_daily on H1@H4 (highest conviction combo)
    _add(RetestConfig(tf_pair="H1@H4", birth_pattern_filter="compression",
         bias_filter="with_daily"))

    # ── Section O: Retest number filter (Phase 2b) ────────────────────────
    for pair in all_pairs:
        for rn in ["1-3", "4-10", "10+"]:
            _add(RetestConfig(tf_pair=pair, retest_number_filter=rn))

    # ── Section P: Time since creation filter (Phase 2c) ──────────────────
    for pair in all_pairs:
        for ts in ["0-3h", "3-12h", "12h-3d", "3d+"]:
            _add(RetestConfig(tf_pair=pair, time_since_creation_filter=ts))

    # ── Section Q: Parent-TF boundary timing (Phase 2e) ───────────────────
    for pair in all_pairs:
        for pb in ["0-1_parent_bars", "1-2_parent_bars", "2-4_parent_bars", "4+_parent_bars"]:
            _add(RetestConfig(tf_pair=pair, parent_tf_boundary_filter=pb))

    # ── Section R: Inside weekly zone (Phase 3a) ──────────────────────────
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, inside_w_zone_filter="inside"))
        _add(RetestConfig(tf_pair=pair, inside_w_zone_filter="outside"))

    # ── Section S: D-to-W relationship (Phase 3b) ─────────────────────────
    for pair in all_pairs:
        for dtw in ["continuation", "pullback", "inside_zone", "neutral"]:
            _add(RetestConfig(tf_pair=pair, d_to_w_filter=dtw))

    # ── Section T: Inside HTF zone cascade (Phase 3c) ─────────────────────
    for pair in all_pairs:
        _add(RetestConfig(tf_pair=pair, cascade_filter="require_inside_htf_zone"))

    # ── Section U: Structural SL/TP (Phase 4a) ─────────────────────────
    priority_pairs = ["H1@H4", "H1@D1", "M15@H4", "M5@H1"]
    for pair in priority_pairs:
        # Structure SL + zone TP
        _add(RetestConfig(tf_pair=pair, sl_mode="structure", tp_mode="zone"))
        _add(RetestConfig(tf_pair=pair, sl_mode="structure", tp_mode="zone",
             bias_filter="with_daily"))
        _add(RetestConfig(tf_pair=pair, sl_mode="structure", tp_mode="zone",
             bias_filter="against_daily"))
        # Structure SL + fixed RR (isolate SL impact)
        for rr in [2.0, 3.0, 4.0]:
            _add(RetestConfig(tf_pair=pair, sl_mode="structure", tp_mode="fixed_rr",
                 fixed_rr=rr))
        # Structure SL + zone TP + role filters
        for role in ["push", "reversal", "continuation"]:
            _add(RetestConfig(tf_pair=pair, sl_mode="structure", tp_mode="zone",
                 zone_role_filter=role))

    # ── Section V: Limit order entries (Phase 4b) ──────────────────────
    for pair in priority_pairs:
        # Limit + zone SL (baseline limit)
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             bias_filter="with_daily"))
        # Limit + structure SL + zone TP (full structural entry)
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="structure",
             tp_mode="zone"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="structure",
             tp_mode="zone", bias_filter="with_daily"))
        # Limit + push zone (order block thesis: 0% break-through + best price)
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", zone_role_filter="push",
             sl_mode="structure"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", zone_role_filter="push",
             sl_mode="zone"))
        # Limit + structure SL + zone TP + push only
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="structure",
             tp_mode="zone", zone_role_filter="push"))

    # ── Section W: PDH/PDL proximity (Phase 4c) ───────────────────────
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, near_pdh_pdl="near",
             sl_mode="structure", tp_mode="zone"))
        _add(RetestConfig(tf_pair=pair, near_pdh_pdl="near",
             sl_mode="structure", tp_mode="zone", bias_filter="with_daily"))

    # ── Section X: Premium/discount alignment (Phase 4d) ──────────────
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, premium_discount="aligned",
             sl_mode="structure", tp_mode="zone"))
        _add(RetestConfig(tf_pair=pair, premium_discount="aligned",
             sl_mode="structure", tp_mode="zone", bias_filter="with_daily"))

    # ── Section Y: Combined PDH/PDL + premium/discount (Phase 4e) ─────
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, near_pdh_pdl="near",
             premium_discount="aligned", sl_mode="structure", tp_mode="zone"))
        _add(RetestConfig(tf_pair=pair, near_pdh_pdl="near",
             premium_discount="aligned", sl_mode="structure", tp_mode="zone",
             bias_filter="with_daily"))

    # ── Section Z: HIGH-VALUE LIMIT COMBINATIONS (from findings analysis) ──
    # These are the untested limit combos identified in level4-findings-and-next-steps.md

    all_limit_pairs = ["H1@H4", "H1@D1", "M15@H4", "M5@H1", "M5@M15", "M15@H1"]

    # Z1: Limit + against_daily (THE biggest gap — against_daily dominates H1@H4)
    for pair in all_limit_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             bias_filter="against_daily"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             bias_filter="against_daily", fixed_rr=3.0))

    # Z2: Limit + reversal zones (42.2% WR market → with limit should improve)
    for pair in all_limit_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             zone_role_filter="reversal"))

    # Z3: Limit + compression-born zones (2x durability)
    for pair in all_limit_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             birth_pattern_filter="compression"))

    # Z4: Limit + retest #4-10 (the sweet spot)
    for pair in all_limit_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             retest_number_filter="4-10"))

    # Z5: Limit + body_close (for adjacent-TF pairs — accumulation inside zone)
    for pair in ["M5@M15", "M5@H1", "M15@H1"]:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             touch_type="body_close"))

    # Z6: Limit + direction (long-only and short-only)
    for pair in all_limit_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             direction="long"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             direction="short"))

    # Z7: Limit + R:R variations (test 1.5, 3.0, 4.0 — current only tests 2.0)
    for pair in priority_pairs:
        for rr in [1.5, 3.0, 4.0]:
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 fixed_rr=rr))

    # Z8: Limit + structural SL + against_daily (best SL + best bias for HTF)
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="structure",
             tp_mode="zone", bias_filter="against_daily"))

    # Z9: Limit + push + against_daily (order block + counter-trend = highest conviction?)
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             zone_role_filter="push", bias_filter="against_daily"))

    # Z10: Limit + fresh/young age
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             age_filter="fresh"))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             age_filter="young"))

    # Z11: Limit + time since creation (12h-3d = sweet spot from Level 1-3)
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             time_since_creation_filter="12h-3d"))

    # Z12: Limit + at_transition (bias flip at zone — highest conviction?)
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             bias_filter="at_transition"))

    # Z13: Full stack combos — limit + against_daily + continuation + young
    _add(RetestConfig(tf_pair="H1@H4", entry_mode="limit", sl_mode="zone",
         bias_filter="against_daily", zone_role_filter="continuation",
         age_filter="young"))
    _add(RetestConfig(tf_pair="H1@H4", entry_mode="limit", sl_mode="zone",
         bias_filter="against_daily", zone_role_filter="continuation",
         age_filter="young", fixed_rr=3.0))
    # Limit + with_daily + push (strongest conviction stack)
    _add(RetestConfig(tf_pair="H1@D1", entry_mode="limit", sl_mode="zone",
         bias_filter="with_daily", zone_role_filter="push"))
    _add(RetestConfig(tf_pair="H1@D1", entry_mode="limit", sl_mode="zone",
         bias_filter="with_daily", zone_role_filter="push", fixed_rr=3.0))

    # ── Section ZZ: Layered cascade limit orders ──────────────────────
    layered_pairs = ["H1@H4", "H1@D1", "M15@H4", "M5@H1"]

    for pair in layered_pairs:
        # Layered + own SL (tightest, highest RR)
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="own", sl_mode="zone", max_concurrent=3))
        # Layered + HTF SL (safest, 0% break-through backstop)
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="htf", sl_mode="zone", max_concurrent=3))
        # Layered + own SL + with_daily
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="own", sl_mode="zone", bias_filter="with_daily",
             max_concurrent=3))
        # Layered + own SL + against_daily
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="own", sl_mode="zone", bias_filter="against_daily",
             max_concurrent=3))
        # Layered + own SL + push zones only (order block thesis)
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="own", sl_mode="zone", zone_role_filter="push",
             max_concurrent=3))
        # Layered + HTF SL + zone TP
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="htf", tp_mode="zone", max_concurrent=3))
        # Layered + R:R variations
        for rr in [1.5, 3.0, 4.0]:
            _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
                 layered_sl_mode="own", fixed_rr=rr, max_concurrent=3))

    # Specific high-conviction combos
    _add(RetestConfig(tf_pair="H1@H4", entry_mode="cascade_layered",
         layered_sl_mode="own", bias_filter="against_daily",
         zone_role_filter="continuation", max_concurrent=3))
    _add(RetestConfig(tf_pair="H1@D1", entry_mode="cascade_layered",
         layered_sl_mode="htf", bias_filter="with_daily",
         zone_role_filter="push", max_concurrent=3))

    # ── Section HMA-A: HMA direction filter (state-based) ──────────────
    hma_entry_pairs = ["M5@H1", "M15@H1", "M5@M15", "M15@H4", "H1@H4"]

    for pair in hma_entry_pairs:
        for ref_tf in ["with_hma_h1", "with_hma_h4"]:
            for period in [12, 24]:
                for source in ["close", "ha_close"]:
                    _add(RetestConfig(tf_pair=pair, hma_filter=ref_tf,
                         hma_period=period, hma_source=source))

    # ── Section HMA-B: HA-cross-HMA trigger (event-based) ──────────────
    for pair in hma_entry_pairs:
        for ref_tf in ["h1", "h4"]:
            for lookback in [5, 10, 20, 50, "until_reverse"]:
                for period in [12, 24]:
                    _add(RetestConfig(tf_pair=pair, hma_cross_trigger=ref_tf,
                         hma_cross_lookback=lookback, hma_period=period))

    # ── Section HMA-C: High-value combos (HMA + proven configs) ────────

    # limit + hma_filter — does HMA improve the SQN 23.64 limit config?
    for pair in priority_pairs:
        for ref_tf in ["with_hma_h1", "with_hma_h4"]:
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 hma_filter=ref_tf, hma_period=24))

    # limit + hma_cross_trigger — does the cross event improve limit entries?
    for pair in priority_pairs:
        for ref_tf in ["h1", "h4"]:
            for lookback in [20, "until_reverse"]:
                _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                     hma_cross_trigger=ref_tf, hma_cross_lookback=lookback,
                     hma_period=24))

    # cascade_layered + hma_filter — does HMA improve layered cascade?
    for pair in ["H1@H4", "H1@D1", "M15@H4", "M5@H1"]:
        _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
             layered_sl_mode="own", hma_filter="with_hma_h4",
             hma_period=24, max_concurrent=3))

    # against_daily + hma_filter — complementary signals?
    for pair in priority_pairs:
        _add(RetestConfig(tf_pair=pair, bias_filter="against_daily",
             hma_filter="with_hma_h1", hma_period=24))
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             bias_filter="against_daily", hma_filter="with_hma_h1",
             hma_period=24))

    return configs


def cross_tf_tp_configs() -> list[RetestConfig]:
    """Focused sweep: limit entries with cross-TF TP targets.

    Only limit configs targeting opposing zones on HIGHER TFs.
    Estimated ~80-100 configs — much smaller than the 797-config discovery sweep.
    """
    configs: list[RetestConfig] = []
    seen: set[str] = set()

    def _add(c: RetestConfig) -> None:
        key = (
            c.tf_pair, c.touch_type, c.bias_filter, c.zone_role_filter,
            c.age_filter, c.test_count_filter, c.min_bias_strength,
            c.max_replacement_count, c.direction, c.session_filter,
            c.cascade_filter, c.cascade_lookback, c.cascade_direction,
            c.entry_mode, c.sl_mode, c.tp_mode, c.fixed_rr, c.sl_atr_mult,
            c.tp_htf,
            c.partial_tp, c.partial_unit1_pct, c.partial_unit1_rr, c.partial_unit2_tp,
            c.touch_policy, c.max_concurrent,
            c.birth_pattern_filter, c.retest_number_filter,
            c.time_since_creation_filter, c.parent_tf_boundary_filter,
            c.inside_w_zone_filter, c.d_to_w_filter,
            c.near_pdh_pdl, c.premium_discount,
            c.layered_sl_mode,
            c.hma_filter, c.hma_cross_trigger, str(c.hma_cross_lookback),
            c.hma_period, c.hma_source,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    # Entry pairs and their valid HTF TP targets
    # (only target TFs that are HIGHER than the context TF)
    pair_targets = {
        "M5@M15": ["H1", "H4", "D1"],
        "M5@H1":  ["H4", "D1"],
        "M15@H1": ["H4", "D1"],
        "M15@H4": ["D1"],
        "H1@H4":  ["D1"],
    }

    for pair, targets in pair_targets.items():
        for tp_htf in targets:
            # Baseline: limit + htf_zone TP
            _add(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                tp_mode="htf_zone", tp_htf=tp_htf))

            # With daily bias
            _add(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                tp_mode="htf_zone", tp_htf=tp_htf, bias_filter="with_daily"))

            # Against daily bias
            _add(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                tp_mode="htf_zone", tp_htf=tp_htf, bias_filter="against_daily"))

            # With retest 4-10 filter (the quality sweet spot)
            _add(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                tp_mode="htf_zone", tp_htf=tp_htf, retest_number_filter="4-10"))

    # Also include the existing best limit configs with fixed R:R for comparison
    best_pairs = ["M5@M15", "M15@H1", "H1@H4"]
    for pair in best_pairs:
        for rr in [2.0, 3.0, 4.0, 6.0, 8.0, 10.0]:
            _add(RetestConfig(
                tf_pair=pair, entry_mode="limit", sl_mode="zone",
                tp_mode="fixed_rr", fixed_rr=rr))

    return configs


def partial_tp_configs() -> list[RetestConfig]:
    """Focused sweep: partial TP (scalp lock + HTF runner) on same entry.

    Combines Profile A (fixed R:R scalp) with Profile B (cross-TF swing)
    using 2-unit partial exits. Estimated ~60-80 configs.
    """
    configs: list[RetestConfig] = []
    seen: set[str] = set()

    def _add(c: RetestConfig) -> None:
        key = (
            c.tf_pair, c.touch_type, c.bias_filter, c.zone_role_filter,
            c.age_filter, c.test_count_filter, c.min_bias_strength,
            c.max_replacement_count, c.direction, c.session_filter,
            c.cascade_filter, c.cascade_lookback, c.cascade_direction,
            c.entry_mode, c.sl_mode, c.tp_mode, c.fixed_rr, c.sl_atr_mult,
            c.tp_htf,
            c.partial_tp, c.partial_unit1_pct, c.partial_unit1_rr, c.partial_unit2_tp,
            c.touch_policy, c.max_concurrent,
            c.birth_pattern_filter, c.retest_number_filter,
            c.time_since_creation_filter, c.parent_tf_boundary_filter,
            c.inside_w_zone_filter, c.d_to_w_filter,
            c.near_pdh_pdl, c.premium_discount,
            c.layered_sl_mode,
            c.hma_filter, c.hma_cross_trigger, str(c.hma_cross_lookback),
            c.hma_period, c.hma_source,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    partial_htf_targets = {
        "M5@M15": ["H1", "H4"],
        "M5@H1":  ["H4", "D1"],
        "M15@H1": ["H4", "D1"],
        "H1@H4":  ["D1"],
    }

    for pair, targets in partial_htf_targets.items():
        for htf in targets:
            # 50/50 split, Unit 1 at rr=3.0
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 partial_tp=True, partial_unit1_rr=3.0, partial_unit2_tp=htf))
            # 70/30 split
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 partial_tp=True, partial_unit1_pct=0.7,
                 partial_unit1_rr=3.0, partial_unit2_tp=htf))
            # Unit 1 at rr=2.0
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 partial_tp=True, partial_unit1_rr=2.0, partial_unit2_tp=htf))
            # Bias filters
            for bias in ["against_daily", "with_daily"]:
                _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                     partial_tp=True, partial_unit1_rr=3.0,
                     partial_unit2_tp=htf, bias_filter=bias))
            # Retest 4-10
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 partial_tp=True, partial_unit1_rr=3.0,
                 partial_unit2_tp=htf, retest_number_filter="4-10"))

    # Comparison: best pure fixed_rr and pure htf_zone configs
    best_pairs = ["M5@M15", "M15@H1", "H1@H4"]
    for pair in best_pairs:
        # Pure scalp baselines
        for rr in [2.0, 3.0, 4.0]:
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 tp_mode="fixed_rr", fixed_rr=rr))
    # Pure cross-TF baselines
    for pair, targets in partial_htf_targets.items():
        for htf in targets:
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 tp_mode="htf_zone", tp_htf=htf))

    return configs


def htf_triggered_ltf_configs(symbol: str = "GBPUSD") -> list[RetestConfig]:
    """Sweep configs for HTF-triggered LTF entry system.

    Tests M15 and M5 zones nested inside H4 zones, triggered by H1@H4 retest.
    Also includes standalone LTF pairs (M5@M15, M1@M5, M1@M15) with full feature set.
    Spread values are symbol-aware via get_typical_spread_pips().
    """
    from iora.strategy.trade_converter import get_typical_spread_pips

    configs: list[RetestConfig] = []
    seen: set = set()

    def _add(c: RetestConfig) -> None:
        key = (
            c.tf_pair, c.ltf_nesting, c.entry_tf_override,
            c.trigger_window_bars, c.require_ltf_push,
            c.trigger_also_trades, c.max_ltf_per_trigger,
            c.spread_pips, c.partial_tp, c.partial_unit1_pct,
            c.partial_unit1_rr, c.partial_unit2_tp,
            c.bias_filter, c.min_sl_pips, c.min_sl_spread_mult,
            c.limit_ttl, c.limit_edge, c.entry_mode,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    typical_spread = get_typical_spread_pips(symbol)
    spread_values = sorted({0.0, typical_spread, typical_spread * 1.5, typical_spread * 2.0})
    sl_mult_values = [0, 2, 3, 5]

    # Common base kwargs
    base = dict(
        tf_pair="H1@H4",
        entry_mode="limit",
        limit_edge="top",
        limit_ttl=0,
        sl_mode="zone",
    )

    partial_kw = dict(
        partial_tp=True,
        partial_unit1_pct=0.7,
        partial_unit1_rr=3.0,
        partial_unit2_tp="H1",
    )

    # --- Baselines (H1@H4 direct, no nesting) ---
    for sp in spread_values:
        _add(RetestConfig(**base, spread_pips=sp))
        _add(RetestConfig(**base, spread_pips=sp, **partial_kw))

    # --- Static nesting ---
    for ltf in ["M15", "M5"]:
        for spread in spread_values:
            for sl_mult in sl_mult_values:
                for push in [False, True]:
                    _add(RetestConfig(**base,
                        ltf_nesting="static",
                        entry_tf_override=ltf,
                        spread_pips=spread,
                        min_sl_spread_mult=sl_mult,
                        require_ltf_push=push,
                        fixed_rr=3.0,
                    ))
                    _add(RetestConfig(**base,
                        ltf_nesting="static",
                        entry_tf_override=ltf,
                        spread_pips=spread,
                        min_sl_spread_mult=sl_mult,
                        require_ltf_push=push,
                        **partial_kw,
                    ))

    # --- Dynamic nesting ---
    for ltf in ["M15", "M5"]:
        for spread in spread_values:
            for sl_mult in sl_mult_values:
                for push in [False, True]:
                    for window in [24, 48]:
                        _add(RetestConfig(**base,
                            ltf_nesting="dynamic",
                            entry_tf_override=ltf,
                            trigger_window_bars=window,
                            spread_pips=spread,
                            min_sl_spread_mult=sl_mult,
                            require_ltf_push=push,
                            fixed_rr=3.0,
                        ))
                        _add(RetestConfig(**base,
                            ltf_nesting="dynamic",
                            entry_tf_override=ltf,
                            trigger_window_bars=window,
                            spread_pips=spread,
                            min_sl_spread_mult=sl_mult,
                            require_ltf_push=push,
                            **partial_kw,
                        ))

    # --- Standalone LTF pairs (NEVER TESTED with full feature set) ---
    for pair, tp_htf in [
        ("M5@M15", "H1"),
        ("M1@M5", "M15"),
        ("M1@M15", "H1"),
    ]:
        ltf_base = dict(
            tf_pair=pair,
            entry_mode="limit",
            limit_edge="top",
            limit_ttl=0,
            sl_mode="zone",
        )
        ltf_partial = dict(
            partial_tp=True,
            partial_unit1_pct=0.7,
            partial_unit1_rr=3.0,
            partial_unit2_tp=tp_htf,
        )
        for spread in spread_values:
            for sl_mult in sl_mult_values:
                _add(RetestConfig(**ltf_base,
                    spread_pips=spread,
                    min_sl_spread_mult=sl_mult,
                    fixed_rr=3.0,
                ))
                _add(RetestConfig(**ltf_base,
                    spread_pips=spread,
                    min_sl_spread_mult=sl_mult,
                    **ltf_partial,
                ))

    return configs


def _build_for_tf(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tf: str,
    symbol: str,
) -> tuple[str, list[RetestCandidate]]:
    """Worker function for parallel candidate building."""
    candidates = build_retest_candidates(
        data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
    )
    return entry_tf, candidates


def run_retest_sweep(
    data_by_tf: dict[str, pd.DataFrame],
    entry_tfs: list[str],
    symbol: str,
    configs: list[RetestConfig] | None = None,
    parallel: bool = True,
) -> SweepSummary:
    """Run full retest sweep for one symbol.

    Args:
        parallel: If True, build candidates for each entry TF in parallel
                  using ProcessPoolExecutor (falls back to ThreadPoolExecutor).
    """
    if configs is None:
        configs = default_configs()

    all_candidates: list[RetestCandidate] = []
    bar_data_by_entry_tf: dict[str, pd.DataFrame] = {}

    valid_tfs = [tf for tf in entry_tfs if tf in data_by_tf]

    # Check if any config needs dynamic nesting or signal-flip (zone birth collection)
    needs_signal_flip = any(c.exit_mode in ("signal_flip", "signal_flip_with_safety") for c in configs)
    needs_births = any(c.ltf_nesting == "dynamic" for c in configs) or needs_signal_flip
    birth_tfs_set: set[str] = set()
    for c in configs:
        if c.ltf_nesting == "dynamic" and c.entry_tf_override:
            birth_tfs_set.add(c.entry_tf_override)
        if c.exit_mode in ("signal_flip", "signal_flip_with_safety"):
            birth_tfs_set.add(c.entry_tf)  # Need births on the entry TF for flip detection
    birth_tfs = list(birth_tfs_set)

    # Check if any config needs static nesting (LTF zone enrichment)
    needs_static = any(c.ltf_nesting == "static" for c in configs)
    static_ltf_tfs = list({c.entry_tf_override for c in configs
                           if c.ltf_nesting == "static" and c.entry_tf_override})
    any_require_push = any(c.require_ltf_push for c in configs
                           if c.ltf_nesting == "static")

    zone_births_by_tf: dict[str, dict] = {}
    cascade_timeline_by_tf: dict[str, dict] = {}
    # Only collect cascade_timeline for entry TFs that have windowed configs
    windowed_entry_tfs = {c.entry_tf for c in configs if c.flip_window == "windowed"}

    if needs_births or needs_static:
        # Use build_retest_candidates_with_births for advanced candidate building
        for entry_tf in valid_tfs:
            need_tl_for_tf = entry_tf in windowed_entry_tfs
            result = build_retest_candidates_with_births(
                data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
                ltf_tf="",  # Auto-populate: collect ALL available LTF zones (M15, M5, M1)
                require_ltf_push=False,  # Don't filter at build time — filter at eval time
                birth_tfs=birth_tfs if needs_births else None,
                collect_cascade_timeline=need_tl_for_tf,
            )
            all_candidates.extend(result.candidates)
            zone_births_by_tf[entry_tf] = result.zone_births
            cascade_timeline_by_tf[entry_tf] = result.cascade_timeline
            bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]
    elif parallel and len(valid_tfs) > 1:
        # Try ProcessPoolExecutor first, fall back to ThreadPoolExecutor
        Executor = ProcessPoolExecutor
        try:
            with Executor(max_workers=min(len(valid_tfs), 4)) as pool:
                futures = {
                    pool.submit(_build_for_tf, data_by_tf, tf, symbol): tf
                    for tf in valid_tfs
                }
                for future in as_completed(futures):
                    entry_tf, candidates = future.result()
                    all_candidates.extend(candidates)
                    bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]
        except (TypeError, AttributeError):
            # Pickle serialization failure — fall back to ThreadPoolExecutor
            all_candidates.clear()
            bar_data_by_entry_tf.clear()
            with ThreadPoolExecutor(max_workers=min(len(valid_tfs), 4)) as pool:
                futures = {
                    pool.submit(_build_for_tf, data_by_tf, tf, symbol): tf
                    for tf in valid_tfs
                }
                for future in as_completed(futures):
                    entry_tf, candidates = future.result()
                    all_candidates.extend(candidates)
                    bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]
    else:
        for entry_tf in valid_tfs:
            candidates = build_retest_candidates(
                data_by_tf=data_by_tf, entry_tf=entry_tf, symbol=symbol,
            )
            all_candidates.extend(candidates)
            bar_data_by_entry_tf[entry_tf] = data_by_tf[entry_tf]

    results: list[RetestResult] = []
    for cfg in configs:
        bar_data = bar_data_by_entry_tf.get(cfg.entry_tf)
        # Resolve HA trail TF data if needed
        trail_tf_data = None
        if cfg.unit2_trail != "none":
            trail_tf = cfg.unit2_trail.replace("ha_", "").upper()
            trail_tf_data = data_by_tf.get(trail_tf)
        # Pass zone_births for dynamic nesting or signal-flip configs
        needs_zb = (
            cfg.ltf_nesting == "dynamic"
            or cfg.exit_mode in ("signal_flip", "signal_flip_with_safety")
        )
        zb = zone_births_by_tf.get(cfg.entry_tf, {}) if needs_zb else None
        ct = cascade_timeline_by_tf.get(cfg.entry_tf, {}) if cfg.flip_window == "windowed" else None
        result = evaluate_retest_config(
            candidates=all_candidates, config=cfg, symbol=symbol,
            bar_data=bar_data, all_candidates=all_candidates,
            trail_tf_data=trail_tf_data,
            zone_births=zb,
            cascade_timeline=ct,
        )
        results.append(result)

    return SweepSummary(results=results, symbol=symbol)


def cascade_sweep_configs(symbol: str = "UNKNOWN") -> list[RetestConfig]:
    """Generate cascade-specific sweep configs.

    Base: H1@H4 limit, partial TP, TTL=0, symbol-specific spread.
    Cross with cascade_phase_filter, tl_break_filter, h1_zone_count_filter,
    ew_overlap_filter, ew_extension_filter, bias_filter, test_count_filter.

    Target: ~200-400 configs per symbol.
    """
    from iora.strategy.trade_converter import _get_pip_size

    configs: list[RetestConfig] = []
    seen: set[tuple] = set()

    # Symbol-specific spread (approximate)
    pip_size = _get_pip_size(symbol)
    spread_pips = 1.5  # Default FX
    if symbol in ("XAUUSD",):
        spread_pips = 3.0
    elif symbol in ("US30", "US500", "JP225", "HK50", "UK100", "F40"):
        spread_pips = 5.0

    def _base(**kw) -> RetestConfig:
        return RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            partial_tp=True,
            partial_unit1_pct=0.5,
            partial_unit1_rr=3.0,
            partial_unit2_tp="H1",
            limit_ttl=0,
            spread_pips=spread_pips,
            min_sl_spread_mult=3.0,
            sl_buffer_atr=0.15,
            **kw,
        )

    def _add(c: RetestConfig) -> None:
        key = (
            c.tf_pair, c.entry_mode, c.bias_filter,
            c.cascade_phase_filter, c.tl_break_filter, c.tl_break_lookback,
            c.h1_zone_count_filter, c.reversal_target_entry,
            c.ew_overlap_filter, c.ew_extension_filter,
            c.test_count_filter, c.fixed_rr, c.partial_tp,
            c.direction, c.zone_role_filter,
            c.choch_conviction_filter, c.min_consumption_count,
            c.require_fvg_at_entry, c.min_pivot_cascade_depth,
            c.require_breaker_zone, c.structural_fvg_filter,
        )
        if key not in seen:
            seen.add(key)
            configs.append(c)

    # ── Section A: Baselines ─────────────────────────────────────────────
    _add(_base())
    _add(_base(bias_filter="with_daily"))
    _add(_base(bias_filter="against_daily"))

    # ── Section B: Cascade phase filter ──────────────────────────────────
    for phase in ["d1_push", "h4_correction", "h4_correction_tl_break",
                   "h1_extended", "h1_terminal", "at_reversal_target"]:
        _add(_base(cascade_phase_filter=phase))
        _add(_base(cascade_phase_filter=phase, bias_filter="with_daily"))
        _add(_base(cascade_phase_filter=phase, bias_filter="against_daily"))

    # ── Section C: TL break filter ───────────────────────────────────────
    for tl in ["after_impulse_break", "after_correction_break"]:
        # Sticky (lookback=0: any time since last D1 trend change)
        _add(_base(tl_break_filter=tl))
        _add(_base(tl_break_filter=tl, bias_filter="with_daily"))
        _add(_base(tl_break_filter=tl, bias_filter="against_daily"))
        # Recency lookbacks (in M5 bars)
        for lb in [10, 20, 50]:
            _add(_base(tl_break_filter=tl, tl_break_lookback=lb))
            _add(_base(tl_break_filter=tl, tl_break_lookback=lb, bias_filter="against_daily"))

    # ── Section D: H1 zone count filter ──────────────────────────────────
    for zc in ["1-3", "4-7", "8+"]:
        _add(_base(h1_zone_count_filter=zc))
        _add(_base(h1_zone_count_filter=zc, bias_filter="with_daily"))
        _add(_base(h1_zone_count_filter=zc, bias_filter="against_daily"))

    # ── Section E: Reversal target entry ─────────────────────────────────
    _add(_base(reversal_target_entry=True))
    _add(_base(reversal_target_entry=True, bias_filter="with_daily"))
    _add(_base(reversal_target_entry=True, bias_filter="against_daily"))

    # ── Section F: EW overlap filter ─────────────────────────────────────
    for ov in ["no_overlap", "overlap_only"]:
        _add(_base(ew_overlap_filter=ov))
        _add(_base(ew_overlap_filter=ov, h1_zone_count_filter="4-7"))
        _add(_base(ew_overlap_filter=ov, h1_zone_count_filter="8+"))

    # ── Section G: EW extension filter ───────────────────────────────────
    for ext in ["extended", "not_extended"]:
        _add(_base(ew_extension_filter=ext))
        _add(_base(ew_extension_filter=ext, bias_filter="with_daily"))
        _add(_base(ew_extension_filter=ext, bias_filter="against_daily"))

    # ── Section H: Retest count combinations ─────────────────────────────
    for tc in ["retested_1", "retested_2plus"]:
        _add(_base(test_count_filter=tc))
        _add(_base(test_count_filter=tc, cascade_phase_filter="h1_extended"))
        _add(_base(test_count_filter=tc, cascade_phase_filter="h1_terminal"))

    # ── Section I: High-conviction combos ────────────────────────────────
    # Terminal + reversal target + against_daily
    _add(_base(cascade_phase_filter="h1_terminal", reversal_target_entry=True,
               bias_filter="against_daily"))
    # Extended + overlap + against_daily
    _add(_base(cascade_phase_filter="h1_extended", ew_overlap_filter="overlap_only",
               bias_filter="against_daily"))
    # Correction TL break + with_daily (continuation)
    _add(_base(tl_break_filter="after_correction_break", bias_filter="with_daily",
               cascade_phase_filter="h4_correction_tl_break"))
    # Terminal + not_extended + against_daily (safe reversal)
    _add(_base(cascade_phase_filter="h1_terminal", ew_extension_filter="not_extended",
               bias_filter="against_daily"))
    # D1 push + 1-3 zones + with_daily (early push continuation)
    _add(_base(cascade_phase_filter="d1_push", h1_zone_count_filter="1-3",
               bias_filter="with_daily"))

    # ── Section J: Direction filters ─────────────────────────────────────
    for direction in ["long", "short"]:
        _add(_base(direction=direction))
        _add(_base(direction=direction, cascade_phase_filter="h1_terminal"))
        _add(_base(direction=direction, cascade_phase_filter="h1_extended"))

    # ── Section K: RR variants ───────────────────────────────────────────
    for rr in [2.0, 4.0, 5.0]:
        _add(RetestConfig(
            tf_pair="H1@H4", entry_mode="limit",
            partial_tp=True, partial_unit1_pct=0.5,
            partial_unit1_rr=rr, partial_unit2_tp="H1",
            limit_ttl=0, spread_pips=spread_pips,
            min_sl_spread_mult=3.0, sl_buffer_atr=0.15,
        ))

    # ── Section L: Zone role within cascade phases ───────────────────────
    for role in ["push", "reversal", "continuation"]:
        _add(_base(zone_role_filter=role))
        _add(_base(zone_role_filter=role, cascade_phase_filter="h1_extended"))

    # ── Section M: CHoCH conviction filter ──────────────────────────────
    for conv in ["strong_only", "weak_only"]:
        _add(_base(choch_conviction_filter=conv))
        _add(_base(choch_conviction_filter=conv, bias_filter="with_daily"))
        _add(_base(choch_conviction_filter=conv, bias_filter="against_daily"))
    # High-conviction combo: strong CHoCH + terminal phase
    _add(_base(choch_conviction_filter="strong_only",
               cascade_phase_filter="h1_terminal"))
    _add(_base(choch_conviction_filter="strong_only",
               cascade_phase_filter="h1_terminal", bias_filter="against_daily"))
    # Strong CHoCH + extended
    _add(_base(choch_conviction_filter="strong_only",
               cascade_phase_filter="h1_extended"))

    # ── Section N: Momentum consumption count ───────────────────────────
    for mc in [1, 2, 3]:
        _add(_base(min_consumption_count=mc))
        _add(_base(min_consumption_count=mc, bias_filter="with_daily"))
        _add(_base(min_consumption_count=mc, bias_filter="against_daily"))
    # Consumption + CHoCH conviction combos
    _add(_base(min_consumption_count=2, choch_conviction_filter="strong_only"))
    _add(_base(min_consumption_count=3, choch_conviction_filter="strong_only"))
    _add(_base(min_consumption_count=2, choch_conviction_filter="strong_only",
               bias_filter="against_daily"))

    # ── Section O: FVG at entry ──────────────────────────────────────────
    _add(_base(require_fvg_at_entry=True))
    _add(_base(require_fvg_at_entry=True, bias_filter="against_daily"))
    _add(_base(require_fvg_at_entry=True, cascade_phase_filter="h1_extended"))
    _add(_base(require_fvg_at_entry=True, cascade_phase_filter="h1_terminal"))

    # ── Section P: Pivot cascade depth ───────────────────────────────────
    for depth in [2, 3, 4]:
        _add(_base(min_pivot_cascade_depth=depth))
        _add(_base(min_pivot_cascade_depth=depth, bias_filter="against_daily"))

    # ── Section Q: Breaker zone at entry ─────────────────────────────────
    _add(_base(require_breaker_zone=True))
    _add(_base(require_breaker_zone=True, bias_filter="against_daily"))
    _add(_base(require_breaker_zone=True, cascade_phase_filter="h1_extended"))

    # ── Section R1: Structural FVG filter ────────────────────────────────
    for sfvg in ["inside_gap", "at_gap_boundary"]:
        _add(_base(structural_fvg_filter=sfvg))
        _add(_base(structural_fvg_filter=sfvg, bias_filter="against_daily"))
    _add(_base(structural_fvg_filter="inside_gap", cascade_phase_filter="h1_extended"))
    _add(_base(structural_fvg_filter="at_gap_boundary", cascade_phase_filter="h1_terminal"))

    # ── Section R2: High-conviction combos with Phase 3 filters ──────────
    _add(_base(require_fvg_at_entry=True, min_pivot_cascade_depth=3))
    _add(_base(require_fvg_at_entry=True, require_breaker_zone=True))
    _add(_base(min_pivot_cascade_depth=3, choch_conviction_filter="strong_only"))
    _add(_base(require_fvg_at_entry=True, cascade_phase_filter="h1_terminal",
               bias_filter="against_daily"))
    _add(_base(min_pivot_cascade_depth=4, cascade_phase_filter="h1_extended",
               bias_filter="against_daily"))

    # ── Section S: M1@M5 with cascade context ────────────────────────────
    # M1@M5 uses the full cascade filtering to test if precision improves
    m1_spread = 1.5 if "USD" in symbol else 3.0
    def _m1_base(**kw):
        return RetestConfig(
            tf_pair="M1@M5",
            entry_mode="limit",
            partial_tp=True,
            partial_unit1_pct=0.5,
            partial_unit1_rr=3.0,
            partial_unit2_tp="M15",
            limit_ttl=0,
            spread_pips=m1_spread,
            min_sl_spread_mult=3.0,
            sl_buffer_atr=0.15,
            **kw,
        )
    _add(_m1_base())
    _add(_m1_base(bias_filter="against_daily"))
    _add(_m1_base(cascade_phase_filter="h1_extended"))
    _add(_m1_base(cascade_phase_filter="h1_terminal"))
    _add(_m1_base(require_fvg_at_entry=True))
    _add(_m1_base(min_pivot_cascade_depth=3))

    return configs
