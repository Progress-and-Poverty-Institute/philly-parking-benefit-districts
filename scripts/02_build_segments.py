"""Build the canonical street-segment table with all spatial joins applied."""
from __future__ import annotations

import logging

import click

from phillyparking._config import data_dir
from phillyparking.io import opendataphilly, census, lodes, osm_loader, gtfs_loader
from phillyparking.spatial.segments import build_segments, save_segments
from phillyparking.spatial.zones import assign_zones, zone_summary
from phillyparking.spatial.join import join_acs, join_lodes, join_pois, join_transit

log = logging.getLogger(__name__)


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(verbose: bool) -> None:
    """Run build_segments + spatial joins, write data/processed/segments.parquet."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    log.info("Loading public layers")
    streets = opendataphilly.fetch_streets()
    meters = opendataphilly.fetch_meters()
    rpp_zones = opendataphilly.fetch_rpp_zones()
    neighborhoods = opendataphilly.fetch_neighborhoods()

    log.info("Building segments (n_streets=%d, n_meters=%d)", len(streets), len(meters))
    segs = build_segments(streets=streets, meters=meters, rpp_zones=rpp_zones, neighborhoods=neighborhoods)

    log.info("Joining ACS")
    try:
        acs = census.fetch_acs_block_groups()
        segs = join_acs(segs, acs)
    except Exception as exc:  # noqa: BLE001
        log.warning("ACS join failed (%s); skipping", exc)

    log.info("Joining LODES")
    try:
        wac = lodes.fetch_wac()
        rac = lodes.fetch_rac()
        segs = join_lodes(segs, wac, rac)
    except Exception as exc:  # noqa: BLE001
        log.warning("LODES join failed (%s); skipping", exc)

    log.info("Joining POIs")
    try:
        pois = osm_loader.load_pois()
        segs = join_pois(segs, pois)
    except Exception as exc:  # noqa: BLE001
        log.warning("POI join failed (%s); skipping", exc)

    log.info("Joining transit")
    try:
        feed = gtfs_loader.load_septa_feed()
        stops = gtfs_loader.stop_frequency(feed)
        segs = join_transit(segs, stops)
    except Exception as exc:  # noqa: BLE001
        log.warning("Transit join failed (%s); skipping", exc)

    segs = assign_zones(segs)

    out_dir = data_dir() / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "segments.parquet"
    save_segments(segs, out_path)

    summary = zone_summary(segs)
    log.info("Zone summary:\n%s", summary.to_string(index=False))
    print(f"segments built: n={len(segs)} -> {out_path}")


if __name__ == "__main__":
    main()
