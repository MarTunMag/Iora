"""
Push trendline construction + break detection.

Ports Pine S13 (canopy.pine lines 962-1426) and S16 (lines 1428-1632).

Two-pivot construction:
  - Bull TL: consecutive non-HH (LH) pivots at H1/H4/etc lows
  - Bear TL: consecutive non-LL (HL) pivots at highs
  - HH resets bear side, LL resets bull side
  - Active line extends right; finalized lines archived to history

Break detection:
  - Bear TL broken when high > interpolated TL value
  - Bull TL broken when low < interpolated TL value
  - Edge trigger: fires event only on first break bar
  - Resets when next HH/LL pivot fires
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import Trendline, EventID
from iora.engine.events import EventBus


@dataclass(slots=True)
class TrendlineAnchor:
    """A single anchor point for a push trendline."""

    time: pd.Timestamp
    price: float


@dataclass(slots=True)
class TrendlineTickState:
    """
    Mutable per-TF state for trendline construction + break detection.
    """

    # Bull trendline (built from consecutive LH/HL lows)
    bull_p1: TrendlineAnchor | None = None
    bull_active: Trendline | None = None
    bull_history: list[Trendline] = field(default_factory=list)
    bull_broken: bool = False

    # Bear trendline (built from consecutive LH/HL highs)
    bear_p1: TrendlineAnchor | None = None
    bear_active: Trendline | None = None
    bear_history: list[Trendline] = field(default_factory=list)
    bear_broken: bool = False


def _interpolate_tl(tl: Trendline, t_now: pd.Timestamp) -> float | None:
    """
    Linear interpolation of trendline price at time t_now.
    Returns None if the two anchors have the same timestamp.
    """
    dt = (tl.t2 - tl.t1).total_seconds()
    if dt == 0:
        return None
    slope = (tl.p2 - tl.p1) / dt
    return tl.p1 + slope * (t_now - tl.t1).total_seconds()


def trendline_tick(
    state: TrendlineTickState,
    hi_fire: bool,
    hi_price: float | None,
    hi_time: pd.Timestamp | None,
    hi_is_hh: bool,
    lo_fire: bool,
    lo_price: float | None,
    lo_time: pd.Timestamp | None,
    lo_is_ll: bool,
    bar_high: float,
    bar_low: float,
    bar_time: pd.Timestamp,
    timeframe: str = "",
    tl_max_history: int = 3,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar for a single TF's trendline state.

    Handles:
      1. Bear trendline construction from high pivots (non-LL → LH/HL)
      2. Bull trendline construction from low pivots (non-HH → LH/HL)
      3. HH/LL resets (finalize current line, clear p1)
      4. Break detection on active trendlines

    Mutates ``state`` in place.
    """
    # ------------------------------------------------------------------
    # BEAR trendline (descending highs → resistance)
    # ------------------------------------------------------------------
    if hi_fire and hi_price is not None and hi_time is not None:
        if hi_is_hh:
            # HH fires → finalize bear TL and reset
            if state.bear_active is not None:
                state.bear_history.append(state.bear_active)
                if len(state.bear_history) > tl_max_history:
                    state.bear_history[:] = state.bear_history[-tl_max_history:]
                state.bear_active = None
            state.bear_p1 = None
            state.bear_broken = False
        else:
            # LH fires → extend or create bear TL
            if state.bear_p1 is None:
                # First anchor
                state.bear_p1 = TrendlineAnchor(time=hi_time, price=hi_price)
            else:
                # Second anchor → create/replace line
                new_tl = Trendline(
                    t1=state.bear_p1.time,
                    p1=state.bear_p1.price,
                    t2=hi_time,
                    p2=hi_price,
                    direction="bear",
                    timeframe=timeframe,
                )
                if state.bear_active is not None:
                    state.bear_history.append(state.bear_active)
                    if len(state.bear_history) > tl_max_history:
                        state.bear_history[:] = state.bear_history[-tl_max_history:]
                state.bear_active = new_tl
                state.bear_p1 = TrendlineAnchor(time=hi_time, price=hi_price)
                state.bear_broken = False

    # ------------------------------------------------------------------
    # BULL trendline (ascending lows → support)
    # ------------------------------------------------------------------
    if lo_fire and lo_price is not None and lo_time is not None:
        if lo_is_ll:
            # LL fires → finalize bull TL and reset
            if state.bull_active is not None:
                state.bull_history.append(state.bull_active)
                if len(state.bull_history) > tl_max_history:
                    state.bull_history[:] = state.bull_history[-tl_max_history:]
                state.bull_active = None
            state.bull_p1 = None
            state.bull_broken = False
        else:
            # HL fires → extend or create bull TL
            if state.bull_p1 is None:
                state.bull_p1 = TrendlineAnchor(time=lo_time, price=lo_price)
            else:
                new_tl = Trendline(
                    t1=state.bull_p1.time,
                    p1=state.bull_p1.price,
                    t2=lo_time,
                    p2=lo_price,
                    direction="bull",
                    timeframe=timeframe,
                )
                if state.bull_active is not None:
                    state.bull_history.append(state.bull_active)
                    if len(state.bull_history) > tl_max_history:
                        state.bull_history[:] = state.bull_history[-tl_max_history:]
                state.bull_active = new_tl
                state.bull_p1 = TrendlineAnchor(time=lo_time, price=lo_price)
                state.bull_broken = False

    # ------------------------------------------------------------------
    # Break detection
    # ------------------------------------------------------------------
    # Bear TL break: bar high > interpolated bear TL
    if state.bear_active is not None and not state.bear_broken:
        tl_val = _interpolate_tl(state.bear_active, bar_time)
        if tl_val is not None and bar_high > tl_val:
            state.bear_broken = True
            if bus is not None:
                bus.emit(
                    EventID.TL_BREAK,
                    bar_time,
                    timeframe,
                    {
                        "direction": "bear",
                        "side": "bullish_break",
                        "tl_price": tl_val,
                        "bar_high": bar_high,
                    },
                )

    # Bull TL break: bar low < interpolated bull TL
    if state.bull_active is not None and not state.bull_broken:
        tl_val = _interpolate_tl(state.bull_active, bar_time)
        if tl_val is not None and bar_low < tl_val:
            state.bull_broken = True
            if bus is not None:
                bus.emit(
                    EventID.TL_BREAK,
                    bar_time,
                    timeframe,
                    {
                        "direction": "bull",
                        "side": "bearish_break",
                        "tl_price": tl_val,
                        "bar_low": bar_low,
                    },
                )


def get_all_trendlines(state: TrendlineTickState) -> list[Trendline]:
    """Return all active + history trendlines for visualization."""
    out: list[Trendline] = []
    out.extend(state.bear_history)
    out.extend(state.bull_history)
    if state.bear_active is not None:
        out.append(state.bear_active)
    if state.bull_active is not None:
        out.append(state.bull_active)
    return out
