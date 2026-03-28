"""
Wave + EW feature extraction — flat features from WaveSMState + EWState.

Extracts H1 wave phase, impulse/correction counts, EW pattern info.
"""

from __future__ import annotations

from iora.engine.wave_sm import WaveSMState, get_wave_label
from iora.engine.ew_classify import EWState


def extract_wave_features(
    wave_sm: WaveSMState | None,
    ew: EWState | None,
) -> dict[str, object]:
    """
    Extract flat wave + EW features.

    Returns dict with keys:
        wave_phase, wave_label, imp_count, cor_count,
        h1_sup_seq, h1_dem_seq,
        ew_pattern, ew_category, ew_changed
    """
    if wave_sm is not None:
        wave_phase = wave_sm.phase
        wave_label = get_wave_label(wave_sm)
        imp_count = wave_sm.imp_count
        cor_count = wave_sm.cor_count
        h1_sup_seq = wave_sm.sup_seq
        h1_dem_seq = wave_sm.dem_seq
    else:
        wave_phase = 0
        wave_label = ""
        imp_count = 0
        cor_count = 0
        h1_sup_seq = 0
        h1_dem_seq = 0

    if ew is not None:
        ew_pattern = ew.name
        ew_category = ew.category
        ew_changed = ew.changed
    else:
        ew_pattern = "UNKNOWN"
        ew_category = ""
        ew_changed = False

    return {
        "wave_phase": wave_phase,
        "wave_label": wave_label,
        "imp_count": imp_count,
        "cor_count": cor_count,
        "h1_sup_seq": h1_sup_seq,
        "h1_dem_seq": h1_dem_seq,
        "ew_pattern": ew_pattern,
        "ew_category": ew_category,
        "ew_changed": ew_changed,
    }
