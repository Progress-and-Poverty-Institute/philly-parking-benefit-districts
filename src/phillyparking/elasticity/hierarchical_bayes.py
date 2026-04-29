"""Hierarchical Bayesian elasticity model with neighborhood partial pooling.

Three-level hierarchy: zone < neighborhood < city. The city-level mean is
anchored to the Lehner-Peer prior; with constant within-zone prices the model
gracefully shrinks zone elasticities fully to the prior.
"""
from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)


@dataclass
class ElasticityFit:
    trace: object
    zone_index: dict[str, int]
    neighborhood_index: dict[str, int]
    coords: dict
    feature_names: list[str]


def _index_map(values) -> dict[str, int]:
    uniq = list(pd.unique(values))
    return {str(v): i for i, v in enumerate(uniq)}


def fit_elasticity_model(
    panel: pd.DataFrame,
    feature_cols: list[str] | None = None,
    draws: int = 1000,
    tune: int = 1000,
    chains: int = 2,
    seed: int = 42,
    target_accept: float = 0.9,
) -> ElasticityFit:
    """Fit the hierarchical elasticity model.

    Required panel columns: segment_id, zone_id, neighborhood, hour_of_week,
    occupancy, price_usd_per_hr (+ any feature columns named in `feature_cols`).
    """
    import pymc as pm

    cfg = load_config("elasticity_priors")["hierarchy"]
    city_mu_cfg = cfg["city_mu_prior"]
    nbhd_sd_cfg = cfg["neighborhood_sd_prior"]
    zone_sd_cfg = cfg["zone_sd_prior"]

    df = panel.copy()
    df = df[(df["occupancy"] > 0) & (df["price_usd_per_hr"] > 0)]
    df["zone_id"] = df["zone_id"].astype(str)
    df["neighborhood"] = df["neighborhood"].astype(str)

    zone_index = _index_map(df["zone_id"])
    nbhd_index = _index_map(df["neighborhood"])

    # Map each zone to its neighborhood (assume one neighborhood per zone).
    zone_to_nbhd = (df.drop_duplicates("zone_id")
                      .set_index("zone_id")["neighborhood"]
                      .to_dict())
    zone_nbhd_idx = np.array([nbhd_index[zone_to_nbhd[z]] for z in zone_index], dtype=int)

    z_idx = df["zone_id"].map(zone_index).to_numpy(dtype=int)
    t_idx = df["hour_of_week"].astype(int).to_numpy()
    t_unique = np.unique(t_idx)
    t_remap = {t: i for i, t in enumerate(t_unique)}
    t_idx_remap = np.array([t_remap[t] for t in t_idx], dtype=int)

    log_occ = np.log(df["occupancy"].to_numpy(dtype=float))
    log_price = np.log(df["price_usd_per_hr"].to_numpy(dtype=float))

    feature_cols = list(feature_cols) if feature_cols else []
    X = df[feature_cols].to_numpy(dtype=float) if feature_cols else np.zeros((len(df), 0))

    n_zones = len(zone_index)
    n_nbhds = len(nbhd_index)
    n_t = len(t_unique)
    n_feat = X.shape[1]

    coords = {
        "zone": list(zone_index.keys()),
        "neighborhood": list(nbhd_index.keys()),
        "time": [int(t) for t in t_unique],
        "feature": feature_cols,
        "obs": np.arange(len(df)),
    }

    with pm.Model(coords=coords) as model:
        mu_city = pm.Normal("mu_city", mu=float(city_mu_cfg["mean"]), sigma=float(city_mu_cfg["sd"]))
        sigma_nbhd = pm.HalfNormal("sigma_nbhd", sigma=float(nbhd_sd_cfg["mean"]) + float(nbhd_sd_cfg["sd"]))
        sigma_zone = pm.HalfNormal("sigma_zone", sigma=float(zone_sd_cfg["mean"]) + float(zone_sd_cfg["sd"]))

        mu_nbhd = pm.Normal("mu_nbhd", mu=mu_city, sigma=sigma_nbhd, dims="neighborhood")
        eps_zone = pm.Normal("eps_zone", mu=mu_nbhd[zone_nbhd_idx], sigma=sigma_zone, dims="zone")

        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0, dims="zone")
        gamma = pm.Normal("gamma", mu=0.0, sigma=0.5, dims="time")
        sigma_obs = pm.HalfNormal("sigma_obs", sigma=0.5)

        mu = alpha[z_idx] + eps_zone[z_idx] * log_price + gamma[t_idx_remap]
        if n_feat > 0:
            beta = pm.Normal("beta", mu=0.0, sigma=1.0, dims="feature")
            mu = mu + pm.math.dot(X, beta)

        pm.Normal("y", mu=mu, sigma=sigma_obs, observed=log_occ)

        trace = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            target_accept=target_accept,
            progressbar=False,
        )

    return ElasticityFit(
        trace=trace,
        zone_index=zone_index,
        neighborhood_index=nbhd_index,
        coords=coords,
        feature_names=feature_cols,
    )


def posterior_zone_elasticity(fit: ElasticityFit) -> pd.DataFrame:
    """Per-zone posterior summary with mean, sd, and 94% HDI."""
    import arviz as az
    summary = az.summary(fit.trace, var_names=["eps_zone"], hdi_prob=0.94)
    rows = []
    for zone, idx in fit.zone_index.items():
        row = summary.loc[f"eps_zone[{zone}]"]
        rows.append({
            "zone_id": zone,
            "mean": float(row["mean"]),
            "sd": float(row["sd"]),
            "hdi_lo": float(row["hdi_3%"]),
            "hdi_hi": float(row["hdi_97%"]),
        })
    return pd.DataFrame(rows)


def save_fit(fit: ElasticityFit, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(fit, f)
    return path


def load_fit(path) -> ElasticityFit:
    with open(path, "rb") as f:
        return pickle.load(f)
