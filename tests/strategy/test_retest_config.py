"""Tests for RetestConfig dataclass."""
from iora.strategy.retest_config import RetestConfig, SESSION_WINDOWS


def test_default_config():
    cfg = RetestConfig()
    assert cfg.tf_pair == "H1@H4"
    assert cfg.touch_type == "wick_touch"
    assert cfg.bias_filter == "any"
    assert cfg.zone_role_filter == "any"
    assert cfg.age_filter == "any"
    assert cfg.test_count_filter == "any"
    assert cfg.cascade_filter == "none"
    assert cfg.cascade_lookback == 20
    assert cfg.sl_mode == "zone"
    assert cfg.tp_mode == "fixed_rr"
    assert cfg.fixed_rr == 2.0
    assert cfg.direction == "both"
    assert cfg.session_filter == "any"
    assert cfg.min_bias_strength == 0
    assert cfg.max_replacement_count == 999
    assert cfg.touch_policy == "until_broken"


def test_config_entry_and_zone_tf():
    cfg = RetestConfig(tf_pair="M5@H1")
    assert cfg.entry_tf == "M5"
    assert cfg.zone_tf == "H1"


def test_config_entry_and_zone_tf_h1_h4():
    cfg = RetestConfig(tf_pair="H1@H4")
    assert cfg.entry_tf == "H1"
    assert cfg.zone_tf == "H4"


def test_session_windows():
    assert "london" in SESSION_WINDOWS
    assert "newyork" in SESSION_WINDOWS
    assert "london_ny_overlap" in SESSION_WINDOWS
    assert "asian" in SESSION_WINDOWS
    # London = 07:00-16:00 UTC
    assert SESSION_WINDOWS["london"] == (7, 16)
    # NY = 12:00-21:00 UTC
    assert SESSION_WINDOWS["newyork"] == (12, 21)


def test_config_htf_pairs():
    """HTF pairs are all pairs with context TF higher than this config's zone TF."""
    cfg = RetestConfig(tf_pair="M5@M15")
    htf = cfg.htf_pairs
    # M15 context → HTF pairs have context above M15: H1, H4, D1
    assert "M15@H1" in htf
    assert "M15@H4" in htf
    assert "H1@H4" in htf
    assert "H1@D1" in htf
    assert "M5@M15" not in htf  # Not higher
    assert "M5@H1" in htf       # M5 entry but H1 context > M15 — valid HTF signal


def test_config_htf_pairs_h1_h4():
    cfg = RetestConfig(tf_pair="H1@H4")
    htf = cfg.htf_pairs
    # H4 context → only D1 is higher
    assert "H1@D1" in htf
    assert len(htf) == 1


def test_config_htf_pairs_h1_d1():
    cfg = RetestConfig(tf_pair="H1@D1")
    htf = cfg.htf_pairs
    # D1 is highest context → no HTF pairs
    assert len(htf) == 0
