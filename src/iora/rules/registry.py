"""
SignalRegistry — Central registry for all rules.

Manages rule registration, enable/disable, and batch evaluation.
Each rule is a module with an `evaluate()` function and a `RuleConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from iora.rules.signal import Signal


@dataclass
class RuleConfig:
    """Base config for a rule. Subclass for rule-specific params."""

    enabled: bool = True
    mode: str = "both"  # "growth", "scalping", "both"


class SignalRegistry:
    """Central registry for all trading rules."""

    def __init__(self) -> None:
        self._rules: dict[str, dict[str, Any]] = {}

    def register(
        self,
        rule_id: str,
        evaluate_fn: Callable,
        config: RuleConfig | None = None,
        description: str = "",
    ) -> None:
        """Register a rule."""
        self._rules[rule_id] = {
            "fn": evaluate_fn,
            "config": config or RuleConfig(),
            "description": description,
        }

    def enable(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id]["config"].enabled = True

    def disable(self, rule_id: str) -> None:
        if rule_id in self._rules:
            self._rules[rule_id]["config"].enabled = False

    def has_rule(self, rule_id: str) -> bool:
        return rule_id in self._rules

    def is_enabled(self, rule_id: str) -> bool:
        r = self._rules.get(rule_id)
        return r["config"].enabled if r else False

    def get_rules(self, mode: str | None = None) -> list[str]:
        """List all rule IDs, optionally filtered by mode."""
        result = []
        for rid, r in self._rules.items():
            if mode is None or r["config"].mode in (mode, "both"):
                result.append(rid)
        return result

    def get_enabled_rules(self, mode: str | None = None) -> list[str]:
        """List enabled rule IDs."""
        return [rid for rid in self.get_rules(mode) if self.is_enabled(rid)]

    def get_config(self, rule_id: str) -> RuleConfig | None:
        r = self._rules.get(rule_id)
        return r["config"] if r else None

    def evaluate_all(self, **kwargs) -> list[Signal]:
        """
        Evaluate all enabled rules. Pass engine state as kwargs.

        Rules are evaluated in registration order. Each rule receives
        `rule_signals_this_bar` containing signals from rules evaluated
        earlier in the same bar (enables cross-rule communication).

        Returns combined list of signals from all rules, sorted by time.
        """
        signals: list[Signal] = []
        for rid, r in self._rules.items():
            if not r["config"].enabled:
                continue
            try:
                result = r["fn"](
                    config=r["config"],
                    rule_signals_this_bar=signals,
                    **kwargs,
                )
                if result:
                    signals.extend(result)
            except Exception as e:
                # Log but don't crash — one bad rule shouldn't kill everything
                import logging
                logging.getLogger(__name__).warning(
                    "Rule %s failed: %s", rid, e
                )
        signals.sort(key=lambda s: s.time)
        return signals

    def describe(self) -> dict[str, dict]:
        """Return description of all registered rules."""
        return {
            rid: {
                "enabled": r["config"].enabled,
                "mode": r["config"].mode,
                "description": r["description"],
            }
            for rid, r in self._rules.items()
        }
