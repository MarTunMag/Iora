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
