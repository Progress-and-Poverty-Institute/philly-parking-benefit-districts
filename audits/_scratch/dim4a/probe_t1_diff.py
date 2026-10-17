import json, sys, hashlib
import geopandas as gpd, pandas as pd, numpy as np
S="C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a"
R="C:/projects/philly-parking-benefit-districts/data/processed"
real=gpd.read_parquet(f"{R}/segments.parquet")
print("real rows",len(real),"priced",int(real.priced_curb.sum()),"cap priced",int(real.loc[real.priced_curb,'capacity'].sum()))
print("real columns",list(real.columns))
for run in ("runA","runB"):
    new=gpd.read_parquet(f"{S}/{run}/data/processed/segments.parquet")
    print("\n==",run,"rows",len(new),"priced",int(new.priced_curb.sum()),"cap priced",int(new.loc[new.priced_curb,'capacity'].sum()))
    print("columns equal:",list(new.columns)==list(real.columns), "dtypes equal:", (new.dtypes==real.dtypes).all())
    print("segment_id order equal:",(new.segment_id.values==real.segment_id.values).all())
    for c in real.columns:
        a,b=real[c],new[c]
        if c=="geometry":
            eq = a.geom_equals_exact(b,tolerance=1e-12).all() if len(a)==len(b) else False
            print(f"  {c}: exact-geom-equal {eq}")
            continue
        try:
            if a.dtype.kind in "fc":
                eq=np.allclose(a.to_numpy(float),b.to_numpy(float),equal_nan=True,rtol=0,atol=0)
                nd=int((~((a.to_numpy(float)==b.to_numpy(float))|(np.isnan(a.to_numpy(float))&np.isnan(b.to_numpy(float))))).sum())
            else:
                eq=a.equals(b); nd=int((a.fillna('NA').astype(str)!=b.fillna('NA').astype(str)).sum())
        except Exception as e:
            eq=False; nd=str(e)
        if not eq: print(f"  {c}: DIFF n_differ={nd}")
    print("  all non-geom columns exactly equal check done")
    # meta
    m_new=json.load(open(f"{S}/{run}/data/processed/segments.meta.json"))
    m_real=json.load(open(f"{R}/segments.meta.json"))
    for k in m_real:
        if k in("created_utc",):continue
        if k=="layers":
            for l in m_real[k]:
                x,y=m_real[k][l],m_new[k][l]
                d={kk:(x.get(kk),y.get(kk)) for kk in set(x)|set(y) if x.get(kk)!=y.get(kk)}
                if d: print("  meta layer",l,"differs:",d)
        elif m_real[k]!=m_new[k]:
            print("  meta",k,"differs:",m_real[k],"vs",m_new[k])
    print("  new build_report in meta:",m_new["build_report"])
