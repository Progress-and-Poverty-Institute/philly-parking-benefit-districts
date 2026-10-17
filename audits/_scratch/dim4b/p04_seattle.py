import numpy as np, pandas as pd
from phillyparking.pricing.seattle_rule import adjust_zone_prices, zone_band_occupancy
bands=[[8,12],[12,16],[16,20]]
hrs=np.arange(168)
def panel(vals):   # vals: dict (segment)->(cap, occ array 168)
    rows=[]
    for s,(z,cap,o) in vals.items():
        rows.append(pd.DataFrame({"segment_id":s,"zone_id":z,"capacity":cap,"hour_of_week":hrs,"occupancy":o}))
    return pd.concat(rows,ignore_index=True)
def prof(a,b,c,off=0.99):
    o=np.full(168,off)       # unpriced hours deliberately 0.99 (must be ignored)
    for d in range(6):       # Mon..Sat priced hrs 8-20
        o[d*24+8:d*24+12]=a; o[d*24+12:d*24+16]=b; o[d*24+16:d*24+20]=c
    return o
# zone ccc: two segments, capacities 10 and 90; band stats designed per band
# band 8-12: both 0.70 exactly -> hold ; 12-16: 0.8501 -> up one step; 16-20: 0.95 -> two steps (up)
# capacity-weighting check: seg1 (cap 10) at 1.0, seg2 (cap 90) at 0.60 in band 12-16 -> weighted .64 (down), unweighted mean .80 (hold)
p=panel({"s1":("ccc",10,prof(0.70,1.0,0.95)),"s2":("ccc",90,prof(0.70,0.60,0.95)),
         "u1":("ucity",20,prof(0.6999,0.85,0.8501))})
cur=pd.DataFrame({"zone_id":["ccc","ucity"],"price_usd_per_hr":[4.0,2.0]})
st=zone_band_occupancy(p,bands); print(st.round(5).to_string(index=False))
out=adjust_zone_prices(p,cur,bands)
print(out[["zone_id","band","previous_price","price_usd_per_hr","band_occ","direction"]].round(4).to_string(index=False))
exp={("ccc","8-12"):4.0,("ccc","12-16"):3.5,("ccc","16-20"):5.0,("ucity","8-12"):1.5,("ucity","12-16"):2.0,("ucity","16-20"):2.5}
got={(r.zone_id,r.band):r.price_usd_per_hr for r in out.itertuples()}
print("expected vs got:",{k:(exp[k],got[k]) for k in exp}, "ALL MATCH" if all(abs(exp[k]-got[k])<1e-9 for k in exp) else "MISMATCH")
print("n_hours per band (ccc priced Mon-Sat 8-20, 4 hrs/band x 6 days = 24):", st[st.zone_id=="ccc"].n_hours.tolist())
