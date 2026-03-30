# Iora Strategy Backtester — Design Spec

## Goal

Create a Pine Script v6 `strategy()` script that backtests the 4 entry models (A/B/C/D) from the Iora Signal Engine, using TradingView's built-in Strategy Tester for equity curve, drawdown, win rate, profit factor, and per-trade analysis.

## Architecture

**Single file:** `tw_indicators/iora_structure/iora_strategy.pine`

**Chart requirement:** Must be applied to an **M1 chart**. The computation preamble's envelope logic assumes M1 as the base timeframe for child-bar counting. Running on M5 or higher will produce incorrect envelope/conviction values.

Three layers:
1. **Computation preamble** — based on Signal Engine sections 1-9 (request.security, envelope, conviction, legs, zones, counting, momentum, cascade, terminal gate, D-cycle, entry models A-D). **Key deviation:** all `request.security()` calls use `lookahead=barmerge.lookahead_off` and reference `[1]` (previous completed bar) to prevent future-leak in strategy mode. All visual outputs stripped (no plotshape, label, line, or dashboard table).
2. **Strategy inputs** — backtesting parameters (lot size, sizing mode, risk%, direction filter, model toggles). Zone box inputs retained for visual trade review on chart.
3. **Trade execution** — `strategy.entry()`/`strategy.exit()` per model with direction gating, duplicate-entry guard, na-guard on SL/TP, per-model SL/TP variables, and per-model trade IDs.

### Preamble Deviation: lookahead

The Signal Engine uses `barmerge.lookahead_on` to get live building-candle OHLC for real-time envelope display. In strategy mode, `lookahead_on` leaks future data — the strategy sees the final HTF close before it has actually closed, inflating backtest results.

**Fix:** All 7 `request.security()` calls switch to `barmerge.lookahead_off`. HTF values reference `[1]` (previous completed candle). This means the strategy's computation is one HTF bar behind the indicator's real-time view — a conservative but honest representation.

## Strategy Declaration

```pine
strategy("Iora Strategy", overlay=true,
    initial_capital=10000,
    default_qty_type=strategy.fixed, default_qty_value=1.0,
    commission_type=strategy.commission.cash_per_order, commission_value=3.0,
    slippage=2, process_orders_on_close=false,
    pyramiding=4, calc_on_every_tick=false,
    max_boxes_count=500)
```

- `initial_capital=10000` — explicit starting equity for reproducible results
- `process_orders_on_close=false` — fills on next bar open for realistic simulation
- `pyramiding=4` — allows up to 4 concurrent positions (one per model)
- `calc_on_every_tick=false` — strategy evaluates on bar close only
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

**Note on Model A + D-Bias filter:** Model A is a terminal reversal — `reversal_dir` is the *opposite* of `d_dir` by definition. In "D-Bias Only" mode, Model A will never fire. This is intentional: a reversal against the macro bias is explicitly filtered out by the bias filter. The user can test Model A by using "Both" mode or toggling other models off.

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

### Per-Model SL/TP Computation

The Signal Engine uses shared `var` variables (`sig_entry`, `sig_sl`, `sig_tp`) since it only displays the most recent signal. The strategy needs **per-model local variables** to prevent cross-model contamination when multiple models fire on the same bar.

Each model computes its own `a_entry`, `a_sl`, `a_tp` (or `b_entry`, `b_sl`, `b_tp`, etc.) as local `float` variables within its `if model_X_fire` block. These are not `var` — they're computed fresh on the fire bar only.

### Entry Pattern (per model)

```pine
if model_a_fire and i_model_a and dir_ok(reversal_dir) and not has_open("Model_A")
    float a_entry = na
    float a_sl    = na
    float a_tp    = na
    // ... compute a_entry/a_sl/a_tp from zone arrays (same logic as Signal Engine) ...
    if not na(a_sl) and not na(a_tp) and a_sl != a_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(a_entry - a_sl), syminfo.mintick)
        if reversal_dir > 0
            strategy.entry("Model_A", strategy.long, qty=qty)
        else
            strategy.entry("Model_A", strategy.short, qty=qty)
        strategy.exit("Model_A_x", from_entry="Model_A", stop=a_sl, limit=a_tp)
```

Key guards:
- `not na(a_sl) and not na(a_tp)` — skip entry if zone arrays are empty and SL/TP couldn't be computed
- `a_sl != a_entry` — prevent division by zero in risk-based sizing
- `math.max(..., syminfo.mintick)` — floor the divisor to minimum tick in risk-based mode

Same pattern for Models B, C, D with their respective:
- Fire boolean: `model_b_fire`, `model_c_fire`, `model_d_fire`
- Direction: `d_dir` (B, D), `cascade_add_dir` (C)
- Trade IDs: `"Model_B"/"Model_B_x"`, `"Model_C"/"Model_C_x"`, `"Model_D"/"Model_D_x"`
- Per-model local SL/TP variables: `b_entry/b_sl/b_tp`, `c_entry/c_sl/c_tp`, `d_entry/d_sl/d_tp`

### Position Rules

- **Max concurrent:** 4 (one per model), enforced by `pyramiding=4` + `has_open()` guard
- **No overlapping entries:** `has_open()` guard prevents same model re-entry
- **Exit:** Pure SL/TP only. SL and TP are zone-boundary structural levels (not entry-relative), so they don't depend on actual fill price.
- **na guard:** Entry skipped if SL or TP could not be computed from available zones
- **SL/TP sources per model:**

| Model | Entry Source | SL Source | TP Source |
|-------|-------------|-----------|-----------|
| A (Terminal Reversal) | M5 zone edge | M1 supply zone top + 10 ticks (long) / M1 demand zone bottom - 10 ticks (short) | H1 supply zone bottom (long) / H1 demand zone top (short) |
| B (Mode B Continuation) | M5 zone edge | M5 supply zone top + 10 ticks (long) / M5 demand zone bottom - 10 ticks (short) | H4 supply zone bottom (long) / H4 demand zone top (short) |
| C (Cascade Add-On) | M5 zone edge | M5 supply zone top + 10 ticks (long) / M5 demand zone bottom - 10 ticks (short) | M15 supply zone bottom (long) / M15 demand zone top (short) |
| D (Macro Bias Limit) | M5 zone edge | M5 supply zone top + 10 ticks (long) / M5 demand zone bottom - 10 ticks (short) | H4 supply zone bottom (long) / H4 demand zone top (short) |

## What This Does NOT Include

- No trailing stops (Phase 2 enhancement)
- No signal-based exits (Phase 2 enhancement)
- No risk-based position sizing optimization (validate signal quality first with fixed lots)
- No ML meta-labeling (separate project, feeds from backtest trade data)
- No multi-pair batch testing (Pine limitation — one chart at a time)
- No `max_bars_back` overrides (add if Pine throws errors on deep history; the `var float` signal variables and `var` arrays may need explicit `max_bars_back` calls if backtesting over very long periods)

## Validation

1. Paste into TradingView, apply to GBPUSD **M1** chart
2. Strategy Tester tab shows: equity curve, drawdown, trade list, performance summary
3. Toggle individual models off to isolate per-model stats
4. Compare "Both" vs "D-Bias Only" direction filter (expect Model A to not fire in D-Bias mode — this is correct)
5. Check trade list for reasonable entry/exit prices relative to zone boundaries
6. Verify no trades have `na` SL or TP in the trade list

## File Dependencies

- Based on Signal Engine computation preamble (sections 1-9), with `lookahead_off` + `[1]` shift
- 7 `request.security` calls (same budget as Signal Engine, well within 40-call limit)
- Zone UDT and arrays identical to Signal Engine
