"""Unit tests for GWD → chainage pre-filter (ILI process-feature-map)."""

from backend.pipeline.feature_map_builder import (
    GWD_CENTER_ADJACENT_GWDS,
    compute_chainage_bounds_for_gwd_filter,
)


def test_gwd_center_adjacent_constant_is_two():
    assert GWD_CENTER_ADJACENT_GWDS == 2


def test_center_gwd_full_five_joint_window_when_possible():
    pairs = [(10, 100.0), (11, 200.0), (12, 300.0), (13, 400.0), (14, 500.0)]
    lo, hi = compute_chainage_bounds_for_gwd_filter(pairs, None, None, 12)
    assert lo == 100.0
    assert hi == 500.0


def test_center_gwd_clamps_at_line_start():
    pairs = [(1, 10.0), (2, 20.0), (3, 30.0)]
    lo, hi = compute_chainage_bounds_for_gwd_filter(pairs, None, None, 1)
    assert lo == 10.0
    assert hi == 30.0


def test_center_gwd_unknown_returns_none_bounds():
    pairs = [(1, 10.0), (2, 20.0)]
    lo, hi = compute_chainage_bounds_for_gwd_filter(pairs, None, None, 99)
    assert lo is None
    assert hi is None


def test_gwd_range_inclusive_chainages():
    pairs = [(5, 50.0), (6, 60.0), (7, 70.0)]
    lo, hi = compute_chainage_bounds_for_gwd_filter(pairs, 5, 7, None)
    assert lo == 50.0
    assert hi == 70.0
