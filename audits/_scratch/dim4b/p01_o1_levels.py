import logging, pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
from pathlib import Path
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.scenarios.runner import run_scenario
from phillyparking.scenarios.compare import comparison_table
S=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4b")
segs=load_priced_segments(S/"data/processed/segments.parquet")
panel=baseline_occupancy(segs,seed=42)
print("baseline priced-hour mean occupancy by zone:")
from phillyparking.pricing.priced_hours import frame_priced_mask
d=panel.merge(segs[["segment_id","zone_id","capacity"]],on="segment_id"); d=d[frame_priced_mask(d)]
d["w"]=d.occupancy*d.capacity; print((d.groupby("zone_id").w.sum()/d.groupby("zone_id").capacity.sum()).round(3).to_dict())
res={n:run_scenario(n,segments=segs,baseline_panel=panel) for n in ("status_quo","seattle","full_pbd")}
t=comparison_table(res); print(t.loc[["total_revenue","mean_price_ccc","mean_price_cca","cruising_dwl_total","cs_change_total"]].round(2).to_string())
