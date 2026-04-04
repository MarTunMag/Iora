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
    entry_mode: str = "market"              # "market" = close price, "limit" = zone edge

    # SL/TP
    sl_mode: str = "zone"                    # "zone", "atr", "period", "structure"
    tp_mode: str = "fixed_rr"               # "zone", "fixed_rr", "period"
    fixed_rr: float = 2.0                    # When tp_mode == "fixed_rr"
    sl_atr_mult: float = 1.5                # When sl_mode == "atr"

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

    # Touch policy (spec dimension: first_touch vs until_broken)
    touch_policy: str = "until_broken"       # "first_touch" = zone consumed after one entry;
                                             # "until_broken" = zone can be re-entered

    # Position management
    max_concurrent: int = 1                  # Max open trades per TF pair

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
