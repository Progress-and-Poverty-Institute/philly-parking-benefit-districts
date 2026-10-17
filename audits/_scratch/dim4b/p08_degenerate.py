import pandas as pd, numpy as np
from pathlib import Path
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
c=pd.read_csv(W/"outputs/tables/cm_sweep_cells.csv")
AX=["elasticity","start_occupancy","block_dispersion","observation_noise"]
y8=c[c.year==8]
print("cells x rules at year 8:",len(y8))
deg=y8[(y8.welfare_change_min==y8.welfare_change_max)]
print("rule-cells whose welfare_change is identical across all 100 replications:",len(deg),"of",len(y8))
print(deg.groupby(["block_dispersion","observation_noise"]).size())
p=pd.read_csv(W/"outputs/tables/cm_sweep_paired.csv"); p8=p[p.year==8]
print("paired: cells with zero spread in welfare_diff:",(p8.welfare_diff_min==p8.welfare_diff_max).sum(),"of",len(p8))
print("by tau,sigma, share of cells degenerate:\n",p8.assign(deg=(p8.welfare_diff_min==p8.welfare_diff_max)).groupby(["block_dispersion","observation_noise"]).deg.mean())
