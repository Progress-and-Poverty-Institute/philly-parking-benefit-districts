"""Spatial joins from external data to segments. All buffering is done in EPSG:32618.

What each column is:

- `join_acs`, over a 15 m buffer around the segment, each block group weighted by the share
  of the buffer it covers, weights renormalised over the covered part:
  `pop_density` (residents per km² of block-group land area), `median_hh_income` (weighted
  mean of block-group medians, an approximation: medians do not average), `pct_renter`,
  `pct_white`, `vehicles_per_hh` (aggregate vehicles / households), `acs_coverage` (share of
  the buffer inside any block group).
- `join_lodes`, over a buffer of `buffer_m` (default 200 m): `jobs_within_200m` is the LODES
  WAC job count of the 2020 census blocks inside the buffer (blocks given as internal points,
  or as polygons with jobs split by the share of block area inside); `workers_within_200m` the
  same for RAC (resident workers); `jobs_retail_share` (NAICS 44-45, CNS07),
  `jobs_food_accommodation_share` (NAICS 72, CNS18), `jobs_office_share` (NAICS 51-56,
  CNS09-CNS14) are shares of those jobs, NaN where there are none.
- `join_transit`: `transit_trips_per_hr` sums scheduled departures per hour at every stop
  within `buffer_m` (400 m); `nearest_stop_distance_m` from the segment centroid.
- `join_pois`: `pois_count` within `buffer_m` (100 m) of the segment, and `pois_restaurant`
  (amenity restaurant / cafe / bar / fast_food / pub), `pois_retail` (any `shop` tag),
  `pois_office` (any `office` tag). POI polygons count by their representative point.
"""
from __future__ import annotations

import logging

import geopandas as gpd
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

UTM = 32618
OFFICE_CNS = ("CNS09", "CNS10", "CNS11", "CNS12", "CNS13", "CNS14")  # NAICS 51-56
RESTAURANT_AMENITIES = {"restaurant", "cafe", "bar", "fast_food", "pub"}


def _to_utm(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return g.to_crs(UTM)


def _buffers(segments: gpd.GeoDataFrame, buffer_m: float) -> gpd.GeoDataFrame:
    buf = _to_utm(segments)[["segment_id", "geometry"]].copy()
    buf["geometry"] = buf.geometry.buffer(buffer_m)
    return buf


def _weighted_mean(values: pd.Series, w: pd.Series, by: pd.Series) -> pd.Series:
    """Sum(w * v) / sum(w) per group, over rows where v is not NaN."""
    ok = values.notna()
    num = (values.where(ok, 0.0) * w).groupby(by).sum()
    den = w.where(ok, 0.0).groupby(by).sum()
    return num / den.replace(0.0, np.nan)


def _merge_checked(segments, feat: pd.DataFrame, what: str):
    """Left-merge per-segment features; the feature table must be one row per segment."""
    if feat["segment_id"].duplicated().any():
        raise ValueError(f"{what}: duplicate segment_id in joined features")
    clash = [c for c in feat.columns if c != "segment_id" and c in segments.columns]
    out = segments.drop(columns=clash).merge(feat, on="segment_id", how="left")
    if len(out) != len(segments):
        raise ValueError(f"{what}: merge changed the row count {len(segments)} -> {len(out)}")
    return out


def join_acs(segments: gpd.GeoDataFrame, acs_bg: gpd.GeoDataFrame, buffer_m: float = 15.0,
             uncovered: str = "raise") -> gpd.GeoDataFrame:
    """Block-group attributes over each segment's buffer; see the module docstring.

    `uncovered`: what to do with segments whose buffer touches no block group (outside the
    county): "raise" (default), "drop" them (logged), or "nan" (keep with NaN attributes).
    """
    if uncovered not in ("raise", "drop", "nan"):
        raise ValueError(f"uncovered must be raise / drop / nan, not {uncovered!r}")
    buf = _buffers(segments, buffer_m)
    buf["__area"] = buf.geometry.area
    bg = _to_utm(acs_bg).copy()
    land = bg["ALAND"].astype(float) if "ALAND" in bg.columns else bg.geometry.area
    bg["__land_m2"] = land.where(land > 0, bg.geometry.area)

    inter = gpd.overlay(buf, bg, how="intersection", keep_geom_type=True)
    w = inter.geometry.area / inter["__area"]
    sid = inter["segment_id"]

    cols: dict[str, pd.Series] = {"acs_coverage": w.groupby(sid).sum().clip(upper=1.0)}
    pop = inter["total_pop"].astype(float) if "total_pop" in inter.columns else None
    if pop is not None:
        cols["pop_density"] = _weighted_mean(pop / inter["__land_m2"] * 1e6, w, sid)
    if "median_hh_income" in inter.columns:
        cols["median_hh_income"] = _weighted_mean(inter["median_hh_income"].astype(float), w, sid)
    if {"tenure_renter", "tenure_owner"} <= set(inter.columns):
        renter = inter["tenure_renter"].astype(float)
        occupied = renter + inter["tenure_owner"].astype(float)
        cols["pct_renter"] = _weighted_mean(renter / occupied.replace(0, np.nan), w, sid)
    if "race_white" in inter.columns and pop is not None:
        cols["pct_white"] = _weighted_mean(inter["race_white"].astype(float)
                                           / pop.replace(0, np.nan), w, sid)
    if {"aggregate_vehicles", "households"} <= set(inter.columns):
        cols["vehicles_per_hh"] = _weighted_mean(
            inter["aggregate_vehicles"].astype(float)
            / inter["households"].astype(float).replace(0, np.nan), w, sid)

    feat = pd.DataFrame(cols).rename_axis("segment_id").reset_index()
    out = _merge_checked(segments, feat, "join_acs")
    out["acs_coverage"] = out["acs_coverage"].fillna(0.0)
    missing = out["acs_coverage"] <= 0
    if missing.any():
        ids = out.loc[missing, "segment_id"].tolist()
        msg = f"join_acs: {len(ids)} of {len(out)} segments touch no block group: {ids[:5]}"
        if uncovered == "raise":
            raise ValueError(msg + " (pass uncovered='drop' to drop them)")
        log.warning(msg + ("; dropped" if uncovered == "drop" else "; kept with NaN"))
        if uncovered == "drop":
            out = out[~missing].reset_index(drop=True)
    return out


def join_lodes(
    segments: gpd.GeoDataFrame,
    wac: pd.DataFrame,
    rac: pd.DataFrame,
    blocks: gpd.GeoDataFrame,
    buffer_m: float = 200.0,
    max_unlocated_share: float = 0.01,
) -> gpd.GeoDataFrame:
    """LODES jobs and resident workers of the census blocks within `buffer_m` of each segment.

    `blocks` has `tabblk2020` and either point geometry (block internal points, from
    `io.lodes.fetch_block_points`: a block counts wholly if its point is in the buffer) or
    polygon geometry (jobs split by the share of block area inside the buffer). Raises if
    more than `max_unlocated_share` of the county's jobs sit in blocks `blocks` does not
    locate, which means the block vintages differ.
    """
    tag = f"{int(round(buffer_m))}m"
    buf = _buffers(segments, buffer_m)
    blk = _to_utm(blocks)[["tabblk2020", "geometry"]].copy()
    blk["tabblk2020"] = blk["tabblk2020"].astype(str)

    def _attach(tab: pd.DataFrame, geo_col: str, what: str) -> pd.DataFrame:
        tab = tab.copy()
        tab["tabblk2020"] = tab[geo_col].astype(str)
        located = tab["tabblk2020"].isin(set(blk["tabblk2020"]))
        total = float(tab["C000"].sum())
        lost = float(tab.loc[~located, "C000"].sum())
        if total > 0 and lost / total > max_unlocated_share:
            raise ValueError(f"join_lodes: {lost / total:.1%} of {what} C000 is in blocks the "
                             f"block geography does not contain (vintage mismatch?)")
        return tab

    wac = _attach(wac, "w_geocode", "WAC")
    rac = _attach(rac, "h_geocode", "RAC")

    if (blk.geom_type == "Point").all():
        pairs = gpd.sjoin(blk, buf, how="inner", predicate="within")
        pairs = pairs[["tabblk2020", "segment_id"]].assign(__share=1.0)
    else:
        blk["__barea"] = blk.geometry.area
        inter = gpd.overlay(blk, buf, how="intersection", keep_geom_type=True)
        pairs = pd.DataFrame({"tabblk2020": inter["tabblk2020"],
                              "segment_id": inter["segment_id"],
                              "__share": inter.geometry.area / inter["__barea"]})

    def _sum(tab: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        cols = [c for c in cols if c in tab.columns]
        m = pairs.merge(tab[["tabblk2020", *cols]], on="tabblk2020", how="inner")
        return m[cols].mul(m["__share"], axis=0).groupby(m["segment_id"]).sum()

    cat_cols = ["C000", "CNS07", "CNS18", *OFFICE_CNS]
    jobs = _sum(wac, cat_cols)
    workers = _sum(rac, ["C000"])

    feat = pd.DataFrame(index=pd.Index(buf["segment_id"], name="segment_id"))
    feat[f"jobs_within_{tag}"] = jobs["C000"].reindex(feat.index).fillna(0.0)
    feat[f"workers_within_{tag}"] = workers["C000"].reindex(feat.index).fillna(0.0)
    total = jobs["C000"].reindex(feat.index)
    denom = total.where(total > 0)
    if "CNS07" in jobs.columns:
        feat["jobs_retail_share"] = jobs["CNS07"].reindex(feat.index) / denom
    if "CNS18" in jobs.columns:
        feat["jobs_food_accommodation_share"] = jobs["CNS18"].reindex(feat.index) / denom
    office = [c for c in OFFICE_CNS if c in jobs.columns]
    if office:
        feat["jobs_office_share"] = jobs[office].sum(axis=1).reindex(feat.index) / denom
    return _merge_checked(segments, feat.reset_index(), "join_lodes")


def join_transit(
    segments: gpd.GeoDataFrame,
    stop_freq: gpd.GeoDataFrame,
    buffer_m: float = 400.0,
) -> gpd.GeoDataFrame:
    stops_m = _to_utm(stop_freq)
    buf = _buffers(segments, buffer_m)
    j = gpd.sjoin(stops_m, buf, how="inner", predicate="within")
    tph = j.groupby("segment_id")["trips_per_hour"].sum().rename("transit_trips_per_hr")

    cents = _to_utm(segments)[["segment_id", "geometry"]].copy()
    cents["geometry"] = cents.geometry.centroid
    nearest = gpd.sjoin_nearest(cents, stops_m[["geometry"]], how="left",
                                distance_col="nearest_stop_distance_m")
    nearest = nearest.drop_duplicates("segment_id", keep="first")  # equidistant stops tie
    feat = (nearest[["segment_id", "nearest_stop_distance_m"]]
            .merge(tph.reset_index(), on="segment_id", how="left"))
    feat["transit_trips_per_hr"] = feat["transit_trips_per_hr"].fillna(0.0)
    return _merge_checked(segments, feat, "join_transit")


def classify_pois(pois: pd.DataFrame) -> pd.DataFrame:
    """Boolean restaurant / retail / office flags from OSM tags (or a synthetic `category`)."""
    def tagged(col: str) -> pd.Series:
        if col not in pois.columns:
            return pd.Series(False, index=pois.index)
        v = pois[col]
        return v.notna() & ~v.astype(str).str.lower().isin({"", "no", "none", "nan"})

    amenity = pois["amenity"].astype(str).str.lower() if "amenity" in pois.columns else \
        pd.Series("", index=pois.index)
    category = pois["category"].astype(str).str.lower() if "category" in pois.columns else \
        pd.Series("", index=pois.index)
    return pd.DataFrame({
        "restaurant": amenity.isin(RESTAURANT_AMENITIES) | (category == "restaurant"),
        "retail": tagged("shop") | category.isin({"shop", "retail"}),
        "office": tagged("office") | (category == "office"),
    }, index=pois.index)


def join_pois(
    segments: gpd.GeoDataFrame,
    pois: gpd.GeoDataFrame,
    buffer_m: float = 100.0,
) -> gpd.GeoDataFrame:
    pts = _to_utm(pois).reset_index(drop=True)
    pts = gpd.GeoDataFrame(classify_pois(pts), geometry=pts.geometry.representative_point(),
                           crs=UTM)
    buf = _buffers(segments, buffer_m)
    j = gpd.sjoin(pts, buf, how="inner", predicate="within")
    g = j.groupby("segment_id")
    feat = pd.DataFrame({
        "pois_count": g.size(),
        "pois_restaurant": g["restaurant"].sum(),
        "pois_retail": g["retail"].sum(),
        "pois_office": g["office"].sum(),
    }).reindex(pd.Index(buf["segment_id"], name="segment_id")).fillna(0).astype(int)
    return _merge_checked(segments, feat.reset_index(), "join_pois")
