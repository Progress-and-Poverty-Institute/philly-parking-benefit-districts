"""Canonical street-segment GeoDataFrame builder."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString
from shapely.ops import substring

from phillyparking._config import data_dir, load_config

log = logging.getLogger(__name__)

SEGMENT_LENGTH_TARGET_M = 80.0
METERS_PER_CAR = 7.0
DRIVEWAY_HYDRANT_SLACK = 0.85


def _seg_id(parent_key: str, idx: int) -> str:
    h = hashlib.sha1(f"{parent_key}|{idx}".encode()).hexdigest()[:12]
    return f"S{h}"


def _split_line(line: LineString, target_m: float, length_m: float) -> list[tuple[int, LineString]]:
    if length_m <= target_m * 1.25:
        return [(0, line)]
    n = max(1, int(round(length_m / target_m)))
    pieces = []
    for i in range(n):
        a = i / n
        b = (i + 1) / n
        sub = substring(line, a, b, normalized=True)
        if sub.is_empty or sub.length == 0:
            continue
        pieces.append((i, sub))
    return pieces


def _zone_from_bbox(lon: float, lat: float, zones_cfg: dict) -> str:
    for z in zones_cfg.get("zones", []):
        b = z["bbox"]
        if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
            return z["id"]
    return "other"


def build_segments(
    streets: gpd.GeoDataFrame | None = None,
    meters: gpd.GeoDataFrame | None = None,
    rpp_zones: gpd.GeoDataFrame | None = None,
    neighborhoods: gpd.GeoDataFrame | None = None,
    target_length_m: float = SEGMENT_LENGTH_TARGET_M,
) -> gpd.GeoDataFrame:
    if streets is None:
        from phillyparking.io.opendataphilly import (
            fetch_meters,
            fetch_neighborhoods,
            fetch_rpp_zones,
            fetch_streets,
        )

        streets = fetch_streets()
        meters = meters if meters is not None else fetch_meters()
        rpp_zones = rpp_zones if rpp_zones is not None else fetch_rpp_zones()
        neighborhoods = neighborhoods if neighborhoods is not None else fetch_neighborhoods()

    streets = streets.to_crs(4326)
    streets_m = streets.to_crs(32618)
    zones_cfg = load_config("zones")

    name_col = "street_name" if "street_name" in streets.columns else ("name" if "name" in streets.columns else None)
    osmid_col = "osmid" if "osmid" in streets.columns else None

    rows = []
    for idx in range(len(streets)):
        geom_ll = streets.geometry.iloc[idx]
        geom_m = streets_m.geometry.iloc[idx]
        if geom_ll is None or geom_ll.is_empty or not isinstance(geom_ll, LineString):
            continue
        parent_key = str(streets[osmid_col].iloc[idx]) if osmid_col else f"row{idx}"
        length_m_total = float(geom_m.length)
        for sub_idx, sub_ll in _split_line(geom_ll, target_length_m, length_m_total):
            sub_m = substring(geom_m, sub_idx / max(1, round(length_m_total / target_length_m)),
                              (sub_idx + 1) / max(1, round(length_m_total / target_length_m)),
                              normalized=True) if length_m_total > target_length_m * 1.25 else geom_m
            length_m = float(sub_m.length) if sub_m and not sub_m.is_empty else length_m_total
            cx, cy = sub_ll.centroid.x, sub_ll.centroid.y
            zone_id = _zone_from_bbox(cx, cy, zones_cfg)
            sname = streets[name_col].iloc[idx] if name_col else None
            capacity = max(0, int((length_m / METERS_PER_CAR) * DRIVEWAY_HYDRANT_SLACK))
            rows.append(
                {
                    "segment_id": _seg_id(parent_key, sub_idx),
                    "geometry": sub_ll,
                    "length_m": length_m,
                    "street_name": sname,
                    "zone_id": zone_id,
                    "neighborhood": None,
                    "rpp_zone": None,
                    "capacity": capacity,
                    "has_meter": False,
                    "n_meters": 0,
                }
            )

    seg = gpd.GeoDataFrame(rows, crs=4326)

    if neighborhoods is not None and len(neighborhoods):
        n_col = "neighborhood" if "neighborhood" in neighborhoods.columns else neighborhoods.columns[0]
        seg = gpd.sjoin(
            seg, neighborhoods[[n_col, "geometry"]], how="left", predicate="intersects"
        ).drop(columns=["index_right"], errors="ignore")
        if n_col in seg.columns and n_col != "neighborhood":
            seg["neighborhood"] = seg[n_col]
            seg = seg.drop(columns=[n_col])
        seg = seg.drop_duplicates("segment_id", keep="first").reset_index(drop=True)

    if rpp_zones is not None and len(rpp_zones):
        r_col = "rpp_zone" if "rpp_zone" in rpp_zones.columns else rpp_zones.columns[0]
        seg = gpd.sjoin(
            seg.drop(columns=["rpp_zone"]),
            rpp_zones[[r_col, "geometry"]],
            how="left",
            predicate="intersects",
        ).drop(columns=["index_right"], errors="ignore")
        if r_col != "rpp_zone":
            seg["rpp_zone"] = seg[r_col]
            seg = seg.drop(columns=[r_col])
        seg = seg.drop_duplicates("segment_id", keep="first").reset_index(drop=True)

    if meters is not None and len(meters):
        seg_m = seg.to_crs(32618)
        meters_m = meters.to_crs(32618)
        buf = seg_m.copy()
        buf["geometry"] = buf.geometry.buffer(15.0)
        joined = gpd.sjoin(meters_m, buf[["segment_id", "geometry"]], how="left", predicate="within")
        counts = joined.groupby("segment_id").size().rename("n_meters")
        seg = seg.merge(counts, on="segment_id", how="left", suffixes=("", "_new"))
        if "n_meters_new" in seg.columns:
            seg["n_meters"] = seg["n_meters_new"].fillna(0).astype(int)
            seg = seg.drop(columns=["n_meters_new"])
        else:
            seg["n_meters"] = seg["n_meters"].fillna(0).astype(int)
        seg["has_meter"] = seg["n_meters"] > 0

    return seg


def _default_path() -> Path:
    p = data_dir() / "interim"
    p.mkdir(parents=True, exist_ok=True)
    return p / "segments.parquet"


def save_segments(segments: gpd.GeoDataFrame, path: Path | None = None) -> Path:
    path = Path(path) if path else _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    segments.to_parquet(path)
    return path


def load_segments(path: Path | None = None) -> gpd.GeoDataFrame:
    path = Path(path) if path else _default_path()
    return gpd.read_parquet(path)
