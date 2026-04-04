# Iora Structure Trendlines — Indicator Spec

> File: `iora_structure_trendlines.pine`
> Pine Script v6 | Overlay indicator
> Limits: 500 lines, 500 labels, 5000 calc bars

---

## Purpose

Trendlines anchored to **zone-confirmed swing points** (HA color transitions) instead of every candle's high/low. Each pivot is a structural event — the same events that create supply/demand zones in `iora_zones.pine` and drive BOS/CHoCH classification in `iora_structure.pine`.

The indicator draws two visual layers per enabled timeframe:
- **Internal trendlines** (dashed, thin) — sub-swing structure within a trend
- **External trendlines** (solid, thick) — structural boundaries, the true trend skeleton

Breaking an internal trendline = minor signal (pullback ending).
Breaking an external trendline = structural shift (iBOS/eBOS territory).

---

## Architecture (9 sections)

### S1 — Types

`StructTrend` UDT holds per-TF state:

| Field | Purpose |
|-------|---------|
| `hi1_p`, `hi1_t` | Most recent swing high price + time |
| `hi2_p`, `hi2_t` | Previous swing high price + time |
| `hi1_class` | 1 = HH, 2 = LH |
| `prev_sup` | Previous supply top (for HH/LH classification) |
| `lo1_p`, `lo1_t` | Most recent swing low price + time |
| `lo2_p`, `lo2_t` | Previous swing low price + time |
| `lo1_class` | 3 = HL, 4 = LL |
| `prev_dem` | Previous demand bottom (for HL/LL classification) |
| `desc_ln`, `asc_ln` | Active descending/ascending trendline objects |
| `broken_desc`, `broken_asc` | Previous broken trendlines (kept for one cycle) |
| `desc_lbl`, `asc_lbl` | Labels on active trendlines |

### S2 — Inputs

**Timeframes** (7 TFs): MN, W, D, H4, H1, M15, M5. Defaults: D + H4 + H1 on.

**Colors**: One color per TF. Broken lines get a separate gray color.

**Style**:
- `External Line Width` (default 3) — thick lines for structural TFs
- `Internal Line Width` (default 1) — thin lines for sub-swing TFs
- `Doji Body %` (default 5.0) — HA body/range threshold below which a candle is treated as doji (inherits previous color, no transition fires)

**Internal/External pairing mode**:
- `Auto (TF cascade)` — lowest enabled TF = internal, everything above = external
- `All Internal` — force all TFs to internal style (dashed, thin)
- `All External` — force all TFs to external style (solid, thick)

### S3 — Helpers

`tf_label()` converts Pine TF strings ("240") to display labels ("H4").

`is_external_tf()` determines if a TF is external in the cascade. In Auto mode, a TF is external if **any lower TF in the cascade is also enabled**. The cascade order is: M5 → M15 → H1 → H4 → D → W → MN. M5 is always internal (lowest possible).

### S4 — Zone-Based Swing Detection (`zone_swings()`)

This is a **function** that runs inside `request.security()` on each enabled TF. It does NOT use Pine lookback windows or `ta.pivothigh/low`. Instead:

1. **HA calculation** from raw OHLC: `haC = (O+H+L+C)/4`, `haO = (prev_haO + prev_haC)/2`
2. **Doji filter**: if `abs(haC - haO) / (high - low) * 100 < doji_pct`, the candle inherits the previous bar's color (no transition fires)
3. **Color state**: `is_blue` (haC >= haO) and `is_red` (haC < haO), with doji inheritance via `var` persistence
4. **Run extreme tracking**: tracks the highest OHLC `high` during a blue run and lowest OHLC `low` during a red run, resetting on color change
5. **Transition detection**: `supply_fire` = blue→red (swing high complete), `demand_fire` = red→blue (swing low complete)
6. **Output**: persistent step-function values (`var` variables) that change only on transitions. This makes edge detection on the chart TF clean — `ta.change()` or direct comparison fires exactly once per swing event.

**Returns**: `[last_shi, last_shi_t, last_dlo, last_dlo_t]` — last swing high price/time, last swing low price/time.

**Critical detail**: The run extreme prices use OHLC (not HA), so trendline anchors sit on actual price levels. HA is only used for transition detection.

### S5 — Data Requests

7 `request.security()` calls, one per TF. Each calls `zone_swings()` with:
- `gaps = barmerge.gaps_off`
- `lookahead = barmerge.lookahead_on`

Each returns 4 values: swing high price, swing high time, swing low price, swing low time.

### S6 — Chart TF Guard

Skips any TF whose period is ≤ the chart's period. You can't draw H1 structure on an H1 or H4 chart — the security call would just echo the current bar.

### S7 — Edge Detection

HTF swing events arrive as **step functions** through `request.security()` — the value stays constant between transitions, then steps to a new value when a swing fires.

Edge detection uses **direct comparison** (not `ta.change()`) to handle the `na → value` transition on the first swing:

```
bool h1_shi_new = not na(h1_shi) and (na(h1_shi[1]) or h1_shi != h1_shi[1])
```

This fires `true` on exactly one chart bar per swing event. The edge boolean then gates the price and time values into `_edge` and `_t_e` variables (na when no new swing).

### S8 — Trendline Update Methods

Two methods on `StructTrend`:

**`process_swing_high(price, time, activeColor, brokenColor, lineWidth, tfString, isExternal)`**

1. Classifies the swing: `HH` if price > previous supply top, `LH` otherwise
2. Updates `prev_sup` to current price
3. Shifts pivot history: hi1 → hi2, new → hi1
4. If 2 pivots available and times differ:
   - **LH** → draw/update descending trendline through hi2 and hi1. External = solid line, internal = dashed line.
   - **HH** → break descending trendline (turn dotted gray, reduce width). Store as `broken_desc`, clear `desc_ln`.

**`process_swing_low(price, time, ...)`**

Same logic mirrored:
- **HL** → draw/update ascending trendline through lo2 and lo1
- **LL** → break ascending trendline

**Label format**: `{i|e} {TF} {↘|↗} {HH|LH|HL|LL}`
Examples: `i H1 ↘ LH`, `e H4 ↗ HL`

**Line styles**:
- Active external = solid, width from `i_ext_w`
- Active internal = dashed, width from `i_int_w`
- Broken = dotted, gray, width reduced by 1 (min 1)

### S9 — State + Execution

7 `var StructTrend` instances (one per TF). On each bar, if the TF is enabled and passes the chart TF guard, edge-detected swing events are routed to the appropriate `process_swing_high` or `process_swing_low` call.

---

## Key Design Decisions

### Why zone-based pivots instead of every candle

The existing `iora_trendlines.pine` creates a pivot on every HA candle close — every candle's high becomes a potential LH/HH, every low a potential HL/LL. This produces many trendlines that update frequently but don't correspond to structural events.

The new indicator only creates pivots on HA color transitions. A blue→red transition means the blue (bullish) run is complete — that run's highest OHLC high is the swing high. This is the same event that creates a supply zone in `iora_zones.pine`. Fewer pivots, each one structurally meaningful.

### Why OHLC prices for trendline anchors

HA values are smoothed and lag real price. Trendlines need to sit on actual price levels so that real-time price interaction (touches, breaks) is accurate. The indicator uses HA only for transition detection, then anchors the trendline to the OHLC extreme of the completed run.

### Why persistent step-function outputs

`request.security()` with `lookahead_on` replays HTF values onto the chart TF. If the function returned `na` on non-transition bars, the security call would forward-fill the last non-na value unpredictably. By using `var` persistence and only updating on transitions, the output is a clean step function that changes exactly when a swing fires. Edge detection on the chart TF then works reliably.

### Why `extend.right` on trendlines

Active trendlines extend right indefinitely until broken (HH breaks descending, LL breaks ascending) or replaced by a new same-direction trendline. This matches how you'd draw trendlines manually — they project forward as potential support/resistance until invalidated.

### Internal/External auto-pairing logic

In Auto mode, a TF is classified as external if any lower TF in the cascade is also enabled. With D + H4 + H1 enabled:
- H1 = internal (H1 has no enabled TF below it in this set... wait, it checks if M15 or M5 is on)
- Actually: H1 is external if M15 or M5 is on. With defaults (M15 off, M5 off), H1 is internal.
- H4 is external if H1, M15, or M5 is on. H1 is on → H4 = external.
- D is external if H4, H1, M15, or M5 is on. H4 is on → D = external.

Result with defaults (D + H4 + H1): H1 = internal (dashed thin), H4 = external (solid thick), D = external (solid thick). This gives the fast reactive sub-swing trendlines on H1 and the structural boundaries on H4/D.

---

## Potential Compilation Issues

### Pine v6 specifics
- UDT (User Defined Type) syntax: `type StructTrend` with field declarations
- Method syntax: `method process_swing_high(StructTrend st, ...)` — first param is the type instance
- `var` inside functions: Pine v6 allows `var` in local scope for persistent state within `request.security()` calls
- `input.string()` with `options` array for dropdown

### Common Pine pitfalls in this code
- **`request.security()` call count**: 7 TFs × 1 call each = 7 security calls (well under the 40-call limit)
- **Return tuple size**: each `zone_swings()` returns 4 values. Pine v6 supports up to 10-element tuples.
- **`var` in functions**: `zone_swings()` uses `var` for persistent state. This works because `request.security()` executes the function in the HTF context where `var` persists across bars.
- **Method calls**: `ts_h1.process_swing_high(...)` — the UDT instance is the implicit first argument
- **Line/label deletion**: always guarded by `not na()` checks before `line.delete()` / `label.delete()`
- **`xloc.bar_time`**: all lines and labels use bar_time xloc, coordinates are Unix timestamps from `time`

### If `is_external_tf()` causes issues
The function uses `if/else if/else` with a `switch` inside. If Pine complains about the nesting, flatten to a single expression:
```pine
is_external_tf(string tf) =>
    i_ie_mode == "All Internal" ? false :
    i_ie_mode == "All External" ? true :
    tf == "1M"  ? (i_wk_on or i_dy_on or i_h4_on or i_h1_on or i_m15_on or i_m5_on) :
    tf == "1W"  ? (i_dy_on or i_h4_on or i_h1_on or i_m15_on or i_m5_on) :
    // ... etc
    false
```

### If edge detection misfires
The pattern `not na(x) and (na(x[1]) or x != x[1])` handles both the first-ever swing (na→value) and subsequent swings (value→different value). If a TF produces two identical swing prices in a row (rare but possible), the edge won't fire for the second one. This is acceptable — identical swing prices mean no structural change.

---

## Relationship to Other Iora Indicators

| Indicator | Pivot Source | What It Draws |
|-----------|-------------|---------------|
| `iora_zones.pine` | HA transitions | Zone boxes (supply/demand rectangles) |
| `iora_structure.pine` | Zone breaks (body close through zone) | BOS/CHoCH horizontal lines + breaker zones |
| `iora_trendlines.pine` (old) | Every HA candle high/low | Trendlines through consecutive candle extremes |
| **`iora_structure_trendlines.pine`** (this) | HA transitions (same as zones) | Trendlines through zone-confirmed swing points |

The new indicator shares the same pivot source as `iora_zones.pine` but draws trendlines instead of boxes. The classification (HH/LH/HL/LL) uses the same comparison logic as the zone classifier. The internal/external distinction mirrors the structural hierarchy in `iora_structure.pine`.
