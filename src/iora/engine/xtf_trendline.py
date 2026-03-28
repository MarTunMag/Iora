"""
Cross-TF zone-anchored trendlines.

Port of Pine `Spring Leaf — Trendlines_v3` concept.

Each parent TF gets TWO pairs of trendlines from its child-TF zones:

  Impulse TLs  (HH/LL zones) — trend continuation push
    Bull impulse: LL demand zone bots (descending lows = bear trend push)
    Bear impulse: HH supply zone tops (ascending highs = bull trend push)

  Correction TLs (LH/HL zones) — pullback toward HTF TL
    Bull correction: HL demand zone bots (ascending pullback support)
    Bear correction: LH supply zone tops (descending pullback resistance)

Visual cascade:
  - HTF impulse TL shows main trend direction
  - LTF correction TL shows pullback within the trend
  - When LTF correction TL breaks → trend continuation confirmed
  - When HTF impulse TL breaks → potential reversal

Anchor mapping (parent ← child):
  MN1←W1, W1←D1, D1←H4, H4←H1, H1←M15, M15←M5, M5←M1
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import Trendline, FractalZone, EventID
from iora.engine.events import EventBus


# Parent TF → child TF whose zones provide anchors
XTF_ANCHOR_MAP: dict[str, str] = {
    "MN1": "W1",
    "W1": "D1",
    "D1": "H4",
    "H4": "H1",
    "H1": "M15",
    "M15": "M5",
    "M5": "M1",
}

# All parent TFs that get cross-TF trendlines
XTF_PARENT_TFS = list(XTF_ANCHOR_MAP.keys())


@dataclass(slots=True)
class XTFAnchor:
    """A zone-derived anchor point."""
    time: pd.Timestamp
    price: float
    zone_top: float
    zone_bot: float


@dataclass(slots=True)
class XTFSideTL:
    """One side (bull or bear) of XTF trendline tracking."""
    anchors: list[XTFAnchor] = field(default_factory=list)
    active: Trendline | None = None
    history: list[Trendline] = field(default_factory=list)


@dataclass(slots=True)
class XTFTrendlineState:
    """Per-parent-TF state for cross-TF zone-anchored trendlines.

    Impulse TLs track HH/LL zones (trend continuation push).
    Correction TLs track LH/HL zones (pullback toward HTF TL).
    """

    # Impulse: HH supply tops (bear) / LL demand bots (bull)
    imp_bull: XTFSideTL = field(default_factory=XTFSideTL)
    imp_bear: XTFSideTL = field(default_factory=XTFSideTL)

    # Correction: LH supply tops (bear) / HL demand bots (bull)
    cor_bull: XTFSideTL = field(default_factory=XTFSideTL)
    cor_bear: XTFSideTL = field(default_factory=XTFSideTL)


def _interpolate(tl: Trendline, t_now: pd.Timestamp) -> float | None:
    """Linear interpolation of trendline price at time t_now."""
    dt = (tl.t2 - tl.t1).total_seconds()
    if dt == 0:
        return None
    slope = (tl.p2 - tl.p1) / dt
    return tl.p1 + slope * (t_now - tl.t1).total_seconds()


def _build_tl(
    a1: XTFAnchor, a2: XTFAnchor,
    direction: str, parent_tf: str, child_tf: str, tl_type: str,
) -> Trendline:
    """Create a Trendline from two zone anchors."""
    return Trendline(
        t1=a1.time,
        p1=a1.price,
        t2=a2.time,
        p2=a2.price,
        direction=direction,
        timeframe=parent_tf,
        anchor_source=child_tf,
        tl_type=tl_type,
    )


def _mark_broken(
    tl: Trendline,
    bar_time: pd.Timestamp,
    target_top: float = 0.0,
    target_bot: float = 0.0,
    target_time: pd.Timestamp | None = None,
) -> Trendline:
    """Create a broken copy of a frozen Trendline with target zone info."""
    return Trendline(
        t1=tl.t1, p1=tl.p1, t2=tl.t2, p2=tl.p2,
        direction=tl.direction, timeframe=tl.timeframe,
        is_broken=True, break_time=bar_time,
        anchor_source=tl.anchor_source, tl_type=tl.tl_type,
        target_zone_top=target_top,
        target_zone_bot=target_bot,
        target_zone_time=target_time,
    )


def _archive(
    active: Trendline | None,
    history: list[Trendline],
    max_history: int,
) -> None:
    """Archive active TL to history, trimming to max."""
    if active is not None:
        history.append(active)
        if len(history) > max_history:
            history[:] = history[-max_history:]


def _collect_anchors_and_build(
    side: XTFSideTL,
    zones: list[FractalZone],
    use_top: bool,
    direction: str,
    parent_tf: str,
    child_tf: str,
    tl_type: str,
    max_history: int,
) -> None:
    """Collect zone anchors for one side, build TL when 2+ anchors exist."""
    for z in zones:
        if z.is_broken:
            continue
        price = z.top if use_top else z.bot
        already = any(
            a.time == z.origin_time and abs(a.price - price) < 1e-10
            for a in side.anchors
        )
        if already:
            continue

        side.anchors.append(
            XTFAnchor(time=z.origin_time, price=price,
                       zone_top=z.top, zone_bot=z.bot)
        )
        side.anchors.sort(key=lambda a: a.time)
        if len(side.anchors) > 2:
            side.anchors[:] = side.anchors[-2:]

        if len(side.anchors) == 2:
            a1, a2 = side.anchors
            if a1.time != a2.time:
                _archive(side.active, side.history, max_history)
                side.active = _build_tl(a1, a2, direction, parent_tf, child_tf, tl_type)


def _check_break(
    side: XTFSideTL,
    bar_high: float,
    bar_low: float,
    bar_time: pd.Timestamp,
    is_bull: bool,
    parent_tf: str,
    child_tf: str,
    bus: EventBus | None,
) -> None:
    """Check and handle break detection for one TL side."""
    if side.active is None or side.active.is_broken:
        return
    tl_val = _interpolate(side.active, bar_time)
    if tl_val is None:
        return

    broken = (bar_low < tl_val) if is_bull else (bar_high > tl_val)
    if not broken:
        return

    # First anchor zone = reversal target (where price will push back to)
    target_top = target_bot = 0.0
    target_time = None
    if side.anchors:
        first_anchor = side.anchors[0]
        target_top = first_anchor.zone_top
        target_bot = first_anchor.zone_bot
        target_time = first_anchor.time

    side.active = _mark_broken(
        side.active, bar_time,
        target_top=target_top, target_bot=target_bot, target_time=target_time,
    )
    if bus is not None:
        bus.emit(
            EventID.TL_BREAK, bar_time, parent_tf,
            {
                "direction": "bull" if is_bull else "bear",
                "side": "bearish_break" if is_bull else "bullish_break",
                "tl_price": tl_val,
                "bar_low" if is_bull else "bar_high": bar_low if is_bull else bar_high,
                "xtf": True,
                "anchor_tf": child_tf,
                "tl_type": side.active.tl_type,
                "target_zone_top": target_top,
                "target_zone_bot": target_bot,
            },
        )


def xtf_trendline_tick(
    state: XTFTrendlineState,
    parent_tf: str,
    child_supply_zones: list[FractalZone],
    child_demand_zones: list[FractalZone],
    bar_high: float,
    bar_low: float,
    bar_time: pd.Timestamp,
    max_history: int = 5,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar for cross-TF zone-anchored trendlines.

    Splits zones by is_hh_or_ll into impulse (HH/LL) and correction (LH/HL),
    builds separate TLs for each, and checks for breaks.
    """
    child_tf = XTF_ANCHOR_MAP.get(parent_tf, "")

    # Split zones by structure type
    imp_demand = [z for z in child_demand_zones if z.is_hh_or_ll]      # LL zones
    cor_demand = [z for z in child_demand_zones if not z.is_hh_or_ll]  # HL zones
    imp_supply = [z for z in child_supply_zones if z.is_hh_or_ll]      # HH zones
    cor_supply = [z for z in child_supply_zones if not z.is_hh_or_ll]  # LH zones

    # ── Impulse TLs ──
    # Bull impulse: LL demand bots (trend push — bear trend making new lows)
    _collect_anchors_and_build(
        state.imp_bull, imp_demand, use_top=False,
        direction="bull", parent_tf=parent_tf, child_tf=child_tf,
        tl_type="impulse", max_history=max_history,
    )
    # Bear impulse: HH supply tops (trend push — bull trend making new highs)
    _collect_anchors_and_build(
        state.imp_bear, imp_supply, use_top=True,
        direction="bear", parent_tf=parent_tf, child_tf=child_tf,
        tl_type="impulse", max_history=max_history,
    )

    # ── Correction TLs ──
    # Bull correction: HL demand bots (pullback support — ascending lows)
    _collect_anchors_and_build(
        state.cor_bull, cor_demand, use_top=False,
        direction="bull", parent_tf=parent_tf, child_tf=child_tf,
        tl_type="correction", max_history=max_history,
    )
    # Bear correction: LH supply tops (pullback resistance — descending highs)
    _collect_anchors_and_build(
        state.cor_bear, cor_supply, use_top=True,
        direction="bear", parent_tf=parent_tf, child_tf=child_tf,
        tl_type="correction", max_history=max_history,
    )

    # ── Break detection for all 4 sides ──
    for side, is_bull in [
        (state.imp_bull, True), (state.imp_bear, False),
        (state.cor_bull, True), (state.cor_bear, False),
    ]:
        _check_break(side, bar_high, bar_low, bar_time, is_bull, parent_tf, child_tf, bus)


def get_all_xtf_trendlines(state: XTFTrendlineState) -> list[Trendline]:
    """Return all active + history cross-TF trendlines for visualization."""
    out: list[Trendline] = []
    for side in [state.imp_bull, state.imp_bear, state.cor_bull, state.cor_bear]:
        out.extend(side.history)
        if side.active is not None:
            out.append(side.active)
    return out
