import pandas as pd, geopandas as gpd
from phillyparking.io import opendataphilly
st=opendataphilly.fetch_streets()
print("rows",len(st)); print("columns",[c for c in st.columns if c!="geometry"])
for c in ("CLASS","ONEWAY","ST_TYPE","STATUS","SEGMENT_TYPE","ST_CODE"):
    if c in st.columns: print(c, st[c].value_counts(dropna=False).head(12).to_dict())
seg=gpd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
p=seg[seg.priced_curb]
suf=p.street_name.str.extract(r"\s(\w+)$")[0]
print("priced street-name suffix counts:",suf.value_counts().head(15).to_dict())
print("priced alley/way/court/place-like:", int(suf.isin(["ALY","WAY","CT","PL","LN","TER","ALLEY","MEWS"]).sum()), "spaces", int(p[suf.isin(["ALY","WAY","CT","PL","LN","TER","ALLEY","MEWS"])].capacity.sum()))
