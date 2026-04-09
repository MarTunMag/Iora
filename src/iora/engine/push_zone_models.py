"""
Push zone models — dataclasses for push zone detection engine.

Pine reference: iora_push_zones_v2.pine (S2 Zone UDT, S5 track_period)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isnan, nan

import pandas as pd


@dataclass(slots=True)
class PushZone:
    """A supply or demand zone with push/reversal/terminal classification."""

    top: float
    bottom: float
    is_supply: bool
    origin_time: pd.Timestamp
    timeframe: str = ""
    is_push: bool = False
    is_reversal: bool = False
    is_terminal: bool = False
    struct_cls: str = ""       # "BOS" or "CHoCH"
    swing_cls: str = ""        # "HH", "LH", "HL", "LL"
    count_num: int = 0

    # --- Retest & birth metadata (Level 0 enrichment) ---
    birth_price_distance: float = 0.0    # ATR(14) units from zone midpoint to close at creation
    birth_bias_d: str = "unknown"        # Daily bias at creation (e.g., "HH_HL_bull_push")
    birth_bias_w: str = "unknown"        # Weekly context at creation
    birth_period_pattern: str = "unknown" # Period pattern at creation (e.g., "HH_HL")
    replacement_count: int = 0           # Same-TF same-side zones created since this one
    test_count: int = 0                  # Times price touched this zone
    first_test_time: pd.Timestamp | None = None  # Timestamp of first retest

    # --- Zone attribution (Level 4: which zone caused a structural event) ---
    caused_bos_choch: str = ""           # "BOS" or "CHoCH" if this zone caused an event
    caused_event_tf: str = ""            # The TF where the structural event occurred

    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top


@dataclass(slots=True)
class PeriodTracker:
    """Tracks previous closed period high/low with rolling history.

    Pine reference: track_period() in iora_push_zones_v2.pine (S5).
    Stores up to `history_depth` previous period highs/lows (most recent first).
    """

    history_depth: int = 3

    cur_hi: float = nan
    cur_lo: float = nan
    cur_hi_time: pd.Timestamp | None = None
    cur_lo_time: pd.Timestamp | None = None

    prev_highs: list[float] = field(default_factory=list)
    prev_lows: list[float] = field(default_factory=list)
    prev_hi_times: list[pd.Timestamp] = field(default_factory=list)
    prev_lo_times: list[pd.Timestamp] = field(default_factory=list)

    hi_brk_time: pd.Timestamp | None = None
    lo_brk_time: pd.Timestamp | None = None

    def rotate(self, new_period_time: pd.Timestamp) -> None:
        """Rotate current → previous on period boundary. Reset break detection."""
        if not isnan(self.cur_hi):
            self.prev_highs.insert(0, self.cur_hi)
            self.prev_hi_times.insert(0, self.cur_hi_time)
            if len(self.prev_highs) > self.history_depth:
                self.prev_highs.pop()
                self.prev_hi_times.pop()
        if not isnan(self.cur_lo):
            self.prev_lows.insert(0, self.cur_lo)
            self.prev_lo_times.insert(0, self.cur_lo_time)
            if len(self.prev_lows) > self.history_depth:
                self.prev_lows.pop()
                self.prev_lo_times.pop()

        self.cur_hi = nan
        self.cur_lo = nan
        self.cur_hi_time = None
        self.cur_lo_time = None
        self.hi_brk_time = None
        self.lo_brk_time = None


@dataclass(slots=True)
class PushZoneTickState:
    """Mutable per-TF state for push zone tick. Mirrors Pine var variables."""

    # HA run tracking (for cross-bar state)
    prev_run_hi: float = nan
    prev_run_lo: float = nan

    # Push validation
    prev_push_extreme_hi: float = nan
    prev_push_extreme_lo: float = nan

    # Trend (from period tracking breaks)
    trend: int = 0  # +1 bull, -1 bear, 0 uninitialized

    # Period tracker
    period: PeriodTracker = field(default_factory=PeriodTracker)

    # Zone arrays
    supply_zones: list[PushZone] = field(default_factory=list)
    demand_zones: list[PushZone] = field(default_factory=list)

    # Zone counting
    sup_count: int = 0
    dem_count: int = 0
    sup_reset_time: pd.Timestamp | None = None
    dem_reset_time: pd.Timestamp | None = None

    # Breaker zones (broken zones with flipped polarity)
    # When a supply zone breaks, it becomes a demand breaker; vice versa.
    supply_breakers: list[PushZone] = field(default_factory=list)  # Former demand zones
    demand_breakers: list[PushZone] = field(default_factory=list)  # Former supply zones
    MAX_BREAKERS_PER_SIDE: int = 5
