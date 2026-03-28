"""
HTF Bias — Top-down per-TF directional bias cascading from W1 to M5.

For each TF from W1 down to M5, derive a bias value:
  +1 (BULL): Structure bullish, active bull TL, push direction bullish
  -1 (BEAR): Structure bearish, active bear TL, push direction bearish
   0 (NEUTRAL): Conflicting signals or no clear direction

The bias at each TF is filtered by its parent: if D1 bias is BULL but W1
bias is BEAR, the D1 bias is capped at NEUTRAL (HTF overrides).

Exception: At HTF zone reversal areas, counter-parent entries are allowed
(this is where push endings happen).

Integration:
  Called per-bar AFTER cascade_tick in the Pulse pipeline.
  Reads TL states, zone states, structure counts, and push states.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iora.engine.trendline_tick import TrendlineTickState
from iora.engine.structure_count import StructureCountState
from iora.engine.cascade_tracker import (
    CascadeTrackerState,
)

# TFs for which we compute bias (W1 down to M5)
_BIAS_TFS = ["W1", "D1", "H4", "H1", "M15", "M5"]


@dataclass(slots=True)
class TFBias:
    """Bias state for a single timeframe."""

    raw_bias: int = 0  # Unfiltered bias from this TF's own structure
    filtered_bias: int = 0  # After applying parent TF filter
    confidence: int = 0  # 0-3: how many factors agree (structure, TL, push)
    context: str = ""  # Human-readable (e.g., "D1: HH→expect HL, bull TL active")


@dataclass(slots=True)
class HTFBiasState:
    """Per-TF bias cascading from W1 down to M5."""

    biases: dict[str, TFBias] = field(default_factory=dict)

    # Derived convenience fields
    trade_direction: int = 0  # Net bias: +1=longs only, -1=shorts only, 0=both
    reversal_zone_tf: str = ""  # HTF where price is at reversal zone
    reversal_zone_side: str = ""  # "supply" or "demand"


def _structure_bias(
    d_structure: StructureCountState | None,
    w_structure: StructureCountState | None,
    tf: str,
) -> int:
    """
    Derive bias from structural counting for a given TF.

    After HH → expect HL → BULL (+1)
    After LL → expect LH → BEAR (-1)
    After HL → expect HH → BULL (+1)
    After LH → expect LL → BEAR (-1)
    """
    struct = None
    if tf == "W1" and w_structure is not None:
        struct = w_structure
    elif tf == "D1" and d_structure is not None:
        struct = d_structure

    if struct is None:
        return 0

    phase = struct.phase
    if "HH" in phase or "HL" in phase:
        return 1
    if "LL" in phase or "LH" in phase:
        return -1
    return 0


def _tl_bias(tl_states: dict[str, TrendlineTickState], tf: str) -> int:
    """Derive bias from active trendlines at a given TF."""
    tl_st = tl_states.get(tf)
    if tl_st is None:
        return 0

    bull_active = tl_st.bull_active is not None and not tl_st.bull_broken
    bear_active = tl_st.bear_active is not None and not tl_st.bear_broken

    if bull_active and not bear_active:
        return 1
    if bear_active and not bull_active:
        return -1
    return 0


def _push_bias(cascade_state: CascadeTrackerState | None, tf: str) -> int:
    """Derive bias from push direction at a given TF."""
    if cascade_state is None:
        return 0
    ps = cascade_state.push_states.get(tf)
    if ps is None:
        return 0
    if ps.direction == "bull":
        return 1
    if ps.direction == "bear":
        return -1
    return 0


def _check_reversal_zone(
    price: float,
    zone_states: dict,
    tf: str,
) -> tuple[bool, str]:
    """
    Check if price is inside an unbroken zone at the given TF.

    Returns (is_in_zone, side) where side is "supply" or "demand".
    """
    zs = zone_states.get(tf)
    if zs is None:
        return False, ""

    for z in getattr(zs, "supply_zones", []):
        if not z.is_broken and z.contains_price(price):
            return True, "supply"
    for z in getattr(zs, "demand_zones", []):
        if not z.is_broken and z.contains_price(price):
            return True, "demand"
    return False, ""


def htf_bias_tick(
    state: HTFBiasState,
    tl_states: dict[str, TrendlineTickState],
    zone_states: dict,
    d_structure: StructureCountState | None,
    w_structure: StructureCountState | None,
    cascade_state: CascadeTrackerState | None,
    bar_close: float,
) -> None:
    """
    Compute per-TF bias cascading top-down from W1 to M5.

    Mutates ``state`` in place. Must be called AFTER cascade_tick.
    """
    # Ensure all bias TFs have entries
    for tf in _BIAS_TFS:
        if tf not in state.biases:
            state.biases[tf] = TFBias()

    # Check for reversal zone at HTF (H4+)
    reversal_tf = ""
    reversal_side = ""
    for tf in ["W1", "D1", "H4"]:
        in_zone, side = _check_reversal_zone(bar_close, zone_states, tf)
        if in_zone:
            reversal_tf = tf
            reversal_side = side
            break  # Highest TF wins

    state.reversal_zone_tf = reversal_tf
    state.reversal_zone_side = reversal_side

    # Compute raw bias per TF
    parent_filtered = 0  # Will cascade from highest to lowest
    first_tf = True

    for tf in _BIAS_TFS:
        tb = state.biases[tf]

        # Gather bias signals
        s_bias = _structure_bias(d_structure, w_structure, tf)
        t_bias = _tl_bias(tl_states, tf)
        p_bias = _push_bias(cascade_state, tf)

        # Combine: majority vote
        votes = [v for v in (s_bias, t_bias, p_bias) if v != 0]
        if not votes:
            raw = 0
            confidence = 0
        else:
            bull_votes = sum(1 for v in votes if v > 0)
            bear_votes = sum(1 for v in votes if v < 0)
            if bull_votes > bear_votes:
                raw = 1
                confidence = bull_votes
            elif bear_votes > bull_votes:
                raw = -1
                confidence = bear_votes
            else:
                raw = 0
                confidence = 0

        tb.raw_bias = raw
        tb.confidence = confidence

        # Build context string
        parts = []
        if s_bias != 0:
            parts.append("struct" + ("^" if s_bias > 0 else "v"))
        if t_bias != 0:
            parts.append("TL" + ("^" if t_bias > 0 else "v"))
        if p_bias != 0:
            parts.append("push" + ("^" if p_bias > 0 else "v"))
        tb.context = f"{tf}: {' '.join(parts)}" if parts else f"{tf}: —"

        # Apply parent filter
        if first_tf:
            # W1 has no parent — raw = filtered
            tb.filtered_bias = raw
            parent_filtered = raw
            first_tf = False
        else:
            if parent_filtered == 0:
                # Parent neutral — allow child's own bias
                tb.filtered_bias = raw
            elif raw == parent_filtered:
                # Aligned with parent — pass through
                tb.filtered_bias = raw
            elif raw == 0:
                # Child neutral — inherit parent direction
                tb.filtered_bias = 0
            else:
                # Counter to parent
                # Exception: at reversal zone, allow counter-bias
                if reversal_tf and tf != reversal_tf:
                    # We're at a reversal zone — allow counter-parent at child TFs
                    # Only if the child TF is below the reversal zone TF
                    tf_idx = _BIAS_TFS.index(tf) if tf in _BIAS_TFS else -1
                    rev_idx = (
                        _BIAS_TFS.index(reversal_tf) if reversal_tf in _BIAS_TFS else -1
                    )
                    if tf_idx > rev_idx:
                        # Child is below reversal zone TF — allow counter
                        tb.filtered_bias = raw
                    else:
                        tb.filtered_bias = 0
                else:
                    tb.filtered_bias = 0

            # Propagate: use filtered_bias for next child (not raw)
            if tb.filtered_bias != 0:
                parent_filtered = tb.filtered_bias
            # If filtered is 0, keep parent_filtered from above

    # Derive trade direction from H4 filtered bias (primary trading TF)
    # Use the highest-confidence aligned TF
    h4_bias = state.biases.get("H4", TFBias())
    h1_bias = state.biases.get("H1", TFBias())

    if h4_bias.filtered_bias != 0:
        state.trade_direction = h4_bias.filtered_bias
    elif h1_bias.filtered_bias != 0:
        state.trade_direction = h1_bias.filtered_bias
    else:
        state.trade_direction = 0


def init_htf_bias_state() -> HTFBiasState:
    """Create fresh HTF bias state."""
    return HTFBiasState(
        biases={tf: TFBias() for tf in _BIAS_TFS},
    )
