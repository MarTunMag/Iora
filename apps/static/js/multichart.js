/**
 * multichart.js — Flexible multi-timeframe chart grid (2, 3, or 4 panels).
 *
 * Creates independent LW Charts instances, each showing a different TF
 * for the same symbol. Supports 2-panel (side-by-side), 3-panel (row),
 * and 4-panel (2x2 grid) layouts via presets.
 * Each panel has its own overlay toggle buttons (Z=zones, T=trendlines, B=BOS).
 * Preset dropdown for quick TF configurations.
 * Crosshair sync: time-locked across panels with toggle.
 * Focused panel concept: one panel is "active" for drawing at a time.
 * Per-panel mini-sidebar for overlay configuration.
 */

const DEBUG_MC = false;

// TF list — derived from server config, with fallback
function _getMcAllTFs() {
    return (App.config && App.config.tf_order_htf_first) || ['MN1', 'W1', 'D1', 'H4', 'H1', 'M15', 'M5', 'M1'];
}

const MultiChart = {
    enabled: false,
    charts: [],        // Array of { chart, series, tf, container, overlays, label, tfSelect, drawings, undoStack, _drawPrimitives } objects
    _containers: null, // The grid wrapper element
    _syncCrosshair: true, // Crosshair sync enabled by default
    _syncing: false,      // Guard to prevent recursive sync

    // Focused panel for drawing
    _focusedIdx: 0,

    // Request sequence counter — discard stale responses on rapid preset switches
    _requestSeq: 0,

    // Replay state
    _replayActive: false,     // true when not at live/end
    _replayTime: Infinity,    // global unix timestamp cursor
    _drivingIdx: -1,          // index of driving (lowest TF) panel

    // TF rank for determining driving panel (lowest = finest granularity)
    _tfRank: { M1: 0, M5: 1, M15: 2, M30: 3, H1: 4, H4: 5, D1: 6, W1: 7, MN1: 8 },

    // Larger right offsets for multichart panels (each panel is ~half width)
    _rightOffset: { M1: 280, M5: 60, M15: 24, M30: 16, H1: 20, H4: 12, D1: 8, W1: 6, MN1: 4 },

    // Per-TF bar spacing: HTFs get tighter spacing so more candles fit in half-width panels
    _barSpacing: { MN1: 3, W1: 3, D1: 3, H4: 3, H1: 4, M30: 4, M15: 5, M5: 5, M1: 5 },

    // Default TFs for multichart panels (supports 2, 3, or 4 panels)
    defaultTFs: ['M15', 'M1'],

    // Preset configurations — variable panel counts (2, 3, or 4)
    presets: {
        // ── 4-panel cascading (each shifts one TF down) ──
        'Macro':     ['MN1', 'W1', 'D1', 'H4'],
        'Swing':     ['W1',  'D1', 'H4', 'H1'],
        'Intraday':  ['D1',  'H4', 'H1', 'M15'],
        'Scalp':     ['H4',  'H1', 'M15', 'M5'],
        'Micro':     ['H1',  'M15', 'M5', 'M1'],
        // ── 4-panel specialty (skip TFs for specific workflows) ──
        'Execution': ['H4',  'H1', 'M5', 'M1'],
        'Entry':     ['H4',  'H1', 'M15', 'M1'],
        'Overview':  ['D1',  'H1', 'M5', 'M1'],
        // ── 3-panel triple views ──
        'Triple Swing':  ['D1', 'H4', 'H1'],
        'Triple Scalp':  ['H4', 'M15', 'M1'],
        'Triple Micro':  ['H1', 'M5',  'M1'],
        'Triple Entry':  ['H4', 'H1',  'M1'],
        'Triple H1-M15-M5':  ['H1', 'M15', 'M5'],
        'Triple H1-M15-M1':  ['H1', 'M15', 'M1'],
        // ── 2-panel focus views ──
        'Focus H1+M1':   ['H1',  'M1'],
        'Focus H4+M15':  ['H4',  'M15'],
        'Focus H1+M5':   ['H1',  'M5'],
        'Focus H1+M15':  ['H1',  'M15'],
        'Focus D1+H1':   ['D1',  'H1'],
        'Focus H4+M1':   ['H4',  'M1'],
        'Focus M15+M1':  ['M15', 'M1'],
        'Focus M15+M5':  ['M15', 'M5'],
    },

    // For each panel TF, which zone TFs to show (last zone per TF)
    _htfMap: {
        MN1: ['MN1'],
        W1:  ['MN1', 'W1'],
        D1:  ['W1', 'D1'],
        H4:  ['D1', 'H4'],
        H1:  ['D1', 'H4', 'H1'],
        M15: ['D1', 'H4', 'H1', 'M15'],
        M5:  ['D1', 'H4', 'H1', 'M15', 'M5'],
        M1:  ['D1', 'H4', 'H1', 'M15', 'M5', 'M1'],
    },

    // HTF candle overlays per panel TF (one level up for context)
    _htfCandleMap: {
        MN1: ['3M', '6M', '12M'],
        W1:  ['MN1'],
        D1:  ['W1'],
        H4:  ['D1'],
        H1:  ['D1'],
        M30: ['D1', 'H4'],
        M15: ['W1', 'D1'],
        M5:  ['H1'],
        M1:  ['D1', 'H4'],
    },

    // ── Focused panel API (for Drawing.js) ──

    /** Get chart instance of focused panel */
    getFocusedChart() {
        const entry = this.charts[this._focusedIdx];
        return entry ? entry.chart : null;
    },

    /** Get series of focused panel */
    getFocusedSeries() {
        const entry = this.charts[this._focusedIdx];
        return entry ? entry.series : null;
    },

    /** Get container element of focused panel */
    getFocusedContainer() {
        const entry = this.charts[this._focusedIdx];
        return entry ? entry.container : null;
    },

    /** Get full entry of focused panel */
    getFocusedEntry() {
        return this.charts[this._focusedIdx] || null;
    },

    /** Find panel index from a container element */
    _panelIndexFromContainer(container) {
        for (let i = 0; i < this.charts.length; i++) {
            if (this.charts[i].container === container) return i;
        }
        return -1;
    },

    /** Set focus to a specific panel */
    setFocus(idx) {
        if (idx < 0 || idx >= this.charts.length) return;
        this._focusedIdx = idx;
        this._updateFocusIndicator();
        Drawing._updateFocusIndicator();
    },

    /** Update visual focus indicator on panels */
    _updateFocusIndicator() {
        this.charts.forEach((entry, i) => {
            const isFocused = (i === this._focusedIdx);
            const isDriving = (i === this._drivingIdx);
            // Focused panel: green left border. Driving panel: blue outline.
            if (isFocused) {
                entry.container.style.borderLeft = `2px solid ${UI.FOCUS_GREEN}`;
            } else {
                entry.container.style.borderLeft = '2px solid transparent';
            }
            entry.container.style.outline = isDriving ? `1px solid ${UI.ACCENT}` : 'none';
            entry.container.style.outlineOffset = '-1px';
            // TF label suffix
            const suffix = isDriving ? ' \u25B6' : '';
            entry.label.textContent = entry.tf + suffix;
        });
    },

    toggle() {
        this.enabled = !this.enabled;
        const mainChart = document.getElementById('chart-container');
        const btn = document.getElementById('multichart-btn');
        const sidebar = document.getElementById('sidebar');

        if (this.enabled) {
            OverlayState.activeMode = 'multichart';
            mainChart.style.display = 'none';
            if (sidebar) sidebar.style.display = 'none';
            this._createGrid();
            this._loadAll();
            if (btn) btn.classList.add('active');
        } else {
            OverlayState.activeMode = 'single';
            mainChart.style.display = '';
            if (sidebar) sidebar.style.display = '';
            this._destroyGrid();
            if (btn) btn.classList.remove('active');
            Drawing._updateFocusIndicator();
        }
    },

    /** Build default overlay config — zones only, 1 per TF, clean start */
    _buildDefaultOverlayConfig(tf) {
        const allTFs = _getMcAllTFs();
        const zoneDefs = this._htfMap[tf] || [tf];
        const htfDefs = this._htfCandleMap[tf] || [];

        const config = { zones: {}, trendlines: {}, htfCandles: {}, signals: {} };
        allTFs.forEach(t => {
            config.zones[t]      = { on: zoneDefs.includes(t), count: 1 };
            config.trendlines[t] = { on: false, count: 0 };
            config.htfCandles[t] = { on: htfDefs.includes(t) };
            config.signals[t]    = { on: false };
        });
        return config;
    },

    /** Apply a preset — rebuilds grid if panel count changed, otherwise just swaps TFs */
    applyPreset(name) {
        const tfs = this.presets[name];
        if (!tfs || tfs.length < 2 || tfs.length > 4) return;

        if (tfs.length === this.charts.length) {
            // Same panel count — just swap TFs in place
            this.charts.forEach((entry, i) => {
                const newTf = tfs[i];
                entry.tf = newTf;
                if (entry.label) entry.label.textContent = newTf;
                if (entry.tfSelect) entry.tfSelect.value = newTf;
                entry.overlayConfig = this._buildDefaultOverlayConfig(newTf);
            });
            this._loadAll();
        } else {
            // Different panel count — rebuild the grid
            this.defaultTFs = tfs;
            this._destroyGrid();
            this._createGrid();
            this._loadAll();
            // Re-select the preset in the dropdown (rebuilt by _createGrid)
            if (this._presetSelect) this._presetSelect.value = name;
        }
    },

    _createGrid() {
        if (this._containers) return;

        const parent = document.getElementById('main');
        const grid = document.createElement('div');
        grid.id = 'multichart-grid';
        const panelCount = this.defaultTFs.length;
        const gridCSS = panelCount <= 2
            ? 'grid-template-columns: 1fr 1fr; grid-template-rows: 1fr;'
            : panelCount === 3
                ? 'grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr;'
                : 'grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;';
        grid.style.cssText = `
            flex: 1;
            display: grid;
            ${gridCSS}
            gap: 1px;
            background: #222;
            position: relative;
        `;

        // ── Top toolbar: preset dropdown + sync toggle ──
        const toolbar = document.createElement('div');
        toolbar.style.cssText = `
            position: absolute; top: -24px; left: 0; right: 0; z-index: 20;
            display: flex; gap: 6px; align-items: center; padding: 2px 8px;
            background: #111; border-bottom: 1px solid #222; height: 22px;
        `;

        // Preset dropdown
        const presetLabel = document.createElement('span');
        presetLabel.textContent = 'Preset:';
        presetLabel.style.cssText = 'font-size: 10px; color: #666;';
        toolbar.appendChild(presetLabel);

        const presetSel = document.createElement('select');
        presetSel.style.cssText = `
            font-size: 10px; padding: 1px 4px; background: #1a1a24;
            color: #90caf9; border: 1px solid #333; border-radius: 2px;
        `;
        // "Custom" option when user manually picks TFs
        const customOpt = document.createElement('option');
        customOpt.value = ''; customOpt.textContent = 'Custom';
        presetSel.appendChild(customOpt);

        const cascading = ['Macro', 'Swing', 'Intraday', 'Scalp', 'Micro'];
        const specialty = ['Execution', 'Entry', 'Overview'];
        const triple   = ['Triple Swing', 'Triple Scalp', 'Triple Micro', 'Triple Entry'];
        const focus    = ['Focus M15+M1', 'Focus M15+M5', 'Focus H1+M1', 'Focus H1+M5', 'Focus H1+M15', 'Focus H4+M15', 'Focus H4+M1', 'Focus D1+H1'];

        const addGroup = (label, names) => {
            const grp = document.createElement('optgroup');
            grp.label = label;
            names.forEach(name => {
                const tfs = this.presets[name];
                if (!tfs) return;
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = `${name} (${tfs.join(' / ')})`;
                if (tfs.length === this.defaultTFs.length && tfs.every((tf, i) => tf === this.defaultTFs[i])) opt.selected = true;
                grp.appendChild(opt);
            });
            presetSel.appendChild(grp);
        };

        addGroup('4-Panel Cascade', cascading);
        addGroup('4-Panel Specialty', specialty);
        addGroup('3-Panel', triple);
        addGroup('2-Panel Focus', focus);
        presetSel.addEventListener('change', (e) => {
            if (e.target.value) this.applyPreset(e.target.value);
        });
        toolbar.appendChild(presetSel);
        this._presetSelect = presetSel;

        // Separator
        const sep = document.createElement('div');
        sep.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep);

        // Crosshair sync toggle
        const syncBtn = document.createElement('button');
        syncBtn.textContent = 'Sync';
        syncBtn.title = 'Toggle crosshair sync across panels';
        syncBtn.style.cssText = `
            font-size: 9px; padding: 1px 6px; background: #1a3a6a;
            color: #90caf9; border: 1px solid #448aff;
            border-radius: 2px; cursor: pointer; line-height: 14px;
        `;
        syncBtn.addEventListener('click', () => {
            this._syncCrosshair = !this._syncCrosshair;
            syncBtn.style.background = this._syncCrosshair ? UI.ACCENT_BG : UI.PANEL_BG;
            syncBtn.style.color = this._syncCrosshair ? UI.ACCENT_TEXT : UI.TEXT_DIM;
            syncBtn.style.borderColor = this._syncCrosshair ? UI.ACCENT : UI.BORDER;
            // Clear crosshairs on all panels when disabling
            if (!this._syncCrosshair) {
                this.charts.forEach(entry => {
                    entry.chart.setCrosshairPosition(undefined, undefined, entry.series);
                });
            }
        });
        toolbar.appendChild(syncBtn);

        // Separator
        const sep2 = document.createElement('div');
        sep2.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep2);

        // "HTF Struct" button — enables zones+TLs+BOS for 2 levels above on ALL panels
        const htfBtn = document.createElement('button');
        htfBtn.textContent = 'HTF Struct';
        htfBtn.title = 'Enable HTF structure (zones + TLs + BOS) 2 levels above each panel';
        htfBtn.style.cssText = `
            font-size: 9px; padding: 1px 6px; background: #1a1a24;
            color: #666; border: 1px solid #333;
            border-radius: 2px; cursor: pointer; line-height: 14px;
        `;
        let htfStructActive = false;
        htfBtn.addEventListener('click', () => {
            htfStructActive = !htfStructActive;
            htfBtn.style.background = htfStructActive ? UI.ACCENT_BG : UI.PANEL_BG;
            htfBtn.style.color = htfStructActive ? UI.ACCENT_TEXT : UI.TEXT_DIM;
            htfBtn.style.borderColor = htfStructActive ? UI.ACCENT : UI.BORDER;

            this.charts.forEach((entry, i) => {
                const tfIdx = _getMcAllTFs().indexOf(entry.tf);
                const oc = entry.overlayConfig;
                if (htfStructActive) {
                    // Enable own TF + 2 levels above for zones and TLs
                    ['zones', 'trendlines'].forEach(key => {
                        _getMcAllTFs().forEach((t, tIdx) => {
                            if (!oc[key][t]) oc[key][t] = { on: false, count: 2 };
                            if (tIdx >= tfIdx - 2 && tIdx <= tfIdx) {
                                oc[key][t].on = true;
                            }
                        });
                    });
                    // BOS/CHoCH breaks are controlled globally via Structure module
                    Structure.setBreaksEnabled(true);
                } else {
                    // Reset to defaults
                    entry.overlayConfig = this._buildDefaultOverlayConfig(entry.tf);
                }
                this._renderOverlays(i);
            });
            // Reset breaks when toggling off
            if (!htfStructActive) Structure.setBreaksEnabled(false);
        });
        toolbar.appendChild(htfBtn);

        // Separator
        const sep3 = document.createElement('div');
        sep3.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep3);

        // Symbol selector (mirrors sidebar)
        const symLabel = document.createElement('span');
        symLabel.textContent = 'Sym:';
        symLabel.style.cssText = 'font-size: 10px; color: #666;';
        toolbar.appendChild(symLabel);

        const symSel = document.createElement('select');
        symSel.style.cssText = `
            font-size: 10px; padding: 1px 4px; background: #1a1a24;
            color: #ccc; border: 1px solid #333; border-radius: 2px; max-width: 80px;
        `;
        App.symbols.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            if (s === App.symbol) opt.selected = true;
            symSel.appendChild(opt);
        });
        symSel.addEventListener('change', () => {
            App.symbol = symSel.value;
            // Sync sidebar symbol selector
            const sidebarSym = document.getElementById('symbol-select');
            if (sidebarSym) sidebarSym.value = symSel.value;
            this.reload();
        });
        toolbar.appendChild(symSel);
        this._symSelect = symSel;

        // Separator
        const sep4 = document.createElement('div');
        sep4.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep4);

        // End date nav (◀ date ▶)
        const dateBack = document.createElement('button');
        dateBack.textContent = '\u25C0';
        dateBack.title = 'Back in time';
        dateBack.style.cssText = 'font-size: 9px; padding: 1px 4px; background: #1a1a24; color: #90caf9; border: 1px solid #333; border-radius: 2px; cursor: pointer; line-height: 14px;';
        dateBack.addEventListener('click', () => {
            document.getElementById('date-back').click();
            // Sync our display after App updates
            setTimeout(() => { if (this._dateDisplay) this._dateDisplay.value = App.endDate; }, 50);
        });
        toolbar.appendChild(dateBack);

        const dateInput = document.createElement('input');
        dateInput.type = 'date';
        dateInput.value = App.endDate;
        dateInput.style.cssText = 'font-size: 10px; color: #90caf9; background: #1a1a24; border: 1px solid #333; border-radius: 2px; padding: 0 4px; min-width: 100px; text-align: center; cursor: pointer; height: 18px; color-scheme: dark;';
        dateInput.addEventListener('change', (e) => {
            App.endDate = e.target.value;
            document.getElementById('end-date').value = e.target.value;
            if (this.enabled) {
                this._loadAll();
            } else {
                App.loadData();
            }
        });
        toolbar.appendChild(dateInput);
        this._dateDisplay = dateInput;

        const dateFwd = document.createElement('button');
        dateFwd.textContent = '\u25B6';
        dateFwd.title = 'Forward in time';
        dateFwd.style.cssText = 'font-size: 9px; padding: 1px 4px; background: #1a1a24; color: #90caf9; border: 1px solid #333; border-radius: 2px; cursor: pointer; line-height: 14px;';
        dateFwd.addEventListener('click', () => {
            document.getElementById('date-fwd').click();
            setTimeout(() => { if (this._dateDisplay) this._dateDisplay.value = App.endDate; }, 50);
        });
        toolbar.appendChild(dateFwd);

        // Separator
        const sep5 = document.createElement('div');
        sep5.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep5);

        // HTF candle type (OHLC/HA)
        const htfTypeLabel = document.createElement('span');
        htfTypeLabel.textContent = 'HTF:';
        htfTypeLabel.style.cssText = 'font-size: 10px; color: #666;';
        toolbar.appendChild(htfTypeLabel);

        const htfTypeSel = document.createElement('select');
        htfTypeSel.style.cssText = `
            font-size: 10px; padding: 1px 4px; background: #1a1a24;
            color: #ccc; border: 1px solid #333; border-radius: 2px;
        `;
        [['ohlc', 'OHLC'], ['ha', 'HA']].forEach(([val, txt]) => {
            const opt = document.createElement('option');
            opt.value = val; opt.textContent = txt;
            if (val === (App.htfCandleType || 'ohlc')) opt.selected = true;
            htfTypeSel.appendChild(opt);
        });
        htfTypeSel.addEventListener('change', () => {
            App.htfCandleType = htfTypeSel.value;
            // Sync sidebar HTF type selector
            const sidebarHtf = document.getElementById('htf-candle-type');
            if (sidebarHtf) sidebarHtf.value = htfTypeSel.value;
            this.reload();
        });
        toolbar.appendChild(htfTypeSel);

        // Separator
        const sep6 = document.createElement('div');
        sep6.style.cssText = 'width: 1px; height: 14px; background: #333; margin: 0 4px;';
        toolbar.appendChild(sep6);

        // Signal toggles — each can be shown/hidden independently
        const sigLabel = document.createElement('span');
        sigLabel.textContent = 'Signals:';
        sigLabel.style.cssText = 'font-size: 10px; color: #666;';
        toolbar.appendChild(sigLabel);

        // Initialize global signal toggle state
        if (!this._signalToggles) {
            this._signalToggles = {
                zoneNumbers: true,    // #N zone chain count
                nesting: true,        // @parent nesting
                tlBreaks: true,       // TL break markers
                choch: true,          // CHoCH entry arrows (HL▲ / LH▼)
            };
        }
        const mkSigBtn = (label, key, title) => {
            const btn = document.createElement('button');
            btn.textContent = label;
            btn.title = title;
            const isOn = this._signalToggles[key];
            btn.style.cssText = `
                font-size: 9px; padding: 1px 5px;
                background: ${isOn ? '#1a2a1a' : '#1a1a24'};
                color: ${isOn ? '#66ff66' : '#666'};
                border: 1px solid ${isOn ? '#448a44' : '#333'};
                border-radius: 2px; cursor: pointer; line-height: 14px;
            `;
            btn.addEventListener('click', () => {
                this._signalToggles[key] = !this._signalToggles[key];
                const on = this._signalToggles[key];
                btn.style.background = on ? '#1a2a1a' : '#1a1a24';
                btn.style.color = on ? '#66ff66' : '#666';
                btn.style.borderColor = on ? '#448a44' : '#333';
                // Re-render overlays on all panels
                this.charts.forEach((_, idx) => this._renderOverlays(idx));
            });
            return btn;
        };
        toolbar.appendChild(mkSigBtn('#', 'zoneNumbers', 'Zone chain numbers (5+3 exhaustion)'));
        toolbar.appendChild(mkSigBtn('N', 'nesting', 'Nesting highlights (child @ parent)'));
        toolbar.appendChild(mkSigBtn('✕', 'tlBreaks', 'TL break markers'));
        toolbar.appendChild(mkSigBtn('▲▼', 'choch', 'CHoCH entry signals (HL▲ buy / LH▼ sell)'));

        grid.appendChild(toolbar);

        // ── Create chart panels (2, 3, or 4 depending on preset) ──
        this.charts = [];
        this.defaultTFs.forEach((tf, i) => {
            const cell = document.createElement('div');
            cell.style.cssText = `position: relative; background: ${BG_COLOR}; overflow: hidden; border-left: 2px solid transparent;`;

            // TF label
            const label = document.createElement('div');
            label.style.cssText = `
                position: absolute; top: 4px; left: 8px; z-index: 10;
                font-size: 13px; font-weight: 700; color: #90caf9;
                pointer-events: none; opacity: 0.7;
            `;
            label.textContent = tf;
            label.className = 'mc-label';
            cell.appendChild(label);

            // Controls bar (right side): TF selector + overlay toggles
            const controls = document.createElement('div');
            controls.style.cssText = `
                position: absolute; top: 4px; right: 8px; z-index: 10;
                display: flex; gap: 3px; align-items: center;
            `;

            // Initialize overlay state from single-chart sidebar state
            const panelInit = OverlayState.buildPanelFromSingle(tf, this._htfMap, this._htfCandleMap);
            const overlayState = panelInit.overlays;
            const overlayConfig = panelInit.overlayConfig;

            const mkBtn = (text, key, defaultOn) => {
                const b = document.createElement('button');
                b.textContent = text;
                b.style.cssText = `
                    font-size: 9px; padding: 1px 4px; background: ${defaultOn ? '#1a3a6a' : '#1a1a24'};
                    color: ${defaultOn ? '#90caf9' : '#666'}; border: 1px solid ${defaultOn ? '#448aff' : '#333'};
                    border-radius: 2px; cursor: pointer; line-height: 14px;
                `;
                b.addEventListener('click', () => {
                    overlayState[key] = !overlayState[key];
                    b.style.background = overlayState[key] ? UI.ACCENT_BG : UI.PANEL_BG;
                    b.style.color = overlayState[key] ? UI.ACCENT_TEXT : UI.TEXT_DIM;
                    b.style.borderColor = overlayState[key] ? UI.ACCENT : UI.BORDER;
                    this._renderOverlays(i);
                });
                return b;
            };

            // Overlay buttons — left-click toggles, right-click opens TF config popover
            const zBtn = mkBtn('Z', 'zones', overlayState.zones);
            zBtn.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const entry = this.charts[i];
                this._showTfConfig(i, zBtn, entry.overlayConfig.zones, 'Zone TFs & Counts', true);
            });
            controls.appendChild(zBtn);

            const tBtn = mkBtn('T', 'trendlines', overlayState.trendlines);
            tBtn.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const entry = this.charts[i];
                this._showTfConfig(i, tBtn, entry.overlayConfig.trendlines, 'Trendline TFs & Counts', true);
            });
            controls.appendChild(tBtn);

            // B button toggles Structure breaks (BOS/CHoCH) globally
            const bBtn = document.createElement('button');
            bBtn.textContent = 'B';
            const bInit = typeof Structure !== 'undefined' && Structure.getBreaksEnabled();
            bBtn.style.cssText = `
                font-size: 9px; padding: 1px 4px; background: ${bInit ? UI.ACCENT_BG : UI.PANEL_BG};
                color: ${bInit ? UI.ACCENT_TEXT : UI.TEXT_DIM}; border: 1px solid ${bInit ? UI.ACCENT : UI.BORDER};
                border-radius: 2px; cursor: pointer; line-height: 14px;
            `;
            bBtn.title = 'Toggle BOS/CHoCH breaks';
            bBtn.addEventListener('click', () => {
                if (typeof Structure === 'undefined') return;
                const newState = !Structure.getBreaksEnabled();
                Structure.setBreaksEnabled(newState);
                bBtn.style.background = newState ? UI.ACCENT_BG : UI.PANEL_BG;
                bBtn.style.color = newState ? UI.ACCENT_TEXT : UI.TEXT_DIM;
                bBtn.style.borderColor = newState ? UI.ACCENT : UI.BORDER;
                // Re-render structure on all panels
                this.charts.forEach((e, idx) => {
                    if (e && e.chart && e.series) {
                        Structure.render(e.chart, e.series, undefined, e.tf);
                    }
                });
            });
            controls.appendChild(bBtn);

            const hBtn = mkBtn('H', 'htfCandles', overlayState.htfCandles);
            hBtn.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const entry = this.charts[i];
                this._showTfConfig(i, hBtn, entry.overlayConfig.htfCandles, 'HTF Candle TFs', false);
            });
            controls.appendChild(hBtn);

            const sBtn = mkBtn('S', 'signals', overlayState.signals);
            sBtn.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const entry = this.charts[i];
                this._showTfConfig(i, sBtn, entry.overlayConfig.signals, 'Signal TFs', false);
            });
            controls.appendChild(sBtn);

            // Gear button for mini-sidebar
            const gearBtn = document.createElement('button');
            gearBtn.textContent = '\u2699';
            gearBtn.title = 'Panel config';
            gearBtn.style.cssText = `
                font-size: 11px; padding: 1px 4px; background: #1a1a24;
                color: #666; border: 1px solid #333;
                border-radius: 2px; cursor: pointer; line-height: 14px;
            `;
            gearBtn.addEventListener('click', () => {
                this._toggleMiniSidebar(i);
            });
            controls.appendChild(gearBtn);

            // TF selector
            const sel = document.createElement('select');
            sel.style.cssText = `
                font-size: 10px; padding: 1px 4px; background: #1a1a24;
                color: #aaa; border: 1px solid #333; border-radius: 2px;
                margin-left: 4px;
            `;
            App.tfOptions.base.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t; opt.textContent = t;
                if (t === tf) opt.selected = true;
                sel.appendChild(opt);
            });
            sel.addEventListener('change', (e) => {
                const entry = this.charts[i];
                const newTf = e.target.value;
                entry.tf = newTf;
                label.textContent = newTf;
                // Reset overlay config defaults for new TF
                entry.overlayConfig = this._buildDefaultOverlayConfig(newTf);
                this._loadOne(i);
                // Reset preset dropdown to "Custom" when manually changing
                if (this._presetSelect) this._presetSelect.value = '';
            });
            controls.appendChild(sel);

            cell.appendChild(controls);
            grid.appendChild(cell);

            // Create LW Chart
            const chart = LightweightCharts.createChart(cell, {
                layout: {
                    background: { type: 'solid', color: BG_COLOR },
                    textColor: '#555',
                    fontSize: 10,
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { visible: false },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                    vertLine: { color: CROSSHAIR_LINE_COLOR, width: 1, style: 0, labelBackgroundColor: CROSSHAIR_LABEL_BG },
                    horzLine: { color: CROSSHAIR_LINE_COLOR, width: 1, style: 0, labelBackgroundColor: CROSSHAIR_LABEL_BG },
                },
                timeScale: {
                    borderColor: UI.BORDER_DARK,
                    timeVisible: true,
                    secondsVisible: false,
                    rightOffset: MultiChart._rightOffset[tf] || 10,
                    barSpacing: MultiChart._barSpacing[tf] || 4,
                },
                rightPriceScale: {
                    borderColor: UI.BORDER_DARK,
                    scaleMargins: { top: 0.05, bottom: 0.05 },
                },
                handleScroll: { vertTouchDrag: false },
                localization: {
                    priceFormatter: (price) => {
                        if (price >= 100) return price.toFixed(2);
                        if (price >= 10) return price.toFixed(3);
                        return price.toFixed(5);
                    },
                },
            });

            const series = chart.addCandlestickSeries({
                upColor: CANDLE_COLORS.candle.up,
                downColor: CANDLE_COLORS.candle.down,
                borderUpColor: CANDLE_COLORS.candle.up,
                borderDownColor: CANDLE_COLORS.candle.down,
                wickUpColor: CANDLE_COLORS.candle.up,
                wickDownColor: CANDLE_COLORS.candle.down,
                priceFormat: { type: 'price', minMove: 0.00001 },
            });

            this.charts.push({
                chart, series, tf, container: cell,
                overlays: overlayState,
                overlayConfig,      // Per-TF visibility + counts for zones/TLs/BOS/HTF
                data: null,         // Cached API response
                _primitives: [],    // ISeriesPrimitive objects for cleanup
                label,              // DOM ref for TF label
                tfSelect: sel,      // DOM ref for TF dropdown
                sBtn,               // DOM ref for signal button (badge updates)
                gearBtn,            // DOM ref for gear button
                // Drawing storage per panel
                drawings: [],
                undoStack: [],
                _drawPrimitives: [],
                _drawCanvas: null,
                _drawCtx: null,
                _drawCanvasRO: null,
                // Mini-sidebar state
                _miniSidebar: null,
                _miniSidebarOpen: false,
                candleType: App.candleType || 'ha', // Per-panel candle type
            });

            // Bind drawing events to this panel
            Drawing._bindContainerEvents(cell);

            // Click on panel to set focus (also handled in Drawing mousedown, but for non-drawing clicks)
            cell.addEventListener('mousedown', () => {
                if (i !== this._focusedIdx) {
                    this.setFocus(i);
                }
            });

            // Double-click on panel → jump replay to that time
            cell.addEventListener('dblclick', (e) => {
                if (this._drivingIdx < 0) return;
                const ts = chart.timeScale();
                const time = ts.coordinateToTime(e.offsetX);
                if (time === null || time === undefined) return;
                // Find nearest barIdx in driving panel's candle array
                const drivingEntry = this.charts[this._drivingIdx];
                if (!drivingEntry || !drivingEntry.data) return;
                const candles = drivingEntry.data.candles;
                let nearest = 0, minDiff = Infinity;
                for (let j = 0; j < candles.length; j++) {
                    const diff = Math.abs(candles[j].time - time);
                    if (diff < minDiff) { minDiff = diff; nearest = j + 1; }
                }
                Replay.jumpTo(nearest);
            });
        });

        // Insert grid before replay bar (with margin-top for toolbar)
        const replayBar = document.getElementById('replay-bar');
        grid.style.marginTop = '24px';
        parent.insertBefore(grid, replayBar);
        this._containers = grid;

        // Set initial focus
        this._focusedIdx = 0;
        this._updateFocusIndicator();

        // Resize observer
        this._ro = new ResizeObserver(() => {
            this.charts.forEach(c => c.chart.applyOptions({
                width: c.container.clientWidth,
                height: c.container.clientHeight,
            }));
        });
        this._ro.observe(grid);

        // ── Crosshair sync: time-locked across panels ──
        this.charts.forEach((entry, idx) => {
            entry.chart.subscribeCrosshairMove((param) => {
                if (!this._syncCrosshair || this._syncing) return;
                if (!param.time) {
                    // Mouse left panel — clear crosshairs on others
                    this._syncing = true;
                    try {
                        this.charts.forEach((other, j) => {
                            if (j !== idx) {
                                try { other.chart.clearCrosshairPosition(); } catch (_) {}
                            }
                        });
                    } finally {
                        this._syncing = false;
                    }
                    return;
                }

                this._syncing = true;
                try {
                    const hoveredTime = param.time;

                    this.charts.forEach((other, j) => {
                        if (j === idx) return;
                        if (!other.data || !other.data.candles || other.data.candles.length === 0) return;

                        // Find the nearest bar in this panel's data to the hovered time
                        const candles = other.data.candles;
                        const snapTime = this._findNearestTime(candles, hoveredTime);
                        if (snapTime === null) return;

                        // Get the price at that bar for the horizontal crosshair
                        const bar = candles.find(c => c.time === snapTime);
                        if (!bar) return;

                        try { other.chart.setCrosshairPosition(bar.close, snapTime, other.series); } catch (_) {}
                    });
                } finally {
                    this._syncing = false;
                }
            });
        });
    },

    /**
     * Binary search for the nearest candle time to a target timestamp.
     * Returns the time of the closest bar, or null if no data.
     */
    _findNearestTime(candles, target) {
        if (!candles || candles.length === 0) return null;
        let lo = 0, hi = candles.length - 1;

        // Binary search for first candle >= target
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (candles[mid].time < target) lo = mid + 1;
            else hi = mid;
        }

        // Compare lo and lo-1 to find closest
        if (lo === 0) return candles[0].time;
        const d0 = Math.abs(candles[lo].time - target);
        const d1 = Math.abs(candles[lo - 1].time - target);
        return d1 <= d0 ? candles[lo - 1].time : candles[lo].time;
    },

    _destroyGrid() {
        if (!this._containers) return;
        if (this._ro) { this._ro.disconnect(); this._ro = null; }
        // Clean up per-panel drawing canvases
        this.charts.forEach(c => {
            if (c._drawCanvasRO) c._drawCanvasRO.disconnect();
            c.chart.remove();
        });
        this.charts = [];
        this._containers.remove();
        this._containers = null;
        this._presetSelect = null;
        this._replayActive = false;
        this._replayTime = Infinity;
        this._drivingIdx = -1;
        this._focusedIdx = 0;
    },

    async _loadAll() {
        const seq = ++this._requestSeq;
        const tfs = this.charts.map(e => e.tf);
        const barCounts = {};
        tfs.forEach(tf => { barCounts[tf] = BAR_COUNTS_BY_TF[tf] || 800; });

        try {
            const res = await fetch('/api/multichart_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: App.symbol,
                    tfs,
                    bar_counts: barCounts,
                    end: App.endDate,
                    candle_type: App.candleType || 'ha',
                    htf_candle_type: App.htfCandleType || 'ohlc',
                }),
            });
            if (this._requestSeq !== seq) return;  // Stale — discard
            if (!res.ok) return;
            const allData = await res.json();
            if (this._requestSeq !== seq) return;  // Stale — discard

            // Load structure data for each panel's TF
            if (typeof Structure !== 'undefined') {
                await Promise.all(this.charts.map(entry => Structure.load(App.symbol, entry.tf)));
            }

            this.charts.forEach((entry, i) => {
                const data = allData[entry.tf];
                if (!data || data.error) return;
                if (!data.candles || data.candles.length === 0) {
                    console.debug('No candles for panel', entry.tf);
                    return;
                }
                entry.data = data;
                entry.series.setData(data.candles);
                entry.chart.timeScale().applyOptions({
                    rightOffset: this._rightOffset[entry.tf] || 10,
                    barSpacing: this._barSpacing[entry.tf] || 4,
                });
                this._renderOverlays(i);
            });
        } catch (e) {
            if (this._requestSeq !== seq) return;
            if (DEBUG_MC) console.error('Multichart batch load failed, falling back to individual loads:', e);
            await Promise.all(this.charts.map((_, i) => this._loadOne(i)));
        }

        this._initReplay();
    },

    async _loadOne(idx) {
        const entry = this.charts[idx];
        if (!entry) return;

        const bars = BAR_COUNTS_BY_TF[entry.tf] || 800;

        try {
            const candleType = entry.candleType || App.candleType || 'ha';
            const htfCandleType = App.htfCandleType || 'ohlc';
            const params = new URLSearchParams({
                symbol: App.symbol, tf: entry.tf, bars: bars,
                end: App.endDate, candle_type: candleType,
                htf_candle_type: htfCandleType,
            });
            const url = `/api/data?${params}`;
            const res = await fetch(url);
            if (!res.ok) return;
            const data = await res.json();

            // Guard: skip empty panels
            if (!data.candles || data.candles.length === 0) {
                console.debug('No candles for panel', entry.tf);
                return;
            }

            // Cache data for overlay re-renders
            entry.data = data;

            // Set candle data
            entry.series.setData(data.candles);

            // Update right offset
            entry.chart.timeScale().applyOptions({
                rightOffset: this._rightOffset[entry.tf] || 10,
            });

            // Set watermark
            entry.chart.applyOptions({
                watermark: {
                    visible: true,
                    text: `${data.symbol} ${data.tf}`,
                    fontSize: 28,
                    color: WATERMARK_COLOR_MC,
                },
            });

            // Load structure data for this panel's TF, then render overlays
            if (typeof Structure !== 'undefined') {
                await Structure.load(App.symbol, entry.tf);
            }
            if (!this._replayActive) {
                this._renderOverlays(idx);
            }

            // Re-render drawings for this panel
            this._renderPanelDrawings(idx);

            // If replay is active, sync the reloaded panel + recalc driving
            if (this._replayActive) {
                const oldDriving = this._drivingIdx;
                this._drivingIdx = this._findDrivingPanel();
                if (this._drivingIdx !== oldDriving) {
                    // Driving panel changed — reinit replay preserving current time
                    this._initReplayAtTime(this._replayTime);
                } else {
                    // Just sync the reloaded panel to current time
                    this._syncOnePanel(idx);
                }
            }
        } catch (e) {
            if (DEBUG_MC) console.warn(`MultiChart: Failed to load ${entry.tf}:`, e);
        }
    },

    /** Re-render drawings for a specific panel (after data reload) */
    _renderPanelDrawings(idx) {
        const entry = this.charts[idx];
        if (!entry || !entry.series) return;

        // Detach old drawing primitives
        if (entry._drawPrimitives) {
            entry._drawPrimitives.forEach(p => {
                try { entry.series.detachPrimitive(p); } catch(e) {}
            });
        }
        entry._drawPrimitives = [];

        // Attach new primitives
        const candles = entry.data && entry.data.candles;
        entry.drawings.forEach(d => {
            const prim = new DrawingPrimitive(d, entry.chart, entry.series, candles);
            entry.series.attachPrimitive(prim);
            entry._drawPrimitives.push(prim);
        });
    },

    /** Re-render all overlays for a panel using the full Overlays renderer */
    _renderOverlays(idx, maxTime) {
        if (maxTime === undefined) maxTime = (this._replayTime !== undefined && this._replayTime !== null) ? this._replayTime : Infinity;
        const entry = this.charts[idx];
        if (!entry || !entry.data) return;

        // Skip rendering for hidden/detached panels
        if (entry.container && entry.container.offsetParent === null) return;

        // Clear previous primitives
        if (entry._primitives) {
            entry._primitives.forEach(p => {
                try { entry.series.detachPrimitive(p); } catch(e) {}
            });
        }
        entry._primitives = [];
        entry.series.setMarkers([]);

        // Build overlay TFs + counts from per-panel overlayConfig
        const oc = entry.overlayConfig || {};

        // Trendlines
        const tc = oc.trendlines || {};
        const dataTlTFs = entry.data.trendlines ? Object.keys(entry.data.trendlines) : [];
        const filteredTlTFs = dataTlTFs.filter(tf => tc[tf] && tc[tf].on);
        const tlCounts = {};
        filteredTlTFs.forEach(tf => { tlCounts[tf] = (tc[tf] && tc[tf].count) || 2; });

        const allTFOrder = _getMcAllTFs();

        // HTF candles
        const hc = oc.htfCandles || {};
        const htfCandleTFs = entry.overlays.htfCandles
            ? allTFOrder.filter(tf => hc[tf] && hc[tf].on)
            : [];

        // Signals — filter by TF when enabled
        const sc = oc.signals || {};
        const signalTFs = entry.overlays.signals
            ? allTFOrder.filter(tf => sc[tf] && sc[tf].on)
            : [];

        const opts = {
            tlTFs: entry.overlays.trendlines ? filteredTlTFs : [],
            showSignals: entry.overlays.signals,
            signalTFs: signalTFs,
            htfCandleTFs: htfCandleTFs,
            tlCounts,
            maxTime: maxTime < Infinity ? maxTime : undefined,
            // Signal toggles from toolbar
            signalToggles: this._signalToggles || { zoneNumbers: true, nesting: true, tlBreaks: true },
        };

        // Use full Overlays renderer (pass chart instance for coordinate conversion)
        entry._primitives = Overlays.renderToSeries(entry.chart, entry.series, entry.data, opts);
        // Structure zones: only render when Z toggle is on for this panel
        if (typeof Structure !== 'undefined') {
            if (entry.overlays.zones) {
                Structure.render(entry.chart, entry.series, maxTime < Infinity ? maxTime : undefined, entry.tf);
            }
        }

        // Update signal count badge on S button
        if (entry.sBtn) {
            let sigCount = 0;
            const signals = entry.data.rule_signals || [];
            if (signals && entry.overlays.signals) {
                const tfSet = signalTFs.length > 0 ? new Set(signalTFs) : null;
                const mt = maxTime < Infinity ? maxTime : Infinity;
                signals.forEach(s => {
                    if (s.time > mt) return;
                    if (tfSet && s.tf && !tfSet.has(s.tf)) return;
                    sigCount++;
                });
            }
            entry.sBtn.textContent = sigCount > 0 ? `S(${sigCount})` : 'S';
        }
    },

    // ── Per-panel mini-sidebar ──

    /** Toggle mini-sidebar for a panel */
    _toggleMiniSidebar(idx) {
        const entry = this.charts[idx];
        if (!entry) return;

        // Close any other open sidebar first
        this.charts.forEach((e, i) => {
            if (i !== idx && e._miniSidebarOpen) {
                this._closeMiniSidebar(i);
            }
        });

        if (entry._miniSidebarOpen) {
            this._closeMiniSidebar(idx);
        } else {
            this._openMiniSidebar(idx);
        }
    },

    _openMiniSidebar(idx) {
        const entry = this.charts[idx];
        if (!entry || entry._miniSidebarOpen) return;

        const sidebar = document.createElement('div');
        sidebar.className = 'mc-mini-sidebar';
        sidebar.style.cssText = `
            position: absolute; right: 0; top: 0; bottom: 0; width: 180px; z-index: 15;
            background: rgba(17, 17, 24, 0.95); border-left: 1px solid #333;
            overflow-y: auto; overflow-x: hidden;
            transform: translateX(180px); transition: transform 0.15s ease-out;
            font-size: 11px; color: #ccc;
        `;

        // ── Close button at top ──
        const closeBtn = document.createElement('button');
        closeBtn.textContent = '\u2715';
        closeBtn.title = 'Close panel config';
        closeBtn.style.cssText = `
            position: sticky; top: 0; float: right; font-size: 14px; padding: 2px 6px;
            background: transparent; color: #888; border: none; cursor: pointer;
            z-index: 1; line-height: 1;
        `;
        closeBtn.addEventListener('click', () => this._closeMiniSidebar(idx));
        sidebar.appendChild(closeBtn);

        // ── Candle type section ──
        const candleSection = this._createSidebarSection('Candle Type');
        const candleSel = document.createElement('select');
        candleSel.style.cssText = `
            width: 100%; font-size: 11px; padding: 3px 4px; background: #1a1a24;
            color: #ccc; border: 1px solid #333; border-radius: 2px; margin-bottom: 4px;
        `;
        ['ohlc', 'hollow', 'ha', 'line', 'bars'].forEach(t => {
            const opt = document.createElement('option');
            opt.value = t;
            opt.textContent = { ohlc: 'OHLC', hollow: 'Hollow', ha: 'Heikin Ashi', line: 'Line', bars: 'Bars' }[t];
            if (t === entry.candleType) opt.selected = true;
            candleSel.appendChild(opt);
        });
        candleSel.addEventListener('change', () => {
            entry.candleType = candleSel.value;
            this._loadOne(idx);
        });
        candleSection.appendChild(candleSel);
        sidebar.appendChild(candleSection);

        // ── Zone TFs section ──
        sidebar.appendChild(this._createOverlaySection(idx, 'Zones', entry.overlayConfig.zones, true));

        // ── Trendline TFs section ──
        sidebar.appendChild(this._createOverlaySection(idx, 'Trendlines', entry.overlayConfig.trendlines, true));

        // ── HTF Candles section ──
        sidebar.appendChild(this._createOverlaySection(idx, 'HTF Candles', entry.overlayConfig.htfCandles, false));

        // ── Signal TFs section ──
        sidebar.appendChild(this._createOverlaySection(idx, 'Signals', entry.overlayConfig.signals, false));

        entry.container.appendChild(sidebar);
        entry._miniSidebar = sidebar;
        entry._miniSidebarOpen = true;

        // Update gear button style
        entry.gearBtn.style.background = UI.ACCENT_BG;
        entry.gearBtn.style.color = UI.ACCENT_TEXT;
        entry.gearBtn.style.borderColor = UI.ACCENT;

        // Trigger slide-in
        requestAnimationFrame(() => {
            sidebar.style.transform = 'translateX(0)';
        });
    },

    _closeMiniSidebar(idx) {
        const entry = this.charts[idx];
        if (!entry || !entry._miniSidebarOpen) return;

        if (entry._miniSidebar) {
            entry._miniSidebar.style.transform = 'translateX(180px)';
            setTimeout(() => {
                if (entry._miniSidebar && entry._miniSidebar.parentNode) {
                    entry._miniSidebar.remove();
                }
                entry._miniSidebar = null;
            }, 160);
        }
        entry._miniSidebarOpen = false;

        // Reset gear button style
        entry.gearBtn.style.background = UI.PANEL_BG;
        entry.gearBtn.style.color = UI.TEXT_DIM;
        entry.gearBtn.style.borderColor = UI.BORDER;
    },

    _createSidebarSection(title) {
        const section = document.createElement('div');
        section.style.cssText = 'padding: 6px 8px; border-bottom: 1px solid #1e1e28;';
        const h = document.createElement('div');
        h.textContent = title;
        h.style.cssText = 'font-size: 10px; font-weight: 600; color: #90caf9; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;';
        section.appendChild(h);
        return section;
    },

    /** Create a mini-sidebar overlay config section (zones/TLs/BOS/HTF/signals) */
    _createOverlaySection(idx, titleText, configObj, hasCounts) {
        const entry = this.charts[idx];
        const section = document.createElement('div');
        section.style.cssText = 'padding: 6px 8px; border-bottom: 1px solid #1e1e28;';

        // Header row: title + All/None buttons
        const header = document.createElement('div');
        header.style.cssText = 'display: flex; align-items: center; gap: 4px; margin-bottom: 4px;';

        const h = document.createElement('div');
        h.textContent = titleText;
        h.style.cssText = 'font-size: 10px; font-weight: 600; color: #90caf9; text-transform: uppercase; letter-spacing: 0.5px;';
        header.appendChild(h);

        // Spacer
        const spacer = document.createElement('div');
        spacer.style.cssText = 'flex: 1;';
        header.appendChild(spacer);

        const checkboxRefs = [];

        const mkToggle = (text, setTo) => {
            const b = document.createElement('span');
            b.textContent = text;
            b.style.cssText = 'font-size: 9px; color: #557; cursor: pointer;';
            b.addEventListener('mouseenter', () => { b.style.color = '#88a'; b.style.textDecoration = 'underline'; });
            b.addEventListener('mouseleave', () => { b.style.color = '#557'; b.style.textDecoration = 'none'; });
            b.addEventListener('click', () => {
                checkboxRefs.forEach(({ cb, cfg }) => {
                    cfg.on = setTo;
                    cb.checked = setTo;
                });
                this._renderOverlays(idx);
            });
            return b;
        };

        header.appendChild(mkToggle('All', true));
        header.appendChild(mkToggle('None', false));
        section.appendChild(header);

        const panelTf = entry.tf;

        _getMcAllTFs().forEach(tf => {
            let cfg = configObj[tf];
            if (!cfg) { cfg = { on: false, count: 2 }; configObj[tf] = cfg; }

            const row = document.createElement('div');
            const isHome = (tf === panelTf);
            row.style.cssText = `display: flex; align-items: center; gap: 3px; margin: 1px 0;${isHome ? ' background: rgba(68,138,255,0.12); border-radius: 2px; padding: 0 2px;' : ''}`;

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = cfg.on;
            cb.style.cssText = 'margin: 0; width: 11px; height: 11px; cursor: pointer;';
            cb.addEventListener('change', () => {
                cfg.on = cb.checked;
                this._renderOverlays(idx);
            });

            const lbl = document.createElement('span');
            lbl.textContent = tf;
            lbl.style.cssText = `width: 26px; font-size: 10px; color: ${isHome ? '#90caf9' : '#aaa'}; font-weight: ${isHome ? '700' : 'normal'};`;

            row.appendChild(cb);
            row.appendChild(lbl);

            if (hasCounts) {
                const num = document.createElement('input');
                num.type = 'number';
                num.min = 0; num.max = 20; num.value = cfg.count || 2;
                num.style.cssText = `
                    width: 30px; font-size: 10px; padding: 0 2px;
                    background: #111; color: #90caf9; border: 1px solid #333;
                    border-radius: 2px; text-align: center;
                `;
                num.addEventListener('change', () => {
                    cfg.count = Math.max(0, Math.min(20, parseInt(num.value) || 0));
                    this._renderOverlays(idx);
                });
                row.appendChild(num);
            }

            section.appendChild(row);
            checkboxRefs.push({ cb, cfg });
        });

        return section;
    },

    // ── Replay sync methods ──

    /** Find the panel with the lowest (finest) TF — that's the driving panel */
    _findDrivingPanel() {
        let bestIdx = 0, bestRank = 99;
        this.charts.forEach((entry, i) => {
            const rank = this._tfRank[entry.tf];
            if (rank !== undefined && rank < bestRank) {
                bestRank = rank;
                bestIdx = i;
            }
        });
        return bestIdx;
    },

    /** Binary search: last index where candle.time <= maxTime. Returns -1 if none. */
    _findSliceIndex(candles, maxTime) {
        if (!candles || candles.length === 0) return -1;
        let lo = 0, hi = candles.length - 1;
        if (candles[0].time > maxTime) return -1;
        if (candles[hi].time <= maxTime) return hi;
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1;
            if (candles[mid].time <= maxTime) lo = mid;
            else hi = mid - 1;
        }
        return lo;
    },

    /** Update visual indicator for which panel drives replay */
    _updateDrivingIndicator() {
        this._updateFocusIndicator();
    },

    /** Initialize replay after all panels are loaded */
    _initReplay() {
        this._drivingIdx = this._findDrivingPanel();
        const drivingEntry = this.charts[this._drivingIdx];
        if (!drivingEntry || !drivingEntry.data) return;

        Replay.initForMultichart(drivingEntry.data.candles);
        this._replayActive = false;
        this._replayTime = Infinity;
        this._updateDrivingIndicator();
    },

    /** Reinit replay preserving a specific time (used when driving panel changes) */
    _initReplayAtTime(time) {
        const drivingEntry = this.charts[this._drivingIdx];
        if (!drivingEntry || !drivingEntry.data) return;
        const candles = drivingEntry.data.candles;

        Replay.initForMultichart(candles);
        this._updateDrivingIndicator();

        if (time < Infinity && candles.length > 0) {
            // Find the bar index in new driving panel closest to preserved time
            const sliceIdx = this._findSliceIndex(candles, time);
            const barIdx = sliceIdx >= 0 ? sliceIdx + 1 : 1;
            Replay.jumpTo(barIdx);
        }
    },

    /** Called from App.onReplayChange when multichart is active */
    onReplayStep(barIdx) {
        const drivingEntry = this.charts[this._drivingIdx];
        if (!drivingEntry || !drivingEntry.data) return;

        const candles = drivingEntry.data.candles;
        const total = candles.length;
        const isLive = barIdx >= total;

        if (isLive) {
            this._replayActive = false;
            this._replayTime = Infinity;
        } else {
            this._replayActive = true;
            this._replayTime = candles[barIdx - 1].time;
        }

        this._syncAllPanels();

        // Update replay info
        if (isLive) {
            Replay.setInfo(`Live \u2014 ${total} bars (${drivingEntry.tf})`);
        } else {
            const bar = candles[barIdx - 1];
            const dt = new Date(bar.time * 1000).toISOString().slice(0, 16).replace('T', ' ');
            Replay.setInfo(`Bar ${barIdx}/${total} (${drivingEntry.tf}) | ${dt}`);
        }
    },

    /** Sync all panels to the current _replayTime */
    _syncAllPanels() {
        this.charts.forEach((_, i) => this._syncOnePanel(i));
    },

    /** Sync a single panel to the current _replayTime */
    _syncOnePanel(idx) {
        const entry = this.charts[idx];
        if (!entry || !entry.data) return;

        const candles = entry.data.candles;
        if (this._replayTime === Infinity) {
            // Live mode — show all data
            entry.series.setData(candles);
            this._renderOverlays(idx, Infinity);
        } else {
            const sliceIdx = this._findSliceIndex(candles, this._replayTime);
            if (sliceIdx < 0) {
                entry.series.setData([]);
                this._renderOverlays(idx, this._replayTime);
            } else {
                entry.series.setData(candles.slice(0, sliceIdx + 1));
                this._renderOverlays(idx, this._replayTime);
            }
        }
    },

    /** Reload all charts (called when symbol or end date changes) */
    reload() {
        if (this.enabled && this.charts.length > 0) {
            // Sync toolbar controls with App state
            if (this._dateDisplay) this._dateDisplay.value = App.endDate;
            if (this._symSelect) this._symSelect.value = App.symbol;
            this._loadAll();
        }
    },

    /** Show TF config popover — generalized for zones, TLs, BOS, HTF candles */
    _showTfConfig(panelIdx, anchorBtn, configObj, titleText, hasCounts) {
        // Remove existing popover
        const old = document.getElementById('mc-tf-popover');
        if (old) old.remove();

        const panelTf = this.charts[panelIdx] ? this.charts[panelIdx].tf : null;
        const panelTfIdx = panelTf ? _getMcAllTFs().indexOf(panelTf) : -1;

        const pop = document.createElement('div');
        pop.id = 'mc-tf-popover';
        pop.style.cssText = `
            position: fixed; z-index: 1000;
            background: #1a1a24; border: 1px solid #448aff; border-radius: 4px;
            padding: 6px 8px; font-size: 10px; color: #ccc;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        `;

        const title = document.createElement('div');
        title.textContent = titleText;
        title.style.cssText = 'font-weight: 700; color: #90caf9; margin-bottom: 4px; font-size: 11px;';
        pop.appendChild(title);

        // Determine which TFs have data in this panel
        const panelData = this.charts[panelIdx] && this.charts[panelIdx].data;
        const availableTFs = new Set();
        if (panelData) {
            ['zones', 'trendlines', 'htf_candles'].forEach(key => {
                if (panelData[key] && typeof panelData[key] === 'object') {
                    Object.keys(panelData[key]).forEach(tf => availableTFs.add(tf));
                }
            });
            if (panelTf) availableTFs.add(panelTf);
        }

        // ── Quick action buttons ──
        const btnRow = document.createElement('div');
        btnRow.style.cssText = 'display: flex; gap: 3px; margin-bottom: 4px;';

        const mkQuickBtn = (text, tooltip, onClick) => {
            const b = document.createElement('button');
            b.textContent = text;
            b.title = tooltip;
            b.style.cssText = `
                font-size: 9px; padding: 1px 5px; background: #111;
                color: #90caf9; border: 1px solid #333; border-radius: 2px;
                cursor: pointer; line-height: 14px;
            `;
            b.addEventListener('click', onClick);
            return b;
        };

        // Collect checkbox refs for quick buttons to toggle
        const checkboxRefs = [];

        // "All above" — enable all TFs above (lower index = higher TF) the panel's own TF
        btnRow.appendChild(mkQuickBtn('All \u2191', 'Enable all TFs above this panel\'s TF', () => {
            checkboxRefs.forEach(({ tf, cb, cfg, tfIdx }) => {
                if (tfIdx < panelTfIdx && !cb.disabled) {
                    cfg.on = true; cb.checked = true;
                }
            });
            this._renderOverlays(panelIdx);
        }));

        // "Own" — enable only the panel's own TF
        btnRow.appendChild(mkQuickBtn('Own', 'Enable only this panel\'s own TF', () => {
            checkboxRefs.forEach(({ tf, cb, cfg }) => {
                const on = (tf === panelTf);
                cfg.on = on; cb.checked = on;
            });
            this._renderOverlays(panelIdx);
        }));

        // "None" — disable all
        btnRow.appendChild(mkQuickBtn('None', 'Disable all TFs', () => {
            checkboxRefs.forEach(({ cb, cfg }) => {
                cfg.on = false; cb.checked = false;
            });
            this._renderOverlays(panelIdx);
        }));

        // "HTF +2" — enable zones/TLs/BOS for 2 levels above the panel's own TF
        if (panelTfIdx > 0) {
            btnRow.appendChild(mkQuickBtn('HTF +2', 'Enable own TF + 2 levels above', () => {
                const enableSet = new Set();
                if (panelTf) enableSet.add(panelTf);
                // 2 levels above: indices panelTfIdx-1 and panelTfIdx-2
                if (panelTfIdx - 1 >= 0) enableSet.add(_getMcAllTFs()[panelTfIdx - 1]);
                if (panelTfIdx - 2 >= 0) enableSet.add(_getMcAllTFs()[panelTfIdx - 2]);
                checkboxRefs.forEach(({ tf, cb, cfg }) => {
                    const on = enableSet.has(tf) && !cb.disabled;
                    cfg.on = on; cb.checked = on;
                });
                this._renderOverlays(panelIdx);
            }));
        }

        pop.appendChild(btnRow);

        // ── TF rows ──
        const allTFs = _getMcAllTFs();
        allTFs.forEach((tf, tfArrIdx) => {
            let cfg = configObj[tf];
            if (!cfg) { cfg = { on: false, count: 2 }; configObj[tf] = cfg; }
            const hasData = availableTFs.size === 0 || availableTFs.has(tf);
            const isHome = (tf === panelTf);
            const row = document.createElement('div');
            row.style.cssText = `display: flex; align-items: center; gap: 4px; margin: 2px 0;${isHome ? ' background: rgba(68,138,255,0.12); border-radius: 2px; padding: 1px 2px;' : ''}`;

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = cfg.on;
            cb.disabled = !hasData;
            cb.style.cssText = `margin: 0; width: 12px; height: 12px; cursor: ${hasData ? 'pointer' : 'default'}; opacity: ${hasData ? '1' : '0.4'};`;
            cb.addEventListener('change', () => {
                cfg.on = cb.checked;
                this._renderOverlays(panelIdx);
            });

            const lbl = document.createElement('span');
            lbl.textContent = tf;
            lbl.style.cssText = `width: 28px; color: ${isHome ? '#90caf9' : (hasData ? '#aaa' : '#555')}; font-weight: ${isHome ? '700' : 'normal'};`;

            row.appendChild(cb);
            row.appendChild(lbl);

            if (hasCounts) {
                const num = document.createElement('input');
                num.type = 'number';
                num.min = 0; num.max = 20; num.value = cfg.count || 2;
                num.disabled = !hasData;
                num.style.cssText = `
                    width: 36px; font-size: 10px; padding: 1px 3px;
                    background: #111; color: ${hasData ? '#90caf9' : '#555'}; border: 1px solid #333;
                    border-radius: 2px; text-align: center; opacity: ${hasData ? '1' : '0.4'};
                `;
                num.addEventListener('change', () => {
                    cfg.count = Math.max(0, Math.min(20, parseInt(num.value) || 0));
                    this._renderOverlays(panelIdx);
                });
                row.appendChild(num);
            }

            pop.appendChild(row);
            checkboxRefs.push({ tf, cb, cfg, tfIdx: tfArrIdx });
        });

        document.body.appendChild(pop);

        // Position near the button, check viewport overflow
        const rect = anchorBtn.getBoundingClientRect();
        const popHeight = allTFs.length * 22 + 70; // estimate (extra for buttons row)
        const spaceBelow = window.innerHeight - rect.bottom;
        pop.style.left = rect.left + 'px';
        if (spaceBelow < popHeight) {
            pop.style.top = (rect.top - popHeight) + 'px';
        } else {
            pop.style.top = (rect.bottom + 2) + 'px';
        }

        // Close on click outside
        const close = (e) => {
            if (!pop.contains(e.target) && e.target !== anchorBtn) {
                pop.remove();
                document.removeEventListener('mousedown', close);
            }
        };
        setTimeout(() => document.addEventListener('mousedown', close), 0);
    },
};
