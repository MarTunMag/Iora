// apps/static/js/structure.js
// Unified Structure module — child/parent zone pairs, BOS/CHoCH events,
// external boundary levels, and zigzag polylines with labels.
//
// Sub-primitives (all follow the ISeriesPrimitive pattern):
//   StructureZonePrimitive      → zone rectangles (parent behind child)
//   StructureBreakPrimitive     → BOS/CHoCH break lines + labels
//   StructureBoundaryPrimitive  → external high/low boundary levels
//   StructureZigzagPrimitive    → zigzag polylines with HH/HL/LH/LL labels

/** Parse ISO string as UTC seconds (append 'Z' if missing so JS doesn't use local TZ). */
function _utcSec(iso) {
    return Math.floor(new Date(iso.endsWith('Z') ? iso : iso + 'Z').getTime() / 1000);
}

const Structure = (() => {
    const _dataByTf = {};       // { 'H4': {...}, 'H1': {...}, ... }
    let _primitives = [];       // [{series, prim}] for cleanup
    let _zonesEnabled = true;
    let _breaksEnabled = false;
    let _boundariesEnabled = true;
    let _zigzagEnabled = false;
    let _breakersEnabled = true;
    let _opposingEnabled = true;
    let _subEnabled = false;
    let _zoneCounts = { parent: 2, child: 3, sub: 0 };
    let _displayMode = 'lines';  // 'lines' | 'rects'

    /** Fetch structure data from server */
    async function load(symbol, tf) {
        try {
            const resp = await fetch('/api/structure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbol, tf }),
            });
            if (!resp.ok) {
                console.warn('Structure fetch failed:', resp.status);
                const info = document.getElementById('status-info');
                if (info) info.textContent = `Structure load failed (${resp.status})`;
                return;
            }
            _dataByTf[tf] = await resp.json();
        } catch (e) {
            console.warn('Structure fetch error:', e);
            const info = document.getElementById('status-info');
            if (info) info.textContent = 'Structure load error';
        }
    }

    /** Render all structure primitives onto chart.
     *  @param {object} chart  - LW Charts chart instance
     *  @param {object} series - Candlestick series to attach primitives to
     *  @param {number} [maxTime] - Unix seconds cutoff for bar replay
     *  @param {string} [tf] - Timeframe key to look up in _dataByTf
     */
    function render(chart, series, maxTime, tf) {
        clear();
        const data = tf ? _dataByTf[tf] : Object.values(_dataByTf)[0];
        if (!data || !series) return;

        // Filter by maxTime for bar replay
        let childZones = data.child_zones || [];
        let parentZones = data.parent_zones || [];
        let events = data.events || [];
        let zigzag = data.zigzag || [];

        if (maxTime) {
            childZones = childZones.filter(z =>
                _utcSec(z.confirm_time) <= maxTime
            );
            parentZones = parentZones.filter(z =>
                _utcSec(z.confirm_time) <= maxTime
            );
            events = events.filter(e =>
                _utcSec(e.time) <= maxTime
            );
            zigzag = zigzag.filter(v =>
                _utcSec(v.time) <= maxTime
            );
        }

        // Add sub-zone filtering
        let subZones = data.sub_zones || [];
        let subEvents = data.sub_events || [];
        let subZigzag = data.sub_zigzag || [];

        if (maxTime) {
            subZones = subZones.filter(z => _utcSec(z.confirm_time) <= maxTime);
            subEvents = subEvents.filter(e => _utcSec(e.time) <= maxTime);
            subZigzag = subZigzag.filter(v => _utcSec(v.time) <= maxTime);
        }

        // Apply client-side count limits (0 = hide level, undefined = show all)
        // Breaker + mitigation zones persist but capped at 2 most recent each
        function _applyCount(zones, count) {
            if (count === 0) return [];
            const breakers = zones.filter(z => z.lifecycle === 'breaker').slice(-2);
            const mitigations = zones.filter(z => z.lifecycle === 'mitigation').slice(-2);
            const rest = zones.filter(z => z.lifecycle !== 'breaker' && z.lifecycle !== 'mitigation');
            const sliced = count > 0 ? rest.slice(-count) : rest;
            // Merge persistent zones back, deduplicate by confirm_time+top+bot
            const seen = new Set(sliced.map(z => z.confirm_time + z.top + z.bot));
            const extras = [...breakers, ...mitigations].filter(z => !seen.has(z.confirm_time + z.top + z.bot));
            return sliced.concat(extras).sort((a, b) =>
                a.confirm_time < b.confirm_time ? -1 : 1
            );
        }
        parentZones = _applyCount(parentZones, _zoneCounts.parent);
        childZones = _applyCount(childZones, _zoneCounts.child);
        if (!_subEnabled) { subZones = []; }
        else { subZones = _applyCount(subZones, _zoneCounts.sub); }

        // 1. Zone rectangles (parent → child → sub)
        if (_zonesEnabled && (childZones.length > 0 || parentZones.length > 0 || subZones.length > 0)) {
            const tfLabels = {
                parent: data.parent_tf || '',
                child: data.child_tf || '',
                sub: data.sub_tf || '',
            };
            const prim = new StructureZonePrimitive(
                childZones, parentZones, subZones, chart, series,
                _breakersEnabled, _opposingEnabled, tfLabels, _displayMode
            );
            series.attachPrimitive(prim);
            _primitives.push({ series, prim });
        }

        // 2. Break lines — child+parent + sub (tag sub events for distinct styling)
        const taggedSubEvents = subEvents.map(e => ({ ...e, _isSub: true }));
        const allEvents = _subEnabled ? events.concat(taggedSubEvents) : events;
        if (_breaksEnabled && allEvents.length > 0) {
            const prim = new StructureBreakPrimitive(allEvents, chart, series);
            series.attachPrimitive(prim);
            _primitives.push({ series, prim });
        }

        // 3. External boundary levels (filter by maxTime to prevent lookahead)
        let extHigh = data.external_high;
        let extLow = data.external_low;
        if (maxTime) {
            // Derive boundaries from parent zones confirmed <= maxTime
            const visibleParent = parentZones.filter(z => !z.is_broken || (z.break_time && _utcSec(z.break_time) > maxTime));
            extHigh = null; extLow = null;
            for (const z of visibleParent) {
                if (z.is_supply) extHigh = { price: z.top, time: z.confirm_time };
                else extLow = { price: z.bot, time: z.confirm_time };
            }
        }
        if (_boundariesEnabled && (extHigh || extLow)) {
            const prim = new StructureBoundaryPrimitive(
                extHigh, extLow, data.parent_tf, chart, series
            );
            series.attachPrimitive(prim);
            _primitives.push({ series, prim });
        }

        // 4. Zigzag — child+parent + sub (tag sub vertices for distinct styling)
        const taggedSubZigzag = subZigzag.map(v => ({ ...v, _isSub: true }));
        const allZigzag = _subEnabled ? zigzag.concat(taggedSubZigzag).sort((a,b) => a.time < b.time ? -1 : 1) : zigzag;
        if (_zigzagEnabled && allZigzag.length > 0) {
            const prim = new StructureZigzagPrimitive(allZigzag, chart, series);
            series.attachPrimitive(prim);
            _primitives.push({ series, prim });
        }
    }

    /** Detach and remove all structure primitives */
    function clear() {
        for (const { series, prim } of _primitives) {
            try { series.detachPrimitive(prim); } catch (_) {}
        }
        _primitives = [];
    }

    function setZonesEnabled(v)      { _zonesEnabled = v; }
    function setBreaksEnabled(v)     { _breaksEnabled = v; }
    function getBreaksEnabled()      { return _breaksEnabled; }
    function setBoundariesEnabled(v) { _boundariesEnabled = v; }
    function setZigzagEnabled(v)     { _zigzagEnabled = v; }
    function setBreakersEnabled(v)   { _breakersEnabled = v; }
    function setOpposingEnabled(v)   { _opposingEnabled = v; }
    function setSubEnabled(v)        { _subEnabled = v; }
    function setZoneCounts(counts)   { _zoneCounts = counts; }
    function getZoneCounts()         { return _zoneCounts; }
    function getData(tf)             { return tf ? _dataByTf[tf] : Object.values(_dataByTf)[0]; }
    function setDisplayMode(mode) { _displayMode = mode; }
    function getDisplayMode()     { return _displayMode; }

    return {
        load,
        render,
        clear,
        setZonesEnabled,
        setBreaksEnabled,
        getBreaksEnabled,
        setBoundariesEnabled,
        setZigzagEnabled,
        setBreakersEnabled,
        setOpposingEnabled,
        setSubEnabled,
        setZoneCounts,
        getZoneCounts,
        getData,
        setDisplayMode,
        getDisplayMode,
    };
})();


// ── Sub-primitive 1: Zone Rectangles (3 levels + lifecycle) ─────────────────
//
// Three zone levels rendered back-to-front: parent → child → sub.
// Colours:
//   Parent supply  → rgb(198,40,40)   red          alpha 0.12, 2px solid, 11px bold
//   Parent demand  → rgb(21,101,192)  blue         alpha 0.12, 2px solid, 11px bold
//   Child  supply  → rgb(255,152,0)   orange       alpha 0.15, 1.5px solid, 11px bold
//   Child  demand  → rgb(0,188,212)   teal         alpha 0.15, 1.5px solid, 11px bold
//   Sub    supply  → rgb(205,220,57)  yellow-green alpha 0.08, 1px dashed, 10px normal
//   Sub    demand  → rgb(128,222,234) cyan         alpha 0.08, 1px dashed, 10px normal
//
// Lifecycle styling:
//   active     → solid fill at level alpha
//   breaker    → diagonal stripe pattern (OffscreenCanvas tile)
//   mitigation → very faint fill (0.03) + dotted border
//   expired    → not rendered
//
// Labels: "{TF} {zone_label}" + lifecycle tag (BREAKER/MITIGATION)
// Opposing nesting: sub zone opposing enclosing child → red glow border + OPPOSING tag

class StructureZonePrimitive {
    constructor(childZones, parentZones, subZones, chart, series, breakersEnabled, opposingEnabled, tfLabels, displayMode) {
        this._childZones = childZones;
        this._parentZones = parentZones;
        this._subZones = subZones;
        this._chart = chart;
        this._series = series;
        this._breakersEnabled = breakersEnabled;
        this._opposingEnabled = opposingEnabled;
        this._tfLabels = tfLabels; // { parent: 'D1', child: 'H4', sub: 'H1' }
        this._displayMode = displayMode || 'lines';
        this._paneViews = [new StructureZonePaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class StructureZonePaneView {
    constructor(source) {
        this._source = source;
        this._renderer = new StructureZoneRenderer(source);
    }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'bottom'; }
}

class StructureZoneRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const chart = this._source._chart;
            const series = this._source._series;
            if (!chart || !series) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const timeScale = chart.timeScale();
            const chartWidth = scope.bitmapSize.width;
            const breakersEnabled = this._source._breakersEnabled;
            const opposingEnabled = this._source._opposingEnabled;
            const tfLabels = this._source._tfLabels || {};

            // Label collision tracking — shared across all draw functions
            const _labelRects = [];
            const _tryPlaceLabel = (x, y, w, h) => {
                // Check overlap with already-placed labels
                for (const r of _labelRects) {
                    if (x < r.x + r.w && x + w > r.x &&
                        y < r.y + r.h && y + h > r.y) {
                        return false;
                    }
                }
                _labelRects.push({ x, y, w, h });
                return true;
            };
            // Try placing label, nudging down up to 3 times on collision
            const _placeLabel = (x, y, w, h, maxNudges) => {
                const nudge = h + 2 * vr;
                for (let i = 0; i <= (maxNudges || 3); i++) {
                    const ny = y + i * nudge;
                    if (_tryPlaceLabel(x, ny, w, h)) return ny;
                }
                return null; // skip label entirely
            };

            // Stripe pattern cache
            const _patternCache = {};
            const getStripePattern = (r, g, b, alpha) => {
                const key = `${r},${g},${b},${alpha}`;
                if (_patternCache[key]) return _patternCache[key];
                const tile = new OffscreenCanvas(8, 8);
                const tCtx = tile.getContext('2d');
                tCtx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
                tCtx.beginPath();
                tCtx.moveTo(0, 8); tCtx.lineTo(3, 8); tCtx.lineTo(8, 3); tCtx.lineTo(8, 0);
                tCtx.lineTo(5, 0); tCtx.lineTo(0, 5);
                tCtx.closePath();
                tCtx.fill();
                const pat = ctx.createPattern(tile, 'repeat');
                _patternCache[key] = pat;
                return pat;
            };

            /**
             * Draw zones for one level.
             * @param {Array}    zones
             * @param {number[]} supplyRGB    - [r,g,b]
             * @param {number[]} demandRGB    - [r,g,b]
             * @param {number}   activeAlpha  - Fill opacity when active
             * @param {number}   brokenAlpha  - Fill opacity when broken (unused for breaker/mitigation which have own styling)
             * @param {number}   borderWidth  - CSS px
             * @param {string}   borderStyle  - "solid" | "dashed"
             * @param {number}   fontSize     - CSS px
             * @param {boolean}  bold
             * @param {string}   levelPrefix  - TF label (e.g. "D1", "H4", "H1")
             */
            const drawZones = (zones, supplyRGB, demandRGB, activeAlpha, brokenAlpha,
                               borderWidth, borderStyle, fontSize, bold, levelPrefix) => {
                for (const z of zones) {
                    if (z.lifecycle === 'expired') continue;
                    if (z.is_broken && !breakersEnabled) continue;

                    const rgb = z.is_supply ? supplyRGB : demandRGB;

                    const confirmSec = _utcSec(z.confirm_time);
                    const breakSec = z.break_time ? _utcSec(z.break_time) : null;

                    const x0 = timeScale.timeToCoordinate(confirmSec);
                    const y0 = series.priceToCoordinate(z.top);
                    const y1 = series.priceToCoordinate(z.bot);
                    if (y0 === null || y1 === null || x0 === null) continue;

                    const bx0 = Math.round(x0 * hr);
                    let bx1;
                    if (z.is_broken && breakSec) {
                        const xBreak = timeScale.timeToCoordinate(breakSec);
                        bx1 = xBreak !== null ? Math.round(xBreak * hr) : chartWidth;
                    } else {
                        bx1 = chartWidth;
                    }

                    const by0 = Math.round(Math.min(y0, y1) * vr);
                    const byH = Math.round(Math.abs(y1 - y0) * vr);

                    // Fill based on lifecycle
                    ctx.save();
                    if (z.lifecycle === 'breaker') {
                        ctx.globalAlpha = 0.06;
                        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
                        ctx.fillRect(bx0, by0, bx1 - bx0, byH);
                    } else if (z.lifecycle === 'mitigation') {
                        ctx.globalAlpha = 0.03;
                        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
                        ctx.fillRect(bx0, by0, bx1 - bx0, byH);
                    } else {
                        ctx.globalAlpha = activeAlpha;
                        ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
                        ctx.fillRect(bx0, by0, bx1 - bx0, byH);
                    }
                    ctx.restore();

                    // Border
                    ctx.save();
                    ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${z.is_broken ? 0.25 : 0.5})`;
                    ctx.lineWidth = Math.ceil(borderWidth * hr);
                    if (z.lifecycle === 'mitigation') {
                        ctx.setLineDash([2 * hr, 2 * hr]);
                    } else if (borderStyle === 'dashed' || (z.is_broken && z.lifecycle !== 'breaker')) {
                        ctx.setLineDash([3 * hr, 3 * hr]);
                    } else {
                        ctx.setLineDash([]);
                    }
                    ctx.strokeRect(bx0, by0, bx1 - bx0, byH);
                    ctx.setLineDash([]);
                    ctx.restore();

                    // Zone label: "{TF} {label}" with collision avoidance
                    if (z.label) {
                        const fSize = Math.round(fontSize * vr);
                        ctx.save();
                        ctx.font = `${bold ? 'bold ' : ''}${fSize}px sans-serif`;
                        let labelText = `${levelPrefix} ${z.label}`;
                        if (z.lifecycle === 'breaker') labelText += ' BREAKER';
                        else if (z.lifecycle === 'mitigation') labelText += ' MIT';
                        const lw = ctx.measureText(labelText).width + 8 * hr;
                        const lh = fSize + 4 * vr;
                        const lx = bx0 + 4 * hr;
                        const baseY = by0 + 2 * vr;
                        const placedY = _placeLabel(lx, baseY, lw, lh, 3);
                        if (placedY !== null) {
                            ctx.textAlign = 'left';
                            ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${z.is_broken ? 0.5 : 0.8})`;
                            ctx.fillText(labelText, lx, placedY + fSize);
                        }
                        ctx.restore();
                    }
                }
            };

            /**
             * Draw zones as single horizontal lines at key price level.
             * Supply → line at zone.top, Demand → line at zone.bot.
             * Breaker zones skip this — always rendered as rectangles.
             */
            const drawLines = (zones, supplyRGB, demandRGB, lineWidth, dashPattern,
                               opacity, brokenOpacity, fontSize, bold, levelPrefix) => {
                for (const z of zones) {
                    if (z.lifecycle === 'expired') continue;
                    if (z.is_broken && !breakersEnabled) continue;
                    // Breaker zones rendered as rectangles below — skip here
                    if (z.lifecycle === 'breaker') continue;

                    const rgb = z.is_supply ? supplyRGB : demandRGB;
                    const keyPrice = z.is_supply ? z.top : z.bot;

                    const confirmSec = _utcSec(z.confirm_time);
                    const originSec = z.origin_time ? _utcSec(z.origin_time) : confirmSec;
                    const breakSec = z.break_time ? _utcSec(z.break_time) : null;

                    const yCoord = series.priceToCoordinate(keyPrice);
                    const x0 = timeScale.timeToCoordinate(originSec);
                    if (yCoord === null || x0 === null) continue;

                    const bx0 = Math.round(x0 * hr);
                    let bx1;
                    if (z.is_broken && breakSec) {
                        const xBreak = timeScale.timeToCoordinate(breakSec);
                        bx1 = xBreak !== null ? Math.round(xBreak * hr) : chartWidth;
                    } else {
                        bx1 = chartWidth;
                    }
                    const by = Math.round(yCoord * vr);

                    // Determine opacity by lifecycle state
                    let alpha = opacity;
                    if (z.lifecycle === 'mitigation') {
                        alpha = 0.3;
                    } else if (z.is_broken) {
                        alpha = brokenOpacity;
                    }

                    // Draw the line
                    ctx.save();
                    ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${alpha})`;
                    ctx.lineWidth = Math.ceil(lineWidth * hr);
                    if (z.lifecycle === 'mitigation') {
                        ctx.setLineDash([2 * hr, 2 * hr]);
                    } else if (dashPattern.length > 0) {
                        ctx.setLineDash(dashPattern.map(d => d * hr));
                    } else {
                        ctx.setLineDash([]);
                    }
                    ctx.beginPath();
                    ctx.moveTo(bx0, by);
                    ctx.lineTo(bx1, by);
                    ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.restore();

                    // Label at right end of line with collision avoidance
                    if (z.label) {
                        const fSize = Math.round(fontSize * vr);
                        ctx.save();
                        ctx.font = `${bold ? 'bold ' : ''}${fSize}px sans-serif`;
                        let labelText = `${levelPrefix} ${z.label}`;
                        if (z.lifecycle === 'mitigation') labelText += ' MIT';
                        const lw = ctx.measureText(labelText).width + 8 * hr;
                        const lh = fSize + 4 * vr;
                        const lx = bx1 - lw;
                        // Supply: above line, Demand: below line
                        const baseY = z.is_supply ? by - lh : by;
                        const placedY = _placeLabel(lx, baseY, lw, lh, 3);
                        if (placedY !== null) {
                            ctx.textAlign = 'right';
                            ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${z.is_broken ? 0.5 : 0.8})`;
                            ctx.fillText(labelText, bx1 - 4 * hr, placedY + fSize);
                        }
                        ctx.restore();
                    }
                }
            };

            /**
             * Draw breaker zones as rectangles (always, regardless of display mode).
             */
            const drawBreakerRects = (zones, supplyRGB, demandRGB, borderWidth, fontSize, bold, levelPrefix) => {
                for (const z of zones) {
                    if (z.lifecycle !== 'breaker') continue;
                    if (!breakersEnabled) continue;

                    const rgb = z.is_supply ? supplyRGB : demandRGB;
                    // confirmSec used as fallback when origin_time is absent
                    const confirmSec = _utcSec(z.confirm_time);
                    const originSec = z.origin_time ? _utcSec(z.origin_time) : confirmSec;
                    const breakSec = z.break_time ? _utcSec(z.break_time) : null;

                    const x0 = timeScale.timeToCoordinate(originSec);
                    const y0 = series.priceToCoordinate(z.top);
                    const y1 = series.priceToCoordinate(z.bot);
                    if (y0 === null || y1 === null || x0 === null) continue;

                    const bx0 = Math.round(x0 * hr);
                    let bx1;
                    if (z.is_broken && breakSec) {
                        const xBreak = timeScale.timeToCoordinate(breakSec);
                        bx1 = xBreak !== null ? Math.round(xBreak * hr) : chartWidth;
                    } else {
                        bx1 = chartWidth;
                    }
                    const by0 = Math.round(Math.min(y0, y1) * vr);
                    const byH = Math.round(Math.abs(y1 - y0) * vr);

                    // Flat fill (very transparent)
                    ctx.save();
                    ctx.globalAlpha = 0.06;
                    ctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
                    ctx.fillRect(bx0, by0, bx1 - bx0, byH);
                    ctx.restore();

                    // Border (subtle)
                    ctx.save();
                    ctx.strokeStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.25)`;
                    ctx.lineWidth = Math.ceil(borderWidth * hr);
                    ctx.setLineDash([]);
                    ctx.strokeRect(bx0, by0, bx1 - bx0, byH);
                    ctx.restore();

                    // Label with collision avoidance
                    if (z.label) {
                        const fSize = Math.round(fontSize * vr);
                        ctx.save();
                        ctx.font = `${bold ? 'bold ' : ''}${fSize}px sans-serif`;
                        let labelText = `${levelPrefix} ${z.label} BREAKER`;
                        const lw = ctx.measureText(labelText).width + 8 * hr;
                        const lh = fSize + 4 * vr;
                        const lx = bx0 + 4 * hr;
                        const baseY = by0 + 2 * vr;
                        const placedY = _placeLabel(lx, baseY, lw, lh, 3);
                        if (placedY !== null) {
                            ctx.textAlign = 'left';
                            // Zone label part
                            const zoneText = `${levelPrefix} ${z.label}`;
                            ctx.fillStyle = `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.8)`;
                            ctx.fillText(zoneText, lx, placedY + fSize);
                            // BREAKER tag
                            const tagX = lx + ctx.measureText(zoneText).width + 8 * hr;
                            ctx.fillStyle = 'rgba(255,87,34,0.6)';
                            ctx.font = `${Math.round(9 * vr)}px sans-serif`;
                            ctx.fillText('BREAKER', tagX, placedY + fSize);
                        }
                        ctx.restore();
                    }
                }
            };

            const displayMode = this._source._displayMode;

            if (displayMode === 'lines') {
                // Lines mode: single line at key level per zone
                // Parent — red/blue, 2px solid, opacity 0.5/0.25
                drawLines(this._source._parentZones, [198,40,40], [21,101,192],
                          2, [], 0.5, 0.25, 11, true, tfLabels.parent || 'P');
                // Child — orange/teal, 1.5px dashed [6,3], opacity 0.5/0.25
                drawLines(this._source._childZones, [255,152,0], [0,188,212],
                          1.5, [6,3], 0.5, 0.25, 11, true, tfLabels.child || 'C');
                // Sub — yellow-green/cyan, 1px dashed [3,2], opacity 0.5/0.25
                drawLines(this._source._subZones, [205,220,57], [128,222,234],
                          1, [3,2], 0.5, 0.25, 10, false, tfLabels.sub || 'S');

                // Breaker zones: always rectangles
                drawBreakerRects(this._source._parentZones, [198,40,40], [21,101,192],
                                 2, 11, true, tfLabels.parent || 'P');
                drawBreakerRects(this._source._childZones, [255,152,0], [0,188,212],
                                 1.5, 11, true, tfLabels.child || 'C');
                drawBreakerRects(this._source._subZones, [205,220,57], [128,222,234],
                                 1, 10, false, tfLabels.sub || 'S');
            } else {
                // Rects mode: existing rectangle rendering (unchanged)
                // Parent zones first (background) — red/blue, alpha 0.12, 2px solid, 11px bold
                drawZones(this._source._parentZones, [198,40,40], [21,101,192],
                          0.12, 0.04, 2, 'solid', 11, true, tfLabels.parent || 'P');

                // Child zones (middle) — orange/teal, alpha 0.15, 1.5px solid, 11px bold
                drawZones(this._source._childZones, [255,152,0], [0,188,212],
                          0.15, 0.05, 1.5, 'solid', 11, true, tfLabels.child || 'C');

                // Sub zones (foreground) — yellow-green/cyan, alpha 0.08, 1px dashed, 10px normal
                drawZones(this._source._subZones, [205,220,57], [128,222,234],
                          0.08, 0.03, 1, 'dashed', 10, false, tfLabels.sub || 'S');
            }

            // Opposing nesting — only in rects mode (relies on rectangle geometry)
            if (displayMode === 'rects' && opposingEnabled && this._source._subZones.length > 0) {
                const activeChildZones = this._source._childZones.filter(z => !z.is_broken);
                for (const sub of this._source._subZones) {
                    if (sub.is_broken) continue;
                    let bestChild = null;
                    let bestOverlap = 0;
                    for (const child of activeChildZones) {
                        const overlapTop = Math.min(sub.top, child.top);
                        const overlapBot = Math.max(sub.bot, child.bot);
                        const overlap = overlapTop - overlapBot;
                        if (overlap > 0 && overlap > bestOverlap) {
                            bestOverlap = overlap;
                            bestChild = child;
                        }
                    }
                    if (bestChild && bestChild.is_supply !== sub.is_supply) {
                        const confirmSec = _utcSec(sub.confirm_time);
                        const x0 = timeScale.timeToCoordinate(confirmSec);
                        const y0 = series.priceToCoordinate(sub.top);
                        const y1 = series.priceToCoordinate(sub.bot);
                        if (x0 !== null && y0 !== null && y1 !== null) {
                            const bx0 = Math.round(x0 * hr);
                            const by0 = Math.round(Math.min(y0, y1) * vr);
                            const byH = Math.round(Math.abs(y1 - y0) * vr);
                            ctx.save();
                            ctx.strokeStyle = 'rgba(255,82,82,0.6)';
                            ctx.lineWidth = Math.ceil(2 * hr);
                            ctx.setLineDash([]);
                            ctx.strokeRect(bx0 - 1, by0 - 1, chartWidth - bx0 + 2, byH + 2);
                            ctx.restore();
                            const fSize = Math.round(9 * vr);
                            ctx.save();
                            ctx.font = `bold ${fSize}px sans-serif`;
                            ctx.fillStyle = 'rgba(255,82,82,0.9)';
                            ctx.textAlign = 'left';
                            ctx.fillText('OPPOSING', bx0 + 4 * hr, by0 + byH + fSize + 2 * vr);
                            ctx.restore();
                        }
                    }
                }
            }
        });
    }
}


// ── Sub-primitive 2: Break Lines (BOS / CHoCH) ───────────────────────────────
//
// Renders ALL events in a single primitive (batch, not one-per-break).
// Each event: { time, price, break_type, is_external, label, direction,
//               zone_label, zone_origin_time }
//
// Internal (is_external: false): dashed 1px, alpha 0.5, small diamond (4px)
//   Label: "iBOS (HH)" / "iCHoCH (LH)"  9px normal
// External (is_external: true): solid 2px, alpha 1.0, larger diamond (6px)
//   Label: "eBOS+ (HH)" / "eCHoCH+ (LH)"  10px bold
//
// Line runs from zone_origin_time → event time at event price.

const BREAK_COLORS = {
    BOS:   { bullish: '#4CAF50', bearish: '#F44336' },
    CHoCH: { bullish: '#00E676', bearish: '#FF5252' },
};

class StructureBreakPrimitive {
    constructor(events, chart, series) {
        this._events = events;
        this._chart = chart;
        this._series = series;
        this._paneViews = [new StructureBreakPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class StructureBreakPaneView {
    constructor(source) {
        this._source = source;
        this._renderer = new StructureBreakRenderer(source);
    }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'normal'; }
}

class StructureBreakRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const chart = this._source._chart;
            const series = this._source._series;
            if (!chart || !series) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const timeScale = chart.timeScale();

            for (const e of this._source._events) {
                const isSub = e._isSub || false;
                const colors = BREAK_COLORS[e.break_type] || BREAK_COLORS.BOS;
                const color = colors[e.direction] || '#888';

                const timeSec = _utcSec(e.time);
                const originSec = _utcSec(e.zone_origin_time);

                const x1 = timeScale.timeToCoordinate(timeSec);
                const y = series.priceToCoordinate(e.price);
                if (x1 === null || y === null) continue;

                const x0 = timeScale.timeToCoordinate(originSec);
                const bx0 = x0 !== null ? Math.round(x0 * hr) : 0;
                const bx1 = Math.round(x1 * hr);
                const by = Math.round(y * vr);

                // 3-level visual hierarchy
                const isExt = e.is_external && !isSub;
                const lineWidth = isSub ? 1 : (isExt ? 2 : 1.5);
                const alpha = isSub ? 0.35 : (isExt ? 1.0 : 0.7);
                const dashed = isSub || (!isExt);

                // Line from zone origin → break point
                ctx.save();
                ctx.strokeStyle = color;
                ctx.lineWidth = Math.ceil(lineWidth * hr);
                ctx.globalAlpha = alpha;
                ctx.setLineDash(dashed ? [4 * hr, 3 * hr] : []);
                ctx.beginPath();
                ctx.moveTo(bx0, by);
                ctx.lineTo(bx1, by);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.restore();

                // Diamond marker at break point
                const sz = (isExt ? 6 : (isSub ? 3 : 4)) * hr;
                ctx.save();
                ctx.globalAlpha = alpha;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.moveTo(bx1, by - sz);
                ctx.lineTo(bx1 + sz, by);
                ctx.lineTo(bx1, by + sz);
                ctx.lineTo(bx1 - sz, by);
                ctx.closePath();
                ctx.fill();
                ctx.restore();

                // Label — OFFSET TO THE RIGHT of the break line with buffer
                // (user request: don't clutter candles, place labels in blank space after break)
                const prefix = isSub ? 'i' : (isExt ? 'e' : '');
                const suffix = isExt ? '+' : '';
                const labelText = `${prefix}${e.break_type}${suffix} (${e.zone_label})`;
                const fontSize = Math.round((isExt ? 10 : (isSub ? 8 : 9)) * vr);
                const labelBuffer = Math.round(10 * hr);  // 10px buffer to the right of diamond
                ctx.save();
                ctx.globalAlpha = alpha;
                ctx.font = `${isExt ? 'bold ' : ''}${fontSize}px sans-serif`;
                ctx.fillStyle = color;
                ctx.textAlign = 'left';
                ctx.fillText(labelText, bx1 + sz + labelBuffer, by - 4 * vr);
                ctx.restore();
            }
        });
    }
}


// ── Sub-primitive 3: Boundary Levels ────────────────────────────────────────
//
// Two full-width horizontal lines marking the external high/low of the parent TF.
// external_high: #c62828 (red)   label: "{parent_tf} supply {price}"
// external_low:  #1565C0 (blue)  label: "{parent_tf} demand {price}"
// Solid 2px, alpha 0.7. Skipped when null.

class StructureBoundaryPrimitive {
    constructor(extHigh, extLow, parentTf, chart, series) {
        this._extHigh = extHigh;
        this._extLow = extLow;
        this._parentTf = parentTf || '';
        this._chart = chart;
        this._series = series;
        this._paneViews = [new StructureBoundaryPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class StructureBoundaryPaneView {
    constructor(source) {
        this._source = source;
        this._renderer = new StructureBoundaryRenderer(source);
    }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'normal'; }
}

class StructureBoundaryRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const chart = this._source._chart;
            const series = this._source._series;
            if (!chart || !series) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const chartWidth = scope.bitmapSize.width;
            const timeScale = chart.timeScale();
            const parentTf = this._source._parentTf;

            const drawLevel = (level, color, labelPrefix) => {
                if (!level) return;
                const y = series.priceToCoordinate(level.price);
                if (y === null) return;
                const by = Math.round(y * vr);

                // Start at zone origin time (not full width)
                const timeSec = _utcSec(level.time);
                const x0 = timeScale.timeToCoordinate(timeSec);
                const bx0 = x0 !== null ? Math.round(x0 * hr) : 0;

                ctx.save();
                ctx.globalAlpha = 0.7;
                ctx.strokeStyle = color;
                ctx.lineWidth = Math.ceil(2 * hr);
                ctx.setLineDash([]);
                ctx.beginPath();
                ctx.moveTo(bx0, by);
                ctx.lineTo(chartWidth, by);
                ctx.stroke();

                // Label at right edge
                const fontSize = Math.round(10 * vr);
                ctx.font = `bold ${fontSize}px sans-serif`;
                ctx.fillStyle = color;
                ctx.textAlign = 'right';
                ctx.fillText(
                    `${labelPrefix} ${level.price.toFixed(5)}`,
                    chartWidth - 4 * hr,
                    by - 4 * vr
                );
                ctx.restore();
            };

            drawLevel(this._source._extHigh, '#c62828', parentTf + ' supply');
            drawLevel(this._source._extLow,  '#1565C0', parentTf + ' demand');
        });
    }
}


// ── Sub-primitive 4: Zigzag ──────────────────────────────────────────────────
//
// Two polylines drawn from the zigzag vertex array:
//   External (is_external: true): solid 1.5px rgba(255,255,255,0.6)
//     Labels: "HH+", "LH+", "HL+", "LL+"  10px bold
//     Bullish (HH+, HL+): #4CAF50 green
//     Bearish (LH+, LL+): #F44336 red
//
//   Internal (is_external: false): dashed 1px rgba(255,255,255,0.25)
//     Labels: "HH", "LH", "HL", "LL"  9px normal
//     Same hue but at 50% alpha via rgba strings
//
// Labels above candle highs, below candle lows.
// zOrder 'top' so labels sit above all other overlays.

class StructureZigzagPrimitive {
    constructor(zigzag, chart, series) {
        this._zigzag = zigzag;
        this._chart = chart;
        this._series = series;
        this._paneViews = [new StructureZigzagPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class StructureZigzagPaneView {
    constructor(source) {
        this._source = source;
        this._renderer = new StructureZigzagRenderer(source);
    }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'top'; }
}

class StructureZigzagRenderer {
    constructor(source) { this._source = source; }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const chart = this._source._chart;
            const series = this._source._series;
            if (!chart || !series) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const timeScale = chart.timeScale();
            const zigzag = this._source._zigzag;

            // Split into external, internal, and sub subsets
            const external = zigzag.filter(v => v.is_external && !v._isSub);
            const internal = zigzag.filter(v => !v.is_external && !v._isSub);
            const sub = zigzag.filter(v => v._isSub);

            /**
             * Draw a polyline connecting the given vertices.
             * @param {Array}   vertices
             * @param {string}  lineColor
             * @param {number}  lineWidth  - CSS pixels (scaled by hr)
             * @param {boolean} dashed
             */
            const drawPolyline = (vertices, lineColor, lineWidth, dashed) => {
                if (vertices.length < 2) return;
                ctx.save();
                ctx.strokeStyle = lineColor;
                ctx.lineWidth = Math.ceil(lineWidth * hr);
                ctx.setLineDash(dashed ? [4 * hr, 3 * hr] : []);
                ctx.beginPath();
                let started = false;
                for (const v of vertices) {
                    const sec = _utcSec(v.time);
                    const x = timeScale.timeToCoordinate(sec);
                    const y = series.priceToCoordinate(v.price);
                    if (x === null || y === null) continue;
                    const bx = Math.round(x * hr);
                    const by = Math.round(y * vr);
                    if (!started) { ctx.moveTo(bx, by); started = true; }
                    else          { ctx.lineTo(bx, by); }
                }
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.restore();
            };

            // Polylines first (drawn under labels)
            // Parent zigzag: solid 1.5px white
            drawPolyline(external, 'rgba(255,255,255,0.6)',  1.5, false);
            // Child zigzag: dashed 1px white alpha 0.25
            drawPolyline(internal, 'rgba(255,255,255,0.25)', 1.0, true);
            // Sub zigzag: dashed 0.5px white alpha 0.15
            drawPolyline(sub,      'rgba(255,255,255,0.15)', 0.5, true);

            /**
             * Draw labels at each vertex in the provided set.
             * @param {Array}   vertices
             * @param {number}  fontSize        - CSS pixels (scaled by vr)
             * @param {boolean} bold
             * @param {number}  alphaMultiplier - 1.0 for external, 0.5 for internal
             */
            const drawLabels = (vertices, fontSize, bold, alphaMultiplier) => {
                const fSize = Math.round(fontSize * vr);
                ctx.font = `${bold ? 'bold ' : ''}${fSize}px sans-serif`;
                ctx.textAlign = 'center';

                for (const v of vertices) {
                    const sec = _utcSec(v.time);
                    const x = timeScale.timeToCoordinate(sec);
                    const y = series.priceToCoordinate(v.price);
                    if (x === null || y === null) continue;

                    const bx = Math.round(x * hr);
                    const by = Math.round(y * vr);

                    const lbl = v.label || '';
                    // Bullish: HH* or HL*  →  green
                    // Bearish: LH* or LL*  →  red
                    const isBullish = lbl.startsWith('HH') || lbl.startsWith('HL');
                    const baseRGB = isBullish ? [76, 175, 80] : [244, 67, 54];
                    ctx.fillStyle = `rgba(${baseRGB[0]},${baseRGB[1]},${baseRGB[2]},${alphaMultiplier})`;

                    // High labels (HH, LH) → above candle; low labels (HL, LL) → below
                    const isHigh = lbl.startsWith('HH') || lbl.startsWith('LH');
                    const yOffset = isHigh ? -8 * vr : 12 * vr;
                    ctx.fillText(lbl, bx, by + yOffset);
                }
            };

            drawLabels(external, 10, true,  1.0);
            drawLabels(internal,  9, false, 0.5);
            drawLabels(sub,       8, false, 0.25);
        });
    }
}
