"""(b) Levels and anchors: what the stated occupancy levels / percentile anchors would have to be
for either rule to raise any zone, on the real 3,145 priced segments. (g) Stand-in subsets:
how the zone statistics move when the priced set is restricted to blocks more likely metered."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.demand.synthetic_baseline import baseline_occupancy, baseline_anchors, _latent_intensity

MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
seg_cols = segs[["segment_id", "zone_id", "capacity"]]
BANDS = [(8, 12), (12, 16), (16, 20)]

def zone_stats(panel, segsub=None):
    s = seg_cols if segsub is None else segsub[["segment_id", "zone_id", "capacity"]]
    p = panel.drop(columns=[c for c in ("zone_id", "capacity") if c in panel.columns]).merge(s, on="segment_id", how="inner")
    p = p.loc[frame_priced_mask(p)].copy()
    p["_oc"] = p.occupancy * p.capacity
    zh = p.groupby(["zone_id", "hour_of_week"]).agg(_oc=("_oc", "sum"), _c=("capacity", "sum")).reset_index()
    zh["occ"] = zh._oc / zh._c
    zh["hod"] = zh.hour_of_week % 24
    out = {}
    for z, g in zh.groupby("zone_id"):
        band = {f"b{a}-{b}": round(float(g.loc[(g.hod >= a) & (g.hod < b), "occ"].mean()), 3) for a, b in BANDS}
        out[z] = dict(busiest=round(float(g.occ.max()), 3), mean=round(float(np.average(g.occ)), 3),
                      arnott="RAISE" if g.occ.max() > 0.85 else "cut", **band,
                      seattle="".join("+" if v > 0.85 else ("-" if v < 0.70 else "0") for v in band.values()))
    return pd.DataFrame(out).T

print("=== 1. Level grid (philadelphia anchors; offpeak_floor 0.20). Columns: busiest priced zone-hour, priced-hour mean, Arnott direction, band means, Seattle directions (8-12,12-16,16-20)")
for ldp in (0.62, 0.70, 0.75, 0.80, 0.85, 0.90):
    for pt in (0.92, 0.99):
        if pt <= ldp: continue
        pan = baseline_occupancy(segs, seed=42, peak_target=pt, low_demand_peak=ldp)
        st = zone_stats(pan)
        print(f"\nlow_demand_peak={ldp} peak_target={pt}")
        print(st.to_string())

print("\n=== 2. Percentile anchors (levels 0.62/0.92): intensity bounds at other percentiles of the priced set's own lambda")
a = baseline_anchors("philadelphia")
lam = _latent_intensity(segs, a)
for lo_q, hi_q in ((1, 99), (5, 95), (10, 90), (25, 75), (40, 60)):
    aa = dict(a); aa["intensity_low"], aa["intensity_high"] = float(np.percentile(lam, lo_q)), float(np.percentile(lam, hi_q))
    pan = baseline_occupancy(segs, seed=42, anchors=aa)
    st = zone_stats(pan)
    print(f"\npercentiles {lo_q}/{hi_q}: bounds {aa['intensity_low']:.2f}/{aa['intensity_high']:.2f}; share at cap {(lam>=aa['intensity_high']).mean():.3f}")
    print(st[["busiest", "mean", "arnott", "seattle"]].to_string())

print("\n=== 3. (g) Stand-in subsets under the tracked panel: zone statistics if only these blocks were metered")
pan = pd.read_parquet(f"{MAIN}/data/processed/demand_panel.parquet")
subsets = {
    "all priced (tracked)": segs,
    "frontage share >= 0.75": segs[segs.commercial_frontage_share >= 0.75],
    "frontage share >= 0.9": segs[segs.commercial_frontage_share >= 0.9],
    "class 2-3 (arterials) only": segs[segs.street_class <= 3],
    "class 2-4 (no locals)": segs[segs.street_class <= 4],
    "class 5 (locals) only": segs[segs.street_class == 5],
    "top half of lambda within zone": pd.concat([g[g.index.isin(g.assign(l=lam[g.index]).sort_values('l', ascending=False).index[:len(g)//2])] for _, g in segs.groupby("zone_id")]),
    "capacity-weighted top half of lambda within zone": pd.concat([g.loc[(g.assign(l=lam[g.index]).sort_values('l', ascending=False).capacity.cumsum() <= g.capacity.sum()/2).reindex(g.index).fillna(False).astype(bool)] for _, g in segs.groupby("zone_id")]),
}
for name, sub in subsets.items():
    st = zone_stats(pan, sub)
    print(f"\n{name}: n={len(sub)} capacity={int(sub.capacity.sum())}")
    print(st[["busiest", "mean", "arnott", "seattle"]].to_string())
