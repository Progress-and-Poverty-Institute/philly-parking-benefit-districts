"""SEPTA GTFS loader via gtfs-kit (with synthetic fallback)."""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox

log = logging.getLogger(__name__)

SEPTA_FEED_URL = "https://github.com/septadev/GTFS/releases/latest/download/gtfs_public.zip"


def _gtfs_dir() -> Path:
    p = data_dir() / "raw" / "septa_gtfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_septa_feed(refresh: bool = False):
    cache = _gtfs_dir() / "septa.zip"
    try:
        import gtfs_kit as gk
    except ImportError as e:
        log.warning("gtfs_kit unavailable (%s)", e)
        return None
    if cache.exists() and not refresh:
        try:
            return gk.read_feed(cache, dist_units="km")
        except (OSError, Exception) as e:
            log.warning("gtfs feed load failed (%s)", e)
            return None
    try:
        import requests

        r = requests.get(SEPTA_FEED_URL, timeout=120)
        r.raise_for_status()
        cache.write_bytes(r.content)
        return gk.read_feed(cache, dist_units="km")
    except (OSError, Exception) as e:
        log.warning("SEPTA feed fetch failed (%s)", e)
        return None


def _synth_stop_freq(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(99)
    w, s, e, n_ = philly_bbox()
    rows = []
    for i in range(n):
        x = rng.uniform(w, e)
        y = rng.uniform(s, n_)
        # higher frequency near Center City
        d = ((x + 75.155) ** 2 + (y - 39.952) ** 2) ** 0.5
        tph = max(0.5, 12.0 - 80 * d + rng.normal(0, 1.5))
        rows.append({"stop_id": f"S{i:04d}", "trips_per_hour": float(tph), "geometry": Point(x, y)})
    return gpd.GeoDataFrame(rows, crs=4326)


def stop_frequency(feed, time_band: tuple[str, str] = ("07:00:00", "09:00:00")) -> pd.DataFrame:
    if feed is None:
        return _synth_stop_freq()
    try:
        dates = feed.get_first_week()
        date = dates[0] if dates else feed.feed_info.feed_start_date.iloc[0]
        st = feed.compute_stop_time_series([date], freq="1h")
        # simplified: total trips per stop in band -> per hour
        start_h = int(time_band[0].split(":")[0])
        end_h = int(time_band[1].split(":")[0])
        hours = end_h - start_h
        trips = st.loc[:, (slice(None), "num_trips")].iloc[start_h:end_h].sum() / max(1, hours)
        trips = trips.reset_index()
        trips.columns = ["stop_id", "_", "trips_per_hour"]
        trips = trips.drop(columns=["_"])
        stops = feed.stops[["stop_id", "stop_lon", "stop_lat"]]
        df = trips.merge(stops, on="stop_id")
        return gpd.GeoDataFrame(
            df.drop(columns=["stop_lon", "stop_lat"]),
            geometry=[Point(x, y) for x, y in zip(df.stop_lon, df.stop_lat)],
            crs=4326,
        )
    except (OSError, Exception) as e:
        log.warning("stop_frequency computation failed (%s); using synthetic", e)
        return _synth_stop_freq()
