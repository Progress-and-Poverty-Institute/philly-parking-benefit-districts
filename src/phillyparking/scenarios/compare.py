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


def chatman_manville_sweep(
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    elasticity_values: list[float] | None = None,
    noise_sigmas: list[float] | None = None,
    rules: list[str] | None = None,
    n_replications: int = 50,
    rolls_forward_years: int = 5,
    seed: int = 42,
) -> pd.DataFrame:
    cfg = load_config("scenarios").get("chatman_manville_sweep", {})
    if elasticity_values is None:
        elasticity_values = cfg.get("elasticity_values", [-0.40])
    if noise_sigmas is None:
        noise_sigmas = cfg.get("demand_noise_sigma", [0.10])
    if rules is None:
        rules = cfg.get("rules", ["avg_occupancy", "min_vacancy_peak"])

    from phillyparking.spatial.synthetic import make_synthetic_segments
    from phillyparking.demand.synthetic_baseline import baseline_occupancy
    from phillyparking.elasticity.scenarios import apply_elasticity
    from phillyparking.welfare.cruising_dwl import annual_cruising_dwl
    from phillyparking.welfare.incidence import gini

    if segments is None:
        segments = make_synthetic_segments(n=20)
    if baseline_panel is None:
        baseline_panel = baseline_occupancy(segments, seed=seed)

    rng = np.random.default_rng(seed)
    rows = []
    for eps in elasticity_values:
        for sigma in noise_sigmas:
            for rule in rules:
                for rep in range(n_replications):
                    panel = baseline_panel.copy()
                    panel = panel.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
                    panel["price_usd_per_hr"] = 2.0
                    noise = rng.normal(0, sigma, size=len(panel))
                    panel["occupancy"] = np.clip(panel["occupancy"] + noise, 0.01, 0.99)

                    for year in range(1, rolls_forward_years + 1):
                        if rule == "avg_occupancy":
                            avg = panel.groupby("zone_id")["occupancy"].mean()
                            adj = avg.apply(lambda a: 0.50 if a > 0.85 else (-0.50 if a < 0.70 else 0.0))
                        else:
                            peak = panel.groupby("zone_id")["occupancy"].quantile(0.95)
                            adj = peak.apply(lambda a: 0.50 if a > 0.85 else (-0.50 if a < 0.70 else 0.0))
                        new_price_df = pd.DataFrame({
                            "zone_id": adj.index,
                            "price_usd_per_hr": panel.groupby("zone_id")["price_usd_per_hr"].first().values + adj.values,
                        })
                        new_price_df["price_usd_per_hr"] = new_price_df["price_usd_per_hr"].clip(0.5, 10.0)
                        # The sweep prices every hour by design (a uniform $2 start, no
                        # meter-off hours), so it opts out of the zones.yaml priced-hours
                        # mask the scenario runner uses.
                        panel = apply_elasticity(panel, new_price_df, eps, priced_hours_only=False)

                        dwl_df = annual_cruising_dwl(panel, segments, priced_hours_only=False)
                        revenue_total = float((panel["occupancy"] * panel["capacity"] * panel["price_usd_per_hr"]).sum() * 52.0 / 168.0 * 168.0)
                        peak_share = float((panel.groupby("zone_id")["occupancy"].quantile(0.95) > 0.85).mean())

                        rows.append({
                            "elasticity": eps,
                            "noise_sigma": sigma,
                            "rule": rule,
                            "replication": rep,
                            "year": year,
                            "cruising_dwl_total": float(dwl_df["annual_dwl_usd"].sum()),
                            "revenue_total": revenue_total,
                            "peak_occupancy_share_above_85": peak_share,
                            "consumer_surplus_change": 0.0,
                            "incidence_gini": float(gini(panel.groupby("zone_id")["price_usd_per_hr"].mean().to_numpy())),
                        })
    return pd.DataFrame(rows)
