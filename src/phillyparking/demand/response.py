"""One demand law for every price response in the model.

The elasticity priors (`config/elasticity_priors.yaml`) are local: the elasticity of
demand at the zone's reference price, the posted rate the prior was formed for. How demand
moves away from that price is the `demand_form` in the same config, and every price response
in the package comes from here: `apply_elasticity` (the scenario runner, the app), the
revenue curve, the Arnott-Inci inversion, the Chatman-Manville sweep and its surplus term.

The form and the elasticities are stated assumptions. The priors are elasticities of occupancy
(EPO = EPD + EPV in Lehner and Peer's terms, p. 178), the quantity this module moves. The paper
supports the sign of the rise of elasticity with the price level (p. 186; the coefficient on the
price per hour relative to daily GDP per capita is negative in Table 3, EPO, and Table 5, EPV)
and nothing about its rate: it estimates no functional form, and its slope (EPV -0.03 against a
constant of -0.33) is much shallower than the exponential's proportional rise. Neither the
central value nor the pessimistic / optimistic bracket is a reported estimate of the paper
(`config/elasticity_priors.yaml` cites the intervals of its Table 6 and Fig. 3 they are informed
by). Constant elasticity
(no rise) and the exponential bracket the paper's gradient; linear rises faster than either.
`scripts/05_run_scenarios.py` and `scripts/07_export_report_assets.py
--rebuild-cm-form-sensitivity` report how the results move across the three forms below.

Forms, with q_ref the demand at the reference price p_ref and e the elasticity there:

  exponential          q(p) = q_ref exp(e (p - p_ref) / p_ref)
                       Elasticity e p / p_ref, rising in proportion to the price: the
                       semi-log demand of a logit choice model with utility linear in price
                       when the parking share is small. Revenue p q(p) peaks at p_ref / |e|.
                       The default.
  linear               q(p) = q_ref (1 + e (p - p_ref) / p_ref), zero above the choke price
                       p_ref (1 - 1/e). Elasticity rises faster than the price; revenue peaks
                       at p_ref (1 - e) / (2 |e|).
  constant_elasticity  q(p) = q_ref (p / p_ref)^e. Elasticity e at every price; for |e| < 1
                       revenue rises without bound, so a revenue curve has no peak.

Every form is path independent: moving from p_old to p_new multiplies demand by
`demand_factor`, which depends on the two prices and p_ref only. Consumer surplus change is
the exact integral -int_{p_ref}^{p} q(x) dx of the same law, in closed form.

**Where the elasticity is anchored.** The scenario runner applies the prior at each zone's own
posted rate (`reference_price=` the posted rates): e = -0.60 is the elasticity at $1.50 in
Fishtown and at $4.00 in Center City Core, so the zones do not share one demand curve. The
alternative is one citywide law anchored at a single reference price p0 with elasticity e
there; `citywide_zone_elasticities` gives each zone's elasticity at its posted rate under it,
and passing that as the run's elasticity makes the zone-anchored machinery follow the single
law exactly (for every form, re-anchoring a law at another price on the same curve leaves the
curve unchanged).
"""
from __future__ import annotations

import numpy as np

from phillyparking._config import load_config

FORMS = ("exponential", "linear", "constant_elasticity")


def load_demand_form() -> str:
    form = str(load_config("elasticity_priors").get("demand_form", "exponential"))
    if form not in FORMS:
        raise ValueError(f"demand_form must be one of {FORMS}, not {form!r}")
    return form


def _arrays(*xs):
    return [np.asarray(x, dtype=float) for x in xs]


def demand_level(p, elasticity, p_ref, form: str | None = None) -> np.ndarray:
    """q(p) / q_ref: demand at `p` relative to demand at the reference price.

    `elasticity` may be a scalar or one value per element of `p`.
    """
    form = form or load_demand_form()
    p, p_ref, e = _arrays(p, p_ref, elasticity)
    if form == "exponential":
        return np.exp(e * (p - p_ref) / p_ref)
    if form == "linear":
        return np.maximum(1.0 + e * (p - p_ref) / p_ref, 0.0)
    if form == "constant_elasticity":
        return np.power(p / p_ref, e)
    raise ValueError(f"unknown demand form {form!r}")


def demand_factor(p_new, p_old, elasticity, p_ref, form: str | None = None) -> np.ndarray:
    """q(p_new) / q(p_old): what to multiply current demand by when the price moves.

    Where demand at p_old is zero (linear form above the choke) the factor is the ratio of
    levels from the reference instead, so demand can return when the price falls.
    """
    form = form or load_demand_form()
    new, old = demand_level(p_new, elasticity, p_ref, form), demand_level(p_old, elasticity, p_ref, form)
    return np.where(old > 0, new / np.where(old > 0, old, 1.0), new)


def price_for_demand_ratio(ratio, p_old, elasticity, p_ref, form: str | None = None) -> np.ndarray:
    """The price at which demand is `ratio` times its level at `p_old` (the inverse law)."""
    form = form or load_demand_form()
    ratio, p_old, p_ref, e = _arrays(ratio, p_old, p_ref, elasticity)
    if form == "exponential":
        return p_old + p_ref * np.log(ratio) / e
    if form == "linear":
        level_old = demand_level(p_old, e, p_ref, form)
        return p_ref + (ratio * level_old - 1.0) * p_ref / e
    if form == "constant_elasticity":
        return p_old * np.power(ratio, 1.0 / e)
    raise ValueError(f"unknown demand form {form!r}")


def elasticity_at(p, elasticity, p_ref, form: str | None = None) -> np.ndarray:
    """The demand elasticity at price `p` under the law anchored at (p_ref, elasticity)."""
    form = form or load_demand_form()
    p, p_ref, e = _arrays(p, p_ref, elasticity)
    if form == "exponential":
        return e * p / p_ref
    if form == "linear":
        level = demand_level(p, e, p_ref, form)
        return np.where(level > 0, e * p / p_ref / np.where(level > 0, level, 1.0), -np.inf)
    if form == "constant_elasticity":
        return np.broadcast_to(e, np.broadcast(p, e).shape).astype(float)
    raise ValueError(f"unknown demand form {form!r}")


def citywide_zone_elasticities(posted, elasticity: float, p_ref_city: float,
                               form: str | None = None):
    """Each zone's elasticity at its posted rate under one law anchored at (p_ref_city, elasticity).

    `posted` is a (zone_id, price_usd_per_hr) frame or a Series of posted rates indexed by
    zone_id; the result is a Series indexed by zone_id. Passing it as the elasticity with
    `reference_price=` the posted rates reproduces the single law: the curve through
    (p_zone, q_zone) with local elasticity `elasticity_at(p_zone, e, p_ref_city)` is the
    single citywide curve rescaled by q_zone, for each of the three forms.
    """
    import pandas as pd
    if isinstance(posted, pd.DataFrame):
        posted = posted.set_index("zone_id")["price_usd_per_hr"]
    values = elasticity_at(posted.to_numpy(dtype=float), elasticity, p_ref_city, form)
    return pd.Series(values, index=posted.index, name="elasticity", dtype=float)


def revenue_maximising_price(elasticity: float, p_ref, form: str | None = None):
    """The price at which p q(p) peaks, or None where the law has no interior peak."""
    form = form or load_demand_form()
    e = float(elasticity)
    p_ref = float(p_ref)
    if form == "exponential":
        return -p_ref / e
    if form == "linear":
        return p_ref * (1.0 - e) / (-2.0 * e)
    if form == "constant_elasticity":
        return None if e > -1.0 else 0.0
    raise ValueError(f"unknown demand form {form!r}")


def cs_change(q_ref, p_ref, p, elasticity, form: str | None = None) -> np.ndarray:
    """Consumer surplus change from p_ref to p: -int_{p_ref}^{p} q(x) dx, with q(p_ref) = q_ref.

    Negative when the price rises. `q_ref` is in cars (demand share x capacity) for one
    hour; the result is dollars for that hour.
    """
    form = form or load_demand_form()
    q_ref, p_ref, p, e = _arrays(q_ref, p_ref, p, elasticity)
    if form == "exponential":
        a = e / p_ref
        return -q_ref * (np.exp(a * (p - p_ref)) - 1.0) / a
    if form == "linear":
        choke = p_ref * (1.0 - 1.0 / e)
        x = np.minimum(p, choke) - p_ref        # demand is zero beyond the choke price
        return -q_ref * (x + e * x * x / (2.0 * p_ref))
    if form == "constant_elasticity":
        ratio = p / p_ref
        e1 = 1.0 + e
        unit = np.abs(e1) < 1e-12                 # e = -1: the integral is a logarithm
        safe = np.where(unit, 1.0, e1)
        power = -q_ref * p_ref * (np.power(ratio, e1) - 1.0) / safe
        return np.where(unit, -q_ref * p_ref * np.log(ratio), power)
    raise ValueError(f"unknown demand form {form!r}")


def cs_change_served(q_ref, p_ref, p, elasticity, capacity, form: str | None = None) -> np.ndarray:
    """Consumer surplus change from p_ref to p counting only the cars that get a space.

    -int_{p_ref}^{p} min(q(x), capacity) dx: where the law's demand exceeds the block's
    capacity the spaces are rationed to the parkers who value them most (efficient
    rationing), so the surplus lost to a price rise on a block that stays full is exactly
    capacity x the rise, and the unserved cars carry no surplus. Equal to `cs_change` wherever
    demand is within capacity over the whole price range. Units as `cs_change`.
    """
    form = form or load_demand_form()
    q_ref, p_ref, p, e, cap = _arrays(q_ref, p_ref, p, elasticity, capacity)
    q_ref, p_ref, p, e, cap = np.broadcast_arrays(q_ref, p_ref, p, e, cap)
    lo, hi = np.minimum(p, p_ref), np.maximum(p, p_ref)
    sign = np.where(p >= p_ref, 1.0, -1.0)
    # The price below which the law's demand exceeds capacity (demand falls in price).
    with np.errstate(divide="ignore", invalid="ignore"):
        p_cap = price_for_demand_ratio(cap / q_ref, p_ref, e, p_ref, form)
    p_cap = np.where(np.isfinite(p_cap), p_cap, -np.inf)

    def integral(a, b):  # int_a^b q(x) dx under the law, for a <= b
        return cs_change(q_ref, p_ref, a, e, form) - cs_change(q_ref, p_ref, b, e, form)

    capped_to = np.clip(p_cap, lo, hi)              # [lo, capped_to] is rationed, [capped_to, hi] is not
    rationed = cap * (capped_to - lo)
    unrationed = integral(capped_to, hi)
    return -sign * (rationed + unrationed)
