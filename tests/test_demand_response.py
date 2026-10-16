"""The demand law (audit finding 14): one form for every price response, with an interior
revenue peak under the default form, and the consumer-surplus integral of the same law."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking._config import load_config
from phillyparking.demand import response as dr

FORMS = dr.FORMS
P_REF, E = 4.0, -0.4


def test_config_names_a_known_form_and_the_default_is_exponential():
    assert dr.load_demand_form() in FORMS
    assert load_config("elasticity_priors")["demand_form"] == "exponential"


@pytest.mark.parametrize("form", FORMS)
def test_demand_is_one_at_the_reference_and_falls_with_price(form):
    p = np.array([2.0, 4.0, 6.0, 8.0])
    q = dr.demand_level(p, E, P_REF, form)
    assert q[1] == pytest.approx(1.0)
    assert (np.diff(q) < 0).all()


@pytest.mark.parametrize("form", FORMS)
def test_elasticity_at_the_reference_is_the_prior(form):
    assert dr.elasticity_at(P_REF, E, P_REF, form) == pytest.approx(E)
    # Elasticity from the definition d ln q / d ln p, by finite differences.
    for p in (3.0, 5.0, 7.0):
        h = 1e-5
        num = (np.log(dr.demand_level(p + h, E, P_REF, form)) - np.log(dr.demand_level(p - h, E, P_REF, form))) / (2 * h) * p
        assert dr.elasticity_at(p, E, P_REF, form) == pytest.approx(num, rel=1e-5)


def test_elasticity_rises_with_price_except_under_constant_elasticity():
    p = np.array([3.0, 4.0, 6.0, 9.0])
    assert (np.diff(dr.elasticity_at(p, E, P_REF, "exponential")) < 0).all()
    assert (np.diff(dr.elasticity_at(p, E, P_REF, "linear")) < 0).all()
    assert (np.diff(dr.elasticity_at(p, E, P_REF, "constant_elasticity")) == 0).all()
    assert dr.elasticity_at(8.0, E, P_REF, "exponential") == pytest.approx(2 * E)


@pytest.mark.parametrize("form", FORMS)
def test_demand_factor_is_path_independent(form):
    direct = dr.demand_factor(7.0, 4.0, E, P_REF, form)
    via = dr.demand_factor(5.5, 4.0, E, P_REF, form) * dr.demand_factor(7.0, 5.5, E, P_REF, form)
    assert direct == pytest.approx(via)
    assert dr.demand_factor(4.0, 4.0, E, P_REF, form) == pytest.approx(1.0)


@pytest.mark.parametrize("form", FORMS)
def test_inverse_price_recovers_the_demand_ratio(form):
    for ratio in (0.7, 0.9, 1.2):
        p = dr.price_for_demand_ratio(ratio, 4.5, E, P_REF, form)
        assert dr.demand_factor(p, 4.5, E, P_REF, form) == pytest.approx(ratio, rel=1e-9)


def test_revenue_peaks_at_the_stated_price_under_the_default_form_and_never_under_constant():
    grid = np.linspace(1.0, 20.0, 1901)
    for form in ("exponential", "linear"):
        rev = grid * dr.demand_level(grid, E, P_REF, form)
        p_star = dr.revenue_maximising_price(E, P_REF, form)
        assert grid[rev.argmax()] == pytest.approx(p_star, abs=0.011)
    assert dr.revenue_maximising_price(E, P_REF, "exponential") == pytest.approx(10.0)
    assert dr.revenue_maximising_price(E, P_REF, "linear") == pytest.approx(7.0)
    rev = grid * dr.demand_level(grid, E, P_REF, "constant_elasticity")
    assert (np.diff(rev) > 0).all() and dr.revenue_maximising_price(E, P_REF, "constant_elasticity") is None


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("elasticity", [-0.2, -0.7, -1.0, -1.5])
def test_cs_change_is_the_integral_of_the_demand_law(form, elasticity):
    q_ref = 8.0
    for p1 in (2.0, 5.0, 11.0):
        grid = np.linspace(P_REF, p1, 40001)
        q = q_ref * dr.demand_level(grid, elasticity, P_REF, form)
        integral = -np.trapezoid(q, grid)
        got = dr.cs_change(q_ref, P_REF, p1, elasticity, form)
        assert float(got) == pytest.approx(integral, rel=1e-6, abs=1e-9)
    assert float(dr.cs_change(q_ref, P_REF, P_REF, elasticity, form)) == 0.0


def test_linear_demand_stops_at_the_choke_price():
    choke = P_REF * (1 - 1 / E)
    assert dr.demand_level(choke + 1.0, E, P_REF, "linear") == 0.0
    # No surplus is lost beyond the choke: the integral is flat there.
    assert dr.cs_change(5.0, P_REF, choke + 3.0, E, "linear") == pytest.approx(dr.cs_change(5.0, P_REF, choke, E, "linear"))
    # Demand comes back when the price falls from above the choke.
    assert dr.demand_factor(P_REF, choke + 3.0, E, P_REF, "linear") == pytest.approx(1.0)


def test_unknown_form_is_refused():
    with pytest.raises(ValueError):
        dr.demand_level(4.0, E, P_REF, "quadratic")
