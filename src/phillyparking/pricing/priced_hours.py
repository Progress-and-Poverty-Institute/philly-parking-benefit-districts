"""Priced hours per zone, read from `config/zones.yaml`.

One source for "when is the meter on". Elasticity application, revenue, the cruising
DWL scorer and both pricing rules all take their hours from here, so no module acts on
hours the configuration leaves unpriced.

`hour_of_week` convention (same as `demand.synthetic_baseline.hour_of_week`):
day = hour_of_week // 24 with Monday = 0, so days 0-4 are weekdays, 5 is Saturday,
6 is Sunday; hour = hour_of_week % 24. A `priced_hours` entry `[a, b]` covers hours
a <= hour < b. A zone absent from the config (e.g. the fixture's `other`) has no
priced hours.
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from phillyparking._config import load_config

WEEKS_PER_YEAR = 52
_DAY_KEYS = (("weekday", range(0, 5)), ("saturday", (5,)), ("sunday", (6,)))


def zone_priced_hours(zones_cfg: list[dict] | None = None) -> dict[str, dict]:
    """Map zone_id -> its `priced_hours` block (weekday / saturday / sunday)."""
    if zones_cfg is None:
        zones_cfg = load_config("zones")["zones"]
    return {z["id"]: dict(z.get("priced_hours") or {}) for z in zones_cfg}


def _hours_of_week(spec: Mapping) -> np.ndarray:
    """Sorted hour_of_week values a single zone's `priced_hours` block covers."""
    out = []
    for key, days in _DAY_KEYS:
        v = spec.get(key)
        if v is None:
            continue
        a, b = int(v[0]), int(v[1])
        for d in days:
            out.extend(d * 24 + h for h in range(a, b))
    return np.array(sorted(out), dtype=int)


def priced_hours_of_week(zone_id: str, hours: Mapping[str, Mapping] | None = None) -> np.ndarray:
    """hour_of_week values at which `zone_id` is priced (empty if the zone is not configured)."""
    hours = zone_priced_hours() if hours is None else hours
    spec = hours.get(zone_id)
    return _hours_of_week(spec) if spec else np.array([], dtype=int)


def weekly_priced_hours(zone_id: str, hours: Mapping[str, Mapping] | None = None) -> int:
    return int(priced_hours_of_week(zone_id, hours).size)


def annual_priced_hours(zone_id: str, hours: Mapping[str, Mapping] | None = None) -> int:
    return weekly_priced_hours(zone_id, hours) * WEEKS_PER_YEAR


def priced_mask(
    zone_id: pd.Series | np.ndarray,
    hour_of_week: pd.Series | np.ndarray,
    hours: Mapping[str, Mapping] | None = None,
) -> np.ndarray:
    """Boolean array: True where (zone_id, hour_of_week) is a priced hour."""
    hours = zone_priced_hours() if hours is None else hours
    z = np.asarray(zone_id, dtype=object)
    how = np.asarray(hour_of_week, dtype=int)
    mask = np.zeros(len(z), dtype=bool)
    for zid, spec in hours.items():
        in_zone = z == zid
        if not in_zone.any():
            continue
        mask[in_zone] = np.isin(how[in_zone], _hours_of_week(spec))
    return mask


def frame_priced_mask(df: pd.DataFrame, hours: Mapping[str, Mapping] | None = None) -> np.ndarray:
    """`priced_mask` for a panel carrying `zone_id` and `hour_of_week` columns."""
    missing = [c for c in ("zone_id", "hour_of_week") if c not in df.columns]
    if missing:
        raise ValueError(f"priced-hours mask needs columns {missing}; merge zone_id onto the panel first")
    return priced_mask(df["zone_id"].to_numpy(), df["hour_of_week"].to_numpy(), hours)


def hourly_prices(prices: pd.DataFrame, hours: Mapping[str, Mapping] | None = None) -> pd.DataFrame:
    """Expand zone prices to one row per (zone_id, hour_of_week) priced hour.

    `prices` is zone-level (zone_id, price_usd_per_hr) or carries `band_start` /
    `band_end` columns (one price per zone and hour-of-day band, from the Seattle rule).
    A priced hour that no band covers is an error: the price there would be undefined.
    """
    hours = zone_priced_hours() if hours is None else hours
    banded = {"band_start", "band_end"} <= set(prices.columns)
    # Segment-level price tables repeat each zone (or zone-band) price once per segment.
    prices = prices.drop_duplicates(["zone_id", "band_start", "band_end"] if banded else ["zone_id"])
    rows = []
    for zid, g in prices.groupby("zone_id", sort=False):
        how = priced_hours_of_week(zid, hours)
        if how.size == 0:
            continue
        if not banded:
            rows.append(pd.DataFrame({"zone_id": zid, "hour_of_week": how,
                                      "price_usd_per_hr": float(g["price_usd_per_hr"].iloc[0])}))
            continue
        hod = how % 24
        covered = np.zeros(how.size, dtype=bool)
        for _, r in g.iterrows():
            m = (hod >= r["band_start"]) & (hod < r["band_end"])
            covered |= m
            rows.append(pd.DataFrame({"zone_id": zid, "hour_of_week": how[m],
                                      "price_usd_per_hr": float(r["price_usd_per_hr"])}))
        if not covered.all():
            raise ValueError(f"zone {zid}: priced hours {sorted(set(hod[~covered]))} fall in no price band")
    if not rows:
        return pd.DataFrame(columns=["zone_id", "hour_of_week", "price_usd_per_hr"])
    return pd.concat(rows, ignore_index=True)


def zone_mean_price(prices: pd.DataFrame, hours: Mapping[str, Mapping] | None = None) -> pd.Series:
    """Priced-hour-weighted mean price per zone (equals the zone price when it has one)."""
    return hourly_prices(prices, hours).groupby("zone_id")["price_usd_per_hr"].mean()
