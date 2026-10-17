"""Tasks 5,6,7: recompute revenue, CS, DWL from saved occupancy+prices+real segments with independent code."""
import numpy as np, pandas as pd, json, sys
from pathlib import Path
SAVED = Path("C:/projects/philly-parking-benefit-districts/outputs/models")
segs = pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet")
print("segments in file", len(segs), "zones", segs.zone_id.value_counts().to_dict())
zones = {"ccc":(8,20,8,20),"cca":(8,20,8,20),"ucity":(8,20,8,20),"south_philly":(8,18,8,18),"fishtown":(8,20,8,20)}  # weekday hrs, sat hrs (hand-typed from zones.yaml)
rate = {"ccc":4.0,"cca":3.5,"ucity":2.0,"south_philly":1.5,"fishtown":1.5}
def priced(h, z):
    wd0,wd1,sa0,sa1 = zones[z]
    d, hh = h//24, h%24
    return ((d<5)&(hh>=wd0)&(hh<wd1)) | ((d==5)&(hh>=sa0)&(hh<sa1))
sq = pd.read_parquet(SAVED/"status_quo/occupancy.parquet")
named = segs[segs.zone_id.isin(zones)]
print("named segs", len(named), "unique segs in sq panel", sq.segment_id.nunique(), "rows", len(sq), "segs in panel not in named:", len(set(sq.segment_id)-set(named.segment_id)), "named not in panel:", len(set(named.segment_id)-set(sq.segment_id)))
print("capacity total (named)", named.capacity.sum())
res = {}
for sc in ["status_quo","seattle","full_pbd"]:
    occ = pd.read_parquet(SAVED/sc/"occupancy.parquet")
    pr = pd.read_parquet(SAVED/sc/"prices.parquet")
    meta = json.load(open(SAVED/sc/"meta.json"))
    df = occ.merge(named[["segment_id","zone_id","capacity"]], on="segment_id", how="inner", suffixes=("_p",""))
    zcol = "zone_id"
    m = np.array([priced(h,z) for h,z in zip(df.hour_of_week.values, df[zcol].values)])
    # panel carries its own price column (the price that clipped occupancy under) -- use the panel's price, and also prices.parquet check
    print(sc, "panel cols", list(occ.columns), "prices cols", list(pr.columns))
    p = df["price_usd_per_hr"].values
    rev_panel_price = 52*(df.occupancy*df.capacity*p)[m].sum()
    # zone-level: revenue = zone_capacity*annual_hours * capweighted occ -- same as 52*sum when full weekly panel
    print(sc, "revenue (52 x sum occ*cap*panel price over priced rows) =", round(rev_panel_price,2), "; table total_revenue =", round(meta["allocation"]["total_revenue_usd"],2), "diff", rev_panel_price-meta["allocation"]["total_revenue_usd"])
    # n rows per segment: full weekly panel?
    print("   rows per segment:", occ.groupby("segment_id").size().unique())
    res[sc]=dict(rev=rev_panel_price)
    # DWL
    tv = meta["diagnostics"]["dwl_target_vacancy"]
    dem = df.occupancy*df.capacity; thr=(1-tv)*df.capacity
    excess = np.maximum(dem-thr,0); dwl = 52*(excess*(5/60)*20)[m].sum()
    print("   target vacancy used by runner:", tv, " DWL recomputed", round(dwl,2))
    res[sc]["dwl"]=dwl
    # price check: panel price vs prices.parquet per zone
    # CS
pd.Series({k:v for k,v in res.items()}).to_json(Path(__file__).with_name("p05_res.json"))
