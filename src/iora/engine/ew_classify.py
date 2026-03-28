"""
Elliott Wave 9-pattern classifier.

Ports Pine Canopy Section 9B + 9C.

9 patterns:
  Motive: IMPULSE (1), DIAGONAL (2), EXTENDED (3)
  Corrective: REG_FLAT (4), EXP_FLAT (5), RUN_FLAT (6)
  Corrective/TL: SYM_TRI (7), ASC_TRI (8), REV_SYM (9)

Uses stored wave pivots from WaveSMState to classify the current pattern.
Triangle patterns require both bull and bear trendline data.
"""

from __future__ import annotations

from dataclasses import dataclass

from iora.engine.wave_sm import WaveSMState
from iora.engine.trendline_tick import TrendlineTickState, _interpolate_tl

EW_NAMES: dict[int, str] = {
    0: "UNKNOWN",
    1: "IMPULSE",
    2: "DIAGONAL",
    3: "EXTENDED",
    4: "REG_FLAT",
    5: "EXP_FLAT",
    6: "RUN_FLAT",
    7: "SYM_TRI",
    8: "ASC_TRI",
    9: "REV_SYM",
}

EW_CATEGORIES: dict[int, str] = {
    1: "motive",
    2: "motive",
    3: "motive",
    4: "corrective",
    5: "corrective",
    6: "corrective",
    7: "corrective_tl",
    8: "corrective_tl",
    9: "corrective_tl",
}

EW_COLORS: dict[int, str] = {
    0: "#888888",
    1: "#26A69A",
    2: "#FF9800",
    3: "#26A69A",
    4: "#AB47BC",
    5: "#AB47BC",
    6: "#AB47BC",
    7: "#42A5F5",
    8: "#42A5F5",
    9: "#42A5F5",
}

EXTENSION_THRESHOLD = 1.618


@dataclass(slots=True)
class EWState:
    """Tracks current EW classification and change detection."""

    pattern: int = 0
    pattern_prev: int = 0

    # Correction pivots (populated during corrective phases)
    cor_start: float | None = None
    cor_a_level: float | None = None
    cor_b_level: float | None = None
    cor_c_level: float | None = None
    cor_is_bull: bool = False

    @property
    def name(self) -> str:
        return EW_NAMES.get(self.pattern, "UNKNOWN")

    @property
    def category(self) -> str:
        return EW_CATEGORIES.get(self.pattern, "unknown")

    @property
    def color(self) -> str:
        return EW_COLORS.get(self.pattern, "#888888")

    @property
    def changed(self) -> bool:
        return self.pattern != self.pattern_prev and self.pattern > 0


def _classify_motive_bull(ws: WaveSMState) -> int:
    """Classify bullish motive pattern from stored pivots."""
    w1t = ws.ew_bull_w1_top
    w1b = ws.ew_bull_w1_bot
    w2b = ws.ew_bull_w2_bot
    w3t = ws.ew_bull_w3_top
    w4b = ws.ew_bull_w4_bot

    if w1t is None:
        return 0

    # Need at least w1 + w4 for diagonal check
    if w4b is not None and w1t is not None:
        if w4b < w1t:  # Wave 4 invades Wave 1 territory
            return 2  # DIAGONAL

    # Extended: Wave 3 > 161.8% of Wave 1
    if w1t is not None and w1b is not None and w3t is not None and w2b is not None:
        w1_rng = w1t - w1b
        w3_rng = w3t - w2b
        if w1_rng > 0 and w3_rng > w1_rng * EXTENSION_THRESHOLD:
            return 3  # EXTENDED

    return 1  # IMPULSE (default motive)


def _classify_motive_bear(ws: WaveSMState) -> int:
    """Classify bearish motive pattern from stored pivots."""
    w1b = ws.ew_bear_w1_bot
    w1t = ws.ew_bear_w1_top
    w2t = ws.ew_bear_w2_top
    w3b = ws.ew_bear_w3_bot
    w4t = ws.ew_bear_w4_top

    if w1b is None:
        return 0

    if w4t is not None and w1b is not None:
        if w4t > w1b:  # Wave 4 invades Wave 1 territory
            return 2  # DIAGONAL

    if w1t is not None and w1b is not None and w3b is not None and w2t is not None:
        w1_rng = w1t - w1b
        w3_rng = w2t - w3b
        if w1_rng > 0 and w3_rng > w1_rng * EXTENSION_THRESHOLD:
            return 3  # EXTENDED

    return 1  # IMPULSE


def _classify_corrective(ew: EWState) -> int:
    """Classify corrective pattern from A/B/C pivots."""
    start = ew.cor_start
    a = ew.cor_a_level
    b = ew.cor_b_level

    if start is None or a is None or b is None:
        return 0

    if ew.cor_is_bull:
        # Bullish correction (correcting bearish impulse) — A goes up, B goes down
        a_range = a - start
        b_retrace = b - a  # negative (B goes back down)
        b_past_start = b < start
    else:
        # Bearish correction (correcting bullish impulse) — A goes down, B goes up
        a_range = start - a
        b_retrace = a - b  # negative (B goes back up)
        b_past_start = b > start

    if a_range == 0:
        return 4  # fallback

    # Expanded flat: B exceeds origin
    if b_past_start:
        return 5  # EXP_FLAT

    # Regular flat: B retraces 90-110% of A
    retrace_pct = abs(b_retrace / a_range)
    if 0.9 <= retrace_pct <= 1.1:
        return 4  # REG_FLAT

    # Running flat: B exceeds A but C fails to reach start
    c = ew.cor_c_level
    if c is not None:
        if ew.cor_is_bull:
            if b < a and c > start:
                return 6  # RUN_FLAT
        else:
            if b > a and c < start:
                return 6  # RUN_FLAT

    # Default corrective
    return 4  # REG_FLAT fallback


def _classify_triangle(
    h1_tl_state: TrendlineTickState | None,
) -> int:
    """
    Check for triangle patterns via TL convergence.
    Requires both active bull and bear trendlines on H1.
    """
    if h1_tl_state is None:
        return 0

    bear_tl = h1_tl_state.bear_active
    bull_tl = h1_tl_state.bull_active
    if bear_tl is None or bull_tl is None:
        return 0

    # Use t2 as the measurement point for both
    # Gap at start (t1 anchor points)
    bear_y1 = bear_tl.p1
    bear_y2 = bear_tl.p2
    bull_y1 = bull_tl.p1
    bull_y2 = bull_tl.p2

    gap_start = abs(bear_y1 - bull_y1)
    gap_end = abs(bear_y2 - bull_y2)

    if gap_start == 0:
        return 0

    # Convergence test: TLs closed >30% of gap
    if gap_end >= gap_start * 0.7:
        return 0  # Not converging

    # Symmetric: bear descending + bull ascending
    if bear_y1 > bear_y2 and bull_y1 < bull_y2:
        return 7  # SYM_TRI

    # Ascending: upper TL nearly flat
    if abs(bear_y1 - bear_y2) < gap_start * 0.1:
        return 8  # ASC_TRI

    return 9  # REV_SYM (default triangle)


def ew_classify_tick(
    ew: EWState,
    ws: WaveSMState,
    h1_tl_state: TrendlineTickState | None = None,
) -> None:
    """
    Classify the current EW pattern based on wave SM state and trendlines.

    Mutates ``ew`` in place.
    """
    ew.pattern_prev = ew.pattern

    # Motive patterns (impulse phases 1 or 3)
    if ws.phase == 1 and ws.imp_count >= 1:
        pat = _classify_motive_bull(ws)
        if pat > 0:
            ew.pattern = pat
            return

    if ws.phase == 3 and ws.imp_count >= 1:
        pat = _classify_motive_bear(ws)
        if pat > 0:
            ew.pattern = pat
            return

    # Corrective patterns (phases 2 or 4)
    if ws.phase in (2, 4):
        # Update correction pivots from wave SM
        if ws.phase == 2:
            # Correcting bullish impulse → bearish correction
            ew.cor_is_bull = False
            if ws.ew_bull_w5_top is not None:
                ew.cor_start = ws.ew_bull_w5_top
            elif ws.ew_bull_w3_top is not None:
                ew.cor_start = ws.ew_bull_w3_top
            elif ws.ew_bull_w1_top is not None:
                ew.cor_start = ws.ew_bull_w1_top
        else:
            # Correcting bearish impulse → bullish correction
            ew.cor_is_bull = True
            if ws.ew_bear_w5_bot is not None:
                ew.cor_start = ws.ew_bear_w5_bot
            elif ws.ew_bear_w3_bot is not None:
                ew.cor_start = ws.ew_bear_w3_bot
            elif ws.ew_bear_w1_bot is not None:
                ew.cor_start = ws.ew_bear_w1_bot

        # Check triangle first (requires TL convergence)
        tri = _classify_triangle(h1_tl_state)
        if tri > 0:
            ew.pattern = tri
            return

        # Standard corrective classification
        if ws.cor_count >= 1:
            pat = _classify_corrective(ew)
            if pat > 0:
                ew.pattern = pat
                return

    # No classification possible
    if ws.phase == 0:
        ew.pattern = 0
