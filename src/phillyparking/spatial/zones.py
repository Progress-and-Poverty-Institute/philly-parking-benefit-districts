"""Pricing-zone assignment and aggregation per config/zones.yaml."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from phillyparking._config import load_config


def _bbox_match(lon: float, lat: float, zones: list[dict]) -> str:
    for z in zones:
        b = z["bbox"]
        if b["west"] <= lon <= b["east"] and b["south"] <= lat <= b["north"]:
            return z["id"]
    return "other"


def assign_zones(segments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cfg = load_config("zones")
    zones = cfg.get("zones", [])
    seg = segments.copy()
    crs = getattr(seg, "crs", None)
    if crs is not None and not crs.is_projected:
        cents = seg.to_crs("EPSG:32618").geometry.centroid.to_crs(crs)
    else:
        cents = seg.geometry.centroid
    seg["zone_id"] = [_bbox_match(p.x, p.y, zones) for p in cents]
    return seg


def aggregate_to_zones(
    segments: gpd.GeoDataFrame,
    metric: str = "occupancy",
    weights: str = "capacity",
) -> pd.DataFrame:
    if metric not in segments.columns:
        return segments.groupby("zone_id").size().rename("n_segments").reset_index()
    w = segments[weights] if weights in segments.columns else np.ones(len(segments))
    df = segments[["zone_id", metric]].copy()
    df["__w"] = w
    df["__wm"] = df[metric] * df["__w"]
    g = df.groupby("zone_id").agg(__sum_wm=("__wm", "sum"), __sum_w=("__w", "sum")).reset_index()
    g[metric] = g["__sum_wm"] / g["__sum_w"].replace(0, np.nan)
    return g[["zone_id", metric]]


def zone_summary(segments: gpd.GeoDataFrame) -> pd.DataFrame:
    cfg = load_config("zones")
    rates = {z["id"]: z.get("current_rate_usd_per_hr") for z in cfg.get("zones", [])}
    g = segments.groupby("zone_id").agg(
        n_segments=("segment_id", "count"),
        total_capacity=("capacity", "sum"),
        total_length_m=("length_m", "sum"),
    ).reset_index()
    g["current_rate"] = g["zone_id"].map(rates)
    return g
