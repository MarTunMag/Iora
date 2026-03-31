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

### `track_period(string tf)`

Copied from `iora_bos_choch.pine`. No changes.

- Tracks previous closed period high/low for a given TF
- Detects first break time of each level
- Runs on chart TF — zero extra `request.security()` calls
- Returns 6-value tuple: `[prev_hi, prev_hi_t, prev_lo, prev_lo_t, hi_brk_t, lo_brk_t]`

---

## Push Validation — Boundary-Break Rule

The critical rule that the prior push zone indicators were missing.

### State per TF

```
var float prev_push_sup_top = na    // previous supply push zone's top
var float prev_push_sup_bot = na    // previous supply push zone's bottom
var float prev_push_dem_top = na    // previous demand push zone's top
var float prev_push_dem_bot = na    // previous demand push zone's bottom
```

### Bearish push validation (supply pushing to new LL)

1. `ha_detect()` fires a new supply zone with `lo1_txt == "LL"` (new sequence low)
2. Check: did the OHLC low of the HA run break below `prev_push_sup_bot`?
   - Wick or body — any price exceedance counts
3. If yes → valid push:
   - Tag the most recent unbroken supply zone as PUSH
   - Update `prev_push_sup_top/bot` to this zone's boundaries
   - Tag the most recent unbroken demand zone as REVERSAL (base of the push)
4. If no → not a push:
   - Zone created as normal, no push tag
   - Previous push zone remains active

### Bullish push validation (demand pushing to new HH)

Mirror: check if OHLC high broke above `prev_push_dem_top`. If yes, tag demand zone as PUSH, tag most recent supply zone as REVERSAL.

### On push zone break

Broken push zones are deleted immediately (body close through boundary). No ghost styling. The reversal zone on the opposite side remains until broken itself.

### On reversal zone break

Deleted like any broken zone. The push structure has failed — new zones forming will establish the next push/reversal naturally.

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

**BOS (Break of Structure)** — push continues the existing trend:
- Trend bearish + new push makes LL → BOS
- Trend bullish + new push makes HH → BOS

**CHoCH (Change of Character)** — push reverses the trend:
- Trend bearish + new push makes HH (breaks previous period high) → CHoCH
- Trend bullish + new push makes LL (breaks previous period low) → CHoCH

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
