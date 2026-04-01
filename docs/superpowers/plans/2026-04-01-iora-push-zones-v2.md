# Iora Push Zones v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the push zones indicator with zone counting (5+3 exhaustion) and zone nesting detection (continuation vs terminal signals).

**Architecture:** Copy v1 push zones template to a new v2 file. Expand the `process()` method to accept parent zone array + counting state, add counting logic with dual reset triggers, nesting detection with terminal classification, and a final-pass label renderer. Reverse S9 execution order to HIGH→LOW so parents populate before children.

**Tech Stack:** Pine Script v6, TradingView

**Spec:** `docs/superpowers/specs/2026-04-01-iora-push-zones-v2-design.md`
**Template (v1 frozen):** `tw_indicators/iora_zones/templates/iora_push_zones.pine`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `tw_indicators/iora_zones/iora_push_zones_v2.pine` | Create | The v2 indicator — all counting, nesting, and push zone logic |

Single file. Built incrementally from the v1 template.

---

### Task 1: Scaffold — Copy v1, Update Declarations, Add Inputs and UDT Fields

**Files:**
- Create: `tw_indicators/iora_zones/iora_push_zones_v2.pine` (copy from `tw_indicators/iora_zones/templates/iora_push_zones.pine`)

**Context:** This task creates the v2 file from the v1 template and makes non-behavioral changes: new indicator name, new inputs, expanded UDT, new helper. The indicator must compile after this task with identical behavior to v1.

- [ ] **Step 1: Copy the v1 template to v2**

```bash
cp tw_indicators/iora_zones/templates/iora_push_zones.pine tw_indicators/iora_zones/iora_push_zones_v2.pine
```

- [ ] **Step 2: Update the indicator declaration**

Change line 1-2 to:

```pine
//@version=6
indicator("Iora Push Zones v2", overlay = true, max_boxes_count = 500, max_labels_count = 500, max_lines_count = 500, calc_bars_count = 2000)
```

Note: `max_lines_count = 500` added for optional nesting lines feature.

- [ ] **Step 3: Add new inputs to S1**

After the existing `i_normal` input (Show Normal Zones), add terminal color inputs:

```pine
color  i_term_bg = input.color(color.new(#9C27B0, 92), "Terminal Fill",      group = GRP_CLR)
color  i_term_br = input.color(color.new(#9C27B0, 30), "Terminal Border",    group = GRP_CLR)
```

After the dashboard inputs, add a new Display group:

```pine
string GRP_DISP  = "Display"
bool   i_nest_lines = input.bool(false, "Show Nesting Lines", group = GRP_DISP)
```

- [ ] **Step 4: Expand the Zone UDT in S2**

Add two new fields after `swing_cls`:

```pine
type Zone
    float   top          = 0.0
    float   bottom       = 0.0
    bool    is_supply    = false
    int     origin_time  = 0
    box     bx
    bool    is_push      = false
    bool    is_reversal  = false
    string  struct_cls   = ""
    string  swing_cls    = ""
    int     count_num    = 0
    bool    is_terminal  = false
```

- [ ] **Step 5: Add `tf_parent()` helper to S3**

After `tf_label()`, add:

```pine
tf_parent(string tf) =>
    string out = tf == "1" ? "15" : tf == "5" ? "60" : tf == "15" ? "60" : tf == "60" ? "240" : tf == "240" ? "1D" : tf == "1D" ? "1W" : tf == "1W" ? "1M" : ""
    out
```

- [ ] **Step 6: Verify compilation**

Paste the indicator in TradingView Pine Editor and confirm it compiles without errors. Behavior should be identical to v1 at this point — the new fields and inputs exist but are unused.

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "feat(push-zones-v2): scaffold from v1 template with new inputs and UDT fields"
```

---

### Task 2: Expand process() Signature and Reverse S9 Execution Order

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones_v2.pine` (S6 process signature, S9 execution block)

**Context:** This task changes the `process()` method signature to accept parent zone array, parent fire signals, and counting state. It also reverses S9 execution from LOW→HIGH to HIGH→LOW order, and adds the new `var` state variables for counting. The indicator must compile after this task. Counting/nesting logic is NOT implemented yet — just the plumbing.

- [ ] **Step 1: Update process() signature in S6**

Replace the existing `process()` method signature:

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, float seq_hh_val, float seq_ll_val, int trend_val, string tf_str, float prev_push_hi, float prev_push_lo) =>
```

With:

```pine
method process(array<Zone> zones, bool fire, float ztop, float zbot, bool is_sup, int z_time, string hi_txt, string lo_txt, float seq_hh_val, float seq_ll_val, int trend_val, string tf_str, float prev_push_hi, float prev_push_lo, array<Zone> parent_zones, bool parent_fire, bool parent_is_sup, int sup_count_in, int dem_count_in, int sup_reset_time_in, int dem_reset_time_in) =>
```

- [ ] **Step 2: Add counting state variables at the top of process()**

Right after `int max_ms = tf_max_age(tf_str) * tf_ms`, add:

```pine
    int new_sup_count = sup_count_in
    int new_dem_count = dem_count_in
    int new_sup_reset = sup_reset_time_in
    int new_dem_reset = dem_reset_time_in
```

- [ ] **Step 3: Update process() return value**

Replace the final line of process():

```pine
    [new_push_hi, new_push_lo]
```

With:

```pine
    [new_push_hi, new_push_lo, new_sup_count, new_dem_count, new_sup_reset, new_dem_reset]
```

- [ ] **Step 4: Add new state variables in S9**

After the existing `var float phN = na, var float plN = na` lines, add counting state per TF:

```pine
var int sc0 = 0, var int dc0 = 0, var int srt0 = 0, var int drt0 = 0
var int sc1 = 0, var int dc1 = 0, var int srt1 = 0, var int drt1 = 0
var int sc2 = 0, var int dc2 = 0, var int srt2 = 0, var int drt2 = 0
var int sc3 = 0, var int dc3 = 0, var int srt3 = 0, var int drt3 = 0
var int sc4 = 0, var int dc4 = 0, var int srt4 = 0, var int drt4 = 0
var int sc5 = 0, var int dc5 = 0, var int srt5 = 0, var int drt5 = 0
var int sc6 = 0, var int dc6 = 0, var int srt6 = 0, var int drt6 = 0
var int sc7 = 0, var int dc7 = 0, var int srt7 = 0, var int drt7 = 0
```

- [ ] **Step 5: Reverse S9 execution order and wire parent arrays**

Replace the entire per-TF execution block (the 8 `if i_tfN_on` blocks) with HIGH→LOW order. Each child receives its parent's zone array, fire signal, and fire side:

```pine
// Process HIGH → LOW: parents populate before children check nesting
var array<Zone> _empty = array.new<Zone>()  // READ-ONLY — never push/modify this array

if i_tf7_on
    [nph7, npl7, nsc7, ndc7, nsrt7, ndrt7] = zones7.process(f7, zt7, zb7, s7, tm7, h1s7, l1s7, hh7, ll7, trend7, i_tf7, ph7, pl7, _empty, false, false, sc7, dc7, srt7, drt7)
    ph7 := nph7, pl7 := npl7, sc7 := nsc7, dc7 := ndc7, srt7 := nsrt7, drt7 := ndrt7

if i_tf6_on
    array<Zone> p6 = i_tf7_on ? zones7 : _empty
    bool pf6 = i_tf7_on ? f7 : false
    bool ps6 = i_tf7_on ? s7 : false
    [nph6, npl6, nsc6, ndc6, nsrt6, ndrt6] = zones6.process(f6, zt6, zb6, s6, tm6, h1s6, l1s6, hh6, ll6, trend6, i_tf6, ph6, pl6, p6, pf6, ps6, sc6, dc6, srt6, drt6)
    ph6 := nph6, pl6 := npl6, sc6 := nsc6, dc6 := ndc6, srt6 := nsrt6, drt6 := ndrt6

if i_tf5_on
    array<Zone> p5 = i_tf6_on ? zones6 : _empty
    bool pf5 = i_tf6_on ? f6 : false
    bool ps5 = i_tf6_on ? s6 : false
    [nph5, npl5, nsc5, ndc5, nsrt5, ndrt5] = zones5.process(f5, zt5, zb5, s5, tm5, h1s5, l1s5, hh5, ll5, trend5, i_tf5, ph5, pl5, p5, pf5, ps5, sc5, dc5, srt5, drt5)
    ph5 := nph5, pl5 := npl5, sc5 := nsc5, dc5 := ndc5, srt5 := nsrt5, drt5 := ndrt5

if i_tf4_on
    array<Zone> p4 = i_tf5_on ? zones5 : _empty
    bool pf4 = i_tf5_on ? f5 : false
    bool ps4 = i_tf5_on ? s5 : false
    [nph4, npl4, nsc4, ndc4, nsrt4, ndrt4] = zones4.process(f4, zt4, zb4, s4, tm4, h1s4, l1s4, hh4, ll4, trend4, i_tf4, ph4, pl4, p4, pf4, ps4, sc4, dc4, srt4, drt4)
    ph4 := nph4, pl4 := npl4, sc4 := nsc4, dc4 := ndc4, srt4 := nsrt4, drt4 := ndrt4

if i_tf3_on
    array<Zone> p3 = i_tf4_on ? zones4 : _empty
    bool pf3 = i_tf4_on ? f4 : false
    bool ps3 = i_tf4_on ? s4 : false
    [nph3, npl3, nsc3, ndc3, nsrt3, ndrt3] = zones3.process(f3, zt3, zb3, s3, tm3, h1s3, l1s3, hh3, ll3, trend3, i_tf3, ph3, pl3, p3, pf3, ps3, sc3, dc3, srt3, drt3)
    ph3 := nph3, pl3 := npl3, sc3 := nsc3, dc3 := ndc3, srt3 := nsrt3, drt3 := ndrt3

if i_tf2_on
    array<Zone> p2 = i_tf3_on ? zones3 : _empty
    bool pf2 = i_tf3_on ? f3 : false
    bool ps2 = i_tf3_on ? s3 : false
    [nph2, npl2, nsc2, ndc2, nsrt2, ndrt2] = zones2.process(f2, zt2, zb2, s2, tm2, h1s2, l1s2, hh2, ll2, trend2, i_tf2, ph2, pl2, p2, pf2, ps2, sc2, dc2, srt2, drt2)
    ph2 := nph2, pl2 := npl2, sc2 := nsc2, dc2 := ndc2, srt2 := nsrt2, drt2 := ndrt2

if i_tf1_on
    array<Zone> p1 = i_tf3_on ? zones3 : _empty
    bool pf1 = i_tf3_on ? f3 : false
    bool ps1 = i_tf3_on ? s3 : false
    [nph1, npl1, nsc1, ndc1, nsrt1, ndrt1] = zones1.process(f1, zt1, zb1, s1, tm1, h1s1, l1s1, hh1, ll1, trend1, i_tf1, ph1, pl1, p1, pf1, ps1, sc1, dc1, srt1, drt1)
    ph1 := nph1, pl1 := npl1, sc1 := nsc1, dc1 := ndc1, srt1 := nsrt1, drt1 := ndrt1

if i_tf0_on
    array<Zone> p0 = i_tf2_on ? zones2 : _empty
    bool pf0 = i_tf2_on ? f2 : false
    bool ps0 = i_tf2_on ? s2 : false
    [nph0, npl0, nsc0, ndc0, nsrt0, ndrt0] = zones0.process(f0, zt0, zb0, s0, tm0, h1s0, l1s0, hh0, ll0, trend0, i_tf0, ph0, pl0, p0, pf0, ps0, sc0, dc0, srt0, drt0)
    ph0 := nph0, pl0 := npl0, sc0 := nsc0, dc0 := ndc0, srt0 := nsrt0, drt0 := ndrt0
```

**Parent wiring table for reference:**

| TF Index | TF | Parent Index | Parent zones | Parent fire | Parent side |
|----------|----|-------------|-------------|-------------|-------------|
| 7 | MN | — | _empty | false | false |
| 6 | W | 7 | zones7 | f7 | s7 |
| 5 | D | 6 | zones6 | f6 | s6 |
| 4 | H4 | 5 | zones5 | f5 | s5 |
| 3 | H1 | 4 | zones4 | f4 | s4 |
| 2 | M15 | 3 | zones3 | f3 | s3 |
| 1 | M5 | 3 | zones3 | f3 | s3 |
| 0 | M1 | 2 | zones2 | f2 | s2 |

- [ ] **Step 6: Verify compilation**

Paste in TradingView Pine Editor. Must compile without errors. Zones should still appear — behavior identical to v1 since counting/nesting logic is not implemented yet (the new parameters are received but unused).

- [ ] **Step 7: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "feat(push-zones-v2): expand process() signature and reverse S9 to HIGH→LOW order"
```

---

### Task 3: Implement Zone Counting

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones_v2.pine` (S6 process method)

**Context:** This task adds zone counting inside `process()`. Two reset triggers (parent fire + same-TF HH/LL). Count increment on zone creation. The `count_num` field gets assigned to each new zone. After this task, zones should be numbered in their labels (if normal zones are visible) or in push/reversal labels.

- [ ] **Step 1: Add count reset logic at the top of process()**

After the counting state initialization lines (`int new_sup_count = sup_count_in` etc.), add reset logic BEFORE the expire/break loop:

```pine
    // Count reset — Trigger 1: parent fires same-side zone
    if parent_fire
        if parent_is_sup
            new_sup_count := 0
            new_sup_reset := time
        else
            new_dem_count := 0
            new_dem_reset := time

    // Count reset — Trigger 2: same-TF structural invalidation (HH resets supply, LL resets demand)
    if fire and is_sup and hi_txt == "HH"
        new_sup_count := 0
        new_sup_reset := time
    if fire and not is_sup and lo_txt == "LL"
        new_dem_count := 0
        new_dem_reset := time
```

**Important:** Both trigger 2 checks use `fire` + `is_sup` direction guards, identical to the push validation guards. This prevents stale `var string hi_txt/lo_txt` values from triggering false resets on non-fire bars.

- [ ] **Step 2: Add count increment in zone creation**

In the zone creation block (`if fire and (time - z_time) < max_ms and valid`), BEFORE the `box.new()` call, add:

```pine
        // Count increment
        if is_sup
            new_sup_count += 1
        else
            new_dem_count += 1
        int cnum = is_sup ? new_sup_count : new_dem_count
```

Update the `Zone.new()` call to include `count_num`:

```pine
        zones.push(Zone.new(ztop, zbot, is_sup, z_time, new_box, false, false, "", cls, cnum, false))
```

Note: `cnum` is the 10th positional arg (`count_num`), `false` is the 11th (`is_terminal`).

- [ ] **Step 3: Update normal zone labels to include count number**

Replace the normal zone label line:

```pine
        string lbl_txt = i_normal and i_labels ? tf_label(tf_str) + (is_sup ? " S " : " D ") + cls : na
```

With:

```pine
        string cnt_str = parent_zones.size() > 0 ? " #" + str.tostring(cnum) : ""
        string lbl_txt = i_normal and i_labels ? tf_label(tf_str) + (is_sup ? " S" : " D") + cnt_str : na
```

When the parent TF is disabled (empty parent array), no count is shown — just TF and side.

- [ ] **Step 4: Update push zone labels to include count number**

In the bearish push validation block, update the push label:

```pine
                        string cnt_pfx = z.count_num > 0 ? " #" + str.tostring(z.count_num) : ""
                        string suffix = scls == "BOS" ? " ▼ BOS" : scls == "CHoCH" ? " ◆ CHoCH" : ""
                        string ptxt = i_labels ? tf_label(tf_str) + " S" + cnt_pfx + " LL" + suffix : na
```

In the bullish push validation block, same pattern:

```pine
                        string cnt_pfx = z.count_num > 0 ? " #" + str.tostring(z.count_num) : ""
                        string suffix = scls == "BOS" ? " ▲ BOS" : scls == "CHoCH" ? " ◆ CHoCH" : ""
                        string ptxt = i_labels ? tf_label(tf_str) + " D" + cnt_pfx + " HH" + suffix : na
```

In the reversal label blocks, same:

```pine
                        string cnt_pfx = z.count_num > 0 ? " #" + str.tostring(z.count_num) : ""
                        string rtxt = i_labels ? tf_label(tf_str) + " D" + cnt_pfx + " REV ⚐" : na
```

And for supply reversal:

```pine
                        string cnt_pfx = z.count_num > 0 ? " #" + str.tostring(z.count_num) : ""
                        string rtxt = i_labels ? tf_label(tf_str) + " S" + cnt_pfx + " REV ⚐" : na
```

- [ ] **Step 5: Verify compilation and zone counting**

Paste in TradingView. Enable H1/H4/D timeframes. Zones should now show count numbers in their labels: `H1 S #1`, `H1 S #2 LL ▼ BOS`, etc. When an H4 zone fires, H1 counts should reset. When H1 makes a new HH, H1 supply count should reset.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "feat(push-zones-v2): implement zone counting with dual reset triggers"
```

---

### Task 4: Implement Zone Nesting Detection

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones_v2.pine` (S6 process method)

**Context:** This task adds nesting detection after push/reversal/BOS-CHoCH classification. For each new zone, check if it's fully contained inside a parent zone. Classify same vs opposing direction. Apply terminal styling for opposing nesting. Update labels with nesting context. The data flow order inside process() is: expire/break → create → push → reversal → BOS/CHoCH → **nesting** → label finalization.

- [ ] **Step 1: Add nesting detection after push/reversal/BOS-CHoCH section**

After the `new_push_hi := seq_hh_val` line (end of bullish push block), add the nesting detection section. This runs on fire bars when a new zone was just created:

```pine
    // 7. Nesting check — does the new zone sit inside a parent zone?
    string nest_ctx = ""
    if fire and valid and parent_zones.size() > 0
        Zone child = zones.get(zones.size() - 1)
        float best_range = 1e18
        int   best_idx   = -1
        for i = 0 to parent_zones.size() - 1
            Zone p = parent_zones.get(i)
            if child.top <= p.top and child.bottom >= p.bottom
                float pr = p.top - p.bottom
                if pr < best_range
                    best_range := pr
                    best_idx   := i
        if best_idx >= 0
            Zone bp = parent_zones.get(best_idx)
            string ptf = tf_label(tf_parent(tf_str))
            string pside = bp.is_supply ? "S" : "D"
            string pcls = bp.is_push and bp.struct_cls != "" ? " " + bp.struct_cls : ""
            nest_ctx := "(in " + ptf + " " + pside + pcls + ")"
            // Opposing direction = terminal
            bool opposing = child.is_supply != bp.is_supply
            if opposing
                child.is_terminal := true
                if not na(child.bx)
                    child.bx.set_bgcolor(i_term_bg)
                    child.bx.set_border_color(i_term_br)
```

- [ ] **Step 2: Add label finalization pass**

After the nesting check, add a label finalization block that rebuilds the label for the newly created zone with all context (count, push/rev, BOS/CHoCH, nesting):

```pine
    // 9. Label finalization — rebuild label with all classifications
    if fire and valid and zones.size() > 0 and i_labels
        Zone latest = zones.get(zones.size() - 1)
        string side_str = latest.is_supply ? " S" : " D"
        string cnt_str = latest.count_num > 0 ? " #" + str.tostring(latest.count_num) : ""
        // Exhaustion markers
        string exh_str = latest.count_num == 5 ? " ⚠" : (latest.count_num >= 8 and not latest.is_terminal) ? " ✕" : ""
        string role_str = ""
        if latest.is_push
            string swing = latest.is_supply ? " LL" : " HH"
            string struct_sfx = ""
            if latest.struct_cls == "BOS"
                struct_sfx := latest.is_supply ? " ▼ BOS" : " ▲ BOS"
            else if latest.struct_cls == "CHoCH"
                struct_sfx := " ◆ CHoCH"
            role_str := swing + struct_sfx
        else if latest.is_reversal
            role_str := " REV ⚐"
        else if latest.is_terminal
            role_str := " ✕"
        string nest_str = nest_ctx != "" ? " " + nest_ctx : ""
        string final_lbl = tf_label(tf_str) + side_str + cnt_str + exh_str + role_str + nest_str
        // Only show label if zone is visible (push, reversal, terminal, or normal toggle on)
        bool visible = latest.is_push or latest.is_reversal or latest.is_terminal or i_normal
        if visible and not na(latest.bx)
            latest.bx.set_text(final_lbl)
        else if not visible and not na(latest.bx)
            latest.bx.set_text(na)
```

- [ ] **Step 3: Remove inline label setting from zone creation and push/reversal blocks**

Now that labels are set in the finalization pass, remove the inline label text setting from:

1. **Zone creation block:** Change `text = lbl_txt` in `box.new()` to `text = na` (labels set in finalization pass). Remove the `lbl_txt` variable.

2. **Bearish push block:** Remove the `string ptxt = ...` and `z.bx.set_text(ptxt)` lines. Keep only the visual styling (bgcolor, border_color, border_width).

3. **Bullish push block:** Same — remove ptxt/set_text lines, keep styling.

4. **Both reversal blocks:** Same — remove rtxt/set_text lines, keep styling.

The finalization pass handles ALL label rendering.

- [ ] **Step 4: Add optional nesting lines**

After the nesting check, if `i_nest_lines` is enabled and nesting was detected:

```pine
    // Optional nesting connector lines
    if fire and valid and nest_ctx != "" and i_nest_lines
        Zone child = zones.get(zones.size() - 1)
        color ln_clr = child.is_terminal ? i_term_br : (child.is_supply ? i_sup_br : i_dem_br)
        line.new(child.origin_time, child.top, child.origin_time, child.top + (child.top - child.bottom) * 0.5, xloc = xloc.bar_time, color = ln_clr, width = 1, style = line.style_dotted)
```

- [ ] **Step 5: Verify compilation and nesting detection**

Paste in TradingView. Enable H1/H4/D. Look for H1 zones that sit inside H4 or D zones. They should show nesting context in their labels: `H1 S #3 (in H4 S)`. Opposing-nested zones should appear in purple. Enable "Show Nesting Lines" to verify connector lines appear.

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "feat(push-zones-v2): implement zone nesting detection with terminal classification"
```

---

### Task 5: Update Dashboard with Count Columns

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones_v2.pine` (S10 dashboard)

**Context:** This task updates the dashboard from 4 columns to 6, adding #S (supply unbroken count) and #D (demand unbroken count) columns with color coding for exhaustion.

- [ ] **Step 1: Create unbroken count helper**

Add a helper function before the dashboard section:

```pine
unbroken_count(array<Zone> zones, bool is_supply, int reset_time) =>
    int cnt = 0
    if zones.size() > 0
        for i = 0 to zones.size() - 1
            Zone z = zones.get(i)
            if z.is_supply == is_supply and z.origin_time >= reset_time
                cnt += 1
    cnt
```

- [ ] **Step 2: Update dash_row() signature and body**

Replace the existing `dash_row()` function:

```pine
dash_row(table tbl, int row_num, string tf_str, int trend_val, array<Zone> zones, int sup_rst, int dem_rst, bool has_parent) =>
    string trend_txt = trend_val == 1 ? "BULL" : trend_val == -1 ? "BEAR" : "—"
    color  trend_clr = trend_val == 1 ? color.green : trend_val == -1 ? color.red : color.gray
    int sc = 0
    int dc = 0
    string push_txt = "—"
    if zones.size() > 0
        for i = 0 to zones.size() - 1
            Zone z = zones.get(i)
            if z.is_supply
                sc += 1
            else
                dc += 1
            if z.is_push
                string side = z.is_supply ? "S" : "D"
                string swing = z.is_supply ? " LL" : " HH"
                string suffix = z.struct_cls == "BOS" ? " BOS" : z.struct_cls == "CHoCH" ? " CHoCH" : ""
                push_txt := side + swing + suffix
    int ub_s = unbroken_count(zones, true, sup_rst)
    int ub_d = unbroken_count(zones, false, dem_rst)
    color s_clr = ub_s >= 8 ? color.red : ub_s >= 5 ? color.yellow : color.white
    color d_clr = ub_d >= 8 ? color.red : ub_d >= 5 ? color.yellow : color.white
    string s_txt = has_parent ? str.tostring(ub_s) : "—"
    string d_txt = has_parent ? str.tostring(ub_d) : "—"
    table.cell(tbl, 0, row_num, tf_label(tf_str), text_size = size.tiny, text_color = color.white)
    table.cell(tbl, 1, row_num, trend_txt,          text_size = size.tiny, text_color = trend_clr)
    table.cell(tbl, 2, row_num, push_txt,            text_size = size.tiny, text_color = color.yellow)
    table.cell(tbl, 3, row_num, s_txt,               text_size = size.tiny, text_color = s_clr)
    table.cell(tbl, 4, row_num, d_txt,               text_size = size.tiny, text_color = d_clr)
    table.cell(tbl, 5, row_num, str.tostring(sc) + "S " + str.tostring(dc) + "D", text_size = size.tiny, text_color = color.white)
    row_num + 1
```

- [ ] **Step 3: Update table.new() to 6 columns and add header cells**

Update the `table.new()` call:

```pine
        var table dash = table.new(dash_position(i_dash_pos), 6, tf_count + 1, bgcolor = color.new(#1a1a2e, 10), border_color = color.new(#ffffff, 80), border_width = 1, frame_color = color.new(#ffffff, 80), frame_width = 1)
        table.cell(dash, 0, 0, "TF",    text_size = size.tiny, text_color = color.white)
        table.cell(dash, 1, 0, "Trend",  text_size = size.tiny, text_color = color.white)
        table.cell(dash, 2, 0, "Push",   text_size = size.tiny, text_color = color.white)
        table.cell(dash, 3, 0, "#S",     text_size = size.tiny, text_color = color.white)
        table.cell(dash, 4, 0, "#D",     text_size = size.tiny, text_color = color.white)
        table.cell(dash, 5, 0, "Zones",  text_size = size.tiny, text_color = color.white)
```

- [ ] **Step 4: Update all dash_row() calls to pass reset times**

Each `dash_row()` call must now pass the supply and demand reset times:

```pine
        if i_tf7_on
            row := dash_row(dash, row, i_tf7, trend7, zones7, srt7, drt7, false)
        if i_tf6_on
            row := dash_row(dash, row, i_tf6, trend6, zones6, srt6, drt6, i_tf7_on)
        if i_tf5_on
            row := dash_row(dash, row, i_tf5, trend5, zones5, srt5, drt5, i_tf6_on)
        if i_tf4_on
            row := dash_row(dash, row, i_tf4, trend4, zones4, srt4, drt4, i_tf5_on)
        if i_tf3_on
            row := dash_row(dash, row, i_tf3, trend3, zones3, srt3, drt3, i_tf4_on)
        if i_tf2_on
            row := dash_row(dash, row, i_tf2, trend2, zones2, srt2, drt2, i_tf3_on)
        if i_tf1_on
            row := dash_row(dash, row, i_tf1, trend1, zones1, srt1, drt1, i_tf3_on)
        if i_tf0_on
            row := dash_row(dash, row, i_tf0, trend0, zones0, srt0, drt0, i_tf2_on)
```

Note: Dashboard rows also in HIGH→LOW order for consistency.

- [ ] **Step 5: Verify compilation and dashboard**

Paste in TradingView. Dashboard should now show 6 columns with #S and #D counts. Counts should turn yellow at 5, red at 8. When parent TF is disabled, count columns show "—".

- [ ] **Step 6: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "feat(push-zones-v2): update dashboard with unbroken count columns (#S, #D)"
```

---

### Task 6: Final Cleanup and Visual Verification

**Files:**
- Modify: `tw_indicators/iora_zones/iora_push_zones_v2.pine`

**Context:** Final pass to clean up any redundant code, verify all label formats match the spec, and ensure the indicator works correctly across different TF configurations.

- [ ] **Step 1: Verify label format matches spec**

Cross-check these label formats in TradingView:

| Zone State | Expected Label |
|------------|---------------|
| Normal supply #3 | `H1 S #3` (only if Show Normal Zones on) |
| Push supply BOS | `H1 S #4 LL ▼ BOS` |
| Push demand CHoCH | `H4 D #1 HH ◆ CHoCH` |
| Reversal demand | `H1 D #3 REV ⚐` |
| Nested (same dir) | `H1 S #3 (in H4 S)` |
| Nested push | `H1 S #5 LL ▼ BOS (in H4 S CHoCH)` |
| Terminal (opposing) | `H1 S #8 ✕ (in H4 D)` |
| Exhaustion at 5 | `H1 S #5 ⚠` |

If unicode characters don't render in TradingView, replace with plain text alternatives: `▼`→`v`, `▲`→`^`, `◆`→`*`, `⚐`→`F`, `⚠`→`!`, `✕`→`X`.

- [ ] **Step 2: Test edge cases**

1. **Only one TF enabled (e.g., D only):** No counting, no nesting — zones appear as in v1 with no count numbers.
2. **All 8 TFs enabled:** Should compile and run. Verify parent-child wiring across the full chain.
3. **M5 and M15 both enabled (shared H1 parent):** Both should count independently against H1.
4. **Parent disabled (H4 off, H1 on):** H1 zones should show no count numbers and "—" in dashboard.

- [ ] **Step 3: Remove any dead code**

Check for:
- Unused variables from v1 that were replaced
- Redundant label-setting code that should have been removed in Task 4
- Any `cnt_str` or `lbl_txt` variables that are now handled by the finalization pass

- [ ] **Step 4: Commit**

```bash
git add tw_indicators/iora_zones/iora_push_zones_v2.pine
git commit -m "fix(push-zones-v2): cleanup and verify label formats"
```
