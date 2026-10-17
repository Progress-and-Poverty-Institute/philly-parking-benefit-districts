"""The project's one cruising-cost model: search for a space, block by block.

Every cruising cost in the project, the scenario table's search-cost row and the
Chatman-Manville sweep's search-cost term alike, comes from here. A block of K spaces
whose mean occupancy is o is full with probability p = o^K (spaces independent), and a
driver who arrives at a full block drives on and checks the next, so the expected number
of full blocks an arriving driver passes is p / (1 - p). Search time is that count times
the minutes a full block costs, and the cost of one hour of one block is

    arrivals x search minutes / 60 x value of time,

with arrivals the cars that park (occupancy x capacity / mean stay). The cost is convex in
occupancy and has no occupancy target in it: at 85% a 10-space block is full one time in
five, at 95% three times in five.

Level. `minutes_at_full_block` (`search_cost` in `config/pricing_rules.yaml`) is the
expected search time of an arrival at a full block of `reference_capacity` spaces, the
quantity that sets almost all of the cost on a priced panel (full block-hours dominate it),
so the level is stated in those units. A full block is scored at `occupancy_cap` rather than
at 1 (turnover frees a space eventually; above the cap drivers give up or park elsewhere), so
the per-block constant is minutes_at_full_block / (cap^K / (1 - cap^K)). The cap decides how
much more a full block costs than a 95% block and is an axis of the sweep. Shoup (2006,
Table 1) collects studies whose average cruising time is 3.5 to 14 minutes, mean 8.1: that is
the average over the drivers who cruise, not over all arrivals; at a full block cap^K of
arrivals cruise under this model, so the per-arrival figure is cap^K times it. No
Philadelphia measurement of any of these exists; the parameters are stated assumptions.

The cost counts only the cars that park (served arrivals): a block-hour whose latent demand
exceeds its capacity is charged the full-block search of the cars it holds and nothing for
the cars it turns away, the same population the surplus and revenue terms count
(`demand.response.cs_change_served`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config


@dataclass(frozen=True)
class SearchCostConfig:
    minutes_at_full_block: float
    reference_occupancy: float
    reference_capacity: float
    mean_duration_hr: float
    occupancy_cap: float
    value_of_time_usd_per_hr: float


def load_search_cost_config(minutes_at_full_block: float | None = None,
                            occupancy_cap: float | None = None) -> SearchCostConfig:
    """The config's search cost; the two overrides are the sweep's level and cap."""
    rules = load_config("pricing_rules")
    s = rules["search_cost"]
    minutes = s["minutes_at_full_block"] if minutes_at_full_block is None else minutes_at_full_block
    cap = s["occupancy_cap"] if occupancy_cap is None else occupancy_cap
    cap = float(cap)
    if not 0.0 < cap <= 1.0:
        raise ValueError(f"occupancy_cap must be in (0, 1], not {cap}")
    return SearchCostConfig(
        minutes_at_full_block=float(minutes),
        reference_occupancy=float(s["reference_occupancy"]),
        reference_capacity=float(s["reference_capacity"]),
        mean_duration_hr=float(s["mean_duration_hr"]),
        occupancy_cap=cap,
        value_of_time_usd_per_hr=float(rules["arnott_inci"]["value_of_time_usd_per_hr"]),
    )


def cited_cruising_minutes() -> dict:
    """The cruising-time range the config cites (per cruiser, not per arrival); see the module docstring."""
    c = load_config("pricing_rules")["search_cost"]["cited_cruising_minutes"]
    return {"low": float(c["low"]), "high": float(c["high"]), "mean": float(c["mean"]), "source": str(c["source"])}


def _full_blocks_passed(occupancy, capacity):
    p_full = np.power(occupancy, capacity)
    return p_full / (1.0 - p_full)


def minutes_per_full_block(cfg: SearchCostConfig) -> float:
    """Minutes one full block costs a driver who passes it: the model's per-block constant."""
    return cfg.minutes_at_full_block / _full_blocks_passed(cfg.occupancy_cap, cfg.reference_capacity)


def reference_minutes_per_full_block_minute(cfg: SearchCostConfig) -> float:
    """Search minutes at the reference block-hour (95% on 10 spaces) per minute at a full block.

    The conversion between the two units the breakeven can be quoted in: minutes at the
    reference = this factor x minutes at a full block. It is 1 when the cap is the reference
    occupancy and falls as the cap rises (a full block then costs far more than a 95% one).
    """
    return float(_full_blocks_passed(min(cfg.reference_occupancy, cfg.occupancy_cap), cfg.reference_capacity)
                 / _full_blocks_passed(cfg.occupancy_cap, cfg.reference_capacity))


def expected_search_minutes(occupancy: np.ndarray, capacity: np.ndarray,
                            cfg: SearchCostConfig) -> np.ndarray:
    """Expected minutes an arriving driver spends passing full blocks; see the module docstring.

    Equal to `minutes_at_full_block` at a full block of `reference_capacity` spaces.
    Occupancy is capped at `occupancy_cap`; capacity below 1 is treated as 1.
    """
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, cfg.occupancy_cap)
    k = np.maximum(np.asarray(capacity, dtype=float), 1.0)
    return minutes_per_full_block(cfg) * _full_blocks_passed(o, k)


def search_cost_usd(occupancy: np.ndarray, capacity: np.ndarray,
                    cfg: SearchCostConfig | None = None) -> np.ndarray:
    """Search cost in dollars for one hour of one block: served arrivals x search time x value of time."""
    cfg = cfg or load_search_cost_config()
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, 1.0)
    k = np.asarray(capacity, dtype=float)
    arrivals_per_hr = o * k / cfg.mean_duration_hr
    minutes = expected_search_minutes(o, k, cfg)
    return arrivals_per_hr * (minutes / 60.0) * cfg.value_of_time_usd_per_hr


def hourly_search_cost(
    occupancy_panel: pd.DataFrame,
    segments: pd.DataFrame,
    cfg: SearchCostConfig | None = None,
    priced_hours_only: bool = True,
) -> pd.DataFrame:
    """Search cost of every block-hour of a segment x hour-of-week panel (`search_cost_usd` per row).

    With `priced_hours_only` (the default) hours outside the zone's priced hours
    (`pricing.priced_hours`) score zero: the policies compared here act only through the
    meter, so search when the meter is off is the same under every scenario. The panel's
    own `capacity` and `zone_id` columns, if any, are dropped before the merge so that the
    segment table's are used.
    """
    cfg = cfg or load_search_cost_config()
    df = occupancy_panel.drop(columns=[c for c in ("capacity", "zone_id") if c in occupancy_panel.columns]).merge(
        segments[["segment_id", "capacity", "zone_id"]], on="segment_id", how="left"
    )
    occ = df["occupancy"].to_numpy(dtype=float)
    cap = df["capacity"].to_numpy(dtype=float)
    cost = search_cost_usd(occ, cap, cfg)
    if priced_hours_only:
        from phillyparking.pricing.priced_hours import frame_priced_mask
        cost = np.where(frame_priced_mask(df), cost, 0.0)
    out = df[["segment_id", "hour_of_week"]].copy()
    out["search_minutes_per_arrival"] = expected_search_minutes(occ, cap, cfg)
    out["search_cost_usd"] = cost
    return out


def annual_search_cost(
    occupancy_panel: pd.DataFrame,
    segments: pd.DataFrame,
    cfg: SearchCostConfig | None = None,
    priced_weeks: int = 52,
    priced_hours_only: bool = True,
) -> pd.DataFrame:
    """Annual search cost by zone (`annual_search_cost_usd`): `priced_weeks` x the weekly panel's."""
    hourly = hourly_search_cost(occupancy_panel, segments, cfg, priced_hours_only=priced_hours_only)
    weekly = hourly.groupby("segment_id", as_index=False)["search_cost_usd"].sum()
    weekly["search_cost_usd"] *= priced_weeks
    weekly = weekly.merge(segments[["segment_id", "zone_id"]], on="segment_id", how="left")
    out = weekly.groupby("zone_id", as_index=False)["search_cost_usd"].sum()
    return out.rename(columns={"search_cost_usd": "annual_search_cost_usd"})
