import geopandas as gpd, numpy as np, pandas as pd
from shapely.geometry import box, LineString
from phillyparking.io import census, lodes, osm_loader, gtfs_loader, opendataphilly
from phillyparking.spatial.join import join_acs, join_lodes
from phillyparking.spatial.segments import build_segments
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
X0,Y0=486_000.0,4_422_000.0
# ---------- ACS hand-built: pop_density and renormalisation
s=gpd.GeoDataFrame({"segment_id":["a","b"]},geometry=[LineString([(X0,Y0),(X0+100,Y0)]),LineString([(X0,Y0+1000),(X0+100,Y0+1000)])],crs=32618).to_crs(4326)
# segment a: buffer 15 m => y in [Y0-15,Y0+15]. BG1 covers y<Y0-5 (25% of 30 m) , BG2 covers y>=Y0-5 (75%)
bg=gpd.GeoDataFrame({"total_pop":[1000.0,4000.0,50.0],"ALAND":[1e6,2e6,1e6],"median_hh_income":[50000.,100000.,70000.],
   "tenure_renter":[10.,30.,5.],"tenure_owner":[10.,10.,5.],"race_white":[500.,2000.,25.],"aggregate_vehicles":[100.,200.,10.],"households":[50.,100.,10.]},
   geometry=[box(X0-500,Y0-500,X0+500,Y0-5),box(X0-500,Y0-5,X0+500,Y0+500),
             box(X0-500,Y0+600,X0+500,Y0+1000)],crs=32618).to_crs(4326)  # BG3 covers only HALF of b's buffer (y<=Y0+1000)
out=join_acs(s,bg,uncovered="nan").set_index("segment_id")
print("segment a: expect pop_density 0.25*1000+0.75*2000 = 1750 (per km2 of land); got",round(out.loc['a','pop_density'],3),"acs_coverage",round(out.loc['a','acs_coverage'],4))
print("segment a: income expect 0.25*50000+0.75*100000=87500; got",round(out.loc['a','median_hh_income'],1))
print("segment a: pct_renter expect .25*.5+.75*.75=.6875; got",round(out.loc['a','pct_renter'],4), " vehicles_per_hh expect .25*2+.75*2=2.0; got",round(out.loc['a','vehicles_per_hh'],4))
print("segment b: buffer half inside BG3 only: pop_density expect 50/1e6*1e6=50 (renormalised); got",round(out.loc['b','pop_density'],3),"acs_coverage expect .5; got",round(out.loc['b','acs_coverage'],4))
# pct_white of a: weight .25*(500/1000)+.75*(2000/4000)=0.5
print("segment a: pct_white expect 0.5; got",round(out.loc['a','pct_white'],4))
# ---------- ACS layer in the cache: ALAND vs polygon area
acs=census.fetch_acs_block_groups()
ac=acs.to_crs(32618); r=ac.ALAND.astype(float)/ac.geometry.area
print("\nreal ACS layer: n BG",len(acs),"cols",[c for c in acs.columns if c!='geometry'])
print(" ALAND/polygon area ratio quantiles:",r.quantile([0,.05,.5,.95,1]).round(3).to_dict()," BG with total_pop==0:",int((acs.total_pop==0).sum()),"NaN pop",int(acs.total_pop.isna().sum()))
print(" negative/sentinel income values:",int((acs.median_hh_income<0).sum()),"NaN income",int(acs.median_hh_income.isna().sum()))
print(" Philadelphia total pop (ACS 2022 BG sum):",int(acs.total_pop.sum()))
# ---------- recon: which segments were dropped by join_acs, and where
streets=opendataphilly.fetch_streets(); rpp=opendataphilly.fetch_rpp_zones(); nb=opendataphilly.fetch_neighborhoods()
built=build_segments(streets=streets,rpp_zones=rpp,neighborhoods=nb)
dropped=built[~built.segment_id.isin(seg.segment_id)]
print("\nbuilt",len(built),"final",len(seg),"dropped",len(dropped))
print("dropped by zone_box (pre-priced):",dropped.zone_id.value_counts().to_dict(),"; classes:",dropped.street_class.value_counts().to_dict())
print("dropped capacity:",int(dropped.capacity.sum()),"; bbox of dropped lon/lat:",[round(v,3) for v in dropped.total_bounds])
print("total Philadelphia centerline extent lon/lat:",[round(v,3) for v in built.total_bounds])
# ---------- independent recomputation of jobs / pois / transit for 40 random priced segments
rng=np.random.default_rng(0)
pp=seg[seg.priced_curb].sample(40,random_state=3)
wac=lodes.fetch_wac(); blocks=lodes.fetch_block_points(); pois=osm_loader.load_pois(); stops=gtfs_loader.load_stop_frequency()
bm=blocks.to_crs(32618); wac_j=wac.set_index(wac["w_geocode"].astype(str))["C000"]
bm["jobs"]=bm["tabblk2020"].astype(str).map(wac_j).fillna(0)
pm=pois.to_crs(32618); pm["geometry"]=pm.geometry.representative_point()
sm=stops.to_crs(32618)
bad=[0,0,0]; maxd=[0,0,0]
for _,r0 in pp.iterrows():
    g=gpd.GeoSeries([r0.geometry],crs=4326).to_crs(32618).iloc[0]
    j=bm.loc[bm.geometry.distance(g)<=200,"jobs"].sum()
    po=int((pm.geometry.distance(g)<=100).sum())
    tr=sm.loc[sm.geometry.distance(g)<=400,"trips_per_hour"].sum()
    for i,(a,b) in enumerate([(j,r0.jobs_within_200m),(po,r0.pois_count),(tr,r0.transit_trips_per_hr)]):
        maxd[i]=max(maxd[i],abs(a-b)); bad[i]+= abs(a-b)>1e-6*max(1,abs(b))
print("\nindependent distance-based recomputation, 40 priced segments: mismatches [jobs,pois,transit]=",bad,"max abs diff",maxd)
print("blocks with jobs: n blocks",len(bm),"sum jobs located",int(bm.jobs.sum()),"WAC total C000",int(wac.C000.sum()))
