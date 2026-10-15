"""Orchestrator. Runs status_quo / seattle / full_pbd x elasticity scenarios."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from phillyparking._config import load_config, outputs_dir

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResults:
    name: str
    elasticity_scenario: str
    prices: pd.DataFrame
    occupancy: pd.DataFrame
    revenue: pd.DataFrame
    cruising_dwl: pd.DataFrame
    cs_change_total: float
    allocation: dict
    diagnostics: dict = field(default_factory=dict)

    def save(self, path) -> Path:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.prices.to_parquet(path / "prices.parquet")
        self.occupancy.to_parquet(path / "occupancy.parquet")
        self.revenue.to_parquet(path / "revenue.parquet")
        self.cruising_dwl.to_parquet(path / "cruising_dwl.parquet")
        meta = {
            "name": self.name,
            "elasticity_scenario": self.elasticity_scenario,
            "cs_change_total": self.cs_change_total,
            "allocation": self.allocation,
            "diagnostics": self.diagnostics,
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
            cruising_dwl=pd.read_parquet(path / "cruising_dwl.parquet"),
            cs_change_total=float(meta["cs_change_total"]),
            allocation=meta["allocation"],
            diagnostics=meta.get("diagnostics", {}),
        )


def _zone_current_prices() -> pd.DataFrame:
    zones = load_config("zones")["zones"]
    return pd.DataFrame([
        {"zone_id": z["id"], "price_usd_per_hr": float(z["current_rate_usd_per_hr"])}
        for z in zones
    ])


def _zone_meta() -> pd.DataFrame:
    zones = load_config("zones")["zones"]
    return pd.DataFrame([
        {
            "zone_id": z["id"],
            "floor": float(z.get("floor", 0.5)),
            "ceiling": float(z.get("ceiling", 10.0)),
        }
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
                  bands: list) -> pd.DataFrame:
    from phillyparking.pricing.seattle_rule import adjust_zone_prices
    occ = occupancy.drop(columns=[c for c in ("zone_id", "capacity") if c in occupancy.columns])
    occ = occ.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    return adjust_zone_prices(occ, current_prices, bands)


def _arnott_zone_prices(panel, segments, current_prices, target_vacancy, elasticity):
    from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci
    from phillyparking.pricing.priced_hours import frame_priced_mask
    rows = []
    z_meta = _zone_meta().set_index("zone_id")
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
        base_price = float(cur_row["price_usd_per_hr"].iloc[0])
        # Occupancy shares: capacity cancels from the Arnott-Inci price.
        p = optimal_price_arnott_inci(
            base_demand=peak_occ,
            base_price=base_price,
            capacity=1.0,
            elasticity=elasticity,
            target_vacancy=target_vacancy,
        )
        floor = z_meta.loc[zid, "floor"] if zid in z_meta.index else 0.5
        ceiling = z_meta.loc[zid, "ceiling"] if zid in z_meta.index else 10.0
        rows.append({"zone_id": zid, "price_usd_per_hr": float(np.clip(p, floor, ceiling)),
                     "peak_occ": peak_occ})
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
    try:
        from phillyparking.revenue.allocation import allocate
        alloc_obj = allocate(total_revenue, pbd_share)
        return alloc_obj.to_dict() if hasattr(alloc_obj, "to_dict") else dict(alloc_obj)
    except (ImportError, ModuleNotFoundError):
        return {
            "total_revenue_usd": total_revenue,
            "pbd_share": pbd_share,
            "pbd_revenue_usd": total_revenue * pbd_share,
            "general_fund_usd": total_revenue * (1.0 - pbd_share),
        }


def _state_metrics(panel, prices, segments, baseline_panel, current_prices, dwl_target_vacancy,
                   pbd_share, seed) -> dict:
    """Revenue, cruising DWL, allocation and CS change of one (panel, prices) state.

    Revenue and DWL both count only priced hours (`pricing.priced_hours`).
    """
    from phillyparking.pricing.priced_hours import hourly_prices, zone_mean_price
    from phillyparking.revenue.forecast import annual_revenue
    from phillyparking.welfare.cruising_dwl import annual_cruising_dwl
    revenue_df = annual_revenue(segments, panel, hourly_prices(prices))
    dwl = annual_cruising_dwl(panel, segments, target_vacancy=dwl_target_vacancy)
    total_revenue = float(revenue_df["annual_revenue_usd"].sum())
    zone_prices = zone_mean_price(prices).rename("price_usd_per_hr")
    cs_total = _synthetic_cs_change(
        segments, baseline_panel, panel, current_prices, zone_prices.reset_index(), seed=seed,
    )
    return {
        "revenue": revenue_df,
        "cruising_dwl": dwl,
        "allocation": _allocation(total_revenue, pbd_share),
        "cs_change_total": cs_total,
        "mean_price_by_zone": zone_prices.to_dict(),
        "total_revenue": total_revenue,
        "cruising_dwl_total": float(dwl["annual_dwl_usd"].sum()),
    }


def _synthetic_cs_change(
    segments: pd.DataFrame,
    baseline_panel: pd.DataFrame,
    scenario_panel: pd.DataFrame,
    baseline_prices: pd.DataFrame,
    scenario_prices: pd.DataFrame,
    n_synthetic_trips: int = 200,
    seed: int = 42,
) -> float:
    from phillyparking.welfare.consumer_surplus import (
        NestedLogitSpec, utilities, consumer_surplus_change,
    )

    spec = NestedLogitSpec(
        nests={"auto": ["curb", "garage"], "non_auto": ["transit", "forgo"]},
        nest_lambda={"auto": 0.7, "non_auto": 0.9},
        alpha_price=-0.40,
        beta_walk=-0.10,
        asc={"curb": 0.0, "garage": -0.5, "transit": -1.0, "forgo": -2.0},
    )
    rng = np.random.default_rng(seed)
    seg_sample = segments.sample(n=min(n_synthetic_trips, len(segments)), replace=True, random_state=seed)
    bp = baseline_prices.set_index("zone_id")["price_usd_per_hr"]
    sp = scenario_prices.set_index("zone_id")["price_usd_per_hr"]

    total = 0.0
    for _, seg in seg_sample.iterrows():
        zid = seg["zone_id"]
        p_b = float(bp.get(zid, 2.0))
        p_s = float(sp.get(zid, 2.0))
        garage = 5.0 + rng.uniform(-1, 1)
        walk_curb = rng.uniform(1, 5)
        walk_garage = rng.uniform(3, 8)
        walk_transit = rng.uniform(5, 12)
        prices_b = pd.DataFrame({"price_usd": [p_b, garage, 2.5, 0.0]},
                                index=["curb", "garage", "transit", "forgo"])
        prices_s = pd.DataFrame({"price_usd": [p_s, garage, 2.5, 0.0]},
                                index=["curb", "garage", "transit", "forgo"])
        walks = pd.DataFrame({"walk_min": [walk_curb, walk_garage, walk_transit, 0.0]},
                             index=["curb", "garage", "transit", "forgo"])
        Vb = utilities(spec, prices_b, walks)
        Vs = utilities(spec, prices_s, walks)
        total += consumer_surplus_change(spec, Vb, Vs)
    return float(total)


def run_scenario(
    name: str,
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    elasticity_scenario: str = "central",
    rolls_forward_years: int | None = None,
    seed: int = 42,
) -> ScenarioResults:
    from phillyparking.elasticity.scenarios import get_scenario, apply_elasticity

    cfg = load_config("scenarios")["scenarios"]
    if name not in cfg:
        raise KeyError(f"Unknown scenario '{name}'. Known: {list(cfg)}")
    scfg = cfg[name]
    if rolls_forward_years is None:
        rolls_forward_years = int(scfg.get("rolls_forward_years", 0))

    segments, baseline_panel = _baseline(segments, baseline_panel, seed=seed)
    elasticity = get_scenario(elasticity_scenario).elasticity

    current_prices = _zone_current_prices()
    baseline_with_price = baseline_panel.merge(
        segments[["segment_id", "zone_id"]], on="segment_id", how="left"
    ).merge(current_prices, on="zone_id", how="left")

    policy = scfg["pricing_policy"]
    policy_kind = policy["kind"]
    # The scorer's cruising threshold is the scenario's own target vacancy when it sets
    # one, else the shared default, so pricer and scorer use the same line.
    dwl_target_vac = float(policy.get(
        "target_vacancy", load_config("pricing_rules")["arnott_inci"]["target_vacancy"]
    ))
    pbd_share = float(scfg.get("rpp_policy", {}).get("revenue_share_to_pbd", 0.0))
    panel = baseline_with_price.copy()
    prices = current_prices.copy()
    diagnostics: dict = {"policy": policy_kind, "max_years": rolls_forward_years,
                         "dwl_target_vacancy": dwl_target_vac}

    if policy_kind == "fixed":
        diagnostics.update(years_run=0, converged=True, converged_year=0)
    elif policy_kind in ("seattle_rule", "arnott_inci"):
        from phillyparking.pricing.priced_hours import hourly_prices
        if policy_kind == "seattle_rule":
            bands = policy["time_of_day_bands"]
            step = lambda pnl, pr: _seattle_step(pnl, pr, segments, bands)  # noqa: E731
        else:
            target_vac = float(policy.get("target_vacancy", 0.15))
            step = lambda pnl, pr: _arnott_zone_prices(pnl, segments, pr, target_vac, elasticity)  # noqa: E731
        # Review annually until the prices stop changing (a fixed point) or repeat with
        # period 2, up to rolls_forward_years reviews. Nothing else in the map moves from
        # year to year, so the state at a fixed point is the rule's long-run outcome and
        # the year it is reached carries no forecast meaning.
        history = [(0, panel, prices, _price_vector(prices))]
        converged_year = None
        cycle = None
        for year in range(1, max(rolls_forward_years, 1) + 1):
            new_prices = step(panel, prices)
            vec = _price_vector(new_prices)
            if _same_prices(vec, history[-1][3]):
                converged_year = year - 1
                break
            prices = new_prices
            panel = apply_elasticity(panel, hourly_prices(prices), elasticity)
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
                                   dwl_target_vac, pbd_share, seed)
                phases.append({
                    "year": y,
                    "prices": pr[[c for c in ("zone_id", "band", "price_usd_per_hr") if c in pr.columns]]
                    .to_dict("records"),
                    **{k: m[k] for k in ("mean_price_by_zone", "total_revenue", "cruising_dwl_total",
                                         "cs_change_total", "allocation")},
                })
            diagnostics["cycle_period"] = 2
            diagnostics["phases"] = phases
            logger.warning("%s: prices cycle with period 2 from year %d; reporting both phases",
                           name, cycle[0][0])
        elif converged_year is None:
            logger.warning("%s: prices still moving after %d reviews", name, history[-1][0])
        diagnostics["final_prices"] = prices.to_dict("records")
    else:
        raise ValueError(f"Unsupported pricing_policy.kind: {policy_kind}")

    seg_prices = _segment_prices(segments, prices.drop(
        columns=[c for c in ("previous_price", "band_occ", "n_hours", "direction", "peak_occ") if c in prices.columns]
    ))
    m = _state_metrics(panel, prices, segments, baseline_panel, current_prices,
                       dwl_target_vac, pbd_share, seed)

    return ScenarioResults(
        name=name,
        elasticity_scenario=elasticity_scenario,
        prices=seg_prices,
        occupancy=panel,
        revenue=m["revenue"],
        cruising_dwl=m["cruising_dwl"],
        cs_change_total=m["cs_change_total"],
        allocation=m["allocation"],
        diagnostics=diagnostics,
    )


def run_all_scenarios(
    segments: pd.DataFrame | None = None,
    baseline_panel: pd.DataFrame | None = None,
    seed: int = 42,
) -> dict[str, ScenarioResults]:
    cfg = load_config("scenarios")["scenarios"]
    out = {}
    for name in cfg:
        out[name] = run_scenario(name, segments=segments, baseline_panel=baseline_panel, seed=seed)
    return out
