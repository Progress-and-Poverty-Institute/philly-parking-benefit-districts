"""CVXPY joint zone-pricing under PBD constraints (research doc §5.6, §7)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci

logger = logging.getLogger(__name__)


@dataclass
class JointPricingProblem:
    zones: list[str]
    base_demand: np.ndarray
    base_price: np.ndarray
    capacity: np.ndarray
    elasticity: np.ndarray | float
    target_vacancy: float = 0.15
    floor: np.ndarray | float = 0.50
    ceiling: np.ndarray | float = 10.00
    revenue_floor_usd: float | None = None


def _broadcast(x: np.ndarray | float, n: int) -> np.ndarray:
    if np.isscalar(x):
        return np.full(n, float(x))
    arr = np.asarray(x, dtype=float)
    if arr.shape == ():
        return np.full(n, float(arr))
    if arr.shape != (n,):
        raise ValueError(f"Expected shape ({n},), got {arr.shape}")
    return arr


def _fallback_independent(problem: JointPricingProblem) -> pd.DataFrame:
    n = len(problem.zones)
    elasticity = _broadcast(problem.elasticity, n)
    floor = _broadcast(problem.floor, n)
    ceiling = _broadcast(problem.ceiling, n)
    rows = []
    for i, z in enumerate(problem.zones):
        p_star = optimal_price_arnott_inci(
            base_demand=float(problem.base_demand[i]),
            base_price=float(problem.base_price[i]),
            capacity=float(problem.capacity[i]),
            elasticity=float(elasticity[i]),
            target_vacancy=problem.target_vacancy,
        )
        binding = "none"
        if p_star <= floor[i]:
            p_clamped = floor[i]
            binding = "floor"
        elif p_star >= ceiling[i]:
            p_clamped = ceiling[i]
            binding = "ceiling"
        else:
            p_clamped = p_star
        demand = float(problem.base_demand[i]) * (p_clamped / float(problem.base_price[i])) ** float(elasticity[i])
        cap = float(problem.capacity[i])
        occ = min(demand / cap, 1.0) if cap > 0 else 0.0
        if binding == "none" and demand > (1.0 - problem.target_vacancy) * cap + 1e-9:
            binding = "occupancy"
        rows.append({
            "zone_id": z,
            "optimal_price": float(p_clamped),
            "predicted_demand": demand,
            "predicted_revenue": float(p_clamped * min(demand, cap)),
            "predicted_occupancy": occ,
            "binding_constraint": binding,
        })
    return pd.DataFrame(rows)


def solve_pbd_pricing(problem: JointPricingProblem) -> pd.DataFrame:
    n = len(problem.zones)
    elasticity = _broadcast(problem.elasticity, n)
    floor = _broadcast(problem.floor, n)
    ceiling = _broadcast(problem.ceiling, n)

    try:
        import cvxpy as cp
    except ImportError:
        logger.warning("cvxpy unavailable; falling back to per-zone Arnott-Inci.")
        return _fallback_independent(problem)

    log_p = cp.Variable(n)
    log_base = np.log(problem.base_price)
    # demand_i = base_demand_i * exp(eps_i * (log_p_i - log_base_i))
    log_demand = np.log(problem.base_demand) + cp.multiply(elasticity, log_p - log_base)
    target_demand = (1.0 - problem.target_vacancy) * problem.capacity

    # objective: maximize log-revenue (sum log_p + log_demand) — proxy for welfare
    objective = cp.Maximize(cp.sum(log_p + log_demand))

    constraints = [
        log_p >= np.log(floor),
        log_p <= np.log(ceiling),
        log_demand <= np.log(target_demand),
    ]
    if problem.revenue_floor_usd is not None:
        # revenue >= floor → log-sum-exp lower bound (non-convex). Skip if needed; use as soft.
        # We approximate by requiring each zone to contribute at least equal share — conservative.
        per_zone_floor = problem.revenue_floor_usd / n
        constraints.append(log_p + log_demand >= np.log(per_zone_floor))

    prob = cp.Problem(objective, constraints)
    try:
        prob.solve()
    except Exception as e:
        logger.warning("cvxpy solve failed (%s); falling back.", e)
        return _fallback_independent(problem)

    if log_p.value is None:
        logger.warning("cvxpy returned no solution; falling back.")
        return _fallback_independent(problem)

    prices = np.exp(np.asarray(log_p.value).flatten())
    rows = []
    for i, z in enumerate(problem.zones):
        p = float(prices[i])
        demand = float(problem.base_demand[i]) * (p / float(problem.base_price[i])) ** float(elasticity[i])
        cap = float(problem.capacity[i])
        occ = min(demand / cap, 1.0) if cap > 0 else 0.0
        binding = "none"
        if abs(p - floor[i]) / max(floor[i], 1e-9) < 1e-3:
            binding = "floor"
        elif abs(p - ceiling[i]) / max(ceiling[i], 1e-9) < 1e-3:
            binding = "ceiling"
        elif demand >= target_demand[i] - 1e-3:
            binding = "occupancy"
        rows.append({
            "zone_id": z,
            "optimal_price": p,
            "predicted_demand": demand,
            "predicted_revenue": float(p * min(demand, cap)),
            "predicted_occupancy": occ,
            "binding_constraint": binding,
        })
    return pd.DataFrame(rows)
