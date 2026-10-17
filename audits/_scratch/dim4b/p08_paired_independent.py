import pandas as pd, numpy as np
from pathlib import Path
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
sw=pd.read_parquet(W/"outputs/tables/cm_sweep.parquet"); csv=pd.read_csv(W/"outputs/tables/cm_sweep_paired.csv")
AX=["elasticity","start_occupancy","block_dispersion","observation_noise"]; K=AX+["replication","year"]
print("sweep rows",len(sw),"=", sw.groupby('rule').size().to_dict())
# identity: welfare_change differences = cs + rev - search_cost differences
wide=sw.pivot_table(index=K,columns="rule",values=["welfare_change","cs_change","revenue","search_cost","search_cost_per_minute"],aggfunc="first")
worst=0
for a,b in [("mean_zone","peak_zone"),("mean_band","peak_band"),("seattle_rule","peak_band"),("peak_band","peak_zone")]:
    dw=wide["welfare_change"][a]-wide["welfare_change"][b]
    parts=(wide["cs_change"][a]-wide["cs_change"][b])+(wide["revenue"][a]-wide["revenue"][b])-(wide["search_cost"][a]-wide["search_cost"][b])
    worst=max(worst,(dw-parts).abs().max())
    scd=wide["search_cost_per_minute"][a]-wide["search_cost_per_minute"][b]
    gain=(wide["cs_change"][a]-wide["cs_change"][b])+(wide["revenue"][a]-wide["revenue"][b])
    be=(gain/scd).where(scd.abs()>1e-9)
    mine=be.groupby(AX+["year"]).median().reset_index(name="be")
    c=csv[(csv.rule==a)&(csv.reference==b)]
    j=c.merge(mine,on=AX+["year"],validate="one_to_one")
    d=(j.breakeven_minutes_median-j.be).abs()
    print(f"{a} vs {b}: cells {len(j)}; max|csv breakeven median - independent| = {np.nanmax(d):.3g}; NaN agree: {(j.breakeven_minutes_median.isna()==j.be.isna()).all()}; searches_more share check max diff {np.abs(c.sort_values(AX+['year']).share_comparator_searches_more.values - (scd>1e-9).groupby(AX+['year']).mean().reset_index(name='s').merge(c[AX+['year']],on=AX+['year']).s.values).max() if False else 'skipped'}")
print("max |welfare_diff - (cs+rev-search)| over all pairs/reps:",worst)
# search cost per minute vs search_cost: ratio constant = 1/5
r=(sw.search_cost/sw.search_cost_per_minute); print("search_cost/search_cost_per_minute unique:",np.unique(r.round(9)))
# NaN breakeven counts
for a,b in [("peak_band","peak_zone")]:
    scd=wide["search_cost_per_minute"][a]-wide["search_cost_per_minute"][b]
    print(a,b,"rep-years with |scd|<=1e-9 (breakeven NaN):",int((scd.abs()<=1e-9).sum()),"of",len(scd),"; with 1e-9<|scd|<0.1 $/min:",int(((scd.abs()>1e-9)&(scd.abs()<0.1)).sum()))
