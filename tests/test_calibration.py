"""Tests for calibration module."""
from __future__ import annotations

import numpy as np

from phillyparking.validation.calibration import calibration_curve, calibration_slope


def test_perfect_calibration():
    rng = np.random.default_rng(0)
    y_true = rng.uniform(0, 1, size=200)
    y_pred = y_true.copy()
    assert abs(calibration_slope(y_true, y_pred) - 1.0) < 1e-9


def test_underconfident():
    rng = np.random.default_rng(0)
    y_true = rng.uniform(0, 1, size=200)
    y_pred = 0.5 * y_true
    assert abs(calibration_slope(y_true, y_pred) - 2.0) < 1e-9


def test_calibration_curve_bins():
    rng = np.random.default_rng(0)
    y_true = rng.uniform(0, 1, size=500)
    y_pred = y_true + rng.normal(0, 0.05, size=500)
    curve = calibration_curve(y_true, y_pred, n_bins=10)
    assert len(curve) == 10
    valid = curve.dropna()
    assert (valid["mean_pred"].diff().dropna() > 0).all()
