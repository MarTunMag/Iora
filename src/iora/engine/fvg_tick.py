"""
FVG (Fair Value Gap) detection — per-TF per-bar imbalance tracking.

Detects 3-bar imbalance gaps:
  - Bullish FVG: bar[2].high < bar[0].low (gap up)
  - Bearish FVG: bar[2].low > bar[0].high (gap down)

Tracks fill state: an FVG is filled when a subsequent bar's range
overlaps the gap. Filled FVGs are removed from the active list.

Integration:
  Called per-TF per-bar AFTER push_zone_tick in the pipeline.
  CascadeState reads active FVGs for overlap checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(frozen=True, slots=True)
class FVGEvent:
    """An unfilled Fair Value Gap."""
    tf: str
    direction: str        # "bullish" or "bearish"
    top: float            # Upper boundary of the gap
    bottom: float         # Lower boundary of the gap
    bar_idx: int
    timestamp: pd.Timestamp


@dataclass(slots=True)
class FVGState:
    """Per-TF FVG tracking state."""
    active_fvgs: list[FVGEvent] = field(default_factory=list)
    # Rolling 3-bar window: [prev2, prev1, current] highs and lows
    _prev2_high: float = float('nan')
    _prev2_low: float = float('nan')
    _prev1_high: float = float('nan')
    _prev1_low: float = float('nan')
    _bar_count: int = 0

    MAX_ACTIVE: int = 10  # Cap active FVGs per TF


def fvg_tick(
    state: FVGState,
    bar_high: float,
    bar_low: float,
    bar_idx: int,
    timestamp: pd.Timestamp,
    tf: str,
) -> list[FVGEvent]:
    """Process one bar for FVG detection and fill tracking.

    Args:
        state: Mutable per-TF FVG state.
        bar_high: Current bar high.
        bar_low: Current bar low.
        bar_idx: Sequential bar index.
        timestamp: Current bar timestamp.
        tf: Timeframe label.

    Returns:
        List of newly detected FVG events this bar.
    """
    new_fvgs: list[FVGEvent] = []

    # --- Fill check: remove FVGs that current bar overlaps ---
    remaining: list[FVGEvent] = []
    for fvg in state.active_fvgs:
        if fvg.direction == "bullish":
            # Bullish FVG filled when bar_low <= fvg.top (price drops into the gap)
            if bar_low <= fvg.bottom:
                continue  # Fully filled, remove
        else:
            # Bearish FVG filled when bar_high >= fvg.bottom (price rises into the gap)
            if bar_high >= fvg.top:
                continue  # Fully filled, remove
        remaining.append(fvg)
    state.active_fvgs = remaining

    # --- Detect new FVGs (need 3 bars of history) ---
    if state._bar_count >= 2:
        # Bullish FVG: prev2_high < current bar_low
        if state._prev2_high < bar_low:
            fvg = FVGEvent(
                tf=tf,
                direction="bullish",
                top=bar_low,
                bottom=state._prev2_high,
                bar_idx=bar_idx,
                timestamp=timestamp,
            )
            new_fvgs.append(fvg)
            state.active_fvgs.append(fvg)

        # Bearish FVG: prev2_low > current bar_high
        if state._prev2_low > bar_high:
            fvg = FVGEvent(
                tf=tf,
                direction="bearish",
                top=state._prev2_low,
                bottom=bar_high,
                bar_idx=bar_idx,
                timestamp=timestamp,
            )
            new_fvgs.append(fvg)
            state.active_fvgs.append(fvg)

    # Enforce cap
    if len(state.active_fvgs) > state.MAX_ACTIVE:
        state.active_fvgs = state.active_fvgs[-state.MAX_ACTIVE:]

    # Shift window
    state._prev2_high = state._prev1_high
    state._prev2_low = state._prev1_low
    state._prev1_high = bar_high
    state._prev1_low = bar_low
    state._bar_count = min(state._bar_count + 1, 3)

    return new_fvgs


def fvg_overlaps_zone(
    fvgs: list[FVGEvent],
    zone_top: float,
    zone_bottom: float,
) -> bool:
    """Check if any active FVG overlaps a given zone boundary."""
    for fvg in fvgs:
        if fvg.top >= zone_bottom and fvg.bottom <= zone_top:
            return True
    return False
