# src/iora/strategy/filter_funnel.py
"""Filter funnel — ordered filter pipeline with per-step attribution.

Applies RetestConfig filters to candidates in a fixed order.
Tracks how many candidates each filter removes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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


_FILTER_FACTORIES = [
    ("touch_type", _make_touch_filter),
    ("direction", _make_direction_filter),
    ("bias_filter", _make_bias_filter),
    ("bias_strength", _make_bias_strength_filter),
    ("zone_role", _make_zone_role_filter),
    ("age_filter", _make_age_filter),
    ("test_count", _make_test_count_filter),
    ("replacement_count", _make_replacement_filter),
    ("session", _make_session_filter),
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
