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
