"""Feature engineering for occupancy ML and discrete-choice models."""
from __future__ import annotations

import numpy as np
import pandas as pd


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    if sd == 0 or pd.isna(sd):
        return s - s.mean()
    return (s - s.mean()) / sd


def segment_features(segments: pd.DataFrame) -> pd.DataFrame:
    """Numeric feature matrix indexed by segment_id."""
    df = pd.DataFrame(segments).copy()
    out = pd.DataFrame(index=df["segment_id"].to_numpy())
    out.index.name = "segment_id"
    out["log_jobs_within_200m"] = np.log1p(df["jobs_within_200m"].to_numpy())
    out["log_pois_count"] = np.log1p(df["pois_count"].to_numpy())
    out["log_pop_density"] = np.log1p(df["pop_density"].to_numpy())
    out["log_transit_freq"] = np.log1p(df["transit_trips_per_hr"].to_numpy())
    out["median_hh_income_z"] = _zscore(df["median_hh_income"]).to_numpy()
    z = df["zone_id"].astype(str).to_numpy()
    out["is_ccc"] = (z == "ccc").astype(int)
    out["is_cca"] = (z == "cca").astype(int)
    out["is_ucity"] = (z == "ucity").astype(int)
    out["is_residential"] = np.isin(z, ["south_philly", "fishtown"]).astype(int)
    return out


def time_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add hour, dow, is_weekday, is_peak, is_evening, hour_sin, hour_cos.

    Expects a 'hour_of_week' (0..167) or 'timestamp' column.
    """
    df = panel.copy()
    if "hour_of_week" in df.columns:
        how = df["hour_of_week"].to_numpy()
        dow = how // 24
        hour = how % 24
    else:
        ts = pd.to_datetime(df["timestamp"])
        dow = ts.dt.dayofweek.to_numpy()
        hour = ts.dt.hour.to_numpy()
    df["hour"] = hour
    df["dow"] = dow
    df["is_weekday"] = (dow < 5).astype(int)
    df["is_peak"] = ((dow < 5) & (hour >= 11) & (hour < 14)).astype(int)
    df["is_evening"] = ((hour >= 17) & (hour < 22)).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    return df
