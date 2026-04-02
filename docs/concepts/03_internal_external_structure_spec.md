# Internal / External Market Structure — Flint Specification

**System:** Flint — Spring Leaf  
**Date:** March 2026  
**Status:** Phase 1 specification — ready for implementation + bar-replay validation

---

## 1. What the Pine Script does (and why we don't need it)

The uploaded `internal_external_market_structure.pine` (UAlgo) uses **fixed lookback windows** to detect swing highs/lows:

```
detectSwings(len) =>
    upperLevel = ta.highest(len)
    lowerLevel = ta.lowest(len)
    swingDirection := high[len] > upperLevel ? 0 : low[len] < lowerLevel ? 1 : swingDirection
```

- **Internal swings:** `len=8` — short-range pivots
- **External swings:** `len=30` — major pivots

When a swing is crossed (body close beyond it), the script classifies:
- **Same direction** as previous break → **BOS** (continuation)
- **Opposite direction** → **CHoCH** / MSB (reversal warning)
- **External breaks** get `+` suffix: `BoS+`, `CHoCH+`

### The problem with this approach

1. **Arbitrary parameters.** `len=8` and `len=30` are static — they don't adapt to market conditions. A `len=30` external swing might catch major pivots in a trend but miss them in a range, or flag false ones in volatility.

2. **Lag.** You need N bars after a swing to confirm it. The swing high is detected at `high[len]` — meaning you're always `len` bars behind reality.

3. **Single-timeframe simulation.** The Pine Script only sees one TF at a time and simulates multi-TF awareness with sliding windows. Flint has **real multi-TF data** — actual H1 zones, actual H4 zones, actual D zones.

4. **No zone awareness.** The script detects naked price swings. It has no concept of supply/demand zones, zone chains, or the institutional order flow encoded in those zones.

---

## 2. The zone-based alternative

### Core insight

Flint's HA zones **already encode the structure**. Each zone has a classification (HH / LH / HL / LL) from comparing to the previous same-type zone on the same TF. The internal/external distinction isn't a parameter to tune — it's a **structural fact** determined by the timeframe relationship.

### The rules

| Concept | Pine Script approach | Zone-based approach |
|---|---|---|
| **Internal swing high** | `ta.highest(8)` lookback | Current TF's latest supply zone top (from HA zone chain) |
| **Internal swing low** | `ta.lowest(8)` lookback | Current TF's latest demand zone bottom (from HA zone chain) |
| **External swing high** | `ta.highest(30)` lookback | **Parent TF's** latest supply zone top |
| **External swing low** | `ta.lowest(30)` lookback | **Parent TF's** latest demand zone bottom |
| **BOS** | Same-direction break of swing | Body close through HH supply or LL demand (zone classification shortcut) |
| **CHoCH** | Opposite-direction break | Body close through LH supply or HL demand (zone classification shortcut) |
| **Lag** | `len` bars after swing | **Zero lag** — CHoCH event IS the confirmation |

### External structure confirmation — the mechanism

An **external high** is confirmed the moment price body-closes below the demand zone that created the last BOS (the HH-making demand). At that instant:
- The **supply zone at the peak** becomes the confirmed external structure top
- No lookback window needed — the CHoCH event is the confirmation itself

An **external low** is confirmed by the consecutive unbroken chain completing:
```
Dem LL → Sup LH → Dem LL → Sup LH → Dem HH
```
The moment that HH BOS fires (breaking the last LH supply), the external low is confirmed as the lowest demand zone bottom in the chain.

### The "unbroken" qualifier

The chain only confirms external structure if **none of the intermediate zones were broken out of sequence**. This is precisely what Flint's zone chain count already tracks — unbroken zones from the last H4 zone. A zone that gets consumed/invalidated mid-chain breaks the sequence and resets the count.

---

## 3. The timeframe cascade

This is where the zone-based approach becomes fundamentally more powerful than any single-TF lookback.

### The hierarchy

| Current TF internal | = | Parent TF |
|---|---|---|
| M1 external structure | = | M5 internal structure |
| M5 external structure | = | M15 internal structure |
| M15 external structure | = | H1 internal structure |
| H1 external structure | = | H4 internal structure |
| H4 external structure | = | D internal structure |
| D external structure | = | W internal structure |
| W external structure | = | MN internal structure |

### What this means in practice

An **H1 CHoCH** (external break on H1) is simultaneously an **H4 internal swing completing**. When enough H4 internal swings accumulate to break H4 external structure, that's the **H4 BOS or CHoCH** — which is itself a **D internal event**. The same logic continues upward: D external breaks create W structure, and W external breaks create MN structure — giving full macro context from the monthly level all the way down to the M1 execution level.

Reading **bottom-up** (for execution):
```
M1 CHoCH → confirms M5 sub-wave direction
  → M5 CHoCH → confirms M15 zone leg complete  
    → M15 CHoCH → confirms H1 sub-wave complete
      → H1 CHoCH → creates H4 structure (H4 HH/HL/LH/LL)
        → H4 structural event → creates D structure
          → D structural event → creates W structure
            → W structural event → creates MN structure
```

Reading **top-down** (for context):
```
MN macro supply/demand → frames the multi-month trend
  → W external = MN zone boundaries (MN supply top, MN demand bottom)
    → D external = W zone boundaries (W supply top, W demand bottom)
      → H4 external = D zone boundaries (D supply top, D demand bottom)
        → H4 internal = H1 external = H1 zone chain
          → H1 internal = M15 external = M15 zone chain
            → M15 internal = M5 external
              → M5 internal = M1 external
```

### The early confirmation cascade

This is the mechanism from the SMC reference document (`EARLY_CONFIRMATION_CASCADE.md`), but now with mechanical plumbing:

The H4 HH is a **lagging description** of something the H1 CHoCH already confirmed. The M1 CHoCH is already telling you the H4 event is mechanically inevitable before the H4 candle has even closed.

| HTF event | Early confirmation | Earliest tradeable signal |
|---|---|---|
| H4 HH | H1 HH (top > prev H4 supply top) | M1 HL after H1 first HL fires |
| H4 LL | H1 LL (bot < prev H4 demand bot) | M1 LH after H1 first LH fires |
| H4 HL | H1 HL sequence ascending inside H4 demand | M15 HL inside H1 demand @ H4 demand |
| H4 LH | H1 LH sequence descending inside H4 supply | M15 LH inside H1 supply @ H4 supply |
| D LH | H4 HH capped below D supply top | H1 CHoCH (first LH after H4 HH) |
| D HL | H4 LL floored above D demand bot | H1 CHoCH (first HL after H4 LL) |
| W LH | D HH capped below W supply top | H4 CHoCH (first LH after D HH) |
| W HL | D LL floored above W demand bot | H4 CHoCH (first HL after D LL) |
| MN LH | W HH capped below MN supply top | D CHoCH (first LH after W HH) |
| MN HL | W LL floored above MN demand bot | D CHoCH (first HL after W LL) |
| H1 leg complete | M15 CHoCH opposing inside H1 zone | M1 CHoCH after M5 CHoCH inside M15 |
| H1 wave count +1 | New H1 zone fires (M15 sub-wave done) | M15 TL break |

---

## 4. Implementation — Phase 1

### What already exists in Flint

- `ha_supply_demand_zones.pine` — base zone detection with 8-TF support, HA color flip → zone creation
- `spring_leaf_wave_navigator.pine` — zone tick, BOS/CHoCH detection, nested containment, sequence counting, wave state machine, boundary zones, HTF phase, dashboard table, push trendlines
- Flint Dash app — visualisation layer in Python/Dash
- Zone classification (HH/LH/HL/LL) by comparing to previous same-type zone on same TF

### What needs to be built

#### 4.1 Structure state per timeframe

For each active TF in the stack, maintain:

```python
class StructureState:
    """Tracks internal/external structure for one TF."""
    
    # Current bias
    bias: str  # 'bullish' | 'bearish' | 'neutral'
    
    # Last confirmed external structure points
    external_high: float  # = parent TF supply zone top
    external_high_time: datetime
    external_low: float   # = parent TF demand zone bottom  
    external_low_time: datetime
    
    # Last internal structure break
    last_internal_break_type: str  # 'BOS' | 'CHoCH'
    last_internal_break_direction: int  # +1 bullish, -1 bearish
    last_internal_break_price: float
    last_internal_break_time: datetime
    
    # Zone chain (unbroken zones since last parent TF zone)
    chain_count: int
    chain_zones: list  # ordered list of zone references
```

#### 4.2 Zone-based swing detection (replaces Pine Script `detectSwings`)

```python
def get_structure_swings(tf_zones, parent_tf_zones):
    """
    Derive internal and external swing levels from zone chains.
    
    Internal swings = current TF zone tops/bottoms
    External swings = parent TF zone tops/bottoms
    
    No lookback windows. No lag. The zones ARE the swings.
    
    Parameters:
        tf_zones: list of zones on current TF (with HH/LH/HL/LL labels)
        parent_tf_zones: list of zones on parent TF
    
    Returns:
        internal_highs: list of (price, time) for each supply zone top
        internal_lows: list of (price, time) for each demand zone bottom
        external_high: (price, time) from latest parent supply zone top
        external_low: (price, time) from latest parent demand zone bottom
    """
```

#### 4.3 BOS/CHoCH classification (replaces Pine Script `checkMarketStructure`)

```python
def classify_break(zone_broken, previous_break_direction):
    """
    Classify a structure break using the zone classification shortcut.
    
    HH or LL zone broken → BOS (structural, trend continues, chain +1)
    LH or HL zone broken → CHoCH (corrective, reversal warning)
    
    No tracing required. The zone classification IS the answer.
    
    Body close rule: only candle body closes count.
    Wicks through a level = liquidity sweep, not a break.
    
    Parameters:
        zone_broken: the zone that was broken (has .label: HH/LH/HL/LL)
        previous_break_direction: +1 or -1
    
    Returns:
        break_type: 'BOS' | 'CHoCH'
        direction: +1 (bullish) | -1 (bearish)
        is_external: bool (True if zone belongs to parent TF)
        label: 'BoS' | 'CHoCH' | 'BoS+' | 'CHoCH+'
    """
    if zone_broken.label in ('HH', 'LL'):
        break_type = 'BOS'
    else:  # LH or HL
        break_type = 'CHoCH'
    
    direction = +1 if zone_broken.label in ('HH', 'LH') else -1
    # HH/LH broken upward = bullish, HL/LL broken downward = bearish
    
    is_external = zone_broken.tf != current_tf  # parent TF zone
    suffix = '+' if is_external else ''
    label = f"{break_type}{suffix}"
    
    return break_type, direction, is_external, label
```

#### 4.4 Cross-TF propagation

```python
def check_cross_tf_propagation(child_tf_zone, parent_tf_zones):
    """
    Check if a child TF zone event creates structure at the parent TF.
    
    Threshold rules (from SMC reference):
        H1 HH: H1 supply top > prev H4 supply top → H4 HH (bearish-to-bullish at H4)
        H1 LH: H1 supply top < prev H4 supply top → H4 LH (H4 correction, D bear intact)
        H1 LL: H1 demand bot < prev H4 demand bot → H4 LL (bullish-to-bearish at H4)
        H1 HL: H1 demand bot > prev H4 demand bot → H4 HL (H4 correction, D bull intact)
    
    Same logic applies H4 → D.
    """
```

#### 4.5 Chart overlay specification

On the Dash chart viewer, overlay:

| Element | Style | Meaning |
|---|---|---|
| **External structure line** | Solid horizontal line (teal for bullish, red for bearish) | Parent TF swing level — the "real" structure |
| **Internal structure line** | Dashed horizontal line (same colours, lighter) | Current TF swing level — sub-wave noise |
| **BoS label** | Below/above line, small text | BOS — continuation confirmed |
| **CHoCH label** | Below/above line, small text | CHoCH — reversal warning |
| **BoS+ label** | Same position, bold text | External BOS — major structural event |
| **CHoCH+ label** | Same position, bold text | External CHoCH — potential macro reversal |

Lines extend from the swing point (zone creation time) to the break point (body close time).

---

## 5. Validation approach — bar replay sequences

After Phase 1 implementation, validate with bar replay on GBPUSD/EURUSD/XAUUSD by checking:

1. **Do internal breaks on H1 match what would be H4 internal structure?** They should — by definition.
2. **Do external breaks on H1 (BoS+/CHoCH+) correspond to H4 zone boundaries?** They must.
3. **Does the chain count match?** Unbroken H1 zones from last H4 zone should count 1-5 (impulse), 6 (boundary), 7-8 (correction/terminal).
4. **Zero lag test:** When a CHoCH fires, is the external swing confirmed immediately (no lookback delay)?
5. **Cross-TF cascade test:** When M15 CHoCH fires inside H1 supply, does it correctly signal H1 sub-wave completion? When H1 CHoCH fires, does it correctly create H4 structure?

### What to look for in replay

- **Push phase:** Consecutive unbroken iBOS labels (Dem LL → Sup LH → Dem LL → Sup LH → ...) with chain count incrementing. Each iBOS should be marked as internal BOS.
- **Reversal point:** The moment price body-closes through the last LH supply (in a bearish push) or HL demand (in a bullish push), that's the iCHoCH. The peak supply or trough demand becomes confirmed external structure.
- **Cascade timing:** The M15 CHoCH should fire before the H1 zone is visually confirmed on the H1 chart. The M1 CHoCH should fire before the M15 is confirmed. This is the early confirmation cascade — and it should be visible as nested events on the overlay.

---

## 6. Phase 2 preview — connecting to meso zones

Once Phase 1 is validated, Phase 2 wires the structure detection into the existing Flint rules:

- **context_mode** gates (RIDE/FLIP/SCALP/SKIP) use external structure state
- **growth_entry** triggers use internal structure (M15 CHoCH inside H1 zone)
- **HTF zone validity:** CHoCH only valid if sourcing from parent TF zone (D1 macro supply/demand)
- **Zone chain count** feeds directly from the unbroken internal zone sequence
- **Breaker/mitigation block detection** uses the zone lifecycle (active OB → consumed → reclassified)

---

## 7. Breaker zone persistence and targeting

### The rule

When an **external BOS (eBOS)** fires, the zone that was broken through becomes a **breaker block**. This breaker block **persists on the chart until retested** — no timeout, no bar limit, no count filtering. It remains visible as a target and a reversal zone until price physically returns to it (body close enters the zone) or a new external structural event overrides it.

### Why breakers must persist

The breaker zone serves a dual purpose:

1. **Exit target** for the reversal trade — the long from the terminal demand (or short from terminal supply) rides TO the breaker zone
2. **Entry zone** for the next directional trade — the D LH (or D HL) forms AT the breaker zone

Removing the breaker prematurely loses both the exit target AND the re-entry zone.

### The mechanical sequence

```
1. eBOS fires (e.g., bearish — price breaks below external low)
   → The supply zone at the peak becomes a BREAKER BLOCK

2. Internal correction begins (internal swings push lower)
   → iBOS events continue, chain count increments

3. Impulse trendline breaks (correction gaining momentum)
   → This is the TL break confirmation from the SMC v6 spec

4. Price targets the breaker zone above
   → The breaker zone IS the specific mechanical target
   → This is WHERE the D1 LH forms (H4 HH capped below D supply = D LH)

5. Two outcomes at the breaker:
   a. Price retests and rejects → D LH confirmed, bearish continuation
   b. Price breaks through the breaker → external CHoCH (eCHoCH)
      → The structure break escalates to the parent TF above
```

### Connection to zone tracking

The breaker block from this section (polarity-flip mechanic) is the **same physical zone** as the "D LH reversal zone" in trade targeting. They are not separate concepts — on the chart, they occupy the same rectangle at the same price level.

| Zone tracking concept | = | Breaker zone concept |
|---|---|---|
| D LH reversal zone (ride-to target) | = | Breaker block from eBOS down |
| D HL reversal zone (ride-to target) | = | Breaker block from eBOS up |
| Exit longs at D LH zone | = | Price retesting the breaker from below |
| Exit shorts at D HL zone | = | Price retesting the breaker from above |

### Breaker expiry conditions

A breaker zone is removed from the chart **only** when:

1. **Retested** — price body-closes inside the zone (the retest is the mechanical event)
2. **Overridden** — a new external structural event at the same or higher TF creates a new breaker that supersedes it

A breaker zone is **never** removed by:
- Count filtering (display limits)
- Time decay or bar limits
- Lower TF events

### Chart overlay behavior

- Breaker zones are **exempt from per-level count limits** (`structureZoneCounts`)
- They always render with the breaker style (diagonal stripe pattern) regardless of count settings
- When count = 0 for a level (hide all), breakers at that level still appear

### Evidence

GBPUSD H4 screenshots (2026-03-26) in `screenshots/structure/breaker_persistence_*.png` showing the complete sequence: eBOS → breaker created → internal correction → TL break → target = breaker zone.

---

## 8. Key terminology mapping

| SMC reference term | Flint/Spring Leaf equivalent | Notes |
|---|---|---|
| Order block (OB) | Supply/demand zone | Same thing — HA color flip creates the zone |
| Internal swing | Current TF zone chain swing | No lookback needed |
| External swing | Parent TF zone boundary | Cross-TF relationship |
| iBOS | Internal BOS — HH/LL zone break on current TF | Chain count +1 |
| eBOS / BoS+ | External BOS — HH/LL zone break on parent TF | Major structural event |
| iCHoCH | Internal CHoCH — LH/HL zone break on current TF | Sub-wave reversal |
| eCHoCH / CHoCH+ | External CHoCH — LH/HL zone break on parent TF | Macro bias change |
| Liquidity sweep | Wick-only break (no body close) | Not a valid structure break |
| Displacement | Strong body close with large candle, minimal overlap | Validates break quality |
| Zone chain count | Unbroken zones from last parent TF zone | 1-5 impulse, 6 boundary, 7-8 correction |
| AMD cycle | Accumulation → Manipulation → Distribution | BOS following a liquidity sweep = highest quality |
