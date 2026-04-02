from __future__ import annotations

import numpy as np
import pandas as pd

from iora.indicators.heikin_ashi import calculate_heikin_ashi
from iora.engine.models import PivotEvent

# Max bars to look back for pivot extremes (supply/demand zone width)
PIVOT_LOOKBACK_LIMIT = 20


def compute_pivot_events(ohlc: pd.DataFrame, doji_pct: float = 5.0) -> pd.DataFrame:
    """
    Python port scaffold of Pine `ha_tf_data(i_doji)`.

    This produces per-bar columns corresponding to the Pine tuple.
    It is designed to be deterministic and suitable for multi-timeframe alignment.

    Notes / parity:
    - Pine keeps `prev_hi/prev_lo` as var state in the security context.
      Here we compute state sequentially across bars of the input dataframe.
    - The pivot search loops back up to 20 bars while HA color remains the prior color.
    - Zone top/bottom follow the Pine logic including doji handling.
    """
    if ohlc.empty:
        return pd.DataFrame(index=ohlc.index)

    ha = calculate_heikin_ashi(ohlc)
    is_blue = ha["close"].values >= ha["open"].values
    is_red = ~is_blue

    high = ohlc["high"].astype(float).values
    low = ohlc["low"].astype(float).values

    ha_h = ha["high"].astype(float).values
    ha_l = ha["low"].astype(float).values
    ha_c = ha["close"].astype(float).values
    ha_o = ha["open"].astype(float).values

    prev_hi = np.nan
    prev_lo = np.nan

    n = len(ohlc)
    hi_fire = np.zeros(n, dtype=bool)
    hi_price = np.full(n, np.nan, dtype=float)
    hi_time = np.array(ohlc.index, dtype="datetime64[ns]")
    hi_is_hh = np.zeros(n, dtype=bool)

    lo_fire = np.zeros(n, dtype=bool)
    lo_price = np.full(n, np.nan, dtype=float)
    lo_time = np.array(ohlc.index, dtype="datetime64[ns]")
    lo_is_ll = np.zeros(n, dtype=bool)

    ztop = np.full(n, np.nan, dtype=float)
    zbot = np.full(n, np.nan, dtype=float)

    seq_hh = np.full(n, np.nan, dtype=float)
    seq_ll = np.full(n, np.nan, dtype=float)
    hi_txt = np.full(n, "", dtype=object)
    lo_txt = np.full(n, "", dtype=object)

    for i in range(1, n):
        # Supply pivot: current bar is red, previous was blue
        if is_red[i] and is_blue[i - 1]:
            rhi_ha = ha_h[i - 1]
            rhi = high[i - 1]
            ext_i = i - 1
            k = 2
            while k < PIVOT_LOOKBACK_LIMIT and (i - k) >= 0 and is_blue[i - k]:
                rhi_ha = max(rhi_ha, ha_h[i - k])
                if high[i - k] > rhi:
                    rhi = high[i - k]
                    ext_i = i - k
                k += 1

            body = abs(ha_c[i] - ha_o[i])
            rng = ha_h[i] - ha_l[i]
            doji = bool(rng > 0.0 and (body / rng * 100.0) < doji_pct)

            hi_fire[i] = True
            hi_price[i] = rhi
            hi_time[i] = ohlc.index[ext_i].to_datetime64()
            hi_is_hh[i] = bool(np.isnan(prev_hi) or rhi > prev_hi)
            prev_hi = rhi

            seq_hh[i] = rhi
            hi_txt[i] = "HH" if hi_is_hh[i] else "LH"

            ztop[i] = rhi
            zbot[i] = ha_l[i] if doji else ha_l[i - 1]

        # Demand pivot: current bar is blue, previous was red
        elif is_blue[i] and is_red[i - 1]:
            rlo_ha = ha_l[i - 1]
            rlo = low[i - 1]
            ext_i = i - 1
            k = 2
            while k < PIVOT_LOOKBACK_LIMIT and (i - k) >= 0 and is_red[i - k]:
                rlo_ha = min(rlo_ha, ha_l[i - k])
                if low[i - k] < rlo:
                    rlo = low[i - k]
                    ext_i = i - k
                k += 1

            body = abs(ha_c[i] - ha_o[i])
            rng = ha_h[i] - ha_l[i]
            doji = bool(rng > 0.0 and (body / rng * 100.0) < doji_pct)

            lo_fire[i] = True
            lo_price[i] = rlo
            lo_time[i] = ohlc.index[ext_i].to_datetime64()
            lo_is_ll[i] = bool(np.isnan(prev_lo) or rlo < prev_lo)
            prev_lo = rlo

            seq_ll[i] = rlo
            lo_txt[i] = "LL" if lo_is_ll[i] else "HL"

            ztop[i] = ha_h[i] if doji else ha_h[i - 1]
            zbot[i] = rlo

    out = pd.DataFrame(
        {
            "hi_fire": hi_fire,
            "hi_price": hi_price,
            "hi_time": pd.to_datetime(hi_time),
            "hi_is_hh": hi_is_hh,
            "lo_fire": lo_fire,
            "lo_price": lo_price,
            "lo_time": pd.to_datetime(lo_time),
            "lo_is_ll": lo_is_ll,
            "seq_hh": seq_hh,
            "seq_ll": seq_ll,
            "hi_txt": hi_txt,
            "lo_txt": lo_txt,
            "ztop": ztop,
            "zbot": zbot,
        },
        index=ohlc.index,
    )
    return out


def align_events_to_base(
    events_df: pd.DataFrame, base_index: pd.DatetimeIndex
) -> pd.DataFrame:
    """
    Align higher-timeframe events to a base timeframe index using strict < matching
    (no lookahead), similar to how fib anchors are aligned.
    """
    if events_df.empty:
        return pd.DataFrame(index=base_index)

    left = pd.DataFrame({"_ts": base_index}, index=base_index).sort_index()
    right = events_df.sort_index()
    aligned = pd.merge_asof(
        left,
        right,
        left_index=True,
        right_index=True,
        direction="backward",
        allow_exact_matches=False,
    )
    aligned = aligned.drop(columns=["_ts"])
    return aligned
