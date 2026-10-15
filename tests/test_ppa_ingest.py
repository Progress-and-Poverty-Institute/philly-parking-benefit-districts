"""Transactions -> occupancy panel (`ingest.ppa`) on the known-answer stub export, its guards,
and the path from the panel into the scenario runner and the elasticity model."""
from __future__ import annotations

import copy
import importlib.util

import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

from phillyparking._config import load_config, project_root
from phillyparking.elasticity.identification import IdentificationError, check_identification
from phillyparking.ingest import ppa
from phillyparking.io.ppa_stub import (KNOWN_ANSWER_PERIODS, KNOWN_ANSWER_WINDOW,
                                       make_known_answer_export, write_known_answer_export)
from phillyparking.scenarios.runner import run_scenario

KEYS = ["segment_id", "period", "hour_of_week"]


def _cfg(**over):
    cfg = copy.deepcopy(dict(load_config("ppa_ingest")))
    for k, v in over.items():
        cfg[k] = v
    return cfg


def _via_file(df, loader, cfg):
    """Write a table as the export would arrive (CSV of text) and read it through the mapping."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.csv"
        df.to_csv(p, index=False)
        return loader(p, cfg)


def _run(tables=None, cfg=None, window=KNOWN_ANSWER_WINDOW):
    t = tables or make_known_answer_export()
    cfg = cfg or _cfg()
    return ppa.build_panel(_via_file(t["sessions"], ppa.load_sessions, cfg),
                           _via_file(t["inventory"], ppa.load_inventory, cfg),
                           _via_file(t["rates"], ppa.load_rates, cfg), cfg, window)


def test_known_answer_is_recovered_exactly():
    t = make_known_answer_export()
    r = _run(t)
    got = r.panel.merge(t["expected"], on=KEYS, how="left", suffixes=("", "_exp"))
    got["paid_occupancy_exp"] = got["paid_occupancy_exp"].fillna(0.0)
    assert np.allclose(got["paid_occupancy"], got["paid_occupancy_exp"], atol=1e-12)
    assert np.allclose(got["occupancy"], got["paid_occupancy"])  # unpaid_share 0
    # full grid: 4 segments x 2 periods x 168 hours, the empty block face included
    assert len(r.panel) == 4 * 2 * 168
    assert r.panel.loc[r.panel["segment_id"] == "BF-CCA-1", "occupancy"].eq(0).all()
    assert r.periods["period"].tolist() == list(KNOWN_ANSWER_PERIODS)
    cap = r.segments.set_index("segment_id")["capacity"]
    assert cap.to_dict() == {"BF-CCA-1": 3, "BF-CCA-2": 4, "BF-CCC-1": 6, "BF-UC-1": 5}
    assert r.report["segment_periods_without_sessions"] == 2


def test_posted_rate_is_carried_by_period():
    r = _run()
    rate = r.panel.groupby(["zone_id", "period"])["price_usd_per_hr"].agg(["min", "max"])
    assert (rate["min"] == rate["max"]).all()
    assert rate["min"].to_dict() == {
        ("cca", "2025-06-02"): 2.5, ("cca", "2025-07-01"): 3.5,
        ("ccc", "2025-06-02"): 3.0, ("ccc", "2025-07-01"): 4.0,
        ("ucity", "2025-06-02"): 2.0, ("ucity", "2025-07-01"): 2.0}


def test_unpaid_share_is_an_explicit_per_zone_parameter():
    base = _run()
    cfg = _cfg(unpaid_use={"unpaid_share": {"default": 0.0, "ccc": 0.25}, "source": "test"})
    r = _run(cfg=cfg)
    m = r.panel.merge(base.panel[KEYS + ["occupancy"]], on=KEYS, suffixes=("", "_base"))
    ccc = m["segment_id"] == "BF-CCC-1"
    assert np.allclose(m.loc[ccc, "occupancy"], m.loc[ccc, "occupancy_base"] / 0.75)
    assert np.allclose(m.loc[~ccc, "occupancy"], m.loc[~ccc, "occupancy_base"])
    assert r.report["unpaid_share"] == {"default": 0.0, "ccc": 0.25}


def test_unpaid_share_must_be_stated():
    with pytest.raises(ppa.PPAIngestError, match="unpaid_share"):
        _run(cfg=_cfg(unpaid_use={"source": "forgot"}))


def test_a_week_with_no_sessions_still_counts_as_observed():
    """The denominator counts calendar dates, not weeks that happen to have sessions."""
    t = make_known_answer_export()
    s = t["sessions"]
    start = pd.to_datetime(s["SessionStart"], format="%m/%d/%Y %H:%M")
    t["sessions"] = s[~start.between("2025-06-09", "2025-06-15 23:59")]  # drop week 2
    r = _run(t)
    cell = r.panel.query("segment_id == 'BF-CCC-1' and period == '2025-06-02' and hour_of_week == 12")
    assert cell["paid_occupancy"].iloc[0] == pytest.approx(0.5 * 4 / 5)  # 4 of 5 Mondays


# --- guards: each fails on an injected defect -------------------------------------------------

def test_missing_mapped_column_names_the_file_columns():
    t = make_known_answer_export()
    t["sessions"] = t["sessions"].rename(columns={"SessionStart": "StartDateTime"})
    with pytest.raises(ppa.PPAIngestError, match="StartDateTime"):
        _run(t)


def test_sessions_at_unknown_meters_raise_above_tolerance():
    t = make_known_answer_export()
    t["sessions"].loc[:5, "MeterNumber"] = "M999"
    with pytest.raises(ppa.PPAIngestError, match="not in the inventory"):
        _run(t)


def test_posted_rate_contradicting_the_schedule_raises():
    t = make_known_answer_export()
    t["sessions"]["RateApplied"] = "9.99"
    with pytest.raises(ppa.PPAIngestError, match="schedule contradicts"):
        _run(t)


def test_location_without_spaces_raises():
    t = make_known_answer_export()
    t["inventory"].loc[0, "Spaces"] = "0"
    with pytest.raises(ppa.PPAIngestError, match="positive space"):
        _run(t)


def test_unmapped_rate_area_raises():
    t = make_known_answer_export()
    t["inventory"].loc[2, "RateArea"] = "Old City"
    with pytest.raises(ppa.PPAIngestError, match="Old City"):
        _run(t)


def test_occupancy_over_capacity_raises():
    t = make_known_answer_export()
    t["inventory"].loc[t["inventory"]["MeterNumber"] == "M003", "Spaces"] = "2"
    with pytest.raises(ppa.PPAIngestError, match="exceed capacity"):
        _run(t)


def test_session_ending_before_it_starts_raises():
    t = make_known_answer_export()
    t["sessions"].loc[0, "SessionEnd"] = "01/01/2025 00:00"
    with pytest.raises(ppa.PPAIngestError, match="end at or before"):
        _run(t)


def test_zone_with_no_sessions_in_a_period_raises():
    t = make_known_answer_export()
    t["sessions"] = t["sessions"][t["sessions"]["MeterNumber"] != "M005"]
    with pytest.raises(ppa.PPAIngestError, match="no paid session at all"):
        _run(t)


def test_zone_with_no_rate_in_a_period_raises():
    t = make_known_answer_export()
    t["rates"] = t["rates"][t["rates"]["RateArea"] != "University City"]
    with pytest.raises(ppa.PPAIngestError, match="no rate in effect"):
        _run(t)


# --- into the runner and the elasticity model --------------------------------------------------

def test_latest_period_runs_through_the_scenario_runner():
    r = _run()
    segs, panel = ppa.runner_inputs(r)
    assert segs.attrs["segment_source"]["period"] == "2025-07-01"
    res = run_scenario("status_quo", segments=segs, baseline_panel=panel, seed=1)
    rev = res.revenue.set_index("zone_id")["annual_revenue_usd"]
    assert np.isfinite(rev).all() and (rev[["ccc", "cca", "ucity"]] > 0).all()


def test_period_with_rates_other_than_the_config_is_refused():
    with pytest.raises(ppa.PPAIngestError, match="differs from zones.yaml"):
        ppa.runner_inputs(_run(), period="2025-06-02")


def test_rate_change_identifies_elasticity_and_one_period_does_not():
    r = _run()
    tab = check_identification(r.panel).set_index("zone_id")["identified"]
    assert tab.to_dict() == {"cca": True, "ccc": True, "ucity": False}
    with pytest.raises(IdentificationError):
        check_identification(r.panel[r.panel["period"] == "2025-07-01"])


def _script(name):
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"),
                                                  project_root() / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scripts_03b_and_05_run_end_to_end_on_the_stub(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PHILLYPARKING_OUTPUTS_DIR", str(tmp_path / "outputs"))
    out = CliRunner().invoke(_script("03b_ingest_ppa.py").main, ["--stub"])
    assert out.exit_code == 0, out.output
    ppa_dir = tmp_path / "data" / "processed" / "ppa_stub"
    assert (ppa_dir / "meta.json").exists() and not (tmp_path / "data" / "processed" / "ppa").exists()
    out = CliRunner().invoke(_script("05_run_scenarios.py").main,
                             ["--ppa", str(ppa_dir), "--n-seeds", "0"])
    assert out.exit_code == 0, out.output
    import json

    meta = json.loads((tmp_path / "outputs" / "models" / "status_quo" / "meta.json").read_text())
    src = meta["provenance"]["segment_source"]
    assert src["kind"] == "ppa_inventory" and src["period"] == "2025-07-01"


def test_script_04_refuses_a_panel_with_one_price_per_zone(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_OUTPUTS_DIR", str(tmp_path / "outputs"))
    one = _run().panel.query("period == '2025-07-01'")
    path = tmp_path / "panel.parquet"
    one.to_parquet(path)
    mod = _script("04_fit_elasticity.py")
    out = CliRunner().invoke(mod.main, ["--panel", str(path)])
    assert out.exit_code == 1
    out = CliRunner().invoke(mod.main, ["--panel", str(path), "--allow-prior-only"])
    assert out.exit_code == 0
    summary = pd.read_parquet(tmp_path / "outputs" / "models" / "elasticity_fit" / "summary.parquet")
    assert set(summary["source"]) == {"prior_only"}


def test_write_known_answer_export_round_trips(tmp_path):
    paths = write_known_answer_export(tmp_path)
    r = ppa.ingest(_cfg(), paths["sessions"], paths["inventory"], paths["rates"],
                   window=KNOWN_ANSWER_WINDOW)
    assert r.report["sessions_unmatched"] == 0 and r.report["cells_over_capacity"] == 0
