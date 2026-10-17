"""Side-by-side comparison utilities for the white paper."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import zone_mean_price

logger = logging.getLogger(__name__)


def _table_column(prices_by_zone: dict, total_revenue: float, search_total: float, cs_total: float,
                  allocation: dict, review_year, converged: bool, revenue_reference: float) -> dict:
    zones_cfg = {z["id"]: z for z in load_config("zones")["zones"]}
    n_at_ceiling = sum(
        1 for zid, p in prices_by_zone.items()
        if zid in zones_cfg and p >= zones_cfg[zid].get("ceiling", 1e9) - 1e-9
    )
    return {
        "total_revenue": float(total_revenue),
        "mean_price_ccc": float(prices_by_zone.get("ccc", np.nan)),
        "mean_price_cca": float(prices_by_zone.get("cca", np.nan)),
        "n_zones_at_ceiling": n_at_ceiling,
        "search_cost_total": float(search_total),
        "cs_change_total": float(cs_total),
        # Parkers' surplus plus meter revenue, both as changes from the status quo: a valid
        # partial welfare object (what the price change does before any search time is
        # valued). The search-cost row is at a stated level and is not netted against it.
        "surplus_plus_revenue_change": float(cs_total) + float(total_revenue) - float(revenue_reference),
        "gf_to_general_fund": float(allocation["general_fund_usd"]),
        "sdp_revenue": float(allocation["school_district_usd"]),
        "pbd_revenue": float(allocation["pbd_usd"]),
        "pbd_unfunded": float(allocation["pbd_unfunded_usd"]),
        "review_year": review_year,
        "converged": int(bool(converged)),
    }


def comparison_table(results: dict) -> pd.DataFrame:
    """Scenarios as columns. Mean prices are priced-hour-weighted across a zone's bands.

    A scenario whose prices cycle with period 2 gets one column per phase
    (`<name>_phase_a`, `<name>_phase_b`) instead of a single column, because neither
    phase is its outcome. `review_year` is the review whose state is reported.
    `surplus_plus_revenue_change` is each column's consumer-surplus change (already against
    the posted rates) plus its revenue minus the `status_quo` column's revenue; NaN when no
    `status_quo` result is given.
    """
    ref = results.get("status_quo")
    revenue_reference = float(ref.revenue["annual_revenue_usd"].sum()) if ref is not None else float("nan")
    cols = {}
    for name, r in results.items():
        d = r.diagnostics or {}
        if d.get("phases"):
            for tag, ph in zip("ab", d["phases"]):
                cols[f"{name}_phase_{tag}"] = _table_column(
                    ph["mean_price_by_zone"], ph["total_revenue"], ph["search_cost_total"],
                    ph["cs_change_total"], ph["allocation"], ph["year"], False, revenue_reference,
                )
            continue
        prices_by_zone = zone_mean_price(r.prices.dropna(subset=["price_usd_per_hr"])).to_dict()
        cols[name] = _table_column(
            prices_by_zone,
            r.revenue["annual_revenue_usd"].sum(),
            r.search_cost["annual_search_cost_usd"].sum(),
            r.cs_change_total,
            r.allocation,
            d.get("converged_year", d.get("years_run")),
            d.get("converged", False),
            revenue_reference,
        )
    return pd.DataFrame(cols)
