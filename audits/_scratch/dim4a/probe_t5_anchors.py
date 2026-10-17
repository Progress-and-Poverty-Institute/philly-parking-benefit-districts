import geopandas as gpd, numpy as np, pandas as pd, yaml, warnings, logging
from phillyparking._config import load_config
from phillyparking.demand.synthetic_baseline import baseline_occupancy, baseline_anchors, anchor_set_for_source, _kernels
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import priced_mask, zone_priced_hours
pd.set_option("display.width",200)
R="C:/projects/philly-parking-benefit-districts/data/processed"
seg=gpd.read_parquet(f"{R}/segments.parquet"); p=seg[seg.priced_curb]
cfg=load_config("demand_baseline"); cov=list(cfg["covariates"])
a=cfg["anchor_sets"]["philadelphia"]
print("== (D2) recompute anchors, independent of derive script (numpy, ddof=0, by hand)")
lg={c:np.log1p(p[c].astype(float).to_numpy()) for c in cov}
for c in cov:
    m,s=lg[c].mean(),lg[c].std(ddof=0)
    print(f"  {c}: mean {m:.4f} -> cfg center {a['centers'][c]} ; sd {s:.4f} -> cfg scale {a['scales'][c]} ; match={round(m,2)==a['centers'][c] and round(s,2)==a['scales'][c]}")
lam=sum(cfg["covariates"][c]["intensity_weight"]*(lg[c]-a["centers"][c])/a["scales"][c] for c in cov)
print("  lambda p5/p95 (using rounded cfg centers/scales):",round(np.percentile(lam,5),4),round(np.percentile(lam,95),4),"cfg",a["intensity_low"],a["intensity_high"])
print("  ddof=1 scales would be:",{c:round(float(lg[c].std(ddof=1)),3) for c in cov})
print("  n priced:",len(p),"; reference text:",a["reference"])
# rounding effect: shares at ends under rounded vs exact
print("  share lam<=low:",round((lam<=a['intensity_low']).mean(),4)," share lam>=high:",round((lam>=a['intensity_high']).mean(),4))
print("  lambda quantiles:",{q:round(float(np.percentile(lam,q)),2) for q in (0,1,5,25,50,75,95,99,100)})
# outlier influence: zero-pop segments pull sd(pop_density)
nz=p.pop_density>0
print("  pop_density: sd(log1p) all %.3f; excluding zeros %.3f; share zero %.3f; share <100/km2: %.3f"%(lg['pop_density'].std(ddof=0),np.log1p(p.pop_density[nz]).std(ddof=0),1-nz.mean(),(p.pop_density<100).mean()))
# lambda per zone
tmp=p.assign(lam=lam)
print("\n  lambda by zone (mean, share at cap, share at floor):")
print(tmp.groupby("zone_id").lam.agg(mean="mean",cap=lambda x:(x>=a['intensity_high']).mean(),floor=lambda x:(x<=a['intensity_low']).mean(),n="size").round(3).to_string())

print("\n== source -> anchor set")
segs=load_priced_segments(f"{R}/segments.parquet")
print("  kind from load_priced_segments:",segs.attrs['segment_source']['kind'],"-> set",anchor_set_for_source(segs))
bare=pd.DataFrame(segs).copy(); bare.attrs={}
try: baseline_occupancy(bare); print("  NO RAISE without attrs (!)")
except ValueError as e: print("  raises without segment_source attrs:",str(e)[:90],"...")
conc=pd.concat([segs.iloc[:10],segs.iloc[10:20]])
print("  attrs after pd.concat:",dict(conc.attrs) if conc.attrs else {} )
try: baseline_occupancy(conc); print("  concat: NO RAISE")
except ValueError as e: print("  concat raises too")
print("  kind mapping:",cfg["source_anchor_sets"])

print("\n== real demand_panel: priced-hour mean occupancy by zone (capacity-weighted) and cap/floor shares")
panel=pd.read_parquet(f"{R}/demand_panel.parquet")
m=panel.merge(segs[["segment_id","zone_id","capacity"]],on="segment_id",how="left")
assert m.zone_id.notna().all()
m["priced"]=priced_mask(m.zone_id,m.hour_of_week)
pm=m[m.priced]
def w(d): return np.average(d.occupancy,weights=d.capacity)
res=pm.groupby("zone_id").apply(lambda d: pd.Series({"priced_hr_mean_capw":w(d),"unweighted":d.occupancy.mean(),"min":d.occupancy.min(),"max":d.occupancy.max()}))
print(res.round(3).to_string())
# the busiest priced zone-hour (capacity weighted), the Arnott statistic
bz=pm.groupby(["zone_id","hour_of_week"]).apply(w).groupby("zone_id").max().round(3)
print("\n  busiest priced zone-hour (capacity-weighted):",bz.to_dict())
print("  cap of occupancy over entire panel: max",panel.occupancy.max().round(4),"min",panel.occupancy.min().round(4))
print("  calibration attr from fresh run:",baseline_occupancy(segs).attrs["calibration"])
# per-zone peak distribution: share of segments whose own weekly peak >=0.85 / 0.7
pk=m.groupby(["zone_id","segment_id"]).occupancy.max().reset_index()
print("\n  segment weekly peak share >=0.85 by zone:",pk.groupby('zone_id').occupancy.apply(lambda x:(x>=0.85).mean()).round(3).to_dict())
print("  segment weekly peak share <0.70 by zone:",pk.groupby('zone_id').occupancy.apply(lambda x:(x<0.70).mean()).round(3).to_dict())
print("  zone mean of segment peaks:",pk.groupby('zone_id').occupancy.mean().round(3).to_dict())
