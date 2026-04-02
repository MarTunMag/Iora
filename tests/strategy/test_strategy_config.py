"""Tests for StrategyConfig dataclass and preset factory."""
from __future__ import annotations

from iora.strategy.strategy_config import StrategyConfig, make_preset


def test_default_config():
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
    cfg = StrategyConfig(
        entry_tf="M15", parent_tf="H4", signal_types={"push"},
        sl_mode="atr", tp_mode="fixed_rr", fixed_rr=3.0, direction="long",
    )
    assert cfg.entry_tf == "M15"
    assert cfg.parent_tf == "H4"
    assert cfg.signal_types == {"push"}
    assert cfg.sl_mode == "atr"
    assert cfg.tp_mode == "fixed_rr"
    assert cfg.fixed_rr == 3.0
    assert cfg.direction == "long"
    assert cfg.require_nesting is True
    assert cfg.max_concurrent == 1


def test_preset_aggressive():
    cfg = make_preset("aggressive")
    assert cfg.require_nesting is False
    assert cfg.signal_types == {"push", "reversal", "terminal", "normal"}
    assert cfg.no_trade_zones is False


def test_preset_conservative():
    cfg = make_preset("conservative")
    assert cfg.require_nesting is True
    assert cfg.signal_types == {"push", "reversal"}
    assert cfg.htf_trend_filter == "with_trend"


def test_preset_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown preset"):
        make_preset("unknown_preset")


def test_config_to_dict():
    cfg = StrategyConfig(entry_tf="M15", sl_mode="atr")
    d = cfg.to_dict()
    assert d["entry_tf"] == "M15"
    assert d["sl_mode"] == "atr"
    assert d["parent_tf"] == "H1"
    assert isinstance(d["signal_types"], list)
