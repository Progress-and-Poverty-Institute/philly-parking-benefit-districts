import numpy as np, pandas as pd
from pathlib import Path
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
sw=pd.read_parquet(W/"outputs/tables/cm_sweep.parquet")
y8=sw[sw.year==8].copy()
y8["p_revmax"]=2.0/y8.elasticity.abs()
y8["beyond_revmax"]=y8.mean_price>y8.p_revmax
print("mean_price at year 8 (start $2.00) by rule:\n",y8.groupby("rule").mean_price.describe()[["min","50%","max"]].round(2))
print("\nshare of rep-years (year 8) whose mean price exceeds the revenue-maximising price 2/|e| (exponential law anchored at $2):")
print(y8.groupby(["rule","elasticity"]).beyond_revmax.mean().unstack().round(3))
print("\nmax elasticity |e p/p0| faced at year-8 mean price, by rule & e:\n",(y8.assign(eff=y8.elasticity.abs()*y8.mean_price/2.0).groupby(["rule","elasticity"]).eff.max().unstack().round(2)))
