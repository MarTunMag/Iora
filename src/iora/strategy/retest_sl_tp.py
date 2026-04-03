# src/iora/strategy/retest_sl_tp.py
"""SL/TP computation for retest entries.

Zone-based SL: below/above the retest zone with ATR buffer.
ATR-based SL: fixed ATR multiple from entry.
Period-based SL: below/above the zone TF's current period extreme.
TP: fixed R:R from SL distance, or opposing zone (future).
"""
from __future__ import annotations

from iora.strategy.retest_candidate import RetestCandidate

_ZONE_BUFFER_ATR: float = 0.15  # Buffer beyond zone edge as ATR fraction


def compute_retest_sl(
    candidate: RetestCandidate,
    mode: str = "zone",
    atr_mult: float = 1.5,
    buffer_atr: float = _ZONE_BUFFER_ATR,
) -> float:
    """Compute stop-loss for a retest entry."""
    c = candidate
    buf = buffer_atr * c.atr

    if mode == "zone":
        if c.direction == "long":
            return c.zone_bottom - buf
        return c.zone_top + buf

    if mode == "atr":
        if c.direction == "long":
            return c.entry_price - atr_mult * c.atr
        return c.entry_price + atr_mult * c.atr

    if mode == "period":
        if c.direction == "long":
            return c.period_lo - buf
        return c.period_hi + buf

    # Fallback to ATR
    if c.direction == "long":
        return c.entry_price - atr_mult * c.atr
    return c.entry_price + atr_mult * c.atr


def compute_retest_tp(
    candidate: RetestCandidate,
    sl_price: float,
    mode: str = "fixed_rr",
    fixed_rr: float = 2.0,
) -> float:
    """Compute take-profit for a retest entry."""
    c = candidate
    risk = abs(c.entry_price - sl_price)

    if mode == "fixed_rr":
        if c.direction == "long":
            return c.entry_price + fixed_rr * risk
        return c.entry_price - fixed_rr * risk

    # Fallback to fixed_rr
    if c.direction == "long":
        return c.entry_price + fixed_rr * risk
    return c.entry_price - fixed_rr * risk
