"""Named elasticity scenarios for revenue/welfare forecasts."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config


@dataclass
class ElasticityScenario:
    name: str
    elasticity: float
    sd: float


def _sd_lookup() -> float:
    return float(load_config("elasticity_priors")["central"]["sd"])


def get_scenario(name: str) -> ElasticityScenario:
    cfg = load_config("elasticity_priors")["scenarios"]
    if name not in cfg:
        raise KeyError(f"Unknown scenario '{name}'. Known: {list(cfg)}")
    return ElasticityScenario(name=name, elasticity=float(cfg[name]), sd=_sd_lookup())


def all_scenarios() -> list[ElasticityScenario]:
    cfg = load_config("elasticity_priors")["scenarios"]
    sd = _sd_lookup()
    return [ElasticityScenario(name=k, elasticity=float(v), sd=sd) for k, v in cfg.items()]


def apply_elasticity(
    baseline_demand: pd.DataFrame,
    new_price: pd.DataFrame,
    elasticity: float | pd.Series,
) -> pd.DataFrame:
    """Apply constant-elasticity demand: occ_new = occ_old * (p_new/p_old)^ε.

    `baseline_demand` cols: segment_id, hour_of_week, occupancy, price.
    `new_price` cols: either (segment_id, hour_of_week, price) or (zone_id, price)
    or (segment_id, price). Merged on shared keys; missing rows keep baseline price.
    """
    df = baseline_demand.copy()
    price_col = "price_usd_per_hr" if "price_usd_per_hr" in df.columns else "price"
    if price_col not in df.columns:
        raise ValueError("baseline_demand must include a 'price_usd_per_hr' (or 'price') column")

    np_in = new_price.copy()
    if "price_usd_per_hr" not in np_in.columns and "price" in np_in.columns:
        np_in = np_in.rename(columns={"price": "price_usd_per_hr"})

    join_keys = [c for c in ["segment_id", "hour_of_week", "zone_id"] if c in np_in.columns and c in df.columns]
    if not join_keys:
        raise ValueError("new_price must share at least one key column with baseline_demand")

    np_renamed = np_in[join_keys + ["price_usd_per_hr"]].rename(columns={"price_usd_per_hr": "_price_new"})
    df = df.merge(np_renamed, on=join_keys, how="left")
    df["_price_new"] = df["_price_new"].fillna(df[price_col])

    if isinstance(elasticity, pd.Series):
        eps = df["zone_id"].map(elasticity) if "zone_id" in df.columns else df["segment_id"].map(elasticity)
        eps = eps.to_numpy(dtype=float)
    else:
        eps = float(elasticity)

    p_old = df[price_col].to_numpy(dtype=float)
    p_new = df["_price_new"].to_numpy(dtype=float)
    safe_old = np.where(p_old > 0, p_old, np.nan)
    ratio = p_new / safe_old
    occ_new = df["occupancy"].to_numpy(dtype=float) * np.power(ratio, eps)
    occ_new = np.where(np.isnan(occ_new), df["occupancy"].to_numpy(dtype=float), occ_new)
    df["occupancy"] = np.clip(occ_new, 0.0, 1.0)
    df[price_col] = p_new
    return df.drop(columns=["_price_new"])
