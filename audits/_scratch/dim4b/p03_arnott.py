import numpy as np, pandas as pd
from phillyparking.scenarios.runner import _arnott_zone_prices
segs=pd.DataFrame({"segment_id":["a","b"],"zone_id":["ccc","ccc"],"capacity":[10.0,30.0]})
hrs=np.arange(168)
def mk(occ_a, occ_b):
    return pd.concat([pd.DataFrame({"segment_id":"a","hour_of_week":hrs,"occupancy":occ_a}),
                      pd.DataFrame({"segment_id":"b","hour_of_week":hrs,"occupancy":occ_b})],ignore_index=True)
oa=np.full(168,0.50); ob=np.full(168,0.50)
# busiest priced hour: Tuesday 13:00 (h=24+13=37): a=0.9, b=0.5 -> cap-weighted (9+15)/40=0.6
oa[37]=1.0; ob[37]=0.9
# a higher unweighted-mean-per-segment hour that is not busiest weighted: Wed 9:00 (h=57): a=1.0, b=0.45 -> (10+13.5)/40=0.5875
oa[57]=1.0; ob[57]=0.8
# unpriced Sunday hour with occupancy 1.0 (h=6*24+12=156): must be ignored
oa[156]=1.0; ob[156]=1.0
# priced-hour-boundary: hour 20 on Mon (h=20) is unpriced (window [8,20)); set high
oa[20]=1.0; ob[20]=1.0
# 7:00 Monday (h=7) unpriced; high
oa[7]=1.0; ob[7]=1.0
panel=mk(oa,ob)
cur=pd.DataFrame({"zone_id":["ccc"],"price_usd_per_hr":[4.0]})
e=-0.4; tv=0.15
r=_arnott_zone_prices(panel,segs,cur,tv,e,cur)
peak=0.925
hand=4.0+4.0*np.log((1-tv)/peak)/e
print("peak_occ reported",r.peak_occ.iloc[0],"expected 0.6; price",r.price_usd_per_hr.iloc[0],"hand",hand)
# current != posted
cur2=pd.DataFrame({"zone_id":["ccc"],"price_usd_per_hr":[3.0]})
r2=_arnott_zone_prices(panel,segs,cur2,tv,e,cur)  # reference = posted 4.0
hand2=3.0+4.0*np.log((1-tv)/peak)/e
print("current 3, posted 4:",r2.price_usd_per_hr.iloc[0],"hand",hand2)
# floor: peak very low -> price below floor 1.0 -> clipped; ceiling: peak 1.0 -> price above? (1-tv)/1.0 -> price falls..., use high elasticity to test ceiling with tiny peak
low=mk(np.full(168,0.05),np.full(168,0.05))
r3=_arnott_zone_prices(low,segs,cur,tv,e,cur); print("low-occupancy zone price (unclipped would be",4.0+4.0*np.log(0.85/0.05)/e,") -> ",r3.price_usd_per_hr.iloc[0],"(ccc ceiling 8.0)")
hi=mk(np.full(168,1.0),np.full(168,1.0))
r4=_arnott_zone_prices(hi,segs,cur,tv,e,cur); print("full zone price unclipped",4.0+4.0*np.log(0.85/1.0)/e,"->",r4.price_usd_per_hr.iloc[0])
hi2=mk(np.full(168,1.0),np.full(168,1.0))
r5=_arnott_zone_prices(hi2,segs,cur,tv,-0.05,cur); print("e=-0.05: unclipped",4.0+4.0*np.log(0.85)/-0.05,"->",r5.price_usd_per_hr.iloc[0],"(ceiling 8.0 binds)")
r6=_arnott_zone_prices(low,segs,cur,tv,-2.0,cur); print("e=-2, occ .05: unclipped",4.0+4.0*np.log(0.85/.05)/-2.0,"->",r6.price_usd_per_hr.iloc[0],"(floor 1.0 binds)")
# fixed point: after repricing, demand (via apply_elasticity) at peak -> 0.85?
from phillyparking.elasticity.scenarios import apply_elasticity
from phillyparking.pricing.priced_hours import hourly_prices
pn=panel.merge(segs[["segment_id","zone_id"]],on="segment_id"); pn["price_usd_per_hr"]=4.0
new=apply_elasticity(pn,hourly_prices(r),e,reference_price=cur)
zh=new.merge(segs[["segment_id","capacity"]],on="segment_id"); zh["oc"]=zh.occupancy*zh.capacity
agg=zh.groupby("hour_of_week").agg(oc=("oc","sum"),c=("capacity","sum")); agg["o"]=agg.oc/agg.c
print("after repricing, peak priced-hour zone occupancy:",agg.loc[37,"o"],"(target 0.85); hour57:",agg.loc[57,"o"])
