"""
Nested zone containment checks.

Ports Pine's nested_zone_check() and nested_break_tick() from
spring_leaf_grove.pine (lines 403-690).

A nested zone fires when a child TF zone is fully contained inside a
parent TF zone of the same side, with no opposite-side overlap from
the parent.

8 combos (Pine defaults):
  Default ON:  H1@H4, M15@H4, M5@H1
  Default OFF: M1@M5, M5@M15, M1@M15, M1@H1, M15@H1
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import FractalZone, EventID
from iora.engine.events import EventBus
from iora.engine.zone_tick import ZoneTickState

# ---------------------------------------------------------------------------
# Nested zone combo definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NestedCombo:
    """Definition of a child@parent nested zone combo."""

    child_tf: str
    parent_tf: str
    label: str  # e.g. "H1@H4"
    default_on: bool


NESTED_COMBOS: list[NestedCombo] = [
    # HTF cascade combos (top-down analysis: W1→D1→H4)
    NestedCombo("D1", "W1", "D1@W1", default_on=True),
    NestedCombo("H4", "D1", "H4@D1", default_on=True),
    # Original combos
    NestedCombo("H1", "H4", "H1@H4", default_on=True),
    NestedCombo("M15", "H4", "M15@H4", default_on=True),
    NestedCombo("M5", "H1", "M5@H1", default_on=True),
    NestedCombo("M1", "M5", "M1@M5", default_on=False),
    NestedCombo("M5", "M15", "M5@M15", default_on=False),
    NestedCombo("M1", "M15", "M1@M15", default_on=False),
    NestedCombo("M1", "H1", "M1@H1", default_on=False),
    NestedCombo("M15", "H1", "M15@H1", default_on=False),
]


@dataclass(slots=True)
class NestedZoneState:
    """Mutable state for one nested combo's zone arrays."""

    supply_zones: list[FractalZone] = field(default_factory=list)
    demand_zones: list[FractalZone] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def nested_break_tick(
    nested_state: NestedZoneState,
    close: float,
) -> tuple[list[FractalZone], list[FractalZone]]:
    """
    Break detection for nested zones. Same close-based logic as zone_tick
    but no BOS/CHoCH line drawing.

    Returns (broken_supply, broken_demand).
    """
    broken_sup: list[FractalZone] = []
    broken_dem: list[FractalZone] = []

    i = len(nested_state.supply_zones) - 1
    while i >= 0:
        z = nested_state.supply_zones[i]
        if close > z.top:
            z.is_broken = True
            broken_sup.append(z)
            nested_state.supply_zones.pop(i)
        i -= 1

    i = len(nested_state.demand_zones) - 1
    while i >= 0:
        z = nested_state.demand_zones[i]
        if close < z.bot:
            z.is_broken = True
            broken_dem.append(z)
            nested_state.demand_zones.pop(i)
        i -= 1

    return broken_sup, broken_dem


def nested_zone_check(
    child_state: ZoneTickState,
    parent_state: ZoneTickState,
    nested_state: NestedZoneState,
    is_supply: bool,
    max_nested: int = 2,
    bar_time: pd.Timestamp | None = None,
    combo_label: str = "",
    bus: EventBus | None = None,
) -> None:
    """
    Check if newest child zone is fully contained inside any parent zone
    of the same side. If so, create a nested zone.

    Pine reference (grove.pine lines 430-474):
      containment: c_zt <= pz.top and c_zb >= pz.bot
      overlap exclusion: opposite-side parent zones must not overlap

    Args:
        child_state:   ZoneTickState for child TF.
        parent_state:  ZoneTickState for parent TF.
        nested_state:  NestedZoneState to append to.
        is_supply:     True to check supply side, False for demand.
        max_nested:    Max nested zones per side.
        bar_time:      Current bar time for events.
        combo_label:   e.g. "H1@H4" for event metadata.
        bus:           Optional EventBus.
    """
    # Get the newest child zone of the requested side
    child_zones = child_state.supply_zones if is_supply else child_state.demand_zones
    if not child_zones:
        return
    child = child_zones[-1]

    # Get parent zones of the same side
    parent_zones = parent_state.supply_zones if is_supply else parent_state.demand_zones
    # Get parent zones of opposite side (for overlap exclusion)
    parent_opp = parent_state.demand_zones if is_supply else parent_state.supply_zones

    for pz in parent_zones:
        # Containment check: child fully inside parent
        if child.top <= pz.top and child.bot >= pz.bot:
            # Overlap exclusion: check no opposite-side parent overlaps the child
            has_opp_overlap = False
            for opz in parent_opp:
                if opz.bot <= child.top and opz.top >= child.bot:
                    has_opp_overlap = True
                    break

            if has_opp_overlap:
                continue

            # Check if this nested zone already exists (same origin_time + side)
            target_list = (
                nested_state.supply_zones if is_supply else nested_state.demand_zones
            )
            already_exists = any(
                nz.origin_time == child.origin_time and nz.is_supply == is_supply
                for nz in target_list
            )
            if already_exists:
                break

            # Create nested zone
            nested = FractalZone(
                top=child.top,
                bot=child.bot,
                is_supply=is_supply,
                is_hh_or_ll=child.is_hh_or_ll,
                origin_time=child.origin_time,
                seq_num=child.seq_num,
            )
            target_list.append(nested)

            # Trim oldest if over limit
            if len(target_list) > max_nested:
                target_list[:] = target_list[-max_nested:]

            if bus is not None and bar_time is not None:
                bus.emit(
                    EventID.NESTED_FIRE,
                    bar_time,
                    combo_label,
                    {
                        "side": "supply" if is_supply else "demand",
                        "top": child.top,
                        "bot": child.bot,
                        "parent_top": pz.top,
                        "parent_bot": pz.bot,
                    },
                )

            break  # Only match first containing parent


def run_nested_combos(
    zone_states: dict[str, ZoneTickState],
    nested_states: dict[str, NestedZoneState],
    close: float,
    enabled_combos: set[str] | None = None,
    max_nested: int = 2,
    bar_time: pd.Timestamp | None = None,
    bus: EventBus | None = None,
) -> None:
    """
    Run all 8 nested combo checks for one bar.

    Args:
        zone_states:    dict[tf_label → ZoneTickState] for all TFs.
        nested_states:  dict[combo_label → NestedZoneState], initialized
                        by the caller (typically in grove.py).
        close:          Current bar close price.
        enabled_combos: Set of combo labels to process. If None, uses
                        defaults (H1@H4, M15@H4, M5@H1).
        max_nested:     Max nested zones per side per combo.
        bar_time:       Current bar timestamp.
        bus:            Optional EventBus.
    """
    if enabled_combos is None:
        enabled_combos = {c.label for c in NESTED_COMBOS if c.default_on}

    for combo in NESTED_COMBOS:
        if combo.label not in enabled_combos:
            continue

        child_state = zone_states.get(combo.child_tf)
        parent_state = zone_states.get(combo.parent_tf)
        if child_state is None or parent_state is None:
            continue

        ns = nested_states.get(combo.label)
        if ns is None:
            ns = NestedZoneState()
            nested_states[combo.label] = ns

        # Break tick first (same as Pine ordering)
        nested_break_tick(ns, close)

        # Check both sides
        nested_zone_check(
            child_state,
            parent_state,
            ns,
            is_supply=True,
            max_nested=max_nested,
            bar_time=bar_time,
            combo_label=combo.label,
            bus=bus,
        )
        nested_zone_check(
            child_state,
            parent_state,
            ns,
            is_supply=False,
            max_nested=max_nested,
            bar_time=bar_time,
            combo_label=combo.label,
            bus=bus,
        )
