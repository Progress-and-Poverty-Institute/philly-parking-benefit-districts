"""Download all public data layers used by the pricing model into data/raw/.

Each layer is cached with a provenance marker (`<file>.provenance.json`). The script prints
one line per layer with its kind (real or synthetic) and exits 1 if any real fetch failed,
whether or not a synthetic stand-in was written for it. Synthetic stand-ins are written only
with --allow-synthetic, and only under `.synthetic` filenames.

There is no public meter inventory; it comes from the Parking Authority (see
`phillyparking.ingest.ppa`), so this script does not fetch one.
"""
from __future__ import annotations

import logging
import sys

import click

from phillyparking._config import data_dir
from phillyparking.io import census, gtfs_loader, lodes, opendataphilly, osm_loader
from phillyparking.io.raw_cache import provenance_of, read_marker

log = logging.getLogger(__name__)

LAYERS = {
    "opendataphilly.streets": opendataphilly.fetch_streets,
    "opendataphilly.rpp_zones": opendataphilly.fetch_rpp_zones,
    "opendataphilly.neighborhoods": opendataphilly.fetch_neighborhoods,
    "opendataphilly.zoning": opendataphilly.fetch_zoning,
    "census.acs_block_groups": census.fetch_acs_block_groups,
    "lodes.wac": lodes.fetch_wac,
    "lodes.rac": lodes.fetch_rac,
    "lodes.block_points": lodes.fetch_block_points,
    "osm.drive_graph": osm_loader.load_drive_graph,
    "osm.pois": osm_loader.load_pois,
}


def _septa(refresh: bool, allow_synthetic: bool):
    if allow_synthetic:
        return gtfs_loader.load_stop_frequency(refresh=refresh, allow_synthetic=True)
    gtfs_loader.load_septa_archive(refresh=refresh)
    return None


def fetch_all(refresh: bool, allow_synthetic: bool, only: tuple[str, ...] = ()) -> list[dict]:
    """Fetch each layer; return one status row per layer. Never raises for one layer's failure."""
    rows = []
    layers = {**LAYERS, "septa.gtfs": None}
    for name, fn in layers.items():
        if only and not any(name.startswith(o) for o in only):
            continue
        log.info("Fetching %s ...", name)
        try:
            if fn is None:
                obj = _septa(refresh, allow_synthetic)
                marker = provenance_of(obj) if obj is not None else read_marker(
                    gtfs_loader._gtfs_dir() / "septa.zip")
            else:
                obj = fn(refresh=refresh, allow_synthetic=allow_synthetic)
                marker = provenance_of(obj) or {}
            kind = (marker or {}).get("kind", "unknown")
            rows.append({"layer": name, "status": "ok" if kind == "real" else kind,
                         "detail": (marker or {}).get("reason") or (marker or {}).get("url")})
        except Exception as exc:  # noqa: BLE001 - reported per layer, and the exit code is 1
            log.error("  -> %s FAILED: %s", name, exc)
            rows.append({"layer": name, "status": "FAILED", "detail": str(exc)})
    return rows


@click.command()
@click.option("--refresh", is_flag=True, help="Re-download even if cached.")
@click.option("--allow-synthetic", is_flag=True,
              help="Write a synthetic stand-in (under a .synthetic filename) for any layer whose "
                   "real fetch fails. The script still exits 1.")
@click.option("--only", multiple=True,
              help="Fetch only layers whose name starts with this (repeatable), e.g. --only lodes.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(refresh: bool, allow_synthetic: bool, only: tuple[str, ...], verbose: bool) -> None:
    """Fetch Open Data Philly, ACS, LODES, OSM and SEPTA layers into data/raw/."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    rows = fetch_all(refresh, allow_synthetic, only)
    width = max(len(r["layer"]) for r in rows) if rows else 10
    print(f"public data -> {data_dir() / 'raw'}")
    for r in rows:
        print(f"  {r['layer']:<{width}}  {r['status']:<9}  {r['detail'] or ''}")
    bad = [r["layer"] for r in rows if r["status"] != "ok"]
    if bad:
        print(f"{len(bad)} of {len(rows)} layers are not real: {', '.join(bad)}", file=sys.stderr)
        sys.exit(1)
    print(f"all {len(rows)} layers real")


if __name__ == "__main__":
    main()
