# Sweep Runner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a batch sweep runner that tests multiple StrategyConfig combinations across multiple symbols, producing a comparison DataFrame with per-config metrics.

**Architecture:** The sweep runner wraps Plan 2's `build_zone_timeline()` (expensive, once per symbol) and `evaluate_strategy()` (cheap, N times per timeline). Config generation produces cartesian products of sweep dimensions. Results are collected as flat dicts and returned as a pandas DataFrame. Multi-symbol sweep iterates sequentially (one symbol at a time to limit memory). Trade dicts from `evaluate_strategy()` are converted to `TradeRecord` objects for the existing `PerformanceMetrics` engine.

**Tech Stack:** Python 3.12, pandas, numpy, pytest. Integrates with existing `backtest/metrics.py` (TradeRecord, PerformanceMetrics), `backtest/market_mechanics.py` (get_pip_size).

---

## File Structure

```
src/iora/strategy/
  config_grid.py                   # Cartesian product config generator
  trade_converter.py               # StrategyResult trade dicts → TradeRecord objects
  sweep_runner.py                  # run_sweep(), run_multi_symbol_sweep()

tests/strategy/
  test_config_grid.py
  test_trade_converter.py
  test_sweep_runner.py
  test_sweep_integration.py        # Real data: GBPUSD sweep
```

| File | Purpose |
|------|---------|
| `config_grid.py` | Takes a dict of dimension → values, produces list of StrategyConfig via cartesian product |
| `trade_converter.py` | Converts `StrategyResult.trades` (list of dicts) to `TradeRecord` objects for `PerformanceMetrics` |
| `sweep_runner.py` | `run_sweep()` for single symbol, `run_multi_symbol_sweep()` for batch. Timeline built once per symbol, configs evaluated cheaply. Returns DataFrame with config params + metrics columns. |

---

### Task 1: Config Grid Generator

**Files:**
- Create: `src/iora/strategy/config_grid.py`
- Test: `tests/strategy/test_config_grid.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_config_grid.py
"""Tests for config grid generator."""
from __future__ import annotations

from iora.strategy.config_grid import build_config_grid
from iora.strategy.strategy_config import StrategyConfig


def test_single_dimension():
    """One dimension with 3 values produces 3 configs."""
    grid = build_config_grid({"sl_mode": ["zone", "atr", "fixed_pips"]})
    assert len(grid) == 3
    modes = {c.sl_mode for c in grid}
    assert modes == {"zone", "atr", "fixed_pips"}
    # All other fields are defaults
    assert all(c.entry_tf == "M5" for c in grid)


def test_two_dimensions():
    """Two dimensions: 2 x 3 = 6 configs."""
    grid = build_config_grid({
        "sl_mode": ["zone", "atr"],
        "tp_mode": ["zone", "fixed_rr", "atr"],
    })
    assert len(grid) == 6
    combos = {(c.sl_mode, c.tp_mode) for c in grid}
    assert ("zone", "zone") in combos
    assert ("atr", "fixed_rr") in combos


def test_three_dimensions():
    """Three dimensions: 2 x 2 x 2 = 8 configs."""
    grid = build_config_grid({
        "entry_tf": ["M5", "M15"],
        "require_nesting": [True, False],
        "direction": ["both", "long"],
    })
    assert len(grid) == 8


def test_empty_grid():
    """Empty dimensions dict returns single default config."""
    grid = build_config_grid({})
    assert len(grid) == 1
    assert grid[0].entry_tf == "M5"


def test_set_dimension():
    """Set-valued dimensions (signal_types) work correctly."""
    grid = build_config_grid({
        "signal_types": [{"push"}, {"push", "reversal"}],
    })
    assert len(grid) == 2
    types = [c.signal_types for c in grid]
    assert {"push"} in types
    assert {"push", "reversal"} in types


def test_base_config_override():
    """Base config overrides defaults for non-swept dimensions."""
    base = StrategyConfig(parent_tf="H4", no_trade_zones=False)
    grid = build_config_grid(
        {"sl_mode": ["zone", "atr"]},
        base=base,
    )
    assert len(grid) == 2
    assert all(c.parent_tf == "H4" for c in grid)
    assert all(c.no_trade_zones is False for c in grid)


def test_invalid_dimension_raises():
    """Unknown dimension key raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Unknown"):
        build_config_grid({"fake_field": [1, 2]})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_config_grid.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/config_grid.py
"""Config grid generator — cartesian product of sweep dimensions."""
from __future__ import annotations

import itertools
from dataclasses import fields

from iora.strategy.strategy_config import StrategyConfig

_VALID_FIELDS = {f.name for f in fields(StrategyConfig)}


def build_config_grid(
    dimensions: dict[str, list],
    base: StrategyConfig | None = None,
) -> list[StrategyConfig]:
    """Generate StrategyConfig instances from cartesian product of dimensions.

    Args:
        dimensions: Dict of field_name → list of values to sweep.
            E.g. {"sl_mode": ["zone", "atr"], "tp_mode": ["zone", "fixed_rr"]}
        base: Base config whose non-swept fields are used as defaults.
            If None, StrategyConfig() defaults are used.

    Returns:
        List of StrategyConfig, one per combination.

    Raises:
        ValueError: If a dimension key is not a valid StrategyConfig field.
    """
    for key in dimensions:
        if key not in _VALID_FIELDS:
            raise ValueError(f"Unknown StrategyConfig field: {key!r}")

    if base is None:
        base = StrategyConfig()

    if not dimensions:
        return [base]

    keys = list(dimensions.keys())
    value_lists = [dimensions[k] for k in keys]

    configs: list[StrategyConfig] = []
    base_dict = base.to_dict()
    # to_dict converts signal_types to sorted list — we need to preserve sets
    base_dict["signal_types"] = base.signal_types

    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        merged = {**base_dict, **overrides}
        configs.append(StrategyConfig(**merged))

    return configs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_config_grid.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/config_grid.py tests/strategy/test_config_grid.py
git commit -m "feat(strategy): add config grid generator for sweep dimensions"
```

---

### Task 2: Trade Converter

**Files:**
- Create: `src/iora/strategy/trade_converter.py`
- Test: `tests/strategy/test_trade_converter.py`

Converts `StrategyResult.trades` (list of dicts with keys like `entry_time`, `exit_time`, `entry_price`, `exit_price`, `direction`, `pnl_pips`, `exit_reason`, `sl_price`, `tp_price`) into `SweepTradeRecord` objects (lightweight, no external deps) and optionally into `flint.backtest.metrics.TradeRecord` for `PerformanceMetrics`.

**IMPORTANT:** The `backtest/` directory imports from `flint` (external package at `C:\Flint\src\flint\`). To avoid a hard dependency, this module defines its own `SweepTradeRecord` dataclass and provides an optional `to_flint_records()` function that requires `flint` on PYTHONPATH.

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_trade_converter.py
"""Tests for trade dict → SweepTradeRecord converter."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.strategy.trade_converter import convert_trades, SweepTradeRecord


def _make_trade(
    direction="long", pnl_pips=10.0, exit_reason="tp_hit",
    entry_price=1.2950, exit_price=1.2960,
) -> dict:
    return {
        "entry_time": pd.Timestamp("2025-01-01 10:00"),
        "exit_time": pd.Timestamp("2025-01-01 12:00"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "direction": direction,
        "sl_price": 1.2920,
        "tp_price": 1.3000,
        "exit_reason": exit_reason,
        "pnl_pips": pnl_pips,
        "signal_type": "push",
        "struct_cls": "BOS",
        "zone_tf": "M5",
        "parent_tf": "H1",
        "nesting_depth": 1,
        "rr_ratio": 2.0,
    }


def test_convert_single_trade():
    """Single trade dict converts to SweepTradeRecord."""
    trades = [_make_trade()]
    records = convert_trades(trades, symbol="GBPUSD")
    assert len(records) == 1
    r = records[0]
    assert r.symbol == "GBPUSD"
    assert r.direction == 1  # long → 1
    assert r.entry_price == 1.2950
    assert r.exit_price == 1.2960
    assert r.exit_reason == "tp_hit"
    assert r.pnl_pips == 10.0


def test_convert_short_trade():
    """Short trade direction maps to -1."""
    trades = [_make_trade(direction="short", pnl_pips=-15.0,
                          exit_reason="sl_hit", exit_price=1.2980)]
    records = convert_trades(trades, symbol="GBPUSD")
    assert records[0].direction == -1
    assert records[0].pnl_pips < 0


def test_convert_empty():
    """Empty list returns empty list."""
    records = convert_trades([], symbol="GBPUSD")
    assert records == []


def test_convert_multiple():
    """Multiple trades get sequential trade_ids."""
    trades = [_make_trade(), _make_trade(pnl_pips=-5.0, exit_reason="sl_hit")]
    records = convert_trades(trades, symbol="GBPUSD")
    assert len(records) == 2
    assert records[0].trade_id != records[1].trade_id


def test_return_r_computed():
    """return_r is pnl_pips / risk_pips (entry-SL distance)."""
    t = _make_trade(pnl_pips=20.0)
    records = convert_trades([t], symbol="GBPUSD")
    # risk = |1.2950 - 1.2920| / 0.0001 = 30 pips
    # return_r = 20 / 30 ≈ 0.667
    assert records[0].return_r == pytest.approx(20.0 / 30.0, abs=0.01)


def test_is_winner_property():
    """SweepTradeRecord has is_winner/is_loser properties."""
    t_win = _make_trade(pnl_pips=10.0)
    t_loss = _make_trade(pnl_pips=-5.0, exit_reason="sl_hit")
    records = convert_trades([t_win, t_loss], symbol="GBPUSD")
    assert records[0].is_winner is True
    assert records[1].is_winner is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_trade_converter.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/trade_converter.py
"""Convert strategy trade dicts to SweepTradeRecord objects.

Uses a lightweight SweepTradeRecord dataclass that has NO external
dependencies (no flint/backtest imports). This allows the sweep runner
to work without flint on PYTHONPATH.

For full PerformanceMetrics integration, use to_flint_records() which
requires flint to be importable.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# Pip sizes for common symbols (avoids flint dependency)
_PIP_SIZES: dict[str, float] = {}
_DEFAULT_PIP_SIZE = 0.0001
_JPY_PIP_SIZE = 0.01


def _get_pip_size(symbol: str) -> float:
    """Get pip size for a symbol without flint dependency."""
    symbol = symbol.upper()
    if symbol in _PIP_SIZES:
        return _PIP_SIZES[symbol]
    if symbol.endswith("JPY") or symbol in ("XAUUSD",):
        return _JPY_PIP_SIZE
    if symbol in ("DE40", "US30", "US500", "US100", "UK100", "JP225"):
        return 1.0
    if symbol in ("BTCUSD", "ETHUSD"):
        return 1.0
    return _DEFAULT_PIP_SIZE


@dataclass(frozen=True, slots=True)
class SweepTradeRecord:
    """Lightweight trade record for sweep results. No external deps."""

    trade_id: str
    symbol: str
    direction: int          # 1=LONG, -1=SHORT
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pips: float
    return_r: float         # P&L in R-multiples
    exit_reason: str
    sl_price: float
    tp_price: float
    zone_tf: str = ""
    signal_type: str = ""

    @property
    def is_winner(self) -> bool:
        return self.pnl_pips > 0

    @property
    def holding_period(self) -> pd.Timedelta:
        return self.exit_time - self.entry_time


def convert_trades(
    trades: list[dict],
    symbol: str,
) -> list[SweepTradeRecord]:
    """Convert strategy result trade dicts to SweepTradeRecord objects.

    Args:
        trades: Trade dicts from StrategyResult.trades.
        symbol: Trading symbol.

    Returns:
        List of SweepTradeRecord objects.
    """
    pip_size = _get_pip_size(symbol)

    records: list[SweepTradeRecord] = []
    for i, t in enumerate(trades):
        direction_int = 1 if t["direction"] == "long" else -1
        pnl_pips = t["pnl_pips"]

        # Risk in pips for R-multiple
        risk_pips = abs(t["entry_price"] - t["sl_price"]) / pip_size
        return_r = pnl_pips / risk_pips if risk_pips > 0 else 0.0

        records.append(SweepTradeRecord(
            trade_id=f"pz_{i:04d}",
            symbol=symbol,
            direction=direction_int,
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            pnl_pips=pnl_pips,
            return_r=return_r,
            exit_reason=t["exit_reason"],
            sl_price=t["sl_price"],
            tp_price=t["tp_price"],
            zone_tf=t.get("zone_tf", ""),
            signal_type=t.get("signal_type", ""),
        ))

    return records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_trade_converter.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/trade_converter.py tests/strategy/test_trade_converter.py
git commit -m "feat(strategy): add trade dict to TradeRecord converter"
```

---

### Task 3: Sweep Runner

**Files:**
- Create: `src/iora/strategy/sweep_runner.py`
- Test: `tests/strategy/test_sweep_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_sweep_runner.py
"""Tests for sweep runner."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.strategy.sweep_runner import run_sweep, run_multi_symbol_sweep
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.engine.push_zone_models import PushZone


def _zone(is_supply: bool, top: float, bottom: float) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
        is_push=True, struct_cls="BOS",
        swing_cls="HH" if is_supply else "LL", count_num=1,
    )


def _make_timeline(n: int = 50) -> list[ZoneTimelineBar]:
    """Synthetic timeline with one fire at bar 5."""
    bars: list[ZoneTimelineBar] = []
    demand = _zone(False, 1.2900, 1.2880)
    for i in range(n):
        fires = [demand] if i == 5 else []
        bars.append(ZoneTimelineBar(
            timestamp=pd.Timestamp("2025-01-01") + pd.Timedelta(minutes=5 * i),
            open_=1.29 + 0.001 * i, high=1.295 + 0.001 * i,
            low=1.285 + 0.001 * i, close=1.29 + 0.001 * i,
            fires=fires, breaks=[],
            zones_by_tf={"M5": [demand] if i >= 5 else []},
            trend_by_tf={"M5": 0},
            period_levels_by_tf={"M5": {"highs": [], "lows": []}},
            zone_counts_by_tf={"M5": (0, 1 if i >= 5 else 0)},
        ))
    return bars


class TestRunSweep:
    def test_single_config(self):
        """Single config returns DataFrame with 1 row."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "total_trades" in df.columns
        assert "win_rate" in df.columns
        assert "entry_tf" in df.columns  # config column

    def test_multiple_configs(self):
        """Multiple configs return one row per config."""
        timeline = _make_timeline()
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                          sl_mode="atr", tp_mode="fixed_rr"),
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                          sl_mode="zone", tp_mode="fixed_rr"),
        ]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        assert len(df) == 2

    def test_no_configs(self):
        """Empty config list returns empty DataFrame."""
        timeline = _make_timeline()
        df = run_sweep(timeline, [], symbol="GBPUSD")
        assert len(df) == 0

    def test_result_columns(self):
        """Result DataFrame has config + metrics columns."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        df = run_sweep(timeline, configs, symbol="GBPUSD")
        # Config columns
        assert "sl_mode" in df.columns
        assert "tp_mode" in df.columns
        assert "entry_tf" in df.columns
        # Metric columns
        assert "total_trades" in df.columns
        assert "total_signals" in df.columns


class TestRunMultiSymbolSweep:
    def test_returns_dataframe_with_symbol_column(self):
        """Multi-symbol sweep adds symbol column."""
        timeline = _make_timeline()
        configs = [StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
        )]
        # Use pre-built timelines dict
        timelines = {"GBPUSD": timeline, "EURUSD": timeline}
        df = run_multi_symbol_sweep(timelines, configs)
        assert "symbol" in df.columns
        assert set(df["symbol"].unique()) == {"GBPUSD", "EURUSD"}
        assert len(df) == 2  # 1 config x 2 symbols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_sweep_runner.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/sweep_runner.py
"""Sweep runner — batch strategy evaluation across configs and symbols.

Key optimization: zone timeline is built ONCE per symbol (expensive).
Strategy evaluation runs N times cheaply per timeline.
"""
from __future__ import annotations

import logging

import pandas as pd

from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.zone_timeline import ZoneTimelineBar, build_zone_timeline
from iora.strategy.push_zone_strategy import evaluate_strategy
from iora.strategy.trade_converter import convert_trades

logger = logging.getLogger(__name__)


def run_sweep(
    timeline: list[ZoneTimelineBar],
    configs: list[StrategyConfig],
    symbol: str = "GBPUSD",
) -> pd.DataFrame:
    """Evaluate multiple configs against a single pre-built timeline.

    Args:
        timeline: Pre-built zone timeline (from build_zone_timeline).
        configs: List of strategy configs to evaluate.
        symbol: Trading symbol for pip/cost calculations.

    Returns:
        DataFrame with one row per config: config params + metrics.
    """
    if not configs:
        return pd.DataFrame()

    rows: list[dict] = []
    for cfg in configs:
        result = evaluate_strategy(timeline, cfg, symbol=symbol)

        # Compute basic metrics
        trades = result.trades
        n_trades = len(trades)
        wins = sum(1 for t in trades if t["pnl_pips"] > 0)
        losses = sum(1 for t in trades if t["pnl_pips"] <= 0)
        total_pnl = sum(t["pnl_pips"] for t in trades)

        metrics = {
            "total_signals": len(result.signals),
            "total_trades": n_trades,
            "open_trades": len(result.open_trades),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / n_trades if n_trades > 0 else 0.0,
            "total_pnl_pips": total_pnl,
            "avg_pnl_pips": total_pnl / n_trades if n_trades > 0 else 0.0,
        }

        # Extended metrics from trade records
        if trades:
            records = convert_trades(trades, symbol=symbol)
            r_values = [r.return_r for r in records]
            win_r = [r for r in r_values if r > 0]
            loss_r = [r for r in r_values if r <= 0]
            metrics.update({
                "avg_win_r": sum(win_r) / len(win_r) if win_r else 0.0,
                "avg_loss_r": sum(loss_r) / len(loss_r) if loss_r else 0.0,
                "total_r": sum(r_values),
                "expectancy": sum(r_values) / len(r_values) if r_values else 0.0,
                "profit_factor": (
                    sum(win_r) / abs(sum(loss_r))
                    if loss_r and sum(loss_r) != 0
                    else float("inf") if win_r else 0.0
                ),
            })

        row = {**cfg.to_dict(), **metrics}
        rows.append(row)

    return pd.DataFrame(rows)


def run_multi_symbol_sweep(
    timelines: dict[str, list[ZoneTimelineBar]],
    configs: list[StrategyConfig],
) -> pd.DataFrame:
    """Evaluate configs across multiple symbols using pre-built timelines.

    Args:
        timelines: Dict of symbol → pre-built zone timeline.
        configs: List of strategy configs to evaluate.

    Returns:
        DataFrame with symbol + config params + metrics columns.
    """
    all_dfs: list[pd.DataFrame] = []

    for symbol, timeline in timelines.items():
        logger.info("Sweeping %s (%d bars, %d configs)",
                     symbol, len(timeline), len(configs))
        df = run_sweep(timeline, configs, symbol=symbol)
        df.insert(0, "symbol", symbol)
        all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)


def build_and_sweep(
    data_by_tf: dict[str, pd.DataFrame],
    configs: list[StrategyConfig],
    symbol: str = "GBPUSD",
    base_tf: str = "M5",
) -> pd.DataFrame:
    """Convenience: build timeline + sweep in one call.

    Args:
        data_by_tf: Raw OHLCV data per TF.
        configs: Strategy configs to sweep.
        symbol: Trading symbol.
        base_tf: Base timeframe for bar iteration.

    Returns:
        DataFrame with config params + metrics.
    """
    timeline = build_zone_timeline(data_by_tf, base_tf=base_tf)
    return run_sweep(timeline, configs, symbol=symbol)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_sweep_runner.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/sweep_runner.py tests/strategy/test_sweep_runner.py
git commit -m "feat(strategy): add sweep runner for batch config evaluation"
```

---

### Task 4: Integration Test + CLI Script

**Files:**
- Create: `tests/strategy/test_sweep_integration.py`
- Create: `scripts/run_sweep.py`
- Modify: `src/iora/strategy/__init__.py` (add sweep runner re-exports)

- [ ] **Step 1: Write integration test**

```python
# tests/strategy/test_sweep_integration.py
"""Integration test: sweep across configs on real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.sweep_runner import run_sweep
from iora.strategy.config_grid import build_config_grid
from iora.strategy.strategy_config import StrategyConfig


@pytest.fixture(scope="module")
def gbpusd_timeline():
    storage = ParquetStorage("data")
    tfs = ["M5", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load("GBPUSD", tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
    if "M5" not in data_by_tf:
        pytest.skip("GBPUSD M5 data not available")
    return build_zone_timeline(data_by_tf, base_tf="M5")


class TestSweepIntegration:
    def test_grid_sweep_produces_results(self, gbpusd_timeline):
        """Grid sweep across SL/TP modes produces comparison table."""
        grid = build_config_grid({
            "sl_mode": ["zone", "atr"],
            "tp_mode": ["zone", "fixed_rr"],
            "require_nesting": [False],
            "no_trade_zones": [False],
        })
        df = run_sweep(gbpusd_timeline, grid, symbol="GBPUSD")
        assert len(df) == 4  # 2 x 2
        assert "win_rate" in df.columns
        assert "total_trades" in df.columns
        assert all(df["total_trades"] > 0)

    def test_sweep_configs_differ(self, gbpusd_timeline):
        """Different configs produce different results."""
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                          sl_mode="atr", tp_mode="fixed_rr", fixed_rr=1.0),
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                          sl_mode="atr", tp_mode="fixed_rr", fixed_rr=5.0),
        ]
        df = run_sweep(gbpusd_timeline, configs, symbol="GBPUSD")
        # Different R:R targets should produce different win rates
        assert df.iloc[0]["win_rate"] != df.iloc[1]["win_rate"]

    def test_sweep_performance(self, gbpusd_timeline):
        """Sweeping 10 configs takes < 30s (replay is cheap)."""
        import time
        configs = [
            StrategyConfig(require_nesting=False, no_trade_zones=False,
                          sl_mode="atr", tp_mode="fixed_rr",
                          fixed_rr=float(rr))
            for rr in range(1, 11)
        ]
        start = time.monotonic()
        df = run_sweep(gbpusd_timeline, configs, symbol="GBPUSD")
        elapsed = time.monotonic() - start
        assert len(df) == 10
        assert elapsed < 30.0
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/strategy/test_sweep_integration.py -v --timeout=120`
Expected: 3 PASSED

- [ ] **Step 3: Write CLI sweep script**

```python
# scripts/run_sweep.py
"""Run a parameter sweep across configs on GBPUSD.

Usage: python scripts/run_sweep.py [--symbols GBPUSD,EURUSD] [--output results.csv]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.sweep_runner import run_sweep, run_multi_symbol_sweep
from iora.strategy.config_grid import build_config_grid


def main():
    parser = argparse.ArgumentParser(description="Push zone strategy sweep")
    parser.add_argument("--symbols", default="GBPUSD",
                        help="Comma-separated symbols (default: GBPUSD)")
    parser.add_argument("--output", default=None,
                        help="Output CSV path (default: print to stdout)")
    parser.add_argument("--base-tf", default="M5",
                        help="Base timeframe (default: M5)")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]
    storage = ParquetStorage("data")

    # Define sweep grid
    grid = build_config_grid({
        "sl_mode": ["zone", "atr"],
        "tp_mode": ["zone", "fixed_rr"],
        "require_nesting": [True, False],
        "no_trade_zones": [True, False],
    })
    print(f"Sweep grid: {len(grid)} configs x {len(symbols)} symbols "
          f"= {len(grid) * len(symbols)} runs")

    # Build timelines (expensive — once per symbol)
    timelines = {}
    for symbol in symbols:
        tfs = [args.base_tf, "M15", "H1", "H4", "D1"]
        data_by_tf = {}
        for tf in tfs:
            df = storage.load(symbol, tf)
            if df is not None and not df.empty:
                data_by_tf[tf] = df

        if args.base_tf not in data_by_tf:
            print(f"  SKIP {symbol}: no {args.base_tf} data")
            continue

        t0 = time.monotonic()
        timelines[symbol] = build_zone_timeline(data_by_tf, base_tf=args.base_tf)
        print(f"  {symbol}: {len(timelines[symbol])} bars "
              f"({time.monotonic() - t0:.1f}s)")

    # Run sweep
    t0 = time.monotonic()
    df = run_multi_symbol_sweep(timelines, grid)
    elapsed = time.monotonic() - t0
    print(f"\nSweep complete: {len(df)} results in {elapsed:.1f}s")

    # Sort by total_pnl_pips descending
    if "total_pnl_pips" in df.columns:
        df = df.sort_values("total_pnl_pips", ascending=False)

    # Output
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Results saved to {args.output}")
    else:
        # Print top 10 configs
        display_cols = [
            "symbol", "sl_mode", "tp_mode", "require_nesting", "no_trade_zones",
            "total_signals", "total_trades", "wins", "losses", "win_rate",
            "total_pnl_pips", "avg_pnl_pips",
        ]
        cols = [c for c in display_cols if c in df.columns]
        print(f"\n{'='*100}")
        print(f"Top 10 configs by total PnL:")
        print(df[cols].head(10).to_string(index=False))
        print(f"\nBottom 5 configs:")
        print(df[cols].tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update __init__.py re-exports**

Read `src/iora/strategy/__init__.py` first, then add:
```python
from iora.strategy.config_grid import build_config_grid
from iora.strategy.trade_converter import convert_trades
from iora.strategy.sweep_runner import run_sweep, run_multi_symbol_sweep, build_and_sweep
```

And update `__all__` to include the new exports.

- [ ] **Step 5: Run CLI script**

Run: `python scripts/run_sweep.py --symbols GBPUSD`
Expected: Grid of 16 configs (2x2x2x2), ranked by total PnL.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/strategy/ -v --timeout=300`
Expected: All tests pass (~75+ tests)

- [ ] **Step 7: Commit**

```bash
git add tests/strategy/test_sweep_integration.py scripts/run_sweep.py \
       src/iora/strategy/__init__.py
git commit -m "feat(strategy): add sweep integration tests and CLI script"
```

---

## Summary

| Task | Files | Tests | Description |
|------|-------|-------|-------------|
| 1 | 1 create | 7 | Config grid generator (cartesian product) |
| 2 | 1 create | 6 | Trade dict → TradeRecord converter |
| 3 | 1 create | 5 | Sweep runner (single + multi-symbol) |
| 4 | 3 create/modify | 3 | Integration test + CLI script |
| **Total** | **6 files** | **~21 tests** | |
