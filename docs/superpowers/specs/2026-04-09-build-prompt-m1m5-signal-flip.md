# BUILD PROMPT — M1-M5 Mechanical Signal-Flip System

> **For:** Fresh Claude Code chat session
> **Goal:** Build and test the M1-M5 signal-flip entry/exit system, run sweeps, produce production-ready configs
> **Priority:** Get Layer 1 (signal-flip engine) working and tested on GBPUSD first. Then refine with cascade filters. Then sweep all 8 symbols.

---

## READ THESE FILES FIRST (in order)

1. `CLAUDE.md` — Project rules, structure, Python/Pine conventions
2. `docs/superpowers/specs/2026-04-09-m1m5-mechanical-signal-flip-spec.md` — Full system architecture, structural concepts, 5 implementation layers
3. `docs/system/mechanical-ruleset-validated.md` — Proven mechanical rules (Rules 1-13)
4. `docs/system/mechanical-cascade-strategy.md` — Cascade strategy with phase definitions
5. `docs/system/sweep-analysis-sop.md` — How to analyze sweep results (17 metrics, 8 steps)
6. `docs/system/cascade-complete-sweep-analysis.md` — Prior H1@H4 findings to build on

---

## CONTEXT: What Happened Before This Chat

### The Problem
M1@M5 with fixed SL/TP produces **30-32% WR, PF 0.85-0.92** — consistently negative on GBPUSD and EURUSD across ALL cascade filter combinations. Meanwhile H1@H4 works great (PF 2.97-5.40, WR 50-60%).

**Root cause:** At M5 zone resolution, zone width = 1-3 pips. GBPUSD spread = 1.0-1.5 pips. The SL is smaller than or equal to the spread. Fixed SL/TP is structurally broken at this resolution.

### The Solution: Signal-Flip Exits
Instead of fixed SL/TP, exit when an **opposite-direction zone fires** on the entry TF:
- Short entry at M1 supply signal → exit when M1 demand signal fires
- That M1 demand signal = simultaneously the new long entry
- Trade is always open, flipping direction on each M1 HA transition
- Spread paid once per flip, not measured against a tiny zone SL
- Exit distance is structural (variable), not fixed

### What's Already Built
| Component | File | Status |
|---|---|---|
| HA zone detection (M1-MN) | `src/iora/engine/ha_pivots.py` + `push_zone_tick.py` | DONE |
| Push zone management | `src/iora/orchestrator/push_zone_engine.py` | DONE |
| Period Hi/Lo tracking | `PeriodTracker` in engine | DONE |
| Trendline state machine | `src/iora/engine/push_trendline.py` | DONE |
| Multi-TF pipeline | `src/iora/orchestrator/pipeline.py` | DONE |
| Retest candidate detection | `src/iora/strategy/retest_engine.py` | DONE |
| SL/TP simulation loop | `src/iora/strategy/retest_engine.py:_simulate_with_bars()` | DONE — needs signal-flip mode |
| Cascade filters | `src/iora/strategy/retest_config.py` | DONE |
| Sweep runner + metrics | `scripts/run_cascade_sweep.py` + `src/iora/strategy/sweep_runner.py` | DONE (17 metrics) |
| Diagnostics (Levels 1-3) | `src/iora/diagnostics/` | DONE |

### What's Missing (Build These)
| Component | Priority | Description |
|---|---|---|
| **Signal-flip exit mode** | P0 — CRITICAL | New exit mode in simulation loop: exit on opposite zone fire, not SL/TP |
| **Zone classification** | P1 | Order block vs breaker vs mitigation block detection |
| **Internal/external BOS split** | P2 | M15 pivots = internal structure, H4+ = external |
| **Structural FVG in Python** | P2 | Gap between HTF pivot and first LTF swing that fell short |
| **Pivot HL classification** | P2 | Port from `joma_pivots_trendlines.pine` |

### Reference Pine Indicators (4 files)
These show what the system looks like visually. The Python engine must replicate the same logic:
- `tw_indicators/JoMa_Indicators/joma_zones_levels.pine` — M1-H4 zones + period Hi/Lo levels
- `tw_indicators/JoMa_Indicators/joma_pivots_trendlines.pine` — Multi-TF pivots + trendlines + divergence
- `tw_indicators/iora_joma/iora_joma_zones.pine` — Extended zones (M1-MN) + structural FVG detection
- `tw_indicators/iora_joma/iora_joma_pivots.pine` — Extended pivots for M1 chart execution

---

## LAYER 1: Signal-Flip Engine (DO THIS FIRST)

### 1.1 Add `exit_mode` to RetestConfig

In `src/iora/strategy/retest_config.py`, add:

```python
# Exit mode
exit_mode: str = "fixed_sl_tp"         # "fixed_sl_tp" = current SL/TP system (default)
                                        # "signal_flip" = exit on opposite zone fire
                                        # "signal_flip_with_safety" = signal_flip + emergency SL at zone boundary
```

### 1.2 Modify `_simulate_with_bars()` in `retest_engine.py`

The current exit loop (lines ~418-451) checks `bar_low <= ot.sl` and `bar_high >= ot.tp`. For signal-flip mode, replace SL/TP checks with **opposite zone fire detection**.

**What signal-flip needs:**
1. Access to the **zone birth events** per bar (already passed as `zone_births` parameter)
2. For each bar, check if a **new zone fired on the entry TF in the opposite direction** to the open trade
3. If yes: close the current trade at the new zone's entry edge price, and open a new trade in the opposite direction

**Pseudocode for signal-flip exit:**
```python
if config.exit_mode in ("signal_flip", "signal_flip_with_safety"):
    for ot in open_trades:
        # Check zone_births at this timestamp for opposite-direction zones
        births_at_bar = zone_births.get(ts, [])
        entry_tf = config.entry_tf  # e.g., "M1"
        
        for birth in births_at_bar:
            if birth.tf != entry_tf:
                continue
            
            opposite = (ot.candidate.direction == "long" and birth.is_supply) or \
                       (ot.candidate.direction == "short" and not birth.is_supply)
            
            if opposite:
                # Close current trade at the new zone's edge
                exit_price = birth.zone_bottom if birth.is_supply else birth.zone_top
                trades.append(ot.close_at(exit_price, ts, "signal_flip"))
                
                # Open new trade in opposite direction
                new_direction = "short" if birth.is_supply else "long"
                # ... create new _OpenTrade with the flipped direction
                break
    
    # Safety SL (only for signal_flip_with_safety)
    if config.exit_mode == "signal_flip_with_safety":
        for ot in open_trades:
            # Emergency exit if zone boundary violated
            # Long: bar_low < zone_bottom of entry zone
            # Short: bar_high > zone_top of entry zone
            ...
```

**Key details:**
- The new trade from a flip should use the **opposite zone's edge** as entry price
- The flip trade's SL (for safety mode) = the opposite zone's far boundary
- Track `flip_count` per trade chain for diagnostics
- A trade that never receives an opposite signal and runs to end-of-data = "open_at_close" exit reason

### 1.3 Zone Birth Events

The `zone_births` dict is already passed to `_simulate_with_bars()`. Check how it's populated:
- Look at `src/iora/strategy/retest_engine.py` for `ZoneBirthEvent` 
- Look at the pipeline for how zone fires are collected per bar
- Each `ZoneBirthEvent` should have: `tf`, `is_supply`, `zone_top`, `zone_bottom`, `timestamp`

If `zone_births` doesn't contain the entry TF's births (e.g., M1 births when running M1@M5), you need to ensure the pipeline collects zone fire events for ALL TFs in the pair, not just the zone TF.

### 1.4 New Metrics for Signal-Flip

Add to `compute_metrics()` in `src/iora/strategy/sweep_runner.py`:
```python
"flip_count": total number of signal-flip exits
"avg_flip_pips": average pips per flip (absolute value)
"avg_flip_duration_mins": average minutes between flips
"net_after_spread": total_pips - (flip_count * spread_pips * 2)
```

### 1.5 Test on GBPUSD M1@M5

Run signal-flip on GBPUSD with these configs:

```python
# Config 1: Raw signal-flip (no cascade filters)
RetestConfig(
    tf_pair="M1@M5",
    exit_mode="signal_flip",
    spread_pips=1.5,  # GBPUSD typical
    entry_mode="market",
    direction="both",
)

# Config 2: Signal-flip with safety SL
RetestConfig(
    tf_pair="M1@M5",
    exit_mode="signal_flip_with_safety",
    spread_pips=1.5,
    entry_mode="market",
    direction="both",
)

# Config 3: Signal-flip with h4_correction filter
RetestConfig(
    tf_pair="M1@M5",
    exit_mode="signal_flip",
    spread_pips=1.5,
    cascade_phase_filter="h4_correction",
    entry_mode="market",
    direction="both",
)
```

**Success criteria for Layer 1:**
- Signal-flip WR > 45% (up from 30-32% with fixed SL)
- Signal-flip PF > 1.3
- avg_flip_pips > 2x spread (each flip captures enough to pay the cost)
- flip_count reasonable (5-20/day, not 100+)

If these criteria are met, proceed to Layer 2. If not, investigate:
- Are M1 zones firing too frequently? (noise)
- Should we use M5 zone flips instead of M1?
- Does adding M15 context (only flip when M15 agrees) help?

---

## LAYER 2: Zone Classification (After Layer 1 Works)

Detect zone type based on lifecycle:

```python
@dataclass(slots=True)
class ZoneClassification:
    zone_type: str  # "order_block", "breaker", "mitigation"
    # Order block: first-touch zone, origin of impulsive move
    # Breaker: zone was broken through, now retested from opposite side (polarity flip)
    # Mitigation: failure swing zone — LH/HL where the extreme holds (not broken)
```

**Detection logic (from structural concept images):**
- **Order block:** Zone has never been touched/tested. It's the origin candle of an impulsive move. In our system = a push zone with `retest_count == 0`.
- **Breaker block:** A zone that was previously supply (or demand), got broken through (body-close), and is now being retested from the other side. The zone that was resistance becomes support (or vice versa). Detection: track broken zones, and when price returns to the broken zone's price range from the opposite direction = breaker.
- **Mitigation block:** A zone at a LH (or HL) where the prior extreme (HH or LL) was NOT broken. The LH zone acts as resistance on retest. Detection: zone is at a pivot that failed to make a new extreme.

### Sweep dimension:
Add `zone_type_filter: str = "any"  # "any", "order_block", "breaker", "mitigation"` to RetestConfig.

---

## LAYER 2.5: Structural Sequence Filters (HIGH PRIORITY — From Live Chart Analysis)

**This is the KEY insight from live XAUUSD M5 chart observation.** The highest-quality entries happen in a specific structural sequence:
1. HTF level gets broken (DY Lo X, H4 Lo established) → liquidity sweep done
2. H1 demand zone forms (H1 D LL) → institutional demand absorbs selling
3. M15 descending trendline breaks → internal correction structure shifts bullish
4. M15 starts making HL sequence → internal trend is now bullish
5. Every M15 D HL zone above the H1 demand = mechanical long entry

### 4 new filter dimensions needed in RetestConfig:

```python
# 1. HTF Level Break Context — was a structural level swept before this zone?
htf_level_break_context: str = "any"
# "after_dy_lo_x", "after_dy_hi_x", "after_h4_lo_x", "after_h4_hi_x",
# "after_h1_lo_x", "after_h1_hi_x", "any"
# Implementation: PeriodTracker already has hi_brk_t/lo_brk_t — check if break
# occurred within lookback window before zone creation

# 2. Zone Spatial Context — zone positioning relative to HTF zones
zone_spatial_context: str = "any"
# "m15_hl_above_htf_demand"    = M15 D HL sitting above unbroken H1/H4 demand
# "m15_lh_below_htf_supply"    = M15 S LH sitting below unbroken H1/H4 supply
# "first_htf_zone_after_break" = First H1/H4 zone after HTF level break
# "any"
# Implementation: compare entry zone position against live HTF zone array

# 3. M15 Trendline State at Entry
m15_tl_state: str = "any"
# "after_correction_break" = M15 correction TL just broke (correction over)
# "impulse_intact"         = M15 impulse TL still holding
# "any"
# Implementation: push_trendline.py break events on M15

# 4. Divergence Confirmation
m15_divergence: str = "any"
# "with_div"  = M15 divergence fired at nearby pivot (DIV+ for longs, DIV- for shorts)
# "no_div"    = no divergence
# "any"
# Implementation: pivot vs trendline slope comparison (from joma_pivots_trendlines.pine)
```

### The mechanical entry rule:
```
LONG: HTF Lo X occurred → H1 D zone formed → M15 correction TL broke → M15 in HL mode
      → Enter at every M15 D HL zone (M1/M5 signal-flip inside)

SHORT: HTF Hi X occurred → H1 S zone formed → M15 correction TL broke → M15 in LH mode
       → Enter at every M15 S LH zone (M1/M5 signal-flip inside)
```

### Sweep configs for structural sequence:
```python
STRUCTURAL_CONFIGS = [
    # Full rule (all conditions)
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5",
     "htf_level_break_context": "after_h4_lo_x",
     "m15_tl_state": "after_correction_break",
     "zone_spatial_context": "m15_hl_above_htf_demand"},

    # Each dimension isolated (measure individual contribution)
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5",
     "htf_level_break_context": "after_h4_lo_x"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5",
     "m15_tl_state": "after_correction_break"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5",
     "zone_spatial_context": "m15_hl_above_htf_demand"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5",
     "m15_divergence": "with_div"},
]
```

---

## LAYER 3: M15-Resolution Cascade Filters (After Layer 2)

Port the proven H1@H4 cascade dimensions down to M15:
- `m15_correction` phase — M15 correction TL intact while H1 makes new swing
- Period level proximity — M5 entry near H1 Hi/Lo or H4 Hi/Lo
- M15 trendline break — correction or impulse TL just broke on M15

These are the same filters that produced PF 3.1-5.4 at H1@H4. Testing whether they translate to M1@M5 resolution.

---

## SWEEP RUNNER: How to Run Everything

### Existing sweep infrastructure:
```bash
# Single symbol, H1@H4 only (30 min):
python scripts/run_cascade_sweep.py --symbols GBPUSD --h1h4-only --output results/sweeps/cascade_v3/

# All 8 symbols (run overnight, ~4 hours):
python scripts/run_cascade_sweep.py --output results/sweeps/cascade_v3/
```

### New M1@M5 signal-flip sweep:
You'll need to either extend `run_cascade_sweep.py` to support signal-flip configs, or create a new runner `scripts/run_signal_flip_sweep.py`.

The sweep should test these dimensions:
```python
SIGNAL_FLIP_CONFIGS = [
    # Exit mode comparison
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5"},
    {"exit_mode": "signal_flip_with_safety", "tf_pair": "M1@M5"},
    {"exit_mode": "fixed_sl_tp", "tf_pair": "M1@M5"},  # baseline comparison
    
    # Entry TF variation (which zone flip triggers the entry?)
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5"},   # M1 entry inside M5 zone
    {"exit_mode": "signal_flip", "tf_pair": "M5@M15"},  # M5 entry inside M15 zone
    {"exit_mode": "signal_flip", "tf_pair": "M1@M15"},  # M1 entry inside M15 zone
    
    # Cascade filter overlay (from H1@H4 proven findings)
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "cascade_phase_filter": "h4_correction"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "bias_filter": "against_daily"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "tl_break_filter": "after_correction_break"},
    
    # Zone type filter (after Layer 2)
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "zone_type_filter": "order_block"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "zone_type_filter": "breaker"},
    {"exit_mode": "signal_flip", "tf_pair": "M1@M5", "zone_type_filter": "mitigation"},
]
```

### Analysis SOP (apply to every sweep result):

Follow `docs/system/sweep-analysis-sop.md`:
1. Data quality check (viable configs, zero-trade configs, metric column check)
2. Baseline establishment (unfiltered config)
3. Dimension-by-dimension comparison (vary one filter, hold others at baseline)
4. Cross-symbol consistency (same direction on 5+ of 8 symbols = universal)
5. Combination testing (stack top 2-3 proven filters)
6. Risk assessment (maxDD, max loss streak, calmar)
7. Structural analysis (zone counts, TL breaks, period level proximity)
8. Documentation (write findings to `docs/system/`)

### All 17 metrics to capture per config:
```
total_trades, win_rate, avg_r, total_r, profit_factor, expectancy_r,
sqn, sharpe, sortino, calmar,
max_dd_r, avg_win_r, avg_loss_r, largest_win_r, largest_loss_r,
max_win_streak, max_loss_streak, avg_hold_hours, avg_sl_pips
```
Plus signal-flip specific: `flip_count, avg_flip_pips, avg_flip_duration_mins, net_after_spread`

---

## H1@H4 CONTEXT (For Reference, Not The Focus)

H1@H4 is NOT the production trading system — it provides **context and targets** for M1-M5.

### Proven H1@H4 findings (from cascade-complete-sweep-analysis.md):
- **h4_correction** = best cascade phase (PF 3.1-4.1, universal on GBPUSD + EURUSD)
- **against_daily** = strong on GBPUSD (PF 5.40), neutral on EURUSD (symbol-specific)
- Correction TL break slightly outperforms impulse TL break
- CHoCH conviction, momentum consumption, TL break lookback = NO effect at H1 resolution
- Candle FVG at entry = slightly negative
- Breaker zone filter = no effect

### H1@H4 metric bug (FIXED):
Runner now captures all 17 metrics correctly. Previous CSVs have zeros for max_dd_r, avg_win_r, avg_loss_r — need re-run if those metrics are needed. The fix is in `scripts/run_cascade_sweep.py` lines 243-267.

---

## DATA AVAILABLE

38 symbols in `data/raw/` as parquet files. Primary test symbols:
- **GBPUSD** — primary test pair (16.5 years, M1 bars)
- **EURUSD** — secondary validation
- **USDJPY, GBPJPY, XAUUSD, BTCUSD, US500, USTEC** — cross-symbol validation

Default spread assumptions:
- FX majors (GBPUSD, EURUSD, USDJPY): 1.0-1.5 pips
- FX crosses (GBPJPY): 2.0-3.0 pips
- XAUUSD: 2.0-3.0 pips
- Indices: 1.0-2.0 points
- BTCUSD: 5.0-15.0

---

## BUILD SEQUENCE

1. **Read the spec** (`2026-04-09-m1m5-mechanical-signal-flip-spec.md`)
2. **Implement Layer 1** — `exit_mode="signal_flip"` in RetestConfig + simulation loop modification
3. **Test Layer 1** — Run GBPUSD M1@M5 signal-flip, compare against fixed SL/TP baseline
4. **Analyze results** — Follow sweep-analysis-sop.md, print all 17+ metrics
5. **If Layer 1 passes:** Implement Layers 2-3 (zone classification, M15 cascade filters)
6. **Run full sweep** — All filter combinations on GBPUSD, then validate on 7 more symbols
7. **Document findings** — Write analysis to `docs/system/m1m5-signal-flip-analysis.md`
8. **Production configs** — The top 2-3 universal configs become the production system

**The test that matters:** Does signal-flip push M1@M5 WR from 30-32% above 45%? If yes, the exit mechanism was the problem and the entries are fine. If no, the M1-M5 zone model itself needs rework.

---

## EXISTING TEST SUITE

340+ tests in `tests/`. Run with:
```bash
pytest tests/ -x -q
```
Any new engine code must pass existing tests (no regressions) and add new tests for signal-flip logic.

---

## CRITICAL: Remove min_sl_spread_mult Floor for Clean Data

**Discovery (2026-04-09):** `min_sl_spread_mult=3.0` is hardcoded in `retest_sweep.py` (lines 936, 1039, 1117). This means:
- Minimum SL = max(0, spread × 3.0) = 4.5 pips for GBPUSD
- Any zone with natural SL < 4.5 pips gets artificially widened
- This **distorts R:R** (a 2-pip zone gets a 4.5-pip SL → inflated risk)
- This **distorts WR** (wider SL = fewer hits, but SL is no longer at structural level)
- This **hides the real edge** (we've never tested M1@M5 at natural zone width)

**M1@M5 diagnostic result:** avg_sl_pips = 6.00 pips (not 1.5 as expected). The 3x floor was propping up every SL to at least 4.5 pips. The 31.5% WR is an artificially *improved* number — the true WR with natural zone boundaries may be worse.

**Requirement:** In ALL signal-flip sweep configs AND the fixed_sl_tp baseline, set:
```python
min_sl_spread_mult = 0.0
min_sl_pips = 0.0
```

The zone boundary IS the structural invalidation level. If a 1.5-pip zone can't hold, that's real information, not something to mask.

### Required 3-Way Comparison Sweep

Run these 3 configs on GBPUSD M1@M5 to isolate the floor's effect:

| # | Config | Purpose |
|---|--------|---------|
| 1 | `exit_mode="fixed_sl_tp"`, `min_sl_spread_mult=0.0` | True M1@M5 baseline (raw zone SL) |
| 2 | `exit_mode="fixed_sl_tp"`, `min_sl_spread_mult=3.0` | The 31.5% WR we already have (floor-propped) |
| 3 | `exit_mode="signal_flip"`, `min_sl_spread_mult=0.0` | The new paradigm |

The gap between #1 and #2 = how much the floor distorted results.
The gap between #1 and #3 = how much signal-flip actually helps.

---

## IMPORTANT NOTES

- **Spread MUST be modeled** — all M1@M5 configs must use `spread_pips=1.5` (GBPUSD). Results without spread are meaningless at this resolution.
- **Don't over-filter** — if a filter reduces trade count below 30, the results are statistically insignificant.
- **Cross-symbol consistency is required** — a filter that helps GBPUSD but hurts EURUSD is symbol-specific, not universal. Only universal filters go into production.
- **The H1@H4 system is context, not the trade** — H1@H4 tells us the bias direction and structural targets. M1@M5 does the actual entries and exits.
- **Every exit = next entry** — the signal-flip model means the position is always open, just flipping direction. This is fundamental — don't add logic that "skips" flips.
- **No SL floor** — `min_sl_spread_mult=0.0` and `min_sl_pips=0.0` for ALL configs. The zone speaks for itself.
