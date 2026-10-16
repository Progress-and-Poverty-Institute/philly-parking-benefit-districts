"""OSM loaders via osmnx for the Philadelphia bbox, cached with provenance markers
(`phillyparking.io.raw_cache`)."""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import LineString, Point

from phillyparking._config import data_dir
from phillyparking.io._bbox import philly_bbox
from phillyparking.io.raw_cache import Layer, load_layer

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


def _fetch_graph() -> nx.MultiDiGraph:
    import osmnx as ox

    w, s, e, n = philly_bbox()
    return ox.graph_from_bbox(bbox=(w, s, e, n), network_type="drive")


def _save_graph(G: nx.MultiDiGraph, path) -> None:
    import osmnx as ox

    ox.save_graphml(G, path)


def _read_graph(path) -> nx.MultiDiGraph:
    import osmnx as ox

    return ox.load_graphml(path)


def load_drive_graph(refresh: bool = False, allow_synthetic: bool | None = None) -> nx.MultiDiGraph:
    layer = Layer(name="osm.drive_graph", path=_osm_dir() / "drive.graphml",
                  source="OpenStreetMap drive network (osmnx, Overpass) for the Philadelphia bbox",
                  url="https://overpass-api.de/api/interpreter", fetch=_fetch_graph,
                  write=_save_graph, read=_read_graph, synth=_synth_graph)
    return load_layer(layer, refresh, allow_synthetic)


def _fetch_pois(tags: dict) -> gpd.GeoDataFrame:
    import osmnx as ox

    w, s, e, n = philly_bbox()
    gdf = ox.features_from_bbox(bbox=(w, s, e, n), tags=tags).reset_index()
    if len(gdf) == 0:
        raise ValueError("Overpass returned 0 POIs")
    return gdf


def _synth_pois() -> gpd.GeoDataFrame:
    rng = np.random.default_rng(11)
    w, s, e, n = philly_bbox()
    rows = []
    for i in range(300):
        rows.append({"poi_id": f"P{i:05d}", "category": rng.choice(["restaurant", "shop", "office"]),
                     "geometry": Point(rng.uniform(w, e), rng.uniform(s, n))})
    return gpd.GeoDataFrame(rows, crs=4326)


def load_pois(tags: dict | None = None, refresh: bool = False,
              allow_synthetic: bool | None = None) -> gpd.GeoDataFrame:
    tags = tags or DEFAULT_POI_TAGS
    layer = Layer(name="osm.pois", path=_osm_dir() / "pois.parquet",
                  source=f"OpenStreetMap features (osmnx, Overpass), tags {tags}",
                  url="https://overpass-api.de/api/interpreter", fetch=lambda: _fetch_pois(tags),
                  write=lambda g, p: g.to_parquet(p), read=gpd.read_parquet, synth=_synth_pois)
    return load_layer(layer, refresh, allow_synthetic)


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
