"""Hour-of-week synthetic baseline occupancy predictor.

Load-bearing while real Parking Authority data is unavailable. Hand-tuned, not fitted:
segment covariates feed a latent demand intensity and a land-use mix, time-of-week kernels
supply the temporal shape, and each segment's profile is scaled linearly between its own
off-peak floor and peak.

Every anchor is absolute (`config/demand_baseline.yaml`): covariates are standardised
against fixed centers and scales, and intensity maps to peak occupancy through fixed
bounds, so a segment's baseline does not depend on which other segments are loaded. The
centers, scales and bounds come in named anchor sets, one per kind of segment (the demo
fixture, real Philadelphia segments); the set follows the segments' recorded source. The
anchors are stated assumptions, not measurements; see the config.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)

HOURS_OF_WEEK = 168  # 7 * 24


def hour_of_week(ts: pd.Series) -> pd.Series:
    """Map a timestamp series to {0..167}, 0 = Mon 00:00."""
    ts = pd.to_datetime(ts)
    return ts.dt.dayofweek * 24 + ts.dt.hour


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


def anchor_set_for_source(segments: pd.DataFrame) -> str:
    """The anchor set for these segments, from `attrs["segment_source"]["kind"]`.

    Raises when the segments carry no recorded source (pandas drops `attrs` in some
    operations): pass `anchor_set=` explicitly then rather than guess.
    """
    src = getattr(segments, "attrs", {}).get("segment_source") or {}
    kind = src.get("kind")
    sets = load_config("demand_baseline")["source_anchor_sets"]
    if kind not in sets:
        raise ValueError(
            f"baseline anchors: segments have source kind {kind!r}, which has no anchor set in "
            f"config/demand_baseline.yaml source_anchor_sets ({sorted(sets)}); pass anchor_set="
        )
    return sets[kind]


def baseline_anchors(anchor_set: str) -> dict:
    """The config with the named set's centers, scales and intensity bounds filled in."""
    cfg = load_config("demand_baseline")
    if anchor_set not in cfg["anchor_sets"]:
        raise KeyError(f"No anchor set {anchor_set!r} in config/demand_baseline.yaml "
                       f"(have {sorted(cfg['anchor_sets'])})")
    a = cfg["anchor_sets"][anchor_set]
    covariates = {c: {**w, "center": a["centers"][c], "scale": a["scales"][c]}
                  for c, w in cfg["covariates"].items()}
    return {**{k: v for k, v in cfg.items() if k not in ("anchor_sets", "source_anchor_sets")},
            "covariates": covariates, "intensity_low": a["intensity_low"],
            "intensity_high": a["intensity_high"], "anchor_set": anchor_set}


def _resolve_anchors(segments: pd.DataFrame, anchors: dict | None,
                     anchor_set: str | None) -> dict:
    if anchors is not None:
        return anchors
    return baseline_anchors(anchor_set or anchor_set_for_source(segments))


def _z(seg_features: pd.DataFrame, col: str, anchors: dict) -> np.ndarray:
    a = anchors["covariates"][col]
    x = seg_features[col].to_numpy(dtype=float)
    if np.isnan(x).any():
        raise ValueError(f"baseline_occupancy: {int(np.isnan(x).sum())} segments have NaN {col}")
    return (np.log1p(x) - float(a["center"])) / float(a["scale"])


def _mix_weights(seg_features: pd.DataFrame, temperature: float, anchors: dict) -> np.ndarray:
    """Per-segment soft mix over (office, retail, residential). Shape (n, 3).

    Each column is mix_weight x (log1p(covariate) - center), so the mix of a segment does not
    depend on the others. `temperature` > 1 sharpens the softmax.
    """
    cov = anchors["covariates"]
    raw = np.column_stack([
        float(cov[c]["mix_weight"]) * (np.log1p(seg_features[c].to_numpy(dtype=float))
                                       - float(cov[c]["center"]))
        for c in ("jobs_within_200m", "pois_count", "pop_density")
    ])
    e = np.exp(raw * temperature)
    return e / e.sum(axis=1, keepdims=True)


def _latent_intensity(seg_features: pd.DataFrame, anchors: dict) -> np.ndarray:
    """Per-segment scalar intensity: sum of intensity_weight x anchored z-score."""
    return sum(float(a["intensity_weight"]) * _z(seg_features, c, anchors)
               for c, a in anchors["covariates"].items())


def baseline_occupancy(
    segments: pd.DataFrame,
    seed: int = 42,
    peak_target: float | None = None,
    offpeak_floor: float | None = None,
    low_demand_peak: float | None = None,
    anchors: dict | None = None,
    anchor_set: str | None = None,
) -> pd.DataFrame:
    """Tidy panel: [segment_id, hour_of_week, occupancy, occupancy_sd] of length n_seg * 168.

    Each segment's peak (and off-peak) occupancy is interpolated by its demand intensity
    between `low_demand_peak` (at `intensity_low`) and `peak_target` (at `intensity_high`).
    Levels default to `config/demand_baseline.yaml`; the anchor set is `anchor_set`, else the
    one for the segments' recorded source (`anchor_set_for_source`). The panel's
    `attrs["calibration"]` records the anchor set and the shares of segments at the cap and
    the floor.
    """
    anchors = _resolve_anchors(segments, anchors, anchor_set)
    peak_target = float(anchors["peak_target"] if peak_target is None else peak_target)
    offpeak_floor = float(anchors["offpeak_floor"] if offpeak_floor is None else offpeak_floor)
    low_demand_peak = float(anchors["low_demand_peak"] if low_demand_peak is None
                            else low_demand_peak)
    rng = np.random.default_rng(seed)
    seg = pd.DataFrame(segments).reset_index(drop=True)
    n = len(seg)

    kernels = _kernels()                 # (3, 168) — each in roughly [0, 1]
    mix = _mix_weights(seg, temperature=float(anchors["mix_temperature"]), anchors=anchors)
    kernel_intensity = mix @ kernels     # (n, 168) per-segment temporal shape

    lam = _latent_intensity(seg, anchors)
    lam_lo, lam_hi = float(anchors["intensity_low"]), float(anchors["intensity_high"])
    lam_norm = np.clip((lam - lam_lo) / (lam_hi - lam_lo), 0.0, 1.0)
    at_cap, at_floor = float((lam >= lam_hi).mean()), float((lam <= lam_lo).mean())
    if max(at_cap, at_floor) > float(anchors.get("max_clipped_share", 1.0)):
        logger.warning("baseline_occupancy: %.0f%% of segments at the peak cap and %.0f%% at the "
                       "floor; anchor set %r in config/demand_baseline.yaml does not suit "
                       "these covariates", 100 * at_cap, 100 * at_floor,
                       anchors.get("anchor_set"))

    seg_peak = low_demand_peak + (peak_target - low_demand_peak) * lam_norm
    seg_off = offpeak_floor + float(anchors["offpeak_span"]) * lam_norm

    k_max = kernel_intensity.max(axis=1)
    k_min = kernel_intensity.min(axis=1)
    span = np.maximum(k_max - k_min, 1e-6)
    slope = (seg_peak - seg_off) / span
    intercept = seg_off - slope * k_min
    occ = intercept[:, None] + slope[:, None] * kernel_intensity
    occ = np.clip(occ, 0.0, 1.0)

    sd = 0.04 + 0.02 * (1.0 - np.abs(occ - 0.5) * 2.0)
    sd = sd + rng.normal(0, 1e-9, size=sd.shape)

    rows = pd.DataFrame({
        "segment_id": np.repeat(seg["segment_id"].to_numpy(), HOURS_OF_WEEK),
        "hour_of_week": np.tile(np.arange(HOURS_OF_WEEK), n),
        "occupancy": occ.reshape(-1),
        "occupancy_sd": sd.reshape(-1),
    })
    rows.attrs["calibration"] = {"anchor_set": anchors.get("anchor_set"),
                                 "share_at_cap": at_cap, "share_at_floor": at_floor}
    return rows


def panel_cache_key(segments: pd.DataFrame, seed: int, anchor_set: str | None = None) -> str:
    """Key for a cached baseline panel: segment ids and covariates, anchors, seed."""
    import hashlib
    import json

    anchors = _resolve_anchors(segments, None, anchor_set)
    cols = ["segment_id", *anchors["covariates"]]
    body = pd.DataFrame(segments)[[c for c in cols if c in segments.columns]]
    h = hashlib.sha256(pd.util.hash_pandas_object(body, index=False).values.tobytes())
    h.update(json.dumps(anchors, sort_keys=True).encode())
    h.update(str(int(seed)).encode())
    return h.hexdigest()


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
