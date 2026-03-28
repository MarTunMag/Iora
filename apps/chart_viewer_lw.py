"""
Lightweight Charts viewer — Flask + TradingView Lightweight Charts v4.2.

Primary (and only) chart viewer. Runs on port 8060.
Uses run_pipeline() for engine output, serves via Flask REST API.
"""

from __future__ import annotations

import time
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import base64
import re

import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_caching import Cache

try:
    from flask_compress import Compress
except ImportError:
    Compress = None

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    Limiter = None

from iora.constants import (
    BASE_TF_OPTIONS,
    SMART_LOOKBACK,
    TF_ORDER,
    TF_ORDER_HTF_FIRST,
    TF_PARENT,
    TL_TF_OPTIONS,
    VALID_CANDLE_TYPES,
    VALID_HTF_CANDLE_TYPES,
    ZONE_TF_OPTIONS,
    get_sub_tf,
)
import yaml

from iora.data.parquet_storage import ParquetStorage
from iora.orchestrator.pipeline import PipelineConfig, PipelineOutput
from iora.orchestrator.signal_engine import run_signal_engine
from iora.paths import DATA_DIR, SCREENSHOTS_DIR, SETTINGS_FILE

logging.basicConfig(level=logging.INFO, force=True)
log = logging.getLogger(__name__)

# ── App setup ────────────────────────────────────────────────────────────

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # No browser caching for static files
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache"})
if Compress is not None:
    Compress(app)

if Limiter is not None:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )
else:
    limiter = None


def _rate_limit_exceeded(e):
    return jsonify({"error": "Rate limit exceeded. Try again later."}), 429


if limiter is not None:
    app.register_error_handler(429, _rate_limit_exceeded)


def _limit(rate: str):
    """Apply rate limit if flask-limiter is available, otherwise no-op."""
    if limiter is not None:
        return limiter.limit(rate)
    return lambda f: f


@app.after_request
def add_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response


storage = ParquetStorage(base_dir=DATA_DIR)

# Warehouse loader — update_storage.py writes here; may have newer data than raw/
from iora.data.data_loader import Mt5DataLoader
try:
    _warehouse_loader = Mt5DataLoader()
except Exception as e:
    log.warning("Mt5DataLoader init failed, using raw storage: %s", e)
    _warehouse_loader = None

# Thread pool for parallel multichart loading (reused across requests)
_EXECUTOR = ThreadPoolExecutor(max_workers=4)

# ── Static file cache busting: MD5 hash per file, computed once at startup ──

import hashlib

_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_HASHES: dict[str, str] = {}


def _compute_static_hashes() -> None:
    """Hash every .js and .css file in static/ at startup. 8-char hex digest."""
    for pattern in ("js/*.js", "css/*.css"):
        for f in sorted(_STATIC_DIR.glob(pattern)):
            data = f.read_bytes()
            _STATIC_HASHES[f.name] = hashlib.md5(data).hexdigest()[:8]


_compute_static_hashes()


@app.context_processor
def inject_cache_bust():
    """Make cache_bust('filename.js') available in all Jinja2 templates."""
    def cache_bust(filename: str) -> str:
        return _STATIC_HASHES.get(filename, "0")
    return {"cache_bust": cache_bust}

# Load viewer defaults from settings.yml
_settings = {}
if SETTINGS_FILE.exists():
    with open(SETTINGS_FILE) as f:
        _settings = yaml.safe_load(f) or {}
_viewer_cfg = _settings.get("viewer", {})
DEFAULT_SYMBOL = _viewer_cfg.get("default_symbol", "GBPUSD")
DEFAULT_TF = _viewer_cfg.get("default_tf", "H4")
DEFAULT_BAR_COUNT = _viewer_cfg.get("default_bar_count", 2000)

# ── Data loading ─────────────────────────────────────────────────────────

CACHE_TIMEOUT_SEC = 600  # 10 minutes


@cache.memoize(timeout=CACHE_TIMEOUT_SEC)
def _load(symbol: str, tf: str, start: str | None, end: str | None) -> pd.DataFrame:
    """Load OHLCV data, preferring warehouse (Mt5DataLoader) over raw (ParquetStorage)."""
    df = pd.DataFrame()

    # Try warehouse first (update_storage.py writes here — usually fresher)
    if _warehouse_loader is not None:
        try:
            df = _warehouse_loader.load(symbol, tf, start_date=start, end_date=end)
        except Exception as e:
            log.debug("Warehouse load failed for %s %s: %s", symbol, tf, e)
            df = pd.DataFrame()

    # Fall back to raw parquet storage
    if df.empty:
        df = storage.load(symbol=symbol, timeframe=tf, start_date=start, end_date=end)

    if df.empty:
        return df
    needed = {"open", "high", "low", "close"}
    if not needed.issubset(set(df.columns)):
        return pd.DataFrame()
    return df


def _get_symbols() -> list[str]:
    syms = storage.list_symbols()
    return syms if syms else ["XAUUSD"]


def _get_latest_date(symbol: str, tf: str) -> str:
    ts = storage.get_latest_timestamp(symbol, tf)
    if ts is not None:
        return ts.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


# ── Core compute (cached 10 min) ─────────────────────────────────────────


@cache.memoize(timeout=CACHE_TIMEOUT_SEC)
def load_and_compute(
    symbol: str,
    base_tf: str,
    bar_count: int,
    end_date_str: str,
    replay_start_date: str = "",
):
    t0 = time.time()

    if replay_start_date:
        # Load ALL data (no end cutoff) so we have bars AFTER the replay date
        base_df = _load(symbol, base_tf, start=None, end=None)
    else:
        base_df = _load(symbol, base_tf, start=None, end=end_date_str)

    if base_df.empty:
        return {
            "error": f"No {base_tf} data for {symbol} up to {end_date_str}",
            "elapsed": time.time() - t0,
        }

    replay_start_idx = 0  # default: no replay offset

    if replay_start_date:
        # Find bar at/after the replay start date
        replay_ts = pd.Timestamp(replay_start_date)
        after_mask = base_df.index >= replay_ts
        if after_mask.any():
            replay_pos = after_mask.argmax()  # first True position
        else:
            # Date is beyond all data — fall back to end
            replay_pos = len(base_df) - 1

        # Replay uses 6000 bars total: history before date + forward after date
        replay_total = 6000
        # 40% history before the date, 60% forward after
        context_bars = int(replay_total * 0.4)
        start_pos = max(0, replay_pos - context_bars)
        end_pos = min(len(base_df), start_pos + replay_total)
        base_df = base_df.iloc[start_pos:end_pos]
        replay_start_idx = replay_pos - start_pos
    else:
        base_df = base_df.tail(int(bar_count))

    start_str = base_df.index[0].strftime("%Y-%m-%d")

    base_idx = TF_ORDER_HTF_FIRST.index(base_tf) if base_tf in TF_ORDER_HTF_FIRST else len(TF_ORDER_HTF_FIRST)
    htfs_to_load = set(TF_ORDER_HTF_FIRST[:base_idx])  # only TFs above base

    # When replay mode, load HTF data covering same range (no end cutoff)
    load_end = None if replay_start_date else end_date_str

    htf_data: dict[str, pd.DataFrame] = {}
    htfs_to_load.discard(base_tf)  # already loaded above
    for tf in htfs_to_load:
        htf_df = _load(symbol, tf, start=start_str, end=load_end)
        if not htf_df.empty:
            htf_data[tf] = htf_df

    # Resample custom HTF candles (3M, 6M, 12M) from MN1 data for display
    if "MN1" in htf_data and not htf_data["MN1"].empty:
        mn1 = htf_data["MN1"]
        for label, rule in [("3M", "QS"), ("6M", "6MS"), ("12M", "YS")]:
            resampled = mn1.resample(rule).agg(
                {"open": "first", "high": "max", "low": "min", "close": "last"}
            ).dropna()
            if not resampled.empty:
                htf_data[label] = resampled

    # Build engine data — include all TFs with data (MN1 included for zone detection)
    engine_data: dict[str, pd.DataFrame] = {}
    for tf in TF_ORDER:
        if tf == base_tf:
            engine_data[tf] = base_df
        elif tf in htf_data:
            engine_data[tf] = htf_data[tf]
    # LTF data needed by signal engine for zone detection at M1/M5 resolution.
    # htfs_to_load only includes TFs ABOVE base — when base is H4+, M1/M5 are missing.
    for ltf in ["M1", "M5"]:
        if ltf not in engine_data:
            ltf_df = _load(symbol, ltf, start=start_str, end=load_end)
            if not ltf_df.empty:
                engine_data[ltf] = ltf_df

    # Run signal engine (pipeline + rules)
    pulse_result: PipelineOutput | None = None
    signal_list = []
    context_series = []
    if engine_data.get(base_tf) is not None:
        signal_result = run_signal_engine(
            engine_data,
            base_tf,
            pipeline_config=PipelineConfig(macro_bias_on=False, cycle_on=False),
            disabled_rules=["scalp_entry", "growth_addon", "tp_targets"],
        )
        pulse_result = signal_result.pipeline
        signal_list = signal_result.signals
        context_series = signal_result.context_series

    return {
        "base_df": base_df,
        "htf_data": htf_data,
        "pulse": pulse_result,
        "signals": signal_list,
        "context_series": context_series,
        "elapsed": time.time() - t0,
        "replay_start_idx": int(replay_start_idx),
    }


# ── Serialization (extracted to apps/serializers.py) ──────────────────────

from apps.serializers import (
    serialize_htf_candles,
    serialize_ohlcv,
    serialize_signals,
    serialize_structure,
    serialize_trendlines,
    serialize_zones,
)


# ── Routes ───────────────────────────────────────────────────────────────


@app.route("/")
def index():
    resp = app.make_response(render_template("viewer.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/symbols")
def api_symbols():
    return jsonify({"symbols": _get_symbols()})


@app.route("/api/timeframes")
def api_timeframes():
    return jsonify(
        {
            "base": BASE_TF_OPTIONS,
            "zones": ZONE_TF_OPTIONS,
            "trendlines": TL_TF_OPTIONS,
        }
    )


@app.route("/api/config")
def api_config():
    """Serve canonical constants so JS never hardcodes TF lists or candle types."""
    return jsonify(
        {
            "tf_order": list(TF_ORDER),
            "tf_order_htf_first": list(TF_ORDER_HTF_FIRST),
            "htf_candle_tf_options": ["12M", "6M", "3M", "MN1", "W1", "D1", "H4", "H1", "M30", "M15", "M5"],
            "base_tf_options": list(BASE_TF_OPTIONS),
            "zone_tf_options": list(ZONE_TF_OPTIONS),
            "tl_tf_options": list(TL_TF_OPTIONS),
            "valid_candle_types": sorted(VALID_CANDLE_TYPES),
            "valid_htf_candle_types": sorted(VALID_HTF_CANDLE_TYPES),
            "default_symbol": DEFAULT_SYMBOL,
            "default_tf": DEFAULT_TF,
            "default_bar_count": DEFAULT_BAR_COUNT,
        }
    )


def _build_tf_response(
    symbol: str,
    tf: str,
    bars: int,
    end: str,
    candle_type: str,
    htf_candle_type: str,
    htf_tfs_filter: set[str] | None = None,
    replay_start_date: str = "",
) -> dict:
    """Build a single-TF response dict. Returns error tuple on failure."""
    data = load_and_compute(symbol, tf, bars, end, replay_start_date=replay_start_date)
    if "error" in data:
        return {"error": data["error"]}

    base_df = data["base_df"]
    pulse = data["pulse"]
    htf_data = data["htf_data"]
    signals = data.get("signals", [])
    context_series = data.get("context_series", [])

    if htf_tfs_filter:
        htf_data = {k: v for k, v in htf_data.items() if k in htf_tfs_filter}

    response: dict = {
        "symbol": symbol,
        "tf": tf,
        "candle_type": candle_type,
        "candles": serialize_ohlcv(base_df, candle_type),
        "elapsed": data["elapsed"],
    }

    if pulse is not None:
        response["zones"] = serialize_zones(pulse)
        response["trendlines"] = serialize_trendlines(pulse)
        response["rule_signals"] = serialize_signals(signals)
        response["context"] = [
            {"time": int(c["time"].timestamp()), "mode": c["mode"], "detail": c["detail"]}
            for c in context_series
        ]
    else:
        response["zones"] = {}
        response["trendlines"] = {}
        response["rule_signals"] = []
        response["context"] = []

    response["htf_candles"] = serialize_htf_candles(htf_data, htf_candle_type)
    response["replay_start_idx"] = data.get("replay_start_idx", 0)
    return response


@app.route("/api/multichart_data", methods=["POST"])
@_limit("10 per minute")
def api_multichart_data():
    """Compound endpoint: compute data for multiple TFs in one request."""
    try:
        body = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400
    if not body:
        return jsonify({"error": "Request body required"}), 400

    symbol = body.get("symbol")
    tfs = body.get("tfs")
    if not symbol or not tfs or not isinstance(tfs, list):
        return jsonify({"error": "symbol (string) and tfs (list) required"}), 400

    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400
    for tf in tfs:
        if tf not in BASE_TF_OPTIONS:
            return jsonify({"error": f"Invalid timeframe: {tf}"}), 400
    if len(tfs) > 8:
        return jsonify({"error": "Maximum 8 TFs per request"}), 400

    candle_type = body.get("candle_type", "ohlc")
    if candle_type not in VALID_CANDLE_TYPES:
        return jsonify({"error": f"Invalid candle_type: {candle_type}"}), 400
    htf_candle_type = body.get("htf_candle_type", "ohlc")
    if htf_candle_type not in VALID_HTF_CANDLE_TYPES:
        return jsonify({"error": f"Invalid htf_candle_type: {htf_candle_type}"}), 400

    end = body.get("end", "")
    # Replay mode requires explicit opt-in via "replay_from" field.
    # "end" alone is a date cutoff — NOT a replay start point.
    replay_start_date = body.get("replay_from", "")
    if end:
        try:
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format — expected YYYY-MM-DD"}), 400
    if replay_start_date:
        try:
            datetime.strptime(replay_start_date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid replay_from date format — expected YYYY-MM-DD"}), 400
    bar_counts = body.get("bar_counts", {})

    log.info("MULTICHART request: symbol=%s tfs=%s bar_counts=%s end=%s replay=%s",
             symbol, tfs, bar_counts, end, replay_start_date)

    # Build args for each TF
    tf_args = []
    for tf in tfs:
        bars = bar_counts.get(tf, SMART_LOOKBACK.get(tf, 800))
        try:
            bars = int(bars)
        except (ValueError, TypeError):
            bars = SMART_LOOKBACK.get(tf, 800)
        bars = max(1, min(bars, 20000))
        log.info("  TF=%s bars=%d", tf, bars)
        tf_end = end if end else _get_latest_date(symbol, tf)
        tf_args.append((tf, bars, tf_end))

    # Load all TFs in parallel — biggest speedup for multichart
    def _load_one_tf(args):
        tf, bars, tf_end = args
        result = _build_tf_response(
            symbol, tf, bars, tf_end, candle_type, htf_candle_type,
            replay_start_date=replay_start_date,
        )
        if isinstance(result, dict) and "error" in result and "candles" not in result:
            return tf, {"error": result["error"]}
        return tf, result

    results: dict[str, dict] = {}
    for tf, result in _EXECUTOR.map(_load_one_tf, tf_args):
        results[tf] = result

    # Propagate rule_signals from finest-resolution panel to all panels.
    # Signals fire on M1 CHOCH events — only the finest TF panel catches them.
    # Coarser panels need the same signals for marker display (time-snapped).
    finest_signals = []
    for tf in reversed(TF_ORDER):  # M1 first (finest)
        if tf in results and isinstance(results[tf], dict):
            sigs = results[tf].get("rule_signals", [])
            if sigs:
                finest_signals = sigs
                break
    if finest_signals:
        for tf, result in results.items():
            if isinstance(result, dict) and not result.get("rule_signals"):
                result["rule_signals"] = finest_signals

    return jsonify(results)


# TODO: Rules will be built from scratch after multichart visual validation.
# Previous cascade rules archived to docs/archive/rules_cascade_v1/.


@app.route("/api/data")
@_limit("10 per minute")
def api_data():
    symbol = request.args.get("symbol")
    tf = request.args.get("tf")
    candle_type = request.args.get("candle_type", "ohlc")

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if not tf:
        return jsonify({"error": "tf is required"}), 400

    # ── Input validation ──────────────────────────────────────────────
    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400
    if tf not in BASE_TF_OPTIONS:
        return jsonify({"error": f"Invalid timeframe: {tf}"}), 400
    if candle_type not in VALID_CANDLE_TYPES:
        return jsonify({"error": f"Invalid candle_type: {candle_type}"}), 400
    try:
        bars = int(request.args.get("bars", SMART_LOOKBACK.get(tf, 800)))
    except (ValueError, TypeError):
        return jsonify({"error": "bars must be an integer"}), 400
    if bars < 1 or bars > 20000:
        return jsonify({"error": "bars must be between 1 and 20000"}), 400

    htf_candle_type = request.args.get("htf_candle_type", "ohlc")
    if htf_candle_type not in VALID_HTF_CANDLE_TYPES:
        return jsonify({"error": f"Invalid htf_candle_type: {htf_candle_type}"}), 400

    end = request.args.get("end", "")
    replay_start_date = ""
    if end:
        try:
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format — expected YYYY-MM-DD"}), 400
        # User explicitly set a date — treat as replay start point
        replay_start_date = end
        end = _get_latest_date(symbol, tf)
    else:
        end = _get_latest_date(symbol, tf)

    htf_tfs_param = request.args.get("htf_tfs", "")
    if htf_tfs_param:
        htf_tfs_list = htf_tfs_param.split(",")
        valid_tfs = set(TF_ORDER)
        invalid = [t for t in htf_tfs_list if t not in valid_tfs]
        if invalid:
            return jsonify({"error": f"Invalid htf_tfs: {', '.join(invalid)}"}), 400
        htf_filter = set(htf_tfs_list)
    else:
        htf_filter = None

    result = _build_tf_response(
        symbol, tf, bars, end, candle_type, htf_candle_type, htf_filter,
        replay_start_date=replay_start_date,
    )
    if "error" in result and "candles" not in result:
        return jsonify({"error": result["error"]}), 404

    return jsonify(result)


@cache.memoize(timeout=CACHE_TIMEOUT_SEC)
def _get_structure(symbol: str, tf: str):
    """Compute structure state for child TF + auto-resolved parent TF."""
    from iora.engine.zone_detect import compute_structure, ZoneResult
    from iora.engine.structure_state import compute_structure_state

    parent_tf = TF_PARENT.get(tf)
    sub_tf = get_sub_tf(tf)

    # Bar limits per TF — enough for structure analysis without O(n*m) blowup.
    # Higher TFs need fewer bars (D1=500≈2yr, W1=200≈4yr, MN1=100≈8yr).
    TF_BAR_CAPS = {
        'MN1': 100, 'W1': 200, 'D1': 500,
        'H4': 2000, 'H1': 3000,
        'M30': 4000, 'M15': 5000, 'M5': 8000, 'M1': 15000,
    }
    def _cap(df, tf_key):
        cap = TF_BAR_CAPS.get(tf_key, 3000)
        return df.iloc[-cap:] if len(df) > cap else df

    # Child TF
    child_df = _load(symbol, tf, None, None)
    if child_df.empty:
        empty = ZoneResult(zones=[], breaks=[], bias="neutral")
        return {
            "child": empty, "parent": empty, "sub": empty,
            "state": None, "sub_state": None,
            "parent_tf": parent_tf, "sub_tf": sub_tf,
        }
    if len(child_df) > 1:
        child_df = child_df.iloc[:-1]
    child_df = _cap(child_df, tf)
    child_result = compute_structure(child_df)

    # Parent TF
    if parent_tf:
        parent_df = _load(symbol, parent_tf, None, None)
        if not parent_df.empty and len(parent_df) > 1:
            parent_df = parent_df.iloc[:-1]
        if not parent_df.empty:
            parent_df = _cap(parent_df, parent_tf)
        parent_result = compute_structure(parent_df) if not parent_df.empty else ZoneResult(zones=[], breaks=[], bias="neutral")
    else:
        parent_result = ZoneResult(zones=[], breaks=[], bias="neutral")

    state = compute_structure_state(child_result, parent_result)

    # Sub TF (one level below child) — uses get_sub_tf for M30 fallback
    if sub_tf:
        sub_df = _load(symbol, sub_tf, None, None)
        if not sub_df.empty and len(sub_df) > 1:
            sub_df = sub_df.iloc[:-1]
        if not sub_df.empty:
            sub_df = _cap(sub_df, sub_tf)
        sub_result = compute_structure(sub_df) if not sub_df.empty else ZoneResult(zones=[], breaks=[], bias="neutral")
        sub_state = compute_structure_state(sub_result, child_result)
    else:
        sub_result = ZoneResult(zones=[], breaks=[], bias="neutral")
        sub_state = None

    return {
        "child": child_result,
        "parent": parent_result,
        "sub": sub_result,
        "state": state,
        "sub_state": sub_state,
        "parent_tf": parent_tf,
        "sub_tf": sub_tf,
    }


@app.route("/api/structure", methods=["POST"])
def api_structure():
    """Return unified structure: child+parent zones, events, boundaries, zigzag."""
    params = request.json or {}
    symbol = params.get("symbol", "GBPUSD")
    tf = params.get("tf", "H4")

    # Input validation (mirrors api_data)
    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400
    if tf not in BASE_TF_OPTIONS:
        return jsonify({"error": f"Invalid timeframe: {tf}"}), 400
    try:
        max_zones = max(1, min(int(params.get("max_zones", 50)), 200))
    except (ValueError, TypeError):
        max_zones = 50

    try:
        data = _get_structure(symbol, tf)
    except Exception as e:
        logging.exception("Structure failed for %s %s", symbol, tf)
        return jsonify({"error": str(e)}), 500

    return jsonify(serialize_structure(data, tf, max_zones))


@app.route("/api/latest_date")
def api_latest_date():
    symbol = request.args.get("symbol")
    tf = request.args.get("tf")
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if not tf:
        return jsonify({"error": "tf is required"}), 400
    known_symbols = _get_symbols()
    if symbol not in known_symbols:
        return jsonify({"error": f"Unknown symbol: {symbol}"}), 400
    if tf not in BASE_TF_OPTIONS:
        return jsonify({"error": f"Invalid timeframe: {tf}"}), 400
    # Try warehouse first (fresher), fall back to raw
    ts = None
    if _warehouse_loader is not None:
        try:
            wh_df = _warehouse_loader.load(symbol, tf)
            if not wh_df.empty:
                ts = wh_df.index[-1]
        except Exception:
            pass
    if ts is None:
        ts = storage.get_latest_timestamp(symbol, tf)
    if ts is None:
        return jsonify({"error": f"No data for {symbol} {tf}"}), 404
    return jsonify({"date": ts.strftime("%Y-%m-%d")})


@app.route("/api/clear_cache", methods=["POST"])
def api_clear_cache():
    """Clear the memoize cache so fresh data is loaded on next request."""
    cache.clear()
    return jsonify({"status": "ok"})


@app.route("/api/screenshot", methods=["POST"])
@_limit("5 per minute")
def api_screenshot():
    """Save a chart screenshot PNG. Body: { image: 'data:image/png;base64,...' }"""
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"error": "No image data"}), 400

    # Strip data URL prefix
    img_data = data["image"]
    if "," in img_data:
        img_data = img_data.split(",", 1)[1]

    # 10 MB size limit on base64 data (~7.5 MB decoded)
    MAX_SCREENSHOT_B64 = 10 * 1024 * 1024
    if len(img_data) > MAX_SCREENSHOT_B64:
        return jsonify({"error": "Screenshot too large (max 10 MB)"}), 413

    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize symbol/tf to prevent path traversal
    symbol = re.sub(r"[^A-Za-z0-9_\-]", "", data.get("symbol", "UNKNOWN"))
    tf = re.sub(r"[^A-Za-z0-9_\-]", "", data.get("tf", ""))
    filename = f"{ts}_{symbol}_{tf}.png"
    filepath = SCREENSHOTS_DIR / filename

    try:
        img_bytes = base64.b64decode(img_data)
    except Exception:
        return jsonify({"error": "Invalid base64 image data"}), 400
    # Validate PNG magic bytes
    if not img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return jsonify({"error": "Only PNG images are accepted"}), 400
    filepath.write_bytes(img_bytes)
    log.info(f"Screenshot saved: {filepath}")
    return jsonify({"path": str(filepath), "filename": filename})


# ── Entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Starting Lightweight Charts viewer on http://127.0.0.1:8060")
    app.run(host="127.0.0.1", port=8060, debug=False)
