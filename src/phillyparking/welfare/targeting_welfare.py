"""Welfare scorer for the Chatman-Manville sweep: search cost, consumer surplus, welfare.

A targeting rule that prices higher removes cruising and, for |elasticity| < 1, earns more:
the cruising proxy (`welfare/cruising_dwl.py`) and revenue are both monotone in price, so on
those two outcomes the rule with the higher statistic wins by construction (audit finding 4).
The question the sweep asks is whether the cruising it removes is worth the parkers it
prices off blocks and hours that had space. That needs the cost of over-pricing in the
outcome, so the sweep scores every priced block-hour on three terms, all in dollars a year:

- **search cost**: a driver checks blocks in turn; a block of K spaces whose mean occupancy
  is o is full with probability p = o^K (spaces independent), so the driver passes p/(1-p)
  full blocks. The shape is that; the level is set by `minutes_at_reference`, the expected
  search time at the reference block-hour (95% occupancy on a 10-space block), which the
  sweep varies because no Philadelphia measurement of it exists. At 85% a 10-space block is
  full one time in five, at 95% three times in five, so the cost is convex in occupancy and
  has no target in it. Arrivals are the served cars divided by the mean stay. Cost =
  arrivals x search time x value of time. Parameters are stated assumptions (`search_cost:`
  in `config/pricing_rules.yaml`).
- **consumer surplus change** against the start of the run, under the same constant
  elasticity demand the rules act on: demand q(p) = q0 (p/p0)^e, so
  dCS = -q0 p0 ((p/p0)^(1+e) - 1) / (1+e) (e != -1), or -q0 p0 ln(p/p0) at e = -1. Negative
  when the price rises. Computed on demand, not on the capacity-clipped occupancy: parkers
  who want a space at p and cannot find one pay the search cost instead.
- **revenue**: served cars x price, a transfer that counts in welfare at face value (the
  marginal cost of a curb space is zero).

welfare_change = dCS + (revenue - revenue0) - (search cost - search cost0): the change in
total surplus since the flat start price. Differences between rules on the same draw are
the sweep's result; the level depends on the start price.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phillyparking._config import load_config


@dataclass(frozen=True)
class SearchCostConfig:
    minutes_at_reference: float
    reference_occupancy: float
    reference_capacity: float
    mean_duration_hr: float
    occupancy_cap: float
    value_of_time_usd_per_hr: float


def load_search_cost_config(minutes_at_reference: float | None = None) -> SearchCostConfig:
    """The config's search cost; `minutes_at_reference` overrides the level (the sweep's axis)."""
    rules = load_config("pricing_rules")
    s = rules["search_cost"]
    minutes = s["minutes_at_reference"] if minutes_at_reference is None else minutes_at_reference
    return SearchCostConfig(
        minutes_at_reference=float(minutes),
        reference_occupancy=float(s["reference_occupancy"]),
        reference_capacity=float(s["reference_capacity"]),
        mean_duration_hr=float(s["mean_duration_hr"]),
        occupancy_cap=float(s["occupancy_cap"]),
        value_of_time_usd_per_hr=float(rules["arnott_inci"]["value_of_time_usd_per_hr"]),
    )


def _full_blocks_passed(occupancy, capacity):
    p_full = np.power(occupancy, capacity)
    return p_full / (1.0 - p_full)


def expected_search_minutes(occupancy: np.ndarray, capacity: np.ndarray,
                            cfg: SearchCostConfig) -> np.ndarray:
    """Expected minutes an arriving driver spends passing full blocks; see the module docstring.

    Equal to `minutes_at_reference` at the reference block-hour. Occupancy is capped at
    `occupancy_cap` so a full block has a finite cost (drivers give up or park elsewhere);
    capacity below 1 is treated as 1.
    """
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, cfg.occupancy_cap)
    k = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    per_block = cfg.minutes_at_reference / _full_blocks_passed(cfg.reference_occupancy,
                                                               cfg.reference_capacity)
    return per_block * _full_blocks_passed(o, k)


def search_cost_usd(occupancy: np.ndarray, capacity: np.ndarray,
                    cfg: SearchCostConfig | None = None) -> np.ndarray:
    """Search cost in dollars for one hour of one block: arrivals x search time x value of time."""
    cfg = cfg or load_search_cost_config()
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, 1.0)
    k = np.asarray(capacity, dtype=float)
    arrivals_per_hr = o * k / cfg.mean_duration_hr
    minutes = expected_search_minutes(o, k, cfg)
    return arrivals_per_hr * (minutes / 60.0) * cfg.value_of_time_usd_per_hr


def cs_change_usd(demand0: np.ndarray, price0: np.ndarray, price: np.ndarray,
                  elasticity: float, capacity: np.ndarray) -> np.ndarray:
    """Consumer surplus change in dollars for one hour of one block, from price0 to price.

    `demand0` is the demand share at `price0` (may exceed 1 when more cars want the block
    than it holds); q0 = demand0 x capacity cars. Zero where the price is unchanged.
    """
    q0 = np.asarray(demand0, dtype=float) * np.asarray(capacity, dtype=float)
    p0 = np.asarray(price0, dtype=float)
    ratio = np.asarray(price, dtype=float) / p0
    e1 = 1.0 + float(elasticity)
    if abs(e1) < 1e-12:
        return -q0 * p0 * np.log(ratio)
    return -q0 * p0 * (np.power(ratio, e1) - 1.0) / e1
