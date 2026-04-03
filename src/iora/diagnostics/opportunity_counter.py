"""Opportunity Counter — Level 3 diagnostics.

Counts retest events per TF pair per filter dimension.
No strategy, no trades — purely counting opportunities.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Import bias direction sets from bias_timeline (single source of truth)
from iora.diagnostics.bias_timeline import _BULLISH_BIASES, _BEARISH_BIASES


def classify_touch(
    zone,  # PushZone
    high: float,
    low: float,
    close: float,
) -> str | None:
    """Classify a bar's interaction with a zone.

    Returns: "wick_touch", "body_close", "break_through", or None (no interaction).

    - wick_touch: price entered zone but close stayed outside
    - body_close: close is inside zone boundaries
    - break_through: price entered zone AND close went through the other side
    """
    if zone.is_supply:
        entered = high >= zone.bottom
        if not entered:
            return None
        if close > zone.top:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close < zone.bottom
    else:  # demand
        entered = low <= zone.top
        if not entered:
            return None
        if close < zone.bottom:
            return "break_through"
        if zone.bottom <= close <= zone.top:
            return "body_close"
        return "wick_touch"  # close > zone.top


def is_near_miss(
    zone,  # PushZone
    high: float,
    low: float,
    atr: float,
    pip_size: float = 0.0001,
) -> bool:
    """Check if price came close to a zone without touching it.

    Threshold: max(min(0.25 * zone_thickness, 0.5 * ATR), 1.0 * pip_size).
    The pip floor prevents sub-pip thresholds on very thin zones.
    """
    zone_thickness = zone.top - zone.bottom
    threshold = max(min(0.25 * zone_thickness, 0.5 * atr), pip_size)

    if zone.is_supply:
        if high >= zone.bottom:
            return False
        distance = zone.bottom - high
    else:  # demand
        if low <= zone.top:
            return False
        distance = low - zone.top

    return distance <= threshold


# Same-direction swing_cls pairs (continuation)
_SAME_DIR = {
    ("HH", "HH"), ("HL", "HL"), ("LL", "LL"), ("LH", "LH"),
    ("HH", "HL"), ("HL", "HH"),  # Both bullish
    ("LL", "LH"), ("LH", "LL"),  # Both bearish
}


def classify_zone_role(zone, prev_swing_cls: str) -> str:
    """Classify zone's structural role.
    Returns: "push", "reversal", "continuation", "pullback", "unknown".
    """
    if zone.is_push:
        return "push"
    if zone.is_reversal:
        return "reversal"
    if not prev_swing_cls or not zone.swing_cls:
        return "unknown"
    if (zone.swing_cls, prev_swing_cls) in _SAME_DIR:
        return "continuation"
    return "pullback"


def classify_age_bucket(age_bars: int) -> str:
    """fresh: 0-10, young: 11-50, mature: 51-200, old: 201+"""
    if age_bars <= 10:
        return "fresh"
    if age_bars <= 50:
        return "young"
    if age_bars <= 200:
        return "mature"
    return "old"


def classify_bias_alignment(is_supply: bool, d_bias: str, is_transition: bool = False) -> str:
    """with_daily, against_daily, at_transition, neutral."""
    if is_transition:
        return "at_transition"
    if d_bias in _BULLISH_BIASES:
        return "with_daily" if not is_supply else "against_daily"
    if d_bias in _BEARISH_BIASES:
        return "with_daily" if is_supply else "against_daily"
    return "neutral"


def classify_test_count(test_count: int) -> str:
    """first_touch (0), retested_1 (1), retested_2plus (2+)."""
    if test_count == 0:
        return "first_touch"
    if test_count == 1:
        return "retested_1"
    return "retested_2plus"


@dataclass(slots=True)
class OpportunityEvent:
    """A single retest/near-miss/break-through event."""
    timestamp: pd.Timestamp
    zone_tf: str
    entry_tf: str
    tf_pair: str
    touch_type: str
    zone_side: str
    zone_role: str
    age_bucket: str
    bias_alignment: str
    test_count_cls: str
    zone_age_bars: int
    zone_test_count: int
    bias_strength: int
    price_distance_at_touch: float
    replacement_count: int = 0
    birth_bias_d: str = "unknown"
    birth_period_pattern: str = "unknown"
    birth_price_distance: float = 0.0


# Valid TF pairs: entry@context (each entry TF scans these higher context TFs)
_TF_PAIRS: dict[str, list[str]] = {
    "M1": ["M5", "M15"],
    "M5": ["M15", "H1", "H4"],
    "M15": ["H1", "H4"],
    "H1": ["H4", "D1"],
}


def detect_events(
    tick_states: dict,
    entry_tf: str,
    high: float, low: float, close: float,
    timestamp: pd.Timestamp,
    bias_rec,
    atr: float,
    pip_size: float,
    bar_idx: int,
    prev_swing_cls: dict,
) -> list[OpportunityEvent]:
    """Detect all opportunity events for one bar across all context TFs."""
    context_tfs = _TF_PAIRS.get(entry_tf, [])
    events: list[OpportunityEvent] = []

    for ctx_tf in context_tfs:
        ts = tick_states.get(ctx_tf)
        if ts is None:
            continue

        for zone_list, side in [(ts.demand_zones, "demand"), (ts.supply_zones, "supply")]:
            for z in zone_list:
                touch = classify_touch(z, high, low, close)

                if touch is not None:
                    events.append(_build_event(
                        z, ctx_tf, entry_tf, touch, side,
                        timestamp, bias_rec, atr, close, prev_swing_cls,
                    ))
                elif is_near_miss(z, high, low, atr, pip_size):
                    events.append(_build_event(
                        z, ctx_tf, entry_tf, "near_miss", side,
                        timestamp, bias_rec, atr, close, prev_swing_cls,
                    ))

    return events


def _build_event(
    zone, ctx_tf: str, entry_tf: str, touch_type: str, side: str,
    timestamp: pd.Timestamp, bias_rec, atr: float, close: float,
    prev_swing_cls: dict,
) -> OpportunityEvent:
    """Build an OpportunityEvent from zone + bar context."""
    age_seconds = (timestamp - zone.origin_time).total_seconds()
    tf_seconds = _tf_to_seconds(ctx_tf)
    age_bars = int(age_seconds / tf_seconds) if tf_seconds > 0 else 0

    prev_cls = prev_swing_cls.get(ctx_tf, {}).get(side, "")
    zone_mid = (zone.top + zone.bottom) / 2.0
    price_dist = abs(close - zone_mid) / atr if atr > 0 else 0.0

    return OpportunityEvent(
        timestamp=timestamp,
        zone_tf=ctx_tf,
        entry_tf=entry_tf,
        tf_pair=f"{entry_tf}@{ctx_tf}",
        touch_type=touch_type,
        zone_side=side,
        zone_role=classify_zone_role(zone, prev_cls),
        age_bucket=classify_age_bucket(age_bars),
        bias_alignment=classify_bias_alignment(
            zone.is_supply, bias_rec.d_bias, bias_rec.is_bias_transition,
        ),
        test_count_cls=classify_test_count(zone.test_count),
        zone_age_bars=age_bars,
        zone_test_count=zone.test_count,
        bias_strength=bias_rec.d_bias_strength,
        price_distance_at_touch=price_dist,
        replacement_count=zone.replacement_count,
        birth_bias_d=zone.birth_bias_d,
        birth_period_pattern=zone.birth_period_pattern,
        birth_price_distance=zone.birth_price_distance,
    )


def _tf_to_seconds(tf: str) -> int:
    return {
        "M1": 60, "M5": 300, "M15": 900, "H1": 3600,
        "H4": 14400, "D1": 86400, "W1": 604800,
    }.get(tf, 3600)
