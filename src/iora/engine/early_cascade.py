"""
Early Confirmation Cascade — CHoCH-to-Structure Propagation.

Detects parent-TF structural events (HH/HL/LH/LL) early by comparing
child-TF zone boundaries against parent-TF zone boundaries.

Core insight: an H1 CHoCH doesn't just confirm an H1 event — it IS the
mechanism that creates H4 structure. An M15 CHoCH IS what completes an H1
sub-wave. Every HTF structural shift is built from LTF CHoCH events.

Detection rules:
  Early parent HH: child supply top > last parent supply top (child is HH)
  Early parent LL: child demand bot < last parent demand bot (child is LL)
  Early parent HL: child demand bot > prev child demand bot, inside parent demand
  Early parent LH: child supply top < prev child supply top, inside parent supply

When detected, creates early anchors that update XTF trendlines hours before
the official HTF zone fires.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import FractalZone, EventID
from iora.engine.events import EventBus
from iora.engine.zone_tick import ZoneTickState
from iora.engine.xtf_trendline import (
    XTFTrendlineState,
    XTFAnchor,
    XTF_ANCHOR_MAP,
    _build_tl,
    _archive,
)

# Same mapping as XTF trendlines: parent ← child
EARLY_CASCADE_MAP = XTF_ANCHOR_MAP


@dataclass(slots=True)
class EarlyAnchor:
    """An early structural anchor detected via LTF CHoCH."""
    parent_tf: str
    child_tf: str
    struct_type: str  # "HH", "HL", "LH", "LL"
    is_supply: bool
    price: float  # anchor price (zone top for supply, zone bot for demand)
    time: pd.Timestamp
    zone: FractalZone


@dataclass(slots=True)
class EarlyCascadeState:
    """Tracks which early detections have already fired to avoid duplicates."""
    seen: set[str] = field(default_factory=set)


def _zone_key(z: FractalZone) -> str:
    """Unique key for a zone to avoid duplicate detections."""
    return f"{z.origin_time}_{z.top}_{z.bot}_{z.is_supply}"


def early_cascade_tick(
    state: EarlyCascadeState,
    zone_states: dict[str, ZoneTickState],
    bar_time: pd.Timestamp,
    bus: EventBus | None = None,
) -> list[EarlyAnchor]:
    """
    Scan all parent-child TF pairs for early structural confirmations.

    Returns list of EarlyAnchor objects that should be injected into
    XTF trendline states for earlier TL updates.
    """
    anchors: list[EarlyAnchor] = []

    for parent_tf, child_tf in EARLY_CASCADE_MAP.items():
        parent_zs = zone_states.get(parent_tf)
        child_zs = zone_states.get(child_tf)
        if not parent_zs or not child_zs:
            continue

        last_parent_sup = parent_zs.supply_zones[-1] if parent_zs.supply_zones else None
        last_parent_dem = parent_zs.demand_zones[-1] if parent_zs.demand_zones else None

        # ── Check child supply zones for early parent HH / LH ──
        for z in child_zs.supply_zones:
            if z.is_broken:
                continue
            key = f"sup_{parent_tf}_{_zone_key(z)}"
            if key in state.seen:
                continue

            if last_parent_sup is not None:
                if z.is_hh_or_ll and z.top > last_parent_sup.top:
                    # Child HH exceeds parent supply top → early parent HH
                    state.seen.add(key)
                    anchors.append(EarlyAnchor(
                        parent_tf=parent_tf, child_tf=child_tf,
                        struct_type="HH", is_supply=True,
                        price=z.top, time=z.origin_time, zone=z,
                    ))
                    _emit(bus, bar_time, parent_tf, child_tf, "HH", z)

                elif not z.is_hh_or_ll and z.top < last_parent_sup.top:
                    # Child LH inside parent supply range → early parent LH
                    if z.bot >= last_parent_sup.bot:
                        state.seen.add(key)
                        # LH = CHoCH → mark this zone as reversal target
                        z.is_reversal_target = True
                        anchors.append(EarlyAnchor(
                            parent_tf=parent_tf, child_tf=child_tf,
                            struct_type="LH", is_supply=True,
                            price=z.top, time=z.origin_time, zone=z,
                        ))
                        _emit(bus, bar_time, parent_tf, child_tf, "LH", z)

        # ── Check child demand zones for early parent LL / HL ──
        for z in child_zs.demand_zones:
            if z.is_broken:
                continue
            key = f"dem_{parent_tf}_{_zone_key(z)}"
            if key in state.seen:
                continue

            if last_parent_dem is not None:
                if z.is_hh_or_ll and z.bot < last_parent_dem.bot:
                    # Child LL below parent demand bot → early parent LL
                    state.seen.add(key)
                    anchors.append(EarlyAnchor(
                        parent_tf=parent_tf, child_tf=child_tf,
                        struct_type="LL", is_supply=False,
                        price=z.bot, time=z.origin_time, zone=z,
                    ))
                    _emit(bus, bar_time, parent_tf, child_tf, "LL", z)

                elif not z.is_hh_or_ll and z.bot > last_parent_dem.bot:
                    # Child HL inside parent demand range → early parent HL
                    if z.top <= last_parent_dem.top:
                        state.seen.add(key)
                        # HL = CHoCH → mark this zone as reversal target
                        z.is_reversal_target = True
                        anchors.append(EarlyAnchor(
                            parent_tf=parent_tf, child_tf=child_tf,
                            struct_type="HL", is_supply=False,
                            price=z.bot, time=z.origin_time, zone=z,
                        ))
                        _emit(bus, bar_time, parent_tf, child_tf, "HL", z)

    return anchors


def _emit(
    bus: EventBus | None,
    bar_time: pd.Timestamp,
    parent_tf: str,
    child_tf: str,
    struct_type: str,
    zone: FractalZone,
) -> None:
    """Emit EARLY_STRUCTURE event."""
    if bus is None:
        return
    bus.emit(
        EventID.EARLY_STRUCTURE,
        bar_time,
        parent_tf,
        {
            "struct_type": struct_type,
            "child_tf": child_tf,
            "is_supply": zone.is_supply,
            "top": zone.top,
            "bot": zone.bot,
            "origin_time": str(zone.origin_time),
        },
    )


def inject_early_anchors(
    early_anchors: list[EarlyAnchor],
    xtf_tl_states: dict[str, XTFTrendlineState],
    max_history: int = 5,
) -> None:
    """
    Inject early cascade anchors into XTF trendline states.

    This updates trendlines BEFORE the official parent-TF zone fires,
    giving earlier visual signals of structural shifts.

    Mapping:
      Early HH → imp_bear anchor (supply top = HH ascending resistance)
      Early LL → imp_bull anchor (demand bot = LL descending support)
      Early HL → cor_bull anchor (demand bot = HL ascending pullback)
      Early LH → cor_bear anchor (supply top = LH descending pullback)
    """
    for ea in early_anchors:
        xtf_state = xtf_tl_states.get(ea.parent_tf)
        if xtf_state is None:
            continue

        anchor = XTFAnchor(
            time=ea.time, price=ea.price,
            zone_top=ea.zone.top, zone_bot=ea.zone.bot,
        )

        if ea.struct_type == "HH":
            side = xtf_state.imp_bear
            _inject_anchor(side, anchor, "bear", ea.parent_tf, ea.child_tf, "impulse", max_history)
        elif ea.struct_type == "LL":
            side = xtf_state.imp_bull
            _inject_anchor(side, anchor, "bull", ea.parent_tf, ea.child_tf, "impulse", max_history)
        elif ea.struct_type == "HL":
            side = xtf_state.cor_bull
            _inject_anchor(side, anchor, "bull", ea.parent_tf, ea.child_tf, "correction", max_history)
        elif ea.struct_type == "LH":
            side = xtf_state.cor_bear
            _inject_anchor(side, anchor, "bear", ea.parent_tf, ea.child_tf, "correction", max_history)


def _inject_anchor(
    side, anchor: XTFAnchor,
    direction: str, parent_tf: str, child_tf: str, tl_type: str,
    max_history: int,
) -> None:
    """Inject an early anchor into an XTFSideTL, rebuilding the TL if 2+ anchors."""
    already = any(
        a.time == anchor.time and abs(a.price - anchor.price) < 1e-10
        for a in side.anchors
    )
    if already:
        return

    side.anchors.append(anchor)
    side.anchors.sort(key=lambda a: a.time)
    if len(side.anchors) > 2:
        side.anchors[:] = side.anchors[-2:]

    if len(side.anchors) == 2:
        a1, a2 = side.anchors
        if a1.time != a2.time:
            _archive(side.active, side.history, max_history)
            side.active = _build_tl(a1, a2, direction, parent_tf, child_tf, tl_type)
