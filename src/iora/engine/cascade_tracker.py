"""
Cascade Tracker — Cross-TF push/pullback detection via trendline cascades.

Implements the fractal cascade framework from STRATEGY_SPEC.md:

  TL Break Confirmation Chain (each level confirms the one above):
    M5 TL break  → M15 sub-wave complete
    M15 TL break → H1 push complete
    H1 TL break  → H4 push complete
    H4 TL break  → D leg complete

  Fractal Zone Ratio (3:1):
    3× M1 zones = 1 M5 zone
    3× M5 zones = 1 M15 zone
    3× M15 zones = 1 H1 zone

  5+3 Exhaustion:
    5 impulse zones + 3 correction zones at H1 = terminal exhaustion
    → H4 reversal expected

  Early Reversal Detection:
    M1 CHOCH = earliest signal of direction change
    M1 LL inside M5 supply = M5 LH forming (early confirmation)
    Cascade propagation: M1→M5→M15 confirms H1 push ending

Integration:
  Called per-bar AFTER zone_engine_tick + structure_tick in the pipeline.
  Reads TL states, zone states, structure counts, and events.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.models import FractalZone, EventID
from iora.engine.trendline_tick import TrendlineTickState
from iora.engine.structure_count import StructureCountState


# TF hierarchy from lowest to highest
TF_HIERARCHY = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]
_TF_INDEX = {tf: i for i, tf in enumerate(TF_HIERARCHY)}

# TL break at child TF confirms completion at parent TF
_TL_BREAK_CONFIRMS = {
    "M5": "M15",   # M5 TL break → M15 sub-wave complete
    "M15": "H1",   # M15 TL break → H1 push complete
    "H1": "H4",    # H1 TL break → H4 push complete
    "H4": "D1",    # H4 TL break → D leg complete
}


def _parent_tf(tf: str) -> str | None:
    """Return the next higher TF, or None if already at W1."""
    idx = _TF_INDEX.get(tf)
    if idx is None or idx >= len(TF_HIERARCHY) - 1:
        return None
    return TF_HIERARCHY[idx + 1]


def _child_tf(tf: str) -> str | None:
    """Return the next lower TF, or None if already at M1."""
    idx = _TF_INDEX.get(tf)
    if idx is None or idx <= 0:
        return None
    return TF_HIERARCHY[idx - 1]


@dataclass(slots=True)
class PushState:
    """Active push state for a single TF."""

    direction: str = "none"  # "bull" | "bear" | "none"
    start_time: pd.Timestamp | None = None
    start_price: float | None = None
    cascade_depth: int = 0  # how many child TFs have confirmed


@dataclass(slots=True)
class ZoneLegCount:
    """
    Tracks zone counts per TF for the fractal 3:1 ratio.

    When a child TF accumulates 3 zones in one direction, it signals
    one complete leg at the parent TF level.
    """
    sup_count: int = 0  # unbroken supply zones since last reset
    dem_count: int = 0  # unbroken demand zones since last reset
    # Legs completed toward parent TF (each = 3 child zones)
    sup_legs: int = 0
    dem_legs: int = 0


@dataclass(slots=True)
class CascadeSignal:
    """A cascade event detected by the tracker."""

    time: pd.Timestamp
    signal_type: str
    tf: str  # TF where the signal originated
    direction: str  # "bull" | "bear"
    target: str  # HTF structural target (e.g., "D1_HL", "W1_HH")
    details: str  # Human-readable description
    parent_tf: str = ""  # parent TF affected (if applicable)
    priority: int = 3  # 1=highest, 2=important, 3=informational


# Signal types
SIGNAL_TYPES = {
    "tl_break_confirms",  # TL break at child confirms parent TF completion
    "cascade_up",         # push direction cascaded to next higher TF
    "cascade_reversal",   # CHOCH inside HTF zone — reversal starting
    "early_reversal",     # M1/M5 LL/HH inside parent zone — early parent LH/HL signal
    "push_ending",        # cascade reversal propagated through 3+ TFs
    "push_confirmed",     # push confirmed by cascade depth >= 2
    "leg_complete",       # 3 child zones = 1 parent leg (fractal 3:1)
    "exhaustion",         # 5+3 zone exhaustion reached
}


def _signal_priority(signal_type: str, tf: str) -> int:
    """
    Compute signal priority: 1=highest, 2=important, 3=informational.

    Priority 1: cascade_reversal, early_reversal at H1+
    Priority 2: early_reversal at M15, push_ending, exhaustion
    Priority 3: tl_break_confirms, leg_complete, cascade_up, push_confirmed
    """
    if signal_type == "cascade_reversal":
        return 1
    if signal_type == "early_reversal":
        idx = _TF_INDEX.get(tf, 0)
        # H1 and above (idx >= 3) → priority 1, M15 → priority 2, below → priority 3
        if idx >= _TF_INDEX["H1"]:
            return 1
        if tf == "M15":
            return 2
        return 3
    if signal_type in ("push_ending", "exhaustion"):
        return 2
    # tl_break_confirms, leg_complete, cascade_up, push_confirmed
    return 3


@dataclass(slots=True)
class CascadeTrackerState:
    """Full mutable state for the cascade tracker."""

    # Per-TF push state (derived from active TLs)
    push_states: dict[str, PushState] = field(default_factory=dict)

    # Per-TF zone leg counting (for 3:1 fractal ratio)
    zone_leg_counts: dict[str, ZoneLegCount] = field(default_factory=dict)

    # TL break tracking: which TF TLs were broken on previous bar
    prev_tl_broken: dict[str, tuple[bool, bool]] = field(default_factory=dict)
    # (bear_broken, bull_broken) per TF

    # Cascade reversal tracking: which TFs have seen CHOCH in current reversal
    reversal_chain: list[str] = field(default_factory=list)
    reversal_direction: str = "none"

    # Accumulated signals
    signals: list[CascadeSignal] = field(default_factory=list)

    # Current structural targets
    bull_target: str = ""
    bear_target: str = ""

    # Edge-triggering: exhaustion (Phase 5) — only fire on transition
    _prev_exhaustion_bull: bool = False
    _prev_exhaustion_bear: bool = False

    # Edge-triggering: push_ending (Phase 6) — only fire once per chain
    _push_ending_fired: bool = False


def init_cascade_state(tf_list: list[str] | None = None) -> CascadeTrackerState:
    """Create fresh cascade tracker state."""
    if tf_list is None:
        tf_list = list(TF_HIERARCHY)
    valid_tfs = [tf for tf in tf_list if tf in _TF_INDEX]
    return CascadeTrackerState(
        push_states={tf: PushState() for tf in valid_tfs},
        zone_leg_counts={tf: ZoneLegCount() for tf in valid_tfs},
        prev_tl_broken={tf: (False, False) for tf in valid_tfs},
    )


def _derive_push_direction(tl_state: TrendlineTickState) -> str:
    """Derive push direction from TL state."""
    bear_active = tl_state.bear_active is not None and not tl_state.bear_broken
    bull_active = tl_state.bull_active is not None and not tl_state.bull_broken

    if bear_active and not bull_active:
        return "bear"
    if bull_active and not bear_active:
        return "bull"
    if bear_active and bull_active:
        bear_t2 = tl_state.bear_active.t2
        bull_t2 = tl_state.bull_active.t2
        return "bear" if bear_t2 >= bull_t2 else "bull"
    return "none"


def _structural_target(
    d_structure: StructureCountState | None,
    w_structure: StructureCountState | None,
) -> tuple[str, str]:
    """Derive (bull_target, bear_target) from D/W structure phase."""
    bull_target = ""
    bear_target = ""

    if d_structure is not None:
        phase = d_structure.phase
        if "HH" in phase:
            bull_target = "D1_HL"
            bear_target = "D1_LH"
        elif "LL" in phase:
            bear_target = "D1_LH"
            bull_target = "D1_HL"
        elif "HL" in phase:
            bull_target = "D1_HH"
            bear_target = "D1_LL"
        elif "LH" in phase:
            bear_target = "D1_LL"
            bull_target = "D1_HH"

    if w_structure is not None:
        w_phase = w_structure.phase
        if "HH" in w_phase:
            bull_target = f"W1_HL>{bull_target}" if bull_target else "W1_HL"
        elif "LL" in w_phase:
            bear_target = f"W1_LH>{bear_target}" if bear_target else "W1_LH"
        elif "HL" in w_phase:
            bull_target = f"W1_HH>{bull_target}" if bull_target else "W1_HH"
        elif "LH" in w_phase:
            bear_target = f"W1_LL>{bear_target}" if bear_target else "W1_LL"

    return bull_target, bear_target


def _price_in_zones(
    price: float,
    zones: list[FractalZone],
    is_supply: bool,
) -> FractalZone | None:
    """Return the first unbroken zone of the given side containing price."""
    for z in reversed(zones):
        if z.is_supply == is_supply and not z.is_broken and z.contains_price(price):
            return z
    return None


def cascade_tick(
    state: CascadeTrackerState,
    tl_states: dict[str, TrendlineTickState],
    zone_states: dict[str, object],  # ZoneTickState per TF
    d_structure: StructureCountState | None,
    w_structure: StructureCountState | None,
    bar_close: float,
    bar_high: float,
    bar_low: float,
    bar_time: pd.Timestamp,
    events: list,
) -> None:
    """
    Process one bar through the cascade tracker.

    Must be called AFTER zone_engine_tick + structure_tick so TL/zone states are current.
    Mutates ``state`` in place.
    """
    # Update structural targets
    bull_target, bear_target = _structural_target(d_structure, w_structure)
    state.bull_target = bull_target
    state.bear_target = bear_target

    # ──────────────────────────────────────────────────────────────────────
    # Phase 1: Update push direction per TF from TL states
    # ──────────────────────────────────────────────────────────────────────
    prev_directions: dict[str, str] = {}
    for tf in state.push_states:
        prev_directions[tf] = state.push_states[tf].direction
        tl_st = tl_states.get(tf)
        if tl_st is None:
            continue

        new_dir = _derive_push_direction(tl_st)
        push = state.push_states[tf]

        if new_dir != push.direction:
            push.direction = new_dir
            push.start_time = bar_time
            push.start_price = bar_close
            push.cascade_depth = 0

    # ──────────────────────────────────────────────────────────────────────
    # Phase 2: TL break confirmation chain
    # M5 break → M15 complete, M15 break → H1 complete, etc.
    # ──────────────────────────────────────────────────────────────────────
    for tf in state.push_states:
        tl_st = tl_states.get(tf)
        if tl_st is None:
            continue

        prev_bear_broken, prev_bull_broken = state.prev_tl_broken.get(tf, (False, False))
        curr_bear_broken = tl_st.bear_broken
        curr_bull_broken = tl_st.bull_broken

        # Detect NEW breaks (edge trigger)
        bear_break_edge = curr_bear_broken and not prev_bear_broken
        bull_break_edge = curr_bull_broken and not prev_bull_broken

        # Save for next bar
        state.prev_tl_broken[tf] = (curr_bear_broken, curr_bull_broken)

        confirms_tf = _TL_BREAK_CONFIRMS.get(tf)
        if confirms_tf is None:
            continue

        if bear_break_edge:
            # Bear TL broken = bullish break → confirms parent TF bullish completion
            target = bull_target
            state.signals.append(
                CascadeSignal(
                    time=bar_time,
                    signal_type="tl_break_confirms",
                    tf=tf,
                    direction="bull",
                    target=target,
                    details=(
                        f"{tf} bear TL broken → {confirms_tf} bullish leg complete, "
                        f"target {target}"
                    ),
                    parent_tf=confirms_tf,
                    priority=_signal_priority("tl_break_confirms", tf),
                )
            )

        if bull_break_edge:
            # Bull TL broken = bearish break → confirms parent TF bearish completion
            target = bear_target
            state.signals.append(
                CascadeSignal(
                    time=bar_time,
                    signal_type="tl_break_confirms",
                    tf=tf,
                    direction="bear",
                    target=target,
                    details=(
                        f"{tf} bull TL broken → {confirms_tf} bearish leg complete, "
                        f"target {target}"
                    ),
                    parent_tf=confirms_tf,
                    priority=_signal_priority("tl_break_confirms", tf),
                )
            )

    # ──────────────────────────────────────────────────────────────────────
    # Phase 3: Cascade-up detection (push direction propagating upward)
    # ──────────────────────────────────────────────────────────────────────
    for tf in state.push_states:
        push = state.push_states[tf]
        prev_dir = prev_directions.get(tf, "none")

        if push.direction == "none" or push.direction == prev_dir:
            continue

        parent = _parent_tf(tf)
        if parent and parent in state.push_states:
            parent_push = state.push_states[parent]
            if parent_push.direction == push.direction:
                parent_push.cascade_depth = max(
                    parent_push.cascade_depth,
                    push.cascade_depth + 1,
                )
                target = bull_target if push.direction == "bull" else bear_target
                state.signals.append(
                    CascadeSignal(
                        time=bar_time,
                        signal_type="cascade_up",
                        tf=tf,
                        direction=push.direction,
                        target=target,
                        details=(
                            f"{tf} {push.direction} aligns with {parent} — "
                            f"cascade depth {parent_push.cascade_depth}, "
                            f"target {target}"
                        ),
                        parent_tf=parent,
                        priority=_signal_priority("cascade_up", tf),
                    )
                )

    # ──────────────────────────────────────────────────────────────────────
    # Phase 4: Zone events — fractal 3:1 counting + early reversal detection
    # ──────────────────────────────────────────────────────────────────────
    for ev in events:
        if ev.id == EventID.ZONE_FIRE:
            # New zone created — count toward parent TF leg
            ev_tf = ev.timeframe
            payload = ev.payload
            side = payload.get("side")  # "supply" or "demand"

            lc = state.zone_leg_counts.get(ev_tf)
            if lc is not None:
                if side == "supply":
                    lc.sup_count += 1
                    if lc.sup_count >= 3:
                        lc.sup_legs += 1
                        lc.sup_count = 0
                        parent = _parent_tf(ev_tf)
                        if parent:
                            state.signals.append(
                                CascadeSignal(
                                    time=bar_time,
                                    signal_type="leg_complete",
                                    tf=ev_tf,
                                    direction="bear",
                                    target=bear_target,
                                    details=(
                                        f"3× {ev_tf} supply = 1 {parent} bearish leg "
                                        f"(leg #{lc.sup_legs})"
                                    ),
                                    parent_tf=parent,
                                    priority=_signal_priority("leg_complete", ev_tf),
                                )
                            )
                elif side == "demand":
                    lc.dem_count += 1
                    if lc.dem_count >= 3:
                        lc.dem_legs += 1
                        lc.dem_count = 0
                        parent = _parent_tf(ev_tf)
                        if parent:
                            state.signals.append(
                                CascadeSignal(
                                    time=bar_time,
                                    signal_type="leg_complete",
                                    tf=ev_tf,
                                    direction="bull",
                                    target=bull_target,
                                    details=(
                                        f"3× {ev_tf} demand = 1 {parent} bullish leg "
                                        f"(leg #{lc.dem_legs})"
                                    ),
                                    parent_tf=parent,
                                    priority=_signal_priority("leg_complete", ev_tf),
                                )
                            )

        elif ev.id == EventID.ZONE_BREAK:
            payload = ev.payload
            side = payload.get("side")
            is_hh_or_ll = payload.get("is_hh_or_ll", False)
            ev_tf = ev.timeframe
            is_choch = not is_hh_or_ll

            # ── Early reversal: LL/HH inside parent zone ──
            # M1 LL inside M5 supply = early M5 LH signal
            # M5 HH inside M15 demand = early M15 HL signal
            if is_hh_or_ll:
                parent = _parent_tf(ev_tf)
                if parent:
                    parent_zs = zone_states.get(parent)
                    if parent_zs is not None:
                        if side == "demand":
                            # Demand broken bearishly with LL → check if inside parent supply
                            sup_zones = getattr(parent_zs, "supply_zones", [])
                            zone = _price_in_zones(bar_close, sup_zones, is_supply=True)
                            if zone is not None:
                                state.signals.append(
                                    CascadeSignal(
                                        time=bar_time,
                                        signal_type="early_reversal",
                                        tf=ev_tf,
                                        direction="bear",
                                        target=bear_target,
                                        details=(
                                            f"{ev_tf} LL inside {parent} supply "
                                            f"({zone.bot:.5f}-{zone.top:.5f}) — "
                                            f"early {parent} LH signal"
                                        ),
                                        parent_tf=parent,
                                        priority=_signal_priority("early_reversal", ev_tf),
                                    )
                                )
                        elif side == "supply":
                            # Supply broken bullishly with HH → check if inside parent demand
                            dem_zones = getattr(parent_zs, "demand_zones", [])
                            zone = _price_in_zones(bar_close, dem_zones, is_supply=False)
                            if zone is not None:
                                state.signals.append(
                                    CascadeSignal(
                                        time=bar_time,
                                        signal_type="early_reversal",
                                        tf=ev_tf,
                                        direction="bull",
                                        target=bull_target,
                                        details=(
                                            f"{ev_tf} HH inside {parent} demand "
                                            f"({zone.bot:.5f}-{zone.top:.5f}) — "
                                            f"early {parent} HL signal"
                                        ),
                                        parent_tf=parent,
                                        priority=_signal_priority("early_reversal", ev_tf),
                                    )
                                )

            # ── CHOCH inside HTF zone = cascade reversal ──
            if is_choch:
                choch_direction = "bull" if side == "supply" else "bear"

                parent = _parent_tf(ev_tf)
                while parent:
                    parent_zs = zone_states.get(parent)
                    if parent_zs is not None:
                        sup_zones = getattr(parent_zs, "supply_zones", [])
                        dem_zones = getattr(parent_zs, "demand_zones", [])

                        if choch_direction == "bull":
                            zone = _price_in_zones(bar_close, sup_zones, is_supply=True)
                        else:
                            zone = _price_in_zones(bar_close, dem_zones, is_supply=False)

                        if zone is not None:
                            target = bull_target if choch_direction == "bull" else bear_target
                            state.signals.append(
                                CascadeSignal(
                                    time=bar_time,
                                    signal_type="cascade_reversal",
                                    tf=ev_tf,
                                    direction=choch_direction,
                                    target=target,
                                    details=(
                                        f"{ev_tf} {choch_direction} CHOCH inside "
                                        f"{parent} {'supply' if choch_direction == 'bull' else 'demand'} "
                                        f"({zone.bot:.5f}-{zone.top:.5f}) — "
                                        f"reversal starting, target {target}"
                                    ),
                                    parent_tf=parent,
                                    priority=_signal_priority("cascade_reversal", ev_tf),
                                )
                            )
                            # Track reversal chain
                            if state.reversal_direction != choch_direction:
                                state.reversal_chain = [ev_tf]
                                state.reversal_direction = choch_direction
                                state._push_ending_fired = False  # reset for new chain
                            elif ev_tf not in state.reversal_chain:
                                state.reversal_chain.append(ev_tf)
                            break

                    parent = _parent_tf(parent)

    # ──────────────────────────────────────────────────────────────────────
    # Phase 5: 5+3 exhaustion detection (H1 zones toward H4 reversal)
    # Edge-triggered: only fire when transitioning from non-exhausted to exhausted.
    # ──────────────────────────────────────────────────────────────────────
    h1_zs = zone_states.get("H1")
    curr_exhaustion_bull = False
    curr_exhaustion_bear = False

    if h1_zs is not None:
        h1_sup = getattr(h1_zs, "supply_zones", [])
        h1_dem = getattr(h1_zs, "demand_zones", [])
        h1_unbroken_sup = sum(1 for z in h1_sup if not z.is_broken)
        h1_unbroken_dem = sum(1 for z in h1_dem if not z.is_broken)

        # 5+ unbroken H1 supply = bearish impulse exhaustion
        if h1_unbroken_sup >= 5:
            h4_zs = zone_states.get("H4")
            if h4_zs is not None:
                h4_dem = getattr(h4_zs, "demand_zones", [])
                h4_zone = _price_in_zones(bar_close, h4_dem, is_supply=False)
                if h4_zone is not None:
                    curr_exhaustion_bull = True
                    if not state._prev_exhaustion_bull:
                        state.signals.append(
                            CascadeSignal(
                                time=bar_time,
                                signal_type="exhaustion",
                                tf="H1",
                                direction="bull",
                                target=bull_target,
                                details=(
                                    f"H1 bearish exhaustion: {h1_unbroken_sup} unbroken supply "
                                    f"inside H4 demand ({h4_zone.bot:.5f}-{h4_zone.top:.5f}) — "
                                    f"H4 reversal expected"
                                ),
                                parent_tf="H4",
                                priority=_signal_priority("exhaustion", "H1"),
                            )
                        )

        # 5+ unbroken H1 demand = bullish impulse exhaustion
        if h1_unbroken_dem >= 5:
            h4_zs = zone_states.get("H4")
            if h4_zs is not None:
                h4_sup = getattr(h4_zs, "supply_zones", [])
                h4_zone = _price_in_zones(bar_close, h4_sup, is_supply=True)
                if h4_zone is not None:
                    curr_exhaustion_bear = True
                    if not state._prev_exhaustion_bear:
                        state.signals.append(
                            CascadeSignal(
                                time=bar_time,
                                signal_type="exhaustion",
                                tf="H1",
                                direction="bear",
                                target=bear_target,
                                details=(
                                    f"H1 bullish exhaustion: {h1_unbroken_dem} unbroken demand "
                                    f"inside H4 supply ({h4_zone.bot:.5f}-{h4_zone.top:.5f}) — "
                                    f"H4 reversal expected"
                                ),
                                parent_tf="H4",
                                priority=_signal_priority("exhaustion", "H1"),
                            )
                        )

    state._prev_exhaustion_bull = curr_exhaustion_bull
    state._prev_exhaustion_bear = curr_exhaustion_bear

    # ──────────────────────────────────────────────────────────────────────
    # Phase 6: Push ending (reversal cascaded through 3+ TFs)
    # Only fire once when reversal_chain first reaches 3+ TFs.
    # Reset _push_ending_fired when reversal_chain resets (direction change).
    # ──────────────────────────────────────────────────────────────────────
    if len(state.reversal_chain) >= 3 and not state._push_ending_fired:
        chain_str = "→".join(state.reversal_chain)
        target = (
            bull_target if state.reversal_direction == "bull" else bear_target
        )
        tf_for_signal = state.reversal_chain[-1]
        state.signals.append(
            CascadeSignal(
                time=bar_time,
                signal_type="push_ending",
                tf=tf_for_signal,
                direction=state.reversal_direction,
                target=target,
                details=(
                    f"Push ending: {chain_str} cascade reversal "
                    f"({state.reversal_direction}), target {target}"
                ),
                priority=_signal_priority("push_ending", tf_for_signal),
            )
        )
        state._push_ending_fired = True

    # ──────────────────────────────────────────────────────────────────────
    # Phase 7: Push confirmed (cascade depth >= 2)
    # ──────────────────────────────────────────────────────────────────────
    for tf in state.push_states:
        push = state.push_states[tf]
        if push.cascade_depth >= 2 and prev_directions.get(tf) != push.direction:
            target = bull_target if push.direction == "bull" else bear_target
            state.signals.append(
                CascadeSignal(
                    time=bar_time,
                    signal_type="push_confirmed",
                    tf=tf,
                    direction=push.direction,
                    target=target,
                    details=(
                        f"{tf} push confirmed: {push.direction} with "
                        f"cascade depth {push.cascade_depth}, target {target}"
                    ),
                    priority=_signal_priority("push_confirmed", tf),
                )
            )


def get_cascade_summary(state: CascadeTrackerState) -> dict:
    """
    Return a summary dict for visualization / compass display.
    """
    pushes = {}
    for tf in TF_HIERARCHY:
        ps = state.push_states.get(tf)
        if ps:
            pushes[tf] = {
                "direction": ps.direction,
                "cascade_depth": ps.cascade_depth,
                "start_time": ps.start_time,
            }

    # Zone leg counts for key TFs
    legs = {}
    for tf in ["M5", "M15", "H1"]:
        lc = state.zone_leg_counts.get(tf)
        if lc:
            legs[tf] = {
                "sup_count": lc.sup_count,
                "dem_count": lc.dem_count,
                "sup_legs": lc.sup_legs,
                "dem_legs": lc.dem_legs,
            }

    return {
        "pushes": pushes,
        "legs": legs,
        "bull_target": state.bull_target,
        "bear_target": state.bear_target,
        "reversal_chain": list(state.reversal_chain),
        "reversal_direction": state.reversal_direction,
        "signal_count": len(state.signals),
        "last_signals": [
            {
                "time": s.time,
                "type": s.signal_type,
                "tf": s.tf,
                "direction": s.direction,
                "target": s.target,
                "details": s.details,
                "parent_tf": s.parent_tf,
                "priority": s.priority,
            }
            for s in state.signals[-10:]  # last 10 signals
        ],
    }
