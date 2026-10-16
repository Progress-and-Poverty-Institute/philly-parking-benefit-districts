"""City of Philadelphia public layers (Open Data Philly), cached with provenance markers.

Sources, checked live on 2026-10-15 (the Carto names this module used before then, other than
`zoning_basedistricts`, returned 400 or 403):

- streets: the Street Centerline FeatureServer (ArcGIS, paged at 2,000 features).
- rpp_zones: Carto `residential_parking_permit_blocks`, one POINT per permit block with its
  `district_number`. It is not a polygon layer.
- neighborhoods: the Azavea neighborhood polygons, as GeoJSON in the Open Data Philly
  storage repository.
- zoning: Carto `zoning_basedistricts`.
- meters: there is no public meter inventory. It comes from the Parking Authority's
  Right-to-Know release (`phillyparking.ingest.ppa`); `fetch_meters` says so instead of
  inventing one.

See `phillyparking.io.raw_cache` for the caching and fallback rules.
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox
from phillyparking.io.raw_cache import Layer, LayerFetchError, load_layer, synthetic_allowed, tag

log = logging.getLogger(__name__)

CARTO_BASE = "https://phl.carto.com/api/v2/sql"
STREETS_URL = ("https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
               "Street_Centerline/FeatureServer/0/query")
NEIGHBORHOODS_URL = ("https://raw.githubusercontent.com/opendataphilly/odp-data-storage/master/"
                     "philadelphia-neighborhoods/philadelphia-neighborhoods.geojson")
CARTO_TABLES = {
    "rpp_zones": "residential_parking_permit_blocks",
    "zoning": "zoning_basedistricts",
}
TIMEOUT_S = 120


def _cache_dir() -> Path:
    p = data_dir() / "raw" / "opendataphilly"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nonempty(gdf: gpd.GeoDataFrame, what: str) -> gpd.GeoDataFrame:
    if len(gdf) == 0:
        raise ValueError(f"{what} returned 0 features")
    return gdf


def _carto_geojson(table: str) -> gpd.GeoDataFrame:
    r = requests.get(CARTO_BASE, params={"q": f"SELECT * FROM {table}", "format": "geojson"},
                     timeout=TIMEOUT_S)
    r.raise_for_status()
    gdf = gpd.read_file(BytesIO(r.content))
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
    return _nonempty(gdf, f"Carto table {table}")


def _arcgis_paged(url: str, page: int = 2000) -> gpd.GeoDataFrame:
    """Every feature of an ArcGIS FeatureServer layer, as EPSG:4326 GeoJSON pages."""
    frames, offset = [], 0
    while True:
        r = requests.get(url, params={"where": "1=1", "outFields": "*", "f": "geojson",
                                      "outSR": 4326, "resultOffset": offset,
                                      "resultRecordCount": page}, timeout=TIMEOUT_S)
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise ValueError(f"ArcGIS error: {body['error']}")
        feats = body.get("features", [])
        if feats:
            frames.append(gpd.GeoDataFrame.from_features(feats, crs=4326))
        exceeded = body.get("exceededTransferLimit") or body.get("properties", {}).get(
            "exceededTransferLimit")
        if not feats or not exceeded:
            break
        offset += len(feats)
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326) if frames else \
        gpd.GeoDataFrame(geometry=[], crs=4326)
    return _nonempty(gdf, url)


def _geojson_url(url: str) -> gpd.GeoDataFrame:
    r = requests.get(url, timeout=TIMEOUT_S)
    r.raise_for_status()
    gdf = gpd.read_file(BytesIO(r.content))
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
    return _nonempty(gdf, url)


def _fetch_streets() -> gpd.GeoDataFrame:
    gdf = _arcgis_paged(STREETS_URL)
    if "seg_id" in gdf.columns and gdf["seg_id"].duplicated().any():
        raise ValueError("Street Centerline seg_id is not unique")
    return gdf


def _fetch_neighborhoods() -> gpd.GeoDataFrame:
    gdf = _geojson_url(NEIGHBORHOODS_URL)
    name_col = next((c for c in ("LISTNAME", "MAPNAME", "NAME") if c in gdf.columns), None)
    if name_col is None:
        raise ValueError(f"neighborhoods layer has no name column: {list(gdf.columns)}")
    gdf["neighborhood"] = gdf[name_col].astype(str)
    return gdf


def _fetch_rpp() -> gpd.GeoDataFrame:
    gdf = _carto_geojson(CARTO_TABLES["rpp_zones"])
    if "district_number" not in gdf.columns:
        raise ValueError(f"RPP layer lacks district_number: {list(gdf.columns)}")
    gdf["rpp_zone"] = gdf["district_number"].astype("Int64").astype(str)
    return gdf


def _layer(name: str, filename: str, source: str, url: str, fetch, synth) -> Layer:
    return Layer(name=f"opendataphilly.{name}", path=_cache_dir() / filename, source=source,
                 url=url, fetch=fetch, write=lambda g, p: g.to_parquet(p),
                 read=gpd.read_parquet, synth=synth)


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
                "seg_id": 1000000 + i,
                "stname": f"Synth St {i}",
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


def fetch_meters(refresh: bool = False, allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    """No public meter inventory exists; the real one is the Parking Authority's release.

    Load it with `phillyparking.ingest.ppa.load_inventory`. This returns a synthetic layer
    (tagged as such, never cached) only when synthetic stand-ins are allowed.
    """
    if not synthetic_allowed(allow_synthetic):
        raise LayerFetchError(
            "opendataphilly.meters: there is no public meter inventory. Use the Parking "
            "Authority's inventory (phillyparking.ingest.ppa.load_inventory), or allow a "
            "synthetic stand-in explicitly."
        )
    log.warning("opendataphilly.meters: returning a SYNTHETIC meter layer (no public source)")
    return tag(_synth_meters(), {"layer": "opendataphilly.meters", "kind": "synthetic",
                                 "source": "synthetic; no public meter inventory", "url": None})


def fetch_rpp_zones(refresh: bool = False, allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    url = f"{CARTO_BASE}?q=SELECT * FROM {CARTO_TABLES['rpp_zones']}&format=geojson"
    return load_layer(_layer("rpp_zones", "rpp_blocks.parquet",
                             "Open Data Philly: Residential Parking Permit Blocks (points)",
                             url, _fetch_rpp, _synth_rpp), refresh, allow_synthetic)


def fetch_streets(refresh: bool = False, allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    return load_layer(_layer("streets", "street_centerline.parquet",
                             "Open Data Philly: Street Centerline", STREETS_URL,
                             _fetch_streets, _synth_streets), refresh, allow_synthetic)


def fetch_neighborhoods(refresh: bool = False, allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    return load_layer(_layer("neighborhoods", "neighborhoods.parquet",
                             "Open Data Philly: Philadelphia Neighborhoods (Azavea)",
                             NEIGHBORHOODS_URL, _fetch_neighborhoods, _synth_neigh),
                      refresh, allow_synthetic)


def fetch_zoning(refresh: bool = False, allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    url = f"{CARTO_BASE}?q=SELECT * FROM {CARTO_TABLES['zoning']}&format=geojson"
    return load_layer(_layer("zoning", "zoning_basedistricts.parquet",
                             "Open Data Philly: Zoning Base Districts", url,
                             lambda: _carto_geojson(CARTO_TABLES["zoning"]), _synth_zoning),
                      refresh, allow_synthetic)
