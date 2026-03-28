"""
Structural cycle state machine — 5-phase D-level reversal cycle.

Ports Pine Pulse S15B (lines 1530-1565).

Two parallel cycles: bear-to-bull and bull-to-bear.

Bear-to-bull cycle phases:
  Phase 0: Init (waiting for D LL break)
  Phase 1: D LL break detected → start tracking
  Phase 2: 1st H4 demand zone captured (below D LL)
  Phase 3: H4 TL anchor set (H4 bear TL that defines reversal structure)
  Phase 4: Rev target H1 supply set (target zone inside terminal H4)

Bull-to-bear cycle phases:
  Phase 0: Init (waiting for D HH break)
  Phase 1: D HH break detected → start tracking
  Phase 2: 1st H4 supply zone captured (above D HH)
  Phase 3: H4 TL anchor set (H4 bull TL that defines reversal structure)
  Phase 4: Rev target H1 demand set (target zone inside terminal H4)

Transitions fire on D structure events (HH/LL) and H4 zone/TL events.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.engine.models import FractalZone, StructuralCycleState, EventID
from iora.engine.events import EventBus


@dataclass(slots=True)
class CycleTickState:
    """
    Per-bar mutable state for the structural cycle.
    Wraps StructuralCycleState plus internal edge tracking.
    """

    # Bear-to-bull cycle (reversal from bearish to bullish)
    bear_to_bull_phase: int = 0
    # Bull-to-bear cycle (reversal from bullish to bearish)
    bull_to_bear_phase: int = 0

    # Persisted levels — bear-to-bull
    first_h4_dem_top: float | None = None
    first_h4_dem_bot: float | None = None
    rev_target_h1_sup_top: float | None = None
    rev_target_h1_sup_bot: float | None = None
    h4_tl_anchor_dem_top: float | None = None
    h4_tl_anchor_dem_bot: float | None = None

    # Persisted levels — bull-to-bear
    first_h4_sup_top: float | None = None
    first_h4_sup_bot: float | None = None
    rev_target_h1_dem_top: float | None = None
    rev_target_h1_dem_bot: float | None = None
    h4_tl_anchor_sup_top: float | None = None
    h4_tl_anchor_sup_bot: float | None = None

    # Internal edge detection
    _prev_d_ll_count: int = 0
    _prev_d_hh_count: int = 0
    _prev_h4_bear_broken: bool = False
    _prev_h4_bull_broken: bool = False

    def to_model(self) -> StructuralCycleState:
        return StructuralCycleState(
            cycle_bear_phase=self.bear_to_bull_phase,
            cycle_bull_phase=self.bull_to_bear_phase,
            first_h4_dem_top=self.first_h4_dem_top,
            first_h4_dem_bot=self.first_h4_dem_bot,
            first_h4_sup_top=self.first_h4_sup_top,
            first_h4_sup_bot=self.first_h4_sup_bot,
            rev_target_h1_sup_top=self.rev_target_h1_sup_top,
            rev_target_h1_sup_bot=self.rev_target_h1_sup_bot,
            rev_target_h1_dem_top=self.rev_target_h1_dem_top,
            rev_target_h1_dem_bot=self.rev_target_h1_dem_bot,
            h4_tl_anchor_sup_top=self.h4_tl_anchor_sup_top,
            h4_tl_anchor_sup_bot=self.h4_tl_anchor_sup_bot,
            h4_tl_anchor_dem_top=self.h4_tl_anchor_dem_top,
            h4_tl_anchor_dem_bot=self.h4_tl_anchor_dem_bot,
        )

    @property
    def phase_label(self) -> str:
        """Human-readable label for Compass display."""
        parts = []
        if self.bear_to_bull_phase > 0:
            parts.append(f"B→BL P{self.bear_to_bull_phase}")
        if self.bull_to_bear_phase > 0:
            parts.append(f"BL→B P{self.bull_to_bear_phase}")
        return " / ".join(parts) if parts else "—"


def cycle_tick(
    state: CycleTickState,
    d_ll_count: int,
    d_hh_count: int,
    h4_demand_zones: list[FractalZone],
    h4_supply_zones: list[FractalZone],
    h1_supply_zones: list[FractalZone],
    h1_demand_zones: list[FractalZone],
    h4_bear_tl_broken: bool,
    h4_bull_tl_broken: bool,
    close: float,
    bar_time: pd.Timestamp,
    h1_sup_exhausted: bool = False,
    h1_dem_exhausted: bool = False,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar for cycle state machine transitions.

    Mutates ``state`` in place.
    """
    # ---- Bear-to-bull cycle (D LL break → reversal upward) ----

    # Phase 0 → 1: D LL break fires
    d_ll_edge = d_ll_count > state._prev_d_ll_count and d_ll_count > 0
    if d_ll_edge:
        state.bear_to_bull_phase = 1
        # Reset persisted levels
        state.first_h4_dem_top = None
        state.first_h4_dem_bot = None
        state.h4_tl_anchor_dem_top = None
        state.h4_tl_anchor_dem_bot = None
        state.rev_target_h1_sup_top = None
        state.rev_target_h1_sup_bot = None
        if bus is not None:
            bus.emit(
                EventID.CYCLE_PHASE,
                bar_time,
                "D1",
                {
                    "cycle": "bear_to_bull",
                    "phase": 1,
                    "trigger": "d_ll_break",
                },
            )

    # Phase 1 → 2: First H4 demand zone captured
    if state.bear_to_bull_phase == 1 and state.first_h4_dem_top is None:
        if h4_demand_zones:
            # Take the most recent H4 demand
            newest_dem = h4_demand_zones[-1]
            state.first_h4_dem_top = newest_dem.top
            state.first_h4_dem_bot = newest_dem.bot
            state.bear_to_bull_phase = 2
            if bus is not None:
                bus.emit(
                    EventID.CYCLE_PHASE,
                    bar_time,
                    "H4",
                    {
                        "cycle": "bear_to_bull",
                        "phase": 2,
                        "trigger": "first_h4_dem",
                        "zone_top": newest_dem.top,
                        "zone_bot": newest_dem.bot,
                    },
                )

    # Phase 2 → 3: H4 bear TL break (bullish confirmation)
    h4_bear_break_edge = h4_bear_tl_broken and not state._prev_h4_bear_broken
    if state.bear_to_bull_phase == 2 and h4_bear_break_edge:
        state.bear_to_bull_phase = 3
        if bus is not None:
            bus.emit(
                EventID.CYCLE_PHASE,
                bar_time,
                "H4",
                {
                    "cycle": "bear_to_bull",
                    "phase": 3,
                    "trigger": "h4_bear_tl_break",
                },
            )

    # Phase 3 → 4: Reversal target H1 supply captured (inside terminal H4 zone)
    if state.bear_to_bull_phase == 3 and state.rev_target_h1_sup_top is None:
        if h1_supply_zones and h1_sup_exhausted:
            # Target = H1 supply inside the terminal structure
            newest_sup = h1_supply_zones[-1]
            state.rev_target_h1_sup_top = newest_sup.top
            state.rev_target_h1_sup_bot = newest_sup.bot
            state.bear_to_bull_phase = 4
            if bus is not None:
                bus.emit(
                    EventID.CYCLE_PHASE,
                    bar_time,
                    "H1",
                    {
                        "cycle": "bear_to_bull",
                        "phase": 4,
                        "trigger": "rev_target_h1_sup",
                        "zone_top": newest_sup.top,
                        "zone_bot": newest_sup.bot,
                    },
                )

    # ---- Bull-to-bear cycle (D HH break → reversal downward) ----

    # Phase 0 → 1: D HH break fires
    d_hh_edge = d_hh_count > state._prev_d_hh_count and d_hh_count > 0
    if d_hh_edge:
        state.bull_to_bear_phase = 1
        state.first_h4_sup_top = None
        state.first_h4_sup_bot = None
        state.h4_tl_anchor_sup_top = None
        state.h4_tl_anchor_sup_bot = None
        state.rev_target_h1_dem_top = None
        state.rev_target_h1_dem_bot = None
        if bus is not None:
            bus.emit(
                EventID.CYCLE_PHASE,
                bar_time,
                "D1",
                {
                    "cycle": "bull_to_bear",
                    "phase": 1,
                    "trigger": "d_hh_break",
                },
            )

    # Phase 1 → 2: First H4 supply zone captured
    if state.bull_to_bear_phase == 1 and state.first_h4_sup_top is None:
        if h4_supply_zones:
            newest_sup = h4_supply_zones[-1]
            state.first_h4_sup_top = newest_sup.top
            state.first_h4_sup_bot = newest_sup.bot
            state.bull_to_bear_phase = 2
            if bus is not None:
                bus.emit(
                    EventID.CYCLE_PHASE,
                    bar_time,
                    "H4",
                    {
                        "cycle": "bull_to_bear",
                        "phase": 2,
                        "trigger": "first_h4_sup",
                        "zone_top": newest_sup.top,
                        "zone_bot": newest_sup.bot,
                    },
                )

    # Phase 2 → 3: H4 bull TL break (bearish confirmation)
    h4_bull_break_edge = h4_bull_tl_broken and not state._prev_h4_bull_broken
    if state.bull_to_bear_phase == 2 and h4_bull_break_edge:
        state.bull_to_bear_phase = 3
        if bus is not None:
            bus.emit(
                EventID.CYCLE_PHASE,
                bar_time,
                "H4",
                {
                    "cycle": "bull_to_bear",
                    "phase": 3,
                    "trigger": "h4_bull_tl_break",
                },
            )

    # Phase 3 → 4: Reversal target H1 demand captured
    if state.bull_to_bear_phase == 3 and state.rev_target_h1_dem_top is None:
        if h1_demand_zones and h1_dem_exhausted:
            newest_dem = h1_demand_zones[-1]
            state.rev_target_h1_dem_top = newest_dem.top
            state.rev_target_h1_dem_bot = newest_dem.bot
            state.bull_to_bear_phase = 4
            if bus is not None:
                bus.emit(
                    EventID.CYCLE_PHASE,
                    bar_time,
                    "H1",
                    {
                        "cycle": "bull_to_bear",
                        "phase": 4,
                        "trigger": "rev_target_h1_dem",
                        "zone_top": newest_dem.top,
                        "zone_bot": newest_dem.bot,
                    },
                )

    # Update edge tracking
    state._prev_d_ll_count = d_ll_count
    state._prev_d_hh_count = d_hh_count
    state._prev_h4_bear_broken = h4_bear_tl_broken
    state._prev_h4_bull_broken = h4_bull_tl_broken
