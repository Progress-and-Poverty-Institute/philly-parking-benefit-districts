"""Aggregate cruising deadweight loss across the network."""
from __future__ import annotations

import numpy as np
import pandas as pd


def hourly_cruising_dwl(
    occupancy_panel: pd.DataFrame,
    segments: pd.DataFrame,
    target_vacancy: float = 0.15,
    avg_cruising_minutes: float = 5.0,
    value_of_time_usd_per_hr: float = 20.0,
) -> pd.DataFrame:
    df = occupancy_panel.drop(columns=[c for c in ("capacity", "zone_id") if c in occupancy_panel.columns]).merge(
        segments[["segment_id", "capacity"]], on="segment_id", how="left"
    )
    demand = df["occupancy"].to_numpy(dtype=float) * df["capacity"].to_numpy(dtype=float)
    threshold = (1.0 - target_vacancy) * df["capacity"].to_numpy(dtype=float)
    excess = np.maximum(demand - threshold, 0.0)
    dwl = excess * (avg_cruising_minutes / 60.0) * value_of_time_usd_per_hr
    cols = ["segment_id", "hour_of_week"]
    out = df[cols].copy()
    out["demand_excess"] = excess
    out["dwl_usd"] = dwl
    return out


def annual_cruising_dwl(
    occupancy_panel: pd.DataFrame,
    segments: pd.DataFrame,
    target_vacancy: float = 0.15,
    avg_cruising_minutes: float = 5.0,
    value_of_time_usd_per_hr: float = 20.0,
    priced_weeks: int = 52,
) -> pd.DataFrame:
    hourly = hourly_cruising_dwl(
        occupancy_panel, segments, target_vacancy,
        avg_cruising_minutes, value_of_time_usd_per_hr,
    )
    weekly = hourly.groupby("segment_id", as_index=False)["dwl_usd"].sum()
    weekly["dwl_usd"] *= priced_weeks
    weekly = weekly.merge(segments[["segment_id", "zone_id"]], on="segment_id", how="left")
    out = weekly.groupby("zone_id", as_index=False)["dwl_usd"].sum()
    out = out.rename(columns={"dwl_usd": "annual_dwl_usd"})
    return out
