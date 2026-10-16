"""The Chatman-Manville sweep: targeting rules run paired on the same demand draws, scored on welfare.

The question. Chatman and Manville (2014) argue that a rule which targets the *average*
occupancy of a block over a period leaves some block-hours full, so a rule should target
the peak (keep a vacancy at the busiest block-hours). A peak rule prices higher, so on
cruising alone it wins by construction; what it costs is the parkers it prices off the
block-hours that had space. The sweep scores both sides (`welfare/targeting_welfare.py`) and
asks where the peak statistic beats the mean, for each price instrument.

Design:

* **Segments and demand.** The fixture (`fixture` in `config/scenarios.yaml`; segments in
  zone "other" are never priced and are dropped) and its baseline weekly profile give each
  block-hour a demand share d. Latent demand responds to price with constant elasticity,
  d(p) = d0 (p / p0)^e, the law `apply_elasticity` applies year by year, written in closed
  form because it is path independent; it is not clipped, so a block more than full stays
  so until the price is high enough. Occupancy is min(d, 1).
* **Block dispersion tau.** Each block's demand is scaled by exp(tau u - tau^2 / 2) with
  u ~ N(0, 1) fixed per block and replication: at tau = 0 blocks differ only as the baseline
  makes them; at tau = 0.6 one block in six is more than 1.8x the zone's typical demand.
* **Start occupancy m.** Each zone's demand is then scaled so that at the start price its
  mean occupancy over priced block-hours is exactly m (the baseline's level is a stated
  anchor, not a measurement, and the question depends on it: below the band both rules
  cut, inside it the mean rule holds while the peak rule raises, which is the case
  Chatman and Manville describe). The weekly shape and the block dispersion are kept.
* **Observation noise sigma.** The rule reviews occupancy + sigma z with z ~ N(0, 1) per
  block-hour, redrawn every year (a fresh week's observation); welfare is scored on the true
  occupancy. Noise biases a peak statistic upward and leaves a mean almost unchanged.
* **Cruising cost level.** The welfare scorer's search time at the reference block-hour
  (`search_cost.minutes_at_reference` in `config/pricing_rules.yaml`; see
  `welfare/targeting_welfare.py`) sets `search_cost` and `welfare_change`. The rules never
  see it and the cost is linear in it, so every row also carries `search_cost_per_minute`
  and `paired_table` reports each comparison's breakeven: the minutes at the reference
  block-hour above which the higher-priced rule gives more welfare.
* **Pairing.** u and z are shared by every rule, elasticity, tau and sigma within a
  replication, so rule differences on one draw are paired.
* **Prices.** Every rule starts each zone at `start_price_usd`, reviews once a year for
  `rolls_forward_years`, and prices only the zone's priced hours (`config/zones.yaml`): a
  rate change does not reach an hour when the meter is off.

Metrics per rule-year, over priced block-hours, in dollars a year (52 weeks): `revenue`,
`search_cost` and `search_cost_per_minute`, `cs_change` (since the start), `welfare_change`
(since the start), `cruising_dwl` (the project's proxy, for continuity), plus
`share_block_hours_above_high`, `share_block_hours_below_low` and `mean_price`. Read the paired tables cell by cell
(`paired_table`, `window_dependence`); nothing is pooled across cells.
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
from phillyparking.welfare.targeting_welfare import (
    cs_change_usd, load_search_cost_config, search_cost_usd,
)

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 52
SWEEP_METRICS = (
    "welfare_change", "cs_change", "revenue", "search_cost", "search_cost_per_minute",
    "cruising_dwl", "share_block_hours_above_high", "share_block_hours_below_low", "mean_price",
)
AXES = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
KEYS = AXES + ["rule", "replication", "year"]
DEFAULT_COMPARISONS = (("mean_zone", "peak_zone"), ("mean_band", "peak_band"),
                       ("seattle_rule", "peak_band"), ("peak_band", "peak_zone"))


def _block_draw(seed: int, rep: int, n_segments: int) -> np.ndarray:
    """u: one standard normal per block, fixed for replication `rep`."""
    return np.random.default_rng(np.random.SeedSequence([int(seed), int(rep), 0])).standard_normal(n_segments)


def _observation_draw(seed: int, rep: int, year: int, n_rows: int) -> np.ndarray:
    """z: one standard normal per block-hour for the review in `year` of replication `rep`."""
    return np.random.default_rng(np.random.SeedSequence([int(seed), int(rep), 1, int(year)])).standard_normal(n_rows)


def _scale_to_start_occupancy(d: np.ndarray, zone_index: np.ndarray, priced: np.ndarray,
                              level: float, tol: float = 1e-6) -> np.ndarray:
    """Scale each zone's latent demand so its mean occupancy min(d, 1) over priced rows is `level`."""
    out = d.copy()
    for z in np.unique(zone_index):
        m = (zone_index == z) & priced
        if not m.any():
            continue
        lo, hi = 0.0, 1.0
        while np.minimum(hi * d[m], 1.0).mean() < level:  # mean occupancy is increasing in the scale
            hi *= 2.0
            if hi > 1e6:
                raise ValueError(f"zone {z}: cannot reach start occupancy {level}")
        while hi - lo > tol:
            mid = 0.5 * (lo + hi)
            if np.minimum(mid * d[m], 1.0).mean() < level:
                lo = mid
            else:
                hi = mid
        out[zone_index == z] = hi * d[zone_index == z]
    return out


def _apply_prices(prices: pd.DataFrame, panel: pd.DataFrame, current: np.ndarray) -> np.ndarray:
    """Expand a review's price table to one price per panel row; uncovered rows keep theirs."""
    keys = [c for c in ("zone_id", "hour_of_week") if c in prices.columns]
    if prices.empty:
        return current.copy()
    merged = panel[keys].merge(prices[keys + ["price_usd_per_hr"]], on=keys, how="left")
    new = merged["price_usd_per_hr"].to_numpy(dtype=float)
    return np.where(np.isnan(new), current, new)


def chatman_manville_sweep(
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    elasticity_values: list[float] | None = None,
    start_occupancy: list[float] | None = None,
    block_dispersion: list[float] | None = None,
    observation_noise: list[float] | None = None,
    rules: list[str] | None = None,
    n_replications: int | None = None,
    rolls_forward_years: int | None = None,
    seed: int = 42,
    start_price: float | None = None,
) -> pd.DataFrame:
    """Rows of elasticity x start_occupancy x block_dispersion x observation_noise x rule x replication x year.

    Arguments left as None come from `chatman_manville_sweep` in `config/scenarios.yaml`.
    `result.attrs["provenance"]` records the segment source, grid, seed, config hashes and
    git state; `save_sweep` writes it beside the parquet.
    """
    from phillyparking.demand.synthetic_baseline import baseline_occupancy
    from phillyparking.spatial.synthetic import make_synthetic_segments

    cfg = load_config("scenarios")["chatman_manville_sweep"]
    elasticity_values = list(cfg["elasticity_values"] if elasticity_values is None else elasticity_values)
    start_occupancy = list(cfg["start_occupancy"] if start_occupancy is None else start_occupancy)
    block_dispersion = list(cfg["block_dispersion"] if block_dispersion is None else block_dispersion)
    observation_noise = list(cfg["observation_noise"] if observation_noise is None else observation_noise)
    rules = list(cfg["rules"] if rules is None else rules)
    n_replications = int(cfg["n_replications"] if n_replications is None else n_replications)
    rolls_forward_years = int(cfg["rolls_forward_years"] if rolls_forward_years is None else rolls_forward_years)
    start_price = float(cfg["start_price_usd"] if start_price is None else start_price)
    if PEAK_RULE not in rules:
        logger.warning("%s is not among the rules; the default comparisons have no reference", PEAK_RULE)

    if segments is None:
        fx = cfg["fixture"]
        segments = make_synthetic_segments(n=int(fx["n"]), seed=int(fx["seed"]))
    src = segment_source(segments)
    priced_zones = {z["id"] for z in load_config("zones")["zones"]}
    unpriced = ~segments["zone_id"].isin(priced_zones)
    if unpriced.any():
        logger.info("dropping %d segments in zones that are never priced", int(unpriced.sum()))
        segments = segments.loc[~unpriced].reset_index(drop=True)
    baseline_note = "supplied panel"
    if baseline_panel is None:
        baseline_panel = baseline_occupancy(segments, seed=seed, anchor_set="synthetic_fixture")
        baseline_note = "baseline_occupancy(segments, seed=seed, anchor_set='synthetic_fixture')"

    tcfg = load_targeting_config()
    scfg = load_search_cost_config()
    base = baseline_panel.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline_panel.columns]).merge(
        segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    base = base.sort_values(["segment_id", "hour_of_week"]).reset_index(drop=True)
    base["price_usd_per_hr"] = start_price
    priced = frame_priced_mask(base)
    seg_index = pd.factorize(base["segment_id"])[0]
    zone_index = pd.factorize(base["zone_id"])[0]
    n_seg = int(seg_index.max()) + 1
    base_d = np.clip(base["occupancy"].to_numpy(dtype=float), 0.01, None)
    cap = base["capacity"].to_numpy(dtype=float)
    p0 = np.full(len(base), start_price)
    n_priced = int(priced.sum())

    def search_cost(occ: np.ndarray) -> float:
        return float(search_cost_usd(occ, cap, scfg)[priced].sum() * WEEKS_PER_YEAR)

    def metrics(d: np.ndarray, price: np.ndarray, eps: float, rev0: float, cost0: float) -> dict:
        occ = np.minimum(d, 1.0)
        rev = float((occ * cap * price)[priced].sum() * WEEKS_PER_YEAR)
        cost = search_cost(occ)
        cs = float(cs_change_usd(d0, p0, price, eps, cap)[priced].sum() * WEEKS_PER_YEAR)
        excess = np.maximum(occ * cap - (1.0 - target_vacancy) * cap, 0.0)
        dwl = float((excess * (5.0 / 60.0) * scfg.value_of_time_usd_per_hr)[priced].sum() * WEEKS_PER_YEAR)
        return {
            "welfare_change": cs + (rev - rev0) - (cost - cost0),
            "cs_change": cs, "revenue": rev, "search_cost": cost,
            "search_cost_per_minute": cost / scfg.minutes_at_reference, "cruising_dwl": dwl,
            "share_block_hours_above_high": float((occ[priced] > tcfg.occ_high).mean()),
            "share_block_hours_below_low": float((occ[priced] < tcfg.occ_low).mean()),
            "mean_price": float(price[priced].mean()),
        }

    target_vacancy = 1.0 - tcfg.occ_high
    rows = []
    for rep in range(n_replications):
        u = _block_draw(seed, rep, n_seg)[seg_index]
        z = {year: _observation_draw(seed, rep, year, len(base)) for year in range(1, rolls_forward_years + 1)}
        for level, tau in ((lv, t) for lv in start_occupancy for t in block_dispersion):
            d0 = _scale_to_start_occupancy(base_d * np.exp(tau * u - 0.5 * tau * tau),
                                           zone_index, priced, float(level))
            occ0 = np.minimum(d0, 1.0)
            rev0 = float((occ0 * cap * p0)[priced].sum() * WEEKS_PER_YEAR)
            cost0 = search_cost(occ0)
            for sigma in observation_noise:
                for eps in elasticity_values:
                    for rule in rules:
                        panel = base.copy()
                        price = p0.copy()
                        d = d0.copy()
                        for year in range(1, rolls_forward_years + 1):
                            panel["occupancy"] = np.clip(np.minimum(d, 1.0) + sigma * z[year], 0.0, 1.0)
                            panel["price_usd_per_hr"] = price
                            new = _apply_prices(review(rule, panel, tcfg), panel, price)
                            price = np.where(priced, new, price)
                            d = np.where(priced, d0 * np.power(price / p0, eps), d0)
                            rows.append({"elasticity": eps, "start_occupancy": level,
                                         "block_dispersion": tau, "observation_noise": sigma,
                                         "rule": rule, "replication": rep, "year": year,
                                         **metrics(d, price, eps, rev0, cost0)})
    out = pd.DataFrame(rows)
    out.attrs["provenance"] = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "seed": int(seed),
        "segment_source": {**src, "n_priced_segments": n_seg, "n_priced_block_hours_per_week": n_priced},
        "baseline": baseline_note,
        "elasticity_values": elasticity_values,
        "start_occupancy": start_occupancy,
        "block_dispersion": block_dispersion,
        "observation_noise": observation_noise,
        "rules": rules,
        "n_replications": n_replications,
        "rolls_forward_years": rolls_forward_years,
        "start_price_usd": start_price,
        "pairing": "block draw u and yearly observation draws z fixed per replication; shared by all rules, elasticities, dispersions and noise levels",
        "search_cost": scfg.__dict__,
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
    """Median and range over replications for every elasticity x level x dispersion x noise x rule x year cell."""
    g = sweep.groupby(AXES + ["rule", "year"], sort=True)
    out = g.size().rename("n_replications").to_frame()
    for m in metrics:
        agg = g[m].agg(["median", "min", "max"])
        for stat in ("median", "min", "max"):
            out[f"{m}_{stat}"] = agg[stat]
    return out.reset_index()


def comparisons_from_config() -> tuple[tuple[str, str], ...]:
    cfg = load_config("scenarios")["chatman_manville_sweep"]
    return tuple((str(a), str(b)) for a, b in cfg.get("comparisons", DEFAULT_COMPARISONS))


def paired_table(sweep: pd.DataFrame, comparisons=None) -> pd.DataFrame:
    """Each (comparator, reference) pair on the same replication, per elasticity x level x dispersion x noise x year.

    `comparisons` is a sequence of (comparator, reference) rule names (default: the config's).
    `welfare_diff` is comparator minus reference in dollars a year at the config's cruising
    cost level (positive: the comparator gives more surplus); `cs_diff`, `revenue_diff` and
    `search_cost_diff` are its parts, and `dwl_ratio` / `revenue_ratio` are comparator over
    reference (the DWL ratio is NaN where the reference's proxy DWL is zero).
    `share_welfare_better` is the share of replications in which the comparator's welfare
    change is strictly higher; `share_dwl_better` and `share_revenue_better` likewise for
    less DWL and more revenue.

    `breakeven_minutes` is the cruising cost level at which the two rules give the same
    welfare: welfare_diff(c) = cs_diff + revenue_diff - c x search_cost_diff_per_minute, so
    c* = (cs_diff + revenue_diff) / search_cost_diff_per_minute. When the comparator has
    the higher search cost (it prices lower; `comparator_searches_more` is True) it gives
    more welfare below c* and less above; the reverse when it searches less. NaN where the
    two rules' search costs are equal.
    """
    comparisons = comparisons_from_config() if comparisons is None else comparisons
    keys = AXES + ["replication", "year"]
    cols = ["welfare_change", "cs_change", "revenue", "search_cost", "search_cost_per_minute", "cruising_dwl"]
    frames = []
    for comparator, reference in comparisons:
        ref = sweep.loc[sweep["rule"] == reference, keys + cols].rename(columns={c: f"{c}_ref" for c in cols})
        comp = sweep.loc[sweep["rule"] == comparator, keys + cols]
        if ref.empty or comp.empty:
            continue
        j = comp.merge(ref, on=keys, how="inner", validate="one_to_one")
        d = j[keys].copy()
        d["rule"], d["reference"] = comparator, reference
        for c in ("welfare_change", "cs_change", "revenue", "search_cost", "search_cost_per_minute"):
            d[f"{c.replace('_change', '')}_diff"] = j[c] - j[f"{c}_ref"]
        scd = d["search_cost_per_minute_diff"].to_numpy()
        gain = (d["cs_diff"] + d["revenue_diff"]).to_numpy()
        d["breakeven_minutes"] = np.where(np.abs(scd) > 1e-9, gain / np.where(np.abs(scd) > 1e-9, scd, 1.0), np.nan)
        d["comparator_searches_more"] = scd > 1e-9
        r, c = j["cruising_dwl_ref"].to_numpy(), j["cruising_dwl"].to_numpy()
        d["dwl_ratio"] = np.where(r > 0, c / np.where(r > 0, r, 1.0), np.nan)
        d["revenue_ratio"] = j["revenue"] / j["revenue_ref"]
        d["welfare_better"] = j["welfare_change"] > j["welfare_change_ref"]
        d["dwl_better"] = c < r
        d["revenue_better"] = j["revenue"] > j["revenue_ref"]
        frames.append(d)
    if not frames:
        raise ValueError(f"no comparison in {list(comparisons)} has both rules in the sweep")
    d = pd.concat(frames, ignore_index=True)
    g = d.groupby(AXES + ["rule", "reference", "year"], sort=True)
    out = g.size().rename("n_replications").to_frame()
    for col in ("welfare_diff", "cs_diff", "revenue_diff", "search_cost_diff", "breakeven_minutes",
                "dwl_ratio", "revenue_ratio"):
        agg = g[col].agg(["median", "min", "max"])
        for stat in ("median", "min", "max"):
            out[f"{col}_{stat}"] = agg[stat]
    for col in ("welfare_better", "dwl_better", "revenue_better", "comparator_searches_more"):
        out[f"share_{col}"] = g[col].mean()
    return out.reset_index()


def window_dependence(paired: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    """How each comparison's gap depends on the cell, across cells, at `year` (default the last).

    One row per (comparator, reference): the median, minimum and maximum over
    elasticity x level x dispersion x noise cells of the per-cell median welfare difference,
    breakeven minutes, DWL ratio and revenue ratio, and the number of cells in which the
    comparator's median welfare change is above the reference's (`cells_welfare_better`), its
    median DWL below and its median revenue above. Cells are never pooled into one number.
    """
    year = int(paired["year"].max()) if year is None else int(year)
    p = paired[paired["year"] == year]
    rows = []
    for (rule, ref), g in p.groupby(["rule", "reference"], sort=False):
        row = {"rule": rule, "reference": ref, "year": year, "n_cells": len(g)}
        for col in ("welfare_diff_median", "breakeven_minutes_median", "dwl_ratio_median",
                    "revenue_ratio_median"):
            row[f"{col}_cells_median"] = g[col].median()
            row[f"{col}_cells_min"] = g[col].min()
            row[f"{col}_cells_max"] = g[col].max()
        row["cells_welfare_better"] = int((g["welfare_diff_median"] > 0).sum())
        row["cells_dwl_better"] = int((g["dwl_ratio_median"] < 1).sum())
        row["cells_revenue_better"] = int((g["revenue_ratio_median"] > 1).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def ordering_violations(sweep: pd.DataFrame, comparator: str = "avg_occupancy",
                        reference: str = "min_vacancy_peak") -> pd.DataFrame:
    """Replication-years in which `comparator` does NOT have at least the reference's DWL and at most its revenue.

    A mean over the same window as a 95th percentile is never above it, so with the same band
    and step the mean rule never raises what the peak rule holds: its proxy DWL is at least
    the peak rule's and, for |elasticity| < 1, its revenue at most, in every replication-year.
    An empty frame is that identity holding; it is a property of mean <= q95, not a finding.
    The same holds for `mean_zone` against `peak_zone` and `mean_band` against `peak_band`.
    """
    keys = AXES + ["replication", "year"]
    a = sweep[sweep["rule"] == comparator].set_index(keys)
    b = sweep[sweep["rule"] == reference].set_index(keys)
    j = a.join(b, lsuffix="_cmp", rsuffix="_ref", how="inner")
    bad = (j["cruising_dwl_cmp"] < j["cruising_dwl_ref"] - 1e-9) | (
        j["revenue_cmp"] > j["revenue_ref"] + 1e-9)
    return j.loc[bad, ["cruising_dwl_cmp", "cruising_dwl_ref", "revenue_cmp", "revenue_ref"]].reset_index()
