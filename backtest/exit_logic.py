"""
Exit Logic — Pure Calculation Functions
========================================

Mechanical exit rules for trailing stops, zone-based SL/TP, and fixed exits.

All functions are pure (no side effects, no file I/O, no broker calls).
Both backtest and live trading import from here.

Functions:
    - calculate_trail_level: HA body trailing stop
    - trail_ha: Trail stop using Heikin Ashi body/wick levels
    - trail_atr: Trail stop using ATR distance from max favorable price
    - calculate_zone_tp: Zone-based take profit with R:R capping
    - calculate_zone_backed_sl: SL behind nearest structural zone
    - calculate_fixed_tp: Simple ATR-multiplier take profit
    - calculate_breakeven_sl: Move SL to breakeven + buffer
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Heikin Ashi body trailing stop
# ---------------------------------------------------------------------------

def calculate_trail_level(
    ha_df: pd.DataFrame,
    direction: int,
    atr_value: float,
    buffer_mult: float = 0.25,
    timestamp: pd.Timestamp | None = None,
) -> float | None:
    """
    Calculate Heikin Ashi body trailing stop level.

    The HA timeframe MUST match the ATR timeframe used for SL/TP:
    - M5 ATR (~4 pips) requires M5 HA body (~1.5 pips) for trail to improve
    - H4 HA body (~20-50 pips) is too wide for M5 ATR-based stops

    Args:
        ha_df: Heikin Ashi DataFrame with 'body_low' and 'body_high' columns.
               Can be any timeframe -- should match ATR timeframe scale.
        direction: 1 for LONG, -1 for SHORT.
        atr_value: ATR value for buffer calculation.
        buffer_mult: Buffer multiplier applied to ATR (default 0.25).
        timestamp: If provided, filter to bars with index < timestamp (backtest
                   mode). If None, use iloc[-1] (live mode -- forming bar).

    Returns:
        Trail level as float, or None if insufficient data.
    """
    if ha_df is None or ha_df.empty:
        return None

    buffer = atr_value * buffer_mult

    if timestamp is not None:
        # Backtest mode: only bars that opened before this timestamp
        ha_times = ha_df.index[ha_df.index < timestamp]
        if len(ha_times) == 0:
            return None
        ha_candle = ha_df.loc[ha_times[-1]]
    else:
        # Live mode: use the forming (most recent) bar
        if len(ha_df) < 1:
            return None
        ha_candle = ha_df.iloc[-1]

    if direction == 1:  # Long -- trail below body low
        return float(ha_candle["body_low"] - buffer)
    else:  # Short -- trail above body high
        return float(ha_candle["body_high"] + buffer)


# ---------------------------------------------------------------------------
# Simplified trailing-stop helpers (replace TrailType enum approach)
# ---------------------------------------------------------------------------

def trail_ha(
    ha_df: pd.DataFrame,
    direction: int,
    atr_value: float,
    buffer_mult: float = 0.35,
    timestamp: pd.Timestamp | None = None,
    reference: str = "body",
) -> float | None:
    """
    Trail stop using Heikin Ashi candle levels.

    Args:
        ha_df: Heikin Ashi DataFrame.  Must contain:
               - 'body_low', 'body_high' (if reference='body')
               - 'low', 'high' (if reference='wick')
        direction: 1 for LONG, -1 for SHORT.
        atr_value: ATR value for buffer calculation.
        buffer_mult: Buffer multiplier applied to ATR (default 0.35).
        timestamp: Backtest cutoff -- bars with index < timestamp are used.
                   None = live mode (use forming bar).
        reference: 'body' uses body_low / body_high (tighter, more exits).
                   'wick' uses low / high (wider, more breathing room).

    Returns:
        Trail level as float, or None if insufficient data.
    """
    if ha_df is None or ha_df.empty:
        return None

    buffer = atr_value * buffer_mult

    if timestamp is not None:
        ha_times = ha_df.index[ha_df.index < timestamp]
        if len(ha_times) == 0:
            return None
        ha_candle = ha_df.loc[ha_times[-1]]
    else:
        if len(ha_df) < 1:
            return None
        ha_candle = ha_df.iloc[-1]

    if reference == "wick":
        low_col, high_col = "low", "high"
    else:
        low_col, high_col = "body_low", "body_high"

    if direction == 1:  # Long -- trail below the reference low
        return float(ha_candle[low_col] - buffer)
    else:  # Short -- trail above the reference high
        return float(ha_candle[high_col] + buffer)


def trail_atr(
    max_favorable_price: float,
    direction: int,
    atr_value: float,
    buffer_mult: float = 1.5,
) -> float:
    """
    Trail stop at a fixed ATR distance from the max favorable price.

    Args:
        max_favorable_price: Highest high (LONG) or lowest low (SHORT) since
                             entry.
        direction: 1 for LONG, -1 for SHORT.
        atr_value: ATR value.
        buffer_mult: Distance in ATR units (default 1.5).

    Returns:
        Trail level as float.
    """
    distance = atr_value * buffer_mult

    if direction == 1:  # Long -- trail below the highest high
        return max_favorable_price - distance
    else:  # Short -- trail above the lowest low
        return max_favorable_price + distance


# ---------------------------------------------------------------------------
# Zone-based take profit
# ---------------------------------------------------------------------------

def calculate_zone_tp(
    direction: int,
    entry_price: float,
    zone_prices: dict[str, float | None],
    atr: float,
    sl_mult: float,
    default_tp_mult: float = 3.5,
    min_rr: float = 1.5,
    max_rr: float = 5.0,
    zone_buffer_mult: float = 0.25,
) -> tuple[float, bool]:
    """
    Calculate zone-based take profit price.

    For LONG: target nearest supply zone (resistance) above entry.
    For SHORT: target nearest demand zone (support) below entry.

    Falls back to ATR-based TP if no valid zone found or R:R < min_rr.

    Args:
        direction: 1 for LONG, -1 for SHORT.
        entry_price: Entry price.
        zone_prices: Dict with optional keys:
            h1_supply_price, h1_demand_price,
            h4_supply_price, h4_demand_price.
        atr: ATR value.
        sl_mult: Stop-loss multiplier (for R:R calculation).
        default_tp_mult: Fallback TP in ATR units (default 3.5).
        min_rr: Minimum R:R ratio to accept zone-based TP (default 1.5).
        max_rr: Maximum R:R ratio cap (default 5.0).
        zone_buffer_mult: Buffer before zone in ATR units (default 0.25).

    Returns:
        Tuple of (tp_price, is_zone_based).
    """
    if zone_prices is None:
        zone_prices = {}

    sl_distance = atr * sl_mult
    zone_buffer = atr * zone_buffer_mult

    # Invalid SL distance -- fall back to ATR TP
    if sl_distance <= 0:
        if direction == 1:
            return entry_price + atr * default_tp_mult, False
        else:
            return entry_price - atr * default_tp_mult, False

    if direction == 1:  # LONG -- target supply zones above entry
        h1_supply = zone_prices.get("h1_supply_price")
        h4_supply = zone_prices.get("h4_supply_price")

        valid = [z for z in [h1_supply, h4_supply] if z is not None and z > entry_price]
        if valid:
            nearest = min(valid)
            tp_distance = nearest - entry_price - zone_buffer
            rr = tp_distance / sl_distance
            if rr >= min_rr:
                capped = min(tp_distance, sl_distance * max_rr)
                return entry_price + capped, True

        return entry_price + atr * default_tp_mult, False

    else:  # SHORT -- target demand zones below entry
        h1_demand = zone_prices.get("h1_demand_price")
        h4_demand = zone_prices.get("h4_demand_price")

        valid = [z for z in [h1_demand, h4_demand] if z is not None and z < entry_price]
        if valid:
            nearest = max(valid)
            tp_distance = entry_price - nearest - zone_buffer
            rr = tp_distance / sl_distance
            if rr >= min_rr:
                capped = min(tp_distance, sl_distance * max_rr)
                return entry_price - capped, True

        return entry_price - atr * default_tp_mult, False


# ---------------------------------------------------------------------------
# Zone-backed stop loss
# ---------------------------------------------------------------------------

def calculate_zone_backed_sl(
    entry_price: float,
    direction: int,
    atr: float,
    sl_mult: float,
    zone_data: dict[str, float | None] | None = None,
    max_sl_atr: float = 2.0,
    zone_buffer_mult: float = 0.15,
) -> tuple[float, str]:
    """
    Calculate stop loss placed behind the nearest structural zone.

    LONG: SL below nearest demand zone bottom (within max_sl_atr).
    SHORT: SL above nearest supply zone top (within max_sl_atr).
    Falls back to fixed ATR SL if no suitable zone is found.

    Args:
        entry_price: Entry price.
        direction: 1 for LONG, -1 for SHORT.
        atr: ATR value at entry.
        sl_mult: Default SL multiplier (for fallback).
        zone_data: Dict with optional keys:
            h1_demand_bottom, h1_supply_top,
            h4_demand_bottom, h4_supply_top.
        max_sl_atr: Maximum SL distance in ATR units.
        zone_buffer_mult: Buffer beyond zone edge in ATR units.

    Returns:
        Tuple of (sl_price, sl_type) where sl_type is 'zone' or 'fixed'.
    """
    fixed = _fixed_sl(entry_price, direction, atr, sl_mult)

    if zone_data is None:
        return fixed, "fixed"

    zone_buffer = atr * zone_buffer_mult
    max_distance = atr * max_sl_atr

    if direction == 1:  # LONG -- SL below demand zone
        h1_demand = zone_data.get("h1_demand_bottom")
        h4_demand = zone_data.get("h4_demand_bottom")

        candidates: list[float] = []
        for zone_price in [h1_demand, h4_demand]:
            if zone_price is not None and zone_price < entry_price:
                sl_price = zone_price - zone_buffer
                distance = entry_price - sl_price
                if 0 < distance <= max_distance:
                    candidates.append(sl_price)

        if candidates:
            # Tightest valid zone-backed SL (closest to entry)
            return max(candidates), "zone"

    else:  # SHORT -- SL above supply zone
        h1_supply = zone_data.get("h1_supply_top")
        h4_supply = zone_data.get("h4_supply_top")

        candidates = []
        for zone_price in [h1_supply, h4_supply]:
            if zone_price is not None and zone_price > entry_price:
                sl_price = zone_price + zone_buffer
                distance = sl_price - entry_price
                if 0 < distance <= max_distance:
                    candidates.append(sl_price)

        if candidates:
            # Tightest valid zone-backed SL (closest to entry)
            return min(candidates), "zone"

    return fixed, "fixed"


# ---------------------------------------------------------------------------
# Fixed helpers
# ---------------------------------------------------------------------------

def _fixed_sl(entry_price: float, direction: int, atr: float, sl_mult: float) -> float:
    """Calculate fixed ATR-based stop loss price."""
    if direction == 1:
        return entry_price - sl_mult * atr
    else:
        return entry_price + sl_mult * atr


def calculate_fixed_tp(
    entry_price: float,
    direction: int,
    atr: float,
    tp_mult: float = 3.0,
) -> float:
    """
    Calculate a simple ATR-multiplier take profit.

    Args:
        entry_price: Entry price.
        direction: 1 for LONG, -1 for SHORT.
        atr: ATR value.
        tp_mult: TP distance in ATR units (default 3.0).

    Returns:
        Take profit price.
    """
    if direction == 1:
        return entry_price + atr * tp_mult
    else:
        return entry_price - atr * tp_mult


def calculate_breakeven_sl(
    entry_price: float,
    direction: int,
    pip_size: float,
    buffer_pips: float = 1.0,
) -> float:
    """
    Move stop loss to breakeven plus a small buffer.

    Args:
        entry_price: Original entry price.
        direction: 1 for LONG, -1 for SHORT.
        pip_size: Size of one pip for the instrument (e.g. 0.0001 for
                  major forex pairs; 0.01 for JPY pairs).
        buffer_pips: Pips beyond breakeven in the favorable direction
                     (default 1.0). Covers spread + slippage.

    Returns:
        Breakeven SL price (slightly in profit).
    """
    buffer = buffer_pips * pip_size
    if direction == 1:
        return entry_price + buffer
    else:
        return entry_price - buffer


# ---------------------------------------------------------------------------
# Partial take-profit & time-based exits
# ---------------------------------------------------------------------------

def calculate_partial_tp(
    entry_price: float,
    direction: int,
    tp_levels: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    Calculate partial take-profit levels for position scaling.

    Growth mode: take half at TP1, trail remainder to TP2+.

    Args:
        entry_price: Entry price.
        direction: 1 for LONG, -1 for SHORT.
        tp_levels: List of (price_or_atr_mult, fraction_to_close) tuples.
                   Example: [(2.0, 0.5), (4.0, 0.5)] means close 50% at 2R, 50% at 4R.
                   If price_or_atr_mult is < 10, treat as ATR multiplier from entry;
                   otherwise treat as absolute price.

    Returns:
        List of (tp_price, fraction) tuples, validated and sorted by price.
    """
    if not tp_levels:
        return []

    result: list[tuple[float, float]] = []
    total_fraction = 0.0

    for tp_val, fraction in tp_levels:
        fraction = max(0.0, min(1.0 - total_fraction, fraction))
        if fraction <= 0:
            continue
        result.append((tp_val, fraction))
        total_fraction += fraction

    # Sort by distance from entry
    if direction == 1:
        result.sort(key=lambda x: x[0])
    else:
        result.sort(key=lambda x: -x[0])

    return result


def should_exit_time_based(
    entry_time: pd.Timestamp,
    current_time: pd.Timestamp,
    max_holding_bars: int | None = None,
    bar_duration_minutes: int = 15,
    avoid_rollover: bool = True,
    avoid_weekend: bool = True,
) -> tuple[bool, str]:
    """
    Check if a time-based exit should trigger.

    Args:
        entry_time: When the trade was entered.
        current_time: Current bar time.
        max_holding_bars: Maximum bars to hold (None = no limit).
        bar_duration_minutes: Minutes per bar for holding period calc.
        avoid_rollover: Exit before 23:00 UTC (death zone).
        avoid_weekend: Exit before Friday 21:00 UTC.

    Returns:
        Tuple of (should_exit, reason).
    """
    # Max holding period
    if max_holding_bars is not None:
        holding_minutes = (current_time - entry_time).total_seconds() / 60
        if holding_minutes >= max_holding_bars * bar_duration_minutes:
            return True, "max_holding"

    hour = current_time.hour
    weekday = current_time.weekday()  # 0=Mon, 4=Fri

    # Avoid rollover (23:00-01:00 UTC death zone)
    if avoid_rollover and hour >= 22:
        return True, "rollover_avoidance"

    # Avoid weekend gap (Friday after 21:00 UTC)
    if avoid_weekend and weekday == 4 and hour >= 21:
        return True, "weekend_avoidance"

    return False, ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "calculate_trail_level",
    "trail_ha",
    "trail_atr",
    "calculate_zone_tp",
    "calculate_zone_backed_sl",
    "calculate_fixed_tp",
    "calculate_breakeven_sl",
    "calculate_partial_tp",
    "should_exit_time_based",
]
