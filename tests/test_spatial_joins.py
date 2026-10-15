"""Audit finding 19: each join column computes what its name says, and the segment builder
accounts for every street. Geometry is built in EPSG:32618 (metres) around Center City so
every expected value is exact arithmetic."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, box

from phillyparking._config import load_config
from phillyparking.spatial.join import join_acs, join_lodes, join_pois, join_transit
from phillyparking.spatial.segments import build_segments
from phillyparking.spatial.zones import zone_for_point

X0, Y0 = 486_000.0, 4_422_000.0  # UTM 18N, Center City


def _utm(geoms, **cols) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(dict(cols), geometry=list(geoms), crs=32618)


def _seg(ids, lines) -> gpd.GeoDataFrame:
    return _utm(lines, segment_id=ids).to_crs(4326)


def _hline(x, y, length=80.0):
    return LineString([(x, y), (x + length, y)])


# --- ACS --------------------------------------------------------------------------------------

def _bgs():
    # Two 1 km x 1 km block groups side by side.
    a, b = box(X0, Y0, X0 + 1000, Y0 + 1000), box(X0 + 1000, Y0, X0 + 2000, Y0 + 1000)
    return _utm([a, b], GEOID=["A", "B"], ALAND=[1e6, 1e6], total_pop=[10_000, 2_000],
                median_hh_income=[40_000.0, 100_000.0], households=[4_000, 1_000],
                aggregate_vehicles=[2_000, 1_500], tenure_owner=[1_000, 500],
                tenure_renter=[3_000, 500], race_white=[5_000, 1_000]).to_crs(4326)


def test_acs_density_is_people_per_km2_of_the_block_group():
    segs = _seg(["in_a", "straddle"], [_hline(X0 + 400, Y0 + 500),
                                       _hline(X0 + 960, Y0 + 300)])  # 40 m in A, 40 m in B
    out = join_acs(segs, _bgs()).set_index("segment_id")
    assert out.loc["in_a", "pop_density"] == pytest.approx(10_000, rel=1e-6)
    assert out.loc["straddle", "pop_density"] == pytest.approx(6_000, rel=0.01)
    assert out.loc["in_a", "vehicles_per_hh"] == pytest.approx(0.5)
    assert out.loc["in_a", "pct_renter"] == pytest.approx(0.75)
    assert out.loc["in_a", "pct_white"] == pytest.approx(0.5)


def test_acs_weights_are_renormalised_over_the_covered_part():
    """A segment half outside every block group keeps its block group's income, not half."""
    segs = _seg(["edge"], [_hline(X0 - 40, Y0 + 500)])
    out = join_acs(segs, _bgs()).set_index("segment_id")
    assert out.loc["edge", "median_hh_income"] == pytest.approx(40_000)
    assert 0.4 < out.loc["edge", "acs_coverage"] < 0.6


def test_acs_uncovered_segments_raise_or_are_dropped():
    segs = _seg(["in_a", "away"], [_hline(X0 + 400, Y0 + 500), _hline(X0 + 50_000, Y0)])
    with pytest.raises(ValueError, match="touch no block group"):
        join_acs(segs, _bgs())
    assert join_acs(segs, _bgs(), uncovered="drop")["segment_id"].tolist() == ["in_a"]


# --- LODES ------------------------------------------------------------------------------------

def _blocks_points():
    pts = [Point(X0, Y0 + 100), Point(X0, Y0 + 150), Point(X0 + 1000, Y0)]
    return _utm(pts, tabblk2020=["b1", "b2", "b3"]).to_crs(4326)


def _wac():
    return pd.DataFrame({"w_geocode": ["b1", "b2", "b3"], "C000": [100, 50, 1000],
                         "CNS07": [10, 0, 0], "CNS18": [20, 50, 0], "CNS09": [5, 0, 0],
                         "CNS12": [15, 0, 500]})


def _rac():
    return pd.DataFrame({"h_geocode": ["b1", "b2", "b3"], "C000": [7, 3, 0]})


def test_jobs_are_counted_from_the_blocks_inside_the_buffer():
    segs = _seg(["near", "far"], [_hline(X0 - 40, Y0), _hline(X0 + 300_000, Y0)])
    out = join_lodes(segs, _wac(), _rac(), _blocks_points()).set_index("segment_id")
    # b1 (100 m) and b2 (150 m) are within 200 m; b3 is 1 km away.
    assert out.loc["near", "jobs_within_200m"] == 150
    assert out.loc["near", "workers_within_200m"] == 10
    assert out.loc["near", "jobs_retail_share"] == pytest.approx(10 / 150)
    assert out.loc["near", "jobs_food_accommodation_share"] == pytest.approx(70 / 150)
    assert out.loc["near", "jobs_office_share"] == pytest.approx(20 / 150)
    # Moved 300 km away it has no jobs; the old area-share join gave every segment ~the same.
    assert out.loc["far", "jobs_within_200m"] == 0
    assert np.isnan(out.loc["far", "jobs_retail_share"])


def test_polygon_blocks_split_jobs_by_area_inside():
    blk = _utm([box(X0 - 200, Y0 - 50, X0 + 600, Y0 + 50)], tabblk2020=["b1"]).to_crs(4326)
    wac = pd.DataFrame({"w_geocode": ["b1"], "C000": [800]})
    rac = pd.DataFrame({"h_geocode": ["b1"], "C000": [0]})
    # buffer 200 m around a point-like 0.01 m line at X0 covers x in [-200, 200]: half the block
    segs = _seg(["s"], [_hline(X0, Y0, length=0.01)])
    out = join_lodes(segs, wac, rac, blk)
    assert out["jobs_within_200m"].iloc[0] == pytest.approx(400, rel=0.02)


def test_jobs_in_blocks_the_geography_lacks_raise():
    wac = _wac()
    wac.loc[2, "w_geocode"] = "not_a_block"
    with pytest.raises(ValueError, match="vintage"):
        join_lodes(_seg(["s"], [_hline(X0, Y0)]), wac, _rac(), _blocks_points())


# --- transit and POIs -------------------------------------------------------------------------

def test_transit_sums_departures_at_stops_within_400m():
    stops = _utm([Point(X0, Y0 + 100), Point(X0, Y0 + 390), Point(X0, Y0 + 900)],
                 stop_id=["a", "b", "c"], trips_per_hour=[4.0, 6.0, 100.0]).to_crs(4326)
    out = join_transit(_seg(["s"], [_hline(X0 - 40, Y0)]), stops)
    assert out["transit_trips_per_hr"].iloc[0] == pytest.approx(10.0)
    assert out["nearest_stop_distance_m"].iloc[0] == pytest.approx(100.0, abs=0.5)


def test_pois_from_real_osm_tags_count_retail():
    """Real OSM features carry `amenity`, `shop`, `office`; retail must not read zero."""
    pois = _utm([Point(X0 + 10, Y0 + 20), Point(X0 + 20, Y0 + 20), Point(X0 + 30, Y0 + 20),
                 box(X0 + 40, Y0 + 10, X0 + 50, Y0 + 30), Point(X0 + 5000, Y0)],
                amenity=["restaurant", None, None, "cafe", "bar"],
                shop=[None, "bakery", None, None, None],
                office=[None, None, "company", None, None]).to_crs(4326)
    out = join_pois(_seg(["s"], [_hline(X0, Y0)]), pois).iloc[0]
    assert (out["pois_count"], out["pois_restaurant"], out["pois_retail"], out["pois_office"]) == (4, 2, 1, 1)


def test_pois_from_synthetic_category_still_work():
    pois = _utm([Point(X0 + 10, Y0 + 20), Point(X0 + 20, Y0 + 20)],
                category=["shop", "office"]).to_crs(4326)
    out = join_pois(_seg(["s"], [_hline(X0, Y0)]), pois).iloc[0]
    assert (out["pois_retail"], out["pois_office"], out["pois_restaurant"]) == (1, 1, 0)


# --- segment builder --------------------------------------------------------------------------

def _osm_edges():
    """Five edges of one OSM way (shared osmid), plus the reverse twin of the first."""
    rows = []
    for i in range(5):
        rows.append({"osmid": 777, "u": i, "v": i + 1, "key": 0, "name": "Market St",
                     "geometry": _hline(X0 + 200 * i, Y0, 200.0)})
    rows.append({"osmid": 777, "u": 1, "v": 0, "key": 0, "name": "Market St",
                 "geometry": LineString([(X0 + 200, Y0), (X0, Y0)])})
    return gpd.GeoDataFrame(rows, crs=32618).to_crs(4326)


def test_edges_sharing_an_osmid_keep_their_length():
    seg = build_segments(streets=_osm_edges())
    assert seg["segment_id"].is_unique
    assert seg["length_m"].sum() == pytest.approx(1000.0, rel=1e-3)  # was 43% after id collisions
    assert seg.attrs["build_report"]["two_way_twins_dropped"] == 1


def test_multilinestrings_are_split_not_dropped():
    streets = gpd.GeoDataFrame({"seg_id": [1, 2]}, geometry=[
        MultiLineString([_hline(X0, Y0), _hline(X0, Y0 + 50)]), _hline(X0, Y0 + 100)],
        crs=32618).to_crs(4326)
    seg = build_segments(streets=streets)
    assert seg["length_m"].sum() == pytest.approx(240.0, rel=1e-3)
    assert seg.attrs["build_report"]["multipart_rows"] == 1


def test_non_line_rows_are_counted_when_dropped():
    streets = gpd.GeoDataFrame({"seg_id": [1, 2]}, geometry=[_hline(X0, Y0), Point(X0, Y0)],
                               crs=32618).to_crs(4326)
    seg = build_segments(streets=streets)
    assert len(seg) == 1 and seg.attrs["build_report"]["non_line_dropped"] == 1


def test_neighborhood_survives_the_join_and_rpp_points_attach():
    streets = gpd.GeoDataFrame({"seg_id": [1]}, geometry=[_hline(X0, Y0)], crs=32618).to_crs(4326)
    nb = _utm([box(X0 - 500, Y0 - 500, X0 + 500, Y0 + 500)],
              neighborhood=["Rittenhouse"]).to_crs(4326)
    rpp = _utm([Point(X0 + 40, Y0 + 10), Point(X0 + 40, Y0 + 400)],
               rpp_zone=["7", "9"]).to_crs(4326)
    seg = build_segments(streets=streets, neighborhoods=nb, rpp_zones=rpp)
    assert "neighborhood_left" not in seg.columns
    assert seg["neighborhood"].tolist() == ["Rittenhouse"]
    assert seg["rpp_zone"].tolist() == ["7"]


def test_meters_mark_their_segments():
    streets = gpd.GeoDataFrame({"seg_id": [1, 2]}, geometry=[_hline(X0, Y0),
                                                            _hline(X0, Y0 + 300)],
                               crs=32618).to_crs(4326)
    meters = _utm([Point(X0 + 10, Y0 + 5), Point(X0 + 50, Y0 - 5)], m=["a", "b"]).to_crs(4326)
    seg = build_segments(streets=streets, meters=meters).sort_values("length_m")
    assert sorted(seg["n_meters"].tolist()) == [0, 2]


# --- zone assignment ----------------------------------------------------------------------------

def test_overlapping_zone_boxes_resolve_to_the_most_specific():
    zones = load_config("zones")["zones"]
    # In CCA's and CCC's boxes -> CCC; in CCA's and University City's -> ucity; in CCA's only -> cca.
    assert zone_for_point(-75.155, 39.950, zones) == "ccc"
    assert zone_for_point(-75.185, 39.955, zones) == "ucity"
    assert zone_for_point(-75.135, 39.970, zones) == "fishtown"
    assert zone_for_point(-75.175, 39.940, zones) == "cca"
    assert zone_for_point(-75.000, 40.100, zones) == "other"
