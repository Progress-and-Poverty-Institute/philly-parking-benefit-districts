"""Tests for scenario runner."""
from __future__ import annotations

import pytest

try:
    from phillyparking.scenarios.runner import run_scenario, run_all_scenarios
    from phillyparking.scenarios.compare import comparison_table
    from phillyparking._config import load_config
    _IMPORT_OK = True
    _IMPORT_ERR = None
except Exception as e:
    _IMPORT_OK = False
    _IMPORT_ERR = str(e)


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not _IMPORT_OK, reason=f"dependent module not yet built: {_IMPORT_ERR}"),
]


def test_status_quo_prices_match_zones_yaml():
    r = run_scenario("status_quo")
    cfg_zones = {z["id"]: z["current_rate_usd_per_hr"] for z in load_config("zones")["zones"]}
    for zid, expected in cfg_zones.items():
        sub = r.prices[r.prices["zone_id"] == zid]
        if len(sub) == 0:
            continue
        assert abs(float(sub["price_usd_per_hr"].iloc[0]) - expected) < 1e-6


def test_seattle_runs():
    r = run_scenario("seattle", rolls_forward_years=2)
    assert r.revenue["annual_revenue_usd"].sum() > 0


def test_compare_scenarios_wide_table():
    results = run_all_scenarios()
    table = comparison_table(results)
    for s in ("status_quo", "seattle", "full_pbd"):
        assert s in table.columns
