import geopandas as gpd, numpy as np, pandas as pd
pd.set_option("display.width",200)
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
cov=["jobs_within_200m","pois_count","pop_density","transit_trips_per_hr"]
p=seg[seg.priced_curb]
print("NaN counts in priced for all columns >0:\n",p.isna().sum()[lambda s:s>0].to_string())
print("NaN counts in ALL segments >0:\n",seg.isna().sum()[lambda s:s>0].to_string())
for c in cov:
    print(f"\n== {c}: priced by zone (n, zero share, min, p25, median, p75, max)")
    g=p.groupby("zone_id")[c].agg(n="size",zero=lambda x:(x==0).mean(),min="min",p25=lambda x:x.quantile(.25),med="median",p75=lambda x:x.quantile(.75),max="max")
    print(g.round(2).to_string())
    print("   all priced: zero share",round((p[c]==0).mean(),4),"; all segments zero share",round((seg[c]==0).mean(),4))
print("\nlog1p stats (priced): mean, sd, skew")
for c in cov:
    l=np.log1p(p[c]); print(f"  {c}: mean {l.mean():.3f} sd {l.std(ddof=0):.3f} skew {pd.Series(l).skew():.2f}")
print("\ncorrelation of log1p covariates (priced):\n",np.log1p(p[cov]).corr().round(2).to_string())
print("\nacs_coverage priced quantiles:",p.acs_coverage.quantile([0,.01,.05,.5]).round(3).to_dict(),"; segments with coverage<0.99:",int((p.acs_coverage<0.99).sum()))
print("pop_density priced quantiles (per km2):",p.pop_density.quantile([0,.05,.5,.95,1]).round(0).to_dict())
print("jobs priced quantiles:",p.jobs_within_200m.quantile([0,.05,.5,.95,1]).round(0).to_dict())
print("transit priced quantiles:",p.transit_trips_per_hr.quantile([0,.05,.5,.95,1]).round(1).to_dict(), "nearest_stop_distance_m median", p.nearest_stop_distance_m.median())
# total jobs sanity: sum over unique blocks cannot check; compare per-segment max to county total
print("\nneighborhood unmatched total:",int(seg.neighborhood.isna().sum()),"priced:",int(p.neighborhood.isna().sum()))
# hand cross-check segments
c=seg.geometry.centroid
seg["lon"]=c.x; seg["lat"]=c.y
def show(name,lonr,latr,n=3):
    d=seg[(seg.street_name.str.upper()==name)&seg.lon.between(*lonr)&seg.lat.between(*latr)]
    print(f"\n--- {name} ({len(d)} segs in window)")
    print(d.head(n)[["segment_id","street_name","street_class","zone_id","priced_curb","capacity","commercial_frontage_share","jobs_within_200m","pois_count","pop_density","transit_trips_per_hr","median_hh_income","acs_coverage","lon","lat"]].round(3).to_string())
show("WALNUT ST",(-75.170,-75.160),(39.949,39.951))
show("S 9TH ST",(-75.160,-75.155),(39.935,39.941))    # Italian Market-ish
show("S BROAD ST",(-75.166,-75.164),(39.915,39.925))   # south philly residential/stadium?
show("OREGON AVE",(-75.18,-75.14),(39.910,39.920))
show("MOLE ST",(-75.2,-75.1),(39.90,40.0))
print("\nTop 5 priced by jobs:\n",p.nlargest(5,'jobs_within_200m')[["street_name","zone_id","jobs_within_200m","pois_count","pop_density"]].to_string())
print("\nPriced in south_philly sample 6:\n",p[p.zone_id=='south_philly'].sample(6,random_state=1)[["street_name","street_class","capacity","commercial_frontage_share","jobs_within_200m","pois_count","pop_density","transit_trips_per_hr"]].round(2).to_string())
