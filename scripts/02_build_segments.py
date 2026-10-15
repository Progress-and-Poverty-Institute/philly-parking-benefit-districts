"""Build the canonical street-segment table with all spatial joins applied.

Every join runs or the script fails: a missing layer is an error, not a skipped column.
`data/processed/segments.meta.json` records the provenance marker of every input layer and
the segment builder's report, so a synthetic input is visible downstream. Synthetic
stand-ins are used only with --allow-synthetic.
"""
from __future__ import annotations

import json
import logging

import click

from phillyparking._config import data_dir
from phillyparking.io import census, gtfs_loader, lodes, opendataphilly, osm_loader
from phillyparking.io.raw_cache import now_utc, provenance_of
from phillyparking.spatial.join import join_acs, join_lodes, join_pois, join_transit
from phillyparking.spatial.segments import build_segments, save_segments
from phillyparking.spatial.zones import zone_summary

log = logging.getLogger(__name__)


@click.command()
@click.option("--allow-synthetic", is_flag=True,
              help="Use synthetic stand-ins for layers whose real fetch fails (recorded in "
                   "segments.meta.json).")
@click.option("--meters", "meters_path", default=None, type=click.Path(exists=True),
              help="Parking Authority meter inventory (any file ingest.ppa can read) to mark "
                   "metered segments; there is no public inventory.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(allow_synthetic: bool, meters_path: str | None, verbose: bool) -> None:
    """Run build_segments + spatial joins, write data/processed/segments.parquet."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    syn = allow_synthetic
    layers = {}

    def got(name, obj):
        layers[name] = provenance_of(obj) or {"kind": "unknown"}
        return obj

    streets = got("streets", opendataphilly.fetch_streets(allow_synthetic=syn))
    rpp = got("rpp_zones", opendataphilly.fetch_rpp_zones(allow_synthetic=syn))
    neighborhoods = got("neighborhoods", opendataphilly.fetch_neighborhoods(allow_synthetic=syn))
    meters = None
    if meters_path:
        from phillyparking.ingest.ppa import inventory_points, load_inventory

        meters = inventory_points(load_inventory(meters_path))
        layers["meters"] = {"kind": "real", "source": "Parking Authority inventory",
                            "path": meters_path}

    log.info("Building segments (n_streets=%d)", len(streets))
    segs = build_segments(streets=streets, meters=meters, rpp_zones=rpp,
                          neighborhoods=neighborhoods)

    acs = got("acs", census.fetch_acs_block_groups(allow_synthetic=syn))
    segs = join_acs(segs, acs, uncovered="drop")
    wac = got("lodes_wac", lodes.fetch_wac(allow_synthetic=syn))
    rac = got("lodes_rac", lodes.fetch_rac(allow_synthetic=syn))
    blocks = got("lodes_blocks", lodes.fetch_block_points(allow_synthetic=syn))
    segs = join_lodes(segs, wac, rac, blocks)
    pois = got("pois", osm_loader.load_pois(allow_synthetic=syn))
    segs = join_pois(segs, pois)
    stops = got("transit", gtfs_loader.load_stop_frequency(allow_synthetic=syn))
    segs = join_transit(segs, stops)

    out_dir = data_dir() / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "segments.parquet"
    save_segments(segs, out_path)
    synthetic = sorted(k for k, m in layers.items() if m.get("kind") != "real")
    meta = {"created_utc": now_utc(), "n_segments": len(segs), "layers": layers,
            "synthetic_layers": synthetic, "build_report": segs.attrs.get("build_report")}
    (out_dir / "segments.meta.json").write_text(json.dumps(meta, indent=2, default=str),
                                                encoding="utf-8")

    log.info("Zone summary:\n%s", zone_summary(segs).to_string(index=False))
    if synthetic:
        log.warning("Segments built with SYNTHETIC layers: %s", synthetic)
    print(f"segments built: n={len(segs)} -> {out_path}"
          + (f" (synthetic layers: {', '.join(synthetic)})" if synthetic else ""))


if __name__ == "__main__":
    main()
