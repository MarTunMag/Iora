/**
 * pulse.js — Pulse Panel: D1 macro bias display.
 *
 * Shows D BIAS from Macro module (supply/demand sequence labels + direction).
 * Updates on data load and crosshair move.
 *
 * CRITICAL: Uses ONLY document.createElement() and textContent. NO innerHTML.
 */

const Pulse = {
    _panel: null,
    _biasEl: null,
    _visible: true,

    init() {
        // Create floating panel
        const panel = document.createElement('div');
        panel.id = 'pulse-panel';
        panel.style.cssText = 'position:fixed;bottom:12px;right:12px;z-index:1000;' +
            'background:rgba(18,18,28,0.92);border:1px solid #333;border-radius:6px;' +
            'padding:8px 12px;font-family:monospace;font-size:11px;color:#ccc;' +
            'min-width:180px;max-width:320px;pointer-events:auto;user-select:text;';

        // Header
        const header = document.createElement('div');
        header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';

        const title = document.createElement('span');
        title.textContent = 'PULSE';
        title.style.cssText = 'color:#4fc3f7;font-weight:bold;font-size:12px;letter-spacing:1px;';

        const closeBtn = document.createElement('span');
        closeBtn.textContent = '\u2715';
        closeBtn.style.cssText = 'cursor:pointer;color:#666;font-size:10px;';
        closeBtn.addEventListener('click', () => Pulse.toggle());

        header.appendChild(title);
        header.appendChild(closeBtn);
        panel.appendChild(header);

        // Bias line (big, colored)
        const biasEl = document.createElement('div');
        biasEl.style.cssText = 'font-size:14px;font-weight:bold;';
        biasEl.textContent = 'D BIAS: \u2014';
        panel.appendChild(biasEl);
        this._biasEl = biasEl;

        document.body.appendChild(panel);
        this._panel = panel;
    },

    toggle() {
        if (!this._panel) return;
        this._visible = !this._visible;
        this._panel.style.display = this._visible ? 'block' : 'none';
    },

    update() {
        if (!this._panel || !this._visible) return;

        const structData = (typeof Structure !== 'undefined') ? Structure.getData() : null;
        if (!structData) {
            this._biasEl.textContent = 'BIAS: \u2014';
            this._biasEl.style.color = '#888';
            return;
        }

        const parentBias = (structData.parent_bias || 'neutral').toUpperCase();
        const childBias = (structData.child_bias || 'neutral').toUpperCase();
        const chain = structData.chain_count || 0;
        const parentTf = structData.parent_tf || '';
        const childTf = structData.child_tf || '';

        // Color based on child bias alignment
        let color = '#888';
        if (structData.child_bias === 'bearish') color = '#FF4444';
        if (structData.child_bias === 'bullish') color = '#2196F3';

        this._biasEl.textContent = `${parentTf} ${parentBias} \u00B7 ${childTf} ${childBias} \u00B7 chain: ${chain}`;
        this._biasEl.style.color = color;
    },
};
