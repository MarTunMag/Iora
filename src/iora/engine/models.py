from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class ZoneSide(str, Enum):
    SUPPLY = "supply"
    DEMAND = "demand"


@dataclass(frozen=True, slots=True)
class PivotEvent:
    """
    Output of the Pine `ha_tf_data()` logic (per timeframe bar).

    This mirrors the Pine tuple:
      [hi_fire, hi_price, hi_time_v, hi_is_hh,
       lo_fire, lo_price, lo_time_v, lo_is_ll,
       ztop, zbot]
    """

    hi_fire: bool
    hi_price: float | None
    hi_time: pd.Timestamp
    hi_is_hh: bool
    lo_fire: bool
    lo_price: float | None
    lo_time: pd.Timestamp
    lo_is_ll: bool
    ztop: float | None
    zbot: float | None


@dataclass(slots=True)
class FractalZone:
    """
    Core zone object used across Grove/Pulse/Compass.

    Pine fields:
      top, bot, is_supply, is_hh_or_ll, origin_t, is_broken, seq_num
    """

    top: float
    bot: float
    is_supply: bool
    is_hh_or_ll: bool
    origin_time: pd.Timestamp
    is_broken: bool = False
    seq_num: int = 0
    is_reversal_target: bool = False  # CHoCH zone = parent reversal target

    @property
    def side(self) -> ZoneSide:
        return ZoneSide.SUPPLY if self.is_supply else ZoneSide.DEMAND

    def contains_price(self, price: float) -> bool:
        return self.bot <= price <= self.top


@dataclass(frozen=True, slots=True)
class Trendline:
    """
    Abstract representation of a Pine `line` used for push trendlines.
    Stored as two anchors in time/price space.
    """

    t1: pd.Timestamp
    p1: float
    t2: pd.Timestamp
    p2: float
    direction: str  # "bull" | "bear"
    timeframe: str  # e.g. "H4"
    is_broken: bool = False
    break_time: pd.Timestamp | None = None
    anchor_source: str = ""  # e.g. "D1" for W TL anchored to D zones
    tl_type: str = ""  # "impulse" | "correction" for XTF trendlines
    # Target zone when TL breaks — the anchor zone that becomes reversal target
    target_zone_top: float = 0.0
    target_zone_bot: float = 0.0
    target_zone_time: pd.Timestamp | None = None


@dataclass(slots=True)
class MacroBiasState:
    """
    Mirrors Pulse/Compass macro bias behavior:
      macro_bias in {-1, 0, +1}
    """

    macro_bias: int = 0
    bear_conf_fired: bool = False
    bull_conf_fired: bool = False


@dataclass(slots=True)
class StructuralCycleState:
    """
    Mirrors Pulse/Compass cycle state machine.
    """

    cycle_bear_phase: int = 0
    cycle_bull_phase: int = 0

    # key persisted levels (used for visualization + downstream signals)
    first_h4_dem_top: float | None = None
    first_h4_dem_bot: float | None = None
    first_h4_sup_top: float | None = None
    first_h4_sup_bot: float | None = None

    rev_target_h1_sup_top: float | None = None
    rev_target_h1_sup_bot: float | None = None
    rev_target_h1_dem_top: float | None = None
    rev_target_h1_dem_bot: float | None = None

    h4_tl_anchor_sup_top: float | None = None
    h4_tl_anchor_sup_bot: float | None = None
    h4_tl_anchor_dem_top: float | None = None
    h4_tl_anchor_dem_bot: float | None = None


# ---------------------------------------------------------------------------
# Canonical event IDs — match Pine alert types exactly
# ---------------------------------------------------------------------------


class EventID(str, Enum):
    ZONE_FIRE = "ZONE_FIRE"
    ZONE_BREAK = "ZONE_BREAK"
    NESTED_FIRE = "NESTED_FIRE"
    NESTED_BREAK = "NESTED_BREAK"
    TL_BREAK = "TL_BREAK"
    BIAS_BULL_CONF = "BIAS_BULL_CONF"
    BIAS_BEAR_CONF = "BIAS_BEAR_CONF"
    TERMINAL_EXHAUST = "TERMINAL_EXHAUST"
    CYCLE_PHASE = "CYCLE_PHASE"
    ENTRY_LONG = "ENTRY_LONG"
    ENTRY_SHORT = "ENTRY_SHORT"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"
    SL_HIT = "SL_HIT"
    ONE_TWO_THREE = "ONE_TWO_THREE"
    EARLY_STRUCTURE = "EARLY_STRUCTURE"


@dataclass(frozen=True, slots=True)
class Event:
    """
    A single event emitted by the engine on a specific bar.
    Carries an ID, the bar timestamp, the source timeframe, and
    an arbitrary payload dict for event-specific metadata.
    """

    id: EventID
    timestamp: pd.Timestamp
    timeframe: str
    payload: dict = field(default_factory=dict)


@dataclass(slots=True)
class BarContext:
    """
    Per-bar context delivered to tick functions.

    Holds the current bar's OHLC for the base TF, the current close,
    and aligned HTF pivot/edge columns as a dict of Series values.

    Fields:
        idx         — integer position in the base DataFrame
        timestamp   — bar open time
        open_       — base TF open
        high        — base TF high
        low         — base TF low
        close       — base TF close
        htf         — dict keyed by TF label (e.g. "H4"), each value is a
                      dict of column→value for the aligned HTF row at this bar
        edges       — dict keyed by TF label, each value is a dict of
                      column→bool for edge-detection flags (True = new HTF bar)
    """

    idx: int
    timestamp: pd.Timestamp
    open_: float
    high: float
    low: float
    close: float
    htf: dict[str, dict[str, object]] = field(default_factory=dict)
    edges: dict[str, dict[str, bool]] = field(default_factory=dict)
