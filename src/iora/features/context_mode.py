"""
Context mode computation -- RIDE/SCALP/FLIP/SKIP macro gate.

Pure function that reads existing BarFeatures fields to determine
the current macro context. Called from composite.py after all other
feature extraction.

Assessment order (first match wins, mutually exclusive):
  FLIP  -> D-level CHOCH fired (d_phase is "D Pull")
  RIDE  -> D pushing, H4 aligned (d_phase is "D Push", H4 active)
  SCALP -> D pushing, H4 retracing (d_phase is "D Push", H4 at zone)
  SKIP  -> No clear direction

References: docs/superpowers/specs/2026-03-23-context-mode-rules-redesign.md
"""

from __future__ import annotations

from iora.features.composite import BarFeatures


def compute_context_mode(f: BarFeatures) -> tuple[str, str]:
    """
    Compute context mode from BarFeatures fields.

    Returns (mode, detail) where:
      mode:   "RIDE" | "SCALP" | "FLIP" | "SKIP"
      detail: Human-readable description of current state
    """
    # 1. FLIP: D-level CHOCH -- d_phase is "D Pull"
    if f.d_phase == "D Pull v":
        return "FLIP", "FLIP: D LH fired, H4 transitioning down, seek D demand for D HL"
    if f.d_phase == "D Pull ^":
        return "FLIP", "FLIP: D HL fired, H4 transitioning up, seek D supply for D LH"

    # Need weekly bias for RIDE/SCALP
    weekly_bull = _weekly_bullish(f)
    weekly_bear = _weekly_bearish(f)

    # 2. D Push phases -- check RIDE vs SCALP
    if f.d_phase == "D Push ^" and weekly_bull:
        if _h4_retracing_in_bull(f):
            return "SCALP", f"SCALP: H4 retrace in D Push ^, h4_phase={f.h4_push_phase}"
        return "RIDE", f"RIDE: D Push ^, H4 push #{f.h4_push_count}"

    if f.d_phase == "D Push v" and weekly_bear:
        if _h4_retracing_in_bear(f):
            return "SCALP", f"SCALP: H4 retrace in D Push v, h4_phase={f.h4_push_phase}"
        return "RIDE", f"RIDE: D Push v, H4 push #{f.h4_push_count}"

    # 3. SKIP: everything else
    return "SKIP", f"SKIP: d_phase={f.d_phase}, no clear context"


def _weekly_bullish(f: BarFeatures) -> bool:
    """Weekly bullish bias.

    Three detection paths (carried from growth_entry v1, validated
    in screenshot analysis -- the d_ll + zone condition catches
    early W HL before structure engine propagates w_hl):
      1. w_hl already propagated by structure engine
      2. D LL forming inside D demand = W HL developing
      3. D bullish structure dominant (d_hl > d_lh) as fallback
    """
    if f.w_hl > 0:
        return True
    if f.d_ll > 0 and f.d1_price_in_demand:
        return True
    if f.d_hl > 0 and f.d_hl > f.d_lh:
        return True
    return False


def _weekly_bearish(f: BarFeatures) -> bool:
    """Weekly bearish bias (mirror of bullish)."""
    if f.w_lh > 0:
        return True
    if f.d_hh > 0 and f.d1_price_in_supply:
        return True
    if f.d_lh > 0 and f.d_lh > f.d_hl:
        return True
    return False


def _h4_retracing_in_bull(f: BarFeatures) -> bool:
    """H4 retracing during bullish D push."""
    # H4 reached D supply (retracement target in bull push)
    if f.h4_push_phase == "H4 @ D SUP":
        return True
    # H4 price pulled into supply (wrong direction for bull)
    if f.h4_price_in_supply:
        return True
    return False


def _h4_retracing_in_bear(f: BarFeatures) -> bool:
    """H4 retracing during bearish D push."""
    # H4 reached D demand (retracement target in bear push)
    if f.h4_push_phase == "H4 @ D DEM":
        return True
    # H4 price pulled into demand (wrong direction for bear)
    if f.h4_price_in_demand:
        return True
    return False
