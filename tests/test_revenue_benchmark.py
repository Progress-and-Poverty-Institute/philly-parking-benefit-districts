"""The Parking Authority revenue benchmark and the gap decomposition (measurement only).

The saved tables must match `config/benchmarks.yaml` and the saved comparison table, and the
factors must multiply back to the model's revenue. Nothing here bounds the size of the gap:
the model is not calibrated to the benchmark, so no tolerance band on the ratio is tested.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phillyparking._config import load_config, outputs_dir
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.pricing.priced_hours import hourly_prices
from phillyparking.revenue.forecast import annual_revenue
from phillyparking.scenarios.runner import _zone_current_prices
from phillyparking.spatial.synthetic import make_synthetic_segments
from phillyparking.validation.revenue_benchmark import (
    FACTORS, NO_SOURCE, annualised_usd, gap_decomposition, load_benchmarks, primary_benchmark_key,
    revenue_identity,
)

TABLES = outputs_dir() / "tables"
RERUN = "scripts/06_export_paper_figures.py (after 05)"


@pytest.fixture(scope="module")
def bench():
    path = TABLES / "revenue_benchmark.csv"
    assert path.exists(), f"{path} is missing; run {RERUN}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def decomp():
    path = TABLES / "revenue_gap_decomposition.csv"
    assert path.exists(), f"{path} is missing; run {RERUN}"
    return pd.read_csv(path)


def test_the_primary_benchmark_is_a_full_fiscal_year_with_its_citation():
    b = load_benchmarks()[primary_benchmark_key()]
    assert b["period_months"] == 12 and b["audited"] is False
    assert b["line_name"] == "Revenue - Meters" and b["statement_page"] == 1
    assert b["statement_url"].startswith("https://philapark.org/wp-content/uploads/")
    assert b["retrieved"] and b["what_it_is"] and b["what_it_is_not"] and b["mobile_payments"]
    assert annualised_usd(b) == b["value_usd"]


def test_benchmark_table_matches_the_config_and_recomputes_the_ratio(bench):
    cfg = load_benchmarks()
    assert set(bench["benchmark"]) == set(cfg)
    saved = pd.read_csv(TABLES / "comparison_table.csv", index_col=0)
    model = float(saved.loc["total_revenue", "status_quo"])
    for _, r in bench.iterrows():
        b = cfg[r["benchmark"]]
        assert r["role"] == b["role"] and r["period"] == b["period"]
        assert r["source_value_usd"] == b["value_usd"]
        assert r["statement_url"] == b["statement_url"] and r["statement_page"] == b["statement_page"]
        assert r["annualised_usd"] == pytest.approx(annualised_usd(b))
        assert r["model_status_quo_revenue_usd"] == pytest.approx(model, rel=1e-9)
        assert r["model_over_benchmark"] == pytest.approx(model / annualised_usd(b), rel=1e-12)
        assert r["benchmark_over_model"] == pytest.approx(annualised_usd(b) / model, rel=1e-12)


def test_the_factors_reproduce_the_saved_revenue_per_zone_and_in_total(decomp, bench):
    model = float(bench["model_status_quo_revenue_usd"].iloc[0])
    for scope, g in decomp.groupby("scope"):
        vals = g.drop_duplicates("factor").set_index("factor")["model_value"]
        assert set(vals.index) == set(FACTORS)
        product = float(np.prod([vals[f] for f in FACTORS]))
        if scope == "total":
            assert product == pytest.approx(model, rel=1e-9)
    zones = decomp[decomp["scope"] != "total"].pivot(index="scope", columns="factor", values="model_value")
    assert zones[list(FACTORS)].prod(axis=1).sum() == pytest.approx(model, rel=1e-9)


def test_external_values_match_the_config_and_unsourced_factors_say_so(decomp):
    cfg = load_config("benchmarks")["gap_factors"]
    total = decomp[decomp["scope"] == "total"]
    for f, spec in cfg.items():
        rows = total[total["factor"] == f]
        assert len(rows) >= 1
        if spec["sources"]:
            assert sorted(rows["external_value"]) == sorted(float(s["value"]) for s in spec["sources"])
            labels = {float(s["value"]): s["verified"] for s in spec["sources"]}
            for _, r in rows.iterrows():
                assert bool(r["external_verified"]) == labels[r["external_value"]]
                assert r["model_over_external"] == pytest.approx(r["model_value"] / r["external_value"])
        else:
            assert (rows["external_source"] == NO_SOURCE).all() and rows["external_value"].isna().all()


def test_each_needed_value_closes_the_gap_with_the_others_held(decomp, bench):
    """Replacing one factor by its needed value, the rest as modelled, gives the benchmark."""
    target = float(bench.loc[bench["role"] == "primary", "annualised_usd"].iloc[0])
    total = decomp[decomp["scope"] == "total"].drop_duplicates("factor").set_index("factor")
    model = total["model_value"]
    for f in FACTORS:
        vals = model.copy()
        vals[f] = total.loc[f, "value_needed_to_close_gap"]
        assert float(np.prod(vals.to_numpy())) == pytest.approx(target, rel=1e-9)


def test_identity_holds_when_the_price_varies_within_a_zone():
    segs = make_synthetic_segments(n=60, seed=3)
    segs = segs.assign(zone_id=np.where(np.arange(len(segs)) % 2 == 0, "ccc", "south_philly"))
    panel = baseline_occupancy(segs, seed=3, anchor_set="synthetic_fixture")
    base = hourly_prices(_zone_current_prices())
    # A price that rises with the hour of day, so price and occupancy covary inside a zone.
    prices = base.assign(price_usd_per_hr=base["price_usd_per_hr"] * (1 + (base["hour_of_week"] % 24) / 24))
    ident = revenue_identity(segs, panel, prices)
    assert ident.loc["total", "identity_revenue_usd"] == pytest.approx(
        annual_revenue(segs, panel, prices)["annual_revenue_usd"].sum(), rel=1e-9)
    assert not np.isclose(ident.loc["ccc", "price_occupancy_interaction"], 1.0, atol=1e-6)
    table = gap_decomposition(ident, benchmark_usd=1.0e6)
    assert set(table["factor"]) == set(FACTORS)
