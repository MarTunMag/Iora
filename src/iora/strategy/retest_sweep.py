"""Retest sweep runner — batch evaluation across configs.

Stage 1: Build candidates once per symbol (expensive).
Stage 2: Evaluate N configs cheaply per candidate set.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
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

    if parallel and len(valid_tfs) > 1:
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
        result = evaluate_retest_config(
            candidates=all_candidates, config=cfg, symbol=symbol,
            bar_data=bar_data, all_candidates=all_candidates,
        )
        results.append(result)

    return SweepSummary(results=results, symbol=symbol)
