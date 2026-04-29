"""Hour-of-week synthetic baseline occupancy predictor.

Calibrated to ~85% peak occupancy reported for Center City Philadelphia.
This module is load-bearing while real PPA transaction data is unavailable.
The model is hand-tuned (no ML libraries): segment features feed a latent
demand intensity, time-of-week kernels supply the temporal shape, and a
sigmoid keeps occupancy in [0, 1].
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HOURS_OF_WEEK = 168  # 7 * 24


def hour_of_week(ts: pd.Series) -> pd.Series:
    """Map a timestamp series to {0..167}, 0 = Mon 00:00."""
    ts = pd.to_datetime(ts)
    return ts.dt.dayofweek * 24 + ts.dt.hour


def _zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else x - x.mean()


def _logit(p: float | np.ndarray) -> float | np.ndarray:
    return np.log(p / (1.0 - p))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _office_kernel() -> np.ndarray:
    """Weekday 9-17 boost, low overnight, near-zero on Sunday."""
    k = np.zeros(HOURS_OF_WEEK)
    for d in range(7):
        for h in range(24):
            i = d * 24 + h
            if d < 5:  # Mon-Fri
                if 9 <= h < 17:
                    k[i] = 1.0 - 0.15 * abs(h - 13) / 4.0
                elif 7 <= h < 9 or 17 <= h < 19:
                    k[i] = 0.5
                else:
                    k[i] = 0.05
            elif d == 5:  # Sat
                k[i] = 0.15 if 10 <= h < 18 else 0.03
            else:  # Sun
                k[i] = 0.02
    return k


def _retail_kernel() -> np.ndarray:
    """Weekday lunch + Sat midday peaks, evening shoulder."""
    k = np.zeros(HOURS_OF_WEEK)
    for d in range(7):
        for h in range(24):
            i = d * 24 + h
            if d < 5:
                if 11 <= h < 14:
                    k[i] = 1.0
                elif 17 <= h < 22:
                    k[i] = 0.85
                elif 9 <= h < 11 or 14 <= h < 17:
                    k[i] = 0.55
                else:
                    k[i] = 0.05
            elif d == 5:
                if 11 <= h < 18:
                    k[i] = 0.95
                elif 18 <= h < 23:
                    k[i] = 0.7
                else:
                    k[i] = 0.05
            else:
                if 11 <= h < 18:
                    k[i] = 0.7
                else:
                    k[i] = 0.05
    return k


def _residential_kernel() -> np.ndarray:
    """High overnight + early morning, dips midday when residents are out."""
    k = np.zeros(HOURS_OF_WEEK)
    for d in range(7):
        for h in range(24):
            i = d * 24 + h
            if 22 <= h or h < 7:
                k[i] = 1.0
            elif 7 <= h < 9:
                k[i] = 0.85
            elif 9 <= h < 17:
                k[i] = 0.45 if d < 5 else 0.65
            else:
                k[i] = 0.7
    return k


def _kernels() -> np.ndarray:
    """Stack kernels: shape (3, 168). Order: office, retail, residential."""
    return np.vstack([_office_kernel(), _retail_kernel(), _residential_kernel()])


def _mix_weights(seg_features: pd.DataFrame, temperature: float = 1.0) -> np.ndarray:
    """Per-segment soft mix over (office, retail, residential). Shape (n, 3).

    `temperature` > 1 sharpens the softmax so dominant land-use wins more clearly.
    """
    jobs = seg_features["jobs_within_200m"].to_numpy(dtype=float)
    pois = seg_features["pois_count"].to_numpy(dtype=float)
    pop = seg_features["pop_density"].to_numpy(dtype=float)
    raw = np.column_stack([
        np.log1p(jobs),
        np.log1p(pois) * 1.2,
        np.log1p(pop) * 0.9,
    ])
    raw = raw - raw.mean(axis=0, keepdims=True)
    e = np.exp(raw * temperature)
    return e / e.sum(axis=1, keepdims=True)


def _latent_intensity(seg_features: pd.DataFrame) -> np.ndarray:
    """Per-segment scalar λ_s on the logit scale."""
    jobs_z = _zscore(np.log1p(seg_features["jobs_within_200m"].to_numpy(dtype=float)))
    pois_z = _zscore(np.log1p(seg_features["pois_count"].to_numpy(dtype=float)))
    pop_z = _zscore(np.log1p(seg_features["pop_density"].to_numpy(dtype=float)))
    transit_z = _zscore(np.log1p(seg_features["transit_trips_per_hr"].to_numpy(dtype=float)))
    return 0.55 * jobs_z + 0.35 * pois_z + 0.25 * pop_z - 0.15 * transit_z


def baseline_occupancy(
    segments: pd.DataFrame,
    seed: int = 42,
    peak_target: float = 0.92,
    offpeak_floor: float = 0.20,
    low_demand_peak: float = 0.62,
) -> pd.DataFrame:
    """Tidy panel: [segment_id, hour_of_week, occupancy, occupancy_sd] of length n_seg * 168.

    Each segment's peak (and off-peak) occupancy is interpolated by demand
    intensity, so the highest-λ segment hits `peak_target` while the lowest-λ
    segment still hits a plausible commercial-corridor peak (`low_demand_peak`,
    default 0.62 — anchored to literature for non-CBD priced zones).
    """
    rng = np.random.default_rng(seed)
    seg = pd.DataFrame(segments).reset_index(drop=True)
    n = len(seg)

    kernels = _kernels()                 # (3, 168) — each in roughly [0, 1]
    mix = _mix_weights(seg, temperature=2.5)   # (n, 3) sharpened softmax
    kernel_intensity = mix @ kernels     # (n, 168) per-segment temporal shape

    lam = _latent_intensity(seg)         # (n,) z-scored
    lam_lo, lam_hi = np.quantile(lam, [0.05, 0.95])
    lam_norm = np.clip((lam - lam_lo) / max(lam_hi - lam_lo, 1e-6), 0.0, 1.0)

    seg_peak = low_demand_peak + (peak_target - low_demand_peak) * lam_norm
    seg_off = offpeak_floor + 0.10 * lam_norm

    k_max = kernel_intensity.max(axis=1)
    k_min = kernel_intensity.min(axis=1)
    span = np.maximum(k_max - k_min, 1e-6)
    slope = (seg_peak - seg_off) / span
    intercept = seg_off - slope * k_min
    occ = intercept[:, None] + slope[:, None] * kernel_intensity
    occ = np.clip(occ, 0.0, 0.99)

    sd = 0.04 + 0.02 * (1.0 - np.abs(occ - 0.5) * 2.0)
    sd = sd + rng.normal(0, 1e-9, size=sd.shape)

    rows = pd.DataFrame({
        "segment_id": np.repeat(seg["segment_id"].to_numpy(), HOURS_OF_WEEK),
        "hour_of_week": np.tile(np.arange(HOURS_OF_WEEK), n),
        "occupancy": occ.reshape(-1),
        "occupancy_sd": sd.reshape(-1),
    })
    return rows


def expand_panel(
    segments: pd.DataFrame,
    occupancy_panel: pd.DataFrame,
    start_date: str = "2025-01-06",
    n_weeks: int = 4,
    add_noise: bool = True,
    noise_sigma: float = 0.05,
    seed: int = 42,
) -> pd.DataFrame:
    """Expand {segment x hour-of-week} to {segment x timestamp} for n_weeks."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp(start_date)
    timestamps = pd.date_range(start, periods=HOURS_OF_WEEK * n_weeks, freq="h")
    hours_of_week = (timestamps.dayofweek * 24 + timestamps.hour).to_numpy()

    base = occupancy_panel.set_index(["segment_id", "hour_of_week"])["occupancy"].unstack("hour_of_week")
    base = base.loc[segments["segment_id"].to_numpy()]

    occ_by_time = base.to_numpy()[:, hours_of_week]  # (n_seg, n_hours)

    if add_noise:
        eps = rng.normal(0, noise_sigma, size=occ_by_time.shape)
        z = _logit(np.clip(occ_by_time, 1e-4, 1 - 1e-4)) + eps
        occ_by_time = _sigmoid(z)

    occ_by_time = np.clip(occ_by_time, 0.0, 1.0)
    n_seg, n_t = occ_by_time.shape
    return pd.DataFrame({
        "segment_id": np.repeat(segments["segment_id"].to_numpy(), n_t),
        "timestamp": np.tile(timestamps.to_numpy(), n_seg),
        "hour_of_week": np.tile(hours_of_week, n_seg),
        "occupancy": occ_by_time.reshape(-1),
    })
