import pandas as pd, geopandas as gpd, hashlib
from phillyparking.io import opendataphilly
st=opendataphilly.fetch_streets().reset_index(drop=True)
seg=gpd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
def sid(parent,idx): return "S"+hashlib.sha1(f"{parent}|{idx}".encode()).hexdigest()[:12]
m={}
for r in st[["seg_id","responsibl","oneway","multi_rep","st_type"]].itertuples(index=False):
    for k in range(12):
        m[sid(str(r.seg_id),k)]=(r.responsibl,r.oneway,r.multi_rep,r.st_type)
info=seg.segment_id.map(m)
print("segments mapped to a centerline row:",int(info.notna().sum()),"of",len(seg),"(unmapped = multipart parts, expect few)")
d=pd.DataFrame(info.dropna().tolist(),index=info.dropna().index,columns=["responsibl","oneway","multi_rep","st_type"])
s=seg.join(d)
p=s[s.priced_curb]
print("priced by responsible party (segments, spaces):")
print(p.groupby("responsibl",dropna=False).capacity.agg(["count","sum"]).to_string())
print("priced by st_type top:",p.st_type.value_counts().head(12).to_dict())
print("priced by oneway:",p.oneway.value_counts().to_dict(),"; multi_rep>0:",int((p.multi_rep>0).sum()),"spaces",int(p[p.multi_rep>0].capacity.sum()))
print("priced on PRIVATE/PHA/PIDC/FAIRMOUNT PARK/DRPA/AIRPORT:",int(p.responsibl.isin(['PRIVATE','PHA','PIDC','FAIRMOUNT PARK','DRPA','AIRPORT','BCBC','TOWNSHIP']).sum()),"spaces",int(p[p.responsibl.isin(['PRIVATE','PHA','PIDC','FAIRMOUNT PARK','DRPA','AIRPORT','BCBC','TOWNSHIP'])].capacity.sum()))
print("priced STATE-responsible streets (top names):",p[p.responsibl=='STATE'].groupby('street_name').capacity.sum().sort_values(ascending=False).head(8).to_dict())
print("priced PRIVATE streets (top names):",p[p.responsibl=='PRIVATE'].groupby('street_name').capacity.sum().sort_values(ascending=False).head(8).to_dict())
