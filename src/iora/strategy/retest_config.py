"""Retest sweep configuration — all Level 4 sweep dimensions."""
from __future__ import annotations

from dataclasses import dataclass
from iora.constants import ENGINE_TF_ORDER

# Session windows: (start_hour_utc, end_hour_utc) — end is exclusive
SESSION_WINDOWS: dict[str, tuple[int, int]] = {
    "london": (7, 16),
    "newyork": (12, 21),
    "london_ny_overlap": (12, 16),
    "asian": (23, 7),  # Wraps midnight
}

# All valid TF pairs: entry@zone
ALL_TF_PAIRS: list[str] = [
    "M1@M5", "M1@M15",
    "M5@M15", "M5@H1",
    "M15@H1", "M15@H4",
    "H1@H4", "H1@D1",
]

# Map from zone_tf → list of pairs with higher context TFs
_TF_IDX = {tf: i for i, tf in enumerate(ENGINE_TF_ORDER)}


@dataclass(slots=True)
class RetestConfig:
    """Configuration for one retest sweep run."""

    # TF pair
    tf_pair: str = "H1@H4"

    # Entry filters
    touch_type: str = "wick_touch"           # "wick_touch", "body_close", "any"
    bias_filter: str = "any"                 # "with_daily", "against_daily", "any"
    zone_role_filter: str = "any"            # "continuation", "pullback", "push", "reversal", "any"
    age_filter: str = "any"                  # "fresh", "young", "mature", "old", "fresh_young", "any"
    test_count_filter: str = "any"           # "retested_1", "retested_2plus", "any"
    min_bias_strength: int = 0               # 0 = no filter, 1-3
    max_replacement_count: int = 999         # 999 = no filter
    direction: str = "both"                  # "long", "short", "both"
    session_filter: str = "any"              # "london", "newyork", "london_ny_overlap", "any"
                                             # "no_asian" = exclude asian window (logical, not a lookup key)

    # Cascade
    cascade_filter: str = "none"             # "none", "require_htf_signal", "require_confluence_2"
    cascade_lookback: int = 20               # Entry-TF bars (converted to seconds for lookup)
    cascade_direction: str = "same"          # "same", "any"

    # Entry mode
    entry_mode: str = "market"              # "market" = close price, "limit" = zone edge,
                                             # "cascade_layered" = limit at breaker zones
    limit_edge: str = "bottom"              # "bottom" = deepest entry (tightest SL, low fill rate),
                                             # "top" = zone top entry (wider SL, high fill rate)
    # Layered cascade SL mode (only used when entry_mode == "cascade_layered")
    layered_sl_mode: str = "own"            # "own" = SL behind each breaker zone,
                                             # "htf" = SL behind HTF context zone

    # Exit mode
    exit_mode: str = "fixed_sl_tp"           # "fixed_sl_tp" = current SL/TP system (default)
                                             # "signal_flip" = exit on opposite zone fire
                                             # "signal_flip_with_safety" = signal_flip + emergency SL

    # Signal-flip active window mode
    flip_window: str = "always"              # "always" = flip continuously after first entry (default)
                                             # "windowed" = only flip during active structural windows
                                             # When "windowed": cascade_phase_filter, tl_break_filter etc.
                                             # define when the system is ON. Outside active windows,
                                             # the system goes flat (closes on next opposite signal).

    # SL/TP
    sl_mode: str = "zone"                    # "zone", "atr", "period", "structure"
    tp_mode: str = "fixed_rr"               # "zone", "fixed_rr", "period", "htf_zone"
    fixed_rr: float = 2.0                    # When tp_mode == "fixed_rr" (also fallback for htf_zone)
    sl_atr_mult: float = 1.5                # When sl_mode == "atr"
    tp_htf: str = "H4"                      # Target TF for tp_mode="htf_zone" ("H1", "H4", "D1")

    # Phase 2 filters
    birth_pattern_filter: str = "any"        # "compression", "trending", "expansion", "any"
    retest_number_filter: str = "any"        # "1-3", "4-10", "10+", "any"
    time_since_creation_filter: str = "any"  # "0-3h", "3-12h", "12h-3d", "3d+", "any"
    parent_tf_boundary_filter: str = "any"   # "0-1_parent_bars", "1-2_parent_bars",
                                             # "2-4_parent_bars", "4+_parent_bars", "any"

    # Phase 3 filters
    inside_w_zone_filter: str = "any"        # "inside", "outside", "any"
    d_to_w_filter: str = "any"               # "continuation", "pullback", "inside_zone", "neutral", "any"

    # Phase 4 filters
    near_pdh_pdl: str = "any"               # "near" = within 0.5 ATR of PDH or PDL, "any"
    premium_discount: str = "any"           # "aligned" = longs in discount + shorts in premium, "any"

    # HMA filters
    hma_filter: str = "any"                # "with_hma_h1", "with_hma_h4", "any"
    hma_cross_trigger: str = "none"        # "h1", "h4", "none"
    hma_cross_lookback: int | str = 20     # entry-TF bars, or "until_reverse"
    hma_period: int = 24                   # HMA period (12 or 24)
    hma_source: str = "close"             # "close" or "ha_close"

    # Partial take-profit (2-unit exit: scalp lock + HTF runner)
    partial_tp: bool = False                 # Enable partial TP mode
    partial_unit1_pct: float = 0.5           # Unit 1 fraction (scalp lock)
    partial_unit1_rr: float = 3.0            # Unit 1 TP as R:R multiple
    partial_unit2_tp: str = "H1"             # Unit 2 TP target TF ("H1", "H4", "D1")
    breakeven_buffer_atr: float = 0.0        # Buffer below breakeven after Unit 1 TP lock
                                             # 0.0 = exact BE, 0.25 = entry - 0.25*ATR for longs
                                             # (gives room for wicks below entry)
    unit2_trail: str = "none"                # Unit 2 trailing stop: "none" = fixed TP (current),
                                             # "ha_m5", "ha_m15", "ha_m30", "ha_h1" = HA trail on TF

    # Spread and SL reality modeling
    spread_pips: float = 0.0                 # Spread cost in pips (0 = no spread, 1.5 = typical FX)
    min_sl_pips: float = 0.0                 # Minimum SL distance in pips (0 = no floor)
    min_sl_spread_mult: float = 0.0          # Spread-relative min SL: min_sl = spread_pips * mult
                                             # 0 = disabled, 2-5 = typical. Applied as:
                                             # max(zone_sl, max(min_sl_pips, spread_pips*mult) * pip_size)
    sl_buffer_atr: float = 0.15              # ATR fraction buffer beyond zone edge for SL
                                             # Default 0.15 matches _ZONE_BUFFER_ATR

    # Limit order TTL (time-to-live in entry-TF bars)
    limit_ttl: int = 1                       # 1 = same-bar only (current), 3/6/12 = carry forward,
                                             # 0 = until zone breaks (body-close)

    # Touch policy (spec dimension: first_touch vs until_broken)
    touch_policy: str = "until_broken"       # "first_touch" = zone consumed after one entry;
                                             # "until_broken" = zone can be re-entered

    # Position management
    max_concurrent: int = 1                  # Max open trades per TF pair

    # HTF-triggered LTF entry
    ltf_nesting: str = "none"              # "none", "static", "dynamic"
    trigger_tf_pair: str = "H1@H4"        # HTF pair that provides trigger
    entry_tf_override: str = ""            # LTF for zone lookup ("M15", "M5", "M1", "" = derive)
    trigger_window_bars: int = 48          # Dynamic mode: max entry-TF bars after trigger
    require_ltf_push: bool = False         # Only use LTF push zones
    trigger_also_trades: bool = False      # H1@H4 trigger also opens its own trade
    max_ltf_per_trigger: int = 3           # Max LTF entries per trigger window

    # Gap analysis additions
    min_rr_ratio: float = 0.0             # 0.0 = no filter, 2.0, 3.0 = skip below this R:R
    tp_target_tf: str = ""                # "" = use default, "H1", "H4", "D1" for nested entries
    entry_refinement: str = "zone_top"    # "zone_top", "zone_50pct" (Fibonacci 50% of zone)

    # Cascade phase filters (from push zone trendline engine)
    cascade_phase_filter: str = "any"     # "any", "d1_push", "h4_correction", "h4_correction_tl_break",
                                           # "h1_extended", "h1_terminal", "at_reversal_target"
    tl_break_filter: str = "any"          # "any", "after_impulse_break", "after_correction_break"
    tl_break_lookback: int = 0            # 0 = any time (sticky), >0 = within N bars
    h1_zone_count_filter: str = "any"     # "any", "1-3", "4-7", "8+"
    reversal_target_entry: bool = False    # Only enter at CHoCH-causing zone

    # EW-derived exhaustion filters
    ew_overlap_filter: str = "any"        # "any", "no_overlap", "overlap_only"
    ew_extension_filter: str = "any"      # "any", "extended", "not_extended"

    # CHoCH conviction filter
    choch_conviction_filter: str = "any"  # "any", "strong_only", "weak_only"

    # Momentum consumption filter (child TFs aligned after H4 CHoCH)
    min_consumption_count: int = 0        # 0, 1, 2, 3

    # Structural overlap filters (Phase 3)
    require_fvg_at_entry: bool = False
    min_pivot_cascade_depth: int = 0      # 0, 2, 3, 4
    require_breaker_zone: bool = False
    structural_fvg_filter: str = "any"    # "any", "inside_gap", "at_gap_boundary"

    # Layer 2.5: Structural sequence filters (from XAUUSD live chart analysis)
    htf_level_break_context: str = "any"  # "any", "after_dy_lo_x", "after_dy_hi_x",
                                           # "after_h4_lo_x", "after_h4_hi_x",
                                           # "after_h1_lo_x", "after_h1_hi_x"
    htf_break_lookback: int = 0           # 0 = any time (sticky), >0 = within N entry-TF bars
    zone_spatial_context: str = "any"     # "any", "m15_hl_above_htf_demand",
                                           # "m15_lh_below_htf_supply",
                                           # "first_htf_zone_after_break"
    m15_tl_state: str = "any"             # "any", "after_correction_break", "impulse_intact"

    @property
    def entry_tf(self) -> str:
        return self.tf_pair.split("@")[0]

    @property
    def zone_tf(self) -> str:
        return self.tf_pair.split("@")[1]

    @property
    def htf_pairs(self) -> list[str]:
        """All TF pairs with context TF higher than this config's zone TF."""
        zone_idx = _TF_IDX.get(self.zone_tf, 0)
        return [
            p for p in ALL_TF_PAIRS
            if _TF_IDX.get(p.split("@")[1], 0) > zone_idx
        ]
