import geopandas as gpd, numpy as np, pandas as pd
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
p=seg[seg.priced_curb]
# 1. arithmetic: capacity == floor(length/7*0.85)
exp=np.floor(seg.length_m/7.0*0.85).astype(int).clip(lower=0)
print("capacity == floor(length_m/7*0.85) for all rows:",bool((exp==seg.capacity).all()),"; n mismatches",int((exp!=seg.capacity).sum()))
# length_m vs geometry length in UTM
L=seg.to_crs(32618).geometry.length
print("length_m vs UTM geometry length max abs diff:",float((L-seg.length_m).abs().max()))
print("\nlength_m (priced) quantiles:\n",p.length_m.describe(percentiles=[.01,.05,.25,.5,.75,.95,.99]).round(2).to_string())
print("\ncapacity (priced) distribution:\n",p.capacity.value_counts().sort_index().to_string())
print("zero capacity among priced:",int((p.capacity==0).sum()),"NaN:",int(p.capacity.isna().sum()), "NaN length", int(p.length_m.isna().sum()))
print("zero capacity among ALL:",int((seg.capacity==0).sum()))
# floor loss: mean(exact) vs mean(floor)
ex=p.length_m/7.0*0.85
print(f"\npriced capacity: sum floor {int(p.capacity.sum())}, sum exact {ex.sum():.0f}, floor loses {ex.sum()-p.capacity.sum():.0f} ({(ex.sum()-p.capacity.sum())/ex.sum():.1%})")
print("segments with length <8.24 m (floor to 0):",int((seg.length_m<7/0.85).sum()))
# splitting: target 80, pieces
print("piece length quantiles all:",seg.length_m.quantile([.01,.05,.5,.95,.99]).round(1).to_dict())
# 2. one-way vs two-way: any direction attr? 
print("\ncolumns:",list(seg.columns))
# duplicates: same geometry stored twice?
g=seg.geometry.to_wkb()
print("duplicate geometries (WKB) among all:",int(g.duplicated().sum()),"; among priced:",int(g[seg.priced_curb].duplicated().sum()))
# reversed-twin check: same endpoints set
def key(geom):
    c=list(geom.coords); a,b=c[0],c[-1]; return tuple(sorted([(round(a[0],6),round(a[1],6)),(round(b[0],6),round(b[1],6))]))
k=p.geometry.map(key)
print("priced segments sharing both endpoints with another priced segment:",int(k.duplicated(keep=False).sum()))
# By street class: capacity per km of priced
print("\nspaces per km priced by class:",(p.groupby('street_class').capacity.sum()/(p.groupby('street_class').length_m.sum()/1000)).round(1).to_dict())
print("implied total curb length priced km:",round(p.length_m.sum()/1000,1),"; spaces/km overall",round(p.capacity.sum()/(p.length_m.sum()/1000),1),"(one curb: 1000/7*0.85 = 121.4)")
