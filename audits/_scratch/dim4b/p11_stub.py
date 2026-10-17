import pandas as pd, numpy as np, os
from pathlib import Path
from phillyparking.io.ppa_stub import make_known_answer_export
S=Path(os.environ["PHILLYPARKING_DATA_DIR"])
panel=pd.read_parquet(S/"processed/ppa_stub/panel.parquet")
exp=make_known_answer_export()["expected"]
print("panel shape",panel.shape,"periods",panel.period.unique(), "segments",panel.segment_id.unique())
m=panel.merge(exp,on=["segment_id","period","hour_of_week"],how="left")
m["paid_occupancy_y"]=m["paid_occupancy_y"].fillna(0.0)
d=(m["paid_occupancy_x"]-m["paid_occupancy_y"]).abs()
print("cells compared",len(m),"; expected nonzero cells",len(exp),"; max |ingested paid_occupancy - expected|",d.max())
print("nonzero ingested cells:",int((panel.paid_occupancy>0).sum()))
print(panel[panel.paid_occupancy>0].groupby(["segment_id","period"]).size())
# expected values are hand-typed arithmetic (cars/6, 30/360, ...) in ppa_stub.make_known_answer_export lines ~236-247: independent of ingest code
