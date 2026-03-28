"""
Internal/external market structure for any child/parent TF pair.

Core insight: internal structure = current TF zone chain; external = parent TF boundaries.
The zones ARE the swings — no lookback windows needed. Zero lag.

TF cascade: M1 ext = M5 int, M5 ext = M15 int, ..., H4 ext = D int, D ext = W int.

Functions:
  classify_break_context() — annotate a child break as BoS/CHoCH/BoS+/CHoCH+
  check_propagation()      — does a child zone cross a parent TF boundary?
  compute_structure_state() — combine child + parent ZoneResults into StructureState
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.engine.zone_detect import Zone, StructureBreak, ZoneResult


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ExternalLevel:
    price: float
    time: pd.Timestamp
    zone: Zone  # the parent TF zone defining this level


@dataclass(frozen=True, slots=True)
class StructureEvent:
    time: pd.Timestamp
    price: float
    break_type: str  # "BOS" | "CHoCH"
    is_external: bool
    label: str  # "BoS" | "CHoCH" | "BoS+" | "CHoCH+"
    direction: str  # "bullish" | "bearish"
    zone_label: str  # HH/LH/HL/LL of the broken zone
    zone_origin_time: pd.Timestamp  # origin of the broken zone (for break line start)


@dataclass(slots=True)
class StructureState:
    bias: str  # "bullish" | "bearish" | "neutral"
    external_high: ExternalLevel | None
    external_low: ExternalLevel | None
    last_event: StructureEvent | None
    chain_count: int  # unbroken child zones since last parent TF zone confirmed
    events: list[StructureEvent]


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def classify_break_context(
    break_event: StructureBreak,
    parent_zones: list[Zone],
) -> StructureEvent:
    """Classify a child TF break as internal or external (BoS/CHoCH +/- '+' suffix)."""
    is_external = False

    if parent_zones:
        if break_event.direction == "bullish":
            # Bullish break — check if price exceeds parent supply top
            parent_supplies = [z for z in parent_zones if z.is_supply and not z.is_broken]
            if parent_supplies:
                latest = parent_supplies[-1]
                if break_event.price > latest.top:
                    is_external = True
        else:
            # Bearish break — check if price exceeds parent demand bottom
            parent_demands = [z for z in parent_zones if not z.is_supply and not z.is_broken]
            if parent_demands:
                latest = parent_demands[-1]
                if break_event.price < latest.bot:
                    is_external = True

    suffix = "+" if is_external else ""
    label = f"{break_event.break_type}{suffix}"
    # Normalize to display form: BOS→BoS, CHoCH stays
    label = label.replace("BOS", "BoS")

    return StructureEvent(
        time=break_event.time,
        price=break_event.price,
        break_type=break_event.break_type,
        is_external=is_external,
        label=label,
        direction=break_event.direction,
        zone_label=break_event.label,
        zone_origin_time=break_event.zone_origin_time,
    )


def check_propagation(
    child_zone: Zone,
    parent_zones: list[Zone],
) -> tuple[str, Zone] | None:
    """Check if a child zone creates structure at the parent TF.

    Returns (parent_label, exceeded_parent_zone) or None.
    """
    if not parent_zones:
        return None

    if child_zone.is_supply:
        parent_supplies = [z for z in parent_zones if z.is_supply]
        if not parent_supplies:
            return None
        latest = parent_supplies[-1]
        if child_zone.top > latest.top:
            return ("HH", latest)
        else:
            return ("LH", latest)
    else:
        parent_demands = [z for z in parent_zones if not z.is_supply]
        if not parent_demands:
            return None
        latest = parent_demands[-1]
        if child_zone.bot < latest.bot:
            return ("LL", latest)
        else:
            return ("HL", latest)


def compute_structure_state(
    child_result: ZoneResult,
    parent_result: ZoneResult,
) -> StructureState:
    """Combine child + parent ZoneResults into a StructureState.

    Internal structure = child TF breaks.
    External structure = parent TF zone boundaries.
    """
    events: list[StructureEvent] = []

    # Classify each child break as internal or external
    for brk in child_result.breaks:
        event = classify_break_context(brk, parent_result.zones)
        events.append(event)

    # External levels from parent zones
    external_high = None
    external_low = None
    for z in parent_result.zones:
        if not z.is_broken:
            if z.is_supply:
                external_high = ExternalLevel(price=z.top, time=z.origin_time, zone=z)
            else:
                external_low = ExternalLevel(price=z.bot, time=z.origin_time, zone=z)

    # Chain count: unbroken child zones since last parent zone confirmed
    chain_count = 0
    last_parent_confirm = None
    for z in parent_result.zones:
        if last_parent_confirm is None or z.confirm_time > last_parent_confirm:
            last_parent_confirm = z.confirm_time

    if last_parent_confirm is not None:
        for z in child_result.zones:
            if z.confirm_time > last_parent_confirm and not z.is_broken:
                chain_count += 1
    else:
        chain_count = sum(1 for z in child_result.zones if not z.is_broken)

    return StructureState(
        bias=child_result.bias,
        external_high=external_high,
        external_low=external_low,
        last_event=events[-1] if events else None,
        chain_count=chain_count,
        events=events,
    )
