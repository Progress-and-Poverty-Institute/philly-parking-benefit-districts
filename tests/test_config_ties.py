"""Guards that a stated constant cannot change a headline unseen (audit finding 7).

* Every tracked artifact that records the hash of the config it was made under is compared
  with the config in the tree, and the failure names the script to rerun.
* The baseline's stated occupancy levels and the search-cost level move the outputs in a known
  direction: a test of the relation, not a pin on a literal value, so it fails for a wrong
  mechanism and not for a changed number.
"""
from __future__ import annotations

import json
import shutil

import pytest
import yaml

from phillyparking._config import config_dir, load_config, outputs_dir, project_root
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios.provenance import config_hashes, config_mismatches
from phillyparking.scenarios.runner import (
    _arnott_zone_prices, _zone_current_prices, run_scenario,
)
from phillyparking.spatial.synthetic import make_synthetic_segments

SCENARIOS = ("status_quo", "seattle", "full_pbd")

# --- artifacts tied to the config that made them -------------------------------------------

SWEEP_META = project_root() / "outputs" / "tables" / "cm_sweep.meta.json"
RERUN_SWEEP = "scripts/07_export_report_assets.py --rebuild-cm-sweep"
RERUN_SCENARIOS = "scripts/05_run_scenarios.py, then 06 and 07 (the order is 05, 06, 07)"


def _saved_scenario_metas():
    base = project_root() / "outputs" / "models"
    return sorted(base.glob("*/meta.json")) if base.exists() else []


def _recorded_hashes(path):
    meta = json.loads(path.read_text(encoding="utf-8"))
    return meta["config_sha256"] if "config_sha256" in meta else meta["provenance"]["config_sha256"]


_ARTIFACTS = [(SWEEP_META, RERUN_SWEEP)] + [(p, RERUN_SCENARIOS) for p in _saved_scenario_metas()]


@pytest.mark.parametrize("path, rerun", _ARTIFACTS, ids=[p.parent.name + "/" + p.name for p, _ in _ARTIFACTS])
def test_artifact_was_made_under_the_config_in_the_tree(path, rerun):
    """Fails when a config file changed after the artifact was generated, so a regeneration
    under a different config (or a stale artifact after a config edit) cannot pass silently."""
    assert path.exists(), f"{path} is a tracked artifact and is missing; rerun {rerun}"
    stale = config_mismatches(_recorded_hashes(path))
    assert not stale, (
        f"{path.relative_to(project_root())} was made under a different config than the tree's: "
        f"{', '.join(stale)}. Rerun {rerun}.")


def test_the_artifact_guard_sees_a_changed_added_and_removed_config_file():
    recorded = dict(config_hashes())
    assert config_mismatches(recorded) == []
    broken = dict(recorded)
    broken["zones"] = "0" * 64
    broken["retired"] = "1" * 64
    del broken["scenarios"]
    assert config_mismatches(broken) == [
        "retired (no longer in the tree)", "scenarios (not recorded by the artifact)", "zones (changed)"]


def test_config_hash_ignores_line_endings(tmp_path, monkeypatch):
    cfg = tmp_path / "config"
    shutil.copytree(config_dir(), cfg)
    before = config_hashes()
    z = cfg / "zones.yaml"
    z.write_bytes(z.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))   # CRLF checkout
    monkeypatch.setenv("PHILLYPARKING_CONFIG_DIR", str(cfg))
    assert config_hashes() == before
    z.write_bytes(z.read_bytes() + b"# edited\n")
    assert config_hashes()["zones"] != before["zones"]


# --- direction of change ---------------------------------------------------------------------


@pytest.fixture
def edit_config(tmp_path, monkeypatch):
    """Copy the config to a temp directory, apply {file: {key: value}} edits, point the loader at it."""
    original = config_dir()

    def apply(edits: dict[str, dict]):
        cfg = tmp_path / "config"
        if cfg.exists():
            shutil.rmtree(cfg)
        shutil.copytree(original, cfg)
        for name, changes in edits.items():
            path = cfg / f"{name}.yaml"
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            for dotted, value in changes.items():
                node = data
                *parents, leaf = dotted.split(".")
                for k in parents:
                    node = node[k]
                assert leaf in node, f"{name}.yaml has no {dotted}"
                node[leaf] = value
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        monkeypatch.setenv("PHILLYPARKING_CONFIG_DIR", str(cfg))
        load_config.cache_clear()
    yield apply
    monkeypatch.delenv("PHILLYPARKING_CONFIG_DIR", raising=False)
    load_config.cache_clear()


@pytest.fixture(scope="module")
def segs():
    return make_synthetic_segments(n=60, seed=4)


def _baseline_outputs(segs):
    """(status-quo annual revenue, {zone: unclipped Arnott-Inci price at the first review})."""
    panel = baseline_occupancy(segs, seed=4)
    posted = _zone_current_prices()
    revenue = float(run_scenario("status_quo", segments=segs, baseline_panel=panel, seed=4)
                    .revenue["annual_revenue_usd"].sum())
    review = _arnott_zone_prices(panel, segs, posted, 0.15, -0.4, posted)
    return revenue, review.set_index("zone_id")["unclipped_price"].to_dict()


@pytest.mark.parametrize("level", ["peak_target", "low_demand_peak"])
def test_raising_a_baseline_occupancy_level_raises_baseline_revenue_and_the_arnott_price(segs, edit_config, level):
    """The levels are stated, not measured (config/demand_baseline.yaml): busier baseline curbs
    earn more at the posted rates and call for a higher rate to reach the target."""
    base = float(load_config("demand_baseline")[level])
    edit_config({"demand_baseline": {level: base}})
    rev_lo, price_lo = _baseline_outputs(segs)
    edit_config({"demand_baseline": {level: base + 0.05}})
    rev_hi, price_hi = _baseline_outputs(segs)
    assert price_lo and set(price_lo) == set(price_hi)
    assert rev_hi > rev_lo
    for zone in price_lo:
        assert price_hi[zone] > price_lo[zone], zone


def test_raising_the_search_cost_level_raises_every_scenarios_search_cost_proportionally(segs, edit_config):
    """Search cost is linear in `search_cost.cruising_minutes_at_full_block` and feeds nothing back into
    the prices, so doubling it doubles every scenario's search cost and leaves its revenue alone."""
    panel = baseline_occupancy(segs, seed=4)
    minutes = float(load_config("pricing_rules")["search_cost"]["cruising_minutes_at_full_block"])
    edit_config({"pricing_rules": {"search_cost.cruising_minutes_at_full_block": minutes}})
    lo = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    edit_config({"pricing_rules": {"search_cost.cruising_minutes_at_full_block": 2.0 * minutes}})
    hi = {n: run_scenario(n, segments=segs, baseline_panel=panel, seed=4) for n in SCENARIOS}
    for n in SCENARIOS:
        s_lo = float(lo[n].search_cost["annual_search_cost_usd"].sum())
        s_hi = float(hi[n].search_cost["annual_search_cost_usd"].sum())
        assert s_lo > 0
        assert s_hi == pytest.approx(2.0 * s_lo, rel=1e-9), n
        assert float(hi[n].revenue["annual_revenue_usd"].sum()) == pytest.approx(
            float(lo[n].revenue["annual_revenue_usd"].sum())), n
