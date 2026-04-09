"""
Structural FVG detection — tracks the gap between HTF pivots and LTF first swings.

Type 2 FVG: After an HTF pivot is confirmed, the first LTF swing in the
opposite direction that falls SHORT of reaching the HTF pivot price creates
a structural FVG — the gap from LTF swing to HTF pivot.

Example: H4 makes a high at 1.3050. M15 pulls back to 1.3020 (first LTF low).
  → Structural FVG: gap from 1.3020 (LTF low) to 1.3050 (HTF high)
  → Until the gap is filled (price reaches 1.3050), it acts as a magnet/target

TF pair matrix: D1→H4, H4→H1, H1→M15, M15→M5, M5→M1 (and skip-level pairs)

Integration:
  Called per-bar AFTER period tracking. Reads PeriodTracker pivot values.
  Results feed into candidate enrichment for sweep filtering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan


@dataclass(frozen=True, slots=True)
class StructuralFVGEvent:
    """A structural FVG (gap between HTF pivot and LTF first swing)."""
    htf: str              # The HTF that made the pivot
    ltf: str              # The LTF that made the first counter-swing
    direction: str        # "bullish" (gap above price) or "bearish" (gap below price)
    htf_pivot_price: float  # The HTF pivot price (magnet/target)
    ltf_swing_price: float  # The LTF first swing price (gap boundary)
    bar_idx: int


@dataclass(slots=True)
class StructuralFVGState:
    """Per TF-pair structural FVG tracking state."""
    htf: str = ""
    ltf: str = ""

    # Last HTF pivot prices (to detect new pivots)
    _prev_htf_high: float = float('nan')
    _prev_htf_low: float = float('nan')

    # After HTF high: waiting for first LTF low (bearish structural FVG test)
    _waiting_for_ltf_low: bool = False
    _htf_high_price: float = float('nan')
    _first_ltf_low_found: bool = False

    # After HTF low: waiting for first LTF high (bullish structural FVG test)
    _waiting_for_ltf_high: bool = False
    _htf_low_price: float = float('nan')
    _first_ltf_high_found: bool = False

    # Active structural FVGs (max 2: one bearish, one bullish)
    active_fvgs: list[StructuralFVGEvent] = field(default_factory=list)

    MAX_ACTIVE: int = 4


def structural_fvg_tick(
    state: StructuralFVGState,
    htf_prev_highs: list[float],
    htf_prev_lows: list[float],
    ltf_prev_highs: list[float],
    ltf_prev_lows: list[float],
    bar_high: float,
    bar_low: float,
    bar_idx: int,
) -> list[StructuralFVGEvent]:
    """Process one bar for structural FVG detection.

    Args:
        state: Mutable per-pair state.
        htf_prev_highs: HTF PeriodTracker.prev_highs (most recent first).
        htf_prev_lows: HTF PeriodTracker.prev_lows (most recent first).
        ltf_prev_highs: LTF PeriodTracker.prev_highs (most recent first).
        ltf_prev_lows: LTF PeriodTracker.prev_lows (most recent first).
        bar_high: Current bar high (for fill detection).
        bar_low: Current bar low (for fill detection).
        bar_idx: Sequential bar index.

    Returns:
        List of newly detected structural FVG events this bar.
    """
    new_events: list[StructuralFVGEvent] = []

    # --- Fill check: remove structural FVGs that price has reached ---
    remaining: list[StructuralFVGEvent] = []
    for fvg in state.active_fvgs:
        if fvg.direction == "bullish":
            # Bullish gap above: filled when bar_high reaches htf_pivot_price
            if bar_high >= fvg.htf_pivot_price:
                continue
        else:
            # Bearish gap below: filled when bar_low reaches htf_pivot_price
            if bar_low <= fvg.htf_pivot_price:
                continue
        remaining.append(fvg)
    state.active_fvgs = remaining

    # --- Detect new HTF pivots ---
    htf_high = htf_prev_highs[0] if htf_prev_highs else float('nan')
    htf_low = htf_prev_lows[0] if htf_prev_lows else float('nan')

    # New HTF high detected
    if not isnan(htf_high) and (isnan(state._prev_htf_high) or htf_high != state._prev_htf_high):
        state._prev_htf_high = htf_high
        state._waiting_for_ltf_low = True
        state._htf_high_price = htf_high
        state._first_ltf_low_found = False

    # New HTF low detected
    if not isnan(htf_low) and (isnan(state._prev_htf_low) or htf_low != state._prev_htf_low):
        state._prev_htf_low = htf_low
        state._waiting_for_ltf_high = True
        state._htf_low_price = htf_low
        state._first_ltf_high_found = False

    # --- Check first LTF counter-swing ---
    ltf_low = ltf_prev_lows[0] if ltf_prev_lows else float('nan')
    ltf_high = ltf_prev_highs[0] if ltf_prev_highs else float('nan')

    # After HTF high: look for first LTF low (pullback)
    if state._waiting_for_ltf_low and not state._first_ltf_low_found and not isnan(ltf_low):
        state._first_ltf_low_found = True
        # If LTF low doesn't reach HTF high = structural FVG (bearish gap above current price)
        if ltf_low < state._htf_high_price:
            fvg = StructuralFVGEvent(
                htf=state.htf,
                ltf=state.ltf,
                direction="bearish",  # Gap is above: price needs to go up to fill
                htf_pivot_price=state._htf_high_price,
                ltf_swing_price=ltf_low,
                bar_idx=bar_idx,
            )
            new_events.append(fvg)
            state.active_fvgs.append(fvg)
        state._waiting_for_ltf_low = False

    # After HTF low: look for first LTF high (bounce)
    if state._waiting_for_ltf_high and not state._first_ltf_high_found and not isnan(ltf_high):
        state._first_ltf_high_found = True
        # If LTF high doesn't reach HTF low = structural FVG (bullish gap below current price)
        if ltf_high > state._htf_low_price:
            fvg = StructuralFVGEvent(
                htf=state.htf,
                ltf=state.ltf,
                direction="bullish",  # Gap is below: price needs to go down to fill
                htf_pivot_price=state._htf_low_price,
                ltf_swing_price=ltf_high,
                bar_idx=bar_idx,
            )
            new_events.append(fvg)
            state.active_fvgs.append(fvg)
        state._waiting_for_ltf_high = False

    # Enforce cap
    if len(state.active_fvgs) > state.MAX_ACTIVE:
        state.active_fvgs = state.active_fvgs[-state.MAX_ACTIVE:]

    return new_events


def structural_fvg_at_zone(
    fvgs: list[StructuralFVGEvent],
    zone_top: float,
    zone_bottom: float,
) -> str:
    """Classify zone's relationship to structural FVGs.

    Returns:
        "inside_gap" — zone sits inside an unfilled structural FVG
        "at_gap_boundary" — zone is at the HTF pivot side of the gap
        "none" — no relationship
    """
    for fvg in fvgs:
        gap_top = max(fvg.htf_pivot_price, fvg.ltf_swing_price)
        gap_bottom = min(fvg.htf_pivot_price, fvg.ltf_swing_price)

        # Zone overlaps with the gap
        if zone_top >= gap_bottom and zone_bottom <= gap_top:
            # At gap boundary: zone touches the HTF pivot side
            if fvg.direction == "bearish":
                # Gap above: HTF pivot is the top
                if zone_top >= fvg.htf_pivot_price * 0.999:  # Near the top
                    return "at_gap_boundary"
            else:
                # Gap below: HTF pivot is the bottom
                if zone_bottom <= fvg.htf_pivot_price * 1.001:  # Near the bottom
                    return "at_gap_boundary"
            return "inside_gap"

    return "none"
