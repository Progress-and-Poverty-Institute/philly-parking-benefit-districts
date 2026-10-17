"""The demand form and its anchoring are stated assumptions, and the pipeline shows how the results
move with them (audit 2026-10-16, finding 6): one citywide law against the per-zone anchoring,
the three forms in the Chatman-Manville sweep, and what `ordering_violations` checks."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from phillyparking._config import load_config
from phillyparking.demand.response import (
    FORMS, cs_change_served, citywide_zone_elasticities, demand_factor, demand_level,
    elasticity_at, revenue_maximising_price,
)
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios import cm_sweep
from phillyparking.scenarios.cm_sweep import (
    FORM_SENSITIVITY_FILES, beyond_peak_table, chatman_manville_sweep, form_sensitivity_table,
    paired_table, save_form_sensitivity,
)
from phillyparking.scenarios.ranges import CITYWIDE_LAW, run_values, summarize
from phillyparking.scenarios.runner import (
    _annual_cs_change, _arnott_zone_prices, _zone_current_prices, citywide_reference_price,
    run_scenario,
)
from phillyparking.spatial.synthetic import make_synthetic_segments

SCENARIOS = ("status_quo", "seattle", "full_pbd")
NAMES = ("pessimistic", "central", "optimistic")


# --------------------------------------------------------------------------- one law, many anchors


@pytest.mark.parametrize("form", FORMS)
def test_citywide_elasticities_make_the_zone_anchored_machinery_follow_one_law(form):
    """Re-anchoring the citywide law at a zone's posted rate with the elasticity it has there
    leaves the curve unchanged, for every form: that is what lets the runner reuse its
    per-zone code for the citywide sensitivity."""
    e, p0 = -0.4, 2.5
    posted = pd.Series({"cheap": 1.5, "mid": 2.5, "dear": 4.0}, name="price_usd_per_hr")
    zone_e = citywide_zone_elasticities(posted, e, p0, form)
    for zone, p_z in posted.items():
        for p in (1.0, 1.5, 2.0, 3.0, 4.5, 6.0):
            single_law = demand_level(p, e, p0, form) / demand_level(p_z, e, p0, form)
            anchored_at_zone = demand_factor(p, p_z, zone_e[zone], p_z, form)
            assert float(anchored_at_zone) == pytest.approx(float(single_law), rel=1e-9), (form, zone, p)


def test_one_citywide_law_gives_the_zones_different_elasticities_at_their_posted_rates():
    posted = pd.DataFrame({"zone_id": ["fishtown", "ccc"], "price_usd_per_hr": [1.5, 4.0]})
    zone_e = citywide_zone_elasticities(posted, -0.4, 1.5, "exponential")
    assert zone_e["fishtown"] == pytest.approx(-0.4)
    assert zone_e["ccc"] == pytest.approx(-0.4 * 4.0 / 1.5)               # -1.07, the audit's number
    assert float(elasticity_at(4.0, -0.4, 1.5, "exponential")) == pytest.approx(zone_e["ccc"])
    # constant elasticity has one elasticity at every price, so the two anchorings coincide
    flat = citywide_zone_elasticities(posted, -0.4, 1.5, "constant_elasticity")
    assert flat.tolist() == [-0.4, -0.4]


def test_citywide_reference_price_is_the_capacity_weighted_mean_posted_rate():
    posted = pd.DataFrame({"zone_id": ["fishtown", "ccc"], "price_usd_per_hr": [1.5, 4.0]})
    segs = pd.DataFrame({"segment_id": ["a", "b", "c"], "zone_id": ["fishtown", "ccc", "other"],
                         "capacity": [30.0, 10.0, 500.0]})      # "other" is never priced: ignored
    assert citywide_reference_price(segs, posted) == pytest.approx((1.5 * 30 + 4.0 * 10) / 40)
    with pytest.raises(ValueError):
        citywide_reference_price(segs.assign(zone_id="other"), posted)


@pytest.fixture(scope="module")
def fixture_data():
    segs = make_synthetic_segments(n=60, seed=4)
    return segs, baseline_occupancy(segs, seed=4)


def test_per_zone_and_citywide_runs_differ_only_where_the_law_does(fixture_data):
    segs, panel = fixture_data
    p0 = citywide_reference_price(segs)
    base = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    city = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4, citywide_reference_price=p0)
            for n in SCENARIOS}
    zones = {z["id"]: float(z["current_rate_usd_per_hr"]) for z in load_config("zones")["zones"]}
    e = load_config("elasticity_priors")["scenarios"]["central"]

    law = base["full_pbd"].diagnostics["demand_law"]
    assert law["anchoring"] == "per_zone" and law["reference_price"] is None
    assert set(law["zone_elasticity_at_posted_rate"].values()) == {e}
    law = city["full_pbd"].diagnostics["demand_law"]
    assert law["anchoring"] == "citywide" and law["reference_price"] == pytest.approx(p0)
    for zid, p in zones.items():
        assert law["zone_elasticity_at_posted_rate"][zid] == pytest.approx(
            float(elasticity_at(p, e, p0, law["form"])))

    # the status quo moves no price: same under either anchoring
    assert city["status_quo"].revenue["annual_revenue_usd"].sum() == pytest.approx(
        base["status_quo"].revenue["annual_revenue_usd"].sum())
    # the reforms move prices, so the law shows
    assert city["full_pbd"].revenue["annual_revenue_usd"].sum() != pytest.approx(
        base["full_pbd"].revenue["annual_revenue_usd"].sum())


def test_scalar_and_constant_series_elasticity_agree_in_the_runner_helpers(fixture_data):
    segs, panel = fixture_data
    posted = _zone_current_prices()
    flat = pd.Series({z: -0.4 for z in posted["zone_id"]})
    scalar_rows = _arnott_zone_prices(panel, segs, posted, 0.15, -0.4, posted)
    series_rows = _arnott_zone_prices(panel, segs, posted, 0.15, flat, posted)
    pd.testing.assert_frame_equal(scalar_rows, series_rows)

    hourly = posted.merge(pd.DataFrame({"hour_of_week": np.arange(168)}), how="cross").assign(
        price_usd_per_hr=lambda d: d["price_usd_per_hr"] + 0.5)
    assert _annual_cs_change(segs, panel, posted, hourly, -0.4) == pytest.approx(
        _annual_cs_change(segs, panel, posted, hourly, flat))


def test_summarize_reports_the_citywide_law_beside_the_per_zone_ranges(fixture_data):
    segs, panel = fixture_data
    p0 = citywide_reference_price(segs)
    res = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    city = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4, citywide_reference_price=p0)
            for n in SCENARIOS}
    runs = pd.concat([run_values(res, "central", 4),
                      run_values(city, "central", 4, law=CITYWIDE_LAW, law_reference_price=p0)],
                     ignore_index=True)
    out = summarize(runs, "central", 4, NAMES)
    rev = out[(out["scenario"] == "full_pbd") & (out["metric"] == "total_revenue")].iloc[0]
    assert rev["headline_lo"] == pytest.approx(res["full_pbd"].revenue["annual_revenue_usd"].sum())
    assert rev["citywide_law_lo"] == pytest.approx(city["full_pbd"].revenue["annual_revenue_usd"].sum())
    assert rev["citywide_law_reference_price"] == pytest.approx(p0)
    assert rev["citywide_law_lo"] != pytest.approx(rev["headline_lo"])
    # a different law is a different run, not a seed
    assert rev["n_seeds"] == 1 and rev["seed_lo"] == rev["seed_hi"] == rev["headline_lo"]
    only = summarize(run_values(res, "central", 4), "central", 4, NAMES)
    assert only["citywide_law_lo"].isna().all() and only["citywide_law_reference_price"].isna().all()


# --------------------------------------------------------------------------- the sweep under each form

SMALL = dict(elasticity_values=[-0.4, -0.7], start_occupancy=[0.75], block_dispersion=[0.3],
             observation_noise=[0.0], occupancy_cap=[0.95, 0.99], n_replications=2, rolls_forward_years=4)
SEGS = make_synthetic_segments(n=30, seed=1)


@pytest.fixture(scope="module")
def form_sweeps():
    return {f: chatman_manville_sweep(segments=SEGS, demand_form=f, **SMALL) for f in FORMS}


def test_the_sweep_records_and_obeys_its_demand_form(form_sweeps):
    for form, sweep in form_sweeps.items():
        assert sweep.attrs["provenance"]["demand_form"] == form
    # the forms disagree where the price is far from the start price: not one law in disguise
    last = {f: s[s["year"] == s["year"].max()].groupby(["elasticity", "rule"])["revenue"].median()
            for f, s in form_sweeps.items()}
    assert not np.allclose(last["exponential"], last["linear"])
    assert not np.allclose(last["exponential"], last["constant_elasticity"])
    with pytest.raises(ValueError, match="demand_form"):
        chatman_manville_sweep(segments=SEGS, demand_form="cubic", **SMALL)


def test_form_sensitivity_table_has_one_row_per_form_comparison_and_cap(form_sweeps):
    table = form_sensitivity_table(form_sweeps)
    comparisons = cm_sweep.comparisons_from_config()
    caps = SMALL["occupancy_cap"]
    assert len(table) == len(FORMS) * len(comparisons) * len(caps)
    assert set(table["form"]) == set(FORMS)
    assert (table["n_replications"] == SMALL["n_replications"]).all()
    for col in ("rule", "reference", "occupancy_cap", "n_cells", "cells_welfare_better",
                "breakeven_cruising_minutes_median_cells_median",
                "breakeven_cruising_minutes_median_cells_min",
                "breakeven_cruising_minutes_median_cells_max"):
        assert col in table.columns, col
    assert (table["n_cells"] == len(SMALL["elasticity_values"])).all()
    assert table["cells_welfare_better"].between(0, table["n_cells"]).all()
    # the exponential rows are the headline form's paired table at these replications
    expo = table[table["form"] == "exponential"]
    direct = cm_sweep.window_dependence(paired_table(form_sweeps["exponential"]))
    pd.testing.assert_frame_equal(expo.drop(columns=["form", "n_replications"]).reset_index(drop=True), direct)


def test_beyond_peak_table_reads_each_form_against_its_own_peak(form_sweeps):
    t = beyond_peak_table(form_sweeps)
    start = float(load_config("scenarios")["chatman_manville_sweep"]["start_price_usd"])
    assert set(t["form"]) == set(FORMS)
    for _, r in t.iterrows():
        peak = revenue_maximising_price(r["elasticity"], start, r["form"])
        if peak is None:
            assert np.isnan(r["revenue_peak_price_usd"]) and np.isnan(r["share_beyond_peak"])
        else:
            assert r["revenue_peak_price_usd"] == pytest.approx(peak)
            assert 0.0 <= r["share_beyond_peak"] <= 1.0
    # |e| < 1: constant elasticity has no revenue peak; the exponential's is start / |e|
    assert t[(t["form"] == "constant_elasticity")]["revenue_peak_price_usd"].isna().all()
    assert t[(t["form"] == "exponential") & (t["elasticity"] == -0.7)]["revenue_peak_price_usd"].tolist() ==         pytest.approx([start / 0.7] * 5)       # one per rule


def test_save_form_sensitivity_writes_the_tables_and_their_provenance(form_sweeps, tmp_path):
    paths = save_form_sensitivity(form_sweeps, tmp_path)
    assert [p.name for p in paths] == list(FORM_SENSITIVITY_FILES)
    assert all(p.exists() for p in paths)
    table = pd.read_csv(tmp_path / "cm_sweep_form_sensitivity.csv")
    assert set(table["form"]) == set(FORMS)
    meta = json.loads((tmp_path / "cm_sweep_form_sensitivity.meta.json").read_text(encoding="utf-8"))
    assert meta["forms"] == list(FORMS)
    assert meta["n_replications"] == SMALL["n_replications"]
    assert set(meta["per_form_demand_form"].values()) == set(FORMS)
    assert meta["config_sha256"] and "git" in meta
    assert meta["same_inputs_across_forms"]["rules"]


# --------------------------------------------------------------------------- what ordering_violations checks


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("capacity", [10.0, 0.5])      # a block that holds its demand, and one that is rationed
def test_total_surplus_falls_in_price_even_where_revenue_falls_too(form, capacity):
    """CS + revenue on the cars served is non-increasing in price under every form, including
    above the revenue-maximising price, so `ordering_violations` can compare it without an
    exception for blocks priced past the peak. Revenue alone is not ordered there."""
    e, p0, q0 = -0.7, 2.0, 1.0
    prices = np.linspace(1.0, 6.0, 51)
    served = np.minimum(q0 * demand_level(prices, e, p0, form), capacity)
    revenue = prices * served
    surplus = cs_change_served(np.full_like(prices, q0), p0, prices, e, capacity, form)
    total = surplus + revenue
    assert (np.diff(total) <= 1e-9).all()
    peak = revenue_maximising_price(e, p0, form)
    if form != "constant_elasticity" and capacity > 1:
        past = prices > peak
        assert past.any() and (np.diff(revenue[past]) <= 1e-12).all()      # revenue itself falls past the peak
        assert revenue[past][-1] < revenue[past][0]


def test_ordering_violations_flags_search_cost_and_total_surplus_only():
    keys = dict(elasticity=-0.4, start_occupancy=0.75, block_dispersion=0.3, observation_noise=0.0,
                occupancy_cap=0.95, replication=0, year=1)
    def row(rule, search, cs, rev):
        return {**keys, "rule": rule, "search_cost": search, "cs_change": cs, "revenue": rev}
    ok = pd.DataFrame([row("a", 10.0, -5.0, 1.0), row("b", 8.0, -7.0, 3.0)])      # less revenue, more surplus
    assert cm_sweep.ordering_violations(ok, "a", "b").empty
    bad_cost = pd.DataFrame([row("a", 7.0, -5.0, 1.0), row("b", 8.0, -7.0, 3.0)])
    assert len(cm_sweep.ordering_violations(bad_cost, "a", "b")) == 1
    bad_surplus = pd.DataFrame([row("a", 10.0, -9.0, 1.0), row("b", 8.0, -7.0, 3.0)])
    assert len(cm_sweep.ordering_violations(bad_surplus, "a", "b")) == 1
