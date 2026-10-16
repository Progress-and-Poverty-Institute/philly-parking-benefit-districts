"""SEPTA GTFS: scheduled transit trips per hour at each stop.

SEPTA publishes one archive, `gtfs_public.zip`, that holds two GTFS feeds as inner archives,
`google_bus.zip` and `google_rail.zip`. Read as one feed, the outer file has no GTFS tables,
so each inner feed is read separately and the stop frequencies are stacked (stop ids are
prefixed with the feed name, since the two feeds number their stops independently).

Trips per hour are counted straight from `stop_times`: the departures in the time band, on a
representative weekday service date, of the trips active that date, divided by the band's
length in hours. This avoids depending on the shape of gtfs-kit's time-series output, which
changed between versions.
"""
from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox
from phillyparking.io.raw_cache import (Layer, LayerFetchError, load_layer, read_marker,
                                        synthetic_allowed, tag)

log = logging.getLogger(__name__)

SEPTA_FEED_URL = "https://github.com/septadev/GTFS/releases/latest/download/gtfs_public.zip"


def _gtfs_dir() -> Path:
    p = data_dir() / "raw" / "septa_gtfs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _fetch_archive() -> bytes:
    import requests

    r = requests.get(SEPTA_FEED_URL, timeout=180)
    r.raise_for_status()
    feeds = inner_feeds(r.content)
    if not feeds:
        raise ValueError("SEPTA archive holds no GTFS feed")
    return r.content


def _write_bytes(b: bytes, path: Path) -> None:
    Path(path).write_bytes(b)


def load_septa_archive(refresh: bool = False) -> bytes:
    """The raw SEPTA archive bytes, cached as `septa.zip` with a provenance marker."""
    layer = Layer(name="septa.gtfs", path=_gtfs_dir() / "septa.zip",
                  source="SEPTA GTFS public archive (bus + rail)", url=SEPTA_FEED_URL,
                  fetch=_fetch_archive, write=_write_bytes, read=lambda p: Path(p).read_bytes())
    return load_layer(layer, refresh, allow_synthetic=False)


def inner_feeds(archive: bytes) -> dict[str, bytes]:
    """Name -> bytes of every GTFS feed in the archive: nested `.zip` members, or the archive
    itself when it is a plain feed (has `stop_times.txt` at its root)."""
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        names = z.namelist()
        if "stop_times.txt" in names:
            return {"feed": archive}
        return {Path(n).stem: z.read(n) for n in names if n.lower().endswith(".zip")}


def _read_feed(raw: bytes):
    import gtfs_kit as gk

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "feed.zip"
        p.write_bytes(raw)
        return gk.read_feed(p, dist_units="km")


def load_septa_feeds(refresh: bool = False) -> dict:
    """Name -> gtfs_kit Feed for each feed in the SEPTA archive (`google_bus`, `google_rail`)."""
    archive = load_septa_archive(refresh)
    feeds = {name: _read_feed(raw) for name, raw in inner_feeds(archive).items()}
    for name, f in feeds.items():
        if f.stop_times is None or len(f.stop_times) == 0:
            raise ValueError(f"SEPTA feed {name} has no stop_times")
    return feeds


def _hours(times: pd.Series) -> pd.Series:
    """GTFS HH:MM:SS (hours may exceed 23) -> integer hour."""
    return pd.to_numeric(times.astype(str).str.split(":").str[0], errors="coerce")


def trips_per_hour(stops: pd.DataFrame, active_trip_ids, stop_times: pd.DataFrame,
                   time_band: tuple[str, str]) -> pd.DataFrame:
    """Departures per hour at each stop within [start, end) on one service date.

    Every stop in `stops` is returned; a stop no active trip serves in the band gets 0.
    """
    start_h, end_h = (int(t.split(":")[0]) for t in time_band)
    if end_h <= start_h:
        raise ValueError(f"time band {time_band} is empty")
    st = stop_times[stop_times["trip_id"].isin(set(active_trip_ids))]
    t = st["departure_time"].where(st["departure_time"].notna(), st.get("arrival_time"))
    h = _hours(t)
    counts = st[(h >= start_h) & (h < end_h)].groupby("stop_id").size()
    out = stops[["stop_id", "stop_lon", "stop_lat"]].copy()
    out["trips_per_hour"] = out["stop_id"].map(counts).fillna(0).astype(float) / (end_h - start_h)
    return out


def _service_date(feed) -> str:
    """A Tuesday-Thursday of the feed's first full week, else its first date."""
    week = feed.get_first_week()
    mid = [d for d in week if pd.Timestamp(d).dayofweek in (1, 2, 3)]
    if mid:
        return mid[0]
    if week:
        return week[0]
    dates = feed.get_dates()
    if not dates:
        raise ValueError("feed has no service dates")
    return dates[0]


def stop_frequency(feeds, time_band: tuple[str, str] = ("07:00:00", "09:00:00")) -> gpd.GeoDataFrame:
    """Trips per hour per stop over every feed, as points in EPSG:4326.

    `feeds` is a dict of gtfs_kit Feeds (from `load_septa_feeds`) or one Feed.
    """
    if feeds is None:
        raise ValueError("no GTFS feed given; use load_stop_frequency for an explicit fallback")
    if not isinstance(feeds, dict):
        feeds = {"feed": feeds}
    frames = []
    for name, feed in feeds.items():
        date = _service_date(feed)
        active = feed.get_trips(date)["trip_id"]
        df = trips_per_hour(feed.stops, active, feed.stop_times, time_band)
        df["stop_id"] = name + ":" + df["stop_id"].astype(str)
        df["service_date"] = date
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    return gpd.GeoDataFrame(df.drop(columns=["stop_lon", "stop_lat"]),
                            geometry=gpd.points_from_xy(df["stop_lon"], df["stop_lat"]), crs=4326)


def _synth_stop_freq(n: int = 80) -> gpd.GeoDataFrame:
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


def load_stop_frequency(refresh: bool = False, allow_synthetic: bool | None = None,
                        time_band: tuple[str, str] = ("07:00:00", "09:00:00")) -> gpd.GeoDataFrame:
    """Stop frequencies from the real SEPTA feeds; a synthetic set (tagged, never cached) only
    when the real archive cannot be fetched and synthetic stand-ins are allowed."""
    try:
        feeds = load_septa_feeds(refresh)
    except LayerFetchError:
        if not synthetic_allowed(allow_synthetic):
            raise
        log.warning("septa.gtfs: using SYNTHETIC stop frequencies (real archive unavailable)")
        return tag(_synth_stop_freq(), {"layer": "septa.stop_frequency", "kind": "synthetic",
                                        "source": "synthetic stand-in for SEPTA GTFS", "url": None})
    sf = stop_frequency(feeds, time_band)
    return tag(sf, {**(read_marker(_gtfs_dir() / "septa.zip") or {}),
                    "layer": "septa.stop_frequency", "time_band": list(time_band)})
