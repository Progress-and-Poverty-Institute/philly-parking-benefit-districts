"""The Chatman-Manville sweep's welfare scorer: search cost shape and level, consumer surplus."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking._config import load_config
from phillyparking.welfare.targeting_welfare import (
    cs_change_usd, expected_search_minutes, load_search_cost_config, search_cost_usd,
)


def test_search_minutes_equal_the_configured_level_at_the_reference_block_hour():
    cfg = load_search_cost_config()
    ref = expected_search_minutes(np.array([cfg.reference_occupancy]), np.array([cfg.reference_capacity]), cfg)
    assert ref[0] == pytest.approx(cfg.minutes_at_reference)
    twice = load_search_cost_config(2 * cfg.minutes_at_reference)
    assert expected_search_minutes(np.array([0.9]), np.array([8.0]), twice)[0] == pytest.approx(
        2 * expected_search_minutes(np.array([0.9]), np.array([8.0]), cfg)[0])


def test_search_minutes_increase_and_are_convex_in_occupancy_and_fall_with_block_size():
    cfg = load_search_cost_config()
    o = np.linspace(0.5, 0.99, 50)
    m = expected_search_minutes(o, np.full_like(o, 10.0), cfg)
    assert (np.diff(m) > 0).all() and (np.diff(m, 2) > 0).all()
    small = expected_search_minutes(np.array([0.9]), np.array([4.0]), cfg)[0]
    big = expected_search_minutes(np.array([0.9]), np.array([16.0]), cfg)[0]
    assert small > big  # a small block is full more often at the same mean occupancy
    # A full block costs the capped search, not an infinite one.
    full = expected_search_minutes(np.array([1.0]), np.array([10.0]), cfg)[0]
    assert np.isfinite(full) and full == expected_search_minutes(np.array([cfg.occupancy_cap]), np.array([10.0]), cfg)[0]


def test_search_cost_is_arrivals_times_time_times_value_of_time():
    cfg = load_search_cost_config()
    occ, cap = np.array([0.95]), np.array([10.0])
    arrivals = 0.95 * 10.0 / cfg.mean_duration_hr
    expected = arrivals * (cfg.minutes_at_reference / 60.0) * cfg.value_of_time_usd_per_hr
    assert search_cost_usd(occ, cap, cfg)[0] == pytest.approx(expected)
    assert search_cost_usd(np.array([0.0]), cap, cfg)[0] == 0.0
    assert cfg.value_of_time_usd_per_hr == load_config("pricing_rules")["arnott_inci"]["value_of_time_usd_per_hr"]


@pytest.mark.parametrize("elasticity", [-0.2, -0.7, -1.0, -1.5])
def test_cs_change_matches_the_integral_of_demand(elasticity):
    from phillyparking.demand.response import demand_level
    d0, p0, cap = 0.8, 2.0, 10.0
    for p1 in (1.0, 2.5, 4.0):
        grid = np.linspace(p0, p1, 20001)
        q = d0 * cap * demand_level(grid, elasticity, p0)
        integral = -np.trapezoid(q, grid)
        got = cs_change_usd(np.array([d0]), np.array([p0]), np.array([p1]), elasticity, np.array([cap]))[0]
        assert got == pytest.approx(integral, rel=1e-6)
    assert cs_change_usd(np.array([d0]), np.array([p0]), np.array([p0]), elasticity, np.array([cap]))[0] == 0.0


def test_cs_change_uses_demand_not_capacity_clipped_occupancy():
    # Two blocks: one with demand 1.5x its capacity. Its surplus loss from a price rise counts
    # every car that wanted the block, not only the ones that fit.
    d0 = np.array([0.8, 1.5])
    got = cs_change_usd(d0, np.array([2.0, 2.0]), np.array([3.0, 3.0]), -0.4, np.array([10.0, 10.0]))
    assert got[1] == pytest.approx(got[0] * 1.5 / 0.8)
