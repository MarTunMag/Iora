# src/iora/strategy/config_grid.py
"""Config grid generator — cartesian product of sweep dimensions."""
from __future__ import annotations

import itertools
from dataclasses import fields

from iora.strategy.strategy_config import StrategyConfig

_VALID_FIELDS = {f.name for f in fields(StrategyConfig)}


def build_config_grid(
    dimensions: dict[str, list],
    base: StrategyConfig | None = None,
) -> list[StrategyConfig]:
    """Generate StrategyConfig instances from cartesian product of dimensions.

    Args:
        dimensions: Dict of field_name → list of values to sweep.
            E.g. {"sl_mode": ["zone", "atr"], "tp_mode": ["zone", "fixed_rr"]}
        base: Base config whose non-swept fields are used as defaults.
            If None, StrategyConfig() defaults are used.

    Returns:
        List of StrategyConfig, one per combination.

    Raises:
        ValueError: If a dimension key is not a valid StrategyConfig field.
    """
    for key in dimensions:
        if key not in _VALID_FIELDS:
            raise ValueError(f"Unknown StrategyConfig field: {key!r}")

    if base is None:
        base = StrategyConfig()

    if not dimensions:
        return [base]

    keys = list(dimensions.keys())
    value_lists = [dimensions[k] for k in keys]

    configs: list[StrategyConfig] = []
    base_dict = base.to_dict()
    # to_dict converts signal_types to sorted list — we need to preserve sets
    base_dict["signal_types"] = base.signal_types

    for combo in itertools.product(*value_lists):
        overrides = dict(zip(keys, combo))
        merged = {**base_dict, **overrides}
        configs.append(StrategyConfig(**merged))

    return configs
