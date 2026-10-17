import pandas as pd, numpy as np, hashlib
S="C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a"
R="C:/projects/philly-parking-benefit-districts/data/processed"
real=pd.read_parquet(f"{R}/demand_panel.parquet")
print("real panel",real.shape,list(real.columns), "key", open(f"{R}/demand_panel.key").read())
for run in("runA","runB"):
    p=pd.read_parquet(f"{S}/{run}/data/processed/demand_panel.parquet")
    print(run,p.shape,"columns equal",list(p.columns)==list(real.columns))
    for c in real.columns:
        a,b=real[c],p[c]
        if a.dtype.kind=="f":
            d=np.abs(a.to_numpy()-b.to_numpy()); print("  ",c,"max abs diff",d.max(),"exactly equal",bool((a.to_numpy()==b.to_numpy()).all()))
        else: print("  ",c,"equal",a.equals(b))
    print("  key equal:",open(f"{S}/{run}/data/processed/demand_panel.key").read()==open(f"{R}/demand_panel.key").read())
    print("  file sha256 equal:",hashlib.sha256(open(f"{S}/{run}/data/processed/demand_panel.parquet","rb").read()).hexdigest()==hashlib.sha256(open(f"{R}/demand_panel.parquet","rb").read()).hexdigest())
a=pd.read_parquet(f"{S}/runA/data/processed/demand_panel.parquet");b=pd.read_parquet(f"{S}/runB/data/processed/demand_panel.parquet")
print("runA == runB:",a.equals(b))
