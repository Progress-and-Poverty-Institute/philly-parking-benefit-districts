"""Tests for incidence module."""
from __future__ import annotations

import numpy as np
import pandas as pd

from phillyparking.welfare.incidence import payment_burden_by_decile, gini, simple_incidence_summary


def test_payment_burden_uniform():
    trips = pd.DataFrame({
        "trip_id": [f"t{i}" for i in range(100)],
        "decile": np.repeat(np.arange(1, 11), 10),
        "parking_cost_usd": [5.0] * 100,
        "n_trips_per_year": [1] * 100,
    })
    out = payment_burden_by_decile(trips)
    assert len(out) == 10
    assert (out["total_paid_usd"] == 50.0).all()
    assert np.allclose(out["share_of_revenue"], 0.10)


def test_simple_incidence_summary_shares_sum_to_one():
    rng = np.random.default_rng(42)
    n = 500
    df = pd.DataFrame({
        "household_id": range(n),
        "income_decile": rng.integers(1, 11, size=n),
        "parking_spend_usd": rng.gamma(shape=2.0, scale=120.0, size=n),
    })
    out = simple_incidence_summary(df)
    assert set(out.columns) >= {"income_decile", "n_households", "mean_parking_spend_usd",
                                 "total_parking_spend_usd", "share_of_burden"}
    assert abs(out["share_of_burden"].sum() - 1.0) < 1e-9


def test_simple_incidence_summary_equal_spend():
    df = pd.DataFrame({
        "household_id": range(20),
        "income_decile": np.repeat(np.arange(1, 11), 2),
        "parking_spend_usd": [100.0] * 20,
    })
    out = simple_incidence_summary(df)
    assert len(out) == 10
    assert np.allclose(out["share_of_burden"], 0.10)


def test_gini_equal():
    g = gini(np.array([1.0, 1.0, 1.0, 1.0]))
    assert abs(g) < 1e-9


def test_gini_concentrated():
    g = gini(np.array([0.0, 0.0, 0.0, 1.0]))
    assert abs(g - 0.75) < 0.05
