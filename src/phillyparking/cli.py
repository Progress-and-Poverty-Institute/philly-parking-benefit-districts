"""Command-line entry points for `phillyparking`."""
from __future__ import annotations

import logging

import click


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging.")
def main(verbose: bool) -> None:
    """Philadelphia curb parking pricing model."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@main.command("download-data")
@click.option("--refresh", is_flag=True, help="Re-download even if cached.")
def download_data(refresh: bool) -> None:
    """Download all public data sources."""
    from phillyparking.io import opendataphilly, census, lodes, osm_loader, gtfs_loader
    opendataphilly.fetch_meters(refresh=refresh)
    opendataphilly.fetch_streets(refresh=refresh)
    opendataphilly.fetch_rpp_zones(refresh=refresh)
    opendataphilly.fetch_neighborhoods(refresh=refresh)
    census.fetch_acs_block_groups(refresh=refresh)
    lodes.fetch_wac(refresh=refresh)
    lodes.fetch_rac(refresh=refresh)
    osm_loader.load_drive_graph(refresh=refresh)
    gtfs_loader.load_septa_feed(refresh=refresh)


@main.command("build-segments")
def build_segments_cmd() -> None:
    """Build the canonical segment table to data/processed/segments.parquet."""
    from phillyparking.spatial.segments import build_segments, save_segments
    segs = build_segments()
    save_segments(segs)


@main.command("run-scenarios")
@click.option("--name", default=None, help="Single scenario; default runs all.")
@click.option("--seed", default=42, type=int)
def run_scenarios_cmd(name: str | None, seed: int) -> None:
    """Run scenarios and save results to outputs/models/."""
    from phillyparking.scenarios.runner import run_scenario, run_all_scenarios
    if name:
        result = run_scenario(name=name, seed=seed)
        result.save(None)
    else:
        results = run_all_scenarios(seed=seed)
        for r in results.values():
            r.save(None)


if __name__ == "__main__":
    main()
