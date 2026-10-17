"""The project's one cruising-cost model on a segment x hour panel (welfare/search_cost.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phillyparking.welfare.search_cost import (
    annual_search_cost, hourly_search_cost, load_search_cost_config, search_cost_usd,
)

MON_NOON = 12        # ccc is priced weekdays 8-20 in zones.yaml
MON_3AM = 3          # unpriced everywhere
SUN_NOON = 6 * 24 + 12


def _one(occ: float, how: int, zone: str = "ccc", capacity: float = 10.0):
    segments = pd.DataFrame({"segment_id": ["s0"], "capacity": [capacity], "zone_id": [zone]})
    panel = pd.DataFrame({"segment_id": ["s0"], "hour_of_week": [how], "occupancy": [occ]})
    return segments, panel


def test_one_full_block_hour_costs_the_per_arrival_minutes():
    cfg = load_search_cost_config()
    segments, panel = _one(1.0, MON_NOON, capacity=6.0)
    out = hourly_search_cost(panel, segments)
    assert len(out) == 1
    assert out["search_minutes_per_arrival"].iloc[0] == pytest.approx(cfg.minutes_at_full_block)
    arrivals = 6.0 / cfg.mean_duration_hr
    assert out["search_cost_usd"].iloc[0] == pytest.approx(
        arrivals * cfg.minutes_at_full_block / 60.0 * cfg.value_of_time_usd_per_hr)


@pytest.mark.parametrize("occ", [0.6, 0.85, 0.95, 1.0])
def test_search_per_arrival_does_not_depend_on_the_segment_capacity(occ):
    """The block a driver checks is the search unit, not the centerline segment: segments of
    1, 4, 10 and 20 spaces at one occupancy charge each arrival the same search, so the cost
    per space is equal. (A segment-sized unit charged a 1-space segment at the 0.99 cap ten
    times the search of a 10-space one.)"""
    cfg = load_search_cost_config()
    caps = np.array([1.0, 4.0, 10.0, 20.0])
    per_space = search_cost_usd(np.full(4, occ), caps, cfg) / caps
    assert np.allclose(per_space, per_space[0], rtol=1e-12)


def test_cost_is_additive_over_any_cut_of_the_curb():
    """One 12-space segment and the same curb cut into segments of 1, 2, 4 and 5 spaces, each
    at the same occupancy hour by hour, cost the same: where the centerline data happen to
    break a street does not move the search cost."""
    hours = [MON_NOON, MON_NOON + 1, MON_NOON + 2, MON_NOON + 3]
    occ = [0.7, 0.9, 0.97, 1.0]
    whole = pd.DataFrame({"segment_id": ["w"], "capacity": [12.0], "zone_id": ["ccc"]})
    pieces = pd.DataFrame({"segment_id": ["a", "b", "c", "d"], "capacity": [1.0, 2.0, 4.0, 5.0],
                           "zone_id": ["ccc"] * 4})
    panel_w = pd.DataFrame({"segment_id": "w", "hour_of_week": hours, "occupancy": occ})
    panel_p = pd.concat([panel_w.assign(segment_id=s) for s in pieces["segment_id"]], ignore_index=True)
    w = annual_search_cost(panel_w, whole)["annual_search_cost_usd"].sum()
    p = annual_search_cost(panel_p, pieces)["annual_search_cost_usd"].sum()
    assert w > 0 and p == pytest.approx(w, rel=1e-12)


def test_cost_is_convex_in_occupancy_with_no_target_in_it():
    cfg = load_search_cost_config()
    o = np.linspace(0.5, cfg.occupancy_cap, 51)   # convex up to the cap, where the search time stops rising
    c = search_cost_usd(o, np.full_like(o, 10.0), cfg)
    assert (c > 0).all() and (np.diff(c) > 0).all() and (np.diff(c, 2) > 0).all()
    assert search_cost_usd(np.array([1.0]), np.array([10.0]), cfg)[0] > c[-1]   # more arrivals at a full block
    assert search_cost_usd(np.array([0.85]), np.array([10.0]), cfg)[0] > 0   # not zero at the band edge


@pytest.mark.parametrize("how", [MON_3AM, SUN_NOON])
def test_unpriced_hours_score_zero(how):
    segments, panel = _one(1.0, how)
    assert hourly_search_cost(panel, segments)["search_cost_usd"].iloc[0] == 0.0
    assert hourly_search_cost(panel, segments, priced_hours_only=False)["search_cost_usd"].iloc[0] > 0.0


def test_unconfigured_zone_scores_zero():
    segments, panel = _one(1.0, MON_NOON, zone="other")
    assert hourly_search_cost(panel, segments)["search_cost_usd"].iloc[0] == 0.0


def test_panel_capacity_and_zone_are_dropped_before_the_merge():
    segments, panel = _one(1.0, MON_NOON)
    stale = panel.assign(capacity=999.0, zone_id="other")
    pd.testing.assert_frame_equal(hourly_search_cost(stale, segments), hourly_search_cost(panel, segments))


def test_annual_cost_by_zone_is_52_weeks():
    segments, panel = _one(1.0, MON_NOON)
    hourly = hourly_search_cost(panel, segments)["search_cost_usd"].iloc[0]
    out = annual_search_cost(panel, segments, priced_weeks=52)
    assert list(out["zone_id"]) == ["ccc"]
    assert out["annual_search_cost_usd"].iloc[0] == pytest.approx(hourly * 52)
