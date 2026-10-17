"""RA probe (A1 ii): share of each dollar row (revenue change, DWL, CS) that sits in the four
floor-bound zones, where both reforms post the same price; and whether those prices are identical."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.demand.response import cs_change
MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
posted = {z["id"]: float(z["current_rate_usd_per_hr"]) for z in load_config("zones")["zones"]}
floors = {z["id"]: float(z["floor"]) for z in load_config("zones")["zones"]}
def load(name):
    o = pd.read_parquet(f"{MAIN}/outputs/models/{name}/occupancy.parquet")
    o = o.drop(columns=["zone_id"]).merge(segs[["segment_id", "zone_id", "capacity"]], on="segment_id")
    return o.loc[frame_priced_mask(o)].sort_values(["segment_id", "hour_of_week"]).reset_index(drop=True)
sq = load("status_quo"); E = -0.4
rows = {}
for name in ("seattle", "full_pbd"):
    o = load(name)
    cap = o.capacity.to_numpy(float); p = o.price_usd_per_hr.to_numpy(float); p_ref = o.zone_id.map(posted).to_numpy(float)
    q_ref = sq.occupancy.to_numpy(float) * cap
    o["d_rev"] = (o.occupancy * cap * p - sq.occupancy * cap * sq.price_usd_per_hr) * 52
    o["dwl"] = np.maximum(o.occupancy * cap - 0.85 * cap, 0) * 5 / 60 * 20 * 52
    o["cs"] = cs_change(q_ref, p_ref, p, E) * 52
    o["at_floor"] = np.isclose(p, o.zone_id.map(floors).to_numpy(float))
    g = o.groupby("zone_id").agg(d_rev=("d_rev", "sum"), dwl=("dwl", "sum"), cs=("cs", "sum"), share_bh_at_floor=("at_floor", "mean"))
    rows[name] = g
    print(f"\n{name} per zone ($M; share of priced block-hours at the zone floor):"); print((g.assign(d_rev=g.d_rev/1e6, dwl=g.dwl/1e6, cs=g.cs/1e6)).round(3).to_string())
    fz = g.drop(index="ccc")
    print(f"  share of total in the four floor zones: d_rev {fz.d_rev.sum()/g.d_rev.sum():.3f}  dwl {fz.dwl.sum()/g.dwl.sum():.3f}  cs {fz.cs.sum()/g.cs.sum():.3f}")
# identical prices in the four floor zones?
s = load("seattle"); f = load("full_pbd")
same = (s.price_usd_per_hr.to_numpy() == f.price_usd_per_hr.to_numpy())
print("\nshare of priced block-hours with identical price under both reforms, by zone:")
print(pd.Series(same).groupby(s.zone_id.values).mean().round(3).to_dict())
print("CCC-only difference between reforms ($M): d_rev", round((rows['full_pbd'].d_rev['ccc'] - rows['seattle'].d_rev['ccc'])/1e6, 2),
      " dwl", round((rows['full_pbd'].dwl['ccc'] - rows['seattle'].dwl['ccc'])/1e6, 2), " cs", round((rows['full_pbd'].cs['ccc'] - rows['seattle'].cs['ccc'])/1e6, 2))
print("table totals check: seattle d_rev", round(rows['seattle'].d_rev.sum()/1e6, 2), "full_pbd d_rev", round(rows['full_pbd'].d_rev.sum()/1e6, 2))
