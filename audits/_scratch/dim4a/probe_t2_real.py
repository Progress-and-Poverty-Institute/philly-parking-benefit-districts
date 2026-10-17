import geopandas as gpd, pandas as pd, numpy as np
from phillyparking._config import load_config
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
print("street_class counts:\n",seg.street_class.value_counts(dropna=False).sort_index().to_string())
print("zone_box counts:\n",seg.zone_box.value_counts().to_string())
cls=[2,3,4,5]; zones=[z["id"] for z in load_config("zones")["zones"]]
inbox=seg.zone_box.isin(zones)
print("\n== PR #10 threshold sensitivity (recomputed from stored commercial_frontage_share, street_class 2-5, in a box)")
for t in (0.1,0.25,0.5,0.75):
    m=inbox & seg.street_class.isin(cls) & (seg.commercial_frontage_share>=t)
    print(f"  min_commercial_share={t}: priced segments {int(m.sum())}, capacity {int(seg.loc[m,'capacity'].sum())}")
# also at 0.5 with strict > and a +-0.01 window
for t in (0.45,0.49,0.51,0.55):
    m=inbox & seg.street_class.isin(cls) & (seg.commercial_frontage_share>=t)
    print(f"  threshold {t}: segments {int(m.sum())}, capacity {int(seg.loc[m,'capacity'].sum())}")
p=seg[seg.priced_curb]
print("\n== priced curb at 0.5 by zone (stored zone_id)")
g=p.groupby("zone_id").agg(n=("segment_id","count"),cap=("capacity","sum"),length_km=("length_m",lambda x:x.sum()/1000),mean_share=("commercial_frontage_share","mean"))
g["share_of_segments"]=g.n/g.n.sum(); g["share_of_capacity"]=g.cap/g.cap.sum()
print(g.round(3).to_string())
print("total",len(p),int(p.capacity.sum()))
print("stored priced_curb == recomputed?", bool((seg.priced_curb==(inbox & seg.street_class.isin(cls) & (seg.commercial_frontage_share>=0.5))).all()))
print("zone_id != other iff priced:", bool(((seg.zone_id!="other")==seg.priced_curb).all()))
# candidate pool per box: street class 2-5 segments in box, and share >= .5
print("\n== per box: all segs, class 2-5 segs, priced, priced share of class 2-5")
b=seg[inbox].groupby("zone_box").apply(lambda d: pd.Series({"all":len(d),"cls2_5":int(d.street_class.isin(cls).sum()),"priced":int(d.priced_curb.sum()),"cap_all":int(d.capacity.sum()),"cap_priced":int(d.loc[d.priced_curb,'capacity'].sum())}))
b["priced/cls2_5"]=b.priced/b.cls2_5
print(b.round(3).to_string())
# priced by class
print("\npriced by class:\n",p.street_class.value_counts().sort_index().to_string())
# frontage share histogram among class 2-5 in box
h=seg[inbox & seg.street_class.isin(cls)].commercial_frontage_share
print("\nfrontage share histogram (class 2-5 in box):",np.histogram(h,bins=[0,0.001,0.1,0.25,0.5,0.75,0.9,1.0001])[0].tolist(),"bins [0,.001,.1,.25,.5,.75,.9,1]")
print("share exactly 0:",int((h==0).sum()),"exactly 1:",int((h==1).sum()),"within 0.01 of 0.5:",int(((h-0.5).abs()<0.01).sum()))
