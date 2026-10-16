"""Build the synthetic baseline-occupancy panel for the saved segment table.

Fails (exit 1) when the segment table is missing or the panel has NaN or out-of-range
occupancy (`runner.check_panel`), instead of writing it. Writes the panel's cache key
(`demand_panel.key`) beside it so script 05 reuses the panel only for the same segments,
covariates, anchors and seed.

Observed occupancy from the Parking Authority comes from `scripts/03b_ingest_ppa.py`.
"""
from __future__ import annotations

import logging

import click

from phillyparking._config import data_dir
from phillyparking.demand.synthetic_baseline import baseline_occupancy, panel_cache_key
from phillyparking.scenarios.runner import check_panel
from phillyparking.spatial.segments import load_segments

log = logging.getLogger(__name__)


@click.command()
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(seed: int, verbose: bool) -> None:
    """Load segments, run baseline_occupancy, save the panel parquet and its cache key."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    proc = data_dir() / "processed"
    seg_path = proc / "segments.parquet"
    segs = load_segments(seg_path)  # missing -> FileNotFoundError: run script 02 first
    log.info("Loaded segments from %s (n=%d)", seg_path, len(segs))

    panel = baseline_occupancy(segs, seed=seed)
    check_panel(panel, "baseline panel")
    panel_path = proc / "demand_panel.parquet"
    panel.to_parquet(panel_path)
    (proc / "demand_panel.key").write_text(panel_cache_key(segs, seed), encoding="utf-8")
    log.info("Wrote %s (rows=%d, calibration %s)", panel_path, len(panel),
             panel.attrs.get("calibration"))
    print(f"baseline panel built: rows={len(panel)} -> {panel_path}")


if __name__ == "__main__":
    main()
