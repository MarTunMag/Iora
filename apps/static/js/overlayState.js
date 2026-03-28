/**
 * overlayState.js — Canonical overlay state owner for single-chart and multichart modes.
 *
 * Two-mode architecture:
 *   - 'single': sidebar checkboxes write to OverlayState.single, chart reads from it
 *   - 'multichart': per-panel state lives in MultiChart.charts[i].overlays/overlayConfig
 *     (independent by design — panels diverge after initialization)
 *
 * Key contract: when switching FROM single TO multichart, panels are initialized
 * from singleChartState so they start with whatever the user had configured.
 * After that, panels are fully independent.
 */

const OverlayState = {
    activeMode: 'single',  // 'single' | 'multichart'

    // ── Single-chart state (sidebar checkboxes write here) ───────────────
    single: {
        tlTFs: [],
        showSignals: false,
        htfCandleTFs: [],
        htfCandleType: 'ohlc',
        tlCounts: {},
        showContextBands: false,
        structureZones: true,
        structureBreaks: false,
        structureBoundaries: true,
        structureZigzag: false,
        structureBreakers: true,
        structureOpposing: true,
        structureZoneCounts: { parent: 2, child: 3, sub: 0 },
        structureDisplayMode: 'lines',
    },

    /** Build render options for the single-chart Overlays.render() call. */
    getSingleRenderOpts(extra) {
        const s = this.single;
        return Object.assign({
            tlTFs: s.tlTFs,
            htfCandleTFs: s.htfCandleTFs,
            tlCounts: s.tlCounts,
            showSignals: s.showSignals,
            showContextBands: s.showContextBands,
        }, extra || {});
    },

    /**
     * Build initial per-panel overlay state from current single-chart state.
     * Called once per panel when creating the multichart grid.
     * Returns { overlays, overlayConfig } — after this, the panel owns its copy.
     *
     * @param {string} panelTf - The TF this panel will display
     * @param {object} htfMap - MultiChart._htfMap (relevant zone/TL TFs per panel TF)
     * @param {object} htfCandleMap - MultiChart._htfCandleMap (relevant HTF candle TFs)
     */
    buildPanelFromSingle(panelTf, htfMap, htfCandleMap) {
        const s = this.single;
        const allTFs = (App.config && App.config.tf_order_htf_first)
            || ['MN1', 'W1', 'D1', 'H4', 'H1', 'M15', 'M5', 'M1'];

        const relevantTlTFs = htfMap[panelTf] || [panelTf];
        const htfCandleDefs = htfCandleMap[panelTf] || [];

        const overlays = {
            trendlines: false,
            signals: false,
            htfCandles: false,
        };
        const ownIdx = allTFs.indexOf(panelTf);
        const bosDefs = ownIdx >= 0
            ? allTFs.slice(Math.max(0, ownIdx - 1), ownIdx + 1)
            : [panelTf];

        const config = { trendlines: {}, htfCandles: {}, signals: {} };
        allTFs.forEach(t => {
            config.trendlines[t] = {
                on: s.tlTFs.includes(t),
                count: s.tlCounts[t] || 0,
            };
            config.htfCandles[t] = {
                on: htfCandleDefs.includes(t),
            };
            config.signals[t] = { on: bosDefs.includes(t) };
        });

        return { overlays, overlayConfig: config };
    },
};
