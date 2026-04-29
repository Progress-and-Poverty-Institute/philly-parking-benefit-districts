"""Fit the synthetic baseline-occupancy panel."""
from __future__ import annotations

import logging

import click

from phillyparking._config import data_dir
from phillyparking.spatial.segments import load_segments, save_segments, build_segments
from phillyparking.spatial.zones import assign_zones
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.io.ppa_stub import generate_transactions

log = logging.getLogger(__name__)


@click.command()
@click.option("--seed", default=42, type=int)
@click.option("--with-transactions/--no-transactions", default=True,
              help="Also write a stub transactions sample.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(seed: int, with_transactions: bool, verbose: bool) -> None:
    """Build/load segments, run baseline_occupancy, save panel parquet."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    proc = data_dir() / "processed"
    proc.mkdir(parents=True, exist_ok=True)
    seg_path = proc / "segments.parquet"

    try:
        segs = load_segments(seg_path)
        log.info("Loaded segments from %s (n=%d)", seg_path, len(segs))
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load segments (%s); building from scratch", exc)
        segs = build_segments()
        segs = assign_zones(segs)
        save_segments(segs, seg_path)

    log.info("Computing baseline occupancy panel")
    panel = baseline_occupancy(segs, seed=seed)
    panel_path = proc / "demand_panel.parquet"
    panel.to_parquet(panel_path)
    log.info("Wrote %s (rows=%d)", panel_path, len(panel))

    if with_transactions:
        log.info("Generating stub transactions sample")
        tx = generate_transactions(segs, n_days=7, seed=seed)
        tx_path = proc / "synthetic_transactions.parquet"
        tx.to_parquet(tx_path)
        log.info("Wrote %s (rows=%d)", tx_path, len(tx))

    print(f"baseline panel built: rows={len(panel)} -> {panel_path}")


if __name__ == "__main__":
    main()
