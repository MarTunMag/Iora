# Triplet Entry Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Models A-D entry logic with spec-aligned triplet state machine (PUSH/CONTINUE/PULLBACK/REVERSAL) driven by zone creation events.

**Architecture:** Keep sections 1-11 of `iora_signals.pine` intact (~1230 lines of working computation). Remove sections 12+ (cascade, terminal, d-cycle, Models A-D, ~465 lines). Insert new triplet state machine + entry logic + dashboard. Mirror all changes to `iora_strategy.pine`.

**Tech Stack:** Pine Script v6, TradingView

**Spec:** `docs/superpowers/specs/2026-03-31-triplet-entry-models-design.md`

**Pine v6 rules:** `docs/pinescriptv6/LLM_MANIFEST.md` — always `//@version=6`, explicit types, no multiline ternaries, no reserved keywords, `.get()` result stored in local var before field access, `var` for persistent state.

---

### Task 1: Remove old entry model code from Signal Engine

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine:1230-1694`

This task removes everything from line 1230 (1-2-3 CASCADE DETECTION) through end of file (line 1694). This includes: cascade arming, trendline break detection, terminal exhaustion gate, d-cycle phase, Models A-D definitions, old SL/TP computation, old plotshape markers, old debug section, old dashboard.

Lines 1-1229 stay untouched (sections 1-11 + zone counting + EW + opposing nesting + consumption).

- [ ] **Step 1: Read the file to confirm line 1229 is the last line of the consumption section**

Read `iora_signals.pine:1225-1235` and verify line 1229 is `consume.score := consume.score + 1` (last line of consumption tracking) and line 1230 starts cascade detection.

- [ ] **Step 2: Delete lines 1230 through end of file**

Remove everything from the `// 1-2-3 CASCADE DETECTION` header through the last `table.cell` line. The file should now end after the consumption score block (line 1229).

- [ ] **Step 3: Remove unused inputs**

In section 1 (lines 5-29), remove these inputs that referenced the old models:
- `i_show_model_a`, `i_show_model_b`, `i_show_model_c`, `i_show_model_d` — replaced by new signal toggles in Task 5
- `i_debug` (current debug toggle) — replaced by new debug in Task 6

Keep: `i_show_zones`, `i_zone_*`, `i_max_zones`, `i_show_sl_tp`, `i_dash_on`, `i_dash_pos`.

- [ ] **Step 4: Verify the file still has valid Pine syntax**

The file should now be a valid Pine script that computes zones and conviction but has no entry logic or visual output (except zone boxes). It won't produce useful output yet, but should compile without errors if you add a minimal `plot(close)` at the end as a placeholder.

Add a temporary placeholder at the end:
```pine
// === PLACEHOLDER (replaced by Tasks 2-7) ===
plot(close, "placeholder", display=display.none)
```

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "refactor(signals): remove old entry models A-D, cascade, terminal, d-cycle

Keep sections 1-11 intact (request.security, envelope, conviction, legs,
zone creation, zone breaks, zone counting, EW, nesting, consumption).
Prepare for triplet state machine replacement."
```

---

### Task 2: Add helper functions

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (append after consumption section, before placeholder)

Two helpers needed by the state machine and entry logic.

- [ ] **Step 1: Add `get_zone_by_cls` helper**

Insert after line 1229 (end of consumption), before the placeholder:

```pine
// =============================================================================
// === SECTION 12: TRIPLET HELPERS
// =============================================================================

// Find the most recent zone with a specific swing classification
// Returns the zone, or a Zone with na fields if not found
get_zone_by_cls(array<Zone> zones, int cls) =>
    Zone result = Zone.new()
    bool found = false
    if zones.size() > 0
        for int i = 0 to math.min(zones.size() - 1, 7)
            Zone z = zones.get(i)
            if z.swing_cls == cls and not found
                result := z
                found := true
    result
```

- [ ] **Step 2: Add `m5_zone_matches_dir` helper**

```pine
// Check if the M5 zone just created matches a given direction
// dir > 0: demand zone (swc 3=LL or 4=HL) = bullish
// dir < 0: supply zone (swc 1=HH or 2=LH) = bearish
m5_zone_matches_dir(int dir) =>
    if dir > 0
        m5_fired and (m5_swc == 3 or m5_swc == 4)
    else if dir < 0
        m5_fired and (m5_swc == 1 or m5_swc == 2)
    else
        false
```

- [ ] **Step 3: Add `m15_zone_matches_dir` helper (for T5)**

```pine
// Same logic for M15 (T5 child)
m15_zone_matches_dir(int dir) =>
    if dir > 0
        m15_fired and (m15_swc == 3 or m15_swc == 4)
    else if dir < 0
        m15_fired and (m15_swc == 1 or m15_swc == 2)
    else
        false
```

- [ ] **Step 4: Compile check**

File should compile cleanly. The helpers are defined but not yet called.

- [ ] **Step 5: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): add triplet helper functions

get_zone_by_cls — find zone by swing classification
m5_zone_matches_dir / m15_zone_matches_dir — check if new zone matches direction"
```

---

### Task 3: Implement T6 state machine (M15 → M5 → M1)

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (append after helpers, before placeholder)

This is the core of the redesign. The T6 state machine tracks what the M15→M5→M1 triplet is doing.

- [ ] **Step 1: Add T6 state variables**

```pine
// =============================================================================
// === SECTION 13: TRIPLET STATE MACHINES
// =============================================================================

// --- T6: Parent=M15, Child=M5, Grandchild=M1 ---

var string t6_state       = "IDLE"
var int    t6_dir         = 0
var float  t6_push_top    = na
var float  t6_push_bot    = na
var float  t6_last_pb_top = na
var float  t6_last_pb_bot = na
var int    t6_zone_count  = 0
var bool   t6_m1_choch    = false
```

- [ ] **Step 2: Add T6 parent direction derivation**

```pine
// T6 parent direction — derived from M15's last swing classification
int t6_parent_dir = (m15_swc == 1 or m15_swc == 4) ? 1 : (m15_swc == 2 or m15_swc == 3) ? -1 : 0
```

- [ ] **Step 3: Add M1 CHoCH tracking**

```pine
// M1 CHoCH — grandchild confirms pullback exhaustion
// Bullish parent: M1 HL (swc==4) = pullback exhausting, parent direction resuming
// Bearish parent: M1 LH (swc==2) = pullback exhausting, parent direction resuming
if t6_state == "PULLBACK" and m1_fired
    if t6_dir > 0 and m1_swc == 4
        t6_m1_choch := true
    else if t6_dir < 0 and m1_swc == 2
        t6_m1_choch := true
```

- [ ] **Step 4: Add structural level lookup for PULLBACK vs REVERSING check**

```pine
// M15 structural level — used to distinguish PULLBACK from REVERSING
// Bullish M15: last HL demand bottom is the structural floor
// Bearish M15: last LH supply top is the structural ceiling
Zone t6_struct_zone = t6_parent_dir > 0 ? get_zone_by_cls(m15_dem, 4) : get_zone_by_cls(m15_sup, 2)
float t6_struct_level = t6_parent_dir > 0 ? t6_struct_zone.bottom : t6_struct_zone.top
bool t6_struct_valid = not na(t6_struct_level)
```

- [ ] **Step 5: Add T6 state transitions**

This is the main state machine logic. All transitions fire on `m5_fired` (new M5 zone created).

```pine
// T6 state transitions — driven by M5 zone creation events
string t6_prev_state = t6_state

if m5_fired
    bool is_with    = m5_zone_matches_dir(t6_parent_dir)
    bool is_counter = m5_zone_matches_dir(-t6_parent_dir)

    if t6_state == "IDLE"
        // IDLE → PUSHING: first M5 zone in parent direction, inside parent zone
        bool inside_parent = t6_parent_dir > 0 ? is_inside_zone(m15_dem) : is_inside_zone(m15_sup)
        if is_with and inside_parent
            t6_state      := "PUSHING"
            t6_dir        := t6_parent_dir
            t6_push_top   := m5_zone_matches_dir(1) ? m5_dem.get(0).top : m5_sup.get(0).top
            t6_push_bot   := m5_zone_matches_dir(1) ? m5_dem.get(0).bottom : m5_sup.get(0).bottom
            t6_zone_count := 1
            t6_m1_choch   := false

    else if t6_state == "PUSHING"
        if is_with
            // PUSHING → CONTINUING: next zone same dir, extends beyond push zone
            bool extends = t6_dir > 0 ? (m5_dem.get(0).bottom > t6_push_top) : (m5_sup.get(0).top < t6_push_bot)
            if extends
                t6_state      := "CONTINUING"
                t6_zone_count := t6_zone_count + 1
            else
                t6_zone_count := t6_zone_count + 1
        else if is_counter
            // PUSHING → PULLBACK or REVERSING
            if t6_struct_valid
                bool breaks_struct = t6_parent_dir > 0 ? (low < t6_struct_level) : (high > t6_struct_level)
                if breaks_struct
                    t6_state      := "REVERSING"
                    t6_zone_count := 0
                else
                    t6_state       := "PULLBACK"
                    t6_last_pb_top := is_counter and t6_parent_dir > 0 ? m5_sup.get(0).top : m5_dem.get(0).top
                    t6_last_pb_bot := is_counter and t6_parent_dir > 0 ? m5_sup.get(0).bottom : m5_dem.get(0).bottom
                    t6_zone_count  := 1
                    t6_m1_choch    := false
            else
                // No structural level found — conservative: treat as REVERSING
                t6_state      := "REVERSING"
                t6_zone_count := 0

    else if t6_state == "CONTINUING"
        if is_with
            t6_zone_count := t6_zone_count + 1
        else if is_counter
            // Same PULLBACK/REVERSING check as PUSHING
            if t6_struct_valid
                bool breaks_struct2 = t6_parent_dir > 0 ? (low < t6_struct_level) : (high > t6_struct_level)
                if breaks_struct2
                    t6_state      := "REVERSING"
                    t6_zone_count := 0
                else
                    t6_state       := "PULLBACK"
                    t6_last_pb_top := is_counter and t6_parent_dir > 0 ? m5_sup.get(0).top : m5_dem.get(0).top
                    t6_last_pb_bot := is_counter and t6_parent_dir > 0 ? m5_sup.get(0).bottom : m5_dem.get(0).bottom
                    t6_zone_count  := 1
                    t6_m1_choch    := false
            else
                t6_state      := "REVERSING"
                t6_zone_count := 0

    else if t6_state == "PULLBACK"
        if is_counter
            // Additional pullback zone — update last_pb tracking
            t6_last_pb_top := t6_parent_dir > 0 ? m5_sup.get(0).top : m5_dem.get(0).top
            t6_last_pb_bot := t6_parent_dir > 0 ? m5_sup.get(0).bottom : m5_dem.get(0).bottom
            t6_zone_count  := t6_zone_count + 1
            // Check if this counter-zone breaks structural level
            if t6_struct_valid
                bool breaks_struct3 = t6_parent_dir > 0 ? (low < t6_struct_level) : (high > t6_struct_level)
                if breaks_struct3
                    t6_state      := "REVERSING"
                    t6_zone_count := 0
        else if is_with and t6_m1_choch
            // Resolution A: zone at push zone level
            bool at_push = t6_dir > 0 ? (m5_dem.get(0).bottom <= t6_push_top) : (m5_sup.get(0).top >= t6_push_bot)
            // Resolution B: last pullback zone body-close broken
            bool pb_broken = t6_dir > 0 ? (close > t6_last_pb_top) : (close < t6_last_pb_bot)
            if at_push or pb_broken
                t6_state      := "PUSHING"
                t6_dir        := t6_parent_dir
                t6_push_top   := t6_dir > 0 ? m5_dem.get(0).top : m5_sup.get(0).top
                t6_push_bot   := t6_dir > 0 ? m5_dem.get(0).bottom : m5_sup.get(0).bottom
                t6_zone_count := 1
                t6_m1_choch   := false

    else if t6_state == "REVERSING"
        // Wait for M15 to confirm new direction
        if is_with and t6_parent_dir != t6_dir
            // M15 has flipped — this is first zone in new direction
            t6_state      := "PUSHING"
            t6_dir        := t6_parent_dir
            t6_push_top   := t6_dir > 0 ? m5_dem.get(0).top : m5_sup.get(0).top
            t6_push_bot   := t6_dir > 0 ? m5_dem.get(0).bottom : m5_sup.get(0).bottom
            t6_zone_count := 1
            t6_m1_choch   := false

// State reset on M15 direction change
if m15_fired
    int new_parent_dir = (m15_swc == 1 or m15_swc == 4) ? 1 : -1
    if new_parent_dir != t6_parent_dir and t6_state != "REVERSING"
        t6_state      := "IDLE"
        t6_dir        := 0
        t6_push_top   := na
        t6_push_bot   := na
        t6_zone_count := 0

// Track state transitions for debug
bool t6_changed = t6_state != t6_prev_state
```

- [ ] **Step 6: Compile check**

File should compile cleanly. The state machine runs but produces no visual output yet.

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): implement T6 triplet state machine (M15→M5→M1)

States: IDLE/PUSHING/CONTINUING/PULLBACK/REVERSING
Transitions driven by M5 zone creation events
M1 CHoCH confirmation for pullback resolution
Dual resolution paths (A: at push zone, B: pb zone broken)"
```

---

### Task 4: Implement T5 state machine (H1 → M15 → M5)

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (append after T6 state machine)

T5 follows the same pattern as T6, one level up. Parent=H1, Child=M15, Grandchild=M5.

- [ ] **Step 1: Add T5 state variables and parent direction**

```pine
// --- T5: Parent=H1, Child=M15, Grandchild=M5 ---

var string t5_state       = "IDLE"
var int    t5_dir         = 0
var float  t5_push_top    = na
var float  t5_push_bot    = na
var float  t5_last_pb_top = na
var float  t5_last_pb_bot = na
var int    t5_zone_count  = 0
var bool   t5_m5_choch    = false

// T5 parent direction — derived from H1's last swing classification
int t5_parent_dir = (h1_swc == 1 or h1_swc == 4) ? 1 : (h1_swc == 2 or h1_swc == 3) ? -1 : 0
```

- [ ] **Step 2: Add M5 CHoCH tracking for T5**

```pine
// M5 CHoCH — grandchild confirms pullback exhaustion for T5
if t5_state == "PULLBACK" and m5_fired
    if t5_dir > 0 and m5_swc == 4
        t5_m5_choch := true
    else if t5_dir < 0 and m5_swc == 2
        t5_m5_choch := true
```

- [ ] **Step 3: Add T5 state transitions**

Same pattern as T6 but using `m15_fired`, `m15_zone_matches_dir`, H1 structural levels, and `h1_fired` for reset. The code follows the same structure as T6 Step 5 with these substitutions:

| T6 | T5 |
|---|---|
| `m5_fired` | `m15_fired` |
| `m5_zone_matches_dir` | `m15_zone_matches_dir` |
| `m15_dem`/`m15_sup` (parent zones) | `h1_dem`/`h1_sup` |
| `m5_dem.get(0)`/`m5_sup.get(0)` (child zones) | `m15_dem.get(0)`/`m15_sup.get(0)` |
| `m1_fired`, `m1_swc` (grandchild CHoCH) | `m5_fired`, `m5_swc` |
| `m15_fired` (parent reset) | `h1_fired` |
| `t6_*` variables | `t5_*` variables |
| `t6_m1_choch` | `t5_m5_choch` |
| `is_inside_zone(m15_dem/sup)` | `is_inside_zone(h1_dem/sup)` |
| `get_zone_by_cls(m15_dem, 4)` | `get_zone_by_cls(h1_dem, 4)` |
| `get_zone_by_cls(m15_sup, 2)` | `get_zone_by_cls(h1_sup, 2)` |

Write the full T5 state machine following the T6 template with these substitutions. Do NOT abbreviate — write the complete code.

- [ ] **Step 4: Add T5 confidence derivation**

```pine
// T5 confidence — alignment between T5 and T6
string t5_confidence = "MEDIUM"
if t5_state == "PUSHING" or t5_state == "CONTINUING"
    if (t5_dir > 0 and t6_dir > 0) or (t5_dir < 0 and t6_dir < 0)
        t5_confidence := "HIGH"
    else if (t5_dir > 0 and t6_dir < 0) or (t5_dir < 0 and t6_dir > 0)
        t5_confidence := "LOW"
else if t5_state == "REVERSING"
    t5_confidence := "LOW"
```

- [ ] **Step 5: Compile check and commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): implement T5 triplet state machine (H1→M15→M5)

Same pattern as T6 one level up. Provides confidence scoring
for T6 entries: HIGH/MEDIUM/LOW based on T5/T6 alignment."
```

---

### Task 5: Implement entry signals + SL/TP

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (append after T5, before placeholder)

- [ ] **Step 1: Add new signal inputs**

Replace the old model toggle inputs (removed in Task 1) with new ones. Add these in section 1 (inputs area at top of file):

```pine
// --- Group: Signals ---
bool   i_show_push     = input.bool(true,            "Show PUSH signals",         group="Signals")
bool   i_show_continue = input.bool(true,            "Show CONTINUE signals",     group="Signals")
bool   i_show_pullback = input.bool(true,            "Show PULLBACK signals",     group="Signals")
bool   i_show_reversal = input.bool(true,            "Show REVERSAL signals",     group="Signals")
bool   i_show_sl_tp    = input.bool(true,            "Show SL/TP lines",          group="Signals")
```

- [ ] **Step 2: Add entry fire booleans**

```pine
// =============================================================================
// === SECTION 14: ENTRY SIGNALS
// =============================================================================

// Entry triggers — fire on M5 zone creation when T6 state matches
bool push_fire     = m5_fired and t6_state == "PUSHING"    and m5_zone_matches_dir(t6_dir)
bool continue_fire = m5_fired and t6_state == "CONTINUING" and m5_zone_matches_dir(t6_dir)
bool pullback_fire = m5_fired and t6_state == "PULLBACK"   and m5_zone_matches_dir(-t6_dir)
bool reversal_fire = m5_fired and t6_state == "REVERSING"  and m5_zone_matches_dir(t6_dir)

// Rising-edge detection — fire once per state entry
var bool push_prev     = false
var bool continue_prev = false
var bool pullback_prev = false
var bool reversal_prev = false

bool push_signal     = push_fire and not push_prev
bool continue_signal = continue_fire and not continue_prev
bool pullback_signal = pullback_fire and not pullback_prev
bool reversal_signal = reversal_fire and not reversal_prev

push_prev     := push_fire
continue_prev := continue_fire
pullback_prev := pullback_fire
reversal_prev := reversal_fire
```

- [ ] **Step 3: Add SL/TP computation**

```pine
// =============================================================================
// === SECTION 15: SL/TP COMPUTATION
// =============================================================================

var float sig_entry = na
var float sig_sl    = na
var float sig_tp    = na
var int   sig_dir   = 0
var string sig_type = "—"
float tick10 = syminfo.mintick * 10

if push_signal
    sig_type := "PUSH"
    sig_dir  := t6_dir
    if t6_dir > 0 and m5_dem.size() > 0
        sig_entry := m5_dem.get(0).bottom
        sig_sl    := t6_push_bot - tick10
        if m15_sup.size() > 0
            sig_tp := m15_sup.get(0).bottom
    else if t6_dir < 0 and m5_sup.size() > 0
        sig_entry := m5_sup.get(0).top
        sig_sl    := t6_push_top + tick10
        if m15_dem.size() > 0
            sig_tp := m15_dem.get(0).top

if continue_signal
    sig_type := "CONT"
    sig_dir  := t6_dir
    if t6_dir > 0 and m5_dem.size() > 0
        sig_entry := m5_dem.get(0).bottom
        sig_sl    := m5_dem.get(0).bottom - tick10
        if m15_sup.size() > 0
            sig_tp := m15_sup.get(0).bottom
    else if t6_dir < 0 and m5_sup.size() > 0
        sig_entry := m5_sup.get(0).top
        sig_sl    := m5_sup.get(0).top + tick10
        if m15_dem.size() > 0
            sig_tp := m15_dem.get(0).top

if pullback_signal
    sig_type := "PULL"
    sig_dir  := -t6_dir
    if sig_dir > 0 and m5_dem.size() > 0
        sig_entry := m5_dem.get(0).bottom
        sig_sl    := m5_dem.get(0).bottom - tick10
        sig_tp    := t6_push_top
    else if sig_dir < 0 and m5_sup.size() > 0
        sig_entry := m5_sup.get(0).top
        sig_sl    := m5_sup.get(0).top + tick10
        sig_tp    := t6_push_bot

if reversal_signal
    sig_type := "REV"
    sig_dir  := t6_dir
    if t6_dir > 0 and m5_dem.size() > 0
        sig_entry := m5_dem.get(0).bottom
        Zone rev_sl = get_zone_by_cls(m15_dem, 4)
        sig_sl := not na(rev_sl.bottom) ? rev_sl.bottom - tick10 : na
        if m15_sup.size() > 0
            sig_tp := m15_sup.get(0).bottom
    else if t6_dir < 0 and m5_sup.size() > 0
        sig_entry := m5_sup.get(0).top
        Zone rev_sl2 = get_zone_by_cls(m15_sup, 2)
        sig_sl := not na(rev_sl2.top) ? rev_sl2.top + tick10 : na
        if m15_dem.size() > 0
            sig_tp := m15_dem.get(0).top
```

- [ ] **Step 4: Add signal plotshapes**

```pine
// =============================================================================
// === SECTION 16: ON-CHART SIGNAL MARKERS
// =============================================================================

bool any_signal = push_signal or continue_signal or pullback_signal or reversal_signal

plotshape(i_show_push     and push_signal     and sig_dir > 0,  "Push Long",     shape.arrowup,      location.belowbar, #26A69A, size=size.small)
plotshape(i_show_push     and push_signal     and sig_dir < 0,  "Push Short",    shape.arrowdown,    location.abovebar, #EF5350, size=size.small)
plotshape(i_show_continue and continue_signal and sig_dir > 0,  "Cont Long",     shape.triangleup,   location.belowbar, #42A5F5, size=size.small)
plotshape(i_show_continue and continue_signal and sig_dir < 0,  "Cont Short",    shape.triangledown, location.abovebar, #42A5F5, size=size.small)
plotshape(i_show_pullback and pullback_signal and sig_dir > 0,  "Pull Long",     shape.circle,       location.belowbar, #FFCA28, size=size.small)
plotshape(i_show_pullback and pullback_signal and sig_dir < 0,  "Pull Short",    shape.circle,       location.abovebar, #FFCA28, size=size.small)
plotshape(i_show_reversal and reversal_signal and sig_dir > 0,  "Rev Long",      shape.diamond,      location.belowbar, #AB47BC, size=size.small)
plotshape(i_show_reversal and reversal_signal and sig_dir < 0,  "Rev Short",     shape.diamond,      location.abovebar, #AB47BC, size=size.small)
```

- [ ] **Step 5: Add SL/TP lines**

```pine
// =============================================================================
// === SECTION 17: SL/TP LINES
// =============================================================================

var line sl_ln = na
var line tp_ln = na
if any_signal and i_show_sl_tp
    if not na(sl_ln)
        line.delete(sl_ln)
    if not na(tp_ln)
        line.delete(tp_ln)
    if not na(sig_sl)
        sl_ln := line.new(bar_index, sig_sl, bar_index + 50, sig_sl, color=color.new(#EF5350, 30), style=line.style_dashed, width=1)
    if not na(sig_tp)
        tp_ln := line.new(bar_index, sig_tp, bar_index + 50, sig_tp, color=color.new(#26A69A, 30), style=line.style_dashed, width=1)
```

- [ ] **Step 6: Remove the placeholder `plot(close)` line added in Task 1**

- [ ] **Step 7: Compile check and commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): add triplet entry signals with SL/TP

4 entry types: PUSH/CONTINUE/PULLBACK/REVERSAL
Zone creation event = entry trigger
Structural SL/TP per state"
```

---

### Task 6: Add debug mode

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (add input at top, add debug section after SL/TP lines)

- [ ] **Step 1: Add debug input**

In the inputs section at top of file:

```pine
// --- Group: Debug ---
bool   i_debug       = input.bool(false,           "Debug: show triplet states", group="Debug")
```

- [ ] **Step 2: Add debug visuals**

After the SL/TP lines section:

```pine
// =============================================================================
// === SECTION 18: DEBUG — TRIPLET STATE VISUALS
// =============================================================================

// Background color for T6 state
color t6_bg = switch t6_state
    "PUSHING"    => color.new(#26A69A, 92)
    "CONTINUING" => color.new(#42A5F5, 92)
    "PULLBACK"   => color.new(#FFCA28, 92)
    "REVERSING"  => color.new(#EF5350, 92)
    => na

bgcolor(i_debug ? t6_bg : na, title="T6 State")

// State transition marker
plotshape(i_debug and t6_changed, "T6 Transition", shape.diamond, location.bottom, color.white, size=size.tiny)

// T6 labels every 100 bars
string t6_dir_arrow = t6_dir > 0 ? " ▲" : t6_dir < 0 ? " ▼" : ""
if i_debug and bar_index % 100 == 0
    label.new(bar_index, low, "T6:" + t6_state + t6_dir_arrow + " z:" + str.tostring(t6_zone_count), style=label.style_label_up, color=color.new(color.gray, 70), textcolor=color.white, size=size.tiny)

// T5 labels every 100 bars (offset by 50)
string t5_dir_arrow = t5_dir > 0 ? " ▲" : t5_dir < 0 ? " ▼" : ""
if i_debug and (bar_index + 50) % 100 == 0
    label.new(bar_index, high, "T5:" + t5_state + t5_dir_arrow + " [" + t5_confidence + "]", style=label.style_label_down, color=color.new(color.gray, 70), textcolor=color.white, size=size.tiny)
```

- [ ] **Step 3: Compile check and commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): add triplet state debug visuals

Background colors per T6 state, transition markers,
T6/T5 state labels with direction and zone count"
```

---

### Task 7: Add dashboard

**Files:**
- Modify: `tw_indicators/iora_structure/iora_signals.pine` (append after debug section)

- [ ] **Step 1: Add dashboard table**

```pine
// =============================================================================
// === SECTION 19: SIGNAL DASHBOARD
// =============================================================================

if i_dash_on and barstate.islast
    string tbl_pos = switch i_dash_pos
        "Top Left"     => position.top_left
        "Top Right"    => position.top_right
        "Bottom Right" => position.bottom_right
        => position.bottom_left

    var table sig_tbl = table.new(tbl_pos, 2, 7, bgcolor=color.new(#1E1E1E, 10), border_color=color.new(#333333, 0), border_width=1)

    string cell_sz = size.tiny
    color  cell_bg = color.new(#1E1E1E, 10)

    // Row 0: Header
    table.cell(sig_tbl, 0, 0, "Signal Engine", text_color=color.new(#E0E0E0, 0), bgcolor=color.new(#2196F3, 20), text_size=cell_sz)
    table.cell(sig_tbl, 1, 0, "Triplet", text_color=color.new(#E0E0E0, 0), bgcolor=color.new(#2196F3, 20), text_size=cell_sz)

    // Row 1: T5 state
    string t5_lbl = "T5: " + t5_state + t5_dir_arrow
    color  t5_clr = t5_state == "IDLE" ? color.new(#546E7A, 0) : t5_dir > 0 ? color.new(#26A69A, 0) : color.new(#EF5350, 0)
    table.cell(sig_tbl, 0, 1, t5_lbl, text_color=t5_clr, bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 1, "z:" + str.tostring(t5_zone_count), text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)

    // Row 2: T6 state
    string t6_lbl = "T6: " + t6_state + t6_dir_arrow
    color  t6_clr = t6_state == "IDLE" ? color.new(#546E7A, 0) : t6_dir > 0 ? color.new(#26A69A, 0) : color.new(#EF5350, 0)
    table.cell(sig_tbl, 0, 2, t6_lbl, text_color=t6_clr, bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 2, "z:" + str.tostring(t6_zone_count), text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)

    // Row 3: Confidence
    color conf_clr = t5_confidence == "HIGH" ? color.new(#26A69A, 0) : t5_confidence == "LOW" ? color.new(#EF5350, 0) : color.new(#FFCA28, 0)
    table.cell(sig_tbl, 0, 3, "Conf: " + t5_confidence, text_color=conf_clr, bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 3, "Consume: " + str.tostring(consume.score) + "/4", text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)

    // Row 4: M1 CHoCH status
    string choch_str = t6_m1_choch ? "CONFIRMED" : "—"
    color  choch_clr = t6_m1_choch ? color.new(#26A69A, 0) : color.new(#546E7A, 0)
    table.cell(sig_tbl, 0, 4, "M1 CHoCH: " + choch_str, text_color=choch_clr, bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 4, "H1 Zones: " + str.tostring(h1_zone_cnt), text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)

    // Row 5: Active signal
    string dir_lbl = sig_dir > 0 ? "LONG" : sig_dir < 0 ? "SHORT" : "—"
    color  dir_clr = sig_dir > 0 ? color.new(#26A69A, 0) : sig_dir < 0 ? color.new(#EF5350, 0) : color.new(#546E7A, 0)
    float rr_ratio = not na(sig_entry) and not na(sig_sl) and not na(sig_tp) and sig_sl != sig_entry ? math.abs(sig_tp - sig_entry) / math.abs(sig_sl - sig_entry) : na
    string rr_str = not na(rr_ratio) ? "R:R 1:" + str.tostring(rr_ratio, "#.#") : "—"
    table.cell(sig_tbl, 0, 5, sig_type + " " + dir_lbl, text_color=dir_clr, bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 5, rr_str, text_color=color.new(#B0BEC5, 0), bgcolor=cell_bg, text_size=cell_sz)

    // Row 6: SL/TP values
    string entry_str = not na(sig_entry) ? str.tostring(sig_entry, format.mintick) : "—"
    string sl_str    = not na(sig_sl)    ? str.tostring(sig_sl,    format.mintick) : "—"
    string tp_str    = not na(sig_tp)    ? str.tostring(sig_tp,    format.mintick) : "—"
    table.cell(sig_tbl, 0, 6, "E:" + entry_str + " SL:" + sl_str, text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)
    table.cell(sig_tbl, 1, 6, "TP:" + tp_str, text_color=color.new(#78909C, 0), bgcolor=cell_bg, text_size=cell_sz)
```

- [ ] **Step 2: Compile check and commit**

```bash
git add tw_indicators/iora_structure/iora_signals.pine
git commit -m "feat(signals): add triplet state dashboard

Shows T5/T6 state, confidence, M1 CHoCH, active signal, SL/TP"
```

---

### Task 8: Mirror changes to Strategy file

**Files:**
- Modify: `tw_indicators/iora_structure/iora_strategy.pine`

The strategy file has the same computation preamble. Apply the same changes:

- [ ] **Step 1: Read `iora_strategy.pine` to identify the equivalent removal range**

The strategy has the same cascade/terminal/d-cycle/Models A-D sections. Find the line where cascade detection starts (equivalent to signals line 1230) and the line where trade execution ends.

- [ ] **Step 2: Remove old entry model code**

Same as Task 1 — remove cascade arming through end of trade execution code. Keep sections 1-11 intact.

- [ ] **Step 3: Copy helpers and state machines from signals file**

Copy sections 12-15 (helpers, T6 state machine, T5 state machine, entry signals + SL/TP) from the updated signals file. These are identical — same computation, no visual output differences.

- [ ] **Step 4: Replace trade execution with new state-based entries**

Replace the old Model A-D `strategy.entry()`/`strategy.exit()` blocks with:

```pine
// =============================================================================
// === TRADE EXECUTION
// =============================================================================

if push_signal and i_model_push and dir_ok(sig_dir) and not has_open("Push")
    if not na(sig_sl) and not na(sig_tp) and sig_sl != sig_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(sig_entry - sig_sl), syminfo.mintick)
        float adj_qty = t5_confidence == "MEDIUM" ? qty * 0.5 : t5_confidence == "LOW" ? 0.0 : qty
        if adj_qty > 0
            if sig_dir > 0
                strategy.entry("Push", strategy.long, qty=adj_qty)
            else
                strategy.entry("Push", strategy.short, qty=adj_qty)
            strategy.exit("Push_x", from_entry="Push", stop=sig_sl, limit=sig_tp)

if continue_signal and i_model_continue and dir_ok(sig_dir) and not has_open("Continue")
    if not na(sig_sl) and not na(sig_tp) and sig_sl != sig_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(sig_entry - sig_sl), syminfo.mintick)
        float adj_qty = t5_confidence == "MEDIUM" ? qty * 0.5 : t5_confidence == "LOW" ? 0.0 : qty
        if adj_qty > 0
            if sig_dir > 0
                strategy.entry("Continue", strategy.long, qty=adj_qty)
            else
                strategy.entry("Continue", strategy.short, qty=adj_qty)
            strategy.exit("Continue_x", from_entry="Continue", stop=sig_sl, limit=sig_tp)

if pullback_signal and i_model_pullback and dir_ok(sig_dir) and not has_open("Pullback")
    if not na(sig_sl) and not na(sig_tp) and sig_sl != sig_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(sig_entry - sig_sl), syminfo.mintick)
        float adj_qty = t5_confidence == "MEDIUM" ? qty * 0.5 : t5_confidence == "LOW" ? 0.0 : qty
        if adj_qty > 0
            if sig_dir > 0
                strategy.entry("Pullback", strategy.long, qty=adj_qty)
            else
                strategy.entry("Pullback", strategy.short, qty=adj_qty)
            strategy.exit("Pullback_x", from_entry="Pullback", stop=sig_sl, limit=sig_tp)

if reversal_signal and i_model_reversal and dir_ok(sig_dir) and not has_open("Reversal")
    if not na(sig_sl) and not na(sig_tp) and sig_sl != sig_entry
        float qty = i_sizing_mode == "Fixed" ? i_lot_size : (strategy.equity * i_risk_pct / 100.0) / math.max(math.abs(sig_entry - sig_sl), syminfo.mintick)
        float adj_qty = t5_confidence == "MEDIUM" ? qty * 0.5 : t5_confidence == "LOW" ? 0.0 : qty
        if adj_qty > 0
            if sig_dir > 0
                strategy.entry("Reversal", strategy.long, qty=adj_qty)
            else
                strategy.entry("Reversal", strategy.short, qty=adj_qty)
            strategy.exit("Reversal_x", from_entry="Reversal", stop=sig_sl, limit=sig_tp)
```

- [ ] **Step 5: Update strategy inputs**

Replace `i_model_a`/`i_model_b`/`i_model_c`/`i_model_d` with:
```pine
bool   i_model_push     = input.bool(true, "Enable PUSH entries",     group="Models")
bool   i_model_continue = input.bool(true, "Enable CONTINUE entries", group="Models")
bool   i_model_pullback = input.bool(true, "Enable PULLBACK entries", group="Models")
bool   i_model_reversal = input.bool(true, "Enable REVERSAL entries", group="Models")
```

- [ ] **Step 6: Compile check and commit**

```bash
git add tw_indicators/iora_structure/iora_strategy.pine
git commit -m "feat(strategy): mirror triplet entry models from signal engine

Same T5/T6 state machines, 4 state-based trade entries,
T5 confidence-adjusted sizing, structural SL/TP"
```

---

### Task 9: Visual validation on chart

**Files:** None modified — this is a testing/validation task.

- [ ] **Step 1: Apply Signal Engine to GBPUSD M1 chart in TradingView**

Paste `iora_signals.pine` into TradingView. Enable debug mode (`i_debug = true`). Verify:
- T6 state background colors change as M5 zones form
- State labels show sensible transitions (PUSHING when M5 zones stack, PULLBACK when counter-zones form)
- Signals fire AT zone creation events (plotshape appears on same bar as new zone box)
- No compilation errors

- [ ] **Step 2: Compare with user's annotated screenshots**

Check the areas previously circled by the user (price entering H1/H4 zones and reversing). Signals should now appear at those zone interaction points because:
- Zone creation IS the trigger (not compound boolean conditions)
- The state machine captures the structural context the user visually identifies

- [ ] **Step 3: Apply Strategy to GBPUSD M1 chart**

Paste `iora_strategy.pine`. Verify Strategy Tester shows:
- Trades with IDs "Push", "Continue", "Pullback", "Reversal"
- SL/TP values are structural (not na)
- Toggle individual models off to isolate per-state behavior

- [ ] **Step 4: Report findings**

Note any issues with signal timing, SL/TP levels, or state transitions that need tuning.
