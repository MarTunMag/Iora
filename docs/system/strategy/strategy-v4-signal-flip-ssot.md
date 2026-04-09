# Strategy v4 — M5@M15 Signal-Flip — Single Source of Truth

> **Version:** 4.0.0
> **Date:** 2026-04-09
> **Status:** VALIDATED — Production candidate
> **Evidence:** 32,197 trades, 82.5% WR, PF 36.92 on GBPUSD (Jul 2024 – Apr 2026)

---

## 1. Strategy Summary

**One sentence:** Enter at every M5 zone fire inside M15 context, exit when the opposite M5 zone fires, position is always open and flipping direction.

**The edge:** M5 HA run-transitions are structural direction signals. When HA switches color on M5, institutional order flow has shifted. The zone created at the transition point captures this shift. 82.5% of the time, the next flip is in profit.

---

## 2. The Complete Mechanical Rules

### Rule 1: Timeframe Hierarchy

```
D1/W1  = Macro bias (not used for entry/exit — for context only)
H4     = External structure (HH/HL or LH/LL sequence)
H1     = Period levels (previous H1 Hi/Lo = structural boundaries)
M15    = Context zones (M5 entry must be INSIDE an M15 zone)
M5     = Signal zones (HA run-transition = the trade signal)
M1     = Not used (too noisy for signal-flip — validated in sweep)
```

### Rule 2: Entry Signal

**A trade entry occurs when:**
1. An M5 zone fires (HA run-transition on M5 timeframe)
2. The M5 zone is inside or overlapping an M15 zone of the SAME direction
3. No existing position in the same direction already open

**Entry price:** Market order at the M5 zone edge
- Long: zone_bottom + 0.10 × ATR (limit buffer inside zone)
- Short: zone_top - 0.10 × ATR

**Direction:**
- M5 DEMAND zone fires (red→blue HA transition) → LONG
- M5 SUPPLY zone fires (blue→red HA transition) → SHORT

### Rule 3: Exit Signal (Signal-Flip)

**A trade exit occurs when:**
1. An M5 zone fires in the OPPOSITE direction to the open position
2. The exit IS simultaneously the next entry (position flips)

**Exit price:** Market close at the new zone's edge price

**There is NO fixed SL. There is NO fixed TP.** The structural reversal is the exit.

### Rule 4: Safety SL (Crash Protection Only)

A safety SL is placed on every position for infrastructure protection:
- Long: zone_bottom - 0.15 × ATR
- Short: zone_top + 0.15 × ATR

**This is NOT a trade exit mechanism.** It exists solely for:
- System crash recovery
- Broker disconnect protection
- Weekend gap protection

**Expected safety SL hit rate: < 1-2% of all exits.** If higher, the safety SL is too tight.

### Rule 5: Position State

The position is **ALWAYS OPEN** once the first signal fires:
- System starts FLAT (no position)
- First M5 zone fire → OPEN position in that direction
- Every subsequent opposite M5 zone fire → FLIP (close + re-open opposite)
- Position is never intentionally closed to go flat (unless windowed mode active)

### Rule 6: Spread Handling

- Spread is baked into the entry price (buy at ask, sell at bid)
- Spread is paid ONCE per flip (on the close/re-open)
- At 1.5 pip spread and 5.5 pip avg flip: spread is 27% of the average move
- This is sustainable because 82.5% of flips are winners

### Rule 7: No SL Floor

**`min_sl_spread_mult = 0.0` and `min_sl_pips = 0.0` for all signal-flip configs.**

The zone boundary IS the structural level. Artificial SL floors distort the data and mask the real edge. The signal-flip exit mechanism makes SL floors irrelevant anyway — the exit is structural, not a fixed distance.

---

## 3. What Does NOT Matter (Validated Negative)

These filters were tested and shown to have NO effect on signal-flip:

| Filter | Result | Why |
|---|---|---|
| CHoCH conviction (strong/weak) | No effect | The zone IS the signal — conviction of the BOS/CHoCH that created it doesn't add |
| Momentum consumption | No effect | Binary at M5 resolution (child TFs flip together) |
| TL break lookback | No effect | Sticky flag already captures it |
| Candle FVG at entry | Slightly negative | Candle-level gaps don't predict zone quality |
| Breaker zone filter | No effect | Nearly all zones are near breakers (too common) |
| Cascade phase (on raw flip) | No effect on flip count | Filters only gate first entry, not subsequent flips |

---

## 4. Enhancement Dimensions (Being Tested)

These are improvements to the baseline, not requirements:

### 4.1 Active-Window Mode (Layer 2.5)

Instead of flipping always, only flip during structural windows:
- **ON:** M15 correction TL broke + M15 in HL/LH mode
- **OFF:** M15 opposite TL breaks or H1 zone breaks

Expected: flip count drops from ~51/day to ~10-20/day, WR stays same or improves.

### 4.2 Structural Sequence Filters

Only start flipping after a specific sequence:
1. HTF level break (H4 Lo X or DY Lo X) → liquidity sweep done
2. H1 demand/supply zone created → institutional level established
3. M15 trendline break → internal correction over
4. M15 in HL/LH mode → internal trend confirmed

### 4.3 Divergence Confirmation

Only enter/flip when M15 divergence (DIV+ for longs, DIV- for shorts) fired at nearby pivot. Expected: higher per-flip quality, fewer flips.

---

## 5. The Numbers

### Baseline (Raw Signal-Flip, No Filters)

| Metric | GBPUSD |
|---|---|
| Trades | 32,197 |
| Win Rate | 82.5% |
| Profit Factor | 36.92 |
| Avg Flip | 5.5 pips |
| Gross Net Pips | ~166,374 |
| Flips/Day | ~51 |
| Data Period | Jul 2024 – Apr 2026 (1.7yr) |

### Comparison Against v3 (Current Production)

| | v3 Limit/Partial | v4 Signal-Flip |
|---|---|---|
| Win Rate | 52.6% | **82.5%** |
| Profit Factor | 3.28 | **36.92** |
| Validation Trades | 6,493 | **32,197** |
| Statistical Confidence | Proven | **5x more trades** |
| Exit Mechanism | Fixed SL/TP + partial | Structural flip |

### Resolution Comparison (Why M5@M15, Not M1@M5)

| TF Pair | WR | PF | Avg Flip | Flips/Day | Net After Spread | Verdict |
|---|---|---|---|---|---|---|
| M1@M5 fixed SL/TP | 34.3% | 0.81 | - | - | -2,969 pip | DEAD |
| M1@M5 signal-flip | 56.1% | 5.24 | 2.1 pip | ~51 | Negative | Spread kills it |
| **M5@M15 signal-flip** | **82.5%** | **36.92** | **5.5 pip** | **~51** | **+166K pip** | **THE ONE** |

---

## 6. Production Config

```json
{
  "strategy": {
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
    "limit_buffer_atr": 0.10,
    "min_sl_spread_mult": 0.0,
    "min_sl_pips": 0.0
  },
  "risk": {
    "risk_per_trade_pct": 0.75,
    "max_concurrent_per_symbol": 1,
    "max_daily_loss_pct": 15.0
  },
  "execution": {
    "platform": "MT5",
    "broker": "ICMarkets",
    "account_type": "ECN Raw Spread",
    "max_slippage_pips": 1.0,
    "max_spread_pct": 0.5,
    "retry_on_requote": true,
    "max_retries": 3
  }
}
```

---

## 7. Deployment Path

1. ✅ Baseline validated (82.5% WR, PF 36.92, 32K trades)
2. 🔄 Active-window enhancement sweep (Iora build chat)
3. 🔄 JoMa v4 implementation (JoMa build chat)
4. ⬜ Cross-symbol validation (USDJPY, XAUUSD, BTCUSD, USTEC)
5. ⬜ 2-week demo run on GBPUSD
6. ⬜ Live deployment

---

## 8. Visual Reference

The JoMa TradingView indicators show exactly what the Python engine detects:

| Indicator | What It Shows |
|---|---|
| **joma_zones_levels.pine** | M1/M5/M15 zones + HTF period Hi/Lo with break markers (X) |
| **joma_pivots_trendlines.pine** | Multi-TF pivot HL classification + trendlines + divergence |
| **joma_structural_fvg.pine** | Gap between HTF pivot and LTF swing (structural FVG) |

These 3 indicators on a TradingView M1/M5 chart = the complete visual representation of what the v4 engine executes mechanically.

---

## 9. Document Index

| Document | Purpose |
|---|---|
| **This file** | SSOT — the complete strategy definition |
| `m5m15-signal-flip-baseline-results.md` | Cemented baseline results with evidence |
| `mechanical-ruleset-validated.md` | Proven rules (Rules 1-13) — v3 system |
| `mechanical-cascade-strategy.md` | Cascade strategy with phase definitions |
| `sweep-analysis-sop.md` | How to analyze any sweep consistently |
| `specs/2026-04-09-m1m5-mechanical-signal-flip-spec.md` | Full technical spec with structural concepts |
| `specs/2026-04-09-build-prompt-m1m5-signal-flip.md` | Build prompt for implementation chats |
| `specs/2026-04-09-joma-signal-flip-upgrade-prompt.md` | JoMa production upgrade prompt |
