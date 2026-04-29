"""Spatial joins from external data to segments. All buffering done in EPSG:32618."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

UTM = 32618


def _to_utm(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return g.to_crs(UTM)


def join_acs(segments: gpd.GeoDataFrame, acs_bg: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Area-weighted attributes from block groups to segment buffer (~15m)."""
    seg_m = _to_utm(segments).copy()
    seg_m["__area"] = seg_m.geometry.buffer(15.0).area
    seg_m["geometry"] = seg_m.geometry.buffer(15.0)
    bg_m = _to_utm(acs_bg)

    inter = gpd.overlay(seg_m[["segment_id", "geometry", "__area"]], bg_m, how="intersection")
    inter["__w"] = inter.geometry.area / inter["__area"]

    pop = inter["total_pop"].astype(float) if "total_pop" in inter.columns else 0.0
    out_cols = {}
    out_cols["median_hh_income"] = (inter["median_hh_income"].astype(float) * inter["__w"]).groupby(inter["segment_id"]).sum()
    out_cols["pop_density"] = (pop / inter.geometry.area * inter["__w"]).groupby(inter["segment_id"]).sum() * 1e6
    if "tenure_renter" in inter.columns and "tenure_owner" in inter.columns:
        renter = inter["tenure_renter"].astype(float)
        owner = inter["tenure_owner"].astype(float)
        out_cols["pct_renter"] = ((renter / (renter + owner).replace(0, np.nan)).fillna(0) * inter["__w"]).groupby(inter["segment_id"]).sum()
    if "race_white" in inter.columns:
        white = inter["race_white"].astype(float)
        out_cols["pct_white"] = ((white / pop.replace(0, np.nan)).fillna(0) * inter["__w"]).groupby(inter["segment_id"]).sum()
    if "vehicle_owners_total" in inter.columns:
        out_cols["vehicles_per_hh"] = (inter["vehicle_owners_total"].astype(float) / pop.replace(0, np.nan).fillna(1) * inter["__w"]).groupby(inter["segment_id"]).sum()

    feat = pd.DataFrame(out_cols).reset_index()
    return segments.merge(feat, on="segment_id", how="left")


def join_lodes(
    segments: gpd.GeoDataFrame,
    wac: pd.DataFrame,
    rac: pd.DataFrame,
    buffer_m: float = 200.0,
) -> gpd.GeoDataFrame:
    """LODES is keyed by 15-digit block geocode; without a block-polygon layer
    we approximate by allocating county totals proportional to segment buffer area.
    Real implementation should sjoin against TIGER block polygons.
    """
    seg_m = _to_utm(segments)
    buf = seg_m.copy()
    buf["geometry"] = buf.geometry.buffer(buffer_m)
    total_area = buf.geometry.area.sum()
    share = buf.geometry.area / total_area if total_area > 0 else 0.0

    total_jobs = float(wac["C000"].sum()) if "C000" in wac.columns else 0.0
    total_workers = float(rac["C000"].sum()) if "C000" in rac.columns else 0.0
    out = segments.copy()
    out["jobs_within_200m"] = (share * total_jobs).round().astype(int).values
    out["workers_within_200m"] = (share * total_workers).round().astype(int).values

    if "CNS07" in wac.columns:
        out["jobs_retail_share"] = float(wac["CNS07"].sum()) / max(total_jobs, 1.0)
    if "CNS18" in wac.columns:
        out["jobs_service_share"] = float(wac["CNS18"].sum()) / max(total_jobs, 1.0)
    if "CNS09" in wac.columns:
        out["jobs_office_share"] = float(wac["CNS09"].sum()) / max(total_jobs, 1.0)
    return out


def join_transit(
    segments: gpd.GeoDataFrame,
    stop_freq: gpd.GeoDataFrame,
    buffer_m: float = 400.0,
) -> gpd.GeoDataFrame:
    seg_m = _to_utm(segments)
    stops_m = _to_utm(stop_freq)
    buf = seg_m.copy()
    buf["geometry"] = buf.geometry.buffer(buffer_m)
    j = gpd.sjoin(stops_m, buf[["segment_id", "geometry"]], how="inner", predicate="within")
    tph = j.groupby("segment_id")["trips_per_hour"].sum().rename("transit_trips_per_hr")

    seg_centroids = seg_m.copy()
    seg_centroids["geometry"] = seg_centroids.geometry.centroid
    nearest = gpd.sjoin_nearest(
        seg_centroids[["segment_id", "geometry"]],
        stops_m[["geometry"]],
        how="left",
        distance_col="nearest_stop_distance_m",
    )
    nearest = nearest.drop_duplicates("segment_id", keep="first")[
        ["segment_id", "nearest_stop_distance_m"]
    ]
    out = segments.merge(tph, on="segment_id", how="left").merge(nearest, on="segment_id", how="left")
    out["transit_trips_per_hr"] = out["transit_trips_per_hr"].fillna(0.0)
    return out


def join_pois(
    segments: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    buffer_m: float = 100.0,
) -> gpd.GeoDataFrame:
    seg_m = _to_utm(segments)
    pois_m = _to_utm(pois)
    buf = seg_m.copy()
    buf["geometry"] = buf.geometry.buffer(buffer_m)
    j = gpd.sjoin(pois_m, buf[["segment_id", "geometry"]], how="inner", predicate="within")

    counts = j.groupby("segment_id").size().rename("pois_count")
    out = segments.merge(counts, on="segment_id", how="left")
    out["pois_count"] = out["pois_count"].fillna(0).astype(int)

    cat_col = None
    for c in ("category", "amenity", "shop"):
        if c in j.columns:
            cat_col = c
            break
    if cat_col:
        for label, key in [("retail", "shop"), ("restaurant", "restaurant"), ("office", "office")]:
            sub = j[j[cat_col].astype(str).str.contains(key, case=False, na=False)]
            ct = sub.groupby("segment_id").size().rename(f"pois_{label}")
            out = out.merge(ct, on="segment_id", how="left")
            out[f"pois_{label}"] = out[f"pois_{label}"].fillna(0).astype(int)
    return out
