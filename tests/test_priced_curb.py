"""Which real segments a zone prices, and which calibration anchors a segment gets.

Without a meter inventory a zone prices curb streets (City centerline classes 2-5) whose
frontage is mostly commercially zoned; roads with no curb are dropped from the segment table;
real segments use the `philadelphia` anchor set and the fixture its own. No test touches
data/ or the network: geometry is built in EPSG:32618 around Center City."""
from __future__ import annotations

import importlib.util

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, box

from phillyparking._config import load_config, project_root
from phillyparking.demand.synthetic_baseline import (anchor_set_for_source, baseline_occupancy,
                                                     panel_cache_key)
from phillyparking.spatial.join import join_zoning
from phillyparking.spatial.segments import (assign_priced_curb, build_segments,
                                            load_priced_segments, save_segments)
from phillyparking.spatial.synthetic import make_synthetic_segments

X0, Y0 = 486_000.0, 4_422_000.0  # UTM 18N, inside the Center City Core box
COMMERCIAL = "Commercial/Commercial Mixed-Use"
RESIDENTIAL = "Residential/Multi-Family/Residential Mixed-Use"


def _utm(geoms, **cols) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(dict(cols), geometry=list(geoms), crs=32618)


def _hline(x, y, length=80.0):
    return LineString([(x, y), (x + length, y)])


# --- street classes ----------------------------------------------------------------------------

def test_roads_without_a_curb_are_dropped_and_counted():
    no_curb = load_config("zones")["priced_curb"]["no_curb_classes"]
    classes = [5, 2, no_curb[0], no_curb[-1], 13]
    streets = _utm([_hline(X0, Y0 + 50 * i) for i in range(len(classes))],
                   seg_id=list(range(len(classes))), **{"class": classes}).to_crs(4326)
    seg = build_segments(streets=streets)
    assert sorted(seg["street_class"].unique()) == [2, 5, 13]
    rep = seg.attrs["build_report"]
    assert rep["no_curb_dropped"] == 2 and rep["input_rows"] == len(classes)


# --- commercial frontage -----------------------------------------------------------------------

def test_commercial_frontage_share_reads_both_sides_of_the_street():
    # Lots start 10 m from the centerline (zoning stops at the property line) and run 40 m back.
    segs = _utm([_hline(X0, Y0), _hline(X0, Y0 + 500), _hline(X0, Y0 + 1000)],
                segment_id=["both", "one_side", "none"]).to_crs(4326)

    def lots(y, north, south):
        return [(box(X0 - 50, y + 10, X0 + 130, y + 50), north),
                (box(X0 - 50, y - 50, X0 + 130, y - 10), south)]

    parts = (lots(Y0, COMMERCIAL, COMMERCIAL) + lots(Y0 + 500, COMMERCIAL, RESIDENTIAL)
             + lots(Y0 + 1000, RESIDENTIAL, RESIDENTIAL))
    zoning = _utm([g for g, _ in parts], zoninggroup=[z for _, z in parts]).to_crs(4326)
    out = join_zoning(segs, zoning, buffer_m=25).set_index("segment_id")
    share = out["commercial_frontage_share"]
    assert share["both"] == pytest.approx(1.0)
    assert share["one_side"] == pytest.approx(0.5, abs=1e-6)
    assert share["none"] == pytest.approx(0.0)


def test_no_zoned_land_in_reach_is_zero_frontage():
    segs = _utm([_hline(X0, Y0)], segment_id=["s"]).to_crs(4326)
    zoning = _utm([box(X0, Y0 + 500, X0 + 50, Y0 + 550)], zoninggroup=[COMMERCIAL]).to_crs(4326)
    assert join_zoning(segs, zoning)["commercial_frontage_share"].iloc[0] == 0.0


# --- priced curb -------------------------------------------------------------------------------

def _frame(**cols):
    n = len(next(iter(cols.values()))) if cols else 1
    base = {"segment_id": [f"s{i}" for i in range(n)], "has_meter": [False] * n,
            "street_class": [5] * n, "commercial_frontage_share": [1.0] * n,
            "zone_id": ["ccc"] * n}
    return pd.DataFrame({**base, **cols})


def test_stand_in_prices_commercial_curb_inside_a_zone_box_only():
    seg = _frame(street_class=[5, 5, 13, 2, 5],
                 commercial_frontage_share=[0.9, 0.2, 0.9, 0.5, 0.9],
                 zone_id=["ccc", "ccc", "ccc", "south_philly", "other"])
    out = assign_priced_curb(seg, inventory=False)
    assert out["priced_curb"].tolist() == [True, False, False, True, False]
    assert out["zone_id"].tolist() == ["ccc", "other", "other", "south_philly", "other"]
    assert out["zone_box"].tolist() == ["ccc", "ccc", "ccc", "south_philly", "other"]
    assert "commercial_frontage_share >= 0.5" in out.attrs["priced_curb_rule"]


def test_a_meter_inventory_replaces_the_stand_in():
    seg = _frame(has_meter=[True, False], commercial_frontage_share=[0.0, 1.0])
    out = assign_priced_curb(seg, inventory=True)
    assert out["zone_id"].tolist() == ["ccc", "other"]
    assert out.attrs["priced_curb_rule"].startswith("meter inventory")


def test_stand_in_needs_the_zoning_join():
    with pytest.raises(ValueError, match="join_zoning"):
        assign_priced_curb(_frame().drop(columns="commercial_frontage_share"), inventory=False)


def test_load_priced_segments_keeps_priced_zones_and_records_the_filter(tmp_path):
    segs = make_synthetic_segments(n=60, seed=3)
    path = save_segments(segs, tmp_path / "segments.parquet")
    out = load_priced_segments(path)
    zones = {z["id"] for z in load_config("zones")["zones"]}
    assert set(out["zone_id"]) <= zones
    assert len(out) == int(segs["zone_id"].isin(zones).sum()) < len(segs)
    src = out.attrs["segment_source"]
    assert src["kind"] == "file" and src["n_in_file"] == len(segs) and src["n_kept"] == len(out)


# --- anchor sets -------------------------------------------------------------------------------

def test_anchor_set_follows_the_recorded_segment_source(tmp_path):
    fixture = make_synthetic_segments(n=20, seed=1)
    assert anchor_set_for_source(fixture) == "synthetic_fixture"
    loaded = load_priced_segments(save_segments(fixture, tmp_path / "s.parquet"))
    assert anchor_set_for_source(loaded) == "philadelphia"
    assert baseline_occupancy(loaded).attrs["calibration"]["anchor_set"] == "philadelphia"
    assert panel_cache_key(loaded, 1) != panel_cache_key(loaded, 1, anchor_set="synthetic_fixture")


def test_segments_with_no_recorded_source_are_refused():
    bare = pd.DataFrame(make_synthetic_segments(n=10, seed=2)).copy()
    bare.attrs = {}
    with pytest.raises(ValueError, match="pass anchor_set="):
        baseline_occupancy(bare)
    assert len(baseline_occupancy(bare, anchor_set="synthetic_fixture")) == 10 * 168


def test_derived_anchors_put_about_five_percent_of_the_reference_at_each_end():
    spec = importlib.util.spec_from_file_location(
        "derive_anchors", project_root() / "scripts" / "derive_baseline_anchors.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rng = np.random.default_rng(0)
    n = 2000
    segs = pd.DataFrame({
        "priced_curb": np.r_[np.ones(n, bool), np.zeros(50, bool)],
        "jobs_within_200m": rng.lognormal(7, 1.5, n + 50),
        "pois_count": rng.poisson(5, n + 50),
        "pop_density": rng.lognormal(8.5, 1.0, n + 50),
        "transit_trips_per_hr": rng.lognormal(5, 0.7, n + 50),
    })
    weights = load_config("demand_baseline")["covariates"]
    d = mod.derive(segs, weights)
    assert d["n"] == n
    ref = segs[segs["priced_curb"]]
    lam = sum(float(weights[c]["intensity_weight"])
              * (np.log1p(ref[c]) - d["centers"][c]) / d["scales"][c] for c in weights)
    assert 0.03 < (lam <= d["intensity_low"]).mean() < 0.07
    assert 0.03 < (lam >= d["intensity_high"]).mean() < 0.07
