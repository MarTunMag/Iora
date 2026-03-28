"""
Composite feature extraction — merges all feature modules into one flat BarFeatures.

This is the interface contract between the engine and everything downstream
(visualization labels, rule evaluation, backtest, live execution).

Usage:
    features = extract_bar_features(pulse_output, close)
    # features.d_phase → "D Push ^"
    # features.h4_supply_count → 2
    # features.wave_label → "IMP ^ W3"
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

import pandas as pd

from iora.engine.zone_tick import ZoneTickState
from iora.engine.trendline_tick import TrendlineTickState
from iora.engine.structure_count import StructureCountState, H4PushPhaseState
from iora.engine.wave_sm import WaveSMState
from iora.engine.ew_classify import EWState
from iora.orchestrator.zone_engine import ZoneState, UBChainCounts

from iora.features.zone_features import extract_zone_features_for_tf
from iora.features.tl_features import extract_tl_features_for_tf
from iora.features.structure_features import extract_structure_features
from iora.features.wave_features import extract_wave_features

# TFs for which we extract zone features
_ZONE_TFS = ["M5", "M15", "H1", "H4", "D1", "W1"]
# TFs for which we extract TL features
_TL_TFS = ["M5", "M15", "H1", "H4", "D1", "W1"]


@dataclass(slots=True)
class BarFeatures:
    """
    Flat per-bar feature record. All fields are simple types
    (int, float, bool, str, Timestamp). No nested objects.

    This dataclass is the SINGLE interface consumed by:
    - Viz layer (chart annotations, structure labels)
    - Rules layer (signal conditions)
    - Trader layer (backtest + live execution)
    """

    timestamp: pd.Timestamp = pd.NaT
    close: float = 0.0

    # ── OHLCV + ATR (needed by Rules layer) ──
    open_: float = 0.0
    high: float = 0.0
    low: float = 0.0
    atr: float = 0.0
    ha_direction: int = 0  # +1 = blue (bullish), -1 = red (bearish), 0 = unknown

    # ── Zone features (per TF) ──
    # M5
    m5_supply_count: int = 0
    m5_demand_count: int = 0
    m5_nearest_supply_dist: float = math.nan
    m5_nearest_demand_dist: float = math.nan
    m5_price_in_supply: bool = False
    m5_price_in_demand: bool = False
    # M15
    m15_supply_count: int = 0
    m15_demand_count: int = 0
    m15_nearest_supply_dist: float = math.nan
    m15_nearest_demand_dist: float = math.nan
    m15_price_in_supply: bool = False
    m15_price_in_demand: bool = False
    # H1
    h1_supply_count: int = 0
    h1_demand_count: int = 0
    h1_nearest_supply_dist: float = math.nan
    h1_nearest_demand_dist: float = math.nan
    h1_price_in_supply: bool = False
    h1_price_in_demand: bool = False
    # H4
    h4_supply_count: int = 0
    h4_demand_count: int = 0
    h4_nearest_supply_dist: float = math.nan
    h4_nearest_demand_dist: float = math.nan
    h4_price_in_supply: bool = False
    h4_price_in_demand: bool = False
    # D1
    d1_supply_count: int = 0
    d1_demand_count: int = 0
    d1_nearest_supply_dist: float = math.nan
    d1_nearest_demand_dist: float = math.nan
    d1_price_in_supply: bool = False
    d1_price_in_demand: bool = False
    # W1
    w1_supply_count: int = 0
    w1_demand_count: int = 0
    w1_nearest_supply_dist: float = math.nan
    w1_nearest_demand_dist: float = math.nan
    w1_price_in_supply: bool = False
    w1_price_in_demand: bool = False

    # ── UB chain (unbroken zone counts) ──
    ub_h1_sup: int = 0
    ub_h1_dem: int = 0
    ub_h4_sup: int = 0
    ub_h4_dem: int = 0
    ub_d_sup: int = 0
    ub_d_dem: int = 0
    h1_sup_exhausted: bool = False
    h1_dem_exhausted: bool = False

    # ── Structure features ──
    d_phase: str = "Unknown"
    d_hh: int = 0
    d_ll: int = 0
    d_lh: int = 0
    d_hl: int = 0
    w_phase: str = "Unknown"
    w_hh: int = 0
    w_ll: int = 0
    w_lh: int = 0
    w_hl: int = 0
    h4_push_phase: str = "Unknown"
    h4_push_count: int = 0
    h4_at_d_zone: bool = False

    # ── Wave features (H1 wave SM) ──
    wave_phase: int = 0
    wave_label: str = ""
    imp_count: int = 0
    cor_count: int = 0
    h1_sup_seq: int = 0
    h1_dem_seq: int = 0

    # ── EW features ──
    ew_pattern: str = "UNKNOWN"
    ew_category: str = ""
    ew_changed: bool = False

    # ── TL features (per TF) ──
    # M5
    m5_bull_tl_active: bool = False
    m5_bear_tl_active: bool = False
    m5_bull_tl_broken: bool = False
    m5_bear_tl_broken: bool = False
    m5_bull_tl_dist: float = math.nan
    m5_bear_tl_dist: float = math.nan
    # M15
    m15_bull_tl_active: bool = False
    m15_bear_tl_active: bool = False
    m15_bull_tl_broken: bool = False
    m15_bear_tl_broken: bool = False
    m15_bull_tl_dist: float = math.nan
    m15_bear_tl_dist: float = math.nan
    # H1
    h1_bull_tl_active: bool = False
    h1_bear_tl_active: bool = False
    h1_bull_tl_broken: bool = False
    h1_bear_tl_broken: bool = False
    h1_bull_tl_dist: float = math.nan
    h1_bear_tl_dist: float = math.nan
    # H4
    h4_bull_tl_active: bool = False
    h4_bear_tl_active: bool = False
    h4_bull_tl_broken: bool = False
    h4_bear_tl_broken: bool = False
    h4_bull_tl_dist: float = math.nan
    h4_bear_tl_dist: float = math.nan
    # D1
    d1_bull_tl_active: bool = False
    d1_bear_tl_active: bool = False
    d1_bull_tl_broken: bool = False
    d1_bear_tl_broken: bool = False
    d1_bull_tl_dist: float = math.nan
    d1_bear_tl_dist: float = math.nan
    # W1
    w1_bull_tl_active: bool = False
    w1_bear_tl_active: bool = False
    w1_bull_tl_broken: bool = False
    w1_bear_tl_broken: bool = False
    w1_bull_tl_dist: float = math.nan
    w1_bear_tl_dist: float = math.nan

    # ── Macro bias + cycle (when enabled) ──
    macro_bias: int = 0
    cycle_label: str = ""

    # ── HTF Bias cascade (per-TF filtered bias: -1, 0, +1) ──
    w1_bias: int = 0
    d1_bias: int = 0
    h4_bias: int = 0
    h1_bias: int = 0
    m15_bias: int = 0
    m5_bias: int = 0

    # Net trade direction and reversal zone context
    trade_direction: int = 0  # +1=longs, -1=shorts, 0=both
    at_reversal_zone: bool = (
        False  # Price inside HTF zone that could reverse current push
    )
    reversal_zone_tf: str = ""  # Which TF's zone we're in

    # ── Nearest zone prices (for SL/TP calculation) ──
    h1_nearest_supply_price: float = math.nan
    h1_nearest_demand_price: float = math.nan
    h4_nearest_supply_price: float = math.nan
    h4_nearest_demand_price: float = math.nan
    d1_nearest_supply_price: float = math.nan
    d1_nearest_demand_price: float = math.nan
    m15_nearest_supply_price: float = math.nan
    m15_nearest_demand_price: float = math.nan
    m5_nearest_supply_price: float = math.nan
    m5_nearest_demand_price: float = math.nan

    # ── Nearest zone origin times (for zone age / time-based invalidation) ──
    h1_nearest_supply_origin: pd.Timestamp = pd.NaT
    h1_nearest_demand_origin: pd.Timestamp = pd.NaT
    h4_nearest_supply_origin: pd.Timestamp = pd.NaT
    h4_nearest_demand_origin: pd.Timestamp = pd.NaT
    d1_nearest_supply_origin: pd.Timestamp = pd.NaT
    d1_nearest_demand_origin: pd.Timestamp = pd.NaT
    m15_nearest_supply_origin: pd.Timestamp = pd.NaT
    m15_nearest_demand_origin: pd.Timestamp = pd.NaT
    m5_nearest_supply_origin: pd.Timestamp = pd.NaT
    m5_nearest_demand_origin: pd.Timestamp = pd.NaT

    # ── BOS/CHOCH event flags this bar ──
    bos_bull: bool = False
    bos_bear: bool = False
    choch_bull: bool = False
    choch_bear: bool = False
    # TF-specific CHOCH flags (for precise entry gating)
    m1_choch_bull: bool = False
    m1_choch_bear: bool = False
    m5_choch_bull: bool = False
    m5_choch_bear: bool = False
    # H1-specific BOS/CHOCH flags (for sweep state tracking)
    h1_bos_bull: bool = False     # H1 supply HH broken (bullish BOS at H1)
    h1_bos_bear: bool = False     # H1 demand LL broken (bearish BOS at H1)
    h1_choch_bull: bool = False   # H1 supply LH broken (bullish CHOCH at H1)
    h1_choch_bear: bool = False   # H1 demand HL broken (bearish CHOCH at H1)

    # ── Event counts this bar ──
    zone_fires: int = 0
    zone_breaks: int = 0
    tl_breaks: int = 0

    # ── Context mode (computed by context_mode.py) ──
    context_mode: str = "SKIP"       # "RIDE" | "SCALP" | "FLIP" | "SKIP"
    context_detail: str = ""         # Human-readable sub-state description

    def to_dict(self) -> dict:
        """Convert to flat dict (for DataFrame row)."""
        return asdict(self)


def extract_bar_features(
    *,
    timestamp: pd.Timestamp,
    close: float,
    open_: float = 0.0,
    high: float = 0.0,
    low: float = 0.0,
    atr: float = 0.0,
    ha_direction: int = 0,
    zone_state: ZoneState | None = None,
    canopy_tl_states: dict[str, TrendlineTickState] | None = None,
    d_structure: StructureCountState | None = None,
    w_structure: StructureCountState | None = None,
    h4_push: H4PushPhaseState | None = None,
    wave_sm: WaveSMState | None = None,
    ew: EWState | None = None,
    macro_bias: int = 0,
    cycle_label: str = "",
    bar_events: list | None = None,
    htf_bias=None,
) -> BarFeatures:
    """
    Extract all features for a single bar from engine state.

    Call this AFTER all engine ticks have completed for the bar.
    All parameters are keyword-only to make call sites self-documenting.
    """
    f = BarFeatures(
        timestamp=timestamp,
        close=close,
        open_=open_,
        high=high,
        low=low,
        atr=atr,
        ha_direction=ha_direction,
    )

    # ── Zone features ──
    if zone_state is not None:
        for tf in _ZONE_TFS:
            zs = zone_state.zone_states.get(tf)
            zf = extract_zone_features_for_tf(zs, close)
            tf_lower = tf.lower()
            setattr(f, f"{tf_lower}_supply_count", zf["supply_count"])
            setattr(f, f"{tf_lower}_demand_count", zf["demand_count"])
            setattr(f, f"{tf_lower}_nearest_supply_dist", zf["nearest_supply_dist"])
            setattr(f, f"{tf_lower}_nearest_demand_dist", zf["nearest_demand_dist"])
            setattr(f, f"{tf_lower}_price_in_supply", zf["price_in_supply"])
            setattr(f, f"{tf_lower}_price_in_demand", zf["price_in_demand"])

            # Propagate nearest zone prices + origin times for key TFs
            if tf in ("M5", "M15", "H1", "H4", "D1"):
                setattr(
                    f, f"{tf_lower}_nearest_supply_price", zf["nearest_supply_edge"]
                )
                setattr(
                    f, f"{tf_lower}_nearest_demand_price", zf["nearest_demand_edge"]
                )
                setattr(
                    f, f"{tf_lower}_nearest_supply_origin", zf["nearest_supply_origin"]
                )
                setattr(
                    f, f"{tf_lower}_nearest_demand_origin", zf["nearest_demand_origin"]
                )

        # UB chain
        ub = zone_state.ub_chain
        f.ub_h1_sup = ub.h1_sup
        f.ub_h1_dem = ub.h1_dem
        f.ub_h4_sup = ub.h4_sup
        f.ub_h4_dem = ub.h4_dem
        f.ub_d_sup = ub.d_sup
        f.ub_d_dem = ub.d_dem
        f.h1_sup_exhausted = ub.h1_sup_exhausted
        f.h1_dem_exhausted = ub.h1_dem_exhausted

    # ── Structure features ──
    sf = extract_structure_features(d_structure, w_structure, h4_push)
    f.d_phase = sf["d_phase"]
    f.d_hh = sf["d_hh"]
    f.d_ll = sf["d_ll"]
    f.d_lh = sf["d_lh"]
    f.d_hl = sf["d_hl"]
    f.w_phase = sf["w_phase"]
    f.w_hh = sf["w_hh"]
    f.w_ll = sf["w_ll"]
    f.w_lh = sf["w_lh"]
    f.w_hl = sf["w_hl"]
    f.h4_push_phase = sf["h4_push_phase"]
    f.h4_push_count = sf["h4_push_count"]
    f.h4_at_d_zone = sf["h4_at_d_zone"]

    # ── Wave + EW features ──
    wf = extract_wave_features(wave_sm, ew)
    f.wave_phase = wf["wave_phase"]
    f.wave_label = wf["wave_label"]
    f.imp_count = wf["imp_count"]
    f.cor_count = wf["cor_count"]
    f.h1_sup_seq = wf["h1_sup_seq"]
    f.h1_dem_seq = wf["h1_dem_seq"]
    f.ew_pattern = wf["ew_pattern"]
    f.ew_category = wf["ew_category"]
    f.ew_changed = wf["ew_changed"]

    # ── TL features ──
    if canopy_tl_states is not None:
        for tf in _TL_TFS:
            tl_state = canopy_tl_states.get(tf)
            tf_feats = extract_tl_features_for_tf(tl_state, close, timestamp)
            tf_lower = tf.lower()
            setattr(f, f"{tf_lower}_bull_tl_active", tf_feats["bull_tl_active"])
            setattr(f, f"{tf_lower}_bear_tl_active", tf_feats["bear_tl_active"])
            setattr(f, f"{tf_lower}_bull_tl_broken", tf_feats["bull_tl_broken"])
            setattr(f, f"{tf_lower}_bear_tl_broken", tf_feats["bear_tl_broken"])
            setattr(f, f"{tf_lower}_bull_tl_dist", tf_feats["bull_tl_dist"])
            setattr(f, f"{tf_lower}_bear_tl_dist", tf_feats["bear_tl_dist"])

    # ── Macro bias + cycle ──
    f.macro_bias = macro_bias
    f.cycle_label = cycle_label

    # ── HTF Bias cascade ──
    if htf_bias is not None:
        for tf_key in ("w1", "d1", "h4", "h1", "m15", "m5"):
            tf_upper = tf_key.upper()
            tb = htf_bias.biases.get(tf_upper)
            if tb is not None:
                setattr(f, f"{tf_key}_bias", tb.filtered_bias)
        f.trade_direction = htf_bias.trade_direction
        f.at_reversal_zone = bool(htf_bias.reversal_zone_tf)
        f.reversal_zone_tf = htf_bias.reversal_zone_tf

    # ── Event counts + BOS/CHOCH flags ──
    if bar_events:
        from iora.engine.models import EventID

        for e in bar_events:
            if e.id == EventID.ZONE_FIRE:
                f.zone_fires += 1
            elif e.id == EventID.ZONE_BREAK:
                f.zone_breaks += 1
                # Classify BOS vs CHOCH from payload
                payload = e.payload
                side = payload.get("side")
                is_hh_or_ll = payload.get("is_hh_or_ll", False)
                if side == "supply":
                    if is_hh_or_ll:
                        f.bos_bull = True
                        if e.timeframe == "H1":
                            f.h1_bos_bull = True
                    else:
                        f.choch_bull = True
                        if e.timeframe == "M1":
                            f.m1_choch_bull = True
                        elif e.timeframe == "M5":
                            f.m5_choch_bull = True
                        elif e.timeframe == "H1":
                            f.h1_choch_bull = True
                elif side == "demand":
                    if is_hh_or_ll:
                        f.bos_bear = True
                        if e.timeframe == "H1":
                            f.h1_bos_bear = True
                    else:
                        f.choch_bear = True
                        if e.timeframe == "M1":
                            f.m1_choch_bear = True
                        elif e.timeframe == "M5":
                            f.m5_choch_bear = True
                        elif e.timeframe == "H1":
                            f.h1_choch_bear = True
            elif e.id == EventID.TL_BREAK:
                f.tl_breaks += 1

    # -- Context mode (macro gate) --
    from iora.features.context_mode import compute_context_mode
    f.context_mode, f.context_detail = compute_context_mode(f)

    return f
