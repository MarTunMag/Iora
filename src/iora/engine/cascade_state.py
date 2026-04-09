"""
Cascade State — per-bar D1→H4→H1 cascade phase classification.

Aggregates trendline breaks, zone counts, and trend directions into a
single phase that the sweep engine reads as a filter dimension.

Phases:
  - "d1_push": D1 and H4 aligned (strong push)
  - "h4_correction": H4 pulling back against D1
  - "h4_correction_tl_break": H4 correction TL broke (push resumes)
  - "h1_extended": H1 push zone count >= 5
  - "h1_terminal": H1 impulse TL broke (push is done)
  - "at_reversal_target": price near the H1 reversal target zone
  - "unknown": insufficient data

Integration:
  Called per-bar AFTER push_zone_engine_tick + push_trendline in the pipeline.
  Reads push zone tick states (trends, zones) and push trendline states (breaks).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.push_trendline import PushTrendlineState, PushTrendlineBreakEvent


@dataclass(slots=True)
class CascadePhaseState:
    """Per-bar cascade state machine tracking the D1→H4→H1 cascade."""

    # Trend per TF (from PushZoneTickState.trend)
    d1_trend: int = 0
    h4_trend: int = 0
    h1_trend: int = 0
    m15_trend: int = 0

    # TL break state per TF (True = intact, False = broken)
    h4_impulse_tl_intact: bool = True
    h4_correction_tl_intact: bool = True
    h1_impulse_tl_intact: bool = True
    h1_correction_tl_intact: bool = True
    m15_impulse_tl_intact: bool = True
    m15_correction_tl_intact: bool = True

    # Zone counting (H1 zones in current push direction)
    h1_push_zone_count: int = 0
    h1_push_direction: int = 0  # +1 counting supply (push up), -1 counting demand (push down)
    _prev_d1_trend: int = 0     # Track D1 trend changes for count reset

    # Reversal targets (from zone attribution)
    h1_reversal_target_top: float = float('nan')
    h1_reversal_target_bottom: float = float('nan')
    h4_reversal_target_top: float = float('nan')
    h4_reversal_target_bottom: float = float('nan')

    # EW-derived exhaustion signals (from H1 zone sequence during push)
    h1_zone1_top: float = float('nan')
    h1_zone1_bottom: float = float('nan')
    h1_zone1_range: float = float('nan')
    h1_zone3_range: float = float('nan')
    h1_zone4_overlaps_zone1: bool = False
    h1_wave3_extension_ratio: float = float('nan')
    _prev_h1_push_zone_count: int = 0
    _prev_h1_push_direction: int = 0

    # CHoCH conviction classification per TF
    # "strong" = next bar confirms break, "weak" = next bar reverses, "pre" = stalling, "" = none
    h4_last_choch_conviction: str = ""
    h1_last_choch_conviction: str = ""
    m15_last_choch_conviction: str = ""
    # Internal: pending CHoCH classification (need next bar to confirm)
    _h4_choch_pending: bool = False
    _h4_choch_direction: int = 0   # New trend direction after CHoCH
    _h4_choch_close: float = float('nan')
    _h1_choch_pending: bool = False
    _h1_choch_direction: int = 0
    _h1_choch_close: float = float('nan')
    _m15_choch_pending: bool = False
    _m15_choch_direction: int = 0
    _m15_choch_close: float = float('nan')
    # Internal: previous trends for change detection + stall counting
    _prev_h4_trend: int = 0
    _prev_h1_trend: int = 0
    _prev_m15_trend: int = 0
    _h4_bars_no_new_extreme: int = 0
    _h1_bars_no_new_extreme: int = 0
    _m15_bars_no_new_extreme: int = 0
    _h4_last_extreme: float = float('nan')
    _h1_last_extreme: float = float('nan')
    _m15_last_extreme: float = float('nan')

    # Momentum consumption count (child TFs aligned after H4 CHoCH)
    h4_consumption_count: int = 0     # 0-3: how many of [H1, M15, M5] match H4 direction
    h4_consumption_complete: bool = False  # True when all 3 flipped

    # TL break recency tracking (bars since last break, -1 = never broken)
    h4_impulse_bars_since_break: int = -1
    h4_correction_bars_since_break: int = -1
    h1_impulse_bars_since_break: int = -1
    h1_correction_bars_since_break: int = -1
    m15_impulse_bars_since_break: int = -1
    m15_correction_bars_since_break: int = -1

    # Structural overlap metrics (computed per-bar for candidate enrichment)
    pivot_cascade_depth: int = 0        # How many TFs confirm same direction
    fvg_at_candidate: bool = False      # Unfilled FVG overlaps candidate zone
    breaker_at_candidate: bool = False  # Breaker zone overlaps candidate zone

    # Phase classification
    phase: str = "unknown"

    # Break events collected this bar (for sweep access)
    bar_tl_events: list[PushTrendlineBreakEvent] = field(default_factory=list)


def cascade_state_tick(
    state: CascadePhaseState,
    push_zone_states: dict[str, PushZoneTickState],
    tl_states: dict[str, PushTrendlineState],
    tl_events: dict[str, list[PushTrendlineBreakEvent]],
    bar_close: float,
) -> str:
    """Update cascade state and return current phase.

    Args:
        state: Mutable cascade state.
        push_zone_states: Per-TF push zone tick states (trends + zones).
        tl_states: Per-TF push trendline states.
        tl_events: Per-TF trendline break events this bar.
        bar_close: Current bar close price.

    Returns:
        Current phase string.
    """
    # --- 1. Update trends from push zone states ---
    state.d1_trend = push_zone_states["D1"].trend if "D1" in push_zone_states else 0
    state.h4_trend = push_zone_states["H4"].trend if "H4" in push_zone_states else 0
    state.h1_trend = push_zone_states["H1"].trend if "H1" in push_zone_states else 0
    state.m15_trend = push_zone_states["M15"].trend if "M15" in push_zone_states else 0
    m5_trend = push_zone_states["M5"].trend if "M5" in push_zone_states else 0

    # --- 2. Update TL break states ---
    state.bar_tl_events = []
    # Increment bars-since-break counters (only for those that have broken)
    for attr in ("h4_impulse_bars_since_break", "h4_correction_bars_since_break",
                 "h1_impulse_bars_since_break", "h1_correction_bars_since_break",
                 "m15_impulse_bars_since_break", "m15_correction_bars_since_break"):
        val = getattr(state, attr)
        if val >= 0:
            setattr(state, attr, val + 1)
    for tf_key, events in tl_events.items():
        for ev in events:
            state.bar_tl_events.append(ev)
            _apply_tl_break(state, ev, tf_key)

    # --- 3. H1 zone counting ---
    _update_h1_zone_count(state, push_zone_states)

    # --- 4. Update reversal targets ---
    _update_reversal_targets(state, push_zone_states)

    # --- 5. CHoCH conviction classification ---
    _update_choch_conviction(state, bar_close)

    # --- 6. Momentum consumption count ---
    _update_consumption_count(state, m5_trend)

    # --- 7. Phase classification ---
    state.phase = _classify_phase(state, bar_close)

    return state.phase


def _apply_tl_break(
    state: CascadePhaseState,
    ev: PushTrendlineBreakEvent,
    tf: str,
) -> None:
    """Apply a TL break event to the cascade state."""
    if tf == "H4":
        if ev.tl_type == "impulse":
            state.h4_impulse_tl_intact = False
            state.h4_impulse_bars_since_break = 0
        elif ev.tl_type == "correction":
            state.h4_correction_tl_intact = False
            state.h4_correction_bars_since_break = 0
    elif tf == "H1":
        if ev.tl_type == "impulse":
            state.h1_impulse_tl_intact = False
            state.h1_impulse_bars_since_break = 0
        elif ev.tl_type == "correction":
            state.h1_correction_tl_intact = False
            state.h1_correction_bars_since_break = 0
    elif tf == "M15":
        if ev.tl_type == "impulse":
            state.m15_impulse_tl_intact = False
            state.m15_impulse_bars_since_break = 0
        elif ev.tl_type == "correction":
            state.m15_correction_tl_intact = False
            state.m15_correction_bars_since_break = 0


def _update_h1_zone_count(
    state: CascadePhaseState,
    push_zone_states: dict[str, PushZoneTickState],
) -> None:
    """Count H1 zones in current push direction. Compute EW exhaustion signals."""
    # Reset on D1 trend change
    if state.d1_trend != state._prev_d1_trend and state._prev_d1_trend != 0:
        state.h1_push_zone_count = 0
        state.h1_push_direction = 0
        _reset_ew_fields(state)
        # Reset TL intact states and recency counters on new cycle
        state.h1_impulse_tl_intact = True
        state.h1_correction_tl_intact = True
        state.h4_impulse_tl_intact = True
        state.h4_correction_tl_intact = True
        state.h4_impulse_bars_since_break = -1
        state.h4_correction_bars_since_break = -1
        state.h1_impulse_bars_since_break = -1
        state.h1_correction_bars_since_break = -1
        state.m15_impulse_bars_since_break = -1
        state.m15_correction_bars_since_break = -1
    state._prev_d1_trend = state.d1_trend

    h1_ts = push_zone_states.get("H1")
    if h1_ts is None:
        return

    old_count = state.h1_push_zone_count
    old_direction = state.h1_push_direction

    if state.d1_trend == -1:
        state.h1_push_direction = -1
        state.h1_push_zone_count = h1_ts.sup_count
    elif state.d1_trend == 1:
        state.h1_push_direction = 1
        state.h1_push_zone_count = h1_ts.dem_count
    else:
        state.h1_push_zone_count = 0
        state.h1_push_direction = 0

    # Reset EW fields on push direction change
    if state.h1_push_direction != old_direction and old_direction != 0:
        _reset_ew_fields(state)

    # EW computations on zone count increment
    if state.h1_push_zone_count > old_count:
        _update_ew_signals(state, h1_ts)


def _reset_ew_fields(state: CascadePhaseState) -> None:
    """Reset EW-derived fields for a new push cycle."""
    state.h1_zone1_top = float('nan')
    state.h1_zone1_bottom = float('nan')
    state.h1_zone1_range = float('nan')
    state.h1_zone3_range = float('nan')
    state.h1_zone4_overlaps_zone1 = False
    state.h1_wave3_extension_ratio = float('nan')
    state._prev_h1_push_zone_count = 0


def _update_ew_signals(
    state: CascadePhaseState,
    h1_ts: PushZoneTickState,
) -> None:
    """Compute EW exhaustion signals from H1 zone sequence."""
    count = state.h1_push_zone_count
    is_bearish = state.h1_push_direction == -1
    zones = h1_ts.supply_zones if is_bearish else h1_ts.demand_zones

    if not zones:
        return

    current_zone = zones[-1]  # Most recently created

    if count == 1:
        state.h1_zone1_top = current_zone.top
        state.h1_zone1_bottom = current_zone.bottom
        state.h1_zone1_range = current_zone.top - current_zone.bottom

    elif count == 3 and not isnan(state.h1_zone1_range) and state.h1_zone1_range > 0:
        # Zone 3 range: push distance from zone 2 to zone 3
        # For bearish: price distance from zone 2 bottom to zone 3 bottom (going lower)
        # For bullish: price distance from zone 2 top to zone 3 top (going higher)
        if len(zones) >= 2:
            zone2 = zones[-2]
            if is_bearish:
                state.h1_zone3_range = abs(zone2.bottom - current_zone.bottom)
            else:
                state.h1_zone3_range = abs(current_zone.top - zone2.top)
            if state.h1_zone3_range > 0:
                state.h1_wave3_extension_ratio = state.h1_zone3_range / state.h1_zone1_range

    if count >= 4 and not isnan(state.h1_zone1_top):
        # Check wave 4 overlap with zone 1
        if is_bearish:
            # Supply zones going lower: overlap if current top > zone1 bottom
            state.h1_zone4_overlaps_zone1 = current_zone.top > state.h1_zone1_bottom
        else:
            # Demand zones going higher: overlap if current bottom < zone1 top
            state.h1_zone4_overlaps_zone1 = current_zone.bottom < state.h1_zone1_top

    state._prev_h1_push_zone_count = count


def _update_reversal_targets(
    state: CascadePhaseState,
    push_zone_states: dict[str, PushZoneTickState],
) -> None:
    """Find zones tagged with caused_bos_choch and set as reversal targets.

    Important: Only UPDATE targets when a tagged zone is found — never clear
    existing targets. The causing zone may get broken (removed from the list)
    before the entry fires, but the reversal target coordinates remain valid.
    Targets are reset when D1 trend changes (handled by _update_h1_zone_count).
    """
    h1_ts = push_zone_states.get("H1")
    if h1_ts is not None:
        for z in reversed(h1_ts.supply_zones + h1_ts.demand_zones):
            if z.caused_bos_choch == "CHoCH":
                state.h1_reversal_target_top = z.top
                state.h1_reversal_target_bottom = z.bottom
                break

    h4_ts = push_zone_states.get("H4")
    if h4_ts is not None:
        for z in reversed(h4_ts.supply_zones + h4_ts.demand_zones):
            if z.caused_bos_choch == "CHoCH":
                state.h4_reversal_target_top = z.top
                state.h4_reversal_target_bottom = z.bottom
                break


def _update_choch_conviction(state: CascadePhaseState, bar_close: float) -> None:
    """Classify CHoCH conviction per TF: strong, weak, or pre.

    Logic:
    - Detect trend change → mark pending CHoCH with close + direction.
    - Next bar: if close continues in break direction → "strong";
      if close reverses → "weak".
    - "pre": no CHoCH but 2+ bars with no new HH/LL (momentum stalling).
    """
    for tf_label in ("H4", "H1", "M15"):
        prev_attr = f"_prev_{tf_label.lower()}_trend"
        pending_attr = f"_{tf_label.lower()}_choch_pending"
        dir_attr = f"_{tf_label.lower()}_choch_direction"
        close_attr = f"_{tf_label.lower()}_choch_close"
        conv_attr = f"{tf_label.lower()}_last_choch_conviction"
        stall_attr = f"_{tf_label.lower()}_bars_no_new_extreme"
        extreme_attr = f"_{tf_label.lower()}_last_extreme"

        current_trend = getattr(state, f"{tf_label.lower()}_trend")
        prev_trend = getattr(state, prev_attr)

        # --- Resolve pending CHoCH from previous bar ---
        if getattr(state, pending_attr):
            choch_dir = getattr(state, dir_attr)
            choch_close = getattr(state, close_attr)
            if choch_dir == 1:
                # Bullish CHoCH: strong if close > choch bar close
                setattr(state, conv_attr,
                        "strong" if bar_close > choch_close else "weak")
            elif choch_dir == -1:
                # Bearish CHoCH: strong if close < choch bar close
                setattr(state, conv_attr,
                        "strong" if bar_close < choch_close else "weak")
            setattr(state, pending_attr, False)

        # --- Detect new CHoCH (trend change) ---
        if current_trend != prev_trend and prev_trend != 0 and current_trend != 0:
            # Trend flipped → CHoCH fired
            setattr(state, pending_attr, True)
            setattr(state, dir_attr, current_trend)
            setattr(state, close_attr, bar_close)
            # Reset stall counter
            setattr(state, stall_attr, 0)
            setattr(state, extreme_attr, bar_close)
        else:
            # --- "pre" detection: stalling momentum ---
            prev_extreme = getattr(state, extreme_attr)
            if current_trend == 1:
                # Bullish: track if price makes new highs
                if not isnan(prev_extreme) and bar_close > prev_extreme:
                    setattr(state, stall_attr, 0)
                    setattr(state, extreme_attr, bar_close)
                else:
                    setattr(state, stall_attr, getattr(state, stall_attr) + 1)
                    if isnan(prev_extreme):
                        setattr(state, extreme_attr, bar_close)
            elif current_trend == -1:
                # Bearish: track if price makes new lows
                if not isnan(prev_extreme) and bar_close < prev_extreme:
                    setattr(state, stall_attr, 0)
                    setattr(state, extreme_attr, bar_close)
                else:
                    setattr(state, stall_attr, getattr(state, stall_attr) + 1)
                    if isnan(prev_extreme):
                        setattr(state, extreme_attr, bar_close)

            # If stalling for 2+ bars and no pending CHoCH, mark as "pre"
            if getattr(state, stall_attr) >= 2 and not getattr(state, pending_attr):
                conv = getattr(state, conv_attr)
                if conv not in ("strong", "weak"):
                    setattr(state, conv_attr, "pre")

        setattr(state, prev_attr, current_trend)


def _update_consumption_count(state: CascadePhaseState, m5_trend: int) -> None:
    """Count how many child TFs (H1, M15, M5) match H4 trend direction.

    Resets to 0 when H4 trend changes.
    """
    if state.h4_trend == 0:
        state.h4_consumption_count = 0
        state.h4_consumption_complete = False
        return

    count = 0
    if state.h1_trend == state.h4_trend:
        count += 1
    if state.m15_trend == state.h4_trend:
        count += 1
    if m5_trend == state.h4_trend:
        count += 1

    state.h4_consumption_count = count
    state.h4_consumption_complete = (count == 3)


def _classify_phase(state: CascadePhaseState, bar_close: float) -> str:
    """Classify the current cascade phase.

    Priority order (highest first):
      1. at_reversal_target (price near reversal zone + terminal)
      2. h1_terminal (impulse TL broke)
      3. h1_extended (5+ zones)
      4. h4_correction_tl_break (correction TL broke = push resumes)
      5. h4_correction (H4 against D1)
      6. d1_push (D1 and H4 aligned)
      7. unknown
    """
    if state.d1_trend == 0:
        return "unknown"

    # Check terminal + at reversal target (lower threshold: zone_count >= 3)
    if not state.h1_impulse_tl_intact and state.h1_push_zone_count >= 3:
        # Is price near a reversal target?
        if _price_near_zone(bar_close, state.h1_reversal_target_top, state.h1_reversal_target_bottom):
            return "at_reversal_target"
        return "h1_terminal"

    # H1 extended push (zone_count >= 4 — lowered from 5 based on data)
    if state.h1_push_zone_count >= 4:
        return "h1_extended"

    # H4 vs D1 alignment
    if state.h4_trend != 0 and state.h4_trend != state.d1_trend:
        # H4 correction
        if not state.h4_correction_tl_intact:
            return "h4_correction_tl_break"
        return "h4_correction"

    if state.d1_trend != 0 and state.h4_trend == state.d1_trend:
        return "d1_push"

    return "unknown"


def _price_near_zone(price: float, zone_top: float, zone_bottom: float) -> bool:
    """Check if price is within or very near a zone (within 1 zone height)."""
    if isnan(zone_top) or isnan(zone_bottom):
        return False
    zone_height = zone_top - zone_bottom
    if zone_height <= 0:
        return False
    return (zone_bottom - zone_height) <= price <= (zone_top + zone_height)
