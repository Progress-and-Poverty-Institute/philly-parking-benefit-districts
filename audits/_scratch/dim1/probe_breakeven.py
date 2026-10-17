import pandas as pd, numpy as np
p = pd.read_csv("outputs/tables/cm_sweep_paired.csv")
print(p.shape, p.year.unique())
last = p[p.year==p.year.max()]
print(last.groupby(["rule","reference"]).size())
for (r,ref),g in last.groupby(["rule","reference"]):
    be=g.breakeven_minutes_median
    print(r,ref,"n cells",len(g),"breakeven med/min/max",be.min(),be.median(),be.max(),
      "NaN",be.isna().sum(),"neg",(be<0).sum(),
      "comparator_searches_more share mean",g.share_comparator_searches_more.mean(),
      "cs+rev diff>0 cells",((g.cs_diff_median+g.revenue_diff_median)>0).sum(),
      "welfare_diff<0 (=comparator worse at 5min)",(g.welfare_diff_median<0).sum())
# the headline pair mean_zone vs peak_zone etc
g=last[(last.rule=="mean_zone")&(last.reference=="peak_zone")]
print("mean_zone vs peak_zone: cells where peak better at 5 min (welfare_diff<0):",(g.welfare_diff_median<0).sum(),"of",len(g))
g=last[(last.rule=="mean_band")&(last.reference=="peak_band")]
print("mean_band vs peak_band: peak better at 5 min:",(g.welfare_diff_median<0).sum(),"of",len(g))
both=pd.concat([last[(last.rule=="mean_zone")&(last.reference=="peak_zone")],last[(last.rule=="mean_band")&(last.reference=="peak_band")]])
print("both instruments peak better at 5:",(both.welfare_diff_median<0).sum(),"of",len(both))
print(both.breakeven_minutes_median.describe())
# are there cells with searches equal (NaN)?
print(last[last.breakeven_minutes_median.isna()][["elasticity","start_occupancy","block_dispersion","observation_noise","rule","reference"]].head(20))
# cells where cs+rev diff > 0 (comparator lower priced yet gain >=0 ) 
