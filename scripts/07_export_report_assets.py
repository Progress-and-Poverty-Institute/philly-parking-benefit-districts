"""Generate the white paper's scenario table and the figures that no other script produces.

Reads the comparison table and saved scenarios written by scripts 05 and 06, plus the
Chatman-Manville sweep table, and writes:

  outputs/reports/white_paper/tables/scenario_comparison.tex
  outputs/figures/zone_map.png
  outputs/figures/occupancy_and_revenue_detail.png
  outputs/figures/cm_sweep_n200_{cruising_dwl_total,revenue_total,peak_occupancy_share_above_85}.png

`--check` regenerates the table in memory and exits 1 if the file on disk differs (the
figures are not compared byte for byte). `--rebuild-cm-sweep` reruns the 200-replication
sweep and rewrites outputs/tables/cm_sweep_n200.parquet first; it takes several minutes.
"""
from __future__ import annotations

import logging
from pathlib import Path

import click
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from phillyparking._config import outputs_dir  # noqa: E402
from phillyparking.scenarios.compare import chatman_manville_sweep  # noqa: E402
from phillyparking.scenarios.runner import default_results_dir, load_saved_scenarios  # noqa: E402
from phillyparking.viz.report_figures import (  # noqa: E402
    cm_sweep_year_chart, occupancy_and_revenue_detail, zone_map_figure,
)
from phillyparking.viz.tables import scenario_comparison_tex  # noqa: E402

log = logging.getLogger(__name__)

CM_METRICS = ("cruising_dwl_total", "revenue_total", "peak_occupancy_share_above_85")
CM_N_REPLICATIONS = 200
CM_YEARS = 5


def table_path() -> Path:
    return outputs_dir() / "reports" / "white_paper" / "tables" / "scenario_comparison.tex"


def render_scenario_table() -> str:
    comp = pd.read_csv(outputs_dir() / "tables" / "comparison_table.csv", index_col=0)
    return scenario_comparison_tex(comp)


@click.command()
@click.option("--check", is_flag=True, help="Exit 1 if scenario_comparison.tex is stale; write nothing.")
@click.option("--rebuild-cm-sweep", is_flag=True,
              help=f"Rerun the {CM_N_REPLICATIONS}-replication sweep and rewrite its parquet first.")
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True)
def main(check: bool, rebuild_cm_sweep: bool, seed: int, verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    tex = render_scenario_table()
    path = table_path()
    if check:
        on_disk = path.read_text(encoding="utf-8") if path.exists() else ""
        if on_disk != tex:
            raise click.ClickException(f"{path} is stale; rerun scripts/07_export_report_assets.py")
        print(f"{path} is up to date")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tex, encoding="utf-8", newline="\n")
    log.info("Wrote %s", path)

    figs = outputs_dir() / "figures"
    fig = zone_map_figure(save_to=figs / "zone_map.png")
    plt.close(fig)
    log.info("Wrote %s", figs / "zone_map.png")

    results = load_saved_scenarios(default_results_dir())
    fig = occupancy_and_revenue_detail(results, save_to=figs / "occupancy_and_revenue_detail.png")
    plt.close(fig)
    log.info("Wrote %s", figs / "occupancy_and_revenue_detail.png")

    sweep_path = outputs_dir() / "tables" / "cm_sweep_n200.parquet"
    if rebuild_cm_sweep:
        log.info("Rerunning the Chatman-Manville sweep (n=%d, %d years)", CM_N_REPLICATIONS, CM_YEARS)
        sweep = chatman_manville_sweep(n_replications=CM_N_REPLICATIONS,
                                       rolls_forward_years=CM_YEARS, seed=seed)
        sweep.to_parquet(sweep_path)
        log.info("Wrote %s", sweep_path)
    sweep = pd.read_parquet(sweep_path)
    for metric in CM_METRICS:
        out = figs / f"cm_sweep_n200_{metric}.png"
        fig = cm_sweep_year_chart(sweep, metric, save_to=out)
        plt.close(fig)
        log.info("Wrote %s", out)

    print(f"report assets complete -> {path.parent}, {figs}")


if __name__ == "__main__":
    main()
