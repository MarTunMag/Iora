# Mechanical FVG + Reversal Target + Leg Building Model

> **Date:** 2026-04-08
> **Purpose:** Documents the complete mechanical flow of how M1→M5 zones build M15→H1→H4 legs, how FVGs form at structural breaks, and how reversal targets are identified and traded.
> **Depends on:** `mechanical-cascade-strategy.md`, `05_TRENDLINE_BREAKS.md`, `11_ZONE_TRACKING_REVERSAL_TARGETS.md`

---

## 1. The Complete Flow — One Leg Cycle

This traces a single bearish-to-bullish leg transition, showing every zone creation, break, and reversal target mechanically.

### Phase 1: The H4 Low is Created

```
STARTING STATE: H4 is pushing down (bearish)
  → H1 zones (supply) are being created as the push extends
  → Each H1 supply = one step in the H4 push

THE H4 LOW FORMS:
  H1 makes its LAST LL (the lowest point of the H4 push)
    → At this H1 LL, an M15 demand zone is created (the reversal origin)
    → Inside this M15 demand, M5 demand zones form (the fractal building blocks)
    → Inside each M5 demand, M1 demand zones form (the micro-structure)

  THE H4 LOW IS CONFIRMED WHEN:
    → H1 makes an HL (not a new LL) = the H4 push is done
    → This H1 HL is visible as: M15 making HH/HL sequence inside H1
    → The M5 zones that build the H1 HL = the "push up" that confirms the bottom
```

### Phase 2: The FVG Forms at the Structural Break

```
AS H1 PUSHES UP FROM THE LOW:
  → H1 breaks above the last H1 supply (the one that was pushing price down)
  → This break creates a FAIR VALUE GAP (FVG):

  THE FVG:
    ┌─── H4 Lo X (the H4 swing low price) ───────────────┐
    │                                                       │
    │  GAP: The space between the H1 Hi (after the H4 Low) │
    │       and the broken M5 demand zone below             │
    │                                                       │
    │  This gap = price moved so fast through this area     │
    │  that no zones were created. It's an IMBALANCE.       │
    │                                                       │
    │  The broken M5 demand that was below the H4 Lo X     │
    │  = the last zone before the gap                       │
    │  = the REVERSAL TARGET                                │
    └───────────────────────────────────────────────────────┘

  SPECIFICALLY:
    H4 Lo X price = where the H4 swing low was set
    H1 Hi after H4 Lo X = where H1 pushed to after the reversal
    The M5 demand zone that BROKE as price pushed up through the H4 Lo X area
      → This broken M5 demand = now a BREAKER zone
      → It flips from demand (support) to supply (resistance) when broken
      → BUT: when price comes BACK DOWN to it, it becomes the REVERSAL TARGET
```

### Phase 3: The M15 High Forms (L15 H)

```
PRICE PUSHES UP (building the H4 correction / potential reversal):
  → M15 makes HH/HL sequence (bullish internal structure)
  → Each M15 HH = one M5 push zone creating a new high
  → M5 zones cascade: demand → push up → supply at top → pullback → demand higher

THE M15 HIGH (L15 H) FORMS WHEN:
  → M5 stops making HH → M5 makes LH
  → This L15 H = where the M15 push exhausted
  → NOW: M15 starts pulling back (making LH/LL)
```

### Phase 4: The Reversal at the FVG Zone

```
PRICE PULLS BACK FROM L15 H:
  → M15 making LL (pulling back down)
  → M5 supply zones form on the way down (each M5 supply = one step in the pullback)
  → Price approaches the FVG area (the gap from Phase 2)

AT THE FVG / BROKEN M5 DEMAND:
  → Price reaches the broken M5 demand zone (now acting as reversal target)
  → TWO OUTCOMES:

  OUTCOME A: ZONE HOLDS (reversal target respected)
    → Price tests the broken M5 demand and BOUNCES
    → M1 makes HL inside this zone (first sign of support)
    → M5 makes HL (confirming the zone held)
    → THIS = the entry for the LONG trade
    → The FVG is "closed" (price returned and found support)
    → Price resumes pushing up → building the next H1 leg up
    → TP: The L15 H that we just reversed from, or the H1 supply above

  OUTCOME B: ZONE BREAKS (new leg down)
    → Price breaks THROUGH the broken M5 demand
    → The FVG was NOT support — the reversal was a false one
    → A new bearish leg is forming
    → M1/M5 supply zones cascade down through the broken zone
    → The H4 push down is RESUMING (the H1 HL was just a pullback, not a reversal)
    → EXIT any longs, prepare for continuation shorts
```

### Phase 5: Riding the Move

```
IF OUTCOME A (zone held, we're long):

ENTRY: M1 demand zone inside M5 demand (at the FVG reversal target)
  → SL below the M5 zone (or below the FVG low)
  → This is structurally safe: if M5 demand breaks, the thesis is wrong

THE RIDE UP:
  M1 builds M5 HL → M5 builds M15 HL → push continues up

  WATCH FOR:
  → M5 demand zones forming on pullbacks = add position / move SL
  → M1 TL connecting HLs = if this breaks, pullback starting
  → L15 H level = first TP target (the high we reversed from)
  → H1 supply above L15 H = second TP target
  → FVG closure = price has returned to fill the imbalance

  EXIT SIGNALS:
  → M5 makes LL (not HL) = the push is weakening
  → M1 breaks the ascending TL = micro-reversal starting
  → Price reaches H1 supply and M15 CHoCH fires = the up-leg is done
```

---

## 2. The Zone Lifecycle in This Flow

Each zone goes through a lifecycle as the leg builds:

```
ZONE BORN → PUSH ZONE (initiated the move)
  │
  ├── Price leaves → CONTINUATION TARGET (retest expected)
  │
  ├── Retested and HOLDS → PROVEN SUPPORT/RESISTANCE
  │     │
  │     └── Retested again → AGED but still valid (retest 4-10 sweet spot)
  │
  ├── BROKEN by price → DEAD as original role
  │     │
  │     └── BUT: becomes BREAKER ZONE (flipped polarity)
  │           │
  │           ├── Demand broken → now acts as SUPPLY (resistance)
  │           │
  │           └── Supply broken → now acts as DEMAND (support)
  │                 │
  │                 └── When retested as breaker → REVERSAL TARGET
  │                       │
  │                       ├── Holds → NEW LEG STARTS (enter here)
  │                       │
  │                       └── Breaks again → CONTINUATION (old direction resumes)
```

**This lifecycle is what the XAUUSD charts showed.** The M5 demand at the bottom was born as a push zone. When H1 pushed through it on the way up, it became a breaker. When price came back to it (the pullback), it became the reversal target. If it holds = long entry. If it breaks = bearish continuation.

---

## 3. FVG Detection — Two Types

### Type 1: Candle FVG (micro-structure)

Standard 3-bar gap — price moved so fast between consecutive candles that a gap remains.

```
BULLISH Candle FVG: bar[2].high < bar[0].low (gap up)
BEARISH Candle FVG: bar[2].low > bar[0].high (gap down)
```

Detection: per bar, per TF. Simple comparison.

### Type 2: Structural FVG (the critical one)

**The gap between an HTF pivot and the first LTF swing that didn't reach it.**

This is NOT a candle gap — it's a structural imbalance between TF levels. It means: price made a structural break at the HTF level, but the LTF hasn't fully tested it yet. The gap MUST be filled (tested) before the structure is confirmed.

```
EXAMPLE (from your XAUUSD chart):

H4 Lo X = 4765 (the H4 structural pivot low)
H1 pushes up after the H4 low, reaches H1 Hi = 4763
H1 Hi did NOT reach H4 Lo X

STRUCTURAL FVG:
  Top:    4765 (H4 Lo X)
  Bottom: 4763 (H1 Hi)
  Gap:    2 points
  
  This means: the H1 push up after the reversal fell SHORT of testing
  the H4 structural level. Price will return to fill this gap.
  
  WHEN FILLED (price reaches 4765):
    → If zone at 4765 HOLDS: H4 Lo X confirmed as resistance, bearish continues
    → If zone at 4765 BREAKS: H4 structural break, potential reversal up
```

### Structural FVG at EVERY TF Pair

The same pattern applies at every parent-child TF relationship:

| HTF Pivot | LTF First Swing | Structural FVG | What it Tests |
|---|---|---|---|
| **D1 Hi X** | H4 Lo after D1 Hi | Gap: D1 Hi X → H4 Lo | Does H4 pullback reach the D1 high? If not = unfilled |
| **D1 Lo X** | H4 Hi after D1 Lo | Gap: H4 Hi → D1 Lo X | Does H4 bounce reach the D1 low? |
| **H4 Hi X** | H1 Lo after H4 Hi | Gap: H4 Hi X → H1 Lo | Does H1 pullback reach the H4 high? |
| **H4 Lo X** | H1 Hi after H4 Lo | Gap: H1 Hi → H4 Lo X | Does H1 bounce reach the H4 low? **Your chart example** |
| **H1 Hi X** | M15 Lo after H1 Hi | Gap: H1 Hi X → M15 Lo | Does M15 pullback reach the H1 high? |
| **H1 Lo X** | M15 Hi after H1 Lo | Gap: M15 Hi → H1 Lo X | Does M15 bounce reach the H1 low? |
| **M15 Hi X** | M5 Lo after M15 Hi | Gap: M15 Hi X → M5 Lo | Does M5 pullback reach the M15 high? |
| **M15 Lo X** | M5 Hi after M15 Lo | Gap: M5 Hi → M15 Lo X | Does M5 bounce reach the M15 low? |
| **M5 Hi X** | M1 Lo after M5 Hi | Gap: M5 Hi X → M1 Lo | Does M1 pullback reach the M5 high? |
| **M5 Lo X** | M1 Hi after M5 Lo | Gap: M1 Hi → M5 Lo X | Does M1 bounce reach the M5 low? |

### Structural FVG Lifecycle

```
1. CREATED: HTF makes pivot, LTF makes first counter-swing that falls SHORT
   → Gap marked between HTF pivot price and LTF swing price

2. OPEN: Price has not returned to the gap area
   → This is a MAGNET — price is structurally expected to return
   → Entries TOWARD the gap = higher probability (trading toward the magnet)

3. TESTED: Price returns to the gap area
   → Now watching: does the zone at the HTF pivot hold or break?
   → If we have a zone (breaker or push zone) at the gap boundary = entry setup

4. FILLED: Price trades THROUGH the gap, touching the HTF pivot level
   → If zone HOLDS: HTF structure confirmed, trade the rejection
   → If zone BREAKS: structural break, new leg forming, trade the continuation

5. CLOSED: Gap is fully traded through and price has moved beyond
   → No longer relevant — structure has resolved
```

### Implementation

```python
@dataclass(frozen=True, slots=True)
class StructuralFVG:
    htf: str              # The higher TF ("H4", "H1", "D1")
    ltf: str              # The lower TF ("H1", "M15", "M5")
    direction: str        # "bullish" (gap above, HTF hi > LTF lo) or "bearish" (gap below)
    htf_pivot_price: float  # The HTF pivot level (H4 Lo X, D1 Hi X, etc.)
    ltf_swing_price: float  # The LTF first swing that fell short
    gap_top: float        # Upper boundary = max(htf_pivot, ltf_swing)
    gap_bottom: float     # Lower boundary = min(htf_pivot, ltf_swing)
    created_bar: int
    created_time: pd.Timestamp
    filled: bool = False
    fill_bar: int = 0

@dataclass(frozen=True, slots=True)
class CandleFVG:
    tf: str
    direction: str        # "bullish" or "bearish"
    top: float
    bottom: float
    bar_idx: int
    timestamp: pd.Timestamp
    filled: bool = False
```

**Detection of Structural FVG:** After each HTF pivot is confirmed (PeriodTracker records new prev_hi or prev_lo), track the first LTF swing in the opposite direction. If that LTF swing doesn't reach the HTF pivot price = structural FVG exists.

**Detection of Candle FVG:** Standard `high[2] < low[0]` or `low[2] > high[0]` per TF per bar.

### Sweep Dimensions

```python
# Candle FVG
require_candle_fvg_at_entry: bool = False  # Unfilled candle FVG at entry zone

# Structural FVG  
structural_fvg_filter: str = "any"  # "any", "inside_gap", "at_gap_boundary", "gap_filled"
# "inside_gap" = entry zone sits INSIDE an unfilled structural FVG (trading toward the magnet)
# "at_gap_boundary" = entry zone is at the HTF pivot side of the gap (the test point)
# "gap_filled" = only enter after the gap has been filled and zone held/broke
```

**Expected impact:**
- `inside_gap`: higher WR because price is being pulled toward the HTF pivot
- `at_gap_boundary`: highest conviction reversal entries (the structural test point)
- `gap_filled` + zone holds: the highest R:R entry (confirmed structural level)

---

## 4. The Reversal Target Chain

Combining zones, FVGs, and pivots into a mechanical reversal target identification:

```
STEP 1: H4 makes a structural break (eBOS or eCHoCH)
  → Identify the H1 zone that CAUSED the break (zone attribution — Layer 2)
  → Identify any FVG created during the break

STEP 2: The reversal target is the INTERSECTION of:
  → The broken zone (now a breaker)
  → The FVG boundary (if one exists)
  → The pivot level (L60/L240 from HL_Ladder)

STEP 3: When price returns to this intersection:
  → M15 must show structural confirmation (CHoCH or TL break)
  → M5 must show zone holding (wick_touch but body close above/below)
  → M1 must show internal structure confirming (iBOS in the new direction)

STEP 4: Entry at M1 zone inside M5 zone at the reversal target
  → SL below the target zone (the breaker + FVG boundary)
  → TP1: Last M15 high/low (the immediate structural target)
  → TP2: The H1 zone that started the push (the origin of the break)
  → TP3: FVG closure level (where the imbalance is fully filled)
```

---

## 5. What We Detect vs What's Missing

| Component | Status | Module |
|---|---|---|
| Zone creation (push/cont/reversal) | ✅ Detected at birth | `push_zone_tick.py` |
| Zone break detection | ✅ Body-close break | `push_zone_tick.py` |
| Zone becomes breaker (flip polarity) | ❌ Not tracked | Need: `breaker_zone` flag on broken zones |
| FVG detection | ❌ Not implemented | Need: `fvg_tick()` in engine |
| FVG fill tracking | ❌ Not implemented | Need: track unfilled FVGs per bar |
| Zone + FVG intersection | ❌ Not computed | Need: match FVGs to nearby zones |
| Reversal target identification | ⚠️ Being built (38 trades) | `cascade_state.py` — needs fix |
| Pivot confirmation (HL_Ladder style) | ❌ Future | `HL_Ladder.mq5` child-confirmation logic |
| M1 inside M5 nesting | ✅ Static nesting works | Tasks 7-13 |
| BOS/CHoCH per TF | ✅ Detected | `push_zone_tick.py` |
| Trendline break per TF | ⚠️ Built but 3 trades | `push_trendline.py` — needs fix |

---

## 6. Build Priority

### Phase B1 (current — fix what's broken):
1. Fix TL break detection (3 trades → hundreds)
2. Fix reversal target attribution (38 trades → hundreds)
3. Fix h1_terminal threshold
4. Add CHoCH conviction + momentum consumption
5. Re-run GBPUSD cascade sweep

### Phase B2 (next — add missing pieces):
6. FVG detection (`fvg_tick.py`) — simple 3-bar gap check per TF
7. Breaker zone tracking — when a zone breaks, mark it as breaker with flipped polarity
8. M1@M5 with cascade context in sweep configs
9. Zone + FVG intersection as entry quality filter

### Phase B3 (refinement):
10. HL_Ladder child-confirmation pivots
11. Zone lifecycle transitions (dynamic role changes)
12. Three-source envelope conviction (from spec 04c full version)

---

## 7. Testable Structural Overlaps — What the Sweep Must Measure

The charts show the key insight: **structural events at different TFs OVERLAP in price and time.** When an L5 high is being set, the L1 zones that built it overlap with the L15 zone that triggered it. These overlaps ARE the confirmation signals.

### 7.1 The Overlap Matrix

At any moment, price is simultaneously building pivots at every TF. The question for the sweep is: **which overlaps predict profitable entries?**

```
WHEN PRICE IS AT A GIVEN LEVEL, WHAT STRUCTURAL EVENTS OVERLAP?

Example from your XAUUSD chart (building L240 L → reversal up):

LEVEL ~4733 (the low):
  L1 (M1):    Making LL → then HL (first reversal signal)
  L5 (M5):    Making LL → the L5 that confirms the L15 LL
  L15 (M15):  Making LL → the L15 that builds the L60 L
  L60 (H1):   At the L60 L (H1 Lo)
  L240 (H4):  This IS the L240 L being set
  L1440 (D1): This confirms the L1440 H above

LEVEL ~4763 (the FVG / H4 Lo X):
  L1:   Making HH → building the L5 HH push
  L5:   Making HH → building the L15 HH
  L15:  At the L15 H (M15 Hi X)
  L60:  The H1 High that hasn't tested the H4 Lo X
  L240: The H4 Lo X level = structural pivot = FVG boundary
  FVG:  Gap between H1 Hi and the broken M5 demand below

LEVEL ~4755 (M15 D HL = current price area):
  L1:   Making HL/HH → confirming L5 HL
  L5:   At M5 D HL level → confirming L15 structure
  L15:  Making HL (M15 D HL) → building the next L15 leg up
  L60:  Inside H1 range → building H1 structure
```

### 7.2 Testable Dimensions for the Sweep

Each of these can be computed from data we already have (zone positions, pivot levels, BOS/CHoCH events):

| Dimension | How to Compute | What It Tests |
|---|---|---|
| **child_confirms_parent_pivot** | L5 HL/LL confirmed when L1 makes counter-pivot after L5 extreme | HL_Ladder confirmation rule — does child confirmation improve entry timing? |
| **zone_at_pivot_level** | Entry zone overlaps with a confirmed Ln pivot (within ATR tolerance) | Do entries AT pivot levels have higher WR? |
| **fvg_between_zone_and_pivot** | Unfilled FVG exists between entry zone and the next HTF pivot | Does FVG presence predict zone hold/break? |
| **bos_choch_overlap_count** | How many TFs have BOS/CHoCH at the same price level (within tolerance) | Do multi-TF structural events at the same level = higher conviction? |
| **zone_inside_fvg** | Entry zone sits inside an unfilled FVG | Is entering inside an FVG more profitable than outside? |
| **pivot_cascade_depth** | How many TF levels are making the same direction pivot (e.g., L1+L5+L15 all making HL = 3 deep) | Do deeper cascading confirmations = higher WR? |
| **structural_leg_phase** | Which leg are we in? (impulse 1/3/5, correction 2/4, using zone count) | Does entering during specific leg phases matter? |
| **zone_break_confirms_pivot** | A zone break at TF X coincides with a pivot confirmation at TF X+1 | Does zone break + pivot confirmation = strongest signal? |

### 7.3 The Specific Flow to Test (from your charts)

```
TEST CASE: L240 L (H4 Low) reversal trade

ENTRY CONDITIONS (all must be true):
  1. L240 (H4) has made a confirmed Low (L60 makes HL after L240 LL)
  2. L60 (H1) pushes up → creates H1 Hi that hasn't reached H4 Lo X
  3. FVG exists between H1 Hi and H4 Lo X (unfilled gap)
  4. L15 (M15) pulls back → makes HL (not LL) at the FVG level
  5. L5 (M5) demand zone exists at the M15 HL
  6. L1 (M1) makes HL inside the M5 demand → ENTER LONG

EXIT CONDITIONS (cascading TPs):
  TP1: H4 Lo X level (the FVG top) — close 50%
  TP2: Next H1 supply zone above — close 30%
  TP3: H4 supply zone (if trend reversal confirmed) — close 20%

SL: Below the M15 HL (or below the M5 demand zone)

WHAT MAKES THIS HIGH PROBABILITY:
  - L240 pivot confirmed (structural direction clear)
  - FVG exists (institutional imbalance pulling price up)
  - L15 making HL (M15 internal structure aligned with direction)
  - L5 demand holding (M5 support proven)
  - L1 confirming (M1 micro-structure aligned)
  - 5 TF levels all confirming the same direction = maximum confluence
```

### 7.4 How This Maps to Sweep Config

```python
# New config dimensions for structural overlap testing
pivot_cascade_min_depth: int = 0    # Min TFs confirming same direction (0-5)
require_fvg_at_entry: bool = False  # Only enter if unfilled FVG present
require_pivot_overlap: bool = False # Only enter if zone overlaps HTF pivot
structural_leg_filter: str = "any"  # "impulse_1", "impulse_3", "correction_2", etc.
bos_choch_min_overlap: int = 0     # Min TFs with BOS/CHoCH at entry level
```

---

## 8. Fractal SL/TP — Child Pivot SL, Parent Target TP

The core execution mechanic across ALL TF levels:

```
UNIVERSAL RULE:
  SL = last confirmed pivot on ENTRY TF (child) on the opposite side
  TP = opposing zone on PARENT TF (one level above context TF)

BUILDING L15 LL (shorting M1 inside M5 supply):
  SL: L1 H (M1 last high) — if M1 makes new HH, our short thesis is wrong
  TP: Next M15 demand zone (where L15 push is heading)

BUILDING L60 HL (longing M5 inside M15 demand):
  SL: L5 L (M5 last low) — if M5 makes new LL, pullback thesis is wrong
  TP: Next H1 supply zone (where L60 leg is heading)

BUILDING L240 (longing M15 inside H1 demand):
  SL: L15 L (M15 last low)
  TP: Next H4 supply zone

BUILDING L1440 (longing H1 inside H4 demand):
  SL: L60 L (H1 last low) — this is our proven H1@H4 production pair
  TP: Next D1 supply zone
```

**Why child_pivot SL is structurally sound:**
- The child TF's last pivot IS the invalidation point
- If M1 makes a new HH while we're short, the M5 supply we entered at is failing
- This is TIGHTER than zone SL (the pivot is closer than the zone boundary)
- Tighter SL = better R:R but potentially more stops
- The sweep tests which is better: structural precision (child_pivot) vs structural safety (zone)

**Partial TP with fractal targets:**
- Unit 1 (70%): Fixed rr=3.0 from child_pivot SL (the quick scalp)
- Unit 2 (30%): Parent TF target zone (the structural ride)
- After Unit 1: SL moves to BE, Unit 2 rides free to parent target
- This combines the high WR of the scalp with the high R:R of the structural move

---

## 9. Cross-Reference

| Document | Relationship |
|---|---|
| `mechanical-cascade-strategy.md` | Parent doc — this model is Section 5 execution detail |
| `cascade-trendline-engine-spec.md` | Build spec for the engine implementing this |
| `archive/concepts_v1/standalone_rules/05_TRENDLINE_BREAKS.md` | TL break rules used in Phase 4 |
| `archive/concepts_v1/standalone_rules/11_ZONE_TRACKING_REVERSAL_TARGETS.md` | Reversal target identification |
| `mechanical_structure_legs/04b_leg_architecture_spec.md` | How legs build parent-TF structure |
| `mechanical_structure_legs/EW_PATTERNS.md` | Wave counting for exhaustion detection |
| `mt5_indicator/HL_Ladder.mq5` | Child-confirmation pivot logic |
| `youtube_references/trendline_concepts_summary.md` | TL + zone intersection = entry (11 videos) |
