# Rule 7 — Macro Bias (Directional Confirmation)

> **M5 TL break + at parent zone = bias confirmed.**
> Everything else follows from this.

---

## The Rule

### Bearish Confirmation (flip to SHORT)

```
ALL must be true:
  ☐  M5 bullish TL broken (ascending support failed)
  ☐  (Optional: M1 bullish TL also broken)
  ☐  Price inside H4 supply OR D supply zone
  ☐  terminal_exhaustion_bull is NOT active
→  macro_bias = BEARISH (-1)
```

### Bullish Confirmation (flip to LONG)

```
ALL must be true:
  ☐  M5 bearish TL broken (descending resistance failed)
  ☐  (Optional: M1 bearish TL also broken)
  ☐  Price inside H4 demand OR D demand zone
  ☐  terminal_exhaustion_bear is NOT active
→  macro_bias = BULLISH (+1)
```

---

## The Terminal Gate

**Critical protection rule:**

```
Don't flip BULLISH when terminal_exhaustion_bear is active
  → (H4 demand below D LL = bounces here are temporary)

Don't flip BEARISH when terminal_exhaustion_bull is active
  → (H4 supply above D HH = dips here are temporary)
```

This prevents false reversals at terminal zones where the correction hasn't completed.

---

## What Changes When Bias Flips

| macro_bias | H1 Supply zones | H1 Demand zones | Meaning |
|-----------|----------------|----------------|---------|
| +1 (Bull) | Hidden (will break) | Shown in blue | Long context |
| -1 (Bear) | Shown in red | Hidden (will break) | Short context |
| 0 (Neutral) | Pink | Green | No direction yet |

**D and W zones are NEVER hidden** — macro targets always visible.

---

## Once Set, It Stays

Bias persists until the **opposite** confirmation fires. No timeout, no decay.

---

## What to Look For on Chart

**M5 panel + parent zone panel:**

1. Has M5 TL broken? (check both bullish and bearish TL)
2. Is price currently inside an H4 or D zone? (check H4/D panel)
3. Is terminal exhaustion blocking the flip? (check dashboard)

**When M5 TL breaks at a parent zone with no terminal block → bias flips → everything follows.**

---

## Sell/Buy Limit on Confirmation

When bias confirms, a limit order level is set:

```
Bear confirmed → SHORT LIMIT at broken M5 demand top
                  SL: M1 supply top + spread buffer

Bull confirmed → LONG LIMIT at broken M5 supply bottom
                  SL: M1 demand bot - spread buffer
```

Dashed line extends right. Clears on bias flip.
