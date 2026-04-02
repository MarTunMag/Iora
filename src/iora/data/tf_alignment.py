"""
Multi-TF alignment and edge detection.

Builds a single aligned DataFrame where each base-TF bar carries the
latest-known HTF pivot data (backward merge_asof, no lookahead) plus
boolean edge columns that fire True on the first base bar after an HTF
pivot value changes.

Pine parity note:
  Pine's `request.security()` returns HTF values that update on HTF bar close
  and remain constant until the next close. We replicate this by shifting
  HTF event timestamps forward by one HTF period before merge_asof — so a
  D1 pivot computed from the March 10 candle only becomes visible to base-TF
  bars after March 11 00:00 (when the D1 candle is confirmed closed).
  Edge detection uses `val and not val[1]` (diff-on-aligned columns).
"""

from __future__ import annotations

import pandas as pd

from iora.engine.ha_pivots import compute_pivot_events, align_events_to_base

# Re-export from canonical source for backward compatibility
from iora.constants import ENGINE_TF_ORDER as TF_ORDER  # noqa: F401

# TF label → duration of one candle (for closed-candle shift)
_TF_PERIODS: dict[str, pd.Timedelta | pd.DateOffset] = {
    "M1": pd.Timedelta(minutes=1),
    "M5": pd.Timedelta(minutes=5),
    "M15": pd.Timedelta(minutes=15),
    "M30": pd.Timedelta(minutes=30),
    "H1": pd.Timedelta(hours=1),
    "H4": pd.Timedelta(hours=4),
    "D1": pd.Timedelta(days=1),
    "W1": pd.Timedelta(weeks=1),
    "MN1": pd.DateOffset(months=1),
}

# Columns from compute_pivot_events that carry pivot fire flags
_FIRE_COLS = ["hi_fire", "lo_fire"]

# All pivot event columns
_EVENT_COLS = [
    "hi_fire",
    "hi_price",
    "hi_time",
    "hi_is_hh",
    "lo_fire",
    "lo_price",
    "lo_time",
    "lo_is_ll",
    "ztop",
    "zbot",
    # Push zone extensions
    "seq_hh",
    "seq_ll",
    "hi_txt",
    "lo_txt",
]


def build_aligned_multi_tf(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    doji_pct: float = 5.0,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    For each TF in data_by_tf, compute pivot events and align to the base TF
    index. Returns:

        aligned_df : DataFrame indexed by base TF, with columns prefixed by TF
                     label (e.g. "H4_hi_fire", "H4_ztop", "H4_edge_hi_fire").
        events_raw : dict[tf_label → raw pivot events DataFrame] for reference.

    Edge columns ("*_edge_hi_fire", "*_edge_lo_fire") are True on the first
    base bar where the aligned fire flag flips from False to True.
    """
    base_df = data_by_tf.get(base_tf)
    if base_df is None or base_df.empty:
        raise ValueError(f"Base TF '{base_tf}' not found or empty in data_by_tf")

    base_index = base_df.index
    events_raw: dict[str, pd.DataFrame] = {}
    aligned_parts: list[pd.DataFrame] = []

    for tf_label in TF_ORDER:
        tf_ohlc = data_by_tf.get(tf_label)
        if tf_ohlc is None or tf_ohlc.empty:
            continue

        # Compute pivot events for this TF
        ev = compute_pivot_events(tf_ohlc, doji_pct=doji_pct)
        events_raw[tf_label] = ev

        if tf_label == base_tf:
            # Same TF — no alignment needed, but still detect edges
            aligned = ev.reindex(base_index)
        else:
            # Shift HTF event timestamps forward by one HTF period.
            # This ensures pivots only become visible to base-TF bars
            # AFTER the HTF candle that produced them has closed.
            # Without this shift, a D1 zone would appear at M15 00:15
            # on the same day — 24h before the D1 candle closes.
            period = _TF_PERIODS.get(tf_label)
            if period is not None:
                ev = ev.copy()
                ev.index = ev.index + period

            # Align HTF → base TF (backward, no exact match, no lookahead)
            aligned = align_events_to_base(ev, base_index)

        # Prefix columns with TF label
        prefixed = aligned.copy()
        prefixed.columns = [f"{tf_label}_{c}" for c in aligned.columns]

        # Edge detection: fire flag was False on previous bar, True now
        for fc in _FIRE_COLS:
            col = f"{tf_label}_{fc}"
            if col in prefixed.columns:
                series = prefixed[col].where(prefixed[col].notna(), False).astype(bool)
                edge = series & ~series.shift(1, fill_value=False)
                prefixed[f"{tf_label}_edge_{fc}"] = edge

        # Period boundary detection: True on first base bar of new TF period
        if tf_label == base_tf:
            prefixed[f"{tf_label}_new_period"] = True
        else:
            # Detect when the aligned HTF period changes from base TF perspective
            tf_time_series = pd.Series(ev.index, index=ev.index, name="tf_time")
            left_for_period = pd.DataFrame({"_ts": base_index}, index=base_index).sort_index()
            tf_time_aligned = pd.merge_asof(
                left_for_period, tf_time_series.to_frame(),
                left_index=True, right_index=True,
                direction="backward", allow_exact_matches=True,
            )["tf_time"]
            prefixed[f"{tf_label}_new_period"] = tf_time_aligned != tf_time_aligned.shift(1)

        aligned_parts.append(prefixed)

    aligned_df = (
        pd.concat(aligned_parts, axis=1)
        if aligned_parts
        else pd.DataFrame(index=base_index)
    )
    return aligned_df, events_raw


def detect_edges_for_tf(
    aligned_col: pd.Series,
) -> pd.Series:
    """
    Generic edge detector: returns True on bars where the input series
    transitions from falsy to truthy.
    """
    s = aligned_col.where(aligned_col.notna(), False).astype(bool)
    return s & ~s.shift(1, fill_value=False)
