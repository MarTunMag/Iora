# BUILD PROMPT — JoMa Production Signal-Flip Upgrade

> **For:** JoMa production system chat (C:\JoMa)
> **Goal:** Add M5@M15 signal-flip exit mode alongside the existing limit partial-TP system
> **Evidence:** Iora backtests show M5@M15 signal-flip produces +118,078 net pips, 82.5% WR, PF 36.92 over 16.5 years on GBPUSD

---

## READ FIRST

1. `C:\JoMa\CLAUDE.md` — JoMa project structure and rules
2. `C:\JoMa\configs\production.json` — Current production config
3. This document — the upgrade spec

---

## CONTEXT: What Was Discovered

In the Iora research project (C:\Iora), we ran a signal-flip sweep on M5@M15 GBPUSD. Results:

### M5@M15 Signal-Flip Backtest Results

| Metric | Value |
|---|---|
| **Trades (flips)** | 32,197 |
| **Win Rate** | 82.5% |
| **Profit Factor** | 36.92 |
| **Avg Flip** | 5.5 pips |
| **Net After Spread** | +118,078 pips |
| **Flips/Day** | ~5.3 |
| **Spread** | 1.5 pips (GBPUSD) |
| **Spread/Flip Ratio** | 27% (spread is 27% of avg flip) |

### Comparison Against Current JoMa System

| Metric | Current (M5@M15 Limit Partial TP) | Signal-Flip (M5@M15) |
|---|---|---|
| WR | 52.6% (v3) | 82.5% |
| PF | 3.28 | 36.92 |
| Trades/16.5yr | 6,493 | 32,197 |
| Avg hold | ~2 hours | ~minutes (flip to flip) |
| Exit mechanism | Fixed SL/TP + partial | Structural (opposite M5 zone fire) |
| Position state | In/out | Always in (flipping) |

### How Signal-Flip Works

```
ENTRY: M5 demand zone fires inside M15 demand context
  → LONG at M5 zone edge

EXIT: M5 supply zone fires on M5 timeframe  
  → Close LONG + Open SHORT simultaneously
  → The supply zone IS the short entry

NEXT EXIT: M5 demand zone fires
  → Close SHORT + Open LONG simultaneously
  → Cycle continues

The position is ALWAYS OPEN, just flipping direction.
Every exit is the next entry. Spread paid once per flip.
```

### What Needs Verification (Before Going Live)

1. **maxDD unknown** — R-metrics were broken in first run, being re-run now. Need maxDD before live.
2. **Spread deduction** — verify spread is deducted on BOTH close and re-open (not just once per flip).
3. **Annual breakdown** — need to confirm no catastrophic years in the 16.5-year backtest.
4. **Cross-symbol validation** — GBPUSD only so far. Need USDJPY, XAUUSD, BTCUSD, USTEC to confirm universality.
5. **Structural sequence filters** — running the system only during high-conviction windows (after HTF level break → H1 zone formed → M15 TL broke) should improve WR further.

---

## THE UPGRADE: What to Build in JoMa

### Option A: Dual-Mode System (Recommended)

Run BOTH the current limit/partial-TP system AND signal-flip simultaneously on different symbols or as separate strategy profiles. This is lowest risk — signal-flip doesn't replace the proven system, it runs alongside it.

```json
{
  "strategies": {
    "v3_limit_partial": {
      "name": "M5@M15 Limit Partial TP v3",
      "symbols": ["GBPUSD", "USDJPY", "XAUUSD"],
      "entry_mode": "limit",
      "exit_mode": "fixed_sl_tp",
      "partial_tp": true,
      "partial_unit1_pct": 0.70,
      "partial_unit1_rr": 3.0,
      "partial_unit2_tp": "H1"
    },
    "v4_signal_flip": {
      "name": "M5@M15 Signal-Flip v4",
      "symbols": ["GBPUSD"],
      "entry_mode": "market",
      "exit_mode": "signal_flip",
      "partial_tp": false,
      "always_in_market": true,
      "flip_on": "m5_opposite_zone"
    }
  }
}
```

### Option B: Signal-Flip Only (After Full Validation)

Replace the v3 system entirely once cross-symbol validation passes, maxDD is acceptable, and 2+ weeks of demo signal-flip confirms parity with backtest.

---

## IMPLEMENTATION DETAILS

### Step 1: Add `exit_mode` to JoMa's RetestConfig

In `C:\JoMa\src\joma\strategy\config.py`, add:

```python
# Exit mode
exit_mode: str = "fixed_sl_tp"         # "fixed_sl_tp" = current SL/TP system
                                        # "signal_flip" = exit on opposite M5 zone fire
                                        # "signal_flip_with_safety" = signal_flip + emergency SL
```

### Step 2: Add Signal-Flip Logic to LiveRunner

In `C:\JoMa\src\joma\execution\live_runner.py`, the current `_process_symbol()` method:
1. Detects M5 zone fires (retest candidates)
2. Places limit orders at zone edge
3. Manages partial TP on open positions

For signal-flip mode, the logic changes to:

```python
def _process_symbol_signal_flip(self, symbol: str) -> None:
    """Signal-flip mode: always in market, flip on opposite M5 zone fire."""
    
    # 1. Run zone engine (same as current)
    self._update_bars(symbol)
    ctx = self._build_bar_context(symbol)
    bus = EventBus()
    push_zone_engine_tick(self.engine_states[symbol], ctx, self.zone_config, bus)
    
    # 2. Check for M5 zone fire events
    m5_zone_fires = [e for e in bus.events if e.tf == "M5" and e.type == "zone_created"]
    
    if not m5_zone_fires:
        return  # No flip signal this bar
    
    # 3. Get the most recent M5 zone fire
    latest = m5_zone_fires[-1]
    new_direction = "short" if latest.is_supply else "long"
    
    # 4. Check if we have an open position in the OPPOSITE direction
    pos = self.positions.get(symbol)
    
    if pos is None:
        # No position — open in the direction of the zone
        self._open_signal_flip_position(symbol, new_direction, latest)
    elif pos.direction != new_direction:
        # Position exists in opposite direction — FLIP
        self._close_position(symbol, reason="signal_flip")
        self._open_signal_flip_position(symbol, new_direction, latest)
    # else: same direction zone — hold current position


def _open_signal_flip_position(self, symbol: str, direction: str, zone_event) -> None:
    """Open a signal-flip position — market order, no partial TP."""
    
    entry_price = self.bridge.get_market_price(symbol, direction)
    
    # Safety SL: behind the zone that caused this entry
    if direction == "long":
        sl = zone_event.zone_bottom - self.sl_buffer_atr * self._get_atr(symbol)
    else:
        sl = zone_event.zone_top + self.sl_buffer_atr * self._get_atr(symbol)
    
    # No TP — exit is the next opposite signal
    tp = 0.0  # 0 = no TP, MT5 will keep position open
    
    # Single unit, full risk (no partial split)
    lot_size = self.bridge.calculate_lot_size(
        symbol, entry_price, sl, self.risk_pct
    )
    
    ticket = self.bridge.place_market_order(symbol, direction, lot_size, sl, tp)
    
    if ticket > 0:
        self.positions[symbol] = LivePosition(
            symbol=symbol,
            direction=direction,
            unit1_ticket=ticket,
            unit2_ticket=0,  # No unit 2
            entry_price=entry_price,
            sl_price=sl,
            tp_unit1=0.0,
            tp_unit2=0.0,
            unit1_lot=lot_size,
            unit2_lot=0.0,
            zone_top=zone_event.zone_top,
            zone_bottom=zone_event.zone_bottom,
            tf_pair=f"{self.entry_tf}@{self.context_tf}",
            state="open",
        )
```

### Step 3: Update production.json

Add a signal-flip config section:

```json
{
  "strategy_signal_flip": {
    "name": "M5@M15 Signal-Flip v4",
    "version": "4.0.0",
    "entry_tf": "M5",
    "context_tf": "M15",
    "entry_mode": "market",
    "exit_mode": "signal_flip",
    "partial_tp": false,
    "always_in_market": true,
    "flip_on": "m5_opposite_zone",
    "safety_sl": true,
    "sl_buffer_atr": 0.15,
    "limit_buffer_atr": 0.0
  }
}
```

### Step 4: Update run_live.py

Add a `--strategy` flag to select between v3 (limit/partial) and v4 (signal-flip):

```bash
# Current v3 system
python scripts/run_live.py --config configs/production.json

# New v4 signal-flip
python scripts/run_live.py --config configs/production.json --strategy signal_flip

# Dual mode (both strategies, different symbols)
python scripts/run_live.py --config configs/production.json --dual
```

### Step 5: Demo Validation Protocol

Before going live with real money:

1. **Run signal-flip on demo for 2 weeks** on GBPUSD only
2. **Track every flip**: entry time, exit time, entry price, exit price, pips, spread
3. **Compare against backtest**: does the live WR match ~82%? Does avg_flip match ~5.5 pips?
4. **Monitor flip frequency**: should be ~5/day, not 50/day
5. **Log all events**: zone fires, position state, flip decisions, MT5 order results

---

## RISK MANAGEMENT FOR SIGNAL-FLIP

### Position Sizing

Since signal-flip has no fixed TP (exit is structural), position sizing uses:
- **Risk = distance from entry to safety SL** (zone boundary + buffer)
- **Max risk per flip = same as current (0.75% per trade)**
- But the position is ALWAYS OPEN, so net exposure = 1 position per symbol at all times

### Safety Mechanisms

```
1. Safety SL: Behind the zone that caused the entry (same as current sl_buffer_atr=0.15)
   → If zone breaks before opposite signal, emergency exit
   
2. Max spread filter: Skip flip if current spread > max_spread_pct of SL distance
   → Prevents flipping during news/high-spread events
   
3. Session filter (optional): Only flip during London/NY sessions
   → Asian session flips may be noise
   
4. Daily loss limit: Same as current (15% max daily loss)
   → Stops all trading if hit
   
5. Flip cooldown (optional): Minimum bars between flips
   → Prevents rapid-fire flipping during chop
```

### The Key Difference

| | Current v3 | Signal-Flip v4 |
|---|---|---|
| Position state | Out most of the time | Always in |
| Exposure | 0-1 positions per symbol | Always 1 position per symbol |
| Risk events | Entry → SL or TP | Flip → Flip → Flip |
| Worst case | SL hit = -1R | Rapid chop = many small losses |
| Best case | TP hit = +3R (unit 1) + runner | Trend = ride entire move |

---

## BACKTEST DATA REFERENCE

The signal-flip backtest was run in Iora:
- Script: `C:\Iora\scripts\run_signal_flip_sweep.py`
- Results: `C:\Iora\results\sweeps\signal_flip/`
- Config: M5@M15, exit_mode=signal_flip, spread_pips=1.5, min_sl_spread_mult=0.0
- Spec: `C:\Iora\docs\superpowers\specs\2026-04-09-m1m5-mechanical-signal-flip-spec.md`
- Build prompt: `C:\Iora\docs\superpowers\specs\2026-04-09-build-prompt-m1m5-signal-flip.md`

---

## WHAT TO DO NOW

1. **Read this document and the JoMa CLAUDE.md**
2. **Add `exit_mode` to RetestConfig** in `src/joma/strategy/config.py`
3. **Add `_process_symbol_signal_flip()` to LiveRunner** in `src/joma/execution/live_runner.py`
4. **Add signal-flip config** to `configs/production.json` (as `strategy_signal_flip` section)
5. **Add `--strategy` flag** to `scripts/run_live.py`
6. **Write tests** for signal-flip position management (flip logic, safety SL, spread filter)
7. **Run on demo** with GBPUSD for 2 weeks to validate against backtest

**DO NOT go live with real money until:**
- Iora backtest maxDD is known (R-metric re-run completing now)
- Cross-symbol validation passes (8 symbols overnight sweep running)
- 2 weeks of demo signal-flip matches backtest expectations (~82% WR, ~5 flips/day)
- Annual backtest breakdown confirms no catastrophic years
