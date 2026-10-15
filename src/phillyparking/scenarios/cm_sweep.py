"""The Chatman-Manville sweep: targeting rules run paired on the same noisy demand draws.

Design (what the sweep is, and is not):

* Every rule starts each zone at the same flat rate and reviews it once a year for
  `rolls_forward_years`, under constant-elasticity demand (`apply_elasticity`), on a
  fixture panel perturbed once by i.i.d. N(0, sigma) noise per segment-hour.
* The noise draw is shared by every rule, elasticity and sigma within a replication
  (`z = N(0,1)` fixed per replication, noise = sigma * z), so rule differences are paired.
* The sweep prices every hour of the week (rates move in meter-off hours too), so each
  metric comes in two forms: `*_total` over all 168 hours and `*_priced_hours` over the hours
  `config/zones.yaml` prices. The Seattle rule sets rates only on priced hours.
* Cruising DWL is scored at the band's upper edge (`1 - occ_high` vacancy), the line the
  peak rule raises on.

What it can show: how rules that watch different statistics of the same occupancy panel move
prices, occupancy and revenue when demand is as the fixture generates it. What it cannot show:
whether the peak rule is better in Philadelphia. The fixture has no within-zone dispersion
beyond the baseline's diurnal shape and no off-peak price response beyond the common
elasticity, so which rule wins is largely fixed by the panel's shape. Read the cell tables
and the window dependence, not a pooled ratio.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import (
    PEAK_RULE, load_targeting_config, review,
)
from phillyparking.scenarios.provenance import config_hashes, git_state, segment_source

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 52
SWEEP_METRICS = (
    "cruising_dwl_total", "cruising_dwl_priced_hours", "revenue_total", "revenue_priced_hours",
    "peak_occupancy_share_above_85", "mean_price_priced_hours", "zone_price_gini",
)
KEYS = ["elasticity", "noise_sigma", "rule", "replication", "year"]


def _noise(seed: int, rep: int, n: int) -> np.ndarray:
    """The standard-normal draw shared by every rule, elasticity and sigma in replication `rep`."""
    return np.random.default_rng(np.random.SeedSequence([int(seed), int(rep)])).standard_normal(n)


def _year_metrics(panel: pd.DataFrame, segments: pd.DataFrame, target_vacancy: float) -> dict:
    from phillyparking.welfare.cruising_dwl import annual_cruising_dwl
    from phillyparking.welfare.incidence import gini

    priced = frame_priced_mask(panel)
    value = (panel["occupancy"] * panel["capacity"] * panel["price_usd_per_hr"]).to_numpy()
    zone_peak = panel.groupby("zone_id")["occupancy"].quantile(load_targeting_config().peak_quantile)
    zone_mean_price = panel.groupby("zone_id")["price_usd_per_hr"].mean().to_numpy()
    return {
        "cruising_dwl_total": float(annual_cruising_dwl(
            panel, segments, target_vacancy=target_vacancy, priced_hours_only=False)["annual_dwl_usd"].sum()),
        "cruising_dwl_priced_hours": float(annual_cruising_dwl(
            panel, segments, target_vacancy=target_vacancy, priced_hours_only=True)["annual_dwl_usd"].sum()),
        # The weekly panel is one typical week; a year is WEEKS_PER_YEAR of them.
        "revenue_total": float(value.sum() * WEEKS_PER_YEAR),
        "revenue_priced_hours": float(value[priced].sum() * WEEKS_PER_YEAR),
        "peak_occupancy_share_above_85": float((zone_peak > 1.0 - target_vacancy).mean()),
        "mean_price_priced_hours": float(panel.loc[priced, "price_usd_per_hr"].mean()) if priced.any() else float("nan"),
        "zone_price_gini": float(gini(zone_mean_price)),
    }


def chatman_manville_sweep(
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    elasticity_values: list[float] | None = None,
    noise_sigmas: list[float] | None = None,
    rules: list[str] | None = None,
    n_replications: int | None = None,
    rolls_forward_years: int | None = None,
    seed: int = 42,
    start_price: float | None = None,
) -> pd.DataFrame:
    """Rows of elasticity x noise_sigma x rule x replication x year with `SWEEP_METRICS`.

    Arguments left as None come from `chatman_manville_sweep` in `config/scenarios.yaml`.
    `result.attrs["provenance"]` records the segment source, grid, seed, config hashes and
    git state; `save_sweep` writes it beside the parquet.
    """
    from phillyparking.demand.synthetic_baseline import baseline_occupancy
    from phillyparking.elasticity.scenarios import apply_elasticity
    from phillyparking.spatial.synthetic import make_synthetic_segments

    cfg = load_config("scenarios")["chatman_manville_sweep"]
    elasticity_values = list(cfg["elasticity_values"] if elasticity_values is None else elasticity_values)
    noise_sigmas = list(cfg["demand_noise_sigma"] if noise_sigmas is None else noise_sigmas)
    rules = list(cfg["rules"] if rules is None else rules)
    n_replications = int(cfg["n_replications"] if n_replications is None else n_replications)
    rolls_forward_years = int(cfg["rolls_forward_years"] if rolls_forward_years is None else rolls_forward_years)
    start_price = float(cfg["start_price_usd"] if start_price is None else start_price)
    if PEAK_RULE not in rules:
        logger.warning("%s is not among the rules; the paired tables have no reference", PEAK_RULE)

    if segments is None:
        segments = make_synthetic_segments(n=20)
    baseline_note = "supplied panel"
    if baseline_panel is None:
        baseline_panel = baseline_occupancy(segments, seed=seed)
        baseline_note = "baseline_occupancy(segments, seed=seed)"

    target_vacancy = 1.0 - load_targeting_config().occ_high
    base = baseline_panel.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline_panel.columns]).merge(
        segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    base["price_usd_per_hr"] = start_price
    base_occ = base["occupancy"].to_numpy()

    rows = []
    for rep in range(n_replications):
        z = _noise(seed, rep, len(base))
        for sigma in noise_sigmas:
            noised = base.copy()
            noised["occupancy"] = np.clip(base_occ + sigma * z, 0.01, 0.99)
            for eps in elasticity_values:
                for rule in rules:
                    panel = noised.copy()
                    for year in range(1, rolls_forward_years + 1):
                        new_prices = review(rule, panel)
                        panel = apply_elasticity(panel, new_prices, eps, priced_hours_only=False)
                        rows.append({"elasticity": eps, "noise_sigma": sigma, "rule": rule,
                                     "replication": rep, "year": year,
                                     **_year_metrics(panel, segments, target_vacancy)})
    out = pd.DataFrame(rows)
    out.attrs["provenance"] = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seed": int(seed),
        "segment_source": segment_source(segments),
        "baseline": baseline_note,
        "elasticity_values": elasticity_values,
        "noise_sigmas": noise_sigmas,
        "rules": rules,
        "n_replications": n_replications,
        "rolls_forward_years": rolls_forward_years,
        "start_price_usd": start_price,
        "pairing": "noise = sigma * z, z fixed per replication; shared by all rules, elasticities and sigmas",
        "config_sha256": config_hashes(),
        "git": git_state(),
    }
    return out


def save_sweep(sweep: pd.DataFrame, path: Path) -> Path:
    """Write the sweep parquet and `<stem>.meta.json` (its provenance) beside it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sweep.to_parquet(path)
    meta = path.with_suffix(".meta.json")
    meta.write_text(json.dumps(sweep.attrs.get("provenance", {}), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_sweep(path: Path) -> pd.DataFrame:
    path = Path(path)
    sweep = pd.read_parquet(path)
    meta = path.with_suffix(".meta.json")
    if meta.exists():
        sweep.attrs["provenance"] = json.loads(meta.read_text(encoding="utf-8"))
    return sweep


# --------------------------------------------------------------------------- summaries


def cell_table(sweep: pd.DataFrame, metrics: tuple[str, ...] = SWEEP_METRICS) -> pd.DataFrame:
    """Median and range over replications for every elasticity x noise x rule x year cell."""
    g = sweep.groupby(["elasticity", "noise_sigma", "rule", "year"], sort=True)
    out = g.size().rename("n_replications").to_frame()
    for m in metrics:
        agg = g[m].agg(["median", "min", "max"])
        for stat in ("median", "min", "max"):
            out[f"{m}_{stat}"] = agg[stat]
    return out.reset_index()


def paired_table(sweep: pd.DataFrame, reference: str = PEAK_RULE) -> pd.DataFrame:
    """Each rule against `reference` on the same replication, per elasticity x noise x year.

    Ratios are comparator / reference per replication: DWL above 1 means the comparator has more
    cruising DWL, revenue below 1 means it earns less. The DWL ratio is NaN where the reference's
    DWL is zero; `dwl_diff_median` (comparator minus reference, dollars a year) is defined there.
    `share_dwl_better` / `share_revenue_better` are the shares of replications in which the
    comparator has strictly less DWL / strictly more revenue than the reference.
    """
    keys = ["elasticity", "noise_sigma", "replication", "year"]
    cols = ["cruising_dwl_total", "cruising_dwl_priced_hours", "revenue_total", "revenue_priced_hours"]
    ref = sweep.loc[sweep["rule"] == reference, keys + cols].rename(columns={c: f"{c}_ref" for c in cols})
    comp = sweep.loc[sweep["rule"] != reference, keys + ["rule"] + cols]
    j = comp.merge(ref, on=keys, how="inner", validate="many_to_one")

    d = j[keys + ["rule"]].copy()
    for tag, col in (("", "cruising_dwl_total"), ("_priced", "cruising_dwl_priced_hours")):
        r, c = j[f"{col}_ref"].to_numpy(), j[col].to_numpy()
        d[f"dwl_ratio{tag}"] = np.where(r > 0, c / np.where(r > 0, r, 1.0), np.nan)
        d[f"dwl_diff{tag}"] = c - r
        d[f"dwl_better{tag}"] = c < r
    for tag, col in (("", "revenue_total"), ("_priced", "revenue_priced_hours")):
        r, c = j[f"{col}_ref"].to_numpy(), j[col].to_numpy()
        d[f"revenue_ratio{tag}"] = c / r
        d[f"revenue_better{tag}"] = c > r

    g = d.groupby(["elasticity", "noise_sigma", "rule", "year"], sort=True)
    out = g.size().rename("n_replications").to_frame()
    for col in ("dwl_ratio", "dwl_ratio_priced", "revenue_ratio", "revenue_ratio_priced"):
        agg = g[col].agg(["median", "min", "max"])
        for stat in ("median", "min", "max"):
            out[f"{col}_{stat}"] = agg[stat]
    out["dwl_diff_median"] = g["dwl_diff"].median()
    out["dwl_diff_priced_median"] = g["dwl_diff_priced"].median()
    out["share_dwl_better"] = g["dwl_better"].mean()
    out["share_dwl_better_priced"] = g["dwl_better_priced"].mean()
    out["share_revenue_better"] = g["revenue_better"].mean()
    out["share_revenue_better_priced"] = g["revenue_better_priced"].mean()
    out.insert(0, "reference", reference)
    return out.reset_index()


def window_dependence(paired: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    """How the comparator's gap to the reference depends on its statistic, across cells.

    One row per comparator at `year` (default the last): the median, minimum and maximum over
    elasticity x noise cells of the per-cell median DWL ratio and revenue ratio, and the number
    of cells in which the comparator's median DWL is below the reference's (it wins) and in
    which its median revenue is above it. Cells are never pooled into one ratio.
    """
    year = int(paired["year"].max()) if year is None else int(year)
    p = paired[paired["year"] == year]
    rows = []
    for rule, g in p.groupby("rule", sort=False):
        row = {"rule": rule, "year": year, "n_cells": len(g)}
        for col in ("dwl_ratio_median", "dwl_ratio_priced_median", "revenue_ratio_median",
                    "revenue_ratio_priced_median"):
            row[f"{col}_cells_median"] = g[col].median()
            row[f"{col}_cells_min"] = g[col].min()
            row[f"{col}_cells_max"] = g[col].max()
        row["cells_dwl_better"] = int((g["dwl_diff_median"] < 0).sum())
        row["cells_dwl_better_priced"] = int((g["dwl_diff_priced_median"] < 0).sum())
        row["cells_revenue_better"] = int((g["revenue_ratio_median"] > 1).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def ordering_violations(sweep: pd.DataFrame, comparator: str = "avg_occupancy",
                        reference: str = PEAK_RULE) -> pd.DataFrame:
    """Replication-years in which `comparator` does NOT have at least the reference's DWL and at most its revenue.

    The sweep's old comparator (mean over 168 hours against a 95th-percentile rule with the same
    band) cannot raise a rate the peak rule holds, so at the total level its DWL is at least the
    peak rule's and its revenue at most (for |elasticity| < 1) in every replication-year. An empty
    frame is that identity holding; it is a property of mean <= q95, not a finding.
    """
    keys = ["elasticity", "noise_sigma", "replication", "year"]
    a = sweep[sweep["rule"] == comparator].set_index(keys)
    b = sweep[sweep["rule"] == reference].set_index(keys)
    j = a.join(b, lsuffix="_cmp", rsuffix="_ref", how="inner")
    bad = (j["cruising_dwl_total_cmp"] < j["cruising_dwl_total_ref"] - 1e-9) | (
        j["revenue_total_cmp"] > j["revenue_total_ref"] + 1e-9)
    return j.loc[bad, ["cruising_dwl_total_cmp", "cruising_dwl_total_ref",
                       "revenue_total_cmp", "revenue_total_ref"]].reset_index()
