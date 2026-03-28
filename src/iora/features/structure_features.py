"""
Structure feature extraction — flat features from StructureCountState + H4PushPhaseState.

Extracts D/W phase labels, HH/HL/LH/LL counts, and H4 push phase info.
"""

from __future__ import annotations

from iora.engine.structure_count import StructureCountState, H4PushPhaseState


def extract_structure_features(
    d_structure: StructureCountState | None,
    w_structure: StructureCountState | None,
    h4_push: H4PushPhaseState | None,
) -> dict[str, object]:
    """
    Extract flat structure features.

    Returns dict with keys:
        d_phase, d_hh, d_ll, d_lh, d_hl,
        w_phase, w_hh, w_ll, w_lh, w_hl,
        h4_push_phase, h4_push_count, h4_at_d_zone
    """
    # D-level structure
    if d_structure is not None:
        d_phase = d_structure.phase
        d_hh = d_structure.hh_count
        d_ll = d_structure.ll_count
        d_lh = d_structure.lh_count
        d_hl = d_structure.hl_count
    else:
        d_phase = "Unknown"
        d_hh = d_ll = d_lh = d_hl = 0

    # W-level structure
    if w_structure is not None:
        w_phase = w_structure.phase
        w_hh = w_structure.hh_count
        w_ll = w_structure.ll_count
        w_lh = w_structure.lh_count
        w_hl = w_structure.hl_count
    else:
        w_phase = "Unknown"
        w_hh = w_ll = w_lh = w_hl = 0

    # H4 push phase
    if h4_push is not None:
        h4_push_phase = h4_push.phase
        h4_push_count = h4_push.push_count
        h4_at_d_zone = h4_push.at_d_zone
    else:
        h4_push_phase = "Unknown"
        h4_push_count = 0
        h4_at_d_zone = False

    return {
        "d_phase": d_phase,
        "d_hh": d_hh,
        "d_ll": d_ll,
        "d_lh": d_lh,
        "d_hl": d_hl,
        "w_phase": w_phase,
        "w_hh": w_hh,
        "w_ll": w_ll,
        "w_lh": w_lh,
        "w_hl": w_hl,
        "h4_push_phase": h4_push_phase,
        "h4_push_count": h4_push_count,
        "h4_at_d_zone": h4_at_d_zone,
    }
