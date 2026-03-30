# Iora Strategy Backtester — Design Spec

## Goal

Create a Pine Script v6 `strategy()` script that backtests the 4 entry models (A/B/C/D) from the Iora Signal Engine, using TradingView's built-in Strategy Tester for equity curve, drawdown, win rate, profit factor, and per-trade analysis.

## Architecture

**Single file:** `tw_indicators/iora_structure/iora_strategy.pine`

Three layers:
1. **Computation preamble** — identical to Signal Engine sections 1-9 (request.security, envelope, conviction, legs, zones, counting, momentum, cascade, terminal gate, D-cycle, entry models A-D, SL/TP computation). All visual outputs stripped (no plotshape, label, line, or dashboard table).
2. **Strategy inputs** — backtesting parameters (lot size, sizing mode, risk%, direction filter, model toggles). Zone box inputs retained for visual trade review on chart.
3. **Trade execution** — `strategy.entry()`/`strategy.exit()` per model with direction gating, duplicate-entry guard, and per-model trade IDs.

## Strategy Declaration

```pine
strategy("Iora Strategy", overlay=true,
    default_qty_type=strategy.fixed, default_qty_value=1.0,
    commission_type=strategy.commission.cash_per_order, commission_value=3.0,
    slippage=2, process_orders_on_close=false,
    max_boxes_count=500)
```

- `process_orders_on_close=false` — fills on next bar open for realistic simulation
- Commission and slippage are compile-time constants in the header (not inputs)

## Inputs

### Group: Strategy

| Input | Type | Default | Notes |
|-------|------|---------|-------|
| `i_lot_size` | float | 1.0 | Lot size for fixed mode, step=0.1 |
| `i_sizing_mode` | string | "Fixed" | Options: "Fixed", "Risk-Based" |
| `i_risk_pct` | float | 1.0 | Risk % of equity per trade (risk-based mode only), step=0.5, minval=0.1, maxval=10 |
| `i_dir_filter` | string | "Both" | Options: "Both", "D-Bias Only", "Long Only", "Short Only" |

### Group: Models

| Input | Type | Default | Notes |
|-------|------|---------|-------|
| `i_model_a` | bool | true | Enable Model A (Terminal Reversal) |
| `i_model_b` | bool | true | Enable Model B (Mode B Continuation) |
| `i_model_c` | bool | true | Enable Model C (Cascade Add-On) |
| `i_model_d` | bool | true | Enable Model D (Macro Bias Limit) |

### Group: Zones

Retained from Signal Engine for visual trade review on chart:
- `i_show_zones`, `i_zone_m1` through `i_zone_d`, `i_max_zones`

### Removed from Signal Engine

- All plotshape/line/dashboard inputs (`i_show_model_a` display toggles, `i_show_sl_tp`, `i_dash_on`, `i_dash_pos`)

## Trade Execution

### Direction Gate

```pine
dir_ok(int sig_d) =>
    if i_dir_filter == "D-Bias Only"
        sig_d == d_dir
    else if i_dir_filter == "Long Only"
        sig_d > 0
    else if i_dir_filter == "Short Only"
        sig_d < 0
    else
        true
```

### Duplicate-Entry Guard

Prevents re-entry into a model that already has an open position (avoids replacing a winning trade with a worse entry):

```pine
has_open(string id) =>
    bool found = false
    if strategy.opentrades > 0
        for int i = 0 to strategy.opentrades - 1
            if strategy.opentrades.entry_id(i) == id
                found := true
    found
```

### Entry Pattern (per model)

```pine
if model_a_fire and i_model_a and dir_ok(reversal_dir) and not has_open("Model_A")
    float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.abs(sig_entry - sig_sl)
    if reversal_dir > 0
        strategy.entry("Model_A", strategy.long, qty=qty)
    else
        strategy.entry("Model_A", strategy.short, qty=qty)
    strategy.exit("Model_A_x", from_entry="Model_A", stop=sig_sl, limit=sig_tp)
```

Same pattern for Models B, C, D with their respective:
- Fire boolean: `model_b_fire`, `model_c_fire`, `model_d_fire`
- Direction: `d_dir` (B, D), `cascade_add_dir` (C)
- Trade IDs: `"Model_B"/"Model_B_x"`, `"Model_C"/"Model_C_x"`, `"Model_D"/"Model_D_x"`

### Position Rules

- **Max concurrent:** 4 (one per model)
- **No overlapping entries:** `has_open()` guard prevents same model re-entry
- **Exit:** Pure SL/TP only. SL and TP are zone-boundary structural levels (not entry-relative), so they don't depend on actual fill price.
- **SL/TP sources per model:**

| Model | Entry Source | SL Source | TP Source |
|-------|-------------|-----------|-----------|
| A (Terminal Reversal) | M5 zone edge | M1 opposing zone + 10 ticks | H1 opposing zone |
| B (Mode B Continuation) | M5 zone edge | M5 opposing zone + 10 ticks | H4 opposing zone |
| C (Cascade Add-On) | M5 zone edge | M5 opposing zone + 10 ticks | M15 opposing zone |
| D (Macro Bias Limit) | M5 zone edge | M5 opposing zone + 10 ticks | H4 opposing zone |

## What This Does NOT Include

- No trailing stops (Phase 2 enhancement)
- No signal-based exits (Phase 2 enhancement)
- No risk-based position sizing optimization (validate signal quality first with fixed lots)
- No ML meta-labeling (separate project, feeds from backtest trade data)
- No multi-pair batch testing (Pine limitation — one chart at a time)

## Validation

1. Paste into TradingView, apply to GBPUSD M1 chart
2. Strategy Tester tab shows: equity curve, drawdown, trade list, performance summary
3. Toggle individual models off to isolate per-model stats
4. Compare "Both" vs "D-Bias Only" direction filter
5. Check trade list for reasonable entry/exit prices relative to zone boundaries

## File Dependencies

- Reuses Signal Engine computation preamble (sections 1-9)
- 7 `request.security` calls (same as Signal Engine)
- Zone UDT and arrays identical to Signal Engine
