"""
H1 4-phase IMP/COR wave state machine.

Ports Pine S9 (canopy.pine lines 359-603).

4-phase model:
  Phase 1: IMP_BULL — HH fired, impulse counting 1-5
  Phase 2: COR_BULL — LH fired, correction counting A-B-C (1-3)
  Phase 3: IMP_BEAR — LL fired, impulse counting 1-5
  Phase 4: COR_BEAR — HL fired, correction counting A-B-C (1-3)

Transitions:
  HH → Phase 1 (from any phase)
  LL → Phase 3 (from any phase)
  LH → Phase 2 (from Phase 1), or increment COR count
  HL → Phase 4 (from Phase 3), or increment COR count
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class WaveSMState:
    """
    Mutable state for the H1 wave phase state machine.
    """

    phase: int = 0  # 0=uninitialized, 1=IMP_BULL, 2=COR_BULL, 3=IMP_BEAR, 4=COR_BEAR
    imp_count: int = 0  # 1-5 impulse wave count
    cor_count: int = 0  # 1-3 correction count (A=1, B=2, C=3)

    # H1 zone sequence counters
    sup_seq: int = 0
    dem_seq: int = 0

    # EW pivot storage (for downstream EW classifier, Milestone 5)
    # Each wave stores both price and timestamp for duration/overlap validation
    ew_bull_w1_top: float | None = None
    ew_bull_w1_bot: float | None = None
    ew_bull_w2_bot: float | None = None
    ew_bull_w3_top: float | None = None
    ew_bull_w4_bot: float | None = None
    ew_bull_w5_top: float | None = None

    ew_bear_w1_bot: float | None = None
    ew_bear_w1_top: float | None = None
    ew_bear_w2_top: float | None = None
    ew_bear_w3_bot: float | None = None
    ew_bear_w4_top: float | None = None
    ew_bear_w5_bot: float | None = None

    # Timestamps for each EW pivot (parallel to price fields above)
    ew_bull_w1_time: pd.Timestamp = pd.NaT
    ew_bull_w2_time: pd.Timestamp = pd.NaT
    ew_bull_w3_time: pd.Timestamp = pd.NaT
    ew_bull_w4_time: pd.Timestamp = pd.NaT
    ew_bull_w5_time: pd.Timestamp = pd.NaT

    ew_bear_w1_time: pd.Timestamp = pd.NaT
    ew_bear_w2_time: pd.Timestamp = pd.NaT
    ew_bear_w3_time: pd.Timestamp = pd.NaT
    ew_bear_w4_time: pd.Timestamp = pd.NaT
    ew_bear_w5_time: pd.Timestamp = pd.NaT


IMP_MAX = 5
COR_MAX = 3

_PHASE_NAMES = {
    0: "INIT",
    1: "IMP ^",
    2: "COR v",
    3: "IMP v",
    4: "COR ^",
}

_COR_LETTERS = {1: "A", 2: "B", 3: "C"}


def wave_sm_tick(
    state: WaveSMState,
    hi_fire: bool,
    hi_ztop: float | None,
    hi_zbot: float | None,
    hi_is_hh: bool,
    lo_fire: bool,
    lo_ztop: float | None,
    lo_zbot: float | None,
    lo_is_ll: bool,
    bar_time: pd.Timestamp | None = None,
) -> None:
    """
    Process one bar's H1 pivot edges through the wave state machine.

    Mutates ``state`` in place.
    """
    # H1 zone sequence counting (S8)
    if hi_fire:
        state.sup_seq += 1
        if hi_is_hh:
            state.dem_seq = 0
    if lo_fire:
        state.dem_seq += 1
        if lo_is_ll:
            state.sup_seq = 0

    # ------------------------------------------------------------------
    # HH fires → Bullish impulse
    # ------------------------------------------------------------------
    if hi_fire and hi_is_hh and hi_ztop is not None:
        if state.phase == 0 or state.phase == 3 or state.phase == 4:
            # Reversal or init → start new bull impulse
            state.phase = 1
            state.imp_count = 1
            state.cor_count = 0
            state.ew_bull_w1_top = hi_ztop
            state.ew_bull_w1_bot = lo_zbot if lo_zbot is not None else hi_zbot
            state.ew_bull_w1_time = bar_time or pd.NaT
            # Clear higher waves
            state.ew_bull_w2_bot = None
            state.ew_bull_w3_top = None
            state.ew_bull_w4_bot = None
            state.ew_bull_w5_top = None
            state.ew_bull_w2_time = pd.NaT
            state.ew_bull_w3_time = pd.NaT
            state.ew_bull_w4_time = pd.NaT
            state.ew_bull_w5_time = pd.NaT
        elif state.phase == 1:
            # Continue impulse
            state.imp_count = min(state.imp_count + 1, IMP_MAX)
            if state.imp_count == 3:
                state.ew_bull_w3_top = hi_ztop
                state.ew_bull_w3_time = bar_time or pd.NaT
            elif state.imp_count == 5:
                state.ew_bull_w5_top = hi_ztop
                state.ew_bull_w5_time = bar_time or pd.NaT
                # 5-wave complete → expect correction
                state.phase = 2
                state.cor_count = 0
        elif state.phase == 2:
            # Correction ended early → new impulse
            state.phase = 1
            state.imp_count = 1
            state.cor_count = 0

    # ------------------------------------------------------------------
    # LL fires → Bearish impulse
    # ------------------------------------------------------------------
    if lo_fire and lo_is_ll and lo_zbot is not None:
        if state.phase == 0 or state.phase == 1 or state.phase == 2:
            # Reversal or init → start new bear impulse
            state.phase = 3
            state.imp_count = 1
            state.cor_count = 0
            state.ew_bear_w1_bot = lo_zbot
            state.ew_bear_w1_top = hi_ztop if hi_ztop is not None else lo_ztop
            state.ew_bear_w1_time = bar_time or pd.NaT
            state.ew_bear_w2_top = None
            state.ew_bear_w3_bot = None
            state.ew_bear_w4_top = None
            state.ew_bear_w5_bot = None
            state.ew_bear_w2_time = pd.NaT
            state.ew_bear_w3_time = pd.NaT
            state.ew_bear_w4_time = pd.NaT
            state.ew_bear_w5_time = pd.NaT
        elif state.phase == 3:
            state.imp_count = min(state.imp_count + 1, IMP_MAX)
            if state.imp_count == 3:
                state.ew_bear_w3_bot = lo_zbot
                state.ew_bear_w3_time = bar_time or pd.NaT
            elif state.imp_count == 5:
                state.ew_bear_w5_bot = lo_zbot
                state.ew_bear_w5_time = bar_time or pd.NaT
                state.phase = 4
                state.cor_count = 0
        elif state.phase == 4:
            state.phase = 3
            state.imp_count = 1
            state.cor_count = 0

    # ------------------------------------------------------------------
    # LH fires → Bull correction (or bear impulse continues)
    # ------------------------------------------------------------------
    if hi_fire and not hi_is_hh:
        if state.phase == 1:
            # Impulse → correction
            state.phase = 2
            state.cor_count = 1
        elif state.phase == 2:
            state.cor_count = min(state.cor_count + 1, COR_MAX)
            if state.cor_count >= COR_MAX:
                # A-B-C complete
                state.phase = 1
                state.imp_count = 1
                state.cor_count = 0

    # ------------------------------------------------------------------
    # HL fires → Bear correction (or bull impulse continues)
    # ------------------------------------------------------------------
    if lo_fire and not lo_is_ll:
        if state.phase == 3:
            state.phase = 4
            state.cor_count = 1
        elif state.phase == 4:
            state.cor_count = min(state.cor_count + 1, COR_MAX)
            if state.cor_count >= COR_MAX:
                state.phase = 3
                state.imp_count = 1
                state.cor_count = 0

    # Even-wave capture (waves 2/4)
    _bt = bar_time or pd.NaT
    if lo_fire and not lo_is_ll and lo_zbot is not None:
        if state.phase in (1, 2) and state.ew_bull_w1_top is not None:
            if state.ew_bull_w2_bot is None:
                state.ew_bull_w2_bot = lo_zbot
                state.ew_bull_w2_time = _bt
            elif state.ew_bull_w3_top is not None and state.ew_bull_w4_bot is None:
                state.ew_bull_w4_bot = lo_zbot
                state.ew_bull_w4_time = _bt

    if hi_fire and not hi_is_hh and hi_ztop is not None:
        if state.phase in (3, 4) and state.ew_bear_w1_bot is not None:
            if state.ew_bear_w2_top is None:
                state.ew_bear_w2_top = hi_ztop
                state.ew_bear_w2_time = _bt
            elif state.ew_bear_w3_bot is not None and state.ew_bear_w4_top is None:
                state.ew_bear_w4_top = hi_ztop
                state.ew_bear_w4_time = _bt


def get_wave_label(state: WaveSMState) -> str:
    """Return a human-readable wave phase label."""
    phase_name = _PHASE_NAMES.get(state.phase, "?")
    if state.phase in (1, 3):
        return f"{phase_name} W{state.imp_count}"
    elif state.phase in (2, 4):
        letter = _COR_LETTERS.get(state.cor_count, "?")
        return f"{phase_name} {letter}"
    return phase_name
