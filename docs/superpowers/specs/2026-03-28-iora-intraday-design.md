# Iora Intraday — Design Spec

> File: `tw_indicators/system/iora_intraday.pine`
> Pine Script v6 | Overlay indicator | Chart TF: M1
> Date: 2026-03-28

---

## Purpose

A single Pine Script indicator that builds a **multi-TF state machine** on top of the existing zone/structure/trendline visual layer. It reads HA zone data across 6 timeframes (D, H4, H1, M15, M5, M1), computes structural bias, zone counts, context mode, and entry cascade triggers.

The existing indicators (`iora_zones.pine`, `iora_structure.pine`, `iora_structure_trendlines.pine`) remain on chart for visual reference. This indicator adds the **decision layer**.

---

## Scope

**6 TFs:** D, H4, H1, M15, M5, M1. No W/MN — not needed for intraday execution.

**Chart TF:** M1 (required — M1 CHoCH is always the final execution trigger).

**`request.security()` budget:** 6 calls (one per TF), well under the 40-call limit.

**Architecture:** Layered build (Approach B) — single indicator, 9 strict sections matching existing Iora indicator conventions.

---

## Dependencies

- `docs/system/01_market_structure.md` — BOS/CHoCH detection rules
- `docs/system/02_supply_demand_zones.md` — zone creation/classification/lifecycle
- `docs/system/03_breaker_mitigation.md` — breaker/mitigation block mechanics
- `docs/concepts/01_zone_classification.md` — HH/LH/HL/LL comparison rules
- `docs/concepts/02_early_confirmation_cascade.md` — CHoCH propagation chain
- `docs/concepts/INTERNAL_EXTERNAL_STRUCTURE_SPEC.md` — TF cascade hierarchy
- `docs/04_htf_ltf_layered_structure.md` — push/magnet/entry framework

---

## Section Architecture

### S1 — Types

#### `TFState` UDT — per-timeframe structural state (6 instances)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `bias` | `int` | `0` | +1 bull, -1 bear, 0 neutral |
| `prev_bias` | `int` | `0` | pre-break bias for BOS/CHoCH classification |
| `last_sup_top` | `float` | `na` | most recent supply zone top |
| `last_sup_bot` | `float` | `na` | most recent supply zone bottom |
| `last_dem_top` | `float` | `na` | most recent demand zone top |
| `last_dem_bot` | `float` | `na` | most recent demand zone bottom |
| `last_sup_cls` | `string` | `""` | "HH" or "LH" |
| `last_dem_cls` | `string` | `""` | "LL" or "HL" |
| `prev_sup_top` | `float` | `na` | previous supply top (for HH/LH classification) |
| `prev_dem_bot` | `float` | `na` | previous demand bottom (for LL/HL classification) |
| `last_event` | `string` | `""` | "iBOS", "iCHoCH", "eBOS", "eCHoCH" |
| `last_event_dir` | `int` | `0` | +1 bullish, -1 bearish |
| `last_event_time` | `int` | `na` | bar time of last event |
| `zone_count` | `int` | `0` | unbroken zones since last parent TF event |

Zone arrays are separate per-TF `array<LightZone>` instances (same `LightZone` type as `iora_structure.pine`).

#### `LightZone` UDT — lightweight zone for break detection

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `top` | `float` | `0.0` | zone top price |
| `bottom` | `float` | `0.0` | zone bottom price |
| `is_supply` | `bool` | `false` | true = supply, false = demand |
| `is_hh_or_ll` | `bool` | `false` | structural zone flag |
| `label_txt` | `string` | `""` | "HH", "LH", "HL", "LL" |
| `origin_time` | `int` | `0` | creation bar time |
| `is_broken` | `bool` | `false` | break flag |
| `break_time` | `int` | `0` | break bar time |

---

### S2 — Inputs

| Input | Type | Default | Group | Purpose |
|-------|------|---------|-------|---------|
| `Doji Body %` | `float` | `5.0` | Zone Detection | HA doji threshold |
| `Show Dashboard` | `bool` | `true` | Display | Toggle dashboard table |
| `Dashboard Position` | `string` | `"Top Right"` | Display | Table position (options: Top Right, Top Left, Bottom Right, Bottom Left) |
| `Show Entry Signals` | `bool` | `true` | Display | Toggle entry/exit markers |
| `Show Zone Roles` | `bool` | `true` | Display | Toggle PUSH/MAGNET/ENTRY labels on zones |

No TF toggles — all 6 TFs are always active (they're all required for the state machine).

---

### S3 — HA Detection

Reuse the exact `ha_detect()` function from `iora_structure.pine`:

```
ha_detect(float doji_pct) =>
    // HA calculation from raw OHLC
    // Color transition detection (red→blue = demand, blue→red = supply)
    // Run extreme scan (up to 50 bars back)
    // HH/LH/HL/LL classification vs previous same-type zone
    // Returns: [fire, ztop, zbot, is_sup, origin_time, hi_cls, lo_cls]
```

6 `request.security()` calls on `ticker.standard(syminfo.tickerid)`:

```
[f_d,  zt_d,  zb_d,  s_d,  tm_d,  hi_d,  lo_d]  = request.security(_sym, "1D",  ha_detect(i_doji))
[f_h4, zt_h4, zb_h4, s_h4, tm_h4, hi_h4, lo_h4] = request.security(_sym, "240", ha_detect(i_doji))
[f_h1, zt_h1, zb_h1, s_h1, tm_h1, hi_h1, lo_h1] = request.security(_sym, "60",  ha_detect(i_doji))
[f_m15,zt_m15,zb_m15,s_m15,tm_m15,hi_m15,lo_m15] = request.security(_sym, "15",  ha_detect(i_doji))
[f_m5, zt_m5, zb_m5, s_m5, tm_m5, hi_m5, lo_m5]  = request.security(_sym, "5",   ha_detect(i_doji))
[f_m1, zt_m1, zb_m1, s_m1, tm_m1, hi_m1, lo_m1]  = request.security(_sym, "1",   ha_detect(i_doji))
```

Edge detection: `fire = fire_raw and not fire_raw[1]` (same pattern as existing indicators).

**Note:** M1 on M1 chart — the `request.security("1", ...)` call echoes the current bar. This is fine because M1 data IS the chart data. The security call ensures consistent execution model with the other TFs.

---

### S4 — Zone State Management

Per-TF zone arrays (6 arrays, one per TF). Same management as `iora_structure.pine`:

1. **Expiry check:** remove zones older than `tf_max_age * tf_period_ms`
2. **Break detection:** body-close only (`close > zone.top` for supply, `close < zone.bottom` for demand)
3. **New zone push:** on HA fire event, validate and push to array
4. **Count overflow:** cap at 20 supply + 20 demand per TF

**Additional zone counting (not in existing indicators):**

On each new zone fire for a TF:
- Increment that TF's `zone_count`
- Track whether the new zone is in push direction (matches parent bias) or correction direction

On parent TF structural event (eBOS or cross-TF propagation event):
- Reset child TF's `zone_count` to 0

The `manage_zones()` method returns the same break info tuple as `iora_structure.pine` plus the updated zone count.

---

### S5 — Bias + Structure Detection

#### Internal Breaks

Each TF's zone array is checked for body-close breaks. On break:

1. Capture `prev_bias` = current `bias` (before update)
2. Update `bias`: supply broken → +1, demand broken → -1
3. Classify:
   - `prev_bias == 0` or `brk_dir == prev_bias` → **iBOS**
   - `brk_dir != prev_bias` → **iCHoCH**
4. Update `TFState.last_event`, `last_event_dir`, `last_event_time`

#### External Breaks

Each child TF checks the parent TF's zone array:

| Child | Parent Zones |
|-------|-------------|
| M1 | M5 zones |
| M5 | M15 zones |
| M15 | H1 zones |
| H1 | H4 zones |
| H4 | D zones |

Same body-close check against parent zones. On external break:
- Tagged "eBOS" or "eCHoCH"
- External bias overrides internal bias
- Child zone count resets (parent structural event)

#### Cross-TF Propagation (Early Confirmation)

When H1 fires a new zone, compare to H4 boundaries:

```
H1 supply top > prev H4 supply top  →  H4 HH detected early
H1 supply top ≤ prev H4 supply top  →  H4 LH detected early
H1 demand bot < prev H4 demand bot  →  H4 LL detected early
H1 demand bot ≥ prev H4 demand bot  →  H4 HL detected early
```

Same logic for H4→D propagation.

On early detection:
- Update parent TFState accordingly
- This is where the "detect H4 HH before the H4 candle closes" happens
- Reset child zone count

---

### S6 — H1 Zone Counter + Exhaustion Clock

The zone count from S4 is interpreted here for H1 specifically:

#### Counting Rules

- **Impulse zones:** H1 zones in H4 bias direction (bearish H4 → H1 supply zones with LH tops descending)
- **Correction zones:** H1 zones opposing H4 bias (bearish H4 → H1 demand zones with HL bots ascending)
- Track separately: `h1_impulse_count` and `h1_correction_count`
- Total: `h1_zone_count = h1_impulse_count + h1_correction_count`

#### Phase Detection

```
H1 last_event == "iBOS" and last_event_dir == h4_bias  →  h1_phase = "impulse"
H1 last_event == "iCHoCH" and last_event_dir != h4_bias  →  h1_phase = "correction"
```

Phase flips on each H1 CHoCH/BOS, not on zone count alone.

#### Terminal Detection

```
h1_zone_count >= 8  →  terminal flag set
h1_impulse_count >= 5 AND h1_correction_count >= 3  →  terminal (5+3 rule)
```

#### Counter-Zone Proximity

Track whether price is inside the H4 counter-zone:

- Bearish impulse: H4 demand below the last broken D demand bottom
- Bullish impulse: H4 supply above the last broken D supply top

```
at_counter_zone = (h1_zone_count >= 6) AND (price within H4 counter-zone boundaries)
```

The H4 counter-zone is identified by finding the H4 demand/supply that sits beyond the D structural level. This uses the same logic as the persisted H4 zones in `iora_structure.pine`.

---

### S7 — Context Mode

Pure function evaluated every bar from the state tuple:

#### RIDE (with-trend)

```
conditions:
    d_bias != 0
    h4_bias == d_bias (aligned)
    h4_zone_count <= 5
    h1_phase == "correction" (pullback completing)

direction:
    d_bias == -1  →  RIDE_SHORT
    d_bias == +1  →  RIDE_LONG
```

#### FLIP (terminal reversal)

```
conditions:
    h1_zone_count >= 8 OR (h1_impulse_count >= 5 AND h1_correction_count >= 3)
    at_counter_zone == true
    H1 CHoCH opposing h4_bias has fired

direction:
    h4_bias == -1 (was bearish, flipping long)  →  FLIP_LONG
    h4_bias == +1 (was bullish, flipping short)  →  FLIP_SHORT
```

#### SCALP (hedge retracement)

```
conditions:
    H1 iBOS just fired (last_event == "iBOS", within recent bars)
    price retracing toward the H1 zone from the BOS leg

direction:
    opposite of H1 BOS direction (counter-trend hedge)
```

#### SKIP (no trade)

Default when none of the above conditions are met:
- D bias neutral
- H4 zones 7-8 without counter-zone proximity
- H1 phase unclear (no recent CHoCH or BOS)
- D and H4 bias misaligned

#### Priority

```
FLIP > RIDE > SCALP > SKIP
```

FLIP takes precedence (terminal exhaustion overrides normal with-trend). RIDE is the primary mode. SCALP only when a specific H1 BOS sweep just occurred. SKIP is the fallback.

---

### S8 — Entry Cascade

Only evaluated when `context_mode != "SKIP"`.

#### Cascade State Machine

A `var int cascade_step` tracks progress (0 = waiting, 1-5 = in cascade). Resets to 0 on:
- Context mode change
- Opposing direction event fires
- Timeout (optional — cascade must complete within a reasonable window)

#### RIDE SHORT Cascade (5 steps)

| Step | Trigger | Check |
|------|---------|-------|
| 1 | H1 LH fires | `h1_phase == "correction"` AND `H1 last_sup_cls == "LH"` |
| 2 | H1 LH overlaps H4 supply | `H1 last_sup_top >= H4 supply bottom AND H1 last_sup_top <= H4 supply top` |
| 3 | M15 LH fires inside H1 supply | `M15 last_sup_top >= H1 last_sup_bot AND M15 last_sup_top <= H1 last_sup_top` |
| 4 | M5 LH fires inside M15 demand | `M5 last_sup_top >= M15 last_dem_bot AND M5 last_sup_top <= M15 last_dem_top` |
| 5 | M1 CHoCH (LH) fires inside M5 demand | **ENTRY TRIGGER** |

#### RIDE LONG Cascade (mirror)

| Step | Trigger | Check |
|------|---------|-------|
| 1 | H1 HL fires | `h1_phase == "correction"` AND `H1 last_dem_cls == "HL"` |
| 2 | H1 HL overlaps H4 demand | containment check |
| 3 | M15 HL fires inside H1 demand | containment check |
| 4 | M5 HL fires inside M15 supply | containment check |
| 5 | M1 CHoCH (HL) fires inside M5 supply | **ENTRY TRIGGER** |

#### FLIP LONG Cascade

| Step | Trigger | Check |
|------|---------|-------|
| 1 | H1 HL fires at H4 counter-zone | `at_counter_zone == true` AND `H1 last_dem_cls == "HL"` |
| 2 | H1 HH fires (BOS confirms) | `H1 last_event == "iBOS"` AND `last_event_dir == +1` |
| 3 | M15 HL inside H1 demand | containment check |
| 4 | M5 HL inside M15 supply | containment check |
| 5 | M1 CHoCH (HL) inside M5 supply | **ENTRY TRIGGER** |

#### FLIP SHORT Cascade (mirror of FLIP LONG)

#### SCALP Cascade (simplified — 3 steps)

| Step | Trigger | Check |
|------|---------|-------|
| 1 | H1 BOS fired | `H1 last_event == "iBOS"` recently |
| 2 | Price inside H1 zone | `close >= H1 zone bottom AND close <= H1 zone top` |
| 3 | M1 CHoCH at H1 zone | **SCALP ENTRY** |

#### Entry Signal Output

On cascade completion:
- `entry_dir`: +1 (long) or -1 (short)
- `entry_price`: M1 zone boundary (demand top for long, supply bottom for short)
- `entry_stop`: H1 supply top + spread (short) or H1 demand bottom - spread (long)
- `entry_mode`: "RIDE" / "FLIP" / "SCALP"

Visual: triangle plotshape on chart. Up-green for long, down-red for short. Label with mode name.

#### Exit Signals (informational)

| Signal | Detection | Visual |
|--------|-----------|--------|
| M15 CHoCH opposing inside H1 zone | M15 event check + containment | Yellow X marker |
| Body close inside breaker zone | Close within any active breaker | Orange X marker |
| H1 zone count 5 + correction TL break | Counter + phase check | Red X marker |

Exit signals are plotted but do not gate entries. They inform the trader.

---

### S9 — Dashboard Table

Pine `table` object, positioned per input setting. Updated every bar.

#### Layout

```
┌─────────┬──────────┬────────────┬───────────┐
│ Layer   │ Bias     │ Count      │ Phase     │
├─────────┼──────────┼────────────┼───────────┤
│ D       │ BEAR ▼   │ —          │ —         │
│ H4      │ BEAR ▼   │ 4/8        │ impulse   │
│ H1      │ BEAR ▼   │ 3i + 1c   │ correction│
│ M15     │ BULL ▲   │ —          │ nested    │
│ M5      │ BEAR ▼   │ —          │ —         │
│ M1      │ —        │ —          │ waiting   │
├─────────┼──────────┼────────────┼───────────┤
│ MODE    │ RIDE SHORT              │ step 3/5 │
└─────────┴──────────┴────────────┴───────────┘
```

#### Cell Contents

| Row | Bias Cell | Count Cell | Phase Cell |
|-----|-----------|------------|------------|
| D | "BULL ▲" / "BEAR ▼" / "—" (colored) | "—" | "—" |
| H4 | bias + direction | `h4_zone_count` / 8 | "impulse" / "correction" |
| H1 | bias + direction | `impulse_count`i + `correction_count`c | "impulse" / "correction" / "terminal" |
| M15 | bias + direction | "—" | "nested" if inside H1 zone, else "—" |
| M5 | bias + direction | "—" | "—" |
| M1 | bias + direction | "—" | "waiting" / "TRIGGER" |
| MODE | context mode + direction | — | cascade step N/5 or N/3 |

#### Colors

- Bull bias: green `#4CAF50`
- Bear bias: red `#F44336`
- Neutral: gray `#9E9E9E`
- RIDE mode: green background
- FLIP mode: orange background
- SCALP mode: cyan background
- SKIP mode: gray background
- TRIGGER cell: bright yellow flash

---

## Pine v6 Constraints

| Constraint | Budget | Used |
|-----------|--------|------|
| `request.security()` calls | 40 | 6 |
| `max_lines_count` | 500 | ~10 (entry/exit markers use plotshape, not lines) |
| `max_labels_count` | 500 | ~50 (zone role labels) |
| `max_boxes_count` | 500 | 0 (no boxes — zones drawn by iora_zones.pine) |
| `calc_bars_count` | 5000 | 5000 |

## Build Order (Incremental Compilation)

Each layer compiles cleanly before the next is added:

1. **S1-S3:** Types + inputs + HA detection — compiles with just 6 security calls outputting debug plots
2. **S4:** Zone state management — compiles with zone arrays and break detection
3. **S5:** Bias + structure — compiles with bias tracking and structure events
4. **S6:** H1 zone counter — compiles with exhaustion clock
5. **S7:** Context mode — compiles with mode computation
6. **S8:** Entry cascade — compiles with cascade state machine + entry signals
7. **S9:** Dashboard — compiles with table display

## File Location

`C:\Iora\tw_indicators\system\iora_intraday.pine`

Sits alongside the existing system indicators:
- `iora_structure.pine`
- `iora_zones.pine`

## Relationship to Existing Indicators

| Indicator | Role | Stays on Chart |
|-----------|------|---------------|
| `iora_zones.pine` | Visual: zone boxes, HH/LL lines, sequence labels | Yes |
| `iora_structure.pine` | Visual: BOS/CHoCH lines, breaker boxes, persisted zones | Yes |
| `iora_structure_trendlines.pine` | Visual: zone-confirmed trendlines | Yes |
| **`iora_intraday.pine`** (new) | Decision: state machine, context mode, entry cascade, dashboard | Yes |

All four run independently. The new indicator replicates zone detection internally (can't share Pine arrays between indicators). The visual indicators provide the chart context; the intraday indicator provides the trading decisions.
