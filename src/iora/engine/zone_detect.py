"""
Generic HA zone detection for any timeframe.

Composable pipeline:
  1. detect_zones(df)       -> raw zones from HA color flips
  2. classify_zones(zones)  -> zones with HH/LH/HL/LL labels
  3. detect_breaks(zones, df) -> zones updated with breaks + StructureBreak events
  4. derive_bias(zones)     -> directional bias from last unbroken supply/demand
  5. compute_structure(df)  -> ZoneResult bundling all steps

Zone detection rules:
  - Demand (red->blue): bot = lowest OHLC low of red run, top = HA high of last red bar
  - Supply (blue->red): top = highest OHLC high of blue run, bot = HA low of last blue bar
  - Doji trigger: if trigger bar is doji, use trigger bar's HA values instead of [i-1]
  - Zones with top <= bot are skipped

Classification:
  - Supply: top > prev_supply.top -> HH, else -> LH
  - Demand: bot < prev_demand.bot -> LL, else -> HL

Break detection (body close rule -- wicks are liquidity sweeps, not breaks):
  - Supply broken if candle close > zone.top; demand broken if candle close < zone.bot
  - HH/LL break -> BOS (trend continuation); LH/HL break -> CHoCH (reversal warning)
  - Only candle body closes after confirm_time count as breaks (no lookahead)

Bias derivation:
  - Most recent unbroken supply LH + demand LL -> bearish
  - Most recent unbroken supply HH + demand HL -> bullish
  - Otherwise -> neutral
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from iora.indicators.heikin_ashi import calculate_heikin_ashi


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Zone:
    top: float
    bot: float
    is_supply: bool
    origin_time: pd.Timestamp      # time of the price extreme
    confirm_time: pd.Timestamp     # time of the HA flip bar (trigger)
    label: str                     # "HH" | "LH" | "HL" | "LL" | ""
    is_broken: bool
    break_time: pd.Timestamp | None


@dataclass(frozen=True, slots=True)
class StructureBreak:
    time: pd.Timestamp
    price: float
    zone_origin_time: pd.Timestamp  # which zone was broken
    break_type: str                 # "BOS" | "CHoCH"
    direction: str                  # "bullish" | "bearish"
    label: str                      # "HH" | "LH" | "HL" | "LL"


@dataclass(frozen=True, slots=True)
class ZoneResult:
    zones: list[Zone]
    breaks: list[StructureBreak]
    bias: str                       # "bullish" | "bearish" | "neutral"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_doji(
    ha_open: float, ha_close: float,
    ha_high: float, ha_low: float,
    doji_pct: float,
) -> bool:
    """Return True if HA candle body is smaller than doji_pct% of the range."""
    body = abs(ha_close - ha_open)
    rng = ha_high - ha_low
    if rng <= 0:
        return False
    return (body / rng * 100) < doji_pct


# ---------------------------------------------------------------------------
# Pipeline step 1: detect zones from HA color flips
# ---------------------------------------------------------------------------

def detect_zones(df: pd.DataFrame, doji_pct: float = 5.0) -> list[Zone]:
    """Detect supply/demand zones from HA color flips. Returns unlabelled zones."""
    if df.empty or len(df) < 2:
        return []

    ha = calculate_heikin_ashi(df)
    if ha.empty:
        return []

    ohlc_high = df["high"].values
    ohlc_low = df["low"].values
    times = df.index

    ha_open = ha["open"].values
    ha_high = ha["high"].values
    ha_low = ha["low"].values
    ha_close = ha["close"].values

    is_blue = [ha_close[i] >= ha_open[i] for i in range(len(ha))]

    zones: list[Zone] = []

    for i in range(1, len(df)):
        prev_blue = is_blue[i - 1]
        curr_blue = is_blue[i]

        # Red -> blue: demand zone
        if not prev_blue and curr_blue:
            # Walk back through red run (max 50 bars)
            run_start = max(0, i - 50)
            j = i - 1
            while j > run_start and not is_blue[j]:
                j -= 1
            red_run_start = j + 1 if is_blue[j] else j

            bot = float("inf")
            bot_time = times[red_run_start]
            for k in range(red_run_start, i):
                if ohlc_low[k] < bot:
                    bot = ohlc_low[k]
                    bot_time = times[k]

            trigger_is_doji = _is_doji(
                ha_open[i], ha_close[i], ha_high[i], ha_low[i], doji_pct,
            )
            top = float(ha_high[i]) if trigger_is_doji else float(ha_high[i - 1])

            if top > bot:
                zones.append(Zone(
                    top=top, bot=bot, is_supply=False,
                    origin_time=bot_time, confirm_time=times[i],
                    label="", is_broken=False, break_time=None,
                ))

        # Blue -> red: supply zone
        elif prev_blue and not curr_blue:
            run_start = max(0, i - 50)
            j = i - 1
            while j > run_start and is_blue[j]:
                j -= 1
            blue_run_start = j + 1 if not is_blue[j] else j

            top = float("-inf")
            top_time = times[blue_run_start]
            for k in range(blue_run_start, i):
                if ohlc_high[k] > top:
                    top = ohlc_high[k]
                    top_time = times[k]

            trigger_is_doji = _is_doji(
                ha_open[i], ha_close[i], ha_high[i], ha_low[i], doji_pct,
            )
            bot = float(ha_low[i]) if trigger_is_doji else float(ha_low[i - 1])

            if top > bot:
                zones.append(Zone(
                    top=top, bot=bot, is_supply=True,
                    origin_time=top_time, confirm_time=times[i],
                    label="", is_broken=False, break_time=None,
                ))

    return zones


# ---------------------------------------------------------------------------
# Pipeline step 2: classify zones (HH/LH/HL/LL)
# ---------------------------------------------------------------------------

def classify_zones(zones: list[Zone]) -> list[Zone]:
    """Assign HH/LH/HL/LL labels by comparing each zone to the previous same-side zone."""
    result: list[Zone] = []
    prev_supply_hi: float | None = None
    prev_demand_lo: float | None = None

    for z in zones:
        if z.is_supply:
            if prev_supply_hi is None or z.top > prev_supply_hi:
                label = "HH"
            else:
                label = "LH"
            prev_supply_hi = z.top
        else:
            if prev_demand_lo is None or z.bot < prev_demand_lo:
                label = "LL"
            else:
                label = "HL"
            prev_demand_lo = z.bot

        result.append(replace(z, label=label))

    return result


# ---------------------------------------------------------------------------
# Pipeline step 3: detect zone breaks -> BOS / CHoCH
# ---------------------------------------------------------------------------

def detect_breaks(
    zones: list[Zone], df: pd.DataFrame,
) -> tuple[list[Zone], list[StructureBreak]]:
    """Walk bars and detect zone breaks. Returns updated zones + break events.

    Break rule: body close — supply broken if close > zone.top,
    demand broken if close < zone.bot. Wicks are liquidity sweeps, not breaks.
    """
    if df.empty or not zones:
        return zones, []

    close = df["close"].values
    times = df.index

    # Mutable list — replace broken zones by index
    updated: list[Zone] = list(zones)
    breaks: list[StructureBreak] = []

    for i in range(len(df)):
        bar_time = times[i]
        for zi, z in enumerate(updated):
            if z.is_broken:
                continue
            # Only check bars after the zone was confirmed (no lookahead)
            if bar_time <= z.confirm_time:
                continue

            broken = False
            if z.is_supply and close[i] > z.top:
                broken = True
            elif not z.is_supply and close[i] < z.bot:
                broken = True

            if broken:
                updated[zi] = replace(z, is_broken=True, break_time=bar_time)

                # BOS if HH/LL (trend), CHoCH if LH/HL (reversal)
                break_type = "BOS" if z.label in ("HH", "LL") else "CHoCH"
                direction = "bullish" if z.is_supply else "bearish"
                price = float(close[i])

                breaks.append(StructureBreak(
                    time=bar_time,
                    price=price,
                    zone_origin_time=z.origin_time,
                    break_type=break_type,
                    direction=direction,
                    label=z.label,
                ))

    return updated, breaks


# ---------------------------------------------------------------------------
# Pipeline step 4: derive bias from most recent unbroken zones
# ---------------------------------------------------------------------------

def derive_bias(zones: list[Zone]) -> str:
    """Derive directional bias from the most recent unbroken supply + demand labels."""
    last_supply_label: str | None = None
    last_demand_label: str | None = None

    for z in zones:
        if not z.is_broken:
            if z.is_supply:
                last_supply_label = z.label
            else:
                last_demand_label = z.label

    if last_supply_label is None or last_demand_label is None:
        return "neutral"
    if last_supply_label == "LH" and last_demand_label == "LL":
        return "bearish"
    if last_supply_label == "HH" and last_demand_label == "HL":
        return "bullish"
    return "neutral"


# ---------------------------------------------------------------------------
# Composed pipeline
# ---------------------------------------------------------------------------

def compute_structure(df: pd.DataFrame, doji_pct: float = 5.0) -> ZoneResult:
    """
    Full pipeline: detect zones -> classify -> detect breaks -> derive bias.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with columns open, high, low, close and a DatetimeIndex.
        Works for any timeframe.
    doji_pct : float
        Body-to-range threshold (%) below which a candle is treated as doji.

    Returns
    -------
    ZoneResult
        All zones (broken + unbroken), all BOS/CHoCH events, and derived bias.
    """
    zones = detect_zones(df, doji_pct)
    zones = classify_zones(zones)
    zones, breaks = detect_breaks(zones, df)
    bias = derive_bias(zones)
    return ZoneResult(zones=zones, breaks=breaks, bias=bias)
