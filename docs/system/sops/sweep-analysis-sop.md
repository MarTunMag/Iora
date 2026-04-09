# Sweep Analysis SOP — Standard Operating Procedure

> **Purpose:** Consistent analysis framework for ALL sweep results. Every sweep gets the same treatment.

---

## Required Metrics (per config)

| Metric | Key in compute_metrics | What it measures | Minimum viable |
|---|---|---|---|
| **total_trades** | `total_trades` | Sample size | >= 30 for any conclusion |
| **win_rate** | `win_rate` | % of trades that win | Report as % |
| **profit_factor** | `profit_factor` | gross_profit / gross_loss | > 1.5 = viable, > 2.0 = good, > 3.0 = excellent |
| **sqn** | `sqn` | (avgR / stdR) * sqrt(N) | > 2.0 = tradeable, > 5.0 = good |
| **avg_r** | `avg_r` | Average return in R-multiples | > 0 = profitable |
| **total_r** | `total_r` | Sum of all R-multiples | Total portfolio return |
| **max_dd_r** | `max_dd_r` | Maximum drawdown in R | Lower = better. > 30R = concerning |
| **avg_win_r** | `avg_win_r` | Average winning trade R | Higher = larger winners |
| **avg_loss_r** | `avg_loss_r` | Average losing trade R | Closer to -1.0 = tighter SL |
| **largest_win_r** | `largest_win_r` | Best single trade | Check for outlier dependence |
| **largest_loss_r** | `largest_loss_r` | Worst single trade | Check for tail risk |
| **max_win_streak** | `max_win_streak` | Longest winning streak | Psychology indicator |
| **max_loss_streak** | `max_loss_streak` | Longest losing streak | Psychology indicator |
| **avg_hold_hours** | `avg_hold_hours` | Average trade duration | Practical execution concern |
| **sharpe** | `sharpe` | Risk-adjusted return | > 1.0 = acceptable |
| **calmar** | `calmar` | Return / MaxDD | > 1.0 = acceptable |
| **expectancy_r** | `expectancy_r` | Expected R per trade | Same as avg_r but labelled differently |

---

## Analysis Steps (execute in order)

### Step 1: Data Quality Check

```
- Total configs in CSV
- Viable configs (30+ trades)
- Any configs with 0 trades? (filter too restrictive)
- Are all metric columns populated? (check for 0s that should be non-zero)
- Spot check: does the baseline match prior sweeps? (regression check)
```

### Step 2: Baseline Establishment

The UNFILTERED config (all filters = "any") is the baseline. Every dimension is compared against this.

```
For each symbol:
  Baseline = cascade_phase=any, bias=any, tl_break=any, all other filters=any/False/0
  Record: SQN, PF, WR, trades, avgR, maxDD
```

### Step 3: Dimension-by-Dimension Comparison

For EACH filter dimension:

```
Hold all other dimensions at baseline values.
Vary ONLY the dimension being tested.
Record: SQN, PF, WR, trades, avgR for each value.
Calculate: delta vs baseline for PF and WR.
```

**Critical:** A filter that improves PF but reduces trades needs the TOTAL R comparison too. A PF 5.0 with 100 trades may produce less total R than PF 2.5 with 3,000 trades.

### Step 4: Cross-Symbol Consistency

```
For each dimension that shows improvement on symbol A:
  Check symbol B, C, D...
  Mark as:
    UNIVERSAL: same direction improvement on 5+ of 8 symbols
    COMMON: same direction on 3-4 symbols
    SYMBOL-SPECIFIC: only helps 1-2 symbols
    INCONSISTENT: helps some, hurts others
```

**Only UNIVERSAL and COMMON dimensions go into production config.**

### Step 5: Combination Testing

```
Stack the top 2-3 PROVEN dimensions together.
Check: does the combined filter produce more or less total R than individual filters?
Beware: combining filters that both reduce trade count may produce too few trades.
```

### Step 6: Risk Assessment

```
For the top 3 configs:
  - maxDD: Is it survivable? (at 1% risk: maxDD * 1% = account drawdown %)
  - max_loss_streak: How many consecutive losses?
  - Calmar ratio: Is return/drawdown acceptable?
  - Does the config have enough trades for statistical confidence?
    Rule: need sqrt(N) * avgR / stdR > 2.0 (SQN > 2.0)
```

### Step 7: Structural Analysis (cascade-specific)

```
Zone-level analysis:
  - How many unbroken zones exist before a trendline break?
  - Does zone count 1-3 vs 4-7 vs 8+ affect outcome?
  - Do entries at zones near HTF pivots outperform?
  - Do entries at structural FVG boundaries outperform?

Trendline analysis:
  - How many TL breaks fire per TF?
  - Do impulse breaks outperform correction breaks?
  - Does TL break recency matter (lookback)?

Direction analysis:
  - Does bias alignment help? (against_daily, with_daily)
  - Is the effect consistent across symbols?
  - Does cascade phase predict entry quality?
```

### Step 8: Documentation

```
Write findings to docs/system/{sweep-name}-analysis.md
Structure:
  1. Summary table (top 5 configs)
  2. Dimension-by-dimension verdict table
  3. Cross-symbol consistency table
  4. Risk assessment for top configs
  5. Production config recommendation
  6. What to test next
  
Update docs/system/mechanical-ruleset-validated.md with new proven/disproven rules.
```

---

## Analysis Script Template

For consistent analysis, use this Python template:

```python
import pandas as pd
import sys

def analyze_sweep(csv_path, symbol):
    df = pd.read_csv(csv_path)
    v = df[df['total_trades'] >= 30]
    
    print(f"=== {symbol} SWEEP ANALYSIS ===")
    print(f"Total configs: {len(df)}, Viable: {len(v)}")
    
    # Step 1: Data quality
    zero_trades = df[df['total_trades'] == 0]
    print(f"Zero-trade configs: {len(zero_trades)}")
    for col in ['max_dd_r', 'avg_win_r', 'avg_loss_r']:
        if col in df.columns:
            nz = (df[col] != 0).sum()
            if nz == 0:
                print(f"WARNING: {col} is ALL ZEROS — metric key mismatch?")
    
    # Step 2: Baseline
    # (customize filter columns per sweep type)
    
    # Step 3: Dimension comparison
    # For each filter dimension, compare values
    
    # Step 6: Risk
    for _, r in v.sort_values('profit_factor', ascending=False).head(5).iterrows():
        print(f"PF={r['profit_factor']:.2f} WR={r['win_rate']:.1%} "
              f"trades={r['total_trades']:.0f} avgR={r['avg_r']:+.3f} "
              f"maxDD={r.get('max_dd_r', 0):.1f}")

if __name__ == "__main__":
    analyze_sweep(sys.argv[1], sys.argv[2])
```

---

## Red Flags to Watch For

| Red Flag | What It Means | Action |
|---|---|---|
| SQN > 30 | Likely inflated by high trade count, not per-trade quality | Check PF and avgR instead |
| maxDD = 0 on all configs | Metric key mismatch | Fix the runner script |
| PF > 5 with < 100 trades | Small sample, likely not robust | Need more data |
| Filter improves one symbol, hurts another | Symbol-specific, not universal | Don't include in production |
| Combined filters produce < 50 trades | Over-filtered | Use individual filters instead |
| WR > 65% with avgR < 0.5 | Lots of small wins, few big losses dominate | Check largest_loss_r |
| avg_win_r >> -avg_loss_r (10x+) | Outlier-dependent | Check if removing top 5% of winners kills profitability |
