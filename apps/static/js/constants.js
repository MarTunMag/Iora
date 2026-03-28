/**
 * constants.js — Single source of truth for all shared constants.
 *
 * Magic numbers, color palettes, and UI theme colors used across JS modules.
 * Loaded before all other JS modules via viewer.html script order.
 */

// ── Bar limits ──────────────────────────────────────────────────────────────
const MAX_BARS = 20000;

// ── Drawing tools ───────────────────────────────────────────────────────────
const ANCHOR_HIT_PX = 8;
const UNDO_STACK_SIZE = 100;

// ── Timing ──────────────────────────────────────────────────────────────────
const REPLAY_SPEED_MS = 200;
const DEBOUNCE_MS = 300;
const FLASH_TIMEOUT_MS = 3000;

// ── Default bar counts per TF (used by main.js + multichart.js) ─────────────
// Generous for intraday replay scrollback, practical for HTFs
const BAR_COUNTS_BY_TF = {
    M1: 15000, M5: 6000, M15: 6000, M30: 6000,
    H1: 6000, H4: 1200, D1: 600, W1: 300, MN1: 100,
};

// ── Default visible bar window per TF ───────────────────────────────────────
// How many bars to show initially (scrolled to the right). Full data is loaded
// for replay — this just sets the initial zoom level.
const VISIBLE_BARS_BY_TF = {
    M1: 500, M5: 500, M15: 500, M30: 500,
    H1: 500, H4: 300, D1: 300, W1: 200, MN1: 120,
};

// ── Background ──────────────────────────────────────────────────────────────
const BG_COLOR = '#0a0a0f';

// ── Candle colors (chart.js series) ─────────────────────────────────────────
const CANDLE_COLORS = {
    candle: { up: '#6ba3d6', down: '#e06466' },
    hollow: { up: '#26c6c6', upBorder: '#26c6c6', down: '#e05252', downBorder: '#e05252' },
    bars:   { up: '#4a90d9', down: '#e25141' },
    line:   '#3366ff',
};
const UP_COLOR = '#6ba3d6';
const DOWN_COLOR = '#e06466';

// ── Drawing colors ──────────────────────────────────────────────────────────
const DRAW_COLOR_DEFAULT = '#FFD700';
const ANCHOR_FILL_COLOR = '#448aff';

// ── Trendline colors/widths/dash ────────────────────────────────────────────
const TL_COLORS = {
    W1:  { bull: '#FF9800', bear: '#FF9800' },
    D1:  { bull: '#2196F3', bear: '#F44336' },
    H4:  { bull: '#42A5F5', bear: '#EF5350' },
    H1:  { bull: '#448AFF', bear: '#FF5252' },
    M15: { bull: '#64B5F6', bear: '#E57373' },
    M5:  { bull: '#90CAF9', bear: '#EF9A9A' },
    M1:  { bull: '#B3E5FC', bear: '#F8BBD0' },
};

const TL_WIDTHS = { W1: 3, D1: 2.5, H4: 2, H1: 1.5, M15: 1.5, M5: 1, M1: 1 };

const TL_DASH = {
    W1: [], D1: [], H4: [], H1: [],
    M15: [8, 4], M5: [4, 3], M1: [2, 3],
};

const TL_PARENT = { D1: 'W1', H4: 'D1', H1: 'H4', M15: 'H1', M5: 'M15', M1: 'M5' };

// ── HTF candle background colors ────────────────────────────────────────────
const HTF_COLORS = {
    '12M': 'rgba(74, 20, 140, 0.18)',
    '6M':  'rgba(106, 27, 154, 0.15)',
    '3M':  'rgba(142, 36, 170, 0.12)',
    MN1: 'rgba(255, 152, 0, 0.15)',
    W1:  'rgba(255, 152, 0, 0.10)',
    D1:  'rgba(100, 181, 246, 0.10)',
    H4:  'rgba(66, 165, 245, 0.08)',
    H1:  'rgba(68, 138, 255, 0.06)',
    M30: 'rgba(100, 181, 246, 0.05)',
    M15: 'rgba(100, 181, 246, 0.05)',
    M5:  'rgba(144, 202, 249, 0.04)',
};

// ── Crosshair colors ────────────────────────────────────────────────────────
const CROSSHAIR_LINE_COLOR = '#448aff44';
const CROSSHAIR_LABEL_BG = '#1a3a6a';

// ── Watermark ───────────────────────────────────────────────────────────────
const WATERMARK_COLOR = 'rgba(255,255,255,0.3)';
const WATERMARK_COLOR_MC = 'rgba(255,255,255,0.04)';

// ── UI theme (multichart toolbar/sidebar) ───────────────────────────────────
const UI = {
    PANEL_BG:     '#1a1a24',
    ACCENT:       '#448aff',
    ACCENT_BG:    '#1a3a6a',
    ACCENT_TEXT:  '#90caf9',
    BORDER:       '#333',
    BORDER_DARK:  '#222',
    TEXT_DIM:     '#666',
    TEXT_MID:     '#aaa',
    TEXT_LIGHT:   '#ccc',
    FOCUS_GREEN:  '#4CAF50',
    SECTION_BORDER: '#1e1e28',
};

// -- Context mode background colors --
const CONTEXT_MODE_COLORS = {
    RIDE:  'rgba(76, 175, 80, 0.03)',   // Green tint
    SCALP: 'rgba(255, 235, 59, 0.03)',  // Yellow tint
    FLIP:  'rgba(244, 67, 54, 0.05)',   // Red tint
    SKIP:  'rgba(0, 0, 0, 0)',          // No tint
};

