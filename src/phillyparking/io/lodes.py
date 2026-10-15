"""LEHD LODES8 for Pennsylvania, filtered to Philadelphia County, plus block geography.

WAC (jobs by workplace block) and RAC (workers by residence block) are keyed by the 15-digit
2020 census block GEOID. `fetch_block_points` supplies where those blocks are: the LODES8
geography crosswalk (`pa_xwalk.csv.gz`), whose `blklatdd` / `blklondd` are each block's
internal point. `spatial.join.join_lodes` counts the jobs of the blocks whose point lies
within a segment's buffer.
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox
from phillyparking.io.raw_cache import Layer, load_layer

log = logging.getLogger(__name__)

BASE = "https://lehd.ces.census.gov/data/lodes/LODES8/pa"
URL_TMPL = BASE + "/{kind}/pa_{kind}_S000_JT00_{year}.csv.gz"
XWALK_URL = BASE + "/pa_xwalk.csv.gz"
PHILLY_COUNTY_PREFIX = "42101"


def _dir() -> Path:
    p = data_dir() / "raw" / "lehd_lodes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_csv_gz(url: str, **kw) -> pd.DataFrame:
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return pd.read_csv(BytesIO(r.content), compression="gzip", **kw)


def _fetch_remote(kind: str, year: int) -> pd.DataFrame:
    geo_col = "w_geocode" if kind == "wac" else "h_geocode"
    df = _get_csv_gz(URL_TMPL.format(kind=kind, year=year), dtype={geo_col: str})
    df = df[df[geo_col].str.startswith(PHILLY_COUNTY_PREFIX)].reset_index(drop=True)
    if len(df) == 0:
        raise ValueError(f"LODES {kind} {year} has no Philadelphia County blocks")
    return df


def _fetch_block_points() -> pd.DataFrame:
    df = _get_csv_gz(XWALK_URL, usecols=["tabblk2020", "blklatdd", "blklondd"],
                     dtype={"tabblk2020": str})
    df = df[df["tabblk2020"].str.startswith(PHILLY_COUNTY_PREFIX)].reset_index(drop=True)
    if len(df) == 0:
        raise ValueError("LODES crosswalk has no Philadelphia County blocks")
    return df


def _synth(kind: str, n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(0 if kind == "wac" else 1)
    geo_col = "w_geocode" if kind == "wac" else "h_geocode"
    blocks = [f"{PHILLY_COUNTY_PREFIX}{i:010d}" for i in range(n)]
    df = pd.DataFrame({geo_col: blocks})
    if kind == "wac":
        total = rng.poisson(35, n)
        df["C000"] = total
        df["CNS07"] = (total * rng.uniform(0.05, 0.3, n)).astype(int)  # retail
        df["CNS18"] = (total * rng.uniform(0.05, 0.3, n)).astype(int)  # accommodation/food
        df["CNS09"] = (total * rng.uniform(0.05, 0.4, n)).astype(int)  # information
    else:
        total = rng.poisson(40, n)
        df["C000"] = total
        df["CE01"] = (total * 0.3).astype(int)
        df["CE02"] = (total * 0.4).astype(int)
        df["CE03"] = (total * 0.3).astype(int)
        df["CR01"] = (total * 0.5).astype(int)
    return df


def _synth_block_points(n: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(5)
    w, s, e, n_ = philly_bbox()
    return pd.DataFrame({
        "tabblk2020": [f"{PHILLY_COUNTY_PREFIX}{i:010d}" for i in range(n)],
        "blklatdd": rng.uniform(s, n_, n),
        "blklondd": rng.uniform(w, e, n),
    })


def _table_layer(name: str, filename: str, source: str, url: str, fetch, synth) -> Layer:
    return Layer(name=name, path=_dir() / filename, source=source, url=url, fetch=fetch,
                 write=lambda d, p: d.to_parquet(p), read=pd.read_parquet, synth=synth)


def fetch_wac(year: int = 2021, refresh: bool = False,
              allow_synthetic: bool | None = None) -> pd.DataFrame:
    url = URL_TMPL.format(kind="wac", year=year)
    return load_layer(_table_layer("lodes.wac", f"pa_wac_{PHILLY_COUNTY_PREFIX}_{year}.parquet",
                                   f"LODES8 WAC {year}, Philadelphia County blocks", url,
                                   lambda: _fetch_remote("wac", year), lambda: _synth("wac")),
                      refresh, allow_synthetic)


def fetch_rac(year: int = 2021, refresh: bool = False,
              allow_synthetic: bool | None = None) -> pd.DataFrame:
    url = URL_TMPL.format(kind="rac", year=year)
    return load_layer(_table_layer("lodes.rac", f"pa_rac_{PHILLY_COUNTY_PREFIX}_{year}.parquet",
                                   f"LODES8 RAC {year}, Philadelphia County blocks", url,
                                   lambda: _fetch_remote("rac", year), lambda: _synth("rac")),
                      refresh, allow_synthetic)


def fetch_block_points(refresh: bool = False,
                       allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    """2020 census blocks of Philadelphia County as internal points (EPSG:4326)."""
    df = load_layer(_table_layer("lodes.block_points",
                                 f"pa_xwalk_blocks_{PHILLY_COUNTY_PREFIX}.parquet",
                                 "LODES8 Pennsylvania geography crosswalk (block internal points)",
                                 XWALK_URL, _fetch_block_points, _synth_block_points),
                    refresh, allow_synthetic)
    gdf = gpd.GeoDataFrame(df[["tabblk2020"]].copy(),
                           geometry=gpd.points_from_xy(df["blklondd"], df["blklatdd"]), crs=4326)
    gdf.attrs["provenance"] = df.attrs.get("provenance")
    return gdf
