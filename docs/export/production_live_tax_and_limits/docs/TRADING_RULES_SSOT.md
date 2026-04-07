# Trading Rules SSOT — Single Source of Truth

> **Current Focus (2026-03-24):** Building macro→meso→micro layer stack.
> Currently implementing: MACRO (D1 zones + HH/HL/LH/LL bias).
> Sections 9-14 (Growth lifecycle, Scalping, SL trailing, position sizing) are
> DEFERRED — will be rebuilt after macro and meso layers are validated.
> Rules v1 code archived to `src/flint/rules/archive/`.

> **Master reference for all trading signals, rules, and their implementation status.**
> Written for developers building the automated Rules + Trader layers.
>
> Source material: standalone rule files 01-11, EARLY_CONFIRMATION_CASCADE.md,
> engine/ and orchestrator/ source code.

---

## Table of Contents

1. [Signal Priority Hierarchy](#1-signal-priority-hierarchy)
2. [Signal Definitions](#2-signal-definitions)
   - [S01 Zone Classification](#s01-zone-classification-hh--hl--lh--ll)
   - [S02 Structure Propagation](#s02-structure-propagation)
   - [S03 Zone Counting](#s03-zone-counting-53-exhaustion)
   - [S04 Zone Nesting](#s04-zone-nesting)
   - [S05 Trendline Breaks](#s05-trendline-breaks)
   - [S06 Terminal Exhaustion](#s06-terminal-exhaustion)
   - [S07 Macro Bias](#s07-macro-bias)
   - [S08 1-2-3 Reversal Pattern](#s08-1-2-3-reversal-pattern)
   - [S09 Boundary Zones](#s09-boundary-zones)
   - [S10 D-Level Cycle](#s10-d-level-cycle)
   - [S11 Zone Tracking / Reversal Targets](#s11-zone-tracking--reversal-targets)
   - [S12 Early Confirmation Cascade](#s12-early-confirmation-cascade)
3. [Entry Signals](#3-entry-signals)
4. [Exit Signals](#4-exit-signals)
5. [Signal Chain — Fractal Cascade](#5-signal-chain--fractal-cascade)
6. [Signal Toggle Map](#6-signal-toggle-map)
7. [Implementation Status Summary](#7-implementation-status-summary)
8. [Context Mode Framework](#8-context-mode-framework)
9. [Data Types Reference](#8-data-types-reference)

---

## 1. Signal Priority Hierarchy

Signals are ordered by structural importance. Higher-priority signals gate or
override lower ones. When conflicts arise, the higher-priority signal wins.

```
Priority 1 (highest):  TERMINAL EXHAUSTION (S06)
Priority 2:            MACRO BIAS (S07)
Priority 3:            D-LEVEL CYCLE PHASE (S10)
Priority 4:            ZONE NESTING — opposing (S04)
Priority 5:            ZONE COUNTING — 5+3 (S03)
Priority 6:            TRENDLINE BREAKS (S05)
Priority 7:            BOUNDARY ZONE DECISIONS (S09)
Priority 8:            1-2-3 REVERSAL PATTERN (S08)
Priority 9:            EARLY CONFIRMATION CASCADE (S12)
Priority 10:           ZONE TRACKING / REVERSAL TARGETS (S11)
Priority 11 (lowest):  ZONE CLASSIFICATION (S01) + STRUCTURE PROPAGATION (S02)
```

S01 and S02 are foundational — they feed every other signal but are not
tradeable on their own.

---

## 2. Signal Definitions

---

### S01: Zone Classification (HH / HL / LH / LL)

**NAME:** `ZONE_CLASSIFICATION`

**DETECTION LOGIC:**
```python
# On new zone fire (HA color flip), compare to previous zone of same type on same TF
def classify_zone(new_zone, prev_same_side_zone):
    if new_zone.is_supply:
        if new_zone.top > prev_same_side_zone.top:
            return "HH"   # structural — trend continues
        else:
            return "LH"   # corrective — trend weakening
    else:  # demand
        if new_zone.bot < prev_same_side_zone.bot:
            return "LL"   # structural — trend continues
        else:
            return "HL"   # corrective — trend weakening
```

**BOS vs CHoCH on zone break:**
```python
def classify_break(broken_zone):
    if broken_zone.is_hh_or_ll:   # HH or LL
        return "BOS"   # Break of Structure — trend confirmed
    else:                          # LH or HL
        return "CHoCH" # Change of Character — reversal signal
```

**DATA REQUIRED:**
- `FractalZone.top`, `FractalZone.bot`, `FractalZone.is_supply`, `FractalZone.is_hh_or_ll`
- Previous zone of same side on same TF (from `ZoneTickState.supply_zones` / `demand_zones`)

**VISUAL OUTPUT:**
- Zone rectangle colored by side (supply=red, demand=blue)
- Label "HH"/"HL"/"LH"/"LL" on zone
- On break: "BOS" or "CHoCH" marker, zone faded

**STATUS:** DONE — `engine/zone_tick.py` fires `ZONE_FIRE` / `ZONE_BREAK` events. Classification stored in `FractalZone.is_hh_or_ll`. Visualization in LW Charts overlays.

---

### S02: Structure Propagation

**NAME:** `STRUCTURE_PROPAGATION`

**DETECTION LOGIC:**
```python
# Parent TF structure = comparison of child TF zones
PARENT_CHILD_MAP = {
    "W1": "D1",   # W structure from D zone comparisons
    "D1": "H4",   # D structure from H4 zone comparisons
    "H4": "H1",   # H4 structure from H1 zone comparisons
    "H1": "M15",  # H1 structure from M15 zone comparisons
    "M15": "M5",  # M15 structure from M5 zone comparisons
}

def detect_parent_structure(child_zone, prev_parent_supply, prev_parent_demand):
    if child_zone.is_supply:
        if child_zone.top > prev_parent_supply.top:
            return "PARENT_HH"  # early H4 HH if child=H1
        elif child_zone.top < prev_parent_supply.top:
            return "PARENT_LH"
    else:
        if child_zone.bot < prev_parent_demand.bot:
            return "PARENT_LL"
        elif child_zone.bot > prev_parent_demand.bot:
            return "PARENT_HL"
```

**Streak resets:**
```python
# HH fires → reset LH count to 0, reset LL count to 0
# LL fires → reset HL count to 0, reset HH count to 0
# LH fires → reset HH count to 0 only
# HL fires → reset LL count to 0 only
```

**DATA REQUIRED:**
- `ZoneTickState` for child TF (supply_zones, demand_zones)
- Last parent TF supply/demand zones for boundary comparison

**VISUAL OUTPUT:**
- D/W HH/HL/LH/LL labels on structure panel (compass dashboard)
- Streak counts in compass

**STATUS:** DONE — `engine/structure_count.py` (`structure_count_tick`). Counts D and W structural events from H4 and D zones respectively. Streak tracking with resets. Visualization in compass panel.

---

### S03: Zone Counting (5+3 Exhaustion)

**NAME:** `ZONE_COUNTING`

**DETECTION LOGIC:**
```python
def count_unbroken_zones(zones_list, zone_side):
    """Count consecutive unbroken zones of one side since last parent reset."""
    count = 0
    for z in zones_list:
        if not z.is_broken and z.is_supply == (zone_side == "supply"):
            count += 1
    return count

def classify_exhaustion(count):
    if count < 5:
        return "IMPULSE_ACTIVE"      # trend has room
    elif count == 5:
        return "IMPULSE_EXHAUSTED"   # trend slowing
    elif count >= 8:  # 5+3
        return "TERMINAL"            # reversal imminent
    else:
        return "CORRECTION"          # 5 < count < 8
```

**Zone count semantics by position:**
```
Zones 1-3:  Strong momentum, wide spacing     → TRADE WITH trend
Zones 4-5:  Deceleration, zones clustering     → PREPARE for reversal
Zone 6 (A): First counter-trend zone           → Correction starting
Zone 7 (B): Retest zone                        → "Perfect retest" possible
Zone 8 (C): Terminal — inside opposing HTF zone → WILL be broken, reversal HERE
```

**What to count at each level:**

| Count target | Reset event | Exhaustion means |
|-------------|-------------|-----------------|
| H1 unbroken supply zones | New H4 supply fires or H1 HH | H4 bearish push exhausted |
| H1 unbroken demand zones | New H4 demand fires or H1 LL | H4 bullish push exhausted |
| M5 unbroken supply zones | New H1 supply fires | H1 bearish leg exhausted |
| M5 unbroken demand zones | New H1 demand fires | H1 bullish leg exhausted |

**Fractal rule:**
```
5+3 M5 zones   = 1 H1 leg complete
5+3 M15 zones  = 1 H1 pullback complete
5+3 H1 zones   = 1 H4 reversal (terminal exhaustion)
ALL levels exhausted simultaneously = FRACTAL DONE = highest conviction
```

**DATA REQUIRED:**
- `ZoneTickState.supply_zones` / `demand_zones` per TF (unbroken filter)
- Parent TF zone fire events for reset triggers

**VISUAL OUTPUT:**
- Numbered zone labels (1-8) on H1 zones
- Exhaustion indicator in compass panel
- Color shift at zone 5+ (warning) and 8 (terminal)

**STATUS:** DONE — `engine/wave_sm.py` (`wave_sm_tick`) tracks H1 zone count in 4-phase impulse/correction model. `engine/structure_count.py` tracks D/W counts. Compass displays wave count. Zone numbering visible in LW Charts overlays.

---

### S04: Zone Nesting

**NAME:** `ZONE_NESTING`

**DETECTION LOGIC:**
```python
def is_nested(child_zone, parent_zone):
    """Full containment check — both edges must be inside."""
    return child_zone.top <= parent_zone.top and child_zone.bot >= parent_zone.bot

def classify_nesting(child_zone, parent_zone):
    if not is_nested(child_zone, parent_zone):
        return None
    same_side = child_zone.is_supply == parent_zone.is_supply
    if same_side:
        return "CONTINUATION"   # stair-step, trade with it
    else:
        return "TERMINAL"       # opposing = will be broken, reversal

def skip_filter(parent_zone, opposing_parent_zones):
    """Skip if parent zone overlaps opposing zone (weak signal)."""
    for opp in opposing_parent_zones:
        if opp.top >= parent_zone.bot and opp.bot <= parent_zone.top:
            return True  # overlapping — skip
    return False
```

**Nesting combos (default ON):**
```
H1 @ H4   — H1 zone inside H4 zone
M15 @ H4  — M15 zone inside H4 zone
M5 @ H1   — M5 zone inside H1 zone
```

**Triple nesting = highest conviction entry:**
```
M5 inside M15 inside H1 (all same direction) → EXECUTE ENTRY
```

**DATA REQUIRED:**
- `ZoneTickState` for child and parent TFs
- `NestedZoneState` tracking fired pairs
- `EventBus` for `NESTED_FIRE` / `NESTED_BREAK` events

**VISUAL OUTPUT:**
- Nested zone highlighted with distinct color (orange outline)
- "NESTED" label on qualifying zones
- Opposing nesting marked with terminal indicator

**STATUS:** DONE — `engine/nested_zones.py` (`nested_break_tick`). 8 combo definitions. Skip filter for overlapping zones. Events: `NESTED_FIRE`, `NESTED_BREAK`. Visualization in LW Charts overlays.

---

### S05: Trendline Breaks

**NAME:** `TRENDLINE_BREAK`

**DETECTION LOGIC:**
```python
def build_trendline(zones, direction):
    """Connect consecutive LH tops (bearish) or HL bots (bullish)."""
    if direction == "bear":
        # Connect LH supply zone tops (descending)
        points = [(z.origin_time, z.top) for z in zones if not z.is_hh_or_ll and z.is_supply]
    else:
        # Connect HL demand zone bottoms (ascending)
        points = [(z.origin_time, z.bot) for z in zones if not z.is_hh_or_ll and not z.is_supply]
    return Trendline(t1=points[-2], p1=..., t2=points[-1], p2=..., direction=direction)

def detect_break(trendline, bar_high, bar_low, bar_time):
    tl_price = interpolate(trendline, bar_time)
    if trendline.direction == "bear" and bar_high > tl_price:
        return True   # bearish TL broken upward
    if trendline.direction == "bull" and bar_low < tl_price:
        return True   # bullish TL broken downward
    return False
```

**TL break confirmation chain:**

| TL that breaks | Confirms |
|---------------|----------|
| M5 TL break | M15 sub-wave complete |
| M15 TL break | H1 push complete |
| H1 TL break | H4 push complete |
| H4 TL break | D leg complete |

**Impulse vs correction TL:**

| Type | Connects | Break means |
|------|----------|-------------|
| Impulse (solid) | HH tops or LL bots | Potential reversal — trend push broke |
| Correction (dashed) | LH tops or HL bots | Trend resumes — pullback failed |

**M15 TL break = entry gate** — prerequisite for most entry paths.

**DATA REQUIRED:**
- `TrendlineTickState` per TF (bear_tl, bull_tl)
- `Trendline` objects with anchors (t1/p1/t2/p2)
- Bar OHLC for interpolation

**VISUAL OUTPUT:**
- Solid line for impulse TL, dashed for correction TL
- Break marker (X) at break point
- Color: bull=blue, bear=red

**STATUS:** DONE — `engine/trendline_tick.py` (`trendline_tick`). Push TL detection from zone sequences. Break detection via interpolation. `TL_BREAK` events emitted. `engine/xtf_trendline.py` adds cross-TF trendlines (impulse/correction typed). Visualization in LW Charts overlays.

---

### S06: Terminal Exhaustion

**NAME:** `TERMINAL_EXHAUSTION`

**DETECTION LOGIC:**
```python
def detect_terminal_bear(d_zones, h4_zones, h1_supply_count):
    """Expect bullish reversal."""
    d_dem_broken = any(z.is_broken and not z.is_supply for z in d_zones)
    if not d_dem_broken:
        return False
    broken_d_ll = min(z.bot for z in d_zones if z.is_broken and not z.is_supply)
    h4_dem_below = any(z.bot < broken_d_ll and not z.is_supply for z in h4_zones)
    return h4_dem_below and h1_supply_count >= 5

def detect_terminal_bull(d_zones, h4_zones, h1_demand_count):
    """Expect bearish reversal."""
    d_sup_broken = any(z.is_broken and z.is_supply for z in d_zones)
    if not d_sup_broken:
        return False
    broken_d_hh = max(z.top for z in d_zones if z.is_broken and z.is_supply)
    h4_sup_above = any(z.top > broken_d_hh and z.is_supply for z in h4_zones)
    return h4_sup_above and h1_demand_count >= 5
```

**Full checklist (bear terminal = expect bullish reversal):**
```
[x] D demand broken (D LL = daily structure bearish)
[x] H4 demand formed BELOW broken D LL price
[x] 5+ unbroken H1 supply zones overhead
[x] H1 wave count shows 5+3 pattern
→ TERMINAL_EXHAUSTION = TRUE
```

**H4 zone confirmation sequence (not "live" until break-retest):**
```
1. H1 demand created at bottom (inside H4 demand)
2. Price pushes up → creates H1 supply (#8)
3. Price pushes back down → breaks that H1 demand
4. Pushdown reaches M15/M5 demand at the lowest point
→ H4 demand is CONFIRMED LIVE
```

**Reset conditions:**
- New D zone fires (D structure changed)
- Macro bias flip

**DATA REQUIRED:**
- D-level `ZoneTickState` (broken demand/supply zones)
- H4-level `ZoneTickState` (new zones beyond D break)
- H1 unbroken zone count (from `WaveSMState`)
- `EventBus` for `TERMINAL_EXHAUST` event

**VISUAL OUTPUT:**
- Terminal indicator in compass panel
- H4 counter-zone highlighted (distinct color)
- Zone count overlay on H1 panel showing 5+3

**STATUS:** DONE — `engine/cycle_sm.py` (`cycle_tick`) detects D break + first H4 counter-zone. `TERMINAL_EXHAUST` event emitted. Compass displays terminal state. The break-retest confirmation sequence for the H4 zone is PARTIAL — the cycle state machine tracks phases but does not yet validate the full break-retest internally.

---

### S07: Macro Bias

**NAME:** `MACRO_BIAS`

**DETECTION LOGIC:**
```python
def macro_bias_tick(bar, m5_tl_state, h4_zones, d_zones, terminal_state):
    # BEARISH confirmation
    if m5_bull_tl_broken(bar, m5_tl_state):
        if close_inside_zone(bar.close, h4_zones, "supply") or \
           close_inside_zone(bar.close, d_zones, "supply"):
            if not terminal_state.bull_active:
                return -1  # BEAR CONFIRMED
    # BULLISH confirmation
    if m5_bear_tl_broken(bar, m5_tl_state):
        if close_inside_zone(bar.close, h4_zones, "demand") or \
           close_inside_zone(bar.close, d_zones, "demand"):
            if not terminal_state.bear_active:
                return +1  # BULL CONFIRMED
    return current_bias  # unchanged
```

**Terminal gate (critical protection):**
```
Don't flip BULLISH when terminal_exhaustion_bear is active
  → bounces at H4 demand below D LL are temporary
Don't flip BEARISH when terminal_exhaustion_bull is active
  → dips at H4 supply above D HH are temporary
```

**On confirmation, set limit order level:**
```
Bear confirmed → SHORT LIMIT at broken M5 demand top
                  SL: M1 supply top + spread buffer
Bull confirmed → LONG LIMIT at broken M5 supply bottom
                  SL: M1 demand bot - spread buffer
```

**Once set, stays until opposite confirmation fires. No timeout, no decay.**

**DATA REQUIRED:**
- `TrendlineTickState` for M5 (bear_tl, bull_tl)
- `ZoneTickState` for H4 and D (containment check)
- Terminal exhaustion flags
- `MacroBiasTickState` (edge detection, prev broken state)

**VISUAL OUTPUT:**
- Compass shows bias direction (+1 / -1 / 0)
- H1 zones colored by bias: bull=blue demand shown, bear=red supply shown
- Dashed limit order line on chart
- D and W zones NEVER hidden (macro targets always visible)

**STATUS:** DONE — `engine/macro_bias.py` (`macro_bias_tick`). M5 TL break + H4/D containment + terminal gate. Events: `BIAS_BULL_CONF` / `BIAS_BEAR_CONF`. Compass integration. Limit order visualization is PENDING (no dashed line drawn yet).

---

### S08: 1-2-3 Reversal Pattern

**NAME:** `ONE_TWO_THREE`

**DETECTION LOGIC:**
```python
def detect_123_bear(zones):
    """Bearish 1-2-3: rally failing (compression)."""
    # Zone 1: Demand (HL) — pullback support
    # Zone 2: Supply (HH) — rally high
    # Zone 3: Demand (HL) — second pullback
    z1, z2, z3 = last_3_alternating_zones(zones)
    if z1.is_supply == False and z2.is_supply == True and z3.is_supply == False:
        if z3.top < z2.bot:  # can't reach the last high = compression
            return True
    return False

def detect_123_bull(zones):
    """Bullish 1-2-3: push down failing."""
    z1, z2, z3 = last_3_alternating_zones(zones)
    if z1.is_supply == True and z2.is_supply == False and z3.is_supply == True:
        if z3.bot > z2.top:  # can't reach the last low = compression
            return True
    return False
```

**Cascade arming (each level arms the next):**
```python
CASCADE_ORDER = ["D1", "H4", "H1", "M15", "M5"]

def cascade_check(tf, close, parent_zones):
    """Child 1-2-3 only fires when close is inside active parent zone."""
    if tf == "D1":
        return True  # D always fires (no parent gate)
    return close_inside_any_unbroken_zone(close, parent_zones)

# D bearish 1-2-3 fires → arms H4 bearish, CLEARS H4 bullish
# H4 fires (inside D zone) → arms H1
# H1 fires (inside H4 zone) → arms M15
# M15 fires (inside H1 zone) → arms M5
# M5 fires (inside M15 zone) → ENTRY TRIGGER ARMED
```

**M1 CHoCH add-on after M5 cascade:**
```python
if m5_cascade_bear_ready:
    # Wait for M1 LL (proves push started)
    # Then M1 LH (CHoCH) = SHORT add-on entry
    # Entry: last_m1_sup_bot
    # SL: last_m1_sup_top + spread

if m5_cascade_bull_ready:
    # Wait for M1 HH (proves push started)
    # Then M1 HL (CHoCH) = LONG add-on entry
```

**DATA REQUIRED:**
- Zone sequences per TF (last 3 alternating zones)
- Parent zone containment for cascade gating
- `EventBus` for `ONE_TWO_THREE` event

**VISUAL OUTPUT:**
- 1-2-3 pattern marker on chart (triangle or numbered zones)
- Cascade state in compass (which levels armed)

**STATUS:** PENDING — Event ID `ONE_TWO_THREE` defined in `models.py`. No tick processor implemented yet. The cascade tracker (`engine/cascade_tracker.py`) handles TL break cascades but not the 1-2-3 zone compression pattern.

---

### S09: Boundary Zones

**NAME:** `BOUNDARY_ZONE`

**DETECTION LOGIC:**
```python
def create_boundary(last_hh_or_ll_zone, last_unbroken_zone):
    """
    On H1 LL: boundary from H1 supply top (last unbroken) → down to H1 LL low
    On H1 HH: boundary from H1 HH high → down to H1 demand bot (last unbroken)
    """
    if last_hh_or_ll_zone.is_supply:  # bearish boundary (after LL)
        return BoundaryZone(
            top=last_unbroken_zone.top,     # supply top
            bot=last_hh_or_ll_zone.bot,     # LL low
            direction="bear"
        )
    else:  # bullish boundary (after HH)
        return BoundaryZone(
            top=last_hh_or_ll_zone.top,     # HH high
            bot=last_unbroken_zone.bot,     # demand bot
            direction="bull"
        )

def check_boundary_break(boundary, bar_close):
    if boundary.direction == "bear":
        if bar_close > boundary.top:
            return "BROKEN"  # bearish invalidated → H4 HH → reversal
    else:
        if bar_close < boundary.bot:
            return "BROKEN"  # bullish invalidated → H4 LL → reversal
    return "HOLDING"
```

**Early detection inside boundary (nested CHoCH):**
```
H1 zones forming inside boundary (building reversal structure)
  → M15 zones inside those H1 zones (refining direction)
    → M5 CHoCH inside M15 = boundary break is coming
      → M1 CHoCH = enter BEFORE the boundary visually breaks
```

**DATA REQUIRED:**
- H1 `ZoneTickState` (last HH/LL zone, last unbroken opposing zone)
- Bar close for break detection
- Dotted internal line at original zone edge

**VISUAL OUTPUT:**
- Wide colored rectangle (boundary box) on H1 panel
- Dotted internal line marking original zone edge
- Orange tint on break, clipped rendering

**STATUS:** PENDING — No dedicated `BoundaryZone` dataclass or tick processor. The boundary concept is implicitly available from zone data (H1 HH/LL zones vs last unbroken zone) but not computed as a first-class object. No visualization.

---

### S10: D-Level Cycle

**NAME:** `D_LEVEL_CYCLE`

**DETECTION LOGIC:**
```python
PHASES = {
    "A": "H4 demand confirmation (break-retest inside terminal H4 demand)",
    "B": "Reversal into boundary (push up from H4 demand, HL sequence)",
    "C": "H4 supply at reversal zone (D LH confirmation)",
    "D": "Aggressive D LL push (Mode B continuation)",
    "E": "New D LL printing → cycle restarts at A",
}

def detect_phase(terminal_state, h4_zones, d_zones, boundary_state, h1_zones):
    if terminal_state.active and h4_demand_confirming(h4_zones):
        return "A"
    if price_pushing_from_h4_demand_toward_boundary(h4_zones, boundary_state):
        return "B"
    if h4_supply_forming_at_boundary(h4_zones, boundary_state):
        return "C"  # D LH confirmed
    if d_lh_confirmed and aggressive_push_down(h1_zones):
        return "D"  # Mode B
    if new_d_ll_printing(d_zones):
        return "E"  # → back to A
```

**Trading mode per phase:**

| Phase | Entry Mode | Trade |
|-------|-----------|-------|
| A | Reversal (Path A) | Long from M15 demand @ terminal H4 demand |
| B | Continuation longs | Long from H1 demand retests (HL sequence) |
| C | Bearish trigger (Path D) | Short from M15 supply @ H1 unbroken supply |
| D | Aggressive continuation (Mode B) | Short from M5/M15 supply zones |
| E | Terminal detection | Watch for next H4 counter-zone |

**DATA REQUIRED:**
- `CycleTickState` (bear_to_bull_phase / bull_to_bear_phase)
- `StructuralCycleState` (persisted zone levels)
- Terminal exhaustion state
- H4/D zone states
- `EventBus` for `CYCLE_PHASE` event

**VISUAL OUTPUT:**
- Phase indicator in compass (A/B/C/D/E)
- Phase-appropriate zone highlighting
- Mode indicator (Path A / Mode B / Path D)

**STATUS:** DONE — `engine/cycle_sm.py` (`cycle_tick`) implements 5-phase state machine for both bear-to-bull and bull-to-bear cycles. Tracks first H4 zone, TL anchors, reversal targets. `CYCLE_PHASE` events emitted. Compass shows cycle phase. The per-phase trading mode selection (Path A / Mode B / Path D) is PENDING — requires Rules layer.

---

### S11: Zone Tracking / Reversal Targets

**NAME:** `ZONE_TRACKING`

**DETECTION LOGIC:**
```python
def track_last_zones(zone_states, push_direction):
    """As price pushes, always track the LAST CREATED zone on each side."""
    targets = {}
    for tf in ["D1", "H4", "H1", "M15"]:
        zs = zone_states[tf]
        if push_direction == "bear":
            # Track last supply = reversal target when turns
            last_sup = last_unbroken(zs.supply_zones)
            targets[tf] = last_sup
        else:
            last_dem = last_unbroken(zs.demand_zones)
            targets[tf] = last_dem
    return targets

def identify_reversal_target(h1_zones, h4_zones):
    """
    The H1 zone that CAUSED the H4 CHoCH = reversal target.
    When H1 makes HL (H4 HL CHoCH), the last H1 supply before that HL
    = the zone that will be the reversal target when price pushes back up.
    """
    # Find last H1 HL (CHoCH at H4)
    last_choch = find_last_choch(h1_zones)
    if last_choch:
        # The supply zone active just before the CHoCH
        return last_supply_before(h1_zones, last_choch.origin_time)
    return None
```

**D LH reversal zone identification:**
```python
def identify_d_lh_zone(h1_zones, h4_zones, d_zones):
    """
    The D LH reversal zone is the H1 supply zone created as the H4 pushed
    to break the H4 HL, which then pushed to break the D LL.

    → When price pushes back up here:
      → H4 HH forms (but below last H4 supply = D LH, not D HH)
      → EXIT LONGS here, ENTER SHORTS
    """
    pass  # Implementation tracks H4 impulse zone at D break
```

**"Don't get tricked by H4 HL" rule:**
```
After D LL break:
  → First H4 demand is important but NOT the reversal yet
  → Wait for H4 HL to BREAK (pushing further down)
  → The H4 supply that caused the H4 HL break
    = the zone that pushed down to break D LL
    = YOUR D LH reversal target when price pushes back up
```

**Weekly context check at every D LL:**
```python
def weekly_context(d_demand, w_demand_from_last_push):
    """Is this D LL inside the W demand that built the last W push up?"""
    if is_nested(d_demand, w_demand_from_last_push):
        return "W_HL_LIKELY"  # buy the D LL for W continuation
    else:
        return "W_CONTINUATION"  # sell the D HL, W impulse continues
```

**DATA REQUIRED:**
- `ZoneTickState` at all TFs
- `CycleTickState` for phase awareness
- `StructuralCycleState.rev_target_h1_sup_top/bot` and `rev_target_h1_dem_top/bot`
- W/D zone nesting for weekly context

**VISUAL OUTPUT:**
- Reversal target zone marked with distinct color/label
- D LH zone highlighted when identified
- Weekly context indicator

**STATUS:** PARTIAL — `engine/cycle_sm.py` tracks `rev_target_h1_sup` and `rev_target_h1_dem` (the H1 reversal target zones). `FractalZone.is_reversal_target` flag exists. The full multi-TF zone tracking chain and D LH identification are not automated — the cycle SM captures the reversal target at H1 level but the mechanical sequence (Steps 1-8) is not wired as a Rules layer. Weekly context check is PENDING.

---

### S12: Early Confirmation Cascade

**NAME:** `EARLY_CONFIRMATION_CASCADE`

**DETECTION LOGIC:**
```python
# Early parent HH: child supply top > last parent supply top (child is HH)
# Early parent LL: child demand bot < last parent demand bot (child is LL)
# Early parent HL: child demand bot > prev child demand bot, inside parent demand
# Early parent LH: child supply top < prev child supply top, inside parent supply

EARLY_CASCADE_MAP = {
    "H4": "H1",   # H4 structure from H1 zones
    "D1": "H4",   # D structure from H4 zones
    "W1": "D1",   # W structure from D zones
}

def early_cascade_tick(state, zone_states, bar_time):
    anchors = []
    for parent_tf, child_tf in EARLY_CASCADE_MAP.items():
        parent_zs = zone_states[parent_tf]
        child_zs = zone_states[child_tf]

        for z in child_zs.supply_zones:
            if z.is_broken: continue
            if z.is_hh_or_ll and z.top > last_parent_sup.top:
                # Early parent HH
                anchors.append(EarlyAnchor("HH", ...))
            elif not z.is_hh_or_ll and z.top < last_parent_sup.top:
                if z.bot >= last_parent_sup.bot:
                    # Early parent LH (CHoCH → reversal target)
                    z.is_reversal_target = True
                    anchors.append(EarlyAnchor("LH", ...))

        # Mirror for demand zones → LL / HL
    return anchors
```

**Propagation chain (bottom-up):**
```
M1 CHoCH (HL/LH)
  → confirms M5 sub-wave direction
    → M5 CHoCH
      → confirms M15 zone leg complete
        → M15 CHoCH
          → confirms H1 sub-wave complete (H1 push TL break)
            → H1 CHoCH
              → creates H4 structure (H4 HH/HL/LH/LL)
                → H4 structural event
                  → creates D structure
```

**Early confirmation table:**

| HTF Event | What Confirms It Early | Earliest Tradeable Signal |
|-----------|----------------------|--------------------------|
| H4 HH | H1 HH (supply top > prev H4 supply top) | M1 HL after H1 first HL fires |
| H4 LL | H1 LL (demand bot < prev H4 demand bot) | M1 LH after H1 first LH fires |
| H4 HL | H1 HL sequence inside H4 demand | M15 HL inside H1 demand @ H4 demand |
| H4 LH | H1 LH sequence inside H4 supply | M15 LH inside H1 supply @ H4 supply |
| D LH | H4 HH capped below D supply top | H1 CHoCH (first LH after H4 HH) |
| D HL | H4 LL floored above D demand bot | H1 CHoCH (first HL after H4 LL) |
| H1 leg complete | M15 CHoCH (opposing inside H1 zone) | M1 CHoCH after M5 CHoCH inside M15 |

**DATA REQUIRED:**
- `EarlyCascadeState` (seen set for dedup)
- `ZoneTickState` for all TF pairs in `EARLY_CASCADE_MAP`
- `XTFTrendlineState` for anchor injection
- `EventBus` for `EARLY_STRUCTURE` events

**VISUAL OUTPUT:**
- Early structure markers on chart (ahead of official HTF zone fire)
- XTF trendlines updated with early anchors
- `EARLY_STRUCTURE` event in event log

**STATUS:** DONE — `engine/early_cascade.py` (`early_cascade_tick`). Scans H1→H4, H4→D, D→W pairs. Detects early HH/HL/LH/LL. Marks `is_reversal_target` on CHoCH zones. Injects anchors into XTF trendline states via `inject_early_anchors`. Events emitted. Integrated into pipeline via `_tick_structure_and_cascade`. The M1→M5→M15 portion of the cascade (lowest TF precision entries) is PENDING — current implementation only covers H1→H4→D→W.

---

## 3. Entry Signals

### E01: Terminal Reversal Entry (Path A)

**TRIGGER:** Terminal exhaustion confirmed + M15 demand nested inside H4 demand

```python
def path_a_long(terminal_bear_active, m15_zone, h4_demand):
    if not terminal_bear_active:
        return None
    if is_nested(m15_zone, h4_demand) and not m15_zone.is_supply:
        # M1 CHoCH (HL) inside M5 @ this M15 demand = execution trigger
        return EntrySignal(
            direction="LONG",
            entry_price=last_m1_dem_top,
            sl_price=last_m1_dem_bot - spread_buf,
            reason="PATH_A_TERMINAL_REVERSAL"
        )
```

**STATUS:** PENDING — Terminal detection done. Entry signal generation needs Rules layer.

---

### E02: H1 Stair-Step Continuation (Path B)

**TRIGGER:** Macro bias set + H1 HL demand retest + M15 TL break

```python
def path_b_long(macro_bias, h1_demand, m15_tl_broken):
    if macro_bias != +1:
        return None
    if h1_demand and not h1_demand.is_hh_or_ll:  # HL zone
        if m15_tl_broken:  # M15 bull TL break = pullback exhaustion
            return EntrySignal(
                direction="LONG",
                entry_price=h1_demand.top,
                sl_price=h1_demand.bot - spread_buf,
                reason="PATH_B_STAIR_STEP"
            )
```

**STATUS:** PENDING — All component signals exist. Rules layer wiring needed.

---

### E03: Aggressive Continuation (Mode B / Phase D)

**TRIGGER:** D LH confirmed + H1 supply zones breaking without retest

```python
def mode_b_short(d_lh_confirmed, m15_supply, m5_supply):
    if not d_lh_confirmed:
        return None
    # Enter directly on M5/M15 supply zones (no H1 retest needed)
    return EntrySignal(
        direction="SHORT",
        entry_price=m5_supply.bot if m5_supply else m15_supply.bot,
        sl_price=(m5_supply or m15_supply).top + spread_buf,
        reason="MODE_B_AGGRESSIVE"
    )
```

**STATUS:** PENDING — Requires Rules layer.

---

### E04: Bearish Trigger at D LH Zone (Path D)

**TRIGGER:** Price reaches H1 supply identified as D LH reversal target

```python
def path_d_short(price, rev_target_h1_supply, m15_supply_nested):
    if rev_target_h1_supply is None:
        return None
    if rev_target_h1_supply.contains_price(price):
        if m15_supply_nested:  # M15 supply inside H1 supply
            return EntrySignal(
                direction="SHORT",
                entry_price=rev_target_h1_supply.bot,
                sl_price=rev_target_h1_supply.top + spread_buf,
                reason="PATH_D_DLH_REVERSAL"
            )
```

**STATUS:** PENDING — Reversal target tracking exists in cycle_sm. Rules layer needed.

---

### E05: M1 CHoCH Add-On Entry (Path E)

**TRIGGER:** M5 cascade armed + M1 CHoCH in the entry direction

```python
def path_e_addon(m5_cascade_ready, m1_choch_direction, last_m1_zones):
    if m5_cascade_ready == "bear" and m1_choch_direction == "LH":
        return EntrySignal(
            direction="SHORT",
            entry_price=last_m1_sup_bot,
            sl_price=last_m1_sup_top + spread_buf,
            reason="PATH_E_M1_ADDON"
        )
    elif m5_cascade_ready == "bull" and m1_choch_direction == "HL":
        return EntrySignal(
            direction="LONG",
            entry_price=last_m1_dem_top,
            sl_price=last_m1_dem_bot - spread_buf,
            reason="PATH_E_M1_ADDON"
        )
```

**STATUS:** PENDING — M1/M5 zone processing not in current pipeline. Requires Rules layer + M1 data integration.

---

### E06: Macro Bias Limit Entry

**TRIGGER:** Macro bias confirms via M5 TL break at parent zone

```python
def macro_limit_entry(bias_direction, broken_m5_zone):
    if bias_direction == -1:  # bear
        return EntrySignal(
            direction="SHORT",
            entry_price=broken_m5_dem_top,  # limit at broken demand top
            sl_price=m1_sup_top + spread_buf,
            reason="MACRO_BIAS_LIMIT"
        )
    elif bias_direction == +1:  # bull
        return EntrySignal(
            direction="LONG",
            entry_price=broken_m5_sup_bot,
            sl_price=m1_dem_bot - spread_buf,
            reason="MACRO_BIAS_LIMIT"
        )
```

**STATUS:** PENDING — Macro bias fires correctly. Limit order level computation needs Rules layer.

---

## 4. Exit Signals

### X01: Reversal Target Reached

```python
def exit_at_reversal_target(position, rev_target_zone):
    """Exit when price reaches the identified reversal target zone."""
    if position.direction == "LONG" and rev_target_zone.is_supply:
        if current_price >= rev_target_zone.bot:
            return ExitSignal(reason="REVERSAL_TARGET_REACHED")
    elif position.direction == "SHORT" and not rev_target_zone.is_supply:
        if current_price <= rev_target_zone.top:
            return ExitSignal(reason="REVERSAL_TARGET_REACHED")
```
**STATUS:** PENDING

---

### X02: Opposing CHoCH

```python
def exit_on_choch(position, zone_break_event):
    """Exit when a CHoCH fires against the position direction."""
    if zone_break_event.is_choch:
        if position.direction == "LONG" and zone_break_event.is_bearish_choch:
            return ExitSignal(reason="OPPOSING_CHOCH")
        elif position.direction == "SHORT" and zone_break_event.is_bullish_choch:
            return ExitSignal(reason="OPPOSING_CHOCH")
```
**STATUS:** PENDING — CHoCH detection exists (zone breaks with `is_hh_or_ll=False`). Exit logic needs Rules layer.

---

### X03: Trailing Stop via Structural Levels

```python
def trail_stop(position, h1_zones, h4_zones):
    """Trail SL to last structural level (H1 COR zone, H4 zone)."""
    if position.direction == "LONG":
        # Trail to highest H1 demand bot that is below current price
        valid_demands = [z for z in h1_zones if not z.is_supply and z.bot < current_price]
        if valid_demands:
            new_sl = max(z.bot for z in valid_demands)
            return max(position.sl, new_sl)
    # Mirror for SHORT
```
**STATUS:** PARTIAL — `backtest/exit_logic.py` has trailing stop functions (ATR-based, zone-based). Not yet connected to live zone state from engine.

---

### X04: Phase Transition Exit

```python
def exit_on_phase_change(position, cycle_phase, prev_phase):
    """Exit when D-level cycle phase transitions."""
    if position.direction == "LONG" and cycle_phase == "C":
        return ExitSignal(reason="PHASE_C_DLH_FORMING")  # short setup forming
    elif position.direction == "SHORT" and cycle_phase == "A":
        return ExitSignal(reason="PHASE_A_TERMINAL")  # reversal setup forming
```
**STATUS:** PENDING

---

### X05: Terminal Exhaustion Counter-Signal

```python
def exit_on_terminal(position, terminal_state):
    """Exit when terminal exhaustion fires against position."""
    if position.direction == "LONG" and terminal_state.bull_active:
        return ExitSignal(reason="TERMINAL_BULL_ACTIVE")  # expect bearish reversal
    elif position.direction == "SHORT" and terminal_state.bear_active:
        return ExitSignal(reason="TERMINAL_BEAR_ACTIVE")  # expect bullish reversal
```
**STATUS:** PENDING — Terminal detection exists. Exit trigger needs Rules layer.

---

## 5. Signal Chain — Fractal Cascade

The core insight: every tradeable moment follows the same fractal template.

```
W1  ──→  D1  ──→  H4  ──→  H1  ──→  M15  ──→  M5  ──→  M1
 │        │        │        │         │         │        │
 │        │        │        │         │         │        └─ M1 CHoCH = EXECUTION TRIGGER
 │        │        │        │         │         └─ M5 CHoCH = cascade armed
 │        │        │        │         └─ M15 TL break = H1 push complete
 │        │        │        └─ H1 CHoCH = H4 structure confirmed early
 │        │        └─ H4 structure = D leg direction
 │        └─ D structure = weekly context
 └─ W structure = monthly direction
```

### Bottom-Up Confirmation Sequence

**For reversal entry at terminal bottom:**
```
1. Terminal exhaustion detected (S06)           → Phase A
2. H4 demand confirmed below D LL (S10)        → Zone live
3. H1 HL fires (S01 CHoCH at H1)               → H4 HL early (S12)
4. M15 bear TL break (S05)                      → H1 push complete
5. M15 HL inside H1 demand (S04 nesting)        → Continuation confirmed
6. M5 CHoCH (S08 cascade if 1-2-3 armed)       → Cascade armed
7. M1 CHoCH (HL) inside M5 supply               → EXECUTE LONG
```

**For continuation short after D LH:**
```
1. D LH confirmed via H4 HH capped (S12)       → Phase D
2. H1 LH fires (bearish structure)              → Direction set
3. M15 bull TL break (S05)                       → Pullback exhausted
4. M5 LH inside M15 supply (S04 nesting)        → Nested bearish
5. M1 LH (CHoCH) inside M5 demand               → EXECUTE SHORT
```

### Universal Pattern

```
HTF structure shifts (detected via zone comparison at HTF)
  → LTF CHoCH confirms it early (nested inside relevant HTF zone)
    → One-level-lower CHoCH provides precision entry
      → M1 CHoCH is always the final execution trigger
```

---

## 6. Signal Toggle Map

Each signal type can be independently enabled/disabled in the trading engine.
This allows selective testing and progressive activation during development.

```
┌──────────────────────────┬─────────┬───────────┬──────────────────────────┐
│ Signal                   │ Default │ Required  │ Dependencies             │
│                          │         │ By        │                          │
├──────────────────────────┼─────────┼───────────┼──────────────────────────┤
│ S01 Zone Classification  │ ON      │ ALL       │ (foundation)             │
│ S02 Structure Propagation│ ON      │ ALL       │ S01                      │
│ S03 Zone Counting        │ ON      │ S06, S10  │ S01                      │
│ S04 Zone Nesting         │ ON      │ E01-E05   │ S01                      │
│ S05 Trendline Breaks     │ ON      │ S07, S12  │ S01                      │
│ S06 Terminal Exhaustion  │ ON      │ E01, S10  │ S01, S02, S03            │
│ S07 Macro Bias           │ ON      │ E02, E06  │ S05, S04, S06            │
│ S08 1-2-3 Pattern        │ OFF*    │ E05       │ S01, S04                 │
│ S09 Boundary Zones       │ OFF*    │ (visual)  │ S01, S02                 │
│ S10 D-Level Cycle        │ ON      │ (context) │ S06, S02                 │
│ S11 Zone Tracking        │ ON      │ E04, X01  │ S01, S02, S10            │
│ S12 Early Cascade        │ ON      │ (early)   │ S01, S02, S05            │
├──────────────────────────┼─────────┼───────────┼──────────────────────────┤
│ E01 Terminal Reversal    │ ON      │ —         │ S06, S04                 │
│ E02 Stair-Step Cont.     │ ON      │ —         │ S07, S05                 │
│ E03 Mode B Aggressive    │ ON      │ —         │ S10, S11                 │
│ E04 D LH Reversal        │ ON      │ —         │ S11, S04                 │
│ E05 M1 CHoCH Add-On     │ OFF*    │ —         │ S08, S01 (M1 data)       │
│ E06 Macro Limit          │ ON      │ —         │ S07                      │
├──────────────────────────┼─────────┼───────────┼──────────────────────────┤
│ X01 Rev Target TP        │ ON      │ —         │ S11                      │
│ X02 Opposing CHoCH       │ ON      │ —         │ S01                      │
│ X03 Trailing Stop        │ ON      │ —         │ S01, S04                 │
│ X04 Phase Transition     │ ON      │ —         │ S10                      │
│ X05 Terminal Counter     │ ON      │ —         │ S06                      │
└──────────────────────────┴─────────┴───────────┴──────────────────────────┘

* OFF by default = requires explicit enabling + M1 data or additional
  processing not yet in the pipeline.
```

---

## 7. Implementation Status Summary

### Engine Layer (Layer 2) — What Exists

| Module | File | Status | What It Does |
|--------|------|--------|-------------|
| Zone tick | `engine/zone_tick.py` | DONE | Zone fire/break, HH/HL/LH/LL classification |
| Nested zones | `engine/nested_zones.py` | DONE | 8 child@parent combos, skip filter |
| Trendline tick | `engine/trendline_tick.py` | DONE | Push TL build + break detection |
| XTF trendlines | `engine/xtf_trendline.py` | DONE | Cross-TF impulse/correction TLs with target zones |
| Structure count | `engine/structure_count.py` | DONE | D/W HH/HL/LH/LL counting + streak resets |
| Wave SM | `engine/wave_sm.py` | DONE | H1 4-phase impulse/correction count |
| EW classify | `engine/ew_classify.py` | DONE | Elliott Wave 9-pattern classification |
| Macro bias | `engine/macro_bias.py` | DONE | M5 TL break + containment + terminal gate |
| Cycle SM | `engine/cycle_sm.py` | DONE | 5-phase D-level cycle (bear↔bull) |
| Early cascade | `engine/early_cascade.py` | DONE | H1→H4, H4→D, D→W early structure detection |
| Cascade tracker | `engine/cascade_tracker.py` | DONE | TL break cascade propagation (M5→M15→H1→H4) |
| HTF bias | `engine/htf_bias.py` | DONE | HTF structural bias from zone sequences |
| HA pivots | `engine/ha_pivots.py` | DONE | Heikin Ashi pivot detection |

### Orchestrator Layer (Layer 3) — What Exists

| Module | File | Status |
|--------|------|--------|
| Zone engine | `orchestrator/zone_engine.py` | DONE |
| Structure engine | `orchestrator/structure_engine.py` | DONE |
| Pipeline | `orchestrator/pipeline.py` | DONE |
| Compass | `orchestrator/compass.py` | DONE |

### What Needs Building

| Component | Layer | Priority | Dependencies |
|-----------|-------|----------|-------------|
| **1-2-3 Pattern detector** | Engine (L2) | HIGH | zone_tick (zone sequences) |
| **Boundary Zone tracker** | Engine (L2) | MEDIUM | zone_tick (H1 HH/LL + last unbroken) |
| **M1→M5 cascade extension** | Engine (L2) | MEDIUM | early_cascade (extend map to lower TFs) |
| **Entry signal generator** | Rules (L5) | HIGH | All engine signals |
| **Exit signal generator** | Rules (L5) | HIGH | Zone tracking, CHoCH, trailing |
| **Position manager** | Trader (L7) | HIGH | Rules layer |
| **Macro limit order viz** | Viz (L6) | LOW | macro_bias |
| **Boundary zone viz** | Viz (L6) | MEDIUM | Boundary tracker |
| **Signal markers on chart** | Viz (L6) | HIGH | Rules layer |
| **Weekly context check** | Rules (L5) | LOW | Zone nesting at W/D level |

### Build Sequence (Recommended)

```
Phase 1 (Engine gaps):
  1. Build 1-2-3 pattern detector (engine/one_two_three.py)
  2. Build boundary zone tracker (engine/boundary_zone.py)
  3. Extend early cascade to M1→M5→M15

Phase 2 (Rules layer):
  4. Build entry signal generator (rules/entries.py)
     - Wire E01-E06 using engine outputs
  5. Build exit signal generator (rules/exits.py)
     - Wire X01-X05 using engine outputs
  6. Build signal toggle config (rules/config.py)
     - Toggle map from Section 6

Phase 3 (Visualization):
  7. Add signal markers to LW Charts
  8. Add boundary zone rendering
  9. Add macro limit order dashed lines

Phase 4 (Trader layer):
  10. Build position manager (trader/position.py)
  11. Build strategy executor (trader/executor.py)
  12. Connect to broker API
```

---

## 8. Data Types Reference

All types from `engine/models.py` used by the rules system:

```python
# Zone
FractalZone(top, bot, is_supply, is_hh_or_ll, origin_time, is_broken, seq_num, is_reversal_target)

# Trendline
Trendline(t1, p1, t2, p2, direction, timeframe, is_broken, break_time,
          anchor_source, tl_type, target_zone_top, target_zone_bot, target_zone_time)

# Events
EventID.ZONE_FIRE / ZONE_BREAK / NESTED_FIRE / NESTED_BREAK / TL_BREAK
EventID.BIAS_BULL_CONF / BIAS_BEAR_CONF / TERMINAL_EXHAUST / CYCLE_PHASE
EventID.ONE_TWO_THREE / EARLY_STRUCTURE
EventID.ENTRY_LONG / ENTRY_SHORT / EXIT_LONG / EXIT_SHORT / SL_HIT

Event(id: EventID, timestamp, timeframe, payload: dict)

# State objects
MacroBiasState(macro_bias, bear_conf_fired, bull_conf_fired)
StructuralCycleState(cycle_bear_phase, cycle_bull_phase,
                     first_h4_dem_top/bot, first_h4_sup_top/bot,
                     rev_target_h1_sup_top/bot, rev_target_h1_dem_top/bot,
                     h4_tl_anchor_sup_top/bot, h4_tl_anchor_dem_top/bot)

# Early cascade
EarlyAnchor(parent_tf, child_tf, struct_type, is_supply, price, time, zone)
EarlyCascadeState(seen: set)

# Cascade tracker
PushState(...)
CascadeTrackerState(...)
```

### Types Needed for Rules Layer (to be created)

```python
@dataclass(frozen=True)
class EntrySignal:
    direction: str          # "LONG" | "SHORT"
    entry_price: float
    sl_price: float
    reason: str             # "PATH_A_TERMINAL_REVERSAL" | "PATH_B_STAIR_STEP" | etc.
    confidence: float       # 0.0-1.0 based on signal convergence
    tf: str                 # timeframe of the trigger
    timestamp: pd.Timestamp

@dataclass(frozen=True)
class ExitSignal:
    reason: str             # "REVERSAL_TARGET_REACHED" | "OPPOSING_CHOCH" | etc.
    exit_price: float | None
    timestamp: pd.Timestamp

@dataclass
class SignalConfig:
    """Toggle map — which signals are active."""
    zone_classification: bool = True
    structure_propagation: bool = True
    zone_counting: bool = True
    zone_nesting: bool = True
    trendline_breaks: bool = True
    terminal_exhaustion: bool = True
    macro_bias: bool = True
    one_two_three: bool = False       # requires implementation
    boundary_zones: bool = False      # requires implementation
    d_level_cycle: bool = True
    zone_tracking: bool = True
    early_cascade: bool = True
```

---

## 8. Context Mode Framework

> **Gating layer for Growth entries, exits, SL trailing, and scalp hedges.**
> Mutually exclusive modes determine which structural levels trigger which signals.
> First-match priority: FLIP → RIDE/SCALP → SKIP.

### 8a. Context Modes (Mutually Exclusive)

**FLIP** — D-Level Reversal Transition
```
Condition:    D-level CHOCH fired (d_phase == "D Pull v" or "D Pull ^")
Structure:    D transitioning from push to pullback
Market state: H4 corrective zone (HL/LH) will break immediately
H4 alignment: Not confirmed yet
Behavior:     Tight entries, aggressive SL, transition mode
```

**RIDE** — D-Level Push + Weekly Alignment
```
Condition:    D pushing (d_phase == "D Push ^" or "D Push v")
              AND H4 aligned with D (H4 also pushing same direction)
              AND weekly bias confirmed (w_lh or w_hl active)
Structure:    D + H4 + W1 all trending same direction
Market state: Building structural levels (HH/LL or confirmed HL/LH)
Behavior:     Can enter at H4 OR D1 zones, wide SL, hold through H4 retracements
```

**SCALP** — D-Level Push + H4 Retracing
```
Condition:    D pushing (d_phase == "D Push ^" or "D Push v")
              AND H4 reached opposing zone (retracing/failing)
Structure:    D pushing but H4 at range boundary, potential breakdown
Market state: H4 supply/demand approached (opposite to D direction)
Behavior:     Growth blocked, scalp hedges only, no Growth entries
```

**SKIP** — Undefined/Conflicting
```
Condition:    No clear macro direction
Examples:     D at equilibrium, conflicting TF signals, post-flip uncertainty
Behavior:     Conservative: no Growth entries, no exits, moderate SL only
```

### 8b. Mode Evaluation Priority

```
FLIP → RIDE/SCALP → SKIP    (first match wins, mutually exclusive)
```

Check FLIP first (overrides everything during transition). Then evaluate
RIDE vs SCALP (both active simultaneously if condition met — strategy picks one).
Finally, fall back to SKIP if no clear macro structure.

### 8c. Signal Gating by Context Mode

| Signal | RIDE | FLIP | SCALP | SKIP |
|--------|------|------|-------|------|
| **Growth Entry** | M15@H4 or M15@D1 + M1 CHOCH | M15@D1 only + M1 CHOCH | Blocked | Blocked |
| **Growth Exit** | D1 zone preferred (hold H4) | H4 or D1 zone (fast exits) | Suppressed | Suppressed |
| **SL Trailing** | H1/H4 wide trail | M15/H1 tight trail | None (no Growth) | M15/H1 moderate |
| **Scalp Hedge** | None | None | M5 zone + M1 CHOCH counter-trade | None |

**Detailed explanation:**

- **RIDE:** Normal mode — enter Growth trades at structural levels (H4 or D1 zone).
  Hold through H4 retracements (only exit at D1). SL is wide (H1 or H4 structure).

- **FLIP:** D-level transition — expect H4 corrective zones to break imminently.
  Only enter at confirmed D1 zones (not H4 alone). SL is tight (M15 structure).
  Exits are aggressive (H4 or D1 zone signals exit).

- **SCALP:** H4 retracing into opposing zone — Growth is risky (zone breakdown imminent).
  Block all Growth entries. Activate scalp hedges only (M5 counter-trades at pullback bounces).
  No SL trailing on Growth (but SL remains static).

- **SKIP:** Macro undefined — no new Growth entries. Hold existing positions with moderate
  SL (M15/H1). Exit existing Growth on clear reversals only.

### 8d. Implementation: `assess()` Function

```python
def assess(bar_features: BarFeatures) -> ContextMode:
    """
    Evaluate D-level phase + H4 alignment → return context_mode.

    Args:
        bar_features: Contains d_phase, h4_d_direction_match, w_lh, w_hl,
                      h4_reached_opposing_zone

    Returns:
        ContextMode: FLIP | RIDE | SCALP | SKIP (first match priority)
    """
    # FLIP: D-level transition overrides everything
    if bar_features.d_phase in ("D Pull v", "D Pull ^"):
        return ContextMode.FLIP

    # RIDE: D pushing + H4 aligned + weekly confirmed
    if (bar_features.d_phase in ("D Push ^", "D Push v") and
        bar_features.h4_d_direction_match and
        (bar_features.w_lh > 0 or bar_features.w_hl > 0)):
        return ContextMode.RIDE

    # SCALP: D pushing but H4 retracing
    if (bar_features.d_phase in ("D Push ^", "D Push v") and
        bar_features.h4_reached_opposing_zone):
        return ContextMode.SCALP

    # SKIP: Default
    return ContextMode.SKIP
```

---

## 9. Growth Mode — Fractal Cascade Entry Model

> **V2 — Simplified from Growth Walkthrough V1 (2026-03-23)**
> Source: 35 annotated screenshots + 63 golden screenshots.
> Full analysis: `docs/GROWTH_WALKTHROUGH_V1_ANALYSIS.md`

### 9a. The Universal Growth Pattern

There is ONE Growth entry pattern. Entries #1-#4 in a sequence are all
the same pattern repeated on retests. No separate "add-on" signal type.

**CONTEXT MODE GATING:** Growth entries are only allowed in RIDE or FLIP modes.
In SCALP mode, all Growth entries are blocked (use scalp hedges instead). In SKIP mode,
no entries until macro structure clarifies. See section 8 (Context Mode Framework).

```
THE PATTERN:
  1. Weekly bias confirmed (master switch)
  2. M1 zone forms inside M15 zone at the push extreme
  3. Execute at M1 zone (sell limit or MKT on M1 CHOCH)
  4. Continuation entries: each retest of the structure = new entry
```

### 9b. Master Switch — Weekly LH/HL Confirmation

```
BEARISH (W LH):
  IF D HH forms inside the last Daily supply zone
  THEN D HH = Weekly LH → go full bearish
  CONDITION: d_hh > 0 AND d1_price_in_supply
             OR w_lh > 0 (already propagated)

BULLISH (W HL):
  IF D LL forms inside the last Daily demand zone
  THEN D LL = Weekly HL → go full bullish
  CONDITION: d_ll > 0 AND d1_price_in_demand
             OR w_hl > 0 (already propagated)

Once set, the master switch stays until the opposing confirmation fires.
```

### 9c. Growth Sell (bearish)

```
CONTEXT:    W LH confirmed (D HH inside D supply)
ZONE:       M15 supply zone inside H4 or D1 supply zone
TRIGGER:    M1 CHOCH bearish (m1_choch_bear)
EXECUTION:  Sell at M1 supply zone / MKT on CHOCH
SL:         Above the M15 supply zone top (nearest_supply_price)
TP:         Next D1/H4 demand zone below
EXIT:       Price reaches D1/H4 demand + M1 CHOCH bullish → flip
```

### 9d. Growth Buy (mirror)

```
CONTEXT:    W HL confirmed (D LL inside D demand)
ZONE:       M15 demand zone inside H4 or D1 demand zone
TRIGGER:    M1 CHOCH bullish (m1_choch_bull)
EXECUTION:  Buy at M1 demand zone / MKT on CHOCH
SL:         Below the M15 demand zone bot (nearest_demand_price)
TP:         Next D1/H4 supply zone above
EXIT:       Price reaches D1/H4 supply + M1 CHOCH bearish → flip
```

### 9e. Continuation Entries (#2, #3, #4...)

```
After Growth #1 fires:
  - Price pulls back, retests the supply/demand zone structure
  - New M1 zone forms on retest → new Growth entry (SAME signal type)
  - Each entry: 1% account risk, independent SL at M15 zone edge
  - Trail SL on prior entries as new structural levels confirm
  - Repeat until target zone reached OR max lot hit

HOW continuation entries relate to H1 zone chain:
  - Each continuation entry happens at an H1 supply/demand zone
  - Between entries: H1 BOS fires (sweep) → retrace (scalp hedge) → zone retest
  - Growth #N corresponds to H1 zone #N in the push chain
  - Entry conviction depends on zone count phase (see 9i)
```

### 9f. Fractal Zone Confirmation Table

```
To confirm ANY structural level, look for the confirming zone one TF below:

  Structural Level → Confirming Zone TF
  W1               → D1
  D1               → H4
  H4               → M15
  H1               → M5
  M15              → M1

"The M5 zone created as we make the H1 LL = same as we use the
 M15 for the H4 LL" — the pattern is self-similar at every scale.
```

### 9g. Max Lot Cycling

```
When max lot per symbol is reached (ICMarkets broker limit):
  → Cannot add more Growth lots
  → Switch to EXIT/ENTER mode:
    - EXIT Growth position on pullback start (M1 CHOCH against direction)
    - ENTER Growth position when pullback ends (M1 CHOCH with direction)
    - Effectively: cycle in/out at max size on every push/pullback
  → Because structure confirms continuation, we KNOW pushes will continue
  → We just can't build MORE lots — so cycle at max
```

### 9h. Max Lot Lifecycle

> **Three stages of position sizing: building → cycling → full_scalp**

**Stage 1: Building** — `max_lot_state == "building"`
```
Condition:    total_lots < max_lots_per_symbol
Behavior:     Accept all Growth entries (fractal cascade)
              Add new M15 zones to growing position
              Each entry: 1% account risk
Exit mode:    Standard Growth exit (D1/H4 zone + M1 CHOCH)
Scaling:      Unlimited — keep adding until max_lots reached
```

**Stage 2: Cycling** — `max_lot_state == "cycling"`
```
Condition:    total_lots == max_lots_per_symbol
              AND multiple open Growth trades (2+ trades)
Behavior:     STOP accepting new Growth entries
              When M1 CHOCH signals pullback: EXIT worst trade (furthest from price)
              When M1 CHOCH signals push: ENTER new Growth trade at same level
              Net effect: rotate worst-performing trade out, new one in
              Position stays at max_lots, quality improves
Exit mode:    Individual trade exits on reversals (tighter SL than building phase)
Scaling:      Locked at max_lots — rotate rather than grow
```

**Stage 3: Full Scalp** — `max_lot_state == "full_scalp"`
```
Condition:    total_lots == max_lots_per_symbol
              AND only ONE open Growth trade remaining
Behavior:     Growth trade is at near-extreme or near-exit levels
              Every M1 CHOCH at M5 zone = potential scalp entry
              Scalp hedges accumulate counter-trend pips
              Primary Growth trade holds for reversal
Exit mode:    Growth exits at structural zones (normal rules)
              Scalp trades exit at pullback bounds (tight, M1-level)
Scaling:      Locked at 1 Growth + multiple scalps
```

**Transitions:**
```
Building → Cycling: When total_lots reaches max_lots for first time
Cycling → Full Scalp: When only 1 Growth trade remains (others closed)
Full Scalp → Cycling: When Growth trade exits and new one enters (back to 2+ trades)
Cycling → Building: When price pulls back significantly, other exits, back below max_lots
```

### 9i. H1 Push Phase — Zone Count Gating

> **The H1 unbroken zone count tells you WHERE you are in the push.**
> Source: 16 TradingView screenshots (`zones. impulse and correction/`)
> showing 8 H1 supply zones in a bearish GBPUSD push (Feb-Mar 2026).
> Cross-referenced with Growth Walkthrough V1 (`docs/GROWTH_WALKTHROUGH_V1_ANALYSIS.md`).

**The H1 zone chain is the push's heartbeat.** Each H1 supply/demand zone
created during a push represents one impulse leg. The retracement between
zones is the correction (scalp hedge territory). The 5+3 exhaustion pattern
applies at H1 level just as it does at every other TF.

```
ZONE COUNT → PUSH PHASE:

  Zones 1-3:  IMPULSE EARLY — High conviction entries
              Growth #1 (master switch) and #2 (retest) fire here
              H1 BOS = fresh sweep, strong momentum
              Scalp hedges on retracements: full target (H1 zone)

  Zones 4-5:  IMPULSE LATE — Standard conviction
              Growth #3, #4 continuation entries
              Momentum slowing but structure still extending
              Scalp hedges: still valid, watch for shorter retracements

  Zone 6:     BOUNDARY — Last zone before D-level break
              This is the reversal target zone when the flip comes
              (the last H1 zone created right before D LL/HH confirmed)
              Still valid for Growth continuation, but trail tight
              Mark this zone: it becomes the bullish reversal target later

  Zones 7-8:  CORRECTION — 5+3 exhaustion approaching
              H1 LH forms (zone 7) = correction wave beginning
              Stop adding Growth entries — push is exhausting
              Scalp hedges still valid (retrace into zone 7 = perfect retest)
              Trail SL aggressively on existing positions

  Zone 8+     TERMINAL — Inside H4 counter-zone
  inside H4:  5+3 exhaustion confirmed
              H1 demand/supply created inside H4 counter-zone = reversal platform
              Expect H1 supply/demand #8 to break (correction confirming)
              Prepare for FLIP: 2nd H1 LH/HL break → H4 HH/LL → D LH/HL
```

**How the zone count maps to Growth entries and scalp hedges:**

```
Bearish example (H1 supply zones pushing down from D supply):

  H1 Supply #1 ──── Growth SELL #1 (M1@M15 inside H1 supply)
       │ retrace UP = scalp BUY hedge → TP at H1 supply #1
  H1 Supply #2 ──── Growth SELL #2 (retest of structure)
       │ retrace UP = scalp BUY hedge → TP at H1 supply #2
  H1 Supply #3 ──── Growth SELL #3 (continuation)
       │ retrace UP = scalp BUY hedge → TP at H1 supply #3
  H1 Supply #4 ──── Growth SELL #4 (continuation)
       │ retrace UP = scalp BUY hedge
  H1 Supply #5 ──── Last high-conviction continuation
       │ retrace UP = scalp BUY hedge
  H1 Supply #6 ──── BOUNDARY: last zone before D LL break
       │              Mark as reversal target for future bullish flip
       │ retrace UP = scalp BUY hedge
  H1 Supply #7 ──── H1 LH forms: STOP adding Growth entries
       │              Perfect retest confirms correction wave (ss#03)
  H1 Supply #8 ──── TERMINAL: 5+3 inside H4 demand
                     New H1 demand inside H4 demand (ss#11)
                     Expect break of #8 → FLIP cascade begins
                     2nd H1 LH break → H4 HH → D LH (ss#13)
                     EXIT Growth SELLs, ENTER Growth BUY
                     Target: H1 supply #6 (ss#14)
```

**Zone count gating rules:**

```
h1_zone_count = count of unbroken H1 zones in current push direction

ENTRY GATING:
  h1_zone_count <= 5:  Accept Growth entries (impulse phase)
  h1_zone_count == 6:  Accept with caution (boundary — trail tight)
  h1_zone_count >= 7:  BLOCK new Growth entries (correction/terminal)

SCALP GATING:
  All phases:          Scalp hedges valid (retracements always tradeable)
  h1_zone_count >= 7:  Scalp hedges are PRIMARY (Growth frozen)

SL TRAILING:
  h1_zone_count <= 5:  Normal trail (H1 structural levels per context mode)
  h1_zone_count >= 6:  Aggressive trail (M15 levels — protect profits)

EXIT AWARENESS:
  h1_zone_count >= 7 AND h4_counter_zone_active:
    → 5+3 terminal exhaustion imminent
    → Prepare for FLIP: watch for 2nd H1 LH/HL break
    → EXIT when D CHOCH fires (context_mode shifts to FLIP)
```

**The boundary zone (#6) as reversal target:**

```
When the push exhausts and FLIP fires:
  → The reversal target is NOT random — it's H1 zone #6
  → Specifically: the last H1 opposing zone created BEFORE the D-level
    structural break was confirmed
  → This zone was the launch point for the final impulse leg
  → Price must reclaim this zone to prove the reversal

BEARISH → BULLISH flip:
  Target = H1 supply #6 (last supply before D LL confirmed)
  Growth BUY enters at H1 demand inside H4 demand (terminal zone)
  TP = H1 supply #6

BULLISH → BEARISH flip:
  Target = H1 demand #6 (last demand before D HH confirmed)
  Growth SELL enters at H1 supply inside H4 supply (terminal zone)
  TP = H1 demand #6
```

**Two-layer confirmation for push exhaustion:**

```
The push end is confirmed by TWO trendline breaks (ss#12):
  1. H1 push trendline break — the larger push structure ended
  2. M15 trendline break — the micro timing signal within the H1 push

When BOTH break together = high conviction that the H1 push leg is over.
This arms the scalp hedge for the retracement into the H1 zone.

M15 TL break alone = current H1 leg ending, watch for retrace
H1 TL break alone = push structure weakening, but may extend
Both break = push leg DONE, scalp hedge armed, Growth entry at zone
```

**Visual Evidence**

TradingView screenshots (`zones. impulse and correction/01-16`):
- ss#01: 8 H1 supply zones counted, 5+3 exhaustion question posed
- ss#02: H1 LL→H1 LH boundary logic = reversal box
- ss#03: Perfect retest on H1 LH zone = correction wave confirmed
- ss#04-08: Multi-TF context (D LL break, H4 rev zone, H1 boundary, M15 TL break)
- ss#09: All 8 zones labeled, 5+3 terminal inside H4 demand
- ss#10: H4 counter-zone below broken D LL = terminal checklist
- ss#11: New H1 demand inside H4 demand → expect break of H1 supply #8
- ss#12: Two-layer confirmation (H1 TL break + M15 TL break)
- ss#13: Phase shift cascade: 2nd H1 LH break → H4 HH → D LH → FLIP
- ss#14: Reversal target = H1 supply #6 (last zone before D LL break)
- ss#15: M15 supply inside H1 target zone = bearish triggers for next leg
- ss#16: Entry execution: buy limit at M15 demand in H1 demand

Growth Walkthrough V1 (`docs/GROWTH_WALKTHROUGH_V1_ANALYSIS.md`):
- Growth #1-#4 map to H1 zones #1-#4 in the push chain
- The retracements between Growth entries = scalp hedge territory
- 5+3 terminal exhaustion = Growth entry freeze + prepare for FLIP

### 9j. D-Level CHOCH Entry Filter

> When D-level CHOCH fires, H4 corrective levels (HL/LH) will break.
> Don't enter Growth at H4 corrective zones — wait for the confirming
> H4 structural level inside D demand/supply.
>
> **Note:** This filter is primarily active during FLIP mode (see section 8).
> In RIDE mode, entries at both H4 and D1 zones are allowed.

```
D LH CHOCH active (d_phase == "D Pull v"):
  → Bearish D transition: expect H4 push DOWN
  → H4 HL will break → DO NOT go Growth LONG at H4 demand alone
  → REQUIRE D1 demand (M15@H4 demand inside D demand = D HL confirmation)
  → Entry fires only when price reaches H4 LL inside D demand

D HL CHOCH active (d_phase == "D Pull ^"):
  → Bullish D transition: expect H4 push UP
  → H4 LH will break → DO NOT go Growth SHORT at H4 supply alone
  → REQUIRE D1 supply (M15@H4 supply inside D supply = D LH confirmation)
  → Entry fires only when price reaches H4 HH inside D supply

IMPLEMENTATION:
  _should_enter_buy():
    IF d_lh_active: nested_demand requires d1_price_in_demand (not H4 alone)
    ELSE: d1_price_in_demand OR h4_price_in_demand (normal)

  _should_enter_sell():
    IF d_hl_active: nested_supply requires d1_price_in_supply (not H4 alone)
    ELSE: d1_price_in_supply OR h4_price_in_supply (normal)
```

**Fractal logic behind the filter:**
```
Bullish example (D LH CHOCH → expect D HL):
  H4 builds bullish staircase: HH → HL → HH → HL → HH
  (this staircase = D bullish push, creating D demand zone beneath)
  D LH CHOCH fires → expect D push DOWN
  → H4 HL will break as H4 makes new LL
  → H4 LL inside D demand = D HL confirmation
  → M15 demand at this H4 LL = Growth LONG entry (confirmed D HL)
  → The D demand was created by the entire H4 staircase sequence

Bearish example (D HL CHOCH → expect D LH):
  H4 builds bearish staircase: LL → LH → LL → LH → LL
  D HL CHOCH fires → expect D push UP
  → H4 LH will break as H4 makes new HH
  → H4 HH inside D supply = D LH confirmation
  → M15 supply at this H4 HH = Growth SHORT entry (confirmed D LH)
```

### 9k. D-Level CHOCH Hold Logic

> When D CHOCH supports the Growth direction, hold through H4
> corrective zones. Only exit at D1 zone where the real reversal confirms.
>
> **Note:** This logic applies in RIDE mode (D supporting Growth direction).
> In FLIP mode, exits are more aggressive (H4 or D1 zone). See section 8c.

```
Growth SHORT + D LH active (bearish D supports our short):
  → H4 demand bounces are NOT exit signals
  → HOLD through H4 demand → only exit at D1 demand
  → The D1 demand is where D HL confirms (our exit + flip point)

Growth LONG + D HL active (bullish D supports our long):
  → H4 supply rejections are NOT exit signals
  → HOLD through H4 supply → only exit at D1 supply
  → The D1 supply is where D LH confirms (our exit + flip point)

IMPLEMENTATION:
  _should_exit_sell():
    IF d_lh_active: in_demand = d1_price_in_demand only (hold past H4)
    ELSE: in_demand = d1_price_in_demand OR h4_price_in_demand

  _should_exit_buy():
    IF d_hl_active: in_supply = d1_price_in_supply only (hold past H4)
    ELSE: in_supply = d1_price_in_supply OR h4_price_in_supply
```

---

## 10. Scalping / Hedging Mode — Counter-Trade Layer

> Scalping is NOT separate from Growth — it hedges Growth positions during
> pullbacks and captures counter-trend pips.

### 10a. Scalp Entry Contexts

```
M1@M15:  M1 CHOCH at M15 zone, counter to H4/H1 direction
M5@M15:  M5 CHOCH at M15 zone, counter to H4/H1 direction
M1@M5:   M1 CHOCH at M5 zone, counter to H1/H4 direction (BOS/CHOCH trigger)
M1@M1:   M1 CHOCH at M1 zone, counter to H1/H4 direction (BOS/CHOCH trigger)
```

### 10b. Scalp → Growth Handoff

```
Growth SELL active, price bouncing up (pullback):
  → H1 BOS fires (new LL = sweep of structural low)
  → ENTER scalp BUY at M5 demand + M1 CHOCH up (counter-trade, 1% risk)
  → Scalp rides pullback UP to last H1 supply zone (structural target)
  → EXIT scalp at H1 supply zone
  → IF h1_zone_count <= 6: ENTER Growth SELL continuation at same zone
  → IF h1_zone_count >= 7: scalp only, Growth frozen (5+3 correction)
  → Repeat at each H1 push leg

Growth BUY active (mirror):
  → H1 BOS fires (new HH = sweep of structural high)
  → ENTER scalp SELL at M5 supply + M1 CHOCH down
  → Scalp rides pullback DOWN to last H1 demand zone
  → EXIT scalp at H1 demand zone
  → IF h1_zone_count <= 6: ENTER Growth BUY continuation at same zone
  → IF h1_zone_count >= 7: scalp only, Growth frozen

The scalp TP and Growth entry are the SAME price level.
See Section 10d (Sweep-Scalp-Entry Chain) for full mechanics.
See Section 9i (H1 Push Phase) for zone count gating.
```

### 10c. HL / LH Target Zones

The HL targets (in demand zones) and LH targets (in supply zones) visible
on the charts serve triple duty:
- **Scalp TP:** Exit counter-trade here
- **Growth add-on entry:** Enter trend-direction trade here
- **Limit order levels:** Pre-place orders at these zone edges

### 10d. Sweep-Scalp-Entry Chain

> The structural break (BOS/CHOCH) at H1/H4 level IS a liquidity sweep.
> The retracement into the broken zone IS the scalp hedge.
> The M1 reversal inside that zone IS the Growth continuation entry.
> Scalp TP and Growth entry are the SAME price level.

**Concept: BOS = Sweep**

When price pushes from a D1 zone and breaks H1/H4 structure (BOS),
that break sweeps the liquidity sitting at the prior structural level.
The break itself is the sweep event — no separate "sweep detection" needed.

```
Bearish example (Growth SELL cycle):

  Price pushes down from D1 supply via H4 zone cascade
  → H1 BOS fires (breaks prior H1 LL)
  → This IS the liquidity sweep of the low
  → Price retraces UP into the last H1 supply zone
    (the zone that launched the push to make the new low)
  → Scalp BUY hedge enters here (M5 zone + M1 CHOCH up)
  → Scalp rides up into H1 supply zone
  → M1 CHOCH down inside H1 supply = Growth SELL continuation entry
  → Scalp closes at profit, Growth position grows

Bullish mirror:
  Price pushes up from D1 demand via H4 zone cascade
  → H1 BOS fires (breaks prior H1 HH)
  → Sweep of the high
  → Price retraces DOWN into last H1 demand zone
  → Scalp SELL hedge enters (M5 zone + M1 CHOCH down)
  → Scalp rides down into H1 demand zone
  → M1 CHOCH up inside H1 demand = Growth BUY continuation entry
```

**Integration with H1 Push Phase (Section 9i)**

The sweep-scalp-entry chain is gated by the H1 zone count from Section 9i.
The zone count determines whether the chain produces a Growth entry or
only a scalp:

```
H1 zone count 1-5 (IMPULSE):
  Sweep → Scalp hedge → Growth continuation entry (full chain)
  Each chain iteration = one more Growth position added

H1 zone count 6 (BOUNDARY):
  Sweep → Scalp hedge → Growth entry with tight trail
  Last high-conviction continuation — mark boundary zone as reversal target

H1 zone count 7-8 (CORRECTION/TERMINAL):
  Sweep → Scalp hedge → NO Growth entry (chain truncated)
  Scalp hedge still fires (retracements are tradeable)
  But Growth is frozen — push is exhausting (5+3 imminent)
  Zone 7 retest = "perfect retest" (ss#03) — scalp only
  Zone 8 inside H4 counter-zone = terminal → prepare for FLIP
```

**Fractal Cascade Confirmation (x4 Rule)**

4× H1 structure breaks (BOS/CHOCH) accumulate into 1× D-level structural
shift. Each H1 break is a sweep of the prior H1 level, and the cascade of
four such sweeps constitutes the D-level CHOCH:

```
H1 BOS #1 → sweep of H1 LL → retrace → scalp hedge → Growth entry
H1 BOS #2 → sweep of H1 LL → retrace → scalp hedge → Growth entry
H1 BOS #3 → sweep of H1 LL → retrace → scalp hedge → Growth entry
H1 BOS #4 → D CHOCH fires → context shifts RIDE→FLIP
             → final Growth exit at D zone, lifecycle resets
```

Note: The x4 rule describes one macro cycle. Within the push, H1 zones
#1-#5 are impulse (Growth entries fire), #6-#8 are correction (scalp only).
The CHOCH that fires after the 5+3 exhaustion is the D-level shift.

**Chain Sequence (Single Iteration)**

```
Step 1: DETECT   — H1 BOS fires during active Growth push
Step 2: SWEEP    — The BOS itself = liquidity sweep of prior H1 level
Step 3: RETRACE  — Price returns to last H1 opposing zone (supply for bear, demand for bull)
Step 4: HEDGE    — Scalp counter-trade at M5 zone + M1 CHOCH (SCALP context)
Step 5: TARGET   — Scalp TP = the H1 zone from Step 3
Step 6: GATE     — Check h1_zone_count: if <= 6 → proceed to Step 7, if >= 7 → STOP (scalp only)
Step 7: ENTRY    — M1 reversal inside that H1 zone = Growth continuation entry
Step 8: REPEAT   — New Growth entry rides next H1 push, cycle restarts at Step 1
```

**Conviction Scoring**

Growth entries preceded by a completed sweep-scalp chain carry higher
conviction than entries without one:

```
sweep_preceded = True:   Scalp completed into H1 zone → M1 reversed → ENTRY
                         Confidence boost: sweep confirmed liquidity taken
sweep_preceded = False:  Direct M1 CHOCH inside zone, no prior scalp
                         Standard confidence (still valid entry)

h1_zone_count modifier:
  zones 1-3:  +HIGH   (impulse early — strongest entries)
  zones 4-5:  +NORMAL (impulse late — still valid)
  zone 6:     +CAUTION (boundary — trail tight immediately)
  zones 7+:   BLOCKED (correction — no Growth entry)
```

**Reversal Target: The Boundary Zone**

When the push exhausts and context shifts to FLIP (Section 8), the
reversal target is the boundary zone — specifically H1 zone #6, the
last opposing zone created before the D-level structural break:

```
Bearish → Bullish FLIP:
  Growth BUY enters at H1 demand inside H4 demand (terminal zone)
  Scalp hedge target = H1 supply #6 (last supply before D LL confirmed)
  Growth BUY TP = H1 supply #6

Bullish → Bearish FLIP:
  Growth SELL enters at H1 supply inside H4 supply (terminal zone)
  Scalp hedge target = H1 demand #6 (last demand before D HH confirmed)
  Growth SELL TP = H1 demand #6

Inside the target zone (H1 #6), the OPPOSING entries fire:
  M15 supply zones inside H1 supply #6 = bearish Growth SELL triggers (ss#15)
  M15 demand zones inside H1 demand #6 = bullish Growth BUY triggers
  This IS section 9c/9d: M15 zone inside H4/D1 zone = Growth entry
```

**M15 TL Break = Push Leg End Signal**

The M15 trendline break signals the end of the current H1 push leg.
When confirmed with the H1 push trendline break (two-layer confirmation),
the scalp hedge is armed:

```
M15 TL break alone:    Current H1 leg ending — watch for retrace
H1 TL break alone:     Push structure weakening — may extend one more leg
Both break together:    Push leg DONE — scalp hedge armed — Growth entry at zone

This is the timing mechanism for Steps 3-4 of the chain sequence.
The M15 TL break is already tracked by trendline_tick.py.
```

**Code Implications (Future)**

```
scalp_hedge.py:
  - target_zone: point to last H1 opposing zone (not just next M15)
  - tag sweep_origin: which H1 BOS triggered the scalp opportunity
  - gate: always fires (all zone count phases allow scalp hedges)

growth_entry.py:
  - check h1_zone_count: block entry if >= 7 (correction phase)
  - check if scalp completed into current zone before entry
  - set sweep_preceded flag on Signal for higher confidence scoring
  - H1 BOS count tracking: which iteration of the cascade (1-8)
  - boundary_zone_flag: tag zone #6 for reversal target tracking

growth_exit.py:
  - reversal target = boundary zone (H1 #6) when in FLIP mode
  - 5+3 terminal detection: h1_zone_count >= 8 + h4_counter_zone → prepare exit

position_state.py:
  - track h1_zone_count per Growth lifecycle
  - track sweep_count (how many completed sweep-scalp-entry chains)
  - cascade_progress: 0-8 H1 zones toward terminal exhaustion
  - boundary_zone_price: price level of H1 zone #6 for TP targeting

sl_trailing.py:
  - h1_zone_count >= 6: switch to aggressive M15-level trail
  - h1_zone_count >= 7: tightest trail (protect all profits)
```

**Visual Evidence**

Flint multichart screenshots 20260324_063020–063529 (GBPUSD M15+M1):
- Context bands showing RIDE→FLIP transitions at D structural shifts
- H1 zone nested inside D supply as the sweep target
- Retracement into H1 zone after BOS = scalp hedge territory
- "H1 CHOCH x4 = D1 CHOCH" cascade annotation
- Circle marking the exact M1 reversal zone where scalp TP = Growth entry

TradingView screenshots (`zones. impulse and correction/01-16`):
- ss#01-03: 8 H1 zones counted, boundary logic (LL→LH), perfect retest
- ss#04-08: Multi-TF overlay (D LL + H4 rev zone + H1 boundary + M15 TL break)
- ss#09-11: 5+3 terminal inside H4 demand, H4 counter-zone, nested H1 demand
- ss#12: Two-layer confirmation (H1 TL + M15 TL break together)
- ss#13: FLIP cascade (2nd H1 LH break → H4 HH → D LH)
- ss#14: Reversal target = H1 supply #6 (last before D LL break)
- ss#15: M15 supply inside H1 target zone = bearish triggers
- ss#16: Entry execution: buy limit at M15 demand in H1 demand

Growth Walkthrough V1 (`docs/GROWTH_WALKTHROUGH_V1_ANALYSIS.md`):
- Growth #1-#4 map to H1 zones #1-#4 in the push chain
- Retracements between Growth entries = scalp hedge territory
- Full fractal cascade: W→D→H4→H1→M15→M5→M1 confirmed

---

## 11. Stop Loss — Detailed Logic

### 11a. SL Placement

```
Growth SELL: SL above the M1 supply zone top (the actual high)
Growth BUY:  SL below the M1 demand zone bot (the actual low)
Scalp:       SL at zone edge of entry zone (tight, M1-level)
```

### 11b. SL Trailing

```
At each new confirmed Growth signal (M1 CHOCH in trend direction):
  → Trail SL to above/below the latest M1 zone that confirmed direction
  → Never move SL backward (only tighten)
  → Continue trailing through entire Growth push

Example (Growth SELL):
  Entry SL:   above M1 supply zone A (initial high)
  After CHOCH 2: SL moves to above M1 supply zone B (lower high)
  After CHOCH 3: SL moves to above M1 supply zone C (even lower high)
  ...continues until exit
```

---

## 12. Position Sizing

### 12a. Risk Per Trade

```
ALL trade types: 1% account risk per entry
  Growth initial:  1% risk
  Growth add-on:   1% risk (SL trailed, so total exposure compresses)
  Scalp/hedge:     1% risk (tight SL at M1 zone edge)
```

### 12b. Position Calculation

```python
def calculate_lots(account_balance, risk_pct, entry_price, sl_price, pip_value):
    risk_amount = account_balance * risk_pct  # e.g. $10,000 * 0.01 = $100
    sl_pips = abs(entry_price - sl_price) / pip_size
    lots = risk_amount / (sl_pips * pip_value)
    return min(lots, max_lots_per_symbol)  # cap at broker limit
```

---

## 13. Daily Session Logic

### 13a. Within Active D1 Trend (bearish example)

```
1. New daily candle opens
2. Price moves UP to test former H1 BOS (LL) level
3. This creates/confirms the DAILY HIGH
4. Price pushes DOWN to create DAILY LOW
5. Growth add-ons fire during the DOWN push
6. Scalps capture the UP move (pullback)
7. Repeat next trading day
```

In bullish D1 trend: mirror (daily low first via pullback, then push up).

### 13b. H4 Candle Cascade

```
M1 HL/LH → sets H4 candle high/low
  → H1 push through zones → new H1 LL/HH
    → new H4 low/high
      → next H4 candle opens → sets new high/low
        → process aggregates into daily structure
          → daily aggregates into weekly structure

Background H4 candle overlay on M1 chart tracks this in real-time.
Growth trades ride the H4 body direction.
Scalps capture the H4 wick pullbacks.
```

---

## 14. Exit/Entry Flip — Continuous Cycle

```
Growth position reaches target zone:
  → EXIT current direction (TP at opposing D1/H4 zone)
  → ENTER opposite direction (new Growth trade at same zone)
  → Same zone serves as both TP and new entry
  → Cycle continues indefinitely

The exit of one Growth trade IS the entry setup for the next.
Sell TP at demand = Buy setup begins.
Buy TP at supply = Sell setup begins.
```

---

## 15. Automation & Backtest Parity

### 15a. Rule-Based Parity

```
The SAME rules apply to:
  - Live trading (real-time execution)
  - Backtesting (historical replay)
  - Visual validation (chart replay mode)

NO discretionary components — 100% rule-based.
Backtest results = expected live results.
```

### 15b. Backtest Plan

```
1. Run full backtest on ALL available candle data, all metrics
2. Visual replay mode for spot-checking results
3. Identify loss clusters → jump to that time period
4. Inspect: are rules wrong, or is market context unusual?
5. Fine-tune small details only — core rules are proven
6. Re-run backtest → verify improvement
7. Iterate → deploy live
```

---

## 16. Rules Layer Implementation Map

### Module Structure (`src/flint/rules/`)

```
signal.py          ← EXISTS: Signal dataclass (ENTRY/EXIT/HEDGE/ADD_ON/SL_MOVE/TP_TARGET/INFO)
registry.py        ← EXISTS: SignalRegistry (register, enable/disable, evaluate_all)
position_state.py  ← EXISTS: Track open positions, lots, direction, max_lot_state
__init__.py        ← EXISTS: Exports + create_default_registry()

context_mode.py    ← EXISTS: assess() function (FLIP/RIDE/SCALP/SKIP gating)
                     Evaluates d_phase + h4_alignment → ContextMode enum

growth_entry.py    ← EXISTS: Fractal cascade entry (W LH/HL + M15@H4/D1 + M1 CHOCH)
                     Gated by context_mode (RIDE/FLIP only, not SCALP/SKIP)
growth_exit.py     ← EXISTS: Exit at opposing D1/H4 zone + M1 CHOCH reversal
                     Behavior varies by context_mode (tight in FLIP, wide in RIDE)
sl_trailing.py     ← EXISTS: Trail SL behind confirmed structural levels (M15/H1/H4)
                     Width varies by context_mode (H1/H4 wide in RIDE, M15/H1 tight in FLIP)

scalp_hedge.py     ← EXISTS: Counter-trend scalp (M5 zone + M1 CHOCH)
                     Only active in SCALP mode, blocked in others
tp_targets.py      ← DISABLED: TP is the next HTF zone (implicit in exit rule)
```

### Active Registry (4 rules + context gating)

```
0. context_mode    — Assess macro phase (first, gates all others)
1. growth_exit     — Check exits first (may free position for new entry)
2. growth_entry    — Fractal cascade entries (gated by context_mode)
3. scalp_hedge     — Counter-trade hedges (SCALP mode only)
4. sl_trailing     — Trail SL on structural confirmations
```

### Build Sequence

```
Phase 1: ✅ Position state (tracks what we're holding)
Phase 2: ✅ Context mode layer (assess macro phase, gate all rules)
Phase 3: ✅ Growth entry + exit (fractal cascade model, context-gated)
Phase 4: ✅ SL trailing (structural levels, width per context_mode)
Phase 5: ✅ Scalp hedge entries (M5 counter-trades, SCALP mode only)
Phase 6: Wire into pipeline + viz (signal markers on chart)
Phase 7: Backtest integration
Phase 8: Live execution (post-production)
```

### Source References

- Section 8 of this document: context mode framework (FLIP/RIDE/SCALP/SKIP gating)
- Sections 9-14 of this document: trade lifecycle rules
- `docs/SCREENSHOT_ANALYSIS.md`: visual evidence (63 golden screenshots)
- `docs/GROWTH_WALKTHROUGH_V1_ANALYSIS.md`: Growth pattern walkthrough (35 screenshots)
- `docs/EARLY_CONFIRMATION_CASCADE.md`: cascade confirmation mechanics
- Sections 1-7 of this document: signal detection framework

---

> **This document is the SSOT for all trading rules.** When rules are added,
> modified, or removed, update this file. When the Rules layer (L5) is built,
> each entry/exit function should reference the signal ID (S01-S12, E01-E06,
> X01-X05) and the operational rule section (9-14) from this document.
