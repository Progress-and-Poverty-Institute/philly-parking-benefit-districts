"""Seattle-style ±$0.50 zone x time-of-day adjustment (research doc §3.3).

Follows SDOT's performance-based rule as its 2024 Paid Parking report describes it: one
statistic, the average occupancy of an area over a time-of-day period, compared with a
70-85% target band. Above the band the period's rate rises one step, below it the rate
falls one step, inside it the rate holds. The band is a dead band: it is what lets the
rule settle instead of alternating between two prices.

Each zone gets one price per configured time-of-day band (`time_of_day_bands` in
`config/scenarios.yaml`). The band statistic is the capacity-weighted zone occupancy,
averaged over the zone's priced hours (weekday and Saturday where priced, from
`pricing.priced_hours`) whose hour of day falls in the band.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import frame_priced_mask

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeattleRuleConfig:
    step_usd: float = 0.50
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
        occ_high=float(s["occ_high"]),
        occ_low=float(s["occ_low"]),
        occ_very_high=float(s["occ_very_high"]),
        max_step_per_cycle=int(s["max_step_per_cycle"]),
        floor=float(rules["global_floor_usd"]),
        ceiling=float(rules["global_ceiling_usd"]),
    )


def band_label(band) -> str:
    return f"{int(band[0])}-{int(band[1])}"


def zone_bounds(zone_id: str | None, fallback: SeattleRuleConfig) -> tuple[float, float]:
    """(floor, ceiling) for a zone from `zones.yaml`; the global bounds for an unlisted zone."""
    if zone_id is None:
        return fallback.floor, fallback.ceiling
    zones = load_config("zones")["zones"]
    for z in zones:
        if z["id"] == zone_id:
            return float(z.get("floor", fallback.floor)), float(z.get("ceiling", fallback.ceiling))
    return fallback.floor, fallback.ceiling


def adjust_price(
    current_price: float,
    band_occupancy: float,
    config: SeattleRuleConfig | None = None,
    zone_id: str | None = None,
) -> tuple[float, dict]:
    """One review of one zone-band: step on its period-average occupancy.

    Above `occ_high` raise one step (two at or above `occ_very_high`); below `occ_low`
    cut one step; inside [occ_low, occ_high] hold.
    """
    cfg = config or load_seattle_config()
    floor, ceiling = zone_bounds(zone_id, cfg)

    if band_occupancy >= cfg.occ_very_high:
        n_steps, direction = cfg.max_step_per_cycle, "up"
    elif band_occupancy > cfg.occ_high:
        n_steps, direction = 1, "up"
    elif band_occupancy < cfg.occ_low:
        n_steps, direction = 1, "down"
    else:
        n_steps, direction = 0, "hold"
    delta = {"up": 1, "down": -1, "hold": 0}[direction] * n_steps * cfg.step_usd

    new_price = float(np.clip(current_price + delta, floor, ceiling))
    diagnostics = {
        "band_occ": float(band_occupancy),
        "direction": direction,
        "n_steps": n_steps,
        "floor": floor,
        "ceiling": ceiling,
        "previous_price": current_price,
    }
    return new_price, diagnostics


def zone_band_occupancy(
    occupancy: pd.DataFrame,
    bands: list,
    capacity_weighted: bool = True,
) -> pd.DataFrame:
    """Mean capacity-weighted zone occupancy per (zone, band) over the zone's priced hours.

    `occupancy` carries segment_id, zone_id, hour_of_week, occupancy (and capacity when
    weighted). Returns zone_id, band, band_start, band_end, band_occ, n_hours (priced
    hours per week in the band). A band with no priced hours in a zone gets no row.
    """
    df = occupancy.loc[frame_priced_mask(occupancy)].copy()
    df["_w"] = df["capacity"] if capacity_weighted and "capacity" in df.columns else 1.0
    df["_wo"] = df["occupancy"] * df["_w"]
    zh = df.groupby(["zone_id", "hour_of_week"], observed=True).agg(_wo=("_wo", "sum"), _w=("_w", "sum")).reset_index()
    zh["occ"] = zh["_wo"] / zh["_w"]
    hod = zh["hour_of_week"] % 24

    rows = []
    for band in bands:
        a, b = int(band[0]), int(band[1])
        in_band = zh.loc[(hod >= a) & (hod < b)]
        for zone_id, g in in_band.groupby("zone_id", observed=True):
            rows.append({
                "zone_id": zone_id, "band": band_label(band), "band_start": a, "band_end": b,
                "band_occ": float(g["occ"].mean()), "n_hours": int(len(g)),
            })
    return pd.DataFrame(rows)


def adjust_zone_prices(
    occupancy: pd.DataFrame,
    current_prices: pd.DataFrame,
    bands: list,
    capacity_weighted: bool = True,
    config: SeattleRuleConfig | None = None,
) -> pd.DataFrame:
    """One annual review of every zone-band.

    `current_prices` is zone-level (zone_id, price_usd_per_hr), which seeds every band
    with the zone's rate, or the zone x band output of a previous review. Zones absent
    from `current_prices` are skipped.
    """
    cfg = config or load_seattle_config()
    stats = zone_band_occupancy(occupancy, bands, capacity_weighted)

    if "band" in current_prices.columns:
        cur = current_prices.set_index(["zone_id", "band"])["price_usd_per_hr"]
        lookup = lambda z, bnd: cur.get((z, bnd))  # noqa: E731
    else:
        cur = current_prices.set_index("zone_id")["price_usd_per_hr"]
        lookup = lambda z, bnd: cur.get(z)  # noqa: E731

    rows = []
    for _, s in stats.iterrows():
        price = lookup(s["zone_id"], s["band"])
        if price is None or pd.isna(price):
            continue
        new_price, diag = adjust_price(float(price), s["band_occ"], cfg, zone_id=str(s["zone_id"]))
        rows.append({
            "zone_id": s["zone_id"],
            "band": s["band"],
            "band_start": s["band_start"],
            "band_end": s["band_end"],
            "price_usd_per_hr": new_price,
            "previous_price": float(price),
            "band_occ": s["band_occ"],
            "n_hours": s["n_hours"],
            "direction": diag["direction"],
        })
    return pd.DataFrame(rows)
