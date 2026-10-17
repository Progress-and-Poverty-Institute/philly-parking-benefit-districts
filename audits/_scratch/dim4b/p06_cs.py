import numpy as np, pandas as pd, json
from pathlib import Path
from scipy.integrate import quad
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
# --- two-segment hand test of runner._annual_cs_change
from phillyparking.scenarios.runner import _annual_cs_change
segs=pd.DataFrame({"segment_id":["a","b"],"zone_id":["ccc","ucity"],"capacity":[10.0,20.0]})
hrs=[10,40]  # Mon 10:00 and Tue 16:00 -> priced in both zones
panel=pd.DataFrame([(s,h,o) for s,o in (("a",0.6),("b",0.9)) for h in hrs],columns=["segment_id","hour_of_week","occupancy"])
bp=pd.DataFrame({"zone_id":["ccc","ucity"],"price_usd_per_hr":[4.0,2.0]})
sp=pd.DataFrame({"zone_id":["ccc","ucity"],"price_usd_per_hr":[3.0,2.5]})
got=_annual_cs_change(segs,panel,bp,sp,-0.4)
hand=0
for s,z,cap,o in (("a","ccc",10,0.6),("b","ucity",20,0.9)):
    pref={"ccc":4.0,"ucity":2.0}[z]; p={"ccc":3.0,"ucity":2.5}[z]
    q=o*cap
    integ=quad(lambda x: q*np.exp(-0.4*(x-pref)/pref), pref, p)[0]   # integral of demand from pref to p
    hand+= -integ*len(hrs)*52
print("_annual_cs_change:",got,"hand quad (x2 hours x52 weeks):",hand,"diff",got-hand)
# --- seattle recompute
segall=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
rate={"ccc":4.0,"cca":3.5,"ucity":2.0,"south_philly":1.5,"fishtown":1.5}
wd_end={"ccc":20,"cca":20,"ucity":20,"south_philly":18,"fishtown":20}
named=segall[segall.zone_id.isin(rate)][["segment_id","zone_id","capacity"]]
base=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/demand_panel.parquet")[["segment_id","hour_of_week","occupancy"]].merge(named,on="segment_id")
sq=pd.read_parquet(SAVED/"status_quo/occupancy.parquet")[["segment_id","hour_of_week","occupancy"]]
print("baseline demand_panel == status_quo occupancy panel:", np.allclose(base.sort_values(['segment_id','hour_of_week']).occupancy.values, sq.sort_values(['segment_id','hour_of_week']).occupancy.values))
base["d"]=base.hour_of_week//24; base["hod"]=base.hour_of_week%24
base["priced"]=[((dd<6)&(x>=8)&(x<wd_end[z])) for dd,x,z in zip(base.d,base.hod,base.zone_id)]
b=base[base.priced].copy()
tot={}
for sc in ["seattle","full_pbd"]:
    pr=pd.read_parquet(SAVED/sc/"prices.parquet")
    if "band" in pr.columns:
        pr=pr.drop_duplicates(["zone_id","band"])
        def pz(z,hod):
            r=pr[(pr.zone_id==z)&(pr.band_start<=hod)&(pr.band_end>hod)]; return float(r.price_usd_per_hr.iloc[0])
        b["p"]=[pz(z,h) for z,h in zip(b.zone_id,b.hod)]
    else:
        zp=pr.drop_duplicates("zone_id").set_index("zone_id").price_usd_per_hr; b["p"]=b.zone_id.map(zp)
    b["pref"]=b.zone_id.map(rate); a=-0.4/b.pref
    q=b.occupancy*b.capacity
    b["cs"]=-q*(np.exp(a*(b.p-b.pref))-1)/a*52
    meta=json.load(open(SAVED/sc/"meta.json"))
    print(sc,"CS recomputed",round(b.cs.sum(),2),"saved cs_change_total",round(meta["cs_change_total"],2),"diff",b.cs.sum()-meta["cs_change_total"])
    # per-zone split of CS gain and revenue change
    occ=pd.read_parquet(SAVED/sc/"occupancy.parquet")[["segment_id","hour_of_week","occupancy","price_usd_per_hr"]].merge(named,on="segment_id")
    occ["d"]=occ.hour_of_week//24; occ["hod"]=occ.hour_of_week%24
    occ["priced"]=[((dd<6)&(x>=8)&(x<wd_end[z])) for dd,x,z in zip(occ.d,occ.hod,occ.zone_id)]
    o=occ[occ.priced]; revs=(o.occupancy*o.capacity*o.price_usd_per_hr*52).groupby(o.zone_id).sum()
    sqo=base[base.priced]; rev0=(sqo.occupancy*sqo.capacity*sqo.zone_id.map(rate)*52).groupby(sqo.zone_id).sum()
    cs=b.groupby("zone_id").cs.sum()
    t=pd.DataFrame({"rev_sq":rev0,"rev_scn":revs,"d_rev":revs-rev0,"cs_gain":cs,"cs_gain_per_$_rev_lost":cs/(rev0-revs)})
    print(t.round(0).to_string()); print("totals: d_rev",round((revs-rev0).sum()),"cs",round(cs.sum()),"cs+d_rev (net of transfer, ignoring search/cruising)",round(cs.sum()+(revs-rev0).sum()))
    # induced demand beyond capacity: share of CS from cars that would exceed capacity? latent demand at new price
    occn=o.copy(); occn["pref"]=occn.zone_id.map(rate)
    # latent demand = baseline occupancy * factor (unclipped)
    bb=b.merge(o[["segment_id","hour_of_week","occupancy"]].rename(columns={"occupancy":"occ_scn"}),on=["segment_id","hour_of_week"])
    bb["lat"]=bb.occupancy*np.exp(-0.4*(bb.p-bb.pref)/bb.pref)
    print("   priced block-hours with latent demand > 1 (clipped in panel):",int((bb.lat>1).sum()),"of",len(bb)," excess cars-hours/yr", round(float(((bb.lat-1).clip(lower=0)*bb.capacity).sum()*52)))

print("\n=== CS restricted to capacity-feasible demand (min(q(x),cap) integrated), for scale of the O3 question")
for sc in ["seattle","full_pbd"]:
    pr=pd.read_parquet(SAVED/sc/"prices.parquet")
    if "band" in pr.columns:
        pr=pr.drop_duplicates(["zone_id","band"])
        b["p"]=[float(pr[(pr.zone_id==z)&(pr.band_start<=h)&(pr.band_end>h)].price_usd_per_hr.iloc[0]) for z,h in zip(b.zone_id,b.hod)]
    else:
        b["p"]=b.zone_id.map(pr.drop_duplicates("zone_id").set_index("zone_id").price_usd_per_hr)
    qref=(b.occupancy*b.capacity).values; cap=b.capacity.values; pref=b.pref.values; p=b.p.values; a=-0.4/pref
    full=-qref*(np.exp(a*(p-pref))-1)/a
    # price cut (p<pref): gain = int_p^pref min(q(x),cap) dx. x* where q=cap
    xs=pref+np.log(cap/qref)/a
    lo=p; hi=pref
    xs_c=np.clip(xs,lo,hi)  # for x<xs_c demand>cap -> contributes cap; for x>xs_c -> q
    gain_cap=cap*(xs_c-lo) + qref*(np.exp(a*(hi-pref))-np.exp(a*(xs_c-pref)))/(-a)*(-1)  # int_xs^pref q = qref*(1-exp(a(xs-pref)))/(-a)... compute explicitly below
    seg2=qref*(np.exp(a*(xs_c-pref))-np.exp(a*(hi-pref)))/(-a)   # int_{xs_c}^{hi} qref e^{a(x-pref)} dx = qref/a*(e^{a(hi-pref)}-e^{a(xs_c-pref)}); a<0 so ...
    seg2=qref/a*(np.exp(a*(hi-pref))-np.exp(a*(xs_c-pref)))
    seg1=cap*(xs_c-lo)
    cut=p<pref
    feas=np.where(cut,seg1+seg2,full)  # raises: demand below q_ref<=cap, no rationing
    print(sc,"full-law CS $%.1fM"%(full.sum()*52/1e6),"| capacity-feasible CS $%.1fM"%(feas.sum()*52/1e6),"| share beyond capacity %.1f%%"%(100*(1-feas.sum()/full.sum())))
