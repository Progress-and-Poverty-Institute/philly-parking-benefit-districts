"""Run policy scenarios and persist ScenarioResults to outputs/models/."""
from __future__ import annotations

import logging
from pathlib import Path

import click
import pandas as pd

from phillyparking._config import data_dir
from phillyparking.spatial.segments import load_segments, build_segments, save_segments
from phillyparking.spatial.zones import assign_zones
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios.provenance import describe_file_source, segment_source
from phillyparking.scenarios.runner import default_results_dir, run_scenario
from phillyparking.scenarios.compare import comparison_table
from phillyparking.scenarios.ranges import run_values, summarize
from phillyparking.elasticity.scenarios import all_scenarios
from phillyparking.spatial.synthetic import make_synthetic_segments

log = logging.getLogger(__name__)

ALL_SCENARIOS = ("status_quo", "seattle", "full_pbd")
HEADLINE_ELASTICITY = "central"


@click.command()
@click.option("--scenario", default=None,
              help=f"Single scenario name; default runs all of {ALL_SCENARIOS}.")
@click.option("--seed", default=42, type=int)
@click.option("--n-seeds", default=20, type=int, show_default=True,
              help="Fixture seeds 0..n-1 for the seed range of the ranges table (0 skips the "
                   "ranges; they are also skipped when a single --scenario is run).")
@click.option("--out", "out_dir", default=None, type=click.Path(),
              help="Output base directory (default: outputs/models).")
@click.option("--verbose", "-v", is_flag=True, help="Verbose (DEBUG) logging.")
def main(scenario: str | None, seed: int, n_seeds: int, out_dir: str | None, verbose: bool) -> None:
    """Run scenarios and write ScenarioResults under <out>/<name>/.

    The scenario results and comparison table are the headline run: the central elasticity
    at --seed. With every scenario selected the script also runs the other two named
    elasticities at that seed and the central elasticity at fixture seeds 0..n-1, and writes
    scenario_ranges.csv (min / max per scenario and metric) and scenario_runs.csv (every run).
    """
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
        seg_source = describe_file_source(seg_path)
        log.info("Loaded segments (n=%d)", len(segs))
    except Exception as exc:  # noqa: BLE001
        log.warning("No saved segments (%s); building from the public layers", exc)
        segs = build_segments()
        segs = assign_zones(segs)
        save_segments(segs, seg_path)
        seg_source = {**describe_file_source(seg_path), "built_this_run": True}

    n_named = int(segs["zone_id"].isin(NAMED_ZONES).sum())
    if n_named < 5:
        log.warning(
            "Loaded segments have only %d in named zones; falling back to "
            "in-package synthetic distribution across all named zones for a "
            "meaningful demo.", n_named,
        )
        segs = make_synthetic_segments(n=120, seed=seed)
        seg_source = {**segment_source(segs), "fallback_reason": f"{n_named} segments in named zones"}
        panel_path.unlink(missing_ok=True)

    if panel_path.exists():
        panel = pd.read_parquet(panel_path)
        seg_source["panel"] = describe_file_source(panel_path)
    else:
        log.info("No saved panel; computing baseline_occupancy")
        panel = baseline_occupancy(segs, seed=seed)
        panel.to_parquet(panel_path)
        seg_source["panel"] = {"kind": "baseline_occupancy", "seed": seed}

    base = Path(out_dir) if out_dir else default_results_dir()
    base.mkdir(parents=True, exist_ok=True)

    names = [scenario] if scenario else list(ALL_SCENARIOS)
    results = {}
    for name in names:
        log.info("Running scenario: %s", name)
        r = run_scenario(name, segments=segs, baseline_panel=panel, seed=seed,
                         segment_source=seg_source)
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

    if len(results) == len(ALL_SCENARIOS) and n_seeds > 0:
        def inputs_for_seed(s: int):
            """Segments and panel a run at seed `s` would use; only the fixture's change with it."""
            if seg_source.get("kind") == "synthetic_fixture":
                sg = make_synthetic_segments(n=120, seed=s)
                return sg, baseline_occupancy(sg, seed=s), {**segment_source(sg)}
            if seg_source.get("panel", {}).get("kind") == "file":
                return segs, panel, seg_source
            # The panel is a deterministic function of segment covariates, so on segments
            # that are not redrawn the seed varies only the consumer-surplus trips.
            return segs, baseline_occupancy(segs, seed=s), seg_source

        if seg_source.get("kind") != "synthetic_fixture":
            log.warning("Segments are not the synthetic fixture, so the seed range reflects "
                        "only the consumer-surplus trips, not segment or panel draws.")
        runs = [run_values(results, HEADLINE_ELASTICITY, seed)]
        quiet = logging.getLogger("phillyparking.scenarios.runner")
        prev_level = quiet.level
        quiet.setLevel(logging.ERROR)  # one warning per run about unpriced zones is noise here
        try:
            elasticity_names = tuple(e.name for e in all_scenarios())
            for ename in elasticity_names:
                if ename == HEADLINE_ELASTICITY:
                    continue
                log.info("Elasticity scenario %s at seed %d", ename, seed)
                runs.append(run_values({
                    n: run_scenario(n, segments=segs, baseline_panel=panel, seed=seed,
                                    elasticity_scenario=ename, segment_source=seg_source)
                    for n in ALL_SCENARIOS
                }, ename, seed))
            for s in range(n_seeds):
                log.info("Seed %d (%d of %d)", s, s + 1, n_seeds)
                sg, pn, src = inputs_for_seed(s)
                runs.append(run_values({
                    n: run_scenario(n, segments=sg, baseline_panel=pn, seed=s, segment_source=src)
                    for n in ALL_SCENARIOS
                }, HEADLINE_ELASTICITY, s))
        finally:
            quiet.setLevel(prev_level)
        all_runs = pd.concat(runs, ignore_index=True)
        ranges = summarize(all_runs, HEADLINE_ELASTICITY, seed, elasticity_names)
        all_runs.to_csv(base / "scenario_runs.csv", index=False)
        ranges.to_csv(base / "scenario_ranges.csv", index=False)
        log.info("Wrote %s and %s", base / "scenario_runs.csv", base / "scenario_ranges.csv")

    print(f"scenarios complete: {list(results)} -> {base}")


if __name__ == "__main__":
    main()
