"""Named elasticity scenarios for revenue/welfare forecasts, and the panel-level price response."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.demand.response import demand_factor, load_demand_form


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


def _per_row(df: pd.DataFrame, table, what: str) -> np.ndarray:
    """One value per row of `df` from a scalar or a (zone_id | segment_id [, hour_of_week], price) table."""
    if np.isscalar(table):
        return np.full(len(df), float(table))
    t = table.rename(columns={"price": "price_usd_per_hr"}) if "price_usd_per_hr" not in table.columns else table
    keys = [c for c in ("segment_id", "hour_of_week", "zone_id") if c in t.columns and c in df.columns]
    if not keys:
        raise ValueError(f"{what} must share a key column with the panel")
    merged = df[keys].merge(t[keys + ["price_usd_per_hr"]].drop_duplicates(keys), on=keys, how="left")
    return merged["price_usd_per_hr"].to_numpy(dtype=float)   # NaN where the table has no row


def apply_elasticity(
    baseline_demand: pd.DataFrame,
    new_price: pd.DataFrame,
    elasticity: float | pd.Series,
    priced_hours_only: bool = True,
    reference_price=None,
) -> pd.DataFrame:
    """Move occupancy from the panel's price to `new_price` under the configured demand law.

    occ_new = occ_old x `demand.response.demand_factor(p_new, p_old, elasticity, p_ref)`:
    `elasticity` is the elasticity at the reference price p_ref (the posted rate the prior
    describes), and the form in `config/elasticity_priors.yaml` says how it changes away
    from it. `reference_price` is a scalar or a (zone_id | segment_id, price_usd_per_hr)
    table; it is required unless the form is constant elasticity, where it does not enter.

    `baseline_demand` cols: segment_id, hour_of_week, occupancy, price, and zone_id
    when `priced_hours_only` (the default).
    `new_price` cols: either (segment_id, hour_of_week, price), (zone_id, hour_of_week,
    price), (zone_id, price) or (segment_id, price). Merged on shared keys; missing rows
    keep baseline price.

    With `priced_hours_only`, occupancy responds only in the zone's priced hours
    (`pricing.priced_hours`): when the meter is off, a change in the posted rate does not
    reach the driver. Pass False only for a design that prices every hour.
    """
    df = baseline_demand.copy()
    form = load_demand_form()
    if reference_price is None and form != "constant_elasticity":
        raise ValueError(f"apply_elasticity: demand form {form!r} needs reference_price, the posted "
                         "rate the elasticity applies at (a scalar or a zone/segment price table)")
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
    p_ref = p_old if reference_price is None else _per_row(df, reference_price, "reference_price")
    # A row with no reference price (a zone the table does not cover) may keep its price,
    # never move it: the response there would be undefined.
    moved = (p_new != p_old) & ~np.isnan(p_new) & ~np.isnan(p_old)
    no_ref = np.isnan(p_ref) & moved
    if no_ref.any():
        raise ValueError(f"reference_price: {int(no_ref.sum())} panel rows change price but have no "
                         "reference price (zones absent from the table)")
    ok = (p_old > 0) & (p_ref > 0)
    factor = np.ones(len(df))
    factor[ok] = demand_factor(p_new[ok], p_old[ok], eps[ok] if np.ndim(eps) else eps, p_ref[ok], form)
    occ_new = df["occupancy"].to_numpy(dtype=float) * factor
    if priced_hours_only:
        from phillyparking.pricing.priced_hours import frame_priced_mask
        occ_new = np.where(frame_priced_mask(df), occ_new, df["occupancy"].to_numpy(dtype=float))
    df["occupancy"] = np.clip(occ_new, 0.0, 1.0)
    df[price_col] = p_new
    return df.drop(columns=["_price_new"])
