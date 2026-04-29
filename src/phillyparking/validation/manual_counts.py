"""Back-test against hand-collected counts."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking._config import data_dir

logger = logging.getLogger(__name__)


def load_manual_counts(path: Path | None = None) -> pd.DataFrame:
    base = Path(path) if path is not None else data_dir() / "external"
    files = sorted(base.glob("manual_counts_*.csv"))
    if not files:
        return pd.DataFrame(columns=["segment_id", "timestamp", "observed_occupied", "capacity"])
    dfs = [pd.read_csv(f, parse_dates=["timestamp"]) for f in files]
    return pd.concat(dfs, ignore_index=True)


def _hour_of_week(ts: pd.Series) -> pd.Series:
    ts = pd.to_datetime(ts)
    return ts.dt.dayofweek * 24 + ts.dt.hour


def backtest(
    manual_counts: pd.DataFrame,
    predicted_panel: pd.DataFrame,
) -> pd.DataFrame:
    mc = manual_counts.copy()
    mc["hour_of_week"] = _hour_of_week(mc["timestamp"])
    mc["observed_occ"] = mc["observed_occupied"] / mc["capacity"]
    merged = mc.merge(
        predicted_panel[["segment_id", "hour_of_week", "occupancy", "occupancy_sd"]],
        on=["segment_id", "hour_of_week"],
        how="inner",
    ).rename(columns={"occupancy": "predicted_occ", "occupancy_sd": "predicted_sd"})
    merged["residual"] = merged["observed_occ"] - merged["predicted_occ"]
    z = 1.645
    merged["in_90pct_interval"] = (
        (merged["observed_occ"] >= merged["predicted_occ"] - z * merged["predicted_sd"]) &
        (merged["observed_occ"] <= merged["predicted_occ"] + z * merged["predicted_sd"])
    )
    return merged[["segment_id", "timestamp", "observed_occ", "predicted_occ",
                   "predicted_sd", "residual", "in_90pct_interval"]]


def backtest_summary(backtest_results: pd.DataFrame) -> dict:
    r = backtest_results["residual"].to_numpy(dtype=float)
    return {
        "n": int(len(r)),
        "bias": float(np.mean(r)) if len(r) else 0.0,
        "rmse": float(np.sqrt(np.mean(r ** 2))) if len(r) else 0.0,
        "mae": float(np.mean(np.abs(r))) if len(r) else 0.0,
        "coverage_90pct": float(backtest_results["in_90pct_interval"].mean()) if len(r) else 0.0,
    }
