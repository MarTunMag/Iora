# Backtest Evaluation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the signal engine into the existing backtest framework so we can run Growth-only trades on historical data and identify which signal contexts produce winners vs losers.

**Architecture:** New `evaluator.py` bridges signal engine `trade_log` dicts → `TradeRecord` objects with costs. CLI script loads data, runs signal engine with scalps/add-ons disabled, evaluates trades, generates reports. Two small modifications to `signal_engine.py`: add `disabled_rules` param and pass `BarFeatures` to `execute_signals()` for entry context capture.

**Tech Stack:** Python 3.12, existing Flint backtest framework (TradeRecord, PerformanceMetrics, CostCalculator, PerformanceReporter), ParquetStorage for data loading.

**Spec:** `docs/superpowers/specs/2026-03-23-backtest-evaluation-design.md`

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `src/flint/orchestrator/signal_engine.py` | Signal engine | MODIFY: add `disabled_rules` param, pass `BarFeatures` to `execute_signals` |
| `src/flint/backtest/evaluator.py` | Trade matching + context analysis | CREATE |
| `scripts/run_backtest.py` | CLI entry point | CREATE |
| `tests/test_evaluator.py` | Unit + integration tests | CREATE |

---

### Task 1: Add disabled_rules parameter to signal engine

**Files:**
- Modify: `src/flint/orchestrator/signal_engine.py:147-153` (run_signal_engine signature)
- Modify: `src/flint/orchestrator/signal_engine.py:187` (after registry creation)
- Test: `tests/test_signal_engine.py` (add test)

- [ ] **Step 1: Write failing test for disabled_rules**

In `tests/test_signal_engine.py`, add:

```python
class TestDisabledRules:
    """Verify disabled_rules parameter prevents specific rules from firing."""

    def test_disabled_rules_skips_scalp(self):
        """When scalp_entry is disabled, no HEDGE signals should fire."""
        from flint.orchestrator.signal_engine import run_signal_engine
        from flint.orchestrator.pipeline import PipelineConfig
        import pandas as pd

        # Minimal synthetic data — just needs to not crash
        dates = pd.date_range("2026-01-01", periods=50, freq="15min")
        df = pd.DataFrame({
            "open": 1.30, "high": 1.301, "low": 1.299, "close": 1.30,
            "tick_volume": 100,
        }, index=dates)
        data = {"M15": df}

        result = run_signal_engine(
            data, "M15",
            pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
            disabled_rules=["scalp_entry", "growth_addon", "tp_targets"],
        )
        # No HEDGE signals should exist (scalp disabled)
        hedge_signals = [s for s in result.signals if s.signal_type == "HEDGE"]
        assert len(hedge_signals) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_signal_engine.py::TestDisabledRules -v`
Expected: FAIL — `run_signal_engine() got an unexpected keyword argument 'disabled_rules'`

- [ ] **Step 3: Implement disabled_rules parameter**

In `src/flint/orchestrator/signal_engine.py`, update `run_signal_engine` signature (line 147-153):

```python
def run_signal_engine(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str,
    pipeline_config: PipelineConfig | None = None,
    account_balance: float = 10_000.0,
    risk_pct: float = 0.01,
    disabled_rules: list[str] | None = None,
) -> SignalEngineOutput:
```

After `registry = create_default_registry()` (line 187), add:

```python
    if disabled_rules:
        for rule_id in disabled_rules:
            registry.disable(rule_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_signal_engine.py::TestDisabledRules -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass (457+)

- [ ] **Step 6: Commit**

```bash
git add src/flint/orchestrator/signal_engine.py tests/test_signal_engine.py
git commit -m "feat: add disabled_rules parameter to run_signal_engine"
```

---

### Task 2: Add BarFeatures context capture to execute_signals

**Files:**
- Modify: `src/flint/orchestrator/signal_engine.py:59-63` (execute_signals signature)
- Modify: `src/flint/orchestrator/signal_engine.py:76-83` (ENTRY log entry)
- Modify: `src/flint/orchestrator/signal_engine.py:276-278` (call site in run_signal_engine)
- Test: `tests/test_signal_engine.py` (add test)

- [ ] **Step 1: Write failing test for context capture**

In `tests/test_signal_engine.py`, add:

```python
class TestContextCapture:
    """Verify execute_signals attaches BarFeatures context to ENTRY log entries."""

    def test_entry_has_context(self):
        from flint.orchestrator.signal_engine import execute_signals, SignalEngineState
        from flint.rules.signal import Signal
        from flint.rules.position_state import PositionState
        from flint.features.composite import BarFeatures
        import pandas as pd

        sig = Signal(
            time=pd.Timestamp("2026-01-01 12:00"),
            rule_id="growth_entry",
            signal_type="ENTRY",
            direction="bull",
            tf="M1",
            parent_tf="H1",
            price=1.3000,
            sl_price=1.2980,
        )
        pos = PositionState(account_balance=1000.0)
        state = SignalEngineState()
        features = BarFeatures(
            timestamp=pd.Timestamp("2026-01-01 12:00"),
            close=1.3000,
            d1_bias=1,
            h4_bias=1,
            h1_bias=1,
            choch_bull=True,
        )
        log = execute_signals([sig], pos, state, bar_features=features)

        assert len(log) == 1
        assert "entry_context" in log[0]
        ctx = log[0]["entry_context"]
        assert ctx["d1_bias"] == 1
        assert ctx["h4_bias"] == 1
        assert ctx["choch_bull"] is True

    def test_no_context_when_none(self):
        from flint.orchestrator.signal_engine import execute_signals, SignalEngineState
        from flint.rules.signal import Signal
        from flint.rules.position_state import PositionState
        import pandas as pd

        sig = Signal(
            time=pd.Timestamp("2026-01-01 12:00"),
            rule_id="growth_entry",
            signal_type="ENTRY",
            direction="bull",
            tf="M1",
            parent_tf="H1",
            price=1.3000,
            sl_price=1.2980,
        )
        pos = PositionState(account_balance=1000.0)
        state = SignalEngineState()
        log = execute_signals([sig], pos, state)

        assert len(log) == 1
        assert "entry_context" not in log[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_signal_engine.py::TestContextCapture -v`
Expected: FAIL — `execute_signals() got an unexpected keyword argument 'bar_features'`

- [ ] **Step 3: Implement context capture**

Define the context fields list near the top of `signal_engine.py` (after the imports, before `SignalEngineState`):

```python
# Fields captured from BarFeatures at trade entry for diagnostic analysis
CONTEXT_FIELDS = [
    "d1_price_in_supply", "d1_price_in_demand",
    "h4_price_in_supply", "h4_price_in_demand",
    "h1_price_in_supply", "h1_price_in_demand",
    "m15_price_in_supply", "m15_price_in_demand",
    "d1_nearest_supply_price", "d1_nearest_demand_price",
    "h4_nearest_supply_price", "h4_nearest_demand_price",
    "h1_nearest_supply_price", "h1_nearest_demand_price",
    "d1_bias", "h4_bias", "h1_bias",
    "d_phase", "w_phase",
    "d_hh", "d_ll", "d_lh", "d_hl",
    "w_hh", "w_ll", "w_lh", "w_hl",
    "choch_bull", "choch_bear",
    "bos_bull", "bos_bear",
    "wave_label", "wave_phase",
    "ub_h1_sup", "ub_h1_dem",
    "ub_h4_sup", "ub_h4_dem",
    "ub_d_sup", "ub_d_dem",
]
```

Update `execute_signals` signature (line 59-63):

```python
def execute_signals(
    signals: list[Signal],
    position: PositionState,
    state: SignalEngineState,
    bar_features: "BarFeatures | None" = None,
) -> list[dict]:
```

After building the ENTRY log dict (line 78-83), before appending, add context:

```python
                if bar_features is not None:
                    log_entry["entry_context"] = {
                        f: getattr(bar_features, f, None)
                        for f in CONTEXT_FIELDS
                    }
```

Do the same for ADD_ON (line 105-108) and HEDGE (line 120-123) log entries.

**Important:** The existing log dict is built inline inside `log.append({...})`. Refactor to build a `log_entry` dict first, then conditionally add context, then append. This applies to ENTRY (lines 78-83), ADD_ON (lines 105-108), and HEDGE (lines 120-123).

**Also important:** The ADD_ON and HEDGE log entries are currently missing the `"sl"` field (only ENTRY has it). Add `"sl": sig.sl_price` to both ADD_ON and HEDGE log dicts. Also add `"rule_id": sig.rule_id` to all three (ENTRY, ADD_ON, HEDGE) — ENTRY is also currently missing it. Without `sl`, the evaluator's R-multiple calculation for those trades would be 0.0 (risk_dollars = 0).

Update the call site in `run_signal_engine` (line 276-278):

```python
        if bar_signals:
            log_entries = execute_signals(
                bar_signals, position, engine_state,
                bar_features=features,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_signal_engine.py::TestContextCapture -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/flint/orchestrator/signal_engine.py tests/test_signal_engine.py
git commit -m "feat: capture BarFeatures entry context in trade_log"
```

---

### Task 3: Create evaluator module — trade matching

**Files:**
- Create: `src/flint/backtest/evaluator.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write failing tests for trade matching**

Create `tests/test_evaluator.py`:

```python
"""Tests for backtest evaluator — trade matching and metrics."""

import pandas as pd
import pytest

from flint.backtest.evaluator import match_trades


class TestMatchTrades:
    """Verify trade_log event dicts are matched into complete trades."""

    def test_entry_then_exit(self):
        """ENTRY followed by EXIT produces one completed trade."""
        trade_log = [
            {
                "time": pd.Timestamp("2026-01-02 10:00"),
                "action": "ENTRY",
                "direction": "bull",
                "price": 1.3000,
                "sl": 1.2980,
                "lots": 0.01,
                "trade_id": 0,
            },
            {
                "time": pd.Timestamp("2026-01-02 14:00"),
                "action": "EXIT",
                "direction": "bull",
                "price": 1.3050,
                "closed_count": 1,
                "closed_lots": 0.01,
            },
        ]
        last_close = 1.3050
        trades = match_trades(trade_log, "GBPUSD", last_close)
        assert len(trades) == 1
        t = trades[0]
        assert t.entry_price == 1.3000
        assert t.exit_price == 1.3050
        assert t.direction == 1  # LONG
        assert t.exit_reason == "rule_exit"
        assert t.sl_price == 1.2980

    def test_entry_then_sl_hit(self):
        """ENTRY followed by SL_HIT produces one trade with exit_reason=sl_hit."""
        trade_log = [
            {
                "time": pd.Timestamp("2026-01-02 10:00"),
                "action": "ENTRY",
                "direction": "bear",
                "price": 1.3000,
                "sl": 1.3020,
                "lots": 0.02,
                "trade_id": 0,
            },
            {
                "time": pd.Timestamp("2026-01-02 12:00"),
                "action": "SL_HIT",
                "direction": "short",
                "sl_price": 1.3020,
                "lots": 0.02,
                "trade_id": 0,
            },
        ]
        trades = match_trades(trade_log, "GBPUSD", 1.3020)
        assert len(trades) == 1
        t = trades[0]
        assert t.exit_price == 1.3020
        assert t.exit_reason == "sl_hit"
        assert t.direction == -1  # SHORT

    def test_unmatched_force_closed(self):
        """Trades still open at end are force-closed at last_close."""
        trade_log = [
            {
                "time": pd.Timestamp("2026-01-02 10:00"),
                "action": "ENTRY",
                "direction": "bull",
                "price": 1.3000,
                "sl": 1.2980,
                "lots": 0.01,
                "trade_id": 0,
            },
        ]
        trades = match_trades(trade_log, "GBPUSD", 1.3030)
        assert len(trades) == 1
        assert trades[0].exit_reason == "end_of_data"
        assert trades[0].exit_price == 1.3030

    def test_sl_move_updates_pending_sl(self):
        """SL_MOVE updates pending trades' SL before they close."""
        trade_log = [
            {
                "time": pd.Timestamp("2026-01-02 10:00"),
                "action": "ENTRY",
                "direction": "bull",
                "price": 1.3000,
                "sl": 1.2980,
                "lots": 0.01,
                "trade_id": 0,
            },
            {
                "time": pd.Timestamp("2026-01-02 12:00"),
                "action": "SL_MOVE",
                "new_sl": 1.2995,
                "trades_updated": 1,
            },
            {
                "time": pd.Timestamp("2026-01-02 14:00"),
                "action": "SL_HIT",
                "direction": "long",
                "sl_price": 1.2995,
                "lots": 0.01,
                "trade_id": 0,
            },
        ]
        trades = match_trades(trade_log, "GBPUSD", 1.2995)
        assert len(trades) == 1
        # SL should reflect the trailed value
        assert trades[0].sl_price == 1.2995

    def test_exit_closes_all_pending(self):
        """EXIT closes ALL pending growth trades, not just one."""
        trade_log = [
            {
                "time": pd.Timestamp("2026-01-02 10:00"),
                "action": "ENTRY",
                "direction": "bull",
                "price": 1.3000,
                "sl": 1.2980,
                "lots": 0.01,
                "trade_id": 0,
            },
            {
                "time": pd.Timestamp("2026-01-02 11:00"),
                "action": "ADD_ON",
                "direction": "bull",
                "price": 1.3010,
                "lots": 0.01,
                "trade_id": 1,
            },
            {
                "time": pd.Timestamp("2026-01-02 14:00"),
                "action": "EXIT",
                "direction": "bull",
                "price": 1.3060,
                "closed_count": 2,
                "closed_lots": 0.02,
            },
        ]
        trades = match_trades(trade_log, "GBPUSD", 1.3060)
        assert len(trades) == 2
        assert all(t.exit_reason == "rule_exit" for t in trades)
        assert all(t.exit_price == 1.3060 for t in trades)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_evaluator.py::TestMatchTrades -v`
Expected: FAIL — `cannot import name 'match_trades'`

- [ ] **Step 3: Implement match_trades**

Create `src/flint/backtest/evaluator.py`:

```python
"""
Backtest Evaluator — Bridge signal engine output to TradeRecord metrics.

Converts SignalEngineOutput.trade_log (event dicts) into TradeRecord objects
with costs applied, then runs PerformanceMetrics for analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

import pandas as pd

from flint.backtest.costs import CostCalculator
from flint.backtest.market_mechanics import get_pip_size, get_pip_value_per_lot
from flint.backtest.metrics import PerformanceMetrics, TradeRecord

logger = logging.getLogger(__name__)


def match_trades(
    trade_log: list[dict],
    symbol: str,
    last_close: float,
) -> list[TradeRecord]:
    """Match trade_log open/close events into completed TradeRecord objects.

    Args:
        trade_log: Event dicts from SignalEngineOutput.trade_log.
        symbol: Trading symbol (for pip/cost calculations).
        last_close: Last bar's close price (for force-closing open trades).

    Returns:
        List of completed TradeRecord objects with costs applied.
    """
    pip_size = get_pip_size(symbol)
    pip_value = get_pip_value_per_lot(symbol)
    cost_calc = CostCalculator(symbol)

    # Track open trades by trade_id
    pending: dict[int, dict] = {}
    completed: list[TradeRecord] = []

    for event in trade_log:
        action = event["action"]

        if action in ("ENTRY", "ADD_ON", "HEDGE"):
            tid = event["trade_id"]
            pending[tid] = {
                "entry_time": event["time"],
                "entry_price": event["price"],
                "direction": event["direction"],
                "sl": event.get("sl", event["price"]),
                "lots": event["lots"],
                "trade_id": tid,
                "rule_id": event.get("rule_id", ""),
                "mode": "scalp" if action == "HEDGE" else "growth",
                "entry_context": event.get("entry_context"),
            }

        elif action == "EXIT":
            # EXIT closes ALL pending growth trades at exit price
            exit_time = event["time"]
            exit_price = event["price"]
            to_close = [
                tid for tid, info in pending.items()
                if info["mode"] == "growth"
            ]
            for tid in to_close:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, exit_time, exit_price, "rule_exit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "SL_HIT":
            tid = event["trade_id"]
            if tid in pending:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, event["time"], event["sl_price"], "sl_hit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "TP_HIT":
            tid = event["trade_id"]
            if tid in pending:
                info = pending.pop(tid)
                record = _build_trade_record(
                    info, event["time"], event["tp_price"], "tp_hit",
                    symbol, pip_size, pip_value, cost_calc,
                )
                completed.append(record)

        elif action == "SL_MOVE":
            # Update SL on ALL pending growth trades
            new_sl = event["new_sl"]
            for info in pending.values():
                if info["mode"] == "growth":
                    info["sl"] = new_sl

    # Force-close any remaining open trades
    for tid, info in pending.items():
        now = info["entry_time"]  # Fallback timestamp
        record = _build_trade_record(
            info, now, last_close, "end_of_data",
            symbol, pip_size, pip_value, cost_calc,
        )
        completed.append(record)

    return completed


def _build_trade_record(
    info: dict,
    exit_time: pd.Timestamp,
    exit_price: float,
    exit_reason: str,
    symbol: str,
    pip_size: float,
    pip_value: float,
    cost_calc: CostCalculator,
) -> TradeRecord:
    """Build a TradeRecord from a pending trade info dict + exit details."""
    entry_price = info["entry_price"]
    lots = info["lots"]
    direction_int = -1 if info["direction"] == "bear" else 1
    sl_price = info["sl"]

    # Raw P&L (before costs)
    if direction_int == 1:  # LONG
        pnl_raw = (exit_price - entry_price) / pip_size * pip_value * lots
    else:  # SHORT
        pnl_raw = (entry_price - exit_price) / pip_size * pip_value * lots

    # Cost — single call, commission is already round-trip
    cost = cost_calc.calculate_total_cost(info["entry_time"], lots)
    pnl_dollars = pnl_raw - cost.total_dollars

    # R-multiple
    risk_pips = abs(entry_price - sl_price) / pip_size
    risk_dollars = risk_pips * pip_value * lots
    return_r = pnl_dollars / risk_dollars if risk_dollars > 0 else 0.0

    return TradeRecord(
        trade_id=str(info["trade_id"]),
        symbol=symbol,
        direction=direction_int,
        entry_time=info["entry_time"],
        exit_time=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        position_size=lots,
        pnl_dollars=pnl_dollars,
        return_r=return_r,
        exit_reason=exit_reason,
        sl_price=sl_price,
        tp_price=0.0,
        timeframe="M15",
        mode=info["mode"],
        cost_dollars=cost.total_dollars,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_evaluator.py::TestMatchTrades -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/flint/backtest/evaluator.py tests/test_evaluator.py
git commit -m "feat: add trade matching logic in evaluator module"
```

---

### Task 4: Add signal type breakdown to evaluator

**Files:**
- Modify: `src/flint/backtest/evaluator.py` (add evaluate_trades + breakdown)
- Modify: `tests/test_evaluator.py` (add tests)

- [ ] **Step 1: Write failing tests for evaluate_trades and breakdown**

In `tests/test_evaluator.py`, add:

```python
from flint.backtest.evaluator import evaluate_trades, EvaluationResult


class TestEvaluateTrades:
    """Verify full evaluation pipeline produces metrics and breakdown."""

    def _make_signal_output(self):
        """Create a minimal SignalEngineOutput with known trades."""
        from unittest.mock import MagicMock
        from flint.orchestrator.signal_engine import SignalEngineOutput
        from flint.orchestrator.pipeline import PipelineOutput
        from flint.rules.position_state import PositionState

        trade_log = [
            {
                "time": pd.Timestamp("2026-02-03 10:00"),
                "action": "ENTRY",
                "direction": "bull",
                "price": 1.3000,
                "sl": 1.2980,
                "lots": 0.01,
                "trade_id": 0,
                "rule_id": "growth_entry",
                "entry_context": {
                    "d1_bias": 1,
                    "h4_bias": 1,
                    "h1_price_in_demand": True,
                    "h4_price_in_demand": False,
                    "m15_price_in_demand": True,
                    "h1_price_in_supply": False,
                    "h4_price_in_supply": False,
                    "m15_price_in_supply": False,
                    "choch_bull": True,
                    "choch_bear": False,
                },
            },
            {
                "time": pd.Timestamp("2026-02-03 16:00"),
                "action": "EXIT",
                "direction": "bull",
                "price": 1.3040,
                "closed_count": 1,
                "closed_lots": 0.01,
            },
        ]
        pipeline = MagicMock(spec=PipelineOutput)
        return SignalEngineOutput(
            pipeline=pipeline,
            signals=[],
            trade_log=trade_log,
            final_position=PositionState(),
        )

    def test_produces_evaluation_result(self):
        output = self._make_signal_output()
        result = evaluate_trades(output, "GBPUSD", initial_balance=1000.0)
        assert isinstance(result, EvaluationResult)
        assert len(result.trades) == 1
        assert "total_trades" in result.metrics
        assert result.metrics["total_trades"] == 1

    def test_breakdown_by_zone_tf(self):
        output = self._make_signal_output()
        result = evaluate_trades(output, "GBPUSD", initial_balance=1000.0)
        # Trade was at H1 demand (highest TF zone) → should be in "H1_zone" group
        bd = result.signal_type_breakdown
        assert "by_zone_tf" in bd
        assert "H1_zone" in bd["by_zone_tf"]
        assert bd["by_zone_tf"]["H1_zone"]["count"] == 1

    def test_breakdown_by_direction(self):
        output = self._make_signal_output()
        result = evaluate_trades(output, "GBPUSD", initial_balance=1000.0)
        bd = result.signal_type_breakdown
        assert "by_direction" in bd
        assert "long" in bd["by_direction"]
        assert bd["by_direction"]["long"]["count"] == 1

    def test_breakdown_by_bias_alignment(self):
        output = self._make_signal_output()
        result = evaluate_trades(output, "GBPUSD", initial_balance=1000.0)
        bd = result.signal_type_breakdown
        assert "by_bias_alignment" in bd
        # d1_bias=1, direction=bull → aligned
        assert "aligned" in bd["by_bias_alignment"]
        assert bd["by_bias_alignment"]["aligned"]["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_evaluator.py::TestEvaluateTrades -v`
Expected: FAIL — `cannot import name 'evaluate_trades'`

- [ ] **Step 3: Implement evaluate_trades and breakdown**

Add to `src/flint/backtest/evaluator.py`:

```python
@dataclass
class EvaluationResult:
    """Complete evaluation output."""
    trades: list[TradeRecord]
    metrics: dict
    trade_contexts: list[dict | None]
    signal_type_breakdown: dict
    raw_trade_log: list[dict]


def evaluate_trades(
    signal_output: "SignalEngineOutput",
    symbol: str,
    initial_balance: float = 1_000.0,
    last_close: float = 0.0,
) -> EvaluationResult:
    """Run full evaluation: match trades, calculate metrics, build breakdown.

    Args:
        signal_output: Output from run_signal_engine().
        symbol: Trading symbol.
        initial_balance: Starting account balance.
            IMPORTANT: Must match the account_balance passed to run_signal_engine()
            for position sizing and metrics to be consistent.
        last_close: Last bar's close price for force-closing open trades.

    Returns:
        EvaluationResult with trades, metrics, contexts, and breakdown.
    """
    trade_log = signal_output.trade_log

    # Match trades
    trades = match_trades(trade_log, symbol, last_close)

    # Extract contexts (aligned with trades by trade_id)
    contexts = _extract_contexts(trade_log, trades)

    # Calculate metrics
    metrics = {}
    if trades:
        pm = PerformanceMetrics(trades, initial_balance=initial_balance)
        metrics = pm.calculate_all()

    # Build breakdown
    breakdown = _build_breakdown(trades, contexts)

    return EvaluationResult(
        trades=trades,
        metrics=metrics,
        trade_contexts=contexts,
        signal_type_breakdown=breakdown,
        raw_trade_log=trade_log,
    )


def _extract_contexts(
    trade_log: list[dict], trades: list[TradeRecord]
) -> list[dict | None]:
    """Extract entry_context dicts aligned with the trades list."""
    # Build map: trade_id → entry_context
    ctx_map: dict[str, dict] = {}
    for event in trade_log:
        if event["action"] in ("ENTRY", "ADD_ON", "HEDGE"):
            ctx = event.get("entry_context")
            if ctx is not None:
                ctx_map[str(event["trade_id"])] = ctx

    return [ctx_map.get(t.trade_id) for t in trades]


def _classify_zone_tf(ctx: dict | None) -> str:
    """Determine highest-TF zone the price was in at entry."""
    if ctx is None:
        return "no_context"
    # Check from highest TF down
    if ctx.get("d1_price_in_supply") or ctx.get("d1_price_in_demand"):
        return "D1_zone"
    if ctx.get("h4_price_in_supply") or ctx.get("h4_price_in_demand"):
        return "H4_zone"
    if ctx.get("h1_price_in_supply") or ctx.get("h1_price_in_demand"):
        return "H1_zone"
    if ctx.get("m15_price_in_supply") or ctx.get("m15_price_in_demand"):
        return "M15_only"
    return "no_zone"


def _build_breakdown(
    trades: list[TradeRecord],
    contexts: list[dict | None],
) -> dict:
    """Group trades by multiple dimensions and calculate per-group metrics."""
    breakdown: dict[str, dict] = {}

    # Dimension: zone TF
    groups_zone: dict[str, list[TradeRecord]] = {}
    for trade, ctx in zip(trades, contexts):
        key = _classify_zone_tf(ctx)
        groups_zone.setdefault(key, []).append(trade)
    breakdown["by_zone_tf"] = {
        k: _group_metrics(v) for k, v in groups_zone.items()
    }

    # Dimension: exit reason
    groups_exit: dict[str, list[TradeRecord]] = {}
    for trade in trades:
        groups_exit.setdefault(trade.exit_reason, []).append(trade)
    breakdown["by_exit_reason"] = {
        k: _group_metrics(v) for k, v in groups_exit.items()
    }

    # Dimension: direction
    groups_dir: dict[str, list[TradeRecord]] = {}
    for trade in trades:
        key = "long" if trade.direction == 1 else "short"
        groups_dir.setdefault(key, []).append(trade)
    breakdown["by_direction"] = {
        k: _group_metrics(v) for k, v in groups_dir.items()
    }

    # Dimension: bias alignment
    groups_bias: dict[str, list[TradeRecord]] = {}
    for trade, ctx in zip(trades, contexts):
        if ctx is None:
            key = "no_context"
        else:
            d1_bias = ctx.get("d1_bias", 0)
            aligned = (trade.direction == 1 and d1_bias == 1) or \
                      (trade.direction == -1 and d1_bias == -1)
            key = "aligned" if aligned else "counter"
        groups_bias.setdefault(key, []).append(trade)
    breakdown["by_bias_alignment"] = {
        k: _group_metrics(v) for k, v in groups_bias.items()
    }

    return breakdown


def _group_metrics(trades: list[TradeRecord]) -> dict:
    """Calculate summary metrics for a group of trades."""
    if not trades:
        return {"count": 0}
    r_values = [t.return_r for t in trades]
    winners = [t for t in trades if t.is_winner]
    holding_hours = [
        t.holding_period.total_seconds() / 3600 for t in trades
    ]
    return {
        "count": len(trades),
        "win_rate": len(winners) / len(trades),
        "avg_r": sum(r_values) / len(r_values),
        "total_r": sum(r_values),
        "avg_holding_hours": sum(holding_hours) / len(holding_hours),
        "best_r": max(r_values),
        "worst_r": min(r_values),
    }
```

Note: Do NOT add a top-level import for `SignalEngineOutput` — use a string annotation `"SignalEngineOutput"` in the function signature to avoid circular imports. The type is only needed for documentation, not runtime.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_evaluator.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/flint/backtest/evaluator.py tests/test_evaluator.py
git commit -m "feat: add evaluate_trades with per-signal-type breakdown"
```

---

### Task 5: Create CLI backtest script

**Files:**
- Create: `scripts/run_backtest.py`
- Test: manual run

- [ ] **Step 1: Create the CLI script**

Create `scripts/run_backtest.py`:

```python
#!/usr/bin/env python
"""
Run Growth-only backtest on historical data.

Usage:
    python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01
    python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01 --balance 1000
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from flint.data.parquet_storage import ParquetStorage
from flint.orchestrator.pipeline import PipelineConfig
from flint.orchestrator.signal_engine import run_signal_engine
from flint.backtest.evaluator import evaluate_trades
from flint.backtest.reporter import PerformanceReporter
from flint.paths import DATA_DIR, REPORTS_DIR

logger = logging.getLogger(__name__)

# TFs required by the signal engine
REQUIRED_TFS = ["M1", "M5", "M15", "H1", "H4", "D1", "W1"]


def main():
    parser = argparse.ArgumentParser(description="Run Growth-only backtest")
    parser.add_argument("--symbol", default="GBPUSD", help="Trading symbol")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--base-tf", default="M15", help="Base timeframe")
    parser.add_argument("--balance", type=float, default=1000.0, help="Initial balance")
    parser.add_argument("--risk-pct", type=float, default=0.01, help="Risk per trade")
    parser.add_argument("--run-name", default="", help="Report folder name")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    run_name = args.run_name or f"{args.symbol}_{args.start}_{args.end}"
    output_dir = REPORTS_DIR / "backtest" / run_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    logger.info(f"Loading {args.symbol} data from {args.start} to {args.end}...")
    storage = ParquetStorage(DATA_DIR)
    data_by_tf: dict[str, pd.DataFrame] = {}

    for tf in REQUIRED_TFS:
        df = storage.load(args.symbol, tf, start_date=args.start, end_date=args.end)
        if not df.empty:
            data_by_tf[tf] = df
            logger.info(f"  {tf}: {len(df)} bars")
        else:
            logger.warning(f"  {tf}: no data")

    if args.base_tf not in data_by_tf:
        logger.error(f"No data for base TF {args.base_tf}")
        sys.exit(1)

    # 2. Run signal engine (Growth lifecycle only)
    logger.info("Running signal engine (Growth entry + exit + SL trail)...")
    t0 = time.time()
    signal_output = run_signal_engine(
        data_by_tf,
        args.base_tf,
        pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
        account_balance=args.balance,
        risk_pct=args.risk_pct,
        disabled_rules=["scalp_entry", "growth_addon", "tp_targets"],
    )
    elapsed = time.time() - t0
    logger.info(f"Signal engine completed in {elapsed:.1f}s")
    logger.info(f"  Signals: {len(signal_output.signals)}")
    logger.info(f"  Trade log events: {len(signal_output.trade_log)}")

    # 3. Evaluate trades
    logger.info("Evaluating trades...")
    last_close = float(data_by_tf[args.base_tf].iloc[-1]["close"])
    result = evaluate_trades(
        signal_output, args.symbol,
        initial_balance=args.balance,
        last_close=last_close,
    )
    logger.info(f"  Completed trades: {len(result.trades)}")

    if not result.trades:
        logger.warning("No trades to evaluate. Check rules and data range.")
        sys.exit(0)

    # 4. Generate reports
    logger.info("Generating reports...")
    reporter = PerformanceReporter(reports_dir=output_dir)

    report = reporter.generate_report(
        result.metrics, args.symbol, run_name,
        result.trades, initial_balance=args.balance,
    )
    reporter.save_report(report, "metrics.json")
    reporter.save_text_summary(report, "summary.txt")

    # Charts
    reporter.generate_all_charts(
        result.trades, initial_balance=args.balance,
        output_dir=output_dir,
    )

    # 5. Save trade details with contexts
    trades_detail = []
    for trade, ctx in zip(result.trades, result.trade_contexts):
        td = {
            "trade_id": trade.trade_id,
            "direction": "long" if trade.direction == 1 else "short",
            "entry_time": str(trade.entry_time),
            "exit_time": str(trade.exit_time),
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "lots": trade.position_size,
            "pnl_dollars": round(trade.pnl_dollars, 2),
            "return_r": round(trade.return_r, 2),
            "exit_reason": trade.exit_reason,
            "sl_price": trade.sl_price,
            "cost_dollars": round(trade.cost_dollars, 2),
            "holding_hours": round(
                trade.holding_period.total_seconds() / 3600, 1
            ),
            "entry_context": ctx,
        }
        trades_detail.append(td)

    trades_path = output_dir / "trades.json"
    with open(trades_path, "w") as f:
        json.dump(trades_detail, f, indent=2, default=str)

    # 6. Save signal breakdown
    breakdown_path = output_dir / "signal_breakdown.json"
    with open(breakdown_path, "w") as f:
        json.dump(result.signal_type_breakdown, f, indent=2)

    # 7. Print summary
    m = result.metrics
    print("\n" + "=" * 60)
    print(f"  BACKTEST RESULTS: {args.symbol} {args.start} → {args.end}")
    print("=" * 60)
    print(f"  Trades:        {m.get('total_trades', 0)}")
    print(f"  Win Rate:      {m.get('win_rate', 0):.1%}")
    print(f"  Total R:       {m.get('total_r', 0):+.1f}")
    print(f"  Expectancy:    {m.get('expectancy', 0):+.2f}R")
    print(f"  SQN:           {m.get('sqn', 0):.2f}")
    print(f"  Profit Factor: {m.get('profit_factor', 0):.2f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown_pct', 0):.1f}%")
    print(f"  Sharpe:        {m.get('sharpe', 0):.2f}")
    print(f"  Total P&L:     ${m.get('total_pnl', 0):+.2f}")
    print(f"  Balance:       ${args.balance}")
    print("=" * 60)

    # Breakdown summary
    print("\n  BREAKDOWN BY ZONE TF:")
    for zone, gm in result.signal_type_breakdown.get("by_zone_tf", {}).items():
        print(f"    {zone:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY DIRECTION:")
    for d, gm in result.signal_type_breakdown.get("by_direction", {}).items():
        print(f"    {d:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY BIAS ALIGNMENT:")
    for b, gm in result.signal_type_breakdown.get("by_bias_alignment", {}).items():
        print(f"    {b:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print("\n  BREAKDOWN BY EXIT REASON:")
    for er, gm in result.signal_type_breakdown.get("by_exit_reason", {}).items():
        print(f"    {er:12s}  {gm['count']:3d} trades  "
              f"WR={gm['win_rate']:.0%}  avg={gm['avg_r']:+.2f}R  "
              f"total={gm['total_r']:+.1f}R")

    print(f"\n  Reports saved to: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the backtest on 1 month of GBPUSD**

```bash
python scripts/run_backtest.py --symbol GBPUSD --start 2026-02-01 --end 2026-03-01 --balance 1000
```

Expected: Completes without error, prints metrics summary, creates files in
`reports/backtest/GBPUSD_2026-02-01_2026-03-01/`.

Verify output files exist:
```bash
ls reports/backtest/GBPUSD_2026-02-01_2026-03-01/
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run_backtest.py
git commit -m "feat: add CLI backtest script for Growth lifecycle evaluation"
```

---

### Task 6: Integration test and full verification

**Files:**
- Modify: `tests/test_evaluator.py` (add integration test)

- [ ] **Step 1: Write integration test**

In `tests/test_evaluator.py`, add:

```python
class TestIntegration:
    """Integration test — run signal engine + evaluator on synthetic data."""

    def test_full_pipeline(self):
        """Run signal engine with disabled rules, evaluate, verify structure."""
        from flint.orchestrator.signal_engine import run_signal_engine
        from flint.orchestrator.pipeline import PipelineConfig
        from flint.backtest.evaluator import evaluate_trades

        # Create enough bars for zones to form
        dates = pd.date_range("2026-01-01", periods=200, freq="15min")
        prices = [1.3000 + 0.001 * (i % 20 - 10) for i in range(200)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 0.001 for p in prices],
            "low": [p - 0.001 for p in prices],
            "close": prices,
            "tick_volume": 100,
        }, index=dates)
        data = {"M15": df}

        output = run_signal_engine(
            data, "M15",
            pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
            account_balance=1000.0,
            disabled_rules=["scalp_entry", "growth_addon", "tp_targets"],
        )

        result = evaluate_trades(output, "GBPUSD", initial_balance=1000.0)

        # Structure checks — may have 0 trades on synthetic data
        assert isinstance(result.trades, list)
        assert isinstance(result.metrics, dict)
        assert isinstance(result.signal_type_breakdown, dict)
        assert "by_zone_tf" in result.signal_type_breakdown
        assert "by_direction" in result.signal_type_breakdown
        assert "by_exit_reason" in result.signal_type_breakdown
        assert "by_bias_alignment" in result.signal_type_breakdown
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -x -q`
Expected: All tests pass (457+ existing + new evaluator tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_evaluator.py
git commit -m "test: add integration test for evaluator pipeline"
```

---
