"""Seattle ±$0.50 annual zone-level adjustment (research doc §3.3)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeattleRuleConfig:
    step_usd: float = 0.50
    peak_window: tuple[int, int] = (11, 14)
    peak_quantile: float = 0.90
    occ_high: float = 0.85
    occ_low: float = 0.70
    occ_very_high: float = 0.95
    max_step_per_cycle: int = 2
    floor: float = 0.50
    ceiling: float = 10.00


def load_seattle_config() -> SeattleRuleConfig:
    rules = load_config("pricing_rules")
    s = rules["seattle_rule"]
    return SeattleRuleConfig(
        step_usd=float(s["step_usd"]),
        peak_window=tuple(s["peak_window"]),  # type: ignore[arg-type]
        peak_quantile=float(s["peak_quantile"]),
        occ_high=float(s["occ_high"]),
        occ_low=float(s["occ_low"]),
        occ_very_high=float(s["occ_very_high"]),
        max_step_per_cycle=int(s["max_step_per_cycle"]),
        floor=float(rules["global_floor_usd"]),
        ceiling=float(rules["global_ceiling_usd"]),
    )


def _zone_bounds(zone_id: str | None, fallback: SeattleRuleConfig) -> tuple[float, float]:
    if zone_id is None:
        return fallback.floor, fallback.ceiling
    zones = load_config("zones")["zones"]
    for z in zones:
        if z["id"] == zone_id:
            return float(z.get("floor", fallback.floor)), float(z.get("ceiling", fallback.ceiling))
    return fallback.floor, fallback.ceiling


def _priced_hours_mask(panel: pd.DataFrame) -> np.ndarray:
    how = panel["hour_of_week"].to_numpy()
    day = how // 24
    hour = how % 24
    return (day < 5) & (hour >= 8) & (hour < 20)


def adjust_price(
    current_price: float,
    occupancy_panel: pd.DataFrame,
    config: SeattleRuleConfig | None = None,
    zone_id: str | None = None,
) -> tuple[float, dict]:
    cfg = config or load_seattle_config()
    floor, ceiling = _zone_bounds(zone_id, cfg)

    weekday_mask = _priced_hours_mask(occupancy_panel)
    priced = occupancy_panel.loc[weekday_mask]
    hour = priced["hour_of_week"].to_numpy() % 24
    peak_mask = (hour >= cfg.peak_window[0]) & (hour < cfg.peak_window[1])
    peak_occ_series = priced.loc[peak_mask, "occupancy"].to_numpy()
    peak_occ = float(np.quantile(peak_occ_series, cfg.peak_quantile)) if peak_occ_series.size else 0.0
    avg_occ = float(priced["occupancy"].mean()) if len(priced) else 0.0

    if peak_occ >= cfg.occ_very_high:
        n_steps = cfg.max_step_per_cycle
        direction = "up"
        delta = n_steps * cfg.step_usd
    elif peak_occ >= cfg.occ_high:
        n_steps = 1
        direction = "up"
        delta = cfg.step_usd
    elif avg_occ < cfg.occ_low:
        n_steps = 1
        direction = "down"
        delta = -cfg.step_usd
    else:
        n_steps = 0
        direction = "hold"
        delta = 0.0

    new_price = float(np.clip(current_price + delta, floor, ceiling))
    diagnostics = {
        "peak_occ": peak_occ,
        "avg_occ": avg_occ,
        "direction": direction,
        "n_steps": n_steps,
        "floor": floor,
        "ceiling": ceiling,
        "previous_price": current_price,
    }
    return new_price, diagnostics


def adjust_zone_prices(
    occupancy: pd.DataFrame,
    current_prices: pd.DataFrame,
    capacity_weighted: bool = True,
    config: SeattleRuleConfig | None = None,
) -> pd.DataFrame:
    cfg = config or load_seattle_config()
    df = occupancy.copy()

    if capacity_weighted and "capacity" in df.columns:
        df["_w"] = df["capacity"]
    else:
        df["_w"] = 1.0
    df["_wo"] = df["occupancy"] * df["_w"]

    grouped = df.groupby(["zone_id", "hour_of_week"], observed=True).agg(
        occupancy=("_wo", "sum"),
        w=("_w", "sum"),
    ).reset_index()
    grouped["occupancy"] = grouped["occupancy"] / grouped["w"]

    rows = []
    for zone_id, panel in grouped.groupby("zone_id", observed=True):
        cur_row = current_prices.loc[current_prices["zone_id"] == zone_id]
        if cur_row.empty:
            continue
        cur = float(cur_row["price_usd_per_hr"].iloc[0])
        new_price, diag = adjust_price(cur, panel, cfg, zone_id=str(zone_id))
        rows.append({
            "zone_id": zone_id,
            "price_usd_per_hr": new_price,
            "previous_price": cur,
            "peak_occ": diag["peak_occ"],
            "avg_occ": diag["avg_occ"],
            "direction": diag["direction"],
        })
    return pd.DataFrame(rows)
