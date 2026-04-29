"""Revenue forecasting under elasticity scenarios (research doc §5.6)."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)


def revenue_per_segment_hour(
    segment_capacity,
    occupancy,
    price_usd_per_hr,
):
    return price_usd_per_hr * segment_capacity * occupancy


def _priced_hours_per_year_from_zones() -> int:
    zones = load_config("zones")["zones"]
    weeks = 52
    totals = []
    for z in zones:
        ph = z.get("priced_hours", {})
        weekly = 0
        for day_key, mult in [("weekday", 5), ("saturday", 1), ("sunday", 1)]:
            v = ph.get(day_key)
            if v is None:
                continue
            weekly += (int(v[1]) - int(v[0])) * mult
        totals.append(weekly * weeks)
    return int(np.mean(totals)) if totals else 4380


def _project_occupancy(occ: np.ndarray, p_old: np.ndarray, p_new: np.ndarray, elasticity: float) -> np.ndarray:
    factor = np.where(p_old > 0, (p_new / p_old) ** elasticity, 1.0)
    return np.clip(occ * factor, 0.0, 1.0)


def annual_revenue(
    segments: pd.DataFrame,
    occupancy_panel: pd.DataFrame,
    prices: pd.DataFrame,
    priced_hours_per_year: int | None = None,
) -> pd.DataFrame:
    if priced_hours_per_year is None:
        priced_hours_per_year = _priced_hours_per_year_from_zones()

    seg = segments[["segment_id", "capacity", "zone_id"]].copy()
    panel = occupancy_panel.drop(columns=[c for c in ("zone_id", "capacity") if c in occupancy_panel.columns]).merge(
        seg, on="segment_id", how="inner"
    )

    if "hour_band" in prices.columns:
        prices = prices.groupby("zone_id", as_index=False)["price_usd_per_hr"].mean()
    panel = panel.merge(prices[["zone_id", "price_usd_per_hr"]], on="zone_id", how="left")

    avg_occ = panel.groupby("zone_id", observed=True).agg(
        avg_occupancy=("occupancy", "mean"),
    ).reset_index()

    cap_per_zone = seg.groupby("zone_id", observed=True)["capacity"].sum().reset_index().rename(
        columns={"capacity": "zone_capacity"}
    )
    res = avg_occ.merge(cap_per_zone, on="zone_id").merge(
        prices[["zone_id", "price_usd_per_hr"]].drop_duplicates("zone_id"), on="zone_id"
    )
    res["capacity_hours"] = res["zone_capacity"] * priced_hours_per_year
    res["paid_hours"] = res["capacity_hours"] * res["avg_occupancy"]
    res["annual_revenue_usd"] = res["paid_hours"] * res["price_usd_per_hr"]
    return res[["zone_id", "capacity_hours", "paid_hours", "annual_revenue_usd"]]


def revenue_under_scenarios(
    segments: pd.DataFrame,
    baseline_panel: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    new_prices: pd.DataFrame,
    scenario_names: list[str] | None = None,
    n_bootstrap: int = 200,
    seed: int = 42,
    priced_hours_per_year: int | None = None,
) -> pd.DataFrame:
    if priced_hours_per_year is None:
        priced_hours_per_year = _priced_hours_per_year_from_zones()
    priors = load_config("elasticity_priors")["scenarios"]
    if scenario_names is None:
        scenario_names = list(priors.keys())

    seg = segments[["segment_id", "capacity", "zone_id"]].copy()
    panel = baseline_panel.merge(seg, on="segment_id", how="inner")
    panel = panel.merge(baseline_prices[["zone_id", "price_usd_per_hr"]].rename(
        columns={"price_usd_per_hr": "p_old"}
    ), on="zone_id", how="left")
    panel = panel.merge(new_prices[["zone_id", "price_usd_per_hr"]].rename(
        columns={"price_usd_per_hr": "p_new"}
    ), on="zone_id", how="left")

    rng = np.random.default_rng(seed)
    rows = []
    for sc in scenario_names:
        eps = float(priors[sc])
        p_old = panel["p_old"].to_numpy()
        p_new = panel["p_new"].to_numpy()
        occ_new = _project_occupancy(panel["occupancy"].to_numpy(), p_old, p_new, eps)

        boots = []
        for _ in range(n_bootstrap):
            noise = rng.normal(0, 0.03, size=occ_new.shape)
            occ_b = np.clip(occ_new + noise, 0.0, 1.0)
            tmp = panel.assign(occ_b=occ_b)
            agg = tmp.groupby("zone_id", observed=True).apply(
                lambda g: float((g["occ_b"] * g["capacity"]).mean() * g["p_new"].iloc[0] * priced_hours_per_year * len(g["segment_id"].unique()))
                / max(len(g["segment_id"].unique()), 1)
            )
            boots.append(agg)
        boot_df = pd.concat(boots, axis=1)
        for zone_id in boot_df.index:
            vals = boot_df.loc[zone_id].to_numpy()
            rows.append({
                "scenario": sc,
                "zone_id": zone_id,
                "revenue_mean": float(vals.mean()),
                "revenue_lo": float(np.quantile(vals, 0.05)),
                "revenue_hi": float(np.quantile(vals, 0.95)),
            })
    return pd.DataFrame(rows)


def revenue_curve(
    segments: pd.DataFrame,
    baseline_panel: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    elasticity: float,
    price_multiplier_grid: np.ndarray | None = None,
    priced_hours_per_year: int | None = None,
) -> pd.DataFrame:
    if price_multiplier_grid is None:
        price_multiplier_grid = np.linspace(0.5, 3.0, 26)
    if priced_hours_per_year is None:
        priced_hours_per_year = _priced_hours_per_year_from_zones()

    seg = segments[["segment_id", "capacity", "zone_id"]].copy()
    panel = baseline_panel.merge(seg, on="segment_id", how="inner")
    panel = panel.merge(baseline_prices[["zone_id", "price_usd_per_hr"]], on="zone_id", how="left")

    rows = []
    for m in price_multiplier_grid:
        p_old = panel["price_usd_per_hr"].to_numpy()
        p_new = p_old * m
        occ_new = _project_occupancy(panel["occupancy"].to_numpy(), p_old, p_new, elasticity)
        tmp = panel.assign(occ_new=occ_new, p_new=p_new)
        agg = tmp.groupby("zone_id", observed=True).agg(
            expected_occupancy=("occ_new", "mean"),
            price=("p_new", "first"),
            zone_capacity=("capacity", lambda c: c.unique().sum() if False else None),
        ).reset_index()
        zone_cap = seg.groupby("zone_id", observed=True)["capacity"].sum().reset_index().rename(
            columns={"capacity": "zone_capacity"}
        )
        agg = agg.drop(columns=["zone_capacity"]).merge(zone_cap, on="zone_id")
        agg["multiplier"] = float(m)
        agg["revenue"] = agg["expected_occupancy"] * agg["zone_capacity"] * agg["price"] * priced_hours_per_year
        rows.append(agg[["zone_id", "multiplier", "price", "expected_occupancy", "revenue"]])
    return pd.concat(rows, ignore_index=True)
