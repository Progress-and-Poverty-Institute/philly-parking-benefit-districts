"""Download all public data layers used by the pricing model."""
from __future__ import annotations

import logging
from pathlib import Path

import click

from phillyparking._config import data_dir
from phillyparking.io import opendataphilly, census, lodes, osm_loader, gtfs_loader

log = logging.getLogger(__name__)


def _safe(label: str, fn, *args, **kwargs):
    log.info("Fetching %s ...", label)
    try:
        result = fn(*args, **kwargs)
        log.info("  -> %s OK", label)
        return result
    except Exception as exc:  # noqa: BLE001
        log.warning("  -> %s FAILED: %s", label, exc)
        return None


def _summarize(raw: Path) -> str:
    if not raw.exists():
        return "(no data/raw/ directory)"
    rows = []
    for p in sorted(raw.rglob("*")):
        if p.is_file():
            rows.append(f"{p.relative_to(raw)} ({p.stat().st_size // 1024} KB)")
    return "\n".join(rows) if rows else "(empty)"


@click.command()
@click.option("--refresh", is_flag=True, help="Re-download even if cached.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(refresh: bool, verbose: bool) -> None:
    """Fetch OpenDataPhilly, ACS, LODES, OSM, and SEPTA layers into data/raw/."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _safe("opendataphilly.meters", opendataphilly.fetch_meters, refresh=refresh)
    _safe("opendataphilly.streets", opendataphilly.fetch_streets, refresh=refresh)
    _safe("opendataphilly.rpp_zones", opendataphilly.fetch_rpp_zones, refresh=refresh)
    _safe("opendataphilly.neighborhoods", opendataphilly.fetch_neighborhoods, refresh=refresh)
    _safe("opendataphilly.zoning", opendataphilly.fetch_zoning, refresh=refresh)
    _safe("census.acs_block_groups", census.fetch_acs_block_groups, refresh=refresh)
    _safe("lodes.wac", lodes.fetch_wac, refresh=refresh)
    _safe("lodes.rac", lodes.fetch_rac, refresh=refresh)
    _safe("osm.drive_graph", osm_loader.load_drive_graph, refresh=refresh)
    _safe("osm.pois", osm_loader.load_pois, refresh=refresh)
    _safe("gtfs.septa_feed", gtfs_loader.load_septa_feed, refresh=refresh)

    raw = data_dir() / "raw"
    log.info("data/raw/ contents:\n%s", _summarize(raw))
    print(f"public data fetch complete -> {raw}")


if __name__ == "__main__":
    main()
