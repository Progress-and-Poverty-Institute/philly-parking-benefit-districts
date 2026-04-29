"""PPA transactions / RPP issuances — synthetic generator with schema-faithful columns.

Real PPA dump format is unknown; the schemas here mirror plausible columns so swap-in
is mechanical: replace `load_transactions` to read a real parquet without changing
downstream code.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from phillyparking._config import data_dir

load_dotenv()
log = logging.getLogger(__name__)

TX_SCHEMA = {
    "transaction_id": "int64",
    "segment_id": "string",
    "meter_id": "string",
    "start_time": "datetime64[ns]",
    "end_time": "datetime64[ns]",
    "paid_minutes": "int32",
    "paid_amount_usd": "float64",
    "payment_method": "string",
    "rate_usd_per_hr": "float64",
}

RPP_SCHEMA = {
    "permit_id": "string",
    "rpp_zone": "string",
    "issued_date": "datetime64[ns]",
    "expires_date": "datetime64[ns]",
    "vehicle_type": "string",
    "low_income_waiver": "bool",
    "annual_fee_usd": "float64",
}


def _hour_of_week_multiplier(hour_of_week: np.ndarray) -> np.ndarray:
    """Return per-hour Poisson rate multiplier; weekday lunch peak ~3x off-peak."""
    dow = (hour_of_week // 24).astype(int)
    hod = (hour_of_week % 24).astype(int)
    mult = np.full_like(hod, 0.3, dtype=float)
    weekday = dow < 5
    saturday = dow == 5
    sunday = dow == 6
    mult = np.where(weekday & (hod >= 8) & (hod < 12), 1.5, mult)
    mult = np.where(weekday & (hod >= 12) & (hod < 14), 3.0, mult)
    mult = np.where(weekday & (hod >= 14) & (hod < 18), 1.8, mult)
    mult = np.where(weekday & (hod >= 18) & (hod < 20), 1.2, mult)
    mult = np.where(saturday & (hod >= 10) & (hod < 20), 2.0, mult)
    mult = np.where(sunday & (hod >= 11) & (hod < 18), 0.8, mult)
    mult = np.where((hod >= 22) | (hod < 6), 0.1, mult)
    return mult


def generate_transactions(
    segments: gpd.GeoDataFrame,
    n_days: int = 7,
    seed: int = 42,
    base_arrival_per_segment_hour: float = 1.5,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_hours = n_days * 24
    hours = np.arange(n_hours)
    mult = _hour_of_week_multiplier(hours)

    capacity = (
        segments["capacity"].to_numpy()
        if "capacity" in segments.columns
        else np.full(len(segments), 6)
    )
    seg_ids = segments["segment_id"].to_numpy()
    rates = (
        segments["current_rate"].to_numpy()
        if "current_rate" in segments.columns
        else np.full(len(segments), 2.5)
    )
    capacity_factor = np.clip(capacity / 6.0, 0.3, 3.0)

    rows = []
    tid = 0
    start_dt = pd.Timestamp("2024-06-03")  # Monday
    for i, seg_id in enumerate(seg_ids):
        lam = base_arrival_per_segment_hour * mult * capacity_factor[i]
        arrivals = rng.poisson(lam)
        rate_hr = float(rates[i])
        for h, n_arr in enumerate(arrivals):
            if n_arr == 0:
                continue
            offsets = rng.uniform(0, 60, n_arr)
            dwells = np.exp(rng.normal(np.log(45.0), 0.5, n_arr)).clip(5, 480)
            for off, dwell in zip(offsets, dwells):
                start = start_dt + pd.Timedelta(hours=int(h)) + pd.Timedelta(minutes=float(off))
                end = start + pd.Timedelta(minutes=float(dwell))
                paid_min = int(round(dwell))
                rows.append(
                    (
                        tid,
                        str(seg_id),
                        f"M{i:05d}",
                        start,
                        end,
                        paid_min,
                        round(paid_min / 60.0 * rate_hr, 2),
                        "meterup" if rng.random() < 0.5 else "meter",
                        rate_hr,
                    )
                )
                tid += 1

    df = pd.DataFrame(
        rows,
        columns=list(TX_SCHEMA.keys()),
    )
    if len(df):
        df["paid_minutes"] = df["paid_minutes"].astype("int32")
        df["transaction_id"] = df["transaction_id"].astype("int64")
        df["segment_id"] = df["segment_id"].astype("string")
        df["meter_id"] = df["meter_id"].astype("string")
        df["payment_method"] = df["payment_method"].astype("string")
    return df


def generate_rpp_issuances(
    rpp_zones: gpd.GeoDataFrame,
    permits_per_zone: int = 200,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    zone_col = "rpp_zone" if "rpp_zone" in rpp_zones.columns else rpp_zones.columns[0]
    rows = []
    pid = 0
    base_date = pd.Timestamp("2024-01-01")
    for z in rpp_zones[zone_col].astype(str).unique():
        for _ in range(permits_per_zone):
            issued = base_date + pd.Timedelta(days=int(rng.integers(0, 365)))
            expires = issued + pd.Timedelta(days=365)
            vtype = "motorcycle" if rng.random() < 0.05 else "car"
            waiver = bool(rng.random() < 0.1)
            fee = 0.0 if waiver else (50.0 if vtype == "motorcycle" else 75.0)
            rows.append((f"RPP{pid:07d}", str(z), issued, expires, vtype, waiver, fee))
            pid += 1
    return pd.DataFrame(rows, columns=list(RPP_SCHEMA.keys()))


def load_transactions(
    segments: gpd.GeoDataFrame | None = None, refresh: bool = False
) -> pd.DataFrame:
    src = os.environ.get("PPA_DATA_SOURCE", "stub").lower()
    if src == "real":
        path = (
            Path(os.environ.get("PPA_DATA_PATH", str(data_dir() / "raw" / "ppa")))
            / "transactions.parquet"
        )
        if path.exists():
            return pd.read_parquet(path)
        log.warning("PPA_DATA_SOURCE=real but %s missing; falling back to stub", path)
    if segments is None:
        from phillyparking.spatial.segments import load_segments

        segments = load_segments()
    return generate_transactions(segments)
