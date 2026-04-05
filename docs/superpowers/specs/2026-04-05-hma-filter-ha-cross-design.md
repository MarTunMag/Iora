# HMA Direction Filter + HA-Cross-HMA Trigger — Design Spec

> **Date:** 2026-04-05
> **Status:** Approved — ready for implementation
> **Depends on:** Level 4 retest sweep infrastructure (complete), cascade_layered entry mode (complete)

---

## 1. Purpose

Add two HMA-based sweep dimensions to the retest entry system:

1. **HMA direction filter** — only enter when HMA slope matches trade direction (state-based)
2. **HA-cross-HMA trigger** — only enter downstream when the HTF HA candle crosses the HMA (event-based)

The HA-cross-HMA is the higher-value concept: it's an *event* (a specific moment when momentum shifts) rather than a *state* (directional filter). When the H1 HA candle closes above the HMA after being below, that's the trigger to start looking for M1/M5/M15 entries in the bullish direction. This catches momentum shifts earlier than a full CHoCH (which requires a structural break).

---

## 2. HMA Indicator

### Formula

```
WMA(series, period) = weighted moving average with linear weights [1, 2, ..., period]
HMA(period) = WMA(2 * WMA(close, period/2) - WMA(close, period), floor(sqrt(period)))
```

### Implementation

New module: `src/iora/indicators/hma.py`

```python
def compute_wma(series: pd.Series, period: int) -> pd.Series:
    """Weighted moving average with linear weights."""

def compute_hma(series: pd.Series, period: int) -> pd.Series:
    """Hull Moving Average — responsive trend-following indicator."""

def compute_hma_direction(
    hma: pd.Series, atr: pd.Series, flat_threshold: float = 0.05,
) -> pd.Series:
    """HMA slope direction: +1 rising, -1 falling, 0 flat.
    Flat threshold: abs(hma[i] - hma[i-1]) < flat_threshold * atr[i]."""
```

### HMA Source

HMA computed on **regular close** by default. Also testable on **HA close** as a sweep dimension:
- `hma_source="close"` — HMA tracks real price, HA crosses it (recommended default)
- `hma_source="ha_close"` — HMA on smoothed HA close (double smoothing, fewer whipsaws, more lag)

### HMA Periods

Test both 12 and 24. Sweep dimension: `hma_period`.

---

## 3. HA-Cross-HMA Detection

### Cross Event

A cross event occurs when the HA candle close transitions relative to the HMA:
- **Bullish cross:** HA close was below HMA on the previous bar, now closes above → `cross_direction = +1`
- **Bearish cross:** HA close was above HMA on the previous bar, now closes below → `cross_direction = -1`

### Cross State Tracking

At each bar on the reference TF (H1 or H4), track:
- `ha_above_hma: bool` — is the current HA close above the HMA?
- `bars_since_cross: int` — how many reference-TF bars since the last cross event
- `cross_direction: int` — direction of the most recent cross (+1 bullish, -1 bearish)

These are computed on the reference TF, then aligned to the entry TF via the existing `merge_asof` pattern (forward-filled, no lookahead). Cross event timestamps are aligned to the entry TF index, and `bars_since_cross` counts **entry-TF bars** from the aligned cross timestamp (matching the `cascade_lookback` convention). This means lookback=20 on M5 = ~100 minutes regardless of whether the cross reference TF is H1 or H4.

---

## 4. New RetestCandidate Fields

```python
# HMA state at entry time (from reference TF, per HMA period)
hma_direction_h1: int = 0       # +1 rising, -1 falling, 0 flat/unavailable
hma_direction_h4: int = 0
ha_above_hma_h1: bool = False   # HA close > HMA on H1 at this bar
ha_above_hma_h4: bool = False
# Bars since last HA-HMA cross event (entry-TF bars, not reference-TF bars)
bars_since_hma_cross_h1: int = 9999  # 9999 = no cross detected yet
bars_since_hma_cross_h4: int = 9999
# Direction of the most recent cross
hma_cross_direction_h1: int = 0  # +1 = bullish, -1 = bearish
hma_cross_direction_h4: int = 0
```

These fields are populated during `build_retest_candidates()` by looking up pre-computed HMA series aligned to the entry TF.

### Computing these at candidate build time

1. Pre-compute HMA(24) on H1 and H4 close prices (and HA close if `hma_source="ha_close"`)
2. Pre-compute HA candles on H1 and H4 (already available from `calculate_heikin_ashi()`)
3. Detect cross events on each reference TF
4. Align to entry TF via `merge_asof` (same no-lookahead pattern as existing HTF alignment)
5. At each candidate event, look up aligned HMA state and populate fields

**HMA period selection:** The candidate fields are populated with the HMA period specified by a new parameter on `build_retest_candidates()`. The default is 24. When the sweep needs period=12, it rebuilds candidates with that period. Since candidate building is the expensive step, we compute both periods in one pass and store both — but the filter config selects which to use.

**Alternative (simpler):** Store only one period's state on the candidate. The sweep runner calls `build_retest_candidates()` once per HMA period. This is simpler but doubles the expensive candidate building step. Given that we already rebuild per entry TF, this is acceptable.

**Decision:** Use the simpler approach — one period per candidate build. The sweep runner parameterizes `hma_period` and rebuilds. This keeps the candidate dataclass cleaner.

---

## 5. New RetestConfig Fields

```python
# HMA direction filter
hma_filter: str = "any"                # "with_hma_h1", "with_hma_h4", "any"

# HA-cross-HMA trigger
hma_cross_trigger: str = "none"        # "h1", "h4", "none"
hma_cross_lookback: int | str = 20     # entry-TF bars, or "until_reverse"

# HMA computation parameters
hma_period: int = 24                   # HMA period (12 or 24)
hma_source: str = "close"             # "close" or "ha_close"
```

### Dedup Key Update

Add `hma_filter`, `hma_cross_trigger`, `hma_cross_lookback`, `hma_period`, `hma_source` to the dedup key tuple in `default_configs()`.

---

## 6. Filter Logic

### HMA Direction Filter

Added to `filter_funnel.py`:

```python
def _hma_filter(config: RetestConfig) -> FilterFn:
    """Filter by HMA direction alignment."""
    if config.hma_filter == "any":
        return None

    ref_tf = "h1" if "h1" in config.hma_filter else "h4"

    def fn(c: RetestCandidate) -> bool:
        hma_dir = c.hma_direction_h1 if ref_tf == "h1" else c.hma_direction_h4
        if c.direction == "long":
            return hma_dir == 1
        return hma_dir == -1

    return fn
```

### HA-Cross-HMA Trigger

```python
def _hma_cross_trigger(config: RetestConfig) -> FilterFn:
    """Filter by HA-cross-HMA event proximity."""
    if config.hma_cross_trigger == "none":
        return None

    ref_tf = config.hma_cross_trigger  # "h1" or "h4"
    lookback = config.hma_cross_lookback

    def fn(c: RetestCandidate) -> bool:
        if ref_tf == "h1":
            cross_dir = c.hma_cross_direction_h1
            bars_since = c.bars_since_hma_cross_h1
            ha_above = c.ha_above_hma_h1
        else:
            cross_dir = c.hma_cross_direction_h4
            bars_since = c.bars_since_hma_cross_h4
            ha_above = c.ha_above_hma_h4

        # Direction must match
        if c.direction == "long" and cross_dir != 1:
            return False
        if c.direction == "short" and cross_dir != -1:
            return False

        # Lookback window check
        if lookback == "until_reverse":
            # Active as long as HA is still on the cross side
            if c.direction == "long":
                return ha_above  # HA still above HMA = cross hasn't reversed
            return not ha_above  # HA still below HMA
        else:
            return bars_since <= int(lookback)

    return fn
```

---

## 7. Sweep Configs

### Standalone HMA configs

```python
hma_entry_pairs = ["M5@H1", "M15@H1", "M5@M15", "M1@M5", "M15@H4", "H1@H4"]

# HMA direction filter (state-based)
for pair in hma_entry_pairs:
    for ref_tf in ["with_hma_h1", "with_hma_h4"]:
        for period in [12, 24]:
            for source in ["close", "ha_close"]:
                _add(RetestConfig(tf_pair=pair, hma_filter=ref_tf,
                     hma_period=period, hma_source=source))

# HA-cross trigger (event-based)
for pair in hma_entry_pairs:
    for ref_tf in ["h1", "h4"]:
        for lookback in [5, 10, 20, 50, "until_reverse"]:
            for period in [12, 24]:
                _add(RetestConfig(tf_pair=pair, hma_cross_trigger=ref_tf,
                     hma_cross_lookback=lookback, hma_period=period))
```

### High-value combos (HMA + proven configs)

```python
# limit + hma_filter — does HMA improve the SQN 23.64 limit config?
for pair in priority_pairs:
    for ref_tf in ["with_hma_h1", "with_hma_h4"]:
        _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
             hma_filter=ref_tf, hma_period=24))

# limit + hma_cross_trigger — does the cross event improve limit entries?
for pair in priority_pairs:
    for ref_tf in ["h1", "h4"]:
        for lookback in [20, "until_reverse"]:
            _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
                 hma_cross_trigger=ref_tf, hma_cross_lookback=lookback,
                 hma_period=24))

# cascade_layered + hma_filter — does HMA improve layered cascade?
for pair in ["H1@H4", "H1@D1", "M15@H4", "M5@H1"]:
    _add(RetestConfig(tf_pair=pair, entry_mode="cascade_layered",
         layered_sl_mode="own", hma_filter="with_hma_h4",
         hma_period=24, max_concurrent=3))

# against_daily + hma_filter — complementary signals?
for pair in priority_pairs:
    _add(RetestConfig(tf_pair=pair, bias_filter="against_daily",
         hma_filter="with_hma_h1", hma_period=24))
    _add(RetestConfig(tf_pair=pair, entry_mode="limit", sl_mode="zone",
         bias_filter="against_daily", hma_filter="with_hma_h1",
         hma_period=24))
```

### Estimated config count

- Standalone HMA direction: ~6 pairs x 2 ref_tfs x 2 periods x 2 sources = ~48
- Standalone HMA cross: ~6 pairs x 2 ref_tfs x 5 lookbacks x 2 periods = ~120
- High-value combos: ~40
- **Total new: ~208 configs**
- **Grand total: ~829 configs** (621 existing + 208 HMA)

---

## 8. Implementation Sequence

1. **`src/iora/indicators/hma.py`** — WMA, HMA, direction, cross detection (pure math, testable independently)
2. **`src/iora/strategy/retest_candidate.py`** — new fields on RetestCandidate + HMA state capture in `build_retest_candidates()`
3. **`src/iora/strategy/retest_config.py`** — new config fields
4. **`src/iora/strategy/filter_funnel.py`** — two new filter functions
5. **`src/iora/strategy/retest_sweep.py`** — sweep configs + dedup key update
6. **Tests** — HMA computation, cross detection, filter logic, integration

### Build order

Step 1 is independent. Steps 2-5 depend on step 1. Step 6 covers all.

---

## 9. Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HMA source default | Regular close | HMA tracks real price; HA crossing it = smoothed vs real signal |
| HMA on HA close | Sweep dimension | Let data show if double smoothing helps |
| Cross lookback | Fixed [5,10,20,50] + "until_reverse" | Fixed for precision, dynamic for full momentum wave |
| Flat threshold | 0.05 * ATR | Prevents noisy flat signals in ranging markets |
| Candidate rebuild per HMA period | Yes (simpler) | Keeps dataclass clean, rebuild cost acceptable |
| HMA computed on reference TF | H1 and H4 | These are the structural TFs that drive downstream entries |

---

## 10. What This Tests

The sweep will answer:
- Does HMA direction ADD to the structural edge, or is it redundant with bias_filter?
- Is the HA-cross-HMA *event* more valuable than the HMA *direction* state?
- Does the "until_reverse" dynamic window outperform fixed lookbacks?
- Does HMA on HA close (double smoothing) reduce whipsaws enough to justify lag?
- Which HMA period (12 vs 24) works better per TF pair?
- Does HMA improve the already-proven limit order and cascade_layered configs?
