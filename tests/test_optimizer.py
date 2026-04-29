"""Tests for the joint zone-pricing optimizer (pricing/optimizer.py)."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from phillyparking.pricing.optimizer import (
    JointPricingProblem,
    _broadcast,
    _fallback_independent,
    solve_pbd_pricing,
)


def _problem(**overrides) -> JointPricingProblem:
    defaults = dict(
        zones=["z1", "z2"],
        base_demand=np.array([8.0, 6.0]),
        base_price=np.array([2.0, 2.0]),
        capacity=np.array([10.0, 8.0]),
        elasticity=-0.5,
        target_vacancy=0.15,
        floor=0.50,
        ceiling=10.00,
    )
    defaults.update(overrides)
    return JointPricingProblem(**defaults)


# ---------------------------------------------------------------------------
# _broadcast
# ---------------------------------------------------------------------------

def test_broadcast_scalar_expands():
    out = _broadcast(3.0, 4)
    assert out.shape == (4,)
    assert np.all(out == 3.0)


def test_broadcast_array_passthrough():
    arr = np.array([1.0, 2.0, 3.0])
    out = _broadcast(arr, 3)
    np.testing.assert_array_equal(out, arr)


def test_broadcast_wrong_shape_raises():
    with pytest.raises(ValueError):
        _broadcast(np.array([1.0, 2.0]), 5)


# ---------------------------------------------------------------------------
# _fallback_independent — output schema & invariants
# ---------------------------------------------------------------------------

def test_fallback_output_schema():
    df = _fallback_independent(_problem())
    expected = {
        "zone_id", "optimal_price", "predicted_demand",
        "predicted_revenue", "predicted_occupancy", "binding_constraint",
    }
    assert set(df.columns) == expected
    assert list(df["zone_id"]) == ["z1", "z2"]


def test_fallback_occupancy_bounded():
    df = _fallback_independent(_problem())
    assert (df["predicted_occupancy"] >= 0).all()
    assert (df["predicted_occupancy"] <= 1).all()


def test_fallback_revenue_non_negative():
    df = _fallback_independent(_problem())
    assert (df["predicted_revenue"] >= 0).all()


def test_fallback_floor_binding():
    # floor above any reasonable optimum → every zone hits the floor
    df = _fallback_independent(_problem(floor=9.00, ceiling=10.00))
    assert (df["binding_constraint"] == "floor").all()
    assert (df["optimal_price"] == 9.00).all()


def test_fallback_ceiling_binding():
    # ceiling below any reasonable optimum → every zone hits the ceiling
    df = _fallback_independent(_problem(floor=0.50, ceiling=0.50))
    assert (df["binding_constraint"] == "ceiling").all()
    assert (df["optimal_price"] == 0.50).all()


def test_fallback_zone_ids_preserved():
    zones = ["alpha", "beta", "gamma"]
    prob = _problem(
        zones=zones,
        base_demand=np.array([8.0, 6.0, 5.0]),
        base_price=np.array([2.0, 2.0, 2.0]),
        capacity=np.array([10.0, 8.0, 7.0]),
    )
    df = _fallback_independent(prob)
    assert list(df["zone_id"]) == zones


# ---------------------------------------------------------------------------
# solve_pbd_pricing — fallback when cvxpy absent
# ---------------------------------------------------------------------------

def test_solve_falls_back_without_cvxpy(monkeypatch):
    monkeypatch.setitem(sys.modules, "cvxpy", None)
    df = solve_pbd_pricing(_problem())
    expected = {
        "zone_id", "optimal_price", "predicted_demand",
        "predicted_revenue", "predicted_occupancy", "binding_constraint",
    }
    assert set(df.columns) == expected
    assert len(df) == 2


def test_solve_returns_correct_row_count():
    prob = _problem()
    df = solve_pbd_pricing(prob)
    assert len(df) == len(prob.zones)


def test_solve_price_within_bounds():
    prob = _problem(floor=1.00, ceiling=8.00)
    df = solve_pbd_pricing(prob)
    assert (df["optimal_price"] >= 1.00 - 1e-6).all()
    assert (df["optimal_price"] <= 8.00 + 1e-6).all()


def test_solve_occupancy_bounded():
    df = solve_pbd_pricing(_problem())
    assert (df["predicted_occupancy"] >= 0).all()
    assert (df["predicted_occupancy"] <= 1).all()
