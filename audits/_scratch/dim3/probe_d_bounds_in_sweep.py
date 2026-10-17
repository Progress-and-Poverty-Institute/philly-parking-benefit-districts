"""(2) Fairness: in how many of the 54 cells is a rule's year-8 price the configured zone floor or
ceiling (zones.yaml, Philadelphia's bounds applied to the fixture) rather than the statistic's choice?
Reads the tracked parquet; the all-floor / all-ceiling mean price is computed from the fixture's
priced block-hour composition."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.spatial.synthetic import make_synthetic_segments
W = "C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/outputs/tables/"
zones = {z["id"]: z for z in load_config("zones")["zones"]}
segs = make_synthetic_segments(n=120, seed=42)
segs = segs[segs.zone_id.isin(zones)].reset_index(drop=True)
rows = [{"zone_id": s.zone_id, "hour_of_week": h} for s in segs.itertuples() for h in range(168)]
base = pd.DataFrame(rows); base["price_usd_per_hr"] = 2.0
pm = frame_priced_mask(base); pb = base[pm]
floor_mean = float(pb.zone_id.map(lambda z: zones[z]["floor"]).mean())
ceil_mean = float(pb.zone_id.map(lambda z: zones[z]["ceiling"]).mean())
print(f"fixture priced block-hours {len(pb)}; zone shares {pb.zone_id.value_counts(normalize=True).round(3).to_dict()}")
print(f"mean price if every zone at its floor: {floor_mean:.3f}; at its ceiling: {ceil_mean:.3f}")
raw = pd.read_parquet(W + "cm_sweep.parquet")
AX = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
y8 = raw[raw.year == 8]
med = y8.groupby(AX + ["rule"]).mean_price.median().reset_index()
for rule in ("mean_zone", "mean_band", "seattle_rule", "peak_zone", "peak_band"):
    m = med[med.rule == rule]
    at_floor = np.isclose(m.mean_price, floor_mean, atol=1e-3).sum()
    at_ceil = np.isclose(m.mean_price, ceil_mean, atol=1e-3).sum()
    print(f"{rule:13s}: cells (of 54) with year-8 median mean price == all-floor {at_floor:2d}, == all-ceiling {at_ceil:2d}")
# per rep-year: share of zones at a bound, read from the raw mean_price? not available per zone; use the cell medians above.
# cells where BOTH sides of the mean-vs-peak comparison are bound-set
mz = med[med.rule == "mean_zone"].set_index(AX).mean_price; pz = med[med.rule == "peak_zone"].set_index(AX).mean_price
both = (np.isclose(mz, floor_mean, atol=1e-3) & np.isclose(pz.reindex(mz.index), ceil_mean, atol=1e-3)).sum()
either = (np.isclose(mz, floor_mean, atol=1e-3) | np.isclose(pz.reindex(mz.index), ceil_mean, atol=1e-3)).sum()
print(f"mean_zone vs peak_zone: cells where the mean rule is at the floors AND the peak rule at the ceilings: {both}; either: {either} of 54")
print("by start_occupancy, cells with either side bound-set:")
e = (np.isclose(mz, floor_mean, atol=1e-3) | np.isclose(pz.reindex(mz.index), ceil_mean, atol=1e-3)).groupby(level="start_occupancy").sum()
print(e.to_string())
