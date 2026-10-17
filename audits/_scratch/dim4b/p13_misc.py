import numpy as np, pandas as pd
from pathlib import Path
from phillyparking.scenarios.cm_sweep import load_sweep, ordering_violations
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
sw=load_sweep(W/"outputs/tables/cm_sweep.parquet")
for a,b in [("mean_zone","peak_zone"),("mean_band","peak_band")]:
    v=ordering_violations(sw,a,b); print(f"ordering_violations({a},{b}): {len(v)} violating rep-years of {len(sw[sw.rule==a])}")
# negative control: swap roles (should be many violations if the guard can fire)
v=ordering_violations(sw,"peak_zone","mean_zone"); print("negative control ordering_violations(peak_zone, mean_zone):",len(v),"violations (guard fires)")
# E4: arc elasticity from a log-log fit on exponential-law data across a rate change
for (p0,p1,e) in [(3.0,4.0,-0.4),(2.5,3.5,-0.4),(3.0,4.0,-0.7)]:
    pref=p1   # posted rate = new rate
    q=lambda p: np.exp(e*(p-pref)/pref)
    slope=(np.log(q(p1))-np.log(q(p0)))/(np.log(p1)-np.log(p0))
    print(f"E4 rate change {p0}->{p1}: truth e at posted {p1} = {e}; local elasticity at old price {e*p0/pref:.3f}; log-log slope returned {slope:.4f}  ({100*(abs(slope)/abs(e)-1):+.1f}% vs the prior-slot meaning)")
# A3: sequential (clipped each year) vs one-shot path
from phillyparking.elasticity.scenarios import apply_elasticity
from phillyparking.pricing.priced_hours import hourly_prices
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
base=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/demand_panel.parquet")
segs=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
named=segs[segs.zone_id.isin(["ccc","cca","ucity","south_philly","fishtown"])][["segment_id","zone_id","capacity"]]
cur=pd.DataFrame({"zone_id":["ccc","cca","ucity","south_philly","fishtown"],"price_usd_per_hr":[4.0,3.5,2.0,1.5,1.5]})
b=base.merge(named,on="segment_id").merge(cur,on="zone_id")
for sc in ["seattle","full_pbd"]:
    pr=pd.read_parquet(SAVED/sc/"prices.parquet"); 
    zp=pr[[c for c in pr.columns if c in("zone_id","band","band_start","band_end","price_usd_per_hr")]]
    one=apply_elasticity(b.drop(columns=["capacity"]),hourly_prices(zp),-0.4,reference_price=cur)
    seq=pd.read_parquet(SAVED/sc/"occupancy.parquet")[["segment_id","hour_of_week","occupancy"]]
    j=one.merge(seq,on=["segment_id","hour_of_week"],suffixes=("_one","_seq"))
    d=(j.occupancy_one-j.occupancy_seq)
    c=j.merge(named[["segment_id","capacity"]],on="segment_id")
    cap=c["capacity"]
    print(f"A3 {sc}: rows where one-shot != sequential: {(d.abs()>1e-9).sum()} of {len(d)}; max diff {d.abs().max():.4f}; one-shot - sequential cars (capacity-weighted, summed over week) {((c.occupancy_one-c.occupancy_seq)*cap).sum():.2f}; sign: one-shot higher in {(d>1e-9).sum()}, lower in {(d<-1e-9).sum()}")
