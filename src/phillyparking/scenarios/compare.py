"""Side-by-side comparison utilities for the white paper."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import zone_mean_price

logger = logging.getLogger(__name__)


def _table_column(prices_by_zone: dict, total_revenue: float, dwl_total: float, cs_total: float,
                  allocation: dict, review_year, converged: bool) -> dict:
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
        "cruising_dwl_total": float(dwl_total),
        "cs_change_total": float(cs_total),
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
    """
    cols = {}
    for name, r in results.items():
        d = r.diagnostics or {}
        if d.get("phases"):
            for tag, ph in zip("ab", d["phases"]):
                cols[f"{name}_phase_{tag}"] = _table_column(
                    ph["mean_price_by_zone"], ph["total_revenue"], ph["cruising_dwl_total"],
                    ph["cs_change_total"], ph["allocation"], ph["year"], False,
                )
            continue
        prices_by_zone = zone_mean_price(r.prices.dropna(subset=["price_usd_per_hr"])).to_dict()
        cols[name] = _table_column(
            prices_by_zone,
            r.revenue["annual_revenue_usd"].sum(),
            r.cruising_dwl["annual_dwl_usd"].sum(),
            r.cs_change_total,
            r.allocation,
            d.get("converged_year", d.get("years_run")),
            d.get("converged", False),
        )
    return pd.DataFrame(cols)
