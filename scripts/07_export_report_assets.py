"""Generate the white paper's scenario table and the figures that no other script produces.

Reads the comparison table and saved scenarios written by scripts 05 and 06, plus the
Chatman-Manville sweep table (with its `.meta.json` provenance), and writes:

  outputs/reports/white_paper/tables/scenario_comparison.tex
  outputs/figures/zone_map.png
  outputs/figures/occupancy_and_revenue_detail.png
  outputs/figures/cm_sweep_{welfare_change,cs_change,search_cost,revenue,mean_price}.png
  outputs/figures/cm_breakeven_{comparator}_vs_{reference}.png   one per configured comparison
  outputs/tables/cm_sweep_cells.csv               median and range per cell x rule x year
  outputs/tables/cm_sweep_paired.csv              each configured comparison, same replication
  outputs/tables/cm_sweep_window_dependence.csv   per comparison and cap, across cells, last year

`--rebuild-cm-form-sensitivity` runs only the demand-form sensitivity and writes
outputs/tables/cm_sweep_form_sensitivity.csv (per comparison, cap and form: the breakeven's
median and range over cells and the welfare-better cell count),
cm_sweep_form_beyond_peak.csv (the rules' prices against each form's revenue peak) and
cm_sweep_form_sensitivity.meta.json (provenance). It reruns the sweep at the config's grid
under the exponential, linear and constant-elasticity forms, 20 replications each, in three
processes; about 15 minutes. The exponential rows there are the headline form at the same 20
replications.

`--check` regenerates the table in memory and exits 1 if the file on disk differs (the
figures are not compared byte for byte). `--rebuild-cm-sweep` reruns the sweep at the
config's size (`chatman_manville_sweep` in config/scenarios.yaml) and rewrites
outputs/tables/cm_sweep.parquet and its .meta.json first; about an hour at 100 replications.
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
from phillyparking.scenarios.cm_sweep import (  # noqa: E402
    FORM_SENSITIVITY_REPLICATIONS, cell_table, chatman_manville_sweep, comparisons_from_config,
    form_sensitivity_sweeps, load_sweep, paired_table, save_form_sensitivity, save_sweep,
    window_dependence,
)
from phillyparking.scenarios.runner import default_results_dir, load_saved_scenarios  # noqa: E402
from phillyparking.viz.report_figures import (  # noqa: E402
    cm_breakeven_chart, cm_sweep_year_chart, occupancy_and_revenue_detail, zone_map_figure,
)
from phillyparking.viz.tables import scenario_comparison_tex  # noqa: E402
from phillyparking.welfare.search_cost import load_search_cost_config  # noqa: E402

log = logging.getLogger(__name__)

CM_METRICS = ("welfare_change", "cs_change", "search_cost", "revenue", "mean_price")


def table_path() -> Path:
    return outputs_dir() / "reports" / "white_paper" / "tables" / "scenario_comparison.tex"


def render_scenario_table() -> str:
    comp = pd.read_csv(outputs_dir() / "tables" / "comparison_table.csv", index_col=0)
    return scenario_comparison_tex(comp)


@click.command()
@click.option("--check", is_flag=True, help="Exit 1 if scenario_comparison.tex is stale; write nothing.")
@click.option("--rebuild-cm-sweep", is_flag=True,
              help="Rerun the Chatman-Manville sweep at the config size and rewrite its parquet first.")
@click.option("--rebuild-cm-form-sensitivity", is_flag=True,
              help="Only: rerun the sweep under each demand form (20 replications) and write the "
                   "form-sensitivity tables. Run alone; writes nothing else.")
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True)
def main(check: bool, rebuild_cm_sweep: bool, rebuild_cm_form_sensitivity: bool, seed: int,
         verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if rebuild_cm_form_sensitivity:
        log.info("Rerunning the sweep under each demand form, %d replications", FORM_SENSITIVITY_REPLICATIONS)
        sweeps = form_sensitivity_sweeps(seed=seed)
        for written in save_form_sensitivity(sweeps, outputs_dir() / "tables"):
            log.info("Wrote %s", written)
        return

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

    sweep_path = outputs_dir() / "tables" / "cm_sweep.parquet"
    if rebuild_cm_sweep:
        log.info("Rerunning the Chatman-Manville sweep at the config's size")
        sweep = chatman_manville_sweep(seed=seed)
        save_sweep(sweep, sweep_path)
        log.info("Wrote %s and its provenance", sweep_path)
    sweep = load_sweep(sweep_path)
    prov = sweep.attrs.get("provenance", {})
    log.info("Sweep provenance: %s, n_replications=%s, seed=%s, commit=%s",
             prov.get("segment_source"), prov.get("n_replications"), prov.get("seed"),
             (prov.get("git") or {}).get("commit"))

    tables = outputs_dir() / "tables"
    paired = paired_table(sweep)
    for name, frame in (("cm_sweep_cells.csv", cell_table(sweep)),
                        ("cm_sweep_paired.csv", paired),
                        ("cm_sweep_window_dependence.csv", window_dependence(paired))):
        frame.to_csv(tables / name, index=False, float_format="%.6g")
        log.info("Wrote %s", tables / name)

    # Year charts at the project's default cap: search_cost and welfare_change depend on it,
    # and the other metrics are the same at every cap.
    default_cap = load_search_cost_config().occupancy_cap
    for metric in CM_METRICS:
        out = figs / f"cm_sweep_{metric}.png"
        fig = cm_sweep_year_chart(sweep, metric, save_to=out, fixed={"occupancy_cap": default_cap})
        plt.close(fig)
        log.info("Wrote %s", out)
    for comparison in comparisons_from_config():
        out = figs / f"cm_breakeven_{comparison[0]}_vs_{comparison[1]}.png"
        fig = cm_breakeven_chart(paired, comparison, save_to=out)
        plt.close(fig)
        log.info("Wrote %s", out)

    print(f"report assets complete -> {path.parent}, {figs}")


if __name__ == "__main__":
    main()
