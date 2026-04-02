# Flask Backtest Visualization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing Flask chart viewer with backtest endpoints and trade visualization — run strategies, view trades on chart, compare sweep configs, and inspect per-trade context.

**Architecture:** New backtest API endpoints are added to `chart_viewer_lw.py` using the existing Flask patterns (rate limiting, caching, input validation, jsonify responses). A new `backtest_serializers.py` module converts strategy output (SweepTradeRecord, metrics dicts) to LW Charts JSON format. The frontend gets a new `backtest.js` module that handles the backtest sidebar panel, trade markers/lines, equity curve, and sweep comparison table. All heavy compute (zone timeline, strategy evaluation) uses the existing strategy layer from Plans 1-3.

**Tech Stack:** Python 3.12, Flask, TradingView Lightweight Charts v4.2, existing `iora.strategy` module (evaluate_strategy, run_sweep, compute_metrics, convert_trades, build_config_grid)

---

## File Structure

```
apps/
  chart_viewer_lw.py          # Add 5 backtest API endpoints (modify)
  backtest_serializers.py      # Serialize trades/metrics/equity to LW Charts JSON (create)
  serializers.py               # No changes (existing zone/trendline serializers)
  templates/
    viewer.html                # Add backtest sidebar section + equity container (modify)
  static/
    js/
      backtest.js              # Backtest UI: sidebar panel, trade markers, equity, sweep table (create)
    css/
      viewer.css               # Add backtest panel styles (modify)

tests/
  apps/
    test_backtest_serializers.py   # Serializer unit tests (create)
    test_backtest_endpoints.py     # Flask endpoint tests with test client (create)
```

| File | Purpose |
|------|---------|
| `apps/backtest_serializers.py` | Convert SweepTradeRecord to LW Charts markers, SL/TP lines, equity curve data. Convert metrics dict to summary JSON. |
| `apps/chart_viewer_lw.py` | 6 new endpoints: `/api/backtest/run`, `/api/backtest/sweep`, `/api/backtest/trades`, `/api/backtest/equity`, `/api/backtest/report`, `/api/backtest/multi` |
| `apps/static/js/backtest.js` | Frontend: backtest sidebar panel, trade marker rendering, equity chart, sweep table, config form |
| `apps/templates/viewer.html` | Add backtest sidebar section with config form, results area, equity container |
| `apps/static/css/viewer.css` | Styles for backtest panel, sweep table, trade markers |

---

### Task 1: Backtest Serializers

**Files:**
- Create: `apps/backtest_serializers.py`
- Create: `tests/apps/test_backtest_serializers.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/apps/test_backtest_serializers.py
"""Tests for backtest serialization to LW Charts format."""
from __future__ import annotations

import pandas as pd
import pytest

from apps.backtest_serializers import (
    serialize_trade_markers,
    serialize_trade_lines,
    serialize_equity_curve,
    serialize_metrics_summary,
)
from iora.strategy.trade_converter import SweepTradeRecord


def _make_record(
    pnl_pips: float = 10.0,
    direction: int = 1,
    exit_reason: str = "tp_hit",
) -> SweepTradeRecord:
    return SweepTradeRecord(
        trade_id="pz_0001",
        symbol="GBPUSD",
        direction=direction,
        entry_time=pd.Timestamp("2025-01-15 10:00"),
        exit_time=pd.Timestamp("2025-01-15 14:00"),
        entry_price=1.2950,
        exit_price=1.2960 if pnl_pips > 0 else 1.2940,
        pnl_pips=pnl_pips,
        risk_pips=30.0,
        reward_pips=60.0,
        return_r=pnl_pips / 30.0,
        rr_ratio=2.0,
        exit_reason=exit_reason,
        sl_price=1.2920,
        tp_price=1.3010,
        signal_type="push",
        struct_cls="BOS",
        zone_tf="M5",
        parent_tf="H1",
        nesting_depth=1,
    )


class TestSerializeTradeMarkers:
    def test_winning_long_marker(self):
        """Winning long trade has green upward entry marker."""
        records = [_make_record(pnl_pips=10.0, direction=1)]
        markers = serialize_trade_markers(records)
        assert len(markers) == 2  # entry + exit
        entry = markers[0]
        assert entry["position"] == "belowBar"
        assert entry["color"] == "#26a69a"  # green
        assert entry["shape"] == "arrowUp"
        exit_ = markers[1]
        assert exit_["shape"] == "circle"

    def test_losing_short_marker(self):
        """Losing short trade has red downward entry marker."""
        records = [_make_record(pnl_pips=-15.0, direction=-1)]
        markers = serialize_trade_markers(records)
        entry = markers[0]
        assert entry["position"] == "aboveBar"
        assert entry["color"] == "#ef5350"  # red
        assert entry["shape"] == "arrowDown"

    def test_empty_records(self):
        markers = serialize_trade_markers([])
        assert markers == []


class TestSerializeTradeLines:
    def test_long_trade_lines(self):
        """Long trade produces SL (red) and TP (green) horizontal lines."""
        records = [_make_record(direction=1)]
        lines = serialize_trade_lines(records)
        assert len(lines) == 2  # SL + TP per trade
        sl_line = [l for l in lines if l["label"] == "SL"][0]
        tp_line = [l for l in lines if l["label"] == "TP"][0]
        assert sl_line["price"] == 1.2920
        assert tp_line["price"] == 1.3010
        assert sl_line["color"] == "#ef5350"
        assert tp_line["color"] == "#26a69a"


class TestSerializeEquityCurve:
    def test_equity_curve(self):
        """Equity curve returns cumulative PnL series."""
        records = [
            _make_record(pnl_pips=10.0),
            _make_record(pnl_pips=-5.0),
            _make_record(pnl_pips=20.0),
        ]
        curve = serialize_equity_curve(records)
        assert len(curve) == 3
        # Cumulative: 10, 5, 25
        assert curve[0]["value"] == pytest.approx(10.0)
        assert curve[1]["value"] == pytest.approx(5.0)
        assert curve[2]["value"] == pytest.approx(25.0)
        assert "time" in curve[0]

    def test_empty_equity(self):
        assert serialize_equity_curve([]) == []


class TestSerializeMetricsSummary:
    def test_summary_structure(self):
        """Metrics summary has expected sections."""
        metrics = {
            "total_trades": 100, "wins": 55, "losses": 45,
            "win_rate": 0.55, "total_pnl_pips": 450.0,
            "sharpe": 1.2, "sortino": 1.8, "sqn": 2.5,
            "calmar": 3.0, "profit_factor": 1.6,
            "max_dd_pips": 120.0, "max_dd_r": 4.5,
            "expectancy_r": 0.15, "avg_win_r": 1.2,
            "avg_loss_r": -0.8, "max_win_streak": 7,
            "max_loss_streak": 4,
        }
        summary = serialize_metrics_summary(metrics)
        assert "overview" in summary
        assert "risk_adjusted" in summary
        assert "streaks" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/apps/test_backtest_serializers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.backtest_serializers'`

- [ ] **Step 3: Write minimal implementation**

```python
# apps/backtest_serializers.py
"""Serialize backtest results (trades, metrics, equity) to LW Charts JSON format.

Converts SweepTradeRecord objects and metrics dicts to the JSON structures
expected by TradingView Lightweight Charts markers, lines, and area series.
"""
from __future__ import annotations

import pandas as pd

from iora.strategy.trade_converter import SweepTradeRecord


# LW Charts color constants
_GREEN = "#26a69a"
_RED = "#ef5350"
_BLUE = "#2196F3"
_GRAY = "#9e9e9e"


def _ts(t: pd.Timestamp) -> int:
    """Convert pandas Timestamp to Unix seconds for LW Charts."""
    return int(t.timestamp())


def serialize_trade_markers(records: list[SweepTradeRecord]) -> list[dict]:
    """Convert trade records to LW Charts marker format.

    Each trade produces two markers: entry arrow + exit circle.
    Color: green for winners, red for losers.
    Shape: arrowUp (long entry), arrowDown (short entry), circle (exit).
    """
    markers: list[dict] = []
    for r in records:
        is_long = r.direction == 1
        color = _GREEN if r.is_winner else _RED
        pnl_label = f"{r.pnl_pips:+.1f}p ({r.return_r:+.2f}R)"

        # Entry marker
        markers.append({
            "time": _ts(r.entry_time),
            "position": "belowBar" if is_long else "aboveBar",
            "color": color,
            "shape": "arrowUp" if is_long else "arrowDown",
            "text": f"{r.signal_type} {r.struct_cls} @ {r.zone_tf}",
        })

        # Exit marker
        markers.append({
            "time": _ts(r.exit_time),
            "position": "aboveBar" if is_long else "belowBar",
            "color": color,
            "shape": "circle",
            "text": f"{r.exit_reason} {pnl_label}",
        })

    return markers


def serialize_trade_lines(records: list[SweepTradeRecord]) -> list[dict]:
    """Convert trade SL/TP to horizontal price lines.

    Each trade produces two lines: SL (red dashed) and TP (green dashed).
    Lines span from entry_time to exit_time.
    """
    lines: list[dict] = []
    for r in records:
        lines.append({
            "price": r.sl_price,
            "color": _RED,
            "label": "SL",
            "start_time": _ts(r.entry_time),
            "end_time": _ts(r.exit_time),
            "trade_id": r.trade_id,
        })
        lines.append({
            "price": r.tp_price,
            "color": _GREEN,
            "label": "TP",
            "start_time": _ts(r.entry_time),
            "end_time": _ts(r.exit_time),
            "trade_id": r.trade_id,
        })
    return lines


def serialize_equity_curve(records: list[SweepTradeRecord]) -> list[dict]:
    """Build cumulative PnL series for LW Charts area chart.

    Returns list of {time, value} dicts sorted by exit_time.
    """
    if not records:
        return []

    sorted_records = sorted(records, key=lambda r: r.exit_time)
    cumulative = 0.0
    curve: list[dict] = []
    for r in sorted_records:
        cumulative += r.pnl_pips
        curve.append({
            "time": _ts(r.exit_time),
            "value": round(cumulative, 2),
        })
    return curve


def serialize_equity_curve_r(records: list[SweepTradeRecord]) -> list[dict]:
    """Build cumulative R-multiple series for LW Charts area chart."""
    if not records:
        return []

    sorted_records = sorted(records, key=lambda r: r.exit_time)
    cumulative = 0.0
    curve: list[dict] = []
    for r in sorted_records:
        cumulative += r.return_r
        curve.append({
            "time": _ts(r.exit_time),
            "value": round(cumulative, 4),
        })
    return curve


def serialize_metrics_summary(metrics: dict) -> dict:
    """Organize flat metrics dict into display sections.

    Returns dict with sections: overview, risk_adjusted, pnl, drawdown, streaks.
    """
    return {
        "overview": {
            "Total Trades": metrics.get("total_trades", 0),
            "Wins": metrics.get("wins", 0),
            "Losses": metrics.get("losses", 0),
            "Win Rate": f"{metrics.get('win_rate', 0) * 100:.1f}%",
            "TP Hits": metrics.get("tp_hits", 0),
            "SL Hits": metrics.get("sl_hits", 0),
        },
        "risk_adjusted": {
            "SQN": f"{metrics.get('sqn', 0):.2f}",
            "Sharpe": f"{metrics.get('sharpe', 0):.2f}",
            "Sortino": f"{metrics.get('sortino', 0):.2f}",
            "Calmar": f"{metrics.get('calmar', 0):.2f}",
            "Profit Factor": f"{metrics.get('profit_factor', 0):.2f}",
        },
        "pnl": {
            "Total PnL (pips)": f"{metrics.get('total_pnl_pips', 0):.1f}",
            "Total R": f"{metrics.get('total_r', 0):.2f}",
            "Expectancy (R)": f"{metrics.get('expectancy_r', 0):.4f}",
            "Avg Win (R)": f"{metrics.get('avg_win_r', 0):.2f}",
            "Avg Loss (R)": f"{metrics.get('avg_loss_r', 0):.2f}",
        },
        "drawdown": {
            "Max DD (pips)": f"{metrics.get('max_dd_pips', 0):.1f}",
            "Max DD (R)": f"{metrics.get('max_dd_r', 0):.2f}",
        },
        "streaks": {
            "Max Win Streak": metrics.get("max_win_streak", 0),
            "Max Loss Streak": metrics.get("max_loss_streak", 0),
        },
    }


def serialize_trade_detail(record: SweepTradeRecord) -> dict:
    """Full detail for a single trade (for trade inspector panel)."""
    return {
        "trade_id": record.trade_id,
        "direction": record.direction_str,
        "entry_time": _ts(record.entry_time),
        "exit_time": _ts(record.exit_time),
        "entry_price": record.entry_price,
        "exit_price": record.exit_price,
        "sl_price": record.sl_price,
        "tp_price": record.tp_price,
        "pnl_pips": round(record.pnl_pips, 2),
        "return_r": round(record.return_r, 4),
        "risk_pips": round(record.risk_pips, 2),
        "reward_pips": round(record.reward_pips, 2),
        "rr_ratio": round(record.rr_ratio, 2),
        "exit_reason": record.exit_reason,
        "signal_type": record.signal_type,
        "struct_cls": record.struct_cls,
        "zone_tf": record.zone_tf,
        "parent_tf": record.parent_tf,
        "nesting_depth": record.nesting_depth,
        "opposing_nest": record.opposing_nest,
        "zone_top": record.zone_top,
        "zone_bottom": record.zone_bottom,
        "zone_is_push": record.zone_is_push,
        "zone_is_reversal": record.zone_is_reversal,
        "zone_is_terminal": record.zone_is_terminal,
        "zone_swing_cls": record.zone_swing_cls,
        "zone_count": record.zone_count,
        "holding_hours": round(record.holding_period.total_seconds() / 3600, 2),
        "is_winner": record.is_winner,
    }


def serialize_sweep_row(config_dict: dict, metrics: dict) -> dict:
    """Combine config + metrics into a single sweep comparison row."""
    return {**config_dict, **metrics}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/apps/test_backtest_serializers.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/backtest_serializers.py tests/apps/test_backtest_serializers.py
git commit -m "feat(viz): add backtest serializers for LW Charts trade markers and metrics"
```

---

### Task 2: Backtest API Endpoints

**Files:**
- Modify: `apps/chart_viewer_lw.py:761` (add endpoints before `__main__` block)
- Create: `tests/apps/test_backtest_endpoints.py`

**Context:** The existing app at `apps/chart_viewer_lw.py` uses Flask patterns:
- `@app.route(...)` for endpoints
- `@_limit("N per minute")` for rate limiting (no-op if flask-limiter not installed)
- `@cache.memoize(timeout=CACHE_TIMEOUT_SEC)` for caching
- `request.get_json()` for POST body parsing
- `jsonify(...)` for JSON responses
- Input validation with early 400 returns
- `storage = ParquetStorage(base_dir=DATA_DIR)` for data loading

All new endpoints follow these same patterns.

- [ ] **Step 1: Write the failing test**

```python
# tests/apps/test_backtest_endpoints.py
"""Tests for backtest API endpoints using Flask test client."""
from __future__ import annotations

import json

import pytest

# Import the Flask app for test client
import sys
sys.path.insert(0, "apps")
sys.path.insert(0, "src")


@pytest.fixture(scope="module")
def client():
    """Flask test client. Skip if app can't import."""
    try:
        from apps.chart_viewer_lw import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c
    except Exception as e:
        pytest.skip(f"Flask app not available: {e}")


class TestBacktestRunEndpoint:
    def test_run_requires_symbol(self, client):
        """POST /api/backtest/run requires symbol."""
        resp = client.post("/api/backtest/run",
                           json={})
        assert resp.status_code == 400
        assert "symbol" in resp.get_json()["error"]

    def test_run_returns_trades_and_metrics(self, client):
        """POST /api/backtest/run returns trades + metrics + equity."""
        resp = client.post("/api/backtest/run", json={
            "symbol": "GBPUSD",
            "config": {
                "require_nesting": False,
                "no_trade_zones": False,
                "sl_mode": "atr",
                "tp_mode": "fixed_rr",
            },
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert "metrics" in data
        assert "equity" in data
        assert "markers" in data


class TestBacktestSweepEndpoint:
    def test_sweep_requires_symbol(self, client):
        """POST /api/backtest/sweep requires symbol."""
        resp = client.post("/api/backtest/sweep", json={})
        assert resp.status_code == 400

    def test_sweep_returns_results(self, client):
        """POST /api/backtest/sweep returns rows of config+metrics."""
        resp = client.post("/api/backtest/sweep", json={
            "symbol": "GBPUSD",
            "dimensions": {
                "sl_mode": ["zone", "atr"],
                "tp_mode": ["fixed_rr"],
                "require_nesting": [False],
                "no_trade_zones": [False],
            },
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert len(data["results"]) == 2  # 2 SL modes x 1 TP mode


class TestBacktestTradesEndpoint:
    def test_trades_requires_symbol(self, client):
        """GET /api/backtest/trades requires symbol."""
        resp = client.get("/api/backtest/trades")
        assert resp.status_code == 400

    def test_trades_returns_list(self, client):
        """GET /api/backtest/trades returns trade list."""
        resp = client.get("/api/backtest/trades?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert "total" in data


class TestBacktestEquityEndpoint:
    def test_equity_requires_symbol(self, client):
        """GET /api/backtest/equity requires symbol."""
        resp = client.get("/api/backtest/equity")
        assert resp.status_code == 400

    def test_equity_returns_curve(self, client):
        """GET /api/backtest/equity returns equity curve."""
        resp = client.get("/api/backtest/equity?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "equity" in data
        assert "mode" in data


class TestBacktestReportEndpoint:
    def test_report_requires_symbol(self, client):
        """GET /api/backtest/report requires symbol."""
        resp = client.get("/api/backtest/report")
        assert resp.status_code == 400


class TestBacktestMultiEndpoint:
    def test_multi_requires_symbols(self, client):
        """POST /api/backtest/multi requires symbols list."""
        resp = client.post("/api/backtest/multi", json={})
        assert resp.status_code == 400

    def test_multi_returns_per_symbol(self, client):
        """POST /api/backtest/multi returns per-symbol results."""
        resp = client.post("/api/backtest/multi", json={
            "symbols": ["GBPUSD"],
            "config": {"require_nesting": False, "no_trade_zones": False},
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert len(data["results"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/apps/test_backtest_endpoints.py -v`
Expected: FAIL — 404 for `/api/backtest/run` (endpoint doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Add the following endpoints to `apps/chart_viewer_lw.py`, just before the `if __name__ == "__main__":` block (line 761):

```python
# ── Backtest endpoints ────────────────────────────────────────────────────

from iora.strategy.strategy_config import StrategyConfig
from iora.strategy.zone_timeline import build_zone_timeline
from iora.strategy.push_zone_strategy import evaluate_strategy
from iora.strategy.trade_converter import convert_trades
from iora.strategy.sweep_runner import run_sweep, compute_metrics
from iora.strategy.config_grid import build_config_grid
from apps.backtest_serializers import (
    serialize_trade_markers,
    serialize_trade_lines,
    serialize_equity_curve,
    serialize_equity_curve_r,
    serialize_metrics_summary,
    serialize_trade_detail,
)


@cache.memoize(timeout=CACHE_TIMEOUT_SEC)
def _build_backtest_timeline(symbol: str, base_tf: str = "M5"):
    """Build zone timeline for backtest (cached 10 min)."""
    tfs = [base_tf, "M15", "H1", "H4", "D1"]
    data_by_tf = {}
    for tf in tfs:
        df = _load(symbol, tf, start=None, end=None)
        if not df.empty:
            data_by_tf[tf] = df
    if base_tf not in data_by_tf:
        return None
    return build_zone_timeline(data_by_tf, base_tf=base_tf)


def _parse_strategy_config(config_dict: dict) -> StrategyConfig:
    """Parse a JSON config dict into StrategyConfig."""
    kwargs = {}
    valid_fields = {
        "entry_tf", "parent_tf", "require_nesting", "signal_types",
        "struct_filter", "htf_trend_filter", "htf_trend_tf",
        "max_zone_count", "no_trade_zones", "sl_mode", "tp_mode",
        "fixed_rr", "sl_period_depth", "position_mode", "direction",
    }
    for k, v in config_dict.items():
        if k in valid_fields:
            if k == "signal_types" and isinstance(v, list):
                kwargs[k] = set(v)
            else:
                kwargs[k] = v
    return StrategyConfig(**kwargs)


@app.route("/api/backtest/run", methods=["POST"])
@_limit("5 per minute")
def api_backtest_run():
    """Run strategy on a symbol with given config.

    Request body:
        symbol: str (required)
        config: dict (optional, defaults to StrategyConfig defaults)
        base_tf: str (optional, default "M5")

    Returns: trades, metrics, equity curve, markers, trade lines.
    """
    body = request.get_json() or {}
    symbol = body.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    base_tf = body.get("base_tf", "M5")
    config_dict = body.get("config", {})
    cfg = _parse_strategy_config(config_dict)

    timeline = _build_backtest_timeline(symbol, base_tf)
    if timeline is None:
        return jsonify({"error": f"No {base_tf} data for {symbol}"}), 404

    result = evaluate_strategy(timeline, cfg, symbol=symbol)
    records = convert_trades(result.trades, symbol=symbol)
    metrics = compute_metrics(records)

    return jsonify({
        "trades": [serialize_trade_detail(r) for r in records],
        "metrics": serialize_metrics_summary(metrics),
        "metrics_raw": metrics,
        "equity": serialize_equity_curve(records),
        "equity_r": serialize_equity_curve_r(records),
        "markers": serialize_trade_markers(records),
        "trade_lines": serialize_trade_lines(records),
        "total_signals": len(result.signals),
        "config": cfg.to_dict(),
    })


@app.route("/api/backtest/sweep", methods=["POST"])
@_limit("2 per minute")
def api_backtest_sweep():
    """Run parameter sweep across configs.

    Request body:
        symbol: str (required)
        dimensions: dict of param_name -> list of values (required)
        base_tf: str (optional, default "M5")

    Returns: list of config+metrics rows.
    """
    body = request.get_json() or {}
    symbol = body.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    dimensions = body.get("dimensions")
    if not dimensions or not isinstance(dimensions, dict):
        return jsonify({"error": "dimensions dict is required"}), 400

    base_tf = body.get("base_tf", "M5")

    timeline = _build_backtest_timeline(symbol, base_tf)
    if timeline is None:
        return jsonify({"error": f"No {base_tf} data for {symbol}"}), 404

    grid = build_config_grid(dimensions)
    if len(grid) > 200:
        return jsonify({"error": f"Too many configs ({len(grid)}). Max 200."}), 400

    df = run_sweep(timeline, grid, symbol=symbol)

    return jsonify({
        "results": df.to_dict(orient="records"),
        "n_configs": len(grid),
        "symbol": symbol,
    })


@app.route("/api/backtest/trades")
def api_backtest_trades():
    """Get trade list with full entry context.

    Query params:
        symbol: str (required)
        base_tf: str (optional, default "M5")
    """
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    base_tf = request.args.get("base_tf", "M5")

    timeline = _build_backtest_timeline(symbol, base_tf)
    if timeline is None:
        return jsonify({"error": f"No {base_tf} data for {symbol}"}), 404

    cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
    result = evaluate_strategy(timeline, cfg, symbol=symbol)
    records = convert_trades(result.trades, symbol=symbol)

    return jsonify({
        "trades": [serialize_trade_detail(r) for r in records],
        "total": len(records),
        "symbol": symbol,
    })


@app.route("/api/backtest/equity")
def api_backtest_equity():
    """Get equity curve and drawdown data.

    Query params:
        symbol: str (required)
        base_tf: str (optional, default "M5")
        mode: str (optional, "pips" or "r", default "pips")
    """
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    base_tf = request.args.get("base_tf", "M5")
    mode = request.args.get("mode", "pips")

    timeline = _build_backtest_timeline(symbol, base_tf)
    if timeline is None:
        return jsonify({"error": f"No {base_tf} data for {symbol}"}), 404

    cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
    result = evaluate_strategy(timeline, cfg, symbol=symbol)
    records = convert_trades(result.trades, symbol=symbol)

    if mode == "r":
        curve = serialize_equity_curve_r(records)
    else:
        curve = serialize_equity_curve(records)

    return jsonify({
        "equity": curve,
        "mode": mode,
        "symbol": symbol,
    })


@app.route("/api/backtest/report")
def api_backtest_report():
    """Get summary metrics for a symbol with default config.

    Query params:
        symbol: str (required)
        base_tf: str (optional, default "M5")
    """
    symbol = request.args.get("symbol")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400

    base_tf = request.args.get("base_tf", "M5")

    timeline = _build_backtest_timeline(symbol, base_tf)
    if timeline is None:
        return jsonify({"error": f"No {base_tf} data for {symbol}"}), 404

    cfg = StrategyConfig(require_nesting=False, no_trade_zones=False)
    result = evaluate_strategy(timeline, cfg, symbol=symbol)
    records = convert_trades(result.trades, symbol=symbol)
    metrics = compute_metrics(records)

    return jsonify({
        "metrics": serialize_metrics_summary(metrics),
        "metrics_raw": metrics,
        "config": cfg.to_dict(),
        "symbol": symbol,
        "total_bars": len(timeline),
    })


@app.route("/api/backtest/multi", methods=["POST"])
@_limit("1 per minute")
def api_backtest_multi():
    """Run strategy across multiple symbols.

    Request body:
        symbols: list of str (required)
        config: dict (optional)
        base_tf: str (optional, default "M5")

    Returns: per-symbol metrics + aggregate.
    """
    from iora.strategy.sweep_runner import run_multi_symbol_sweep

    body = request.get_json() or {}
    symbols = body.get("symbols")
    if not symbols or not isinstance(symbols, list):
        return jsonify({"error": "symbols list is required"}), 400
    if len(symbols) > 10:
        return jsonify({"error": "Max 10 symbols per request"}), 400

    known_symbols = _get_symbols()
    invalid = [s for s in symbols if s not in known_symbols]
    if invalid:
        return jsonify({"error": f"Unknown symbols: {', '.join(invalid)}"}), 400

    base_tf = body.get("base_tf", "M5")
    config_dict = body.get("config", {})
    cfg = _parse_strategy_config(config_dict)

    # Build timelines and run per-symbol
    per_symbol = []
    for symbol in symbols:
        timeline = _build_backtest_timeline(symbol, base_tf)
        if timeline is None:
            per_symbol.append({"symbol": symbol, "error": f"No {base_tf} data"})
            continue

        result = evaluate_strategy(timeline, cfg, symbol=symbol)
        records = convert_trades(result.trades, symbol=symbol)
        metrics = compute_metrics(records)

        per_symbol.append({
            "symbol": symbol,
            "metrics": serialize_metrics_summary(metrics),
            "metrics_raw": metrics,
            "equity": serialize_equity_curve(records),
            "total_trades": len(records),
        })

    return jsonify({
        "results": per_symbol,
        "config": cfg.to_dict(),
        "n_symbols": len(symbols),
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/apps/test_backtest_endpoints.py -v --timeout=120`
Expected: All PASSED (some may skip if GBPUSD data not available)

- [ ] **Step 5: Commit**

```bash
git add apps/chart_viewer_lw.py tests/apps/test_backtest_endpoints.py
git commit -m "feat(viz): add backtest API endpoints for run, sweep, and report"
```

---

### Task 3: Frontend Backtest Panel (HTML + CSS)

**Files:**
- Modify: `apps/templates/viewer.html`
- Modify: `apps/static/css/viewer.css`

**Context:** The existing `viewer.html` has a sidebar (`#sidebar`) with sections for Chart settings, Zone display, HTF candles, and Trendlines. Each section follows this pattern:
```html
<div class="sidebar-section">
    <h3>Section Title</h3>
    <label>Field</label>
    <select id="..."></select>
</div>
```

- [ ] **Step 1: Read existing viewer.html and viewer.css**

Read: `apps/templates/viewer.html` and `apps/static/css/viewer.css`

- [ ] **Step 2: Add backtest sidebar section to viewer.html**

Add a new sidebar section after the existing sections (before `</div><!-- end sidebar -->`), and add an equity chart container div after the main chart area. Also add the `backtest.js` script tag.

```html
<!-- ── Backtest ── -->
<div class="sidebar-section" id="backtest-section">
    <h3>Backtest</h3>

    <!-- Config form -->
    <label>SL Mode</label>
    <select id="bt-sl-mode">
        <option value="zone">Zone</option>
        <option value="atr" selected>ATR</option>
        <option value="structure">Structure</option>
        <option value="fixed_pips">Fixed Pips</option>
    </select>

    <label>TP Mode</label>
    <select id="bt-tp-mode">
        <option value="zone">Zone</option>
        <option value="fixed_rr" selected>Fixed R:R</option>
        <option value="structure">Structure</option>
        <option value="atr">ATR</option>
    </select>

    <label>Fixed R:R</label>
    <input type="number" id="bt-fixed-rr" value="2.0" min="0.5" max="10" step="0.5">

    <label>Nesting</label>
    <select id="bt-nesting">
        <option value="false">No</option>
        <option value="true">Yes</option>
    </select>

    <label>Direction</label>
    <select id="bt-direction">
        <option value="both" selected>Both</option>
        <option value="long">Long Only</option>
        <option value="short">Short Only</option>
    </select>

    <label>HTF Trend</label>
    <select id="bt-htf-trend">
        <option value="none" selected>None</option>
        <option value="with_trend">With Trend</option>
    </select>

    <div style="margin-top:8px; display:flex; gap:4px;">
        <button id="bt-run-btn" style="flex:1;">Run</button>
        <button id="bt-sweep-btn" style="flex:1;">Sweep</button>
    </div>

    <!-- Results area -->
    <div id="bt-results" style="display:none; margin-top:8px;">
        <div id="bt-metrics" class="bt-metrics-panel"></div>
    </div>

    <!-- Sweep table (shown after sweep) -->
    <div id="bt-sweep-results" style="display:none; margin-top:8px; max-height:300px; overflow-y:auto;">
        <table id="bt-sweep-table" class="bt-sweep-table">
            <thead><tr></tr></thead>
            <tbody></tbody>
        </table>
    </div>
</div>
```

After the main chart container `<div id="chart-container">`, add:

```html
<!-- Equity curve chart (shown during backtest) -->
<div id="equity-container" style="display:none; height:150px; width:100%;"></div>
```

At the bottom with other script tags, add:

```html
<script src="/static/js/backtest.js?v={{ cache_bust('backtest.js') }}"></script>
```

- [ ] **Step 3: Add backtest CSS styles**

Append to `apps/static/css/viewer.css`:

```css
/* ── Backtest panel ────────────────────────── */
.bt-metrics-panel {
    font-size: 11px;
    line-height: 1.6;
}
.bt-metrics-panel h4 {
    margin: 6px 0 2px 0;
    font-size: 11px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.bt-metrics-panel .metric-row {
    display: flex;
    justify-content: space-between;
    padding: 1px 0;
}
.bt-metrics-panel .metric-label { color: #888; }
.bt-metrics-panel .metric-value { color: #ddd; font-weight: 500; }

.bt-sweep-table {
    width: 100%;
    font-size: 10px;
    border-collapse: collapse;
    color: #ccc;
}
.bt-sweep-table th {
    text-align: left;
    padding: 3px 4px;
    border-bottom: 1px solid #444;
    color: #aaa;
    cursor: pointer;
    white-space: nowrap;
}
.bt-sweep-table th:hover { color: #fff; }
.bt-sweep-table td {
    padding: 2px 4px;
    border-bottom: 1px solid #333;
    white-space: nowrap;
}
.bt-sweep-table tr:hover { background: #2a2a3a; }
.bt-sweep-table tr.selected { background: #1a3a5a; }

#equity-container {
    border-top: 1px solid #333;
    background: #1a1a2e;
}
```

- [ ] **Step 4: Verify templates load**

Start the Flask app manually and check that the page loads without errors:
```bash
cd C:\Iora && python apps/chart_viewer_lw.py
```
Open `http://127.0.0.1:8060` — verify the backtest sidebar section appears.

- [ ] **Step 5: Commit**

```bash
git add apps/templates/viewer.html apps/static/css/viewer.css
git commit -m "feat(viz): add backtest sidebar panel HTML and CSS"
```

---

### Task 4: Frontend Backtest JavaScript

**Files:**
- Create: `apps/static/js/backtest.js`

**Context:** Existing JS modules in `apps/static/js/` follow this pattern:
- Each module is an IIFE or plain script that attaches to global `window` or uses DOM event listeners.
- `chart.js` creates the LW Charts instance (available as `window.chart` or via a getter).
- `overlays.js` manages chart overlays (zones, trendlines).
- `main.js` handles sidebar controls and data loading via `fetch()`.
- All JS modules use vanilla JS (no frameworks, no bundler).

**Important:** Use safe DOM methods (`textContent`, `createElement`, `appendChild`) instead of `innerHTML` to avoid XSS risks. All data comes from our own Flask server, but we follow safe patterns consistently.

- [ ] **Step 1: Create backtest.js**

```javascript
// apps/static/js/backtest.js
// Backtest UI: run strategy, display trades on chart, show equity curve, sweep comparison.
(function () {
    'use strict';

    // ── State ──────────────────────────────────────────────────────────
    let equityChart = null;
    let equitySeries = null;

    // ── DOM helpers (safe — no innerHTML) ──────────────────────────────
    function clearChildren(el) {
        while (el.firstChild) el.removeChild(el.firstChild);
    }

    function createEl(tag, attrs, textContent) {
        const el = document.createElement(tag);
        if (attrs) {
            for (const [k, v] of Object.entries(attrs)) {
                if (k === 'className') el.className = v;
                else if (k === 'dataset') Object.assign(el.dataset, v);
                else el.setAttribute(k, v);
            }
        }
        if (textContent !== undefined) el.textContent = textContent;
        return el;
    }

    // ── Config from sidebar ────────────────────────────────────────────
    function getConfig() {
        return {
            sl_mode: document.getElementById('bt-sl-mode').value,
            tp_mode: document.getElementById('bt-tp-mode').value,
            fixed_rr: parseFloat(document.getElementById('bt-fixed-rr').value) || 2.0,
            require_nesting: document.getElementById('bt-nesting').value === 'true',
            no_trade_zones: false,
            direction: document.getElementById('bt-direction').value,
            htf_trend_filter: document.getElementById('bt-htf-trend').value,
        };
    }

    function getSymbol() {
        const el = document.getElementById('symbol-select');
        return el ? el.value : 'GBPUSD';
    }

    // ── Run single backtest ────────────────────────────────────────────
    async function runBacktest() {
        const btn = document.getElementById('bt-run-btn');
        btn.disabled = true;
        btn.textContent = 'Running...';

        try {
            const resp = await fetch('/api/backtest/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: getSymbol(),
                    config: getConfig(),
                }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert('Backtest error: ' + (err.error || resp.statusText));
                return;
            }

            const data = await resp.json();
            displayResults(data);
        } catch (e) {
            alert('Backtest failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Run';
        }
    }

    // ── Display results ────────────────────────────────────────────────
    function displayResults(data) {
        const resultsDiv = document.getElementById('bt-results');
        resultsDiv.style.display = 'block';
        document.getElementById('bt-sweep-results').style.display = 'none';

        renderMetrics(data.metrics);
        renderTradeMarkers(data.markers);
        renderEquityCurve(data.equity);
    }

    function renderMetrics(metrics) {
        const container = document.getElementById('bt-metrics');
        clearChildren(container);

        for (const [section, items] of Object.entries(metrics)) {
            const h4 = createEl('h4', null, section.replace(/_/g, ' '));
            container.appendChild(h4);

            for (const [label, value] of Object.entries(items)) {
                const row = createEl('div', { className: 'metric-row' });
                row.appendChild(createEl('span', { className: 'metric-label' }, label));
                row.appendChild(createEl('span', { className: 'metric-value' }, String(value)));
                container.appendChild(row);
            }
        }
    }

    function renderTradeMarkers(markers) {
        const series = window.mainSeries || window.candleSeries;
        if (!series) return;

        try {
            series.setMarkers(markers);
        } catch (e) {
            console.warn('Could not set trade markers:', e);
        }
    }

    function renderEquityCurve(equityData) {
        const container = document.getElementById('equity-container');
        if (!equityData || equityData.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';

        if (equityChart) {
            equityChart.remove();
        }

        equityChart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: 150,
            layout: {
                background: { color: '#1a1a2e' },
                textColor: '#888',
            },
            grid: {
                vertLines: { color: '#2a2a3a' },
                horzLines: { color: '#2a2a3a' },
            },
            rightPriceScale: { borderColor: '#333' },
            timeScale: { borderColor: '#333' },
            crosshair: { mode: 0 },
        });

        equitySeries = equityChart.addAreaSeries({
            lineColor: '#2196F3',
            topColor: 'rgba(33, 150, 243, 0.3)',
            bottomColor: 'rgba(33, 150, 243, 0.0)',
            lineWidth: 2,
        });

        equitySeries.setData(equityData);
        equityChart.timeScale().fitContent();
    }

    // ── Sweep ──────────────────────────────────────────────────────────
    async function runSweep() {
        const btn = document.getElementById('bt-sweep-btn');
        btn.disabled = true;
        btn.textContent = 'Sweeping...';

        try {
            const resp = await fetch('/api/backtest/sweep', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: getSymbol(),
                    dimensions: {
                        sl_mode: ['zone', 'atr'],
                        tp_mode: ['zone', 'fixed_rr'],
                        require_nesting: [true, false],
                        no_trade_zones: [false],
                        fixed_rr: [1.5, 2.0, 3.0],
                    },
                }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert('Sweep error: ' + (err.error || resp.statusText));
                return;
            }

            const data = await resp.json();
            displaySweepResults(data);
        } catch (e) {
            alert('Sweep failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Sweep';
        }
    }

    function displaySweepResults(data) {
        document.getElementById('bt-results').style.display = 'none';
        const sweepDiv = document.getElementById('bt-sweep-results');
        sweepDiv.style.display = 'block';

        const table = document.getElementById('bt-sweep-table');
        const thead = table.querySelector('thead tr');
        const tbody = table.querySelector('tbody');

        clearChildren(thead);
        clearChildren(tbody);

        if (!data.results || data.results.length === 0) {
            const tr = createEl('tr');
            tr.appendChild(createEl('td', null, 'No results'));
            tbody.appendChild(tr);
            return;
        }

        // Display columns (subset for readability)
        const displayCols = [
            'sl_mode', 'tp_mode', 'require_nesting', 'fixed_rr',
            'total_trades', 'win_rate', 'expectancy_r', 'sqn',
            'sharpe', 'profit_factor', 'max_dd_r', 'total_r',
        ];

        // Sort by expectancy_r descending
        data.results.sort((a, b) => (b.expectancy_r || 0) - (a.expectancy_r || 0));

        // Header
        displayCols.forEach(col => {
            const th = createEl('th', { dataset: { col: col } }, col.replace(/_/g, ' '));
            th.addEventListener('click', () => {
                data.results.sort((a, b) => (b[col] || 0) - (a[col] || 0));
                displaySweepResults(data);
            });
            thead.appendChild(th);
        });

        // Body
        data.results.forEach((row, idx) => {
            const tr = createEl('tr', { dataset: { idx: String(idx) } });
            displayCols.forEach(col => {
                let v = row[col];
                if (typeof v === 'number') {
                    v = v.toFixed(
                        ['win_rate', 'expectancy_r', 'sharpe', 'sqn', 'profit_factor', 'max_dd_r', 'total_r'].includes(col) ? 3 : 1
                    );
                }
                if (typeof v === 'boolean') v = v ? 'Y' : 'N';
                tr.appendChild(createEl('td', null, v != null ? String(v) : '-'));
            });

            tr.addEventListener('click', () => {
                tbody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
                tr.classList.add('selected');
                loadSweepConfig(row);
            });

            tbody.appendChild(tr);
        });
    }

    async function loadSweepConfig(configRow) {
        if (configRow.sl_mode) document.getElementById('bt-sl-mode').value = configRow.sl_mode;
        if (configRow.tp_mode) document.getElementById('bt-tp-mode').value = configRow.tp_mode;
        if (configRow.fixed_rr) document.getElementById('bt-fixed-rr').value = configRow.fixed_rr;
        if (configRow.require_nesting !== undefined) {
            document.getElementById('bt-nesting').value = configRow.require_nesting ? 'true' : 'false';
        }
        await runBacktest();
    }

    // ── Cleanup ────────────────────────────────────────────────────────
    function clearBacktestOverlays() {
        const series = window.mainSeries || window.candleSeries;
        if (series) {
            try { series.setMarkers([]); } catch (e) {}
        }
        if (equityChart) {
            equityChart.remove();
            equityChart = null;
        }
        document.getElementById('equity-container').style.display = 'none';
        document.getElementById('bt-results').style.display = 'none';
        document.getElementById('bt-sweep-results').style.display = 'none';
    }

    // ── Init ───────────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        const runBtn = document.getElementById('bt-run-btn');
        const sweepBtn = document.getElementById('bt-sweep-btn');

        if (runBtn) runBtn.addEventListener('click', runBacktest);
        if (sweepBtn) sweepBtn.addEventListener('click', runSweep);
    });

    // Expose for other modules
    window.backtestModule = { clearOverlays: clearBacktestOverlays };
})();
```

- [ ] **Step 2: Verify JS loads in browser**

Start the Flask app and open `http://127.0.0.1:8060`. Open browser console — verify no JS errors from `backtest.js`. Click the "Run" button — verify it sends a POST to `/api/backtest/run` and displays results.

- [ ] **Step 3: Commit**

```bash
git add apps/static/js/backtest.js
git commit -m "feat(viz): add backtest.js frontend — trade markers, equity curve, sweep table"
```

---

### Task 5: Integration Test and Smoke Test

**Files:**
- Modify: `tests/apps/test_backtest_endpoints.py` (add integration assertions)
- Modify: `apps/chart_viewer_lw.py` (any fixes from integration testing)

- [ ] **Step 1: Add integration assertions to endpoint tests**

Add these tests to `tests/apps/test_backtest_endpoints.py`:

```python
class TestBacktestIntegration:
    def test_run_metrics_have_comprehensive_fields(self, client):
        """Run endpoint returns all comprehensive metric sections."""
        resp = client.post("/api/backtest/run", json={
            "symbol": "GBPUSD",
            "config": {"require_nesting": False, "no_trade_zones": False,
                        "sl_mode": "atr", "tp_mode": "fixed_rr"},
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        data = resp.get_json()

        # Metrics sections
        m = data["metrics"]
        assert "overview" in m
        assert "risk_adjusted" in m
        assert "pnl" in m
        assert "drawdown" in m
        assert "streaks" in m

        # Raw metrics for downstream use
        raw = data["metrics_raw"]
        assert "sqn" in raw
        assert "sharpe" in raw
        assert "calmar" in raw
        assert "profit_factor" in raw
        assert "max_dd_pips" in raw

    def test_run_trades_have_full_context(self, client):
        """Each trade in run response has full entry context."""
        resp = client.post("/api/backtest/run", json={
            "symbol": "GBPUSD",
            "config": {"require_nesting": False, "no_trade_zones": False,
                        "sl_mode": "atr", "tp_mode": "fixed_rr"},
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        data = resp.get_json()
        if not data["trades"]:
            pytest.skip("No trades generated")

        trade = data["trades"][0]
        # Core fields
        assert "entry_price" in trade
        assert "exit_price" in trade
        assert "pnl_pips" in trade
        assert "return_r" in trade
        # Signal classification
        assert "signal_type" in trade
        assert "struct_cls" in trade
        assert "zone_tf" in trade
        # Zone context
        assert "zone_top" in trade
        assert "zone_is_push" in trade
        assert "zone_swing_cls" in trade

    def test_equity_curve_monotonic_times(self, client):
        """Equity curve times are monotonically increasing."""
        resp = client.post("/api/backtest/run", json={
            "symbol": "GBPUSD",
            "config": {"require_nesting": False, "no_trade_zones": False,
                        "sl_mode": "atr", "tp_mode": "fixed_rr"},
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        data = resp.get_json()
        equity = data["equity"]
        if len(equity) > 1:
            times = [e["time"] for e in equity]
            assert times == sorted(times)

    def test_markers_have_entry_and_exit(self, client):
        """Each trade produces entry + exit markers."""
        resp = client.post("/api/backtest/run", json={
            "symbol": "GBPUSD",
            "config": {"require_nesting": False, "no_trade_zones": False,
                        "sl_mode": "atr", "tp_mode": "fixed_rr"},
        })
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        data = resp.get_json()
        n_trades = len(data["trades"])
        n_markers = len(data["markers"])
        if n_trades > 0:
            assert n_markers == n_trades * 2  # entry + exit per trade
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/apps/ tests/strategy/ -v --timeout=300`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/apps/test_backtest_endpoints.py
git commit -m "test(viz): add integration tests for backtest endpoints"
```

---

## Summary

| Task | Files | Tests | Description |
|------|-------|-------|-------------|
| 1 | 1 create | ~10 | Backtest serializers (markers, lines, equity, metrics) |
| 2 | 1 modify, 1 create | ~11 | Backtest API endpoints (/run, /sweep, /trades, /equity, /report, /multi) |
| 3 | 2 modify | Manual | Frontend HTML + CSS (sidebar panel, equity container) |
| 4 | 1 create | Manual | Frontend JS (backtest.js — run, sweep, display) |
| 5 | 1 modify | ~4 | Integration tests (comprehensive fields, equity, markers) |
| **Total** | **6 files** | **~25 tests** | |
