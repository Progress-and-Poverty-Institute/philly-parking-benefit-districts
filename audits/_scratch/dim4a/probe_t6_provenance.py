import json, pathlib, shutil, os, glob
import pandas as pd
from phillyparking.io.raw_cache import (Layer, load_layer, write_marker, marker_path, synthetic_path,
                                        UnknownProvenanceError, LayerFetchError)
T=pathlib.Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/prov_tmp")
shutil.rmtree(T,ignore_errors=True); T.mkdir(parents=True)
calls=[]
def fetch(): calls.append(1); raise ConnectionError("blocked")
def mk(name): return Layer(name="t."+name,path=T/f"{name}.parquet",source="src",url="u",fetch=fetch,
        write=lambda d,p:d.to_parquet(p),read=pd.read_parquet,synth=lambda:pd.DataFrame({"x":[0]}))
def attempt(label,fn):
    try: r=fn(); print(f"{label}: RETURNED {type(r).__name__} provenance={getattr(r,'attrs',{}).get('provenance',{}).get('kind')}")
    except Exception as e: print(f"{label}: raised {type(e).__name__}: {str(e)[:90]}")
df=pd.DataFrame({"x":[1,2,3]})
# 1. unmarked file under the real name
L=mk("unmarked"); df.to_parquet(L.path)
attempt("1 unmarked real-name file (allow_synthetic False)",lambda:load_layer(L,retries=1,backoff_s=0))
attempt("1b unmarked real-name file (allow_synthetic True)",lambda:load_layer(L,allow_synthetic=True,retries=1,backoff_s=0))
# 2. marker says synthetic under the real name
L=mk("synthname"); df.to_parquet(L.path); write_marker(L.path,layer="t.synthname",kind="synthetic",source="s",url=None,reason="x")
attempt("2 kind=synthetic marker under real name",lambda:load_layer(L,retries=1,backoff_s=0))
attempt("2b same with allow_synthetic=True",lambda:load_layer(L,allow_synthetic=True,retries=1,backoff_s=0))
# 3. .synthetic file only with opt-in
L=mk("syn"); sp=synthetic_path(L.path); df.to_parquet(sp); write_marker(sp,layer="t.syn",kind="synthetic",source="s",url=None,reason="x")
n0=len(calls)
attempt("3a .synthetic file, allow False (fetch fails)",lambda:load_layer(L,allow_synthetic=False,retries=1,backoff_s=0))
print("   fetch calls made in 3a:",len(calls)-n0)
attempt("3b .synthetic file, allow True",lambda:load_layer(L,allow_synthetic=True,retries=1,backoff_s=0))
os.environ["PHILLYPARKING_ALLOW_SYNTHETIC"]="1"
attempt("3c .synthetic file, env switch",lambda:load_layer(L,retries=1,backoff_s=0)); del os.environ["PHILLYPARKING_ALLOW_SYNTHETIC"]
# 3d: .synthetic file with marker missing / marker says real
L=mk("synmk"); sp=synthetic_path(L.path); df.to_parquet(sp); write_marker(sp,layer="t.synmk",kind="real",source="s",url=None)
attempt("3d .synthetic file whose marker says kind=real, allow True",lambda:load_layer(L,allow_synthetic=True,retries=1,backoff_s=0))
# 4. marker bound to content? copy a real marker beside a different file
L=mk("real"); df.to_parquet(L.path); write_marker(L.path,layer="t.real",kind="real",source="s",url="u")
pd.DataFrame({"x":[999]}).to_parquet(L.path)   # content swapped after marking
r=load_layer(L,retries=1,backoff_s=0); print("4 content replaced after marking: loaded x=",r.x.tolist(),"marker kind real -> accepted (no content hash)")
m=json.load(open(marker_path(L.path))); print("   marker fields:",sorted(m))
# 5. real markers on disk: every raw file has one, kind real, file name equal
raw=pathlib.Path("C:/projects/philly-parking-benefit-districts/data/raw")
files=[p for p in raw.rglob("*") if p.is_file() and not p.name.endswith(".provenance.json") and p.name!=".gitkeep"]
bad=[]
for p in files:
    mp=marker_path(p)
    if not mp.exists(): bad.append((p.name,"no marker")); continue
    mk_=json.load(open(mp))
    if mk_["kind"]!="real" or mk_["file"]!=p.name: bad.append((p.name,mk_["kind"],mk_["file"]))
print(f"5 real raw cache: {len(files)} data files, problems: {bad}")
for p in sorted(files):
    m=json.load(open(marker_path(p))); print("   ",p.name,m["kind"],m["fetched_utc"],m["url"][:70])
# 6. load_pois cache key ignores tags
from phillyparking.io import osm_loader
os.environ["PHILLYPARKING_DATA_DIR"]="C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/runA/data"
