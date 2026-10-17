import numpy as np, pandas as pd, json, logging
from pathlib import Path
logging.disable(logging.WARNING)
from phillyparking.scenarios.runner import run_scenario, _same_prices, _price_vector
from phillyparking.spatial.segments import load_priced_segments
S=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4b")
segs=load_priced_segments(S/"data/processed/segments.parquet"); panel=pd.read_parquet(S/"data/processed/demand_panel.parquet")
for sc,el in [("seattle","pessimistic"),("seattle","optimistic"),("full_pbd","pessimistic"),("full_pbd","optimistic")]:
    r=run_scenario(sc,segments=segs,baseline_panel=panel,elasticity_scenario=el)
    d=r.diagnostics
    print(sc,el,"converged",d["converged"],"converged_year",d["converged_year"],"years_run",d["years_run"],"cycle_period",d.get("cycle_period"),"phases",None if "phases" not in d else [(p["year"],round(p["total_revenue"])) for p in d["phases"]])
# unit test of detection with a synthetic 2-cycle: a step function that alternates
a=pd.Series({"x":1.0}); b=pd.Series({"x":1.5})
print("_same_prices tol: 1.0 vs 1.0005:", _same_prices(pd.Series({"x":1.0}),pd.Series({"x":1.0005})), "| 1.0 vs 1.002:", _same_prices(pd.Series({"x":1.0}),pd.Series({"x":1.002})))
