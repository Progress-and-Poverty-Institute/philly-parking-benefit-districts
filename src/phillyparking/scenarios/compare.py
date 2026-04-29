"""Side-by-side comparison utilities for the white paper."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)


def comparison_table(results: dict) -> pd.DataFrame:
    rows = []
    for name, r in results.items():
        prices_by_zone = r.prices.groupby("zone_id")["price_usd_per_hr"].mean()
        ccc = float(prices_by_zone.get("ccc", np.nan))
        cca = float(prices_by_zone.get("cca", np.nan))
        n_at_ceiling = 0
        zones_cfg = {z["id"]: z for z in load_config("zones")["zones"]}
        for zid, p in prices_by_zone.items():
            if zid in zones_cfg and p >= zones_cfg[zid].get("ceiling", 1e9) - 1e-9:
                n_at_ceiling += 1
        rows.append({
            "scenario": name,
            "total_revenue": float(r.revenue["annual_revenue_usd"].sum()),
            "mean_price_ccc": ccc,
            "mean_price_cca": cca,
            "n_zones_at_ceiling": n_at_ceiling,
            "cruising_dwl_total": float(r.cruising_dwl["annual_dwl_usd"].sum()),
            "cs_change_total": float(r.cs_change_total),
            "gf_to_general_fund": float(r.allocation.get("general_fund_usd", 0.0)),
            "sdp_revenue": float(r.allocation.get("sdp_revenue_usd", 0.0)),
            "pbd_revenue": float(r.allocation.get("pbd_revenue_usd", 0.0)),
        })
    df = pd.DataFrame(rows).set_index("scenario").T
    return df


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
                        panel = apply_elasticity(panel, new_price_df, eps)

                        dwl_df = annual_cruising_dwl(panel, segments)
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
