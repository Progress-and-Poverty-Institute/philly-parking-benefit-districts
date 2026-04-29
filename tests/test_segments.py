from __future__ import annotations

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString

pytest.importorskip("geopandas")

from phillyparking.spatial.segments import build_segments


def _long_streets():
    """A handful of long lines that should be split into ~80m pieces."""
    # 0.005 deg lat ~ 555m at this latitude; build 5 lines of varying length
    rows = []
    for i, dlon in enumerate([0.004, 0.006, 0.008, 0.005, 0.003]):
        line = LineString([(-75.155, 39.952 + i * 0.001), (-75.155 + dlon, 39.952 + i * 0.001)])
        rows.append({"osmid": 1000 + i, "name": f"Street {i}", "highway": "residential", "geometry": line})
    return gpd.GeoDataFrame(rows, crs=4326)


def test_target_length_within_tolerance():
    streets = _long_streets()
    seg = build_segments(streets=streets, meters=None, rpp_zones=None, neighborhoods=None)
    median = float(np.median(seg["length_m"]))
    assert abs(median - 80.0) < 20.0, f"median segment length {median} too far from 80m"


def test_segment_id_unique_and_stable():
    streets = _long_streets()
    a = build_segments(streets=streets)
    b = build_segments(streets=streets)
    assert a["segment_id"].is_unique
    assert list(a["segment_id"]) == list(b["segment_id"])


def test_capacity_non_negative():
    streets = _long_streets()
    seg = build_segments(streets=streets)
    assert (seg["capacity"] >= 0).all()
