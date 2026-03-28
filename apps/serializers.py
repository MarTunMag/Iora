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
