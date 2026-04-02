from iora.diagnostics.period_pattern import compute_period_pattern


def test_bull_push_pattern():
    """HH + HL = bull push."""
    assert compute_period_pattern(
        prev_highs=[1.3100, 1.3000],  # HH
        prev_lows=[1.2900, 1.2850],   # HL
    ) == "HH_HL"


def test_bear_push_pattern():
    """LH + LL = bear push."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3100],  # LH
        prev_lows=[1.2800, 1.2900],   # LL
    ) == "LH_LL"


def test_compression_pattern():
    """LH + HL = compression."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3100],  # LH
        prev_lows=[1.2900, 1.2850],   # HL
    ) == "LH_HL"


def test_expansion_pattern():
    """HH + LL = expansion."""
    assert compute_period_pattern(
        prev_highs=[1.3100, 1.3000],  # HH
        prev_lows=[1.2800, 1.2900],   # LL
    ) == "HH_LL"


def test_insufficient_history():
    """Less than 2 periods returns 'unknown'."""
    assert compute_period_pattern(prev_highs=[1.3000], prev_lows=[1.2900]) == "unknown"
    assert compute_period_pattern(prev_highs=[], prev_lows=[]) == "unknown"


def test_equal_values():
    """Equal highs/lows returns 'mixed'."""
    assert compute_period_pattern(
        prev_highs=[1.3000, 1.3000],
        prev_lows=[1.2900, 1.2900],
    ) == "mixed"
