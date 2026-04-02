# Iora Push Zone Strategy — Design Spec

**Date:** 2026-04-02
**Platform:** Python + Flask (TradingView Lightweight Charts)
**Pine Reference:** `tw_indicators/iora_zones/iora_push_zones_v2.pine` + `tw_indicators/gold_system/iora_bos_choch.pine`
**Approach:** Hybrid — new push zone engine plugged into existing pipeline infrastructure

---

## Overview

A Python signal matrix backtester built on push zone detection ported from `iora_push_zones_v2.pine`. Detects HA-based supply/demand zones across 8 timeframes, classifies them as push/reversal/terminal with BOS/CHoCH structure, then evaluates configurable entry/exit strategies against the zone timeline. Supports batch sweeping across nesting combos, SL/TP modes, and all 38 symbols.

The same zone engine serves backtesting, Flask visualization, and eventually live trading — one code path, three consumers.

---

## Architecture

```
Data loading (ParquetStorage — exists)
  → Multi-TF alignment (tf_alignment.py — exists, extended with HA columns)
  → Pipeline bar-by-bar loop (pipeline.py — exists, extended)
      ├── push_zone_engine.py  (NEW — ports push_zones_v2 logic)
      │   ├── HA computation (heikin_ashi.py — exists, reused)
      │   ├── Run transition detection + zone creation
      │   ├── Push validation (boundary-break rule)
      │   ├── Reversal tagging
      │   ├── Period tracking + trend state (ports iora_bos_choch)
      │   ├── Nesting detection + terminal classification
      │   └── Zone counting with dual reset triggers
      ├── structure_engine.py  (exists — optional context: trendlines, wave state)
      └── push_zone_strategy.py (NEW — entry/exit rules)
          ↓
      Backtester (exists) → Flask viewer (exists, extended)
```

---

## Push Zone Engine

### PushZone Model

```python
@dataclass
class PushZone:
    top: float
    bottom: float
    is_supply: bool
    origin_time: pd.Timestamp
    timeframe: str = ""
    is_push: bool = False
    is_reversal: bool = False
    is_terminal: bool = False
    struct_cls: str = ""          # "BOS" or "CHoCH"
    swing_cls: str = ""           # "HH", "LH", "HL", "LL"
    count_num: int = 0
```

### Per-TF State

```python
@dataclass
class PushZoneTickState:
    # HA run tracking
    prev_ha_open: float = nan
    prev_ha_close: float = nan
    is_blue_prev: bool = False
    prev_run_hi: float = nan         # previous same-direction run extreme
    prev_run_lo: float = nan

    # Push validation state
    prev_push_extreme_hi: float = nan  # last confirmed bullish push HH
    prev_push_extreme_lo: float = nan  # last confirmed bearish push LL

    # Trend (from period tracking)
    trend: int = 0                   # +1 bull, -1 bear, 0 uninitialized

    # Period tracker
    period: PeriodTracker = field(default_factory=PeriodTracker)

    # Zone arrays
    supply_zones: list[PushZone] = field(default_factory=list)
    demand_zones: list[PushZone] = field(default_factory=list)

    # Zone counting
    sup_count: int = 0
    dem_count: int = 0
    sup_reset_time: pd.Timestamp | None = None
    dem_reset_time: pd.Timestamp | None = None
```

### HA Detection — Run Transition Logic

Ports `ha_detect()` from Pine. Runs per-TF on resampled bars:

1. Compute HA candles: `ha_close = (O+H+L+C)/4`, `ha_open = (prev_ha_open + prev_ha_close)/2`
2. Determine color: `is_blue = ha_close >= ha_open`
3. Detect transition: blue→red = supply fire, red→blue = demand fire
4. On fire, walk back through completed run to find OHLC extreme:
   - Supply: `run_hi_ohlc` = highest OHLC high during the blue run
   - Demand: `run_lo_ohlc` = lowest OHLC low during the red run
5. Classify: compare run extreme to previous same-side run
   - `run_hi_ohlc > prev_run_hi` → HH, else LH
   - `run_lo_ohlc < prev_run_lo` → LL, else HL

**Zone boundaries (ORIZ spec):**
- Supply: `top = run_hi_ohlc` (structural extreme), `bottom = ha_low` (order-block edge)
- Demand: `top = ha_high` (order-block edge), `bottom = run_lo_ohlc` (structural extreme)

**Doji handling:** If current bar is a doji (body/range < doji_pct%), use current bar's HA extreme instead of previous bar's.

### Per-Bar Tick Sequence

Same order as Pine `process()`:

1. **Count reset** — parent fires same-side zone OR same-TF HH/LL structural invalidation
2. **Zone expire + break** — age-based expiry (`max_age * tf_seconds`), body-close break detection
3. **Zone creation** — on fire with valid boundaries, increment count
4. **Push validation** — boundary-break rule:
   - Bearish: demand fires with LL, check `seq_ll < prev_push_extreme_lo` (or bootstrap if `nan`)
   - Bullish: supply fires with HH, check `seq_hh > prev_push_extreme_hi` (or bootstrap if `nan`)
   - If valid: tag most recent opposite-side zone as PUSH, tag trigger zone as REVERSAL
5. **BOS/CHoCH classification** — push direction vs current trend state:
   - Push matches trend → BOS (continuation)
   - Push opposes trend → CHoCH (reversal)
   - Trend uninitialized → no classification
6. **Nesting detection** — child zone inside parent zone (`child.top <= parent.top AND child.bottom >= parent.bottom`), opposing direction = terminal. The Pine indicator hardcodes a parent map: M1→M15, M5→H1, M15→H1, H1→H4, H4→D, D→W, W→MN (notably M5 skips M15). In Python, nesting is driven by `StrategyConfig.entry_tf` / `parent_tf` — the implementer should use the push zone engine's zone arrays directly rather than replicating the Pine parent map

### Break Standards (Three Levels)

- **Push validation:** wick or body exceedance (did price reach new extreme?)
- **Zone breaks:** body-close only (wicks = liquidity sweep, not structural break)
- **Period-level breaks:** wick-based (`high > prev_hi` / `low < prev_lo`)

---

## Period Tracking + Trend State

Ports `track_period()` from `iora_bos_choch.pine`. One `PeriodTracker` per TF.

### PeriodTracker

```python
@dataclass
class PeriodTracker:
    # Current period
    cur_hi: float = nan
    cur_lo: float = nan
    cur_hi_time: pd.Timestamp | None = None
    cur_lo_time: pd.Timestamp | None = None

    # Previous period levels — rolling window of 3
    prev_highs: list[float] = field(default_factory=list)   # [most_recent, one_back, two_back]
    prev_lows: list[float] = field(default_factory=list)
    prev_hi_times: list[pd.Timestamp] = field(default_factory=list)
    prev_lo_times: list[pd.Timestamp] = field(default_factory=list)

    # Break detection
    hi_brk_time: pd.Timestamp | None = None
    lo_brk_time: pd.Timestamp | None = None
```

### Per-Bar Logic

1. On new period (TF boundary): rotate current → prepend to prev lists (cap at 3), reset break times
2. Track current period high/low
3. Detect first break of most recent previous high/low (wick-based)
4. On break edge: update trend (+1 for high break, -1 for low break)

### 3-Level History

Stores last 3 period highs and lows per TF. V1 uses only the most recent for push classification and trend state. The extra history enables future analysis:
- Retest detection (price returns to previous period level)
- Break depth (how many period levels broken in current push)
- SL placement behind 2nd/3rd period level
- Understanding how M5 pushes build up M15/H1 levels

---

## Signal Matrix Strategy

### EntrySignal

Every potential entry captures the full system state:

```python
@dataclass
class EntrySignal:
    # Trigger
    zone: PushZone
    zone_tf: str                      # "M1", "M5", "M15", etc.
    signal_type: str                  # "push", "reversal", "terminal", "normal"
    struct_cls: str                   # "BOS", "CHoCH", ""
    direction: str                    # "long", "short"

    # Nesting context
    parent_zone: PushZone | None
    parent_tf: str
    nesting_depth: int
    opposing_nest: bool               # Terminal

    # Full dashboard state at entry time
    trend_by_tf: dict[str, int]       # {M5: +1, M15: +1, H1: -1, ...}
    period_levels: dict[str, dict]    # {H1: {highs: [...], lows: [...]}, ...}
    zone_counts: dict[str, tuple]     # {M5: (3, 2), ...} → (sup_count, dem_count)
    exhaustion: dict[str, bool]       # {M5_sup: True, H1_dem: False, ...}

    # Computed trade parameters
    sl_price: float
    tp_price: float
    risk_pips: float
    reward_pips: float
    entry_time: pd.Timestamp
    entry_price: float
```

### StrategyConfig — Sweep Dimensions

```python
@dataclass
class StrategyConfig:
    # Entry nesting
    entry_tf: str = "M5"              # Zone TF for entry
    parent_tf: str = "H1"             # Parent TF for nesting requirement
    require_nesting: bool = True      # Must be inside parent zone?

    # Signal filters
    signal_types: set[str] = field(default_factory=lambda: {"push", "reversal"})
    struct_filter: str = "any"        # "bos_only", "choch_only", "any"
    htf_trend_filter: str = "none"    # "with_trend", "counter_allowed", "none"
    htf_trend_tf: str = "H4"
    max_zone_count: int = 0           # Skip if zone count > N (0 = disabled)
    no_trade_zones: bool = True       # Skip if inside D/W opposing zone

    # SL/TP
    sl_mode: str = "zone"             # "zone", "structure", "fixed_pips", "atr"
    tp_mode: str = "zone"             # "zone", "structure", "fixed_rr", "atr"
    fixed_rr: float = 2.0
    sl_period_depth: int = 1          # Which period level for structure SL (1st/2nd/3rd)

    # Position management (v1: single only; partial/scale_in added later)
    position_mode: str = "single"

    # Direction
    direction: str = "both"           # "long", "short", "both"

    # Risk
    risk_per_trade_pct: float = 1.0   # % of equity
    max_concurrent: int = 1           # Max open positions per symbol
```

### Sweep Runner

```python
def run_sweep(
    symbol: str,
    data_by_tf: dict[str, pd.DataFrame],
    configs: list[StrategyConfig],
    base_tf: str = "M1",
) -> pd.DataFrame:
    """Run push zone engine once, evaluate multiple configs against same zones."""
    # 1. Run push zone engine (expensive — do once per symbol)
    zone_timeline = run_push_zone_engine(data_by_tf, base_tf)

    # 2. For each config, evaluate against same timeline
    results = []
    for config in configs:
        trades = evaluate_strategy(zone_timeline, config)
        metrics = calculate_metrics(trades)
        results.append({**config_to_dict(config), **metrics})

    return pd.DataFrame(results)


def run_multi_symbol_sweep(
    symbols: list[str],
    configs: list[StrategyConfig],
    base_tf: str = "M1",
) -> pd.DataFrame:
    """Sweep across all symbols. Zone engine runs once per symbol."""
    all_results = []
    for symbol in symbols:
        data = load_symbol_data(symbol)
        df = run_sweep(symbol, data, configs, base_tf)
        df["symbol"] = symbol
        all_results.append(df)
    return pd.concat(all_results)
```

Key optimization: the push zone engine runs **once per symbol**. Strategy evaluation runs N times cheaply against the same zone timeline. This makes sweeping hundreds of configs fast.

---

## Flask Visualization + Backtest Reporting

### New Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/backtest/run` | POST | Run strategy on symbol with config → trades + metrics |
| `/api/backtest/sweep` | POST | Run parameter sweep → comparison table |
| `/api/backtest/trades` | GET | Trade list with full entry context |
| `/api/backtest/equity` | GET | Equity curve + drawdown data |
| `/api/backtest/report` | GET | Summary metrics (Sharpe, Sortino, win rate, etc.) |

### Trade Visualization on Chart

- Entry markers (arrow at entry bar, zone highlight)
- SL/TP horizontal lines from entry bar
- Exit markers with P&L label
- Trade outcome coloring (green = win, red = loss)
- Active zones highlighted at entry time

### Sweep Comparison View

- Table of all config combos ranked by selected metric
- Click row → loads that config's trades on chart
- Filter by asset class, nesting combo, SL/TP mode
- Heatmap: nesting combo × SL/TP mode → performance

### Multi-Symbol Batch View

- Per-symbol metrics table
- Aggregate equity curve (portfolio level)
- Asset class breakdown (forex / metals / crypto / indices / energy)

### Existing Infrastructure Reused

- `chart_viewer_lw.py` — Flask app, Lightweight Charts, compression, caching
- `serializers.py` — zone/signal serialization (extended for push zones + trades)
- `backtest/metrics.py` — Sharpe, Sortino, Calmar, SQN, drawdown, streaks, profit factor
- `backtest/costs.py` — spread, commission, slippage, session multipliers, death zone penalty
- `backtest/market_mechanics.py` — pip sizes, position sizing, asset class detection

---

## File Structure

### New Files

```
src/iora/
  engine/
    push_zone_tick.py          # HA run detection, zone creation, push/reversal validation
    push_zone_models.py        # PushZone, PushZoneTickState, PeriodTracker dataclasses
  orchestrator/
    push_zone_engine.py        # Multi-TF orchestration (calls push_zone_tick per TF per bar)
  strategy/
    __init__.py
    push_zone_strategy.py      # Entry/exit rule evaluation against push zone timeline
    strategy_config.py         # StrategyConfig dataclass + preset configs
    sweep_runner.py            # Batch sweep across configs/symbols
  backtest/
    push_zone_evaluator.py     # Bridges strategy signals → TradeRecord → metrics
```

### Modified Files

```
src/iora/
  orchestrator/pipeline.py     # Add push_zone_engine as optional component
  data/tf_alignment.py         # Add HA columns to per-TF computation
apps/
  chart_viewer_lw.py           # Add backtest/sweep endpoints
  serializers.py               # Add push zone + trade serialization
```

### Legacy Files (archive, stop using)

```
src/iora/
  engine/zone_tick.py          # Fractal pivot-based zones → legacy
  orchestrator/zone_engine.py  # Fractal zone orchestration → legacy
  rules/                       # Old rule registry → replaced by strategy_config
```

---

## Pipeline Integration

### PipelineConfig Extension

```python
@dataclass
class PipelineConfig:
    # ... existing fields ...
    push_zone_on: bool = True        # Enable push zone engine
    push_zone_doji_pct: float = 5.0
    push_zone_lookback: int = 30
    push_zone_max_age: dict[str, int] = field(default_factory=lambda: {
        "M1": 50, "M5": 50, "M15": 50, "H1": 50,
        "H4": 50, "D1": 50, "W1": 30, "MN1": 20,
    })  # Max bars per TF before zone expires (matches Pine defaults)
    period_history_depth: int = 3    # How many period levels to store per TF
```

### PipelineOutput Extension

```python
@dataclass
class PipelineOutput:
    # ... existing fields ...

    # Push zone engine output
    push_zones_by_tf: dict[str, list[PushZone]] = field(default_factory=dict)
    push_trend_by_tf: dict[str, int] = field(default_factory=dict)
    period_levels_by_tf: dict[str, dict] = field(default_factory=dict)
    # period_levels_by_tf example: {"H1": {"highs": [1.265, 1.258, 1.251], "lows": [...]}}
```

### TF Alignment Extension

Add to `tf_alignment.py` per-TF computation:
- `ha_open`, `ha_close` — HA candle values
- `ha_color` — blue (True) / red (False)
- `ha_fire` — color transition edge (True on first bar of new color)
- `run_hi_ohlc`, `run_lo_ohlc` — extremes of the completed run
- `hi_txt`, `lo_txt` — HH/LH/LL/HL classification

---

## Data Requirements

- **Source:** `C:\Iora\data\raw\` — 38 symbols, M1→MN1 as yearly parquet files
- **Loading:** `ParquetStorage.load()` or `Mt5DataLoader`
- **TFs needed per symbol:** M1, M5, M15, H1, H4, D1, W1 (MN1 optional)
- **Base TF:** M1 for finest granularity entries, M5 for faster sweeps

---

## Scope Boundaries

### In Scope (v1)

- Push zone engine ported from Pine (HA detection, push/reversal, nesting, terminal, BOS/CHoCH)
- Period tracker with 3-level history per TF
- Signal matrix strategy with configurable entry/exit rules
- Sweep runner across configs and symbols
- Flask visualization of trades on chart
- Backtest metrics and reporting
- Single position mode (all-in / all-out)

### Out of Scope (later)

- Partial exits and scale-in position management
- ML enhancement of mechanical signals
- Live trading execution
- Pine Script strategy port (use TV indicator for visual spot-checking only)
- Hedging (simultaneous long + short models)
