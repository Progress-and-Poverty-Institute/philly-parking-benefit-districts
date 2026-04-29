"""Tests for demand feature engineering (demand/features.py)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from phillyparking.demand.features import _zscore, segment_features, time_features
from tests.fixtures import make_synthetic_segments


# ---------------------------------------------------------------------------
# _zscore
# ---------------------------------------------------------------------------

def test_zscore_zero_mean_unit_std():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = _zscore(s)
    assert math.isclose(float(out.mean()), 0.0, abs_tol=1e-9)
    assert math.isclose(float(out.std()), 1.0, abs_tol=1e-6)


def test_zscore_constant_series_returns_zeros():
    s = pd.Series([7.0, 7.0, 7.0])
    out = _zscore(s)
    assert (out == 0.0).all()


def test_zscore_preserves_length():
    s = pd.Series(range(10), dtype=float)
    assert len(_zscore(s)) == len(s)


# ---------------------------------------------------------------------------
# segment_features
# ---------------------------------------------------------------------------

EXPECTED_SEG_COLS = {
    "log_jobs_within_200m", "log_pois_count", "log_pop_density",
    "log_transit_freq", "median_hh_income_z",
    "is_ccc", "is_cca", "is_ucity", "is_residential",
}


def test_segment_features_columns():
    segs = make_synthetic_segments(n=10, seed=0)
    out = segment_features(segs)
    assert EXPECTED_SEG_COLS.issubset(set(out.columns))


def test_segment_features_no_nan():
    segs = make_synthetic_segments(n=20, seed=1)
    out = segment_features(segs)
    assert not out.isna().any().any()


def test_segment_features_log_columns_non_negative():
    segs = make_synthetic_segments(n=20, seed=2)
    out = segment_features(segs)
    for col in ("log_jobs_within_200m", "log_pois_count", "log_pop_density", "log_transit_freq"):
        assert (out[col] >= 0).all(), f"{col} contains negative values"


def test_segment_features_index_is_segment_id():
    segs = make_synthetic_segments(n=8, seed=0)
    out = segment_features(segs)
    assert out.index.name == "segment_id"
    assert list(out.index) == list(segs["segment_id"])


def test_segment_features_ccc_flag_matches_zone():
    segs = make_synthetic_segments(n=40, seed=3)
    out = segment_features(segs)
    for _, row in segs.iterrows():
        expected = 1 if row["zone_id"] == "ccc" else 0
        assert out.loc[row["segment_id"], "is_ccc"] == expected


def test_segment_features_residential_flag():
    segs = make_synthetic_segments(n=40, seed=4)
    out = segment_features(segs)
    for _, row in segs.iterrows():
        expected = 1 if row["zone_id"] in ("south_philly", "fishtown") else 0
        assert out.loc[row["segment_id"], "is_residential"] == expected


# ---------------------------------------------------------------------------
# time_features
# ---------------------------------------------------------------------------

def _how_panel(how_values):
    return pd.DataFrame({
        "segment_id": "s0",
        "hour_of_week": list(how_values),
        "occupancy": 0.5,
    })


def test_time_features_output_columns():
    out = time_features(_how_panel(range(168)))
    for col in ("hour", "dow", "is_weekday", "is_peak", "is_evening", "hour_sin", "hour_cos"):
        assert col in out.columns, f"Missing column: {col}"


def test_time_features_sin_cos_unit_circle():
    out = time_features(_how_panel(range(168)))
    sq_sum = out["hour_sin"] ** 2 + out["hour_cos"] ** 2
    assert (sq_sum - 1.0).abs().max() < 1e-10


def test_time_features_peak_weekday_noon():
    # day=0 (Mon), hour=12 → is_peak=1, is_weekday=1
    out = time_features(_how_panel([12]))
    assert out["is_peak"].iloc[0] == 1
    assert out["is_weekday"].iloc[0] == 1


def test_time_features_no_peak_on_weekend():
    # day=5 (Sat), hour=12 → is_peak=0 even though it's noon
    out = time_features(_how_panel([5 * 24 + 12]))
    assert out["is_peak"].iloc[0] == 0
    assert out["is_weekday"].iloc[0] == 0


def test_time_features_no_peak_outside_window():
    # Weekday 10:00 is just before the 11-14 peak window
    out = time_features(_how_panel([10]))
    assert out["is_peak"].iloc[0] == 0


def test_time_features_evening_flag():
    # Weekday 19:00 (hour_of_week=19) → is_evening=1
    out = time_features(_how_panel([19]))
    assert out["is_evening"].iloc[0] == 1


def test_time_features_from_timestamp():
    # Monday 2024-01-15 at noon → weekday, peak hour
    ts = pd.date_range("2024-01-15 12:00", periods=3, freq="h")
    panel = pd.DataFrame({"segment_id": "s0", "timestamp": ts, "occupancy": 0.5})
    out = time_features(panel)
    assert "hour" in out.columns
    assert out["hour"].iloc[0] == 12
    assert out["is_weekday"].iloc[0] == 1
    assert out["is_peak"].iloc[0] == 1


def test_time_features_preserves_row_count():
    panel = _how_panel(range(168))
    out = time_features(panel)
    assert len(out) == 168
