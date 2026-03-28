"""
Bar-by-bar iterator that yields BarContext objects.

Consumes the aligned multi-TF DataFrame produced by tf_alignment and
yields one BarContext per base-TF bar, suitable for sequential tick
processing (mirroring Pine's bar-by-bar execution model).
"""

from __future__ import annotations

from typing import Iterator

import math
import numpy as np
import pandas as pd

from iora.engine.models import BarContext
from iora.data.tf_alignment import TF_ORDER, _FIRE_COLS


def iter_bars(
    base_df: pd.DataFrame,
    aligned_df: pd.DataFrame,
    tf_list: list[str] | None = None,
) -> Iterator[BarContext]:
    """
    Yield one BarContext per bar in base_df.

    Args:
        base_df:     Base-TF OHLCV DataFrame (must have open/high/low/close).
        aligned_df:  Aligned multi-TF DataFrame from build_aligned_multi_tf().
        tf_list:     TF labels to include in htf/edges dicts.
                     Defaults to all TFs present in aligned_df.
    """
    if tf_list is None:
        # Infer TF labels from aligned column prefixes
        tf_set: set[str] = set()
        for tf in TF_ORDER:
            if any(c.startswith(f"{tf}_") for c in aligned_df.columns):
                tf_set.add(tf)
        tf_list = sorted(
            tf_set, key=lambda t: TF_ORDER.index(t) if t in TF_ORDER else 99
        )

    # Pre-extract numpy arrays for speed
    opens = base_df["open"].values.astype(float)
    highs = base_df["high"].values.astype(float)
    lows = base_df["low"].values.astype(float)
    closes = base_df["close"].values.astype(float)
    timestamps = base_df.index

    # Build per-TF column lists and pre-compute column positions
    tf_cols: dict[str, list[str]] = {}
    tf_edge_cols: dict[str, list[str]] = {}
    tf_col_positions: dict[str, list[int]] = {}
    tf_edge_col_positions: dict[str, list[int]] = {}
    for tf in tf_list:
        tf_cols[tf] = [
            c
            for c in aligned_df.columns
            if c.startswith(f"{tf}_") and "_edge_" not in c
        ]
        tf_edge_cols[tf] = [
            c for c in aligned_df.columns if c.startswith(f"{tf}_edge_")
        ]
        tf_col_positions[tf] = [aligned_df.columns.get_loc(c) for c in tf_cols[tf]]
        tf_edge_col_positions[tf] = [aligned_df.columns.get_loc(c) for c in tf_edge_cols[tf]]

    for i in range(len(base_df)):
        htf: dict[str, dict[str, object]] = {}
        edges: dict[str, dict[str, bool]] = {}

        for tf in tf_list:
            # HTF aligned values
            tf_data: dict[str, object] = {}
            for col, pos in zip(tf_cols[tf], tf_col_positions[tf]):
                # Strip TF prefix to get canonical name
                key = col[len(tf) + 1 :]  # e.g. "H4_hi_fire" → "hi_fire"
                val = aligned_df.iat[i, pos]
                # Convert numpy types to Python natives
                if isinstance(val, (np.bool_,)):
                    val = bool(val)
                elif isinstance(val, (np.integer,)):
                    val = int(val)
                elif isinstance(val, (np.floating,)):
                    val = float(val) if not np.isnan(val) else None
                tf_data[key] = val
            htf[tf] = tf_data

            # Edge flags
            edge_data: dict[str, bool] = {}
            for col, pos in zip(tf_edge_cols[tf], tf_edge_col_positions[tf]):
                key = col[len(tf) + 1 :]  # e.g. "H4_edge_hi_fire" → "edge_hi_fire"
                val = aligned_df.iat[i, pos]
                edge_data[key] = (
                    bool(val)
                    if not (isinstance(val, float) and math.isnan(val))
                    else False
                )
            edges[tf] = edge_data

        yield BarContext(
            idx=i,
            timestamp=timestamps[i],
            open_=float(opens[i]),
            high=float(highs[i]),
            low=float(lows[i]),
            close=float(closes[i]),
            htf=htf,
            edges=edges,
        )
