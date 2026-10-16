"""Audit findings 17 and 18: loaders never cache a synthetic layer under a real name, every
file under data/raw/ has a provenance marker, script 01 exits non-zero on a failed fetch, and
the four named loader bugs stay fixed. No test touches the network."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import types
import zipfile

import pandas as pd
import pytest
import requests
from click.testing import CliRunner

from phillyparking._config import project_root
from phillyparking.io import census, gtfs_loader, opendataphilly, ppa_stub
from phillyparking.io.raw_cache import (Layer, LayerFetchError, UnknownProvenanceError,
                                        load_layer, marker_path, read_marker, synthetic_path)


def _layer(tmp_path, fetch, synth=lambda: pd.DataFrame({"x": [0]})):
    return Layer(name="test.layer", path=tmp_path / "layer.parquet", source="test source",
                 url="https://example.invalid/layer", fetch=fetch,
                 write=lambda d, p: d.to_parquet(p), read=pd.read_parquet, synth=synth)


def _fail():
    raise requests.ConnectionError("network down")


def test_real_fetch_is_cached_with_a_real_marker(tmp_path):
    calls = []
    layer = _layer(tmp_path, lambda: calls.append(1) or pd.DataFrame({"x": [1, 2]}))
    df = load_layer(layer, retries=1)
    assert df.attrs["provenance"]["kind"] == "real"
    m = read_marker(layer.path)
    assert m["kind"] == "real" and m["url"] == layer.url and m["fetched_utc"]
    again = load_layer(layer, retries=1)
    assert len(calls) == 1 and again.attrs["provenance"]["kind"] == "real"


def test_failed_fetch_raises_and_writes_nothing(tmp_path):
    layer = _layer(tmp_path, _fail)
    with pytest.raises(LayerFetchError, match="network down"):
        load_layer(layer, retries=2, backoff_s=0)
    assert not layer.path.exists() and not synthetic_path(layer.path).exists()


def test_synthetic_fallback_is_opt_in_and_never_under_the_real_name(tmp_path):
    layer = _layer(tmp_path, _fail)
    df = load_layer(layer, allow_synthetic=True, retries=1)
    assert df.attrs["provenance"]["kind"] == "synthetic"
    assert not layer.path.exists()
    spath = synthetic_path(layer.path)
    assert spath.name == "layer.synthetic.parquet" and spath.exists()
    m = read_marker(spath)
    assert m["kind"] == "synthetic" and "network down" in m["reason"]


def test_environment_switch_allows_synthetic(tmp_path, monkeypatch):
    monkeypatch.setenv("PHILLYPARKING_ALLOW_SYNTHETIC", "1")
    assert load_layer(_layer(tmp_path, _fail), retries=1).attrs["provenance"]["kind"] == "synthetic"


def test_unmarked_cache_under_a_real_name_is_refused(tmp_path):
    """The pre-marker loaders left synthetic layers under real names with no marker."""
    layer = _layer(tmp_path, lambda: pd.DataFrame({"x": [1]}))
    pd.DataFrame({"x": [9]}).to_parquet(layer.path)
    with pytest.raises(UnknownProvenanceError, match="no provenance marker"):
        load_layer(layer, retries=1)
    df = load_layer(layer, refresh=True, retries=1)
    assert df["x"].tolist() == [1] and read_marker(layer.path)["kind"] == "real"


def test_marker_saying_synthetic_under_real_name_is_refused(tmp_path):
    layer = _layer(tmp_path, lambda: pd.DataFrame({"x": [1]}))
    pd.DataFrame({"x": [9]}).to_parquet(layer.path)
    marker_path(layer.path).write_text(json.dumps({"kind": "synthetic"}), encoding="utf-8")
    with pytest.raises(UnknownProvenanceError):
        load_layer(layer, retries=1)


def test_retry_recovers_from_a_transient_failure(tmp_path):
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise requests.Timeout("slow")
        return pd.DataFrame({"x": [1]})

    assert load_layer(_layer(tmp_path, flaky), retries=3, backoff_s=0).attrs["provenance"]["kind"] == "real"
    assert len(attempts) == 3


# --- script 01 -------------------------------------------------------------------------------

def _script01():
    spec = importlib.util.spec_from_file_location(
        "s01", project_root() / "scripts" / "01_download_public_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_real(**kw):
    df = pd.DataFrame({"x": [1]})
    df.attrs["provenance"] = {"kind": "real", "url": "https://example.invalid"}
    return df


def _fake_fail(**kw):
    if kw.get("allow_synthetic"):
        df = pd.DataFrame({"x": [0]})
        df.attrs["provenance"] = {"kind": "synthetic", "reason": "network down"}
        return df
    raise LayerFetchError("network down")


@pytest.mark.parametrize("extra", [[], ["--allow-synthetic"]])
def test_script_01_exits_nonzero_when_a_real_fetch_fails(monkeypatch, extra):
    mod = _script01()
    monkeypatch.setattr(mod, "LAYERS", {"a.ok": _fake_real, "b.bad": _fake_fail})
    out = CliRunner().invoke(mod.main, ["--only", "a", "--only", "b", *extra])
    assert out.exit_code == 1
    assert "b.bad" in out.output


def test_script_01_exits_zero_when_every_layer_is_real(monkeypatch):
    mod = _script01()
    monkeypatch.setattr(mod, "LAYERS", {"a.ok": _fake_real})
    out = CliRunner().invoke(mod.main, ["--only", "a"])
    assert out.exit_code == 0, out.output


# --- the four loader bugs of finding 17 --------------------------------------------------------

class _Resp:
    def __init__(self, body, ok=True, ctype="application/json"):
        self._body, self.ok, self.status_code = body, ok, 200 if ok else 500
        self.headers = {"Content-Type": ctype}
        self.content = json.dumps(body).encode() if not isinstance(body, bytes) else body

    def json(self):
        return self._body

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError("500")


def test_arcgis_streets_are_paged_to_the_end(monkeypatch):
    def page(n0, n):
        return {"type": "FeatureCollection", "exceededTransferLimit": n0 + n < 5, "features": [
            {"type": "Feature", "properties": {"seg_id": i, "stname": f"S{i}"},
             "geometry": {"type": "LineString", "coordinates": [[-75.16, 39.95], [-75.159, 39.95]]}}
            for i in range(n0, n0 + n)]}

    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params["resultOffset"])
        return _Resp(page(params["resultOffset"], min(2, 5 - params["resultOffset"])))

    monkeypatch.setattr(opendataphilly.requests, "get", fake_get)
    gdf = opendataphilly._fetch_streets()
    assert calls == [0, 2, 4] and sorted(gdf["seg_id"]) == [0, 1, 2, 3, 4]


def test_meters_have_no_public_source():
    with pytest.raises(LayerFetchError, match="no public meter inventory"):
        opendataphilly.fetch_meters(allow_synthetic=False)
    assert opendataphilly.fetch_meters(allow_synthetic=True).attrs["provenance"]["kind"] == "synthetic"


def test_acs_sentinels_become_nan():
    rows = [["B19013_001E", "B01003_001E", "B25044_001E", "B25046_001E", "B25003_002E",
             "B25003_003E", "B02001_002E", "state", "county", "tract", "block group"],
            ["-666666666", "0", "0", "-666666666", "0", "0", "0", "42", "101", "000101", "1"],
            ["55000", "1200", "500", "400", "200", "300", "600", "42", "101", "000102", "2"]]
    df = census.parse_acs_json(rows)
    assert df["GEOID"].tolist() == ["421010001011", "421010001022"]
    assert df["median_hh_income"].isna().tolist() == [True, False]
    assert df.loc[1, "aggregate_vehicles"] == 400


def test_census_errors_never_carry_the_api_key(monkeypatch):
    monkeypatch.setenv("CENSUS_API_KEY", "SECRET-KEY-123")

    def boom(*a, **k):
        raise requests.ConnectionError("Max retries exceeded with url: /acs5?key=SECRET-KEY-123")

    monkeypatch.setattr(census.requests, "get", boom)
    with pytest.raises(RuntimeError) as e:
        census._fetch_acs(2022)
    assert "SECRET" not in str(e.value)
    monkeypatch.setattr(census.requests, "get",
                        lambda *a, **k: _Resp(b"<html>Missing Key</html>", ctype="text/html"))
    with pytest.raises(ValueError, match="not JSON"):
        census._fetch_acs(2022)


def test_acs_without_a_key_fails_instead_of_going_synthetic(monkeypatch, tmp_path):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.setenv("PHILLYPARKING_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("phillyparking.io.raw_cache.time.sleep", lambda s: None)
    with pytest.raises(LayerFetchError, match="CENSUS_API_KEY"):
        census.fetch_acs_block_groups(allow_synthetic=False)
    assert not any(p.suffix == ".parquet" for p in tmp_path.rglob("*"))


def _zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_septa_nested_archive_yields_both_inner_feeds():
    inner = _zip({"stop_times.txt": b"trip_id,stop_id\n"})
    outer = _zip({"google_bus.zip": inner, "google_rail.zip": inner})
    assert sorted(gtfs_loader.inner_feeds(outer)) == ["google_bus", "google_rail"]
    assert list(gtfs_loader.inner_feeds(inner)) == ["feed"]


def test_trips_per_hour_counts_band_departures_of_active_trips():
    stops = pd.DataFrame({"stop_id": ["a", "b", "c"], "stop_lon": [0, 0, 0], "stop_lat": [0, 0, 0]})
    st = pd.DataFrame({
        "trip_id": ["t1", "t1", "t2", "t3", "t4"],
        "stop_id": ["a", "b", "a", "a", "a"],
        "departure_time": ["07:10:00", "07:20:00", "08:59:00", "09:00:00", "07:30:00"],
    })
    out = gtfs_loader.trips_per_hour(stops, ["t1", "t2", "t3"], st, ("07:00:00", "09:00:00"))
    got = out.set_index("stop_id")["trips_per_hour"]
    # a: t1 07:10 and t2 08:59 in band (t3 at 09:00 is out, t4 inactive) -> 2 / 2 h
    assert got.to_dict() == {"a": 1.0, "b": 0.5, "c": 0.0}


def test_real_transactions_requested_but_missing_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("PPA_DATA_SOURCE", "real")
    monkeypatch.setenv("PPA_DATA_PATH", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        ppa_stub.load_transactions()


def test_osm_fetches_run_with_the_osmnx_cache_off(monkeypatch):
    """A fetch must reach Overpass: osmnx's own response cache would answer an old query and the
    marker would date it as this fetch. The setting is restored afterwards, even on error."""
    from phillyparking.io import osm_loader

    seen = []
    fake = types.SimpleNamespace(settings=types.SimpleNamespace(use_cache=True))

    def graph_from_bbox(**kw):
        seen.append(fake.settings.use_cache)
        return "graph"

    def features_from_bbox(**kw):
        seen.append(fake.settings.use_cache)
        raise RuntimeError("boom")

    fake.graph_from_bbox, fake.features_from_bbox = graph_from_bbox, features_from_bbox
    monkeypatch.setitem(sys.modules, "osmnx", fake)

    assert osm_loader._fetch_graph() == "graph"
    assert fake.settings.use_cache is True
    with pytest.raises(RuntimeError):
        osm_loader._fetch_pois({"shop": True})
    assert seen == [False, False] and fake.settings.use_cache is True
