"""The Chatman-Manville sweep's welfare scorer: search cost shape, level and cap, consumer surplus."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking._config import load_config
from phillyparking.welfare.targeting_welfare import (
    cited_cruising_minutes, cs_change_usd, expected_search_minutes, load_search_cost_config,
    reference_minutes_per_full_block_minute, search_cost_usd,
)


def test_search_minutes_equal_the_configured_level_at_a_full_reference_block():
    cfg = load_search_cost_config()
    full = expected_search_minutes(np.array([1.0]), np.array([cfg.reference_capacity]), cfg)
    assert full[0] == pytest.approx(cfg.minutes_at_full_block)
    twice = load_search_cost_config(2 * cfg.minutes_at_full_block)
    assert expected_search_minutes(np.array([0.9]), np.array([8.0]), twice)[0] == pytest.approx(
        2 * expected_search_minutes(np.array([0.9]), np.array([8.0]), cfg)[0])


def test_cap_sets_how_much_more_a_full_block_costs_than_the_reference_block():
    """At every cap a full block costs the stated minutes; the cap decides the 95% block's cost,
    and `reference_minutes_per_full_block_minute` is exactly that conversion."""
    ref_occ, k = 0.95, np.array([10.0])
    for cap in (0.95, 0.99, 0.999):
        cfg = load_search_cost_config(occupancy_cap=cap)
        full = expected_search_minutes(np.array([1.0]), k, cfg)[0]
        at_ref = expected_search_minutes(np.array([ref_occ]), k, cfg)[0]
        assert full == pytest.approx(cfg.minutes_at_full_block)
        assert at_ref / full == pytest.approx(reference_minutes_per_full_block_minute(cfg))
    assert reference_minutes_per_full_block_minute(load_search_cost_config(occupancy_cap=0.95)) == pytest.approx(1.0)
    assert reference_minutes_per_full_block_minute(load_search_cost_config(occupancy_cap=0.999)) < 0.02
    with pytest.raises(ValueError):
        load_search_cost_config(occupancy_cap=1.5)


def test_level_is_inside_the_cited_cruising_range():
    """The config level is a per-arrival full-block figure set at the cited per-cruiser mean."""
    cfg, cited = load_search_cost_config(), cited_cruising_minutes()
    assert cited["low"] < cited["mean"] < cited["high"]
    assert cited["low"] <= cfg.minutes_at_full_block <= cited["high"]
    assert "cruise" in cited["source"]


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
    minutes = expected_search_minutes(occ, cap, cfg)[0]
    assert search_cost_usd(occ, cap, cfg)[0] == pytest.approx(arrivals * (minutes / 60.0) * cfg.value_of_time_usd_per_hr)
    full = search_cost_usd(np.array([1.0]), cap, cfg)[0]
    assert full == pytest.approx(10.0 / cfg.mean_duration_hr * (cfg.minutes_at_full_block / 60.0) * cfg.value_of_time_usd_per_hr)
    assert search_cost_usd(np.array([0.0]), cap, cfg)[0] == 0.0
    assert cfg.value_of_time_usd_per_hr == load_config("pricing_rules")["arnott_inci"]["value_of_time_usd_per_hr"]


@pytest.mark.parametrize("elasticity", [-0.2, -0.7, -1.0, -1.5])
def test_cs_change_matches_the_integral_of_served_demand(elasticity):
    """-int min(q(x), capacity) dx: the plain integral while demand fits, capacity x the price
    move where it does not (a deep cut at the more elastic values fills the block)."""
    from phillyparking.demand.response import demand_level
    d0, p0, cap = 0.8, 2.0, 10.0
    for p1 in (1.0, 2.5, 4.0):
        grid = np.linspace(p0, p1, 20001)
        q = np.minimum(d0 * cap * demand_level(grid, elasticity, p0), cap)
        integral = -np.trapezoid(q, grid)
        got = cs_change_usd(np.array([d0]), np.array([p0]), np.array([p1]), elasticity, np.array([cap]))[0]
        assert got == pytest.approx(integral, rel=1e-6)
    assert cs_change_usd(np.array([d0]), np.array([p0]), np.array([p0]), elasticity, np.array([cap]))[0] == 0.0


def test_cs_change_counts_only_the_cars_that_get_a_space():
    """Two blocks, one with demand 1.5x its capacity: a $0.50 rise that leaves it still full
    costs exactly capacity x $0.50 of surplus, the same as a block at demand 1.0 that stays
    full, not 1.5x that. The sweep's search cost charges only served arrivals, so the surplus
    term counts the same population (audit 2026-10-16, finding 5)."""
    from phillyparking.demand.response import cs_change, demand_level
    cap = np.array([10.0, 10.0, 10.0])
    d0 = np.array([0.8, 1.5, 1.1])
    p0, p1 = np.full(3, 2.0), np.full(3, 2.5)
    assert float(d0[1] * demand_level(2.5, -0.4, 2.0)) > 1.0 and float(d0[2] * demand_level(2.5, -0.4, 2.0)) < 1.0
    got = cs_change_usd(d0, p0, p1, -0.4, cap)
    assert got[1] == pytest.approx(-10.0 * 0.5)
    latent = cs_change(d0 * cap, p0, p1, -0.4)
    assert got[0] == pytest.approx(latent[0])            # within capacity: the plain integral
    assert abs(got[1]) < abs(latent[1])                  # over-full: the latent integral overstates it
    assert abs(got[2]) < abs(latent[2]) and -10.0 * 0.5 < got[2] < 0.0   # partly rationed
    # Search cost charges served arrivals: identical for the two blocks that are full.
    cfg = load_search_cost_config()
    occ = np.minimum(d0 * demand_level(2.5, -0.4, 2.0), 1.0)
    cost = search_cost_usd(occ, cap, cfg)
    assert occ[1] == 1.0 and cost[1] == pytest.approx(search_cost_usd(np.array([1.0]), np.array([10.0]), cfg)[0])
