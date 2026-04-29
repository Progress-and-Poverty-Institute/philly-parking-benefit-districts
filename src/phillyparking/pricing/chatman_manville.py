"""Chatman-Manville: side-by-side comparison of two targeting rules (§1.2, §9)."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from phillyparking.pricing.arnott_inci import cruising_dwl

logger = logging.getLogger(__name__)


def _project_occupancy(occ: np.ndarray, current_price: float, new_price: float, elasticity: float) -> np.ndarray:
    if new_price <= 0 or current_price <= 0:
        return occ.copy()
    factor = (new_price / current_price) ** elasticity
    return np.clip(occ * factor, 0.0, 1.0)


def target_avg_occupancy(
    occupancy_panel: pd.DataFrame,
    current_price: float,
    target_low: float = 0.70,
    target_high: float = 0.85,
    elasticity: float = -0.40,
    step: float = 0.50,
    max_iters: int = 40,
    floor: float = 0.50,
    ceiling: float = 10.00,
) -> tuple[float, dict]:
    occ = occupancy_panel["occupancy"].to_numpy()
    price = float(current_price)
    iters = 0
    direction = "hold"
    while iters < max_iters:
        proj = _project_occupancy(occ, current_price, price, elasticity)
        mean_occ = float(proj.mean())
        if mean_occ > target_high and price < ceiling:
            price = min(ceiling, price + step)
            direction = "up"
        elif mean_occ < target_low and price > floor:
            price = max(floor, price - step)
            direction = "down"
        else:
            break
        iters += 1

    proj = _project_occupancy(occ, current_price, price, elasticity)
    diag = {
        "rule": "avg_occupancy",
        "iterations": iters,
        "direction": direction,
        "predicted_avg_occ": float(proj.mean()),
        "predicted_peak_occ": float(np.quantile(proj, 0.95)),
        "previous_price": current_price,
    }
    return price, diag


def target_min_vacancy_peak(
    occupancy_panel: pd.DataFrame,
    current_price: float,
    min_vacancy: float = 0.15,
    peak_quantile: float = 0.95,
    elasticity: float = -0.40,
    step: float = 0.50,
    max_iters: int = 40,
    floor: float = 0.50,
    ceiling: float = 10.00,
) -> tuple[float, dict]:
    occ = occupancy_panel["occupancy"].to_numpy()
    price = float(current_price)
    target = 1.0 - min_vacancy
    iters = 0
    direction = "hold"
    while iters < max_iters:
        proj = _project_occupancy(occ, current_price, price, elasticity)
        peak = float(np.quantile(proj, peak_quantile))
        if peak > target and price < ceiling:
            price = min(ceiling, price + step)
            direction = "up"
        elif peak < target - 0.10 and price > floor:
            price = max(floor, price - step)
            direction = "down"
        else:
            break
        iters += 1

    proj = _project_occupancy(occ, current_price, price, elasticity)
    diag = {
        "rule": "min_vacancy_peak",
        "iterations": iters,
        "direction": direction,
        "predicted_avg_occ": float(proj.mean()),
        "predicted_peak_occ": float(np.quantile(proj, peak_quantile)),
        "previous_price": current_price,
    }
    return price, diag


def compare_targeting_rules(
    occupancy_panel: pd.DataFrame,
    current_price: float,
    elasticity: float = -0.40,
    capacity: float = 10.0,
) -> pd.DataFrame:
    occ = occupancy_panel["occupancy"].to_numpy()
    base_revenue = float(occ.mean() * capacity * current_price)

    rows = []
    for fn, kwargs in [
        (target_avg_occupancy, {}),
        (target_min_vacancy_peak, {}),
    ]:
        new_price, diag = fn(occupancy_panel, current_price, elasticity=elasticity, **kwargs)
        proj = _project_occupancy(occ, current_price, new_price, elasticity)
        peak_occ = float(np.quantile(proj, 0.95))
        avg_occ = float(proj.mean())
        peak_demand = peak_occ * capacity
        dwl = cruising_dwl(peak_demand, capacity)
        new_revenue = float(avg_occ * capacity * new_price)
        rev_change_pct = 100.0 * (new_revenue - base_revenue) / base_revenue if base_revenue > 0 else 0.0
        rows.append({
            "rule": diag["rule"],
            "new_price": new_price,
            "predicted_peak_occ": peak_occ,
            "predicted_avg_occ": avg_occ,
            "predicted_cruising_dwl_per_hr": dwl,
            "revenue_change_pct": rev_change_pct,
        })
    return pd.DataFrame(rows)
