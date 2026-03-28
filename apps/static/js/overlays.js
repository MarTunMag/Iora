/**
 * overlays.js — Zone/TL/BOS-CHOCH/HTF rendering via LW Charts primitives.
 *
 * Uses ISeriesPrimitive interface for custom canvas drawing attached to the
 * candlestick series.
 */

const Overlays = {
    // Registered primitives (to remove on re-render)
    _primitives: [],
    _targetChart: null,
    _targetSeries: null,

    // Color palettes now in constants.js: TL_COLORS, TL_WIDTHS,
    // TL_DASH, TL_PARENT, HTF_COLORS

    // ── Main render ─────────────────────────────────────────────────────

    render(data, opts) {
        this._clearPrimitives();
        const series = Chart.getCandleSeries();
        if (!series) return;
        this._renderInternal(series, data, opts);
    },

    /**
     * Render overlays onto an arbitrary series (for multichart panels).
     * Returns array of attached primitives so caller can manage cleanup.
     */
    renderToSeries(chart, series, data, opts) {
        const primitives = [];
        const origPush = this._primitives;
        const origChart = this._targetChart;
        const origSeries = this._targetSeries;
        this._primitives = primitives;
        this._targetChart = chart;
        this._targetSeries = series;

        try {
            this._renderInternal(series, data, opts);
        } finally {
            this._primitives = origPush;
            this._targetChart = origChart;
            this._targetSeries = origSeries;
        }
        return primitives;
    },

    _renderInternal(series, data, opts) {
        const maxTime = opts.maxTime || Infinity;
        const tlCounts = opts.tlCounts || {};
        const sigToggles = opts.signalToggles || { zoneNumbers: true, nesting: true, tlBreaks: true, choch: true };

        // Context mode background bands (behind everything)
        this._renderContextBands(series, data, opts);

        // HTF candles FIRST — behind everything (zOrder: 'bottom')
        // Render higher TFs first so daily candles overlay weekly
        if (data.htf_candles && opts.htfCandleTFs && opts.htfCandleTFs.length > 0 && data.candles) {
            const baseTimes = data.candles.map(c => c.time);
            const htfOrder = (App.config && App.config.tf_order_htf_first) || ['12M', '6M', '3M', 'MN1', 'W1', 'D1', 'H4', 'H1', 'M30', 'M15', 'M5'];
            const sorted = [...opts.htfCandleTFs].sort((a, b) => htfOrder.indexOf(a) - htfOrder.indexOf(b));
            sorted.forEach(tf => {
                const candles = data.htf_candles[tf];
                if (!candles) return;
                this._renderHtfCandles(series, candles, tf, maxTime, baseTimes, data.candles);
            });
        }

        // Initialize marker arrays BEFORE rendering (TL renderers push to these)
        this._tlBreakMarkers = [];
        this._chochMarkers = [];

        // Trendlines — cascading clip (child TL stops at parent TL)
        // LTF TLs are scoped to the parent's last zone origin time
        if (data.trendlines && opts.tlTFs) {
            const activeTLs = {};
            // Collect latest zone origin time per TF (most recent unbroken zone)
            const latestZoneTime = {};
            if (data.zones) {
                for (const [tf, zones] of Object.entries(data.zones)) {
                    const unbroken = zones.filter(z => !z.is_broken);
                    if (unbroken.length > 0) {
                        latestZoneTime[tf] = Math.max(...unbroken.map(z => z.origin_time));
                    }
                }
            }
            opts.tlTFs.forEach(tf => {
                const tls = data.trendlines[tf];
                if (!tls) return;
                const actives = tls.filter(tl => tl.active);
                activeTLs[tf] = actives;
            });
            opts.tlTFs.forEach(tf => {
                const tls = data.trendlines[tf];
                if (!tls) return;
                const parentTf = TL_PARENT[tf];
                const parentActiveTLs = parentTf ? (activeTLs[parentTf] || []) : [];
                // Scope: use parent's latest zone origin as the "current move" reference
                const parentZoneTime = parentTf ? latestZoneTime[parentTf] : null;
                this._renderTrendlines(series, tls, tf, maxTime, tlCounts[tf] || 0, parentActiveTLs, parentZoneTime);
            });
        }

        // BOS/CHOCH — now handled by structure.js Breaks sub-primitive

        // Signal markers + TL break markers
        const allSignals = [];
        if (data.rule_signals && opts.showSignals) {
            allSignals.push(...data.rule_signals);
        }
        // TL break markers (controlled by toggle)
        if (sigToggles.tlBreaks && this._tlBreakMarkers && this._tlBreakMarkers.length > 0) {
            allSignals.push(...this._tlBreakMarkers);
        }
        // CHoCH entry markers (HL/LH = entry signals)
        if (sigToggles.choch && this._chochMarkers && this._chochMarkers.length > 0) {
            allSignals.push(...this._chochMarkers);
        }
        if (allSignals.length > 0) {
            this._renderCascadeMarkers(series, allSignals, maxTime, data.candles, opts.signalTFs);
        }
    },

    _clearPrimitives() {
        const series = Chart.getCandleSeries();
        if (!series) return;
        this._primitives.forEach(p => {
            try { series.detachPrimitive(p); } catch(e) {}
        });
        this._primitives = [];
        // Also clear markers
        if (series.setMarkers) {
            series.setMarkers([]);
        }
    },

    // ── Cascade signal markers ───────────────────────────────────────────

    _renderCascadeMarkers(series, signals, maxTime, candles, signalTFs) {
        if (!signals || signals.length === 0 || !candles) return;

        // Build set of valid candle times for snapping
        const validTimes = new Set(candles.map(c => c.time));

        // Filter by TF if provided (multichart per-panel filtering)
        const tfSet = signalTFs && signalTFs.length > 0 ? new Set(signalTFs) : null;

        // Filter and snap signal times to nearest candle
        const markers = [];
        signals.forEach(sig => {
            if (sig.time > maxTime) return;
            if (tfSet && sig.tf && !tfSet.has(sig.tf)) return;
            // Priority filtering is done server-side (priority <= 2 only)

            // Snap to nearest valid candle time (binary search)
            let snapTime = sig.time;
            if (!validTimes.has(sig.time)) {
                let lo = 0, hi = candles.length - 1;
                while (lo < hi) {
                    const mid = (lo + hi) >> 1;
                    if (candles[mid].time < sig.time) lo = mid + 1;
                    else hi = mid;
                }
                if (lo === 0) {
                    snapTime = candles[0].time;
                } else {
                    const before = candles[lo - 1].time;
                    const after = candles[lo].time;
                    snapTime = (sig.time - before <= after - sig.time) ? before : after;
                }
            }

            markers.push({
                time: snapTime,
                position: sig.position,
                color: sig.color,
                shape: sig.shape,
                size: sig.size,
                text: sig.text,
            });
        });

        // LW Charts requires markers sorted by time
        markers.sort((a, b) => a.time - b.time);

        // Deduplicate same time+position (keep highest priority)
        const seen = new Set();
        const deduped = [];
        markers.forEach(m => {
            const key = `${m.time}_${m.position}`;
            if (!seen.has(key)) {
                seen.add(key);
                deduped.push(m);
            }
        });

        if (deduped.length > 0) {
            series.setMarkers(deduped);
        }
    },

    // ── Trendline rendering ─────────────────────────────────────────────

    _renderTrendlines(series, tls, tf, maxTime, countLimit, parentActiveTLs, parentAnchorTime) {
        const colors = TL_COLORS[tf] || TL_COLORS.H1;
        const width = TL_WIDTHS[tf] || 1;
        const dash = TL_DASH[tf] || [];

        let filtered = tls.filter(tl => tl.t1 <= maxTime);
        if (countLimit > 0) {
            // Keep all active TLs, then fill remaining slots with most recent history
            const active = filtered.filter(tl => tl.active && !tl.is_broken);
            const inactive = filtered.filter(tl => !tl.active || tl.is_broken);
            const historySlots = Math.max(0, countLimit - active.length);
            filtered = [...inactive.slice(-historySlots), ...active];
        }

        filtered.forEach(tl => {
            // Style based on broken / xtf impulse / xtf correction / regular
            let tlColor, tlWidth, tlDash, tlOpacity;
            if (tl.is_broken) {
                // Broken: gray dotted, stop at break point
                tlColor = '#666';
                tlWidth = 1;
                tlDash = [3, 3];
                tlOpacity = 0.35;
            } else if (tl.xtf && tl.tl_type === 'correction') {
                // Correction TL: dashed — pullback within trend
                // Min width 1.2 so LTF corrections stay visible
                tlColor = colors[tl.direction] || '#888';
                tlWidth = Math.max(1.2, width * 0.7);
                tlDash = [6, 4];
                tlOpacity = tl.active ? 0.85 : 0.3;
            } else if (tl.xtf && tl.tl_type === 'impulse') {
                // Impulse TL: solid — main trend push
                // Min width 1.5 so LTF impulse TLs stay clearly visible
                tlColor = colors[tl.direction] || '#888';
                tlWidth = Math.max(1.5, width);
                tlDash = [];  // Always solid for impulse XTF
                tlOpacity = tl.active ? 1.0 : 0.4;
            } else if (tl.xtf) {
                // XTF without type (fallback)
                tlColor = colors[tl.direction] || '#888';
                tlWidth = Math.max(1.5, width);
                tlDash = dash;
                tlOpacity = tl.active ? 1.0 : 0.4;
            } else {
                // Regular pivot TL
                tlColor = colors[tl.direction] || '#888';
                tlWidth = width;
                tlDash = dash;
                tlOpacity = tl.active ? 1.0 : 0.4;
            }

            // Scope to parent zone: history TLs from before the parent's last zone get dimmed
            // Active TLs are NEVER dimmed — they represent the current structure
            if (parentAnchorTime && tl.t2 < parentAnchorTime && !tl.is_broken && !tl.active) {
                tlOpacity *= 0.15;
            }

            // For active TLs, find clip point at parent TF's TL intersection
            let clipTime = null, clipPrice = null;
            if (tl.active && !tl.is_broken && parentActiveTLs && parentActiveTLs.length > 0) {
                let nearestT = Infinity;
                parentActiveTLs.forEach(ptl => {
                    const ix = this._tlIntersection(tl, ptl);
                    if (ix && ix.t > tl.t2 && ix.t < nearestT) {
                        nearestT = ix.t;
                        clipTime = ix.t;
                        clipPrice = ix.p;
                    }
                });
            }

            // Broken TLs: clip at break time
            let breakClipTime = null;
            if (tl.is_broken && tl.break_time) {
                breakClipTime = tl.break_time;
            }

            // Label: impulse gets ▸, correction gets ◂
            let label;
            if (tl.xtf) {
                const typeTag = tl.tl_type === 'impulse' ? '▸' : '◂';
                label = `${tf}${typeTag}${tl.anchor_source}`;
            } else {
                label = tf;
            }

            const prim = new TrendlinePrimitive(
                tl.t1, tl.p1, tl.t2, tl.p2,
                tlColor, tlWidth, tlDash, tlOpacity,
                tl.active && !tl.is_broken,
                label,
                clipTime, clipPrice,
                this._targetChart, this._targetSeries,
                breakClipTime,
            );
            series.attachPrimitive(prim);
            this._primitives.push(prim);

            // TL break marker — small ✕ at break point
            if (tl.is_broken && tl.break_time && tl.break_price && this._tlBreakMarkers) {
                const breakLabel = `${tf} ${tl.tl_type === 'impulse' ? 'IMP' : 'COR'} break`;
                const breakDir = tl.direction === 'bull' ? 'belowBar' : 'aboveBar';
                const breakShape = tl.direction === 'bull' ? 'arrowDown' : 'arrowUp';
                this._tlBreakMarkers.push({
                    time: tl.break_time,
                    position: breakDir,
                    shape: breakShape,
                    color: tl.direction === 'bull' ? '#ff6666' : '#66ff66',
                    text: breakLabel,
                    size: 1,
                });
            }
        });
    },

    /** Calculate intersection point of two trendlines (as unix timestamps + price). */
    _tlIntersection(tl1, tl2) {
        const dt1 = tl1.t2 - tl1.t1;
        const dt2 = tl2.t2 - tl2.t1;
        if (Math.abs(dt1) < 1 || Math.abs(dt2) < 1) return null;
        const s1 = (tl1.p2 - tl1.p1) / dt1;
        const s2 = (tl2.p2 - tl2.p1) / dt2;
        // Parallel lines don't intersect
        if (Math.abs(s1 - s2) < 1e-15) return null;
        // p1_1 + s1*(t - t1_1) = p1_2 + s2*(t - t1_2)
        const t = (tl2.p1 - tl1.p1 + s1 * tl1.t1 - s2 * tl2.t1) / (s1 - s2);
        const p = tl1.p1 + s1 * (t - tl1.t1);
        return { t, p };
    },

    // BOS/CHOCH — removed, now handled by structure.js Breaks sub-primitive

    // ── HTF candle rendering ────────────────────────────────────────────

    _renderHtfCandles(series, candles, tf, maxTime, baseTimes, baseCandles) {
        const color = HTF_COLORS[tf] || 'rgba(100, 181, 246, 0.08)';
        // Include candles that have started (time <= maxTime), even if not closed yet
        const filtered = candles.filter(c => c.time <= maxTime);
        if (filtered.length === 0) return;
        const prim = new HtfCandleBatchPrimitive(filtered, color, tf, baseTimes, this._targetChart, this._targetSeries, maxTime, baseCandles);
        series.attachPrimitive(prim);
        this._primitives.push(prim);
    },

    // ── Context mode background bands ─────────────────────────────────
    _renderContextBands(series, data, opts) {
        if (!opts.showContextBands || !data.context) return;
        const contextData = data.context;
        if (!contextData.length) return;

        // Group contiguous same-mode regions
        const regions = [];
        let i = 0;
        while (i < contextData.length) {
            const mode = contextData[i].mode;
            const color = CONTEXT_MODE_COLORS[mode];
            if (!color || mode === 'SKIP') { i++; continue; }

            let j = i + 1;
            while (j < contextData.length && contextData[j].mode === mode) j++;

            regions.push({
                startTime: contextData[i].time,
                endTime: contextData[j - 1].time,
                mode: mode,
                color: color,
            });
            i = j;
        }

        if (!regions.length) return;

        const prim = new ContextBandPrimitive(regions, this._targetChart, this._targetSeries);
        series.attachPrimitive(prim);
        this._primitives.push(prim);
    },
};


// ═══════════════════════════════════════════════════════════════════════════
// Context band primitive — full-height background bands colored by mode
// ═══════════════════════════════════════════════════════════════════════════

class ContextBandPrimitive {
    constructor(regions, chart, series) {
        this._regions = regions;  // [{startTime, endTime, mode, color}]
        this._chart = chart || null;
        this._series = series || null;
        this._paneViews = [new ContextBandPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class ContextBandPaneView {
    constructor(source) { this._source = source; this._renderer = new ContextBandRenderer(source); }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'bottom'; }
}

class ContextBandRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const chart = this._source._chart || Chart.getChart();
            if (!chart) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const timeScale = chart.timeScale();
            const height = scope.bitmapSize.height;

            for (const r of this._source._regions) {
                const x1 = timeScale.timeToCoordinate(r.startTime);
                const x2 = timeScale.timeToCoordinate(r.endTime);
                if (x1 === null || x2 === null) continue;

                const bx1 = Math.round(x1 * hr);
                const bx2 = Math.round(x2 * hr);

                ctx.fillStyle = r.color;
                ctx.fillRect(
                    Math.min(bx1, bx2),
                    0,
                    Math.abs(bx2 - bx1) + Math.round(hr),
                    height
                );
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// Custom primitives using ISeriesPrimitive interface
// ═══════════════════════════════════════════════════════════════════════════

/**
 * TrendlinePrimitive — Renders a trendline between two price/time points.
 */
// TFs whose active TLs extend as rays
const RAY_TFS = new Set(['MN1', 'W1', 'D1', 'H4']);

class TrendlinePrimitive {
    constructor(t1, p1, t2, p2, color, width, dash, opacity, active, tfLabel, clipTime, clipPrice, chart, series, breakClipTime) {
        this._t1 = t1; this._p1 = p1;
        this._t2 = t2; this._p2 = p2;
        this._color = color;
        this._width = width;
        this._dash = dash;
        this._opacity = opacity;
        this._active = active;
        this._tfLabel = tfLabel || '';
        this._clipTime = clipTime || null;
        this._clipPrice = clipPrice || null;
        this._chart = chart || null;
        this._series = series || null;
        this._breakClipTime = breakClipTime || null;
        this._paneViews = [new TrendlinePaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class TrendlinePaneView {
    constructor(source) { this._source = source; this._renderer = new TrendlineRenderer(source); }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'bottom'; }
}

class TrendlineRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const s = this._source;
            const chart = s._chart || Chart.getChart();
            const series = s._series || Chart.getCandleSeries();
            if (!chart || !series) return;

            const ts = chart.timeScale();
            const x1 = ts.timeToCoordinate(s._t1);
            const x2 = ts.timeToCoordinate(s._t2);
            if (x1 === null || x2 === null) return;

            const y1 = series.priceToCoordinate(s._p1);
            const y2 = series.priceToCoordinate(s._p2);
            if (y1 === null || y2 === null) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;

            ctx.globalAlpha = s._opacity;
            ctx.strokeStyle = s._color;
            ctx.lineWidth = s._width * hr;
            if (s._dash.length > 0) {
                ctx.setLineDash(s._dash.map(d => d * hr));
            } else {
                ctx.setLineDash([]);
            }

            ctx.beginPath();
            ctx.moveTo(x1 * hr, y1 * vr);

            // Determine end point: broken TLs stop at break, active extend
            let endX, endY;
            if (s._breakClipTime !== null) {
                // Broken TL: extend from anchors to break point
                const bx = ts.timeToCoordinate(s._breakClipTime);
                if (bx !== null && Math.abs(x2 - x1) > 0.001) {
                    const slope = (y2 - y1) / (x2 - x1);
                    endX = bx;
                    endY = y1 + slope * (bx - x1);
                } else {
                    endX = x2; endY = y2;
                }
            } else if (s._active) {
                if (s._clipTime !== null && s._clipPrice !== null) {
                    const cx = ts.timeToCoordinate(s._clipTime);
                    const cy = series.priceToCoordinate(s._clipPrice);
                    if (cx !== null && cy !== null) {
                        endX = cx; endY = cy;
                    } else {
                        endX = x2; endY = y2;
                    }
                } else if (RAY_TFS.has(s._tfLabel.split('⊂')[0])) {
                    // Top-level TFs (including XTF W1⊂D1) extend to right edge
                    const chartWidth = scope.bitmapSize.width / hr;
                    const dx = x2 - x1;
                    const dy = y2 - y1;
                    if (Math.abs(dx) > 0.001) {
                        const slope = dy / dx;
                        endX = chartWidth;
                        endY = y1 + slope * (endX - x1);
                    } else {
                        endX = x2; endY = y2;
                    }
                } else {
                    endX = x2; endY = y2;
                }
            } else {
                endX = x2;
                endY = y2;
            }
            ctx.lineTo(endX * hr, endY * vr);
            ctx.stroke();

            // Draw TF label near the second anchor point
            if (s._tfLabel) {
                const labelX = x2 * hr;
                const labelY = y2 * vr;
                const fontSize = Math.round(11 * hr);
                ctx.font = `bold ${fontSize}px sans-serif`;
                ctx.fillStyle = s._color;
                ctx.globalAlpha = Math.min(s._opacity + 0.2, 1.0);
                // Offset label above for bear TLs, below for bull TLs
                const offsetY = (s._p2 < s._p1) ? -8 * vr : 12 * vr;
                ctx.fillText(s._tfLabel, labelX + 4 * hr, labelY + offsetY);
            }

            ctx.globalAlpha = 1.0;
            ctx.setLineDash([]);
        });
    }
}


/**
 * HtfCandleBatchPrimitive — Renders all HTF candles for a single TF as
 * semi-transparent background candles spanning their full time range.
 * Each candle stretches from time to time_end (next candle's open).
 */
class HtfCandleBatchPrimitive {
    constructor(candles, color, tf, baseTimes, chart, series, maxTime, baseCandles) {
        this._candles = candles;
        this._color = color;
        this._tf = tf;
        this._baseTimes = baseTimes || [];
        this._chart = chart || null;
        this._series = series || null;
        this._maxTime = maxTime || Infinity;
        this._baseCandles = baseCandles || [];
        this._paneViews = [new HtfCandleBatchPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }

    /** Snap a timestamp to the nearest base bar time using binary search. */
    snapTime(t) {
        const bt = this._baseTimes;
        if (bt.length === 0) return t;
        let lo = 0, hi = bt.length - 1;
        while (lo < hi) {
            const mid = (lo + hi) >> 1;
            if (bt[mid] < t) lo = mid + 1;
            else hi = mid;
        }
        // lo is the first element >= t; check lo and lo-1 for closest
        if (lo === 0) return bt[0];
        const diff0 = Math.abs(bt[lo] - t);
        const diff1 = Math.abs(bt[lo - 1] - t);
        return diff1 <= diff0 ? bt[lo - 1] : bt[lo];
    }
}

class HtfCandleBatchPaneView {
    constructor(source) { this._source = source; this._renderer = new HtfCandleBatchRenderer(source); }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'bottom'; }
}

class HtfCandleBatchRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const s = this._source;
            const chart = s._chart || Chart.getChart();
            const series = s._series || Chart.getCandleSeries();
            if (!chart || !series) return;

            const ts = chart.timeScale();
            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;

            // Parse base alpha from the color string (e.g. 'rgba(100, 181, 246, 0.10)')
            const alphaMatch = s._color.match(/rgba?\([^)]*,\s*([\d.]+)\s*\)/);
            const baseAlpha = alphaMatch ? parseFloat(alphaMatch[1]) : 0.10;

            // TF-specific color palettes:
            // W1/MN1 = orange tints, D1 and below = blue/red
            const tf = s._tf;
            const isOrangeTF = (tf === 'W1' || tf === 'MN1' || tf === '3M' || tf === '6M' || tf === '12M');
            const bullRGB = isOrangeTF ? '255, 180, 50' : '68, 138, 255';
            const bearRGB = isOrangeTF ? '200, 100, 30' : '255, 60, 60';
            const wickWidth = 2;
            const borderWidth = isOrangeTF ? 1.5 : 1;

            const maxTime = s._maxTime;
            const baseArr = s._baseCandles;

            for (const c of s._candles) {
                // Determine if this is a forming (incomplete) candle
                const isForming = c.time <= maxTime && c.time_end > maxTime;
                let cOpen = c.open, cHigh = c.high, cLow = c.low, cClose = c.close;
                let formingEnd = c.time_end;

                if (isForming && baseArr.length > 0) {
                    // Compute OHLC from base candles within [c.time, maxTime]
                    // Binary search for start index
                    let lo = 0, hi = baseArr.length;
                    while (lo < hi) {
                        const mid = (lo + hi) >> 1;
                        if (baseArr[mid].time < c.time) lo = mid + 1; else hi = mid;
                    }
                    let first = true;
                    for (let j = lo; j < baseArr.length && baseArr[j].time <= maxTime; j++) {
                        const b = baseArr[j];
                        if (first) { cOpen = b.open; cHigh = b.high; cLow = b.low; first = false; }
                        else { cHigh = Math.max(cHigh, b.high); cLow = Math.min(cLow, b.low); }
                        cClose = b.close;
                    }
                    if (first) continue; // no base bars in range
                    // Forming candle extends to maxTime, not the full period end
                    formingEnd = maxTime;
                }

                // Snap HTF times to nearest base bar time so timeToCoordinate works
                const snappedTime = s.snapTime(c.time);
                const snappedEnd = s.snapTime(isForming ? formingEnd : c.time_end);
                const x0 = ts.timeToCoordinate(snappedTime);
                const x1 = ts.timeToCoordinate(snappedEnd);
                if (x0 === null || x1 === null) continue;

                const yHigh = series.priceToCoordinate(cHigh);
                const yLow = series.priceToCoordinate(cLow);
                const yOpen = series.priceToCoordinate(cOpen);
                const yClose = series.priceToCoordinate(cClose);
                if (yHigh === null || yLow === null || yOpen === null || yClose === null) continue;

                const bx0 = Math.round(x0 * hr);
                const bx1 = Math.round(x1 * hr);
                const candleWidth = bx1 - bx0;
                if (candleWidth < 1) continue;

                const bullish = cClose >= cOpen;
                const rgb = bullish ? bullRGB : bearRGB;
                const bodyColor = `rgba(${rgb}, ${baseAlpha * 1.5})`;
                const wickColor = `rgba(${rgb}, ${baseAlpha * 0.8})`;
                const borderColor = `rgba(${rgb}, ${baseAlpha * 2.5})`;

                const byHigh = Math.round(yHigh * vr);
                const byLow = Math.round(yLow * vr);
                const byOpen = Math.round(yOpen * vr);
                const byClose = Math.round(yClose * vr);
                const bodyTop = Math.min(byOpen, byClose);
                const bodyBot = Math.max(byOpen, byClose);
                const bodyH = Math.max(bodyBot - bodyTop, 1 * vr);
                const midX = Math.round((bx0 + bx1) / 2);

                // Upper wick (high to body top) — NOT through body
                if (byHigh < bodyTop) {
                    ctx.strokeStyle = borderColor;
                    ctx.lineWidth = Math.max(wickWidth * hr, wickWidth);
                    ctx.beginPath();
                    ctx.moveTo(midX, byHigh);
                    ctx.lineTo(midX, bodyTop);
                    ctx.stroke();
                }

                // Lower wick (body bottom to low) — NOT through body
                if (byLow > bodyBot) {
                    ctx.strokeStyle = borderColor;
                    ctx.lineWidth = Math.max(wickWidth * hr, wickWidth);
                    ctx.beginPath();
                    ctx.moveTo(midX, bodyBot);
                    ctx.lineTo(midX, byLow);
                    ctx.stroke();
                }

                // Body (full-width rectangle from time to time_end)
                ctx.fillStyle = bodyColor;
                ctx.fillRect(bx0, bodyTop, candleWidth, bodyH);

                // Body border — dashed for forming candles
                ctx.strokeStyle = borderColor;
                ctx.lineWidth = borderWidth * hr;
                if (isForming) ctx.setLineDash([4 * hr, 3 * hr]);
                ctx.strokeRect(bx0, bodyTop, candleWidth, bodyH);
                if (isForming) ctx.setLineDash([]);
            }
        });
    }
}
