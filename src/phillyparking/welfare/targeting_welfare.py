"""Welfare scorer for the Chatman-Manville sweep: search cost, consumer surplus, welfare.

A targeting rule that prices higher removes cruising and, up to the revenue peak, earns
more: search cost falls in price and revenue rises in it, so on those two outcomes the rule
with the higher statistic wins by construction. The question the sweep asks is whether the
cruising it removes is worth the parkers it prices off blocks and hours that had space. That
needs the cost of over-pricing in the outcome, so the sweep scores every priced block-hour
on three terms, all in dollars a year and all counting the same population, the cars that
park:

- **search cost**: the project's cruising model (`welfare/search_cost.py`): served arrivals
  x the expected minutes spent passing full blocks x the value of time. Its level is
  `cruising_minutes_at_full_block` and its cap `occupancy_cap` (`search_cost:` in
  `config/pricing_rules.yaml`); the sweep varies the cap and reports the level at which
  rules tie, because no Philadelphia measurement of either exists.
- **consumer surplus change** against the start of the run: the exact integral of the
  demand law the rules act on (`demand.response.cs_change_served`, anchored at the start
  price) over the cars a block holds, min(demand, capacity). Negative when the price
  rises. A block whose latent demand exceeds its capacity is rationed to the parkers who
  value it most; the cars it turns away carry no surplus here and no search cost either.
  (Scoring surplus on latent demand while charging search only to served cars would credit
  a lower-priced rule with surplus on block-hours that were over-full before any rule
  acted; audit 2026-10-16, finding 5.)
- **revenue**: served cars x price, a transfer that counts in welfare at face value (the
  marginal cost of a curb space is zero).

welfare_change = dCS + (revenue - revenue0) - (search cost - search cost0): the change in
total surplus since the flat start price. Differences between rules on the same draw are
the sweep's result; the level depends on the start price.
"""
from __future__ import annotations

import numpy as np

from phillyparking.demand.response import cs_change_served
from phillyparking.welfare.search_cost import (  # noqa: F401  (re-exported for the sweep and tests)
    SearchCostConfig, cited_cruising_minutes, expected_search_minutes, load_search_cost_config,
    minutes_per_full_block, reference_minutes_per_cruising_minute, search_cost_usd,
)


def cs_change_usd(demand0: np.ndarray, price0: np.ndarray, price: np.ndarray,
                  elasticity: float, capacity: np.ndarray, form: str | None = None) -> np.ndarray:
    """Consumer surplus change in dollars for one hour of one block, from price0 to price.

    `demand0` is the latent demand share at `price0`, the reference price the elasticity
    applies at (it may exceed 1 when more cars want the block than it holds); q0 = demand0
    x capacity cars. Only the cars that get a space count: the integral is of
    min(q(x), capacity). Zero where the price is unchanged. `form` is the demand law (default:
    the config's).
    """
    q0 = np.asarray(demand0, dtype=float) * np.asarray(capacity, dtype=float)
    return cs_change_served(q0, price0, price, elasticity, capacity, form)
