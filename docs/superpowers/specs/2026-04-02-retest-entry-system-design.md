# Retest Entry System — Data-First, 4-Level Architecture

## Problem

The current strategy enters on zone **creation** (HA color flip) — producing 18 trades across 21 months with nesting required, or ~200 noisy trades without. Zone lifecycle uses age-based expiry (50 bars). No bias cascade, no retest detection, no structural context for entries.

Traders enter on zone **retests** — price returns to an existing zone after moving away. The system needs to detect retests, understand multi-TF bias, and test which combinations produce edge.

## Approach

**Approach 2 (selected):** New retest strategy layer on top of the proven push zone engine. The zone engine correctly detects HA transitions, creates zones, validates boundaries, classifies BOS/CHoCH, and handles nesting across all TFs. Only the zone lifecycle and strategy layer change.

**Build order:** Data-first. Each level feeds the next with real understanding, not assumptions. Levels 1-3 are built AND analyzed before Level 4 code is written. Level 1-3 insights inform Level 4 sweep dimensions.

---

## Level 0: Zone Engine Enhancement

Minimal change to the proven zone engine in `src/iora/engine/push_zone_tick.py`.

### Zone Lifecycle Change

- **Remove** age-based expiry (`max_age` / `birth_bar` check)
- **Keep** body-close break as the only hard invalidation (already works)
- Zones live until price closes through them

### Zone Metadata Enrichment

Add fields to `PushZone` dataclass:

| Field | Type | Description |
|-------|------|-------------|
| `birth_price_distance` | `float` | Distance from zone midpoint to close price at creation. Fresh-flip zones are near 0; zones where price already moved away are larger. Measured in ATR(14) of the zone's own TF for cross-symbol and cross-TF comparability. |
| `birth_bias_d` | `str` | Daily bias state at zone creation: `"HH_push"`, `"LH_pullback"`, `"LL_push"`, `"HL_pullback"`, `"unknown"` |
| `birth_bias_w` | `str` | Weekly context at zone creation: `"inside_w_zone"`, `"pushing_from_w"`, `"pulling_to_w"`, `"unknown"` |
| `birth_period_pattern` | `str` | Period-tracker pattern at creation, derived from the 3-deep period history on the zone's own TF. Values: `"HH_HL"` (bull push), `"LH_LL"` (bear push), `"HH_LL"` (expansion), `"LH_HL"` (compression), `"mixed"`. Computed from `PeriodTracker.prev_highs[0:2]` and `prev_lows[0:2]` at creation time. Note: uses short 4-letter form (`HH_HL`) since it's a compact zone field. The bias timeline (Level 2) uses the same computation but with descriptive suffixes (`HH_HL_bull_push`) for readability in reports. Both encode the same (high_pattern, low_pattern) pair. |
| `replacement_count` | `int` | How many same-TF same-side zones have been created since this one. When a new zone fires on TF X side S, ALL existing active zones on TF X side S have their `replacement_count` incremented by 1. This is performed by the orchestrator (`push_zone_engine.py`) after the tick function returns newly created zones, since the orchestrator has access to the full zone list per TF. |
| `test_count` | `int` | Number of times price has touched this zone. A "touch" is defined as: for demand zones, bar low <= zone.top AND bar close > zone.bottom (wick entered but didn't break); for supply zones, bar high >= zone.bottom AND bar close < zone.top. Incremented by the orchestrator during the per-bar loop, checking all active zones against the current bar's OHLC. This runs at Level 0 so the count is available for all higher levels. |
| `first_test_time` | `Timestamp | None` | Timestamp of first retest (`None` if untested). Set by the orchestrator on the first bar where `test_count` increments from 0 to 1. Uses timestamp instead of bar index for cross-session/cross-symbol comparability. |

Existing `PushZone` fields (`top`, `bottom`, `is_supply`, `origin_time`, `timeframe`, `is_push`, `is_reversal`, `is_terminal`, `struct_cls`, `swing_cls`, `count_num`) remain unchanged.

### Zone Population Cap

With age-based expiry removed, lower TFs (M1, M5) could accumulate hundreds of active zones. To prevent unbounded memory growth:
- **Soft cap:** Max 30 active zones per TF per side. When exceeded, the oldest zone (by `origin_time`) is dropped.
- Level 1 audit will reveal actual population dynamics. If the cap is regularly hit, the results will show it and the cap can be adjusted.
- This cap is a performance guard, not a strategy rule. It should rarely be reached on higher TFs.

### What Does NOT Change

- Zone detection logic (HA run-transition, boundary computation)
- Push validation (wick/body break standard)
- BOS/CHoCH classification
- Nesting detection
- Zone break detection (body-close)
- Period tracking

---

## Level 1: Zone Activity Audit

Diagnostic module. No strategy, no trades. Answers: "What does our zone engine actually produce?"

### Module: `src/iora/diagnostics/zone_audit.py`

**Input:** Symbol data (all available TFs), zone engine output.

**Output:** `ZoneAuditReport` dataclass with per-TF statistics:

| Metric | Description |
|--------|-------------|
| `zones_created` | Total zones created per TF per side |
| `zones_broken` | Total zones broken (body-close) |
| `zones_untouched` | Zones that were broken without ever being retested |
| `zones_retested` | Zones that received at least one retest |
| `avg_tests_before_break` | Average retest count before zone breaks |
| `avg_bars_to_first_test` | Average bars from creation to first retest |
| `avg_zones_alive` | Average number of active zones per TF per side at any bar |
| `max_zones_alive` | Peak simultaneous active zones per TF per side |
| `replacement_survival` | % of zones that survive N same-side replacements (N=1,2,3+) |
| `zone_clustering` | When multiple zones exist on same TF/side, average distance between them (ATR units) |
| `d_w_intraday_correlation` | Correlation between D/W zone creation events and intraday zone creation rate |

**Also outputs:** Per-zone lifecycle records (CSV) — one row per zone with: creation time, TF, side, role, birth context, test count, break time (or "alive"), lifespan in bars.

### Flask Visualization

- Zone population timeline chart per TF (line chart: active zone count over time)
- Overlaid on price chart
- Clickable zones → full lifecycle detail (see Flask section below)

---

## Level 2: Bias State Timeline

Continuous structural state tracker. Answers: "What is the market's structural context at every bar?"

### Module: `src/iora/diagnostics/bias_timeline.py`

**Input:** Zone engine output, period tracker history.

### Bias Computation (precise definition)

**Daily bias** is derived from the period tracker's rolling history of daily period highs and lows (3-deep history from `PeriodTracker.prev_highs` / `prev_lows`):

The label encodes the (high pattern, low pattern) pair from the last two period highs and lows. Computed from `PeriodTracker.prev_highs[0]` vs `prev_highs[1]` and `prev_lows[0]` vs `prev_lows[1]`:

| High Pattern | Low Pattern | Bias | Label |
|-------|------|------|-------|
| Higher high (HH) | Higher low (HL) | Bullish push — structure making new highs with rising floors | `HH_HL_bull_push` |
| Lower high (LH) | Higher low (HL) | Compression — lower highs but higher lows, range squeezing | `LH_HL_compression` |
| Lower high (LH) | Lower low (LL) | Bearish push — structure making new lows with falling ceilings | `LH_LL_bear_push` |
| Higher high (HH) | Lower low (LL) | Expansion — range widening, outside bar pattern, no clear bias | `HH_LL_expansion` |

**3-deep trend strength:** Using the 3-period history:
- 3 consecutive lower highs = strong bearish structure
- Last high lower but previous two higher = possible transition
- Mixed = range/consolidation

**Daily-to-Weekly relationship:**
- Nearest active W supply zone above price, nearest W demand below
- If daily is pushing TOWARD a W zone = pullback within weekly structure
- If daily is pushing AWAY from a W zone = continuation of weekly move
- Computed from price position relative to W zone boundaries

**H4/H1 bias within daily context:**
- Same period-tracker logic applied to H4/H1 periods
- Classified as: pushing WITH daily bias, pushing AGAINST (pullback), or neutral

### Per-Bar State Record

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `Timestamp` | Bar time |
| `d_bias` | `str` | Daily bias label |
| `d_bias_strength` | `int` | 1-3 based on period history consistency |
| `d_to_w_relationship` | `str` | `"continuation"`, `"pullback"`, `"inside_zone"`, `"neutral"` |
| `h4_bias` | `str` | H4 bias label |
| `h4_vs_daily` | `str` | `"with"`, `"against"`, `"neutral"` |
| `h1_bias` | `str` | H1 bias label |
| `h1_vs_daily` | `str` | `"with"`, `"against"`, `"neutral"` |
| `nearest_w_supply_dist` | `float` | Distance to nearest W supply (ATR units, negative if inside) |
| `nearest_w_demand_dist` | `float` | Distance to nearest W demand (ATR units, negative if inside) |
| `nearest_d_supply_dist` | `float` | Distance to nearest D supply (ATR units) |
| `nearest_d_demand_dist` | `float` | Distance to nearest D demand (ATR units) |
| `is_bias_transition` | `bool` | True if bias flipped on this bar |
| `transition_from` | `str` | Previous bias (only set on transition bars) |
| `transition_to` | `str` | New bias (only set on transition bars) |

### Flask Visualization

- Bias state ribbon below price chart (color-coded strip showing D/H4/H1 bias over time)
- Transition moments highlighted with vertical markers
- Active W/D zone distance indicators

---

## Level 3: Opportunity Counter

Count retest events before any win/loss logic. Answers: "How many valid opportunities exist?"

### Module: `src/iora/diagnostics/opportunity_counter.py`

**Input:** Zone engine output (with metadata), bias state timeline.

### Event Definitions

| Event | Definition |
|-------|------------|
| **Wick touch** | Bar's low enters demand zone (low <= zone.top) or bar's high enters supply zone (high >= zone.bottom), candle closes outside zone |
| **Body close** | Candle closes inside zone boundaries |
| **Near-miss** | Price came within threshold of zone but didn't touch. Threshold defined in ATR-relative terms: `0.25 * zone_thickness` or `0.5 * ATR` (whichever is smaller). Works across all 38 symbols without per-asset tuning. |
| **Break-through** | Price entered zone AND closed through it on the same bar (blew straight through). Track characteristics: zone age, bias alignment, TF relationship, replacement count, birth context. |

### Counting Dimensions

**TF pair notation:** `entry@context` means "retest of a context-TF zone, entered on the entry-TF bar." This is independent of the nesting parent mapping in `push_zone_engine.py` (`_PARENT_TF`). Nesting determines zone classification (is this M5 zone inside an H1 zone?). TF pairs determine entry logic (when an H1 zone is retested, enter on M5 bars). These are separate concepts.

Events counted per combination of:

| Dimension | Values |
|-----------|--------|
| TF pair (entry@context) | M1@M5, M1@M15, M5@M15, M5@H1, M15@H1, M15@H4, H1@H4, H1@D |
| Touch type | wick_touch, body_close, near_miss, break_through |
| Bias alignment | with_daily, against_daily, at_transition, neutral |
| Zone role | push, continuation, pullback, reversal, any | Same derivation as Level 4 sweep dimension (see definition above) |
| Zone age bucket | fresh (0-10 bars), young (10-50), mature (50-200), old (200+) | Note: bar counts are on the zone's own TF. A "fresh" D1 zone (0-10 D1 bars = 0-10 days) is intentionally different from a "fresh" M1 zone (0-10 minutes). Cross-TF comparison uses the zone's TF label as context — the age bucket is always relative to the zone's native timeframe. |
| Zone test count | first_touch, retested_1, retested_2plus |

### Output

**Opportunity matrix** (DataFrame): One row per dimension combination, columns: `count`, `avg_zone_age`, `avg_bias_strength`, `avg_price_distance_at_touch`.

**Summary per TF pair:**
```
M5@H1 GBPUSD (21 months):
  Wick touches:    847
  Body closes:     312
  Near-misses:     1,203
  Break-throughs:  289
  With daily bias: 512  Against: 335  Transition: 89
```

This tells us the opportunity universe. If a TF pair + filter has 500+ events, there's enough data for the strategy sweep. If it has 30, the combination is too tight.

### Flask Visualization

- Opportunity density heatmap per TF pair over time
- Near-miss vs touch vs break-through ratio visualization

---

## Level 4: Strategy Sweep

Built on top of Levels 1-3. Only implemented after Level 1-3 results are analyzed and the opportunity landscape is understood.

### Sweep Dimensions

| Dimension | Values | Notes |
|-----------|--------|-------|
| TF pair | M1@M5, M1@M15, M5@M15, M5@H1, M15@H1, M15@H4, H1@H4, H1@D | Entry TF @ context TF |
| Retest type | wick_touch, body_close | What counts as entry trigger |
| Zone role | push, continuation, pullback, reversal, any | Zone role for entry. **Push** = zone where `is_push=True` (HA transition initiated structural move). **Reversal** = `is_reversal=True` (zone created against prior structure). **Continuation** = zone with same-direction `swing_cls` as previous zone on same TF (e.g., HH after HH, LL after LL — extending the move). **Pullback** = zone with counter-direction `swing_cls` (e.g., LH after HH, HL after LL). Continuation/pullback are derived from `swing_cls` sequence, not stored as fields — computed at retest time by comparing the zone's `swing_cls` to the previous same-side zone on the same TF. |
| Touch policy | first_touch, until_broken | Zone consumed after first test, or valid until broken |
| Bias filter | with_trend, counter_allowed, any | Require alignment with daily bias |
| Cascade filter | none, require_htf_signal, require_confluence_2 | HTF signal must be active for LTF entry |
| Cascade direction | same, any | LTF entry must match HTF signal direction |
| SL mode | zone, atr, period | Existing SL computation |
| TP mode | zone, fixed_rr | Existing TP computation |
| Fixed R:R | 1.0, 1.5, 2.0, 3.0 | When tp_mode=fixed_rr |
| Direction | long, short, both | Trade direction filter |
| Session filter | any, london, newyork, london_ny_overlap, no_asian | Time-of-day filter. MT5 data uses UTC timestamps. Session definitions: **London** = 07:00-16:00 UTC, **New York** = 12:00-21:00 UTC, **London-NY overlap** = 12:00-16:00 UTC, **Asian** = 23:00-07:00 UTC, **no_asian** = exclude 23:00-07:00. Forex and metals use these defaults. Crypto uses `any` (24/7 market). Session definitions stored in a config dict, overridable per symbol class. |
| Zone age filter | any, fresh_only, young_only | Only enter on zones below age threshold |

### Cascade Logic

When `cascade_filter != none`:
- Check if an HTF signal is "active" — meaning an HTF zone retest event occurred recently (within N bars of the **entry TF**). N is a sweep dimension with values `[5, 10, 20, 50]` entry-TF bars. Example: if entry TF is M5 and N=20, the HTF signal must have fired within the last 20 M5 bars (100 minutes).
- `require_htf_signal`: at least one HTF TF pair has an active signal
- `require_confluence_2`: at least 2 HTF TF pairs have active signals
- `cascade_direction=same`: LTF entry direction must match the HTF signal direction
- The HTF TF pairs checked are all pairs with a context TF higher than the entry's context TF. E.g., for M5@M15 entry, HTF pairs are: M15@H1, M15@H4, H1@H4, H1@D.

Example: M5@M15 entry with cascade requiring M15@H4 signal active → only enter M5 when M15 recently retested an H4-context zone in the same direction.

### Filter Attribution Funnel (first-class output)

For every sweep config, report the filter pipeline:

```
Total retest events: 500
After direction filter: 480 (removed 20)
After bias filter: 320 (removed 160)
After zone role filter: 280 (removed 40)
After cascade filter: 195 (removed 85)
After session filter: 170 (removed 25)
After first-touch filter: 140 (removed 30)
→ 140 entries → 82 wins, 58 losses
→ WR: 58.6%, Expectancy: 0.42R, SQN: 3.2
```

Each filter's marginal contribution visible: opportunities removed AND win-rate change. Shows which filters add edge vs just reduce count.

### Existing Metrics Preserved

All metrics from the current `compute_metrics()`: SQN, Sharpe, Sortino, Calmar, profit factor, expectancy (pips + R), max drawdown (pips + R), streaks, holding periods, breakdowns by direction/signal_type/struct_cls/zone_tf/exit_reason.

---

## Flask Visualization (across all levels)

### Zone Lifecycle Inspector

Click any zone on the chart → modal/panel showing:
- Creation time, TF, side, role
- Birth context: daily bias, weekly relationship, period pattern, price distance
- Every retest event (time, touch type, outcome if strategy was active)
- Every near-miss (time, distance)
- Replacement history (survived N replacements, eventually replaced by zone X)
- How it died (body-close break at time T, or still alive)

### Bias State Ribbon

Below price chart: color-coded horizontal strip showing D/H4/H1 bias over time. Transition moments marked with vertical lines. Hoverable for detail.

### Opportunity Heatmap

Grid showing retest density per TF pair per time bucket. Color intensity = opportunity count. Immediately shows where the data is rich vs sparse.

### Calendar Heatmap

Trade density and PnL by day-of-week x hour-of-day. Instantly shows session-dependent edge. Color = net PnL, size = trade count. Critical for finding whether edge is London-only, NY-only, etc.

### Filter Funnel Visualization

Sankey-style diagram showing how each filter reduces the opportunity set. Interactive: click a filter stage to see which trades were removed and their characteristics.

---

## Data Handling

- Use full data range available per TF
- M1 has less history than M5 — when running M1@M5 pairs, use M1's date range
- When running M5@H1 pairs, use M5's full date range
- All 38 symbols available in `data/raw/{SYMBOL}/{YEAR}/` parquet format
- ATR computation: ATR(14) per TF for cross-symbol normalization (zone distance, near-miss threshold, birth_price_distance)

### Timeline Architecture

The existing `ZoneTimeline` / `ZoneTimelineBar` architecture snapshots zone state per bar by reference (shallow copies). Since the retest engine needs to mutate `test_count` on `PushZone` objects, and those objects are shared across timeline bars, the retest strategy layer must NOT use the existing `ZoneTimelineBar.zones_by_tf` for zone mutation.

Instead, the retest engine operates directly on the zone engine state (the `PushZoneTickState` per-TF zone lists), running alongside the zone engine in the per-bar loop. The `test_count` and `first_test_bar` fields on `PushZone` are updated in-place during the orchestrator's per-bar loop (before the zones are snapshotted into the timeline). This means retest detection is part of the engine loop, not a post-hoc replay.

The Level 4 strategy sweep replays the timeline for SL/TP and filter evaluation (cheap), but retest events are already recorded during the engine run (expensive, run once per symbol).

### Near-Miss Threshold

Near-miss threshold: `max(min(0.25 * zone_thickness, 0.5 * ATR(14)), 1.0 * pip_size)`. The floor of 1 pip prevents sub-pip thresholds on very thin zones (common on M1).

### Warm-Up Period

The first N bars per TF have sparse zone state and incomplete period history. Skip the first `3 * period_length` bars per TF for diagnostic counting and opportunity measurement (e.g., 3 daily periods = ~3 days of D1 bars, ~3 weeks of H4 bars). This avoids startup artifacts in Level 1-3 statistics. The warm-up period is logged but not configurable — it's a data quality guard.

---

## File Structure

```
src/iora/
  engine/
    push_zone_models.py          # Enhanced PushZone with new metadata fields
    push_zone_tick.py             # Remove age-based expiry
  diagnostics/                    # NEW — Levels 1-3
    zone_audit.py                 # Level 1: zone population analysis
    bias_timeline.py              # Level 2: structural state tracker
    opportunity_counter.py        # Level 3: retest event counting
  strategy/
    retest_engine.py              # NEW — Level 4: retest detection + entry logic
    retest_sweep.py               # NEW — Level 4: sweep runner for retest entries
    retest_config.py              # NEW — Level 4: sweep config with all dimensions
    filter_funnel.py              # NEW — Level 4: filter attribution report
    # Existing files preserved (push_zone_strategy.py etc.)

apps/
  backtest_serializers.py         # Extended for new visualizations
  chart_viewer_lw.py              # Extended with diagnostic endpoints

scripts/
  run_zone_audit.py               # CLI for Level 1
  run_bias_timeline.py            # CLI for Level 2
  run_opportunity_count.py        # CLI for Level 3
  run_retest_sweep.py             # CLI for Level 4

tests/
  diagnostics/                    # NEW
    test_zone_audit.py
    test_bias_timeline.py
    test_opportunity_counter.py
  strategy/
    test_retest_engine.py         # NEW
    test_retest_sweep.py          # NEW
    test_retest_config.py         # NEW
    test_filter_funnel.py         # NEW
```

---

## Build Order

**Phase 1: Level 0 + Level 1** — Zone lifecycle change + zone activity audit. Run across all 38 symbols. Analyze results: how many zones exist, retest patterns, untouched zones, clustering.

**Phase 2: Level 2** — Bias state timeline. Run across all symbols. Analyze: bias transition frequency, D-to-W relationships, bias duration. Flask visualization to validate structural logic on real charts.

**Phase 3: Level 3** — Opportunity counter. Count retests per TF pair per filter combination. Analyze: which TF pairs have enough opportunities (500+), which are too sparse. Near-miss analysis to check zone boundary quality.

**ANALYSIS GATE:** Review Level 1-3 results before proceeding. Insights from Levels 1-3 may change which sweep dimensions matter for Level 4. For example:
- If D zones get retested 8 times on average → first-touch-only may not be the right default
- If near-misses outnumber touches 10:1 → zone boundaries need loosening or retest definition needs adjustment
- If bias transitions are rare → bias transition filter won't produce enough opportunities

**Phase 4: Level 4** — Retest strategy sweep. Build entry engine, cascade logic, filter funnel. Run sweep across validated TF pairs and dimension combinations.

**Phase 5: Flask visualization** — Zone lifecycle inspector, bias ribbon, opportunity heatmap, calendar heatmap, filter funnel visualization.

---

## Success Criteria

1. Level 1 audit runs across all 38 symbols and produces zone population statistics
2. Level 2 bias timeline produces continuous structural state for all symbols
3. Level 3 opportunity counter identifies TF pairs with 500+ retest events
4. Level 4 sweep produces filter attribution funnels showing marginal contribution of each filter
5. At least one TF pair + filter combination produces: 200+ trades, positive expectancy, SQN > 2.0
6. Flask app shows zone lifecycle, bias ribbon, and opportunity heatmap for any symbol
