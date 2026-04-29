"""Incidence by ACS income decile."""
from __future__ import annotations

import numpy as np
import pandas as pd


def income_deciles_from_acs(acs_bg: pd.DataFrame, n_quantiles: int = 10) -> pd.DataFrame:
    df = acs_bg[["bg_id", "median_hh_income"]].copy()
    df["decile"] = pd.qcut(df["median_hh_income"], q=n_quantiles, labels=False, duplicates="drop") + 1
    return df


def trip_origin_decile(
    trips: pd.DataFrame,
    bg_decile: pd.DataFrame,
) -> pd.DataFrame:
    return trips.merge(bg_decile[["bg_id", "decile"]], left_on="origin_bg", right_on="bg_id", how="left").drop(columns=["bg_id"])


def payment_burden_by_decile(trips_with_decile: pd.DataFrame) -> pd.DataFrame:
    df = trips_with_decile.copy()
    df["payment"] = df["parking_cost_usd"] * df.get("n_trips_per_year", 1)
    g = df.groupby("decile", as_index=False).agg(
        total_paid_usd=("payment", "sum"),
        mean_paid_per_trip=("parking_cost_usd", "mean"),
    )
    grand = g["total_paid_usd"].sum()
    g["share_of_revenue"] = g["total_paid_usd"] / grand if grand > 0 else 0.0
    return g


def cs_change_by_decile(
    trips_with_decile: pd.DataFrame,
    cs_change_per_trip: pd.Series,
) -> pd.DataFrame:
    df = trips_with_decile.copy()
    df["cs_change"] = df["trip_id"].map(cs_change_per_trip)
    return df.groupby("decile", as_index=False).agg(
        total_cs_change=("cs_change", "sum"),
        mean_cs_change=("cs_change", "mean"),
        n_trips=("trip_id", "count"),
    )


def gini(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    v = np.asarray(values, dtype=float)
    if weights is None:
        n = len(v)
        if n == 0:
            return 0.0
        sorted_v = np.sort(v)
        total = sorted_v.sum()
        if total <= 0:
            return 0.0
        idx = np.arange(1, n + 1)
        return float((2.0 * np.sum(idx * sorted_v) - (n + 1) * total) / (n * total))
    w = np.asarray(weights, dtype=float)
    order = np.argsort(v)
    v = v[order]
    w = w[order]
    cw = np.cumsum(w)
    cwv = np.cumsum(w * v)
    total_w = cw[-1]
    total_wv = cwv[-1]
    if total_wv <= 0:
        return 0.0
    lorenz = np.concatenate(([0.0], cwv / total_wv))
    pop = np.concatenate(([0.0], cw / total_w))
    trapz = getattr(np, "trapezoid", None) or np.trapz
    g = 1.0 - 2.0 * trapz(lorenz, pop)
    return float(max(g, 0.0))


def incidence_summary(
    trips_with_decile: pd.DataFrame,
    cs_change_per_trip: pd.Series,
    revenue_by_decile: pd.DataFrame | None = None,
) -> pd.DataFrame:
    df = trips_with_decile.copy()
    df["cs_change"] = df["trip_id"].map(cs_change_per_trip)
    g = df.groupby("decile", as_index=False).agg(
        n_trips=("trip_id", "count"),
        mean_income=("median_hh_income", "mean") if "median_hh_income" in df.columns else ("trip_id", "count"),
        mean_cs_change=("cs_change", "mean"),
        mean_payment=("parking_cost_usd", "mean"),
    )
    g["net_welfare_change"] = g["mean_cs_change"] - g["mean_payment"]
    if revenue_by_decile is not None:
        g = g.merge(revenue_by_decile, on="decile", how="left")
    return g
