"""Revenue forecasting under elasticity scenarios (research doc §5.6)."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.demand.response import demand_factor
from phillyparking.pricing.priced_hours import (
    annual_priced_hours, frame_priced_mask, zone_priced_hours,
)

logger = logging.getLogger(__name__)


def revenue_per_segment_hour(
    segment_capacity,
    occupancy,
    price_usd_per_hr,
):
    return price_usd_per_hr * segment_capacity * occupancy


def _project_occupancy(occ: np.ndarray, p_old: np.ndarray, p_new: np.ndarray, elasticity: float,
                       p_ref: np.ndarray | None = None) -> np.ndarray:
    """Occupancy at p_new under the configured demand law; the reference price defaults to p_old."""
    ref = p_old if p_ref is None else p_ref
    ok = p_old > 0
    factor = np.ones_like(occ, dtype=float)
    factor[ok] = demand_factor(p_new[ok], p_old[ok], elasticity, ref[ok])
    return np.clip(occ * factor, 0.0, 1.0)


def _priced_panel(segments: pd.DataFrame, occupancy_panel: pd.DataFrame, hours=None) -> pd.DataFrame:
    """Panel rows in each zone's own priced hours, with segment capacity and zone_id attached."""
    seg = segments[["segment_id", "capacity", "zone_id"]]
    panel = occupancy_panel.drop(
        columns=[c for c in ("zone_id", "capacity") if c in occupancy_panel.columns]
    ).merge(seg, on="segment_id", how="inner")
    return panel.loc[frame_priced_mask(panel, hours)]


def _zone_revenue(segments: pd.DataFrame, priced: pd.DataFrame, hours=None) -> pd.DataFrame:
    """Annual revenue per zone from priced rows carrying occupancy, capacity and price.

    capacity_hours = zone spaces x the zone's own priced hours per year. Occupied (paid)
    space-hours and revenue scale that by the capacity-weighted occupancy, and the
    capacity-weighted price x occupancy, over the zone's priced rows. For a full weekly
    profile this equals 52 x the sum of occupancy x capacity (x price) over priced rows.
    Full compliance is assumed: every occupied priced space-hour pays.
    """
    hours = zone_priced_hours() if hours is None else hours
    cap = segments.groupby("zone_id", observed=True)["capacity"].sum()
    p = priced.assign(
        _oc=priced["occupancy"] * priced["capacity"],
        _ocp=priced["occupancy"] * priced["capacity"] * priced["price_usd_per_hr"],
    )
    agg = p.groupby("zone_id", observed=True).agg(
        _oc=("_oc", "sum"), _ocp=("_ocp", "sum"), _c=("capacity", "sum"),
    )
    rows = []
    for zid, zone_capacity in cap.items():
        capacity_hours = float(zone_capacity) * annual_priced_hours(zid, hours)
        if zid in agg.index and agg.loc[zid, "_c"] > 0:
            occ = agg.loc[zid, "_oc"] / agg.loc[zid, "_c"]
            rev_per_space_hour = agg.loc[zid, "_ocp"] / agg.loc[zid, "_c"]
        else:
            occ = rev_per_space_hour = 0.0
        rows.append({
            "zone_id": zid,
            "capacity_hours": capacity_hours,
            "paid_hours": capacity_hours * occ,
            "annual_revenue_usd": capacity_hours * rev_per_space_hour,
        })
    return pd.DataFrame(rows)


def annual_revenue(
    segments: pd.DataFrame,
    occupancy_panel: pd.DataFrame,
    prices: pd.DataFrame,
    hours=None,
) -> pd.DataFrame:
    """Annual meter revenue per zone over that zone's priced hours (`pricing.priced_hours`).

    `prices` is zone-level (zone_id, price_usd_per_hr) or hourly (zone_id, hour_of_week,
    price_usd_per_hr); extra columns such as segment_id are ignored. `hours` overrides the
    zones.yaml priced hours (zone_id -> priced_hours block), for tests.
    """
    priced = _priced_panel(segments, occupancy_panel, hours)
    # `prices` is the authority; a price column carried on the panel would split the merge.
    priced = priced.drop(columns=[c for c in ("price_usd_per_hr", "price") if c in priced.columns])
    keys =["zone_id", "hour_of_week"] if "hour_of_week" in prices.columns else ["zone_id"]
    zp = prices[keys + ["price_usd_per_hr"]].drop_duplicates(keys)
    priced = priced.merge(zp, on=keys, how="left")
    return _zone_revenue(segments, priced, hours)


def revenue_under_scenarios(
    segments: pd.DataFrame,
    baseline_panel: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    new_prices: pd.DataFrame,
    scenario_names: list[str] | None = None,
    n_bootstrap: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    priors = load_config("elasticity_priors")["scenarios"]
    if scenario_names is None:
        scenario_names = list(priors.keys())

    panel = _priced_panel(segments, baseline_panel)
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
                lambda g: float((g["occ_b"] * g["capacity"]).mean() * g["p_new"].iloc[0]
                                * annual_priced_hours(g.name))
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
    hours=None,
) -> pd.DataFrame:
    """Zone revenue against a uniform price multiplier, over each zone's priced hours.

    `baseline_prices` are the reference prices the elasticity applies at, so under the
    exponential form the curve peaks at p_ref / |elasticity| (`demand.response`).
    """
    if price_multiplier_grid is None:
        price_multiplier_grid = np.linspace(0.5, 3.0, 26)

    panel = _priced_panel(segments, baseline_panel, hours)
    panel = panel.merge(baseline_prices[["zone_id", "price_usd_per_hr"]], on="zone_id", how="inner")
    segs = segments[segments["zone_id"].isin(panel["zone_id"].unique())]

    rows = []
    for m in price_multiplier_grid:
        p_old = panel["price_usd_per_hr"].to_numpy()
        p_new = p_old * m
        occ_new = _project_occupancy(panel["occupancy"].to_numpy(), p_old, p_new, elasticity)
        tmp = panel.assign(occupancy=occ_new, price_usd_per_hr=p_new)
        agg = _zone_revenue(segs, tmp, hours).rename(columns={"annual_revenue_usd": "revenue"})
        agg["expected_occupancy"] = agg["paid_hours"] / agg["capacity_hours"]
        agg["price"] = agg["zone_id"].map(tmp.groupby("zone_id")["price_usd_per_hr"].first())
        agg["multiplier"] = float(m)
        rows.append(agg[["zone_id", "multiplier", "price", "expected_occupancy", "revenue"]])
    return pd.concat(rows, ignore_index=True)
