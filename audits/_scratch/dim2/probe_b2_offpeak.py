"""(b) continued: the third level constant, offpeak_floor, and why the zone aggregate never aligns."""
import numpy as np, pandas as pd
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.demand.synthetic_baseline import baseline_occupancy, baseline_anchors, _mix_weights
MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
seg_cols = segs[["segment_id", "zone_id", "capacity"]]
def zone_stats(panel):
    p = panel.merge(seg_cols, on="segment_id").loc[lambda d: frame_priced_mask(d)].copy()
    p["_oc"] = p.occupancy * p.capacity
    zh = p.groupby(["zone_id", "hour_of_week"]).agg(_oc=("_oc", "sum"), _c=("capacity", "sum"))
    zh["occ"] = zh._oc / zh._c
    g = zh.groupby("zone_id")["occ"]
    return pd.DataFrame({"busiest": g.max().round(3), "mean": g.mean().round(3)})
for off in (0.20, 0.40, 0.60):
    for ldp, pt in ((0.62, 0.92), (0.85, 0.99)):
        if off >= ldp: continue
        st = zone_stats(baseline_occupancy(segs, seed=42, peak_target=pt, low_demand_peak=ldp, offpeak_floor=off))
        st["arnott"] = np.where(st.busiest > 0.85, "RAISE", "cut")
        print(f"\noffpeak_floor={off} low_demand_peak={ldp} peak_target={pt}"); print(st.to_string())
# Why the aggregate sits low: per-segment peak hour and the land-use mix in each zone
a = baseline_anchors("philadelphia")
mix = _mix_weights(segs, float(a["mix_temperature"]), a)
m = pd.DataFrame(mix, columns=["office", "retail", "residential"]).assign(zone=segs.zone_id.values, cap=segs.capacity.values)
print("\nCapacity-weighted land-use mix by zone (office / retail / residential):")
print(m.groupby("zone").apply(lambda g: pd.Series({c: round(float(np.average(g[c], weights=g.cap)), 3) for c in ("office", "retail", "residential")})).to_string())
pan = pd.read_parquet(f"{MAIN}/data/processed/demand_panel.parquet").merge(seg_cols, on="segment_id")
pan = pan.loc[frame_priced_mask(pan)]
pk = pan.loc[pan.groupby("segment_id").occupancy.idxmax()]
pk["hod"] = pk.hour_of_week % 24; pk["dow"] = pk.hour_of_week // 24
print("\nShare of each zone's priced capacity whose own weekly peak falls in each hour-of-day (weekday rows):")
print(pk[pk.dow < 5].groupby(["zone_id", "hod"]).capacity.sum().unstack(fill_value=0).pipe(lambda t: (t.div(t.sum(axis=1), axis=0)).round(2)).to_string())
print("\nMean segment own-peak (capacity-weighted) vs zone busiest hour:")
print(pk.groupby("zone_id").apply(lambda g: round(float(np.average(g.occupancy, weights=g.capacity)), 3)).to_string())
