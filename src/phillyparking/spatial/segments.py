"""Canonical street-segment GeoDataFrame builder.

Streets are split into pieces of about `target_length_m` (in EPSG:32618). Every input line
is accounted for in `segments.attrs["build_report"]`; nothing is dropped without a count:

- MultiLineStrings are split into their parts, each part keyed by its index.
- Empty geometries and non-line geometries are dropped and counted.
- In an OSM drive graph a two-way street is two directed edges with the same osmid and
  reversed geometry; one of each such pair is dropped (counted as `two_way_twins_dropped`).

Segment ids hash a parent key that identifies the input line: `seg_id` (City Street
Centerline), else `osmid|u|v|key` (an OSM graph edge; osmid alone repeats across edges),
else `osmid|row`, else the row number. Ids are checked unique; a collision raises.

City centerline rows whose street class has no curb (`priced_curb.no_curb_classes` in
`config/zones.yaml`: expressways, ramps, driveways, walkways) are dropped and counted as
`no_curb_dropped`; the class is kept as `street_class`. `assign_priced_curb` then decides
which segments a zone prices: `zone_box` is the zone box the segment lies in, and `zone_id`
is that box only for priced curb, else "other".
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString
from shapely.ops import substring

from phillyparking._config import data_dir, load_config
from phillyparking.spatial.zones import zone_for_point

log = logging.getLogger(__name__)

SEGMENT_LENGTH_TARGET_M = 80.0
METERS_PER_CAR = 7.0
DRIVEWAY_HYDRANT_SLACK = 0.85
RPP_POINT_MAX_DISTANCE_M = 30.0
UTM = 32618


def _seg_id(parent_key: str, idx: int) -> str:
    h = hashlib.sha1(f"{parent_key}|{idx}".encode()).hexdigest()[:12]
    return f"S{h}"


def _split_line(line: LineString, target_m: float) -> list[LineString]:
    """Split a projected line into about-equal pieces near `target_m` long."""
    length_m = line.length
    if length_m <= target_m * 1.25:
        return [line]
    n = max(1, int(round(length_m / target_m)))
    pieces = [substring(line, i / n, (i + 1) / n, normalized=True) for i in range(n)]
    return [p for p in pieces if not p.is_empty and p.length > 0]


def _parent_keys(streets: gpd.GeoDataFrame) -> list[str]:
    cols = set(streets.columns)
    if "seg_id" in cols:
        return [str(v) for v in streets["seg_id"]]
    if {"osmid", "u", "v", "key"} <= cols:
        return [f"{o}|{u}|{v}|{k}" for o, u, v, k in
                zip(streets["osmid"], streets["u"], streets["v"], streets["key"])]
    if "osmid" in cols:
        return [f"{o}|row{i}" for i, o in enumerate(streets["osmid"])]
    return [f"row{i}" for i in range(len(streets))]


def _two_way_twins(streets: gpd.GeoDataFrame, lines_m) -> set[int]:
    """Row positions of the second edge of each (u->v, v->u) pair with the same osmid."""
    if not {"osmid", "u", "v"} <= set(streets.columns):
        return set()
    seen: dict[tuple, int] = {}
    drop: set[int] = set()
    keys = streets["key"] if "key" in streets.columns else pd.Series(0, index=streets.index)
    for pos, (o, u, v, k) in enumerate(zip(streets["osmid"], streets["u"], streets["v"], keys)):
        twin = (str(o), v, u, k)
        if twin in seen and lines_m[seen[twin]] is not None and lines_m[pos] is not None \
                and abs(lines_m[seen[twin]].length - lines_m[pos].length) < 0.5:
            drop.add(pos)
            continue
        seen[(str(o), u, v, k)] = pos
    return drop


def _street_class_col(streets: gpd.GeoDataFrame) -> str | None:
    return next((c for c in ("class", "CLASS", "street_class") if c in streets.columns), None)


def _street_name_col(streets: gpd.GeoDataFrame) -> str | None:
    return next((c for c in ("street_name", "stname", "name") if c in streets.columns), None)


def build_segments(
    streets: gpd.GeoDataFrame | None = None,
    meters: gpd.GeoDataFrame | None = None,
    rpp_zones: gpd.GeoDataFrame | None = None,
    neighborhoods: gpd.GeoDataFrame | None = None,
    target_length_m: float = SEGMENT_LENGTH_TARGET_M,
) -> gpd.GeoDataFrame:
    if streets is None:
        from phillyparking.io.opendataphilly import fetch_neighborhoods, fetch_rpp_zones, fetch_streets

        streets = fetch_streets()
        rpp_zones = rpp_zones if rpp_zones is not None else fetch_rpp_zones()
        neighborhoods = neighborhoods if neighborhoods is not None else fetch_neighborhoods()

    streets = streets.to_crs(4326).reset_index(drop=True)
    class_col = _street_class_col(streets)
    no_curb_dropped = 0
    if class_col:
        no_curb = set(load_config("zones")["priced_curb"]["no_curb_classes"])
        drop = pd.to_numeric(streets[class_col], errors="coerce").isin(no_curb)
        no_curb_dropped = int(drop.sum())
        streets = streets[~drop].reset_index(drop=True)
    lines_m = list(streets.to_crs(UTM).geometry)
    zones = load_config("zones").get("zones", [])
    name_col = _street_name_col(streets)
    parents = _parent_keys(streets)
    twins = _two_way_twins(streets, lines_m)

    report = {"input_rows": len(streets) + no_curb_dropped, "no_curb_dropped": no_curb_dropped,
              "empty_dropped": 0, "non_line_dropped": 0,
              "multipart_rows": 0, "two_way_twins_dropped": len(twins)}
    rows = []
    for idx, geom in enumerate(lines_m):
        if idx in twins:
            continue
        if geom is None or geom.is_empty:
            report["empty_dropped"] += 1
            continue
        if isinstance(geom, MultiLineString):
            report["multipart_rows"] += 1
            parts = [(f"{parents[idx]}|part{j}", g) for j, g in enumerate(geom.geoms)]
        elif isinstance(geom, LineString):
            parts = [(parents[idx], geom)]
        else:
            report["non_line_dropped"] += 1
            continue
        sname = streets[name_col].iloc[idx] if name_col else None
        sclass = pd.to_numeric(streets[class_col].iloc[idx], errors="coerce") if class_col else None
        for key, part in parts:
            for sub_idx, piece in enumerate(_split_line(part, target_length_m)):
                rows.append({
                    "segment_id": _seg_id(key, sub_idx),
                    "geometry": piece,
                    "length_m": float(piece.length),
                    "street_name": sname,
                    "street_class": sclass,
                    "capacity": max(0, int((piece.length / METERS_PER_CAR) * DRIVEWAY_HYDRANT_SLACK)),
                    "has_meter": False,
                    "n_meters": 0,
                })

    seg = gpd.GeoDataFrame(rows, geometry="geometry", crs=UTM).to_crs(4326)
    report["segments"] = len(seg)
    dup = seg["segment_id"].duplicated()
    if dup.any():
        raise ValueError(f"build_segments: {int(dup.sum())} segment ids collide, e.g. "
                         f"{seg.loc[dup, 'segment_id'].head(3).tolist()}")
    cents = seg.to_crs(UTM).geometry.centroid.to_crs(4326)
    seg["zone_id"] = [zone_for_point(p.x, p.y, zones) for p in cents]

    seg["neighborhood"] = None
    if neighborhoods is not None and len(neighborhoods):
        n_col = "neighborhood" if "neighborhood" in neighborhoods.columns else neighborhoods.columns[0]
        pts = gpd.GeoDataFrame(seg[["segment_id"]], geometry=cents, crs=4326)
        j = gpd.sjoin(pts, neighborhoods[[n_col, "geometry"]].to_crs(4326),
                      how="left", predicate="within")
        report["neighborhood_overlaps"] = int(j["segment_id"].duplicated().sum())
        j = j.drop_duplicates("segment_id", keep="first").set_index("segment_id")[n_col]
        seg["neighborhood"] = seg["segment_id"].map(j)
        report["neighborhood_unmatched"] = int(seg["neighborhood"].isna().sum())

    seg["rpp_zone"] = None
    if rpp_zones is not None and len(rpp_zones):
        r_col = "rpp_zone" if "rpp_zone" in rpp_zones.columns else rpp_zones.columns[0]
        rz = rpp_zones[[r_col, "geometry"]].to_crs(UTM)
        if (rz.geom_type == "Point").all():
            # Permit blocks are published as points: the segment takes the nearest one
            # within RPP_POINT_MAX_DISTANCE_M.
            j = gpd.sjoin_nearest(seg[["segment_id", "geometry"]].to_crs(UTM), rz, how="left",
                                  max_distance=RPP_POINT_MAX_DISTANCE_M)
        else:
            pts = gpd.GeoDataFrame(seg[["segment_id"]], geometry=cents, crs=4326).to_crs(UTM)
            j = gpd.sjoin(pts, rz, how="left", predicate="within")
        j = j.drop_duplicates("segment_id", keep="first").set_index("segment_id")[r_col]
        seg["rpp_zone"] = seg["segment_id"].map(j)

    if meters is not None and len(meters):
        buf = seg[["segment_id", "geometry"]].to_crs(UTM)
        buf["geometry"] = buf.geometry.buffer(15.0)
        joined = gpd.sjoin(meters.to_crs(UTM), buf, how="inner", predicate="within")
        counts = joined.groupby("segment_id").size()
        seg["n_meters"] = seg["segment_id"].map(counts).fillna(0).astype(int)
        seg["has_meter"] = seg["n_meters"] > 0

    lost = report["empty_dropped"] + report["non_line_dropped"]
    log.info("build_segments: %s", report)
    if lost:
        log.warning("build_segments: dropped %d of %d input rows (empty or not a line)",
                    lost, report["input_rows"])
    seg.attrs["build_report"] = report
    return seg


def assign_priced_curb(seg: gpd.GeoDataFrame, inventory: bool,
                       cfg: dict | None = None) -> gpd.GeoDataFrame:
    """Set `zone_box`, `priced_curb` and the pricing `zone_id` (see the module docstring).

    With a meter inventory (`inventory=True`) a segment is priced curb when it has a meter.
    Without one there is no public record of which blocks are metered, so the stand-in is a
    street class with curb parking (`street_classes`) and at least `min_commercial_share` of
    the zoned land within `frontage_buffer_m` in the `zoning_group` (`commercial_frontage_share`
    from `join_zoning`). Segments in a zone box that are not priced curb get zone "other": they
    keep their baseline and earn nothing.
    """
    cfg = cfg or load_config("zones")["priced_curb"]
    seg = seg.copy()
    seg["zone_box"] = seg["zone_box"] if "zone_box" in seg.columns else seg["zone_id"]
    if inventory:
        priced = seg["has_meter"].astype(bool)
        rule = "meter inventory: has_meter"
    else:
        if "commercial_frontage_share" not in seg.columns:
            raise ValueError("assign_priced_curb: no meter inventory and no "
                             "commercial_frontage_share; run join_zoning first")
        priced = (seg["street_class"].isin(cfg["street_classes"])
                  & (seg["commercial_frontage_share"] >= float(cfg["min_commercial_share"])))
        rule = (f"no meter inventory: street_class in {list(cfg['street_classes'])} and "
                f"commercial_frontage_share >= {cfg['min_commercial_share']}")
    seg["priced_curb"] = priced & (seg["zone_box"] != "other")
    seg["zone_id"] = seg["zone_box"].where(seg["priced_curb"], "other")
    seg.attrs["priced_curb_rule"] = rule
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
    segs = gpd.read_parquet(path)
    segs.attrs["segment_source"] = {"kind": "file", "path": str(path.resolve())}
    return segs


def load_priced_segments(path: Path | None = None) -> gpd.GeoDataFrame:
    """`load_segments`, keeping only segments in a zone that `config/zones.yaml` prices.

    The rest (zone "other": outside every zone box, or in one but not priced curb) earn
    nothing, are not scored for cruising and carry no trips, so the scenarios leave them out.
    `attrs["segment_source"]` records the filter and both counts.
    """
    segs = load_segments(path)
    zones = {z["id"] for z in load_config("zones")["zones"]}
    keep = segs["zone_id"].isin(zones)
    out = segs[keep].reset_index(drop=True)
    out.attrs["segment_source"] = {**segs.attrs["segment_source"],
                                   "filter": "zone_id priced in config/zones.yaml",
                                   "n_in_file": int(len(segs)), "n_kept": int(keep.sum())}
    return out
