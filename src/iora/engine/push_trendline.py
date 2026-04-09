"""
Push trendline detection — trendline construction from PeriodTracker pivots.

Uses PeriodTracker.prev_highs[] and prev_lows[] as confirmed swing points.
Two trendlines per TF:
  - Descending TL: connects consecutive swing highs where h[0] < h[1] (LH sequence)
  - Ascending TL: connects consecutive swing lows where l[0] > l[1] (HL sequence)

Break detection:
  - Default "close" mode: body close through projected TL price
  - Optional "wick" mode: high/low through projected TL price
  - Fires once per TL; resets when TL is redrawn (new pivot added)

Impulse/correction classification:
  - If TF trend = bearish: descending TL = impulse, ascending TL = correction
  - If TF trend = bullish: ascending TL = impulse, descending TL = correction
  - Break of impulse TL = potential reversal
  - Break of correction TL = trend resumes

Pine reference: iora_pivot_hl_trendlines.pine (TLState, checkBreak, addAnchor)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan


@dataclass(slots=True)
class PushTrendlineState:
    """Per-TF trendline tracking state using PeriodTracker pivots."""

    # Descending TL (connects swing highs going lower — LH sequence)
    desc_anchor1_price: float = float('nan')
    desc_anchor1_bar: int = -1
    desc_anchor2_price: float = float('nan')
    desc_anchor2_bar: int = -1
    desc_active: bool = False
    desc_broken: bool = False
    desc_break_bar: int = -1

    # Ascending TL (connects swing lows going higher — HL sequence)
    asc_anchor1_price: float = float('nan')
    asc_anchor1_bar: int = -1
    asc_anchor2_price: float = float('nan')
    asc_anchor2_bar: int = -1
    asc_active: bool = False
    asc_broken: bool = False
    asc_break_bar: int = -1

    # Track previous pivot values to detect new pivots
    prev_high_value: float = float('nan')
    prev_low_value: float = float('nan')


@dataclass(frozen=True, slots=True)
class PushTrendlineBreakEvent:
    """Event emitted when a push trendline breaks."""

    tf: str
    tl_type: str            # "impulse" or "correction"
    break_direction: str    # "bullish" (broke above desc TL) or "bearish" (broke below asc TL)
    bar_idx: int
    break_price: float      # The price that broke through
    projected_price: float  # Where the TL was at break time
    anchor1_price: float
    anchor2_price: float


def _project_price(p1: float, b1: int, p2: float, b2: int, at_bar: int) -> float:
    """Linear interpolation/extrapolation of TL price at a given bar index."""
    d_bars = b2 - b1
    if d_bars == 0:
        return p2
    slope = (p2 - p1) / d_bars
    return p2 + slope * (at_bar - b2)


def _classify_tl(tl_side: str, trend: int) -> str:
    """Classify a trendline as impulse or correction based on trend.

    tl_side: "desc" (descending, connecting LH highs) or "asc" (ascending, connecting HL lows)
    trend: +1 bull, -1 bear, 0 unknown

    Impulse TL = the push direction (break = potential reversal)
    Correction TL = the pullback direction (break = trend resumes)
    """
    if trend == 0:
        return "unknown"
    if trend == -1:
        # Bearish trend: descending TL (LH tops) = impulse, ascending TL (HL bots) = correction
        return "impulse" if tl_side == "desc" else "correction"
    # Bullish trend: ascending TL (HL bots) = impulse, descending TL (LH tops) = correction
    return "impulse" if tl_side == "asc" else "correction"


def push_trendline_tick(
    state: PushTrendlineState,
    bar_idx: int,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    prev_highs: list[float],
    prev_lows: list[float],
    trend: int,
    break_mode: str = "close",
    tf: str = "",
) -> list[PushTrendlineBreakEvent]:
    """Process one bar for push trendline detection on a single TF.

    Args:
        state: Mutable per-TF trendline state.
        bar_idx: Sequential bar index (for slope calculation).
        bar_high: Current bar high.
        bar_low: Current bar low.
        bar_close: Current bar close.
        prev_highs: PeriodTracker.prev_highs (most recent first).
        prev_lows: PeriodTracker.prev_lows (most recent first).
        trend: PushZoneTickState.trend (+1 bull, -1 bear, 0 unknown).
        break_mode: "close" (body close) or "wick" (high/low).
        tf: Timeframe label for event metadata.

    Returns:
        List of break events fired this bar (usually 0 or 1).
    """
    events: list[PushTrendlineBreakEvent] = []

    # --- Detect new pivots by comparing most recent value ---
    new_high = (len(prev_highs) >= 1
                and (isnan(state.prev_high_value) or prev_highs[0] != state.prev_high_value))
    new_low = (len(prev_lows) >= 1
               and (isnan(state.prev_low_value) or prev_lows[0] != state.prev_low_value))
    if len(prev_highs) >= 1:
        state.prev_high_value = prev_highs[0]
    if len(prev_lows) >= 1:
        state.prev_low_value = prev_lows[0]

    # --- Descending TL: update on new swing high ---
    # Capture state before update to detect pivot-induced breaks
    if new_high and len(prev_highs) >= 1:
        new_price = prev_highs[0]
        was_desc_active = state.desc_active
        was_desc_broken = state.desc_broken
        old_a1 = state.desc_anchor1_price
        old_a2 = state.desc_anchor2_price
        old_a1_bar = state.desc_anchor1_bar
        old_a2_bar = state.desc_anchor2_bar
        _update_descending_tl(state, new_price, bar_idx)
        # Transition 5: pivot above projected TL deactivated it — emit break event
        if was_desc_active and not was_desc_broken and not state.desc_active:
            proj = _project_price(old_a1, old_a1_bar, old_a2, old_a2_bar, bar_idx)
            tl_type = _classify_tl("desc", trend)
            events.append(PushTrendlineBreakEvent(
                tf=tf,
                tl_type=tl_type,
                break_direction="bullish",
                bar_idx=bar_idx,
                break_price=new_price,
                projected_price=proj,
                anchor1_price=old_a1,
                anchor2_price=old_a2,
            ))

    # --- Ascending TL: update on new swing low ---
    if new_low and len(prev_lows) >= 1:
        new_price = prev_lows[0]
        was_asc_active = state.asc_active
        was_asc_broken = state.asc_broken
        old_a1 = state.asc_anchor1_price
        old_a2 = state.asc_anchor2_price
        old_a1_bar = state.asc_anchor1_bar
        old_a2_bar = state.asc_anchor2_bar
        _update_ascending_tl(state, new_price, bar_idx)
        # Transition 5: pivot below projected TL deactivated it — emit break event
        if was_asc_active and not was_asc_broken and not state.asc_active:
            proj = _project_price(old_a1, old_a1_bar, old_a2, old_a2_bar, bar_idx)
            tl_type = _classify_tl("asc", trend)
            events.append(PushTrendlineBreakEvent(
                tf=tf,
                tl_type=tl_type,
                break_direction="bearish",
                bar_idx=bar_idx,
                break_price=new_price,
                projected_price=proj,
                anchor1_price=old_a1,
                anchor2_price=old_a2,
            ))

    # --- Break detection ---
    # Descending TL break: price breaks ABOVE (bullish break)
    if state.desc_active and not state.desc_broken:
        proj = _project_price(
            state.desc_anchor1_price, state.desc_anchor1_bar,
            state.desc_anchor2_price, state.desc_anchor2_bar,
            bar_idx,
        )
        check_price = bar_close if break_mode == "close" else bar_high
        if check_price > proj:
            state.desc_broken = True
            state.desc_break_bar = bar_idx
            tl_type = _classify_tl("desc", trend)
            events.append(PushTrendlineBreakEvent(
                tf=tf,
                tl_type=tl_type,
                break_direction="bullish",
                bar_idx=bar_idx,
                break_price=check_price,
                projected_price=proj,
                anchor1_price=state.desc_anchor1_price,
                anchor2_price=state.desc_anchor2_price,
            ))

    # Ascending TL break: price breaks BELOW (bearish break)
    if state.asc_active and not state.asc_broken:
        proj = _project_price(
            state.asc_anchor1_price, state.asc_anchor1_bar,
            state.asc_anchor2_price, state.asc_anchor2_bar,
            bar_idx,
        )
        check_price = bar_close if break_mode == "close" else bar_low
        if check_price < proj:
            state.asc_broken = True
            state.asc_break_bar = bar_idx
            tl_type = _classify_tl("asc", trend)
            events.append(PushTrendlineBreakEvent(
                tf=tf,
                tl_type=tl_type,
                break_direction="bearish",
                bar_idx=bar_idx,
                break_price=check_price,
                projected_price=proj,
                anchor1_price=state.asc_anchor1_price,
                anchor2_price=state.asc_anchor2_price,
            ))

    return events


def _update_descending_tl(state: PushTrendlineState, new_high: float, bar_idx: int) -> None:
    """Update descending TL with a new swing high pivot.

    Pine reference: TLState.addAnchor() transitions 1-5 for descending=true.

    Logic mirrors the Pine indicator:
      - No anchor1 → set anchor1 (first pivot)
      - anchor1 set, no anchor2 → if new_high < anchor1 (LH), set anchor2 and activate TL
      - TL broken → reset to fresh anchor1
      - TL active, new pivot on or below projected TL → re-anchor (shift a2→a1, new→a2)
      - TL active, new pivot above projected TL → break (handled in break detection)
    """
    if state.desc_broken:
        # Transition 3: After break, reset with fresh anchor
        state.desc_anchor1_price = new_high
        state.desc_anchor1_bar = bar_idx
        state.desc_anchor2_price = float('nan')
        state.desc_anchor2_bar = -1
        state.desc_active = False
        state.desc_broken = False
        return

    if isnan(state.desc_anchor1_price) or state.desc_anchor1_bar < 0:
        # Transition 1: No anchor → set first
        state.desc_anchor1_price = new_high
        state.desc_anchor1_bar = bar_idx
        return

    if not state.desc_active:
        # Transition 2: anchor1 set, no active TL yet
        if new_high < state.desc_anchor1_price:
            # LH confirmed → create TL
            state.desc_anchor2_price = new_high
            state.desc_anchor2_bar = bar_idx
            state.desc_active = True
            state.desc_broken = False
        else:
            # HH → replace anchor1 (keep looking for LH)
            state.desc_anchor1_price = new_high
            state.desc_anchor1_bar = bar_idx
        return

    # Transition 4/5: Active TL, new pivot arrives
    proj = _project_price(
        state.desc_anchor1_price, state.desc_anchor1_bar,
        state.desc_anchor2_price, state.desc_anchor2_bar,
        bar_idx,
    )

    if new_high <= proj:
        # Transition 4: On or below projected TL → re-anchor
        state.desc_anchor1_price = state.desc_anchor2_price
        state.desc_anchor1_bar = state.desc_anchor2_bar
        state.desc_anchor2_price = new_high
        state.desc_anchor2_bar = bar_idx
        state.desc_broken = False  # Reset break state on re-anchor
    else:
        # Pivot is above TL → this is effectively a break via pivot
        # The bar-level break detection will catch the actual price break
        # Reset and start fresh
        state.desc_anchor1_price = new_high
        state.desc_anchor1_bar = bar_idx
        state.desc_anchor2_price = float('nan')
        state.desc_anchor2_bar = -1
        state.desc_active = False
        state.desc_broken = False


def _update_ascending_tl(state: PushTrendlineState, new_low: float, bar_idx: int) -> None:
    """Update ascending TL with a new swing low pivot.

    Mirror of _update_descending_tl for ascending (connecting HL lows).
    """
    if state.asc_broken:
        # Transition 3: After break, reset with fresh anchor
        state.asc_anchor1_price = new_low
        state.asc_anchor1_bar = bar_idx
        state.asc_anchor2_price = float('nan')
        state.asc_anchor2_bar = -1
        state.asc_active = False
        state.asc_broken = False
        return

    if isnan(state.asc_anchor1_price) or state.asc_anchor1_bar < 0:
        # Transition 1: No anchor → set first
        state.asc_anchor1_price = new_low
        state.asc_anchor1_bar = bar_idx
        return

    if not state.asc_active:
        # Transition 2: anchor1 set, no active TL yet
        if new_low > state.asc_anchor1_price:
            # HL confirmed → create TL
            state.asc_anchor2_price = new_low
            state.asc_anchor2_bar = bar_idx
            state.asc_active = True
            state.asc_broken = False
        else:
            # LL → replace anchor1 (keep looking for HL)
            state.asc_anchor1_price = new_low
            state.asc_anchor1_bar = bar_idx
        return

    # Transition 4/5: Active TL, new pivot arrives
    proj = _project_price(
        state.asc_anchor1_price, state.asc_anchor1_bar,
        state.asc_anchor2_price, state.asc_anchor2_bar,
        bar_idx,
    )

    if new_low >= proj:
        # Transition 4: On or above projected TL → re-anchor
        state.asc_anchor1_price = state.asc_anchor2_price
        state.asc_anchor1_bar = state.asc_anchor2_bar
        state.asc_anchor2_price = new_low
        state.asc_anchor2_bar = bar_idx
        state.asc_broken = False
    else:
        # Pivot is below TL → break via pivot
        state.asc_anchor1_price = new_low
        state.asc_anchor1_bar = bar_idx
        state.asc_anchor2_price = float('nan')
        state.asc_anchor2_bar = -1
        state.asc_active = False
        state.asc_broken = False


def get_projected_prices(
    state: PushTrendlineState,
    bar_idx: int,
) -> tuple[float, float]:
    """Return current projected prices for both TLs (nan if inactive).

    Returns (desc_projected, asc_projected).
    """
    desc_proj = float('nan')
    asc_proj = float('nan')

    if state.desc_active and not state.desc_broken:
        desc_proj = _project_price(
            state.desc_anchor1_price, state.desc_anchor1_bar,
            state.desc_anchor2_price, state.desc_anchor2_bar,
            bar_idx,
        )
    if state.asc_active and not state.asc_broken:
        asc_proj = _project_price(
            state.asc_anchor1_price, state.asc_anchor1_bar,
            state.asc_anchor2_price, state.asc_anchor2_bar,
            bar_idx,
        )

    return desc_proj, asc_proj
