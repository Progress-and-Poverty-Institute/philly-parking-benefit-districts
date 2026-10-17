"""Scenario-level guards on hours, revenue units, the Arnott-Inci peak and the search cost.

Every expected value is recomputed here from the raw YAML and the scenario's own panel,
independently of `pricing.priced_hours`, so a change to the mask, to the revenue hours or
to a threshold in the code makes these fail.
"""
from __future__ import annotations

import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from phillyparking._config import load_config, project_root
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios.runner import run_scenario
from phillyparking.spatial.synthetic import make_synthetic_segments

pytestmark = pytest.mark.slow


def _raw(name: str) -> dict:
    with open(project_root() / "config" / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _yaml_priced(zone_id: np.ndarray, how: np.ndarray) -> np.ndarray:
    zones = {z["id"]: z["priced_hours"] for z in _raw("zones")["zones"]}
    day, hour = how // 24, how % 24
    out = np.zeros(len(how), dtype=bool)
    for zid, ph in zones.items():
        for key, on_day in (("weekday", day < 5), ("saturday", day == 5), ("sunday", day == 6)):
            w = ph.get(key)
            if w is not None:
                out |= (zone_id == zid) & on_day & (hour >= w[0]) & (hour < w[1])
    return out


@pytest.fixture(scope="module")
def fixture_data():
    segs = make_synthetic_segments(n=60, seed=7)
    return segs, baseline_occupancy(segs, seed=7)


@pytest.fixture(scope="module")
def results(fixture_data):
    segs, panel = fixture_data
    return {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=7)
            for n in ("status_quo", "seattle", "full_pbd")}


def _with_zone(r, segs) -> pd.DataFrame:
    occ = r.occupancy.drop(columns=[c for c in ("zone_id", "capacity") if c in r.occupancy.columns])
    return occ.merge(segs[["segment_id", "zone_id", "capacity"]], on="segment_id")


def _row_price(df: pd.DataFrame, prices: pd.DataFrame) -> np.ndarray:
    zp = prices.drop_duplicates([c for c in ("zone_id", "band_start", "band_end") if c in prices.columns])
    out = np.full(len(df), np.nan)
    hod = df["hour_of_week"].to_numpy() % 24
    for _, r in zp.iterrows():
        m = df["zone_id"].to_numpy() == r["zone_id"]
        if "band_start" in zp.columns:
            m &= (hod >= r["band_start"]) & (hod < r["band_end"])
        out[m] = r["price_usd_per_hr"]
    return out


@pytest.mark.parametrize("name", ["status_quo", "seattle", "full_pbd"])
def test_revenue_is_52_weeks_of_priced_rows(results, fixture_data, name):
    segs, _ = fixture_data
    r = results[name]
    df = _with_zone(r, segs)
    priced = _yaml_priced(df["zone_id"].to_numpy(), df["hour_of_week"].to_numpy())
    p = df.loc[priced]
    expected = 52 * float((p["occupancy"] * p["capacity"] * _row_price(p, r.prices)).sum())
    assert float(r.revenue["annual_revenue_usd"].sum()) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("name", ["seattle", "full_pbd"])
def test_no_response_in_unpriced_hours(results, fixture_data, name):
    segs, base = fixture_data
    df = _with_zone(results[name], segs).merge(
        base[["segment_id", "hour_of_week", "occupancy"]].rename(columns={"occupancy": "base_occ"}),
        on=["segment_id", "hour_of_week"],
    )
    unpriced = ~_yaml_priced(df["zone_id"].to_numpy(), df["hour_of_week"].to_numpy())
    assert unpriced.sum() > 0
    assert np.allclose(df.loc[unpriced, "occupancy"], df.loc[unpriced, "base_occ"])
    assert not np.allclose(df.loc[~unpriced, "occupancy"], df.loc[~unpriced, "base_occ"])


def _busiest_priced_zone_hour(r, segs) -> pd.Series:
    df = _with_zone(r, segs)
    df = df.loc[_yaml_priced(df["zone_id"].to_numpy(), df["hour_of_week"].to_numpy())]
    df = df.assign(oc=df["occupancy"] * df["capacity"])
    zh = df.groupby(["zone_id", "hour_of_week"])[["oc", "capacity"]].sum()
    return (zh["oc"] / zh["capacity"]).groupby("zone_id").max()


def _expected_search_cost(r, segs) -> float:
    """The search-cost row recomputed from the raw YAML: served arrivals x minutes passing
    full blocks (p/(1-p), p = min(o, cap)^K, scaled so a full block of the reference size
    costs the stated minutes) x value of time, priced rows only, 52 weeks."""
    pr = _raw("pricing_rules")
    sc, vot = pr["search_cost"], pr["arnott_inci"]["value_of_time_usd_per_hr"]
    df = _with_zone(r, segs)
    priced = _yaml_priced(df["zone_id"].to_numpy(), df["hour_of_week"].to_numpy())
    occ = df["occupancy"].to_numpy(dtype=float)
    cap = df["capacity"].to_numpy(dtype=float)
    ratio = lambda o, k: o ** k / (1 - o ** k)  # noqa: E731
    per_block = sc["minutes_at_full_block"] / ratio(sc["occupancy_cap"], sc["reference_capacity"])
    minutes = per_block * ratio(np.minimum(occ, sc["occupancy_cap"]), np.maximum(cap, 1.0))
    arrivals = occ * cap / sc["mean_duration_hr"]
    cost = arrivals * minutes / 60.0 * vot
    return float(cost[priced].sum() * 52)


def test_arnott_prices_busiest_priced_zone_hour_to_target(results, fixture_data):
    segs, _ = fixture_data
    r = results["full_pbd"]
    target = 1.0 - _raw("scenarios")["scenarios"]["full_pbd"]["pricing_policy"]["target_vacancy"]
    zones = {z["id"]: z for z in _raw("zones")["zones"]}
    prices = r.prices.drop_duplicates("zone_id").set_index("zone_id")["price_usd_per_hr"].dropna()
    peak = _busiest_priced_zone_hour(r, segs)
    checked = 0
    for zid, p in prices.items():
        if np.isclose(p, zones[zid]["floor"]) or np.isclose(p, zones[zid]["ceiling"]):
            continue
        assert peak[zid] == pytest.approx(target, abs=2e-3), zid
        checked += 1
    assert checked >= 1   # the fixture's other zones sit at a floor or ceiling
    # The iteration reaches a fixed point; how many reviews it takes depends on the panel
    # (on this fixture the last move is at review 10, one short of confirming it under the
    # configured cap of 10), so convergence is checked with a looser cap.
    longer = run_scenario("full_pbd", segments=segs, baseline_panel=fixture_data[1], seed=7,
                          rolls_forward_years=30)
    assert longer.diagnostics["converged"]
    assert np.allclose(longer.prices.drop_duplicates("zone_id").set_index("zone_id")
                       ["price_usd_per_hr"].dropna().sort_index(), prices.sort_index(), atol=1e-3)


def test_seattle_reports_fixed_point_or_both_phases(results):
    d = results["seattle"].diagnostics
    if d["converged"]:
        assert "phases" not in d
    else:
        assert d["cycle_period"] == 2 and len(d["phases"]) == 2
        a, b = (pd.DataFrame(ph["prices"]).set_index(["zone_id", "band"])["price_usd_per_hr"] for ph in d["phases"])
        assert not np.allclose(a, b.loc[a.index])


@pytest.mark.parametrize("name", ["status_quo", "seattle", "full_pbd"])
def test_search_cost_is_the_search_model_over_priced_hours(results, fixture_data, name):
    """The scenario's cruising row is the project's search model, with no target in it."""
    segs, _ = fixture_data
    r = results[name]
    default = _raw("pricing_rules")["arnott_inci"]["target_vacancy"]
    tv = _raw("scenarios")["scenarios"][name]["pricing_policy"].get("target_vacancy", default)
    assert r.diagnostics["target_vacancy"] == tv
    assert "dwl_target_vacancy" not in r.diagnostics
    assert float(r.search_cost["annual_search_cost_usd"].sum()) == pytest.approx(_expected_search_cost(r, segs), rel=1e-9)


def test_pricer_follows_scenario_target_vacancy_and_scorer_has_no_target(fixture_data, tmp_path, monkeypatch):
    """Retune full_pbd's target_vacancy in a copied config: the price moves; the search cost
    is scored by the same target-free formula on the new panel."""
    cfg = tmp_path / "config"
    shutil.copytree(project_root() / "config", cfg)
    sc = yaml.safe_load((cfg / "scenarios.yaml").read_text(encoding="utf-8"))
    sc["scenarios"]["full_pbd"]["pricing_policy"]["target_vacancy"] = 0.25
    (cfg / "scenarios.yaml").write_text(yaml.safe_dump(sc), encoding="utf-8")
    monkeypatch.setenv("PHILLYPARKING_CONFIG_DIR", str(cfg))
    load_config.cache_clear()
    try:
        segs, panel = fixture_data
        r = run_scenario("full_pbd", segments=segs, baseline_panel=panel, seed=7)
    finally:
        monkeypatch.delenv("PHILLYPARKING_CONFIG_DIR")
        load_config.cache_clear()
    assert r.diagnostics["target_vacancy"] == 0.25
    assert float(r.search_cost["annual_search_cost_usd"].sum()) == pytest.approx(_expected_search_cost(r, segs), rel=1e-9)
    peak = _busiest_priced_zone_hour(r, segs)
    assert peak["ccc"] == pytest.approx(0.75, abs=2e-3)


def _one_zone(zone: str, occ_priced: float, occ_unpriced: float):
    segs = pd.DataFrame({"segment_id": ["s0"], "zone_id": [zone], "capacity": [10]})
    how = np.arange(168)
    priced = _yaml_priced(np.full(168, zone, dtype=object), how)
    panel = pd.DataFrame({"segment_id": "s0", "hour_of_week": how,
                          "occupancy": np.where(priced, occ_priced, occ_unpriced),
                          "occupancy_sd": 0.0})
    return segs, panel


def test_arnott_ignores_busier_unpriced_hours():
    # Overnight (unpriced) occupancy 0.95 must not set the rate; the priced peak 0.70 does.
    segs, panel = _one_zone("ccc", 0.70, 0.95)
    r = run_scenario("full_pbd", segments=segs, baseline_panel=panel)
    z = _raw("zones")["zones"][0]
    assert z["id"] == "ccc"
    eps = _raw("elasticity_priors")["scenarios"]["central"]
    target = 1.0 - _raw("scenarios")["scenarios"]["full_pbd"]["pricing_policy"]["target_vacancy"]
    from phillyparking.demand.response import price_for_demand_ratio
    rate = z["current_rate_usd_per_hr"]
    expected = float(price_for_demand_ratio(target / 0.70, rate, eps, rate))
    expected = min(max(expected, z["floor"]), z["ceiling"])
    assert float(r.prices["price_usd_per_hr"].iloc[0]) == pytest.approx(expected, rel=1e-6)


def test_seattle_two_cycle_is_detected_and_both_phases_reported():
    # Fishtown: $1.50 -> one cut to $1.00 leaves occupancy under the band, the next cut to
    # its $0.50 floor lifts it over the band, so it alternates. A $0.50 step moves demand by
    # exp(|e| 0.5 / 1.5) under the exponential form, which clears the band's 0.85 / 0.70
    # ratio only for the pessimistic elasticity (-0.7); at -0.4 the rule settles.
    from phillyparking.demand.response import demand_level
    from phillyparking.scenarios.compare import comparison_table
    eps = _raw("elasticity_priors")["scenarios"]["pessimistic"]
    occ_at_1 = 0.69
    occ_at_1_5 = occ_at_1 / float(demand_level(1.0, eps, 1.5))
    assert occ_at_1 < 0.70 < 0.85 < occ_at_1 * float(demand_level(0.5, eps, 1.5) / demand_level(1.0, eps, 1.5))
    segs, panel = _one_zone("fishtown", occ_at_1_5, 0.2)
    r = run_scenario("seattle", segments=segs, baseline_panel=panel, elasticity_scenario="pessimistic")
    d = r.diagnostics
    assert not d["converged"] and d["cycle_period"] == 2
    phase_prices = [{p["price_usd_per_hr"] for p in ph["prices"]} for ph in d["phases"]]
    assert sorted(phase_prices, key=min) == [{0.5}, {1.0}]
    assert {"seattle_phase_a", "seattle_phase_b"} <= set(comparison_table({"seattle": r}).columns)


def test_seattle_holding_band_converges_at_once():
    segs, panel = _one_zone("fishtown", 0.75, 0.2)
    d = run_scenario("seattle", segments=segs, baseline_panel=panel).diagnostics
    assert d["converged"] and d["converged_year"] == 1 and "phases" not in d


def test_pricer_falls_back_to_the_pricing_rules_target(fixture_data, tmp_path, monkeypatch):
    """With no scenario `target_vacancy`, the pricer reads `pricing_rules.yaml` (not a literal in the runner)."""
    cfg = tmp_path / "config"
    shutil.copytree(project_root() / "config", cfg)
    sc = yaml.safe_load((cfg / "scenarios.yaml").read_text(encoding="utf-8"))
    del sc["scenarios"]["full_pbd"]["pricing_policy"]["target_vacancy"]
    (cfg / "scenarios.yaml").write_text(yaml.safe_dump(sc), encoding="utf-8")
    pr = yaml.safe_load((cfg / "pricing_rules.yaml").read_text(encoding="utf-8"))
    pr["arnott_inci"]["target_vacancy"] = 0.25
    (cfg / "pricing_rules.yaml").write_text(yaml.safe_dump(pr), encoding="utf-8")
    monkeypatch.setenv("PHILLYPARKING_CONFIG_DIR", str(cfg))
    load_config.cache_clear()
    try:
        segs, panel = fixture_data
        r = run_scenario("full_pbd", segments=segs, baseline_panel=panel, seed=7)
    finally:
        monkeypatch.delenv("PHILLYPARKING_CONFIG_DIR")
        load_config.cache_clear()
    assert r.diagnostics["target_vacancy"] == 0.25
    assert float(r.search_cost["annual_search_cost_usd"].sum()) == pytest.approx(_expected_search_cost(r, segs), rel=1e-9)
    assert _busiest_priced_zone_hour(r, segs)["ccc"] == pytest.approx(0.75, abs=2e-3)
