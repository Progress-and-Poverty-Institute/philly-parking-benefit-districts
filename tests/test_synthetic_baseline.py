"""Tests for the synthetic baseline occupancy predictor."""
from __future__ import annotations

import pandas as pd

from phillyparking.demand.synthetic_baseline import (
    HOURS_OF_WEEK,
    baseline_occupancy,
    expand_panel,
    hour_of_week,
)
from tests.fixtures import make_synthetic_segments


def test_baseline_shape_and_bounds():
    segs = make_synthetic_segments(n=20, seed=0)
    panel = baseline_occupancy(segs, seed=42)
    assert len(panel) == 20 * HOURS_OF_WEEK
    assert set(panel.columns) == {"segment_id", "hour_of_week", "occupancy", "occupancy_sd"}
    assert panel["occupancy"].between(0.0, 1.0).all()


def test_baseline_high_jobs_peaks_higher_than_low_jobs():
    segs = make_synthetic_segments(n=40, seed=1)
    panel = baseline_occupancy(segs, seed=42)
    j = segs.set_index("segment_id")["jobs_within_200m"]
    high_id = j.idxmax()
    low_id = j.idxmin()
    high_peak = panel.loc[panel["segment_id"] == high_id, "occupancy"].max()
    low_peak = panel.loc[panel["segment_id"] == low_id, "occupancy"].max()
    assert high_peak > low_peak


def test_baseline_deterministic_given_seed():
    segs = make_synthetic_segments(n=10, seed=2)
    p1 = baseline_occupancy(segs, seed=42)
    p2 = baseline_occupancy(segs, seed=42)
    pd.testing.assert_frame_equal(p1, p2)


def test_expand_panel_length():
    segs = make_synthetic_segments(n=5, seed=3)
    panel = baseline_occupancy(segs, seed=42)
    expanded = expand_panel(segs, panel, n_weeks=2, add_noise=True, noise_sigma=0.05, seed=42)
    assert len(expanded) == 5 * HOURS_OF_WEEK * 2
    assert expanded["occupancy"].between(0.0, 1.0).all()


def test_hour_of_week_basic():
    ts = pd.Series(pd.to_datetime(["2025-01-06 00:00", "2025-01-06 13:00", "2025-01-12 23:00"]))
    how = hour_of_week(ts)
    assert how.tolist() == [0, 13, 6 * 24 + 23]
