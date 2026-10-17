import pandas as pd, numpy as np, time
from pathlib import Path
from phillyparking.scenarios.cm_sweep import chatman_manville_sweep, save_sweep, load_sweep
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47"); S=W/"audits/_scratch/dim4b"
t=time.time()
sw = chatman_manville_sweep(n_replications=3, rolls_forward_years=3)
print("elapsed", time.time()-t, sw.shape)
save_sweep(sw, S/"outputs/tables_small/cm_sweep_small.parquet")
tr = load_sweep(W/"outputs/tables/cm_sweep.parquet")
print("tracked shape", tr.shape, "years", sorted(tr.year.unique()), "reps", tr.replication.nunique())
keys=["elasticity","start_occupancy","block_dispersion","observation_noise","rule","replication","year"]
sub = tr[(tr.replication<3)&(tr.year<=3)]
j = sw.merge(sub, on=keys, suffixes=("_new","_trk"), validate="one_to_one")
print("matched rows", len(j), "of", len(sw), "new and", len(sub), "tracked subset")
from phillyparking.scenarios.cm_sweep import SWEEP_METRICS
for m in SWEEP_METRICS:
    d=(j[m+"_new"]-j[m+"_trk"]).abs()
    print(f"{m:35s} max abs diff {d.max():.3e}  max rel {(d/ j[m+'_trk'].abs().clip(lower=1e-12)).max():.3e}")
