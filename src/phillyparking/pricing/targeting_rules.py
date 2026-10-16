"""The targeting rules compared in the Chatman-Manville sweep: one implementation each.

Every rule is one annual review of a rate, a +-`step_usd` move decided by comparing one
statistic of occupancy with the same 0.70 / 0.85 band (`chatman_manville:` in
`config/pricing_rules.yaml`): above the band raise, below it cut, inside it hold. The rules
differ in two things only, which is what the sweep varies:

* the **statistic**: the peak (the `peak_quantile`, 0.95, of block-hour occupancy: keep a
  vacancy at the busiest block-hours) or the mean of the same block-hours;
* the **instrument**: one rate per zone over all its priced hours, or one rate per zone and
  time-of-day band (`time_of_day_bands` of the Seattle scenario in `config/scenarios.yaml`).

  peak_zone          q95 of priced block-hours in the zone -> one zone rate
  mean_zone          mean of priced block-hours in the zone -> one zone rate
  peak_band          q95 of priced block-hours in the zone and band -> one rate per zone-band
  mean_band          mean of priced block-hours in the zone and band -> one rate per zone-band
  seattle_rule       the project's own rule (`pricing.seattle_rule`): per zone and band, the
                     capacity-weighted priced-hour mean, dead band, two steps at 0.95
  min_vacancy_peak   q95 over all 168 hours -> one zone rate (the original sweep's rule)
  avg_occupancy      mean over all 168 hours -> one zone rate (the original comparator; the
                     weakest averaging rule, kept for `ordering_violations`)

Block-hours are unweighted: a full block is a full block whatever its size. Every rule applies
the zone's `zones.yaml` floor and ceiling (the global bounds for a zone not listed). A zone
with no priced hours is not reviewed by a priced-hours rule: its rate holds.

`panel` carries segment_id, zone_id, hour_of_week, occupancy, capacity and the current
price_usd_per_hr. `review` returns the new prices in the shape `apply_elasticity` merges:
(zone_id, price_usd_per_hr) for the zone rules, (zone_id, hour_of_week, price_usd_per_hr)
for the band rules and the Seattle rule, whose prices are defined only on priced hours.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import frame_priced_mask, hourly_prices
from phillyparking.pricing.seattle_rule import (
    adjust_zone_prices, band_label, load_seattle_config, zone_bounds,
)

PEAK_RULE = "peak_zone"
ZONE_RULES = ("peak_zone", "mean_zone", "min_vacancy_peak", "avg_occupancy")
BAND_RULES = ("peak_band", "mean_band")
RULE_NAMES = ("peak_zone", "mean_zone", "peak_band", "mean_band", "seattle_rule",
              "min_vacancy_peak", "avg_occupancy")


@dataclass(frozen=True)
class TargetingConfig:
    occ_low: float
    occ_high: float
    step_usd: float
    peak_quantile: float
    bands: tuple


def load_targeting_config() -> TargetingConfig:
    cm = load_config("pricing_rules")["chatman_manville"]
    bands = load_config("scenarios")["scenarios"]["seattle"]["pricing_policy"]["time_of_day_bands"]
    return TargetingConfig(
        occ_low=float(cm["occ_low"]), occ_high=float(cm["occ_high"]),
        step_usd=float(cm["step_usd"]), peak_quantile=float(cm["peak_quantile"]),
        bands=tuple((int(a), int(b)) for a, b in bands),
    )


def step_for(statistic: float, cfg: TargetingConfig) -> float:
    """+step above the band, -step below it, 0 inside [occ_low, occ_high]."""
    if statistic > cfg.occ_high:
        return cfg.step_usd
    if statistic < cfg.occ_low:
        return -cfg.step_usd
    return 0.0


def _statistic(occ: pd.Series, by, rule: str, cfg: TargetingConfig) -> dict:
    if rule.startswith("peak") or rule == "min_vacancy_peak":
        return occ.groupby(by).quantile(cfg.peak_quantile).to_dict()
    return occ.groupby(by).mean().to_dict()


def _zone_statistic(panel: pd.DataFrame, rule: str, cfg: TargetingConfig) -> dict[str, float]:
    """zone_id -> the rule's statistic over its window."""
    z = panel["zone_id"].to_numpy()
    occ = panel["occupancy"]
    if rule in ("min_vacancy_peak", "avg_occupancy"):
        return _statistic(occ, z, rule, cfg)
    if rule in ("peak_zone", "mean_zone"):
        priced = frame_priced_mask(panel)
        return _statistic(occ[priced], z[priced], rule, cfg)
    raise ValueError(f"no zone statistic for rule {rule!r}")


def zone_rule_prices(panel: pd.DataFrame, rule: str, cfg: TargetingConfig | None = None) -> pd.DataFrame:
    """Next rates under a zone-level rule: (zone_id, price_usd_per_hr).

    A zone the rule has no statistic for (no priced hours) keeps its rate.
    """
    cfg = cfg or load_targeting_config()
    sea = load_seattle_config()
    stats = _zone_statistic(panel, rule, cfg)
    # The rate in force is the one on the zone's priced rows; a panel may carry a stale
    # price on meter-off rows. A zone with no priced rows (never priced) reads any row.
    priced = frame_priced_mask(panel)
    current = panel.loc[priced].groupby("zone_id")["price_usd_per_hr"].first()
    current = current.combine_first(panel.groupby("zone_id")["price_usd_per_hr"].first())
    rows = []
    for zid, price in current.items():
        floor, ceiling = zone_bounds(str(zid), sea)
        step = step_for(float(stats[zid]), cfg) if zid in stats else 0.0
        rows.append({"zone_id": zid, "price_usd_per_hr": float(np.clip(price + step, floor, ceiling))})
    return pd.DataFrame(rows)


def _current_band_prices(panel: pd.DataFrame, bands) -> pd.DataFrame:
    """The zone x band rates in force, read off the panel's per-row prices."""
    priced = frame_priced_mask(panel)
    hod = panel["hour_of_week"].to_numpy() % 24
    rows = []
    for a, b in bands:
        m = priced & (hod >= a) & (hod < b)
        for zid, p in panel.loc[m].groupby("zone_id")["price_usd_per_hr"].first().items():
            rows.append({"zone_id": zid, "band": band_label((a, b)), "band_start": a, "band_end": b,
                         "price_usd_per_hr": float(p)})
    return pd.DataFrame(rows, columns=["zone_id", "band", "band_start", "band_end", "price_usd_per_hr"])


def band_rule_prices(panel: pd.DataFrame, rule: str, cfg: TargetingConfig | None = None) -> pd.DataFrame:
    """Next rates under `peak_band` / `mean_band`: (zone_id, hour_of_week, price_usd_per_hr).

    Each zone-band steps on its own statistic of the priced block-hours whose hour of day
    falls in the band, within the zone's floor and ceiling. A zone-band with no priced hours
    has no row.
    """
    cfg = cfg or load_targeting_config()
    sea = load_seattle_config()
    current = _current_band_prices(panel, cfg.bands)
    cols = ["zone_id", "hour_of_week", "price_usd_per_hr"]
    if current.empty:
        return pd.DataFrame(columns=cols)
    priced = frame_priced_mask(panel)
    hod = panel["hour_of_week"].to_numpy() % 24
    occ = panel["occupancy"]
    z = panel["zone_id"].to_numpy()
    new = current.copy()
    for i, r in current.iterrows():
        m = priced & (hod >= r["band_start"]) & (hod < r["band_end"]) & (z == r["zone_id"])
        stat = _statistic(occ[m], z[m], rule, cfg).get(r["zone_id"])
        floor, ceiling = zone_bounds(str(r["zone_id"]), sea)
        step = step_for(float(stat), cfg) if stat is not None else 0.0
        new.loc[i, "price_usd_per_hr"] = float(np.clip(r["price_usd_per_hr"] + step, floor, ceiling))
    return hourly_prices(new)[cols]


def seattle_rule_prices(panel: pd.DataFrame, cfg: TargetingConfig | None = None) -> pd.DataFrame:
    """Next rates under the project's Seattle rule: (zone_id, hour_of_week, price_usd_per_hr)."""
    cfg = cfg or load_targeting_config()
    current = _current_band_prices(panel, cfg.bands)
    cols = ["zone_id", "hour_of_week", "price_usd_per_hr"]
    if current.empty:
        return pd.DataFrame(columns=cols)
    new = adjust_zone_prices(panel, current, [list(b) for b in cfg.bands])
    return hourly_prices(new)[cols]


def review(rule: str, panel: pd.DataFrame, cfg: TargetingConfig | None = None) -> pd.DataFrame:
    """One annual review of every zone under `rule`; see the module docstring for the shape."""
    if rule == "seattle_rule":
        return seattle_rule_prices(panel, cfg)
    if rule in BAND_RULES:
        return band_rule_prices(panel, rule, cfg)
    if rule in ZONE_RULES:
        return zone_rule_prices(panel, rule, cfg)
    raise ValueError(f"unknown targeting rule {rule!r}; known: {RULE_NAMES}")
