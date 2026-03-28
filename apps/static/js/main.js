/**
 * main.js — App initialization, state management, Flask API calls.
 */

const App = {
    // Current state (defaults overridden by /api/config on init)
    symbol: '',
    tf: '',
    barCount: 0,
    endDate: '',
    candleType: 'ha',

    // Full data from server
    data: null,
    controller: null,
    _requestSeq: 0,

    // Toggle states — delegated to OverlayState.single (SSOT)
    get tlTFs() { return OverlayState.single.tlTFs; },
    set tlTFs(v) { OverlayState.single.tlTFs = v; },
    get showSignals() { return OverlayState.single.showSignals; },
    set showSignals(v) { OverlayState.single.showSignals = v; },
    get htfCandleTFs() { return OverlayState.single.htfCandleTFs; },
    set htfCandleTFs(v) { OverlayState.single.htfCandleTFs = v; },
    get htfCandleType() { return OverlayState.single.htfCandleType; },
    set htfCandleType(v) { OverlayState.single.htfCandleType = v; },
    get tlCounts() { return OverlayState.single.tlCounts; },
    set tlCounts(v) { OverlayState.single.tlCounts = v; },

    // Available options (from server)
    symbols: [],
    tfOptions: { base: [], zones: [], trendlines: [] },

    async init() {
        // Load available symbols, timeframes, and canonical config
        const [symResponse, tfResponse, cfgResponse] = await Promise.all([
            fetch('/api/symbols'),
            fetch('/api/timeframes'),
            fetch('/api/config'),
        ]);
        if (!symResponse.ok || !tfResponse.ok || !cfgResponse.ok) {
            document.getElementById('status-info').textContent = 'Failed to load symbols/timeframes';
            return;
        }
        const symRes = await symResponse.json();
        const tfRes = await tfResponse.json();
        const cfgRes = await cfgResponse.json();
        this.symbols = symRes.symbols;
        this.tfOptions = tfRes;
        this.config = cfgRes;

        // Set defaults from server config
        const cfgSym = cfgRes.default_symbol || 'GBPUSD';
        this.symbol = this.symbols.includes(cfgSym) ? cfgSym :
                      this.symbols.includes('XAUUSD') ? 'XAUUSD' : this.symbols[0];
        this.tf = cfgRes.default_tf || 'H4';
        this.barCount = BAR_COUNTS_BY_TF[this.tf] || 6000;

        // Get latest date
        const dateResponse = await fetch(`/api/latest_date?${new URLSearchParams({ symbol: this.symbol, tf: this.tf })}`);
        if (!dateResponse.ok) {
            document.getElementById('status-info').textContent = 'Failed to fetch latest date';
            return;
        }
        const dateRes = await dateResponse.json();
        this.endDate = dateRes.date;

        this._buildControls();
        this._bindEvents();

        // Init chart
        Chart.init();
        Chart.enableCrosshairTooltip();
        Drawing.init();

        // Load data
        await this.loadData();

        // Default to single-chart view
        // Press M or click multichart button to toggle
    },

    _buildControls() {
        // Symbol select
        const symSel = document.getElementById('symbol-select');
        const symFrag = document.createDocumentFragment();
        this.symbols.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            if (s === this.symbol) opt.selected = true;
            symFrag.appendChild(opt);
        });
        symSel.appendChild(symFrag);

        // TF select
        const tfSel = document.getElementById('tf-select');
        const tfFrag = document.createDocumentFragment();
        this.tfOptions.base.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t; opt.textContent = t;
            if (t === this.tf) opt.selected = true;
            tfFrag.appendChild(opt);
        });
        tfSel.appendChild(tfFrag);

        // Bar count & end date
        document.getElementById('bar-count').value = this.barCount;
        document.getElementById('end-date').value = this.endDate;

        // TL TF checkboxes with count inputs
        this._buildTFChecks('tl-tf-checks', this.tfOptions.trendlines, this.tlTFs, (tfs) => {
            this.tlTFs = tfs;
            this._rebuildOverlays();
        }, this.tlCounts, (counts) => {
            this.tlCounts = counts;
            this._rebuildOverlays();
        });

        // HTF candle checkboxes (no count needed) — TF list from server config
        const htfOptions = (this.config && this.config.htf_candle_tf_options) || ['12M', '6M', '3M', 'MN1', 'W1', 'D1', 'H4', 'H1', 'M30', 'M15', 'M5'];
        this._buildTFChecks('htf-candle-checks', htfOptions, this.htfCandleTFs, (tfs) => {
            this.htfCandleTFs = tfs;
            this._rebuildOverlays();
        });

        // All/None toggle links
        document.querySelectorAll('.toggle-all').forEach(el => {
            el.addEventListener('click', () => {
                const target = document.getElementById(el.dataset.target);
                target.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = true; });
                target.querySelector('input[type="checkbox"]').dispatchEvent(new Event('change'));
            });
        });
        document.querySelectorAll('.toggle-none').forEach(el => {
            el.addEventListener('click', () => {
                const target = document.getElementById(el.dataset.target);
                target.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
                target.querySelector('input[type="checkbox"]').dispatchEvent(new Event('change'));
            });
        });
    },

    /**
     * Build TF checkbox row. If countsObj + onCountChange provided, adds
     * a small number input next to each TF for limiting visible items.
     * Value 0 (or empty) = show all.
     */
    _buildTFChecks(containerId, options, defaults, onChange, countsObj, onCountChange) {
        const container = document.getElementById(containerId);
        options.forEach(tf => {
            const lbl = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = tf;
            cb.checked = defaults.includes(tf);
            cb.addEventListener('change', () => {
                const checked = Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
                onChange(checked);
            });
            lbl.appendChild(cb);
            lbl.appendChild(document.createTextNode(' ' + tf));

            // Add count input if countsObj provided
            if (countsObj !== undefined && onCountChange) {
                const numInput = document.createElement('input');
                numInput.type = 'number';
                numInput.min = '0';
                numInput.max = '999';
                numInput.value = countsObj[tf] || '';
                numInput.placeholder = '∞';
                numInput.title = `Max ${tf} items (0 or empty = all)`;
                let _countDebounce = null;
                numInput.addEventListener('change', () => {
                    clearTimeout(_countDebounce);
                    _countDebounce = setTimeout(() => {
                        const val = parseInt(numInput.value);
                        if (val > 0) {
                            countsObj[tf] = val;
                        } else {
                            delete countsObj[tf];
                            numInput.value = '';
                        }
                        onCountChange(countsObj);
                    }, DEBOUNCE_MS);
                });
                lbl.appendChild(numInput);
            }

            container.appendChild(lbl);
        });
    },

    _bindEvents() {
        // Refresh
        document.getElementById('refresh-btn').addEventListener('click', async () => {
            await fetch('/api/clear_cache', { method: 'POST' });
            await this._fetchLatestDateAndReload();
        });

        // Symbol change
        document.getElementById('symbol-select').addEventListener('change', (e) => {
            this.symbol = e.target.value;
            this._fetchLatestDateAndReload();
        });

        // TF change
        document.getElementById('tf-select').addEventListener('change', (e) => {
            this.tf = e.target.value;
            this.barCount = BAR_COUNTS_BY_TF[this.tf] || 800;
            document.getElementById('bar-count').value = this.barCount;
            this._fetchLatestDateAndReload();
        });

        // Bar count
        document.getElementById('bar-count').addEventListener('change', (e) => {
            this.barCount = parseInt(e.target.value) || 800;
        });

        // End date
        document.getElementById('end-date').addEventListener('change', (e) => {
            this.endDate = e.target.value;
        });

        // Date navigation: step back/forward based on TF
        const dateStepDays = { M1: 1, M5: 3, M15: 7, M30: 14, H1: 14, H4: 30, D1: 90, W1: 180, MN1: 365 };
        const stepDate = (direction) => {
            if (!this.endDate) return;
            const d = new Date(this.endDate);
            const step = dateStepDays[this.tf] || 7;
            d.setDate(d.getDate() + (direction * step));
            this.endDate = d.toISOString().slice(0, 10);
            document.getElementById('end-date').value = this.endDate;
            this.loadData();
        };
        document.getElementById('date-back').addEventListener('click', () => stepDate(-1));
        document.getElementById('date-fwd').addEventListener('click', () => stepDate(1));

        // Keyboard: PageUp/PageDown for time navigation
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            if (e.key === 'PageUp') { e.preventDefault(); stepDate(-1); }
            if (e.key === 'PageDown') { e.preventDefault(); stepDate(1); }
            if (e.key === 'm' || e.key === 'M') {
                if (typeof MultiChart !== 'undefined') MultiChart.toggle();
            }
        });

        // Candle type selector
        document.getElementById('candle-type-select').addEventListener('change', (e) => {
            const prev = this.candleType;
            this.candleType = e.target.value;
            // HA needs server recomputation; switching away from HA also needs reload
            // to get raw OHLC back. Line/bars can switch client-side from OHLC data.
            const needsReload = (this.candleType === 'ha' || prev === 'ha');
            if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
                // Multichart always needs server reload (all panels use App.candleType)
                MultiChart.reload();
            } else if (needsReload) {
                this.loadData();
            } else if (this.data) {
                Chart.setChartType(this.candleType, this.data);
                this._rebuildOverlays();
            }
        });

        // Structure toggles (BOS/CHoCH now handled by Structure breaks)
        ['zones', 'breaks', 'boundaries', 'zigzag'].forEach(key => {
            const el = document.getElementById('structure-' + key);
            if (el) el.addEventListener('change', (e) => {
                const setter = 'set' + key.charAt(0).toUpperCase() + key.slice(1) + 'Enabled';
                Structure[setter](e.target.checked);
                const series = Chart.getCandleSeries();
                if (series) Structure.render(Chart.getChart(), series, undefined, App.tf);
                else Structure.clear();
            });
        });

        // Structure zone count spinners
        ['parent', 'child', 'sub'].forEach(level => {
            const el = document.getElementById('structure-' + level + '-count');
            if (el) el.addEventListener('change', () => {
                const counts = Structure.getZoneCounts();
                counts[level] = parseInt(el.value) || 0;
                Structure.setZoneCounts(counts);
                const series = Chart.getCandleSeries();
                if (series) Structure.render(Chart.getChart(), series, undefined, this.tf);
            });
        });

        // Breaker/mitigation toggle
        const breakersEl = document.getElementById('structure-breakers');
        if (breakersEl) breakersEl.addEventListener('change', (e) => {
            Structure.setBreakersEnabled(e.target.checked);
            const series = Chart.getCandleSeries();
            if (series) Structure.render(Chart.getChart(), series, undefined, this.tf);
        });

        // Structure display mode toggle (Lines / Rects)
        function _setStructureModeButtons(activeMode) {
            ['lines', 'rects'].forEach(m => {
                const btn = document.getElementById('structure-mode-' + m);
                if (!btn) return;
                const active = m === activeMode;
                btn.style.background  = active ? '#448aff' : '#1a1a2e';
                btn.style.color       = active ? '#fff'    : '#888';
                btn.style.borderColor = active ? '#448aff' : '#333';
            });
        }
        ['lines', 'rects'].forEach(mode => {
            const el = document.getElementById('structure-mode-' + mode);
            if (el) el.addEventListener('click', () => {
                Structure.setDisplayMode(mode);
                OverlayState.single.structureDisplayMode = mode;
                _setStructureModeButtons(mode);
                const series = Chart.getCandleSeries();
                if (series) Structure.render(Chart.getChart(), series, undefined, App.tf);
            });
        });
        // Sync initial display mode from OverlayState into Structure module
        const initialMode = OverlayState.single.structureDisplayMode || 'lines';
        Structure.setDisplayMode(initialMode);
        _setStructureModeButtons(initialMode);

        // Opposing nesting toggle
        const opposingEl = document.getElementById('structure-opposing');
        if (opposingEl) opposingEl.addEventListener('change', (e) => {
            Structure.setOpposingEnabled(e.target.checked);
            const series = Chart.getCandleSeries();
            if (series) Structure.render(Chart.getChart(), series, undefined, this.tf);
        });

        // Signals toggle
        document.getElementById('signals-toggle').addEventListener('change', (e) => {
            this.showSignals = e.target.checked;
            this._rebuildOverlays();
        });

        // Context bands toggle
        const contextBandsToggle = document.getElementById('context-bands-toggle');
        if (contextBandsToggle) {
            contextBandsToggle.addEventListener('change', (e) => {
                OverlayState.single.showContextBands = e.target.checked;
                this._rebuildOverlays();
            });
        }

        // HTF candle type selector
        document.getElementById('htf-candle-type').addEventListener('change', (e) => {
            this.htfCandleType = e.target.value;
            // HA needs server recomputation — reload multichart directly if active
            if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
                MultiChart.reload();
            } else {
                this.loadData();
            }
        });

        // Screenshot button
        document.getElementById('screenshot-btn').addEventListener('click', () => this.takeScreenshot());

        // Multi-chart toggle
        const mcBtn = document.getElementById('multichart-btn');
        if (mcBtn) {
            mcBtn.addEventListener('click', () => {
                if (typeof MultiChart !== 'undefined') MultiChart.toggle();
            });
        }

        // Pulse panel
        if (typeof Pulse !== 'undefined') Pulse.init();
    },

    async takeScreenshot() {
        // Use multichart grid if active, otherwise main chart container
        const mcActive = typeof MultiChart !== 'undefined' && MultiChart.enabled;
        const container = mcActive
            ? document.getElementById('multichart-grid')
            : document.getElementById('chart-container');
        const flash = document.getElementById('screenshot-flash');
        try {
            if (!container) { flash.textContent = 'No chart'; flash.style.display = 'inline'; return; }
            const canvases = container.querySelectorAll('canvas');
            if (canvases.length === 0) { flash.textContent = 'No canvas'; flash.style.display = 'inline'; return; }

            // Create composite canvas
            const rect = container.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            const w = Math.round(rect.width * dpr);
            const h = Math.round(rect.height * dpr);
            const composite = document.createElement('canvas');
            composite.width = w;
            composite.height = h;
            const ctx = composite.getContext('2d');

            // Dark background
            ctx.fillStyle = BG_COLOR;
            ctx.fillRect(0, 0, w, h);

            // Layer all canvases (skip zero-size canvases)
            canvases.forEach(c => {
                if (c.width === 0 || c.height === 0) return;
                const cr = c.getBoundingClientRect();
                const ox = (cr.left - rect.left) * dpr;
                const oy = (cr.top - rect.top) * dpr;
                ctx.drawImage(c, ox, oy);
            });

            // Build TF label: multichart shows all panel TFs, single shows base TF
            let tfLabel;
            if (mcActive && typeof MultiChart !== 'undefined' && MultiChart.charts) {
                const panelTFs = MultiChart.charts.map(c => c.tf).join('+');
                tfLabel = `MC_${panelTFs}`;
            } else {
                tfLabel = this.tf;
            }

            // Add watermark with symbol/TF/time
            ctx.fillStyle = WATERMARK_COLOR;
            ctx.font = `${12 * dpr}px sans-serif`;
            const label = `${this.symbol} ${tfLabel} | ${new Date().toLocaleString()}`;
            ctx.fillText(label, 10 * dpr, h - 10 * dpr);

            const dataUrl = composite.toDataURL('image/png');

            const res = await fetch('/api/screenshot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: dataUrl, symbol: this.symbol, tf: tfLabel }),
            });
            const result = await res.json();
            if (!res.ok) {
                throw new Error(result.error || 'Screenshot save failed');
            }
            flash.textContent = `Saved: ${result.filename}`;
            flash.style.display = 'inline';
            setTimeout(() => { flash.style.display = 'none'; }, FLASH_TIMEOUT_MS);
        } catch (e) {
            flash.textContent = 'Error: ' + e.message;
            flash.style.display = 'inline';
            console.error('Screenshot error:', e);
        }
    },

    async loadData() {
        // Skip single-chart fetch when multichart is active — just reload panels
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            MultiChart.reload();
            return;
        }

        const seq = ++this._requestSeq;
        if (this.controller) this.controller.abort();
        this.controller = new AbortController();

        const loading = document.getElementById('loading');
        loading.classList.add('visible');

        try {
            const params = new URLSearchParams({
                symbol: this.symbol, tf: this.tf, bars: this.barCount,
                end: this.endDate, candle_type: this.candleType,
                htf_candle_type: this.htfCandleType,
            });
            const url = `/api/data?${params}`;
            const res = await fetch(url, { signal: this.controller.signal });
            if (this._requestSeq !== seq) return;
            if (!res.ok) {
                const err = await res.json();
                document.getElementById('status-info').textContent = err.error || 'Load failed';
                return;
            }

            this.data = await res.json();
            if (this._requestSeq !== seq) return;

            // Guard: zero bars — show message instead of degenerate UI
            if (!this.data.candles || this.data.candles.length === 0) {
                document.getElementById('status-info').textContent =
                    'No data for ' + this.symbol + ' ' + this.tf;
                return;
            }

            // Fetch structure (child+parent zones, events, boundaries, zigzag)
            await Structure.load(this.symbol, this.tf);
            this._updateStructureTFLabels();

            // Update chart
            Chart.setData(this.data);
            Chart.setWatermark(this.data.symbol, this.data.tf);

            // Right-side buffer — use chart.js canonical RIGHT_OFFSET_BY_TF
            Chart.getChart().timeScale().applyOptions({ rightOffset: RIGHT_OFFSET_BY_TF[this.tf] || 6 });

            // Set up replay — start at Live (latest candles), user scrolls back
            Replay.init(this.data.candles.length);

            // Render overlays
            this._rebuildOverlays();

            // Render structure overlay
            const structSeries = Chart.getCandleSeries();
            if (structSeries) {
                Structure.render(Chart.getChart(), structSeries, undefined, this.tf);
            }

            // Update Pulse panel with structure bias
            if (typeof Pulse !== 'undefined') Pulse.update();

            // Status
            const info = `${this.data.symbol} ${this.data.tf} | ${this.data.candles.length} bars | ${this.data.elapsed.toFixed(1)}s`;
            document.getElementById('status-info').textContent = info;

        } catch (e) {
            if (e.name === 'AbortError') return;  // Request was cancelled, ignore
            document.getElementById('status-info').textContent = 'Error: ' + e.message;
            console.error(e);
        } finally {
            loading.classList.remove('visible');
        }
    },

    /** Fetch latest date for current symbol/tf, then reload. Shared by symbol + TF handlers. */
    async _fetchLatestDateAndReload() {
        const seq = ++this._requestSeq;
        if (this.controller) this.controller.abort();
        this.controller = new AbortController();
        try {
            const res = await fetch(`/api/latest_date?${new URLSearchParams({ symbol: this.symbol, tf: this.tf })}`, { signal: this.controller.signal });
            if (this._requestSeq !== seq) return;
            if (!res.ok) {
                document.getElementById('status-info').textContent = `No data for ${this.symbol} ${this.tf}`;
                return;
            }
            const dateRes = await res.json();
            this.endDate = dateRes.date;
            document.getElementById('end-date').value = this.endDate;
        } catch (err) {
            if (err.name === 'AbortError') return;
        }
        if (this._requestSeq !== seq) return;
        this.loadData();
    },

    _updateStructureTFLabels() {
        const data = Structure.getData(this.tf);
        if (data) {
            const ptf = document.getElementById('parent-tf-label');
            const ctf = document.getElementById('child-tf-label');
            const stf = document.getElementById('sub-tf-label');
            if (ptf) ptf.textContent = data.parent_tf || '—';
            if (ctf) ctf.textContent = data.child_tf || this.tf;
            if (stf) stf.textContent = data.sub_tf || '—';
        }
    },

    _rebuildOverlays() {
        if (!this.data) return;
        Overlays.render(this.data, OverlayState.getSingleRenderOpts());
    },

    /** Called by Replay when slider changes — re-slice and render. */
    onReplayChange(barIdx) {
        // Route to MultiChart when active
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            MultiChart.onReplayStep(barIdx);
            return;
        }
        if (!this.data) return;
        const total = this.data.candles.length;
        const isLive = barIdx >= total;
        const sliceEnd = isLive ? total : barIdx;
        const slicedCandles = this.data.candles.slice(0, sliceEnd);

        Chart.updateCandles(slicedCandles);

        // Update overlays with time filter
        const maxTime = slicedCandles.length > 0 ? slicedCandles[slicedCandles.length - 1].time : 0;
        Overlays.render(this.data, OverlayState.getSingleRenderOpts({ maxTime }));

        // Re-render structure with time filter (no lookahead)
        const replaySeries = Chart.getCandleSeries();
        if (replaySeries) {
            Structure.render(Chart.getChart(), replaySeries, maxTime, this.tf);
        }

        // Update replay info
        if (isLive) {
            Replay.setInfo(`Live — ${total} bars`);
        } else {
            const bar = slicedCandles[slicedCandles.length - 1];
            const dt = new Date(bar.time * 1000).toISOString().slice(0, 16).replace('T', ' ');
            Replay.setInfo(`Bar ${barIdx}/${total} | ${dt}`);
        }
    },
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
