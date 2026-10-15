"""ACS 5-year block-group attributes for Philadelphia County (FIPS 42101), with geometry.

Attributes come from the Census Data API (`api.census.gov`, needs `CENSUS_API_KEY`; without
a key the API answers 200 with an HTML "Missing Key" page, which is treated as a failure).
Geometry and land area (`ALAND`, m²) come from the Census cartographic boundary file for the
same vintage. The cenpy package this module used before cannot request any vintage after
2019 or block groups in 2019, so it is not used.

ACS uses large negative sentinels (-666666666 and similar) for "not available"; they become
NaN here, never numbers.
"""
from __future__ import annotations

import logging
import os
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from shapely.geometry import Polygon

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox
from phillyparking.io.raw_cache import Layer, load_layer

load_dotenv()
log = logging.getLogger(__name__)

STATE_FIPS, COUNTY_FIPS = "42", "101"
PHILLY_COUNTY_FIPS = STATE_FIPS + COUNTY_FIPS
API_TMPL = "https://api.census.gov/data/{year}/acs/acs5"
GEOM_TMPL = "https://www2.census.gov/geo/tiger/GENZ{year}/shp/cb_{year}_{state}_bg_500k.zip"
ACS_VARS = {
    "B19013_001E": "median_hh_income",
    "B01003_001E": "total_pop",
    "B25044_001E": "households",            # occupied housing units (tenure by vehicles)
    "B25046_001E": "aggregate_vehicles",    # aggregate vehicles available
    "B25003_002E": "tenure_owner",
    "B25003_003E": "tenure_renter",
    "B02001_002E": "race_white",
}


def _cache_path(year: int) -> Path:
    p = data_dir() / "raw" / "census_acs"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"acs5_bg_{PHILLY_COUNTY_FIPS}_{year}.parquet"


def parse_acs_json(rows: list[list[str]]) -> pd.DataFrame:
    """Census API JSON (header row first) -> one row per block group with a 12-digit GEOID."""
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"] + df["block group"]
    for var, name in ACS_VARS.items():
        v = pd.to_numeric(df[var], errors="coerce")
        df[name] = v.where(v >= 0)  # ACS "not available" sentinels are large negatives
    return df[["GEOID", *ACS_VARS.values()]]


def _fetch_acs(year: int) -> gpd.GeoDataFrame:
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise RuntimeError("CENSUS_API_KEY is not set; the Census Data API requires a key")
    try:
        r = requests.get(API_TMPL.format(year=year), timeout=120, params={
            "get": ",".join(ACS_VARS), "for": "block group:*",
            "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}", "key": key})
    except requests.RequestException as exc:
        # requests' messages quote the request URL, key included; keep it out of logs and markers
        raise RuntimeError(f"Census API request failed ({type(exc).__name__})") from None
    if not r.ok:  # not raise_for_status: its message carries the URL, key included
        raise RuntimeError(f"Census API answered HTTP {r.status_code}")
    if "json" not in r.headers.get("Content-Type", ""):
        raise ValueError(f"Census API returned {r.headers.get('Content-Type')}, not JSON "
                         f"(an invalid or missing key returns an HTML page)")
    attrs = parse_acs_json(r.json())

    g = requests.get(GEOM_TMPL.format(year=year, state=STATE_FIPS), timeout=120)
    g.raise_for_status()
    geom = gpd.read_file(BytesIO(g.content))
    geom = geom[geom["GEOID"].str.startswith(PHILLY_COUNTY_FIPS)][["GEOID", "ALAND", "geometry"]]
    gdf = geom.merge(attrs, on="GEOID", how="inner").to_crs(4326)
    missing = set(attrs["GEOID"]) - set(gdf["GEOID"])
    if missing or len(gdf) == 0:
        raise ValueError(f"{len(missing)} ACS block groups have no {year} boundary "
                         f"(of {len(attrs)}); vintages of attributes and geometry differ?")
    return gpd.GeoDataFrame(gdf, geometry="geometry", crs=4326)


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
            households = int(pop / 2.3)
            rows.append(
                {
                    "GEOID": f"42101{j:03d}{i:03d}",
                    "median_hh_income": float(income),
                    "total_pop": pop,
                    "households": households,
                    "aggregate_vehicles": int(households * 0.8),
                    "tenure_owner": owner,
                    "tenure_renter": renter,
                    "race_white": white,
                    "geometry": poly,
                }
            )
    gdf = gpd.GeoDataFrame(rows, crs=4326)
    gdf["ALAND"] = gdf.to_crs(32618).geometry.area
    return gdf


def fetch_acs_block_groups(year: int = 2022, refresh: bool = False,
                           allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    layer = Layer(
        name="census.acs_block_groups", path=_cache_path(year),
        source=f"Census ACS 5-year {year} block groups (Data API) + cb_{year} boundaries",
        url=API_TMPL.format(year=year), fetch=lambda: _fetch_acs(year),
        write=lambda g, p: g.to_parquet(p), read=gpd.read_parquet, synth=_synth_acs)
    return load_layer(layer, refresh, allow_synthetic)
