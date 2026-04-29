"""Arnott-Inci cruising-elimination optimal price (research doc §1.1, §5.5)."""
from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def constant_elasticity_demand(
    base_demand: float,
    base_price: float,
    elasticity: float,
) -> Callable[[float], float]:
    def D(p: float) -> float:
        return base_demand * (p / base_price) ** elasticity
    return D


def optimal_price_arnott_inci(
    base_demand: float,
    base_price: float,
    capacity: float,
    elasticity: float,
    target_vacancy: float = 0.15,
) -> float:
    target_demand = (1.0 - target_vacancy) * capacity
    return base_price * (target_demand / base_demand) ** (1.0 / elasticity)


def cruising_dwl(
    demand: float,
    capacity: float,
    target_vacancy: float = 0.15,
    avg_cruising_minutes: float = 5.0,
    value_of_time_usd_per_hr: float = 20.0,
) -> float:
    excess = max(0.0, demand - (1.0 - target_vacancy) * capacity)
    return excess * (avg_cruising_minutes / 60.0) * value_of_time_usd_per_hr
