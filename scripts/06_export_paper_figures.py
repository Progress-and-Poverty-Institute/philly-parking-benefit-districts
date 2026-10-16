"""Export paper-ready figures and tables from saved scenario results."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

import click
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from phillyparking._config import data_dir, outputs_dir
from phillyparking.scenarios.runner import ScenarioResults, default_results_dir
from phillyparking.scenarios.compare import comparison_table
from phillyparking.scenarios.cm_sweep import chatman_manville_sweep
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.revenue.forecast import revenue_curve
from phillyparking.viz.charts import (
    incidence_bar_chart, chatman_manville_results_chart, laffer_curve,
)

log = logging.getLogger(__name__)

ALL_SCENARIOS = ("status_quo", "seattle", "full_pbd")


def _revenue_by_scenario_chart(table: pd.DataFrame, save_to: Path) -> None:
    """One bar per comparison-table column, so a cycling scenario shows both phases."""
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(table.columns)
    totals = [float(v) for v in table.loc["total_revenue"]]
    palette = {"status_quo": "#888888", "seattle": "#3a86ff", "full_pbd": "#ff006e"}
    colors = [next((c for k, c in palette.items() if n.startswith(k)), "#444444") for n in names]
    ax.bar([n.replace("_phase_", "\nphase ") for n in names], totals, color=colors)
    ax.set_ylabel("Annual revenue (USD)")
    ax.set_title("Annual curb-meter revenue by scenario")
    for i, t in enumerate(totals):
        ax.text(i, t, f"${t/1e6:.2f}M", ha="center", va="bottom")
    fig.tight_layout()
    save_to.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_to, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _placeholder_incidence() -> pd.DataFrame:
    """Constants (50 and -10 in every decile), not a computation: no incidence stage exists.

    Kept only so the white paper's figure reference resolves; the figure says
    PLACEHOLDER on it. Replace with a real decile frame when trip origins are joined to ACS.
    """
    deciles = np.arange(1, 11)
    return pd.DataFrame({
        "decile": deciles,
        "mean_payment": np.full(10, 50.0),
        "mean_cs_change": np.full(10, -10.0),
    })


@click.command()
@click.option("--results-dir", default=None, type=click.Path(),
              help="Where saved scenarios live (default outputs/models).")
@click.option("--seed", default=42, type=int)
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(results_dir: str | None, seed: int, verbose: bool) -> None:
    """Render paper figures and tables under outputs/figures and outputs/tables."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    base = Path(results_dir) if results_dir else default_results_dir()
    figs = outputs_dir() / "figures"
    tables = outputs_dir() / "tables"
    figs.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    results = {}
    for name in ALL_SCENARIOS:
        path = base / name
        if not path.exists():
            log.warning("Missing scenario at %s; skipping", path)
            continue
        results[name] = ScenarioResults.load(path)
        log.info("Loaded %s from %s", name, path)

    if not results:
        raise click.ClickException(f"No scenario results found under {base}")

    table = comparison_table(results)
    rev_path = figs / "revenue_by_scenario.png"
    _revenue_by_scenario_chart(table, rev_path)
    log.info("Wrote %s", rev_path)

    inc_path = figs / "incidence_by_decile.png"
    fig = incidence_bar_chart(_placeholder_incidence(), save_to=inc_path, placeholder=True)
    plt.close(fig)
    log.warning("Wrote %s as a PLACEHOLDER (constants, not a result; no incidence stage exists)",
                inc_path)

    log.info("Running chatman_manville_sweep")
    sweep = chatman_manville_sweep(n_replications=5, rolls_forward_years=4, seed=seed)
    cm_path = figs / "chatman_manville_sweep.png"
    fig = chatman_manville_results_chart(sweep, save_to=cm_path)
    plt.close(fig)
    log.info("Wrote %s", cm_path)

    from phillyparking.spatial.synthetic import make_synthetic_segments

    proc = data_dir() / "processed"
    seg_path = proc / "segments.parquet"
    NAMED_ZONES = {"ccc", "cca", "ucity", "south_philly", "fishtown"}
    segs = load_priced_segments(seg_path) if seg_path.exists() else None
    n_named = int(segs["zone_id"].isin(NAMED_ZONES).sum()) if segs is not None else 0
    if n_named < 5:
        log.warning("Only %d segments in named zones; using synthetic segments for figures", n_named)
        segs = make_synthetic_segments(n=120, seed=seed)
    # Computed, not read from a cache: it is cheap, and a cached panel could belong to
    # other segments or anchors.
    panel = baseline_occupancy(segs, seed=seed)

    ccc_segs = segs[segs["zone_id"] == "ccc"]
    if len(ccc_segs):
        ccc_panel = panel[panel["segment_id"].isin(ccc_segs["segment_id"])]
        baseline_prices = pd.DataFrame({"zone_id": ["ccc"], "price_usd_per_hr": [4.0]})
        curve_df = revenue_curve(ccc_segs, ccc_panel, baseline_prices, elasticity=-0.4)
        ccc_curve = curve_df[curve_df["zone_id"] == "ccc"].sort_values("price")
        laffer_path = figs / "laffer_curve_ccc.png"
        fig = laffer_curve(ccc_curve, save_to=laffer_path)
        plt.close(fig)
        log.info("Wrote %s", laffer_path)
    else:
        log.warning("No ccc segments found; skipping Laffer curve")

    table_path = tables / "comparison_table.csv"
    table.to_csv(table_path)
    log.info("Wrote %s", table_path)

    for name in ("scenario_ranges.csv", "scenario_runs.csv"):
        src = base / name
        if src.exists():
            shutil.copyfile(src, tables / name)
            log.info("Wrote %s", tables / name)
        else:
            log.warning("%s not found; rerun scripts/05_run_scenarios.py for the ranges", src)

    print(f"paper exports complete -> {figs}, {tables}")


if __name__ == "__main__":
    main()
