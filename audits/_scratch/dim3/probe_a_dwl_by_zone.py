"""(6) Circularity: per-zone cruising DWL and prices in the saved scenarios. The Arnott pricer
targets the zone's busiest priced hour at 0.85 and the scorer scores excess over 0.85, so the
full-PBD CCC row should be near zero by construction; the rest of the DWL row is then the floored
zones'. Also: share of each scenario's DWL from zones at a configured floor."""
import json, pandas as pd, numpy as np
from phillyparking._config import load_config
MAIN = "C:/projects/philly-parking-benefit-districts/outputs/models"
zones = {z["id"]: z for z in load_config("zones")["zones"]}
rows = {}
for name in ("status_quo", "seattle", "full_pbd"):
    d = pd.read_parquet(f"{MAIN}/{name}/cruising_dwl.parquet").set_index("zone_id")["annual_dwl_usd"]
    rows[name] = d
df = pd.DataFrame(rows)
df["floor"] = [zones[z]["floor"] for z in df.index]
pr = {}
for name in ("seattle", "full_pbd"):
    meta = json.load(open(f"{MAIN}/{name}/meta.json"))
    fp = pd.DataFrame(meta["diagnostics"]["final_prices"])
    pr[name] = fp.groupby("zone_id")["price_usd_per_hr"].mean()
df["p_seattle"] = pr["seattle"]; df["p_full_pbd"] = pr["full_pbd"]
pd.set_option("display.width", 200)
print(df.round(0).to_string())
tot = df[["status_quo", "seattle", "full_pbd"]].sum()
print("\ntotals:", tot.round(0).to_dict())
for name in ("seattle", "full_pbd"):
    at_floor = df.index[np.isclose(df[f"p_{name}"], df["floor"])]
    print(f"{name}: zones at floor {list(at_floor)}; DWL share from floored zones "
          f"{df.loc[at_floor, name].sum() / df[name].sum():.3f}; CCC share {df.loc['ccc', name] / df[name].sum():.3f}; "
          f"CCC DWL ${df.loc['ccc', name]:,.0f}")
# the full-PBD fixed point: CCC zone-hour peak vs segment-level excess
seg = pd.read_parquet("C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet", columns=["segment_id", "zone_id", "capacity"])
from phillyparking.pricing.priced_hours import frame_priced_mask
for name in ("seattle", "full_pbd"):
    o = pd.read_parquet(f"{MAIN}/{name}/occupancy.parquet").drop(columns=["zone_id"]).merge(seg, on="segment_id")
    o = o[frame_priced_mask(o)]
    c = o[o.zone_id == "ccc"]
    zh = c.assign(oc=c.occupancy * c.capacity).groupby("hour_of_week").agg(oc=("oc", "sum"), cap=("capacity", "sum"))
    print(f"{name} ccc: busiest priced zone-hour {float((zh.oc / zh.cap).max()):.4f}; share of priced block-hours > 0.85: "
          f"{float((c.occupancy > 0.85).mean()):.3f}; share at 1.0: {float((c.occupancy >= 0.999).mean()):.3f}")
