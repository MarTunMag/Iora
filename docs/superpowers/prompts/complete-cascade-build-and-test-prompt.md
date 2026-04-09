# Complete Cascade Build, Fix, and Test — Master Prompt

Paste this into a fresh Claude Code CLI opened at C:\Iora

---

## PROMPT START

Read these files in order before doing anything:

1. `CLAUDE.md` — project rules
2. `docs/superpowers/specs/2026-04-08-cascade-trendline-engine-spec.md` — original build spec
3. `docs/system/mechanical-cascade-strategy.md` — full strategy with Sections 7-9
4. `docs/system/mechanical-fvg-reversal-leg-model.md` — FVG + reversal targets + testable overlaps
5. `src/iora/engine/push_trendline.py` — trendline detection (already built)
6. `src/iora/engine/cascade_state.py` — cascade state (already built)
7. `src/iora/engine/push_zone_tick.py` — zone engine
8. `src/iora/engine/push_zone_models.py` — PushZone, PeriodTracker
9. `src/iora/orchestrator/pipeline.py` — the bar loop
10. `src/iora/strategy/retest_config.py` — RetestConfig
11. `src/iora/strategy/filter_funnel.py` — filters
12. `src/iora/strategy/retest_engine.py` — sweep simulation
13. `src/iora/strategy/retest_sweep.py` — config generators
14. `results/gbpusd_cascade_sweep.csv` — first sweep results (74 configs, TL breaks broken)

After reading, you have 4 phases to execute IN ORDER. Each phase must compile 
and test green before the next. Run `python -m pytest tests/ -x -q` after each phase.

---

## PHASE 1: Debug and Fix TL Breaks + Reversal Targets

The first cascade sweep showed:
- tl_break_filter: 3 trades out of 40,529 (BROKEN)
- reversal_target_entry: 38 trades (TOO FEW)
- h1_terminal phase: 0 trades (NEVER FIRES)

### Step 1.1: Add diagnostic counting

Add a `--diagnostics` flag to the cascade sweep runner. When enabled, print at the 
end of each symbol run:

```
=== DIAGNOSTICS ===
TrendlineBreakEvents per TF:
  H4: impulse=N, correction=N
  H1: impulse=N, correction=N
  M15: impulse=N, correction=N
PeriodTracker pivot counts:
  H4: prev_highs=N entries, prev_lows=N entries
  H1: prev_highs=N, prev_lows=N
  M15: prev_highs=N, prev_lows=N
CascadeState maximums observed:
  h1_push_zone_count max: N
  cascade phases seen: {phase: count}
Zone attribution:
  Zones with caused_bos_choch set: N
  Reversal target matches: N
```

### Step 1.2: Run diagnostics on GBPUSD

```
python scripts/run_cascade_sweep.py GBPUSD --diagnostics --output results/sweeps/cascade/
```

### Step 1.3: Fix based on diagnostic output

LIKELY ISSUES (check each):

**TL breaks not firing:**
- Check if PeriodTracker.prev_highs has 2+ entries per TF (need 2 pivots to form a TL)
- Check if push_trendline_tick is being called in the pipeline bar loop
- Check if TL break events are being stored/propagated to cascade_state
- MOST LIKELY FIX: The TL break flag resets every bar. Make it STICKY — once broken, 
  stays `True` until a new TL is drawn (new pivot creates new TL). Add 
  `bars_since_tl_break: int` counter per TF. Filter on "break within last N bars" 
  instead of "break on this exact bar."
- Add sweep dimension: `tl_break_lookback: int` = [0, 5, 10, 20, 50] bars

**Reversal target too few:**
- Check how many zones get `caused_bos_choch` tag. If very few, the attribution 
  logic may be too strict (requiring exact TF-below match).
- LOOSEN: Attribute to the last zone on the opposite side at ANY TF below, not just 
  TF-1. For example, when H4 CHoCH fires, check H1, M15, AND M5 for the causing zone.
- Also: the candidate filter may require the zone to be the EXACT reversal target zone.
  LOOSEN: Check if candidate zone OVERLAPS the reversal target price range (within 
  1 ATR tolerance), not exact zone ID match.

**h1_terminal never fires:**
- Check max h1_push_zone_count observed. If max < 5, lower threshold to 3.
- Also: the h1_impulse_tl_broken check may be too strict. If h1 TL breaks also 
  aren't firing (same root cause), fixing TL breaks fixes this too.

### Step 1.4: Re-run cascade sweep after fixes

Run full 74 configs again with fixes. Verify TL break configs now have 100+ trades.

---

## PHASE 2: Add CHoCH Conviction + Momentum Consumption + EW Signals

### Step 2.1: CHoCH Conviction Classification

Add to CascadeState:

```python
h4_last_choch_conviction: str = ""   # "strong", "weak", "pre", ""
h1_last_choch_conviction: str = ""
m15_last_choch_conviction: str = ""
```

Classification (simplified):
- "strong" = CHoCH where the NEXT bar continues in the break direction (close confirms)
- "weak" = CHoCH where the next bar reverses back (wick/sweep, not committed)
- "pre" = no CHoCH yet but last 2+ bars made no new HH/LL (momentum fading)

Track by storing the CHoCH event and checking the following bar's close direction.

Add sweep dimension:
```python
choch_conviction_filter: str = "any"  # "any", "strong_only", "weak_only"
```

### Step 2.2: Momentum Consumption Count

Add to CascadeState:

```python
h4_consumption_count: int = 0       # 0-3: how many of [H1, M15, M5] match H4 direction
h4_consumption_complete: bool = False
```

Logic: On each bar, count TFs where trend matches H4 trend. Reset when H4 trend changes.

Add sweep dimension:
```python
min_consumption_count: int = 0  # 0, 1, 2, 3
```

### Step 2.3: EW Exhaustion Signals

Add to CascadeState (if not already from prior prompt):

```python
h1_zone1_top: float = float('nan')
h1_zone1_bottom: float = float('nan')
h1_zone4_overlaps_zone1: bool = False
h1_wave3_extension_ratio: float = float('nan')
```

Logic:
- On zone count == 1: store zone1 boundaries
- On zone count == 3: compute wave3 extension ratio
- On zone count >= 4: check if current zone overlaps zone1 territory

Add sweep dimensions:
```python
ew_overlap_filter: str = "any"     # "any", "no_overlap", "overlap_only"
ew_extension_filter: str = "any"   # "any", "extended", "not_extended"
```

### Step 2.4: Run sweep with all new dimensions

Expand cascade_sweep_configs() to include conviction, consumption, and EW dimensions.
Keep total under 200 configs. Run GBPUSD.

---

## PHASE 3: FVG Detection + Breaker Zones + Structural Overlaps

### Step 3.1: FVG Detection

New module: `src/iora/engine/fvg_tick.py`

```python
@dataclass(frozen=True, slots=True)
class FVGEvent:
    tf: str
    direction: str        # "bullish" or "bearish"
    top: float
    bottom: float
    bar_idx: int
    timestamp: pd.Timestamp

@dataclass(slots=True)
class FVGState:
    active_fvgs: list = field(default_factory=list)  # Unfilled FVGs (max 10)

def fvg_tick(state, bar_high, bar_low, prev2_high, prev2_low, bar_idx, ts, tf):
    """
    Bullish FVG: prev2_high < bar_low (gap up between bar[2].high and bar[0].low)
    Bearish FVG: prev2_low > bar_high (gap down between bar[2].low and bar[0].high)
    Also check existing FVGs for fill (bar range overlaps FVG range).
    """
```

Wire into pipeline per TF. Track active unfilled FVGs.

### Step 3.1b: Structural FVG Detection

This is DIFFERENT from candle FVGs. A structural FVG is the gap between an HTF pivot 
and the first LTF swing that didn't reach it.

See `docs/system/mechanical-fvg-reversal-leg-model.md` Section 3 for the full 
explanation and the TF pair matrix.

Add to `fvg_tick.py`:

```python
@dataclass(frozen=True, slots=True)
class StructuralFVG:
    htf: str              # "H4", "H1", "D1"
    ltf: str              # "H1", "M15", "M5"  
    direction: str        # "bullish" or "bearish"
    htf_pivot_price: float
    ltf_swing_price: float
    gap_top: float
    gap_bottom: float
    created_bar: int
    created_time: pd.Timestamp
    filled: bool = False
```

Detection logic:
- After each HTF pivot confirmed (new prev_hi or prev_lo in PeriodTracker):
  - Track the first LTF swing in the opposite direction
  - If LTF swing doesn't reach HTF pivot = structural FVG created
  - Gap = between HTF pivot price and LTF swing price

- Fill detection: on each bar, check if price has traded through the gap

TF pairs to check (parent → child):
- D1 pivot → H4 first swing
- H4 pivot → H1 first swing  
- H1 pivot → M15 first swing
- M15 pivot → M5 first swing
- M5 pivot → M1 first swing

Sweep dimensions:
```python
structural_fvg_filter: str = "any"  # "any", "inside_gap", "at_gap_boundary", "gap_filled"
require_candle_fvg_at_entry: bool = False
```

### Step 3.2: Breaker Zone Tracking

In push_zone_tick.py, when a zone is body-close broken:
- BEFORE removing it, copy its boundaries to a breaker list
- Add field: `PushZone.is_breaker: bool = False`
- Add field: `PushZone.breaker_polarity: str = ""` ("demand" if was supply, "supply" if was demand)
- Keep max 5 breaker zones per side per TF
- Breaker zones are removed when THEY get broken (body-close through the breaker)

### Step 3.3: Structural Overlap Metrics

Add to CascadeState:

```python
pivot_cascade_depth: int = 0        # How many TFs confirm same direction
fvg_at_candidate: bool = False      # Unfilled FVG overlaps candidate zone
breaker_at_candidate: bool = False  # Breaker zone overlaps candidate zone
bos_choch_overlap_count: int = 0    # TFs with BOS/CHoCH near current price
```

Compute per bar:
- pivot_cascade_depth: count TFs where PeriodTracker.trend matches entry direction
- fvg_at_candidate: check if any active FVG overlaps with the candidate zone boundaries
- breaker_at_candidate: check if any breaker zone overlaps candidate zone
- bos_choch_overlap_count: count TFs with recent BOS/CHoCH within 1.5*ATR of price

### Step 3.4: Sweep dimensions

```python
require_fvg_at_entry: bool = False
min_pivot_cascade_depth: int = 0      # 0, 2, 3, 4
require_breaker_zone: bool = False
min_bos_choch_overlap: int = 0        # 0, 1, 2
```

### Step 3.5: Add M1@M5 TF pair with cascade context

Add M1@M5 to cascade_sweep_configs() — NOT standalone. M1 entry at M5 zones with 
the full cascade filtering (phase, TL break, conviction, consumption, FVG, overlaps).

This tests: can M1 precision inside the cascade framework improve on the SQN 3-5 
we saw from standalone M1@M5?

---

## PHASE 4: Run Complete Sweep and Analyze

### Step 4.1: Generate final config set

cascade_sweep_configs() should produce ~200-300 configs covering:
- H1@H4 (primary) with all cascade dimensions
- M1@M5 with cascade context (secondary)
- Key cross-combinations of phase × TL break × conviction × FVG × overlap depth

### Step 4.2: Run GBPUSD sweep

```
python scripts/run_cascade_sweep.py GBPUSD --output results/sweeps/cascade/GBPUSD_complete.csv
```

### Step 4.3: Full analysis

For each dimension, compare filtered vs unfiltered:

1. **Cascade phase:** any vs d1_push vs h4_correction vs h1_extended vs h1_terminal
2. **TL break:** any vs after_impulse_break vs after_correction_break (with lookback)
3. **CHoCH conviction:** any vs strong_only vs weak_only
4. **Momentum consumption:** 0 vs 1 vs 2 vs 3
5. **Bias:** any vs against_daily vs with_daily
6. **EW overlap:** any vs no_overlap vs overlap_only
7. **EW extension:** any vs extended vs not_extended
8. **FVG at entry:** any vs required
9. **Pivot cascade depth:** 0 vs 2+ vs 3+ vs 4+
10. **Breaker zone:** any vs required
11. **M1@M5 cascade vs M1@M5 standalone**
12. **Best combined config** — the full cascade with all best filters stacked

For each comparison, report: SQN, PF, WR, trades, avgR, maxDD.

### Step 4.4: Write findings

Save to: `docs/system/cascade-complete-sweep-analysis.md`

Structure:
```
## Proven (data confirms improvement)
## Disproven (data shows no improvement or negative)
## Insufficient data (too few trades to judge)
## Production config recommendation
## Next tests needed
```

Update `docs/system/mechanical-ruleset-validated.md` with any new proven/disproven rules.

---

## PHASE 5: Fractal SL/TP Model — Child Pivot SL, Parent Target TP

The core execution mechanic: SL at the child TF's last pivot, TP at the parent TF's target zone.

### The Model

When building an L15 LL (M15 pushing down):
- ENTRY: M1 supply inside M5 supply (short)
- SL: L1 H (the M1 last confirmed high) — the child pivot that would invalidate the move
- TP options to test:
  - Next M5 demand zone below (immediate structural target)
  - L5 LL target (the M5 swing low being built)
  - L15 target zone (the M15 zone we're pushing toward)
  - Fixed R:R from the L1 H SL

When building an L60 HL (H1 pulling back up after H1 low):
- ENTRY: M5 demand inside M15 demand (long)
- SL: L5 L (the M5 last confirmed low)
- TP: Next M15 supply above, or the L60 target, or fixed R:R

The pattern repeats at EVERY scale:

```
BUILDING L15 (M15 structure):
  Entry TF: M1 (inside M5 zone)
  SL: L1 pivot (M1 last H for shorts, M1 last L for longs)
  TP: L5 target zone or L15 target zone

BUILDING L60 (H1 structure):
  Entry TF: M5 (inside M15 zone)
  SL: L5 pivot (M5 last H for shorts, M5 last L for longs)
  TP: L15 target zone or L60 target zone

BUILDING L240 (H4 structure):
  Entry TF: M15 (inside H1 zone)
  SL: L15 pivot (M15 last H for shorts, M15 last L for longs)
  TP: L60 target zone or L240 target zone

BUILDING L1440 (D1 structure):
  Entry TF: H1 (inside H4 zone)
  SL: L60 pivot (H1 last H for shorts, H1 last L for longs)
  TP: L240 target zone or L1440 target zone
```

### New SL Mode: "child_pivot"

Add to RetestConfig:
```python
sl_mode: str = "zone"  # existing: "zone", "atr", "period", "structure"
# NEW:
# "child_pivot" = SL at the entry TF's last confirmed pivot on the opposite side
#   For longs: SL at last confirmed LOW on entry TF (the L1 L or L5 L)
#   For shorts: SL at last confirmed HIGH on entry TF (the L1 H or L5 H)
```

Implementation in retest_sl_tp.py:
```python
if mode == "child_pivot":
    # Use PeriodTracker at the ENTRY TF level
    # For M1@M5: entry TF = M1, so use M1 PeriodTracker prev_hi/prev_lo
    # For M5@M15: entry TF = M5, use M5 PeriodTracker
    if c.direction == "long":
        return c.entry_tf_prev_lo - buf  # SL below last confirmed low on entry TF
    return c.entry_tf_prev_hi + buf      # SL above last confirmed high on entry TF
```

This requires adding `entry_tf_prev_hi` and `entry_tf_prev_lo` to RetestCandidate 
(populated from the entry TF's PeriodTracker at candidate creation time).

### New TP Mode: "parent_target"

Add to RetestConfig tp_mode options:
```python
# "parent_target" = TP at the nearest opposing zone on the PARENT TF
#   For M1@M5 building L15: TP at next M15 opposing zone
#   For M5@M15 building L60: TP at next H1 opposing zone
#   For M15@H1 building L240: TP at next H4 opposing zone
```

The parent TF for each entry pair:
- M1@M5 → parent = M15
- M5@M15 → parent = H1
- M15@H1 → parent = H4
- H1@H4 → parent = D1

### Sweep Dimensions for Fractal SL/TP

```python
sl_mode: ["zone", "child_pivot"]
tp_mode: ["fixed_rr", "htf_zone", "parent_target"]
```

Combined with partial TP:
- Unit 1 at fixed_rr (lock profit at child level)
- Unit 2 at parent_target (ride to parent TF zone)
- SL at child_pivot (invalidation = child structure broken)

### Multi-TF Pair Testing

The cascade_sweep_configs() should generate configs for MULTIPLE entry TF pairs,
each with the fractal SL/TP options:

```python
# Entry pairs to test (entry_tf @ context_tf):
tf_pairs = [
    "M1@M5",    # Building M15 structure
    "M5@M15",   # Building H1 structure  
    "M15@H1",   # Building H4 structure
    "H1@H4",    # Building D1 structure (our proven production pair)
]
```

For each pair, test:
- sl_mode: zone vs child_pivot
- tp_mode: fixed_rr vs parent_target
- partial: True (unit1 at rr=3, unit2 at parent_target) vs False
- With all cascade filters (phase, TL break, conviction, FVG, overlaps)

This tests the SAME mechanical model at every fractal level. The data tells us 
which TF pair + SL/TP combination produces the best risk-adjusted returns.

### Expected Outcome

The fractal model predicts:
- child_pivot SL should be TIGHTER than zone SL (the L1 H is closer than the M5 zone top)
- parent_target TP should capture MORE of the move (riding to M15/H1/H4 zone vs fixed R:R)
- The combination should produce higher R:R per trade
- But tighter SL = more stops, so WR may drop
- The sweep will reveal the optimal balance

---

## CRITICAL RULES

1. Build in layers. Each phase compiles and tests green before the next.
2. Run `python -m pytest tests/ -x -q` after EVERY code change.
3. Don't break existing functionality — 445+ tests must keep passing.
4. All dataclasses use `@dataclass(slots=True)`.
5. Tick functions mutate state in place, return events/items.
6. Use `math.isnan()` for NaN checks.
7. Keep sweep configs under 300 total to avoid multi-hour runs.
8. The data speaks. No assumptions about what works. Every dimension gets tested.

## PROMPT END
