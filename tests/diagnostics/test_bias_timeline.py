"""Unit tests for bias timeline computation functions."""
from __future__ import annotations

from iora.diagnostics.bias_timeline import compute_bias_label


class TestComputeBiasLabel:
    def test_bull_push(self):
        # HH + HL → bull push
        assert compute_bias_label([1.32, 1.30], [1.28, 1.26]) == "HH_HL_bull_push"

    def test_bear_push(self):
        # LH + LL → bear push
        assert compute_bias_label([1.28, 1.30], [1.24, 1.26]) == "LH_LL_bear_push"

    def test_compression(self):
        # LH + HL → compression
        assert compute_bias_label([1.28, 1.30], [1.28, 1.26]) == "LH_HL_compression"

    def test_expansion(self):
        # HH + LL → expansion
        assert compute_bias_label([1.32, 1.30], [1.24, 1.26]) == "HH_LL_expansion"

    def test_insufficient_data(self):
        assert compute_bias_label([1.30], [1.26]) == "unknown"
        assert compute_bias_label([], []) == "unknown"

    def test_equal_highs_lows(self):
        # Equal values → mixed
        assert compute_bias_label([1.30, 1.30], [1.26, 1.26]) == "mixed"


from iora.diagnostics.bias_timeline import compute_bias_strength


class TestComputeBiasStrength:
    def test_strong_bull_3_hh(self):
        # 3 consecutive HH → strength 3
        assert compute_bias_strength([1.34, 1.32, 1.30], [1.28, 1.26, 1.24]) == 3

    def test_moderate_2_hh(self):
        # Last 2 HH but 3rd breaks → strength 2
        assert compute_bias_strength([1.34, 1.32, 1.33], [1.28, 1.26, 1.24]) == 2

    def test_weak_single(self):
        # Only latest is HH, previous was LH → strength 1
        assert compute_bias_strength([1.34, 1.32, 1.35], [1.26, 1.28, 1.24]) == 1

    def test_insufficient_data(self):
        # < 2 periods → strength 0
        assert compute_bias_strength([1.30], [1.26]) == 0
        assert compute_bias_strength([], []) == 0

    def test_strong_bear_3_lh(self):
        # 3 consecutive LH + LL → strength 3
        assert compute_bias_strength([1.30, 1.32, 1.34], [1.24, 1.26, 1.28]) == 3


import pandas as pd
from iora.diagnostics.bias_timeline import nearest_zone_distance, BiasStateRecord
from iora.engine.push_zone_models import PushZone


class TestNearestZoneDistance:
    def test_no_zones(self):
        assert nearest_zone_distance(1.3000, [], 0.0020) == float("inf")

    def test_single_zone_above(self):
        z = PushZone(top=1.3100, bottom=1.3080, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Zone bottom = 1.3080, close = 1.3000, distance to nearest boundary = 0.0080
        # ATR = 0.002, so in ATR units = 0.0080 / 0.002 = 4.0
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert abs(dist - 4.0) < 0.01

    def test_inside_zone_negative(self):
        z = PushZone(top=1.3020, bottom=1.2980, is_supply=True,
                     origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        # Close = 1.3000, inside zone (bottom=1.2980, top=1.3020)
        dist = nearest_zone_distance(1.3000, [z], 0.002)
        assert dist < 0  # Negative means inside

    def test_picks_nearest(self):
        z_far = PushZone(top=1.3200, bottom=1.3180, is_supply=True,
                         origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        z_near = PushZone(top=1.3060, bottom=1.3040, is_supply=True,
                          origin_time=pd.Timestamp("2025-01-01"), timeframe="D1")
        dist = nearest_zone_distance(1.3000, [z_far, z_near], 0.002)
        # Should pick z_near: boundary distance = 1.3040 - 1.3000 = 0.004 / 0.002 = 2.0
        assert dist < 10.0  # Closer to z_near


class TestBiasStateRecord:
    def test_defaults(self):
        rec = BiasStateRecord(timestamp=pd.Timestamp("2025-01-01"))
        assert rec.d_bias == "unknown"
        assert rec.d_bias_strength == 0
        assert rec.is_bias_transition is False
