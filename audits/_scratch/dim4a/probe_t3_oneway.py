import pandas as pd, geopandas as gpd
from phillyparking.io import opendataphilly
st=opendataphilly.fetch_streets()
for c in ("oneway","multi_rep","class","st_type","responsibl"):
    print(c, st[c].value_counts(dropna=False).head(12).to_dict())
seg=gpd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
p=seg[seg.priced_curb]
# join street attributes back by seg_id? segment_id is a hash; rebuild parent mapping via street_name+class is lossy; instead recompute per-street flags using geometry nearest is overkill.
# use the build mapping: same parent key => seg_id; reproduce hash
import hashlib
st=st.reset_index(drop=True)
def sid(parent,idx): return "S"+hashlib.sha1(f"{parent}|{idx}".encode()).hexdigest()[:12]
m={}
for _,r in st.iterrows():
    m[sid(str(r["seg_id"]),0)]=(r["oneway"],r["multi_rep"],r["st_type"])
hit=p.segment_id.map(lambda s:m.get(s))
print("priced segments matched to an unsplit parent (idx 0):",int(hit.notna().sum()),"of",len(p),"(split pieces keep idx>0 hashes; matched only for single-piece parents)")
d=pd.DataFrame(hit.dropna().tolist(),columns=["oneway","multi_rep","st_type"],index=hit.dropna().index)
print(" oneway among matched priced:",d.oneway.value_counts(dropna=False).to_dict())
print(" multi_rep among matched priced:",d.multi_rep.value_counts(dropna=False).to_dict())
bt=p[p.street_name.str.contains(r"\b(BRG|TUNL)\b",regex=True)] if p.street_name.notna().any() else p.iloc[:0]
print("priced rows whose street_name contains BRG/TUNL:",len(bt))
x=p.merge(st[["stname","st_type"]].drop_duplicates("stname"),left_on="street_name",right_on="stname",how="left")
bt=x[x.st_type.isin(["BRG","TUNL"])]
print("priced segments on BRG/TUNL street types:",len(bt),"spaces",int(bt.capacity.sum()),"; names:",bt.street_name.unique().tolist()[:12])
