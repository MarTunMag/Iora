/**
 * backtest.js — Backtest panel: run, sweep, equity curve, trade markers.
 *
 * CRITICAL: Uses ONLY safe DOM methods (createElement/textContent). NO innerHTML anywhere.
 */

(function () {
    'use strict';

    // ── DOM helpers ──────────────────────────────────────────────────────────

    /** Remove all child nodes from an element. */
    function clearChildren(el) {
        while (el.firstChild) {
            el.removeChild(el.firstChild);
        }
    }

    /**
     * Create a DOM element with optional attributes and text content.
     * @param {string} tag
     * @param {Object} [attrs]  — key/value pairs applied as el[key] = value
     * @param {string} [text]   — textContent to set
     * @returns {HTMLElement}
     */
    function createEl(tag, attrs, text) {
        const el = document.createElement(tag);
        if (attrs) {
            Object.keys(attrs).forEach(function (k) {
                el[k] = attrs[k];
            });
        }
        if (text !== undefined && text !== null) {
            el.textContent = text;
        }
        return el;
    }

    // ── State ────────────────────────────────────────────────────────────────

    const Backtest = {
        _equityChart: null,
        _equitySeries: null,
        _sweepData: [],
        _sweepSortCol: null,
        _sweepSortAsc: true,
        _selectedSweepRow: null,

        // ── Init ─────────────────────────────────────────────────────────────

        init() {
            const runBtn = document.getElementById('bt-run-btn');
            const sweepBtn = document.getElementById('bt-sweep-btn');
            if (runBtn) runBtn.addEventListener('click', () => this.run());
            if (sweepBtn) sweepBtn.addEventListener('click', () => this.sweep());
        },

        // ── Config reader ─────────────────────────────────────────────────────

        /** Read current form values and App state into a config object. */
        _readConfig() {
            const symbol = (typeof App !== 'undefined') ? App.symbol : '';
            const tf = (typeof App !== 'undefined') ? App.tf : '';
            const endDate = (typeof App !== 'undefined') ? App.endDate : '';
            const barCount = (typeof App !== 'undefined') ? App.barCount : 500;

            return {
                symbol: symbol,
                tf: tf,
                end_date: endDate,
                bar_count: parseInt(barCount, 10) || 500,
                sl_mode: document.getElementById('bt-sl-mode').value,
                tp_mode: document.getElementById('bt-tp-mode').value,
                fixed_rr: parseFloat(document.getElementById('bt-fixed-rr').value) || 2.0,
                nesting: document.getElementById('bt-nesting').value === 'true',
                direction: document.getElementById('bt-direction').value,
                htf_trend: document.getElementById('bt-htf-trend').value,
            };
        },

        // ── Run ───────────────────────────────────────────────────────────────

        async run() {
            const config = this._readConfig();
            const runBtn = document.getElementById('bt-run-btn');
            if (runBtn) {
                runBtn.disabled = true;
                runBtn.textContent = '...';
            }

            try {
                const resp = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config),
                });

                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({ error: resp.statusText }));
                    this._showError(errData.error || 'Run failed');
                    return;
                }

                const data = await resp.json();
                this._renderMetrics(data.metrics || {});
                this._renderTradeMarkers(data.trades || []);
                this._renderEquityCurve(data.equity_curve || []);

                // Show results panel, hide sweep
                const resultsEl = document.getElementById('bt-results');
                const sweepEl = document.getElementById('bt-sweep-results');
                if (resultsEl) resultsEl.style.display = 'block';
                if (sweepEl) sweepEl.style.display = 'none';

            } catch (err) {
                this._showError('Network error: ' + err.message);
            } finally {
                if (runBtn) {
                    runBtn.disabled = false;
                    runBtn.textContent = 'Run';
                }
            }
        },

        // ── Sweep ─────────────────────────────────────────────────────────────

        async sweep() {
            const config = this._readConfig();
            const sweepBtn = document.getElementById('bt-sweep-btn');
            if (sweepBtn) {
                sweepBtn.disabled = true;
                sweepBtn.textContent = '...';
            }

            try {
                const resp = await fetch('/api/backtest/sweep', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config),
                });

                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({ error: resp.statusText }));
                    this._showError(errData.error || 'Sweep failed');
                    return;
                }

                const data = await resp.json();
                this._sweepData = data.results || [];
                this._sweepSortCol = null;
                this._sweepSortAsc = true;
                this._selectedSweepRow = null;
                this._renderSweepTable(this._sweepData);

                // Show sweep results, hide single results
                const resultsEl = document.getElementById('bt-results');
                const sweepEl = document.getElementById('bt-sweep-results');
                if (resultsEl) resultsEl.style.display = 'none';
                if (sweepEl) sweepEl.style.display = 'block';

            } catch (err) {
                this._showError('Network error: ' + err.message);
            } finally {
                if (sweepBtn) {
                    sweepBtn.disabled = false;
                    sweepBtn.textContent = 'Sweep';
                }
            }
        },

        // ── Metrics rendering ─────────────────────────────────────────────────

        /**
         * Render a metrics object into #bt-metrics using safe DOM methods.
         * Supports flat key/value pairs and nested sections (object values).
         */
        _renderMetrics(metrics) {
            const container = document.getElementById('bt-metrics');
            if (!container) return;
            clearChildren(container);

            const sections = this._groupMetrics(metrics);

            sections.forEach(function (section) {
                if (section.title) {
                    const h4 = createEl('h4', null, section.title);
                    container.appendChild(h4);
                }
                section.rows.forEach(function (row) {
                    const div = createEl('div', { className: 'metric-row' });
                    const label = createEl('span', { className: 'metric-label' }, row.label);
                    const value = createEl('span', { className: 'metric-value' }, row.value);

                    // Color win rate / expectancy values
                    if (row.colorize) {
                        const num = parseFloat(row.rawValue);
                        if (!isNaN(num)) {
                            value.style.color = num >= 0 ? '#4caf50' : '#f44336';
                        }
                    }

                    div.appendChild(label);
                    div.appendChild(value);
                    container.appendChild(div);
                });
            });
        },

        /**
         * Convert a flat or nested metrics object into grouped sections.
         * Each section: { title: string|null, rows: [{label, value, rawValue, colorize}] }
         */
        _groupMetrics(metrics) {
            const sections = [];
            const topRows = [];

            Object.keys(metrics).forEach(function (key) {
                const val = metrics[key];
                if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
                    // Nested section
                    const sectionRows = [];
                    Object.keys(val).forEach(function (subKey) {
                        sectionRows.push({
                            label: Backtest._formatLabel(subKey),
                            value: Backtest._formatValue(subKey, val[subKey]),
                            rawValue: val[subKey],
                            colorize: Backtest._shouldColorize(subKey),
                        });
                    });
                    sections.push({ title: Backtest._formatLabel(key), rows: sectionRows });
                } else {
                    topRows.push({
                        label: Backtest._formatLabel(key),
                        value: Backtest._formatValue(key, val),
                        rawValue: val,
                        colorize: Backtest._shouldColorize(key),
                    });
                }
            });

            if (topRows.length > 0) {
                sections.unshift({ title: null, rows: topRows });
            }
            return sections;
        },

        _formatLabel(key) {
            return key.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
        },

        _formatValue(key, val) {
            if (val === null || val === undefined) return '—';
            if (typeof val === 'boolean') return val ? 'Yes' : 'No';

            const pctKeys = ['win_rate', 'loss_rate', 'expectancy_pct'];
            const rrKeys = ['avg_win_rr', 'avg_loss_rr', 'expectancy_rr', 'profit_factor'];

            if (pctKeys.some(function (k) { return key.includes(k); })) {
                return (parseFloat(val) * 100).toFixed(1) + '%';
            }
            if (rrKeys.some(function (k) { return key.includes(k); })) {
                return parseFloat(val).toFixed(2) + 'R';
            }
            if (typeof val === 'number') {
                if (Number.isInteger(val)) return val.toString();
                return val.toFixed(2);
            }
            return String(val);
        },

        _shouldColorize(key) {
            const colorKeys = ['expectancy', 'pnl', 'profit', 'net'];
            return colorKeys.some(function (k) { return key.toLowerCase().includes(k); });
        },

        // ── Error display ─────────────────────────────────────────────────────

        _showError(msg) {
            const container = document.getElementById('bt-metrics');
            if (!container) return;
            clearChildren(container);
            const el = createEl('div', { className: 'metric-row' });
            el.style.color = '#f44336';
            el.textContent = msg;
            container.appendChild(el);

            const resultsEl = document.getElementById('bt-results');
            if (resultsEl) resultsEl.style.display = 'block';
        },

        // ── Trade markers ─────────────────────────────────────────────────────

        /**
         * Set trade markers on the main chart series.
         * trades: [{time, direction, result}]  (time: unix seconds)
         */
        _renderTradeMarkers(trades) {
            // Resolve the main series — chart.js exposes Chart.candleSeries
            const series = (typeof Chart !== 'undefined' && Chart.candleSeries)
                ? Chart.candleSeries
                : null;
            if (!series) return;

            const markers = trades.map(function (t) {
                const isLong = t.direction === 'long';
                const isWin = t.result === 'win';
                return {
                    time: t.time,
                    position: isLong ? 'belowBar' : 'aboveBar',
                    color: isWin ? '#4caf50' : '#f44336',
                    shape: isLong ? 'arrowUp' : 'arrowDown',
                    text: isWin ? 'W' : 'L',
                    size: 1,
                };
            });

            // Sort markers by time (required by LW Charts)
            markers.sort(function (a, b) { return a.time - b.time; });

            try {
                series.setMarkers(markers);
            } catch (e) {
                // Series type may not support markers; fail silently
            }
        },

        /** Clear all trade markers from the main series. */
        _clearTradeMarkers() {
            const series = (typeof Chart !== 'undefined' && Chart.candleSeries)
                ? Chart.candleSeries
                : null;
            if (!series) return;
            try { series.setMarkers([]); } catch (e) { /* ignore */ }
        },

        // ── Equity curve ──────────────────────────────────────────────────────

        /**
         * Render (or update) the equity curve area chart in #equity-container.
         * equityCurve: [{time, value}]  (time: unix seconds)
         */
        _renderEquityCurve(equityCurve) {
            const container = document.getElementById('equity-container');
            if (!container) return;

            if (!equityCurve || equityCurve.length === 0) {
                container.style.display = 'none';
                this._destroyEquityChart();
                return;
            }

            container.style.display = 'block';

            // Destroy and recreate if already exists (simplest safe approach)
            this._destroyEquityChart();

            const chart = LightweightCharts.createChart(container, {
                layout: {
                    background: { type: 'solid', color: '#1a1a2e' },
                    textColor: '#666',
                    fontSize: 10,
                },
                grid: {
                    vertLines: { visible: false },
                    horzLines: { color: '#1e1e30' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                timeScale: {
                    borderColor: '#333',
                    timeVisible: true,
                    secondsVisible: false,
                },
                rightPriceScale: {
                    borderColor: '#333',
                    scaleMargins: { top: 0.1, bottom: 0.1 },
                },
                handleScroll: { vertTouchDrag: false },
            });

            const areaSeries = chart.addAreaSeries({
                lineColor: '#448aff',
                topColor: 'rgba(68, 138, 255, 0.25)',
                bottomColor: 'rgba(68, 138, 255, 0.02)',
                lineWidth: 1,
                priceLineVisible: false,
                lastValueVisible: true,
            });

            // Sort by time (defensive)
            const sorted = equityCurve.slice().sort(function (a, b) { return a.time - b.time; });
            areaSeries.setData(sorted);
            chart.timeScale().fitContent();

            this._equityChart = chart;
            this._equitySeries = areaSeries;
        },

        _destroyEquityChart() {
            if (this._equityChart) {
                try { this._equityChart.remove(); } catch (e) { /* ignore */ }
                this._equityChart = null;
                this._equitySeries = null;
            }
        },

        // ── Sweep table ───────────────────────────────────────────────────────

        /**
         * Render the sweep results table.
         * rows: [{config: {...}, metrics: {...}}]
         */
        _renderSweepTable(rows) {
            const table = document.getElementById('bt-sweep-table');
            if (!table) return;

            const thead = table.querySelector('thead tr');
            const tbody = table.querySelector('tbody');
            clearChildren(thead);
            clearChildren(tbody);

            if (!rows || rows.length === 0) {
                const td = createEl('td', { colSpan: 1 }, 'No results');
                const tr = createEl('tr');
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            // Determine columns: config keys + top-level metric keys
            const firstRow = rows[0];
            const configKeys = Object.keys(firstRow.config || {}).filter(function (k) {
                return k !== 'symbol' && k !== 'tf' && k !== 'end_date' && k !== 'bar_count';
            });
            const metricKeys = Object.keys(firstRow.metrics || {}).filter(function (k) {
                return typeof firstRow.metrics[k] !== 'object';
            });
            const columns = configKeys.concat(metricKeys);

            // Header
            columns.forEach(function (col) {
                const th = createEl('th', null, Backtest._formatLabel(col));
                th.addEventListener('click', function () {
                    Backtest._sortSweepBy(col);
                });
                thead.appendChild(th);
            });

            // Rows
            const self = this;
            rows.forEach(function (row, idx) {
                const tr = document.createElement('tr');
                if (self._selectedSweepRow === idx) tr.className = 'selected';

                columns.forEach(function (col) {
                    let rawVal = null;
                    if (configKeys.includes(col)) {
                        rawVal = (row.config || {})[col];
                    } else {
                        rawVal = (row.metrics || {})[col];
                    }
                    const td = createEl('td', null, Backtest._formatValue(col, rawVal));
                    tr.appendChild(td);
                });

                tr.addEventListener('click', function () {
                    self._onSweepRowClick(idx, rows[idx], tr);
                });
                tbody.appendChild(tr);
            });
        },

        _sortSweepBy(col) {
            if (this._sweepSortCol === col) {
                this._sweepSortAsc = !this._sweepSortAsc;
            } else {
                this._sweepSortCol = col;
                this._sweepSortAsc = false; // default: best (highest) first
            }

            const asc = this._sweepSortAsc;
            const sorted = this._sweepData.slice().sort(function (a, b) {
                const aVal = Backtest._getSweepColValue(a, col);
                const bVal = Backtest._getSweepColValue(b, col);
                if (typeof aVal === 'number' && typeof bVal === 'number') {
                    return asc ? aVal - bVal : bVal - aVal;
                }
                const aStr = String(aVal);
                const bStr = String(bVal);
                return asc ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
            });

            this._selectedSweepRow = null;
            this._renderSweepTable(sorted);
        },

        _getSweepColValue(row, col) {
            const configKeys = Object.keys(row.config || {});
            if (configKeys.includes(col)) return (row.config || {})[col];
            return (row.metrics || {})[col];
        },

        /** Click a sweep row: highlight it, load its trades and equity curve. */
        async _onSweepRowClick(idx, row, trEl) {
            // Update selection highlight
            const tbody = document.getElementById('bt-sweep-table').querySelector('tbody');
            tbody.querySelectorAll('tr').forEach(function (r) { r.className = ''; });
            trEl.className = 'selected';
            this._selectedSweepRow = idx;

            // Load trades for this config by running a single backtest
            if (!row.config) return;
            const runBtn = document.getElementById('bt-run-btn');
            try {
                const resp = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(row.config),
                });
                if (!resp.ok) return;
                const data = await resp.json();
                this._renderTradeMarkers(data.trades || []);
                this._renderEquityCurve(data.equity_curve || []);

                // Show metrics in the results panel without hiding sweep table
                this._renderMetrics(data.metrics || {});
                const resultsEl = document.getElementById('bt-results');
                if (resultsEl) resultsEl.style.display = 'block';

            } catch (e) {
                // fail silently on sweep row click
            }
        },
    };

    // ── Boot ──────────────────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {
        Backtest.init();
    });

    // Expose for console debugging
    window.Backtest = Backtest;

})();
