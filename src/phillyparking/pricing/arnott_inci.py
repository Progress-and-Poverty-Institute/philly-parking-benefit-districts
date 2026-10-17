"""Arnott-Inci cruising-elimination optimal price (research doc §1.1, §5.5)."""
from __future__ import annotations

import logging
from collections.abc import Callable

from phillyparking.demand.response import demand_factor, price_for_demand_ratio

logger = logging.getLogger(__name__)


def demand_function(
    base_demand: float,
    base_price: float,
    elasticity: float,
    reference_price: float | None = None,
    form: str | None = None,
) -> Callable[[float], float]:
    """D(p) under the configured demand law, anchored so that D(base_price) = base_demand."""
    ref = base_price if reference_price is None else reference_price

    def D(p: float) -> float:
        return float(base_demand * demand_factor(p, base_price, elasticity, ref, form))
    return D


def optimal_price_arnott_inci(
    base_demand: float,
    base_price: float,
    capacity: float,
    elasticity: float,
    target_vacancy: float = 0.15,
    reference_price: float | None = None,
    form: str | None = None,
) -> float:
    """The price that brings demand to (1 - target_vacancy) x capacity under the demand law.

    `elasticity` applies at `reference_price` (default `base_price`); see `demand.response`.
    """
    target_demand = (1.0 - target_vacancy) * capacity
    ref = base_price if reference_price is None else reference_price
    return float(price_for_demand_ratio(target_demand / base_demand, base_price, elasticity, ref, form))

