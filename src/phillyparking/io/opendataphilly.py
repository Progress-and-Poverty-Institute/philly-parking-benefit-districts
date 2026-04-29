"""Open Data Philly loaders. Network -> cached parquet -> synthetic fallback."""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import LineString, Point, Polygon

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox

log = logging.getLogger(__name__)

CARTO_BASE = "https://phl.carto.com/api/v2/sql"
ENDPOINTS = {
    "meters": "parking_meters",
    "streets": "streets",
    "rpp_zones": "permitparking",
    "neighborhoods": "philadelphia_neighborhoods",
    "zoning": "zoning_basedistricts",
}


def _cache_dir() -> Path:
    p = data_dir() / "raw" / "opendataphilly"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _carto_geojson(table: str) -> gpd.GeoDataFrame:
    url = f"{CARTO_BASE}?q=SELECT *, ST_AsGeoJSON(the_geom) AS geometry FROM {table}&format=geojson"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return gpd.read_file(BytesIO(r.content)).set_crs(4326, allow_override=True)


def _fetch(name: str, synth_fn, refresh: bool = False) -> gpd.GeoDataFrame:
    cache = _cache_dir() / f"{name}.parquet"
    if cache.exists() and not refresh:
        return gpd.read_parquet(cache)
    try:
        gdf = _carto_geojson(ENDPOINTS[name])
        gdf.to_parquet(cache)
        return gdf
    except (requests.RequestException, OSError, Exception) as e:
        log.warning("Carto fetch for %s failed (%s); falling back to synthetic", name, e)
        if cache.exists():
            return gpd.read_parquet(cache)
        gdf = synth_fn()
        gdf.to_parquet(cache)
        return gdf


def _synth_meters(n: int = 200) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(42)
    w, s, e, n_ = philly_bbox()
    # cluster meters around Center City
    cx, cy = -75.155, 39.952
    lons = rng.normal(cx, 0.01, n).clip(w, e)
    lats = rng.normal(cy, 0.005, n).clip(s, n_)
    return gpd.GeoDataFrame(
        {
            "meter_id": [f"M{i:05d}" for i in range(n)],
            "rate": rng.choice([2.0, 3.0, 4.0], n),
            "geometry": [Point(x, y) for x, y in zip(lons, lats)],
        },
        crs=4326,
    )


def _synth_streets(n: int = 100) -> gpd.GeoDataFrame:
    rng = np.random.default_rng(7)
    w, s, e, n_ = philly_bbox()
    rows = []
    for i in range(n):
        x0 = rng.uniform(w, e)
        y0 = rng.uniform(s, n_)
        dx = rng.uniform(-0.005, 0.005)
        dy = rng.uniform(-0.005, 0.005)
        rows.append(
            {
                "osmid": 1000000 + i,
                "name": f"Synth St {i}",
                "highway": rng.choice(["residential", "secondary", "tertiary"]),
                "geometry": LineString([(x0, y0), (x0 + dx, y0 + dy)]),
            }
        )
    return gpd.GeoDataFrame(rows, crs=4326)


def _synth_polys(ids: list[str]) -> gpd.GeoDataFrame:
    w, s, e, n_ = philly_bbox()
    nx_, ny_ = 5, max(1, len(ids) // 5 + 1)
    xs = np.linspace(w, e, nx_ + 1)
    ys = np.linspace(s, n_, ny_ + 1)
    rows = []
    k = 0
    for j in range(ny_):
        for i in range(nx_):
            if k >= len(ids):
                break
            poly = Polygon(
                [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])]
            )
            rows.append({"id": ids[k], "name": ids[k], "geometry": poly})
            k += 1
    return gpd.GeoDataFrame(rows, crs=4326)


def _synth_rpp() -> gpd.GeoDataFrame:
    g = _synth_polys([f"Z{i}" for i in range(10)])
    return g.rename(columns={"id": "rpp_zone"})


def _synth_neigh() -> gpd.GeoDataFrame:
    return _synth_polys(
        [
            "Center City",
            "University City",
            "South Philly",
            "Fishtown",
            "Northern Liberties",
            "Fairmount",
            "Brewerytown",
            "Manayunk",
            "Kensington",
            "Mt Airy",
        ]
    ).rename(columns={"id": "neighborhood"})


def _synth_zoning() -> gpd.GeoDataFrame:
    g = _synth_polys([f"ZN{i}" for i in range(15)])
    g["zoning"] = np.random.default_rng(3).choice(["RSA-5", "CMX-2", "CMX-3", "I-2"], len(g))
    return g


def fetch_meters(refresh: bool = False) -> gpd.GeoDataFrame:
    return _fetch("meters", _synth_meters, refresh)


def fetch_rpp_zones(refresh: bool = False) -> gpd.GeoDataFrame:
    return _fetch("rpp_zones", _synth_rpp, refresh)


def fetch_streets(refresh: bool = False) -> gpd.GeoDataFrame:
    return _fetch("streets", _synth_streets, refresh)


def fetch_neighborhoods(refresh: bool = False) -> gpd.GeoDataFrame:
    return _fetch("neighborhoods", _synth_neigh, refresh)


def fetch_zoning(refresh: bool = False) -> gpd.GeoDataFrame:
    return _fetch("zoning", _synth_zoning, refresh)
