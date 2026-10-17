"""Finding 3 re-verification: sensitivity of the full-PBD one-step price and fixed point to the peak statistic (real segments, central e)."""
import numpy as np, pandas as pd
from pathlib import Path
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
segs=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
rate={"ccc":4.0,"cca":3.5,"ucity":2.0,"south_philly":1.5,"fishtown":1.5}
floor={"ccc":1.0,"cca":1.0,"ucity":1.0,"south_philly":0.5,"fishtown":0.5}; ceil={"ccc":8.0,"cca":7.0,"ucity":6.0,"south_philly":4.0,"fishtown":4.0}
wd_end={"ccc":20,"cca":20,"ucity":20,"south_philly":18,"fishtown":20}
named=segs[segs.zone_id.isin(rate)][["segment_id","zone_id","capacity"]]
sq=pd.read_parquet(SAVED/"status_quo/occupancy.parquet")[["segment_id","hour_of_week","occupancy"]].merge(named,on="segment_id")
sq["d"]=sq.hour_of_week//24; sq["hod"]=sq.hour_of_week%24
sq=sq[(sq.d<6)&(sq.hod>=8)&(sq.hod<sq.zone_id.map(wd_end))]
sq["oc"]=sq.occupancy*sq.capacity
zh=sq.groupby(["zone_id","hour_of_week"]).agg(oc=("oc","sum"),c=("capacity","sum")).reset_index(); zh["o"]=zh.oc/zh.c
e=-0.4; tv=0.15
stats={"max (coded)":lambda x:x.max(),"q95":lambda x:x.quantile(.95),"q90":lambda x:x.quantile(.90),"q75":lambda x:x.quantile(.75),"mean":lambda x:x.mean()}
rows=[]
for nm,f in stats.items():
    for z in rate:
        s=f(zh[zh.zone_id==z].o); p=float(np.clip(rate[z]+rate[z]*np.log((1-tv)/s)/e,floor[z],ceil[z]))
        rows.append((nm,z,round(s,3),round(rate[z]+rate[z]*np.log((1-tv)/s)/e,3),round(p,3),"FLOOR" if abs(p-floor[z])<1e-9 else ("CEIL" if abs(p-ceil[z])<1e-9 else "")))
t=pd.DataFrame(rows,columns=["statistic","zone","stat_value","unclipped_price","clipped_price","bound"])
print(t.pivot(index="zone",columns="statistic",values="clipped_price").to_string())
print("\nunclipped one-step price (what the statistic alone says):")
print(t.pivot(index="zone",columns="statistic",values="unclipped_price").to_string())
print("\nzones at a floor, by statistic:",t[t.bound=="FLOOR"].groupby("statistic").size().to_dict())
