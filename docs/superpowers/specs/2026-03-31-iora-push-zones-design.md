# Iora Push Zones — Design Spec

**Date:** 2026-03-31
**File:** `tw_indicators/iora_zones/iora_push_zones.pine`
**Base:** `iora_zones.pine` (HA zone detection) + `iora_bos_choch.pine` (period structure tracking)

---

## Overview

A unified indicator that detects HA-based supply/demand zones across 8 timeframes, classifies them as **Push**, **Reversal**, or **Normal**, and overlays BOS/CHoCH structure classification using period high/low tracking. Push zones are the zones whose HA runs created new structural extremes (HH/LL), validated by a boundary-break rule. Reversal zones mark where the push structure fails if broken.

The cascading TF view — M15 pushes through H1 highs/lows, H1 through H4, H4 through Daily — emerges naturally from having push/reversal + BOS/CHoCH on all TFs simultaneously.

---

## Zone UDT

```pine
type Zone
    float   top          = 0.0
    float   bottom       = 0.0
    bool    is_supply    = false    // true = supply, false = demand
    int     origin_time  = 0
    box     bx
    bool    is_push      = false
    bool    is_reversal  = false
    string  struct_cls   = ""      // "BOS" or "CHoCH"
    string  swing_cls    = ""      // "HH", "LH", "HL", "LL"
```

- `is_supply`: boolean flag — `true` for supply, `false` for demand. Bidirectional.
- `is_push`: tagged when this zone's HA run created a new extreme, validated by boundary-break.
- `is_reversal`: the deepest opposite-side zone at the base of a push sequence. If broken, push structure has failed.
- `struct_cls`: whether the push was a BOS (continuation) or CHoCH (trend reversal).
- `swing_cls`: the HH/LH/HL/LL classification from `ha_detect()`.

---

## Core Detection Functions

### `ha_detect(float doji_pct)`

Copied from `iora_zones.pine` template. No changes.

- Computes HA candles from raw OHLC
- Detects blue/red HA color runs
- On run transition: creates zone with ORIZ spec boundaries
  - Supply: top = OHLC high (structural extreme), bottom = HA low (order-block edge)
  - Demand: top = HA high (order-block edge), bottom = OHLC low (structural extreme)
- Tracks sequence HH/LL with classification text (`hi1_txt`, `lo1_txt`)
- Returns 11-value tuple: `[fire, ztop, zbot, is_sup, zt_origin, seq_hh, seq_ll, seq_hh_time, seq_ll_time, hi1_txt, lo1_txt]`
- On any given fire bar, only one of `hi1_txt`/`lo1_txt` is freshly updated — the one matching the current run transition direction. The other retains its value from the last opposite-direction fire (`var string` persistence).

### `track_period(string tf)`

Copied from `iora_bos_choch.pine`. No changes.

- Tracks previous closed period high/low for a given TF
- Detects first break time of each level
- Runs on chart TF — zero extra `request.security()` calls
- Returns 6-value tuple: `[prev_hi, prev_hi_t, prev_lo, prev_lo_t, hi_brk_t, lo_brk_t]`
- Called once per enabled TF — the same 8 TFs used for `request.security()` (M1, M5, M15, H1, H4, D, W, MN). Note: `iora_bos_choch.pine` uses a different TF set; this indicator creates its own `track_period()` calls matching its 8 TFs

---

## Push Validation — Boundary-Break Rule

The critical rule that the prior push zone indicators were missing.

### Key concept: trigger zone vs tagged zone

Zone fires happen on HA color-run transitions. The zone that **fires** (trigger) is not the zone that gets **tagged** as PUSH — they are on opposite sides:

- Blue→red transition fires a **supply** zone (with `hi1_txt` = HH or LH)
- Red→blue transition fires a **demand** zone (with `lo1_txt` = LL or HL)

The trigger zone confirms the **previous opposite-side zone** as the push zone, because the completed run is what created the structural extreme.

### State per TF

```
var float prev_push_extreme_hi = na   // seq_hh value of last confirmed bullish push
var float prev_push_extreme_lo = na   // seq_ll value of last confirmed bearish push
```

### Bearish push validation (supply pushing to new LL)

All push validation runs **only on fire bars** with the correct direction guard. Since `hi1_txt`/`lo1_txt` are `var string` that persist across bars, a supply fire could see stale `lo1_txt == "LL"` from a previous demand fire. The `is_sup` check prevents cross-contamination:

- Bearish: `if fire and not is_sup and lo1_txt == "LL"`
- Bullish: `if fire and is_sup and hi1_txt == "HH"`

1. Red HA run pushes price down, creating a new sequence low
2. Red→blue transition fires a **demand** zone with `lo1_txt == "LL"`
3. This is the **trigger** — the completed red run made a new LL
4. **Boundary check:** did `seq_ll` break below `prev_push_extreme_lo`?
   - Wick or body — any price exceedance counts for push validation
   - **Bootstrap:** if `prev_push_extreme_lo` is `na` (first LL ever), auto-qualifies as push
5. If yes → valid push:
   - Tag the **most recent unbroken supply zone** as PUSH — iterate the TF's zone array from the end (highest index = most recently added), filter by `is_supply == true`, pick the first match. This is the zone whose red run created the LL.
   - Update `prev_push_extreme_lo` to `seq_ll`
   - Tag the **most recent unbroken demand zone** as REVERSAL — same search (filter `is_supply == false`, highest index). This is the demand zone just created by the trigger fire — it marks the base of the push. The tag is applied immediately after zone creation in the same `process()` invocation.
   - The reversal zone retains its original `swing_cls` from detection (e.g., "LL") — this field is unused in reversal label rendering.
6. If no → not a push:
   - Zones remain normal, no push/reversal tags
   - Previous push state unchanged

### Bullish push validation (demand pushing to new HH)

Mirror: blue HA run pushes price up. Blue→red transition fires a **supply** zone with `hi1_txt == "HH"` (only evaluated on fire bars). Check `seq_hh > prev_push_extreme_hi` (or `na` bootstrap). If yes, tag most recent unbroken demand zone (highest index, `is_supply == false`) as PUSH, most recent unbroken supply zone (highest index, `is_supply == true`) as REVERSAL, update `prev_push_extreme_hi`.

### On push zone break

Broken push zones are deleted immediately (body close through boundary). No ghost styling. The reversal zone on the opposite side remains until broken itself.

### On reversal zone break

Deleted like any broken zone. The push structure has failed — new zones forming will establish the next push/reversal naturally.

### Break standards (three levels, all intentional)

Three different break standards are used, each fit for purpose:

- **Push validation** (boundary-break): wick or body exceedance counts. The question is "did price reach a new extreme?" — wicks count because they represent real price action.
- **Zone breaks**: body-close only. Wicks into a zone are liquidity sweeps, not structural breaks. A zone is only broken when the candle body closes through its boundary.
- **Period-level breaks** (`track_period()` for BOS/CHoCH trend): wick-based (`high > prev_hi` / `low < prev_lo`). Period high/low breaks are structural — a wick that exceeds a prior period's range represents genuine structural extension regardless of close. This drives the `trend` state used for BOS/CHoCH classification.

### HH/LL classification note

The `hi1_txt` / `lo1_txt` values from `ha_detect()` are **run-to-run** comparisons (each HA run's extreme vs the previous same-side run), not swing-structure HH/LL. This is the correct granularity for push detection — each HA run is a directional move, and we want to know if it extended beyond the previous move in that direction.

---

## BOS/CHoCH Classification

### Trend tracking per TF

```
var int trend = 0    // +1 bullish, -1 bearish, 0 uninitialized
```

Updated when `track_period()` detects a break:
- `hi_brk_t` fires (previous high broken) → `trend = +1`
- `lo_brk_t` fires (previous low broken) → `trend = -1`

### Classification rules

BOS/CHoCH is classified **at push-validation time** using the current `trend` state. The `trend` state is updated independently by `track_period()` break events — it reflects the last period-level break direction, not the push direction. The push direction comes from `ha_detect()` HH/LL (run-to-run). These are independent signals that combine at classification time.

**BOS (Break of Structure)** — push direction matches current trend:
- `trend == -1` (bearish) + new push makes LL → BOS
- `trend == +1` (bullish) + new push makes HH → BOS

**CHoCH (Change of Character)** — push direction opposes current trend:
- `trend == -1` (bearish) + new push makes HH → CHoCH
- `trend == +1` (bullish) + new push makes LL → CHoCH

**Uninitialized trend** (`trend == 0`): first push gets no BOS/CHoCH classification — `struct_cls` remains `""`.

### Cascading TF view

Each TF's push zones drive the next higher TF's period high/low:

```
M15 pushes → breaks/extends H1 high/low
H1 pushes  → breaks/extends H4 high/low
H4 pushes  → breaks/extends D high/low
D pushes   → breaks/extends W high/low
```

This is an emergent property — no extra logic needed. The zone labels and structure breaks across TFs tell the full story. An M15 CHoCH inside an H1 LH supply zone signals the H1 LH S zone is forming there.

---

## Zone Labels

Labels combine TF, side, role, and structure classification:

| Zone State | Label Example |
|------------|---------------|
| Normal supply HH | `D S HH` |
| Normal demand LL | `H4 D LL` |
| Push supply BOS | `D S PUSH-BOS` |
| Push demand CHoCH | `H4 D PUSH-CHoCH` |
| Reversal demand | `H1 D REV` |
| Reversal supply | `M15 S REV` |

---

## Visual Styling

| Zone Type | Fill | Border | Width |
|-----------|------|--------|-------|
| Normal Supply | `#FF4444` @ 85% transparency | `#FF4444` @ 20% | 1 |
| Normal Demand | `#2196F3` @ 85% transparency | `#2196F3` @ 20% | 1 |
| Push Supply | `#FF4444` @ 70% transparency | `#FF4444` @ 0% | 2 |
| Push Demand | `#2196F3` @ 70% transparency | `#2196F3` @ 0% | 2 |
| Reversal | `#FFB300` @ 75% transparency | `#FFB300` @ 0% | 2 |

Push zones: brighter, thicker border. Reversal zones: amber/yellow, distinct from both supply and demand.

---

## Inputs

### Group: Zone Detection
- `Doji Body %` — float, default 5.0, range 0.1–50.0

### Group: Timeframes
| Input | Default | TF String |
|-------|---------|-----------|
| M1 | off | `"1"` |
| M5 | off | `"5"` |
| M15 | off | `"15"` |
| H1 | on | `"60"` |
| H4 | on | `"240"` |
| D | on | `"1D"` |
| W | off | `"1W"` |
| MN | off | `"1M"` |

### Group: Zone Age (max bars per TF)
One `input.int` per TF. Same defaults as `iora_zones.pine` (50 for M1–H4, 50 for D, 30 for W, 20 for MN).

### Group: Colors
- Supply Fill / Border (normal)
- Demand Fill / Border (normal)
- Push Supply Fill / Border
- Push Demand Fill / Border
- Reversal Fill / Border (amber)
- Show Zone Labels toggle

### Group: Dashboard
- Show Dashboard toggle (default on)
- Position selector (default Bottom Left)

---

## Dashboard

Compact table, one row per enabled TF:

| Column | Content | Source |
|--------|---------|--------|
| TF | Timeframe label | Static |
| Trend | BULL / BEAR / — | `track_period()` break direction |
| Push | Active push classification (e.g., `S PUSH-BOS`) or `—` | Push zone state |
| Zones | Supply/demand count (e.g., `2S 1D`) | Zone array sizes |

---

## Data Flow Summary

```
request.security() x8          track_period() x8
    │                               │
    ▼                               ▼
ha_detect() ──► zone fire    prev hi/lo + break times
    │                               │
    ▼                               ▼
edge-detect ──► new HH/LL   edge-detect ──► BOS/CHoCH
    │                               │
    └───────────┬───────────────────┘
                ▼
    process() per TF:
    1. Expire + break check (body close)
    2. Create new zone
    3. Push validation (boundary-break rule)
    4. Reversal zone tagging
    5. BOS/CHoCH classification
    6. Visual styling + labels
```

---

## File Structure

Single file: `tw_indicators/iora_zones/iora_push_zones.pine`

| Section | Content |
|---------|---------|
| S1 | Inputs |
| S2 | Types (Zone UDT) |
| S3 | Helpers (`tf_max_age`, `tf_label`) |
| S4 | `ha_detect()` — zone detection |
| S5 | `track_period()` — structure tracking |
| S6 | Zone management (`delete_zone`, `process` with push/reversal/BOS-CHoCH) |
| S7 | Data requests (8 `request.security()` calls) |
| S8 | Edge detection (zone fires + HH/LL + structure breaks + trend) |
| S9 | Zone arrays + execution (8 TFs) |
| S10 | Dashboard |

Estimated ~550–650 lines.

---

## Pine v6 Rules (from CLAUDE.md)

- `//@version=6` always
- All variables explicitly typed
- No multiline ternaries
- No reserved keywords as variable names
- `request.security()` max 40 — this indicator uses 8
- Timeframe strings: `"1"`, `"5"`, `"15"`, `"60"`, `"240"`, `"1D"`, `"1W"`, `"1M"`
- Field assignment on `.get()` — store in local variable first
- Broken zones deleted immediately — no ghost styling
- Body-close break rule — wicks = liquidity sweep, not a break (for zone breaks)
- Wick or body exceedance for push validation (boundary-break rule)
