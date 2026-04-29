"""Tests for MLOccupancyModel (demand/ml_occupancy.py)."""
from __future__ import annotations

import math

import numpy as np
import pytest

xgboost = pytest.importorskip("xgboost", reason="xgboost not installed")

from phillyparking.demand.ml_occupancy import MLOccupancyModel, _build_X, _logit, _sigmoid
from tests.fixtures import make_synthetic_panel, make_synthetic_segments


# ---------------------------------------------------------------------------
# _logit / _sigmoid
# ---------------------------------------------------------------------------

def test_logit_sigmoid_inverse():
    p = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
    np.testing.assert_allclose(_sigmoid(_logit(p)), p, atol=1e-6)


def test_logit_clips_extremes_no_inf():
    out = _logit(np.array([0.0, 1.0]))
    assert np.all(np.isfinite(out))


def test_sigmoid_at_zero_is_half():
    assert math.isclose(float(_sigmoid(np.array([0.0]))[0]), 0.5, abs_tol=1e-9)


def test_sigmoid_output_bounded():
    x = np.array([-1000.0, 0.0, 1000.0])
    out = _sigmoid(x)
    assert (out >= 0).all() and (out <= 1).all()


# ---------------------------------------------------------------------------
# _build_X
# ---------------------------------------------------------------------------

def test_build_X_expected_columns():
    segs = make_synthetic_segments(n=10, seed=0)
    panel = make_synthetic_panel(segs, seed=0)
    X = _build_X(panel, segs)
    expected_time = {"hour", "dow", "is_weekday", "is_peak", "is_evening", "hour_sin", "hour_cos"}
    assert expected_time.issubset(set(X.columns))


def test_build_X_row_count_matches_panel():
    segs = make_synthetic_segments(n=10, seed=1)
    panel = make_synthetic_panel(segs, seed=1)
    X = _build_X(panel, segs)
    assert len(X) == len(panel)


def test_build_X_no_nan():
    segs = make_synthetic_segments(n=10, seed=2)
    panel = make_synthetic_panel(segs, seed=2)
    X = _build_X(panel, segs)
    assert not X.isna().any().any()


# ---------------------------------------------------------------------------
# MLOccupancyModel — fit / predict / save / load
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def trained():
    segs = make_synthetic_segments(n=20, seed=42)
    panel = make_synthetic_panel(segs, seed=42)
    model = MLOccupancyModel(n_estimators=10, max_depth=3, seed=42)
    model.fit(panel, segs)
    return model, segs, panel


def test_fit_populates_feature_cols(trained):
    model, _, _ = trained
    assert model.feature_cols is not None
    assert len(model.feature_cols) > 0


def test_predict_row_count(trained):
    model, segs, panel = trained
    result = model.predict(panel, segs)
    assert len(result) == len(panel)


def test_predict_has_occupancy_column(trained):
    model, segs, panel = trained
    result = model.predict(panel, segs)
    assert "occupancy" in result.columns


def test_predict_occupancy_in_unit_interval(trained):
    model, segs, panel = trained
    result = model.predict(panel, segs)
    assert (result["occupancy"] >= 0).all()
    assert (result["occupancy"] <= 1).all()


def test_save_load_roundtrip(trained, tmp_path):
    model, segs, panel = trained
    path = tmp_path / "model.pkl"
    saved_path = model.save(path)
    assert saved_path.exists()

    loaded = MLOccupancyModel.load(path)
    assert loaded.feature_cols == model.feature_cols
    assert loaded.n_estimators == model.n_estimators

    pred_orig = model.predict(panel, segs)["occupancy"].to_numpy()
    pred_loaded = loaded.predict(panel, segs)["occupancy"].to_numpy()
    np.testing.assert_allclose(pred_orig, pred_loaded, atol=1e-9)


def test_predict_is_deterministic(trained):
    model, segs, panel = trained
    pred1 = model.predict(panel, segs)["occupancy"].to_numpy()
    pred2 = model.predict(panel, segs)["occupancy"].to_numpy()
    np.testing.assert_array_equal(pred1, pred2)
