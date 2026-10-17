import geopandas as gpd, numpy as np, pandas as pd
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
c=seg.geometry.centroid
seg["lon"]=c.x; seg["lat"]=c.y
def med(name,col,box=None):
    d=seg[seg.street_name.str.upper()==name]
    if box: d=d[(d.lon>-75.20)&(d.lon<-75.13)&(d.lat>39.93)&(d.lat<39.97)]
    return round(d[col].median(),4), len(d)
print("E-W streets, median latitude within -75.20..-75.13 lon:")
for n in ["VINE ST","RACE ST","ARCH ST","MARKET ST","WALNUT ST","LOCUST ST","SPRUCE ST","PINE ST","LOMBARD ST","SOUTH ST","SPRING GARDEN ST","CALLOWHILL ST","GIRARD AVE","CHESTNUT ST","SANSOM ST"]:
    print(" ",n,med(n,"lat",True))
print("N-S streets, median longitude within lat 39.94..39.96:")
for n in ["S 4TH ST","S 5TH ST","S 8TH ST","S 12TH ST","S 15TH ST","S BROAD ST","S 18TH ST","S 19TH ST","S 20TH ST","S 22ND ST","S 30TH ST","N 4TH ST","N 20TH ST","S 2ND ST"]:
    d=seg[(seg.street_name.str.upper()==n)&(seg.lat>39.94)&(seg.lat<39.965)]
    print(" ",n,round(d.lon.median(),4) if len(d) else None,len(d))
p=seg[seg.zone_id=="ccc"]
print("\nccc priced extents: lon",p.lon.min().round(4),p.lon.max().round(4),"lat",p.lat.min().round(4),p.lat.max().round(4))
print("ccc box: lon -75.170..-75.140 lat 39.945..39.960")
print("Priced ccc segments by street (top 15 by capacity):")
print(p.groupby("street_name").capacity.sum().sort_values(ascending=False).head(15).to_string())
