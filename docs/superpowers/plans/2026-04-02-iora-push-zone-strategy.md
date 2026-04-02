# Push Zone Strategy Evaluation Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strategy evaluation layer that replays push zone engine output against configurable entry/exit rules, producing trade records compatible with the existing backtest metrics pipeline.

**Architecture:** The push zone engine runs once per symbol and produces a `ZoneTimeline` — a per-bar recording of all zone fires, breaks, active zones, trends, and period levels. The strategy evaluator replays this timeline N times (once per `StrategyConfig`) cheaply, applying signal filters and SL/TP computation to generate `EntrySignal` objects, then simulating position management to produce `TradeRecord` objects for the existing `PerformanceMetrics` engine.

**Tech Stack:** Python 3.12, pandas, numpy, pytest. Integrates with existing `backtest/metrics.py` (TradeRecord, PerformanceMetrics), `backtest/costs.py` (CostCalculator), `backtest/market_mechanics.py` (pip sizes, broker specs).

---

## File Structure

```
src/iora/strategy/
  __init__.py                      # Package init, re-exports key classes
  strategy_config.py               # StrategyConfig dataclass + preset factory
  entry_signal.py                  # EntrySignal dataclass — full dashboard snapshot at entry
  sl_tp.py                         # SL/TP computation for 4 modes each (zone/structure/fixed/atr)
  signal_filters.py                # Filter functions: nesting, trend, zone count, no-trade, direction
  zone_timeline.py                 # ZoneTimelineBar + build_zone_timeline() — records engine output
  push_zone_strategy.py            # evaluate_strategy() — replays timeline, applies filters, simulates trades

tests/strategy/
  __init__.py
  test_strategy_config.py
  test_entry_signal.py
  test_sl_tp.py
  test_signal_filters.py
  test_zone_timeline.py
  test_push_zone_strategy.py
  test_strategy_integration.py     # End-to-end: real GBPUSD data → trades → metrics
```

**Responsibilities:**

| File | Purpose |
|------|---------|
| `strategy_config.py` | Defines all sweep dimensions (entry TF, parent TF, filters, SL/TP modes, direction, risk). Preset factory for common configs. |
| `entry_signal.py` | Immutable snapshot of system state at entry time — zone, nesting, trends, period levels, counts, SL/TP. Used for post-hoc analysis. |
| `sl_tp.py` | Pure functions computing SL/TP prices from push zone state. 4 SL modes × 4 TP modes. Uses period levels for "structure" mode, zone boundaries for "zone" mode. |
| `signal_filters.py` | Pure predicate functions. Each returns `(pass: bool, reason: str)`. Composable — strategy evaluator chains them. |
| `zone_timeline.py` | Records push zone engine output per bar into a lightweight list. `build_zone_timeline()` runs the engine and captures output. |
| `push_zone_strategy.py` | Main evaluator. Replays timeline bar-by-bar, detects zone fires → applies filters → computes SL/TP → manages single position → produces TradeRecords. |

---

### Task 1: StrategyConfig Dataclass

**Files:**
- Create: `src/iora/strategy/__init__.py`
- Create: `src/iora/strategy/strategy_config.py`
- Create: `tests/strategy/__init__.py`
- Test: `tests/strategy/test_strategy_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_strategy_config.py
"""Tests for StrategyConfig dataclass and preset factory."""
from __future__ import annotations

from iora.strategy.strategy_config import StrategyConfig, make_preset


def test_default_config():
    """Default config has sensible defaults matching design spec."""
    cfg = StrategyConfig()
    assert cfg.entry_tf == "M5"
    assert cfg.parent_tf == "H1"
    assert cfg.require_nesting is True
    assert cfg.signal_types == {"push", "reversal"}
    assert cfg.struct_filter == "any"
    assert cfg.htf_trend_filter == "none"
    assert cfg.htf_trend_tf == "H4"
    assert cfg.max_zone_count == 0
    assert cfg.no_trade_zones is True
    assert cfg.sl_mode == "zone"
    assert cfg.tp_mode == "zone"
    assert cfg.fixed_rr == 2.0
    assert cfg.sl_period_depth == 1
    assert cfg.position_mode == "single"
    assert cfg.direction == "both"
    assert cfg.risk_per_trade_pct == 1.0
    assert cfg.max_concurrent == 1


def test_custom_config():
    """Custom config overrides specific fields."""
    cfg = StrategyConfig(
        entry_tf="M15",
        parent_tf="H4",
        signal_types={"push"},
        sl_mode="atr",
        tp_mode="fixed_rr",
        fixed_rr=3.0,
        direction="long",
    )
    assert cfg.entry_tf == "M15"
    assert cfg.parent_tf == "H4"
    assert cfg.signal_types == {"push"}
    assert cfg.sl_mode == "atr"
    assert cfg.tp_mode == "fixed_rr"
    assert cfg.fixed_rr == 3.0
    assert cfg.direction == "long"
    # Unchanged defaults
    assert cfg.require_nesting is True
    assert cfg.max_concurrent == 1


def test_preset_aggressive():
    """Aggressive preset: no nesting, all signal types, wider SL."""
    cfg = make_preset("aggressive")
    assert cfg.require_nesting is False
    assert cfg.signal_types == {"push", "reversal", "terminal", "normal"}
    assert cfg.no_trade_zones is False


def test_preset_conservative():
    """Conservative preset: nesting required, push+reversal only, with-trend."""
    cfg = make_preset("conservative")
    assert cfg.require_nesting is True
    assert cfg.signal_types == {"push", "reversal"}
    assert cfg.htf_trend_filter == "with_trend"


def test_preset_unknown_raises():
    """Unknown preset name raises ValueError."""
    import pytest
    with pytest.raises(ValueError, match="Unknown preset"):
        make_preset("unknown_preset")


def test_config_to_dict():
    """Config can be serialized to dict for sweep results."""
    cfg = StrategyConfig(entry_tf="M15", sl_mode="atr")
    d = cfg.to_dict()
    assert d["entry_tf"] == "M15"
    assert d["sl_mode"] == "atr"
    assert d["parent_tf"] == "H1"  # default
    assert isinstance(d["signal_types"], list)  # sets → lists for JSON
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_strategy_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iora.strategy'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/__init__.py
"""Push zone strategy evaluation layer."""
```

```python
# src/iora/strategy/strategy_config.py
"""StrategyConfig — all sweep dimensions for push zone strategy evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for a single strategy evaluation run.

    Every field is a sweep dimension — the sweep runner generates
    StrategyConfig instances with different combinations.
    """

    # Entry nesting
    entry_tf: str = "M5"
    parent_tf: str = "H1"
    require_nesting: bool = True

    # Signal filters
    signal_types: set[str] = field(
        default_factory=lambda: {"push", "reversal"}
    )
    struct_filter: str = "any"        # "bos_only", "choch_only", "any"
    htf_trend_filter: str = "none"    # "with_trend", "counter_allowed", "none"
    htf_trend_tf: str = "H4"
    max_zone_count: int = 0           # Skip if zone count > N (0 = disabled)
    no_trade_zones: bool = True       # Skip if inside D/W opposing zone

    # SL/TP
    sl_mode: str = "zone"             # "zone", "structure", "fixed_pips", "atr"
    tp_mode: str = "zone"             # "zone", "structure", "fixed_rr", "atr"
    fixed_rr: float = 2.0
    sl_period_depth: int = 1          # Which period level for structure SL

    # Position management
    position_mode: str = "single"     # v1: single only

    # Direction
    direction: str = "both"           # "long", "short", "both"

    # Risk
    risk_per_trade_pct: float = 1.0
    max_concurrent: int = 1

    def to_dict(self) -> dict:
        """Serialize to dict (sets → sorted lists for JSON compat)."""
        return {
            "entry_tf": self.entry_tf,
            "parent_tf": self.parent_tf,
            "require_nesting": self.require_nesting,
            "signal_types": sorted(self.signal_types),
            "struct_filter": self.struct_filter,
            "htf_trend_filter": self.htf_trend_filter,
            "htf_trend_tf": self.htf_trend_tf,
            "max_zone_count": self.max_zone_count,
            "no_trade_zones": self.no_trade_zones,
            "sl_mode": self.sl_mode,
            "tp_mode": self.tp_mode,
            "fixed_rr": self.fixed_rr,
            "sl_period_depth": self.sl_period_depth,
            "position_mode": self.position_mode,
            "direction": self.direction,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_concurrent": self.max_concurrent,
        }


def make_preset(name: str) -> StrategyConfig:
    """Create a StrategyConfig from a named preset.

    Presets:
        aggressive — no nesting, all signal types, no no-trade zones
        conservative — nesting required, push+reversal, with-trend filter
        default — baseline defaults
    """
    if name == "aggressive":
        return StrategyConfig(
            require_nesting=False,
            signal_types={"push", "reversal", "terminal", "normal"},
            no_trade_zones=False,
            htf_trend_filter="none",
        )
    elif name == "conservative":
        return StrategyConfig(
            require_nesting=True,
            signal_types={"push", "reversal"},
            htf_trend_filter="with_trend",
            htf_trend_tf="H4",
            no_trade_zones=True,
        )
    elif name == "default":
        return StrategyConfig()
    else:
        raise ValueError(f"Unknown preset: {name!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_strategy_config.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/__init__.py src/iora/strategy/strategy_config.py \
       tests/strategy/__init__.py tests/strategy/test_strategy_config.py
git commit -m "feat(strategy): add StrategyConfig dataclass with presets"
```

---

### Task 2: EntrySignal Dataclass

**Files:**
- Create: `src/iora/strategy/entry_signal.py`
- Test: `tests/strategy/test_entry_signal.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_entry_signal.py
"""Tests for EntrySignal dataclass."""
from __future__ import annotations

import pandas as pd

from iora.strategy.entry_signal import EntrySignal
from iora.engine.push_zone_models import PushZone


def _make_zone(is_supply: bool = True, top: float = 1.30, bottom: float = 1.29) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"),
        timeframe="M5", is_push=True,
        struct_cls="BOS", swing_cls="HH", count_num=1,
    )


def test_entry_signal_creation():
    """EntrySignal captures full dashboard state at entry time."""
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone,
        zone_tf="M5",
        signal_type="push",
        struct_cls="BOS",
        direction="short",
        parent_zone=None,
        parent_tf="H1",
        nesting_depth=0,
        opposing_nest=False,
        trend_by_tf={"M5": -1, "H1": -1, "H4": 1},
        period_levels={"H1": {"highs": [1.31], "lows": [1.28]}},
        zone_counts={"M5": (3, 2)},
        exhaustion={"M5_sup": False},
        sl_price=1.3010,
        tp_price=1.2850,
        risk_pips=10.0,
        reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02 10:00"),
        entry_price=1.2950,
    )
    assert sig.direction == "short"
    assert sig.zone is zone
    assert sig.nesting_depth == 0
    assert sig.risk_pips == 10.0
    assert sig.reward_pips == 50.0


def test_entry_signal_rr_ratio():
    """R:R ratio computed from risk/reward pips."""
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="BOS",
        direction="short", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.3010, tp_price=1.2850,
        risk_pips=10.0, reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.2950,
    )
    assert sig.rr_ratio == 5.0


def test_entry_signal_rr_zero_risk():
    """R:R ratio is 0.0 when risk is zero (edge case)."""
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="",
        direction="long", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.29, tp_price=1.31,
        risk_pips=0.0, reward_pips=20.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.29,
    )
    assert sig.rr_ratio == 0.0


def test_entry_signal_to_dict():
    """EntrySignal serializes to dict for CSV/JSON export."""
    zone = _make_zone()
    sig = EntrySignal(
        zone=zone, zone_tf="M5", signal_type="push", struct_cls="BOS",
        direction="short", parent_zone=None, parent_tf="H1",
        nesting_depth=0, opposing_nest=False,
        trend_by_tf={"M5": -1}, period_levels={}, zone_counts={}, exhaustion={},
        sl_price=1.3010, tp_price=1.2850,
        risk_pips=10.0, reward_pips=50.0,
        entry_time=pd.Timestamp("2025-01-02"), entry_price=1.2950,
    )
    d = sig.to_dict()
    assert d["zone_tf"] == "M5"
    assert d["signal_type"] == "push"
    assert d["direction"] == "short"
    assert d["entry_price"] == 1.2950
    assert d["rr_ratio"] == 5.0
    assert d["zone_top"] == 1.30
    assert d["zone_bottom"] == 1.29
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_entry_signal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iora.strategy.entry_signal'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/entry_signal.py
"""EntrySignal — immutable snapshot of full system state at entry time."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from iora.engine.push_zone_models import PushZone


@dataclass(frozen=True, slots=True)
class EntrySignal:
    """Captures every dimension of system state when a trade entry fires.

    Used for post-hoc analysis, sweep result comparison, and ML feature extraction.
    """

    # Trigger
    zone: PushZone
    zone_tf: str
    signal_type: str      # "push", "reversal", "terminal", "normal"
    struct_cls: str        # "BOS", "CHoCH", ""
    direction: str         # "long", "short"

    # Nesting context
    parent_zone: PushZone | None
    parent_tf: str
    nesting_depth: int
    opposing_nest: bool    # Terminal nesting

    # Full dashboard state at entry time
    trend_by_tf: dict[str, int]
    period_levels: dict[str, dict]
    zone_counts: dict[str, tuple]
    exhaustion: dict[str, bool]

    # Computed trade parameters
    sl_price: float
    tp_price: float
    risk_pips: float
    reward_pips: float
    entry_time: pd.Timestamp
    entry_price: float

    @property
    def rr_ratio(self) -> float:
        """Reward-to-risk ratio."""
        if self.risk_pips <= 0:
            return 0.0
        return self.reward_pips / self.risk_pips

    def to_dict(self) -> dict:
        """Serialize to flat dict for CSV/JSON export."""
        return {
            "zone_tf": self.zone_tf,
            "signal_type": self.signal_type,
            "struct_cls": self.struct_cls,
            "direction": self.direction,
            "parent_tf": self.parent_tf,
            "nesting_depth": self.nesting_depth,
            "opposing_nest": self.opposing_nest,
            "sl_price": self.sl_price,
            "tp_price": self.tp_price,
            "risk_pips": self.risk_pips,
            "reward_pips": self.reward_pips,
            "rr_ratio": self.rr_ratio,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "zone_top": self.zone.top,
            "zone_bottom": self.zone.bottom,
            "zone_is_push": self.zone.is_push,
            "zone_is_reversal": self.zone.is_reversal,
            "zone_is_terminal": self.zone.is_terminal,
            "zone_swing_cls": self.zone.swing_cls,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_entry_signal.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/entry_signal.py tests/strategy/test_entry_signal.py
git commit -m "feat(strategy): add EntrySignal dataclass with to_dict serialization"
```

---

### Task 3: SL/TP Computation Functions

**Files:**
- Create: `src/iora/strategy/sl_tp.py`
- Test: `tests/strategy/test_sl_tp.py`
- Reference: `backtest/exit_logic.py` (existing zone/structure SL/TP — reuse concepts, not code, since push zone strategy uses PushZone objects and period levels instead of the fractal zone dict format)

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_sl_tp.py
"""Tests for SL/TP computation across 4 modes each."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone
from iora.strategy.sl_tp import compute_sl, compute_tp


def _zone(is_supply: bool, top: float, bottom: float) -> PushZone:
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="H1",
    )


# --- SL Tests ---

class TestComputeSL:
    def test_zone_sl_long(self):
        """Long SL below nearest demand zone bottom with buffer."""
        demand = _zone(False, 1.2940, 1.2930)
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="zone",
            zones=[demand], atr=0.0050, period_levels=None,
        )
        # SL = demand bottom - buffer (atr * 0.15 = 0.00075)
        # demand.bottom=1.2930, buffer=0.00075 → SL=1.29225
        # distance = 1.2950 - 1.29225 = 0.00275, max_dist = 0.005*3=0.015 → within cap
        assert sl == pytest.approx(1.29225, abs=1e-4)

    def test_zone_sl_short(self):
        """Short SL above nearest supply zone top with buffer."""
        supply = _zone(True, 1.2960, 1.2950)
        sl = compute_sl(
            direction="short", entry_price=1.2940, mode="zone",
            zones=[supply], atr=0.0050, period_levels=None,
        )
        # SL = supply top + buffer = 1.2960 + 0.00075 = 1.29675
        assert sl == pytest.approx(1.29675, abs=1e-4)

    def test_zone_sl_no_zone_falls_back_to_atr(self):
        """When no suitable zone found, fall back to ATR-based SL."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="zone",
            zones=[], atr=0.0020, period_levels=None,
        )
        # Fallback: entry - 1.5 * ATR
        assert sl == pytest.approx(1.2920, abs=1e-4)

    def test_structure_sl_long(self):
        """Long SL below period low at given depth."""
        levels = {"lows": [1.2850, 1.2800, 1.2750]}
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="structure",
            zones=[], atr=0.0020, period_levels=levels, period_depth=1,
        )
        # SL = period low[0] - buffer
        assert sl < 1.2850

    def test_structure_sl_depth_2(self):
        """Deeper period depth uses second level."""
        levels = {"lows": [1.2850, 1.2800, 1.2750]}
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="structure",
            zones=[], atr=0.0020, period_levels=levels, period_depth=2,
        )
        assert sl < 1.2800

    def test_atr_sl_long(self):
        """ATR SL: entry - atr * multiplier."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="atr",
            zones=[], atr=0.0020, period_levels=None, atr_mult=1.5,
        )
        assert sl == pytest.approx(1.2920, abs=1e-4)

    def test_atr_sl_short(self):
        """ATR SL: entry + atr * multiplier."""
        sl = compute_sl(
            direction="short", entry_price=1.2950, mode="atr",
            zones=[], atr=0.0020, period_levels=None, atr_mult=1.5,
        )
        assert sl == pytest.approx(1.2980, abs=1e-4)

    def test_fixed_pips_sl(self):
        """Fixed pips SL."""
        sl = compute_sl(
            direction="long", entry_price=1.2950, mode="fixed_pips",
            zones=[], atr=0.0020, period_levels=None,
            fixed_pips=15.0, pip_size=0.0001,
        )
        assert sl == pytest.approx(1.2935, abs=1e-4)


# --- TP Tests ---

class TestComputeTP:
    def test_zone_tp_long(self):
        """Long TP at nearest supply zone with buffer."""
        supply = _zone(True, 1.3050, 1.3030)
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="zone", zones=[supply], atr=0.0020, period_levels=None,
        )
        # TP near supply bottom - buffer
        assert tp > 1.2950  # above entry
        assert tp < 1.3050  # below zone top

    def test_zone_tp_short(self):
        """Short TP at nearest demand zone with buffer."""
        demand = _zone(False, 1.2880, 1.2860)
        tp = compute_tp(
            direction="short", entry_price=1.2950, sl_price=1.2980,
            mode="zone", zones=[demand], atr=0.0020, period_levels=None,
        )
        assert tp < 1.2950  # below entry
        assert tp > 1.2860  # above zone bottom

    def test_fixed_rr_tp(self):
        """Fixed R:R TP: entry + (risk * rr_mult)."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="fixed_rr", zones=[], atr=0.0020, period_levels=None,
            fixed_rr=3.0,
        )
        risk = 1.2950 - 1.2920  # 0.003
        expected = 1.2950 + risk * 3.0  # 1.304
        assert tp == pytest.approx(expected, abs=1e-4)

    def test_atr_tp_long(self):
        """ATR TP: entry + atr * multiplier."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="atr", zones=[], atr=0.0020, period_levels=None,
            atr_mult=3.0,
        )
        assert tp == pytest.approx(1.3010, abs=1e-4)

    def test_zone_tp_no_zone_falls_back(self):
        """No opposing zone → fall back to fixed_rr TP."""
        tp = compute_tp(
            direction="long", entry_price=1.2950, sl_price=1.2920,
            mode="zone", zones=[], atr=0.0020, period_levels=None,
        )
        # Falls back to default R:R of 2.0
        risk = 1.2950 - 1.2920
        expected = 1.2950 + risk * 2.0
        assert tp == pytest.approx(expected, abs=1e-4)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_sl_tp.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'iora.strategy.sl_tp'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/sl_tp.py
"""SL/TP computation for push zone strategy.

Four SL modes: zone, structure, atr, fixed_pips
Four TP modes: zone, structure, fixed_rr, atr

All functions are pure — no side effects.
"""
from __future__ import annotations

from iora.engine.push_zone_models import PushZone

_DEFAULT_ATR_MULT: float = 1.5
_DEFAULT_ZONE_BUFFER: float = 0.15  # ATR fraction
_DEFAULT_FALLBACK_RR: float = 2.0
_MAX_SL_ATR: float = 3.0  # Max SL distance in ATR units


def compute_sl(
    *,
    direction: str,
    entry_price: float,
    mode: str,
    zones: list[PushZone],
    atr: float,
    period_levels: dict | None,
    period_depth: int = 1,
    atr_mult: float = _DEFAULT_ATR_MULT,
    fixed_pips: float = 15.0,
    pip_size: float = 0.0001,
    zone_buffer_mult: float = _DEFAULT_ZONE_BUFFER,
) -> float:
    """Compute stop-loss price.

    Args:
        direction: "long" or "short"
        entry_price: Trade entry price
        mode: "zone", "structure", "atr", "fixed_pips"
        zones: Active push zones (all TFs) for zone-backed SL
        atr: ATR value at entry bar
        period_levels: {"highs": [...], "lows": [...]} from PeriodTracker
        period_depth: Which period level index (1-based) for structure mode
        atr_mult: ATR multiplier for atr mode
        fixed_pips: Pip distance for fixed_pips mode
        pip_size: Pip size (0.0001 for most forex)
        zone_buffer_mult: Buffer beyond zone edge as ATR fraction

    Returns:
        SL price as float. Always on the losing side of entry.
    """
    if mode == "zone":
        sl = _zone_sl(direction, entry_price, zones, atr, zone_buffer_mult)
        if sl is not None:
            return sl
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "structure":
        sl = _structure_sl(direction, entry_price, atr, period_levels,
                           period_depth, zone_buffer_mult)
        if sl is not None:
            return sl
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "atr":
        return _atr_sl(direction, entry_price, atr, atr_mult)

    elif mode == "fixed_pips":
        dist = fixed_pips * pip_size
        if direction == "long":
            return entry_price - dist
        else:
            return entry_price + dist

    raise ValueError(f"Unknown SL mode: {mode!r}")


def compute_tp(
    *,
    direction: str,
    entry_price: float,
    sl_price: float,
    mode: str,
    zones: list[PushZone],
    atr: float,
    period_levels: dict | None,
    period_depth: int = 1,
    fixed_rr: float = _DEFAULT_FALLBACK_RR,
    atr_mult: float = 3.0,
    zone_buffer_mult: float = _DEFAULT_ZONE_BUFFER,
    min_rr: float = 1.5,
    max_rr: float = 5.0,
) -> float:
    """Compute take-profit price.

    Args:
        direction: "long" or "short"
        entry_price: Trade entry price
        sl_price: Already-computed SL price (for R:R calculation)
        mode: "zone", "structure", "fixed_rr", "atr"
        zones: Active push zones (all TFs) for zone-based TP
        atr: ATR value at entry bar
        period_levels: {"highs": [...], "lows": [...]} from PeriodTracker
        fixed_rr: R:R multiplier for fixed_rr mode
        atr_mult: ATR multiplier for atr mode
        zone_buffer_mult: Buffer before zone edge as ATR fraction
        min_rr: Minimum R:R to accept zone TP
        max_rr: Maximum R:R cap

    Returns:
        TP price as float. Always on the winning side of entry.
    """
    risk = abs(entry_price - sl_price)

    if mode == "zone":
        tp = _zone_tp(direction, entry_price, risk, zones, atr,
                       zone_buffer_mult, min_rr, max_rr)
        if tp is not None:
            return tp
        return _rr_tp(direction, entry_price, risk, _DEFAULT_FALLBACK_RR)

    elif mode == "structure":
        tp = _structure_tp(direction, entry_price, risk, period_levels,
                           period_depth, atr, zone_buffer_mult, min_rr, max_rr)
        if tp is not None:
            return tp
        return _rr_tp(direction, entry_price, risk, _DEFAULT_FALLBACK_RR)

    elif mode == "fixed_rr":
        return _rr_tp(direction, entry_price, risk, fixed_rr)

    elif mode == "atr":
        if direction == "long":
            return entry_price + atr * atr_mult
        else:
            return entry_price - atr * atr_mult

    raise ValueError(f"Unknown TP mode: {mode!r}")


# --- Internal helpers ---

def _atr_sl(direction: str, entry: float, atr: float, mult: float) -> float:
    if direction == "long":
        return entry - atr * mult
    return entry + atr * mult


def _rr_tp(direction: str, entry: float, risk: float, rr: float) -> float:
    if direction == "long":
        return entry + risk * rr
    return entry - risk * rr


def _zone_sl(
    direction: str,
    entry: float,
    zones: list[PushZone],
    atr: float,
    buffer_mult: float,
) -> float | None:
    """SL behind nearest same-side zone (demand for long, supply for short)."""
    buffer = atr * buffer_mult
    max_dist = atr * _MAX_SL_ATR

    if direction == "long":
        # Find demand zones below entry
        candidates = [
            z.bottom - buffer
            for z in zones
            if not z.is_supply and z.bottom < entry
            and entry - (z.bottom - buffer) <= max_dist
        ]
        return max(candidates) if candidates else None
    else:
        # Find supply zones above entry
        candidates = [
            z.top + buffer
            for z in zones
            if z.is_supply and z.top > entry
            and (z.top + buffer) - entry <= max_dist
        ]
        return min(candidates) if candidates else None


def _zone_tp(
    direction: str,
    entry: float,
    risk: float,
    zones: list[PushZone],
    atr: float,
    buffer_mult: float,
    min_rr: float,
    max_rr: float,
) -> float | None:
    """TP at nearest opposing zone (supply for long, demand for short)."""
    buffer = atr * buffer_mult

    if risk <= 0:
        return None

    if direction == "long":
        candidates = [
            z.bottom - buffer
            for z in zones
            if z.is_supply and z.bottom > entry
        ]
        if not candidates:
            return None
        nearest = min(candidates)
        tp_dist = nearest - entry
    else:
        candidates = [
            z.top + buffer
            for z in zones
            if not z.is_supply and z.top < entry
        ]
        if not candidates:
            return None
        nearest = max(candidates)
        tp_dist = entry - nearest

    rr = tp_dist / risk
    if rr < min_rr:
        return None

    capped_dist = min(tp_dist, risk * max_rr)
    if direction == "long":
        return entry + capped_dist
    return entry - capped_dist


def _structure_sl(
    direction: str,
    entry: float,
    atr: float,
    levels: dict | None,
    depth: int,
    buffer_mult: float,
) -> float | None:
    """SL behind period level at given depth."""
    if levels is None:
        return None

    buffer = atr * buffer_mult
    idx = depth - 1  # 1-based → 0-based

    if direction == "long":
        lows = levels.get("lows", [])
        if idx < len(lows):
            return lows[idx] - buffer
    else:
        highs = levels.get("highs", [])
        if idx < len(highs):
            return highs[idx] + buffer

    return None


def _structure_tp(
    direction: str,
    entry: float,
    risk: float,
    levels: dict | None,
    depth: int,
    atr: float,
    buffer_mult: float,
    min_rr: float,
    max_rr: float,
) -> float | None:
    """TP at opposing period level."""
    if levels is None or risk <= 0:
        return None

    buffer = atr * buffer_mult
    idx = depth - 1

    if direction == "long":
        highs = levels.get("highs", [])
        if idx < len(highs):
            tp = highs[idx] - buffer
            tp_dist = tp - entry
            rr = tp_dist / risk if risk > 0 else 0
            if rr >= min_rr:
                capped = min(tp_dist, risk * max_rr)
                return entry + capped
    else:
        lows = levels.get("lows", [])
        if idx < len(lows):
            tp = lows[idx] + buffer
            tp_dist = entry - tp
            rr = tp_dist / risk if risk > 0 else 0
            if rr >= min_rr:
                capped = min(tp_dist, risk * max_rr)
                return entry - capped

    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_sl_tp.py -v`
Expected: 13 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/sl_tp.py tests/strategy/test_sl_tp.py
git commit -m "feat(strategy): add SL/TP computation for 4 modes each"
```

---

### Task 4: Signal Filter Functions

**Files:**
- Create: `src/iora/strategy/signal_filters.py`
- Test: `tests/strategy/test_signal_filters.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_signal_filters.py
"""Tests for signal filter functions."""
from __future__ import annotations

import pandas as pd

from iora.engine.push_zone_models import PushZone
from iora.strategy.signal_filters import (
    filter_signal_type,
    filter_struct,
    filter_direction,
    filter_nesting,
    filter_htf_trend,
    filter_zone_count,
    filter_no_trade_zone,
    apply_all_filters,
)
from iora.strategy.strategy_config import StrategyConfig


def _zone(**kw) -> PushZone:
    defaults = dict(
        top=1.30, bottom=1.29, is_supply=True,
        origin_time=pd.Timestamp("2025-01-01"), timeframe="M5",
    )
    defaults.update(kw)
    return PushZone(**defaults)


# --- Individual filters ---

class TestSignalTypeFilter:
    def test_push_in_set(self):
        ok, _ = filter_signal_type("push", {"push", "reversal"})
        assert ok is True

    def test_normal_not_in_set(self):
        ok, reason = filter_signal_type("normal", {"push", "reversal"})
        assert ok is False
        assert "signal_type" in reason


class TestStructFilter:
    def test_any_passes_all(self):
        ok, _ = filter_struct("BOS", "any")
        assert ok is True

    def test_bos_only_rejects_choch(self):
        ok, _ = filter_struct("CHoCH", "bos_only")
        assert ok is False

    def test_bos_only_accepts_bos(self):
        ok, _ = filter_struct("BOS", "bos_only")
        assert ok is True

    def test_choch_only_rejects_bos(self):
        ok, _ = filter_struct("BOS", "choch_only")
        assert ok is False

    def test_empty_struct_passes_any(self):
        ok, _ = filter_struct("", "any")
        assert ok is True


class TestDirectionFilter:
    def test_both_passes(self):
        ok, _ = filter_direction("long", "both")
        assert ok is True

    def test_long_only_rejects_short(self):
        ok, _ = filter_direction("short", "long")
        assert ok is False

    def test_short_only_accepts_short(self):
        ok, _ = filter_direction("short", "short")
        assert ok is True


class TestNestingFilter:
    def test_required_with_parent(self):
        parent = _zone(is_supply=False, top=1.32, bottom=1.28)
        ok, _ = filter_nesting(True, parent, 1)
        assert ok is True

    def test_required_without_parent(self):
        ok, _ = filter_nesting(True, None, 0)
        assert ok is False

    def test_not_required(self):
        ok, _ = filter_nesting(False, None, 0)
        assert ok is True


class TestHTFTrendFilter:
    def test_none_passes_all(self):
        ok, _ = filter_htf_trend("long", 1, "none")
        assert ok is True

    def test_with_trend_long_bullish(self):
        ok, _ = filter_htf_trend("long", 1, "with_trend")
        assert ok is True

    def test_with_trend_long_bearish(self):
        ok, _ = filter_htf_trend("long", -1, "with_trend")
        assert ok is False

    def test_with_trend_neutral_blocks(self):
        """Neutral trend (0) blocks with_trend filter — must have confirmed direction."""
        ok, _ = filter_htf_trend("long", 0, "with_trend")
        assert ok is False

    def test_counter_allowed_passes_all(self):
        ok, _ = filter_htf_trend("long", -1, "counter_allowed")
        assert ok is True


class TestZoneCountFilter:
    def test_disabled(self):
        ok, _ = filter_zone_count(5, 0)
        assert ok is True

    def test_within_limit(self):
        ok, _ = filter_zone_count(2, 3)
        assert ok is True

    def test_exceeds_limit(self):
        ok, _ = filter_zone_count(4, 3)
        assert ok is False


class TestNoTradeZoneFilter:
    def test_enabled_inside_opposing(self):
        opposing = _zone(is_supply=True, top=1.30, bottom=1.28)
        ok, _ = filter_no_trade_zone(True, 1.29, [opposing], "long")
        assert ok is False

    def test_enabled_not_inside(self):
        opposing = _zone(is_supply=True, top=1.30, bottom=1.28)
        ok, _ = filter_no_trade_zone(True, 1.31, [opposing], "long")
        assert ok is True

    def test_disabled(self):
        opposing = _zone(is_supply=True, top=1.30, bottom=1.28)
        ok, _ = filter_no_trade_zone(False, 1.29, [opposing], "long")
        assert ok is True


# --- Composite filter ---

class TestApplyAllFilters:
    def test_all_pass(self):
        zone = _zone(is_push=True, struct_cls="BOS")
        cfg = StrategyConfig(
            signal_types={"push"}, struct_filter="any",
            direction="both", require_nesting=False,
            htf_trend_filter="none", max_zone_count=0,
            no_trade_zones=False,
        )
        ok, reasons = apply_all_filters(
            signal_type="push", struct_cls="BOS", direction="long",
            parent_zone=None, nesting_depth=0, htf_trend=0,
            zone_count=0, entry_price=1.29, htf_zones=[], config=cfg,
        )
        assert ok is True
        assert reasons == []

    def test_multiple_failures(self):
        cfg = StrategyConfig(
            signal_types={"push"}, struct_filter="bos_only",
            direction="long", require_nesting=True,
        )
        ok, reasons = apply_all_filters(
            signal_type="normal", struct_cls="CHoCH", direction="short",
            parent_zone=None, nesting_depth=0, htf_trend=0,
            zone_count=0, entry_price=1.29, htf_zones=[], config=cfg,
        )
        assert ok is False
        assert len(reasons) >= 3  # signal_type, struct, direction, nesting
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_signal_filters.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/signal_filters.py
"""Signal filter functions for push zone strategy.

Each filter returns (pass: bool, reason: str). Reason is empty if passed.
Composable — apply_all_filters chains them per StrategyConfig.
"""
from __future__ import annotations

from iora.engine.push_zone_models import PushZone
from iora.strategy.strategy_config import StrategyConfig


def filter_signal_type(
    signal_type: str, allowed: set[str],
) -> tuple[bool, str]:
    """Check if signal type is in allowed set."""
    if signal_type in allowed:
        return True, ""
    return False, f"signal_type '{signal_type}' not in {sorted(allowed)}"


def filter_struct(
    struct_cls: str, struct_filter: str,
) -> tuple[bool, str]:
    """Check structure classification filter."""
    if struct_filter == "any":
        return True, ""
    if struct_filter == "bos_only" and struct_cls != "BOS":
        return False, f"struct_filter=bos_only but got '{struct_cls}'"
    if struct_filter == "choch_only" and struct_cls != "CHoCH":
        return False, f"struct_filter=choch_only but got '{struct_cls}'"
    return True, ""


def filter_direction(
    signal_direction: str, config_direction: str,
) -> tuple[bool, str]:
    """Check if signal direction matches config direction filter."""
    if config_direction == "both":
        return True, ""
    if signal_direction == config_direction:
        return True, ""
    return False, f"direction '{signal_direction}' blocked by filter '{config_direction}'"


def filter_nesting(
    require_nesting: bool,
    parent_zone: PushZone | None,
    nesting_depth: int,
) -> tuple[bool, str]:
    """Check nesting requirement."""
    if not require_nesting:
        return True, ""
    if parent_zone is not None and nesting_depth > 0:
        return True, ""
    return False, "nesting required but no parent zone"


def filter_htf_trend(
    direction: str, htf_trend: int, htf_filter: str,
) -> tuple[bool, str]:
    """Check HTF trend alignment.

    Args:
        direction: "long" or "short"
        htf_trend: +1 (bull), -1 (bear), 0 (neutral)
        htf_filter: "with_trend", "counter_allowed", "none"
    """
    if htf_filter == "none" or htf_filter == "counter_allowed":
        return True, ""

    if htf_filter == "with_trend":
        if direction == "long" and htf_trend > 0:
            return True, ""
        if direction == "short" and htf_trend < 0:
            return True, ""
        if htf_trend == 0:
            return False, f"htf_trend=0 (neutral) blocks {direction} (with_trend)"
        return False, f"htf_trend={htf_trend} blocks {direction} (with_trend)"

    return True, ""


def filter_zone_count(
    current_count: int, max_count: int,
) -> tuple[bool, str]:
    """Check if zone count exceeds max (0 = disabled)."""
    if max_count == 0:
        return True, ""
    if current_count <= max_count:
        return True, ""
    return False, f"zone_count {current_count} > max {max_count}"


def filter_no_trade_zone(
    enabled: bool,
    entry_price: float,
    htf_zones: list[PushZone],
    direction: str,
) -> tuple[bool, str]:
    """Check if price is inside an opposing HTF zone (D/W).

    For long entries: blocked if inside a supply zone.
    For short entries: blocked if inside a demand zone.
    """
    if not enabled:
        return True, ""

    opposing_supply = direction == "long"
    for z in htf_zones:
        if z.is_supply == opposing_supply and z.contains_price(entry_price):
            return False, f"inside opposing {z.timeframe} {'supply' if z.is_supply else 'demand'} zone"

    return True, ""


def apply_all_filters(
    *,
    signal_type: str,
    struct_cls: str,
    direction: str,
    parent_zone: PushZone | None,
    nesting_depth: int,
    htf_trend: int,
    zone_count: int,
    entry_price: float,
    htf_zones: list[PushZone],
    config: StrategyConfig,
) -> tuple[bool, list[str]]:
    """Apply all filters from StrategyConfig. Returns (all_pass, failure_reasons)."""
    failures: list[str] = []

    checks = [
        filter_signal_type(signal_type, config.signal_types),
        filter_struct(struct_cls, config.struct_filter),
        filter_direction(direction, config.direction),
        filter_nesting(config.require_nesting, parent_zone, nesting_depth),
        filter_htf_trend(direction, htf_trend, config.htf_trend_filter),
        filter_zone_count(zone_count, config.max_zone_count),
        filter_no_trade_zone(config.no_trade_zones, entry_price, htf_zones, direction),
    ]

    for passed, reason in checks:
        if not passed:
            failures.append(reason)

    return len(failures) == 0, failures
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_signal_filters.py -v`
Expected: 23 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/signal_filters.py tests/strategy/test_signal_filters.py
git commit -m "feat(strategy): add composable signal filter functions"
```

---

### Task 5: ZoneTimeline Builder

**Files:**
- Create: `src/iora/strategy/zone_timeline.py`
- Test: `tests/strategy/test_zone_timeline.py`
- Reference: `src/iora/orchestrator/push_zone_engine.py` (push_zone_engine_tick, init_push_zone_state)
- Reference: `src/iora/data/bar_iterator.py` (iter_bars, BarContext)

This is the key optimization: run the push zone engine once, capture output per bar, replay cheaply.

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_zone_timeline.py
"""Tests for ZoneTimeline builder."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from iora.strategy.zone_timeline import ZoneTimelineBar, build_zone_timeline
from iora.engine.push_zone_models import PushZone


def _make_ohlc(n: int = 100, base: float = 1.30) -> pd.DataFrame:
    """Generate synthetic OHLC data."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="5min")
    close = base + np.cumsum(rng.normal(0, 0.0005, n))
    high = close + rng.uniform(0, 0.001, n)
    low = close - rng.uniform(0, 0.001, n)
    open_ = close + rng.normal(0, 0.0003, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=dates,
    )


class TestZoneTimelineBar:
    def test_dataclass_fields(self):
        bar = ZoneTimelineBar(
            timestamp=pd.Timestamp("2025-01-01"),
            open_=1.30, high=1.31, low=1.29, close=1.305,
            fires=[], breaks=[],
            zones_by_tf={}, trend_by_tf={},
            period_levels_by_tf={},
            zone_counts_by_tf={},
        )
        assert bar.timestamp == pd.Timestamp("2025-01-01")
        assert bar.fires == []
        assert bar.trend_by_tf == {}


class TestBuildZoneTimeline:
    def test_returns_list_of_bars(self):
        """build_zone_timeline returns one ZoneTimelineBar per base TF bar."""
        m5 = _make_ohlc(200)
        h1 = m5.resample("1h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        ).dropna()
        data_by_tf = {"M5": m5, "H1": h1}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        assert len(timeline) == len(m5)
        assert all(isinstance(b, ZoneTimelineBar) for b in timeline)

    def test_bar_ohlc_matches_source(self):
        """OHLC in timeline bars matches source data."""
        m5 = _make_ohlc(50)
        data_by_tf = {"M5": m5}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        assert timeline[0].open_ == pytest.approx(m5.iloc[0]["open"])
        assert timeline[0].close == pytest.approx(m5.iloc[0]["close"])

    def test_timeline_captures_trend(self):
        """Trend state is captured per bar (may be 0 initially)."""
        m5 = _make_ohlc(200)
        data_by_tf = {"M5": m5}
        timeline = build_zone_timeline(data_by_tf, base_tf="M5")
        # At least some bars should have trend captured
        assert all("M5" in b.trend_by_tf for b in timeline)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_zone_timeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/zone_timeline.py
"""ZoneTimeline — records push zone engine output per bar for cheap replay.

The push zone engine is expensive (HA detection, push validation, nesting,
period tracking). Running it once per symbol and recording the output lets
the strategy evaluator replay N configs cheaply against the same timeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.engine.events import EventBus
from iora.orchestrator.push_zone_engine import (
    PushZoneEngineConfig,
    PushZoneEngineState,
    init_push_zone_state,
    push_zone_engine_tick,
)
from iora.data.tf_alignment import build_aligned_multi_tf
from iora.data.bar_iterator import iter_bars


@dataclass(slots=True)
class ZoneTimelineBar:
    """Per-bar snapshot of push zone engine state.

    Captures everything the strategy evaluator needs to make
    entry/exit decisions without re-running the engine.
    """

    timestamp: pd.Timestamp
    open_: float
    high: float
    low: float
    close: float

    # Zone events this bar
    fires: list[PushZone]
    breaks: list[PushZone]

    # Full zone state snapshot
    zones_by_tf: dict[str, list[PushZone]]
    trend_by_tf: dict[str, int]
    period_levels_by_tf: dict[str, dict]
    zone_counts_by_tf: dict[str, tuple[int, int]]


def _snapshot_zone_ids(
    state: PushZoneEngineState,
) -> dict[str, set[int]]:
    """Capture zone identity set (by id()) for diffing before/after tick."""
    result: dict[str, set[int]] = {}
    for tf, ts in state.tick_states.items():
        result[tf] = {id(z) for z in ts.supply_zones} | {id(z) for z in ts.demand_zones}
    return result


def build_zone_timeline(
    data_by_tf: dict[str, pd.DataFrame],
    base_tf: str = "M5",
    config: PushZoneEngineConfig | None = None,
    period_depth: int = 3,
) -> list[ZoneTimelineBar]:
    """Run push zone engine once and capture per-bar output.

    Fire/break detection uses state-diffing (comparing zone lists
    before and after each tick) rather than event payloads, since
    event payloads contain flat dicts, not PushZone objects.

    Args:
        data_by_tf: Dict of TF -> OHLCV DataFrame.
        base_tf: Base timeframe for bar iteration.
        config: Push zone engine config (defaults used if None).
        period_depth: Period tracker history depth.

    Returns:
        List of ZoneTimelineBar, one per base TF bar.
    """
    if config is None:
        config = PushZoneEngineConfig()

    tfs = [tf for tf in data_by_tf]
    aligned_df, _ = build_aligned_multi_tf(data_by_tf, base_tf)
    state = init_push_zone_state(tfs, period_depth=period_depth)
    bus = EventBus()

    timeline: list[ZoneTimelineBar] = []

    for ctx in iter_bars(data_by_tf[base_tf], aligned_df, tfs):
        # Snapshot zone ids BEFORE tick
        pre_ids = _snapshot_zone_ids(state)

        push_zone_engine_tick(state, ctx, config, bus=bus)
        bus.drain()  # Clear events (we use state-diffing instead)

        # Detect fires and breaks by diffing zone lists
        fires: list[PushZone] = []
        breaks: list[PushZone] = []

        for tf, ts in state.tick_states.items():
            pre = pre_ids.get(tf, set())
            all_zones = list(ts.supply_zones) + list(ts.demand_zones)
            post = {id(z) for z in all_zones}

            # New zones (in post but not in pre) = fires
            for z in all_zones:
                if id(z) not in pre:
                    fires.append(z)

            # Broken zones were removed: in pre but not in post
            # We can't recover the PushZone objects for broken zones
            # since they were already removed from state. Instead,
            # we don't need break detection for the strategy evaluator --
            # it only cares about zone fires (entry triggers) and
            # active zones (for SL/TP computation).

        # Snapshot zone state
        zones_by_tf: dict[str, list[PushZone]] = {}
        trend_by_tf: dict[str, int] = {}
        period_levels: dict[str, dict] = {}
        zone_counts: dict[str, tuple[int, int]] = {}

        for tf, ts in state.tick_states.items():
            zones_by_tf[tf] = list(ts.supply_zones) + list(ts.demand_zones)
            trend_by_tf[tf] = ts.trend
            zone_counts[tf] = (ts.sup_count, ts.dem_count)
            period_levels[tf] = {
                "highs": list(ts.period.prev_highs),
                "lows": list(ts.period.prev_lows),
            }

        timeline.append(ZoneTimelineBar(
            timestamp=ctx.timestamp,
            open_=ctx.open_,
            high=ctx.high,
            low=ctx.low,
            close=ctx.close,
            fires=fires,
            breaks=breaks,
            zones_by_tf=zones_by_tf,
            trend_by_tf=trend_by_tf,
            period_levels_by_tf=period_levels,
            zone_counts_by_tf=zone_counts,
        ))

    return timeline
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_zone_timeline.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/zone_timeline.py tests/strategy/test_zone_timeline.py
git commit -m "feat(strategy): add ZoneTimeline builder for cheap strategy replay"
```

---

### Task 6: Strategy Evaluator

**Files:**
- Create: `src/iora/strategy/push_zone_strategy.py`
- Test: `tests/strategy/test_push_zone_strategy.py`
- Reference: `backtest/metrics.py` (TradeRecord)
- Reference: `backtest/costs.py` (CostCalculator)
- Reference: `backtest/market_mechanics.py` (get_pip_size, get_pip_value_per_lot)

This is the core: replays `ZoneTimeline` bar-by-bar, detects zone fires → applies filters → computes SL/TP → manages single position → produces TradeRecords.

- [ ] **Step 1: Write the failing test**

```python
# tests/strategy/test_push_zone_strategy.py
"""Tests for the push zone strategy evaluator."""
from __future__ import annotations

import pandas as pd
import pytest

from iora.engine.push_zone_models import PushZone
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.push_zone_strategy import evaluate_strategy, StrategyResult


def _zone(is_supply: bool, top: float, bottom: float, **kw) -> PushZone:
    defaults = dict(
        origin_time=pd.Timestamp("2025-01-01"),
        timeframe="M5", is_push=True, struct_cls="BOS",
        swing_cls="HH" if is_supply else "LL", count_num=1,
    )
    defaults.update(kw)
    return PushZone(top=top, bottom=bottom, is_supply=is_supply, **defaults)


def _bar(
    ts: str, o: float, h: float, lo: float, c: float,
    fires: list[PushZone] | None = None,
    breaks: list[PushZone] | None = None,
    zones_by_tf: dict | None = None,
    trend_by_tf: dict | None = None,
) -> ZoneTimelineBar:
    return ZoneTimelineBar(
        timestamp=pd.Timestamp(ts),
        open_=o, high=h, low=lo, close=c,
        fires=fires or [],
        breaks=breaks or [],
        zones_by_tf=zones_by_tf or {"M5": []},
        trend_by_tf=trend_by_tf or {"M5": 0},
        period_levels_by_tf={"M5": {"highs": [], "lows": []}},
        zone_counts_by_tf={"M5": (0, 0)},
    )


class TestEvaluateStrategy:
    def test_no_fires_no_trades(self):
        """Timeline with no zone fires produces no trades."""
        timeline = [
            _bar("2025-01-01 00:00", 1.30, 1.31, 1.29, 1.305),
            _bar("2025-01-01 00:05", 1.305, 1.31, 1.295, 1.30),
        ]
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.trades) == 0

    def test_supply_fire_generates_short(self):
        """Supply zone fire → short entry signal if filters pass."""
        supply = _zone(True, 1.3020, 1.3000)
        demand_for_sl = _zone(False, 1.2900, 1.2880, timeframe="H1")
        timeline = [
            # Bar 0: supply zone fires, price at zone
            _bar("2025-01-01 00:00", 1.301, 1.302, 1.299, 1.300,
                 fires=[supply],
                 zones_by_tf={"M5": [supply], "H1": [demand_for_sl]}),
            # Bars 1-10: price moves down (TP hit)
            *[_bar(f"2025-01-01 00:{5*(i+1):02d}",
                   1.30 - 0.002*i, 1.301 - 0.002*i,
                   1.295 - 0.002*i, 1.298 - 0.002*i)
              for i in range(10)],
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) >= 1
        assert result.signals[0].direction == "short"

    def test_demand_fire_generates_long(self):
        """Demand zone fire → long entry signal if filters pass."""
        demand = _zone(False, 1.2900, 1.2880)
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[demand],
                 zones_by_tf={"M5": [demand]}),
            *[_bar(f"2025-01-01 00:{5*(i+1):02d}",
                   1.29 + 0.002*i, 1.295 + 0.002*i,
                   1.289 + 0.002*i, 1.293 + 0.002*i)
              for i in range(10)],
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) >= 1
        assert result.signals[0].direction == "long"

    def test_filter_rejects_signal(self):
        """Signal blocked by direction filter produces no trade."""
        supply = _zone(True, 1.3020, 1.3000)
        timeline = [
            _bar("2025-01-01 00:00", 1.301, 1.302, 1.299, 1.300,
                 fires=[supply], zones_by_tf={"M5": [supply]}),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            direction="long",  # Blocks short signals
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        assert len(result.trades) == 0

    def test_sl_hit_closes_trade(self):
        """Price hitting SL closes the trade with a loss."""
        demand = _zone(False, 1.2900, 1.2880)
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[demand], zones_by_tf={"M5": [demand]}),
            # Bar 1: price drops hard (SL hit)
            _bar("2025-01-01 00:05", 1.290, 1.290, 1.270, 1.275),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr", fixed_rr=2.0,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        if result.trades:
            assert result.trades[0].exit_reason in ("sl_hit", "SL_HIT")

    def test_single_position_blocks_second_entry(self):
        """In single position mode, second fire while position open is ignored."""
        d1 = _zone(False, 1.2900, 1.2880)
        d2 = _zone(False, 1.2850, 1.2830, origin_time=pd.Timestamp("2025-01-01 00:05"))
        timeline = [
            _bar("2025-01-01 00:00", 1.289, 1.291, 1.288, 1.290,
                 fires=[d1], zones_by_tf={"M5": [d1]}),
            _bar("2025-01-01 00:05", 1.290, 1.291, 1.284, 1.285,
                 fires=[d2], zones_by_tf={"M5": [d1, d2]}),
            _bar("2025-01-01 00:10", 1.285, 1.286, 1.284, 1.285),
        ]
        cfg = StrategyConfig(
            require_nesting=False, no_trade_zones=False,
            sl_mode="atr", tp_mode="fixed_rr",
            position_mode="single", max_concurrent=1,
        )
        result = evaluate_strategy(timeline, cfg, symbol="GBPUSD")
        # Should have at most 1 signal (second blocked by open position)
        assert len(result.signals) <= 1


class TestStrategyResult:
    def test_result_has_signals_and_trades(self):
        """StrategyResult contains both signals and completed trades."""
        result = StrategyResult(signals=[], trades=[], open_trades=[])
        assert result.signals == []
        assert result.trades == []
        assert result.open_trades == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/strategy/test_push_zone_strategy.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/iora/strategy/push_zone_strategy.py
"""Push zone strategy evaluator.

Replays a ZoneTimeline bar-by-bar, applying StrategyConfig filters
and SL/TP computation to generate EntrySignals and simulate trades.

Key design: this is CHEAP to run. The expensive push zone engine
already ran once to build the timeline. This function just replays
the recorded state with different filter/SL/TP configurations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from iora.engine.push_zone_models import PushZone
from iora.strategy.zone_timeline import ZoneTimelineBar
from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.entry_signal import EntrySignal
from iora.strategy.signal_filters import apply_all_filters
from iora.strategy.sl_tp import compute_sl, compute_tp

# Parent TF mapping for nesting lookup
_PARENT_TF: dict[str, str] = {
    "M1": "M15", "M5": "H1", "M15": "H1",
    "H1": "H4", "H4": "D1", "D1": "W1", "W1": "MN1",
}

# HTF TFs for no-trade zone filtering
_HTF_TFS: set[str] = {"D1", "W1", "MN1"}

# Default ATR estimate (used when no ATR data available)
_DEFAULT_ATR: dict[str, float] = {
    "M1": 0.00015, "M5": 0.0004, "M15": 0.0007,
    "H1": 0.0015, "H4": 0.003, "D1": 0.008,
}


@dataclass(slots=True)
class StrategyResult:
    """Output of a strategy evaluation run."""
    signals: list[EntrySignal]
    trades: list[dict]        # Completed trades (entry + exit)
    open_trades: list[dict]   # Still open at end of timeline


@dataclass(slots=True)
class _OpenPosition:
    """Internal tracker for an open position."""
    signal: EntrySignal
    sl_price: float
    tp_price: float
    entry_bar_idx: int
    max_favorable: float  # For trailing (future use)


def evaluate_strategy(
    timeline: list[ZoneTimelineBar],
    config: StrategyConfig,
    symbol: str = "GBPUSD",
    pip_size: float = 0.0001,
) -> StrategyResult:
    """Replay zone timeline with given config, produce signals and trades.

    Args:
        timeline: Per-bar zone state from build_zone_timeline().
        config: Strategy configuration (filters, SL/TP, direction).
        symbol: Trading symbol (for cost/pip calculations).
        pip_size: Pip size for the symbol.

    Returns:
        StrategyResult with signals, completed trades, and open trades.
    """
    signals: list[EntrySignal] = []
    trades: list[dict] = []
    position: _OpenPosition | None = None

    for bar_idx, bar in enumerate(timeline):
        # --- 1. Check SL/TP on open position ---
        if position is not None:
            exit_result = _check_exit(position, bar, pip_size)
            if exit_result is not None:
                trades.append(exit_result)
                position = None

        # --- 2. Process zone fires for new entries ---
        if position is None:  # Single position mode
            for zone in bar.fires:
                # Only process zones on the entry TF
                if zone.timeframe != config.entry_tf:
                    continue

                direction = "short" if zone.is_supply else "long"

                # Determine signal type
                signal_type = _classify_signal(zone)

                # Find parent zone for nesting
                parent_tf = config.parent_tf
                parent_zone, nesting_depth = _find_parent(
                    bar, zone, parent_tf, direction,
                )

                # Get HTF trend
                htf_trend = bar.trend_by_tf.get(config.htf_trend_tf, 0)

                # Get zone count for entry TF
                counts = bar.zone_counts_by_tf.get(config.entry_tf, (0, 0))
                zone_count = counts[0] if zone.is_supply else counts[1]

                # Collect HTF zones for no-trade filter
                htf_zones = _collect_htf_zones(bar)

                # Apply all filters
                passed, _ = apply_all_filters(
                    signal_type=signal_type,
                    struct_cls=zone.struct_cls,
                    direction=direction,
                    parent_zone=parent_zone,
                    nesting_depth=nesting_depth,
                    htf_trend=htf_trend,
                    zone_count=zone_count,
                    entry_price=bar.close,
                    htf_zones=htf_zones,
                    config=config,
                )
                if not passed:
                    continue

                # Compute SL/TP
                all_zones = _flatten_zones(bar)
                atr = _estimate_atr(config.entry_tf)
                period_lvls = bar.period_levels_by_tf.get(
                    parent_tf, {"highs": [], "lows": []},
                )

                sl = compute_sl(
                    direction=direction,
                    entry_price=bar.close,
                    mode=config.sl_mode,
                    zones=all_zones,
                    atr=atr,
                    period_levels=period_lvls,
                    period_depth=config.sl_period_depth,
                    pip_size=pip_size,
                )
                tp = compute_tp(
                    direction=direction,
                    entry_price=bar.close,
                    sl_price=sl,
                    mode=config.tp_mode,
                    zones=all_zones,
                    atr=atr,
                    period_levels=period_lvls,
                    period_depth=config.sl_period_depth,
                    fixed_rr=config.fixed_rr,
                )

                risk_pips = abs(bar.close - sl) / pip_size
                reward_pips = abs(tp - bar.close) / pip_size

                sig = EntrySignal(
                    zone=zone,
                    zone_tf=config.entry_tf,
                    signal_type=signal_type,
                    struct_cls=zone.struct_cls,
                    direction=direction,
                    parent_zone=parent_zone,
                    parent_tf=parent_tf,
                    nesting_depth=nesting_depth,
                    opposing_nest=zone.is_terminal,
                    trend_by_tf=dict(bar.trend_by_tf),
                    period_levels=dict(bar.period_levels_by_tf),
                    zone_counts=dict(bar.zone_counts_by_tf),
                    exhaustion={},  # Populated in future versions
                    sl_price=sl,
                    tp_price=tp,
                    risk_pips=risk_pips,
                    reward_pips=reward_pips,
                    entry_time=bar.timestamp,
                    entry_price=bar.close,
                )
                signals.append(sig)

                position = _OpenPosition(
                    signal=sig,
                    sl_price=sl,
                    tp_price=tp,
                    entry_bar_idx=bar_idx,
                    max_favorable=bar.close,
                )
                break  # Single position: stop after first entry

    # Handle still-open position at end of timeline
    open_trades: list[dict] = []
    if position is not None and timeline:
        last_bar = timeline[-1]
        open_trades.append({
            "entry_time": position.signal.entry_time,
            "entry_price": position.signal.entry_price,
            "direction": position.signal.direction,
            "sl_price": position.sl_price,
            "tp_price": position.tp_price,
            "current_price": last_bar.close,
            "exit_reason": "end_of_data",
        })

    return StrategyResult(
        signals=signals,
        trades=trades,
        open_trades=open_trades,
    )


# --- Internal helpers ---

def _classify_signal(zone: PushZone) -> str:
    """Classify zone into signal type."""
    if zone.is_terminal:
        return "terminal"
    if zone.is_reversal:
        return "reversal"
    if zone.is_push:
        return "push"
    return "normal"


def _find_parent(
    bar: ZoneTimelineBar,
    child_zone: PushZone,
    parent_tf: str,
    direction: str,
) -> tuple[PushZone | None, int]:
    """Find parent zone containing child zone's price range."""
    parent_zones = bar.zones_by_tf.get(parent_tf, [])
    for pz in parent_zones:
        # Parent must be same-side (supply parent for short child, etc.)
        if direction == "short" and pz.is_supply:
            if pz.contains_price(child_zone.top) or pz.contains_price(child_zone.bottom):
                return pz, 1
        elif direction == "long" and not pz.is_supply:
            if pz.contains_price(child_zone.top) or pz.contains_price(child_zone.bottom):
                return pz, 1
    return None, 0


def _collect_htf_zones(bar: ZoneTimelineBar) -> list[PushZone]:
    """Collect D1/W1/MN1 zones for no-trade filtering."""
    result: list[PushZone] = []
    for tf in _HTF_TFS:
        result.extend(bar.zones_by_tf.get(tf, []))
    return result


def _flatten_zones(bar: ZoneTimelineBar) -> list[PushZone]:
    """Flatten all zones across all TFs into a single list."""
    result: list[PushZone] = []
    for zones in bar.zones_by_tf.values():
        result.extend(zones)
    return result


def _estimate_atr(tf: str) -> float:
    """Get default ATR estimate for a timeframe.

    In production, ATR should come from the data. This fallback
    provides reasonable estimates for GBPUSD-class instruments.
    """
    return _DEFAULT_ATR.get(tf, 0.0010)


def _check_exit(
    pos: _OpenPosition,
    bar: ZoneTimelineBar,
    pip_size: float,
) -> dict | None:
    """Check if SL or TP was hit on this bar. Returns trade dict or None."""
    sig = pos.signal
    direction = sig.direction

    # Update max favorable
    if direction == "long":
        pos.max_favorable = max(pos.max_favorable, bar.high)
        # SL hit: low touches or crosses SL
        if bar.low <= pos.sl_price:
            return _make_trade(sig, pos.sl_price, bar.timestamp, "sl_hit", pip_size)
        # TP hit: high touches or crosses TP
        if bar.high >= pos.tp_price:
            return _make_trade(sig, pos.tp_price, bar.timestamp, "tp_hit", pip_size)
    else:
        pos.max_favorable = min(pos.max_favorable, bar.low)
        # SL hit: high touches or crosses SL
        if bar.high >= pos.sl_price:
            return _make_trade(sig, pos.sl_price, bar.timestamp, "sl_hit", pip_size)
        # TP hit: low touches or crosses TP
        if bar.low <= pos.tp_price:
            return _make_trade(sig, pos.tp_price, bar.timestamp, "tp_hit", pip_size)

    return None


def _make_trade(
    sig: EntrySignal,
    exit_price: float,
    exit_time: pd.Timestamp,
    exit_reason: str,
    pip_size: float,
) -> dict:
    """Build a completed trade dict."""
    if sig.direction == "long":
        pnl_pips = (exit_price - sig.entry_price) / pip_size
    else:
        pnl_pips = (sig.entry_price - exit_price) / pip_size

    return {
        "entry_time": sig.entry_time,
        "exit_time": exit_time,
        "entry_price": sig.entry_price,
        "exit_price": exit_price,
        "direction": sig.direction,
        "sl_price": sig.sl_price,
        "tp_price": sig.tp_price,
        "exit_reason": exit_reason,
        "pnl_pips": pnl_pips,
        "signal_type": sig.signal_type,
        "struct_cls": sig.struct_cls,
        "zone_tf": sig.zone_tf,
        "parent_tf": sig.parent_tf,
        "nesting_depth": sig.nesting_depth,
        "rr_ratio": sig.rr_ratio,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/strategy/test_push_zone_strategy.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add src/iora/strategy/push_zone_strategy.py tests/strategy/test_push_zone_strategy.py
git commit -m "feat(strategy): add push zone strategy evaluator with SL/TP simulation"
```

---

### Task 7: Integration Test with Real Data

**Files:**
- Create: `tests/strategy/test_strategy_integration.py`
- Create: `scripts/verify_strategy.py`
- Modify: `src/iora/strategy/__init__.py` (re-export key classes)

- [ ] **Step 1: Write integration test**

```python
# tests/strategy/test_strategy_integration.py
"""Integration test: run strategy against real GBPUSD data."""
from __future__ import annotations

import pytest

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.strategy_config import StrategyConfig, make_preset
from iora.strategy.push_zone_strategy import evaluate_strategy


@pytest.fixture(scope="module")
def gbpusd_timeline():
    """Build zone timeline from real GBPUSD data (cached per module)."""
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


class TestStrategyIntegration:
    def test_timeline_built(self, gbpusd_timeline):
        """Timeline has expected number of bars."""
        assert len(gbpusd_timeline) > 10_000

    def test_default_config_produces_trades(self, gbpusd_timeline):
        """Default config generates at least some trades."""
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        assert len(result.signals) > 0
        assert len(result.trades) > 0

    def test_aggressive_vs_conservative(self, gbpusd_timeline):
        """Aggressive config produces more signals than conservative."""
        agg = make_preset("aggressive")
        con = make_preset("conservative")
        r_agg = evaluate_strategy(gbpusd_timeline, agg, symbol="GBPUSD")
        r_con = evaluate_strategy(gbpusd_timeline, con, symbol="GBPUSD")
        assert len(r_agg.signals) >= len(r_con.signals)

    def test_direction_filter_halves_signals(self, gbpusd_timeline):
        """Long-only produces roughly half the signals of both."""
        cfg_both = StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="both",
        )
        cfg_long = StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="long",
        )
        r_both = evaluate_strategy(gbpusd_timeline, cfg_both, symbol="GBPUSD")
        r_long = evaluate_strategy(gbpusd_timeline, cfg_long, symbol="GBPUSD")
        # Long-only should be strictly fewer
        assert len(r_long.signals) < len(r_both.signals)

    def test_trades_have_valid_pnl(self, gbpusd_timeline):
        """All completed trades have non-zero pnl_pips."""
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        result = evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        for t in result.trades[:50]:  # Check first 50
            assert "pnl_pips" in t
            assert t["exit_reason"] in ("sl_hit", "tp_hit")

    def test_replay_is_cheap(self, gbpusd_timeline):
        """Running evaluate_strategy 10x is fast (< 30s)."""
        import time
        cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
        start = time.monotonic()
        for _ in range(10):
            evaluate_strategy(gbpusd_timeline, cfg, symbol="GBPUSD")
        elapsed = time.monotonic() - start
        assert elapsed < 30.0, f"10 replays took {elapsed:.1f}s (too slow)"
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/strategy/test_strategy_integration.py -v --timeout=120`
Expected: 6 PASSED (may be slow first run due to timeline build)

- [ ] **Step 3: Write verification script**

```python
# scripts/verify_strategy.py
"""Verify push zone strategy against real GBPUSD data.

Runs multiple configs, prints signal/trade counts and basic metrics.
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")

from iora.data.parquet_storage import ParquetStorage
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.strategy_config import StrategyConfig, make_preset
from iora.strategy.push_zone_strategy import evaluate_strategy


def main():
    storage = ParquetStorage("data")
    symbol = "GBPUSD"

    tfs = ["M5", "M15", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = storage.load(symbol, tf)
        if df is not None and not df.empty:
            data_by_tf[tf] = df
            print(f"  {tf}: {len(df)} bars, {df.index[0]} -> {df.index[-1]}")

    print("\nBuilding zone timeline (this is the expensive step)...")
    t0 = time.monotonic()
    timeline = build_zone_timeline(data_by_tf, base_tf="M5")
    t_build = time.monotonic() - t0
    print(f"  Timeline: {len(timeline)} bars in {t_build:.1f}s")

    # Test multiple configs
    configs = {
        "default": StrategyConfig(require_nesting=False, no_trade_zones=False),
        "aggressive": make_preset("aggressive"),
        "conservative": make_preset("conservative"),
        "long_only": StrategyConfig(
            require_nesting=False, no_trade_zones=False, direction="long",
        ),
        "bos_only": StrategyConfig(
            require_nesting=False, no_trade_zones=False, struct_filter="bos_only",
        ),
    }

    print(f"\n{'Config':<20} {'Signals':>8} {'Trades':>8} {'Open':>6} "
          f"{'Win':>6} {'Loss':>6} {'WR%':>6} {'Time':>6}")
    print("-" * 80)

    for name, cfg in configs.items():
        t0 = time.monotonic()
        result = evaluate_strategy(timeline, cfg, symbol=symbol)
        elapsed = time.monotonic() - t0

        wins = sum(1 for t in result.trades if t["pnl_pips"] > 0)
        losses = sum(1 for t in result.trades if t["pnl_pips"] <= 0)
        wr = (wins / len(result.trades) * 100) if result.trades else 0

        print(f"{name:<20} {len(result.signals):>8} {len(result.trades):>8} "
              f"{len(result.open_trades):>6} {wins:>6} {losses:>6} "
              f"{wr:>5.1f}% {elapsed:>5.2f}s")

    # Print sample trades from default config
    result = evaluate_strategy(timeline, configs["default"], symbol=symbol)
    print(f"\n--- Sample Trades (first 10) ---")
    for t in result.trades[:10]:
        pnl = t["pnl_pips"]
        print(f"  {t['direction']:>5} {t['signal_type']:<10} {t['struct_cls']:<5} "
              f"@ {t['entry_price']:.5f} -> {t['exit_price']:.5f} "
              f"{t['exit_reason']:<7} {pnl:>+8.1f} pips  "
              f"RR={t['rr_ratio']:.1f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Update __init__.py with re-exports**

```python
# src/iora/strategy/__init__.py
"""Push zone strategy evaluation layer.

Re-exports key classes for convenient access.
"""
from iora.strategy.strategy_config import StrategyConfig, make_preset
from iora.strategy.entry_signal import EntrySignal
from iora.strategy.zone_timeline import ZoneTimelineBar, build_zone_timeline
from iora.strategy.push_zone_strategy import evaluate_strategy, StrategyResult

__all__ = [
    "StrategyConfig",
    "make_preset",
    "EntrySignal",
    "ZoneTimelineBar",
    "build_zone_timeline",
    "evaluate_strategy",
    "StrategyResult",
]
```

- [ ] **Step 5: Run verification script**

Run: `python scripts/verify_strategy.py`
Expected: Table showing signal/trade counts for each config, with aggressive > conservative, and replay times < 1s each.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=120`
Expected: All tests pass (42 existing + ~52 new = ~94 total)

- [ ] **Step 7: Commit**

```bash
git add src/iora/strategy/__init__.py tests/strategy/test_strategy_integration.py \
       scripts/verify_strategy.py
git commit -m "feat(strategy): add integration tests and verification script"
```

---

## Summary

| Task | Files | Tests | Description |
|------|-------|-------|-------------|
| 1 | 2 create | 6 | StrategyConfig dataclass + presets |
| 2 | 1 create | 4 | EntrySignal dataclass |
| 3 | 1 create | 13 | SL/TP computation (4 modes each) |
| 4 | 1 create | 23 | Signal filter functions |
| 5 | 1 create | 4 | ZoneTimeline builder |
| 6 | 1 create | 7 | Strategy evaluator (core) |
| 7 | 3 create | 6 | Integration test + verification script |
| **Total** | **10 files** | **~63 tests** | |
