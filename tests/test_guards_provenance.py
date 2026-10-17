"""Guards on the comparison table, saved-result provenance, the app's results path and the
generated report assets (audit findings 20, 21, 22 and advisory items A1, A2).

Expected values come from the YAML config, from `allocate`, or from files on disk, never from
a constant restated here, so a change to the code or to the config that the code ignores
makes a test fail.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import subprocess
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

matplotlib.use("Agg")

from phillyparking._config import config_dir, load_config, project_root  # noqa: E402
from phillyparking.demand.synthetic_baseline import baseline_occupancy  # noqa: E402
from phillyparking.revenue.allocation import RevenueAllocation, allocate  # noqa: E402
from phillyparking.scenarios.compare import _table_column, comparison_table  # noqa: E402
from phillyparking.scenarios.runner import (  # noqa: E402
    ScenarioResults, check_panel, default_results_dir, load_saved_scenarios, run_scenario,
)
from phillyparking.spatial.synthetic import make_synthetic_segments  # noqa: E402
from phillyparking.viz.report_figures import (  # noqa: E402
    cm_sweep_year_chart, occupancy_and_revenue_detail, zone_map_figure,
)
from phillyparking.viz.tables import rows as table_rows, scenario_comparison_tex  # noqa: E402

pytestmark = pytest.mark.slow

SCENARIOS = ("status_quo", "seattle", "full_pbd")


def _raw(name: str) -> dict:
    with open(project_root() / "config" / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def fixture_data():
    segs = make_synthetic_segments(n=40, seed=3)
    return segs, baseline_occupancy(segs, seed=3)


@pytest.fixture(scope="module")
def results(fixture_data):
    segs, panel = fixture_data
    return {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=3) for n in SCENARIOS}


# --- A2: comparison-table allocation keys --------------------------------------------------

def test_table_column_reads_the_allocation_keys_allocate_emits():
    """A $100M total is large enough that the School District residual is non-zero."""
    share = _raw("scenarios")["scenarios"]["full_pbd"]["rpp_policy"]["revenue_share_to_pbd"]
    total = 100e6
    gf_min = RevenueAllocation(total_revenue_usd=total).general_fund_minimum_usd
    col = _table_column({}, total, 0.0, 0.0, allocate(total, share).to_dict(), 1, True, 0.0)
    # Statutory order: General Fund minimum first, then the PBD, then the School District.
    expected_gf = min(total, gf_min)
    expected_pbd = min(total * share, total - expected_gf)
    assert col["gf_to_general_fund"] == pytest.approx(expected_gf)
    assert col["pbd_revenue"] == pytest.approx(expected_pbd)
    assert col["pbd_unfunded"] == pytest.approx(total * share - expected_pbd)
    assert col["sdp_revenue"] == pytest.approx(total - expected_pbd - expected_gf)
    assert col["sdp_revenue"] > 0 and col["pbd_revenue"] > 0


def test_table_column_does_not_default_a_missing_allocation_key():
    stale = {"total_revenue_usd": 1.0, "pbd_revenue_usd": 1.0, "general_fund_usd": 0.0}
    with pytest.raises(KeyError):
        _table_column({}, 1.0, 0.0, 0.0, stale, 1, True, 0.0)


def test_comparison_table_allocation_rows_conserve_revenue(results):
    table = comparison_table(results)
    share = _raw("scenarios")["scenarios"]["full_pbd"]["rpp_policy"]["revenue_share_to_pbd"]
    assert share > 0
    for col in table.columns:
        parts = table.loc[["pbd_revenue", "sdp_revenue", "gf_to_general_fund"], col].sum()
        assert parts == pytest.approx(table.loc["total_revenue", col])
    # The PBD's claim is its share of revenue; what is paid plus what the General Fund minimum
    # leaves unpaid adds back to it.
    paid_plus_unpaid = table.loc["pbd_revenue", "full_pbd"] + table.loc["pbd_unfunded", "full_pbd"]
    assert paid_plus_unpaid == pytest.approx(share * table.loc["total_revenue", "full_pbd"])
    assert table.loc["pbd_revenue", "status_quo"] == 0.0 and table.loc["pbd_unfunded", "status_quo"] == 0.0


# --- A1: a zone the config does not price --------------------------------------------------

def test_zone_absent_from_config_earns_zero_and_is_reported(results, fixture_data):
    segs, _ = fixture_data
    configured = {z["id"] for z in load_config("zones")["zones"]}
    stray = segs.loc[~segs["zone_id"].isin(configured)]
    assert len(stray) > 0, "fixture should carry a zone zones.yaml does not configure"
    for name, r in results.items():
        rev = r.revenue.set_index("zone_id")["annual_revenue_usd"]
        assert np.isfinite(rev.sum())
        for z in stray["zone_id"].unique():
            assert rev.get(z, 0.0) == 0.0, (name, z)
        reported = r.diagnostics["unpriced_zones"]
        for z, g in stray.groupby("zone_id"):
            assert reported[z] == {"n_segments": len(g), "capacity": float(g["capacity"].sum())}


# --- finding 20: a NaN or out-of-range panel must not become a number ----------------------

def test_runner_rejects_nan_panel(fixture_data):
    segs, panel = fixture_data
    bad = panel.copy()
    bad.loc[bad.index[:5], "occupancy"] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        run_scenario("status_quo", segments=segs, baseline_panel=bad)


def test_check_panel_rejects_out_of_range_and_missing_columns(fixture_data):
    _, panel = fixture_data
    check_panel(panel)
    with pytest.raises(ValueError, match="outside"):
        check_panel(panel.assign(occupancy=panel["occupancy"] + 1.0))
    with pytest.raises(ValueError, match="lacks columns"):
        check_panel(panel.drop(columns=["hour_of_week"]))


# --- finding 21: provenance in meta.json ---------------------------------------------------

def test_provenance_records_segments_config_commit_and_elasticity(results, tmp_path):
    r = results["full_pbd"]
    r.save(tmp_path / "full_pbd")
    prov = ScenarioResults.load(tmp_path / "full_pbd").provenance

    assert prov["segment_source"]["kind"] == "synthetic_fixture"
    assert prov["segment_source"]["n"] == 40 and prov["segment_source"]["seed"] == 3
    assert prov["segment_source"]["n_segments"] == 40
    assert prov["seed"] == 3

    on_disk = {p.stem: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
               for p in config_dir().glob("*.yaml")}
    assert prov["config_sha256"] == on_disk
    assert set(on_disk) >= {"zones", "scenarios", "pricing_rules", "elasticity_priors"}

    central = _raw("elasticity_priors")["scenarios"][r.elasticity_scenario]
    assert prov["elasticity"]["scenario"] == r.elasticity_scenario
    assert prov["elasticity"]["central"] == pytest.approx(central)
    assert prov["elasticity"]["sd"] > 0

    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root(), capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git not available")
    assert prov["git"]["commit"] == head
    assert isinstance(prov["git"]["dirty"], bool)
    assert prov["created_utc"]


def test_provenance_hash_changes_with_config(fixture_data, tmp_path, monkeypatch):
    import shutil
    cfg = tmp_path / "config"
    shutil.copytree(project_root() / "config", cfg)
    z = cfg / "zones.yaml"
    z.write_text(z.read_text(encoding="utf-8") + "\n# edited\n", encoding="utf-8")
    monkeypatch.setenv("PHILLYPARKING_CONFIG_DIR", str(cfg))
    load_config.cache_clear()
    try:
        segs, panel = fixture_data
        r = run_scenario("status_quo", segments=segs, baseline_panel=panel, seed=3)
    finally:
        monkeypatch.delenv("PHILLYPARKING_CONFIG_DIR")
        load_config.cache_clear()
    assert r.provenance["config_sha256"]["zones"] == hashlib.sha256(
        z.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_explicit_segment_source_overrides_attrs(fixture_data):
    segs, panel = fixture_data
    src = {"kind": "file", "path": "data/processed/segments.parquet"}
    r = run_scenario("status_quo", segments=segs, baseline_panel=panel, seed=3, segment_source=src)
    assert r.provenance["segment_source"]["kind"] == "file"
    assert r.provenance["segment_source"]["path"] == src["path"]


def test_frame_without_attrs_is_reported_unknown(fixture_data):
    segs, panel = fixture_data
    plain = pd.DataFrame(segs.drop(columns="geometry"))
    plain.attrs.clear()
    r = run_scenario("status_quo", segments=plain, baseline_panel=panel, seed=3)
    assert r.provenance["segment_source"]["kind"] == "unknown"


# --- finding 22: the app reads what script 05 writes ---------------------------------------

def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), project_root() / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_results_written_by_script_05_are_found_by_the_app_loader(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("PHILLYPARKING_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data" / "processed").mkdir(parents=True)
    mod = _load_script("05_run_scenarios.py")
    make_synthetic_segments(n=30, seed=5).to_parquet(tmp_path / "data" / "processed" / "segments.parquet")

    with pytest.raises(FileNotFoundError, match="05_run_scenarios"):
        load_saved_scenarios()
    out = CliRunner().invoke(mod.main, ["--seed", "5"])
    assert out.exit_code == 0, out.output

    loaded = load_saved_scenarios()
    assert list(loaded) == list(SCENARIOS)
    for name, r in loaded.items():
        assert (default_results_dir() / name / "meta.json").exists()
        assert r.provenance["segment_source"]["kind"] == "file"
        assert r.provenance["segment_source"]["path"].endswith("segments.parquet")
        assert r.provenance["seed"] == 5


def test_app_and_scripts_use_the_shared_results_dir():
    """The path is decided once, in `default_results_dir`; no entry point joins its own."""
    root = project_root()
    for rel in ("app/streamlit_app.py", "scripts/05_run_scenarios.py", "scripts/06_export_paper_figures.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "default_results_dir" in text, rel
        assert not re.search(r"outputs_dir\(\)\s*/\s*[\"']models[\"']\s*/\s*[\"']scenarios", text), rel
        assert "run_all_scenarios" not in text or rel.startswith("scripts/"), rel


def test_app_does_not_import_from_tests():
    for p in (project_root() / "app").rglob("*.py"):
        assert "tests.fixtures" not in p.read_text(encoding="utf-8"), p


# --- finding 21: generated report assets ---------------------------------------------------

def _cells(tex: str, label: str) -> list[str]:
    line = next(l for l in tex.splitlines() if l.startswith(label))
    return [c.strip().rstrip("\\").strip() for c in line.split("&")[1:]]


def test_scenario_table_values_come_from_the_comparison_table(results):
    table = comparison_table(results)
    tex = scenario_comparison_tex(table)
    for label, key, _ in table_rows():
        cells = _cells(tex, label)
        assert len(cells) == len(table.columns)
        for cell, col in zip(cells, table.columns):
            number = re.sub(r"[^0-9.]", "", cell.replace("\\,", ""))
            decimals = len(number.split(".")[1]) if "." in number else 0
            v = float(table.loc[key, col])
            scale = 1e6 if "M" in cell else 1.0
            # Within half a unit of the last printed digit.
            tol = 0.5 * 10 ** -decimals * scale + 1e-9
            assert float(number) * scale == pytest.approx(abs(v), abs=tol), (label, col, cell)
    assert tex.count("\\textbf{") == 1 + len(table.columns)


def test_scenario_table_prints_surplus_plus_revenue_and_no_net(results):
    """Audit 2026-10-16 finding 3: one labelled row for parkers' surplus + revenue (a partial
    welfare object), the search cost labelled with the level it is scored at, no "first
    order", no DWL row, and nothing printed as a net of the two."""
    from phillyparking.welfare.search_cost import load_search_cost_config
    table = comparison_table(results)
    tex = scenario_comparison_tex(table)
    labels = [lab for lab, _, _ in table_rows()]
    assert any("surplus + meter revenue" in lab and "change from status quo" in lab for lab in labels)
    assert not any("first order" in lab.lower() or "dwl" in lab.lower() or "welfare" in lab.lower() for lab in labels)
    level = load_search_cost_config().minutes_at_full_block
    assert any(f"{level:g} min per arrival at a full block" in lab for lab in labels)
    assert "first order" not in tex and "DWL" not in tex
    sq = float(table.loc["total_revenue", "status_quo"])
    for col in table.columns:
        assert table.loc["surplus_plus_revenue_change", col] == pytest.approx(
            table.loc["cs_change_total", col] + table.loc["total_revenue", col] - sq)
    assert table.loc["surplus_plus_revenue_change", "status_quo"] == pytest.approx(0.0)
    assert (table.loc["search_cost_total"] > 0).all()


def test_tracked_scenario_table_matches_tracked_comparison_csv():
    out = project_root() / "outputs"
    comp = pd.read_csv(out / "tables" / "comparison_table.csv", index_col=0)
    on_disk = (out / "reports" / "white_paper" / "tables" / "scenario_comparison.tex").read_text(encoding="utf-8")
    assert on_disk == scenario_comparison_tex(comp), (
        "scenario_comparison.tex is stale; run scripts/07_export_report_assets.py"
    )


def test_tracked_comparison_csv_accounts_for_the_pbd_share():
    comp = pd.read_csv(project_root() / "outputs" / "tables" / "comparison_table.csv", index_col=0)
    share = _raw("scenarios")["scenarios"]["full_pbd"]["rpp_policy"]["revenue_share_to_pbd"]
    claim = share * comp.loc["total_revenue", "full_pbd"]
    assert comp.loc["pbd_revenue", "full_pbd"] + comp.loc["pbd_unfunded", "full_pbd"] == pytest.approx(claim)
    assert claim > 0


def test_zone_map_draws_every_configured_box():
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig = zone_map_figure()
    try:
        rects = [p for p in fig.axes[0].patches if isinstance(p, Rectangle)]
        boxes = [z["bbox"] for z in load_config("zones")["zones"] if z.get("bbox")]
        assert len(rects) == len(boxes)
        for rect, b in zip(rects, boxes):
            assert rect.get_x() == pytest.approx(b["west"]) and rect.get_y() == pytest.approx(b["south"])
            assert rect.get_width() == pytest.approx(b["east"] - b["west"])
    finally:
        plt.close(fig)


def test_cm_sweep_chart_plots_median_of_cell_medians_by_year():
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(0)
    rows = [{"elasticity": e, "start_occupancy": m, "rule": r, "year": y, "replication": k,
             "revenue": 100.0 * (y + (r == "a")) * (1 + abs(e)) + rng.normal()}
            for e in (-0.2, -0.4, -0.6) for m in (0.6, 0.75) for r in ("a", "b") for y in (1, 2, 3) for k in range(4)]
    sweep = pd.DataFrame(rows)
    fig = cm_sweep_year_chart(sweep, "revenue")
    try:
        assert len(fig.axes) == 2
        line = next(l for l in fig.axes[0].get_lines() if l.get_label() == "a")
        sub = sweep[(sweep.start_occupancy == 0.6) & (sweep.rule == "a")]
        cell_med = sub.groupby(["elasticity", "year"])["revenue"].median().unstack("elasticity")
        assert list(line.get_xdata()) == [1, 2, 3]
        assert np.allclose(line.get_ydata(), cell_med.median(axis=1).to_numpy())
    finally:
        plt.close(fig)


def test_occupancy_and_revenue_figure_reads_saved_results(results):
    import matplotlib.pyplot as plt
    fig = occupancy_and_revenue_detail(results)
    try:
        left, right = fig.axes
        assert len(left.get_lines()) >= len(results)
        assert len(right.patches) == len(results) * len(load_config("zones")["zones"])
    finally:
        plt.close(fig)
