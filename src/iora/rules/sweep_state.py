"""
SweepStateTracker — Tracks the sweep-scalp-growth chain across bars.

The chain: H1 BOS (sweep) → scalp hedge (retracement) → scalp TP at H1 zone
→ Growth continuation entry (tagged sweep_confirmed).

Pure state tracker. No signals emitted — just state that rules read.
Ticked once per bar by signal_engine.py.

References: TRADING_RULES_SSOT.md sections 9i, 10b, 10d.
Spec: docs/smc/SWEEP_SCALP_GROWTH_CHAIN.md
"""

from __future__ import annotations

from dataclasses import dataclass

from iora.features.composite import BarFeatures
from iora.rules.signal import Signal, HEDGE, ENTRY


@dataclass
class SweepStateTracker:
    """Tracks sweep-scalp-growth chain progression.

    Lifecycle:
      1. H1 BOS fires → h1_bos_fired = True, chain starts
      2. HEDGE signal emitted → scalp_armed = True
      3. Price reaches H1 opposing zone (scalp TP territory) → scalp_completed, sweep_confirmed, chain_count++
      4. Growth ENTRY signal → sweep_confirmed consumed (reset to False)
      5. Next H1 BOS → resets chain for next iteration

    Direction flip (bull↔bear) resets everything including chain_count.
    """

    # Chain state
    h1_bos_fired: bool = False
    scalp_armed: bool = False
    scalp_completed: bool = False
    sweep_confirmed: bool = False

    # Direction tracking
    push_direction: str = ""  # "bull" or "bear"

    # How many completed sweep-scalp chains in current push
    chain_count: int = 0

    def tick(self, features: BarFeatures, bar_signals: list[Signal]) -> None:
        """Advance chain state for this bar."""
        # Detect direction from d_phase
        new_direction = _direction_from_phase(features.d_phase)

        # Direction flip → full reset
        if new_direction and new_direction != self.push_direction:
            self._reset_all()
            self.push_direction = new_direction

        # Step 1: H1 BOS detection — new sweep starts
        if features.h1_bos_bear or features.h1_bos_bull:
            # Reset chain for new iteration
            self.h1_bos_fired = True
            self.scalp_armed = False
            self.scalp_completed = False
            self.sweep_confirmed = False
            # Set direction if not already set
            if not self.push_direction:
                self.push_direction = "bear" if features.h1_bos_bear else "bull"

        # Step 2: Check for scalp hedge entry (HEDGE signal this bar)
        if self.h1_bos_fired and not self.scalp_armed:
            for sig in bar_signals:
                if sig.signal_type == HEDGE and sig.mode == "scalp":
                    self.scalp_armed = True
                    break

        # Step 3: Check if scalp reached H1 opposing zone (TP territory)
        if self.scalp_armed and not self.scalp_completed:
            if _price_at_h1_target(features, self.push_direction):
                self.scalp_completed = True
                self.sweep_confirmed = True
                self.chain_count += 1

        # Step 4: Consume sweep_confirmed when Growth ENTRY fires
        if self.sweep_confirmed:
            for sig in bar_signals:
                if sig.signal_type == ENTRY and sig.mode == "growth":
                    self.sweep_confirmed = False
                    break

    def _reset_all(self) -> None:
        """Full reset on direction change."""
        self.h1_bos_fired = False
        self.scalp_armed = False
        self.scalp_completed = False
        self.sweep_confirmed = False
        self.chain_count = 0


def _direction_from_phase(d_phase: str) -> str:
    """Extract push direction from d_phase string."""
    if d_phase.endswith("^"):
        return "bull"
    elif d_phase.endswith("v"):
        return "bear"
    return ""


def _price_at_h1_target(f: BarFeatures, push_direction: str) -> bool:
    """Check if price has reached the H1 opposing zone (scalp TP territory).

    Bearish push: scalp BUY target = H1 supply zone (price_in_supply)
    Bullish push: scalp SELL target = H1 demand zone (price_in_demand)
    """
    if push_direction == "bear":
        return f.h1_price_in_supply
    elif push_direction == "bull":
        return f.h1_price_in_demand
    return False
