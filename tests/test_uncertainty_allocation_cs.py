"""Tests for audit findings 6, 11, 15 and 16 and the seed guard deferred from PR #5.

Expected values come from the YAML config or from the code's own definition of the
quantity, not from numbers restated here.
"""
from __future__ import annotations

import ast
import importlib.util

import matplotlib
import numpy as np
import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

matplotlib.use("Agg")

from phillyparking._config import load_config, project_root  # noqa: E402
from phillyparking.demand.synthetic_baseline import baseline_occupancy  # noqa: E402
from phillyparking.pricing.priced_hours import hourly_prices  # noqa: E402
from phillyparking.revenue.allocation import allocate, statutory_general_fund_minimum_usd  # noqa: E402
from phillyparking.revenue.forecast import annual_revenue  # noqa: E402
from phillyparking.scenarios.ranges import run_values, summarize  # noqa: E402
from phillyparking.scenarios.runner import (  # noqa: E402
    _annual_cs_change, _zone_current_prices, run_scenario,
)
from phillyparking.spatial.synthetic import make_synthetic_segments  # noqa: E402
from phillyparking.viz.charts import PLACEHOLDER_NOTE, incidence_bar_chart  # noqa: E402

pytestmark = pytest.mark.slow

SCENARIOS = ("status_quo", "seattle", "full_pbd")


# --- finding 11: statutory waterfall ---------------------------------------------------------

def test_general_fund_minimum_comes_from_config():
    with open(project_root() / "config" / "allocation.yaml", encoding="utf-8") as f:
        assert statutory_general_fund_minimum_usd() == float(yaml.safe_load(f)["general_fund_minimum_usd"])
    assert allocate(1.0).general_fund_minimum_usd == statutory_general_fund_minimum_usd()


@pytest.mark.parametrize("share", [0.0, 0.10, 0.30, 1.0])
@pytest.mark.parametrize("scale", [0.1, 0.9, 1.0, 1.3, 3.0])
def test_allocation_pays_general_fund_first_then_pbd_then_school_district(share, scale):
    floor = statutory_general_fund_minimum_usd()
    total = floor * scale
    a = allocate(total, share)
    # The General Fund is paid first, in full, before anyone else sees a dollar.
    assert a.general_fund_usd == pytest.approx(min(total, floor))
    residual = total - a.general_fund_usd
    # The PBD is paid from the residual, never beyond it, and the School District gets the rest.
    assert a.pbd_usd == pytest.approx(min(share * total, residual))
    assert a.school_district_usd == pytest.approx(residual - a.pbd_usd)
    # Nothing is created or lost: paid parts add to the total, the unpaid PBD share is reported.
    assert a.pbd_usd + a.general_fund_usd + a.school_district_usd == pytest.approx(total)
    assert a.pbd_usd + a.pbd_unfunded_usd == pytest.approx(share * total)
    assert min(a.pbd_usd, a.school_district_usd, a.pbd_unfunded_usd) >= 0.0


def test_pbd_gets_nothing_while_revenue_is_below_the_general_fund_minimum():
    total = 0.5 * statutory_general_fund_minimum_usd()
    a = allocate(total, 0.30)
    assert a.general_fund_usd == total
    assert a.pbd_usd == 0.0 and a.school_district_usd == 0.0
    assert a.pbd_unfunded_usd == pytest.approx(0.30 * total)


def test_pbd_share_comes_out_of_the_school_district_residual():
    floor = statutory_general_fund_minimum_usd()
    total = 2 * floor
    no_pbd, with_pbd = allocate(total, 0.0), allocate(total, 0.10)
    assert with_pbd.general_fund_usd == no_pbd.general_fund_usd
    assert with_pbd.school_district_usd == pytest.approx(no_pbd.school_district_usd - 0.10 * total)


# --- finding 15: consumer surplus in annual dollars ------------------------------------------

@pytest.fixture(scope="module")
def fixture_data():
    segs = make_synthetic_segments(n=60, seed=11)
    return segs, baseline_occupancy(segs, seed=11)


def _scenario_prices(factor: float) -> pd.DataFrame:
    cur = _zone_current_prices()
    return cur.assign(price_usd_per_hr=cur["price_usd_per_hr"] * factor)


def _paid_hours(segs, panel):
    cur = _zone_current_prices()
    return annual_revenue(segs, panel, hourly_prices(cur)).set_index("zone_id")["paid_hours"]


def test_cs_change_is_zero_when_prices_do_not_move(fixture_data):
    segs, panel = fixture_data
    cur = _zone_current_prices()
    assert _annual_cs_change(segs, panel, cur, cur) == pytest.approx(0.0, abs=1e-6)


def test_cs_change_is_annual_dollars_between_zero_and_the_price_change_times_paid_hours(fixture_data):
    """Roy's identity: d(CS)/d(price) = -P(curb) per paid hour, and P(curb) is a probability.

    So a price cut gains between 0 and |dp| per paid space-hour, summed over the status-quo
    paid hours of each zone. A sum over a few hundred trips, not scaled to hours, falls
    several orders of magnitude below the lower bound.
    """
    segs, panel = fixture_data
    cur = _zone_current_prices()
    cut = _scenario_prices(0.6)
    paid = _paid_hours(segs, panel)
    upper = float(sum(paid.get(z, 0.0) * (p0 - p1) for z, p0, p1 in
                      zip(cur["zone_id"], cur["price_usd_per_hr"], cut["price_usd_per_hr"])))
    cs = _annual_cs_change(segs, panel, cur, cut)
    assert 0.05 * upper < cs < upper
    # A price rise loses surplus.
    assert _annual_cs_change(segs, panel, cut, cur) < 0.0


def test_cs_change_scales_with_paid_hours(fixture_data):
    """Doubling every segment's capacity doubles the zone's paid hours and the annual figure."""
    segs, panel = fixture_data
    cur, cut = _zone_current_prices(), _scenario_prices(0.6)
    base = _annual_cs_change(segs, panel, cur, cut)
    doubled = segs.assign(capacity=segs["capacity"] * 2)
    assert _annual_cs_change(doubled, panel, cur, cut) == pytest.approx(2 * base, rel=1e-9)


def test_cs_change_does_not_invent_a_price_for_a_priced_zone(fixture_data):
    segs, panel = fixture_data
    cur = _zone_current_prices()
    with pytest.raises(KeyError):
        _annual_cs_change(segs, panel, cur, cur[cur["zone_id"] != "ccc"])


# --- finding 6: elasticity scenarios and seed ranges ----------------------------------------

def test_named_elasticity_scenarios_change_the_run(fixture_data):
    segs, panel = fixture_data
    rev = {}
    for name in ("pessimistic", "central", "optimistic"):
        r = run_scenario("seattle", segments=segs, baseline_panel=panel, seed=11, elasticity_scenario=name)
        assert r.elasticity_scenario == name
        assert r.provenance["elasticity"]["scenario"] == name
        rev[name] = float(r.revenue["annual_revenue_usd"].sum())
    assert len({round(v, 2) for v in rev.values()}) == 3, rev


def _runs(values: dict) -> pd.DataFrame:
    """values: {(elasticity, seed): {(column, metric): value}} -> run_values-shaped frame."""
    rows = []
    for (e, s), cells in values.items():
        for (col, metric), v in cells.items():
            rows.append({"elasticity_scenario": e, "seed": s, "scenario": col.partition("_phase_")[0],
                         "metric": metric, "column": col, "value": v})
    return pd.DataFrame(rows)


def test_summarize_reports_elasticity_seed_and_phase_ranges():
    m = "total_revenue"
    runs = _runs({
        ("central", 42): {("seattle_phase_a", m): 10.0, ("seattle_phase_b", m): 14.0},
        ("pessimistic", 42): {("seattle_phase_a", m): 40.0, ("seattle_phase_b", m): 42.0},
        ("optimistic", 42): {("seattle", m): 0.5},
        ("central", 0): {("seattle", m): 1.0},
        ("central", 1): {("seattle_phase_a", m): 30.0, ("seattle_phase_b", m): 31.0},
    })
    row = summarize(runs, "central", 42, ("pessimistic", "central", "optimistic")).iloc[0]
    assert (row["headline_lo"], row["headline_hi"]) == (10.0, 14.0)      # both phases
    assert (row["pessimistic_lo"], row["pessimistic_hi"]) == (40.0, 42.0)
    assert (row["optimistic_lo"], row["optimistic_hi"]) == (0.5, 0.5)
    assert (row["seed_lo"], row["seed_hi"], row["n_seeds"]) == (1.0, 31.0, 3)  # seeds 42, 0, 1


def test_run_values_drops_bookkeeping_rows_and_tags_the_run(fixture_data):
    segs, panel = fixture_data
    res = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=11) for n in SCENARIOS}
    long = run_values(res, "central", 11)
    assert set(long["scenario"]) == set(SCENARIOS)
    assert not {"review_year", "converged"} & set(long["metric"])
    assert {"total_revenue", "cruising_dwl_total", "cs_change_total", "pbd_unfunded"} <= set(long["metric"])
    assert set(long["seed"]) == {11} and set(long["elasticity_scenario"]) == {"central"}


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), project_root() / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def script05(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("PHILLYPARKING_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data" / "processed").mkdir(parents=True)
    return _script("05_run_scenarios.py"), tmp_path


def _no_named_zones(path):
    """Loaded segments none of which are in a named zone: script 05 falls back to the fixture."""
    segs = make_synthetic_segments(n=30, seed=5)
    segs["zone_id"] = "other"
    return segs


def test_script_05_writes_ranges_with_every_elasticity_and_seed(script05, monkeypatch):
    mod, root = script05
    models = root / "outputs" / "models"
    monkeypatch.setattr(mod, "load_segments", _no_named_zones)
    out = CliRunner().invoke(mod.main, ["--seed", "5", "--n-seeds", "3"])
    assert out.exit_code == 0, out.output
    ranges = pd.read_csv(models / "scenario_ranges.csv")
    runs = pd.read_csv(models / "scenario_runs.csv")
    names = set(load_config("elasticity_priors")["scenarios"])
    assert set(runs["elasticity_scenario"]) == names
    assert set(runs[runs["elasticity_scenario"] == "central"]["seed"]) == {0, 1, 2, 5}
    assert set(ranges["scenario"]) == set(SCENARIOS)
    assert {f"{n}_lo" for n in names - {"central"}} <= set(ranges.columns)
    rev = ranges[(ranges["scenario"] == "seattle") & (ranges["metric"] == "total_revenue")].iloc[0]
    assert rev["pessimistic_lo"] != rev["optimistic_lo"]      # the elasticity reaches the run
    assert rev["seed_lo"] < rev["seed_hi"]                    # and so does the seed
    assert rev["n_seeds"] == 4


# --- the seed reaches the outputs ------------------------------------------------------------

def _run_05(mod, root, seed: int) -> pd.DataFrame:
    (root / "data" / "processed" / "demand_panel.parquet").unlink(missing_ok=True)
    out = CliRunner().invoke(mod.main, ["--seed", str(seed), "--n-seeds", "0"])
    assert out.exit_code == 0, out.output
    return pd.read_csv(root / "outputs" / "models" / "comparison_table.csv", index_col=0)


def test_script_05_outputs_change_with_the_seed_on_loaded_segments(script05, monkeypatch):
    """The occupancy panel is a deterministic function of segment covariates, so on segments
    that are loaded rather than drawn the seed reaches only the consumer-surplus trips. It must
    reach those."""
    mod, root = script05
    monkeypatch.setattr(mod, "load_segments", lambda path: make_synthetic_segments(n=30, seed=5))
    a1 = _run_05(mod, root, 1)
    a1_again = _run_05(mod, root, 1)
    a2 = _run_05(mod, root, 2)
    pd.testing.assert_frame_equal(a1, a1_again)               # same seed, same numbers
    assert a1.loc["cs_change_total", "full_pbd"] != a2.loc["cs_change_total", "full_pbd"]


def test_script_05_outputs_change_with_the_seed_when_it_falls_back_to_the_fixture(script05, monkeypatch):
    mod, root = script05

    monkeypatch.setattr(mod, "load_segments", _no_named_zones)
    a1 = _run_05(mod, root, 1)
    a2 = _run_05(mod, root, 2)
    for row in ("total_revenue", "cruising_dwl_total", "cs_change_total"):
        assert a1.loc[row, "status_quo"] != a2.loc[row, "status_quo"] or row == "cs_change_total", row
        assert a1.loc[row, "full_pbd"] != a2.loc[row, "full_pbd"], row


# --- finding 16: the placeholder incidence figure says so ------------------------------------

def test_placeholder_incidence_figure_is_labelled_in_the_figure():
    import matplotlib.pyplot as plt
    inc = pd.DataFrame({"decile": range(1, 11), "mean_payment": 50.0, "mean_cs_change": -10.0})
    marked, plain = incidence_bar_chart(inc, placeholder=True), incidence_bar_chart(inc)
    try:
        assert PLACEHOLDER_NOTE in marked.axes[0].get_title()
        assert any("PLACEHOLDER" in t.get_text() for t in marked.axes[0].texts)
        assert "PLACEHOLDER" not in plain.axes[0].get_title() and not plain.axes[0].texts
    finally:
        plt.close(marked)
        plt.close(plain)


def test_every_script_and_app_call_of_the_incidence_chart_is_marked_placeholder():
    root = project_root()
    files = [*(root / "scripts").glob("*.py"), *(root / "app").rglob("*.py")]
    calls = 0
    for p in files:
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "incidence_bar_chart":
                calls += 1
                kw = {k.arg: k.value for k in node.keywords}
                assert isinstance(kw.get("placeholder"), ast.Constant) and kw["placeholder"].value is True, p
    assert calls >= 2
