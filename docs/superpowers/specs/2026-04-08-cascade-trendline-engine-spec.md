# Cascade Trendline Engine — Design Spec

> **Date:** 2026-04-08
> **Goal:** Port trendline detection from Pine to Python, build cascade direction state, add as sweep dimensions.
> **Reference implementations:** `tw_indicators/iora_structure/iora_pivot_hl_trendlines.pine`, `docs/archive/concepts_v1/standalone_rules/05_TRENDLINE_BREAKS.md`
> **Strategy doc:** `docs/system/mechanical-cascade-strategy.md`

---

## Overview

Three new capabilities, built as layers:

1. **Trendline detection** — detect pivot points per TF, draw trendlines, detect breaks
2. **Zone attribution** — when a CHoCH/BOS occurs, tag which zone caused it
3. **Cascade state** — per-bar state machine tracking the full D1→H4→H1→M15 cascade phase

These feed into the sweep engine as new filter dimensions.

---

## Layer 1: Trendline Detection

### New module: `src/iora/engine/trendline_tick.py`

**Inputs per TF per bar:** The PeriodTracker's `prev_highs[]`, `prev_lows[]` and the current push zone state (HH/HL/LH/LL from BOS/CHoCH classification).

**What it detects:**

1. **Pivot points** — Confirmed swing highs and swing lows per TF.
   - A swing high is confirmed when the PeriodTracker records a new `prev_hi` (the period closed and the high is set).
   - A swing low is confirmed when `prev_lo` is set.
   - These ARE the `prev_highs[]` and `prev_lows[]` already in PeriodTracker.

2. **Trendlines** — Two active trendlines per TF at any time:
   - **Descending TL** (impulse in bearish, correction in bullish): connects the two most recent swing highs where high[0] < high[1] (LH sequence).
   - **Ascending TL** (impulse in bullish, correction in bearish): connects the two most recent swing lows where low[0] > low[1] (HL sequence).
   - Anchored at (time1, price1) and (time2, price2). Projected forward linearly.

3. **Trendline breaks** — On each bar, check if price has broken through the projected TL value:
   - Bearish TL break (bullish signal): `bar_high > projected_tl_price` (or body close, configurable)
   - Bullish TL break (bearish signal): `bar_low < projected_tl_price` (or body close)
   - Fire once per TL. Reset when TL is redrawn (new pivot added).

4. **Impulse vs Correction classification:**
   - If TF trend = bearish (+trend from PeriodTracker):
     - Descending TL (connecting LH tops) = **impulse TL**
     - Ascending TL (connecting HL bottoms) = **correction TL**
   - If TF trend = bullish:
     - Ascending TL (connecting HL bottoms) = **impulse TL**
     - Descending TL (connecting LH tops) = **correction TL**
   - Break of impulse TL = **potential reversal**
   - Break of correction TL = **trend resumes**

### State dataclass:

```python
@dataclass(slots=True)
class TrendlineState:
    """Per-TF trendline tracking state."""
    # Descending TL (connects swing highs going lower)
    desc_anchor1_price: float = float('nan')
    desc_anchor1_bar: int = 0
    desc_anchor2_price: float = float('nan')
    desc_anchor2_bar: int = 0
    desc_active: bool = False
    desc_broken: bool = False
    desc_break_bar: int = 0
    
    # Ascending TL (connects swing lows going higher)
    asc_anchor1_price: float = float('nan')
    asc_anchor1_bar: int = 0
    asc_anchor2_price: float = float('nan')
    asc_anchor2_bar: int = 0
    asc_active: bool = False
    asc_broken: bool = False
    asc_break_bar: int = 0
```

### Tick function:

```python
def trendline_tick(
    state: TrendlineState,
    bar_idx: int,
    bar_high: float,
    bar_low: float,
    bar_close: float,
    prev_highs: list[float],  # From PeriodTracker
    prev_lows: list[float],
    trend: int,               # From PushZoneTickState.trend
    break_mode: str = "close", # "close" or "wick"
) -> list[TrendlineBreakEvent]:
```

### Break event:

```python
@dataclass(frozen=True, slots=True)
class TrendlineBreakEvent:
    tf: str
    tl_type: str           # "impulse" or "correction"  
    break_direction: str   # "bullish" (broke above desc TL) or "bearish" (broke below asc TL)
    bar_idx: int
    break_price: float
    projected_price: float
    anchor1_price: float
    anchor2_price: float
```

---

## Layer 2: Zone Attribution

### Enhancement to existing `push_zone_tick.py`

When a BOS or CHoCH is classified, record which zone was the "last active zone on the opposite side" — this is the zone that caused the structural event.

**Add to PushZone dataclass:**
```python
# In push_zone_models.py, PushZone:
caused_bos_choch: str = ""  # "BOS" or "CHoCH" if this zone caused a structural event
caused_event_tf: str = ""   # The TF level where the event occurred
```

**Logic in push_zone_tick.py:**
When CHoCH fires on TF X:
- Look at all active zones on TF X-1 (one TF below)
- The last-created zone on the side OPPOSITE to the CHoCH direction = the "causing zone"
- Tag that zone with `caused_bos_choch = "CHoCH"`, `caused_event_tf = TF_X`

Example: H4 CHoCH (bearish → bullish) fires. The last-created H1 supply zone before this event = the zone that broke to create the H4 HL. Tag it.

---

## Layer 3: Cascade State

### New module: `src/iora/engine/cascade_state.py`

A per-bar state machine that aggregates trendline breaks, zone counts, and trend directions into a single cascade phase classification.

```python
@dataclass(slots=True)
class CascadeState:
    # Trend per TF (from PeriodTracker)
    d1_trend: int = 0
    h4_trend: int = 0
    h1_trend: int = 0
    m15_trend: int = 0
    
    # TL break state per TF
    h4_impulse_tl_intact: bool = True
    h4_correction_tl_intact: bool = True
    h1_impulse_tl_intact: bool = True
    h1_correction_tl_intact: bool = True
    m15_impulse_tl_intact: bool = True
    m15_correction_tl_intact: bool = True
    
    # Zone counting (H1 zones in current push direction)
    h1_push_zone_count: int = 0
    h1_push_direction: int = 0  # +1 supply counting up, -1 demand counting down
    
    # Reversal targets
    h1_reversal_target_top: float = float('nan')
    h1_reversal_target_bottom: float = float('nan')
    h4_reversal_target_top: float = float('nan')
    h4_reversal_target_bottom: float = float('nan')
    
    # Phase classification
    phase: str = "unknown"
    # Phases: "d1_push", "h4_correction", "h4_correction_tl_break" (= resume),
    #         "h1_extended" (5+ zones), "h1_terminal" (TL break),
    #         "reversal_entry", "reversal_ride", "at_reversal_target"
```

### Tick function:

```python
def cascade_state_tick(
    state: CascadeState,
    tl_events: dict[str, list[TrendlineBreakEvent]],  # Per-TF TL break events this bar
    zone_states: dict[str, PushZoneTickState],          # Per-TF zone state
    period_trackers: dict[str, PeriodTracker],           # Per-TF period trackers
) -> str:
    """Update cascade state and return current phase."""
```

**Phase classification logic:**

```
IF d1_trend != 0 AND h4_trend == d1_trend:
    phase = "d1_push"  (D1 and H4 aligned = strong push)
    
IF d1_trend != 0 AND h4_trend != d1_trend:
    phase = "h4_correction"  (H4 pulling back against D1)
    
    IF h4_correction_tl_intact == False:
        phase = "h4_correction_tl_break"  (correction TL broke = push resumes)
        
IF h1_push_zone_count >= 5:
    phase = "h1_extended"  (push is extended)
    
    IF h1_impulse_tl_intact == False:
        phase = "h1_terminal"  (impulse TL broke = push is done)

IF phase == "h1_terminal" AND price near h1_reversal_target:
    phase = "at_reversal_target"
```

---

## Sweep Integration

### New config fields in RetestConfig:

```python
# Cascade filters
cascade_phase_filter: str = "any"          # "any", "d1_push", "h4_correction", "h1_extended", "h1_terminal", "at_reversal_target"
tl_break_filter: str = "any"              # "any", "after_impulse_break", "after_correction_break"
h1_zone_count_filter: str = "any"         # "any", "1-3", "4-7", "8+"
reversal_target_entry: bool = False        # Only enter at CHoCH-causing zone
```

### Config generator: `cascade_sweep_configs()`

Generate configs combining:
- Base: H1@H4 limit, partial TP, TTL=0, symbol-specific spread
- × cascade_phase_filter: ["any", "h4_correction", "h1_extended", "h1_terminal"]
- × tl_break_filter: ["any", "after_impulse_break", "after_correction_break"]
- × h1_zone_count_filter: ["any", "4-7", "8+"]
- × bias_filter: ["any", "against_daily", "with_daily"]
- × test_count_filter: ["any", "retested_4plus"]
- Plus the existing spread/min_sl dimensions

Target: ~200-400 configs per symbol.

### Runner script: `scripts/run_cascade_sweep.py`

Same pattern as `run_overnight_sweep.py` but using the cascade config generator.

---

## Build Sequence

| Task | Module | Description | Tests |
|:---:|---|---|---|
| 1 | `trendline_tick.py` | TrendlineState, TrendlineBreakEvent dataclasses | Unit tests with synthetic pivot data |
| 2 | `trendline_tick.py` | `trendline_tick()` function — pivot tracking, TL construction, break detection | Test with known GBPUSD H1 pivots |
| 3 | `trendline_tick.py` | Impulse/correction classification based on trend direction | Test both trend directions |
| 4 | `push_zone_tick.py` | Zone attribution — tag zones that cause BOS/CHoCH events | Test CHoCH → zone tagging |
| 5 | `cascade_state.py` | CascadeState dataclass + `cascade_state_tick()` | Unit tests with mocked inputs |
| 6 | `cascade_state.py` | Phase classification logic | Test all phase transitions |
| 7 | `pipeline.py` | Wire trendline_tick + cascade_state into the bar loop | Integration test with GBPUSD data |
| 8 | `retest_config.py` | Add cascade filter fields | Config validation tests |
| 9 | `filter_funnel.py` | Add cascade phase, TL break, zone count filters | Filter unit tests |
| 10 | `retest_sweep.py` | `cascade_sweep_configs()` generator | Config count test |
| 11 | `retest_engine.py` | Wire cascade state into candidate evaluation | Integration with sweep |
| 12 | `scripts/` | `run_cascade_sweep.py` CLI runner | Syntax check |
| 13 | Run sweep | GBPUSD cascade sweep | Analyze results |
| 14 | Analyze | Write findings doc | Update mechanical-ruleset-validated.md |

---

## Key Design Decisions

1. **Trendlines use PeriodTracker pivots, not raw price pivots.** The PeriodTracker already tracks confirmed swing H/L per TF. We reuse these rather than implementing separate pivot detection. This ensures consistency with BOS/CHoCH classification.

2. **Break detection uses body close by default** (matching Pine `i_breakType = "Close"`). Wick breaks are too noisy — a wick above the TL that closes back below is NOT a real break. Configurable via parameter.

3. **Zone attribution happens at the ENGINE level**, not in the sweep. Every CHoCH/BOS event gets its causing zone tagged in real-time as the engine runs. The sweep just filters on these tags.

4. **Cascade state is read-only in the sweep.** The cascade_state_tick runs every bar and updates the state. The sweep engine reads `state.phase` when evaluating candidates. No sweep-specific logic in the cascade module.

5. **H1 zone counting resets on D1 trend change.** When D1 trend flips, the H1 zone count starts over because it's a new push cycle.

6. **The "two steps down" rule is built into the config generator**, not the engine. The engine provides data at all TFs. The config generator creates the right TF pair combinations (H4→M15→M5, H4→H1→M15, etc.).
