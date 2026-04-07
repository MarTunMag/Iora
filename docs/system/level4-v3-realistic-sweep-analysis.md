# V3 Realistic Sweep Analysis — GBPUSD

> **Date:** 2026-04-06
> **Sweep version:** V3 realistic (TTL carry-forward, BE buffer, HA trailing)
> **Configs:** ~108
> **Key finding:** TTL=0 (until zone breaks) doubles Total R. HA trail and BE buffer don't help.

---

## 1. TTL Impact — The Major Finding

| M5@M15 limit rr=3.0 | TTL=1 (v2) | TTL=3 | TTL=6 | TTL=12 | TTL=0 |
|---------------------|:----------:|:-----:|:-----:|:------:|:-----:|
| Trades | 2,402 | 3,419 | 3,951 | 4,501 | **6,493** |
| Fill rate | 7.1% | ~10% | ~12% | ~13% | **19%** |
| WR | 63.7% | 57.0% | 55.7% | 54.2% | **52.6%** |
| SQN | 39.43 | 37.76 | 38.85 | 39.36 | **44.61** |
| Total R | 3,718 | 4,373 | 4,853 | 5,263 | **7,179** |
| PF | 5.10 | 3.97 | 3.79 | 3.56 | **3.28** |
| MaxDD R | 10 | 10 | 14 | 10 | **11** |

**TTL=0 wins decisively.** Nearly doubles Total R, highest SQN, manageable MaxDD.

The WR drops monotonically with longer TTL (63.7% → 52.6%) because later fills are at zones that have been touched more. But the volume increase (2,402 → 6,493) overwhelms the WR decrease. Every TTL step adds profitable trades that v2 discarded.

**TTL=0 is NOT lookahead bias.** The limit order is placed at bar N based on bar N's information. It fills whenever price reaches the zone edge — bar N, N+1, N+100. This is exactly how a real pending order works. The v2 same-bar-only approach was LESS realistic.

---

## 2. BE Buffer Impact — Marginal

| M5@M15 partial 50/50 | BE=0.0 | BE=0.1 | BE=0.25 | BE=0.5 |
|----------------------|:------:|:------:|:-------:|:------:|
| AvgR | 1.918 | ~1.90 | ~1.87 | ~1.86 |
| BE stops | 976 | 831 | 744 | ~650 |

BE buffer reduces the number of BE stops but doesn't meaningfully improve the blended outcome. The trades saved from BE stops eventually hit the original SL instead. **Not worth the complexity.**

---

## 3. HA Trail Impact — Hurts Performance

| M5@M15 partial | trail=none | trail=ha_m5 | trail=ha_m15 | trail=ha_h1 |
|----------------|:----------:|:-----------:|:------------:|:-----------:|
| AvgR | **1.918** | ~1.4 | 0.987 | 1.255 |

HA trailing REDUCES AvgR across all TF pairs. The HA reversal fires before the Unit 2 TP is reached — the trail cuts winners short. The fixed TP at the H1 opposing zone is superior to any trailing method.

**For M15@H1 and H1@H4:** Trail has zero to slightly negative effect. The HA trail SL never tightens past the BE/original exit levels before TP fires.

**Conclusion: don't use HA trailing.** The fixed partial TP (70% at rr=3, 30% at H1 zone) is the optimal exit strategy.

---

## 4. Production Config (V3)

| Parameter | V2 | V3 | Change |
|-----------|:--:|:--:|:------:|
| limit_ttl | 1 | **0** | Doubles Total R |
| breakeven_buffer | 0.0 | 0.0 | No change |
| unit2_trail | none | none | Confirmed — trail hurts |
| All other params | Same | Same | Entry, SL, TP unchanged |

**The V3 config is SIMPLER than V2 + the new dimensions.** We tested BE buffer and HA trail to check if they help — they don't. The only change is `limit_ttl=0`. One parameter change, double the returns.

---

## 5. Cross-Reference

| Document | What Changed |
|----------|-------------|
| `JoMa/configs/production.json` | Updated to v3.0.0 with limit_ttl=0 |
| `JoMa/docs/strategy/PRODUCTION_CONFIGS.md` | V3 metrics added |
| `Iora/docs/system/level4-findings-and-next-steps.md` | TTL discovery section |

---

## 6. Live Diagnosis (April 6-7) — Root Cause Found

### The Problem
31 limits placed, 4 filled, 4 SL hits, 0 TP hits = 0% WR. Balance dropped $889.97 → $788.91 (-$101).

### Root Cause
Three bugs in the live runner:

1. **Pending limits blocked new entries.** `max_concurrent=1` counted pending orders as "open positions." When a limit sat unfilled, NO new limits could be placed — even when fresher, better zones appeared. The system was stuck on stale limits.

2. **No zone-break cancellation.** When a zone was body-close broken, the pending limit at that zone's edge stayed active. It eventually filled at a zone that was already invalidated → instant SL hit.

3. **Broker-side expiry.** 19 of 31 limits "disappeared" — broker expired them. The system wasn't managing its own order lifecycle.

### Fixes Applied (V3)

1. **Pending limits don't block entries.** Only FILLED positions count toward `max_concurrent`. Pending = "maybe" → doesn't prevent new signals.

2. **Pending limit replacement.** New retest on same symbol → cancel old limit, place new one at fresher zone edge. Logged as `LIMIT_REPLACED`.

3. **Zone-break cancellation.** Every M5 bar, check if the zone behind each pending limit has been body-close broken. If yes → cancel immediately. Logged as `LIMIT_CANCELLED | zone broken`.

### Why This Wasn't Caught in Backtest
The backtest's `limit_ttl=1` (same-bar fill or discard) never had pending limits carry forward — there was nothing to get "stuck." The V3 `limit_ttl=0` (until zone breaks) requires the cancellation logic that only exists in live. The V3 sweep tested the FILL behavior correctly but didn't simulate the pending-order-management behavior that live requires.

### Lesson
Backtest parity requires not just matching entry/exit logic but also ORDER LIFECYCLE management: placement, replacement, and cancellation. The V3 sweep engine should be updated to match this behavior for full parity.
