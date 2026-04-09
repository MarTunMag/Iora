# Phase B2 Prompt: FVG + Structural Overlaps + M1@M5 Cascade

Paste this into the build chat AFTER Phase B1 fixes are done (TL breaks firing, 
reversal target working, conviction + consumption added).

---

## PROMPT START

Read these files first:
1. `docs/system/mechanical-fvg-reversal-leg-model.md` — the full model with testable dimensions
2. `docs/system/mechanical-cascade-strategy.md` — Section 7-8 for what's built vs missing
3. `src/iora/engine/push_zone_tick.py` — existing zone engine
4. `src/iora/engine/cascade_state.py` — the cascade state you just built

You're adding 3 things to the engine, then expanding the sweep:

## 1. FVG Detection

New module: `src/iora/engine/fvg_tick.py`

Simple 3-bar gap detection per TF:

```python
@dataclass(frozen=True, slots=True)
class FVGEvent:
    tf: str
    direction: str        # "bullish" or "bearish"
    top: float            # Upper boundary of gap
    bottom: float         # Lower boundary of gap
    bar_idx: int
    timestamp: pd.Timestamp

@dataclass(slots=True)
class FVGState:
    """Per-TF FVG tracking."""
    active_fvgs: list  # List of unfilled FVGEvents (max 10 per TF)

def fvg_tick(state, bar_high, bar_low, bar_high_2, bar_low_2, bar_idx, ts, tf):
    """Check for FVG on each bar. Uses bar[0] and bar[2] (current and 2 bars back).
    Bullish FVG: bar[2].high < bar[0].low (gap up)
    Bearish FVG: bar[2].low > bar[0].high (gap down)
    Also check if any existing FVGs are now filled (price returned to the gap)."""
```

FVG fill check: on each bar, iterate active FVGs. If bar's range overlaps the FVG, mark as filled and remove.

Wire into pipeline: run fvg_tick per TF per bar, emit FVGEvents.

## 2. Breaker Zone Tracking

Enhancement to `push_zone_tick.py`:

When a zone is body-close broken:
- Don't just delete it — BEFORE deletion, record it as a breaker zone
- Add to PushZone: `is_breaker: bool = False`, `breaker_direction: str = ""`  
- When a demand zone breaks (close below bottom): `is_breaker=True, breaker_direction="supply"` (flipped)
- When a supply zone breaks (close above top): `is_breaker=True, breaker_direction="demand"` (flipped)
- Keep breaker zones in a separate list per TF (max 5 per side)
- Breaker zones are valid retest targets until THEY break again

## 3. Structural Overlap Computation

Enhancement to `cascade_state.py`:

Add per-bar computation of overlap metrics:

```python
# In CascadeState:
pivot_cascade_depth: int = 0       # How many TFs have same-direction pivot confirmed
fvg_at_entry_zone: bool = False    # Active unfilled FVG overlaps with candidate zone
bos_choch_overlap_count: int = 0   # TFs with BOS/CHoCH near current price
breaker_zone_at_level: bool = False # A breaker zone exists at/near current price
```

Logic in cascade_state_tick:
- Count how many TFs have trend matching the entry direction = pivot_cascade_depth
- Check if any unfilled FVG overlaps the candidate zone boundaries = fvg_at_entry_zone  
- Count TFs where BOS/CHoCH price is within 1 ATR of current price = bos_choch_overlap_count
- Check if any breaker zone (flipped polarity) overlaps the candidate zone = breaker_zone_at_level

## 4. Sweep Expansion

Add to RetestConfig:
```python
require_fvg_at_entry: bool = False
min_pivot_cascade_depth: int = 0      # 0, 2, 3, 4
min_bos_choch_overlap: int = 0        # 0, 1, 2
require_breaker_zone: bool = False
```

Add to filter_funnel.py: filters for each new dimension.

Add to cascade_sweep_configs(): expand configs to include:
- × require_fvg_at_entry: [False, True]
- × min_pivot_cascade_depth: [0, 2, 3]
- × require_breaker_zone: [False, True]
- Keep total configs under 200.

Also add M1@M5 as a TF pair in cascade configs:
- M1 entry at M5 zones WITH full cascade context
- Same cascade filters (phase, TL break, conviction, consumption, FVG, overlaps)
- This tests the M1/M5 fractal execution within the HTF cascade

## 5. Run and Analyze

Run GBPUSD cascade sweep with the expanded configs.
Save to: results/sweeps/cascade/GBPUSD_v2.csv

Analyze:
1. Does FVG at entry improve WR/SQN?
2. Does pivot cascade depth improve WR? (depth 3+ = 3 TFs confirming)
3. Does breaker zone at entry improve WR?
4. Does M1@M5 with cascade context beat standalone M1@M5?
5. What's the best combined config across ALL dimensions?
6. What's the WR of the full cascade (phase + TL break + conviction + FVG + depth 3+)?

Save analysis to: docs/system/cascade-sweep-v2-analysis-gbpusd.md

## PROMPT END
