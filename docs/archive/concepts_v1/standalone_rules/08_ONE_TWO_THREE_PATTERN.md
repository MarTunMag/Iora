# Rule 8 — 1-2-3 Reversal Pattern (Compression Signal)

> **Three zones compressing = push ending.**
> Cascades through TFs — each level arms the next.

---

## The Pattern

### Bearish 1-2-3 (Rally Failing)

```
Zone 1:  Demand (HL)   — pullback support
Zone 2:  Supply (HH)   — rally high
Zone 3:  Demand (HL)   — second pullback

Signal:  Zone 3 demand top < Zone 2 supply bottom
         → The rally can't reach the last high
         → Push up is compressing = failing
```

### Bullish 1-2-3 (Push Down Failing)

```
Zone 1:  Supply (LH)   — pullback resistance
Zone 2:  Demand (LL)   — push low
Zone 3:  Supply (LH)   — second pullback

Signal:  Zone 3 supply bottom > Zone 2 demand top
         → The push can't reach the last low
         → Push down is compressing = failing
```

---

## The Cascade (Each Level Arms the Next)

```
D 1-2-3 fires (always — no gate needed)
  → arms H4
    H4 1-2-3 fires (only inside D zone)
      → arms H1
        H1 1-2-3 fires (only inside H4 zone)
          → arms M15
            M15 1-2-3 fires (only inside H1 zone)
              → arms M5
                M5 1-2-3 fires (only inside M15 zone)
                  → ENTRY TRIGGER ARMED
```

---

## Containment Rule

Each child 1-2-3 can only fire when price (close) is **inside** an active unbroken parent zone.

```
H4 1-2-3 → close must be inside D zone
H1 1-2-3 → close must be inside H4 zone
M15 1-2-3 → close must be inside H1 zone
M5 1-2-3 → close must be inside M15 zone
```

---

## Arming Resets

Each direction clears the opposite:

```
D bearish 1-2-3 fires → arms H4 bearish, CLEARS H4 bullish
```

---

## What to Look For on Chart

**Any single panel:**

1. Find three consecutive zones: corrective → structural → corrective
2. Check compression: does the third zone NOT reach the second?
3. If yes → 1-2-3 pattern detected at this TF

**Cross-panel:** Check if the parent TF also shows 1-2-3 → cascade is building.

---

## Connection to M1 CHoCH Add-On Entries

When the M5 1-2-3 cascade fires:
```
m5_cascade_bear_ready = true
  → Wait for M1 LL (proves push started)
    → Then M1 LH (CHoCH) = SHORT add-on entry
    → Entry: last_m1_sup_bot
    → SL: last_m1_sup_top + spread

m5_cascade_bull_ready = true
  → Wait for M1 HH (proves push started)
    → Then M1 HL (CHoCH) = LONG add-on entry
```
