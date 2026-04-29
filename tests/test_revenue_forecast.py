"""Tests for revenue forecasting."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from phillyparking.revenue.forecast import _project_occupancy, annual_revenue


def test_annual_revenue_trivial():
    segments = pd.DataFrame({
        "segment_id": ["s0"],
        "capacity": [10],
        "zone_id": ["z1"],
    })
    panel = pd.DataFrame({
        "segment_id": ["s0"] * 10,
        "hour_of_week": list(range(10)),
        "occupancy": [0.6] * 10,
    })
    prices = pd.DataFrame({"zone_id": ["z1"], "price_usd_per_hr": [2.0]})
    result = annual_revenue(segments, panel, prices, priced_hours_per_year=4380)
    assert len(result) == 1
    rev = float(result["annual_revenue_usd"].iloc[0])
    assert math.isclose(rev, 0.6 * 10 * 2 * 4380, rel_tol=1e-9)
    assert math.isclose(rev, 52_560, rel_tol=1e-9)


def test_scenario_projection_constant_elasticity():
    # baseline: occ=0.6, p=2 → new p=3, eps=-0.5 → new occ = 0.6*1.5^-0.5
    occ_old = np.array([0.6] * 100)
    p_old = np.array([2.0] * 100)
    p_new = np.array([3.0] * 100)
    occ_new = _project_occupancy(occ_old, p_old, p_new, -0.5)
    expected_occ = 0.6 * (1.5) ** -0.5
    assert math.isclose(float(occ_new.mean()), expected_occ, rel_tol=1e-6)
    expected_rev = expected_occ * 10 * 3 * 4380
    actual_rev = float(occ_new.mean()) * 10 * 3 * 4380
    assert math.isclose(actual_rev, expected_rev, rel_tol=1e-6)
    assert math.isclose(actual_rev, 64_386, rel_tol=0.01)
