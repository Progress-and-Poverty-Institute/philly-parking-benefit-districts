"""Seattle's transactions-to-occupancy method (research doc §3.3 / §5.4), for stub-schema
transactions (`io.ppa_stub.TX_SCHEMA`: segment_id, start_time, end_time).

Real Parking Authority exports go through `phillyparking.ingest.ppa`, which maps their
columns, carries the posted rate by calendar period and states unpaid use in config. Both
use the same session-to-clock-hour split (`ingest.ppa.explode_to_hours`).

occupancy(s, h) = paid minutes in hour-of-week h / (capacity_s x 60 x number of calendar
dates with that weekday in the data's date range) x no_pay_correction[zone]. The correction
is a required argument: there is no default in code.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking.ingest.ppa import explode_to_hours

logger = logging.getLogger(__name__)


def transactions_to_occupancy(
    transactions: pd.DataFrame,
    segments: pd.DataFrame,
    no_pay_correction: dict[str, float],
) -> pd.DataFrame:
    """Aggregate paid sessions to per-(segment, hour-of-week) occupancy.

    `no_pay_correction`: multiplier per zone_id plus a required "default" (1.0 = paid
    occupancy only). Weekday counts come from the calendar between the first and last
    session date, so a week with no sessions still counts as observed.
    """
    if no_pay_correction is None or "default" not in no_pay_correction:
        raise ValueError("no_pay_correction must be given with a 'default' entry "
                         "(1.0 = paid occupancy only)")
    seg = pd.DataFrame(segments)[["segment_id", "capacity", "zone_id"]].copy()
    seg["zone_id"] = seg["zone_id"].astype(str)
    seg["correction"] = seg["zone_id"].map(no_pay_correction).fillna(
        float(no_pay_correction["default"]))

    if len(transactions) == 0:
        return pd.DataFrame(columns=["segment_id", "hour_of_week", "occupancy",
                                     "n_paid_sessions", "n_paid_minutes"])

    tx = transactions[["segment_id", "start_time", "end_time"]].reset_index(drop=True)
    start, end = pd.to_datetime(tx["start_time"]), pd.to_datetime(tx["end_time"])
    hrs = explode_to_hours(start, end)
    hrs["segment_id"] = tx["segment_id"].to_numpy()[hrs["session"]]
    hrs["hour_of_week"] = hrs["bucket"].dt.dayofweek * 24 + hrs["bucket"].dt.hour

    dates = pd.date_range(hrs["bucket"].min().normalize(), hrs["bucket"].max().normalize(),
                          freq="D")
    n_days = np.bincount(dates.dayofweek, minlength=7)

    grp = hrs.groupby(["segment_id", "hour_of_week"]).agg(
        n_paid_minutes=("minutes", "sum"),
        n_paid_sessions=("minutes", "size"),
    ).reset_index()
    grp = grp.merge(seg[["segment_id", "capacity", "correction"]], on="segment_id", how="left")
    if grp["capacity"].isna().any():
        missing = grp.loc[grp["capacity"].isna(), "segment_id"].unique()[:5].tolist()
        raise ValueError(f"transactions on segments absent from `segments`: {missing}")
    days = n_days[grp["hour_of_week"].to_numpy() // 24]
    grp["occupancy"] = (grp["n_paid_minutes"] * grp["correction"]) / (grp["capacity"] * 60.0 * days)
    over = grp["occupancy"] > 1.0
    if over.any():
        logger.warning("%d segment-hours exceed capacity; clipped to 1", int(over.sum()))
    grp["occupancy"] = grp["occupancy"].clip(0.0, 1.0)
    return grp[["segment_id", "hour_of_week", "occupancy", "n_paid_sessions", "n_paid_minutes"]]


def occupancy_panel_from_stub(segments: pd.DataFrame, n_days: int = 28, seed: int = 42) -> pd.DataFrame:
    """Convenience: generate stub transactions, then convert to occupancy panel."""
    from phillyparking.io.ppa_stub import generate_transactions
    tx = generate_transactions(segments, n_days=n_days, seed=seed)
    return transactions_to_occupancy(tx, segments, no_pay_correction={"default": 1.0})


def hourly_to_weekly(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to mean / sd per (segment_id, hour_of_week)."""
    return panel.groupby(["segment_id", "hour_of_week"], observed=True).agg(
        occupancy_mean=("occupancy", "mean"),
        occupancy_sd=("occupancy", "std"),
        n=("occupancy", "size"),
    ).reset_index()
