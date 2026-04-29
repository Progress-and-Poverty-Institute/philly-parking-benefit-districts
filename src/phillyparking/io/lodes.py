"""LEHD LODES WAC/RAC for Pennsylvania, filtered to Philadelphia County."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from phillyparking._config import data_dir

log = logging.getLogger(__name__)

URL_TMPL = "https://lehd.ces.census.gov/data/lodes/LODES8/pa/{kind}/pa_{kind}_S000_JT00_{year}.csv.gz"
PHILLY_COUNTY_PREFIX = "42101"


def _cache(kind: str, year: int) -> Path:
    p = data_dir() / "raw" / "lehd_lodes"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"pa_{kind}_{year}.parquet"


def _fetch_remote(kind: str, year: int) -> pd.DataFrame:
    url = URL_TMPL.format(kind=kind, year=year)
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    from io import BytesIO

    df = pd.read_csv(BytesIO(r.content), compression="gzip", dtype={"w_geocode": str, "h_geocode": str})
    geo_col = "w_geocode" if kind == "wac" else "h_geocode"
    df = df[df[geo_col].astype(str).str.startswith(PHILLY_COUNTY_PREFIX)]
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
        df["CNS09"] = (total * rng.uniform(0.05, 0.4, n)).astype(int)  # office/info
    else:
        total = rng.poisson(40, n)
        df["C000"] = total
        df["CE01"] = (total * 0.3).astype(int)
        df["CE02"] = (total * 0.4).astype(int)
        df["CE03"] = (total * 0.3).astype(int)
        df["CR01"] = (total * 0.5).astype(int)
    return df


def _load(kind: str, year: int, refresh: bool) -> pd.DataFrame:
    cache = _cache(kind, year)
    if cache.exists() and not refresh:
        return pd.read_parquet(cache)
    try:
        df = _fetch_remote(kind, year)
        df.to_parquet(cache)
        return df
    except (requests.RequestException, OSError, Exception) as e:
        log.warning("LODES %s fetch failed (%s); using synthetic", kind, e)
        df = _synth(kind)
        df.to_parquet(cache)
        return df


def fetch_wac(year: int = 2021, refresh: bool = False) -> pd.DataFrame:
    return _load("wac", year, refresh)


def fetch_rac(year: int = 2021, refresh: bool = False) -> pd.DataFrame:
    return _load("rac", year, refresh)
