"""End-to-end smoke test for the scenario pipeline."""
from __future__ import annotations

import pytest

from phillyparking.scenarios.runner import run_all_scenarios, ScenarioResults
from phillyparking.scenarios.compare import comparison_table


@pytest.mark.slow
def test_e2e_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_OUTPUTS_DIR", str(tmp_path / "outputs"))

    results = run_all_scenarios(seed=42)

    expected = {"status_quo", "seattle", "full_pbd"}
    assert expected.issubset(set(results)), f"missing: {expected - set(results)}"

    for name, r in results.items():
        total = float(r.revenue["annual_revenue_usd"].sum())
        assert total > 0, f"{name} revenue not positive: {total}"

    table = comparison_table(results)
    for name in expected:
        assert name in table.columns, f"{name} missing from comparison_table"

    save_dir = tmp_path / "scenarios"
    save_dir.mkdir()
    for name, r in results.items():
        path = save_dir / name
        r.save(path)
        loaded = ScenarioResults.load(path)
        assert loaded.name == r.name
        assert loaded.elasticity_scenario == r.elasticity_scenario
        assert abs(
            float(loaded.revenue["annual_revenue_usd"].sum())
            - float(r.revenue["annual_revenue_usd"].sum())
        ) < 1e-6
        assert loaded.allocation == r.allocation
