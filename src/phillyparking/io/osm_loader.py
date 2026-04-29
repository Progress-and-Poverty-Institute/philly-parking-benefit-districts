"""OSM loaders via osmnx for the Philadelphia bbox."""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import LineString, Point

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox

log = logging.getLogger(__name__)

DEFAULT_POI_TAGS = {"amenity": ["restaurant", "cafe", "bar"], "shop": True, "office": True}


def _osm_dir() -> Path:
    p = data_dir() / "raw" / "osm"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _synth_graph() -> nx.MultiDiGraph:
    w, s, e, n = philly_bbox()
    G = nx.MultiDiGraph()
    nx_, ny_ = 6, 6
    xs = np.linspace(w, e, nx_)
    ys = np.linspace(s, n, ny_)
    nodes = {}
    nid = 0
    for j in range(ny_):
        for i in range(nx_):
            nodes[(i, j)] = nid
            G.add_node(nid, x=float(xs[i]), y=float(ys[j]))
            nid += 1
    osmid = 9000000
    for j in range(ny_):
        for i in range(nx_):
            if i + 1 < nx_:
                a, b = nodes[(i, j)], nodes[(i + 1, j)]
                geom = LineString([(xs[i], ys[j]), (xs[i + 1], ys[j])])
                G.add_edge(a, b, osmid=osmid, highway="residential", name=f"E{a}-{b}", geometry=geom, length=1.0)
                osmid += 1
            if j + 1 < ny_:
                a, b = nodes[(i, j)], nodes[(i, j + 1)]
                geom = LineString([(xs[i], ys[j]), (xs[i], ys[j + 1])])
                G.add_edge(a, b, osmid=osmid, highway="residential", name=f"E{a}-{b}", geometry=geom, length=1.0)
                osmid += 1
    G.graph["crs"] = "EPSG:4326"
    return G


def load_drive_graph(refresh: bool = False) -> nx.MultiDiGraph:
    cache = _osm_dir() / "drive.graphml"
    if cache.exists() and not refresh:
        try:
            import osmnx as ox

            return ox.load_graphml(cache)
        except (OSError, Exception) as e:
            log.warning("osmnx graph load failed (%s); using synthetic", e)
            return _synth_graph()
    try:
        import osmnx as ox

        w, s, e, n = philly_bbox()
        G = ox.graph_from_bbox(bbox=(w, s, e, n), network_type="drive")
        ox.save_graphml(G, cache)
        return G
    except (OSError, Exception) as e:
        log.warning("osmnx graph fetch failed (%s); using synthetic", e)
        return _synth_graph()


def load_pois(tags: dict | None = None, refresh: bool = False) -> gpd.GeoDataFrame:
    cache = _osm_dir() / "pois.parquet"
    if cache.exists() and not refresh:
        return gpd.read_parquet(cache)
    tags = tags or DEFAULT_POI_TAGS
    try:
        import osmnx as ox

        w, s, e, n = philly_bbox()
        gdf = ox.features_from_bbox(bbox=(w, s, e, n), tags=tags)
        gdf = gdf.reset_index()
        gdf.to_parquet(cache)
        return gdf
    except (OSError, Exception) as exc:
        log.warning("osmnx POI fetch failed (%s); using synthetic", exc)
        rng = np.random.default_rng(11)
        w, s, e, n = philly_bbox()
        N = 300
        rows = []
        cats = ["restaurant", "shop", "office"]
        for i in range(N):
            rows.append(
                {
                    "poi_id": f"P{i:05d}",
                    "category": rng.choice(cats),
                    "geometry": Point(rng.uniform(w, e), rng.uniform(s, n)),
                }
            )
        gdf = gpd.GeoDataFrame(rows, crs=4326)
        gdf.to_parquet(cache)
        return gdf


def graph_to_segments(G: nx.MultiDiGraph) -> gpd.GeoDataFrame:
    """Convert a graph's edges into a LineString GeoDataFrame in EPSG:4326."""
    rows = []
    for u, v, k, d in G.edges(keys=True, data=True):
        geom = d.get("geometry")
        if geom is None:
            ux, uy = G.nodes[u]["x"], G.nodes[u]["y"]
            vx, vy = G.nodes[v]["x"], G.nodes[v]["y"]
            geom = LineString([(ux, uy), (vx, vy)])
        osmid = d.get("osmid")
        if isinstance(osmid, list):
            osmid = osmid[0]
        rows.append(
            {
                "u": u,
                "v": v,
                "key": k,
                "osmid": osmid,
                "highway": d.get("highway"),
                "name": d.get("name"),
                "geometry": geom,
            }
        )
    gdf = gpd.GeoDataFrame(rows, crs=G.graph.get("crs", "EPSG:4326"))
    if str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs(4326)
    gdf["length_m"] = gdf.to_crs(32618).length
    return gdf
