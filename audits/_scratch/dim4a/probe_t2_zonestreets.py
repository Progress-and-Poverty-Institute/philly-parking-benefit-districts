import geopandas as gpd, pandas as pd, numpy as np
R="C:/projects/philly-parking-benefit-districts/data/processed"
seg=gpd.read_parquet(f"{R}/segments.parquet")
p=seg[seg.priced_curb]
for z in ["ucity","south_philly","fishtown"]:
    d=p[p.zone_id==z]
    print(f"\n== {z}: {len(d)} priced segs, {int(d.capacity.sum())} spaces; top streets by capacity")
    print(d.groupby("street_name").capacity.agg(["sum","count"]).sort_values("sum",ascending=False).head(10).to_string())
# class 2-5 segments in box, candidate pool vs priced, by zone: share of boxes' street length
box=seg[seg.zone_box.isin(["ucity","south_philly","fishtown","cca","ccc"])]
print("\npriced share of in-box class-2-5 length (km) by zone:")
t=box[box.street_class.isin([2,3,4,5])].groupby("zone_box").length_m.sum()/1000
q=p.groupby("zone_id").length_m.sum()/1000
print(pd.DataFrame({"all_km":t,"priced_km":q,"share":q/t}).round(3).to_string())
# Penn campus streets: Walnut 34th-40th
c=seg.geometry.centroid; seg["lon"]=c.x; seg["lat"]=c.y
w=seg[(seg.street_name.str.upper()=="WALNUT ST")&seg.lon.between(-75.205,-75.18)]
print("\nWALNUT ST in ucity longitudes:",len(w),"priced:",int(w.priced_curb.sum()),"; frontage share quantiles",w.commercial_frontage_share.quantile([0,.5,1]).round(2).tolist())
