"""Orchestrator. Runs status_quo / seattle / full_pbd x elasticity scenarios."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking._config import load_config, outputs_dir
from phillyparking.scenarios.provenance import build_provenance

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResults:
    name: str
    elasticity_scenario: str
    prices: pd.DataFrame
    occupancy: pd.DataFrame
    revenue: pd.DataFrame
    search_cost: pd.DataFrame
    cs_change_total: float
    allocation: dict
    diagnostics: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def save(self, path) -> Path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.prices.to_parquet(path / "prices.parquet")
        self.occupancy.to_parquet(path / "occupancy.parquet")
        self.revenue.to_parquet(path / "revenue.parquet")
        self.search_cost.to_parquet(path / "search_cost.parquet")
        meta = {
            "name": self.name,
            "elasticity_scenario": self.elasticity_scenario,
            "cs_change_total": self.cs_change_total,
            "allocation": self.allocation,
            "diagnostics": self.diagnostics,
            "provenance": self.provenance,
        }
        with open(path / "meta.json", "w") as f:
            json.dump(meta, f, indent=2, default=str)
        return path

    @classmethod
    def load(cls, path) -> "ScenarioResults":
        path = Path(path)
        with open(path / "meta.json") as f:
            meta = json.load(f)
        return cls(
            name=meta["name"],
            elasticity_scenario=meta["elasticity_scenario"],
            prices=pd.read_parquet(path / "prices.parquet"),
            occupancy=pd.read_parquet(path / "occupancy.parquet"),
            revenue=pd.read_parquet(path / "revenue.parquet"),
            search_cost=pd.read_parquet(path / "search_cost.parquet"),
            cs_change_total=float(meta["cs_change_total"]),
            allocation=meta["allocation"],
            diagnostics=meta.get("diagnostics", {}),
            provenance=meta.get("provenance", {}),
        )


SCENARIO_NAMES = ("status_quo", "seattle", "full_pbd")


def default_results_dir() -> Path:
    """Where scripts 05 and 06 write scenario results, and where the app reads them."""
    return outputs_dir() / "models"


def load_saved_scenarios(base: Path | None = None, names=SCENARIO_NAMES) -> dict[str, "ScenarioResults"]:
    """Load saved scenarios from `<base>/<name>/`; raise if any is missing.

    Never recomputes: a result is only as good as the run that wrote it, and the app
    must show that run's numbers, not a silent re-run on a different segment set.
    """
    base = Path(base) if base is not None else default_results_dir()
    missing = [n for n in names if not (base / n / "meta.json").exists()]
    if missing:
        raise FileNotFoundError(
            f"No saved results for {missing} under {base}; run scripts/05_run_scenarios.py first."
        )
    return {n: ScenarioResults.load(base / n) for n in names}


def check_panel(panel: pd.DataFrame, what: str = "occupancy panel") -> None:
    """Fail loudly on a panel the runner would otherwise turn into NaN revenue."""
    missing = [c for c in ("segment_id", "hour_of_week", "occupancy") if c not in panel.columns]
    if missing:
        raise ValueError(f"{what} lacks columns {missing}")
    n_nan = int(panel["occupancy"].isna().sum())
    if n_nan:
        raise ValueError(f"{what} has {n_nan} NaN occupancy values of {len(panel)}")
    lo, hi = float(panel["occupancy"].min()), float(panel["occupancy"].max())
    if lo < 0.0 or hi > 1.0:
        raise ValueError(f"{what} has occupancy outside [0, 1]: min {lo:.3f}, max {hi:.3f}")


def _zone_current_prices() -> pd.DataFrame:
    zones = load_config("zones")["zones"]
    return pd.DataFrame([
        {"zone_id": z["id"], "price_usd_per_hr": float(z["current_rate_usd_per_hr"])}
        for z in zones
    ])


def _segment_prices(segments: pd.DataFrame, zone_prices: pd.DataFrame) -> pd.DataFrame:
    return segments[["segment_id", "zone_id"]].merge(zone_prices, on="zone_id", how="left")


def _baseline(segments=None, baseline_panel=None, seed: int = 42):
    from phillyparking.spatial.synthetic import make_synthetic_segments
    from phillyparking.demand.synthetic_baseline import baseline_occupancy

    if segments is None:
        segments = make_synthetic_segments(n=20)
    if baseline_panel is None:
        baseline_panel = baseline_occupancy(segments, seed=seed)
    return segments, baseline_panel


def _seattle_step(occupancy: pd.DataFrame, current_prices: pd.DataFrame, segments: pd.DataFrame,
                  bands: list, use_zone_floors: bool = True) -> pd.DataFrame:
    from dataclasses import replace
    from phillyparking.pricing.seattle_rule import adjust_zone_prices, load_seattle_config
    occ = occupancy.drop(columns=[c for c in ("zone_id", "capacity") if c in occupancy.columns])
    occ = occ.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    cfg = replace(load_seattle_config(), use_zone_floors=use_zone_floors)
    return adjust_zone_prices(occ, current_prices, bands, config=cfg)


# Columns of an Arnott-Inci review beyond the rates themselves: what the busiest hour and the
# unclipped price were, and which bound (if any) the rate ended on. They describe the review
# and are kept in the run's diagnostics, not on the price frame the next review reads.
_ARNOTT_REVIEW_COLS = ("target_occ", "target_slack", "unclipped_price", "floor", "ceiling",
                       "at_floor", "at_ceiling")


def _arnott_zone_prices(panel, segments, current_prices, target_vacancy, elasticity, reference_prices,
                        use_zone_floors: bool = True):
    """Next zone rates under the Arnott-Inci step; `reference_prices` are the posted rates the
    elasticity applies at (`demand.response`), `current_prices` the rates in force.
    `elasticity` is a scalar or a Series by zone_id (see `run_scenario`).

    Besides `price_usd_per_hr` (the unclipped solution held to the zone's floor and ceiling,
    `seattle_rule.zone_bounds`) each row carries the review's `_ARNOTT_REVIEW_COLS`. The target
    slack is the target occupancy minus the busiest priced hour's occupancy: positive when the
    zone never reaches the target at the rate it has, in which case the unclipped price is
    the rate that would fill the busiest hour to the target and may sit below any floor (or
    below zero, where no non-negative rate attains it).
    """
    from dataclasses import replace
    from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci
    from phillyparking.pricing.priced_hours import frame_priced_mask
    from phillyparking.pricing.seattle_rule import load_seattle_config, zone_bounds
    rows = []
    bounds_cfg = replace(load_seattle_config(), use_zone_floors=use_zone_floors)
    ref = reference_prices.set_index("zone_id")["price_usd_per_hr"]
    panel_drop = panel.drop(columns=[c for c in ("zone_id", "capacity") if c in panel.columns])
    panel_z = panel_drop.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    panel_z = panel_z.loc[frame_priced_mask(panel_z)]
    panel_z = panel_z.assign(_oc=panel_z["occupancy"] * panel_z["capacity"])
    zone_hour = panel_z.groupby(["zone_id", "hour_of_week"], as_index=False).agg(
        _oc=("_oc", "sum"), _cap=("capacity", "sum"),
    )
    zone_hour["occupancy"] = zone_hour["_oc"] / zone_hour["_cap"]
    for zid, zh in zone_hour.groupby("zone_id"):
        cur_row = current_prices.loc[current_prices["zone_id"] == zid]
        if cur_row.empty:
            continue
        # Peak statistic: the zone's busiest priced hour of capacity-weighted occupancy.
        # Arnott-Inci treat a downtown area as one pool of spaces that a cruiser searches
        # block by block, so the occupancy that governs search is the zone aggregate, not
        # any one block. The zone has one rate across its priced hours, so the only rate
        # that holds that aggregate at or below 1 - target_vacancy in every priced hour is
        # the one that brings the busiest priced hour to the target. Unpriced hours are
        # left out because the rate cannot act on them. The panel is a typical-week
        # profile (each hour already averages over weeks), so its maximum is not a single
        # noisy draw; on real week-by-week data a high quantile would be the stabler choice.
        peak_occ = float(zh["occupancy"].max())
        if not peak_occ > 0:
            raise ValueError(f"zone '{zid}' has zero occupancy at every priced hour, so its "
                             f"Arnott-Inci price is undefined (no demand observed, or a data gap)")
        base_price = float(cur_row["price_usd_per_hr"].iloc[0])
        # Occupancy shares: capacity cancels from the Arnott-Inci price.
        p = optimal_price_arnott_inci(
            base_demand=peak_occ,
            base_price=base_price,
            capacity=1.0,
            elasticity=float(elasticity[zid]) if isinstance(elasticity, pd.Series) else elasticity,
            target_vacancy=target_vacancy,
            reference_price=float(ref[zid]) if zid in ref.index else base_price,
        )
        floor, ceiling = zone_bounds(str(zid), bounds_cfg)
        price = float(np.clip(p, floor, ceiling))
        target_occ = 1.0 - target_vacancy
        rows.append({"zone_id": zid, "price_usd_per_hr": price, "peak_occ": peak_occ,
                     "target_occ": target_occ, "target_slack": target_occ - peak_occ,
                     "unclipped_price": float(p), "floor": floor, "ceiling": ceiling,
                     "at_floor": bool(price <= floor + 1e-9), "at_ceiling": bool(price >= ceiling - 1e-9)})
    return pd.DataFrame(rows)


# Two reviews' rates count as the same if no zone (or zone-band) rate differs by more than
# a tenth of a cent per hour. The Arnott-Inci step approaches its fixed point geometrically
# once the 1.0 occupancy clip binds, so an exact-equality test would never fire.
PRICE_TOL_USD = 0.001


def _price_vector(prices: pd.DataFrame) -> pd.Series:
    keys = ["zone_id", "band"] if "band" in prices.columns else ["zone_id"]
    return prices.set_index(keys)["price_usd_per_hr"].sort_index()


def _same_prices(a: pd.Series, b: pd.Series) -> bool:
    if not a.index.equals(b.index):
        return False
    return bool((a - b).abs().max() <= PRICE_TOL_USD)


def _allocation(total_revenue: float, pbd_share: float) -> dict:
    from phillyparking.revenue.allocation import allocate
    return allocate(total_revenue, pbd_share).to_dict()


def _state_metrics(panel, prices, segments, baseline_panel, current_prices,
                   pbd_share, elasticity) -> dict:
    """Revenue, search cost, allocation and CS change of one (panel, prices) state.

    Revenue, search cost and surplus all count only priced hours (`pricing.priced_hours`)
    and only the cars that park: the search cost is the project's one cruising model
    (`welfare/search_cost.py`, served arrivals x search time x value of time) and the
    surplus is the integral of served demand (`_annual_cs_change`).
    """
    from phillyparking.pricing.priced_hours import hourly_prices, zone_mean_price
    from phillyparking.revenue.forecast import annual_revenue
    from phillyparking.welfare.search_cost import annual_search_cost
    revenue_df = annual_revenue(segments, panel, hourly_prices(prices))
    search = annual_search_cost(panel, segments)
    total_revenue = float(revenue_df["annual_revenue_usd"].sum())
    zone_prices = zone_mean_price(prices).rename("price_usd_per_hr")
    cs_total = _annual_cs_change(segments, baseline_panel, current_prices, hourly_prices(prices), elasticity)
    return {
        "revenue": revenue_df,
        "search_cost": search,
        "allocation": _allocation(total_revenue, pbd_share),
        "cs_change_total": cs_total,
        "mean_price_by_zone": zone_prices.to_dict(),
        "total_revenue": total_revenue,
        "search_cost_total": float(search["annual_search_cost_usd"].sum()),
    }


def _annual_cs_change(
    segments: pd.DataFrame,
    baseline_panel: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    scenario_prices: pd.DataFrame,
    elasticity: float | pd.Series,
) -> float:
    """Annual consumer-surplus change in USD: the integral of served demand over every
    priced block-hour, commensurable with annual revenue.

    For each priced block-hour the baseline panel's demand at the baseline (reference) price
    is q_ref = occupancy x capacity; the scenario price p gives
    `demand.response.cs_change_served(q_ref, p_ref, p, elasticity, capacity)`, the exact
    -int_{p_ref}^{p} min(q(x), capacity) dx of the same law the runner moves occupancy
    with; summed and taken over 52 weeks. Negative when prices rise. Only the cars that get
    a space count, the same population as revenue and the search cost (a block whose demand
    exceeds its capacity at the scenario price is rationed to the parkers who value it
    most). It values parkers' surplus only: search time is the search-cost row's job, so
    this is not a welfare total.

    `baseline_prices` is zone-level; `scenario_prices` is zone-level or (zone_id,
    hour_of_week) from `hourly_prices`. A zone with priced block-hours must have a price in
    both; none is invented. `elasticity` is a scalar or a Series by zone_id.
    """
    from phillyparking.demand.response import cs_change_served
    from phillyparking.pricing.priced_hours import frame_priced_mask

    panel = baseline_panel.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline_panel.columns])
    panel = panel.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="inner")
    panel = panel.loc[frame_priced_mask(panel)]
    if panel.empty:
        return 0.0
    bp = baseline_prices.rename(columns={"price": "price_usd_per_hr"})
    sp = scenario_prices.rename(columns={"price": "price_usd_per_hr"})
    keys = [c for c in ("zone_id", "hour_of_week") if c in sp.columns]
    panel = panel.merge(bp[["zone_id", "price_usd_per_hr"]].rename(columns={"price_usd_per_hr": "_p_ref"}),
                        on="zone_id", how="left")
    panel = panel.merge(sp[keys + ["price_usd_per_hr"]].drop_duplicates(keys).rename(columns={"price_usd_per_hr": "_p"}),
                        on=keys, how="left")
    missing = panel["_p_ref"].isna() | panel["_p"].isna()
    if missing.any():
        zones = sorted(panel.loc[missing, "zone_id"].unique())
        raise KeyError(f"zones {zones} have priced block-hours but no baseline or scenario price")
    cap = panel["capacity"].to_numpy(dtype=float)
    q_ref = panel["occupancy"].to_numpy(dtype=float) * cap
    eps = panel["zone_id"].map(elasticity).to_numpy(dtype=float) if isinstance(elasticity, pd.Series) else elasticity
    per_hour = cs_change_served(q_ref, panel["_p_ref"].to_numpy(), panel["_p"].to_numpy(), eps, cap)
    return float(per_hour.sum() * 52)


def citywide_reference_price(segments: pd.DataFrame, posted: pd.DataFrame | None = None) -> float:
    """The reference price p0 of the citywide-law sensitivity: the capacity-weighted mean posted
    rate over the segments in zones `zones.yaml` prices.

    The central prior is one number for the city, not for any zone, so it is placed at the
    price of the average priced space; the zone rates range from $1.50 to $4.00 and a zone's
    own rate would make that zone the reference and the others extrapolations. The value
    depends on the segment set (the fixture's zone mix differs from the real curb's).
    """
    posted = _zone_current_prices() if posted is None else posted
    seg = segments.merge(posted.rename(columns={"price_usd_per_hr": "_posted"}), on="zone_id", how="inner")
    if seg.empty:
        raise ValueError("citywide_reference_price: no segment lies in a zone that zones.yaml prices")
    return float(np.average(seg["_posted"], weights=seg["capacity"]))


def run_scenario(
    name: str,
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    elasticity_scenario: str = "central",
    rolls_forward_years: int | None = None,
    seed: int = 42,
    segment_source: dict | None = None,
    use_zone_floors: bool = True,
    citywide_reference_price: float | None = None,
) -> ScenarioResults:
    """Run one scenario. `use_zone_floors=False` is the floor sensitivity: the `floor` of each
    zone in `zones.yaml` is ignored and only the global floor bounds a rate from below.

    By default the elasticity prior applies at each zone's own posted rate. With
    `citywide_reference_price` p0 it applies at p0 instead, as one law for every zone
    (`demand.response.citywide_zone_elasticities`): each zone's elasticity at its posted rate
    then follows from the law, and `diagnostics["demand_law"]` records them.
    """
    from phillyparking.demand.response import citywide_zone_elasticities, load_demand_form
    from phillyparking.elasticity.scenarios import get_scenario, apply_elasticity

    cfg = load_config("scenarios")["scenarios"]
    if name not in cfg:
        raise KeyError(f"Unknown scenario '{name}'. Known: {list(cfg)}")
    scfg = cfg[name]
    if rolls_forward_years is None:
        rolls_forward_years = int(scfg.get("rolls_forward_years", 0))

    segments, baseline_panel = _baseline(segments, baseline_panel, seed=seed)
    check_panel(baseline_panel, "baseline panel")
    elasticity_spec = get_scenario(elasticity_scenario)
    elasticity = elasticity_spec.elasticity

    current_prices = _zone_current_prices()
    if citywide_reference_price is None:
        zone_elasticity = {str(z): float(elasticity) for z in current_prices["zone_id"]}
        demand_law = {"anchoring": "per_zone", "reference_price": None}
    else:
        elasticity = citywide_zone_elasticities(current_prices, elasticity, float(citywide_reference_price))
        zone_elasticity = {str(z): float(v) for z, v in elasticity.items()}
        demand_law = {"anchoring": "citywide", "reference_price": float(citywide_reference_price)}
    demand_law.update(form=load_demand_form(), headline_elasticity=float(elasticity_spec.elasticity),
                      zone_elasticity_at_posted_rate=zone_elasticity)
    baseline_with_price = baseline_panel.merge(
        segments[["segment_id", "zone_id"]], on="segment_id", how="left"
    ).merge(current_prices, on="zone_id", how="left")

    policy = scfg["pricing_policy"]
    policy_kind = policy["kind"]
    # The Arnott-Inci pricer's target; the search-cost scorer has no target in it.
    target_vac = float(policy.get(
        "target_vacancy", load_config("pricing_rules")["arnott_inci"]["target_vacancy"]
    ))
    pbd_share = float(scfg.get("rpp_policy", {}).get("revenue_share_to_pbd", 0.0))
    panel = baseline_with_price.copy()
    prices = current_prices.copy()
    diagnostics: dict = {"policy": policy_kind, "max_years": rolls_forward_years,
                         "target_vacancy": target_vac, "use_zone_floors": bool(use_zone_floors),
                         "demand_law": demand_law}
    # Zones the fixture or the real segments carry that zones.yaml does not configure have
    # no price and no priced hours: they earn nothing and are not scored for cruising.
    configured = set(current_prices["zone_id"])
    unpriced = segments.loc[~segments["zone_id"].isin(configured)]
    if len(unpriced):
        diagnostics["unpriced_zones"] = {
            str(z): {"n_segments": int(len(g)), "capacity": float(g["capacity"].sum())}
            for z, g in unpriced.groupby("zone_id")
        }
        logger.warning("%s: %d segments in zones absent from zones.yaml (%s) earn no revenue",
                       name, len(unpriced), sorted(diagnostics["unpriced_zones"]))

    if policy_kind == "fixed":
        diagnostics.update(years_run=0, converged=True, converged_year=0)
    elif policy_kind in ("seattle_rule", "arnott_inci"):
        from phillyparking.pricing.priced_hours import hourly_prices
        if policy_kind == "seattle_rule":
            bands = policy["time_of_day_bands"]
            step = lambda pnl, pr: _seattle_step(pnl, pr, segments, bands, use_zone_floors)  # noqa: E731
        else:
            step = lambda pnl, pr: _arnott_zone_prices(pnl, segments, pr, target_vac, elasticity, current_prices,
                                                       use_zone_floors)  # noqa: E731
        # Review annually until the prices stop changing (a fixed point) or repeat with
        # period 2, up to rolls_forward_years reviews. Nothing else in the map moves from
        # year to year, so the state at a fixed point is the rule's long-run outcome and
        # the year it is reached carries no forecast meaning.
        history = [(0, panel, prices, _price_vector(prices))]
        converged_year = None
        cycle = None
        reviews = []   # Arnott-Inci only: every review's per-zone detail
        for year in range(1, max(rolls_forward_years, 1) + 1):
            new_prices = step(panel, prices)
            if policy_kind == "arnott_inci":
                reviews.append(new_prices)
                new_prices = new_prices.drop(columns=list(_ARNOTT_REVIEW_COLS))
            vec = _price_vector(new_prices)
            if _same_prices(vec, history[-1][3]):
                converged_year = year - 1
                break
            prices = new_prices
            panel = apply_elasticity(panel, hourly_prices(prices), elasticity, reference_price=current_prices)
            history.append((year, panel, prices, vec))
            if len(history) >= 3 and _same_prices(vec, history[-3][3]):
                cycle = history[-2:]
                break
        diagnostics["years_run"] = history[-1][0]
        diagnostics["converged"] = converged_year is not None
        diagnostics["converged_year"] = converged_year
        if cycle is not None:
            # A two-cycle has no single outcome: report both phases. The returned state
            # is the later phase; `phases` carries both for the comparison table.
            phases = []
            for y, pnl, pr, _ in cycle:
                m = _state_metrics(pnl, pr, segments, baseline_panel, current_prices,
                                   pbd_share, elasticity)
                phases.append({
                    "year": y,
                    "prices": pr[[c for c in ("zone_id", "band", "price_usd_per_hr") if c in pr.columns]]
                    .to_dict("records"),
                    **{k: m[k] for k in ("mean_price_by_zone", "total_revenue", "search_cost_total",
                                         "cs_change_total", "allocation")},
                })
            diagnostics["cycle_period"] = 2
            diagnostics["phases"] = phases
            logger.warning("%s: prices cycle with period 2 from year %d; reporting both phases",
                           name, cycle[0][0])
        elif converged_year is None:
            logger.warning("%s: prices still moving after %d reviews", name, history[-1][0])
        diagnostics["final_prices"] = prices.to_dict("records")
        if reviews:
            # The first review is against the posted rates (is the target reachable at all?);
            # the last against the state the run ends in (how far below it the zone stays).
            diagnostics["zone_pricing"] = {
                "first_review": reviews[0].to_dict("records"),
                "last_review": reviews[-1].to_dict("records"),
            }
    else:
        raise ValueError(f"Unsupported pricing_policy.kind: {policy_kind}")

    seg_prices = _segment_prices(segments, prices.drop(
        columns=[c for c in ("previous_price", "band_occ", "n_hours", "direction", "peak_occ") if c in prices.columns]
    ))
    m = _state_metrics(panel, prices, segments, baseline_panel, current_prices,
                       pbd_share, elasticity)

    check_panel(panel, "scenario panel")
    if not np.isfinite(m["total_revenue"]):
        raise ValueError(f"{name}: total revenue is not finite")

    return ScenarioResults(
        name=name,
        elasticity_scenario=elasticity_scenario,
        prices=seg_prices,
        occupancy=panel,
        revenue=m["revenue"],
        search_cost=m["search_cost"],
        cs_change_total=m["cs_change_total"],
        allocation=m["allocation"],
        diagnostics=diagnostics,
        provenance=build_provenance(segments, elasticity_spec, seed, segment_source),
    )


def run_all_scenarios(
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    seed: int = 42,
    segment_source: dict | None = None,
) -> dict[str, ScenarioResults]:
    cfg = load_config("scenarios")["scenarios"]
    out = {}
    for name in cfg:
        out[name] = run_scenario(name, segments=segments, baseline_panel=baseline_panel, seed=seed,
                                segment_source=segment_source)
    return out
