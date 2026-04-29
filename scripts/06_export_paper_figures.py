"""Export paper-ready figures and tables from saved scenario results."""
from __future__ import annotations

import logging
from pathlib import Path

import click
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from phillyparking._config import data_dir, outputs_dir
from phillyparking.scenarios.runner import ScenarioResults
from phillyparking.scenarios.compare import comparison_table, chatman_manville_sweep
from phillyparking.spatial.segments import load_segments, build_segments, save_segments
from phillyparking.spatial.zones import assign_zones
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.revenue.forecast import revenue_curve
from phillyparking.viz.charts import (
    incidence_bar_chart, chatman_manville_results_chart, laffer_curve,
)

log = logging.getLogger(__name__)

ALL_SCENARIOS = ("status_quo", "seattle", "full_pbd")


def _revenue_by_scenario_chart(results: dict, save_to: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(results.keys())
    totals = [float(r.revenue["annual_revenue_usd"].sum()) for r in results.values()]
    ax.bar(names, totals, color=["#888888", "#3a86ff", "#ff006e"])
    ax.set_ylabel("Annual revenue (USD)")
    ax.set_title("Annual curb-meter revenue by scenario")
    for i, t in enumerate(totals):
        ax.text(i, t, f"${t/1e6:.2f}M", ha="center", va="bottom")
    fig.tight_layout()
    save_to.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(save_to, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _synthetic_incidence() -> pd.DataFrame:
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

    base = Path(results_dir) if results_dir else (outputs_dir() / "models")
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

    rev_path = figs / "revenue_by_scenario.png"
    _revenue_by_scenario_chart(results, rev_path)
    log.info("Wrote %s", rev_path)

    inc_path = figs / "incidence_by_decile.png"
    fig = incidence_bar_chart(_synthetic_incidence(), save_to=inc_path)
    plt.close(fig)
    log.info("Wrote %s (synthetic --- replace when LODES join lands)", inc_path)

    log.info("Running chatman_manville_sweep")
    sweep = chatman_manville_sweep(n_replications=20, rolls_forward_years=3, seed=seed)
    cm_path = figs / "chatman_manville_sweep.png"
    fig = chatman_manville_results_chart(sweep, save_to=cm_path)
    plt.close(fig)
    log.info("Wrote %s", cm_path)

    from phillyparking.spatial.synthetic import make_synthetic_segments

    proc = data_dir() / "processed"
    seg_path = proc / "segments.parquet"
    panel_path = proc / "demand_panel.parquet"
    NAMED_ZONES = {"ccc", "cca", "ucity", "south_philly", "fishtown"}
    try:
        segs = load_segments(seg_path)
    except Exception:  # noqa: BLE001
        segs = build_segments()
        segs = assign_zones(segs)
        save_segments(segs, seg_path)
    n_named = int(segs["zone_id"].isin(NAMED_ZONES).sum())
    if n_named < 5:
        log.warning("Only %d segments in named zones; using synthetic segments for figures", n_named)
        segs = make_synthetic_segments(n=120, seed=seed)
        panel_path = proc / "demand_panel_synthetic.parquet"
    panel = pd.read_parquet(panel_path) if panel_path.exists() else baseline_occupancy(segs, seed=seed)

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

    table = comparison_table(results)
    table_path = tables / "comparison_table.csv"
    table.to_csv(table_path)
    log.info("Wrote %s", table_path)

    print(f"paper exports complete -> {figs}, {tables}")


if __name__ == "__main__":
    main()
