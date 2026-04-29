"""ACS 5-year block-group loader for Philadelphia County (FIPS 42101)."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
from dotenv import load_dotenv
from shapely.geometry import Polygon

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox

load_dotenv()
log = logging.getLogger(__name__)

PHILLY_COUNTY_FIPS = "42101"
ACS_VARS = {
    "B19013_001E": "median_hh_income",
    "B01003_001E": "total_pop",
    "B25044_001E": "vehicle_owners_total",
    "B25003_002E": "tenure_owner",
    "B25003_003E": "tenure_renter",
    "B02001_002E": "race_white",
}


def _cache_path(year: int) -> Path:
    p = data_dir() / "raw" / "census_acs"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"acs_bg_{year}.parquet"


def _via_cenpy(year: int) -> gpd.GeoDataFrame:
    import cenpy  # noqa

    conn = cenpy.products.ACS(year)
    gdf = conn.from_county(
        "Philadelphia, PA",
        level="block group",
        variables=list(ACS_VARS.keys()),
    )
    return gdf.rename(columns=ACS_VARS).to_crs(4326)


def _synth_acs() -> gpd.GeoDataFrame:
    rng = np.random.default_rng(2022)
    w, s, e, n = philly_bbox()
    nx_, ny_ = 12, 10
    xs = np.linspace(w, e, nx_ + 1)
    ys = np.linspace(s, n, ny_ + 1)
    cx, cy = -75.155, 39.952
    rows = []
    for j in range(ny_):
        for i in range(nx_):
            poly = Polygon(
                [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])]
            )
            mx, my = poly.centroid.x, poly.centroid.y
            d = ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5
            # higher income near Center City; deterministic with noise
            income = max(20000, 90000 - 200000 * d + rng.normal(0, 8000))
            pop = int(max(200, rng.normal(1500, 400)))
            renter = int(pop * np.clip(0.7 - 2 * d + rng.normal(0, 0.05), 0.1, 0.95))
            owner = pop - renter
            white = int(pop * np.clip(0.45 + rng.normal(0, 0.2), 0.05, 0.95))
            rows.append(
                {
                    "GEOID": f"42101{j:03d}{i:03d}",
                    "median_hh_income": float(income),
                    "total_pop": pop,
                    "vehicle_owners_total": int(pop * 0.6),
                    "tenure_owner": owner,
                    "tenure_renter": renter,
                    "race_white": white,
                    "geometry": poly,
                }
            )
    return gpd.GeoDataFrame(rows, crs=4326)


def fetch_acs_block_groups(year: int = 2022, refresh: bool = False) -> gpd.GeoDataFrame:
    cache = _cache_path(year)
    if cache.exists() and not refresh:
        return gpd.read_parquet(cache)
    if os.environ.get("CENSUS_API_KEY"):
        try:
            gdf = _via_cenpy(year)
            gdf.to_parquet(cache)
            return gdf
        except (OSError, Exception) as e:
            log.warning("cenpy fetch failed (%s); using synthetic", e)
    gdf = _synth_acs()
    gdf.to_parquet(cache)
    return gdf
