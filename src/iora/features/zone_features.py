"""
Zone feature extraction — flat numeric/bool features from zone engine state.

Extracts per-TF zone counts, nearest zone distances, containment flags,
and UB chain counts from ZoneState.
"""

from __future__ import annotations

import math

import pandas as pd

from iora.engine.models import FractalZone
from iora.engine.zone_tick import ZoneTickState


def _nearest_zone(
    zones: list[FractalZone],
    is_supply: bool,
    close: float,
) -> tuple[float, float, pd.Timestamp]:
    """
    Find the nearest unbroken zone of the given side.

    Returns (zone_edge_price, signed_distance, origin_time).
    For supply: edge = bot (lower edge), distance = bot - close (positive = above).
    For demand: edge = top (upper edge), distance = close - top (positive = below).

    If no zone found, returns (nan, nan, NaT).
    """
    best_dist = math.inf
    best_edge = math.nan
    best_origin: pd.Timestamp = pd.NaT
    for z in zones:
        if z.is_broken:
            continue
        if z.is_supply != is_supply:
            continue
        if is_supply:
            edge = z.bot
            dist = abs(edge - close)
        else:
            edge = z.top
            dist = abs(close - edge)
        if dist < best_dist:
            best_dist = dist
            best_edge = edge
            best_origin = z.origin_time
    if math.isinf(best_dist):
        return math.nan, math.nan, pd.NaT
    signed = best_edge - close if is_supply else close - best_edge
    return best_edge, signed, best_origin


def _count_active(zones: list[FractalZone], is_supply: bool) -> int:
    """Count unbroken zones of a given side."""
    return sum(1 for z in zones if not z.is_broken and z.is_supply == is_supply)


def _price_in_zone(zones: list[FractalZone], is_supply: bool, close: float) -> bool:
    """Check if close is inside any unbroken zone of given side."""
    for z in zones:
        if z.is_broken:
            continue
        if z.is_supply != is_supply:
            continue
        if z.contains_price(close):
            return True
    return False


def extract_zone_features_for_tf(
    zone_state: ZoneTickState | None,
    close: float,
) -> dict[str, object]:
    """
    Extract flat zone features for a single TF.

    Returns dict with keys (no TF prefix — caller adds it):
        supply_count, demand_count,
        nearest_supply_edge, nearest_supply_dist,
        nearest_demand_edge, nearest_demand_dist,
        price_in_supply, price_in_demand,
        supply_seq, demand_seq
    """
    if zone_state is None:
        return {
            "supply_count": 0,
            "demand_count": 0,
            "nearest_supply_edge": math.nan,
            "nearest_supply_dist": math.nan,
            "nearest_supply_origin": pd.NaT,
            "nearest_demand_edge": math.nan,
            "nearest_demand_dist": math.nan,
            "nearest_demand_origin": pd.NaT,
            "price_in_supply": False,
            "price_in_demand": False,
            "supply_seq": 0,
            "demand_seq": 0,
        }

    all_zones = zone_state.supply_zones + zone_state.demand_zones

    sup_edge, sup_dist, sup_origin = _nearest_zone(all_zones, is_supply=True, close=close)
    dem_edge, dem_dist, dem_origin = _nearest_zone(all_zones, is_supply=False, close=close)

    return {
        "supply_count": _count_active(all_zones, is_supply=True),
        "demand_count": _count_active(all_zones, is_supply=False),
        "nearest_supply_edge": sup_edge,
        "nearest_supply_dist": sup_dist,
        "nearest_supply_origin": sup_origin,
        "nearest_demand_edge": dem_edge,
        "nearest_demand_dist": dem_dist,
        "nearest_demand_origin": dem_origin,
        "price_in_supply": _price_in_zone(all_zones, is_supply=True, close=close),
        "price_in_demand": _price_in_zone(all_zones, is_supply=False, close=close),
        "supply_seq": zone_state.seq_sup,
        "demand_seq": zone_state.seq_dem,
    }
