# src/iora/strategy/sl_tp.py
"""SL/TP computation for push zone strategy.

Four SL modes: zone, structure, atr, fixed_pips
Four TP modes: zone, structure, fixed_rr, atr

All functions are pure — no side effects.
"""
from __future__ import annotations

from iora.engine.push_zone_models import PushZone

_DEFAULT_ATR_MULT: float = 1.5
_DEFAULT_ZONE_BUFFER: float = 0.15  # ATR fraction
_DEFAULT_FALLBACK_RR: float = 2.0
_MAX_SL_ATR: float = 3.0  # Max SL distance in ATR units


def compute_sl(
    *,
    direction: str,
    entry_price: float,
    mode: str,
    zones: list[PushZone],
    atr: float,
    period_levels: dict | None,
    period_depth: int = 1,
    atr_mult: float = _DEFAULT_ATR_MULT,
    fixed_pips: float = 15.0,
    pip_size: float = 0.0001,
    zone_buffer_mult: float = _DEFAULT_ZONE_BUFFER,
) -> float:
    """Compute stop-loss price.

    Args:
        direction: "long" or "short"
        entry_price: Trade entry price
        mode: "zone", "structure", "atr", "fixed_pips"
        zones: Active push zones (all TFs) for zone-backed SL
        atr: ATR value at entry bar
        period_levels: {"highs": [...], "lows": [...]} from PeriodTracker
        period_depth: Which period level index (1-based) for structure mode
        atr_mult: ATR multiplier for atr mode
        fixed_pips: Pip distance for fixed_pips mode
        pip_size: Pip size (0.0001 for most forex)
        zone_buffer_mult: Buffer beyond zone edge as ATR fraction

    Returns:
        SL price as float. Always on the losing side of entry.
    """
    if mode == "zone":
        sl = _zone_sl(direction, entry_price, zones, atr, zone_buffer_mult)
        if sl is not None:
            return sl
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "structure":
        sl = _structure_sl(direction, entry_price, atr, period_levels,
                           period_depth, zone_buffer_mult)
        if sl is not None:
            return sl
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "atr":
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "fixed_pips":
        dist = fixed_pips * pip_size
        if direction == "long":
            return entry_price - dist
        else:
            return entry_price + dist

    raise ValueError(f"Unknown SL mode: {mode!r}")


def compute_tp(
    *,
    direction: str,
    entry_price: float,
    sl_price: float,
    mode: str,
    zones: list[PushZone],
    atr: float,
    period_levels: dict | None,
    period_depth: int = 1,
    fixed_rr: float = _DEFAULT_FALLBACK_RR,
    atr_mult: float = 3.0,
    zone_buffer_mult: float = _DEFAULT_ZONE_BUFFER,
    min_rr: float = 1.5,
    max_rr: float = 5.0,
) -> float:
    """Compute take-profit price.

    Args:
        direction: "long" or "short"
        entry_price: Trade entry price
        sl_price: Already-computed SL price (for R:R calculation)
        mode: "zone", "structure", "fixed_rr", "atr"
        zones: Active push zones (all TFs) for zone-based TP
        atr: ATR value at entry bar
        period_levels: {"highs": [...], "lows": [...]} from PeriodTracker
        fixed_rr: R:R multiplier for fixed_rr mode
        atr_mult: ATR multiplier for atr mode
        zone_buffer_mult: Buffer before zone edge as ATR fraction
        min_rr: Minimum R:R to accept zone TP
        max_rr: Maximum R:R cap

    Returns:
        TP price as float. Always on the winning side of entry.
    """
    risk = abs(entry_price - sl_price)

    if mode == "zone":
        tp = _zone_tp(direction, entry_price, risk, zones, atr,
                       zone_buffer_mult, min_rr, max_rr)
        if tp is not None:
            return tp
        return _rr_tp(direction, entry_price, risk, _DEFAULT_FALLBACK_RR)

    elif mode == "structure":
        tp = _structure_tp(direction, entry_price, risk, period_levels,
                           period_depth, atr, zone_buffer_mult, min_rr, max_rr)
        if tp is not None:
            return tp
        return _rr_tp(direction, entry_price, risk, _DEFAULT_FALLBACK_RR)

    elif mode == "fixed_rr":
        return _rr_tp(direction, entry_price, risk, fixed_rr)

    elif mode == "atr":
        if direction == "long":
            return entry_price + atr * atr_mult
        else:
            return entry_price - atr * atr_mult

    raise ValueError(f"Unknown TP mode: {mode!r}")


# --- Internal helpers ---

def _atr_sl(direction: str, entry: float, atr: float, mult: float) -> float:
    if direction == "long":
        return entry - atr * mult
    return entry + atr * mult


def _rr_tp(direction: str, entry: float, risk: float, rr: float) -> float:
    if direction == "long":
        return entry + risk * rr
    return entry - risk * rr


def _zone_sl(
    direction: str,
    entry: float,
    zones: list[PushZone],
    atr: float,
    buffer_mult: float,
) -> float | None:
    """SL behind nearest same-side zone (demand for long, supply for short)."""
    buffer = atr * buffer_mult
    max_dist = atr * _MAX_SL_ATR

    if direction == "long":
        # Find demand zones below entry
        candidates = [
            z.bottom - buffer
            for z in zones
            if not z.is_supply and z.bottom < entry
            and entry - (z.bottom - buffer) <= max_dist
        ]
        return max(candidates) if candidates else None
    else:
        # Find supply zones above entry
        candidates = [
            z.top + buffer
            for z in zones
            if z.is_supply and z.top > entry
            and (z.top + buffer) - entry <= max_dist
        ]
        return min(candidates) if candidates else None


def _zone_tp(
    direction: str,
    entry: float,
    risk: float,
    zones: list[PushZone],
    atr: float,
    buffer_mult: float,
    min_rr: float,
    max_rr: float,
) -> float | None:
    """TP at nearest opposing zone (supply for long, demand for short)."""
    buffer = atr * buffer_mult

    if risk <= 0:
        return None

    if direction == "long":
        candidates = [
            z.bottom - buffer
            for z in zones
            if z.is_supply and z.bottom > entry
        ]
        if not candidates:
            return None
        nearest = min(candidates)
        tp_dist = nearest - entry
    else:
        candidates = [
            z.top + buffer
            for z in zones
            if not z.is_supply and z.top < entry
        ]
        if not candidates:
            return None
        nearest = max(candidates)
        tp_dist = entry - nearest

    rr = tp_dist / risk
    if rr < min_rr:
        return None

    capped_dist = min(tp_dist, risk * max_rr)
    if direction == "long":
        return entry + capped_dist
    return entry - capped_dist


def _structure_sl(
    direction: str,
    entry: float,
    atr: float,
    levels: dict | None,
    depth: int,
    buffer_mult: float,
) -> float | None:
    """SL behind period level at given depth."""
    if levels is None:
        return None

    buffer = atr * buffer_mult
    idx = depth - 1  # 1-based → 0-based

    if direction == "long":
        lows = levels.get("lows", [])
        if idx < len(lows):
            return lows[idx] - buffer
    else:
        highs = levels.get("highs", [])
        if idx < len(highs):
            return highs[idx] + buffer

    return None


def _structure_tp(
    direction: str,
    entry: float,
    risk: float,
    levels: dict | None,
    depth: int,
    atr: float,
    buffer_mult: float,
    min_rr: float,
    max_rr: float,
) -> float | None:
    """TP at opposing period level."""
    if levels is None or risk <= 0:
        return None

    buffer = atr * buffer_mult
    idx = depth - 1

    if direction == "long":
        highs = levels.get("highs", [])
        if idx < len(highs):
            tp = highs[idx] - buffer
            tp_dist = tp - entry
            rr = tp_dist / risk if risk > 0 else 0
            if rr >= min_rr:
                capped = min(tp_dist, risk * max_rr)
                return entry + capped
    else:
        lows = levels.get("lows", [])
        if idx < len(lows):
            tp = lows[idx] + buffer
            tp_dist = entry - tp
            rr = tp_dist / risk if risk > 0 else 0
            if rr >= min_rr:
                capped = min(tp_dist, risk * max_rr)
                return entry - capped

    return None
