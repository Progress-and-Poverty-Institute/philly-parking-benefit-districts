"""The Chatman-Manville sweep's welfare scorer: search cost shape, level and cap, consumer surplus."""
from __future__ import annotations

import numpy as np
import pytest

from phillyparking._config import load_config
from phillyparking.welfare.targeting_welfare import (
    cited_cruising_minutes, cs_change_usd, expected_search_minutes, load_search_cost_config,
    minutes_per_full_block, reference_minutes_per_cruising_minute, search_cost_usd,
)

CAPS = (0.95, 0.99, 0.999)


def test_level_is_per_cruiser_and_an_arrival_at_a_full_block_searches_cap_k_of_it():
    """The level is in the units of the cited studies, the mean search of the drivers who
    cruise. When every block is full a cruiser passes 1 / (1 - cap^K) full blocks, and an
    arrival cruises only if the first block is full (probability cap^K), so the expected
    search per arrival there is cap^K x the level, not the level itself."""
    for cap in CAPS:
        cfg = load_search_cost_config(occupancy_cap=cap)
        p_full = cap ** cfg.search_unit_spaces
        assert minutes_per_full_block(cfg) / (1.0 - p_full) == pytest.approx(cfg.cruising_minutes_at_full_block)
        per_arrival = expected_search_minutes(np.array([1.0]), cfg)[0]
        assert per_arrival == pytest.approx(p_full * cfg.cruising_minutes_at_full_block)
        assert per_arrival == pytest.approx(cfg.minutes_at_full_block)
        assert per_arrival < cfg.cruising_minutes_at_full_block
    cfg = load_search_cost_config()
    twice = load_search_cost_config(2 * cfg.cruising_minutes_at_full_block)
    assert expected_search_minutes(np.array([0.9]), twice)[0] == pytest.approx(
        2 * expected_search_minutes(np.array([0.9]), cfg)[0])


def test_cap_sets_how_much_more_a_full_block_costs_than_the_reference_block():
    """The cap decides the 95% block's cost relative to a full one, and
    `reference_minutes_per_cruising_minute` is exactly the conversion of the level to minutes
    per arrival at the 95% block. A block short of the lower cap costs less at a higher cap."""
    for cap in CAPS:
        cfg = load_search_cost_config(occupancy_cap=cap)
        at_ref = expected_search_minutes(np.array([0.95]), cfg)[0]
        assert at_ref / cfg.cruising_minutes_at_full_block == pytest.approx(reference_minutes_per_cruising_minute(cfg))
    full_over_ref = {cap: float(expected_search_minutes(np.array([1.0]), load_search_cost_config(occupancy_cap=cap))[0]
                                / expected_search_minutes(np.array([0.95]), load_search_cost_config(occupancy_cap=cap))[0])
                     for cap in CAPS}
    assert full_over_ref[0.95] == pytest.approx(1.0)
    assert 6.0 < full_over_ref[0.99] < 6.5 and full_over_ref[0.999] > 60
    lo, hi = (expected_search_minutes(np.array([0.9]), load_search_cost_config(occupancy_cap=c))[0] for c in (0.95, 0.99))
    assert hi < lo
    with pytest.raises(ValueError):
        load_search_cost_config(occupancy_cap=1.5)
    with pytest.raises(ValueError):
        load_search_cost_config(occupancy_cap=1.0)   # a cruiser at a full block would never find a space


def test_level_is_the_cited_mean_cruising_time():
    """The config level is set at the cited per-cruiser mean, in the cited units."""
    cfg, cited = load_search_cost_config(), cited_cruising_minutes()
    assert cited["low"] < cited["mean"] < cited["high"]
    assert cfg.cruising_minutes_at_full_block == cited["mean"]
    assert "cruise" in cited["source"]


def test_search_minutes_increase_and_are_convex_in_occupancy_up_to_the_cap():
    cfg = load_search_cost_config()
    o = np.linspace(0.5, cfg.occupancy_cap, 50)
    m = expected_search_minutes(o, cfg)
    assert (np.diff(m) > 0).all() and (np.diff(m, 2) > 0).all()
    # A full block costs the capped search, not an infinite one.
    full = expected_search_minutes(np.array([1.0]), cfg)[0]
    assert np.isfinite(full) and full == expected_search_minutes(np.array([cfg.occupancy_cap]), cfg)[0]


def test_search_cost_is_arrivals_times_time_times_value_of_time():
    cfg = load_search_cost_config()
    occ, cap = np.array([0.95]), np.array([10.0])
    arrivals = 0.95 * 10.0 / cfg.mean_duration_hr
    minutes = expected_search_minutes(occ, cfg)[0]
    assert search_cost_usd(occ, cap, cfg)[0] == pytest.approx(arrivals * (minutes / 60.0) * cfg.value_of_time_usd_per_hr)
    full = search_cost_usd(np.array([1.0]), cap, cfg)[0]
    assert full == pytest.approx(10.0 / cfg.mean_duration_hr * (cfg.minutes_at_full_block / 60.0) * cfg.value_of_time_usd_per_hr)
    assert search_cost_usd(np.array([0.0]), cap, cfg)[0] == 0.0
    assert search_cost_usd(np.array([0.9]), np.array([0.0]), cfg)[0] == 0.0   # no space, no arrivals
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
