# Iora Strategy Backtester — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Pine Script v6 `strategy()` backtester for the 4 Iora entry models (A/B/C/D), reusing the Signal Engine's computation preamble with strategy-specific trade execution.

**Architecture:** Single file `iora_strategy.pine` with three layers: computation preamble (copied from Signal Engine with `lookahead_off` fix), strategy inputs, and trade execution with per-model entry/exit.

**Tech Stack:** Pine Script v6, TradingView Strategy Tester.

**Spec:** `docs/superpowers/specs/2026-03-30-iora-strategy-backtest-design.md`

**Coding rules:** `CLAUDE.md` (root) — always `//@version=6`, explicit types, no multiline ternaries, no reserved keywords, `request.security` tuples max 40, field assignment via local variable not `.get().field :=`.

**Pine v6 reference:** `docs/pinescriptv6/LLM_MANIFEST.md` for routing.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `tw_indicators/iora_structure/iora_strategy.pine` | CREATE | Strategy backtester: preamble + strategy inputs + trade execution |

---

## Task 1: Create strategy file — header, inputs, and request.security

**Files:**
- Create: `tw_indicators/iora_structure/iora_strategy.pine`
- Reference: `tw_indicators/iora_structure/iora_signals.pine` (copy preamble)

This task creates the strategy file with the header, strategy-specific inputs, and the 7 `request.security` calls with `lookahead_off`.

- [ ] **Step 1: Create file with strategy declaration + inputs**

```pine
//@version=6
strategy("Iora Strategy", overlay=true,
    initial_capital=10000,
    default_qty_type=strategy.fixed, default_qty_value=1.0,
    commission_type=strategy.commission.cash_per_order, commission_value=3.0,
    slippage=2, process_orders_on_close=false,
    pyramiding=4, calc_on_every_tick=false,
    max_boxes_count=500)

// =============================================================================
// === SECTION 1: INPUTS
// =============================================================================

// --- Group: Strategy ---
float  i_lot_size    = input.float(1.0,     "Lot size",                     group="Strategy", step=0.1)
string i_sizing_mode = input.string("Fixed", "Sizing mode",                 group="Strategy", options=["Fixed", "Risk-Based"])
float  i_risk_pct    = input.float(1.0,     "Risk % (risk-based mode)",     group="Strategy", step=0.5, minval=0.1, maxval=10.0)
string i_dir_filter  = input.string("Both", "Direction filter",             group="Strategy", options=["Both", "D-Bias Only", "Long Only", "Short Only"])

// --- Group: Models ---
bool   i_model_a     = input.bool(true,     "Enable Model A (Terminal Reversal)",   group="Models")
bool   i_model_b     = input.bool(true,     "Enable Model B (Mode B Continuation)", group="Models")
bool   i_model_c     = input.bool(true,     "Enable Model C (Cascade Add-On)",      group="Models")
bool   i_model_d     = input.bool(true,     "Enable Model D (Macro Bias Limit)",    group="Models")

// --- Group: Zones (visual, retained for trade review) ---
bool   i_show_zones  = input.bool(true,           "Show zone boxes",           group="Zones")
bool   i_zone_m1     = input.bool(false,           "Show M1 zones",             group="Zones")
bool   i_zone_m5     = input.bool(false,           "Show M5 zones",             group="Zones")
bool   i_zone_m15    = input.bool(false,           "Show M15 zones",            group="Zones")
bool   i_zone_h1     = input.bool(true,            "Show H1 zones",             group="Zones")
bool   i_zone_h4     = input.bool(true,            "Show H4 zones",             group="Zones")
bool   i_zone_d      = input.bool(true,            "Show D zones",              group="Zones")
int    i_max_zones   = input.int(4,                "Max zones per TF per side", group="Zones", options=[2, 4, 6, 8])
```

- [ ] **Step 2: Add request.security calls with `lookahead_off`**

Copy the 7 `request.security` calls from `iora_signals.pine` lines 33-39, changing `lookahead=barmerge.lookahead_on` to `lookahead=barmerge.lookahead_off` on all 7 calls:

```pine
// =============================================================================
// === SECTION 2: REQUEST.SECURITY — 7 TIMEFRAMES (lookahead OFF for strategy)
// =============================================================================

[m5o,  m5h,  m5l,  m5c,  m5t,  m5tc]  = request.security(syminfo.tickerid, "5",   [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[m15o, m15h, m15l, m15c, m15t, m15tc] = request.security(syminfo.tickerid, "15",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[h1o,  h1h,  h1l,  h1c,  h1t,  h1tc]  = request.security(syminfo.tickerid, "60",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[h4o,  h4h,  h4l,  h4c,  h4t,  h4tc]  = request.security(syminfo.tickerid, "240", [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[d_o,  d_h,  d_l,  d_c,  d_t,  d_tc]  = request.security(syminfo.tickerid, "1D",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[w_o,  w_h,  w_l,  w_c,  w_t,  w_tc]  = request.security(syminfo.tickerid, "1W",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
[mn_o, mn_h, mn_l, mn_c, mn_t, mn_tc] = request.security(syminfo.tickerid, "1M",  [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_off)
```

- [ ] **Step 3: Commit**

```bash
git add tw_indicators/iora_structure/iora_strategy.pine
git commit -m "feat(strategy): Task 1 — strategy header + inputs + request.security (lookahead_off)"
```

---

## Task 2: Copy computation preamble from Signal Engine

**Files:**
- Modify: `tw_indicators/iora_structure/iora_strategy.pine`
- Reference: `tw_indicators/iora_structure/iora_signals.pine:42-1461`

Copy sections 3-9 and all pre-model computation (envelope, conviction, legs, zones, zone breaks, zone counting, EW, opposing nesting, momentum consumption, cascade, trendlines, terminal gate, D-cycle, entry models A-D fire booleans) from the Signal Engine. This is a direct copy with NO visual output changes — the preamble produces the same variables the trade execution layer needs.

- [ ] **Step 1: Copy sections 3-7 (new-period booleans, envelope, gradients, conviction+legs, period breaks + swing state)**

Copy `iora_signals.pine` lines 42-780 verbatim. These produce:
- New-period detection booleans
- Envelope floor/mid/ceil for all 8 TFs
- Gradients for all 8 TFs
- `assess_conv()` and `leg_transition()` helpers
- Per-TF conviction (`m5_cv`, `m5_sd`, etc.), health, and leg tracking for all 8 TFs
- `track_period()` and `swing_state()` functions + calls for 7 TFs

- [ ] **Step 2: Copy sections 8-11 (zone UDT, arrays, zone creation, zone creation on leg transitions, zone break checking)**

Copy `iora_signals.pine` lines 753-930 verbatim. These produce:
- `Zone` UDT definition
- 12 zone arrays (6 TFs x supply/demand)
- `create_zone()` function (retains `box.new` gated by `i_show_zones`)
- Zone creation on leg transitions for M1-D
- `check_zone_breaks()` function + calls for all 12 arrays

- [ ] **Step 3: Copy zone counting through entry model D fire boolean**

Copy `iora_signals.pine` lines 931-1461 verbatim. These produce:
- Zone counting (H1/H4/D with directional reset)
- H1 EW state machine + pattern classification + `h1_ew_thr`
- Opposing nesting detection
- `ConsumptionCycle` UDT + momentum tracking
- `is_inside_zone()` helper (with size > 0 guard)
- 1-2-3 cascade detection + cascade arming
- M5/M15 trendline break detection
- Terminal exhaustion gate (`terminal_active`)
- D-level cycle phase state machine (`d_cycle_phase`)
- `is_m15_nested_h4()` helper (with size > 0 guard)
- Entry Model A: `model_a_fire`, `reversal_dir`
- Entry Model B: `model_b_fire`, `d_dir` for direction
- Entry Model C: `model_c_fire`, `cascade_add_dir`
- Entry Model D: `model_d_fire`, `d_dir` for direction

**Do NOT copy** anything after line 1461 (the SL/TP computation, plotshape, lines, dashboard are all replaced by Task 3).

- [ ] **Step 4: Validate — paste into TradingView**

Expected: compiles cleanly on GBPUSD M1. No trades yet (no `strategy.entry` calls). Zone boxes should appear if `i_show_zones` is on.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_structure/iora_strategy.pine
git commit -m "feat(strategy): Task 2 — computation preamble (sections 3-9 + zones + entry model fire booleans)"
```

---

## Task 3: Add trade execution layer

**Files:**
- Modify: `tw_indicators/iora_structure/iora_strategy.pine`

This task adds the strategy-specific trade execution: direction gate, duplicate-entry guard, per-model SL/TP computation + entry/exit calls.

- [ ] **Step 1: Add helper functions**

Append after the entry model fire booleans:

```pine
// =============================================================================
// STRATEGY HELPERS
// =============================================================================

// Direction filter gate
dir_ok(int sig_d) =>
    if i_dir_filter == "D-Bias Only"
        sig_d == d_dir
    else if i_dir_filter == "Long Only"
        sig_d > 0
    else if i_dir_filter == "Short Only"
        sig_d < 0
    else
        true

// Duplicate-entry guard: is there already an open trade with this ID?
has_open(string id) =>
    bool found = false
    if strategy.opentrades > 0
        for int i = 0 to strategy.opentrades - 1
            if strategy.opentrades.entry_id(i) == id
                found := true
    found
```

- [ ] **Step 2: Add Model A entry block**

```pine
// =============================================================================
// TRADE EXECUTION
// =============================================================================

// --- Model A: Terminal Reversal ---
if model_a_fire and i_model_a and dir_ok(reversal_dir) and not has_open("Model_A")
    float a_entry = na
    float a_sl    = na
    float a_tp    = na
    if reversal_dir > 0 and m5_dem.size() > 0
        Zone ez = m5_dem.get(0)
        a_entry := ez.bottom
    else if reversal_dir < 0 and m5_sup.size() > 0
        Zone ez = m5_sup.get(0)
        a_entry := ez.top
    if reversal_dir > 0 and m1_sup.size() > 0
        Zone sz = m1_sup.get(0)
        a_sl := sz.top + syminfo.mintick * 10
    else if reversal_dir < 0 and m1_dem.size() > 0
        Zone sz = m1_dem.get(0)
        a_sl := sz.bottom - syminfo.mintick * 10
    if reversal_dir > 0 and h1_sup.size() > 0
        Zone tz = h1_sup.get(0)
        a_tp := tz.bottom
    else if reversal_dir < 0 and h1_dem.size() > 0
        Zone tz = h1_dem.get(0)
        a_tp := tz.top
    if not na(a_sl) and not na(a_tp) and not na(a_entry) and a_sl != a_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(a_entry - a_sl), syminfo.mintick)
        if reversal_dir > 0
            strategy.entry("Model_A", strategy.long, qty=qty)
        else
            strategy.entry("Model_A", strategy.short, qty=qty)
        strategy.exit("Model_A_x", from_entry="Model_A", stop=a_sl, limit=a_tp)
```

- [ ] **Step 3: Add Model B entry block**

```pine
// --- Model B: Mode B Continuation ---
if model_b_fire and i_model_b and dir_ok(d_dir) and not has_open("Model_B")
    float b_entry = na
    float b_sl    = na
    float b_tp    = na
    if d_dir > 0 and m5_dem.size() > 0
        Zone ez = m5_dem.get(0)
        b_entry := ez.bottom
    else if d_dir < 0 and m5_sup.size() > 0
        Zone ez = m5_sup.get(0)
        b_entry := ez.top
    if d_dir > 0 and m5_sup.size() > 0
        Zone sz = m5_sup.get(0)
        b_sl := sz.top + syminfo.mintick * 10
    else if d_dir < 0 and m5_dem.size() > 0
        Zone sz = m5_dem.get(0)
        b_sl := sz.bottom - syminfo.mintick * 10
    if d_dir > 0 and h4_sup.size() > 0
        Zone tz = h4_sup.get(0)
        b_tp := tz.bottom
    else if d_dir < 0 and h4_dem.size() > 0
        Zone tz = h4_dem.get(0)
        b_tp := tz.top
    if not na(b_sl) and not na(b_tp) and not na(b_entry) and b_sl != b_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(b_entry - b_sl), syminfo.mintick)
        if d_dir > 0
            strategy.entry("Model_B", strategy.long, qty=qty)
        else
            strategy.entry("Model_B", strategy.short, qty=qty)
        strategy.exit("Model_B_x", from_entry="Model_B", stop=b_sl, limit=b_tp)
```

- [ ] **Step 4: Add Model C entry block**

```pine
// --- Model C: Cascade Add-On ---
if model_c_fire and i_model_c and dir_ok(cascade_add_dir) and not has_open("Model_C")
    float c_entry = na
    float c_sl    = na
    float c_tp    = na
    if cascade_add_dir > 0 and m5_dem.size() > 0
        Zone ez = m5_dem.get(0)
        c_entry := ez.bottom
    else if cascade_add_dir < 0 and m5_sup.size() > 0
        Zone ez = m5_sup.get(0)
        c_entry := ez.top
    if cascade_add_dir > 0 and m5_sup.size() > 0
        Zone sz = m5_sup.get(0)
        c_sl := sz.top + syminfo.mintick * 10
    else if cascade_add_dir < 0 and m5_dem.size() > 0
        Zone sz = m5_dem.get(0)
        c_sl := sz.bottom - syminfo.mintick * 10
    if cascade_add_dir > 0 and m15_sup.size() > 0
        Zone tz = m15_sup.get(0)
        c_tp := tz.bottom
    else if cascade_add_dir < 0 and m15_dem.size() > 0
        Zone tz = m15_dem.get(0)
        c_tp := tz.top
    if not na(c_sl) and not na(c_tp) and not na(c_entry) and c_sl != c_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(c_entry - c_sl), syminfo.mintick)
        if cascade_add_dir > 0
            strategy.entry("Model_C", strategy.long, qty=qty)
        else
            strategy.entry("Model_C", strategy.short, qty=qty)
        strategy.exit("Model_C_x", from_entry="Model_C", stop=c_sl, limit=c_tp)
```

- [ ] **Step 5: Add Model D entry block**

```pine
// --- Model D: Macro Bias Limit ---
if model_d_fire and i_model_d and dir_ok(d_dir) and not has_open("Model_D")
    float d_entry_price = na
    float d_sl_price    = na
    float d_tp_price    = na
    if d_dir > 0 and m5_dem.size() > 0
        Zone ez = m5_dem.get(0)
        d_entry_price := ez.bottom
    else if d_dir < 0 and m5_sup.size() > 0
        Zone ez = m5_sup.get(0)
        d_entry_price := ez.top
    if d_dir > 0 and m5_sup.size() > 0
        Zone sz = m5_sup.get(0)
        d_sl_price := sz.top + syminfo.mintick * 10
    else if d_dir < 0 and m5_dem.size() > 0
        Zone sz = m5_dem.get(0)
        d_sl_price := sz.bottom - syminfo.mintick * 10
    if d_dir > 0 and h4_sup.size() > 0
        Zone tz = h4_sup.get(0)
        d_tp_price := tz.bottom
    else if d_dir < 0 and h4_dem.size() > 0
        Zone tz = h4_dem.get(0)
        d_tp_price := tz.top
    if not na(d_sl_price) and not na(d_tp_price) and not na(d_entry_price) and d_sl_price != d_entry_price
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(d_entry_price - d_sl_price), syminfo.mintick)
        if d_dir > 0
            strategy.entry("Model_D", strategy.long, qty=qty)
        else
            strategy.entry("Model_D", strategy.short, qty=qty)
        strategy.exit("Model_D_x", from_entry="Model_D", stop=d_sl_price, limit=d_tp_price)
```

**Note:** Model D uses `d_entry_price`, `d_sl_price`, `d_tp_price` (not `d_entry`, `d_sl`, `d_tp`) to avoid conflicts with existing preamble variables like `d_o`, `d_h`, `d_l`, `d_c`. The prefix `d_` is heavily used by D-level timeframe variables.

- [ ] **Step 6: Validate — paste into TradingView**

Expected: compiles on GBPUSD M1. Strategy Tester tab shows:
- Equity curve
- Trade list with entries labeled "Model_A", "Model_B", "Model_C", "Model_D"
- Each trade has a defined SL and TP
- No `na` entries in the trade list

Test toggles:
1. Set all models to false except Model A → only Model A trades appear
2. Set direction filter to "D-Bias Only" → Model A should show zero trades (reversal vs bias)
3. Set direction filter to "Long Only" → only long trades

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_structure/iora_strategy.pine
git commit -m "feat(strategy): Task 3 — trade execution (helpers + 4 model entry/exit blocks)"
```
