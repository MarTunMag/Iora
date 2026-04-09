# Elliott Wave Pattern Reference — Spring Leaf

> Project reference for all 9 EW patterns detected by Canopy (Section 9B + 9C).
> Copy into `C:\Oriz\docs\` or wherever your project docs live.
>
> Version 1.0 — March 18, 2026

---

## Quick Lookup

| Code | `ew_pattern` | Name | Category | Phase | Color (label) |
|------|-------------|------|----------|-------|---------------|
| 1 | `IMPULSE` | Standard Impulse | Motive | 1 or 3 | Green (bull) / Red (bear) |
| 2 | `DIAGONAL` | Ending Diagonal | Motive | 1 or 3 | Orange `#FF9800` |
| 3 | `EXTENDED` | Extended Impulse | Motive | 1 or 3 | Green (bull) / Red (bear) |
| 4 | `REG_FLAT` | Regular Flat | Corrective | 2 or 4 | Purple `#AB47BC` |
| 5 | `EXP_FLAT` | Expanded Flat | Corrective | 2 or 4 | Purple `#AB47BC` |
| 6 | `RUN_FLAT` | Running Flat | Corrective | 2 or 4 | Purple `#AB47BC` |
| 7 | `SYM_TRI` | Symmetric Triangle | Corrective (TL) | 2 or 4 | Blue `#42A5F5` |
| 8 | `ASC_TRI` | Ascending Triangle | Corrective (TL) | 2 or 4 | Blue `#42A5F5` |
| 9 | `REV_SYM` | Reverse Symmetric | Corrective (TL) | 2 or 4 | Blue `#42A5F5` |

---

## Pine Script Source Locations

| What | Where |
|------|-------|
| EW variable declarations | Canopy Section 9 (lines ~374–414) |
| Pivot storage during wave transitions | Canopy Section 9 state machine (`h1_hfire` / `h1_lfire` blocks) |
| Pattern classification logic | Canopy Section 9B (lines ~604–680) |
| TL convergence (triangles 7/8/9) | Canopy Section 9C (lines ~1633–1653) |
| Pattern event emission | `emit_ev("EV_EW_PATTERN", "H1", ...)` at end of Section 9B |
| Dashboard display | Compass Section (table row 10, lines ~1883–1918) |
| Pattern label toggle | Input `i_ew_labels` (default: false) |

---

## State Variables Used

### Bullish Impulse Pivots (active when `h1_wave_phase == 1`)

| Variable | Set When | Meaning |
|----------|----------|---------|
| `ew_bull_w1_top` | Phase 0/2/4 → 1 (HH fires) | Wave 1 supply zone top (= `h1_zt`) |
| `ew_bull_w1_bot` | Same | Wave 1 origin (= `last_h1_dem_bot` or `h1_zb`) |
| `ew_bull_w2_bot` | Phase 2, first HL after W1 | Wave 2 correction low (= `h1_zb`) |
| `ew_bull_w3_top` | Phase 1, `h1_imp_count == 3` | Wave 3 peak (= `h1_zt`) |
| `ew_bull_w4_bot` | Phase 2, first HL after W3 | Wave 4 correction low (= `h1_zb`) |
| `ew_bull_w5_top` | Phase 1, `h1_imp_count == 5` | Wave 5 peak (= `h1_zt`) |

### Bearish Impulse Pivots (active when `h1_wave_phase == 3`)

| Variable | Set When | Meaning |
|----------|----------|---------|
| `ew_bear_w1_bot` | Phase 0/1/2 → 3 (LL fires) | Wave 1 demand zone bottom (= `h1_zb`) |
| `ew_bear_w1_top` | Same | Wave 1 origin (= `last_h1_sup_top` or `h1_zt`) |
| `ew_bear_w2_top` | Phase 4, first LH after W1 | Wave 2 correction high (= `h1_zt`) |
| `ew_bear_w3_bot` | Phase 3, `h1_imp_count == 3` | Wave 3 trough (= `h1_zb`) |
| `ew_bear_w4_top` | Phase 4, first LH after W3 | Wave 4 correction high (= `h1_zt`) |
| `ew_bear_w5_bot` | Phase 3, `h1_imp_count == 5` | Wave 5 trough (= `h1_zb`) |

### Correction Pivots (active when `h1_wave_phase == 2` or `4`)

| Variable | Set When | Meaning |
|----------|----------|---------|
| `ew_cor_start` | Impulse → correction transition | Origin of the correction (= last impulse extreme: W5 or W3 or W1) |
| `ew_cor_a_level` | First counter-trend zone in correction | Wave A endpoint |
| `ew_cor_b_level` | First same-direction zone in correction | Wave B endpoint (retrace back) |
| `ew_cor_c_level` | `h1_cor_count == 3` | Wave C endpoint |
| `ew_cor_is_bull` | Set on transition | `true` = bullish correction (after bearish impulse), `false` = bearish |

### Pattern State

| Variable | Type | Purpose |
|----------|------|---------|
| `ew_pattern` | `int` (0–9) | Current classified pattern |
| `ew_pattern_prev` | `int` | Previous bar's pattern (for change detection) |

---

## Pattern Detection Rules (Exact Pine Logic)

### Motive Patterns — Evaluated when `h1_wave_phase == 1` or `3` and `h1_imp_count >= 2`

**Requires all 4 pivots:** W1, W2, W3, W4 must all be non-`na`.

#### Pattern 2: DIAGONAL (checked first — takes priority)

```
Bullish: ew_bull_w4_bot < ew_bull_w1_top   → overlap = true → DIAGONAL
Bearish: ew_bear_w4_top > ew_bear_w1_bot   → overlap = true → DIAGONAL
```

Wave 4 invades Wave 1 territory. This is a wedge / ending diagonal. Appears at the end of moves (Wave 5 or Wave C positions).

#### Pattern 3: EXTENDED (checked second)

```
Bullish: w1_rng = ew_bull_w1_top - ew_bull_w1_bot
         w3_rng = ew_bull_w3_top - ew_bull_w2_bot
         w3_rng > w1_rng * 1.618  → EXTENDED

Bearish: w1_rng = ew_bear_w1_top - ew_bear_w1_bot
         w3_rng = ew_bear_w2_top - ew_bear_w3_bot
         w3_rng > w1_rng * 1.618  → EXTENDED
```

Wave 3 exceeds 161.8% of Wave 1. Strong trend — the impulse has more room to run.

#### Pattern 1: IMPULSE (default)

If no overlap and no extension → standard impulse. Also assigned as fallback when only W1 exists (`not na(ew_bull_w1_top)` but other pivots still `na`).

---

### Corrective Patterns — Evaluated when `h1_wave_phase == 2` or `4`

**Requires:** `ew_cor_start`, `ew_cor_a_level`, `ew_cor_b_level` all non-`na`.

The logic branches on `ew_cor_is_bull`:

#### Bearish Correction (`ew_cor_is_bull == false` — correcting a bullish impulse)

```
a_range       = ew_cor_start - ew_cor_a_level      (start is the high, A goes down)
b_retrace     = ew_cor_a_level - ew_cor_b_level     (B goes back up from A)
b_past_start  = ew_cor_b_level > ew_cor_start       (B exceeds the impulse peak)
retrace_pct   = abs(b_retrace / a_range)
```

#### Bullish Correction (`ew_cor_is_bull == true` — correcting a bearish impulse)

```
a_range       = ew_cor_a_level - ew_cor_start       (start is the low, A goes up)
b_retrace     = ew_cor_b_level - ew_cor_a_level     (B goes back down from A)
b_past_start  = ew_cor_b_level < ew_cor_start       (B exceeds the impulse trough)
retrace_pct   = abs(b_retrace / a_range)
```

#### Pattern 5: EXPANDED FLAT (checked first)

```
b_past_start == true  → EXPANDED FLAT
```

B wave exceeds the origin of the entire correction. This is the "false breakout" pattern — B tricks traders into thinking the impulse resumed, then C reverses hard past A.

#### Pattern 4: REGULAR FLAT (checked second)

```
retrace_pct >= 0.9 and retrace_pct <= 1.1  → REGULAR FLAT
```

B retraces 90–110% of A. Shallow, standard correction. C will end near A level.

#### Pattern 6: RUNNING FLAT (checked third)

```
Bearish correction: ew_cor_b_level > ew_cor_a_level AND ew_cor_c_level < ew_cor_start
Bullish correction: ew_cor_b_level < ew_cor_a_level AND ew_cor_c_level > ew_cor_start
```

Requires `ew_cor_c_level` to be non-`na`. B exceeds A but C fails to reach the correction's origin point. The correction barely corrects — extremely trending.

#### Fallback

If none match but `h1_cor_count >= 1` → defaults to `REG_FLAT` (Pattern 4).

---

### Triangle Patterns — Evaluated in Section 9C via TL Convergence

**Requires:** Both `h1_tl_bear_ln` and `h1_tl_bull_ln` exist (non-`na`).
**Phase gate:** Only during correction (`h1_wave_phase == 2` or `4`).

```
gap_start = abs(bear_y1 - bull_y1)          // TL gap at anchor point
gap_end   = abs(bear_y2 - bull_y2)          // TL gap at current extension

Convergence test: gap_end < gap_start * 0.7  // TLs closed >30% of gap
```

If convergence passes:

#### Pattern 7: SYMMETRIC TRIANGLE

```
bear_y1 > bear_y2  (descending upper TL)
AND
bull_y1 < bull_y2  (ascending lower TL)
```

Both TLs slope toward each other. Classic EW triangle — usually resolves in prior trend direction.

#### Pattern 8: ASCENDING TRIANGLE

```
abs(bear_y1 - bear_y2) < gap_start * 0.1    // Upper TL nearly flat (<10% slope)
```

Flat top, rising bottom. Bullish bias — demand is persistent.

#### Pattern 9: REVERSE SYMMETRIC (default triangle)

If converging but neither symmetric nor ascending → reverse symmetric (expanding wedge-like behavior or descending triangle). Higher volatility, less clear direction.

---

## Event Wire Format

Emitted by Canopy on pattern change (independent of `i_ew_labels` toggle):

```
EV_EW_PATTERN|H1|B|{close}|pat={PATTERN_NAME}
```

Examples:
```
EV_EW_PATTERN|H1|B|1.08234|pat=IMPULSE
EV_EW_PATTERN|H1|B|1.07891|pat=DIAGONAL
EV_EW_PATTERN|H1|B|1.08456|pat=EXP_FLAT
EV_EW_PATTERN|H1|B|1.08100|pat=SYM_TRI
```

Fires only when `ew_pattern != ew_pattern_prev` and `ew_pattern > 0`.

Bar-confirmed gating: controlled by `i_ev_confirmed` toggle (recommended `true` for deterministic replay).

---

## What Each Pattern Means for Trading

### Motive Patterns (impulse is active)

| Pattern | What's happening | Trading implication |
|---------|-----------------|---------------------|
| **IMPULSE** | Normal 5-wave push. No overlap, no extension. | Standard playbook. Expect 5 zones then ABC correction. Trade continuations on Wave 2/4 pullbacks into nested zones. |
| **DIAGONAL** | Wave 4 overlaps Wave 1. Wedge forming. | **Early exhaustion warning.** Even if UB count < 5, the push is dying. Treat `h1_imp_count >= 3` + DIAGONAL as functionally exhausted. Prepare for reversal. |
| **EXTENDED** | Wave 3 is >161.8% of Wave 1. Strong momentum. | **Don't exit early.** The trend has more room than it looks. Hold through the full 5-wave count. Wave 3 alone may create 2–3 H1 zones (the "stairs" pattern). |

### Corrective Patterns (correction is active)

| Pattern | What's happening | Trading implication |
|---------|-----------------|---------------------|
| **REG FLAT** | B retraces ~100% of A. Shallow correction. | **High-prob continuation.** When `h1_cor_count >= 2`, look for M15 nested zone entries to re-enter the prior impulse direction. |
| **EXP FLAT** | B exceeds impulse extreme. False breakout. | **Trap pattern — stay out.** The B wave fakes a trend resumption, then C reverses past A. Do not enter until C wave is confirmed complete (C creates a zone that holds). |
| **RUN FLAT** | B exceeds A start, C falls short of A end. | **Ultra-strong trend signal.** The correction barely corrects. The next impulse will be aggressive. Enter on first M15 confirmation after C. |

### Triangle Patterns (correction + TL convergence)

| Pattern | What's happening | Trading implication |
|---------|-----------------|---------------------|
| **SYM TRI** | Upper TL descending, lower TL ascending. | **Wait for breakout.** Breakout direction = prior impulse direction (continuation). Enter on M15 TL break signal after the triangle resolves. |
| **ASC TRI** | Flat top, rising bottom. | **Bullish bias.** Demand stepping up while supply holds flat. Breakout usually upward. Strong when appearing in bullish Wave 4. |
| **REV SYM** | Expanding/diverging TL structure. | **High volatility, low clarity.** Reduce size or wait. Use 1-2-3 cascade as the entry filter to cut through the noise. |

---

## Python Parity: `EWState` Dataclass

```python
from dataclasses import dataclass

EW_NAMES = {
    0: "UNKNOWN", 1: "IMPULSE", 2: "DIAGONAL", 3: "EXTENDED",
    4: "REG_FLAT", 5: "EXP_FLAT", 6: "RUN_FLAT",
    7: "SYM_TRI", 8: "ASC_TRI", 9: "REV_SYM",
}

EW_CATEGORIES = {
    1: "motive", 2: "motive", 3: "motive",
    4: "corrective", 5: "corrective", 6: "corrective",
    7: "corrective_tl", 8: "corrective_tl", 9: "corrective_tl",
}


@dataclass
class EWState:
    """Tracks all EW pivot data and current classification."""

    pattern: int = 0
    pattern_prev: int = 0

    # Bullish impulse pivots (h1_wave_phase == 1)
    bull_w1_top: float | None = None
    bull_w1_bot: float | None = None
    bull_w2_bot: float | None = None
    bull_w3_top: float | None = None
    bull_w4_bot: float | None = None
    bull_w5_top: float | None = None

    # Bearish impulse pivots (h1_wave_phase == 3)
    bear_w1_bot: float | None = None
    bear_w1_top: float | None = None
    bear_w2_top: float | None = None
    bear_w3_bot: float | None = None
    bear_w4_top: float | None = None
    bear_w5_bot: float | None = None

    # Correction pivots
    cor_start: float | None = None
    cor_a_level: float | None = None
    cor_b_level: float | None = None
    cor_c_level: float | None = None
    cor_is_bull: bool = False

    @property
    def name(self) -> str:
        return EW_NAMES.get(self.pattern, "UNKNOWN")

    @property
    def category(self) -> str:
        return EW_CATEGORIES.get(self.pattern, "unknown")

    @property
    def changed(self) -> bool:
        return self.pattern != self.pattern_prev and self.pattern > 0

    def reset_bull_impulse(self) -> None:
        self.bull_w1_top = self.bull_w1_bot = None
        self.bull_w2_bot = self.bull_w3_top = None
        self.bull_w4_bot = self.bull_w5_top = None
        self.pattern = 0

    def reset_bear_impulse(self) -> None:
        self.bear_w1_bot = self.bear_w1_top = None
        self.bear_w2_top = self.bear_w3_bot = None
        self.bear_w4_top = self.bear_w5_bot = None
        self.pattern = 0

    def reset_correction(self) -> None:
        self.cor_start = self.cor_a_level = None
        self.cor_b_level = self.cor_c_level = None
```

---

## Fibonacci Levels for EW (Reference)

Standard Fibonacci levels used by EW practitioners. Useful for projecting targets from the stored pivot data:

| Level | Ratio | Use |
|-------|-------|-----|
| Wave 2 retrace of Wave 1 | 38.2%, 50%, 61.8% | Predict Wave 2 depth: `w1_bot + (w1_top - w1_bot) * ratio` |
| Wave 3 extension of Wave 1 | 100%, 161.8%, 261.8% | Predict Wave 3 target: `w2_bot + w1_range * ratio` |
| Wave 4 retrace of Wave 3 | 23.6%, 38.2% | Predict Wave 4 depth (shallow — must not overlap Wave 1 for standard impulse) |
| Wave 5 projection | 61.8%, 100% of Wave 1 | Predict Wave 5 target: `w4_bot + w1_range * ratio` |
| Wave C projection | 100%, 161.8% of Wave A | Predict Wave C target: `cor_b + a_range * ratio` |

These are not implemented in the Pine indicators today but can be added as Dash overlay lines using the stored `ew_bull_w*` / `ew_bear_w*` pivot values.

---

## Guardrails

1. **EW classification is an enhancer, not a gate.** If `ew_pattern == 0` (unclassified), all other Spring Leaf signals remain valid. Do not wait for a pattern to trade.
2. **Never override zone breaks because of a wave count.** If the H1 zone is broken, it's broken. A "Wave 3 should hold" argument is discretionary — the system is mechanical.
3. **Do not count sub-waves below M15.** M5/M1 data is too noisy for reliable EW counting. These TFs are execution-only.
4. **Patterns can reclassify mid-wave.** An IMPULSE at Wave 2 may become DIAGONAL when Wave 4 data arrives. The latest classification is always canonical.
5. **Triangle detection requires both H1 TLs to exist.** If only one side has a push trendline, patterns 7/8/9 cannot fire. This is correct — single-sided TL data cannot confirm a triangle.
