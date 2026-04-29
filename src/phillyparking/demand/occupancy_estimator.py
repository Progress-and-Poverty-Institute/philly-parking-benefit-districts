"""Seattle's transactions-to-occupancy method (research doc §3.3 / §5.4).

Aggregates paid sessions into per-(segment, hour-of-week) occupancy by counting
session minutes within each clock hour and dividing by capacity * 60. A
multiplicative no-pay correction accounts for unpaid users (RPP, placards,
scofflaws).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)


def _no_pay_correction_lookup() -> dict[str, float]:
    return load_config("pricing_rules")["occupancy_estimator"]["no_pay_correction_factor"]


def _explode_session_minutes(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return one row per (session, clock-hour) with minutes spent in that hour."""
    df = transactions[["segment_id", "start_time", "end_time"]].copy()
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    df["hour_start"] = df["start_time"].dt.floor("h")
    df["hour_end"] = (df["end_time"] - pd.Timedelta(microseconds=1)).dt.floor("h")
    df["n_hours"] = ((df["hour_end"] - df["hour_start"]) // pd.Timedelta(hours=1)).astype(int) + 1

    # Repeat each row n_hours times.
    df = df.loc[df.index.repeat(df["n_hours"].to_numpy())].reset_index(drop=True)
    offsets = df.groupby(level=0).cumcount() if False else None
    # Compute the offset within each original session by using a running counter
    # per session id (approximate via cumcount over a stable session key).
    df["session_idx"] = (df["hour_start"] != df["hour_start"].shift()) | \
                        (df["segment_id"] != df["segment_id"].shift()) | \
                        (df["end_time"] != df["end_time"].shift())
    # Simpler approach: assign session id and use cumcount.
    session_id = (df["start_time"].astype("int64").astype(str) + "|" +
                  df["end_time"].astype("int64").astype(str) + "|" +
                  df["segment_id"].astype(str))
    df["__sid"] = session_id
    df["offset_h"] = df.groupby("__sid").cumcount()
    df["bucket_start"] = df["hour_start"] + pd.to_timedelta(df["offset_h"], unit="h")
    df["bucket_end"] = df["bucket_start"] + pd.Timedelta(hours=1)

    overlap_start = np.maximum(df["start_time"].to_numpy(), df["bucket_start"].to_numpy())
    overlap_end = np.minimum(df["end_time"].to_numpy(), df["bucket_end"].to_numpy())
    minutes = (overlap_end - overlap_start) / np.timedelta64(1, "m")
    df["minutes_in_hour"] = np.clip(minutes.astype(float), 0.0, 60.0)

    df["dow"] = df["bucket_start"].dt.dayofweek
    df["hour"] = df["bucket_start"].dt.hour
    df["hour_of_week"] = df["dow"] * 24 + df["hour"]
    return df[["segment_id", "hour_of_week", "minutes_in_hour", "bucket_start"]]


def transactions_to_occupancy(
    transactions: pd.DataFrame,
    segments: pd.DataFrame,
    no_pay_correction: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Aggregate paid sessions to per-(segment, hour-of-week) occupancy.

    occupancy(s, h) = sum_minutes / (capacity_s * 60 * n_observed_weeks)
    Multiplied by no_pay_correction[zone_id] (default 1.15).
    """
    correction = no_pay_correction or _no_pay_correction_lookup()
    default_corr = correction.get("default", 1.15)

    seg = pd.DataFrame(segments)[["segment_id", "capacity", "zone_id"]].copy()
    seg["zone_id"] = seg["zone_id"].astype(str)
    seg["correction"] = seg["zone_id"].map(correction).fillna(default_corr)

    if len(transactions) == 0:
        out = seg[["segment_id"]].assign(hour_of_week=0, occupancy=0.0,
                                         n_paid_sessions=0, n_paid_minutes=0.0)
        return out.iloc[0:0]

    expanded = _explode_session_minutes(transactions)

    # n_observed_weeks: number of distinct weeks in the data, used to convert
    # a per-week panel from accumulated minutes.
    n_weeks = max(1, expanded["bucket_start"].dt.isocalendar().week.nunique())

    grp = expanded.groupby(["segment_id", "hour_of_week"], observed=True).agg(
        n_paid_minutes=("minutes_in_hour", "sum"),
        n_paid_sessions=("minutes_in_hour", "size"),
    ).reset_index()

    grp = grp.merge(seg[["segment_id", "capacity", "correction"]], on="segment_id", how="left")
    grp["occupancy"] = (grp["n_paid_minutes"] * grp["correction"]) / (grp["capacity"] * 60.0 * n_weeks)
    grp["occupancy"] = grp["occupancy"].clip(0.0, 1.0)
    return grp[["segment_id", "hour_of_week", "occupancy", "n_paid_sessions", "n_paid_minutes"]]


def occupancy_panel_from_stub(segments: pd.DataFrame, n_days: int = 28, seed: int = 42) -> pd.DataFrame:
    """Convenience: generate stub transactions, then convert to occupancy panel."""
    from phillyparking.io.ppa_stub import generate_transactions
    tx = generate_transactions(segments, n_days=n_days, seed=seed)
    return transactions_to_occupancy(tx, segments)


def hourly_to_weekly(panel: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to mean / sd per (segment_id, hour_of_week)."""
    return panel.groupby(["segment_id", "hour_of_week"], observed=True).agg(
        occupancy_mean=("occupancy", "mean"),
        occupancy_sd=("occupancy", "std"),
        n=("occupancy", "size"),
    ).reset_index()
