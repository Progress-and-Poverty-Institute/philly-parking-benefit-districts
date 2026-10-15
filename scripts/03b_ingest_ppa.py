"""Parking Authority export -> occupancy panel by segment, calendar period and hour of week.

Reads sessions, the meter inventory and the rate schedule through the column mapping in
`config/ppa_ingest.yaml` (`phillyparking.ingest.ppa`) and writes, under --out (default
`data/processed/ppa/`):

- `panel.parquet`: segment_id, zone_id, period, hour_of_week, occupancy, paid_occupancy,
  price_usd_per_hr, paid_minutes, n_sessions, n_days, capacity;
- `segments.parquet`: segment_id, zone_id, capacity (spaces), n_locations;
- `meta.json`: source (real or stub), input files with SHA-256, the ingest config with its
  hash, the observation window, the periods and the ingestion report.

`scripts/04_fit_elasticity.py` fits on the panel; `scripts/05_run_scenarios.py --ppa` runs the
scenarios on one period of it.

--stub writes the known-answer stub export (`ppa_stub.make_known_answer_export`) to
`data/raw/ppa_stub/` and ingests it into `data/processed/ppa_stub/`, never into the real
output directory.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import click

from phillyparking._config import config_dir, data_dir
from phillyparking.ingest.ppa import _resolve, ingest, ingest_config
from phillyparking.io.ppa_stub import KNOWN_ANSWER_WINDOW, write_known_answer_export
from phillyparking.io.raw_cache import now_utc
from phillyparking.scenarios.provenance import git_state

log = logging.getLogger(__name__)


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@click.command()
@click.option("--sessions", "sessions_path", default=None, help="Override sessions.path.")
@click.option("--inventory", "inventory_path", default=None, help="Override inventory.path.")
@click.option("--rates", "rates_path", default=None, help="Override rates.path.")
@click.option("--window", nargs=2, default=None,
              help="First and last observed dates (YYYY-MM-DD YYYY-MM-DD). Default: the "
                   "sessions' own range, which drops trailing dates with no sessions.")
@click.option("--out", "out_dir", default=None, type=click.Path(),
              help="Output directory (default data/processed/ppa, or ppa_stub with --stub).")
@click.option("--stub", is_flag=True, help="Ingest the known-answer stub export instead.")
@click.option("--verbose", "-v", is_flag=True)
def main(sessions_path, inventory_path, rates_path, window, out_dir, stub, verbose) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = ingest_config()
    if stub:
        paths = write_known_answer_export(data_dir() / "raw" / "ppa_stub")
        sessions_path, inventory_path, rates_path = (paths["sessions"], paths["inventory"],
                                                     paths["rates"])
        window = window or KNOWN_ANSWER_WINDOW
    files = {
        "sessions": _resolve(sessions_path or cfg["sessions"]["path"]),
        "inventory": _resolve(inventory_path or cfg["inventory"]["path"]),
        "rates": _resolve(rates_path or cfg["rates"]["path"]),
    }
    if not window:
        log.warning("No --window given: the observation window is the sessions' own date range")
    result = ingest(cfg, files["sessions"], files["inventory"], files["rates"],
                    window=tuple(window) if window else None)

    out = Path(out_dir) if out_dir else data_dir() / "processed" / ("ppa_stub" if stub else "ppa")
    out.mkdir(parents=True, exist_ok=True)
    result.panel.to_parquet(out / "panel.parquet")
    result.segments.to_parquet(out / "segments.parquet")
    meta = {
        "created_utc": now_utc(),
        "source": "stub (ppa_stub.make_known_answer_export)" if stub else "real",
        "files": {k: {"path": str(p), "sha256": _sha(p)} for k, p in files.items()},
        "config": {"path": str(config_dir() / "ppa_ingest.yaml"),
                   "sha256": _sha(config_dir() / "ppa_ingest.yaml")},
        "git": git_state(),
        "report": result.report,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    print(f"PPA panel: {len(result.segments)} segments x {len(result.periods)} periods x 168 "
          f"hours -> {out}")


if __name__ == "__main__":
    main()
