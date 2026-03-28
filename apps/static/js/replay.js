/**
 * replay.js — Bar replay: play/pause/step/jump, slider, client-side slicing.
 */

const Replay = {
    totalBars: 0,
    currentBar: 0,
    playing: false,
    playInterval: null,
    playSpeed: REPLAY_SPEED_MS, // ms per bar
    _multichartMode: false,
    _drivingCandles: null,

    init(totalBars) {
        this.totalBars = totalBars;
        this.currentBar = totalBars;
        this.playing = false;
        this._multichartMode = false;
        this._drivingCandles = null;
        if (this.playInterval) {
            clearInterval(this.playInterval);
            this.playInterval = null;
        }

        const slider = document.getElementById('replay-slider');
        slider.min = 1;
        slider.max = totalBars;
        slider.value = totalBars;

        this.setInfo(`Live — ${totalBars} bars`);
        this._bindEvents();
    },

    /** Init replay for multichart mode — uses driving panel's candle array */
    initForMultichart(drivingCandles) {
        this._multichartMode = true;
        this._drivingCandles = drivingCandles;
        this.totalBars = drivingCandles.length;
        this.currentBar = this.totalBars;
        this.playing = false;
        if (this.playInterval) {
            clearInterval(this.playInterval);
            this.playInterval = null;
        }

        const slider = document.getElementById('replay-slider');
        slider.min = 1;
        slider.max = this.totalBars;
        slider.value = this.totalBars;

        this.setInfo(`Live — ${this.totalBars} bars`);
        this._bindEvents();
    },

    _bindEvents() {
        const slider = document.getElementById('replay-slider');

        // Remove old listeners by replacing element
        const newSlider = slider.cloneNode(true);
        slider.parentNode.replaceChild(newSlider, slider);

        newSlider.addEventListener('input', (e) => {
            this.currentBar = parseInt(e.target.value);
            App.onReplayChange(this.currentBar);
        });

        // Step buttons
        this._bindBtn('replay-back10', () => this.step(-10));
        this._bindBtn('replay-back1', () => this.step(-1));
        this._bindBtn('replay-fwd1', () => this.step(1));
        this._bindBtn('replay-fwd10', () => this.step(10));

        // Play/pause
        this._bindBtn('replay-play', () => this.togglePlay());

        // Click on chart to jump to bar
        const container = document.getElementById('chart-container');
        // Remove old handler
        if (this._chartClickHandler) {
            container.removeEventListener('dblclick', this._chartClickHandler);
        }
        this._chartClickHandler = (e) => {
            if (Drawing.activeTool) return; // Don't interfere with drawing
            if (this._multichartMode) return; // Multichart panels handle their own dblclick
            const chart = Chart.getChart();
            if (!chart) return;
            const ts = chart.timeScale();
            const time = ts.coordinateToTime(e.offsetX);
            if (time === null) return;
            // Find nearest bar
            const candles = App.data?.candles;
            if (!candles) return;
            let nearest = 0;
            let minDiff = Infinity;
            for (let i = 0; i < candles.length; i++) {
                const diff = Math.abs(candles[i].time - time);
                if (diff < minDiff) {
                    minDiff = diff;
                    nearest = i + 1;
                }
            }
            this.jumpTo(nearest);
        };
        container.addEventListener('dblclick', this._chartClickHandler);
    },

    _bindBtn(id, handler) {
        const btn = document.getElementById(id);
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener('click', handler);
    },

    step(delta) {
        this.currentBar = Math.max(1, Math.min(this.totalBars, this.currentBar + delta));
        document.getElementById('replay-slider').value = this.currentBar;
        App.onReplayChange(this.currentBar);
    },

    jumpTo(barIdx) {
        this.currentBar = Math.max(1, Math.min(this.totalBars, barIdx));
        document.getElementById('replay-slider').value = this.currentBar;
        App.onReplayChange(this.currentBar);
    },

    togglePlay() {
        this.playing = !this.playing;
        const btn = document.getElementById('replay-play');
        btn.textContent = this.playing ? '⏸' : '▶';
        btn.classList.toggle('active', this.playing);

        if (this.playing) {
            this.playInterval = setInterval(() => {
                if (this.currentBar >= this.totalBars) {
                    this.togglePlay(); // Stop at end
                    return;
                }
                this.step(1);
            }, this.playSpeed);
        } else {
            clearInterval(this.playInterval);
            this.playInterval = null;
        }
    },

    setInfo(text) {
        document.getElementById('replay-info').textContent = text;
    },
};
