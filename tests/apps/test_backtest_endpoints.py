"""Tests for backtest API endpoints in chart_viewer_lw.py."""
from __future__ import annotations

import sys

sys.path.insert(0, "apps")
sys.path.insert(0, "src")

import pytest


@pytest.fixture(scope="module")
def client():
    try:
        from apps.chart_viewer_lw import app

        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c
    except Exception as e:
        pytest.skip(f"Flask app not available: {e}")


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset flask-limiter storage before each test so rate limits don't accumulate."""
    try:
        from apps.chart_viewer_lw import limiter

        if limiter is not None:
            limiter.reset()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# POST /api/backtest/run
# ---------------------------------------------------------------------------


class TestBacktestRunEndpoint:
    def test_run_requires_symbol(self, client):
        resp = client.post("/api/backtest/run", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_run_rejects_unknown_symbol(self, client):
        resp = client.post("/api/backtest/run", json={"symbol": "FAKEXYZ"})
        assert resp.status_code == 400

    def test_run_returns_trades_and_metrics(self, client):
        resp = client.post(
            "/api/backtest/run",
            json={"symbol": "GBPUSD", "config": {"require_nesting": False}},
        )
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert "metrics" in data
        assert "metrics_raw" in data
        assert "equity" in data
        assert "equity_r" in data
        assert "markers" in data
        assert "trade_lines" in data
        assert "total_signals" in data
        assert "config" in data
        assert isinstance(data["trades"], list)
        assert isinstance(data["metrics"], dict)

    def test_run_accepts_config_overrides(self, client):
        resp = client.post(
            "/api/backtest/run",
            json={
                "symbol": "GBPUSD",
                "config": {
                    "require_nesting": False,
                    "no_trade_zones": False,
                    "signal_types": ["push"],
                },
            },
        )
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["config"]["require_nesting"] is False


# ---------------------------------------------------------------------------
# POST /api/backtest/sweep
# ---------------------------------------------------------------------------


class TestBacktestSweepEndpoint:
    def test_sweep_requires_symbol(self, client):
        resp = client.post("/api/backtest/sweep", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_sweep_rejects_unknown_symbol(self, client):
        resp = client.post("/api/backtest/sweep", json={"symbol": "FAKEXYZ"})
        assert resp.status_code == 400

    def test_sweep_rejects_invalid_dimension_field(self, client):
        resp = client.post(
            "/api/backtest/sweep",
            json={
                "symbol": "GBPUSD",
                "dimensions": {"not_a_real_field": [True, False]},
            },
        )
        # Either 400 (invalid field) or 404 (no data) — both acceptable
        assert resp.status_code in (400, 404)

    def test_sweep_returns_results(self, client):
        resp = client.post(
            "/api/backtest/sweep",
            json={
                "symbol": "GBPUSD",
                "dimensions": {"require_nesting": [True, False]},
            },
        )
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert "n_configs" in data
        assert data["n_configs"] == 2
        assert data["symbol"] == "GBPUSD"
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2
        for row in data["results"]:
            assert "config" in row
            assert "metrics" in row

    def test_sweep_rejects_too_many_configs(self, client):
        # 201 configs: 3 * 67 = 201 > 200
        resp = client.post(
            "/api/backtest/sweep",
            json={
                "symbol": "GBPUSD",
                "dimensions": {
                    "fixed_rr": [round(1.0 + i * 0.1, 1) for i in range(67)],
                    "require_nesting": [True, False, True],
                },
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Too many configs" in data["error"]


# ---------------------------------------------------------------------------
# GET /api/backtest/trades
# ---------------------------------------------------------------------------


class TestBacktestTradesEndpoint:
    def test_trades_requires_symbol(self, client):
        resp = client.get("/api/backtest/trades")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_trades_rejects_unknown_symbol(self, client):
        resp = client.get("/api/backtest/trades?symbol=FAKEXYZ")
        assert resp.status_code == 400

    def test_trades_returns_list(self, client):
        resp = client.get("/api/backtest/trades?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "trades" in data
        assert "total" in data
        assert "symbol" in data
        assert isinstance(data["trades"], list)
        assert data["total"] == len(data["trades"])
        assert data["symbol"] == "GBPUSD"

    def test_trades_each_record_has_required_fields(self, client):
        resp = client.get("/api/backtest/trades?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        if not data["trades"]:
            pytest.skip("No trades returned")
        trade = data["trades"][0]
        for field in ("trade_id", "direction", "entry_time", "exit_time",
                      "entry_price", "exit_price", "pnl_pips", "return_r",
                      "signal_type", "is_winner"):
            assert field in trade, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/backtest/equity
# ---------------------------------------------------------------------------


class TestBacktestEquityEndpoint:
    def test_equity_requires_symbol(self, client):
        resp = client.get("/api/backtest/equity")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_equity_rejects_unknown_symbol(self, client):
        resp = client.get("/api/backtest/equity?symbol=FAKEXYZ")
        assert resp.status_code == 400

    def test_equity_returns_curve(self, client):
        resp = client.get("/api/backtest/equity?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "equity" in data
        assert "mode" in data
        assert "symbol" in data
        assert data["mode"] == "pips"
        assert isinstance(data["equity"], list)

    def test_equity_mode_r(self, client):
        resp = client.get("/api/backtest/equity?symbol=GBPUSD&mode=r")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["mode"] == "r"
        assert isinstance(data["equity"], list)

    def test_equity_points_have_time_and_value(self, client):
        resp = client.get("/api/backtest/equity?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        for point in data["equity"]:
            assert "time" in point
            assert "value" in point


# ---------------------------------------------------------------------------
# GET /api/backtest/report
# ---------------------------------------------------------------------------


class TestBacktestReportEndpoint:
    def test_report_requires_symbol(self, client):
        resp = client.get("/api/backtest/report")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_report_rejects_unknown_symbol(self, client):
        resp = client.get("/api/backtest/report?symbol=FAKEXYZ")
        assert resp.status_code == 400

    def test_report_returns_metrics(self, client):
        resp = client.get("/api/backtest/report?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "metrics" in data
        assert "metrics_raw" in data
        assert "config" in data
        assert "symbol" in data
        assert "total_bars" in data
        assert data["symbol"] == "GBPUSD"
        assert isinstance(data["total_bars"], int)
        assert data["total_bars"] >= 0

    def test_report_metrics_has_sections(self, client):
        resp = client.get("/api/backtest/report?symbol=GBPUSD")
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        metrics = data["metrics"]
        for section in ("overview", "risk_adjusted", "pnl", "drawdown", "streaks"):
            assert section in metrics, f"Missing metrics section: {section}"


# ---------------------------------------------------------------------------
# POST /api/backtest/multi
# ---------------------------------------------------------------------------


class TestBacktestMultiEndpoint:
    def test_multi_requires_symbols(self, client):
        resp = client.post("/api/backtest/multi", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_multi_requires_symbols_to_be_a_list(self, client):
        resp = client.post("/api/backtest/multi", json={"symbols": "GBPUSD"})
        assert resp.status_code == 400

    def test_multi_rejects_unknown_symbols(self, client):
        resp = client.post(
            "/api/backtest/multi", json={"symbols": ["GBPUSD", "FAKEXYZ"]}
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "FAKEXYZ" in data["error"]

    def test_multi_rejects_too_many_symbols(self, client):
        symbols = [f"SYM{i:02d}" for i in range(11)]
        resp = client.post("/api/backtest/multi", json={"symbols": symbols})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "Too many symbols" in data["error"]

    def test_multi_returns_per_symbol(self, client):
        resp = client.post(
            "/api/backtest/multi",
            json={
                "symbols": ["GBPUSD"],
                "config": {"require_nesting": False},
            },
        )
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert "symbols" in data
        assert "GBPUSD" in data["results"]
        gbp = data["results"]["GBPUSD"]
        # Either has error (no data) or full results
        if "error" not in gbp:
            assert "metrics" in gbp
            assert "equity" in gbp
            assert "total_trades" in gbp

    def test_multi_result_structure(self, client):
        resp = client.post(
            "/api/backtest/multi",
            json={"symbols": ["GBPUSD"]},
        )
        if resp.status_code == 404:
            pytest.skip("GBPUSD data not available")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["symbols"] == ["GBPUSD"]
        gbp = data["results"]["GBPUSD"]
        if "error" not in gbp:
            metrics = gbp["metrics"]
            for section in ("overview", "risk_adjusted", "pnl", "drawdown", "streaks"):
                assert section in metrics


# ---------------------------------------------------------------------------
# Integration: deeper assertions across run response
# ---------------------------------------------------------------------------


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
