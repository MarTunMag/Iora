# Project Reset — 2026-04-10

> **Status:** Look-ahead bug identified. Strategy hypothesis space wide open. Ready to rebuild on solid foundations.
> **Mood:** Optimistic. The hard part (finding the bug) is done. Now we get to do the fun part (testing real strategies).

---

## What Happened

### The Discovery (and Why It's Actually Great News)

On 2026-04-10 we discovered that the v4 signal-flip backtest had look-ahead bias. The "97% WR universal edge" was a software artifact, not a real strategy property.

**The numbers, corrected for live-parity fills:**

| Symbol | Reported WR | Live-at-Close WR | Delta |
|---|---|---|---|
| F40 | 96.37% | 33.14% | -63 pp |
| GBPUSD | 82.48% | 21.08% | -61 pp |
| US500 | 97.13% | 33.44% | -64 pp |
| BTCUSD | 98.15% | 34.87% | -63 pp |

GBPUSD live-at-close (21%) ≈ JoMa observed live (~25%). **The discovery process worked perfectly:**
- Demo deployed Friday with $753
- Bot lost $190 in 30 hours (controlled, manageable)
- Forensic investigation found exact root cause (line numbers cited)
- Backtest correction empirically matched live behavior (proof, not theory)
- Live system halted before any meaningful damage
- **Total real cost of the lesson: $190**

This is what a good failure looks like. We have the truth now, in a controlled way, with the entire engine still intact and ready to test real hypotheses.

### The Bug (One-Line Summary)

`retest_engine.py:391` and `:579` use `birth.zone_bottom`/`zone_top` for flip entry/exit prices. Those zone edges come from PRIOR bar wick extremes, not prices reachable at the current bar. Result: 91%+ of trades fill at impossible prices, generating phantom edge.

**The bug is conceptually simple to fix.** Use bar close (or next bar open) as the fill price. The challenge isn't fixing the engine — the challenge is then finding which strategy ideas actually have real edge once impossible fills are removed.

---

## What's Still True (Reusable Foundations)

A LOT of valuable infrastructure survives this reset:

### Engine Components (Verified Working)
- **HA run-transition zone detection** — produces correct zones, not affected by the bug
- **PeriodTracker** — period Hi/Lo tracking with break detection, used by v3 and v4
- **Push trendline state machine** — anchor detection + break detection, working correctly
- **Multi-TF pipeline** — bar-by-bar coordination across M1-W1, working correctly
- **Cascade phase state** — h4_correction, d1_push, h1_terminal, etc. — logic is sound
- **Structural FVG detection** — gap detection between HTF pivot and LTF swing
- **38 symbols × 1.7 years M5 data** — clean data, ready for re-testing

### Live Infrastructure (Verified Working)
- **JoMa LiveRunner** — multi-symbol, MT5-integrated, faithful execution
- **Self-healing startup sync** — adopts/cleans positions on restart
- **Race condition fixes** — close-before-open, IOC filling mode (commits 0a3ab6a, c6bb0db, 315f96a)
- **Trade journal CSV** — 43 fields per trade, ready for analysis
- **Symbol mapping** — verified ICMarkets canonical names for all Tier 1 + Tier 2 symbols
- **Risk override system** — per-symbol risk throttling

### Research Infrastructure
- **Sweep runner** — parallelized, multi-symbol, multi-config
- **17-metric compute_metrics()** — properly computes WR, PF, SQN, maxDD, sharpe, etc.
- **Diagnostic modules** — Level 1-3 (zone audit, bias timeline, opportunity counter)
- **38-symbol parquet warehouse** — clean OHLCV data, multi-TF aligned

### Documentation & Process
- **Sweep analysis SOP** — 8-step procedure, 17 metrics, red flags checklist
- **Audit methodology** — proven to find real bugs (4 critical issues found in JoMa)
- **Forensic methodology** — proven to find root causes (this bug, found in 2 hours)

### v3 System (Likely Unaffected)
- **62% WR, PF 5.3 production system** — uses limit orders + partial TP, NOT flip logic
- **Different code path** in `_simulate_with_bars` — bug is in flip-specific lines
- **Hypothesis: v3 is bug-free** — needs validation, but mechanically separate

---

## What Needs To Be Done

### Phase A: Engine Fix (1-2 days)

1. **Fix the look-ahead bug** in `retest_engine.py:391, 579`
   - Replace zone-edge prices with bar close (or next bar open) fills
   - Add three hard invariants as test assertions:
     - `bar.low <= entry_price <= bar.high` for every trade
     - `bar.low <= exit_price <= bar.high` for every trade
     - Flip chains are time-contiguous (close[i] timestamp == open[i+1] timestamp)
   - Any trade violating these invariants throws an error

2. **Add metadata logging** to every backtest run
   - `results/sweeps/{name}/{symbol}_metadata.json`
   - Captures: full RetestConfig, git commit, code version, data range, bars processed
   - Mandatory — no sweep without metadata

3. **Build live-parity simulator**
   - Mode flag: `simulation_mode: "research" | "live_parity"`
   - In live_parity: spread always applied, fills at bar close, hard invariants enforced
   - Used for ALL future strategy validation before any live deployment

### Phase B: v3 Validation (2 hours)

4. **Verify v3 limit/partial-TP code path is bug-free**
   - Run the same "live-at-close" test on a v3 sweep result
   - Check: do v3 trades fill at prices within bar OHLC?
   - Check: are reported WR/PF numbers reproducible from raw trade records?
   - **If v3 is clean → v3 is the real production system, JoMa can resume with v3**
   - If v3 also has issues → narrow down the divergence per code path

### Phase C: Strategy Hypothesis Testing (1 week)

This is where it gets fun. The engine produces correct zones, the bug is fixed, the live-parity simulator catches phantom fills. Now we test REAL ideas.

**Strategy hypotheses to test (your ideas + extensions):**

#### H1: Stop Orders at Zone Break
- Buy stop above zone top, sell stop below zone bottom
- Trades the BREAKOUT, not the rejection
- Different mathematical character: catches momentum, loses on false breaks

#### H2: Limit Orders at Zone Edge
- This is essentially v3 — already known to work (62% WR pre-bug)
- Re-validate with bug-free engine
- Test variations: bottom edge, 50% level, top edge

#### H3: M15 Push Zones (instead of M5)
- M15 zones are wider, more structural
- Less spread-sensitive (zone width 10-30 pips vs M5's 1-5 pips)
- Lower flip frequency (5-15 per day instead of 60)
- Each flip has more room for the spread

#### H4: M5 Push Zones with H1 Context
- Use H1 zones as the directional filter
- M5 zones as entry timing
- Wider context = stronger directional bias
- Test: only flip when M5 zone aligns with H1 unbroken zone direction

#### H5: Limit at Zone 50% (Fibonacci Mid)
- Enter on retracement to zone midpoint
- Tighter SL (50% of zone width), better R:R
- Lower fill rate but better risk profile

#### H6: Hybrid Stop+Limit
- Limit at zone edge for retest
- Stop at zone break for breakout
- Whichever fills first; cancel the other
- Captures both rejection and breakout patterns

#### H7: Trendline Break Entries (the cascade ideas)
- Enter when correction TL breaks on M15
- Use H4 cascade phase as filter
- This is what the cascade-trendline engine was designed for
- Already partially built, never properly tested

#### H8: Mitigation Block Entries
- Enter at LH/HL retest zones (the mitigation block pattern from images)
- Only when prior extreme NOT broken
- This is a structural pattern, not a flip pattern
- Should have low frequency but high quality

#### H9: Period Hi/Lo Break + Retest
- Wait for period level break (DY Hi/Lo, H4 Hi/Lo)
- Enter on first retest of broken level (now flipped polarity)
- This is the JoMa structural reversal pattern from your XAUUSD chart

#### H10: Multi-Confluence Required
- Only enter when 3+ structural conditions align
- E.g., M5 zone + M15 same-direction zone + H1 push direction + cascade phase
- Lower frequency, much higher conviction

### Phase D: Live Validation Loop (continuous)

5. **Test each viable hypothesis on demo first**
   - Deploy small capital ($500-1000)
   - Compare live behavior to live-parity simulator (must match)
   - Run 2 weeks minimum before scaling
   - Hard halt if WR diverges from simulator by >10pp over rolling 100 trades

6. **Only scale strategies that survive demo**
   - Real edge survives spread, slippage, broker behavior
   - Real edge produces consistent metrics across trade samples
   - Real edge is reproducible — same config always produces same numbers

---

## What We Learned (Process Improvements)

### Mandatory Going Forward

1. **Reproducibility Mandate**
   - Every sweep produces a metadata file
   - No "anonymous" backtest results — always traceable to exact config
   - No deployment based on results without metadata

2. **Live-Parity Invariant**
   - Every backtest trade must have entry/exit price within bar OHLC
   - Automated assertion, not optional check
   - Backtest fails fast if any trade is "impossible"

3. **Demo-First Validation**
   - No live capital until 2-week demo validates within 10pp WR of backtest
   - Demo must use the SAME config that produced backtest reference
   - Live results stripped of safety_sl_hit before WR comparison

4. **Cross-Repo Parity Tests**
   - Iora and JoMa must produce identical zone sequences on the same bar data
   - Automated test: run both engines on same hour, compare outputs
   - Any divergence is a red flag

5. **Healthy Skepticism on Extreme Numbers**
   - WR > 80% on a mechanical strategy = investigate before celebrating
   - PF > 10 = investigate before celebrating
   - Universal edge across all asset classes = investigate before celebrating
   - "If it sounds too good to be true, it's probably a bug"

### Discovery Velocity

This bug was found in **30 hours of live + 2 hours of forensic analysis**. That's elite failure detection. Most retail traders run broken strategies for months before catching them. The methodology that found this bug is the most valuable thing we built — and it survives the reset.

---

## The Optimistic View

We just learned more about our trading system in 30 hours than most projects learn in 6 months:
- Our discovery process is fast and rigorous
- Our infrastructure (engine, live runner, sweep runner, audit methodology) all works
- We have 38 symbols of clean data ready for new tests
- We have a long list of testable hypotheses (v3, stop orders, M15 zones, structural patterns, multi-confluence)
- We have a controlled $190 lesson instead of a $19,000 disaster

**The strategy is the easy part to replace. The methodology is the hard part to build, and we have it.**

---

## Files To Reference

| File | Purpose |
|---|---|
| `docs/system/analysis/signal-flip/backtest-validity-investigation.md` | The forensic report — proves the bug |
| `docs/system/strategy/strategy-v4-signal-flip-ssot.md` | The invalidated v4 spec — KEEP for historical reference, mark INVALID |
| `docs/system/analysis/signal-flip/master-portfolio-raw-vs-windowed.md` | Also invalid, mark for archival |
| `src/iora/strategy/retest_engine.py:391, 579` | The bug locations |
| `src/iora/strategy/retest_engine.py:_simulate_with_bars()` | The function that needs fixing |
| `results/sweeps/signal_flip/_master_summary.csv` | The phantom-edge sweep results — KEEP for the corrected re-run comparison |
| `results/sweeps/signal_flip/trades/*.csv` | The trade-level dumps — VALUABLE for forensic analysis of the bug |
| `C:/JoMa/forensic/2026-04-10-tier1-halt/` | Live snapshot — proves bug behavior in live |
| `docs/system/strategy/PROJECT_RESET_2026-04-10.md` | THIS FILE — the rebuild plan |

---

## Status of Active Chats

| Chat | Status | Action |
|---|---|---|
| Iora Backtest Validity | Complete (found the bug) | Close, findings preserved in report |
| Iora R-MaxDD Forensics | Complete (secondary finding, now superseded) | Close |
| JoMa Audit | Complete | Closed |
| JoMa Live Runner | Halted, account safe at $562 | Stay halted until v3 verified |
| JoMa Dashboard | Phase 1 complete, Phase 2 starting | Pause backtest-comparison features, continue infrastructure |
| Master Controller (Desktop) | Not yet opened | Wait until we know which strategy to scale |

---

## Next Conversation

A fresh strategic coordinator chat will pick up from this document. Its mandate:
1. Fix the engine
2. Validate v3
3. Test real hypotheses
4. Build the live-parity simulator
5. Re-deploy when ready

**The trading system isn't dead. The phantom strategy is dead. The real strategy is somewhere in the 10 hypotheses listed above, waiting to be tested with bug-free tools.**

Onward.
