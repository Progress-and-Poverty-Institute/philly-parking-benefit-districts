"""Independent re-derivation of full_pbd zone prices from status_quo occupancy, plus Seattle fixed-point check."""
import numpy as np, pandas as pd, json
from pathlib import Path
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
segs=pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
rate={"ccc":4.0,"cca":3.5,"ucity":2.0,"south_philly":1.5,"fishtown":1.5}
floor={"ccc":1.0,"cca":1.0,"ucity":1.0,"south_philly":0.5,"fishtown":0.5}
ceil={"ccc":8.0,"cca":7.0,"ucity":6.0,"south_philly":4.0,"fishtown":4.0}
wd_end={"ccc":20,"cca":20,"ucity":20,"south_philly":18,"fishtown":20}
named=segs[segs.zone_id.isin(rate)][["segment_id","zone_id","capacity"]]
sq=pd.read_parquet(SAVED/"status_quo/occupancy.parquet")[["segment_id","hour_of_week","occupancy"]].merge(named,on="segment_id")
h=sq.hour_of_week.values; hh=h%24; d=h//24
sq["priced"]=[((dd<6)&(x>=8)&(x<wd_end[z])) for dd,x,z in zip(d,hh,sq.zone_id)]
e=-0.4; tv=0.15
price={z:rate[z] for z in rate}
occ=sq.occupancy.values.copy()
zone=sq.zone_id.values; cap=sq.capacity.values; pr=sq.priced.values
for yr in range(1,30):
    new={}
    for z in rate:
        m=(zone==z)&pr
        df=pd.DataFrame({"h":sq.hour_of_week.values[m],"oc":occ[m]*cap[m],"c":cap[m]})
        g=df.groupby("h").sum(); peak=(g.oc/g.c).max()
        p=price[z]+rate[z]*np.log((1-tv)/peak)/e
        new[z]=float(np.clip(p,floor[z],ceil[z]))
    delta=max(abs(new[z]-price[z]) for z in rate)
    if delta<=0.001: print("fixed point: no zone moves by >0.001 at review",yr,"(converged_year",yr-1,")"); break
    fac=np.array([np.exp(e*(new[z]-price[z])/rate[z]) for z in zone])
    occ=np.where(pr,np.clip(occ*fac,0,1),occ); price=new
print("hand prices:",{k:round(v,6) for k,v in price.items()})
fp=pd.read_parquet(SAVED/"full_pbd/prices.parquet").drop_duplicates("zone_id").set_index("zone_id").price_usd_per_hr
print("saved full_pbd:",fp.round(6).to_dict())
print("max abs diff hand vs saved", max(abs(fp[z]-price[z]) for z in rate))
meta=json.load(open(SAVED/"full_pbd/meta.json")); print("saved diagnostics years_run/conv_year", meta["diagnostics"]["years_run"], meta["diagnostics"]["converged_year"])
# at fixed point, zone peaks
for z in rate:
    m=(zone==z)&pr; df=pd.DataFrame({"h":sq.hour_of_week.values[m],"oc":occ[m]*cap[m],"c":cap[m]}).groupby("h").sum(); print(z,"peak priced-hour occ at fixed point",round((df.oc/df.c).max(),4),"price",round(price[z],4),"floor",floor[z])
# Seattle fixed point check from saved seattle panel
se=pd.read_parquet(SAVED/"seattle/occupancy.parquet")[["segment_id","hour_of_week","occupancy"]].merge(named,on="segment_id")
sp=pd.read_parquet(SAVED/"seattle/prices.parquet").drop_duplicates(["zone_id","band"])
print(sp[["zone_id","band","price_usd_per_hr"]].sort_values(["zone_id","band"]).to_string(index=False))
bands=[(8,12),(12,16),(16,20)]
se["d"]=se.hour_of_week//24; se["hod"]=se.hour_of_week%24
se["priced"]=[((dd<6)&(x>=8)&(x<wd_end[z])) for dd,x,z in zip(se.d,se.hod,se.zone_id)]
p=se[se.priced]; p=p.assign(oc=p.occupancy*p.capacity)
zh=p.groupby(["zone_id","hour_of_week"]).agg(oc=("oc","sum"),c=("capacity","sum")).reset_index(); zh["o"]=zh.oc/zh.c; zh["hod"]=zh.hour_of_week%24
bad=0
for z in rate:
    for a,b in bands:
        s=zh[(zh.zone_id==z)&(zh.hod>=a)&(zh.hod<b)]
        if s.empty: continue
        stat=s.o.mean(); cur=float(sp[(sp.zone_id==z)&(sp.band==f"{a}-{b}")].price_usd_per_hr.iloc[0])
        step = 2*0.5 if stat>=0.95 else 0.5 if stat>0.85 else -0.5 if stat<0.70 else 0.0
        nxt=float(np.clip(cur+step,floor[z],ceil[z])); moves=abs(nxt-cur)>1e-9
        bad+=moves
        print(f"{z:13s} {a:2d}-{b:2d} stat={stat:.4f} price={cur:.2f} next={nxt:.2f} {'MOVES' if moves else 'holds'}  {'(at floor)' if abs(cur-floor[z])<1e-9 else ''}")
print("bands that would still move:",bad)
