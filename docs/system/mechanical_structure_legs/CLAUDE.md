# Iora Structural Detection System — Build Instructions

## Project Context

We are building a modular Pine Script v6 structural detection system. All design decisions, architectural reasoning, and spec details are in the docs below. **Read the MASTER_SPEC first — it's the single source of truth.**

## Key Files

### Specifications (read in this order)
1. `C:\Iora\docs\system\mechanical_structure_legs\MASTER_SPEC_iora_structural_detection.md` — **READ THIS FIRST.** Complete system design: four-layer detection architecture, three-source envelope, conviction-based internal/external classification, leg architecture, momentum consumption, hybrid computation, and the 7-module build plan.
2. `C:\Iora\docs\system\mechanical_structure_legs\04_period_level_structure_spec_v2.md` — Dynamic averages + period-level breaks
3. `C:\Iora\docs\system\mechanical_structure_legs\04a_candle_type_price_source_analysis.md` — Three-source envelope design
4. `C:\Iora\docs\system\mechanical_structure_legs\04b_leg_architecture_spec.md` — Leg architecture
5. `C:\Iora\docs\system\mechanical_structure_legs\04c_conviction_internal_external_spec.md` — Conviction as I/E classifier
6. `C:\Iora\docs\system\mechanical_structure_legs\04d_momentum_consumption_spec.md` — Momentum consumption
7. `C:\Iora\docs\system\mechanical_structure_legs\04e_computation_architecture_spec.md` — Hybrid computation architecture

### Existing Pine Script Indicators (working code — reuse patterns)
- `C:\Iora\tw_indicators\templates\iora_bos_choch.pine` — Period high/low tracking + break detection. Base for Module 3.
- `C:\Iora\tw_indicators\templates\HTF Candles (M5 - 12MN).pine` — Building candle visualisation. Uses `request.security(..., lookahead=barmerge.lookahead_on)` which returns LIVE building candle OHLC — **this is the key shortcut for the hybrid envelope** (no manual M1 reconstruction needed).

### Output Directory
All new Pine Script indicators go in: `C:\Iora\tw_indicators\iora_structure\`

## What We're Building

A four-layer structural detection system in Pine Script v6:

1. **Direct M1 momentum** — SMA crossovers (pre-alert layer)
2. **Hybrid cascade envelope** — three-source envelope using live building candles via `request.security` with lookahead. Conviction scoring (Strong/Weak/Pre) classifies events as internal or external.
3. **Period-level breaks** — extending `iora_bos_choch.pine` with swing state machine + parent propagation
4. **Zone-based confirmation** — existing system (not in scope)

## Build Plan (7 Modules, 5 Phases)

**Phase 1:** Module 1 (`iora_envelope.pine`) + Module 2 (`iora_conviction.pine`)
**Phase 2:** Module 3 (`iora_bos_choch_v2.pine`) — extend existing indicator
**Phase 3:** Module 4 (`iora_legs.pine`) + Module 5 (`iora_consumption.pine`)
**Phase 4:** Module 6 (`iora_momentum.pine`)
**Phase 5:** Module 7 (`iora_dashboard.pine`) + integration

See MASTER_SPEC Part 8 for full module specifications.

## Code Rules

- **Pine Script v6 only.** Use `indicator()` not `strategy()`.
- **Line candles (raw OHLC)** for everything. No Heikin Ashi.
- **No user-tunable parameters** except TF enable/disable toggles and visual styling. All structural parameters (window sizes, ratios) derived from natural parent-child TF ratios.
- **Each module = one complete .pine file** that can be loaded independently in TradingView.
- Use the `request.security(syminfo.tickerid, TF, [open, high, low, close, time, time_close], lookahead=barmerge.lookahead_on)` pattern from the HTF Candles indicator for live building candle data.
- Modules don't share data between indicators — each computes what it needs from the same `request.security` calls.
- **Validate visually** in TradingView Replay on GBPUSD/EURUSD/XAUUSD M1 chart.
