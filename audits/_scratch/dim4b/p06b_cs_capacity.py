"""O3 scale: how much of the CS gain is surplus of latent demand that exceeds capacity (cannot be served)."""
import numpy as np, pandas as pd
from pathlib import Path
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
segall=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
rate={"ccc":4.0,"cca":3.5,"ucity":2.0,"south_philly":1.5,"fishtown":1.5}; wd_end={"ccc":20,"cca":20,"ucity":20,"south_philly":18,"fishtown":20}
named=segall[segall.zone_id.isin(rate)][["segment_id","zone_id","capacity"]]
b=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/demand_panel.parquet")[["segment_id","hour_of_week","occupancy"]].merge(named,on="segment_id")
b["hod"]=b.hour_of_week%24; b["d"]=b.hour_of_week//24
we=b.zone_id.map(wd_end); b=b[(b.d<6)&(b.hod>=8)&(b.hod<we)].copy()
b["pref"]=b.zone_id.map(rate)
for sc in ["seattle","full_pbd"]:
    pr=pd.read_parquet(SAVED/sc/"prices.parquet")
    if "band" in pr.columns:
        pr=pr.drop_duplicates(["zone_id","band"]); b["p"]=np.nan
        for _,r in pr.iterrows():
            m=(b.zone_id==r.zone_id)&(b.hod>=r.band_start)&(b.hod<r.band_end); b.loc[m,"p"]=r.price_usd_per_hr
    else:
        b["p"]=b.zone_id.map(pr.drop_duplicates("zone_id").set_index("zone_id").price_usd_per_hr)
    qref=(b.occupancy*b.capacity).values; cap=b.capacity.values; pref=b.pref.values; p=b.p.values; a=-0.4/pref
    full=-qref*(np.exp(a*(p-pref))-1)/a
    qref=np.where(qref>0,qref,1e-12); xs=pref+np.log(cap/qref)/a
    xs_c=np.clip(xs,p,pref)
    seg1=cap*(xs_c-p)                      # below xs, demand>cap: only cap cars can be served
    seg2=qref/a*(np.exp(a*(pref-pref))-np.exp(a*(xs_c-pref)))  # int_{xs_c}^{pref} q
    seg2=-seg2*(-1)
    cut=p<pref
    # int_{xs_c}^{pref} qref e^{a(x-pref)}dx = qref/a*(1-e^{a(xs_c-pref)}) ; a<0 and e^{..}>1 -> positive
    seg2=qref/a*(1-np.exp(a*(xs_c-pref)))
    feas=np.where(cut,seg1+seg2,full)
    print(sc,"full-law CS $%.2fM"%(full.sum()*52/1e6),"| CS if only capacity-feasible demand counts $%.2fM"%(feas.sum()*52/1e6),"| share of reported CS that is surplus of unservable demand: %.1f%%"%(100*(1-feas.sum()/full.sum())))
