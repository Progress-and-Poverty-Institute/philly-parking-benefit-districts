# Output delta of a baseline-config change: priced-hour zone means, busiest hour, cap share. Run once per PHILLYPARKING_CONFIG_DIR.
import os, numpy as np, pandas as pd
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import priced_mask
R="C:/projects/philly-parking-benefit-districts/data/processed"
segs=load_priced_segments(f"{R}/segments.parquet")
pan=baseline_occupancy(segs); cal=pan.attrs["calibration"]
m=pan.merge(segs[["segment_id","zone_id","capacity"]],on="segment_id"); m["priced"]=priced_mask(m.zone_id,m.hour_of_week); pm=m[m.priced]
w=lambda d: np.average(d.occupancy,weights=d.capacity)
mean=pm.groupby("zone_id").apply(w).round(3).to_dict()
busy=pm.groupby(["zone_id","hour_of_week"]).apply(w).groupby("zone_id").max().round(3).to_dict()
print(os.path.basename(os.environ.get("PHILLYPARKING_CONFIG_DIR","default")),"| anchor",cal["anchor_set"],"cap/floor",round(cal["share_at_cap"],3),round(cal["share_at_floor"],3),"| max occ",round(pan.occupancy.max(),3),"| priced-hr mean",mean,"| busiest",busy,"| n priced segs kept",len(segs))
