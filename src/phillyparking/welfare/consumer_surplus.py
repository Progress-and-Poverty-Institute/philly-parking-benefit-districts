"""Logsum-based consumer surplus from a nested-logit travel-mode-and-park-location model."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class NestedLogitSpec:
    nests: dict[str, list[str]]
    nest_lambda: dict[str, float]
    alpha_price: float = -0.40
    beta_walk: float = -0.10
    asc: dict[str, float] = field(default_factory=dict)


def utilities(
    spec: NestedLogitSpec,
    prices: pd.DataFrame,
    walk_times: pd.DataFrame,
    extra_features: pd.DataFrame | None = None,
) -> pd.Series:
    alts = sorted({a for nest in spec.nests.values() for a in nest})
    p = prices["price_usd"].reindex(alts).fillna(0.0)
    w = walk_times["walk_min"].reindex(alts).fillna(0.0)
    asc = pd.Series({a: spec.asc.get(a, 0.0) for a in alts})
    V = spec.alpha_price * p + spec.beta_walk * w + asc
    if extra_features is not None:
        for col in extra_features.columns:
            V = V.add(extra_features[col].reindex(alts).fillna(0.0), fill_value=0.0)
    V.name = "V"
    return V


def logsum(spec: NestedLogitSpec, V: pd.Series) -> float:
    total = 0.0
    nest_inclusive = []
    for nest_name, alts in spec.nests.items():
        lam = spec.nest_lambda[nest_name]
        v = V.reindex(alts).to_numpy(dtype=float)
        m = np.max(v / lam)
        iv = lam * (m + np.log(np.sum(np.exp(v / lam - m))))
        nest_inclusive.append(iv)
    arr = np.array(nest_inclusive, dtype=float)
    m = arr.max()
    total = m + np.log(np.sum(np.exp(arr - m)))
    return float(total)


def consumer_surplus_change(
    spec: NestedLogitSpec,
    V_before: pd.Series,
    V_after: pd.Series,
) -> float:
    return float((logsum(spec, V_after) - logsum(spec, V_before)) / (-spec.alpha_price))


def aggregate_cs_change(
    spec: NestedLogitSpec,
    baseline_choice_data: pd.DataFrame,
    scenario_choice_data: pd.DataFrame,
    weights: pd.Series | None = None,
) -> float:
    trip_ids = baseline_choice_data["trip_id"].unique()
    total = 0.0
    for tid in trip_ids:
        b = baseline_choice_data[baseline_choice_data["trip_id"] == tid].set_index("alternative")
        s = scenario_choice_data[scenario_choice_data["trip_id"] == tid].set_index("alternative")
        Vb = utilities(spec, b[["price"]].rename(columns={"price": "price_usd"}),
                       b[["walk_min"]])
        Vs = utilities(spec, s[["price"]].rename(columns={"price": "price_usd"}),
                       s[["walk_min"]])
        dcs = consumer_surplus_change(spec, Vb, Vs)
        w = float(weights.loc[tid]) if weights is not None and tid in weights.index else 1.0
        total += w * dcs
    return float(total)
