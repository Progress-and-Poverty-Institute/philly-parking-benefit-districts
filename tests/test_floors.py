"""Zone floors are stated assumptions that bind, so the pipeline reports them (audit finding 4):
an at-floor count beside the at-ceiling count, the Arnott-Inci target slack, and a rerun with
the zone floors removed (the global floor still applies)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from phillyparking._config import load_config
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.pricing.seattle_rule import load_seattle_config, zone_bounds
from phillyparking.scenarios.compare import comparison_table
from phillyparking.scenarios.ranges import NO_ZONE_FLOORS, run_values, summarize
from phillyparking.scenarios.runner import _arnott_zone_prices, run_scenario
from phillyparking.spatial.synthetic import make_synthetic_segments

SCENARIOS = ("status_quo", "seattle", "full_pbd")


def _zones() -> dict:
    return {z["id"]: z for z in load_config("zones")["zones"]}


@pytest.fixture(scope="module")
def fixture_data():
    segs = make_synthetic_segments(n=60, seed=4)
    return segs, baseline_occupancy(segs, seed=4)


def _lone_zone(occupancy: float, zone: str = "ccc"):
    """One 10-space segment in `zone`, constant occupancy in every hour of the week."""
    segs = pd.DataFrame({"segment_id": ["s"], "zone_id": [zone], "capacity": [10.0]})
    panel = pd.DataFrame({"segment_id": "s", "hour_of_week": np.arange(168), "occupancy": occupancy})
    return segs, panel


def _posted(zone: str = "ccc") -> pd.DataFrame:
    return pd.DataFrame({"zone_id": [zone],
                         "price_usd_per_hr": [float(_zones()[zone]["current_rate_usd_per_hr"])]})


def test_zone_bounds_use_the_zone_floor_unless_removed():
    cfg = load_seattle_config()
    zones = _zones()
    for zid, zone in zones.items():
        assert zone_bounds(zid, cfg) == (float(zone["floor"]), float(zone["ceiling"]))
        assert zone_bounds(zid, replace(cfg, use_zone_floors=False)) == (cfg.floor, float(zone["ceiling"]))
    assert any(float(zone["floor"]) > cfg.floor for zone in zones.values())   # removal changes something


def test_arnott_step_records_target_slack_and_the_unclipped_price():
    floor = float(_zones()["ccc"]["floor"])
    segs, panel = _lone_zone(0.30)                    # far below the 0.85 target in every hour
    row = _arnott_zone_prices(panel, segs, _posted(), 0.15, -0.4, _posted()).iloc[0]
    assert row["peak_occ"] == pytest.approx(0.30)
    assert row["target_occ"] == pytest.approx(0.85)
    assert row["target_slack"] == pytest.approx(0.85 - 0.30)
    assert row["unclipped_price"] < floor             # the target is not reachable above the floor
    assert row["price_usd_per_hr"] == pytest.approx(floor)
    assert bool(row["at_floor"]) and not bool(row["at_ceiling"])
    assert row["floor"] == pytest.approx(floor)

    g = load_seattle_config().floor
    free = _arnott_zone_prices(panel, segs, _posted(), 0.15, -0.4, _posted(), use_zone_floors=False).iloc[0]
    assert free["unclipped_price"] == pytest.approx(row["unclipped_price"])   # same solution, other bound
    assert free["floor"] == pytest.approx(g)
    assert free["price_usd_per_hr"] == pytest.approx(max(row["unclipped_price"], g))


def test_target_slack_is_negative_above_the_target_and_the_price_rises():
    segs, panel = _lone_zone(0.95)
    row = _arnott_zone_prices(panel, segs, _posted(), 0.15, -0.4, _posted()).iloc[0]
    assert row["target_slack"] == pytest.approx(0.85 - 0.95) and row["target_slack"] < 0
    assert row["unclipped_price"] > float(_posted().iloc[0]["price_usd_per_hr"])


def test_full_pbd_diagnostics_carry_the_zone_pricing_of_the_first_and_last_review(fixture_data):
    segs, panel = fixture_data
    r = run_scenario("full_pbd", segments=segs, baseline_panel=panel, seed=4)
    zp = r.diagnostics["zone_pricing"]
    assert set(zp) == {"first_review", "last_review"}
    target_occ = 1.0 - r.diagnostics["target_vacancy"]
    posted = {zid: float(z["current_rate_usd_per_hr"]) for zid, z in _zones().items()}
    assert zp["first_review"]
    for row in zp["first_review"] + zp["last_review"]:
        assert row["target_slack"] == pytest.approx(row["target_occ"] - row["peak_occ"])
        assert row["target_occ"] == pytest.approx(target_occ)
        assert bool(row["at_floor"]) == (row["price_usd_per_hr"] <= row["floor"] + 1e-9)
    for row in zp["first_review"]:
        if row["target_slack"] > 0:                    # below the target at the posted rate: price falls
            assert row["unclipped_price"] < posted[row["zone_id"]]
    assert "zone_pricing" not in run_scenario("seattle", segments=segs, baseline_panel=panel, seed=4).diagnostics
    assert r.diagnostics["use_zone_floors"] is True


def _mean_rates(r) -> pd.Series:
    return r.prices.dropna(subset=["price_usd_per_hr"]).groupby("zone_id")["price_usd_per_hr"].mean()


def test_comparison_table_counts_zones_at_their_floor(fixture_data):
    segs, panel = fixture_data
    res = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    table = comparison_table(res)
    assert "n_zones_at_floor" in table.index and "n_zones_at_ceiling" in table.index
    zones = _zones()
    for name, r in res.items():
        expected = sum(1 for zid, p in _mean_rates(r).items()
                       if zid in zones and p <= float(zones[zid]["floor"]) + 1e-9)
        assert table.loc["n_zones_at_floor", name] == expected, name
    assert table.loc["n_zones_at_floor", "status_quo"] == 0


def test_removing_zone_floors_lets_rates_down_to_the_global_floor(fixture_data):
    segs, panel = fixture_data
    # A slack city: demand well under the target everywhere, so the floors are what set rates.
    panel = panel.assign(occupancy=panel["occupancy"] * 0.4)
    base = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    free = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4, use_zone_floors=False)
            for n in SCENARIOS}
    g = load_seattle_config().floor
    zones = _zones()
    lowered = 0
    for name in ("seattle", "full_pbd"):
        assert free[name].diagnostics["use_zone_floors"] is False
        assert (free[name].prices.dropna(subset=["price_usd_per_hr"])["price_usd_per_hr"] >= g - 1e-9).all()
        for zid, p in _mean_rates(base[name]).items():
            held_up = zid in zones and abs(p - float(zones[zid]["floor"])) < 1e-9 and float(zones[zid]["floor"]) > g
            if held_up:
                assert _mean_rates(free[name])[zid] < p - 1e-9, (name, zid)   # a rate held up by its floor comes down
                lowered += 1
    assert lowered > 0                                  # the fixture has floors that bind
    t_free = comparison_table(free)                     # counted against the bound in force
    for name in SCENARIOS:
        assert t_free.loc["n_zones_at_floor", name] == sum(
            1 for zid, p in _mean_rates(free[name]).items() if zid in zones and p <= g + 1e-9), name


def test_summarize_puts_the_floor_sensitivity_beside_the_elasticity_ranges(fixture_data):
    segs, panel = fixture_data
    panel = panel.assign(occupancy=panel["occupancy"] * 0.4)    # floors bind (see above)
    res = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    free = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4, use_zone_floors=False)
            for n in SCENARIOS}
    runs = pd.concat([run_values(res, "central", 4), run_values(free, "central", 4, floors=NO_ZONE_FLOORS)],
                     ignore_index=True)
    out = summarize(runs, "central", 4, ("pessimistic", "central", "optimistic"))
    rev = out[(out["scenario"] == "full_pbd") & (out["metric"] == "total_revenue")].iloc[0]
    assert rev["headline_lo"] == pytest.approx(res["full_pbd"].revenue["annual_revenue_usd"].sum())
    assert rev["no_zone_floors_lo"] == pytest.approx(free["full_pbd"].revenue["annual_revenue_usd"].sum())
    assert rev["no_zone_floors_lo"] != pytest.approx(rev["headline_lo"])
    # the floor run is a different run, not a seed: it must not enter the seed range
    assert rev["n_seeds"] == 1 and rev["seed_lo"] == rev["seed_hi"] == rev["headline_lo"]
    # without a floor run the columns are empty
    only = summarize(run_values(res, "central", 4), "central", 4, ("pessimistic", "central", "optimistic"))
    assert only["no_zone_floors_lo"].isna().all()
