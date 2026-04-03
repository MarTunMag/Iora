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
