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


def test_limit_order_fills_when_price_reaches_zone():
    """Limit long: entry at zone_bottom + buffer; fills only if bar low reaches it."""
    ts = pd.Timestamp("2025-01-15 10:00")
    c = _candidate(ts=ts, side="demand", entry_price=1.2520,
                   zone_top=1.2510, zone_bottom=1.2490, atr=0.0030)
    # Limit price = zone_bottom + 0.1 * atr = 1.2490 + 0.0003 = 1.2493
    # Bar low must reach 1.2493 for fill
    bar_data = pd.DataFrame(
        {"open": [1.2520, 1.2500, 1.2530],
         "high": [1.2550, 1.2540, 1.2600],
         "low":  [1.2490, 1.2480, 1.2520],
         "close": [1.2510, 1.2530, 1.2580],
         "tick_volume": [100, 100, 100]},
        index=pd.date_range(ts, periods=3, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="limit", sl_mode="zone", fixed_rr=2.0,
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    assert len(result.trades) >= 1
    # Entry price should be the limit price, not the bar close
    trade = result.trades[0]
    expected_limit = 1.2490 + 0.1 * 0.0030  # 1.2493
    assert abs(trade.entry_price - expected_limit) < 1e-6


def test_limit_order_no_fill_when_price_doesnt_reach():
    """Limit long: if bar low never reaches zone_bottom + buffer, no entry."""
    ts = pd.Timestamp("2025-01-15 10:00")
    c = _candidate(ts=ts, side="demand", entry_price=1.2520,
                   zone_top=1.2510, zone_bottom=1.2490, atr=0.0030)
    # Limit price = 1.2493; bar lows stay above it
    bar_data = pd.DataFrame(
        {"open": [1.2520, 1.2530],
         "high": [1.2550, 1.2560],
         "low":  [1.2510, 1.2515],  # Never reaches 1.2493
         "close": [1.2530, 1.2540],
         "tick_volume": [100, 100]},
        index=pd.date_range(ts, periods=2, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="limit", sl_mode="zone", fixed_rr=2.0,
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    assert len(result.trades) == 0


def test_config_entry_mode_default():
    cfg = RetestConfig()
    assert cfg.entry_mode == "market"


def test_hma_filter_passes_matching_direction():
    """HMA direction filter keeps candidates matching HMA direction."""
    from iora.strategy.filter_funnel import apply_filters

    ts = pd.Timestamp("2025-01-15 10:00")
    # Long candidate with HMA H1 rising (+1)
    c_long = _candidate(ts=ts, side="demand")
    c_long = RetestCandidate(
        event=c_long.event, zone_top=c_long.zone_top, zone_bottom=c_long.zone_bottom,
        entry_price=c_long.entry_price, atr=c_long.atr,
        period_hi=c_long.period_hi, period_lo=c_long.period_lo,
        hma_direction_h1=1,  # rising
    )
    cfg = RetestConfig(tf_pair="H1@H4", hma_filter="with_hma_h1")
    funnel = apply_filters([c_long], cfg)
    assert len(funnel.passed) == 1  # passes — long + rising

    # Same candidate but HMA falling
    c_long_fall = RetestCandidate(
        event=c_long.event, zone_top=c_long.zone_top, zone_bottom=c_long.zone_bottom,
        entry_price=c_long.entry_price, atr=c_long.atr,
        period_hi=c_long.period_hi, period_lo=c_long.period_lo,
        hma_direction_h1=-1,  # falling
    )
    funnel2 = apply_filters([c_long_fall], cfg)
    assert len(funnel2.passed) == 0  # filtered — long + falling


def test_hma_cross_trigger_until_reverse():
    """HMA cross trigger with until_reverse keeps candidates while HA stays above HMA."""
    from iora.strategy.filter_funnel import apply_filters

    ts = pd.Timestamp("2025-01-15 10:00")
    # Long candidate: bullish cross happened, HA still above HMA
    c = _candidate(ts=ts, side="demand")
    c_above = RetestCandidate(
        event=c.event, zone_top=c.zone_top, zone_bottom=c.zone_bottom,
        entry_price=c.entry_price, atr=c.atr,
        period_hi=c.period_hi, period_lo=c.period_lo,
        hma_cross_direction_h1=1,  # bullish cross
        ha_above_hma_h1=True,      # still above
        bars_since_hma_cross_h1=50,
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", hma_cross_trigger="h1",
        hma_cross_lookback="until_reverse",
    )
    funnel = apply_filters([c_above], cfg)
    assert len(funnel.passed) == 1

    # Same but HA crossed back below (reversed)
    c_reversed = RetestCandidate(
        event=c.event, zone_top=c.zone_top, zone_bottom=c.zone_bottom,
        entry_price=c.entry_price, atr=c.atr,
        period_hi=c.period_hi, period_lo=c.period_lo,
        hma_cross_direction_h1=1,
        ha_above_hma_h1=False,     # reversed
        bars_since_hma_cross_h1=50,
    )
    funnel2 = apply_filters([c_reversed], cfg)
    assert len(funnel2.passed) == 0


def test_cascade_layered_produces_multiple_trades():
    """cascade_layered should produce multiple trades from one retest event
    when breaker zones are present and price reaches them."""
    ts = pd.Timestamp("2025-01-15 10:00")
    ev = OpportunityEvent(
        timestamp=ts, zone_tf="H4", entry_tf="H1", tf_pair="H1@H4",
        touch_type="wick_touch", zone_side="demand",
        zone_role="continuation", age_bucket="fresh",
        bias_alignment="with_daily", test_count_cls="retested_1",
        zone_age_bars=5, zone_test_count=1, bias_strength=2,
        price_distance_at_touch=1.5, replacement_count=0,
        birth_bias_d="unknown", birth_period_pattern="HH_HL",
        birth_price_distance=0.3,
    )
    # Context zone: 1.2490 - 1.2550, 3 breaker zones inside
    breaker_zones = [
        (1.2540, 1.2530, "M15"),  # shallowest
        (1.2520, 1.2510, "M5"),   # middle
        (1.2505, 1.2495, "M1"),   # deepest
    ]
    c = RetestCandidate(
        event=ev, zone_top=1.2550, zone_bottom=1.2490,
        entry_price=1.2520, atr=0.0030,
        period_hi=1.2600, period_lo=1.2450,
        breaker_zones=breaker_zones,
    )
    # Bar that reaches ALL breaker zone limits
    # Limit prices: brk_top + 0.1*atr = 1.2540+0.0003=1.2543, 1.2520+0.0003=1.2523, 1.2505+0.0003=1.2508
    # Bar low must reach all three → low=1.2480
    bar_data = pd.DataFrame(
        {"open": [1.2540, 1.2530, 1.2540, 1.2560, 1.2580],
         "high": [1.2560, 1.2560, 1.2570, 1.2590, 1.2700],
         "low":  [1.2480, 1.2510, 1.2530, 1.2540, 1.2560],
         "close": [1.2530, 1.2540, 1.2560, 1.2570, 1.2650],
         "tick_volume": [100]*5},
        index=pd.date_range(ts, periods=5, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="cascade_layered", layered_sl_mode="own",
        sl_mode="zone", fixed_rr=2.0, max_concurrent=3,
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    # Should have 3 trades (one per breaker zone)
    assert len(result.trades) == 3
    # All trade IDs should contain _L suffix
    for t in result.trades:
        assert "_L" in t.trade_id


def test_cascade_layered_sl_modes():
    """layered_sl_mode='own' uses breaker zone boundary; 'htf' uses context zone."""
    from iora.strategy.retest_sl_tp import compute_layered_sl

    atr = 0.0030
    buf = 0.15 * atr

    # Own SL: behind each breaker zone
    sl_own = compute_layered_sl(
        direction="long", brk_top=1.2520, brk_bottom=1.2510,
        ctx_zone_top=1.2550, ctx_zone_bottom=1.2490,
        atr=atr, mode="own",
    )
    assert abs(sl_own - (1.2510 - buf)) < 1e-8

    # HTF SL: behind the context zone
    sl_htf = compute_layered_sl(
        direction="long", brk_top=1.2520, brk_bottom=1.2510,
        ctx_zone_top=1.2550, ctx_zone_bottom=1.2490,
        atr=atr, mode="htf",
    )
    assert abs(sl_htf - (1.2490 - buf)) < 1e-8

    # HTF SL should be further away (lower for longs)
    assert sl_htf < sl_own

    # Short direction
    sl_own_short = compute_layered_sl(
        direction="short", brk_top=1.2530, brk_bottom=1.2520,
        ctx_zone_top=1.2550, ctx_zone_bottom=1.2490,
        atr=atr, mode="own",
    )
    assert abs(sl_own_short - (1.2530 + buf)) < 1e-8

    sl_htf_short = compute_layered_sl(
        direction="short", brk_top=1.2530, brk_bottom=1.2520,
        ctx_zone_top=1.2550, ctx_zone_bottom=1.2490,
        atr=atr, mode="htf",
    )
    assert abs(sl_htf_short - (1.2550 + buf)) < 1e-8
    assert sl_htf_short > sl_own_short


def test_partial_tp_full_win():
    """Partial TP: both Unit 1 and Unit 2 hit → blended P&L."""
    ts = pd.Timestamp("2025-01-15 10:00")
    # Long demand: entry at zone bottom, opposing H1 zone above
    c = _candidate(ts=ts, side="demand", entry_price=1.2500,
                   zone_top=1.2510, zone_bottom=1.2490, atr=0.0030)
    # Set opposing_zone_h1 for the HTF TP target
    c = RetestCandidate(
        event=c.event, zone_top=c.zone_top, zone_bottom=c.zone_bottom,
        entry_price=c.entry_price, atr=c.atr,
        period_hi=c.period_hi, period_lo=c.period_lo,
        opposing_zone_h1=1.2700,  # H1 TP target — 200 pips above entry
    )
    # Limit price = zone_bottom + 0.1 * atr = 1.2490 + 0.0003 = 1.2493
    # SL = zone_bottom - 0.15 * atr = 1.2490 - 0.00045 = 1.24855
    # Risk = 1.2493 - 1.24855 = 0.00075
    # Unit 1 TP @ rr=3.0: 1.2493 + 3.0 * 0.00075 = 1.25155
    # Unit 2 TP @ H1 zone: 1.2700
    #
    # Bar 1: entry bar (low reaches limit)
    # Bar 2: price rises to hit Unit 1 TP (high >= 1.25155)
    # Bar 3: price keeps rising to hit Unit 2 TP (high >= 1.2700)
    bar_data = pd.DataFrame(
        {"open": [1.2510, 1.2510, 1.2600],
         "high": [1.2520, 1.2520, 1.2750],  # Bar 3 hits H1 TP
         "low":  [1.2480, 1.2500, 1.2580],  # Bar 1 reaches limit
         "close": [1.2510, 1.2515, 1.2720],
         "tick_volume": [100, 100, 100]},
        index=pd.date_range(ts, periods=3, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="limit", sl_mode="zone",
        partial_tp=True, partial_unit1_pct=0.5,
        partial_unit1_rr=3.0, partial_unit2_tp="H1",
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "partial_full"
    assert trade.pnl_pips > 0  # positive — both units won


def test_partial_tp_breakeven():
    """Partial TP: Unit 1 locks profit, Unit 2 hits breakeven → positive P&L."""
    ts = pd.Timestamp("2025-01-15 10:00")
    c = _candidate(ts=ts, side="demand", entry_price=1.2500,
                   zone_top=1.2510, zone_bottom=1.2490, atr=0.0030)
    c = RetestCandidate(
        event=c.event, zone_top=c.zone_top, zone_bottom=c.zone_bottom,
        entry_price=c.entry_price, atr=c.atr,
        period_hi=c.period_hi, period_lo=c.period_lo,
        opposing_zone_h1=1.2700,  # Far away — Unit 2 won't reach
    )
    # Limit price = 1.2493, SL = 1.24855, risk = 0.00075
    # Unit 1 TP = 1.2493 + 3.0 * 0.00075 = 1.25155
    #
    # Bar 1: entry (low reaches limit)
    # Bar 2: rises to hit Unit 1 TP → SL moves to breakeven (1.2493)
    # Bar 3: drops back to breakeven → Unit 2 closed at entry price
    bar_data = pd.DataFrame(
        {"open": [1.2510, 1.2510, 1.2520],
         "high": [1.2520, 1.2520, 1.2530],  # Bar 2 hits Unit 1 TP
         "low":  [1.2480, 1.2500, 1.2490],  # Bar 3 hits breakeven SL
         "close": [1.2510, 1.2515, 1.2495],
         "tick_volume": [100, 100, 100]},
        index=pd.date_range(ts, periods=3, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="limit", sl_mode="zone",
        partial_tp=True, partial_unit1_pct=0.5,
        partial_unit1_rr=3.0, partial_unit2_tp="H1",
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "partial_be"
    # P&L should be positive — Unit 1 profit locked
    assert trade.pnl_pips > 0


def test_partial_tp_sl_hit():
    """Partial TP: SL hit before Unit 1 locks → full loss."""
    ts = pd.Timestamp("2025-01-15 10:00")
    c = _candidate(ts=ts, side="demand", entry_price=1.2500,
                   zone_top=1.2510, zone_bottom=1.2490, atr=0.0030)
    c = RetestCandidate(
        event=c.event, zone_top=c.zone_top, zone_bottom=c.zone_bottom,
        entry_price=c.entry_price, atr=c.atr,
        period_hi=c.period_hi, period_lo=c.period_lo,
        opposing_zone_h1=1.2700,
    )
    # Limit price = 1.2493, SL = 1.24855
    #
    # Bar 1: entry (low reaches limit)
    # Bar 2: drops to SL → full loss on both units
    bar_data = pd.DataFrame(
        {"open": [1.2510, 1.2495],
         "high": [1.2520, 1.2500],
         "low":  [1.2480, 1.2480],  # Bar 2: SL hit
         "close": [1.2510, 1.2485],
         "tick_volume": [100, 100]},
        index=pd.date_range(ts, periods=2, freq="1h"),
    )
    cfg = RetestConfig(
        tf_pair="H1@H4", touch_type="wick_touch", bias_filter="with_daily",
        entry_mode="limit", sl_mode="zone",
        partial_tp=True, partial_unit1_pct=0.5,
        partial_unit1_rr=3.0, partial_unit2_tp="H1",
    )
    result = evaluate_retest_config([c], cfg, symbol="GBPUSD", bar_data=bar_data)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "sl_hit"
    assert trade.pnl_pips < 0  # full loss
