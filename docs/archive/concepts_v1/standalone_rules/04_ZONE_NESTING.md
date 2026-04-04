# Rule 4 — Zone Nesting (Child Inside Parent)

> **A child zone inside a parent zone is a signal.**
> Same direction = continuation. Opposing direction = terminal.

---

## The Containment Check

```
Child zone is nested IF:
  child.top ≤ parent.top  AND  child.bot ≥ parent.bot
```

Both edges must be inside. Partial overlap doesn't count.

---

## What Nesting Means

| Child | Inside Parent | Direction Match | Signal |
|-------|--------------|----------------|--------|
| H1 supply | H4 supply | Same (both bearish) | Stair-step continuation — trend intact |
| H1 demand | H4 demand | Same (both bullish) | Stair-step continuation — trend intact |
| H1 supply | H4 demand | **Opposing** | **Terminal — this H1 zone WILL be broken** |
| H1 demand | H4 supply | **Opposing** | **Terminal — this H1 zone WILL be broken** |
| M15 demand | H1 demand | Same | Entry refinement — buy limit candidate |
| M15 supply | H1 supply | Same | Entry refinement — sell limit candidate |
| M5 inside M15 inside H1 | Triple nest | Same | **Highest conviction entry** |

---

## The Opposing Nesting Rule (Most Important)

```
H1 zone OPPOSING the H4 zone it sits inside = WILL be broken
```

**Why:** The H4 zone represents the larger force. The H1 zone inside it going the other way is a correction that cannot hold. The H4 absorbs the pressure.

**Practical:**
- H1 supply #8 inside H4 demand → this H1 supply will break upward → reversal
- H1 demand #8 inside H4 supply → this H1 demand will break downward → reversal

---

## What to Look For on Chart

**Two panels needed:**

1. **Parent TF panel:** Identify the active parent zone (H4 supply or H4 demand)
2. **Child TF panel:** Watch for child zones forming INSIDE that parent zone

**Check:**
- Same direction? → Continuation, trade with it
- Opposing direction? → Terminal signal, prepare for reversal
- Triple nested (M5 @ M15 @ H1)? → Execute entry

---

## Skip Filter

**IF parent zone overlaps an opposing zone → weak signal, skip.**

The parent zone must be clean — no overlapping zone on the other side eating into it.
