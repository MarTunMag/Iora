# src/iora/strategy/retest_sl_tp.py
"""SL/TP computation for retest entries.

Zone-based SL: below/above the retest zone with ATR buffer.
ATR-based SL: fixed ATR multiple from entry.
Period-based SL: below/above the zone TF's current period extreme.
TP: fixed R:R from SL distance, or opposing zone (future).
"""
from __future__ import annotations

from math import isnan

from iora.strategy.retest_candidate import RetestCandidate

_ZONE_BUFFER_ATR: float = 0.15  # Buffer beyond zone edge as ATR fraction
_LIMIT_BUFFER_ATR: float = 0.10  # Buffer for limit order entry at breaker zone


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

    if mode == "structure":
        if not isnan(c.ltf_choch_zone_boundary):
            if c.direction == "long":
                return c.ltf_choch_zone_boundary - buf
            return c.ltf_choch_zone_boundary + buf
        # Fallback to ATR if no structural level available
        if c.direction == "long":
            return c.entry_price - atr_mult * c.atr
        return c.entry_price + atr_mult * c.atr

    # Fallback to ATR
    if c.direction == "long":
        return c.entry_price - atr_mult * c.atr
    return c.entry_price + atr_mult * c.atr


def compute_layered_sl(
    direction: str,
    brk_top: float,
    brk_bottom: float,
    ctx_zone_top: float,
    ctx_zone_bottom: float,
    atr: float,
    mode: str = "own",
    buffer_atr: float = _ZONE_BUFFER_ATR,
) -> float:
    """Compute SL for a layered cascade entry at a breaker zone.

    Args:
        direction: "long" or "short"
        brk_top, brk_bottom: breaker zone boundaries
        ctx_zone_top, ctx_zone_bottom: HTF context zone boundaries
        atr: ATR(14) at entry time
        mode: "own" = SL behind breaker zone, "htf" = SL behind HTF zone
        buffer_atr: ATR fraction for buffer beyond zone edge
    """
    buf = buffer_atr * atr
    if mode == "own":
        if direction == "long":
            return brk_bottom - buf
        return brk_top + buf
    elif mode == "htf":
        if direction == "long":
            return ctx_zone_bottom - buf
        return ctx_zone_top + buf
    # Fallback to own
    if direction == "long":
        return brk_bottom - buf
    return brk_top + buf


def compute_retest_tp(
    candidate: RetestCandidate,
    sl_price: float,
    mode: str = "fixed_rr",
    fixed_rr: float = 2.0,
) -> float:
    """Compute take-profit for a retest entry.

    Modes:
        fixed_rr: TP at fixed R:R multiple from SL distance
        period: TP at period tracker extreme (hi for longs, lo for shorts)
    """
    c = candidate
    risk = abs(c.entry_price - sl_price)

    if mode == "zone":
        if not isnan(c.next_opposing_zone_price):
            tp = c.next_opposing_zone_price
            if c.direction == "long" and tp > c.entry_price:
                return tp
            if c.direction == "short" and tp < c.entry_price:
                return tp
        # Fallback to fixed_rr
        if c.direction == "long":
            return c.entry_price + fixed_rr * risk
        return c.entry_price - fixed_rr * risk

    if mode == "period":
        # TP at period extreme on zone TF
        if c.direction == "long":
            tp = c.period_hi
            # Period hi must be above entry for a valid long TP
            if tp > c.entry_price:
                return tp
        else:
            tp = c.period_lo
            # Period lo must be below entry for a valid short TP
            if tp < c.entry_price:
                return tp
        # Fallback to fixed_rr if period level is invalid
        if c.direction == "long":
            return c.entry_price + fixed_rr * risk
        return c.entry_price - fixed_rr * risk

    # fixed_rr (default)
    if c.direction == "long":
        return c.entry_price + fixed_rr * risk
    return c.entry_price - fixed_rr * risk
