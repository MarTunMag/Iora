# src/iora/strategy/filter_funnel.py
"""Filter funnel — ordered filter pipeline with per-step attribution.

Applies RetestConfig filters to candidates in a fixed order.
Tracks how many candidates each filter removes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan

import pandas as pd

from iora.constants import TF_SECONDS
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig, SESSION_WINDOWS


@dataclass(slots=True)
class FunnelStep:
    """One step in the filter pipeline."""
    name: str
    input_count: int
    output_count: int

    @property
    def removed(self) -> int:
        return self.input_count - self.output_count


@dataclass(slots=True)
class FilterFunnel:
    """Result of applying all filters."""
    steps: list[FunnelStep] = field(default_factory=list)
    passed: list[RetestCandidate] = field(default_factory=list)
    total_input: int = 0

    @property
    def total_removed(self) -> int:
        return self.total_input - len(self.passed)


# Filter order — each filter is (name, predicate_factory)
# Predicate returns True to KEEP the candidate

def _make_touch_filter(cfg: RetestConfig):
    if cfg.touch_type == "any":
        return None
    val = cfg.touch_type
    return lambda c: c.event.touch_type == val


def _make_direction_filter(cfg: RetestConfig):
    if cfg.direction == "both":
        return None
    val = cfg.direction
    return lambda c: c.direction == val


def _make_bias_filter(cfg: RetestConfig):
    if cfg.bias_filter == "any":
        return None
    val = cfg.bias_filter
    return lambda c: c.event.bias_alignment == val


def _make_bias_strength_filter(cfg: RetestConfig):
    if cfg.min_bias_strength <= 0:
        return None
    min_s = cfg.min_bias_strength
    return lambda c: c.event.bias_strength >= min_s


def _make_zone_role_filter(cfg: RetestConfig):
    if cfg.zone_role_filter == "any":
        return None
    val = cfg.zone_role_filter
    return lambda c: c.event.zone_role == val


def _make_age_filter(cfg: RetestConfig):
    if cfg.age_filter == "any":
        return None
    if cfg.age_filter == "fresh_young":
        return lambda c: c.event.age_bucket in ("fresh", "young")
    val = cfg.age_filter
    return lambda c: c.event.age_bucket == val


def _make_test_count_filter(cfg: RetestConfig):
    if cfg.test_count_filter == "any":
        return None
    val = cfg.test_count_filter
    return lambda c: c.event.test_count_cls == val


def _make_replacement_filter(cfg: RetestConfig):
    if cfg.max_replacement_count >= 999:
        return None
    mx = cfg.max_replacement_count
    return lambda c: c.event.replacement_count <= mx


def _make_birth_pattern_filter(cfg: RetestConfig):
    if cfg.birth_pattern_filter == "any":
        return None
    val = cfg.birth_pattern_filter
    if val == "compression":
        return lambda c: c.event.birth_period_pattern == "LH_HL"
    if val == "trending":
        return lambda c: c.event.birth_period_pattern in ("HH_HL", "LH_LL")
    if val == "expansion":
        return lambda c: c.event.birth_period_pattern == "HH_LL"
    return None


def _make_retest_number_filter(cfg: RetestConfig):
    if cfg.retest_number_filter == "any":
        return None
    val = cfg.retest_number_filter
    if val == "1-3":
        return lambda c: 1 <= c.event.zone_test_count <= 3
    if val == "4-10":
        return lambda c: 4 <= c.event.zone_test_count <= 10
    if val == "10+":
        return lambda c: c.event.zone_test_count >= 10
    return None


def _make_time_since_creation_filter(cfg: RetestConfig):
    if cfg.time_since_creation_filter == "any":
        return None
    val = cfg.time_since_creation_filter
    # zone_age_bars is in context-TF bars; convert to approximate hours
    # using the entry_tf context is tricky here — use raw age_bars * tf_seconds
    # Instead, use the OpportunityEvent's zone_age_bars and zone_tf to compute hours
    if val == "0-3h":
        return lambda c: _age_hours(c) <= 3
    if val == "3-12h":
        return lambda c: 3 < _age_hours(c) <= 12
    if val == "12h-3d":
        return lambda c: 12 < _age_hours(c) <= 72
    if val == "3d+":
        return lambda c: _age_hours(c) > 72
    return None


def _age_hours(c: RetestCandidate) -> float:
    """Compute zone age in hours from zone_age_bars and zone_tf."""
    tf_secs = TF_SECONDS.get(c.event.zone_tf, 3600)
    return c.event.zone_age_bars * tf_secs / 3600.0


def _make_parent_tf_boundary_filter(cfg: RetestConfig):
    if cfg.parent_tf_boundary_filter == "any":
        return None
    val = cfg.parent_tf_boundary_filter
    # zone_tf → parent TF → parent TF seconds
    # Zone age in parent-TF bars = zone_age_hours / (parent_TF_seconds / 3600)
    _PARENT_TF: dict[str, str] = {
        "M5": "M15", "M15": "H1", "H1": "H4", "H4": "D1", "D1": "W1",
    }
    if val == "0-1_parent_bars":
        return lambda c: _parent_bars(c, _PARENT_TF) <= 1
    if val == "1-2_parent_bars":
        return lambda c: 1 < _parent_bars(c, _PARENT_TF) <= 2
    if val == "2-4_parent_bars":
        return lambda c: 2 < _parent_bars(c, _PARENT_TF) <= 4
    if val == "4+_parent_bars":
        return lambda c: _parent_bars(c, _PARENT_TF) > 4
    return None


def _parent_bars(c: RetestCandidate, parent_map: dict[str, str]) -> float:
    """Zone age measured in parent-TF bars."""
    zone_tf = c.event.zone_tf
    parent_tf = parent_map.get(zone_tf, zone_tf)
    parent_secs = TF_SECONDS.get(parent_tf, 3600)
    zone_tf_secs = TF_SECONDS.get(zone_tf, 3600)
    age_secs = c.event.zone_age_bars * zone_tf_secs
    return age_secs / parent_secs if parent_secs > 0 else 0.0


def _make_inside_w_zone_filter(cfg: RetestConfig):
    if cfg.inside_w_zone_filter == "any":
        return None
    if cfg.inside_w_zone_filter == "inside":
        return lambda c: c.inside_w_zone
    if cfg.inside_w_zone_filter == "outside":
        return lambda c: not c.inside_w_zone
    return None


def _make_d_to_w_filter(cfg: RetestConfig):
    if cfg.d_to_w_filter == "any":
        return None
    val = cfg.d_to_w_filter
    return lambda c: c.d_to_w_relationship == val


def _make_session_filter(cfg: RetestConfig):
    if cfg.session_filter == "any":
        return None
    if cfg.session_filter == "no_asian":
        start, end = SESSION_WINDOWS["asian"]
        # Asian wraps midnight: 23:00-07:00 — exclude this range
        return lambda c: not _in_session(c.event.timestamp.hour, start, end)
    if cfg.session_filter in SESSION_WINDOWS:
        start, end = SESSION_WINDOWS[cfg.session_filter]
        return lambda c: _in_session(c.event.timestamp.hour, start, end)
    return None


def _in_session(hour: int, start: int, end: int) -> bool:
    """Check if hour is within session window (handles midnight wrap)."""
    if start < end:
        return start <= hour < end
    # Wraps midnight (e.g., 23:00-07:00)
    return hour >= start or hour < end


def _make_near_pdh_pdl_filter(cfg: RetestConfig):
    if cfg.near_pdh_pdl == "any":
        return None

    def filt(c: RetestCandidate) -> bool:
        if c.atr <= 0:
            return True
        dist_hi = abs(c.entry_price - c.period_hi) / c.atr
        dist_lo = abs(c.entry_price - c.period_lo) / c.atr
        return dist_hi < 0.5 or dist_lo < 0.5

    return filt


def _make_premium_discount_filter(cfg: RetestConfig):
    if cfg.premium_discount == "any":
        return None

    def filt(c: RetestCandidate) -> bool:
        if isnan(c.d1_range_midpoint):
            return True
        if c.direction == "long":
            return c.entry_price < c.d1_range_midpoint
        return c.entry_price > c.d1_range_midpoint

    return filt


def _make_hma_filter(cfg: RetestConfig):
    if cfg.hma_filter == "any":
        return None
    ref_tf = "h1" if "h1" in cfg.hma_filter else "h4"

    def fn(c: RetestCandidate) -> bool:
        hma_dir = c.hma_direction_h1 if ref_tf == "h1" else c.hma_direction_h4
        if c.direction == "long":
            return hma_dir == 1
        return hma_dir == -1

    return fn


def _make_hma_cross_trigger(cfg: RetestConfig):
    if cfg.hma_cross_trigger == "none":
        return None
    ref_tf = cfg.hma_cross_trigger  # "h1" or "h4"
    lookback = cfg.hma_cross_lookback

    def fn(c: RetestCandidate) -> bool:
        if ref_tf == "h1":
            cross_dir = c.hma_cross_direction_h1
            bars_since = c.bars_since_hma_cross_h1
            ha_above = c.ha_above_hma_h1
        else:
            cross_dir = c.hma_cross_direction_h4
            bars_since = c.bars_since_hma_cross_h4
            ha_above = c.ha_above_hma_h4

        # Direction must match
        if c.direction == "long" and cross_dir != 1:
            return False
        if c.direction == "short" and cross_dir != -1:
            return False

        # Lookback window check
        if lookback == "until_reverse":
            # Active as long as HA is still on the cross side
            if c.direction == "long":
                return ha_above
            return not ha_above
        else:
            return bars_since <= int(lookback)

    return fn


_FILTER_FACTORIES = [
    ("touch_type", _make_touch_filter),
    ("direction", _make_direction_filter),
    ("bias_filter", _make_bias_filter),
    ("bias_strength", _make_bias_strength_filter),
    ("zone_role", _make_zone_role_filter),
    ("age_filter", _make_age_filter),
    ("test_count", _make_test_count_filter),
    ("replacement_count", _make_replacement_filter),
    ("birth_pattern", _make_birth_pattern_filter),
    ("retest_number", _make_retest_number_filter),
    ("time_since_creation", _make_time_since_creation_filter),
    ("parent_tf_boundary", _make_parent_tf_boundary_filter),
    ("inside_w_zone", _make_inside_w_zone_filter),
    ("d_to_w", _make_d_to_w_filter),
    ("session", _make_session_filter),
    ("near_pdh_pdl", _make_near_pdh_pdl_filter),
    ("premium_discount", _make_premium_discount_filter),
    ("hma_filter", _make_hma_filter),
    ("hma_cross_trigger", _make_hma_cross_trigger),
]


def apply_filters(
    candidates: list[RetestCandidate],
    cfg: RetestConfig,
) -> FilterFunnel:
    """Apply all config filters in order, tracking attribution."""
    funnel = FilterFunnel(total_input=len(candidates))
    current = list(candidates)

    for name, factory in _FILTER_FACTORIES:
        pred = factory(cfg)
        input_count = len(current)
        if pred is not None:
            current = [c for c in current if pred(c)]
        funnel.steps.append(FunnelStep(
            name=name,
            input_count=input_count,
            output_count=len(current),
        ))

    funnel.passed = current
    return funnel


def apply_filters_with_cascade(
    candidates: list[RetestCandidate],
    cfg: RetestConfig,
    all_candidates: list[RetestCandidate] | None = None,
) -> FilterFunnel:
    """Apply standard filters + cascade filter."""
    # Standard filters first
    funnel = apply_filters(candidates, cfg)

    if cfg.cascade_filter == "none" or all_candidates is None:
        return funnel

    # Build HTF event index
    htf_pairs = set(cfg.htf_pairs)

    if cfg.cascade_filter == "require_inside_htf_zone":
        # Special cascade: price must currently be inside an HTF zone
        # (body_close event at same timestamp in an HTF pair)
        htf_body_close_ts: set[tuple[pd.Timestamp, str]] = set()
        for h in all_candidates:
            if h.event.tf_pair in htf_pairs and h.event.touch_type == "body_close":
                htf_body_close_ts.add((h.event.timestamp, h.direction))

        input_count = len(funnel.passed)
        passed = []
        for c in funnel.passed:
            ts = c.event.timestamp
            if cfg.cascade_direction == "same":
                if (ts, c.direction) in htf_body_close_ts:
                    passed.append(c)
            else:
                # Any direction — check both
                if ((ts, "long") in htf_body_close_ts
                        or (ts, "short") in htf_body_close_ts):
                    passed.append(c)

        funnel.steps.append(FunnelStep(
            name="cascade",
            input_count=input_count,
            output_count=len(passed),
        ))
        funnel.passed = passed
        return funnel

    htf_events = sorted(
        [c for c in all_candidates
         if c.event.tf_pair in htf_pairs
         and c.event.touch_type in ("wick_touch", "body_close")],
        key=lambda c: c.event.timestamp,
    )

    # Lookback window in seconds
    entry_tf_seconds = TF_SECONDS.get(cfg.entry_tf, 300)
    lookback_seconds = cfg.cascade_lookback * entry_tf_seconds

    min_htf = 2 if cfg.cascade_filter == "require_confluence_2" else 1

    input_count = len(funnel.passed)
    passed = []
    for c in funnel.passed:
        ts = c.event.timestamp
        window_start = ts - pd.Timedelta(seconds=lookback_seconds)

        htf_hit_pairs: set[str] = set()
        for h in htf_events:
            if h.event.timestamp < window_start:
                continue
            if h.event.timestamp > ts:
                break
            if cfg.cascade_direction == "same" and c.direction != h.direction:
                continue
            htf_hit_pairs.add(h.event.tf_pair)

        if len(htf_hit_pairs) >= min_htf:
            passed.append(c)

    funnel.steps.append(FunnelStep(
        name="cascade",
        input_count=input_count,
        output_count=len(passed),
    ))
    funnel.passed = passed
    return funnel
