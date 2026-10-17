import geopandas as gpd, pandas as pd
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.spatial.segments import load_priced_segments
seg=gpd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
c=seg.geometry.centroid; seg["lon"]=c.x; seg["lat"]=c.y
cols=["street_name","street_class","zone_box","priced_curb","capacity","commercial_frontage_share","jobs_within_200m","pois_count","pop_density","transit_trips_per_hr","median_hh_income","pct_renter","rpp_zone","neighborhood"]
r=seg[(seg.lat.between(39.925,39.930))&(seg.lon.between(-75.178,-75.170))&(seg.street_class==5)]
print("residential South Philly local blocks (lat 39.925-39.930, lon -75.178..-75.170):",len(r)); print(r.head(4)[cols].round(2).to_string())
w=seg[(seg.street_name=="WALNUT ST")&seg.lon.between(-75.170,-75.166)&(seg.priced_curb)]
print("\nWalnut St (ccc):"); print(w.head(2)[cols].round(2).to_string())
segs=load_priced_segments("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
pan=baseline_occupancy(segs).merge(segs[["segment_id","street_name","zone_id"]],on="segment_id")
pk=pan.groupby("segment_id").occupancy.max()
print("\nbaseline weekly peak: Walnut ccc blocks:",pk.reindex(w.segment_id).round(3).tolist()[:5])
sp=segs[segs.zone_id=="south_philly"]; print("south_philly priced blocks peak: median",round(pk.reindex(sp.segment_id).median(),3))
