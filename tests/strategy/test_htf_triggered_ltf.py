"""Tests for HTF-triggered LTF entry system."""
import pandas as pd
import pytest
from iora.strategy.retest_config import RetestConfig
from iora.strategy.retest_candidate import (
    ZoneBirthEvent, CandidateBuildResult, RetestCandidate,
    _find_nested_ltf_zones, build_retest_candidates_with_births,
)
from iora.diagnostics.opportunity_counter import OpportunityEvent
from iora.engine.push_zone_models import PushZone, PushZoneTickState
from iora.orchestrator.push_zone_engine import PushZoneEngineState


class TestHTFTriggeredConfig:
    def test_default_ltf_nesting_is_none(self):
        cfg = RetestConfig()
        assert cfg.ltf_nesting == "none"

    def test_default_trigger_tf_pair(self):
        cfg = RetestConfig()
        assert cfg.trigger_tf_pair == "H1@H4"

    def test_default_entry_tf_override_empty(self):
        cfg = RetestConfig()
        assert cfg.entry_tf_override == ""

    def test_default_trigger_window_bars(self):
        cfg = RetestConfig()
        assert cfg.trigger_window_bars == 48

    def test_default_require_ltf_push_false(self):
        cfg = RetestConfig()
        assert cfg.require_ltf_push is False

    def test_default_trigger_also_trades_false(self):
        cfg = RetestConfig()
        assert cfg.trigger_also_trades is False

    def test_default_max_ltf_per_trigger(self):
        cfg = RetestConfig()
        assert cfg.max_ltf_per_trigger == 3

    def test_static_nesting_config(self):
        cfg = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit", limit_edge="top",
            ltf_nesting="static", entry_tf_override="M15", limit_ttl=0,
        )
        assert cfg.ltf_nesting == "static"
        assert cfg.entry_tf == "H1"
        assert cfg.zone_tf == "H4"
        assert cfg.entry_tf_override == "M15"

    def test_dynamic_nesting_config(self):
        cfg = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit",
            ltf_nesting="dynamic", entry_tf_override="M5",
            trigger_window_bars=24,
        )
        assert cfg.ltf_nesting == "dynamic"
        assert cfg.trigger_window_bars == 24


class TestZoneBirthEvent:
    def test_create_demand_birth(self):
        ev = ZoneBirthEvent(
            timestamp=pd.Timestamp("2020-01-01 12:00"),
            zone_top=1.3010, zone_bottom=1.3000,
            zone_tf="M15", zone_side="demand",
            is_push=True,
            origin_time=pd.Timestamp("2020-01-01 11:45"),
        )
        assert ev.zone_side == "demand"
        assert ev.is_push is True
        assert ev.origin_time == pd.Timestamp("2020-01-01 11:45")

    def test_create_supply_birth(self):
        ev = ZoneBirthEvent(
            timestamp=pd.Timestamp("2020-01-01 12:00"),
            zone_top=1.3100, zone_bottom=1.3090,
            zone_tf="M5", zone_side="supply",
            is_push=False,
            origin_time=pd.Timestamp("2020-01-01 11:50"),
        )
        assert ev.zone_side == "supply"
        assert ev.is_push is False


class TestCandidateBuildResult:
    def test_empty_result(self):
        result = CandidateBuildResult(candidates=[], zone_births={})
        assert len(result.candidates) == 0
        assert len(result.zone_births) == 0

    def test_result_with_births(self):
        ts = pd.Timestamp("2020-01-01 12:00")
        ev = ZoneBirthEvent(
            timestamp=ts, zone_top=1.3010, zone_bottom=1.3000,
            zone_tf="M15", zone_side="demand",
            is_push=True,
            origin_time=ts,
        )
        result = CandidateBuildResult(candidates=[], zone_births={ts: [ev]})
        assert len(result.zone_births[ts]) == 1


def _make_event(**kwargs) -> OpportunityEvent:
    defaults = dict(
        timestamp=pd.Timestamp("2020-01-01 12:00"),
        tf_pair="H1@H4", entry_tf="H1", zone_tf="H4",
        zone_side="demand", touch_type="wick_touch",
        zone_role="push", age_bucket="young",
        test_count_cls="retested_1", bias_alignment="with_daily",
        bias_strength=2, replacement_count=0,
        price_distance_at_touch=0.0005, birth_period_pattern="HH_HL",
        zone_age_bars=50, zone_test_count=1,
    )
    defaults.update(kwargs)
    return OpportunityEvent(**defaults)


class TestNestedLtfZonesField:
    def test_default_empty(self):
        c = RetestCandidate(
            event=_make_event(), zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020, period_hi=1.3100, period_lo=1.2950,
        )
        assert c.nested_ltf_zones == []

    def test_with_nested_zones(self):
        c = RetestCandidate(
            event=_make_event(), zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020, period_hi=1.3100, period_lo=1.2950,
            nested_ltf_zones=[
                (1.3020, 1.3010, "M15", "demand", True),
                (1.3035, 1.3025, "M15", "demand", False),
            ],
        )
        assert len(c.nested_ltf_zones) == 2
        assert c.nested_ltf_zones[0] == (1.3020, 1.3010, "M15", "demand", True)


# ── Task 4: _find_nested_ltf_zones tests ─────────────────────────────────

def _make_zone(top, bottom, is_supply, tf="M15", is_push=False, is_reversal=False):
    """Create a PushZone for testing."""
    return PushZone(
        top=top, bottom=bottom, is_supply=is_supply,
        origin_time=pd.Timestamp("2020-01-01"),
        timeframe=tf, is_push=is_push, is_reversal=is_reversal,
        struct_cls="", swing_cls="",
    )


class TestFindNestedLtfZones:
    """_find_nested_ltf_zones() — geometric containment check."""

    def test_demand_zone_inside_demand_h4(self):
        """M15 demand zone geometrically inside H4 demand zone."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3020, 1.3010, is_supply=False, tf="M15"),  # inside
                    _make_zone(1.2980, 1.2970, is_supply=False, tf="M15"),  # outside (below)
                ],
                supply_zones=[
                    _make_zone(1.3040, 1.3030, is_supply=True, tf="M15"),  # wrong side
                ],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )

        assert len(result) == 1
        assert result[0][:2] == (1.3020, 1.3010)
        assert result[0][2] == "M15"
        assert result[0][3] == "demand"

    def test_supply_zone_inside_supply_h4(self):
        """M15 supply zone inside H4 supply zone."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                supply_zones=[
                    _make_zone(1.3090, 1.3080, is_supply=True, tf="M15"),  # inside
                ],
                demand_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="supply",
            ctx_zone_top=1.3100,
            ctx_zone_bottom=1.3050,
            require_push=False,
        )

        assert len(result) == 1
        assert result[0][:2] == (1.3090, 1.3080)
        assert result[0][3] == "supply"

    def test_require_push_filters_non_push(self):
        """When require_push=True, only push zones returned."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3020, 1.3010, is_supply=False, tf="M15", is_push=False),
                    _make_zone(1.3035, 1.3025, is_supply=False, tf="M15", is_push=True),
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=True,
        )

        assert len(result) == 1
        assert result[0][4] is True  # is_push

    def test_no_nested_zones_returns_empty(self):
        """No LTF zones inside H4 zone."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.2990, 1.2980, is_supply=False, tf="M15"),  # below H4 zone
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )

        assert result == []

    def test_missing_ltf_tf_returns_empty(self):
        """LTF TF not in state returns empty list."""
        state = PushZoneEngineState(tick_states={})
        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M5",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
        )
        assert result == []

    def test_max_zones_limit(self):
        """Returns at most max_zones results."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3010 + i * 0.0005, 1.3005 + i * 0.0005,
                               is_supply=False, tf="M15")
                    for i in range(5)
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state,
            ltf_tf="M15",
            zone_side="demand",
            ctx_zone_top=1.3050,
            ctx_zone_bottom=1.3000,
            require_push=False,
            max_zones=3,
        )

        assert len(result) <= 3

    def test_demand_sorted_by_top_descending(self):
        """Demand zones sorted by zone_top descending (nearest to entry first)."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                demand_zones=[
                    _make_zone(1.3010, 1.3005, is_supply=False, tf="M15"),
                    _make_zone(1.3040, 1.3035, is_supply=False, tf="M15"),
                    _make_zone(1.3025, 1.3020, is_supply=False, tf="M15"),
                ],
                supply_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state, ltf_tf="M15", zone_side="demand",
            ctx_zone_top=1.3050, ctx_zone_bottom=1.3000,
        )

        tops = [r[0] for r in result]
        assert tops == sorted(tops, reverse=True)

    def test_supply_sorted_by_bottom_ascending(self):
        """Supply zones sorted by zone_bottom ascending (nearest to entry first)."""
        state = PushZoneEngineState(tick_states={
            "M15": PushZoneTickState(
                supply_zones=[
                    _make_zone(1.3090, 1.3085, is_supply=True, tf="M15"),
                    _make_zone(1.3070, 1.3060, is_supply=True, tf="M15"),
                    _make_zone(1.3080, 1.3075, is_supply=True, tf="M15"),
                ],
                demand_zones=[],
            ),
        })

        result = _find_nested_ltf_zones(
            state=state, ltf_tf="M15", zone_side="supply",
            ctx_zone_top=1.3100, ctx_zone_bottom=1.3050,
        )

        bottoms = [r[1] for r in result]
        assert bottoms == sorted(bottoms)


# ── Task 5: Static nesting enrichment tests ──────────────────────────────

class TestStaticNestingEnrichment:
    """Static nesting enrichment during candidate building."""

    def test_enrichment_populates_nested_zones(self):
        """When nested zones present, candidate stores them correctly."""
        event = _make_event(tf_pair="H1@H4", zone_tf="H4", zone_side="demand")
        c = RetestCandidate(
            event=event,
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            nested_ltf_zones=[(1.3020, 1.3010, "M15", "demand", True)],
        )
        assert len(c.nested_ltf_zones) == 1
        top, bot, tf, side, is_push = c.nested_ltf_zones[0]
        assert tf == "M15"
        assert top > bot
        assert bot >= c.zone_bottom
        assert top <= c.zone_top
        assert is_push is True


# ── Task 6: Zone birth collection tests ──────────────────────────────────

class TestZoneBirthCollection:
    """Zone birth event collection during candidate building."""

    def test_build_with_births_returns_result(self):
        """build_retest_candidates_with_births returns CandidateBuildResult."""
        result = build_retest_candidates_with_births(
            data_by_tf={}, entry_tf="M5", symbol="TEST",
        )
        assert isinstance(result, CandidateBuildResult)
        assert result.candidates == []
        assert result.zone_births == {}

    def test_build_with_births_no_birth_tfs_empty_births(self):
        """Without birth_tfs, zone_births is empty even with data."""
        result = build_retest_candidates_with_births(
            data_by_tf={}, entry_tf="M5", symbol="TEST",
            birth_tfs=None,
        )
        assert result.zone_births == {}

    def test_build_with_births_birth_tfs_specified(self):
        """With birth_tfs, the function accepts the parameter."""
        result = build_retest_candidates_with_births(
            data_by_tf={}, entry_tf="M5", symbol="TEST",
            birth_tfs=["M15", "M5"],
        )
        assert isinstance(result, CandidateBuildResult)
        assert result.zone_births == {}  # No data = no births


# ── Task 7: Static nesting simulation tests ────────────────────────────

from iora.strategy.retest_engine import _simulate_with_bars, RetestTradeRecord


class TestStaticNestingSimulation:
    """Static nesting path in _simulate_with_bars."""

    def _make_candidate_with_nested(self, nested_zones):
        """Create a candidate with nested LTF zones for simulation."""
        return RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050,
            zone_bottom=1.3000,
            entry_price=1.3025,
            atr=0.0020,
            period_hi=1.3100,
            period_lo=1.2950,
            opposing_zone_h4=1.3200,
            nested_ltf_zones=nested_zones,
        )

    def test_static_nesting_creates_limit_at_ltf_zone_top(self):
        """Static nesting places limit at LTF zone top for demand."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            partial_tp=False,
            fixed_rr=3.0,
            spread_pips=0.0,
        )

        nested = [(1.3020, 1.3010, "M15", "demand", True)]
        candidate = self._make_candidate_with_nested(nested)

        # Bar data: price dips to fill limit at LTF zone top (~1.3020),
        # then rallies to hit TP
        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015, 1.3025, 1.3050, 1.3100],
            "high": [1.3035, 1.3025, 1.3060, 1.3080, 1.3110],
            "low":  [1.3015, 1.3008, 1.3020, 1.3040, 1.3090],
            "close":[1.3020, 1.3020, 1.3050, 1.3070, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        # Must produce at least one trade from the nested LTF zone
        assert len(trades) >= 1, "Expected at least one trade from static nesting"
        t = trades[0]
        # SL should be near LTF zone bottom (1.3010), not H4 (1.3000)
        assert t.sl_price > 1.3000, f"SL {t.sl_price} should be above H4 bottom 1.3000"

    def test_static_nesting_no_nested_zones_no_trade(self):
        """If no nested LTF zones, static nesting skips the candidate (no trade)."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = self._make_candidate_with_nested([])

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015],
            "high": [1.3035, 1.3025],
            "low":  [1.3015, 1.3008],
            "close":[1.3020, 1.3020],
        }, index=pd.date_range("2020-01-02 08:00", periods=2, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        assert len(trades) == 0

    def test_static_nesting_supply_side(self):
        """Static nesting for supply side places limit at LTF zone bottom."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
            spread_pips=0.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="supply",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3100,
            zone_bottom=1.3050,
            entry_price=1.3075,
            atr=0.0020,
            period_hi=1.3150,
            period_lo=1.2950,
            opposing_zone_h4=1.2900,
            nested_ltf_zones=[(1.3090, 1.3080, "M15", "supply", False)],
        )

        # Price rallies up to fill the supply limit, then drops to TP
        bar_data = pd.DataFrame({
            "open": [1.3070, 1.3085, 1.3075, 1.3050, 1.3020],
            "high": [1.3090, 1.3095, 1.3080, 1.3060, 1.3030],
            "low":  [1.3065, 1.3075, 1.3040, 1.3010, 1.2990],
            "close":[1.3085, 1.3080, 1.3050, 1.3020, 1.3000],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        assert len(trades) >= 1
        t = trades[0]
        # SL should be near LTF zone top (1.3090), not H4 (1.3100)
        assert t.sl_price < 1.3100, f"SL {t.sl_price} should be below H4 top 1.3100"

    def test_static_nesting_max_ltf_per_trigger(self):
        """Static nesting respects max_ltf_per_trigger limit."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="static",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
            spread_pips=0.0,
            max_ltf_per_trigger=1,
        )

        # Two nested zones, but max_ltf=1
        nested = [
            (1.3020, 1.3010, "M15", "demand", True),
            (1.3035, 1.3025, "M15", "demand", False),
        ]
        candidate = self._make_candidate_with_nested(nested)

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015, 1.3050, 1.3080, 1.3100],
            "high": [1.3035, 1.3025, 1.3060, 1.3090, 1.3110],
            "low":  [1.3005, 1.3005, 1.3040, 1.3070, 1.3090],
            "close":[1.3020, 1.3020, 1.3050, 1.3080, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
        )

        # max_ltf_per_trigger=1, so at most 1 trade
        assert len(trades) <= 1

    def test_static_nesting_filters_by_entry_tf_override(self):
        """Static nesting only uses zones matching config.entry_tf_override."""
        # Candidate has zones from both M15 and M5 (as built with ltf_tf="")
        nested = [
            (1.3020, 1.3010, "M15", "demand", True),
            (1.3035, 1.3025, "M5", "demand", True),
        ]
        candidate = self._make_candidate_with_nested(nested)

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015, 1.3050, 1.3080, 1.3100],
            "high": [1.3035, 1.3025, 1.3060, 1.3090, 1.3110],
            "low":  [1.3005, 1.3005, 1.3040, 1.3070, 1.3090],
            "close":[1.3020, 1.3020, 1.3050, 1.3080, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        pip_size = _get_pip_size("GBPUSD")

        # Config asks for M5 only — should skip the M15 zone
        cfg_m5 = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit", limit_edge="top",
            ltf_nesting="static", entry_tf_override="M5",
            limit_ttl=0, fixed_rr=3.0, spread_pips=0.0,
        )
        trades_m5 = _simulate_with_bars([candidate], cfg_m5, "GBPUSD", bar_data, pip_size)

        # Config asks for M15 only — should skip the M5 zone
        cfg_m15 = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit", limit_edge="top",
            ltf_nesting="static", entry_tf_override="M15",
            limit_ttl=0, fixed_rr=3.0, spread_pips=0.0,
        )
        trades_m15 = _simulate_with_bars([candidate], cfg_m15, "GBPUSD", bar_data, pip_size)

        # Both should produce trades, but from different zones
        assert len(trades_m5) >= 1
        assert len(trades_m15) >= 1
        # M5 zone top=1.3035, M15 zone top=1.3020 — different SL levels
        assert trades_m5[0].sl_price != trades_m15[0].sl_price, \
            "M5 and M15 overrides should produce different SL levels"

    def test_static_nesting_require_ltf_push_filters(self):
        """Static nesting with require_ltf_push=True skips non-push zones."""
        # Two nested zones: one push, one not
        nested = [
            (1.3020, 1.3010, "M15", "demand", False),  # not push
            (1.3035, 1.3025, "M15", "demand", True),    # push
        ]
        candidate = self._make_candidate_with_nested(nested)

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3015, 1.3050, 1.3080, 1.3100],
            "high": [1.3035, 1.3025, 1.3060, 1.3090, 1.3110],
            "low":  [1.3005, 1.3005, 1.3040, 1.3070, 1.3090],
            "close":[1.3020, 1.3020, 1.3050, 1.3080, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        pip_size = _get_pip_size("GBPUSD")

        # With push filter: should only use the push zone
        cfg_push = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit", limit_edge="top",
            ltf_nesting="static", entry_tf_override="M15",
            limit_ttl=0, fixed_rr=3.0, spread_pips=0.0,
            require_ltf_push=True, max_ltf_per_trigger=3,
        )
        trades_push = _simulate_with_bars([candidate], cfg_push, "GBPUSD", bar_data, pip_size)

        # Without push filter: should use both zones
        cfg_no_push = RetestConfig(
            tf_pair="H1@H4", entry_mode="limit", limit_edge="top",
            ltf_nesting="static", entry_tf_override="M15",
            limit_ttl=0, fixed_rr=3.0, spread_pips=0.0,
            require_ltf_push=False, max_ltf_per_trigger=3,
        )
        trades_no_push = _simulate_with_bars([candidate], cfg_no_push, "GBPUSD", bar_data, pip_size)

        # Push filter should produce fewer or equal trades
        assert len(trades_push) <= len(trades_no_push), \
            f"Push filter should not produce more trades ({len(trades_push)} > {len(trades_no_push)})"


# ── Task 8: Dynamic nesting simulation tests ───────────────────────────


class TestDynamicNestingSimulation:
    """Dynamic nesting path with _ActiveTrigger state machine."""

    def test_dynamic_nesting_places_limit_on_zone_birth(self):
        """When a new LTF zone is born inside a triggered H4 zone, a limit is placed."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=48,
            limit_ttl=0,
            fixed_rr=3.0,
            spread_pips=0.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        # Zone birth: M15 demand zone born inside H4 zone on bar 2
        birth_ts = pd.Timestamp("2020-01-02 10:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="demand",
                is_push=True,
                origin_time=birth_ts,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020, 1.3015, 1.3020, 1.3050, 1.3080, 1.3100],
            "high": [1.3035, 1.3025, 1.3025, 1.3060, 1.3080, 1.3110, 1.3110],
            "low":  [1.3015, 1.3010, 1.3010, 1.3015, 1.3040, 1.3070, 1.3090],
            "close":[1.3020, 1.3015, 1.3020, 1.3050, 1.3070, 1.3100, 1.3100],
        }, index=pd.date_range("2020-01-02 08:00", periods=7, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        assert len(trades) >= 1, "Expected at least one trade from dynamic nesting"
        t = trades[0]
        # SL should be near LTF zone bottom (~1.3015), not H4 (1.3000)
        assert t.sl_price > 1.3000, "SL should be near LTF zone bottom, not H4"

    def test_dynamic_nesting_window_expiry(self):
        """Trigger window expires after trigger_window_bars."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=2,  # Very short window
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        # Zone born AFTER window expires (bar 4, window=2)
        birth_ts = pd.Timestamp("2020-01-02 12:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="demand",
                is_push=True,
                origin_time=birth_ts,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020, 1.3025, 1.3020, 1.3015],
            "high": [1.3035, 1.3025, 1.3030, 1.3025, 1.3025],
            "low":  [1.3015, 1.3010, 1.3015, 1.3010, 1.3010],
            "close":[1.3020, 1.3015, 1.3020, 1.3015, 1.3020],
        }, index=pd.date_range("2020-01-02 08:00", periods=5, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        # Window expired before zone birth — no trade
        assert len(trades) == 0

    def test_dynamic_nesting_ignores_wrong_side_birth(self):
        """Supply zone birth inside demand H4 zone is ignored."""
        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            limit_edge="top",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            trigger_window_bars=48,
            limit_ttl=0,
            fixed_rr=3.0,
        )

        candidate = RetestCandidate(
            event=_make_event(
                tf_pair="H1@H4", zone_tf="H4", zone_side="demand",
                timestamp=pd.Timestamp("2020-01-02 08:00"),
            ),
            zone_top=1.3050, zone_bottom=1.3000,
            entry_price=1.3025, atr=0.0020,
            period_hi=1.3100, period_lo=1.2950,
            opposing_zone_h4=1.3200,
        )

        birth_ts = pd.Timestamp("2020-01-02 09:00")
        zone_births = {
            birth_ts: [ZoneBirthEvent(
                timestamp=birth_ts,
                zone_top=1.3025, zone_bottom=1.3015,
                zone_tf="M15", zone_side="supply",  # Wrong side!
                is_push=True,
                origin_time=birth_ts,
            )],
        }

        bar_data = pd.DataFrame({
            "open": [1.3030, 1.3020],
            "high": [1.3035, 1.3025],
            "low":  [1.3015, 1.3010],
            "close":[1.3020, 1.3015],
        }, index=pd.date_range("2020-01-02 08:00", periods=2, freq="h"))

        from iora.strategy.trade_converter import _get_pip_size
        trades = _simulate_with_bars(
            [candidate], cfg, "GBPUSD", bar_data, _get_pip_size("GBPUSD"),
            zone_births=zone_births,
        )

        assert len(trades) == 0


# ── Task 9: evaluate_retest_config wiring tests ───────────────────────

class TestEvaluateWithNesting:
    """evaluate_retest_config passes zone_births through."""

    def test_evaluate_accepts_zone_births(self):
        """evaluate_retest_config can accept zone_births parameter."""
        from iora.strategy.retest_engine import evaluate_retest_config

        cfg = RetestConfig(
            tf_pair="H1@H4",
            entry_mode="limit",
            ltf_nesting="dynamic",
            entry_tf_override="M15",
            limit_ttl=0,
            fixed_rr=3.0,
        )

        result = evaluate_retest_config(
            candidates=[], config=cfg, symbol="GBPUSD",
            zone_births={},
        )
        assert result.metrics.get("total_trades", 0) == 0


# ── Task 10: Sweep config generator tests ──────────────────────────────

class TestHTFTriggeredSweepConfigs:
    """htf_triggered_ltf_configs() sweep generator."""

    def test_generates_configs(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        assert len(configs) > 40, f"Expected >40 configs, got {len(configs)}"

    def test_all_configs_have_ltf_nesting_or_standalone(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        nested = [c for c in configs if c.ltf_nesting != "none"]
        standalone_ltf = [c for c in configs if c.tf_pair in ("M5@M15", "M1@M5", "M1@M15")]
        assert len(nested) + len(standalone_ltf) > 40

    def test_includes_baseline(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        baselines = [c for c in configs if c.ltf_nesting == "none" and c.tf_pair == "H1@H4"]
        assert len(baselines) >= 2  # With and without partial

    def test_all_configs_use_limit_entry(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        for c in configs:
            assert c.entry_mode == "limit"

    def test_all_configs_ttl_zero(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        for c in configs:
            assert c.limit_ttl == 0

    def test_includes_standalone_ltf_pairs(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        pairs = {c.tf_pair for c in configs}
        assert "M5@M15" in pairs, "Missing M5@M15 standalone"
        assert "M1@M5" in pairs, "Missing M1@M5 standalone"
        assert "M1@M15" in pairs, "Missing M1@M15 standalone"

    def test_symbol_aware_spread(self):
        from iora.strategy.retest_sweep import htf_triggered_ltf_configs
        configs = htf_triggered_ltf_configs("GBPUSD")
        spreads = sorted({c.spread_pips for c in configs})
        assert 0.0 in spreads  # Always include zero-spread baseline
        assert len(spreads) >= 3  # At least 0, typical, and 1.5x/2x
