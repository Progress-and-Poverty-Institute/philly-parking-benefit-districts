from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString

pytest.importorskip("geopandas")

from phillyparking.spatial.zones import assign_zones, zone_summary
from tests.fixtures import make_synthetic_segments


def test_ccc_bbox_assigned():
    seg = make_synthetic_segments()
    out = assign_zones(seg)
    assert (out["zone_id"] == "ccc").all()


def test_other_fallback():
    # Point well outside any configured bbox (mid-Atlantic ocean area)
    rows = [
        {
            "segment_id": "X1",
            "geometry": LineString([(-70.0, 35.0), (-70.0001, 35.0)]),
            "length_m": 80.0,
            "capacity": 5,
        }
    ]
    seg = gpd.GeoDataFrame(rows, crs=4326)
    out = assign_zones(seg)
    assert out["zone_id"].iloc[0] == "other"


def test_zone_summary_contains_expected_columns():
    seg = make_synthetic_segments()
    seg = assign_zones(seg)
    summ = zone_summary(seg)
    for c in ("zone_id", "n_segments", "total_capacity", "total_length_m", "current_rate"):
        assert c in summ.columns
