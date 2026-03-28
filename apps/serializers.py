"""
Serialization helpers — convert engine output (zones, trendlines, signals, HTF candles)
to LW Charts JSON format.

Extracted from chart_viewer_lw.py for separation of concerns.
"""

from __future__ import annotations

import pandas as pd

from iora.constants import TF_SECONDS
from iora.indicators.heikin_ashi import calculate_heikin_ashi
from iora.orchestrator.pipeline import PipelineOutput


def ts(t) -> int:
    """Convert pandas Timestamp to Unix seconds for LW Charts."""
    if isinstance(t, pd.Timestamp):
        return int(t.timestamp())
    return int(pd.Timestamp(t).timestamp())


def df_to_candles(df: pd.DataFrame) -> list[dict]:
    """Fast vectorized OHLCV → LW Charts format."""
    times = (df.index.astype("int64") // 10**9).tolist()
    opens = df["open"].round(6).tolist()
    highs = df["high"].round(6).tolist()
    lows = df["low"].round(6).tolist()
    closes = df["close"].round(6).tolist()
    return [
        {"time": t, "open": o, "high": h, "low": l, "close": c}
        for t, o, h, l, c in zip(times, opens, highs, lows, closes)
    ]


def serialize_ohlcv(df: pd.DataFrame, candle_type: str = "ohlc") -> list[dict]:
    """Convert DataFrame to LW Charts candlestick data format."""
    if candle_type == "ha":
        return df_to_candles(calculate_heikin_ashi(df))
    return df_to_candles(df)


def serialize_zones(pulse: PipelineOutput) -> dict:
    """Serialize zones by TF for client rendering."""
    result = {}
    for tf, zones in pulse.zones_by_tf.items():
        tf_zones = []

        # Compute unbroken chain counts per side (5+3 exhaustion model)
        # Walk zones in order, counting consecutive unbroken on each side
        sup_chain = 0
        dem_chain = 0
        chain_map: dict[int, int] = {}  # zone index → chain position
        for i, z in enumerate(zones):
            if z.is_supply and not z.is_broken:
                sup_chain += 1
                chain_map[i] = sup_chain
            elif z.is_supply and z.is_broken:
                sup_chain = 0  # reset on break
            elif not z.is_supply and not z.is_broken:
                dem_chain += 1
                chain_map[i] = dem_chain
            elif not z.is_supply and z.is_broken:
                dem_chain = 0  # reset on break

        for i, z in enumerate(zones):
            if z.is_supply:
                struct = "HH" if z.is_hh_or_ll else "LH"
            else:
                struct = "LL" if z.is_hh_or_ll else "HL"
            zd = {
                "top": z.top,
                "bot": z.bot,
                "is_supply": z.is_supply,
                "is_hh_or_ll": z.is_hh_or_ll,
                "struct": struct,
                "origin_time": ts(z.origin_time),
                "is_broken": z.is_broken,
            }
            if i in chain_map:
                zd["chain_pos"] = chain_map[i]
            if z.is_reversal_target:
                zd["is_reversal_target"] = True
            tf_zones.append(zd)
        result[tf] = tf_zones
    return result


def _serialize_tl(tl, active: bool) -> dict:
    """Serialize a single Trendline to JSON dict."""
    d = {
        "t1": ts(tl.t1),
        "p1": tl.p1,
        "t2": ts(tl.t2),
        "p2": tl.p2,
        "direction": tl.direction,
        "tf": tl.timeframe,
        "active": active and not tl.is_broken,
    }
    if tl.is_broken:
        d["is_broken"] = True
        if tl.break_time is not None:
            d["break_time"] = ts(tl.break_time)
            # Interpolate TL price at break time for break marker
            if tl.t1 != tl.t2:
                t1_epoch = tl.t1.timestamp()
                t2_epoch = tl.t2.timestamp()
                bt_epoch = tl.break_time.timestamp()
                frac = (bt_epoch - t1_epoch) / (t2_epoch - t1_epoch)
                d["break_price"] = tl.p1 + frac * (tl.p2 - tl.p1)
    if tl.anchor_source:
        d["anchor_source"] = tl.anchor_source
        d["xtf"] = True
    if tl.tl_type:
        d["tl_type"] = tl.tl_type
    # Target zone — where price pushes back to after TL break
    if tl.is_broken and tl.target_zone_top > 0:
        d["target_zone"] = {
            "top": tl.target_zone_top,
            "bot": tl.target_zone_bot,
            "time": ts(tl.target_zone_time) if tl.target_zone_time else None,
        }
    return d


def serialize_trendlines(pulse: PipelineOutput) -> dict:
    """Serialize trendlines by TF (regular + cross-TF zone-anchored)."""
    result = {}
    # Regular pivot-based trendlines
    for tf, tl_state in pulse.tl_states.items():
        tls = []
        for tl in [tl_state.bull_active, tl_state.bear_active]:
            if tl is not None:
                tls.append(_serialize_tl(tl, active=True))
        for tl in list(tl_state.bull_history) + list(tl_state.bear_history):
            tls.append(_serialize_tl(tl, active=False))
        if tls:
            result[tf] = tls

    # Cross-TF zone-anchored trendlines (merged into same TF keys)
    from iora.engine.xtf_trendline import get_all_xtf_trendlines
    for tf, xtf_state in pulse.xtf_tl_states.items():
        all_xtf = get_all_xtf_trendlines(xtf_state)
        xtf_tls = []
        for tl in all_xtf:
            is_active = not tl.is_broken and tl in [
                xtf_state.imp_bull.active, xtf_state.imp_bear.active,
                xtf_state.cor_bull.active, xtf_state.cor_bear.active,
            ]
            xtf_tls.append(_serialize_tl(tl, active=is_active))
        if xtf_tls:
            if tf in result:
                result[tf].extend(xtf_tls)
            else:
                result[tf] = xtf_tls
    return result


def serialize_signals(signals) -> list[dict]:
    """Convert Signal objects to LW Charts marker format."""
    result = []
    for s in signals:
        if s.viz_priority > 2:
            continue
        result.append({
            "time": ts(s.time),
            "position": "belowBar" if s.direction == "bull" else "aboveBar",
            "color": s.viz_color,
            "shape": s.viz_shape,
            "size": s.viz_size,
            "text": f"{s.signal_type}: {s.details}",
        })
    return result


def serialize_htf_candles(
    htf_data: dict[str, pd.DataFrame], candle_type: str = "ohlc"
) -> dict:
    """Serialize HTF candle data with time_end for proper width rendering."""
    result = {}
    for tf, df in htf_data.items():
        if df.empty:
            continue
        src = calculate_heikin_ashi(df) if candle_type == "ha" else df
        times = (src.index.astype("int64") // 10**9).tolist()
        opens = src["open"].round(6).tolist()
        highs = src["high"].round(6).tolist()
        lows = src["low"].round(6).tolist()
        closes = src["close"].round(6).tolist()
        candles = []
        for i in range(len(times)):
            if i + 1 < len(times):
                time_end = times[i + 1]
            else:
                time_end = times[i] + TF_SECONDS.get(tf, 86400)
            candles.append(
                {
                    "time": times[i],
                    "time_end": time_end,
                    "open": opens[i],
                    "high": highs[i],
                    "low": lows[i],
                    "close": closes[i],
                }
            )
        result[tf] = candles
    return result


# ── Structure serialization ──────────────────────────────────────────────


def _structure_zone_dict(z) -> dict:
    """Convert a single ZoneResult zone to a JSON-safe dict with lifecycle."""
    if not z.is_broken:
        lifecycle = "active"
    elif not z.label:
        lifecycle = "expired"
    elif z.label in ("HH", "LL"):
        lifecycle = "breaker"
    else:
        lifecycle = "mitigation"

    return {
        "top": z.top, "bot": z.bot, "is_supply": z.is_supply,
        "origin_time": z.origin_time.isoformat(),
        "confirm_time": z.confirm_time.isoformat(),
        "label": z.label, "is_broken": z.is_broken,
        "break_time": z.break_time.isoformat() if z.break_time else None,
        "lifecycle": lifecycle,
    }


def _serialize_events(state) -> list[dict]:
    """Convert StructureState events to JSON-safe dicts."""
    if not state:
        return []
    return [
        {
            "time": e.time.isoformat(),
            "price": e.price,
            "break_type": e.break_type,
            "is_external": e.is_external,
            "label": e.label,
            "direction": e.direction,
            "zone_label": e.zone_label,
            "zone_origin_time": e.zone_origin_time.isoformat(),
        }
        for e in state.events
    ]


def _serialize_zigzag(zones, is_external: bool = False) -> list[dict]:
    """Build zigzag vertices from zone list."""
    suffix = "+" if is_external else ""
    return [
        {
            "time": z.confirm_time.isoformat(),
            "price": z.top if z.is_supply else z.bot,
            "label": (z.label + suffix) if z.label else ("" if is_external else z.label),
            "is_external": is_external,
        }
        for z in zones
    ]


def serialize_structure(data: dict, tf: str, max_zones: int = 50) -> dict:
    """Serialize full structure response (child + parent + sub zones, events, zigzag).

    ``data`` is the dict returned by ``_get_structure()`` in chart_viewer_lw.py.
    """
    child_result = data["child"]
    parent_result = data["parent"]
    sub_result = data["sub"]
    state = data["state"]
    sub_state = data.get("sub_state")
    parent_tf = data["parent_tf"]
    sub_tf = data.get("sub_tf")

    child_zones = [_structure_zone_dict(z) for z in child_result.zones[-max_zones:]]
    parent_zones = [_structure_zone_dict(z) for z in parent_result.zones[-max_zones:]]
    sub_zones = [_structure_zone_dict(z) for z in sub_result.zones[-max_zones:]]

    events = _serialize_events(state)
    sub_events = _serialize_events(sub_state)

    # External boundary levels
    ext_high = None
    ext_low = None
    if state and state.external_high:
        ext_high = {"price": state.external_high.price, "time": state.external_high.time.isoformat()}
    if state and state.external_low:
        ext_low = {"price": state.external_low.price, "time": state.external_low.time.isoformat()}

    # Zigzag — child + parent merged and sorted
    zigzag = _serialize_zigzag(child_result.zones) + _serialize_zigzag(parent_result.zones, is_external=True)
    zigzag.sort(key=lambda v: v["time"])

    sub_zigzag = _serialize_zigzag(sub_result.zones)

    return {
        "child_zones": child_zones,
        "parent_zones": parent_zones,
        "sub_zones": sub_zones,
        "events": events,
        "sub_events": sub_events,
        "external_high": ext_high,
        "external_low": ext_low,
        "zigzag": zigzag,
        "sub_zigzag": sub_zigzag,
        "child_bias": child_result.bias,
        "parent_bias": parent_result.bias,
        "sub_bias": sub_result.bias,
        "chain_count": state.chain_count if state else 0,
        "child_tf": tf,
        "parent_tf": parent_tf or "",
        "sub_tf": sub_tf or "",
    }
