"""
Macro bias confirmation — M5 TL break at H4/D zone.

Ports Pine Pulse S16C (lines 1565-1610).

Logic:
  - M5 bearish TL breaks (high > TL) while inside H4/D zone → BULL CONFIRMED (+1)
  - M5 bullish TL breaks (low < TL) while inside H4/D zone → BEAR CONFIRMED (-1)
  - Terminal exhaustion gates: don't flip bullish when H1 demand exhausted,
    don't flip bearish when H1 supply exhausted
  - Once set, stays until opposite confirmation fires

Zone containment test: bar close is inside any unbroken H4 or D zone.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.engine.models import FractalZone, MacroBiasState, EventID
from iora.engine.trendline_tick import TrendlineTickState, _interpolate_tl
from iora.engine.events import EventBus


@dataclass(slots=True)
class MacroBiasTickState:
    """
    Per-bar mutable state for macro bias computation.

    Wraps MacroBiasState plus internal tracking for edge detection.
    """

    macro_bias: int = 0
    bear_conf_fired: bool = False
    bull_conf_fired: bool = False

    # Edge detection: only fire once per TL break
    _prev_m5_bear_broken: bool = False
    _prev_m5_bull_broken: bool = False

    def to_model(self) -> MacroBiasState:
        return MacroBiasState(
            macro_bias=self.macro_bias,
            bear_conf_fired=self.bear_conf_fired,
            bull_conf_fired=self.bull_conf_fired,
        )


def _price_inside_zones(
    price: float,
    zones: list[FractalZone],
) -> bool:
    """Check if price is inside any unbroken zone."""
    for z in zones:
        if not z.is_broken and z.bot <= price <= z.top:
            return True
    return False


def macro_bias_tick(
    state: MacroBiasTickState,
    m5_tl: TrendlineTickState | None,
    h4_supply_zones: list[FractalZone],
    h4_demand_zones: list[FractalZone],
    d_supply_zones: list[FractalZone],
    d_demand_zones: list[FractalZone],
    close: float,
    bar_high: float,
    bar_low: float,
    bar_time: pd.Timestamp,
    h1_sup_exhausted: bool = False,
    h1_dem_exhausted: bool = False,
    bus: EventBus | None = None,
) -> None:
    """
    Process one bar for macro bias confirmation.

    Checks M5 TL break events and zone containment to set macro_bias.
    Terminal exhaustion gates prevent false reversals.

    Mutates ``state`` in place.
    """
    if m5_tl is None:
        return

    # Check if price is inside any H4 or D zone
    all_supply = h4_supply_zones + d_supply_zones
    all_demand = h4_demand_zones + d_demand_zones
    in_supply = _price_inside_zones(close, all_supply)
    in_demand = _price_inside_zones(close, all_demand)
    at_zone = in_supply or in_demand

    if not at_zone:
        # Reset edge tracking when not at zone
        state._prev_m5_bear_broken = m5_tl.bear_broken
        state._prev_m5_bull_broken = m5_tl.bull_broken
        return

    # M5 bear TL break (bullish break — high crosses above bear TL)
    # Edge: only fire on the transition from not-broken to broken
    m5_bear_break_edge = m5_tl.bear_broken and not state._prev_m5_bear_broken
    m5_bull_break_edge = m5_tl.bull_broken and not state._prev_m5_bull_broken

    # Update edge tracking
    state._prev_m5_bear_broken = m5_tl.bear_broken
    state._prev_m5_bull_broken = m5_tl.bull_broken

    # BULL CONFIRMATION: M5 bear TL breaks while at zone
    # Gated by terminal: don't flip bull when demand is exhausted
    if m5_bear_break_edge and not h1_dem_exhausted:
        if state.macro_bias != 1:
            state.macro_bias = 1
            state.bull_conf_fired = True
            state.bear_conf_fired = False
            if bus is not None:
                bus.emit(
                    EventID.BIAS_BULL_CONF,
                    bar_time,
                    "M5",
                    {
                        "trigger": "m5_bear_tl_break_at_zone",
                        "close": close,
                        "in_supply": in_supply,
                        "in_demand": in_demand,
                    },
                )

    # BEAR CONFIRMATION: M5 bull TL breaks while at zone
    # Gated by terminal: don't flip bear when supply is exhausted
    if m5_bull_break_edge and not h1_sup_exhausted:
        if state.macro_bias != -1:
            state.macro_bias = -1
            state.bear_conf_fired = True
            state.bull_conf_fired = False
            if bus is not None:
                bus.emit(
                    EventID.BIAS_BEAR_CONF,
                    bar_time,
                    "M5",
                    {
                        "trigger": "m5_bull_tl_break_at_zone",
                        "close": close,
                        "in_supply": in_supply,
                        "in_demand": in_demand,
                    },
                )
