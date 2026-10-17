import numpy as np, pandas as pd
from pathlib import Path
from phillyparking.scenarios.cm_sweep import load_sweep, ordering_violations
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
sw=load_sweep(W/"outputs/tables/cm_sweep.parquet")
pd.set_option("display.width",250); pd.set_option("display.max_columns",30)
for a,b in [("mean_zone","peak_zone"),("mean_band","peak_band")]:
    v=ordering_violations(sw,a,b)
    v["dwl_gap"]=v.cruising_dwl_cmp-v.cruising_dwl_ref; v["rev_gap"]=v.revenue_cmp-v.revenue_ref
    print(a,b,len(v)); print(v.round(3).to_string())
    print(" by elasticity/start/tau/sigma/year:\n", v.groupby(["elasticity","start_occupancy","block_dispersion","observation_noise","year"]).size())
# which of the two conditions
