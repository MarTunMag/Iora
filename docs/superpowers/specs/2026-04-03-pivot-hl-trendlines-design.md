# Pivot HL Trendlines — Design Spec

**Date:** 2026-04-03
**File:** `tw_indicators/iora_structure/iora_pivot_hl_trendlines.pine`
**Status:** Draft

---

## Overview

A new Pine Script v6 overlay indicator that combines per-TF pivot HL tracking (HH/LH/HL/LL classification, horizontal lines, labels) with per-TF trendline tracking (2-anchor + re-anchor + break logic) and slope divergence detection.

This is a **new indicator** — `iora_pivot_hl.pine` and `iora_pivot_trendlines.pine` remain unchanged. Templates of both are archived in `tw_indicators/templates/`.

### Key design choice: Per-TF trendlines (not merged)

The reference `iora_pivot_trendlines.pine` merges all TF levels into a single descending and single ascending TL globally. This indicator deliberately separates them: each TF level gets its own independent pair of TLs. This means:
- Each level's TL only anchors to pivots detected at that level's lookback
- Lower TF levels (M15) will re-anchor more frequently than higher TF levels (D1)
- You see the trendline structure at each timeframe independently, matching how the Pivot HL labels already show per-TF structure

---

## Inputs

### Pivot Levels (group: "Pivot Levels")

| Input    | Default | Notes |
|----------|---------|-------|
| Level 1  | M15     | Lower default set — user requested M15/H1/H4/D1 as defaults |
| Level 2  | H1      | |
| Level 3  | H4      | |
| Level 4  | D1      | |
| Level 5  | Off     | Available for W1, MN, etc. |
| Level 6  | Off     | Available for higher TFs |

All levels use the same TF options: `["Off","M1","M5","M15","M30","H1","H2","H3","H4","D1","W1","MN","3MN","6MN","12MN"]`

### Settings (group: "Settings")

| Input              | Default | Notes |
|--------------------|---------|-------|
| Right Lookback     | 1       | `minval=0, maxval=5` |
| Confirmed History  | 3       | Confirmed pivots to keep per level per side |
| TL History         | 3       | Broken/superseded TLs to keep per TF per side. Auto-reduces to 2 when 5+ levels active |
| TL Break Detection | Close   | Options: Close, Wick |

### Display (group: "Display")

| Input            | Default | Notes |
|------------------|---------|-------|
| Labels           | true    | Pivot HH/LH/HL/LL labels |
| Lines            | true    | Horizontal pivot lines |
| Show Trendlines  | true    | Master TL toggle |
| Show Divergence  | true    | Divergence arrow markers |
| TL Width         | 1       | Active trendline width, `minval=1, maxval=4` |
| Info Table       | false   | Debug table (from Pivot HL) |

### Colors (groups: "L1 Colors" through "L6 Colors")

Same as `iora_pivot_hl.pine` — per-level Hi/Lo color pairs. TLs reuse these colors.

---

## UDTs

### TLState

Tracks one trendline side (descending through highs OR ascending through lows) for a single TF level.

```
type TLState
    bool   descending  = true     // true = descending (highs), false = ascending (lows)
    color  clr         = #ef5350
    string tfName      = ""
    // 2-anchor model
    float  a1p         = na       // anchor 1 price
    int    a1b         = 0        // anchor 1 bar_index
    float  a2p         = na       // anchor 2 price
    int    a2b         = 0        // anchor 2 bar_index
    line   activeTL    = na       // current active trendline line object
    bool   broken      = false    // has the active TL been broken?
    // Anchor labels (max 2 per active TL)
    label  lbl1        = na
    label  lbl2        = na
    // Broken/superseded TL history
    array<line> history = na    // must be explicitly initialized with array.new<line>(0)
```

### PivotLevel (extended from iora_pivot_hl.pine)

Same as existing PivotLevel UDT, with two additional fields:

```
    TLState  hiTL = na    // descending TL through confirmed pivot highs
    TLState  loTL = na    // ascending TL through confirmed pivot lows
```

---

## TLState Methods

### `checkBreak(breakPrice, barIdx)`

Called every bar, before pivot processing.

- If no A2 or already broken → skip
- Project TL price at `barIdx` using slope from A1→A2
- Descending: if `breakPrice > projected` → broken
- Ascending: if `breakPrice < projected` → broken
- On break: freeze TL (dashed, faded to 65%, clip x2/y2 to break point), push to history, trim excess

### `addAnchor(price, bar, tfName, maxHistory, showTL, showDiv)`

Called when a pivot is confirmed on the corresponding side.

**State transitions (with label lifecycle):**

1. **No A1** → set A1, create lbl1
2. **A1, no A2** → set A2, create lbl2, draw active TL (solid, extend.right), check divergence
3. **Broken** → delete lbl1 and lbl2, set A1 = new pivot, create fresh lbl1, clear A2
4. **Active, pivot on/inside TL** → re-anchor:
   - Delete old lbl1
   - Move lbl2 → lbl1 (pointer reassign, no delete)
   - A1 = old A2, A2 = new pivot
   - Create new lbl2
   - Delete old activeTL, draw new activeTL
   - Check divergence
5. **Active, pivot beyond TL** → break:
   - Freeze activeTL (dashed, 65% fade, clip to break point), push to history, trim
   - Dim lbl1 and lbl2 (set textcolor transparency to 75), do NOT delete them
   - Set A1 = new pivot, clear A2, create fresh lbl1, clear lbl2

This matches the proven logic from `iora_pivot_trendlines.pine`.

### `checkDivergence()` → bool

Called when A2 is set (transitions 2 and 4 above).

- Descending TL (through highs): divergence if `a2p > a1p` (slope is positive — highs rising, contradicts bearish structure)
- Ascending TL (through lows): divergence if `a2p < a1p` (slope is negative — lows falling, contradicts bullish structure)

**Why this is not redundant with break logic:** A re-anchor (transition 4) happens when the new pivot is geometrically on/inside the projected TL — so it's not a break. But after re-anchoring (A2→A1, new→A2), the resulting TL can slope in the opposite direction. Example: two consecutive LH pivots where LH₂ > LH₁. Each is individually lower than its preceding HH, but the sequence of LHs is rising. The TL is valid (no break), but the slope contradicts the bearish structure — this is the divergence signal.

### `extendTL(barIdx)`

Called every bar. If active TL exists and not broken, extends the line's x2 to current bar_index (for visual projection beyond the last anchor).

---

## Divergence Markers

When `checkDivergence()` returns true:

- **Descending TL divergence** (highs rising): place `▼` label at A2 anchor, above price
  - Text: `"H4 ▼"` (TF name + down arrow)
  - Style: `label.style_label_down`, transparent background, level's hi color
- **Ascending TL divergence** (lows falling): place `▲` label at A2 anchor, below price
  - Text: `"H1 ▲"` (TF name + up arrow)
  - Style: `label.style_label_up`, transparent background, level's lo color

Divergence markers are created inline during `addAnchor` — no additional state tracking needed. They persist as regular labels (subject to Pine's label limit).

---

## TL Line Styling

### Active trendline
- Style: `line.style_solid`
- Color: level's hi/lo color, transparency 0
- Width: `i_tlWidth` input

### History lines (broken/superseded)
Restyled after any history mutation:

| History index (newest first) | Style | Transparency |
|------------------------------|-------|-------------|
| 0 (most recent) | `line.style_dashed` | 65 |
| 1 | `line.style_dotted` | 75 |
| 2+ | `line.style_dotted` | 85 |

History lines have `extend.none` — clipped to their break point.

---

## Processing Order (per bar)

For each active level:

```
0. breakHi = (i_breakType == "Close") ? close : high
   breakLo = (i_breakType == "Close") ? close : low
1. hiTL.checkBreak(breakHi, bar_index)       // detect TL breaks
2. loTL.checkBreak(breakLo, bar_index)
3. handleHigh(ph, pivotBar, ...)             // existing pivot HL logic
   └─ on low confirmation: loTL.addAnchor(self.pendLo, self.pendLoBar, ...)
4. handleLow(pl, pivotBar, ...)
   └─ on high confirmation: hiTL.addAnchor(self.pendHi, self.pendHiBar, ...)
5. extendLines(...)                          // existing: horizontal pivot lines
6. hiTL.extendTL(bar_index)                  // new: extend active TLs
7. loTL.extendTL(bar_index)
```

**Cross-wiring explanation:** In Pivot HL, a direction change confirms the previous opposite pivot. When `handleHigh` receives a new pivot high after a pending low, the pending low is confirmed — its price (`self.pendLo`) and bar (`self.pendLoBar`) become the anchor for `loTL.addAnchor`. Similarly, `handleLow` confirms the pending high for `hiTL.addAnchor`.

---

## Auto-Scaling TL History

```
activeLevels = count of levels where tf != "Off"
maxTLHistory = activeLevels >= 5 ? math.min(i_tlHistory, 2) : i_tlHistory
```

Computed once. Passed to all `addAnchor` calls as `maxHistory`.

---

## Drawing Budget Estimate

With 4 active levels, 3 TL history:

| Category | Count |
|----------|-------|
| Active TLs | 4 levels × 2 sides = 8 lines |
| TL history | 4 × 2 × 3 = 24 lines |
| TL anchor labels | 4 × 2 × 2 = 16 labels |
| Divergence labels | ~4-8 (occasional) |
| Pivot horizontal lines | 4 × 2 × (1 active + 3 confirmed) = 32 lines |
| Pivot labels | ~32-40 labels |
| **Total** | **~64 lines, ~56 labels** |

Well within Pine's 500/500 limits.

---

## Files

| File | Action |
|------|--------|
| `tw_indicators/iora_structure/iora_pivot_hl_trendlines.pine` | Create (new) |
| `tw_indicators/templates/iora_pivot_hl_v1.pine` | Already archived |
| `tw_indicators/templates/iora_pivot_trendlines_v1.pine` | Already archived |
| `tw_indicators/iora_structure/iora_pivot_hl.pine` | No changes |
| `tw_indicators/iora_structure/iora_pivot_trendlines.pine` | No changes |
