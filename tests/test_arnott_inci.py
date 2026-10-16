"""Tests for Arnott-Inci optimal price + cruising DWL."""
from __future__ import annotations

import math

from phillyparking.pricing.arnott_inci import (
    cruising_dwl,
    demand_function,
    optimal_price_arnott_inci,
)


def test_optimal_price_inverts_the_demand_law():
    p = optimal_price_arnott_inci(
        base_demand=10, base_price=2, capacity=10, elasticity=-0.5, target_vacancy=0.15
    )
    assert math.isclose(demand_function(10, 2, -0.5)(p), 8.5, abs_tol=1e-9)
    # Exponential form at p_ref = 2: p = 2 + 2 ln(0.85) / -0.5
    assert math.isclose(p, 2 + 2 * math.log(0.85) / -0.5, abs_tol=1e-9)
    assert math.isclose(p, 2.6500, abs_tol=1e-3)
    assert math.isclose(optimal_price_arnott_inci(10, 2, 10, -0.5, 0.15, form="constant_elasticity"),
                        2 * (8.5 / 10) ** (1 / -0.5), abs_tol=1e-9)


def test_demand_function_matches_anchor_and_takes_a_reference_price():
    D = demand_function(10, 2, -0.5)
    assert math.isclose(D(2), 10, abs_tol=1e-9)
    # With the elasticity anchored at $4, the same $2 -> $3 move is less elastic.
    assert demand_function(10, 2, -0.5, reference_price=4.0)(3) > D(3)


def test_cruising_dwl():
    dwl = cruising_dwl(demand=12, capacity=10, target_vacancy=0.15,
                       avg_cruising_minutes=5.0, value_of_time_usd_per_hr=20.0)
    assert math.isclose(dwl, 3.5 * (5 / 60) * 20, abs_tol=1e-9)
    assert math.isclose(dwl, 5.8333, abs_tol=1e-3)


def test_cruising_dwl_zero_when_below_capacity():
    dwl = cruising_dwl(demand=5, capacity=10)
    assert dwl == 0.0
