"""The project's one cruising-cost model: search for a space, block by block.

Every cruising cost in the project, the scenario table's search-cost row and the
Chatman-Manville sweep's search-cost term alike, comes from here. A driver who arrives
checks a block of K spaces; if it is full (probability p = o^K at mean occupancy o, spaces
independent) the driver drives on to the next block, so the expected number of full blocks
an arriving driver passes is p / (1 - p). Search time is that count times the minutes a
full block costs, and the cost of one hour of one segment is

    arrivals x search minutes / 60 x value of time,

with arrivals the cars that park on the segment (occupancy x capacity / mean stay). The
cost is convex in occupancy and has no occupancy target in it: at 85% a block is full one
time in five, at 95% three times in five.

The block is the search unit, not the segment. A block here is `search_unit_spaces` spaces
of curb (`search_cost` in `config/pricing_rules.yaml`) at the occupancy of the segment the
driver arrives at: the blocks the driver checks next are taken to be at that same
occupancy, as in any geometric search model. A segment is a piece of the City centerline
cut at intersections, at attribute breaks and by the builder into pieces of about 80 m
(`spatial/segments.py`); its capacity counts one curb side and on the priced curb runs from
0 to 14 spaces, set by where the data happen to break the street. Passing a block costs the
same minutes whatever segment it sits on, so if the segment were the unit, a short segment
would be full far more often at the same occupancy and be charged far more search per
arrival (at the 0.99 cap, 85 minutes for one space against 8.1 for ten). With a fixed unit
the search minutes per arrival depend on occupancy alone, capacity enters only through
arrivals, and the cost is additive over any cut of the curb: two adjacent segments at one
occupancy cost what one segment of their joint capacity costs. The unit's size matters
only away from the cap (a larger unit is full less often at moderate occupancy); at and
near the cap, where the cost of a priced panel sits, it hardly does.

Level. `cruising_minutes_at_full_block` is the mean search time of the drivers who cruise
when every block is full, in the units of the studies Shoup (2006, Table 1) collects (the
average cruising time of those who cruise: 3.5 to 14 minutes, mean 8.1). A full block is
scored at `occupancy_cap` rather than at 1 (turnover frees a space eventually; above the
cap drivers give up or park elsewhere). A driver who cruises passes 1 / (1 - cap^K) full
blocks on average, so the per-block constant is cruising_minutes x (1 - cap^K); an arrival
cruises only if the first block is full, so the expected search per arrival at a full block
(`SearchCostConfig.minutes_at_full_block`) is cap^K x cruising_minutes (7.3 at 8.1 minutes
and cap 0.99 on 10 spaces). The cap decides how much more a full block costs than a 95%
block and is an axis of the sweep. No Philadelphia measurement of any of these exists; the
parameters are stated assumptions.

The cost counts only the cars that park (served arrivals): a segment-hour whose latent
demand exceeds its capacity is charged the full-block search of the cars it holds and
nothing for the cars it turns away, the same population the surplus and revenue terms count
(`demand.response.cs_change_served`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config


@dataclass(frozen=True)
class SearchCostConfig:
    cruising_minutes_at_full_block: float
    reference_occupancy: float
    search_unit_spaces: float
    mean_duration_hr: float
    occupancy_cap: float
    value_of_time_usd_per_hr: float

    @property
    def p_full_at_cap(self) -> float:
        """Probability that a block at the cap is full: the share of arrivals at a full block who cruise."""
        return float(self.occupancy_cap ** self.search_unit_spaces)

    @property
    def minutes_at_full_block(self) -> float:
        """Expected search per arrival when every block is full: cap^K x the per-cruiser minutes."""
        return self.p_full_at_cap * self.cruising_minutes_at_full_block


def load_search_cost_config(cruising_minutes_at_full_block: float | None = None,
                            occupancy_cap: float | None = None) -> SearchCostConfig:
    """The config's search cost; the two overrides are the sweep's level and cap."""
    rules = load_config("pricing_rules")
    s = rules["search_cost"]
    minutes = (s["cruising_minutes_at_full_block"] if cruising_minutes_at_full_block is None
               else cruising_minutes_at_full_block)
    cap = float(s["occupancy_cap"] if occupancy_cap is None else occupancy_cap)
    if not 0.0 < cap < 1.0:
        raise ValueError(f"occupancy_cap must be in (0, 1), not {cap}")
    return SearchCostConfig(
        cruising_minutes_at_full_block=float(minutes),
        reference_occupancy=float(s["reference_occupancy"]),
        search_unit_spaces=float(s["search_unit_spaces"]),
        mean_duration_hr=float(s["mean_duration_hr"]),
        occupancy_cap=cap,
        value_of_time_usd_per_hr=float(rules["arnott_inci"]["value_of_time_usd_per_hr"]),
    )


def cited_cruising_minutes() -> dict:
    """The cruising-time range the config cites (per cruiser, the level's units); see the module docstring."""
    c = load_config("pricing_rules")["search_cost"]["cited_cruising_minutes"]
    return {"low": float(c["low"]), "high": float(c["high"]), "mean": float(c["mean"]), "source": str(c["source"])}


def _full_blocks_passed(occupancy, spaces):
    p_full = np.power(occupancy, spaces)
    return p_full / (1.0 - p_full)


def minutes_per_full_block(cfg: SearchCostConfig) -> float:
    """Minutes one full block costs a driver who passes it: the model's per-block constant."""
    return cfg.cruising_minutes_at_full_block * (1.0 - cfg.p_full_at_cap)


def reference_minutes_per_cruising_minute(cfg: SearchCostConfig) -> float:
    """Search minutes per arrival at the reference block-hour (95%) per cruising minute of the level.

    The conversion between the two units the breakeven can be quoted in: minutes per arrival
    at the reference = this factor x the per-cruiser minutes at a full block. It is cap^K
    (0.60) at cap 0.95 and falls as the cap rises (a full block then costs far more than a
    95% one).
    """
    ref = min(cfg.reference_occupancy, cfg.occupancy_cap)
    return float((1.0 - cfg.p_full_at_cap) * _full_blocks_passed(ref, cfg.search_unit_spaces))


def expected_search_minutes(occupancy: np.ndarray, cfg: SearchCostConfig) -> np.ndarray:
    """Expected minutes an arriving driver spends passing full blocks; see the module docstring.

    A function of occupancy alone: the block is the search unit, not the segment. Equal to
    `cfg.minutes_at_full_block` at the cap and above.
    """
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, cfg.occupancy_cap)
    return minutes_per_full_block(cfg) * _full_blocks_passed(o, cfg.search_unit_spaces)


def search_cost_usd(occupancy: np.ndarray, capacity: np.ndarray,
                    cfg: SearchCostConfig | None = None) -> np.ndarray:
    """Search cost in dollars for one hour of one segment: served arrivals x search time x value of time."""
    cfg = cfg or load_search_cost_config()
    o = np.clip(np.asarray(occupancy, dtype=float), 0.0, 1.0)
    arrivals_per_hr = o * np.asarray(capacity, dtype=float) / cfg.mean_duration_hr
    return arrivals_per_hr * (expected_search_minutes(o, cfg) / 60.0) * cfg.value_of_time_usd_per_hr


def hourly_search_cost(
    occupancy_panel: pd.DataFrame,
    segments: pd.DataFrame,
    cfg: SearchCostConfig | None = None,
    priced_hours_only: bool = True,
) -> pd.DataFrame:
    """Search cost of every segment-hour of a segment x hour-of-week panel (`search_cost_usd` per row).

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
    out["search_minutes_per_arrival"] = expected_search_minutes(occ, cfg)
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
