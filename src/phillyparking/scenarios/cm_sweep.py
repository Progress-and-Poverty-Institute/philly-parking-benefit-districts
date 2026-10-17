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
  block-hour a demand share d. Latent demand responds to price under the configured demand
  law (`demand.response`, anchored at the start price, where the elasticity applies), the
  same law `apply_elasticity` applies year by year, written in closed form because it is
  path independent; it is not clipped, so a block more than full stays so until the price
  is high enough. Occupancy is min(d, 1).
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
* **Search cost cap and level.** The welfare scorer (`welfare/targeting_welfare.py`) charges
  the project's search cost (`welfare/search_cost.py`): its level
  `cruising_minutes_at_full_block` is the mean search of the drivers who cruise when every
  block is full (the units of the cruising times the config cites), and `occupancy_cap`
  decides how much more a full block costs than a nearly full one. The rules never see
  either. The cap is an axis (`occupancy_cap`): each rule's price path is run once and
  scored once per cap. The level is not: the cost is linear in it, so every row carries
  `search_cost_per_cruising_minute` and `paired_table` reports each comparison's
  breakeven, the cruising minutes above which the higher-priced rule gives more welfare,
  with the same level in minutes per arrival at the 95% reference block-hour as a
  secondary column.
* **One population.** Surplus, revenue and search cost all count the cars that park: a
  block whose latent demand exceeds its capacity is rationed to the parkers who value it
  most (`demand.response.cs_change_served`), and the cars it turns away carry neither
  surplus nor search cost.
* **Pairing.** u and z are shared by every rule, elasticity, tau and sigma within a
  replication, so rule differences on one draw are paired.
* **Prices.** Every rule starts each zone at `start_price_usd`, reviews once a year for
  `rolls_forward_years`, and prices only the zone's priced hours (`config/zones.yaml`): a
  rate change does not reach an hour when the meter is off.

Metrics per rule-year and cap, over priced block-hours, in dollars a year (52 weeks):
`revenue`, `search_cost` and `search_cost_per_cruising_minute`, `cs_change` (since the
start), `welfare_change` (since the start), plus `share_block_hours_above_high`,
`share_block_hours_below_low` and `mean_price`. Read the paired tables cell by cell
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
from phillyparking.demand.response import FORMS, demand_level, load_demand_form, revenue_maximising_price
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import (
    PEAK_RULE, load_targeting_config, review,
)
from phillyparking.scenarios.provenance import config_hashes, git_state, segment_source
from phillyparking.welfare.targeting_welfare import (
    cs_change_usd, load_search_cost_config, reference_minutes_per_cruising_minute, search_cost_usd,
)

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 52
SWEEP_METRICS = (
    "welfare_change", "cs_change", "revenue", "search_cost", "search_cost_per_cruising_minute",
    "share_block_hours_above_high", "share_block_hours_below_low", "mean_price",
)
AXES = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise", "occupancy_cap"]
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
    occupancy_cap: list[float] | None = None,
    rules: list[str] | None = None,
    n_replications: int | None = None,
    rolls_forward_years: int | None = None,
    seed: int = 42,
    start_price: float | None = None,
    demand_form: str | None = None,
) -> pd.DataFrame:
    """Rows of elasticity x start_occupancy x block_dispersion x observation_noise x occupancy_cap x rule x replication x year.

    Arguments left as None come from `chatman_manville_sweep` in `config/scenarios.yaml`
    (`demand_form`: from `config/elasticity_priors.yaml`; the form sensitivity passes the
    other two, see `form_sensitivity_table`).
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
    occupancy_cap = [float(c) for c in (cfg["occupancy_cap"] if occupancy_cap is None else occupancy_cap)]
    rules = list(cfg["rules"] if rules is None else rules)
    n_replications = int(cfg["n_replications"] if n_replications is None else n_replications)
    rolls_forward_years = int(cfg["rolls_forward_years"] if rolls_forward_years is None else rolls_forward_years)
    start_price = float(cfg["start_price_usd"] if start_price is None else start_price)
    form = load_demand_form() if demand_form is None else str(demand_form)
    if form not in FORMS:
        raise ValueError(f"demand_form must be one of {FORMS}, not {form!r}")
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

    # Captured before the run: the provenance names the tree the sweep started from.
    git, hashes = git_state(), config_hashes()
    tcfg = load_targeting_config()
    scfg = load_search_cost_config()
    scfgs = {cap: load_search_cost_config(occupancy_cap=cap) for cap in occupancy_cap}
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

    def search_cost(occ: np.ndarray, sc) -> float:
        return float(search_cost_usd(occ, cap, sc)[priced].sum() * WEEKS_PER_YEAR)

    def metrics(d: np.ndarray, price: np.ndarray, eps: float, rev0: float, cost0: dict) -> list[dict]:
        """One dict per occupancy cap: the price path is the rule's, the search cost the cap's."""
        occ = np.minimum(d, 1.0)
        rev = float((occ * cap * price)[priced].sum() * WEEKS_PER_YEAR)
        cs = float(cs_change_usd(d0, p0, price, eps, cap, form)[priced].sum() * WEEKS_PER_YEAR)
        shared = {
            "cs_change": cs, "revenue": rev,
            "share_block_hours_above_high": float((occ[priced] > tcfg.occ_high).mean()),
            "share_block_hours_below_low": float((occ[priced] < tcfg.occ_low).mean()),
            "mean_price": float(price[priced].mean()),
        }
        out = []
        for c, sc in scfgs.items():
            cost = search_cost(occ, sc)
            out.append({"occupancy_cap": c, "welfare_change": cs + (rev - rev0) - (cost - cost0[c]),
                        "search_cost": cost,
                        "search_cost_per_cruising_minute": cost / sc.cruising_minutes_at_full_block, **shared})
        return out

    rows = []
    for rep in range(n_replications):
        u = _block_draw(seed, rep, n_seg)[seg_index]
        z = {year: _observation_draw(seed, rep, year, len(base)) for year in range(1, rolls_forward_years + 1)}
        for level, tau in ((lv, t) for lv in start_occupancy for t in block_dispersion):
            d0 = _scale_to_start_occupancy(base_d * np.exp(tau * u - 0.5 * tau * tau),
                                           zone_index, priced, float(level))
            occ0 = np.minimum(d0, 1.0)
            rev0 = float((occ0 * cap * p0)[priced].sum() * WEEKS_PER_YEAR)
            cost0 = {c: search_cost(occ0, sc) for c, sc in scfgs.items()}
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
                            d = np.where(priced, d0 * demand_level(price, eps, p0, form), d0)
                            for m in metrics(d, price, eps, rev0, cost0):
                                rows.append({"elasticity": eps, "start_occupancy": level,
                                             "block_dispersion": tau, "observation_noise": sigma,
                                             "rule": rule, "replication": rep, "year": year, **m})
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
        "occupancy_cap": occupancy_cap,
        "rules": rules,
        "n_replications": n_replications,
        "rolls_forward_years": rolls_forward_years,
        "start_price_usd": start_price,
        "demand_form": form,
        "pairing": "block draw u and yearly observation draws z fixed per replication; shared by all rules, elasticities, dispersions and noise levels",
        "search_cost": {**scfg.__dict__, "level_units": "cruising minutes per cruiser when every block "
                        "(search_unit_spaces spaces) is full; occupancy_cap is swept (see occupancy_cap)"},
        "welfare_population": "served cars: surplus on min(demand, capacity), revenue and search cost on served arrivals",
        "config_sha256": hashes,
        "git": git,
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
    """Median and range over replications for every elasticity x level x dispersion x noise x cap x rule x year cell."""
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
    """Each (comparator, reference) pair on the same replication, per elasticity x level x dispersion x noise x cap x year.

    `comparisons` is a sequence of (comparator, reference) rule names (default: the config's).
    `welfare_diff` is comparator minus reference in dollars a year at the config's search-cost
    level (positive: the comparator gives more surplus); `cs_diff`, `revenue_diff` and
    `search_cost_diff` are its parts, and `search_cost_ratio` / `revenue_ratio` are
    comparator over reference (NaN where the reference's is zero). `share_welfare_better`
    is the share of replications in which the comparator's welfare change is strictly
    higher; `share_search_cost_better` and `share_revenue_better` likewise for less search
    cost and more revenue.

    `breakeven_cruising_minutes` is the search-cost level at which the two rules give the
    same welfare, in the level's units: the mean cruising time of the drivers who cruise
    when every block is full, the units of the cited cruising times (`welfare/search_cost.py`):
    welfare_diff(c) = cs_diff + revenue_diff - c x search_cost_diff_per_cruising_minute, so
    c* = (cs_diff + revenue_diff) / search_cost_diff_per_cruising_minute. When the
    comparator has the higher search cost (it prices lower; `comparator_searches_more` is
    True) it gives more welfare below c* and less above; the reverse when it searches less.
    NaN where the two rules' search costs are equal. `breakeven_reference_minutes` is the same
    level quoted as minutes per arrival at the 95% reference block-hour: c* x the row's cap's
    `reference_minutes_per_cruising_minute` (0.60 at cap 0.95, 0.14 at 0.99, 0.015 at
    0.999), so it is not comparable across caps; the cruising-minute column is.

    For a same-instrument pair (the mean against the peak statistic over the same
    block-hours: `mean_zone` vs `peak_zone`, `mean_band` vs `peak_band`) the SIGN of c* is a
    property of the design, not a finding: a mean is never above a 95th percentile of the
    same block-hours, so the mean rule prices at or below the peak rule, total surplus (surplus
    + revenue) falls in price at zero marginal cost and search cost rises in occupancy, so
    cs_diff + revenue_diff >= 0 and search_cost_diff >= 0 in every replication
    (`ordering_violations` checks that identity). The sweep's content for such pairs is the
    SIZE of c* against the cited cruising times (`welfare/search_cost.py`). The sign is not an
    identity for pairs across instruments or for `seattle_rule`.
    """
    comparisons = comparisons_from_config() if comparisons is None else comparisons
    keys = AXES + ["replication", "year"]
    cols = ["welfare_change", "cs_change", "revenue", "search_cost", "search_cost_per_cruising_minute"]
    frames = []
    for comparator, reference in comparisons:
        ref = sweep.loc[sweep["rule"] == reference, keys + cols].rename(columns={c: f"{c}_ref" for c in cols})
        comp = sweep.loc[sweep["rule"] == comparator, keys + cols]
        if ref.empty or comp.empty:
            continue
        j = comp.merge(ref, on=keys, how="inner", validate="one_to_one")
        d = j[keys].copy()
        d["rule"], d["reference"] = comparator, reference
        for c in cols:
            d[f"{c.replace('_change', '')}_diff"] = j[c] - j[f"{c}_ref"]
        scd = d["search_cost_per_cruising_minute_diff"].to_numpy()
        gain = (d["cs_diff"] + d["revenue_diff"]).to_numpy()
        nonzero = np.abs(scd) > 1e-9
        d["breakeven_cruising_minutes"] = np.where(nonzero, gain / np.where(nonzero, scd, 1.0), np.nan)
        to_ref = {c: reference_minutes_per_cruising_minute(load_search_cost_config(occupancy_cap=c))
                  for c in d["occupancy_cap"].unique()}
        d["breakeven_reference_minutes"] = d["breakeven_cruising_minutes"] * d["occupancy_cap"].map(to_ref)
        d["comparator_searches_more"] = scd > 1e-9
        r, c = j["search_cost_ref"].to_numpy(), j["search_cost"].to_numpy()
        d["search_cost_ratio"] = np.where(r > 0, c / np.where(r > 0, r, 1.0), np.nan)
        d["revenue_ratio"] = j["revenue"] / j["revenue_ref"]
        d["welfare_better"] = j["welfare_change"] > j["welfare_change_ref"]
        d["search_cost_better"] = c < r
        d["revenue_better"] = j["revenue"] > j["revenue_ref"]
        frames.append(d)
    if not frames:
        raise ValueError(f"no comparison in {list(comparisons)} has both rules in the sweep")
    d = pd.concat(frames, ignore_index=True)
    g = d.groupby(AXES + ["rule", "reference", "year"], sort=True)
    out = g.size().rename("n_replications").to_frame()
    for col in ("welfare_diff", "cs_diff", "revenue_diff", "search_cost_diff",
                "breakeven_cruising_minutes", "breakeven_reference_minutes",
                "search_cost_ratio", "revenue_ratio"):
        agg = g[col].agg(["median", "min", "max"])
        for stat in ("median", "min", "max"):
            out[f"{col}_{stat}"] = agg[stat]
    for col in ("welfare_better", "search_cost_better", "revenue_better", "comparator_searches_more"):
        out[f"share_{col}"] = g[col].mean()
    return out.reset_index()


def window_dependence(paired: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    """How each comparison's gap depends on the cell, across cells, at `year` (default the last).

    One row per (comparator, reference, occupancy_cap): the median, minimum and maximum over
    elasticity x level x dispersion x noise cells of the per-cell median welfare difference,
    breakeven minutes (cruising minutes, and per arrival at the 95% reference), search-cost
    ratio and revenue ratio, and the number of cells in which the comparator's median welfare
    change is above the reference's (`cells_welfare_better`), its median search cost below
    and its median revenue above. The cap gets its own rows so that the stability of the
    cruising-minute breakeven across caps, and the instability of the reference-minute one, is
    visible. Cells are never pooled into one number.
    """
    year = int(paired["year"].max()) if year is None else int(year)
    p = paired[paired["year"] == year]
    rows = []
    for (rule, ref, cap), g in p.groupby(["rule", "reference", "occupancy_cap"], sort=False):
        row = {"rule": rule, "reference": ref, "occupancy_cap": cap, "year": year, "n_cells": len(g)}
        for col in ("welfare_diff_median", "breakeven_cruising_minutes_median",
                    "breakeven_reference_minutes_median", "search_cost_ratio_median",
                    "revenue_ratio_median"):
            row[f"{col}_cells_median"] = g[col].median()
            row[f"{col}_cells_min"] = g[col].min()
            row[f"{col}_cells_max"] = g[col].max()
        row["cells_welfare_better"] = int((g["welfare_diff_median"] > 0).sum())
        row["cells_search_cost_better"] = int((g["search_cost_ratio_median"] < 1).sum())
        row["cells_revenue_better"] = int((g["revenue_ratio_median"] > 1).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def ordering_violations(sweep: pd.DataFrame, comparator: str = "avg_occupancy",
                        reference: str = "min_vacancy_peak") -> pd.DataFrame:
    """Replication-years in which `comparator` has less search cost or less total surplus than `reference`.

    Two comparisons per replication-year and nothing else: the comparator's search cost is
    not below the reference's, and its total surplus (consumer surplus + revenue,
    `cs_change + revenue`) is not below the reference's. It does not compare revenue alone, and
    it does not compare the price paths.

    Why both are expected to hold for a mean rule against a peak rule over the same
    block-hours: a mean is never above a 95th percentile of them, so with the same band and
    step the mean rule prices at or below the peak rule (the premise; the function does not
    test it, because the two rules' paths differ after the first review). Search cost
    rises in occupancy, so the lower price searches at least as much. Total surplus falls in
    price under every demand law in `demand.response`, because the revenue term cancels the
    surplus term's loss on the cars served: d(CS + p q)/dp = p q'(p) <= 0, and 0 on a
    rationed block. That holds above the revenue-maximising price too (p_ref / |e| under the
    exponential law), where revenue itself falls in price. Revenue alone is not checked: below
    the peak the mean rule earns less, above it more, so it has no sign in this comparison.

    An empty frame is therefore the ordering holding on the sweep's draws. It is a property
    of mean <= q95 and a monotone demand law, not a finding, and it is what makes the sign of
    the paired tables' breakeven a property of the design for same-instrument pairs
    (`paired_table`): `mean_zone` against `peak_zone`, `mean_band` against `peak_band`.
    """
    keys = AXES + ["replication", "year"]
    a = sweep[sweep["rule"] == comparator].set_index(keys)
    b = sweep[sweep["rule"] == reference].set_index(keys)
    j = a.join(b, lsuffix="_cmp", rsuffix="_ref", how="inner")
    surplus_cmp = j["cs_change_cmp"] + j["revenue_cmp"]
    surplus_ref = j["cs_change_ref"] + j["revenue_ref"]
    bad = (j["search_cost_cmp"] < j["search_cost_ref"] - 1e-6) | (surplus_cmp < surplus_ref - 1e-6)
    out = j.loc[bad, ["search_cost_cmp", "search_cost_ref", "cs_change_cmp", "cs_change_ref",
                      "revenue_cmp", "revenue_ref"]].copy()
    out["total_surplus_cmp"] = surplus_cmp[bad]
    out["total_surplus_ref"] = surplus_ref[bad]
    return out.reset_index()


# --------------------------------------------------------------------------- form sensitivity

FORM_SENSITIVITY_REPLICATIONS = 20
FORM_SENSITIVITY_FILES = ("cm_sweep_form_sensitivity.csv", "cm_sweep_form_beyond_peak.csv",
                          "cm_sweep_form_sensitivity.meta.json")


def form_sensitivity_sweeps(forms=FORMS, n_replications: int = FORM_SENSITIVITY_REPLICATIONS,
                            seed: int = 42, max_workers: int | None = None) -> dict[str, pd.DataFrame]:
    """The sweep at the config's grid under each demand form, `n_replications` replications.

    Everything but the form and the replication count is the headline sweep's, and the draws
    are the same (replication r of a short run is replication r of a long one), so the rows of
    different forms are paired. Forms run in separate processes.
    """
    from concurrent.futures import ProcessPoolExecutor

    forms = list(forms)
    with ProcessPoolExecutor(max_workers=max_workers or len(forms)) as pool:
        futures = {f: pool.submit(chatman_manville_sweep, n_replications=n_replications, seed=seed,
                                  demand_form=f) for f in forms}
        return {f: fut.result() for f, fut in futures.items()}


def form_sensitivity_table(sweeps: dict[str, pd.DataFrame], comparisons=None,
                           year: int | None = None) -> pd.DataFrame:
    """Each comparison's breakeven and welfare-better count under each demand form.

    One row per (form, comparator, reference, occupancy_cap) in the sweep's last year (or
    `year`): `window_dependence` of that form's paired table, so the median and range over cells
    of the per-cell median breakeven (cruising minutes, and minutes per arrival at the 95%
    reference), `n_cells` and `cells_welfare_better` (cells in which the comparator's median
    welfare change is above the reference's), with `form` and `n_replications` in front. Read a
    row against the same comparison, cap and year under the other forms.
    """
    frames = []
    for form, sweep in sweeps.items():
        w = window_dependence(paired_table(sweep, comparisons), year)
        w.insert(0, "n_replications", int(sweep["replication"].nunique()))
        w.insert(0, "form", form)
        frames.append(w)
    return pd.concat(frames, ignore_index=True)


def beyond_peak_table(sweeps: dict[str, pd.DataFrame], start_price: float | None = None) -> pd.DataFrame:
    """Where the rules' prices sit relative to the revenue-maximising price of each form.

    One row per (form, elasticity, rule): the revenue-maximising price of that form at that
    elasticity anchored at the start price (`demand.response.revenue_maximising_price`; NaN
    where the form has none, constant elasticity at |e| < 1), the number of rule-years (every
    cell, replication and year) and the share whose mean priced-hour price is above it, over
    all years and in the last year alone (`share_beyond_peak_last_year`, where the rules have
    settled). The price paths differ across forms, so each form's sweep is read against its
    own peak.
    """
    start_price = float(load_config("scenarios")["chatman_manville_sweep"]["start_price_usd"]
                        if start_price is None else start_price)
    rows = []
    for form, sweep in sweeps.items():
        one_cap = sweep[sweep["occupancy_cap"] == sweep["occupancy_cap"].iloc[0]]   # mean_price is cap-free
        for (eps, rule), g in one_cap.groupby(["elasticity", "rule"], sort=True):
            peak = revenue_maximising_price(float(eps), start_price, form)
            peak = np.nan if peak is None else float(peak)
            rows.append({"form": form, "elasticity": eps, "rule": rule, "start_price_usd": start_price,
                         "revenue_peak_price_usd": peak, "n_rule_years": int(len(g)),
                         "share_beyond_peak": float((g["mean_price"] > peak).mean()) if peak == peak else np.nan,
                         "share_beyond_peak_last_year": float((g.loc[g["year"] == g["year"].max(), "mean_price"]
                                                               > peak).mean()) if peak == peak else np.nan,
                         "median_mean_price": float(g["mean_price"].median())})
    return pd.DataFrame(rows)


def save_form_sensitivity(sweeps: dict[str, pd.DataFrame], out_dir: Path) -> list[Path]:
    """Write the form-sensitivity tables and their provenance (`FORM_SENSITIVITY_FILES`) to `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    table, beyond = form_sensitivity_table(sweeps), beyond_peak_table(sweeps)
    paths = [out_dir / f for f in FORM_SENSITIVITY_FILES]
    table.to_csv(paths[0], index=False, float_format="%.6g")
    beyond.to_csv(paths[1], index=False, float_format="%.6g")
    per_form = {f: sw.attrs.get("provenance", {}) for f, sw in sweeps.items()}
    first = next(iter(per_form.values()))
    meta = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "forms": list(sweeps),
        "n_replications": int(first.get("n_replications", 0)),
        "seed": first.get("seed"),
        "config_sha256": first.get("config_sha256"),
        "git": first.get("git"),
        "same_inputs_across_forms": {k: first.get(k) for k in (
            "segment_source", "baseline", "elasticity_values", "start_occupancy", "block_dispersion",
            "observation_noise", "occupancy_cap", "rules", "rolls_forward_years", "start_price_usd",
            "pairing", "search_cost", "welfare_population")},
        "per_form_demand_form": {f: v.get("demand_form") for f, v in per_form.items()},
        "per_form_created_utc": {f: v.get("created_utc") for f, v in per_form.items()},
        "headline": "outputs/tables/cm_sweep.meta.json (config's form and replications)",
    }
    paths[2].write_text(json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8")
    return paths
