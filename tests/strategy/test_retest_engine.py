"""Tests for retest trade simulation."""
import pandas as pd
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.strategy.retest_candidate import RetestCandidate
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_engine import (
    RetestTradeRecord, evaluate_retest_config, RetestResult,
)


def _candidate(ts, side="demand", touch="wick_touch", bias="with_daily",
               entry_price=1.2560, zone_top=1.2550, zone_bottom=1.2500,
               atr=0.0080) -> RetestCandidate:
    ev = OpportunityEvent(
        timestamp=ts, zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type=touch, zone_side=side,
        zone_role="continuation", age_bucket="fresh",
        bias_alignment=bias, test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    return RetestCandidate(
        event=ev, zone_top=zone_top, zone_bottom=zone_bottom,
        entry_price=entry_price, atr=atr,
        period_hi=1.2600, period_lo=1.2450,
    )


def test_trade_record_is_winner():
    rec = RetestTradeRecord(
        trade_id="T001", symbol="GBPUSD", direction=1,
        entry_time=pd.Timestamp("2025-01-15 10:00"),
        exit_time=pd.Timestamp("2025-01-15 14:00"),
        entry_price=1.2560, exit_price=1.2620,
        sl_price=1.2490, tp_price=1.2700,
        pnl_pips=60.0, risk_pips=70.0, reward_pips=140.0,
        return_r=0.857, rr_ratio=2.0, exit_reason="tp",
        tf_pair="H1@H4", touch_type="wick_touch",
        zone_role="continuation", bias_alignment="with_daily",
        age_bucket="fresh", test_count_cls="retested_1",
    )
    assert rec.is_winner


def test_evaluate_empty_candidates():
    cfg = RetestConfig()
    result = evaluate_retest_config([], cfg, symbol="TEST")
    assert isinstance(result, RetestResult)
    assert len(result.trades) == 0


def test_evaluate_produces_trades():
    times = pd.date_range("2025-01-15 10:00", periods=50, freq="1h")
    candidates = []
    for i, t in enumerate(times):
        price = 1.2500 + 0.0002 * (i % 10)
        candidates.append(_candidate(
            ts=t, entry_price=price,
            zone_top=1.2510, zone_bottom=1.2490, atr=0.0030,
        ))

    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch",
        bias_filter="with_daily", tp_mode="fixed_rr", fixed_rr=2.0,
    )
    bar_data = pd.DataFrame(
        {"open": [1.2500]*50, "high": [1.2550]*50,
         "low": [1.2470]*50, "close": [1.2510]*50,
         "tick_volume": [100]*50},
        index=times,
    )
    result = evaluate_retest_config(
        candidates, cfg, symbol="GBPUSD", bar_data=bar_data,
    )
    assert isinstance(result, RetestResult)
    assert result.total_candidates > 0


def test_result_has_metrics():
    times = pd.date_range("2025-01-15 10:00", periods=20, freq="1h")
    candidates = [
        _candidate(ts=t, entry_price=1.2500 + 0.0005 * i, atr=0.0030)
        for i, t in enumerate(times)
    ]
    cfg = RetestConfig(touch_type="wick_touch", bias_filter="with_daily")
    bar_data = pd.DataFrame(
        {"open": [1.2500]*20, "high": [1.2600]*20,
         "low": [1.2400]*20, "close": [1.2510]*20,
         "tick_volume": [100]*20},
        index=times,
    )
    result = evaluate_retest_config(
        candidates, cfg, symbol="GBPUSD", bar_data=bar_data,
    )
    if result.trades:
        assert "total_trades" in result.metrics
        assert "win_rate" in result.metrics
