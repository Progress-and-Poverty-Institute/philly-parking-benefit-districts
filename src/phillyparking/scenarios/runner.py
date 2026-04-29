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


def _seattle_step(occupancy: pd.DataFrame, current_prices: pd.DataFrame, segments: pd.DataFrame) -> pd.DataFrame:
    from phillyparking.pricing.seattle_rule import adjust_zone_prices
    occ = occupancy.drop(columns=[c for c in ("zone_id",) if c in occupancy.columns])
    occ_with_zone = occ.merge(segments[["segment_id", "zone_id"]], on="segment_id", how="left")
    if "capacity" not in occ_with_zone.columns:
        occ_with_zone = occ_with_zone.merge(segments[["segment_id", "capacity"]], on="segment_id", how="left")
    return adjust_zone_prices(occ_with_zone, current_prices)


def _arnott_zone_prices(panel, segments, current_prices, target_vacancy, elasticity):
    from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci
    rows = []
    z_meta = _zone_meta().set_index("zone_id")
    panel_drop = panel.drop(columns=[c for c in ("zone_id", "capacity") if c in panel.columns])
    panel_z = panel_drop.merge(segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
    for zid, zg in panel_z.groupby("zone_id"):
        cur_row = current_prices.loc[current_prices["zone_id"] == zid]
        if cur_row.empty:
            continue
        base_demand = float((zg["occupancy"] * zg["capacity"]).mean())
        capacity = float(zg["capacity"].mean())
        base_price = float(cur_row["price_usd_per_hr"].iloc[0])
        p = optimal_price_arnott_inci(
            base_demand=base_demand,
            base_price=base_price,
            capacity=capacity,
            elasticity=elasticity,
            target_vacancy=target_vacancy,
        )
        floor = z_meta.loc[zid, "floor"] if zid in z_meta.index else 0.5
        ceiling = z_meta.loc[zid, "ceiling"] if zid in z_meta.index else 10.0
        rows.append({"zone_id": zid, "price_usd_per_hr": float(np.clip(p, floor, ceiling))})
    return pd.DataFrame(rows)


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
    from phillyparking.welfare.cruising_dwl import annual_cruising_dwl

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

    policy_kind = scfg["pricing_policy"]["kind"]
    panel = baseline_with_price.copy()
    prices = current_prices.copy()
    diagnostics: dict = {"policy": policy_kind, "years": rolls_forward_years}

    if policy_kind == "fixed":
        pass
    elif policy_kind == "seattle_rule":
        for _ in range(max(rolls_forward_years, 1)):
            prices = _seattle_step(panel, prices, segments)
            panel = apply_elasticity(panel, prices, elasticity)
    elif policy_kind == "arnott_inci":
        target_vac = float(scfg["pricing_policy"].get("target_vacancy", 0.15))
        for _ in range(max(rolls_forward_years, 1)):
            prices = _arnott_zone_prices(panel, segments, prices, target_vac, elasticity)
            panel = apply_elasticity(panel, prices, elasticity)
    else:
        raise ValueError(f"Unsupported pricing_policy.kind: {policy_kind}")

    seg_prices = _segment_prices(segments, prices)

    try:
        from phillyparking.revenue.forecast import annual_revenue
        revenue_df = annual_revenue(segments, panel, seg_prices)
    except (ImportError, ModuleNotFoundError):
        merged = panel.merge(segments[["segment_id", "capacity"]], on="segment_id", how="left")
        merged = merged.merge(seg_prices, on=["segment_id", "zone_id"], how="left")
        merged["hourly_revenue"] = merged["occupancy"] * merged["capacity"] * merged["price_usd_per_hr"]
        per_seg = merged.groupby(["segment_id", "zone_id"], as_index=False)["hourly_revenue"].sum()
        per_seg["annual_revenue_usd"] = per_seg["hourly_revenue"] * 52.0
        revenue_df = per_seg[["segment_id", "zone_id", "annual_revenue_usd"]]

    total_revenue = float(revenue_df["annual_revenue_usd"].sum())

    rpp_policy = scfg.get("rpp_policy", {})
    pbd_share = float(rpp_policy.get("revenue_share_to_pbd", 0.0))
    try:
        from phillyparking.revenue.allocation import allocate
        alloc_obj = allocate(total_revenue, pbd_share)
        allocation = alloc_obj.to_dict() if hasattr(alloc_obj, "to_dict") else dict(alloc_obj)
    except (ImportError, ModuleNotFoundError):
        allocation = {
            "total_revenue_usd": total_revenue,
            "pbd_share": pbd_share,
            "pbd_revenue_usd": total_revenue * pbd_share,
            "general_fund_usd": total_revenue * (1.0 - pbd_share),
        }

    dwl = annual_cruising_dwl(panel, segments)

    baseline_prices_df = current_prices
    cs_total = _synthetic_cs_change(
        segments, baseline_panel, panel,
        baseline_prices_df, prices,
        seed=seed,
    )

    return ScenarioResults(
        name=name,
        elasticity_scenario=elasticity_scenario,
        prices=seg_prices,
        occupancy=panel,
        revenue=revenue_df,
        cruising_dwl=dwl,
        cs_change_total=cs_total,
        allocation=allocation,
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
