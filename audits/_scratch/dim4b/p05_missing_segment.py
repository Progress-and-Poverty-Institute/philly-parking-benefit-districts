import numpy as np, pandas as pd
from phillyparking.revenue.forecast import annual_revenue
segs=pd.DataFrame({"segment_id":["a","b"],"zone_id":["ccc","ccc"],"capacity":[10.0,10.0]})
hrs=np.arange(168)
full=pd.concat([pd.DataFrame({"segment_id":s,"hour_of_week":hrs,"occupancy":o}) for s,o in (("a",0.5),("b",0.9))])
pr=pd.DataFrame({"zone_id":["ccc"],"price_usd_per_hr":[4.0]})
r_full=annual_revenue(segs,full,pr).annual_revenue_usd.sum()
r_miss=annual_revenue(segs,full[full.segment_id=="a"],pr).annual_revenue_usd.sum()
hand_full=52*4.0*sum(10*o*(12*5+12) for o in (0.5,0.9))   # priced hrs/wk = 12*5+12 = 72
print("full panel revenue",r_full,"hand",hand_full)
print("segment b has NO panel rows -> revenue",r_miss,"= b imputed the zone-mean occupancy of a (0.5): hand",52*4.0*20*0.5*72, "| true revenue if b contributes 0:",52*4.0*10*0.5*72)
