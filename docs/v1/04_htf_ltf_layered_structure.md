# 04 — HTF/LTF Layered Structure: Magnets, Push Zones & Entry Areas

> Concept document — builds on:
> - `C:\Iora\docs\system\01_market_structure.md` (BOS/CHoCH detection)
> - `C:\Iora\docs\system\02_supply_demand_zones.md` (zone creation/classification)
> - `C:\Iora\docs\system\03_breaker_mitigation.md` (breaker/mitigation blocks)
> - `C:\Iora\docs\concepts\01_zone_classification.md` (HH/LH/HL/LL rules)
> - `C:\Iora\docs\concepts\02_early_confirmation_cascade.md` (CHoCH propagation)
> - `C:\Iora\docs\concepts\INTERNAL_EXTERNAL_STRUCTURE_SPEC.md` (TF cascade)
>
> Visual companion: `04_htf_ltf_layered_structure.html` (self-contained with embedded images)

---

## Purpose

This document defines the complete mechanical framework for how timeframes interact to produce tradeable setups. It answers five questions:

1. **Which zones are magnets** (pulling price toward them) vs **which zones are push zones** (driving price away)
2. **How to read the structural state across all TFs simultaneously**
3. **Where the reversal areas are** (terminal exhaustion + breaker targets)
4. **The precise entry mechanics** (which LTF CHoCH at which HTF zone)
5. **Exit + re-entry logic** (when a leg ends, where the next entry forms)

Every decision maps to a specific zone event at a specific TF level. No discretion.

---

## 1. Zone Roles — Push vs Magnet vs Entry

Every active zone plays exactly one role at any moment. The role is NOT intrinsic — it is determined by the zone's position relative to the current structural bias at its own TF and above.

### Three Zone Roles

| Role | Definition | Position |
|------|-----------|----------|
| **Push** | Drives price away from it. The zone that just fired a BOS event. | Behind price in the direction of movement |
| **Magnet** | Pulls price toward it. An unbroken zone ahead of price in the push direction. | Ahead of price in the push direction |
| **Entry Area** | Where push and magnet overlap at different TF levels, confirmed by LTF CHoCH. | Intersection of HTF push + meso magnet + LTF trigger |

### Role Assignment Rules

| Zone Position | Relative to Bias | Role |
|--------------|------------------|------|
| Behind price, caused last BOS | With-trend | **Push** |
| Ahead of price, unbroken | Against-trend | **Magnet** |
| Ahead of price, beyond last broken HTF level | Terminal counter-zone | **Magnet (terminal)** |
| Broken zone, polarity flipped | Breaker — new direction target | **Magnet (breaker)** |
| HTF zone where LTF CHoCH fires | Nested confirmation | **Entry Area** |

### Key Rule

A zone can flip from magnet to push zone when a BOS event fires through it. The H4 demand that was a magnet (target) becomes a push zone the moment H4 BOS fires through it and creates a new leg.

---

## 2. The TF Cascade — How Each Layer Controls the Next

### The Three Layers

```
MACRO:  D bias + H4 zone count       → direction + exhaustion clock
MESO:   H1 impulse/correction phase  → leg identification (THE MISSING LAYER)
MICRO:  M15 → M5 → M1 CHoCH         → entry trigger
```

**Skipping the meso layer (H1) and going from D bias directly to M1 triggers is the diagnosed root cause of too many false signals.**

### Layer 1 — D Zones Set the Magnets for H4

When D bias is bearish:
- **Push**: Last D supply zone (caused D bearish BOS). Above price, driving everything down.
- **Primary magnet**: Nearest unbroken D demand zone below price.
- **Terminal magnet**: H4 counter-zone — H4 demand sitting below a broken D LL.

When D bias is bullish:
- **Push**: Last D demand zone (caused D bullish BOS). Below price, driving everything up.
- **Primary magnet**: Nearest unbroken D supply zone above price.
- **Terminal magnet**: H4 counter-zone — H4 supply sitting above a broken D HH.

### Layer 2 — H4 Zones Push H1 Legs

Within D context, each H4 BOS pushes a new H1 leg. The H1 zones inherit directional context but their role depends on position:

| H1 Zone Position | H4 Zone Count | Role | What Happens |
|-----------------|---------------|------|-------------|
| H1 demand, mid-impulse | H4 zones 1–5 | Correction magnet | Price touches, H1 HL fires, push resumes |
| H1 demand, late impulse | H4 zones 6–7 | Exhaustion magnet | Price touches, bounce weaker, nearing terminal |
| H1 demand at H4 counter-zone | H4 zone 8 + counter-zone | Terminal magnet | H1 HL fires = FLIP preparation |
| H1 supply (correction peak) | H1 LH at H4 push zone | Entry area | M15→M5→M1 CHoCH = with-trend entry |

### Layer 3 — H1 Legs Create Entry Areas

Entry areas exist only where a push zone and a magnet zone overlap at different TF levels:

```
D bearish push  →  sets H4 magnet below
  H4 bearish BOS  →  pushes H1 impulse leg down
    H1 impulse completes  →  H1 correction leg up begins
      H1 LH forms at / near H4 push supply  →  THIS IS THE ENTRY AREA
        M15 LH inside H1 supply
          M5 LH inside M15
            M1 CHoCH (LH) = ENTRY TRIGGER
```

---

## 3. Multi-TF State Machine

At any moment, the mechanical state is a tuple:

| Layer | State Variables | Determines |
|-------|----------------|-----------|
| **D** | Bias (bull/bear/neutral) · Last event (HH/HL/LH/LL) · Push→magnet distance | Overall direction |
| **H4** | Bias · Zone count · Counter-zone proximity · Last event | Exhaustion clock, terminal detection |
| **H1** | Phase (impulse/correction) · Zone count · Position vs H4 zones | Leg phase — the meso layer |
| **M15/M5** | Sub-wave position · CHoCH direction | Timing, H1 leg completion |
| **M1** | CHoCH event at HTF zone | Entry trigger — only when all above confirm |

### Context Mode Mapping

| Mode | State | Action |
|------|-------|--------|
| **RIDE** (with-trend) | D + H4 aligned · H4 zones 1–5 · H1 correction completing | Enter at H1 LH/HL zone when M1 CHoCH fires |
| **FLIP** (reversal) | H4 zone 8 + counter-zone · H1 CHoCH opposing direction | Enter at H1 demand/supply after H1 BOS confirms |
| **SCALP** (hedge) | H1 BOS fires (sweep) · Retracement to H1 zone | M1 CHoCH at H1 zone = scalp entry |
| **SKIP** (no trade) | Layers not aligned · H4 zones 7–8 without counter-zone · H1 phase unclear | Wait |

### State Examples

**RIDE Short** — D bearish + H4 impulse (zones 1–5) + H1 impulse down:
- Push: H4 supply above + H1 LH supply behind price
- Magnet: Next H1 demand below
- Entry: M1 LH at H1 LH supply (after M15→M5 LH confirm)

**Nearing Exhaustion** — D bearish + H4 zones 6–7 + H1 correction up:
- Push: H4 supply above (weakening)
- Magnet: H1 supply above (correction target)
- Entry: Wait for H1 LH, then M1 LH — expect smaller move

**FLIP Preparation** — D bearish + H4 zone 8 at counter-zone + H1 HL fires:
- Push: Dying — H1 HL signals old push exhausting
- Magnet: Breaker from previous H4 push = new upside target
- Entry: M1 HL at H1 demand (after H1 HH BOS confirms reversal)

---

## 4. Reversal Areas — Terminal Exhaustion

Reversal areas are defined by three converging mechanical signals. All three must be present.

### Signal 1: Zone Count Terminal

H1 impulse produced **5+ unbroken zones** in push direction + correction sequence of **up to 3 zones**. Zone 8 = terminal.

### Signal 2: H4 Counter-Zone Reached

Price is inside the H4 demand (bearish impulse) or H4 supply (bullish impulse) that sits **beyond the last broken D structural level**.

### Signal 3: LTF Structural Shift

H1 CHoCH fires in opposing direction. Followed by H1 BOS confirming new direction. Breaker from previous push becomes target.

### Terminal Bottom Sequence

```
H1 zone count hits terminal (5 impulse + 3 correction = zone 8)
  → Price enters H4 counter-zone (H4 demand below broken D LL)
    → H1 HL fires — first CHoCH — correction starting
      → H1 HH fires — BOS — reversal confirmed
        → Breaker from H4 supply = upside magnet
          → Persisted H4 zone = intermediate target
            → M15 HL inside H1 demand → M5 HL → M1 HL = ENTRY
```

### Terminal Top Sequence

```
H1 zone count hits terminal (5 impulse + 3 correction = zone 8)
  → Price enters H4 counter-zone (H4 supply above broken D HH)
    → H1 LH fires — first CHoCH — correction starting
      → H1 LL fires — BOS — reversal confirmed
        → Breaker from H4 demand = downside magnet
          → Persisted H4 zone = intermediate target
            → M15 LH inside H1 supply → M5 LH → M1 LH = ENTRY
```

---

## 5. Entry Mechanics — The Full Cascade

Every entry follows the same three-layer template. No exceptions.

```
1. MACRO confirms direction    →  D bias + H4 zone count = context mode
2. MESO confirms leg phase     →  H1 impulse/correction + position vs H4 zones
3. MICRO confirms timing       →  M15 CHoCH → M5 → M1 CHoCH = trigger
```

### RIDE Short Entry (With-Trend)

**Conditions:** D bearish · H4 zones 1–5 · H1 correction completing

| Step | Event | Confirms |
|------|-------|----------|
| 1 | H1 correction up completes (H1 HL → H1 LH forms) | H1 LH supply = correction peak |
| 2 | H1 LH supply overlaps with / near H4 push supply | Meso: correction into push zone |
| 3 | M15 makes LH inside H1 supply | Sub-wave turning bearish |
| 4 | M5 makes LH inside last M15 demand | Nested confirmation tightening |
| 5 | M1 CHoCH (LH) inside last M5 demand | **ENTRY** |

- **Stop**: Above H1 LH supply top
- **Target**: Next H1 demand below (correction magnet)

### FLIP Long Entry (Terminal Reversal)

**Conditions:** H4 zone 8 at counter-zone · H1 CHoCH + BOS confirmed

| Step | Event | Confirms |
|------|-------|----------|
| 1 | H1 HL fires (CHoCH) at H4 counter-zone | Terminal exhaustion signal |
| 2 | H1 HH fires (BOS) — reversal confirmed | New direction validated |
| 3 | M15 HL inside H1 demand that just formed | Sub-wave confirms pullback |
| 4 | M5 HL inside last M15 supply | Nested confirmation |
| 5 | M1 CHoCH (HL) inside last M5 supply | **ENTRY** |

- **Stop**: Below H1 demand bottom (inside H4 counter-zone)
- **Target**: Breaker block from previous H4 push supply

### SCALP Hedge Entry (Counter-Trend)

**Conditions:** H1 BOS fires (sweep) · Price retraces to H1 zone

| Step | Event | Confirms |
|------|-------|----------|
| 1 | H1 BOS fires — impulse leg completes | Liquidity taken, impulse exhausted |
| 2 | Price retraces to H1 zone (from BOS leg) | Correction reaching institutional zone |
| 3 | M1 CHoCH at H1 zone | **SCALP ENTRY** |

- **Exit**: Next H1 zone in correction direction

### Early Confirmation Cascade

| HTF Event | Confirmed Early By | Earliest Tradeable Signal |
|-----------|-------------------|--------------------------|
| H4 HH | H1 HH (supply top > prev H4 supply top) | M1 HL after H1 first HL |
| H4 LL | H1 LL (demand bot < prev H4 demand bot) | M1 LH after H1 first LH |
| H4 HL | H1 HL sequence inside H4 demand | M15 HL inside H1 demand @ H4 demand |
| H4 LH | H1 LH sequence inside H4 supply | M15 LH inside H1 supply @ H4 supply |
| D LH | H4 HH capped below D supply top | H1 CHoCH (first LH after H4 HH) |
| D HL | H4 LL floored above D demand bot | H1 CHoCH (first HL after H4 LL) |
| H1 leg complete | M15 CHoCH (opposing inside H1 zone) | M1 CHoCH after M5 CHoCH inside M15 |

---

## 6. Exit + Re-Entry — Leg Transitions

Exit and re-entry are two halves of the same cycle. Every exit creates the setup for the next entry.

### Exit Signals

| Signal | Meaning | Action |
|--------|---------|--------|
| M15 correction TL break inside H1 leg | Sub-wave completing | Tighten stop or partial exit |
| M15 CHoCH opposing direction inside H1 zone | H1 sub-wave done | Exit at M15 signal |
| Body close inside breaker zone | Target reached | Full exit — magnet consumed |
| H1 zone count 5 + correction TL break | Impulse exhausting | Exit, wait for correction |

### Re-Entry Signals

| Signal | Where | Entry |
|--------|-------|-------|
| H1 correction completes (LH or HL) | New H1 supply/demand zone | M1 CHoCH at new H1 LH/HL zone |
| Breaker from completed leg forms | Broken zone, polarity flipped | M1 CHoCH at breaker |
| H1 BOS in push direction | After correction ends | Already positioned or enter on pullback |

### The Full Cycle

```
H1 BOS (sweep) → ride impulse → target: next H1 magnet
  → H1 zone reached → SCALP hedge (M1 CHoCH at H1 zone)
    → H1 correction plays out → H1 LH/HL forms
      → EXIT scalp at correction extreme
        → M1 CHoCH at new H1 LH/HL = RE-ENTRY in push direction
          → next H1 BOS → REPEAT
            → until zone count terminal + H4 counter-zone → FLIP
```

### The Unified Sweep-Scalp-Growth Chain

H1 BOS (sweep) → scalp hedge retracement to H1 zone → M1 CHoCH at H1 zone = **one mechanical cycle**.

Zone count gates the cycle:
- **Zones 1–5**: Growth entries allowed
- **Zone 6**: Last entry
- **Zones 7–8**: Hold-only
- **Zone 8 inside H4 counter-zone**: Terminal → FLIP preparation

---

## 7. Breaker & Mitigation Roles in the Framework

### Breaker Block — Strong Magnet

Formation: External HH/LL break → broken zone flips polarity.

| Original | Broken By | Becomes |
|----------|-----------|---------|
| Supply | Bullish eBOS | Bullish breaker (support on retest) |
| Demand | Bearish eBOS | Bearish breaker (resistance on retest) |

**Framework role**: Breakers are **primary magnets** for the new directional move. FLIP reversal trades target the breaker from the previous push. Breakers persist until retested — removing early loses both exit target and re-entry zone.

**Confidence weight**: ~2× vs mitigation blocks.

### Mitigation Block — Moderate Magnet

Formation: Failure swing — reversal without full structural break, no liquidity grab.

**Framework role**: Mitigation blocks are **secondary reference zones**. They provide one-retest reactions but don't persist like breakers. Used as intermediate targets, not primary magnets.

### Distinction Rule

- **Breaker**: Zone broken by move that swept liquidity (BSL/SSL) AND produced full structural reversal → strong, persists
- **Mitigation**: Zone broken by failure swing, no liquidity grab → moderate, one retest

### Persisted H4 Zones (Pre-eBOS Context)

On H4 eBOS, captures last unbroken H4 zone of opposite type. Serves as **intermediate magnet** — reversal trade's first target before reaching the breaker.

| Event | Persisted Zone | Role |
|-------|---------------|------|
| Bearish H4 eBOS | Last unbroken H4 supply | Rally target / resistance |
| Bullish H4 eBOS | Last unbroken H4 demand | Pullback target / support |

---

## 8. Trendline Cascade Confirmation

The structure trendlines indicator (`iora_structure_trendlines.pine`) provides visual confirmation of the push/magnet framework:

### Impulse Trendline (trend continuation)

Connects LH supply tops (descending in bearish) or HL demand bots (ascending in bullish). Built from CHoCH events one level below. **Break = correction strong enough to threaten structure.**

### Correction Trendline (pullback within trend)

Connects HL demand bots (ascending correction in bearish) or LH supply tops (descending correction in bullish). **Break = correction failed, trend impulse resumes.**

### How Trendlines Map to Framework

| TL Break | Meaning | Framework Implication |
|----------|---------|---------------------|
| Internal TL break | Minor signal, pullback ending | H1 sub-wave transition |
| External TL break | Structural shift | iBOS/eBOS territory — possible context mode change |
| Correction TL break | Correction exhausted, push resumes | Re-entry area forming |
| Impulse TL break | Push losing momentum | Exit signal, correction starting |

---

## Universal Pattern (Summary)

```
HTF structure shifts (detected via zone comparison)
  → LTF CHoCH confirms it early (nested inside relevant HTF zone)
    → One-level-lower CHoCH provides precision entry
      → M1 CHoCH is always the final execution trigger
```

Every entry, exit, and reversal maps to a specific zone event at a specific TF level. No discretion.

---

## File References

### Prerequisite System Specs
- `C:\Iora\docs\system\01_market_structure.md`
- `C:\Iora\docs\system\02_supply_demand_zones.md`
- `C:\Iora\docs\system\03_breaker_mitigation.md`

### Prerequisite Concept Docs
- `C:\Iora\docs\concepts\01_zone_classification.md`
- `C:\Iora\docs\concepts\02_early_confirmation_cascade.md`
- `C:\Iora\docs\concepts\INTERNAL_EXTERNAL_STRUCTURE_SPEC.md`

### This Document
- `C:\Iora\docs\concepts\04_htf_ltf_layered_structure.md` (this file — for Claude)
- `C:\Iora\docs\concepts\04_htf_ltf_layered_structure.html` (visual companion with images)

### Pine Script Indicators
- `iora_structure.pine` — Market structure + breaker detection
- `iora_zones.pine` — Supply/demand zone creation + classification
- `iora_structure_trendlines.pine` — Zone-confirmed trendlines
- `iora_trendlines.pine` — Legacy per-candle trendlines
