"""RA probe: is the kernel-mix de-alignment the reason outer zones stay below 0.85, or the levels/intensity?
Upper bound (all peaks aligned) = capacity-weighted mean segment peak; then busiest hour under other mixes."""
import numpy as np, pandas as pd
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.demand.synthetic_baseline import baseline_occupancy, baseline_anchors, _latent_intensity
MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
sc = segs[["segment_id", "zone_id", "capacity"]]
def busiest(panel):
    p = panel.merge(sc, on="segment_id").loc[lambda d: frame_priced_mask(d)].copy()
    p["_oc"] = p.occupancy * p.capacity
    zh = p.groupby(["zone_id", "hour_of_week"]).agg(_oc=("_oc", "sum"), _c=("capacity", "sum"))
    return (zh._oc / zh._c).groupby("zone_id").max()
a = baseline_anchors("philadelphia")
lam = _latent_intensity(segs, a)
ln = np.clip((lam - a["intensity_low"]) / (a["intensity_high"] - a["intensity_low"]), 0, 1)
w = segs.capacity.values
print("cap-weighted mean lam_norm by zone:", pd.Series(ln).groupby(segs.zone_id.values).apply(lambda s: round(float(np.average(s, weights=w[s.index])), 3)).to_dict())
for ldp, pt in ((0.62, 0.92), (0.85, 0.99)):
    segpk = ldp + (pt - ldp) * ln
    ub = pd.Series(segpk).groupby(segs.zone_id.values).apply(lambda s: round(float(np.average(s, weights=w[s.index])), 3))
    print(f"\nlevels {ldp}/{pt}: ALIGNED-PEAK UPPER BOUND on busiest zone-hour (cap-weighted mean seg peak):", ub.to_dict())
print("\n=== mix_temperature sweep (levels default 0.62/0.92 and 0.85/0.99, offpeak 0.20)")
for T in (0.0, 1.0, 2.5, 5.0, 25.0):
    aa = dict(a); aa["mix_temperature"] = T
    for ldp, pt in ((0.62, 0.92), (0.85, 0.99)):
        b = busiest(baseline_occupancy(segs, seed=42, anchors=aa, peak_target=pt, low_demand_peak=ldp))
        print(f"T={T:5.1f} levels {ldp}/{pt}:", b.round(3).to_dict())
print("\n=== mix weights: residential excluded (pop_density mix_weight -> -10, i.e. office/retail only); and all-office")
for label, mw in (("no residential", {"pop_density": -10.0}), ("office only", {"pois_count": -10.0, "pop_density": -10.0})):
    aa = dict(a); aa["covariates"] = {c: dict(v) for c, v in a["covariates"].items()}
    for c, m in mw.items(): aa["covariates"][c]["mix_weight"] = m
    for ldp, pt, off in ((0.62, 0.92, 0.20), (0.85, 0.99, 0.20), (0.85, 0.99, 0.60)):
        b = busiest(baseline_occupancy(segs, seed=42, anchors=aa, peak_target=pt, low_demand_peak=ldp, offpeak_floor=off))
        print(f"{label:15s} levels {ldp}/{pt} off {off}:", b.round(3).to_dict())
print("\n=== exact ucity at off 0.60 / 0.85 / 0.99 (default mix)")
b = busiest(baseline_occupancy(segs, seed=42, peak_target=0.99, low_demand_peak=0.85, offpeak_floor=0.60))
print(b.round(4).to_dict())
