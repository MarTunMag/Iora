# Deep System Audit — Mechanical Ruleset Validation

> **For:** Fresh Claude Code CLI chat
> **Date:** 2026-04-07
> **Goal:** Comprehensive audit of ALL validated findings, transcripts, and data insights.
> No judgment calls without data. Everything must be tested before labeled "works" or "dead."

---

## READ FIRST (in order)

1. `CLAUDE.md` — project rules
2. `docs/system/trading_concepts_reference.md` — 18 YouTube videos mapped to our system
3. `docs/system/level4-spread-reality-analysis.md` — spread impact analysis
4. `docs/system/level4-findings-and-next-steps.md` — all validated findings
5. `docs/system/level4-cross-tf-tp-deep-analysis.md` — dual-profile strategy
6. `docs/system/level4-v3-realistic-sweep-analysis.md` — TTL=0 findings
7. ALL files in `docs/system/youtube_references/` — 31 transcripts total

---

## YOUR TASK

### Phase 1: Transcript Deep Review

Read ALL 31 YouTube transcripts in `docs/system/youtube_references/`. For each one, extract:

1. **Entry rules** — when/where/how to enter (zone edge, zone interior, confirmation candle, etc.)
2. **SL rules** — where SL goes relative to zone, how tight, what invalidates
3. **TP rules** — fixed R:R, structural targets, partial TP, trailing
4. **Multi-TF rules** — how HTF filters LTF, what confirms what
5. **Position management** — partial close, breakeven, trail, re-entry
6. **What makes a VALID entry vs NOISE** — the filtering criteria

Create a master table: `Concept | Sources (which videos) | Iora Status (implemented/tested/untested/missing)`

### Phase 2: Data Insight Audit

Read ALL the analysis docs and answer these questions WITH EVIDENCE:

**A. What has been TESTED and PROVEN (data speaks)?**
List every config that has been swept with results. Include SQN, PF, WR, trade count.
Organize by TF pair.

**B. What has been TESTED and FAILED?**
List every config that was tested and performed poorly. BUT — for each one, check:
- Was it tested with partial TP? (If not, it's NOT fully tested — H1@H4 went from SQN 1.61 → 24.14 with partial)
- Was it tested with min_sl_pips floor? (If not, spread may have killed a viable config)
- Was it tested with zone-top entry? (Bottom entry has tighter SL, more vulnerable to spread)
- Was it tested with TTL=0? (TTL=1 gets half the trades)

**If a config failed but was NOT tested with all 4 parameters, mark it as "INCOMPLETE — needs retest".**

**C. What has NEVER been tested?**
Scan all possible TF pair × entry mode × limit_edge × partial_tp × min_sl_pips combinations.
Which combinations have zero sweep results? These are gaps.

Known gaps from our analysis:
- M5@M15 top edge + partial TP + spread (NEVER RUN — the biggest gap)
- M1@M5 anything (never tested)
- M1@M15 anything (never tested)
- HTF-triggered LTF nesting (being built now in Tasks 7-13)

**D. Spread integration — is our model correct?**

CRITICAL QUESTION: Our backtest models spread as a COST added to entry price:
```python
def _compute_effective_entry(entry_price, direction, spread_pips, pip_size):
    spread_cost = spread_pips * pip_size
    if direction == "long":
        return entry_price + spread_cost  # Buy at ask
    return entry_price - spread_cost      # Sell at bid
```

This means:
- Spread is added ON TOP of the limit entry price
- SL distance stays the same (zone width)
- Effective R:R worsens because entry shifts toward SL

BUT: In live trading, spread is INTEGRATED into the SL distance. When you place a buy limit
at 1.3000 with SL at 1.2990 (10 pip zone), the broker fills at ASK = 1.3000 + spread.
Your actual SL distance = 1.3000 + spread - 1.2990 = 10 pips + spread. The SL is wider
than the zone, not tighter.

**Audit question:** Does our backtest spread model match live reality? Or is the model
pessimistic/optimistic in a way that changes which configs "survive"?

Check `src/iora/strategy/retest_engine.py` lines 739-751 (`_compute_effective_entry`).
Check `src/iora/strategy/retest_sl_tp.py` for how SL is computed.
Trace a complete example:
- GBPUSD demand zone: top=1.3010, bottom=1.3000
- Limit entry at zone top: 1.3010
- SL at zone bottom: 1.3000
- Spread = 1.5 pips = 0.00015
- What does the backtest compute for effective_entry, SL distance, TP distance?
- What would happen in live MT5?

### Phase 3: Mechanical Ruleset Summary

Produce a single authoritative document: `docs/system/mechanical-ruleset-validated.md`

Structure:
```
## Proven Rules (data confirms)
- Rule 1: [description] — Evidence: [SQN, PF, WR from sweep]
- Rule 2: ...

## Probable Rules (data suggests, needs more testing)
- Rule: [description] — Evidence: [partial results] — Gap: [what's untested]

## Untested Hypotheses (no data yet)
- Hypothesis: [description] — Required test: [specific config]

## Disproven Rules (data rejects)
- Rule: [description] — Evidence: [sweep results showing failure]
- BUT: Was it fully tested? [yes/no — check partial TP, min_sl, top edge, TTL=0]

## Video Concepts Not Yet Mechanized
- Concept: [from transcripts] — Potential implementation: [how]
- Priority: [high/medium/low based on how many videos agree]
```

### Phase 4: Recommendations

Based on the audit, what should we test NEXT? Prioritize by:
1. Highest potential impact (untested configs that MIGHT be strong)
2. Lowest implementation effort (can test with existing engine)
3. Most video consensus (concepts agreed by 5+ independent sources)

---

## CRITICAL PRINCIPLES

1. **Data speaks, not assumptions.** Never label a config "dead" unless it has been tested
   with: partial TP, min_sl floor, zone-top entry, TTL=0, AND spread modeling. Missing
   any one of these means the test was incomplete.

2. **Live production is profitable on M5@M15.** This means our backtest "dead" conclusion
   for M5@M15 was based on incomplete testing. The right config may work.

3. **Spread is integrated in SL in live trading.** Verify that our backtest spread model
   matches this reality. If it doesn't, some "failed" configs may actually be viable.

4. **Partial TP is transformative.** H1@H4 went from SQN 1.61 to 24.14 with partial.
   Any config tested WITHOUT partial that showed SQN 1-3 might become SQN 10-20+ with it.

5. **TTL=0 doubles trade count.** Any config tested with TTL=1 has seen only half its
   potential trades. Retest with TTL=0.

6. **31 YouTube transcripts from professional traders all agree on the same principles.**
   Cross-reference our mechanical rules against these. Where we diverge, test both.

---

## CONTEXT: LIVE SYSTEM (JoMa) IS RUNNING

A parallel chat is managing the live trading system at `C:\JoMa`. Key facts:

- **Live M5@M15 is profitable** — +$120 recovered after fixing edge limit issues
- **26 completed trades on April 6-7** — during tariff crash selloff (extreme conditions)
- **P&L logging was broken** — MT5 deal history returned garbage values (5-41x overstated losses). Being fixed with dual P&L: computed from price action (SSOT) + MT5 history (audit)
- **Enhanced LiveTradeRecord being built** — mirrors RetestTradeRecord for backtest-live parity
- **Live spread data will be available** — actual spread at fill time, slippage, tick_value

This means: once JoMa's logging is fixed, we'll have REAL spread/slippage numbers to
validate against our backtest's fixed 1.5p assumption. Factor this into recommendations.

If the audit finds that our backtest spread model is pessimistic (live spread < 1.5p average),
then some "failed" backtest configs may actually work in live. And vice versa.

## CONTEXT: HTF-TRIGGERED LTF ENTRY (Being Built)

Tasks 1-6 of the 13-task implementation plan are COMPLETE:
- Config fields added (ltf_nesting, trigger_tf_pair, entry_tf_override, etc.)
- ZoneBirthEvent, CandidateBuildResult dataclasses added
- Static nesting (find LTF zones inside HTF zones) — implemented
- Dynamic nesting (zone birth tracking) — implemented
- 27 new tests passing, 445 total tests green

Tasks 7-13 remain: simulation engine changes, sweep generator, CLI runner, sweep execution.
The audit should factor in what this new entry mode will test and NOT duplicate that work.

## OUTPUT

Save the mechanical ruleset to: `docs/system/mechanical-ruleset-validated.md`
Save the audit findings to: `docs/system/deep-system-audit-2026-04-07.md`

Be thorough. This is the foundation document for all future development.
