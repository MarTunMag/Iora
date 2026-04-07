#!/usr/bin/env python
"""Deep analysis of sweep results for specified symbols."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np


def analyze_symbol(symbol: str) -> None:
    csv_path = Path(f"results/{symbol}/{symbol.lower()}_retest_sweep.csv")
    if not csv_path.exists():
        print(f"  {symbol}: no CSV found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    has_trades = df[df["num_trades"] > 0]
    qual = df[df["num_trades"] >= 30].copy()

    print()
    print("=" * 80)
    print(f"  {symbol} DEEP ANALYSIS - {len(df)} configs")
    print("=" * 80)
    print(f"Configs with trades: {len(has_trades)}/{len(df)}")
    print(f"Total trades across all configs: {df['num_trades'].sum():,}")

    # ---- TOP 20 BY SQN ----
    top = qual.nlargest(20, "sqn")
    print(f"\n--- TOP 20 BY SQN (min 30 trades) ---")
    print(f"Qualified configs: {len(qual)}")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        _print_config_line(i, r)

    # ---- ENTRY MODE ----
    print(f"\n--- ENTRY MODE COMPARISON (min 30 trades) ---")
    for mode in ["market", "limit", "cascade_layered"]:
        sub = qual[qual["entry_mode"] == mode]
        if len(sub) == 0:
            print(f"  {mode}: no qualified configs")
            continue
        print(f"  {mode}:")
        print(f"    Configs: {len(sub)} | Median SQN: {sub['sqn'].median():.2f} | "
              f"Best SQN: {sub['sqn'].max():.2f} | Median WR: {sub['win_rate'].median()*100:.1f}%")
        print(f"    Median AvgR: {sub['avg_r'].median():.3f} | Median PF: {sub['profit_factor'].median():.2f} | "
              f"Median MaxDD: {sub['max_dd_r'].median():.1f}R")
        if mode == "cascade_layered":
            for sl in ["own", "htf"]:
                sl_sub = sub[sub["layered_sl_mode"] == sl]
                if len(sl_sub) > 0:
                    print(f"      SL={sl}: configs={len(sl_sub)} median_sqn={sl_sub['sqn'].median():.2f} "
                          f"best_sqn={sl_sub['sqn'].max():.2f} median_wr={sl_sub['win_rate'].median()*100:.1f}%")

    # ---- TF PAIR ----
    print(f"\n--- TF PAIR BREAKDOWN (min 30 trades) ---")
    for tf in ["M1@M5", "M1@M15", "M5@M15", "M5@H1", "M15@H1", "M15@H4", "H1@H4", "H1@D1"]:
        sub = qual[qual["tf_pair"] == tf]
        if len(sub) == 0:
            continue
        print(f"  {tf}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_trades={int(sub['num_trades'].median())} med_pf={sub['profit_factor'].median():.2f}")

    # ---- BIAS FILTER ----
    print(f"\n--- BIAS FILTER (min 30 trades) ---")
    for bias in ["any", "with_daily", "against_daily"]:
        sub = qual[qual["bias_filter"] == bias]
        if len(sub) == 0:
            continue
        print(f"  {bias}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_avgr={sub['avg_r'].median():.3f}")

    # ---- ZONE ROLE ----
    print(f"\n--- ZONE ROLE FILTER (min 30 trades) ---")
    for role in ["any", "continuation", "pullback", "push", "reversal"]:
        sub = qual[qual["zone_role_filter"] == role]
        if len(sub) == 0:
            continue
        print(f"  {role}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_avgr={sub['avg_r'].median():.3f}")

    # ---- SL MODE ----
    print(f"\n--- SL MODE (min 30 trades) ---")
    for sl in ["zone", "atr", "period", "structure"]:
        sub = qual[qual["sl_mode"] == sl]
        if len(sub) == 0:
            continue
        print(f"  {sl}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_maxdd={sub['max_dd_r'].median():.1f}R")

    # ---- FIXED RR ----
    print(f"\n--- FIXED RR COMPARISON (min 30 trades) ---")
    for rr in sorted(qual["fixed_rr"].unique()):
        sub = qual[qual["fixed_rr"] == rr]
        if len(sub) == 0:
            continue
        print(f"  RR={rr}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_avgr={sub['avg_r'].median():.3f} med_pf={sub['profit_factor'].median():.2f}")

    # ---- HMA FILTER ----
    print(f"\n--- HMA FILTER (min 30 trades) ---")
    for hf in ["any", "with_hma_h1", "with_hma_h4"]:
        sub = qual[qual["hma_filter"] == hf]
        if len(sub) == 0:
            continue
        print(f"  {hf}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}% "
              f"med_avgr={sub['avg_r'].median():.3f}")

    # ---- HMA CROSS TRIGGER ----
    print(f"\n--- HMA CROSS TRIGGER (min 30 trades) ---")
    for ct in ["none", "h1", "h4"]:
        sub = qual[qual["hma_cross_trigger"] == ct]
        if len(sub) == 0:
            continue
        print(f"  trigger={ct}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")
        if ct != "none":
            for lb in sorted(sub["hma_cross_lookback"].unique()):
                lb_sub = sub[sub["hma_cross_lookback"] == lb]
                if len(lb_sub) > 0:
                    print(f"    lookback={lb}: configs={len(lb_sub)} med_sqn={lb_sub['sqn'].median():.2f} "
                          f"best_sqn={lb_sub['sqn'].max():.2f} med_wr={lb_sub['win_rate'].median()*100:.1f}%")

    # ---- HMA SOURCE ----
    print(f"\n--- HMA SOURCE (min 30 trades) ---")
    for src in ["close", "ha_close"]:
        sub = qual[qual["hma_source"] == src]
        if len(sub) == 0:
            continue
        print(f"  source={src}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- HMA PERIOD ----
    print(f"\n--- HMA PERIOD (min 30 trades) ---")
    for p in [12, 24]:
        sub = qual[qual["hma_period"] == p]
        if len(sub) == 0:
            continue
        print(f"  period={p}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- SESSION ----
    print(f"\n--- SESSION FILTER (min 30 trades) ---")
    for sess in sorted(qual["session_filter"].unique()):
        sub = qual[qual["session_filter"] == sess]
        print(f"  {sess}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- CASCADE ----
    print(f"\n--- CASCADE FILTER (min 30 trades) ---")
    for cf in ["none", "require_htf_signal", "require_confluence_2"]:
        sub = qual[qual["cascade_filter"] == cf]
        if len(sub) == 0:
            continue
        print(f"  {cf}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- TOUCH POLICY ----
    print(f"\n--- TOUCH POLICY (min 30 trades) ---")
    for tp in ["first_touch", "until_broken"]:
        sub = qual[qual["touch_policy"] == tp]
        if len(sub) == 0:
            continue
        print(f"  {tp}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- DIRECTION ----
    print(f"\n--- DIRECTION (min 30 trades) ---")
    for d in ["both", "long", "short"]:
        sub = qual[qual["direction"] == d]
        if len(sub) == 0:
            continue
        print(f"  {d}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- AGE FILTER ----
    print(f"\n--- AGE FILTER (min 30 trades) ---")
    for age in sorted(qual["age_filter"].unique()):
        sub = qual[qual["age_filter"] == age]
        print(f"  {age}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
              f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- BIRTH PATTERN ----
    print(f"\n--- BIRTH PATTERN (min 30 trades) ---")
    for bp in sorted(qual["birth_pattern_filter"].unique()):
        sub = qual[qual["birth_pattern_filter"] == bp]
        if len(sub) > 0:
            print(f"  {bp}: configs={len(sub)} med_sqn={sub['sqn'].median():.2f} "
                  f"best_sqn={sub['sqn'].max():.2f} med_wr={sub['win_rate'].median()*100:.1f}%")

    # ---- TOP 10 BY PROFIT FACTOR ----
    top_pf = qual.nlargest(10, "profit_factor")
    print(f"\n--- TOP 10 BY PROFIT FACTOR (min 30 trades) ---")
    for i, (_, r) in enumerate(top_pf.iterrows(), 1):
        _print_config_line(i, r, extra_metric="PF")

    # ---- TOP 10 BY CALMAR ----
    top_cal = qual[qual["calmar"] < 999].nlargest(10, "calmar")
    print(f"\n--- TOP 10 BY CALMAR RATIO (min 30 trades) ---")
    for i, (_, r) in enumerate(top_cal.iterrows(), 1):
        _print_config_line(i, r, extra_metric="Calmar")

    # ---- CONSISTENCY CHECK ----
    print(f"\n--- CONSISTENCY: configs in top 50 by multiple metrics ---")
    top50_sqn = set(qual.nlargest(50, "sqn").index)
    top50_pf = set(qual.nlargest(50, "profit_factor").index)
    top50_sharpe = set(qual.nlargest(50, "sharpe").index)
    top50_calmar = set(qual[qual["calmar"] < 999].nlargest(50, "calmar").index)

    all_idx = list(top50_sqn | top50_pf | top50_sharpe | top50_calmar)
    scores = {}
    for idx in all_idx:
        s = sum([idx in top50_sqn, idx in top50_pf, idx in top50_sharpe, idx in top50_calmar])
        if s >= 3:
            scores[idx] = s

    consistent = sorted(scores.keys(), key=lambda x: (-scores[x], -qual.loc[x, "sqn"]))
    print(f"  Configs in top-50 of 3+ metrics: {len(consistent)}")
    for idx in consistent[:15]:
        r = qual.loc[idx]
        hma_info = _hma_str(r)
        entry = _entry_str(r)
        metrics_in = []
        if idx in top50_sqn:
            metrics_in.append("SQN")
        if idx in top50_pf:
            metrics_in.append("PF")
        if idx in top50_sharpe:
            metrics_in.append("Sharpe")
        if idx in top50_calmar:
            metrics_in.append("Calmar")
        print(f"  [{scores[idx]}/4] {r['tf_pair']} entry={entry} bias={r['bias_filter']} "
              f"role={r['zone_role_filter']} sl={r['sl_mode']} rr={r['fixed_rr']}{hma_info}")
        print(f"         Trades={int(r['num_trades']):,} WR={r['win_rate']*100:.1f}% SQN={r['sqn']:.2f} "
              f"PF={r['profit_factor']:.2f} Sharpe={r['sharpe']:.2f} MaxDD={r['max_dd_r']:.1f}R "
              f"({' + '.join(metrics_in)})")

    print()


def _hma_str(r) -> str:
    hma_info = ""
    if r["hma_filter"] != "any":
        hma_info += f" hma={r['hma_filter']}"
    if r["hma_cross_trigger"] != "none":
        hma_info += f" cross={r['hma_cross_trigger']}@{r['hma_cross_lookback']}"
    return hma_info


def _entry_str(r) -> str:
    entry = r["entry_mode"]
    if entry == "cascade_layered":
        entry += f"/{r['layered_sl_mode']}"
    return entry


def _print_config_line(i: int, r, extra_metric: str = "") -> None:
    hma_info = _hma_str(r)
    entry = _entry_str(r)
    print(f"  #{i}: {r['tf_pair']} | entry={entry} bias={r['bias_filter']} "
          f"role={r['zone_role_filter']} sl={r['sl_mode']} rr={r['fixed_rr']}{hma_info}")
    line2 = (f"      Trades={int(r['num_trades']):,} WR={r['win_rate']*100:.1f}% "
             f"SQN={r['sqn']:.2f} AvgR={r['avg_r']:.3f} PF={r['profit_factor']:.2f} "
             f"MaxDD={r['max_dd_r']:.1f}R Sharpe={r['sharpe']:.2f}")
    if extra_metric == "Calmar":
        line2 += f" Calmar={r['calmar']:.2f}"
    print(line2)


if __name__ == "__main__":
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["USDJPY", "XAUUSD"]
    for sym in symbols:
        analyze_symbol(sym)
