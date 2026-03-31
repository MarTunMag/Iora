# Triplet Entry Models — Design Spec

## Goal

Redesign the Signal Engine's entry models to align with the trading system spec's Universal Triplet State Machine. Replace Models A-D (compound boolean gates) with 4 state-based entries (PUSH/CONTINUE/PULLBACK/REVERSAL) driven by zone creation events within an explicit triplet state machine.

## Problem

The current entry models (A-D) require complex combinations of derived metrics — trendline breaks, cascade levels, conviction scores, consumption scores, terminal states, d-cycle phases. These don't align with the spec, which says:

- **Entry trigger = zone creation event** — when a new child zone forms within a parent zone, that IS the entry signal
- **Trendline breaks are early warnings, NOT entry triggers** — yet Model D requires an M5 trendline break
- **Triplet state drives the trade** — PUSHING/CONTINUING/PULLING BACK/REVERSING each have their own entry logic
- **"Every child zone in parent's direction = entry opportunity"** (PUSHING state)

The result: signals fire when compound boolean conditions happen to align (often far from zones), instead of when price interacts with zones (what the user sees on chart).

## Architecture

**Approach:** Replace entry models in-place (sections 12-13 of `iora_signals.pine`). Keep sections 1-11 intact (request.security, envelope, conviction, legs, zone creation, zone breaks). Add triplet state machine between zone breaks and entries.

**Scope:** Two execution triplets only:
- **T5** (Parent=H1, Child=M15, Grandchild=M5) — provides bias/confidence
- **T6** (Parent=M15, Child=M5, Grandchild=M1) — generates trade entries

Higher triplets (T1-T4) already contribute via `d_dir`, `cascade_dir`, and zone arrays from `request.security()`. They provide macro context without needing formal state machines.

## What Gets Removed

From `iora_signals.pine`, remove ~250 lines:

- Cascade arming booleans (`d_armed_bear/bull` through `m5_armed_bear/bull`) — ~20 lines
- `cascade_level`, `cascade_dir` derivation — ~5 lines
- Terminal detection (`d_level_broken`, `h4_counter`, `h1_count_met`, `opp_nesting`, `terminal_active`) — ~30 lines
- D-cycle phase state machine (`d_cycle_phase`, all phase transitions) — ~30 lines
- Models A-D boolean definitions + `_prev`/`_fire` edge detection — ~50 lines
- Old SL/TP computation (per-model `sig_entry`/`sig_sl`/`sig_tp`) — ~80 lines
- Old plotshape markers for Models A-D — ~8 lines
- Old debug section (at_entry plots, condition labels) — ~25 lines
- Dashboard rows referencing cascade/terminal/d-cycle/model names — updated

## What Gets Kept

Sections 1-11 (~1200 lines), unchanged:

- Sections 1-9: `request.security()`, envelope, conviction, legs, swing classification
- Section 10: Zone creation (`create_zone` + all TF zone blocks)
- Section 11: Zone break checking (`check_zone_breaks`)
- `is_inside_zone()` helper — used by triplet state transitions
- `is_m15_nested_h4()` / `opp_nesting()` — available for future confidence scoring
- Zone arrays (`m1_dem`/`m1_sup` through `d_dem`/`d_sup`)
- All `_fired` booleans and `_swc` values (swing classification)
- Consumption score — available for future confidence scoring

## Triplet State Machine

### Design

Two state machines — `t5_state` and `t6_state` — each tracking one of 5 values: `"IDLE"`, `"PUSHING"`, `"CONTINUING"`, `"PULLBACK"`, `"REVERSING"`.

### T6 State Variables (Parent=M15, Child=M5, Grandchild=M1)

```pine
var string t6_state      = "IDLE"   // current triplet state
var int    t6_dir        = 0        // +1 bullish, -1 bearish
var float  t6_push_top   = na       // push zone top (SL reference for PUSH state)
var float  t6_push_bot   = na       // push zone bottom (SL reference for PUSH state)
var float  t6_last_pb_top = na      // last pullback zone top (for Resolution B check)
var float  t6_last_pb_bot = na      // last pullback zone bottom (for Resolution B check)
var int    t6_zone_count = 0        // zones created in current state
```

T5 has identical structure one level up (Parent=H1, Child=M15, Grandchild=M5).

### Parent Direction

Derived from parent TF's last swing classification:

```
t6_parent_dir:
  m15_swc == 1 (HH) or m15_swc == 4 (HL) → +1 (bullish)
  m15_swc == 2 (LH) or m15_swc == 3 (LL) → -1 (bearish)

t5_parent_dir:
  h1_swc == 1 (HH) or h1_swc == 4 (HL) → +1 (bullish)
  h1_swc == 2 (LH) or h1_swc == 3 (LL) → -1 (bearish)
```

### Child Zone Direction Match

A new child zone matches the parent direction when:

- **M5 demand created** (`m5_fired and (m5_swc == 3 or m5_swc == 4)`) while `t6_parent_dir > 0` → bullish child zone matching bullish parent
- **M5 supply created** (`m5_fired and (m5_swc == 1 or m5_swc == 2)`) while `t6_parent_dir < 0` → bearish child zone matching bearish parent

Counter-direction is the inverse.

### M1 CHoCH Detection (Grandchild Confirmation)

M1 CHoCH = M1 swing classification fires in the direction that opposes the pullback (i.e., confirms pullback is exhausting):

- If `t6_dir > 0` (bullish parent, pullback was bearish): M1 CHoCH = `m1_fired and (m1_swc == 4)` (HL — M1 turned bullish)
- If `t6_dir < 0` (bearish parent, pullback was bullish): M1 CHoCH = `m1_fired and (m1_swc == 2)` (LH — M1 turned bearish)

This is tracked via a persistent variable:
```pine
var bool t6_m1_choch = false
// Set true when M1 fires CHoCH opposing the pullback direction
// Reset to false on state transition out of PULLBACK
```

### M15 Structural Level Lookup

Finding "M15's last HL demand bottom" or "M15's last LH supply top" requires scanning the zone array by swing classification:

```pine
get_zone_by_cls(array<Zone> zones, int cls) =>
    Zone result = na
    for int i = 0 to math.min(zones.size() - 1, 7)
        Zone z = zones.get(i)
        if z.swing_cls == cls
            result := z
            break
    result
```

- M15 structural HL demand = `get_zone_by_cls(m15_dem, 4)` (swing_cls == 4 = HL)
- M15 structural LH supply = `get_zone_by_cls(m15_sup, 2)` (swing_cls == 2 = LH)

Fallback: if no matching zone found, the structural level check defaults to `false` (treat as REVERSING rather than PULLBACK — conservative).

### State Transitions

All transitions are driven by `m5_fired` (T6) or `m15_fired` (T5) events — the moment a new child zone is created.

**Evaluation order on each bar:** (1) Update T6 state based on new zone event, (2) Check entry conditions against the **updated** state. This means the first counter-zone both transitions to PULLBACK and fires the PULLBACK entry on the same bar.

| From | To | Trigger | Condition |
|---|---|---|---|
| IDLE | PUSHING | M5 zone in M15 direction | Bullish: `is_inside_zone(m15_dem)`. Bearish: `is_inside_zone(m15_sup)` |
| PUSHING | CONTINUING | Next M5 zone, same direction | Bullish: new M5 dem zone bottom > `t6_push_top`. Bearish: new M5 sup zone top < `t6_push_bot` |
| PUSHING / CONTINUING | PULLBACK | M5 zone counter to M15 dir | Doesn't break M15 structural level (see check below) |
| PULLBACK | PUSHING (Resolution A) | M5 zone in M15 dir, at push zone | Bullish: new zone bottom <= `t6_push_top`. Bearish: new zone top >= `t6_push_bot`. Plus `t6_m1_choch == true` |
| PULLBACK | PUSHING (Resolution B) | Last pullback zone body-close broken | Bullish: `close > t6_last_pb_top`. Bearish: `close < t6_last_pb_bot`. Plus M5 zone in M15 dir. Plus `t6_m1_choch == true` |
| PULLBACK | REVERSING | M5 counter-zone breaks M15 structural level | See structural level check below |
| REVERSING | PUSHING | New M15 leg confirmed | `m15_fired` and M15 direction flips, first M5 zone in new dir |

### "Doesn't Break M15 Structural Level" Check

- For M15 bullish (`t6_parent_dir > 0`): the M5 counter-zone's low stays above M15's last HL demand bottom (`get_zone_by_cls(m15_dem, 4).bottom`). If no HL demand exists → defaults to REVERSING.
- For M15 bearish (`t6_parent_dir < 0`): the M5 counter-zone's high stays below M15's last LH supply top (`get_zone_by_cls(m15_sup, 2).top`). If no LH supply exists → defaults to REVERSING.

If the counter-zone DOES break the structural level → transition to REVERSING, not PULLBACK.

### State Variable Updates on Transition

| Transition | Variable Updates |
|---|---|
| → PUSHING | `t6_dir := t6_parent_dir`, `t6_push_top := new_zone.top`, `t6_push_bot := new_zone.bottom`, `t6_zone_count := 1`, `t6_m1_choch := false` |
| → CONTINUING | `t6_zone_count += 1` |
| → PULLBACK | `t6_last_pb_top := new_zone.top`, `t6_last_pb_bot := new_zone.bottom`, `t6_zone_count := 1`, `t6_m1_choch := false` |
| → REVERSING | `t6_zone_count := 0` |
| → IDLE | `t6_dir := 0`, `t6_push_top := na`, `t6_push_bot := na`, `t6_zone_count := 0` |

On subsequent PULLBACK zones (still in PULLBACK state): update `t6_last_pb_top`/`t6_last_pb_bot` to the newest counter-zone, increment `t6_zone_count`.

### State Reset

When M15 fires a new swing (`m15_fired`), T6 re-evaluates its parent direction. If M15 direction changes, T6 resets to IDLE and waits for the first M5 zone in the new direction to begin PUSHING.

## Entry Signals

Entries fire on zone creation events when the triplet state allows it. T6 only for entries. T5 for confidence.

### Entry Trigger

All 4 models share the same trigger mechanism: `m5_fired` (a new M5 zone was just created) AND the T6 state matches.

```pine
bool push_fire     = m5_fired and t6_state == "PUSHING"    and m5_zone_matches_dir(t6_dir)
bool continue_fire = m5_fired and t6_state == "CONTINUING" and m5_zone_matches_dir(t6_dir)
bool pullback_fire = m5_fired and t6_state == "PULLBACK"   and m5_zone_matches_dir(-t6_dir)
bool reversal_fire = m5_fired and t6_state == "REVERSING"  and m5_zone_matches_dir(t6_dir)
```

### Entry Direction

| Model | Trade Direction |
|---|---|
| PUSH | `t6_dir` (with parent) |
| CONTINUE | `t6_dir` (with parent) |
| PULLBACK | `-t6_dir` (counter to parent, temporary) |
| REVERSAL | `t6_dir` (new direction, after structural break) |

### Duplicate Guard

Same rising-edge pattern as current implementation:

```pine
var bool push_prev = false
bool push_signal = push_fire and not push_prev
push_prev := push_fire
```

### T5 Confidence Modifier

T5 state determines confidence level for T6 entries:

| T5 State vs T6 Direction | Confidence |
|---|---|
| T5 PUSHING/CONTINUING in same direction as T6 | HIGH — full alignment |
| T5 neutral, IDLE, or PULLBACK | MEDIUM — partial alignment |
| T5 PUSHING/CONTINUING against T6, or REVERSING | LOW — conflicting structure |

Confidence is displayed on the dashboard and used by the strategy for position sizing. It does NOT block entries — the user decides via the strategy's direction filter and model toggles.

## SL/TP Per State

### Entry Price

M5 zone edge: `m5_dem.get(0).bottom` (long) / `m5_sup.get(0).top` (short).

### Stop Loss (structural invalidation)

| State | Long SL | Short SL |
|---|---|---|
| PUSH | `t6_push_bot - mintick * 10` | `t6_push_top + mintick * 10` |
| CONTINUE | `m5_dem.get(0).bottom - mintick * 10` | `m5_sup.get(0).top + mintick * 10` |
| PULLBACK | `m5_dem.get(0).bottom - mintick * 10` | `m5_sup.get(0).top + mintick * 10` |
| REVERSAL | `get_zone_by_cls(m15_dem, 4).bottom - mintick * 10` (M15 HL demand) | `get_zone_by_cls(m15_sup, 2).top + mintick * 10` (M15 LH supply) |

### Take Profit (state target)

| State | Long TP | Short TP |
|---|---|---|
| PUSH | `m15_sup.get(0).bottom` (parent supply boundary) | `m15_dem.get(0).top` (parent demand boundary) |
| CONTINUE | `m15_sup.get(0).bottom` (parent boundary) | `m15_dem.get(0).top` (parent boundary) |
| PULLBACK | `t6_push_top` (push zone = magnet) | `t6_push_bot` (push zone = magnet) |
| REVERSAL | `m15_sup.get(0).bottom` (next overhead supply) | `m15_dem.get(0).top` (next underlying demand) |

Note: REVERSAL TP uses the same opposing-zone lookup as PUSH/CONTINUE. After a reversal, the nearest parent zone in the opposing direction is the natural target for the new leg.

### Guards

- `not na(sl) and not na(tp)` — skip entry if zones empty
- `sl != entry` — prevent zero-risk division in strategy sizing
- `m5_dem.size() > 0` / `m5_sup.size() > 0` — zone array must have content

## Dashboard

Bottom-left table, same position as current:

| Row | Content | Example |
|---|---|---|
| 1 | T5 state + direction | `T5: PUSHING ▲` |
| 2 | T6 state + direction | `T6: PULLBACK ▼` |
| 3 | Confidence | `Conf: HIGH` |
| 4 | Active signal | `Signal: PUSH Long` or `—` |
| 5 | SL / TP | `SL: 1.33420  TP: 1.33890` |

## Debug Mode

Toggle: `i_debug` input (default false).

| Visual | What It Shows |
|---|---|
| Background color | T6 state: green=PUSHING, blue=CONTINUING, orange=PULLBACK, red=REVERSING |
| Labels every 100 bars | `T6: PUSHING ▲ z:3` (state, direction, zone count) |
| Labels offset 50 bars | `T5: CONTINUING ▲` |
| plotshape on state transitions | Diamond on bar where T6 state changes |

## Signal Markers (plotshape)

| Signal | Shape | Location | Color |
|---|---|---|---|
| PUSH long | `shape.arrowup` | `location.belowbar` | `#26A69A` (green) |
| PUSH short | `shape.arrowdown` | `location.abovebar` | `#EF5350` (red) |
| CONTINUE long | `shape.triangleup` | `location.belowbar` | `#42A5F5` (blue) |
| CONTINUE short | `shape.triangledown` | `location.abovebar` | `#42A5F5` (blue) |
| PULLBACK long | `shape.circle` | `location.belowbar` | `#FFCA28` (orange) |
| PULLBACK short | `shape.circle` | `location.abovebar` | `#FFCA28` (orange) |
| REVERSAL long | `shape.diamond` | `location.belowbar` | `#AB47BC` (purple) |
| REVERSAL short | `shape.diamond` | `location.abovebar` | `#AB47BC` (purple) |

## Strategy File (`iora_strategy.pine`)

Same changes mirrored:

- Remove cascade, terminal, d-cycle, Models A-D trade execution
- Add identical T5/T6 state machine
- Trade IDs: `"Push"`, `"Continue"`, `"Pullback"`, `"Reversal"`
- `has_open()`, `dir_ok()`, `pyramiding=4` — unchanged
- `i_sizing_mode`, `i_risk_pct`, `i_lot_size` inputs — unchanged
- Commission/slippage hardcoded in header — unchanged

T5 confidence feeds strategy sizing:
- HIGH: full `i_risk_pct`
- MEDIUM: `i_risk_pct * 0.5`
- LOW: skip entry

## Inputs

### Group: Signals (updated)

| Input | Type | Default | Notes |
|---|---|---|---|
| `i_show_push` | bool | true | Show PUSH signals |
| `i_show_continue` | bool | true | Show CONTINUE signals |
| `i_show_pullback` | bool | true | Show PULLBACK signals |
| `i_show_reversal` | bool | true | Show REVERSAL signals |
| `i_show_sl_tp` | bool | true | Show SL/TP lines |

### Group: Zones (unchanged)

All zone display toggles and max_zones kept as-is.

### Group: Debug (updated)

| Input | Type | Default | Notes |
|---|---|---|---|
| `i_debug` | bool | false | Show triplet state debug visuals |

### Group: Dashboard (unchanged)

`i_dash_on`, `i_dash_pos` kept as-is.

## What This Does NOT Include

- No trailing stops (future enhancement)
- No signal-based exits (future enhancement)
- No T1-T4 formal state machines (macro context from existing `request.security()` data)
- No consumption-based confidence scoring (available for future enhancement — data exists)
- No zone nesting confidence boost (available for future enhancement — `is_m15_nested_h4` exists)
- No re-entry on zone retest (Phase 2 — zone creation is the trigger for now)

## Validation

1. Apply to GBPUSD M1 chart
2. Enable debug mode — verify T6 state transitions make visual sense (PUSHING when M5 zones stack in parent direction, PULLBACK when counter-zones form)
3. Verify signals fire AT zone creation events, not at arbitrary structural alignment points
4. Compare with user's annotated screenshots — signals should appear in the circled areas
5. Toggle individual signal types off to isolate per-state behavior
6. Apply strategy version, verify trades in Strategy Tester

## File Dependencies

- `iora_signals.pine` — sections 12-13 rewritten, sections 1-11 unchanged
- `iora_strategy.pine` — same changes mirrored for backtesting
- 7 `request.security()` calls (unchanged, well within 40-call limit)
- Zone UDT and arrays identical to current implementation
