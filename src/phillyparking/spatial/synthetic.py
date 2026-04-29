"""Shared test fixtures."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString

CCC_BBOX = (-75.170, 39.945, -75.140, 39.960)
ZONE_NAMES = ("ccc", "cca", "ucity", "south_philly", "fishtown", "other")
NEIGHBORHOOD_FOR_ZONE = {
    "ccc": "Center City",
    "cca": "Center City",
    "ucity": "University City",
    "south_philly": "South Philly",
    "fishtown": "Fishtown",
    "other": "Other",
}


def make_synthetic_segments(n: int = 25, seed: int = 0) -> gpd.GeoDataFrame:
    """A roughly grid of LineString segments inside the CCC bbox.

    Returns a GeoDataFrame with all columns produced by spatial.segments + joins:
    segment_id, geometry, length_m, street_name, zone_id, neighborhood, rpp_zone,
    capacity, has_meter, n_meters, current_rate, median_hh_income, pop_density,
    vehicles_per_hh, jobs_within_200m, pois_count, transit_trips_per_hr.
    """
    rng = np.random.default_rng(seed)
    side = max(1, int(np.ceil(n**0.5)))
    west, south, east, north = CCC_BBOX
    xs = np.linspace(west + 0.001, east - 0.001, side)
    ys = np.linspace(south + 0.001, north - 0.001, side)

    zone_choice = rng.choice(ZONE_NAMES, size=n,
                             p=[0.25, 0.20, 0.15, 0.15, 0.15, 0.10])
    rows = []
    for k in range(n):
        i, j = k % side, k // side
        x, y = xs[i], ys[min(j, side - 1)]
        line = LineString([(x, y), (x + 0.0008, y)])
        zone = zone_choice[k]
        is_ccc = zone == "ccc"
        rows.append({
            "segment_id": f"T{k:04d}",
            "geometry": line,
            "length_m": float(rng.uniform(60, 100)),
            "street_name": f"Synth {k}",
            "zone_id": zone,
            "neighborhood": NEIGHBORHOOD_FOR_ZONE[zone],
            "rpp_zone": None,
            "capacity": int(rng.integers(4, 16)),
            "has_meter": bool(rng.random() < 0.7),
            "n_meters": int(rng.integers(0, 4)),
            "current_rate": 4.0 if is_ccc else 2.0,
            "median_hh_income": float(rng.uniform(30_000, 130_000)),
            "pop_density": float(rng.uniform(2_000, 40_000)),
            "vehicles_per_hh": float(rng.uniform(0.3, 1.6)),
            "jobs_within_200m": float(rng.uniform(8_000, 9_500) if is_ccc
                                      else rng.uniform(50, 3_000)),
            "pois_count": int(rng.integers(0, 60)),
            "transit_trips_per_hr": float(rng.uniform(0, 40)),
        })
    return gpd.GeoDataFrame(rows, crs=4326)


def make_synthetic_panel(segments: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """A {segment × hour-of-week} panel with plausible occupancy."""
    rng = np.random.default_rng(seed)
    hours = np.arange(168)
    is_weekday = (hours // 24) < 5
    hour_of_day = hours % 24
    peak_mask = is_weekday & (hour_of_day >= 11) & (hour_of_day < 14)
    evening_mask = (hour_of_day >= 17) & (hour_of_day < 21)

    rows = []
    for _, s in segments.iterrows():
        base = 0.30 + 0.5 * (s["jobs_within_200m"] / 9000.0)
        peak = 1.5 if s["zone_id"] == "ccc" else 1.2
        occ = base * (1.0 + 0.4 * evening_mask + (peak - 1.0) * peak_mask)
        occ = np.clip(occ + rng.normal(0, 0.03, size=168), 0, 1)
        rows.append(pd.DataFrame({
            "segment_id": s["segment_id"],
            "zone_id": s["zone_id"],
            "neighborhood": s["neighborhood"],
            "hour_of_week": hours,
            "occupancy": occ,
            "occupancy_sd": 0.05,
            "capacity": s["capacity"],
        }))
    return pd.concat(rows, ignore_index=True)
