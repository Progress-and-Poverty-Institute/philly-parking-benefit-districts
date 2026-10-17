import geopandas as gpd, pandas as pd, numpy as np
from phillyparking.io import opendataphilly
R="C:/projects/philly-parking-benefit-districts/data"
seg=gpd.read_parquet(f"{R}/processed/segments.parquet")
z=opendataphilly.fetch_zoning()
print("zoning rows",len(z),"cols",list(z.columns)[:12]); print(z.zoninggroup.value_counts(dropna=False).to_string())
zu=z.to_crs(32618).copy(); zu["geometry"]=zu.geometry.make_valid(); zu=zu.explode(index_parts=False)
zu=zu[zu.geom_type.isin(["Polygon","MultiPolygon"])]
# overlap within the zoning layer
tot=zu.geometry.area.sum(); un=zu.geometry.union_all().area
print(f"sum polygon area {tot:,.0f} m2, union area {un:,.0f} m2, overlap double count {tot-un:,.0f} m2 ({(tot-un)/tot:.4%})")
# zoned coverage of each priced segment's buffer
p=seg[seg.priced_curb].copy()
buf=p.to_crs(32618)[["segment_id","geometry"]].copy(); buf["geometry"]=buf.geometry.buffer(25,cap_style="flat")
buf["barea"]=buf.geometry.area
inter=gpd.overlay(buf,zu[["zoninggroup","geometry"]],how="intersection",keep_geom_type=True)
a=inter.geometry.area.groupby(inter.segment_id).sum()
cov=(a/buf.set_index("segment_id").barea).reindex(p.segment_id).fillna(0)
cov.index=p.index
p["zoned_cov"]=cov.values
print("\nzoned coverage of the 25 m flat buffer, priced segments: quantiles")
print(p.zoned_cov.quantile([0,.01,.05,.1,.25,.5,.75,.9,1]).round(3).to_string())
for t in (0.1,0.25,0.5):
    print(f"  priced segments with zoned coverage < {t}: {(p.zoned_cov<t).sum()} (capacity {int(p.loc[p.zoned_cov<t,'capacity'].sum())}); share>=0.5 decided on that little land")
# compare: all class 2-5 in box (not just priced) coverage
print("\nexample low-coverage priced segments:")
print(p.nsmallest(5,"zoned_cov")[["street_name","street_class","zone_id","zoned_cov","commercial_frontage_share","capacity"]].to_string())
# consistency: recompute the stored share
inter["a"]=inter.geometry.area
zoned=inter.groupby("segment_id").a.sum(); comm=inter[inter.zoninggroup=="Commercial/Commercial Mixed-Use"].groupby("segment_id").a.sum()
rec=(comm/zoned).reindex(p.segment_id).fillna(0); rec.index=p.index
print("\nrecomputed share equals stored (max abs diff):",float((rec-p.commercial_frontage_share).abs().max()))
p.to_pickle(f"{R.replace('data','')}.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/priced_with_cov.pkl") if False else None
