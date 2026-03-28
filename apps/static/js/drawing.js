/**
 * drawing.js — Drawing tools (line, ray, arrow, rect, circle, text) with movable anchors.
 *
 * All drawn objects are stored client-side. Engine overlays are never affected by clear/undo.
 * Supports both single-chart and multichart modes via resolver methods.
 */

/** Convert time to pixel coordinate, with extrapolation for future times. */
function _extrapolateTimeToX(ts, time, candles) {
    const x = ts.timeToCoordinate(time);
    if (x !== null) return x;
    if (!candles) candles = App.data && App.data.candles;
    if (candles && candles.length >= 2) {
        const lastTime = candles[candles.length - 1].time;
        const prevTime = candles[candles.length - 2].time;
        const lastX = ts.timeToCoordinate(lastTime);
        const prevX = ts.timeToCoordinate(prevTime);
        if (lastX !== null && prevX !== null && lastTime !== prevTime) {
            const pxPerSec = (lastX - prevX) / (lastTime - prevTime);
            return lastX + pxPerSec * (time - lastTime);
        }
    }
    return null;
}

const Drawing = {
    activeTool: null,
    // Single-chart drawing storage (used when multichart is NOT active)
    drawings: [],
    undoStack: [],
    _clickState: null,  // Pending first click for two-click tools
    _dragState: null,   // For rect/circle drag
    _rafPending: null,  // rAF throttle for mousemove redraws
    _primitives: [],    // Attached LW primitives
    _color: DRAW_COLOR_DEFAULT,
    _canvas: null,      // Overlay canvas for drawing feedback (single chart)
    _ctx: null,

    // Anchor dragging
    _draggingAnchor: null,
    _draggingDrawing: null,
    _bodyDrag: null,  // { drawing, startPx, startPy, anchorSnaps[] } for whole-shape drag

    // ── Resolver methods: route to multichart or single chart ──

    /** Get the active chart instance for drawing operations */
    _getChart() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            return MultiChart.getFocusedChart();
        }
        return Chart.getChart();
    },

    /** Get the active series for drawing operations */
    _getSeries() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            return MultiChart.getFocusedSeries();
        }
        return Chart.getCandleSeries();
    },

    /** Get the active container element for the overlay canvas */
    _getContainer() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            return MultiChart.getFocusedContainer();
        }
        return document.getElementById('chart-container');
    },

    /** Get the candle data for the active panel (for time extrapolation) */
    _getCandles() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            return entry && entry.data && entry.data.candles;
        }
        return App.data && App.data.candles;
    },

    /** Get drawings array for the active panel */
    _getDrawings() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            return entry ? entry.drawings : this.drawings;
        }
        return this.drawings;
    },

    /** Get undo stack for the active panel */
    _getUndoStack() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            return entry ? entry.undoStack : this.undoStack;
        }
        return this.undoStack;
    },

    /** Get primitives array for the active panel */
    _getPrimitives() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            return entry ? entry._drawPrimitives : this._primitives;
        }
        return this._primitives;
    },

    /** Set primitives array for the active panel */
    _setPrimitives(prims) {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            if (entry) entry._drawPrimitives = prims;
        } else {
            this._primitives = prims;
        }
    },

    /** Get or create overlay canvas for the active container */
    _getOverlayCanvas() {
        const container = this._getContainer();
        if (!container) return { canvas: this._canvas, ctx: this._ctx };

        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            // Per-panel overlay canvas
            const entry = MultiChart.getFocusedEntry();
            if (!entry) return { canvas: null, ctx: null };
            if (!entry._drawCanvas) {
                const canvas = document.createElement('canvas');
                canvas.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:50;';
                container.appendChild(canvas);
                entry._drawCanvas = canvas;
                entry._drawCtx = canvas.getContext('2d');
                // ResizeObserver for this panel's canvas
                const ro = new ResizeObserver(() => {
                    canvas.width = container.clientWidth * window.devicePixelRatio;
                    canvas.height = container.clientHeight * window.devicePixelRatio;
                    canvas.style.width = container.clientWidth + 'px';
                    canvas.style.height = container.clientHeight + 'px';
                });
                ro.observe(container);
                entry._drawCanvasRO = ro;
                // Initial size
                canvas.width = container.clientWidth * window.devicePixelRatio;
                canvas.height = container.clientHeight * window.devicePixelRatio;
                canvas.style.width = container.clientWidth + 'px';
                canvas.style.height = container.clientHeight + 'px';
            }
            return { canvas: entry._drawCanvas, ctx: entry._drawCtx };
        }
        return { canvas: this._canvas, ctx: this._ctx };
    },

    init() {
        this._bindToolButtons();
        this._bindKeyboard();
        this._createOverlayCanvas();
        this._bindChartInteraction();
    },

    _bindToolButtons() {
        document.querySelectorAll('#draw-toolbar-inline button[data-tool]').forEach(btn => {
            btn.addEventListener('click', () => {
                const tool = btn.dataset.tool;
                if (this.activeTool === tool) {
                    this.deactivate();
                } else {
                    this.activate(tool);
                }
            });
        });

        document.getElementById('draw-undo-btn').addEventListener('click', () => this.undo());
        document.getElementById('draw-clear-btn').addEventListener('click', () => this.clearAll());
        document.getElementById('draw-color').addEventListener('input', (e) => {
            this._color = e.target.value;
        });
    },

    _bindKeyboard() {
        document.addEventListener('keydown', (e) => {
            // Skip all hotkeys when typing in an input or textarea
            const tag = e.target.tagName;
            if (tag === 'TEXTAREA' || tag === 'INPUT') return;

            // Ctrl+Z undo
            if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                this.undo();
                return;
            }
            // Escape — cancel current tool
            if (e.key === 'Escape') {
                this.deactivate();
                return;
            }
            // Screenshot shortcut
            if (e.key === 's' && !e.ctrlKey && !e.altKey) {
                e.preventDefault();
                App.takeScreenshot();
                return;
            }
            // Keyboard shortcuts for tools
            const toolMap = { l: 'line', r: 'ray', a: 'arrow', e: 'rect', c: 'circle', t: 'text' };
            if (!e.ctrlKey && !e.altKey && toolMap[e.key]) {
                e.preventDefault();
                this.activate(toolMap[e.key]);
            }
        });
    },

    _createOverlayCanvas() {
        const container = document.getElementById('chart-container');
        this._canvas = document.createElement('canvas');
        this._canvas.style.cssText = 'position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:50;';
        container.appendChild(this._canvas);
        this._ctx = this._canvas.getContext('2d');

        // Resize canvas with container
        this._canvasRO = new ResizeObserver(() => {
            this._canvas.width = container.clientWidth * window.devicePixelRatio;
            this._canvas.height = container.clientHeight * window.devicePixelRatio;
            this._canvas.style.width = container.clientWidth + 'px';
            this._canvas.style.height = container.clientHeight + 'px';
            this._redrawOverlay();
        });
        this._canvasRO.observe(container);
    },

    destroy() {
        if (this._canvasRO) {
            this._canvasRO.disconnect();
            this._canvasRO = null;
        }
    },

    _bindChartInteraction() {
        // For single chart mode — bind to chart-container
        const container = document.getElementById('chart-container');
        this._bindContainerEvents(container);

        // Multichart panels get bound when created (via MultiChart._bindDrawingToPanel)
    },

    /** Bind drawing mouse events to a container element */
    _bindContainerEvents(container) {
        container.addEventListener('mousedown', (e) => this._handleMouseDown(e, container));
        container.addEventListener('mousemove', (e) => this._handleMouseMove(e));
        container.addEventListener('mouseup', (e) => this._handleMouseUp(e));
    },

    _handleMouseDown(e, container) {
        // In multichart mode, handle focus switching
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const idx = MultiChart._panelIndexFromContainer(container);
            if (idx >= 0 && idx !== MultiChart._focusedIdx) {
                if (this._clickState || this._dragState) {
                    this._clickState = null;
                    this._dragState = null;
                    this._redrawOverlay();
                }
                MultiChart.setFocus(idx);
            }
        }

        if (!this.activeTool && e.button === 0) {
            // Use chart element's rect, not cell — cell includes controls bar offset
            const chart = this._getChart();
            const chartEl = chart ? chart.chartElement() : null;
            const rect = (chartEl || container).getBoundingClientRect();
            const px = e.clientX - rect.left;
            const py = e.clientY - rect.top;

            // Double-click on text → edit it
            if (e.detail === 2) {
                const textHit = this._findTextAt(px, py);
                if (textHit) {
                    const pos = this._mouseToChartPos(e);
                    if (pos) this._openTextInput(pos, textHit);
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
            }

            // Check anchors first, then text body for dragging
            const anchor = this._findAnchorAt(px, py);
            if (anchor) {
                this._draggingAnchor = anchor.anchor;
                this._draggingDrawing = anchor.drawing;
                const { canvas } = this._getOverlayCanvas();
                if (canvas) canvas.style.pointerEvents = 'auto';
                e.preventDefault();
                e.stopPropagation();
                return;
            }
            // Click anywhere on text body to drag it
            const textHit = this._findTextAt(px, py);
            if (textHit) {
                const posAnchor = textHit.anchors.find(a => a.role === 'pos');
                if (posAnchor) {
                    this._draggingAnchor = posAnchor;
                    this._draggingDrawing = textHit;
                    const { canvas } = this._getOverlayCanvas();
                    if (canvas) canvas.style.pointerEvents = 'auto';
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
            }
            // Click inside shape body (rect/circle) to drag whole shape
            const shapeHit = this._findShapeAt(px, py);
            if (shapeHit) {
                this._bodyDrag = {
                    drawing: shapeHit,
                    lastTime: this._mouseToChartPos(e)?.time,
                    lastPrice: this._mouseToChartPos(e)?.price,
                };
                const { canvas } = this._getOverlayCanvas();
                if (canvas) canvas.style.pointerEvents = 'auto';
                e.preventDefault();
                e.stopPropagation();
                return;
            }
        }
        if (!this.activeTool) return;
        if (e.button !== 0) return;

        const pos = this._mouseToChartPos(e);
        if (!pos) return;

        if (this.activeTool === 'text') {
            this._openTextInput(pos, null);
            return;
        }

        if (this.activeTool === 'rect') {
            this._dragState = { startTime: pos.time, startPrice: pos.price };
            const { canvas } = this._getOverlayCanvas();
            if (canvas) canvas.style.pointerEvents = 'auto';
            return;
        }

        // Two-click tools: line, ray, arrow, circle
        if (!this._clickState) {
            this._clickState = { time: pos.time, price: pos.price };
        } else {
            if (this.activeTool === 'circle') {
                // Two-click circle: first click = center, second click = edge (radius)
                this._addDrawing({
                    type: 'circle',
                    cx: this._clickState.time, cy: this._clickState.price,
                    edgeTime: pos.time, edgePrice: pos.price,
                    color: this._color,
                });
            } else {
                this._addDrawing({
                    type: this.activeTool,
                    x1: this._clickState.time, y1: this._clickState.price,
                    x2: pos.time, y2: pos.price,
                    color: this._color,
                });
            }
            this._clickState = null;
        }
    },

    _handleMouseMove(e) {
        if (this._draggingAnchor) {
            if (!this._rafPending) {
                this._rafPending = requestAnimationFrame(() => {
                    const pos = this._mouseToChartPos(e);
                    if (pos) {
                        this._draggingAnchor.time = pos.time;
                        this._draggingAnchor.price = pos.price;
                        this._syncDrawingToAnchors(this._draggingDrawing);
                        this._renderDrawings();
                    }
                    this._rafPending = null;
                });
            }
            e.preventDefault();
            return;
        }
        if (this._bodyDrag) {
            if (!this._rafPending) {
                this._rafPending = requestAnimationFrame(() => {
                    const pos = this._mouseToChartPos(e);
                    if (pos && this._bodyDrag.lastTime != null) {
                        const dt = pos.time - this._bodyDrag.lastTime;
                        const dp = pos.price - this._bodyDrag.lastPrice;
                        for (const a of this._bodyDrag.drawing.anchors) {
                            a.time += dt;
                            a.price += dp;
                        }
                        this._syncDrawingToAnchors(this._bodyDrag.drawing);
                        this._bodyDrag.lastTime = pos.time;
                        this._bodyDrag.lastPrice = pos.price;
                        this._renderDrawings();
                    }
                    this._rafPending = null;
                });
            }
            e.preventDefault();
            return;
        }
        if ((this._dragState || this._clickState) && this.activeTool) {
            if (!this._rafPending) {
                this._rafPending = requestAnimationFrame(() => {
                    this._redrawOverlay();
                    const pos = this._mouseToChartPos(e);
                    if (pos) {
                        if (this._dragState) {
                            this._drawPreview(this._dragState, pos);
                        }
                        if (this._clickState) {
                            this._drawPreview(this._clickState, pos);
                        }
                    }
                    this._rafPending = null;
                });
            }
        }
    },

    _handleMouseUp(e) {
        if (this._draggingAnchor) {
            this._draggingAnchor = null;
            this._draggingDrawing = null;
            const { canvas } = this._getOverlayCanvas();
            if (canvas) canvas.style.pointerEvents = 'none';
            return;
        }
        if (this._bodyDrag) {
            this._bodyDrag = null;
            const { canvas } = this._getOverlayCanvas();
            if (canvas) canvas.style.pointerEvents = 'none';
            return;
        }
        if (this._dragState && this.activeTool) {
            const pos = this._mouseToChartPos(e);
            if (!pos) return;
            this._addDrawing({
                type: this.activeTool,
                x1: this._dragState.startTime, y1: this._dragState.startPrice,
                x2: pos.time, y2: pos.price,
                color: this._color,
            });
            this._dragState = null;
            const { canvas } = this._getOverlayCanvas();
            if (canvas) canvas.style.pointerEvents = 'none';
            this._redrawOverlay();
        }
    },

    _mouseToChartPos(e) {
        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return null;

        // Use clientX/clientY relative to the container's bounding rect.
        // e.offsetX is relative to e.target which may be a nested LW Charts
        // internal element, not the container we bound the event to.
        const container = this._getContainer();
        let x, y;
        if (container) {
            const rect = container.getBoundingClientRect();
            x = e.clientX - rect.left;
            y = e.clientY - rect.top;
        } else {
            x = e.offsetX;
            y = e.offsetY;
        }

        let time = chart.timeScale().coordinateToTime(x);
        const price = series.coordinateToPrice(y);
        if (price === null) return null;

        // If time is null (beyond last candle / in rightOffset area),
        // extrapolate from the last candle using bar spacing
        if (time === null) {
            const candles = this._getCandles();
            if (candles && candles.length >= 2) {
                const lastTime = candles[candles.length - 1].time;
                const lastX = chart.timeScale().timeToCoordinate(lastTime);
                if (lastX !== null) {
                    const barInterval = candles[candles.length - 1].time - candles[candles.length - 2].time;
                    const prevX = chart.timeScale().timeToCoordinate(candles[candles.length - 2].time);
                    if (prevX !== null) {
                        const pxPerBar = lastX - prevX;
                        if (pxPerBar > 0) {
                            const barsAhead = (x - lastX) / pxPerBar;
                            time = lastTime + Math.round(barsAhead * barInterval);
                        }
                    }
                }
            }
            if (time === null) return null;
        }
        return { time, price };
    },

    activate(tool) {
        this.activeTool = tool;
        this._clickState = null;
        this._dragState = null;
        // Update button states
        document.querySelectorAll('#draw-toolbar-inline button[data-tool]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
        // Disable chart scroll/pan while drawing on the active chart
        const chart = this._getChart();
        if (chart) {
            chart.applyOptions({
                handleScroll: { mouseWheel: true, pressedMouseMove: false },
                handleScale: { mouseWheel: true, pinch: true },
            });
        }
        // Update focus indicator text
        this._updateFocusIndicator();
    },

    deactivate() {
        this.activeTool = null;
        this._clickState = null;
        this._dragState = null;
        document.querySelectorAll('#draw-toolbar-inline button[data-tool]').forEach(btn => {
            btn.classList.remove('active');
        });
        // Re-enable chart interaction
        const chart = this._getChart();
        if (chart) {
            chart.applyOptions({
                handleScroll: { mouseWheel: true, pressedMouseMove: true },
                handleScale: { mouseWheel: true, pinch: true },
            });
        }
        const { canvas } = this._getOverlayCanvas();
        if (canvas) canvas.style.pointerEvents = 'none';
        this._redrawOverlay();
        this._updateFocusIndicator();
    },

    /** Find a text drawing whose body covers the pixel position (px, py). */
    _findTextAt(px, py) {
        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return null;
        const candles = this._getCandles();
        const drawings = this._getDrawings();
        const fontSize = 12;

        for (const d of drawings) {
            if (d.type !== 'text') continue;
            const x = _extrapolateTimeToX(chart.timeScale(), d.x, candles);
            const y = series.priceToCoordinate(d.y);
            if (x === null || y === null) continue;

            const lines = (d.text || '').split('\n');
            const lineHeight = fontSize * 1.3;
            const maxWidth = Math.max(...lines.map(l => l.length)) * fontSize * 0.65;
            const totalHeight = lines.length * lineHeight;

            // Text is drawn at (x, y) with baseline near top
            if (px >= x - 4 && px <= x + maxWidth + 8 &&
                py >= y - lineHeight && py <= y + totalHeight) {
                return d;
            }
        }
        return null;
    },

    /** Open a textarea overlay to create or edit text. */
    _openTextInput(pos, existingDrawing) {
        // Remove any existing text input
        const old = document.getElementById('drawing-text-input');
        if (old) old.remove();

        const container = this._getContainer();
        if (!container) return;

        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return;
        const candles = this._getCandles();

        // Position the textarea at the drawing location
        const editTime = existingDrawing ? existingDrawing.x : pos.time;
        const editPrice = existingDrawing ? existingDrawing.y : pos.price;
        const screenX = _extrapolateTimeToX(chart.timeScale(), editTime, candles);
        const screenY = series.priceToCoordinate(editPrice);
        if (screenX === null || screenY === null) return;

        const wrap = document.createElement('div');
        wrap.id = 'drawing-text-input';
        wrap.style.cssText = `position:absolute; left:${screenX}px; top:${Math.max(0, screenY - 16)}px; z-index:200;`;

        const textarea = document.createElement('textarea');
        textarea.value = existingDrawing ? existingDrawing.text : '';
        textarea.placeholder = 'Type here… (Shift+Enter = new line)';
        textarea.style.cssText = `
            width: 220px; min-height: 32px; max-width: 500px;
            padding: 6px 8px; font: 13px sans-serif;
            background: #1a1a2a; color: #e8e8e8; border: 2px solid #448aff;
            border-radius: 4px; outline: none; resize: both;
            box-shadow: 0 4px 16px rgba(0,0,0,0.6);
            cursor: text;
        `;
        textarea.rows = existingDrawing ? Math.max(2, (existingDrawing.text.match(/\n/g) || []).length + 1) : 2;

        const cleanup = () => {
            wrap.remove();
            document.removeEventListener('mousedown', outsideClick);
        };

        const confirm = () => {
            const text = textarea.value;
            cleanup();
            if (!text) return;
            if (existingDrawing) {
                existingDrawing.text = text;
                this._renderDrawings();
            } else {
                this._addDrawing({ type: 'text', x: pos.time, y: pos.price, text, color: this._color });
            }
        };

        const cancel = () => { cleanup(); };

        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                confirm();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                cancel();
            }
            e.stopPropagation(); // Prevent drawing hotkeys
        });

        // Close on outside click
        const outsideClick = (e) => {
            if (!wrap.contains(e.target)) {
                confirm();
            }
        };
        setTimeout(() => document.addEventListener('mousedown', outsideClick), 0);

        wrap.appendChild(textarea);
        container.appendChild(wrap);
        // Defer focus so browser doesn't steal it back to the chart after mousedown
        requestAnimationFrame(() => {
            textarea.focus();
            if (existingDrawing) textarea.select();
        });
    },

    /** Update the "Drawing on: M5" indicator in the toolbar */
    _updateFocusIndicator() {
        const indicator = document.getElementById('draw-focus-indicator');
        if (!indicator) return;
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled && this.activeTool) {
            const entry = MultiChart.getFocusedEntry();
            indicator.textContent = `Drawing on: ${entry ? entry.tf : '?'}`;
            indicator.style.display = 'inline';
        } else {
            indicator.style.display = 'none';
        }
    },

    _addDrawing(drawing) {
        // Add anchor points for movability
        drawing.anchors = this._createAnchors(drawing);
        const drawings = this._getDrawings();
        const undoStack = this._getUndoStack();
        drawings.push(drawing);
        undoStack.push({ action: 'add', index: drawings.length - 1 });
        const MAX_UNDO = UNDO_STACK_SIZE;
        if (undoStack.length > MAX_UNDO) undoStack.shift();
        this._renderDrawings();
    },

    _createAnchors(d) {
        switch (d.type) {
            case 'line': case 'ray': case 'arrow':
                return [
                    { time: d.x1, price: d.y1, role: 'start' },
                    { time: d.x2, price: d.y2, role: 'end' },
                ];
            case 'rect':
                return [
                    { time: d.x1, price: d.y1, role: 'start' },
                    { time: d.x2, price: d.y2, role: 'end' },
                ];
            case 'circle':
                return [
                    { time: d.cx, price: d.cy, role: 'center' },
                    { time: d.edgeTime, price: d.edgePrice, role: 'edge' },
                ];
            case 'text':
                return [{ time: d.x, price: d.y, role: 'pos' }];
            default:
                return [];
        }
    },

    _syncDrawingToAnchors(d) {
        if (!d.anchors) return;
        switch (d.type) {
            case 'line': case 'ray': case 'arrow': case 'rect': {
                const s = d.anchors.find(a => a.role === 'start');
                const e = d.anchors.find(a => a.role === 'end');
                if (s) { d.x1 = s.time; d.y1 = s.price; }
                if (e) { d.x2 = e.time; d.y2 = e.price; }
                break;
            }
            case 'circle': {
                const c = d.anchors.find(a => a.role === 'center');
                const e = d.anchors.find(a => a.role === 'edge');
                if (c) { d.cx = c.time; d.cy = c.price; }
                if (e) { d.edgeTime = e.time; d.edgePrice = e.price; }
                break;
            }
            case 'text': {
                const p = d.anchors.find(a => a.role === 'pos');
                if (p) { d.x = p.time; d.y = p.price; }
                break;
            }
        }
    },

    _findShapeAt(px, py) {
        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return null;
        const candles = this._getCandles();

        const drawings = this._getDrawings();
        for (const d of drawings) {
            if (d.type === 'rect') {
                const x1 = _extrapolateTimeToX(chart.timeScale(), d.x1, candles);
                const y1 = series.priceToCoordinate(d.y1);
                const x2 = _extrapolateTimeToX(chart.timeScale(), d.x2, candles);
                const y2 = series.priceToCoordinate(d.y2);
                if (x1 === null || y1 === null || x2 === null || y2 === null) continue;
                const minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
                const minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
                if (px >= minX && px <= maxX && py >= minY && py <= maxY) return d;
            }
            if (d.type === 'circle') {
                const cx = _extrapolateTimeToX(chart.timeScale(), d.cx, candles);
                const cy = series.priceToCoordinate(d.cy);
                const ex = _extrapolateTimeToX(chart.timeScale(), d.edgeTime, candles);
                const ey = series.priceToCoordinate(d.edgePrice);
                if (cx === null || cy === null || ex === null || ey === null) continue;
                const radius = Math.sqrt((ex - cx) ** 2 + (ey - cy) ** 2);
                const dist = Math.sqrt((px - cx) ** 2 + (py - cy) ** 2);
                if (dist <= radius) return d;
            }
        }
        return null;
    },

    _findAnchorAt(px, py) {
        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return null;
        const candles = this._getCandles();

        const threshold = ANCHOR_HIT_PX;
        const drawings = this._getDrawings();
        for (const d of drawings) {
            if (!d.anchors) continue;
            for (const anchor of d.anchors) {
                const x = _extrapolateTimeToX(chart.timeScale(), anchor.time, candles);
                const y = series.priceToCoordinate(anchor.price);
                if (x === null || y === null) continue;
                if (Math.abs(px - x) < threshold && Math.abs(py - y) < threshold) {
                    return { drawing: d, anchor };
                }
            }
        }
        return null;
    },

    undo() {
        const undoStack = this._getUndoStack();
        if (undoStack.length === 0) return;
        const last = undoStack.pop();
        if (last.action === 'add') {
            const drawings = this._getDrawings();
            drawings.splice(last.index, 1);
        }
        this._renderDrawings();
    },

    clearAll() {
        if (typeof MultiChart !== 'undefined' && MultiChart.enabled) {
            const entry = MultiChart.getFocusedEntry();
            if (entry) {
                entry.drawings = [];
                entry.undoStack = [];
            }
        } else {
            this.drawings = [];
            this.undoStack = [];
        }
        this._renderDrawings();
    },

    _renderDrawings() {
        const series = this._getSeries();
        if (!series) return;

        // Remove old primitives
        const oldPrims = this._getPrimitives();
        if (oldPrims) {
            oldPrims.forEach(p => {
                try { series.detachPrimitive(p); } catch(e) {}
            });
        }

        const drawings = this._getDrawings();
        const chart = this._getChart();
        const candles = this._getCandles();
        const newPrims = [];

        // Create new primitives for each drawing
        drawings.forEach(d => {
            const prim = new DrawingPrimitive(d, chart, series, candles);
            series.attachPrimitive(prim);
            newPrims.push(prim);
        });

        this._setPrimitives(newPrims);
    },

    _redrawOverlay() {
        const { ctx, canvas } = this._getOverlayCanvas();
        if (!ctx || !canvas) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    },

    _drawPreview(start, end) {
        const { ctx, canvas } = this._getOverlayCanvas();
        if (!ctx) return;
        const chart = this._getChart();
        const series = this._getSeries();
        if (!chart || !series) return;
        const candles = this._getCandles();

        const dpr = window.devicePixelRatio;
        // Normalize start coords: drag state uses startTime/startPrice, click state uses time/price
        const startTime = start.startTime !== undefined ? start.startTime : start.time;
        const startPrice = start.startPrice !== undefined ? start.startPrice : start.price;
        const x1 = _extrapolateTimeToX(chart.timeScale(), startTime, candles) * dpr;
        const y1 = series.priceToCoordinate(startPrice) * dpr;
        const x2 = _extrapolateTimeToX(chart.timeScale(), end.time, candles) * dpr;
        const y2 = series.priceToCoordinate(end.price) * dpr;

        if (x1 === null || y1 === null || x2 === null || y2 === null) return;

        ctx.strokeStyle = this._color;
        ctx.lineWidth = 1.5 * dpr;
        ctx.setLineDash([4 * dpr, 4 * dpr]);

        if (this.activeTool === 'rect') {
            ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        } else if (this.activeTool === 'circle') {
            // Preview: first click = center (x1,y1), mouse = edge (x2,y2)
            const radius = Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
            ctx.beginPath();
            ctx.arc(x1, y1, radius, 0, Math.PI * 2);
            ctx.stroke();
            // Center dot
            ctx.setLineDash([]);
            ctx.fillStyle = ANCHOR_FILL_COLOR;
            ctx.globalAlpha = 0.6;
            ctx.beginPath();
            ctx.arc(x1, y1, 4 * dpr, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1.0;
        } else {
            // Line, ray, arrow
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            if (this.activeTool === 'ray') {
                const dx = x2 - x1;
                const dy = y2 - y1;
                if (Math.abs(dx) > 0.001) {
                    const t = (canvas.width - x1) / dx;
                    ctx.lineTo(x1 + dx * t, y1 + dy * t);
                } else {
                    ctx.lineTo(x2, y2);
                }
            } else {
                ctx.lineTo(x2, y2);
            }
            ctx.stroke();

            if (this.activeTool === 'arrow') {
                const angle = Math.atan2(y2 - y1, x2 - x1);
                const headLen = 12 * dpr;
                ctx.beginPath();
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - headLen * Math.cos(angle - 0.4), y2 - headLen * Math.sin(angle - 0.4));
                ctx.moveTo(x2, y2);
                ctx.lineTo(x2 - headLen * Math.cos(angle + 0.4), y2 - headLen * Math.sin(angle + 0.4));
                ctx.stroke();
            }

            // Start anchor dot
            ctx.setLineDash([]);
            ctx.fillStyle = ANCHOR_FILL_COLOR;
            ctx.globalAlpha = 0.6;
            ctx.beginPath();
            ctx.arc(x1, y1, 4 * dpr, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1.0;
        }
        ctx.setLineDash([]);
    },
};


/**
 * DrawingPrimitive — Renders user-drawn shapes via ISeriesPrimitive.
 * Now receives chart/series/candles references to avoid global lookups.
 */
class DrawingPrimitive {
    constructor(drawing, chart, series, candles) {
        this._drawing = drawing;
        this._chart = chart;
        this._series = series;
        this._candles = candles;
        this._paneViews = [new DrawingPaneView(this)];
    }
    updateAllViews() {}
    paneViews() { return this._paneViews; }
}

class DrawingPaneView {
    constructor(source) { this._source = source; this._renderer = new DrawingRenderer(source); }
    update() {}
    renderer() { return this._renderer; }
    zOrder() { return 'top'; }
}

class DrawingRenderer {
    constructor(source) { this._source = source; }

    /** Convert time to pixel coordinate, extrapolating for future times. */
    _timeToX(ts, time) {
        return _extrapolateTimeToX(ts, time, this._source._candles);
    }

    draw(target) {
        target.useBitmapCoordinateSpace(scope => {
            const ctx = scope.context;
            const d = this._source._drawing;
            const chart = this._source._chart;
            const series = this._source._series;
            if (!chart || !series) return;

            const hr = scope.horizontalPixelRatio;
            const vr = scope.verticalPixelRatio;
            const ts = chart.timeScale();

            ctx.strokeStyle = d.color;
            ctx.fillStyle = d.color;
            ctx.lineWidth = 1.5 * hr;
            ctx.setLineDash([]);

            switch (d.type) {
                case 'line':
                case 'ray':
                case 'arrow': {
                    const x1 = this._timeToX(ts, d.x1);
                    const y1 = series.priceToCoordinate(d.y1);
                    const x2 = this._timeToX(ts, d.x2);
                    const y2 = series.priceToCoordinate(d.y2);
                    if (x1 === null || y1 === null || x2 === null || y2 === null) return;

                    const bx1 = x1 * hr, by1 = y1 * vr;
                    const bx2 = x2 * hr, by2 = y2 * vr;

                    ctx.beginPath();
                    ctx.moveTo(bx1, by1);

                    if (d.type === 'ray') {
                        // Extend to right edge
                        const dx = bx2 - bx1;
                        const dy = by2 - by1;
                        const chartW = scope.bitmapSize.width;
                        if (Math.abs(dx) > 0.001) {
                            const t = (chartW - bx1) / dx;
                            ctx.lineTo(bx1 + dx * t, by1 + dy * t);
                        } else {
                            ctx.lineTo(bx2, by2);
                        }
                    } else {
                        ctx.lineTo(bx2, by2);
                    }
                    ctx.stroke();

                    // Arrow head
                    if (d.type === 'arrow') {
                        const angle = Math.atan2(by2 - by1, bx2 - bx1);
                        const headLen = 12 * hr;
                        ctx.beginPath();
                        ctx.moveTo(bx2, by2);
                        ctx.lineTo(bx2 - headLen * Math.cos(angle - 0.4), by2 - headLen * Math.sin(angle - 0.4));
                        ctx.moveTo(bx2, by2);
                        ctx.lineTo(bx2 - headLen * Math.cos(angle + 0.4), by2 - headLen * Math.sin(angle + 0.4));
                        ctx.stroke();
                    }

                    // Anchor circles
                    this._drawAnchor(ctx, bx1, by1, hr);
                    this._drawAnchor(ctx, bx2, by2, hr);
                    break;
                }

                case 'rect': {
                    const x1 = this._timeToX(ts, d.x1);
                    const y1 = series.priceToCoordinate(d.y1);
                    const x2 = this._timeToX(ts, d.x2);
                    const y2 = series.priceToCoordinate(d.y2);
                    if (x1 === null || y1 === null || x2 === null || y2 === null) return;

                    const bx1 = x1 * hr, by1 = y1 * vr;
                    const bx2 = x2 * hr, by2 = y2 * vr;

                    ctx.globalAlpha = 0.15;
                    ctx.fillRect(bx1, by1, bx2 - bx1, by2 - by1);
                    ctx.globalAlpha = 1.0;
                    ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1);

                    this._drawAnchor(ctx, bx1, by1, hr);
                    this._drawAnchor(ctx, bx2, by2, hr);
                    break;
                }

                case 'circle': {
                    const cxCoord = this._timeToX(ts, d.cx);
                    const cyCoord = series.priceToCoordinate(d.cy);
                    const exCoord = this._timeToX(ts, d.edgeTime);
                    const eyCoord = series.priceToCoordinate(d.edgePrice);
                    if (cxCoord === null || cyCoord === null || exCoord === null || eyCoord === null) return;

                    const bcx = cxCoord * hr, bcy = cyCoord * vr;
                    const bex = exCoord * hr, bey = eyCoord * vr;
                    const radius = Math.sqrt((bex - bcx) ** 2 + (bey - bcy) ** 2);

                    ctx.globalAlpha = 0.1;
                    ctx.beginPath();
                    ctx.arc(bcx, bcy, radius, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.globalAlpha = 1.0;
                    ctx.beginPath();
                    ctx.arc(bcx, bcy, radius, 0, Math.PI * 2);
                    ctx.stroke();

                    this._drawAnchor(ctx, bcx, bcy, hr);
                    this._drawAnchor(ctx, bex, bey, hr);
                    break;
                }

                case 'text': {
                    const x = this._timeToX(ts, d.x);
                    const y = series.priceToCoordinate(d.y);
                    if (x === null || y === null) return;

                    const bx = x * hr, by = y * vr;
                    const fontSize = Math.round(12 * vr);
                    const lineHeight = Math.round(fontSize * 1.3);
                    ctx.font = `${fontSize}px sans-serif`;

                    const lines = (d.text || '').split('\n');
                    const padX = Math.round(6 * hr);
                    const padY = Math.round(4 * vr);

                    // Measure text width for background
                    let maxW = 0;
                    for (const line of lines) {
                        const w = ctx.measureText(line).width;
                        if (w > maxW) maxW = w;
                    }
                    const boxW = maxW + padX * 2;
                    const boxH = lines.length * lineHeight + padY * 2;

                    // Background panel
                    const cornerR = Math.round(3 * hr);
                    const rx0 = bx - padX, ry0 = by - padY;
                    ctx.fillStyle = 'rgba(20, 20, 35, 0.82)';
                    ctx.beginPath();
                    if (ctx.roundRect) {
                        ctx.roundRect(rx0, ry0, boxW, boxH, cornerR);
                    } else {
                        ctx.rect(rx0, ry0, boxW, boxH);
                    }
                    ctx.fill();

                    // Border
                    ctx.strokeStyle = d.color;
                    ctx.lineWidth = 1 * hr;
                    ctx.globalAlpha = 0.5;
                    ctx.beginPath();
                    if (ctx.roundRect) {
                        ctx.roundRect(rx0, ry0, boxW, boxH, cornerR);
                    } else {
                        ctx.rect(rx0, ry0, boxW, boxH);
                    }
                    ctx.stroke();
                    ctx.globalAlpha = 1.0;

                    // Text
                    ctx.fillStyle = d.color;
                    for (let i = 0; i < lines.length; i++) {
                        ctx.fillText(lines[i], bx, by + fontSize * 0.85 + i * lineHeight);
                    }

                    this._drawAnchor(ctx, bx - padX, by - padY, hr);
                    break;
                }
            }
        });
    }

    _drawAnchor(ctx, x, y, hr) {
        const r = 4 * hr;
        ctx.fillStyle = ANCHOR_FILL_COLOR;
        ctx.globalAlpha = 0.6;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1.0;
    }
}
