# 02 — Supply & Demand Zones

> Indicator: `iora_zones.pine`
> Describes how the system creates, classifies, and manages supply/demand zones across 8 timeframes.

---

## What This Indicator Plots

- **Zone boxes** on the chart: red for supply, blue for demand
- **Zone labels**: `{TF} S {HH|LH}` for supply, `{TF} D {LL|HL}` for demand
- **HH/LL sequence lines**: dashed lines tracking the current highest high and lowest low per TF
- **Sequence labels**: last 2 highs (HH/LH) and last 2 lows (LL/HL) per enabled TF

---

## Zone Creation

Zones are created by **Heikin-Ashi color transitions** detected via `request.security()` on each enabled timeframe.

### Trigger Events

| Transition | Zone Type | Meaning |
|-----------|-----------|---------|
| Red → Blue (HA close >= HA open after red run) | **Demand** | Sellers exhausted, buyers stepping in |
| Blue → Red (HA close < HA open after blue run) | **Supply** | Buyers exhausted, sellers stepping in |

### Zone Boundaries (ORIZ Spec)

The zone is not just the transition candle — it spans the entire run that preceded it:

| Zone Type | Top | Bottom |
|-----------|-----|--------|
| **Supply** | OHLC high of the run (structural extreme) | HA low of transition candle (order-block edge) |
| **Demand** | HA high of transition candle (order-block edge) | OHLC low of the run (structural extreme) |

The run is scanned backwards (up to 50 bars) to find the extreme. For supply, the highest `high` in the blue run. For demand, the lowest `low` in the red run.

### Doji Handling

If the transition candle is a doji (body/range < 5%), the zone boundary uses the **current** candle's HA extreme instead of the previous candle's. This prevents tiny-body candles from creating unreasonably narrow zones.

---

## Zone Classification (HH / LH / HL / LL)

> One rule, every timeframe, every zone.

When a new zone fires, compare it to the **previous zone of the same type** on the same TF:

### Supply Zone (blue → red)

```
New supply top > previous supply top  →  HH  (structural — trend extends)
New supply top ≤ previous supply top  →  LH  (corrective — trend weakening)
```

### Demand Zone (red → blue)

```
New demand bot < previous demand bot  →  LL  (structural — trend extends)
New demand bot ≥ previous demand bot  →  HL  (corrective — trend weakening)
```

### What Classification Tells You

| Classification | Meaning | Structural Implication |
|---------------|---------|----------------------|
| **HH** (supply) | New high exceeded previous high | Bullish trend continuing |
| **LH** (supply) | New high failed to exceed previous | Bullish momentum fading |
| **LL** (demand) | New low exceeded previous low | Bearish trend continuing |
| **HL** (demand) | New low held above previous | Bearish momentum fading |

**This classification directly feeds BOS/CHoCH detection** (see `01_market_structure.md`):
- HH or LL zone broken → **BOS** (trend continuation confirmed)
- LH or HL zone broken → **CHoCH** (reversal signal)

---

## Zone Lifecycle

### Creation

A zone is created when the HA color transition fires and the zone passes validation:
- `ztop > zbot` (valid range)
- Zone age within TF-specific max age window
- Zone pushed to the per-TF zone array

### Active State

While active, the zone box extends to the right. Labeled with TF, type (S/D), and classification (HH/LH/HL/LL).

### Break Detection (Body Close Only)

A zone is broken **only** by a candle body close through it:

- **Supply broken**: `close > zone.top` — price body-closed above supply
- **Demand broken**: `close < zone.bottom` — price body-closed below demand

**Wicks through a zone are NOT breaks.** A wick into a supply zone is a liquidity sweep (stops above resistance being taken). The zone remains active.

### Deletion

A zone is removed from the chart when:
1. **Broken** — body close through it (immediate deletion, box removed)
2. **Expired** — zone age exceeds the TF-specific max age (in bars × TF period)
3. **Count overflow** — more than 20 supply or 20 demand zones per TF (oldest removed first)

**Broken zones are deleted immediately.** They do not persist as "ghost" zones.

---

## Sequence Tracking

The indicator tracks the **last 2 highs** and **last 2 lows** per enabled TF, updated on each zone fire:

| Tracked | Updated When | Value |
|---------|-------------|-------|
| `hi1` (most recent high) | Supply fires | Run high OHLC price + HH/LH label |
| `hi2` (previous high) | Supply fires | Previous `hi1` value shifts here |
| `lo1` (most recent low) | Demand fires | Run low OHLC price + LL/HL label |
| `lo2` (previous low) | Demand fires | Previous `lo1` value shifts here |

### HH/LL Lines

Dashed horizontal lines track the current HH and LL per TF. These extend right and update as new extremes form.

- **HH line**: orange `#FF9800` — tracks the latest sequence high
- **LL line**: cyan `#26C6DA` — tracks the latest sequence low

### Sequence Labels

Small labels at each tracked point showing `{TF} {HH|LH|HL|LL}`. Up to 4 labels per TF (2 highs + 2 lows), 32 max across 8 TFs.

---

## Cross-TF Zone Propagation

Zone classification naturally cascades upward through the timeframe hierarchy:

| This TF zone event | Creates structure at parent TF |
|--------------------|-------------------------------|
| H1 HH (supply top > prev H1 supply top) | H4 HH if top also > prev H4 supply top |
| H1 LL (demand bot < prev H1 demand bot) | H4 LL if bot also < prev H4 demand bot |
| H1 LH (supply top < prev H1 supply top) | H4 LH if top < prev H4 supply top |
| H1 HL (demand bot > prev H1 demand bot) | H4 HL if bot > prev H4 demand bot |

Same logic applies H4→D, D→W, W→MN.

---

## Visual Spec

| Element | Style | Color |
|---------|-------|-------|
| Supply zone box | Filled rectangle, border width 1 | Fill: `#FF4444` at 85% transparency, Border: `#FF4444` at 20% |
| Demand zone box | Filled rectangle, border width 1 | Fill: `#2196F3` at 85% transparency, Border: `#2196F3` at 20% |
| Zone label | Tiny text, top-right aligned | Red for supply, blue for demand |
| HH sequence line | Dashed horizontal | Orange `#FF9800` |
| LL sequence line | Dashed horizontal | Cyan `#26C6DA` |
| Sequence label | Tiny, no background | Matches line color |

---

## Configuration

| Input | Default | Description |
|-------|---------|-------------|
| Timeframes (M1–MN) | H1, H4 on | Which TFs to draw zones for |
| Zone Age per TF | 50 bars (M1–H4), 30 (W), 20 (MN) | Max age before zones expire |
| Doji Body % | 5.0 | Threshold for doji classification |
| Show Zone Labels | On | Toggle TF/type/classification labels |
| Show Sequence HH/LL | On | Toggle HH/LL dashed lines |
| Show Sequence Labels | On | Toggle HH/LH/HL/LL point labels |

---

## How It Works (Implementation Summary)

1. **HA detection** runs on raw OHLC via `request.security()` per enabled TF
2. HA candles computed manually: `haC = (O+H+L+C)/4`, `haO = (prev_haO + prev_haC)/2`
3. Color transitions detected: `is_blue and is_red[1]` (demand) or `is_red and is_blue[1]` (supply)
4. Run scanned backwards to find extreme price (highest high for supply, lowest low for demand)
5. Classification determined by comparing to previous same-type zone's extreme
6. Sequence state updated (hi1/hi2/lo1/lo2 shift)
7. Edge detection ensures each HTF event fires only once: `fire_raw and not fire_raw[1]`
8. Zone arrays managed per TF with expiry, break detection, and count limits
