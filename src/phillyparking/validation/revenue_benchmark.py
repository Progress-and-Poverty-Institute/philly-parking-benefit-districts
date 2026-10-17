"""The model's status-quo meter revenue against the Parking Authority's, and the gap's factors.

Measurement only. Nothing here feeds a model input: `config/benchmarks.yaml` holds the
external figures with their citations, `revenue_benchmark` sets the model's revenue beside the
Authority's, and `revenue_identity` writes the model's revenue as an exact product of factors
so the gap can be read factor by factor.

The identity, per zone z over its priced rows (segment x hour of week in z's priced hours):

    revenue_z = spaces_z x hours_z x occupancy_z x price_z x interaction_z x paid_share

* spaces_z      capacity of z's segments (one curb side each, `spatial/segments.py`)
* hours_z       priced hours per year (`pricing.priced_hours.annual_priced_hours`)
* occupancy_z   capacity-weighted mean occupancy over the priced rows
* price_z       capacity-weighted mean posted price over the priced rows
* interaction_z mean(occupancy x price) / (mean(occupancy) x mean(price)) over the same rows
                (capacity-weighted); exactly 1 when z has one price, as the status quo does
* paid_share    1.0: `revenue.forecast` assumes full compliance

For the whole city the factors are taken over all priced zones with capacity-hours as weights:
spaces is the sum, hours the capacity-weighted mean of the zones' hours, occupancy the
capacity-hour-weighted mean, price the capacity-hour-weighted mean posted price, and the
interaction is whatever remains, i.e. the cross-zone covariance of price and occupancy. A
factor's value that would close the gap with all else equal is the model's value times
benchmark / model, because the product is linear in each factor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import annual_priced_hours, zone_priced_hours

PRIMARY = "primary"
FACTORS = (
    "priced_spaces", "annual_priced_hours", "mean_occupancy_priced_hours", "mean_posted_price",
    "price_occupancy_interaction", "paid_share",
)
NO_SOURCE = "no source found"
BENCHMARK_COLUMNS = [
    "benchmark", "role", "period", "line_name", "source_value_usd", "period_months",
    "annualised_usd", "model_status_quo_revenue_usd", "model_over_benchmark",
    "benchmark_over_model", "statement_url", "statement_page", "audited",
]
DECOMPOSITION_COLUMNS = [
    "scope", "factor", "unit", "model_value", "external_value", "external_source",
    "external_verified", "model_over_external", "value_needed_to_close_gap", "note",
]


def load_benchmarks() -> dict:
    return load_config("benchmarks")["benchmarks"]


def annualised_usd(b: dict) -> float:
    """The figure scaled to twelve months (identity for a full fiscal year)."""
    return float(b["value_usd"]) * 12.0 / float(b["period_months"])


def primary_benchmark_key() -> str:
    keys = [k for k, b in load_benchmarks().items() if b.get("role") == PRIMARY]
    if len(keys) != 1:
        raise ValueError(f"benchmarks.yaml needs exactly one role: {PRIMARY} entry, found {keys}")
    return keys[0]


def revenue_benchmark(model_revenue_usd: float) -> pd.DataFrame:
    """One row per configured benchmark: the model's status-quo revenue against it."""
    rows = []
    for key, b in load_benchmarks().items():
        ann = annualised_usd(b)
        rows.append({
            "benchmark": key,
            "role": b["role"],
            "period": b["period"],
            "line_name": b["line_name"],
            "source_value_usd": float(b["value_usd"]),
            "period_months": int(b["period_months"]),
            "annualised_usd": ann,
            "model_status_quo_revenue_usd": float(model_revenue_usd),
            "model_over_benchmark": float(model_revenue_usd) / ann,
            "benchmark_over_model": ann / float(model_revenue_usd),
            "statement_url": b["statement_url"],
            "statement_page": int(b["statement_page"]),
            "audited": bool(b["audited"]),
        })
    return pd.DataFrame(rows, columns=BENCHMARK_COLUMNS)


def revenue_identity(segments: pd.DataFrame, occupancy_panel: pd.DataFrame,
                     hourly_prices: pd.DataFrame, hours=None, paid_share: float = 1.0) -> pd.DataFrame:
    """Per zone and in total: the factors of the identity above and their product.

    `hourly_prices` is what `annual_revenue` takes (zone_id[, hour_of_week], price_usd_per_hr).
    Returns one row per priced zone plus a `total` row, with the columns of FACTORS,
    `identity_revenue_usd` (their product) and `model_revenue_usd` (`annual_revenue`); the
    two must agree, and `ValueError` says where they do not.
    """
    from phillyparking.revenue.forecast import _priced_panel, annual_revenue

    hours = zone_priced_hours() if hours is None else hours
    model = annual_revenue(segments, occupancy_panel, hourly_prices, hours).set_index("zone_id")["annual_revenue_usd"]

    priced = _priced_panel(segments, occupancy_panel, hours)
    priced = priced.drop(columns=[c for c in ("price_usd_per_hr", "price") if c in priced.columns])
    keys = ["zone_id", "hour_of_week"] if "hour_of_week" in hourly_prices.columns else ["zone_id"]
    priced = priced.merge(hourly_prices[keys + ["price_usd_per_hr"]].drop_duplicates(keys),
                          on=keys, how="left")
    if priced["price_usd_per_hr"].isna().any():
        raise ValueError("priced rows without a price; the identity needs every priced hour priced")
    cap_by_zone = segments.groupby("zone_id", observed=True)["capacity"].sum()

    rows = []
    for zid, g in priced.groupby("zone_id", observed=True):
        w = g["capacity"].to_numpy(float)
        occ, price = g["occupancy"].to_numpy(float), g["price_usd_per_hr"].to_numpy(float)
        mo, mp, mop = np.average(occ, weights=w), np.average(price, weights=w), np.average(occ * price, weights=w)
        rows.append({
            "zone_id": str(zid),
            "priced_spaces": float(cap_by_zone[zid]),
            "annual_priced_hours": float(annual_priced_hours(zid, hours)),
            "mean_occupancy_priced_hours": float(mo),
            "mean_posted_price": float(mp),
            "price_occupancy_interaction": float(mop / (mo * mp)) if mo * mp > 0 else 1.0,
            "paid_share": float(paid_share),
        })
    zones = pd.DataFrame(rows).set_index("zone_id")
    zones["identity_revenue_usd"] = zones[list(FACTORS)].prod(axis=1)
    zones["model_revenue_usd"] = model.reindex(zones.index).astype(float)

    s, h = zones["priced_spaces"], zones["annual_priced_hours"]
    ch = s * h
    total_revenue = float(model.sum())
    t = {
        "priced_spaces": float(s.sum()),
        "annual_priced_hours": float(ch.sum() / s.sum()),
        "mean_occupancy_priced_hours": float((ch * zones["mean_occupancy_priced_hours"]).sum() / ch.sum()),
        "mean_posted_price": float((ch * zones["mean_posted_price"]).sum() / ch.sum()),
        "paid_share": float(paid_share),
    }
    t["price_occupancy_interaction"] = total_revenue / (
        t["priced_spaces"] * t["annual_priced_hours"] * t["mean_occupancy_priced_hours"]
        * t["mean_posted_price"] * t["paid_share"])
    total = pd.Series(t)
    total["identity_revenue_usd"] = float(total[list(FACTORS)].prod())
    total["model_revenue_usd"] = total_revenue
    out = pd.concat([zones, total.to_frame("total").T])
    out.index.name = "scope"
    bad = out.index[~np.isclose(out["identity_revenue_usd"], out["model_revenue_usd"], rtol=1e-9, atol=1e-6)]
    if len(bad):
        raise ValueError(f"the factors do not reproduce the model's revenue for {list(bad)}")
    return out


_UNITS = {
    "priced_spaces": "spaces", "annual_priced_hours": "hours per space per year",
    "mean_occupancy_priced_hours": "share", "mean_posted_price": "usd per hour",
    "price_occupancy_interaction": "ratio", "paid_share": "share",
}
_NOTES = {
    "priced_spaces": "capacity of priced segments; one curb side (length / 7 m x 0.85)",
    "annual_priced_hours": "zones.yaml priced windows x 52 weeks; total is the capacity-weighted mean",
    "mean_occupancy_priced_hours": "stated baseline (demand_baseline.yaml), capacity-hour weighted",
    "mean_posted_price": "zones.yaml posted rates, capacity-hour weighted",
    "price_occupancy_interaction": "1 within a zone (one posted rate); city total is the cross-zone covariance",
    "paid_share": "revenue.forecast assumes full compliance",
}


def gap_decomposition(identity: pd.DataFrame, benchmark_usd: float) -> pd.DataFrame:
    """Long table: each zone's and the total's factor values; for the total, the external value
    where `gap_factors` in benchmarks.yaml has a source, else "no source found", and the value
    the factor would need, all else equal, to close the gap."""
    sources = load_config("benchmarks")["gap_factors"]
    total_model = float(identity.loc["total", "model_revenue_usd"])
    scale = benchmark_usd / total_model
    rows = []
    for scope, r in identity.iterrows():
        for f in FACTORS:
            base = {"scope": scope, "factor": f, "unit": _UNITS[f], "model_value": float(r[f]),
                    "external_value": np.nan, "external_source": "", "external_verified": "",
                    "model_over_external": np.nan, "value_needed_to_close_gap": np.nan,
                    "note": _NOTES[f]}
            if scope != "total":
                rows.append(base)
                continue
            need = float(r[f]) * scale
            base["value_needed_to_close_gap"] = need
            if f == "price_occupancy_interaction":
                base["external_source"] = "not a lever: a residual of the other factors"
                rows.append(base)
                continue
            srcs = sources.get(f, {}).get("sources") or []
            if not srcs:
                base["external_source"] = NO_SOURCE
                rows.append(base)
                continue
            for s in srcs:
                rows.append({**base, "external_value": float(s["value"]),
                             "external_source": f"{s['label']} ({s['url']})",
                             "external_verified": bool(s["verified"]),
                             "model_over_external": float(r[f]) / float(s["value"])})
    out = pd.DataFrame(rows, columns=DECOMPOSITION_COLUMNS)
    out["external_verified"] = out["external_verified"].astype(object)
    return out
