# Spread Reality Analysis — The Truth About Live Viability

> **Date:** 2026-04-07
> **Status:** CRITICAL — changes the production config. M5@M15 is dead at real spread. H1@H4 is the production pair.
> **Sweep:** 125 configs on GBPUSD with spread 0/0.5/1.0/1.5/2.0/3.0 pips, min_sl 0/5/10, sl_buffer 0.15/0.25/0.50/0.75/1.0, limit_edge bottom/top

---

## 1. The Verdict

**The SQN 44 on M5@M15 was a fantasy.** At realistic FX spread (1.5 pips), M5@M15 limit is DEAD (SQN -11.72). The 1.2-pip SL is destroyed by the 1.5-pip spread.

**H1@H4 is the real production pair.** SQN 21.95 at 1.5-pip spread, PF 2.25. The 5+ pip SL on H4 zones survives spread comfortably.

---

## 2. Full Results by TF Pair

### M5@M15 — DEAD at realistic spread

| Config | Spread | SQN | PF | WR | Trades | Verdict |
|--------|:------:|:---:|:--:|:--:|:------:|---------|
| Bottom edge, TTL=0 | 0 | 44.61 | 3.28 | 52.6% | 6,493 | Fantasy |
| Bottom edge, TTL=0 | 0.5p | 23.87 | 1.98 | 52.6% | 6,493 | Half edge gone |
| Bottom edge, TTL=0 | 1.0p | 5.39 | 1.27 | 52.6% | 6,493 | Barely alive |
| Bottom edge, TTL=0 | **1.5p** | **-11.72** | **0.83** | **52.6%** | **6,493** | **DEAD** |
| Bottom + min_sl=5p | 1.5p | 6.30 | 1.25 | — | — | Thin — barely profitable |
| Bottom + sl_buf=1.0 | 1.5p | 5.43 | 1.24 | — | — | Similar to min_sl=5 |
| Top edge, any spread | — | -2.88 | 0.85 | 26.5% | — | Dead — WR too low |

**Why M5@M15 dies:** The SL distance (zone_bottom to entry at zone_bottom + 0.1*ATR) is only ~1.2 pips. The spread (1.5 pips) is LARGER than the SL. Every fill starts at a loss exceeding the SL distance. The math is physically impossible.

### M15@H1 — Survivable with min_sl floor

| Config | Spread | SQN | PF | Verdict |
|--------|:------:|:---:|:--:|---------|
| Bottom edge | 0 | 33.13 | 3.11 | Good without spread |
| Bottom edge | 1.5p | 8.69 | 1.48 | Survivable |
| Bottom + min_sl=5p | 1.5p | **14.46** | **1.67** | **Best middle-ground** |
| Top edge | any | ~0 | ~0.88 | Dead |

**M15@H1 with min_sl=5p and spread=1.5p is viable.** SQN 14.46, PF 1.67. The min_sl floor widens the SL enough to survive spread while maintaining the zone-edge entry precision.

### H1@H4 — THE PRODUCTION PAIR

| Config | Spread | SQN | PF | Trades | Verdict |
|--------|:------:|:---:|:--:|:------:|---------|
| Bottom edge | 0 | 31.93 | 3.21 | — | Excellent |
| Bottom edge | 1.5p | **21.95** | **2.25** | **3,614** | **PRODUCTION** |
| Bottom edge | 3.0p | 12.49 | 1.64 | — | Still strong at double spread |
| Top edge + partial | 1.5p | **24.14** | **2.54** | **3,747** | **Best config overall** |
| Top edge + partial | 2.0p | **23.70** | **2.51** | — | Nearly spread-immune |

**H1@H4 is bulletproof.** The SL is already 5+ pips on H4 zones, so 1.5-pip spread is only 30% of SL — manageable. Even at 3 pips spread (volatile conditions), SQN is 12.49.

---

## 3. The Surprise: H1@H4 Top Edge + Partial TP

The biggest finding: H1@H4 with top edge entry (zone top for demand, zone bottom for supply) PLUS partial TP:

| Metric | Bottom edge (no partial) | Top edge + partial |
|--------|:------------------------:|:------------------:|
| SQN (spread=1.5p) | 21.95 | **24.14** |
| PF | 2.25 | **2.54** |
| WR | ~55% | **54.6%** |
| Trades | 3,614 | **3,747** |

Top edge gets MORE fills (price only needs to touch the zone, not penetrate to the bottom). The partial TP (Unit 1 scalp lock) compensates for the wider SL by locking profit early. Combined: higher SQN, higher PF, more trades.

**And it's spread-immune:** SQN drops from 24.14 (1.5p spread) to 23.70 (2.0p spread) — barely a dent. The 8+ pip SL from zone-top entry means spread is <25% of SL.

---

## 4. Updated Production Config

### OLD (INVALID — spread kills it)
```
M5@M15 limit, zone SL, TTL=0, rr=3.0
SQN 44.61 at spread=0 → SQN -11.72 at spread=1.5p ← DEAD
```

### NEW PRODUCTION CONFIG
```
H1@H4 limit, top edge, partial TP (70%@rr3.0 + 30%@H1 zone)
TTL=0 (until zone breaks)
SQN 24.14 at spread=1.5p — SPREAD IMMUNE
PF 2.54, WR 54.6%, 3,747 trades over 16.5 years
~227 trades/year per symbol = ~4.5 trades/week
```

### SECONDARY CONFIG (faster frequency)
```
M15@H1 limit, bottom edge, min_sl=5p
TTL=0, rr=3.0, spread=1.5p
SQN 14.46, PF 1.67, 3,606 trades
```

---

## 5. What This Means For JoMa Live

The live system was running M5@M15 with sub-1-pip SL → instant SL hits from spread. The fix:

1. **Switch primary pair from M5@M15 to H1@H4** — H4 zones have 5+ pip SL that survives spread
2. **Use top edge entry with partial TP** — zone_top entry for demand, zone_bottom for supply
3. **Keep M15@H1 as secondary** with min_sl=5p floor
4. **DROP M5@M15 from live** — it doesn't work at real spread costs

The trade frequency drops from ~15/day (M5@M15) to ~1/day (H1@H4) per symbol. With 8 symbols: ~8 trades/day. Slower but profitable.

---

## 6. Lesson Learned

**ALWAYS model spread in the backtest before trusting SQN numbers.** The M5@M15 SQN 44 led us to deploy a config that was physically impossible to trade profitably. The spread test should have been run FIRST, not after live losses.

**The rule going forward:** No config goes live until it passes the spread test at `spread=1.5p` (FX) or `spread=0.5p` (indices/crypto with tighter spreads). The spread test is a GATE, not an optimization.

---

## 7. Cross-Reference

| Document | Update Needed |
|----------|---------------|
| `JoMa/configs/production.json` | Change to H1@H4, top edge, partial TP |
| `JoMa/docs/strategy/PRODUCTION_CONFIGS.md` | Update recommended config + all metrics |
| `Iora/docs/system/level4-findings-and-next-steps.md` | Add spread reality section |
