/**
 * chart.js — LW Charts setup, multi-type series (OHLC, HA, Line, Bars), volume.
 */

// Right-side buffer: ~0.5 day of empty space after last candle (in bar counts per TF)
const RIGHT_OFFSET_BY_TF = {
    M1: 180,  // 180 bars = 3h of M1
    M5: 36,   // 36 bars = 3h
    M15: 12,  // 12 bars = 3h
    M30: 8,   // 8 bars = 4h
    H1: 12,   // 12 bars = 12h
    H4: 6,    // 6 bars = 24h
    D1: 4,    // 4 bars = 4 days
    W1: 3,    // 3 bars = 3 weeks
    MN1: 2,   // 2 bars = 2 months
};

// Candle colors, UP_COLOR, DOWN_COLOR now in constants.js (CANDLE_COLORS)

const Chart = {
    chart: null,
    /** The "main" series — could be candlestick, bar, or line. Overlays attach to this. */
    candleSeries: null,
    _seriesType: 'ohlc',   // 'ohlc' | 'ha' | 'line' | 'bars'
    _lastPriceLine: null,
    _currentData: null,     // last full data payload for re-rendering on type switch
    _resizeObserver: null,

    init() {
        const container = document.getElementById('chart-container');

        this.chart = LightweightCharts.createChart(container, {
            layout: {
                background: { type: 'solid', color: BG_COLOR },
                textColor: '#666',
                fontSize: 11,
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
                rightOffset: 6,
                barSpacing: 6,
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

        // Create initial candlestick series
        this._createCandleSeries();

        // Auto-resize
        this._resizeObserver = new ResizeObserver(() => this.resize());
        this._resizeObserver.observe(container);
    },

    destroy() {
        if (this._resizeObserver) {
            this._resizeObserver.disconnect();
            this._resizeObserver = null;
        }
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
        this.candleSeries = null;
        this._lastPriceLine = null;
        this._currentData = null;
    },

    // ── Series creation by type ──────────────────────────────────────────

    _createCandleSeries() {
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: CANDLE_COLORS.candle.up,
            downColor: CANDLE_COLORS.candle.down,
            borderUpColor: CANDLE_COLORS.candle.up,
            borderDownColor: CANDLE_COLORS.candle.down,
            wickUpColor: CANDLE_COLORS.candle.up,
            wickDownColor: CANDLE_COLORS.candle.down,
            priceFormat: { type: 'price', minMove: 0.00001 },
        });
    },

    _createHollowSeries() {
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: 'transparent',
            downColor: CANDLE_COLORS.hollow.down,
            borderUpColor: CANDLE_COLORS.hollow.upBorder,
            borderDownColor: CANDLE_COLORS.hollow.downBorder,
            wickUpColor: CANDLE_COLORS.hollow.upBorder,
            wickDownColor: CANDLE_COLORS.hollow.downBorder,
            priceFormat: { type: 'price', minMove: 0.00001 },
        });
    },

    _createBarSeries() {
        this.candleSeries = this.chart.addBarSeries({
            upColor: CANDLE_COLORS.bars.up,
            downColor: CANDLE_COLORS.bars.down,
            thinBars: true,
            priceFormat: { type: 'price', minMove: 0.00001 },
        });
    },

    _createLineSeries() {
        this.candleSeries = this.chart.addLineSeries({
            color: CANDLE_COLORS.line,
            lineWidth: 2,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 3,
            priceFormat: { type: 'price', minMove: 0.00001 },
        });
    },

    /**
     * Remove the current main series and create a new one of the given type.
     * Detaches all overlay primitives first (caller must re-attach).
     */
    _switchSeries(type) {
        // Detach overlay primitives before removing series
        Overlays._clearPrimitives();
        Drawing._renderDrawings();  // will detach drawing primitives too

        // Remove current main series
        if (this.candleSeries) {
            this._lastPriceLine = null;
            this.chart.removeSeries(this.candleSeries);
            this.candleSeries = null;
        }

        // Create new series of requested type
        if (type === 'line') {
            this._createLineSeries();
        } else if (type === 'bars') {
            this._createBarSeries();
        } else if (type === 'hollow') {
            this._createHollowSeries();
        } else {
            // 'ohlc' and 'ha' both use candlestick series
            this._createCandleSeries();
        }

        this._seriesType = type;
    },

    // ── Data methods ─────────────────────────────────────────────────────

    resize() {
        if (!this.chart) return;
        const container = document.getElementById('chart-container');
        this.chart.resize(container.clientWidth, container.clientHeight);
    },

    setData(data) {
        if (!data.candles || data.candles.length === 0) return;
        this._currentData = data;

        const candles = data.candles;
        const type = data.candle_type || 'ohlc';

        // Switch series type if needed
        if (type !== this._seriesType) {
            this._switchSeries(type);
        }

        // Set data (line series needs {time, value} format)
        if (type === 'line') {
            this.candleSeries.setData(candles.map(c => ({ time: c.time, value: c.close })));
        } else {
            this.candleSeries.setData(candles);
        }

        // Apply TF-specific right offset buffer
        const offset = RIGHT_OFFSET_BY_TF[data.tf] || 6;
        this.chart.timeScale().applyOptions({ rightOffset: offset });

        // Show only the last N bars initially (full data loaded for replay)
        const visibleBars = VISIBLE_BARS_BY_TF[data.tf] || 500;
        if (candles.length > visibleBars) {
            this.chart.timeScale().setVisibleLogicalRange({
                from: candles.length - visibleBars,
                to: candles.length - 1 + offset,
            });
        } else {
            this.chart.timeScale().fitContent();
        }

        this._updatePriceLine(candles);
        this._updatePricePrecision(candles);
    },

    /**
     * Switch chart type client-side without reloading data.
     * Called from main.js when user picks a different candle type.
     * HA requires server reload (different OHLC values), handled by main.js.
     */
    setChartType(type, data) {
        if (type === this._seriesType) return;

        this._switchSeries(type);

        const candles = data.candles;
        if (type === 'line') {
            this.candleSeries.setData(candles.map(c => ({ time: c.time, value: c.close })));
        } else {
            this.candleSeries.setData(candles);
        }

        this._updatePriceLine(candles);
        this._updatePricePrecision(candles);

        // Re-attach overlay primitives (caller should call _rebuildOverlays)
    },

    updateCandles(candles) {
        if (!candles || candles.length === 0) return;
        if (this._seriesType === 'line') {
            this.candleSeries.setData(candles.map(c => ({ time: c.time, value: c.close })));
        } else {
            this.candleSeries.setData(candles);
        }
        this._updatePriceLine(candles);
    },

    _updatePriceLine(candles) {
        if (this._lastPriceLine) {
            try { this.candleSeries.removePriceLine(this._lastPriceLine); } catch(e) {}
        }
        this._lastPriceLine = null;
        if (candles.length === 0) return;
        const last = candles[candles.length - 1];
        this._lastPriceLine = this.candleSeries.createPriceLine({
            price: last.close,
            color: last.close >= last.open ? UP_COLOR : DOWN_COLOR,
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            axisLabelVisible: true,
            title: '',
        });
    },

    _updatePricePrecision(candles) {
        if (candles.length === 0) return;
        const price = candles[candles.length - 1].close;
        let precision = 5;
        if (price >= 1000) precision = 1;
        else if (price >= 100) precision = 2;
        else if (price >= 10) precision = 3;
        this.candleSeries.applyOptions({
            priceFormat: { type: 'price', precision: precision, minMove: Math.pow(10, -precision) },
        });
    },

    /** Set watermark text (symbol + TF). */
    setWatermark(symbol, tf) {
        this.chart.applyOptions({
            watermark: {
                visible: true,
                text: `${symbol}  ${tf}`,
                fontSize: 48,
                color: 'rgba(255, 255, 255, 0.04)',
                fontFamily: 'Segoe UI, sans-serif',
            },
        });
    },

    /** Subscribe to crosshair move for OHLCV tooltip. */
    enableCrosshairTooltip() {
        const tooltip = document.getElementById('crosshair-ohlcv');
        if (!tooltip) return;
        this.chart.subscribeCrosshairMove((param) => {
            if (!param.time || !param.seriesData) {
                tooltip.style.display = 'none';
                return;
            }
            const data = param.seriesData.get(this.candleSeries);
            if (!data) {
                tooltip.style.display = 'none';
                return;
            }
            // Line series only has {time, value}
            if (this._seriesType === 'line') {
                tooltip.style.display = 'flex';
                tooltip.innerHTML = `<span style="color:#888">Close</span> <span style="color:${UP_COLOR}">${data.value}</span>`;
                return;
            }
            const o = data.open, h = data.high, l = data.low, c = data.close;
            const up = c >= o;
            const color = up ? UP_COLOR : DOWN_COLOR;
            tooltip.style.display = 'flex';
            tooltip.innerHTML =
                `<span style="color:#888">O</span> <span style="color:${color}">${o}</span> ` +
                `<span style="color:#888">H</span> <span style="color:${color}">${h}</span> ` +
                `<span style="color:#888">L</span> <span style="color:${color}">${l}</span> ` +
                `<span style="color:#888">C</span> <span style="color:${color}">${c}</span>`;
        });
    },

    /** Get the chart instance for overlays to attach primitives. */
    getChart() { return this.chart; },
    getCandleSeries() { return this.candleSeries; },
};
