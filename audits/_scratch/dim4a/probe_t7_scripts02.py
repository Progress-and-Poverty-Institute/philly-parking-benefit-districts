import geopandas as gpd, pandas as pd, numpy as np
S="C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a"
base=gpd.read_parquet(f"{S}/runA/data/processed/segments.parquet")
for name,run in (("min_commercial_share 0.9","runD"),("no_curb_classes []","runE")):
    s=gpd.read_parquet(f"{S}/{run}/data/processed/segments.parquet")
    p=s[s.priced_curb]; bp=base[base.priced_curb]
    print(f"{name}: rows {len(s)} (base {len(base)}), priced {len(p)} (base {len(bp)}), priced capacity {int(p.capacity.sum())} (base {int(bp.capacity.sum())}),"
          f" same priced ids as base: {set(p.segment_id)==set(bp.segment_id)}; classes in table {sorted(s.street_class.dropna().unique().tolist())}")
    print("   priced by zone:",p.groupby('zone_id').capacity.agg(['count','sum']).to_dict('index'))
    import json; print("   rule:",json.load(open(f"{S}/{run}/data/processed/segments.meta.json"))["priced_curb_rule"])
