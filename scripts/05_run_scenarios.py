"""Run policy scenarios and persist ScenarioResults to outputs/models/."""
from __future__ import annotations

import logging
from pathlib import Path

import click
import pandas as pd

from phillyparking._config import data_dir, outputs_dir
from phillyparking.spatial.segments import load_segments, build_segments, save_segments
from phillyparking.spatial.zones import assign_zones
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios.runner import run_scenario
from phillyparking.scenarios.compare import comparison_table

log = logging.getLogger(__name__)

ALL_SCENARIOS = ("status_quo", "seattle", "full_pbd")


@click.command()
@click.option("--scenario", default=None,
              help=f"Single scenario name; default runs all of {ALL_SCENARIOS}.")
@click.option("--seed", default=42, type=int)
@click.option("--out", "out_dir", default=None, type=click.Path(),
              help="Output base directory (default: outputs/models).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(scenario: str | None, seed: int, out_dir: str | None, verbose: bool) -> None:
    """Run scenarios and write ScenarioResults under <out>/<name>/."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    proc = data_dir() / "processed"
    seg_path = proc / "segments.parquet"
    panel_path = proc / "demand_panel.parquet"

    NAMED_ZONES = {"ccc", "cca", "ucity", "south_philly", "fishtown"}
    try:
        segs = load_segments(seg_path)
        log.info("Loaded segments (n=%d)", len(segs))
    except Exception as exc:  # noqa: BLE001
        log.warning("No saved segments (%s); building synthetic", exc)
        segs = build_segments()
        segs = assign_zones(segs)
        save_segments(segs, seg_path)

    n_named = int(segs["zone_id"].isin(NAMED_ZONES).sum())
    if n_named < 5:
        from phillyparking.spatial.synthetic import make_synthetic_segments
        log.warning(
            "Loaded segments have only %d in named zones; falling back to "
            "in-package synthetic distribution across all named zones for a "
            "meaningful demo.", n_named,
        )
        segs = make_synthetic_segments(n=120, seed=seed)
        panel_path.unlink(missing_ok=True)

    if panel_path.exists():
        panel = pd.read_parquet(panel_path)
    else:
        log.info("No saved panel; computing baseline_occupancy")
        panel = baseline_occupancy(segs, seed=seed)
        panel.to_parquet(panel_path)

    base = Path(out_dir) if out_dir else (outputs_dir() / "models")
    base.mkdir(parents=True, exist_ok=True)

    names = [scenario] if scenario else list(ALL_SCENARIOS)
    results = {}
    for name in names:
        log.info("Running scenario: %s", name)
        r = run_scenario(name, segments=segs, baseline_panel=panel, seed=seed)
        target = base / name
        r.save(target)
        log.info("  saved -> %s (revenue=$%.0f)", target,
                 r.revenue["annual_revenue_usd"].sum())
        results[name] = r

    if len(results) > 1:
        table = comparison_table(results)
        log.info("Comparison table:\n%s", table.to_string())
        table_path = base / "comparison_table.csv"
        table.to_csv(table_path)
        log.info("Wrote %s", table_path)

    print(f"scenarios complete: {list(results)} -> {base}")


if __name__ == "__main__":
    main()
