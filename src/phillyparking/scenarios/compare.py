"""Side-by-side comparison utilities for the white paper."""
from __future__ import annotations

import logging
from dataclasses import replace

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import zone_mean_price
from phillyparking.pricing.seattle_rule import load_seattle_config, zone_bounds

logger = logging.getLogger(__name__)


def _bound_counts(prices_by_zone: dict, use_zone_floors: bool) -> tuple[int, int]:
    """(zones at their floor, zones at their ceiling) for mean zone rates, against the bounds
    in force (`seattle_rule.zone_bounds`; with `use_zone_floors` False the global floor)."""
    cfg = replace(load_seattle_config(), use_zone_floors=use_zone_floors)
    known = {z["id"] for z in load_config("zones")["zones"]}
    at_floor = at_ceiling = 0
    for zid, p in prices_by_zone.items():
        if zid not in known:
            continue
        floor, ceiling = zone_bounds(zid, cfg)
        at_floor += bool(p <= floor + 1e-9)
        at_ceiling += bool(p >= ceiling - 1e-9)
    return at_floor, at_ceiling


def _table_column(prices_by_zone: dict, total_revenue: float, search_total: float, cs_total: float,
                  allocation: dict, review_year, converged: bool, revenue_reference: float,
                  use_zone_floors: bool = True) -> dict:
    n_at_floor, n_at_ceiling = _bound_counts(prices_by_zone, use_zone_floors)
    return {
        "total_revenue": float(total_revenue),
        "mean_price_ccc": float(prices_by_zone.get("ccc", np.nan)),
        "mean_price_cca": float(prices_by_zone.get("cca", np.nan)),
        "n_zones_at_floor": n_at_floor,
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
    `status_quo` result is given. `n_zones_at_floor` / `n_zones_at_ceiling` count the zones
    whose mean rate sits on the bound in force for the run (its `diagnostics["use_zone_floors"]`).
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
                    d.get("use_zone_floors", True),
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
            d.get("use_zone_floors", True),
        )
    return pd.DataFrame(cols)
