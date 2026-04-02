# Backtest Evaluation Pipeline Design Spec

Wire the signal engine into the existing backtest framework so we can run
Growth lifecycle trades on historical data, measure performance, and identify
which signal contexts produce winners vs losers.

## Context

**What exists:**
- `run_signal_engine()` produces `SignalEngineOutput` with `trade_log`,
  `signals`, `final_position`, and full `PipelineOutput`.
- `TradeRecord` (frozen dataclass) — complete entry→exit trade with P&L, R-multiple,
  exit reason, mode, costs.
- `PerformanceMetrics` — SQN, Sharpe, Sortino, Calmar, win rate, expectancy,
  drawdown, streaks, monthly/weekly/daily returns, trade statistics.
- `CostCalculator` — session-aware spreads (ICMarkets raw), commission ($7/lot RT),
  slippage. Death zone 10x multiplier 23:00-01:00 UTC.
- `PerformanceReporter` — JSON/TXT/PNG reports (equity curve, monthly heatmap,
  R-distribution, exit reason breakdown).
- 6 rule modules: `growth_entry`, `growth_exit`, `growth_addon`, `scalp_entry`,
  `sl_trailing`, `tp_targets`.
- `SignalRegistry.evaluate_all()` runs all enabled rules.
- Data: 38 symbols, 9 TFs (M1-MN1), yearly-partitioned parquet.

**What's missing:**
- Bridge between `trade_log` (dict events) and `TradeRecord` (complete trades).
- Entry context snapshots (BarFeatures at trade open) for diagnostic analysis.
- Per-signal-type performance breakdown.
- CLI script to run end-to-end.
- Rule filtering in signal engine (disable scalps/add-ons for baseline).

## Architecture

### New Files

| File | Responsibility |
|------|---------------|
| `src/flint/backtest/evaluator.py` | Convert SignalEngineOutput → list[TradeRecord] with costs + context |
| `scripts/run_backtest.py` | CLI: load data, run signal engine, evaluate, generate reports |
| `tests/test_evaluator.py` | Unit tests for trade matching and context capture |

### Modified Files

| File | Change |
|------|--------|
| `src/flint/orchestrator/signal_engine.py` | Add `disabled_rules` param, pass BarFeatures to execute_signals |
| `src/flint/orchestrator/signal_engine.py` | `execute_signals()` accepts BarFeatures, attaches context to trade_log |

## Evaluator Module: `src/flint/backtest/evaluator.py`

### Core Function

```python
def evaluate_trades(
    signal_output: SignalEngineOutput,
    symbol: str,
    initial_balance: float = 1_000.0,
) -> EvaluationResult
```

### EvaluationResult Dataclass

```python
@dataclass
class EvaluationResult:
    trades: list[TradeRecord]           # Complete entry→exit pairs
    metrics: dict                       # PerformanceMetrics.calculate_all()
    trade_contexts: list[dict]          # BarFeatures snapshot per trade
    signal_type_breakdown: dict         # Per-context-group metrics
    raw_trade_log: list[dict]           # Original signal engine trade_log
```

### Trade Matching Logic

The signal engine's `trade_log` contains event dicts. Each has an `action` field
(uppercase, matching signal types):

```
action="ENTRY"    → store in pending_trades[trade_id]
action="ADD_ON"   → store in pending_trades[trade_id] (same as ENTRY)
action="HEDGE"    → store in pending_trades[trade_id] (same as ENTRY)
action="EXIT"     → close ALL pending growth trades, create TradeRecord per trade
                     exit_reason="rule_exit". Note: EXIT does not carry individual
                     trade_id — it closes all growth trades (closed_count, closed_lots).
action="SL_HIT"   → match with pending by trade_id, create TradeRecord,
                     exit_reason="sl_hit", exit_price=sl_price
action="TP_HIT"   → match with pending by trade_id, create TradeRecord,
                     exit_reason="tp_hit", exit_price=tp_price
action="SL_MOVE"  → update ALL pending growth trades' SL to new_sl value.
                     Note: SL_MOVE does not carry individual trade_id — it has
                     trades_updated count and new_sl price.
```

**Field mapping from trade_log to TradeRecord:**
- `trade_id`: int in trade_log → `str(trade_id)` for TradeRecord
- `direction`: `"bull"` → `1` (LONG), `"bear"` → `-1` (SHORT)
- `sl`: field name in ENTRY events (not `sl_price`)
- `tp_price`: not present in ENTRY events — default to `0.0` in TradeRecord
- `exit_price`: for SL_HIT use `sl_price`, for TP_HIT use `tp_price`,
  for EXIT use the signal's `price` field
- `timeframe`: from signal's `tf` field, default `"M15"`
- `mode`: `"growth"` for ENTRY/ADD_ON, `"scalp"` for HEDGE

**P&L calculation:**
```python
pip_size = get_pip_size(symbol)
pip_value = get_pip_value_per_lot(symbol)
if direction == 1:  # LONG
    pnl_raw = (exit_price - entry_price) / pip_size * pip_value * lots
else:  # SHORT
    pnl_raw = (entry_price - exit_price) / pip_size * pip_value * lots
pnl_dollars = pnl_raw - total_cost
```

Unmatched trades at end of run: force-close at last bar's close price,
`exit_reason="end_of_data"`.

### Cost Application

For each completed trade, calculate cost ONCE using entry timestamp.
`CostCalculator.calculate_total_cost()` already includes round-trip commission
($3.50 x 2 sides = $7/lot) and spread. Do NOT call twice (entry+exit) as that
would double-count commission and spread.

```python
cost_calc = CostCalculator(symbol)
cost = cost_calc.calculate_total_cost(entry_time, lots)
total_cost = cost.total_dollars
```

Deducted from `pnl_dollars`. The `cost_dollars` field on `TradeRecord` stores this.

### R-Multiple Calculation

```python
risk_pips = abs(entry_price - sl_price) / pip_size
risk_dollars = risk_pips * pip_value_per_lot * lots
return_r = pnl_dollars / risk_dollars  # After costs
```

### Entry Context Snapshot

When `execute_signals()` processes an ENTRY signal, it captures a subset of
the current `BarFeatures`:

```python
CONTEXT_FIELDS = [
    # Zone context — which zone triggered the entry
    "h4_price_in_supply", "h4_price_in_demand",
    "h1_price_in_supply", "h1_price_in_demand",
    "m15_price_in_supply", "m15_price_in_demand",
    "d1_nearest_supply_price", "d1_nearest_demand_price",
    "h4_nearest_supply_price", "h4_nearest_demand_price",
    "h1_nearest_supply_price", "h1_nearest_demand_price",
    # Structure context
    "d1_bias", "h4_bias", "h1_bias",
    "d_phase", "w_phase",
    "d_hh", "d_ll", "d_lh", "d_hl",
    "w_hh", "w_ll", "w_lh", "w_hl",
    # BOS/CHOCH events
    "choch_bull", "choch_bear",
    "bos_bull", "bos_bear",
    # Wave state
    "wave_label", "wave_phase",
    # Zone exhaustion
    "ub_h1_sup", "ub_h1_dem",
    "ub_h4_sup", "ub_h4_dem",
    "ub_d_sup", "ub_d_dem",
]
```

Stored in `trade_log` entry as `"entry_context": {field: value, ...}`.

## Per-Signal-Type Breakdown

The evaluator groups completed trades by multiple dimensions and calculates
metrics per group:

### Grouping Dimensions

1. **Entry zone TF** — derived from entry_context: which was the highest TF
   zone the price was in at entry (D1 > H4 > H1 > M15). Categories:
   `"D1_zone"`, `"H4_zone"`, `"H1_zone"`, `"M15_only"`, `"no_zone"`.

2. **Exit reason** — `"sl_hit"`, `"rule_exit"`, `"end_of_data"`.

3. **Direction** — `"long"`, `"short"`.

4. **Bias alignment** — entry direction matches `d1_bias`? `"aligned"` or
   `"counter"`.

### Per-Group Metrics

For each group:
```python
{
    "count": int,
    "win_rate": float,
    "avg_r": float,
    "total_r": float,
    "avg_holding_bars": float,
    "best_r": float,
    "worst_r": float,
}
```

This answers: "D1 zone entries aligned with D1 bias: 8 trades, 62% win rate,
avg +1.3R" vs "M15-only entries counter to bias: 5 trades, 20% win rate,
avg -0.8R."

## Signal Engine Modifications

### 1. Rule Filtering

Add `disabled_rules` parameter to `run_signal_engine()`:

```python
def run_signal_engine(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    pipeline_config: PipelineConfig | None = None,
    account_balance: float = 1_000.0,
    risk_pct: float = 0.01,
    disabled_rules: list[str] | None = None,
) -> SignalEngineOutput
```

Before `registry.evaluate_all()`, disable specified rules:

```python
if disabled_rules:
    for rule_id in disabled_rules:
        registry.disable(rule_id)
```

For baseline Growth lifecycle:
```python
disabled_rules=["scalp_entry", "growth_addon", "tp_targets"]
```

**Note on TP behavior:** Disabling `tp_targets` prevents TP_TARGET signals
(informational zone-based levels) from being emitted. However, `growth_entry`
may set `tp_price` on the entry Signal, which gets stored on `OpenTrade`. If
`OpenTrade.tp_price` is set, `PositionState.check_tp_hits()` will still fire
TP_HIT events. This is correct — the entry rule's built-in TP is part of the
Growth lifecycle. The disabled `tp_targets` rule is a separate informational
overlay.

### 2. BarFeatures in execute_signals

Change signature:

```python
def execute_signals(
    signals: list[Signal],
    position: PositionState,
    state: SignalEngineState,
    bar_features: BarFeatures | None = None,
) -> list[dict]
```

When action="ENTRY", attach context to the existing trade_log dict:

```python
if bar_features is not None:
    log_entry["entry_context"] = {
        f: getattr(bar_features, f, None) for f in CONTEXT_FIELDS
    }
```

The existing trade_log entry fields (`action`, `trade_id`, `time`, `price`,
`direction`, `lots`, `sl`, `rule_id`) are unchanged — we only ADD the
`entry_context` key.

## CLI Script: `scripts/run_backtest.py`

```
Usage:
  python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01

Options:
  --symbol      Trading symbol (default: GBPUSD)
  --start       Start date YYYY-MM-DD (required)
  --end         End date YYYY-MM-DD (required)
  --base-tf     Base timeframe (default: M15)
  --balance     Initial balance (default: 1000.0)
  --risk-pct    Risk per trade (default: 0.01)
  --run-name    Report folder name (default: {symbol}_{start}_{end})
```

### Pipeline

```python
1. Load data via ParquetStorage.load(symbol, tf, start, end) for each TF:
   Required TFs: M1, M5, M15, H1, H4, D1, W1
   Build data_by_tf dict. M1 is needed for CHOCH detection, W1 for bias.
2. Call run_signal_engine(
       data_by_tf, base_tf,
       pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
       account_balance=balance,
       disabled_rules=["scalp_entry", "growth_addon", "tp_targets"]
   )
3. Call evaluate_trades(signal_output, symbol, initial_balance=balance)
4. Generate reports via PerformanceReporter(reports_dir).generate_report(
       metrics, symbol, run_name, trades, initial_balance=balance
   )
   IMPORTANT: pass initial_balance consistently to signal engine, metrics,
   and reporter (all default to 10k — must override to 1000).
5. Save trade details with entry contexts to trades.json
6. Print summary to console
```

### Output Structure

```
reports/backtest/{run_name}/
├── metrics.json              — PerformanceMetrics.calculate_all()
├── summary.txt               — human-readable summary
├── trades.json               — per-trade detail + entry context
├── signal_breakdown.json     — per-group metrics (zone TF, direction, bias)
├── equity_curve.png          — equity + drawdown overlay
├── drawdown.png              — drawdown chart
├── monthly_returns.png       — P&L by month
├── r_distribution.png        — win/loss R histogram
└── exit_analysis.png         — exit reason breakdown
```

## Configuration

- **Initial balance:** $1,000 (user's planned starting capital)
- **Risk per trade:** 1% ($10 risk per trade)
- **Symbol:** GBPUSD (primary, expand to all 38 later)
- **Baseline rules:** growth_entry + growth_exit + sl_trailing only
- **Costs:** ICMarkets raw spread, session-aware, commission $7/lot RT

## Testing

- **Unit: trade matching** — open→close pairs, open→sl_hit, unmatched→end_of_data
- **Unit: cost application** — verify CostCalculator deduction from P&L
- **Unit: R-multiple calc** — verify risk-based R calculation
- **Unit: context capture** — verify BarFeatures fields extracted correctly
- **Unit: signal type breakdown** — verify grouping and per-group metrics
- **Integration: 1-month run** — run on GBPUSD 2026-02, verify reasonable
  trade count (not hundreds), report files generated
- **Regression: signal engine** — existing 457 tests still pass

## What We Do NOT Build

- No Flask endpoint (CLI only for now)
- No real-time streaming backtest
- No parameter optimization / walk-forward
- No multi-symbol portfolio backtest
- No visualization of individual trades on chart (markers only)
- No modification to existing rule logic (just filtering)

## Design Principles

- **Reusable evaluator** — `evaluator.py` is the core, CLI is a thin wrapper
- **Existing framework** — use TradeRecord, PerformanceMetrics, CostCalculator,
  PerformanceReporter as-is, no modifications
- **Diagnostic focus** — the per-signal-type breakdown is the key output,
  not just aggregate metrics
- **$1,000 baseline** — matches user's real starting capital
- **Growth only** — isolate the core lifecycle before adding complexity
