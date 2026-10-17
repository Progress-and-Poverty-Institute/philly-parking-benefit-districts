import pandas as pd, numpy as np
from phillyparking.scenarios.cm_sweep import paired_table
pd.set_option("display.width",220)
out={}
for nm in ("exp","const"):
    sw=pd.read_parquet(f"audits/_scratch/dim4b/outputs/sw_{nm}.parquet")
    p=paired_table(sw,comparisons=[("mean_zone","peak_zone"),("mean_band","peak_band"),("seattle_rule","peak_band"),("peak_band","peak_zone")])
    out[nm]=p[(p.year==3)&(p.rule.isin(["mean_zone","mean_band","seattle_rule"]))][["elasticity","start_occupancy","rule","reference","welfare_diff_median","breakeven_minutes_median","revenue_ratio_median"]].set_index(["elasticity","start_occupancy","rule","reference"])
j=out["exp"].join(out["const"],lsuffix="_exp",rsuffix="_const")
print("year 3, tau=0.3 sigma=0.1, 2 reps, same u/z draws; exponential vs constant_elasticity demand form")
print(j[["breakeven_minutes_median_exp","breakeven_minutes_median_const","welfare_diff_median_exp","welfare_diff_median_const"]].round(2).loc[(slice(None),slice(None),["mean_zone"],slice(None)),:].to_string())
d=(j.breakeven_minutes_median_exp-j.breakeven_minutes_median_const).abs()
print("\nmax |breakeven exp - const| over these cells (all comparisons):",d.max().round(3),"; median breakeven exp",j.breakeven_minutes_median_exp.median().round(2),"const",j.breakeven_minutes_median_const.median().round(2))
