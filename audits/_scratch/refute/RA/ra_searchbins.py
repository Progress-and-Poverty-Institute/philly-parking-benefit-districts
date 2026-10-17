"""RA probe: where the $108M 'sweep-shape' search cost on the Seattle panel comes from: by block capacity bin."""
import numpy as np, pandas as pd
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.welfare.targeting_welfare import load_search_cost_config, search_cost_usd, expected_search_minutes
MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
cfg = load_search_cost_config()
o = pd.read_parquet(f"{MAIN}/outputs/models/seattle/occupancy.parquet").drop(columns=["zone_id"]).merge(segs[["segment_id","zone_id","capacity"]], on="segment_id")
o = o.loc[frame_priced_mask(o)].copy()
o["sc"] = search_cost_usd(o.occupancy.values, o.capacity.values, cfg) * 52
o["mins"] = expected_search_minutes(o.occupancy.values, o.capacity.values, cfg)
o["kbin"] = pd.cut(o.capacity, [-1, 0, 3, 5, 8, 10, 15], labels=["0", "1-3", "4-5", "6-8", "9-10", "11-14"])
o["full"] = o.occupancy >= 0.99
t = o.groupby("kbin", observed=True).agg(bh=("sc", "size"), share_full=("full", "mean"), sc_musd=("sc", lambda s: s.sum()/1e6), mins_at_full=("mins", lambda s: s[o.loc[s.index, "full"]].mean() if o.loc[s.index, "full"].any() else np.nan))
print(t.to_string()); print("total $M:", round(o.sc.sum()/1e6, 1))
print("share of $ from blocks at >=0.99:", round(o.loc[o.full, "sc"].sum()/o.sc.sum(), 3))
print("by zone $M:", (o.groupby("zone_id").sc.sum()/1e6).round(1).to_dict())
# with K fixed at 10 for every block (the sweep's reference block), same occupancies
o["sc10"] = search_cost_usd(o.occupancy.values, np.full(len(o), 10.0), cfg) * 52 * (o.capacity.values/10.0)
print("if every block were K=10 at its own occupancy (arrivals scaled by true cap): $M", round(o.sc10.sum()/1e6, 1))
