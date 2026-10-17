import pandas as pd, numpy as np
from pathlib import Path
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
p=pd.read_csv(W/"outputs/tables/cm_sweep_paired.csv")
pz=p[(p.rule=="peak_band")&(p.reference=="peak_zone")&(p.year==8)]
print("cells",len(pz))
i=pz.breakeven_minutes_median.idxmin(); print(pz.loc[[i]].T.to_string())
print("\ndistribution of breakeven_minutes_median in peak_band vs peak_zone, year 8:\n",pz.breakeven_minutes_median.describe())
print("cells with |search_cost_diff_median|<1000 $/yr:", (pz.search_cost_diff_median.abs()<1000).sum(), " with exactly 0 diff all reps:", ((pz.search_cost_diff_min==0)&(pz.search_cost_diff_max==0)).sum())
print("cells with share_comparator_searches_more in (0,1) (sign of search diff mixed across reps):", ((pz.share_comparator_searches_more>0)&(pz.share_comparator_searches_more<1)).sum())
print("cells with breakeven_minutes_median<0:", (pz.breakeven_minutes_median<0).sum())
print(pz[pz.breakeven_minutes_median<0][["elasticity","start_occupancy","block_dispersion","observation_noise","welfare_diff_median","cs_diff_median","revenue_diff_median","search_cost_diff_median","breakeven_minutes_median","breakeven_minutes_min","breakeven_minutes_max","share_comparator_searches_more"]].to_string())
