import numpy as np, pandas as pd
import phillyparking.demand.synthetic_baseline as sb
from phillyparking.demand.synthetic_baseline import baseline_occupancy, panel_cache_key
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.scenarios.runner import check_panel
R="C:/projects/philly-parking-benefit-districts/data/processed"
segs=load_priced_segments(f"{R}/segments.parquet")
full=baseline_occupancy(segs).set_index(["segment_id","hour_of_week"]).occupancy
sub=segs.sample(25,random_state=5)
alone=baseline_occupancy(sub).set_index(["segment_id","hour_of_week"]).occupancy
print("24: 25-segment subset vs same segments inside full set: max abs diff",float((alone-full.reindex(alone.index)).abs().max()))
one=baseline_occupancy(segs.iloc[:1]); print("24: a single segment alone peak",round(one.occupancy.max(),4),"in full set",round(full.loc[segs.segment_id.iloc[0]].max(),4))
# extreme covariate in one segment: do others move?
s2=segs.copy(); s2.loc[s2.index[0],"jobs_within_200m"]=1e9
p2=baseline_occupancy(s2).set_index(["segment_id","hour_of_week"]).occupancy
d=(p2-full).abs().groupby(level=0).max(); print("24: after setting one segment's jobs to 1e9, segments whose panel changed:",int((d>0).sum()),"(only itself expected)")
# 17: NaN guard
s3=segs.copy(); s3.loc[s3.index[3],"pop_density"]=np.nan
try: baseline_occupancy(s3); print("17: NaN covariate NOT caught")
except ValueError as e: print("17: NaN covariate raises:",str(e))
bad=full.reset_index(); bad.loc[5,"occupancy"]=np.nan
try: check_panel(bad,"p"); print("17: check_panel passes NaN (!)")
except Exception as e: print("17: check_panel raises:",type(e).__name__,str(e)[:80])
# cache key: sensitive to covariate, to seed, to anchors; insensitive to kernel code
k0=panel_cache_key(segs,42)
s4=segs.copy(); s4.loc[s4.index[7],"pois_count"]+=1
print("key changes with a covariate:",panel_cache_key(s4,42)!=k0,"| with seed:",panel_cache_key(segs,43)!=k0,"| with zone_id relabel:",panel_cache_key(segs.assign(zone_id="ccc"),42)==k0,"(unchanged = panel does not depend on it)")
orig=sb._office_kernel
sb._office_kernel=lambda: np.ones(168)*0.3
print("key changes when the OFFICE KERNEL (code) is replaced:",panel_cache_key(segs,42)!=k0,"| panel changes:",not np.allclose(baseline_occupancy(segs).occupancy.values,full.values))
sb._office_kernel=orig
# retail/pois columns sanity
import geopandas as gpd
seg=gpd.read_parquet(f"{R}/segments.parquet")
print("19: pois_retail>0 share (priced):",round((seg[seg.priced_curb].pois_retail>0).mean(),3),"; pois_restaurant>0:",round((seg[seg.priced_curb].pois_restaurant>0).mean(),3),"; pois_office>0:",round((seg[seg.priced_curb].pois_office>0).mean(),3))
print("19: jobs_within_200m distinct values (all):",seg.jobs_within_200m.nunique(),"std",round(seg.jobs_within_200m.std(),1))
print("19: neighborhood column present, NaN in priced:",int(seg[seg.priced_curb].neighborhood.isna().sum()))
