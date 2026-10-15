"""Ranges around the headline scenario table: elasticity scenarios and fixture seeds.

The headline table (`comparison_table`) is one run: the central elasticity and one seed.
Two things move it that the run cannot show.

* Elasticity. `config/elasticity_priors.yaml` names three (pessimistic, central,
  optimistic). The labels follow the elasticity's size, not the revenue: both reforms are
  net price cuts in the fixture, so the "pessimistic" (most elastic) value gives the
  highest revenue and the "optimistic" one the lowest.
* The seed. On the synthetic fixture the seed draws the segments (zone labels, capacities,
  covariates), the occupancy panel and the consumer-surplus trips, so any one row, the
  Seattle cruising cost above all, is a single draw. The seed range is the spread of that draw.

A scenario that cycles with period 2 has two states and no single outcome, so its values
pool both phases (min and max take in both).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from phillyparking.scenarios.compare import comparison_table

# Rows of the comparison table that are not outcomes of the policy.
_NOT_OUTCOMES = {"review_year", "converged", "n_zones_at_ceiling"}


def _scenario_of(column: str) -> str:
    return column.partition("_phase_")[0]


def run_values(results: dict, elasticity: str, seed: int) -> pd.DataFrame:
    """One long row per (scenario column, metric) of this run's comparison table."""
    table = comparison_table(results).drop(index=list(_NOT_OUTCOMES), errors="ignore")
    long = table.stack().rename("value").reset_index()
    long.columns = ["metric", "column", "value"]
    long.insert(0, "scenario", long["column"].map(_scenario_of))
    long.insert(0, "seed", seed)
    long.insert(0, "elasticity_scenario", elasticity)
    return long


def summarize(runs: pd.DataFrame, headline_elasticity: str, headline_seed: int,
              elasticity_names: tuple[str, ...]) -> pd.DataFrame:
    """Ranges per (scenario, metric) from the long `run_values` rows.

    `headline_*` and `<elasticity>_*` use the headline seed. `seed_*` uses every seed run at
    the headline elasticity (the headline seed included), and `n_seeds` counts them. Each
    cell pools a cycling scenario's phases.
    """
    rows = []
    for (scenario, metric), g in runs.groupby(["scenario", "metric"], sort=False):
        at_seed = g[g["seed"] == headline_seed]
        head = at_seed[at_seed["elasticity_scenario"] == headline_elasticity]["value"]
        row = {"scenario": scenario, "metric": metric,
               "headline_lo": float(head.min()), "headline_hi": float(head.max())}
        for name in elasticity_names:
            if name == headline_elasticity:
                continue
            v = at_seed[at_seed["elasticity_scenario"] == name]["value"]
            row[f"{name}_lo"] = float(v.min()) if len(v) else np.nan
            row[f"{name}_hi"] = float(v.max()) if len(v) else np.nan
        by_seed = g[g["elasticity_scenario"] == headline_elasticity]
        sv = by_seed["value"]
        row["seed_lo"] = float(sv.min())
        row["seed_p50"] = float(sv.median())
        row["seed_hi"] = float(sv.max())
        row["n_seeds"] = int(by_seed["seed"].nunique())
        rows.append(row)
    return pd.DataFrame(rows)
