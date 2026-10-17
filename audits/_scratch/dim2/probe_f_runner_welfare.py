"""(f) The runner's surplus row: decomposition (transfer vs triangle), latent over-capacity demand,
and what the scenarios' cruising term would be under the sweep's own search-cost shape."""
import dataclasses, numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask, hourly_prices
from phillyparking.demand.response import demand_level, cs_change
from phillyparking.welfare.targeting_welfare import load_search_cost_config, search_cost_usd, expected_search_minutes

MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
scfg = load_search_cost_config()
posted = {z["id"]: float(z["current_rate_usd_per_hr"]) for z in load_config("zones")["zones"]}
E = -0.4

def load(name):
    o = pd.read_parquet(f"{MAIN}/outputs/models/{name}/occupancy.parquet")
    o = o.drop(columns=["zone_id"]).merge(segs[["segment_id", "zone_id", "capacity"]], on="segment_id")
    return o.loc[frame_priced_mask(o)].reset_index(drop=True)

sq = load("status_quo")
print("priced block-hours per week:", len(sq), " capacity:", int(segs.capacity.sum()))
res = {}
for name in ("status_quo", "seattle", "full_pbd"):
    o = load(name)
    assert (o.segment_id.values == sq.segment_id.values).all() and (o.hour_of_week.values == sq.hour_of_week.values).all()
    occ, cap, p = o.occupancy.to_numpy(float), o.capacity.to_numpy(float), o.price_usd_per_hr.to_numpy(float)
    p_ref = o.zone_id.map(posted).to_numpy(float)
    q_ref = sq.occupancy.to_numpy(float) * cap
    latent = sq.occupancy.to_numpy(float) * demand_level(p, E, p_ref)
    rev = float((occ * cap * p).sum() * 52)
    cs = float(cs_change(q_ref, p_ref, p, E).sum() * 52)
    transfer = float(((p_ref - p) * q_ref).sum() * 52)
    proxy = float((np.maximum(occ * cap - 0.85 * cap, 0) * 5 / 60 * 20).sum() * 52)
    sc = float(search_cost_usd(occ, cap, scfg).sum() * 52)
    sc95 = float(search_cost_usd(occ, cap, dataclasses.replace(scfg, occupancy_cap=0.95)).sum() * 52)
    # arrivals = latent demand (everyone who wants a space at this price searches)
    mins = expected_search_minutes(occ, cap, scfg)
    sc_lat = float((latent * cap / scfg.mean_duration_hr * mins / 60 * scfg.value_of_time_usd_per_hr).sum() * 52)
    res[name] = dict(revenue=rev, cs=cs, cs_transfer=transfer, cs_triangle=cs - transfer, proxy_dwl=proxy,
                     search_oK=sc, search_oK_cap95=sc95, search_oK_latent_arrivals=sc_lat,
                     share_bh_occ_ge_0p99=float((occ >= 0.99).mean()), share_bh_latent_gt_1=float((latent > 1).mean()),
                     unserved_car_hours_per_year=float((np.maximum(latent - 1, 0) * cap).sum() * 52),
                     share_bh_above_0p85=float((occ > 0.85).mean()))
df = pd.DataFrame(res).T
pd.set_option("display.float_format", lambda v: f"{v:,.3f}" if abs(v) < 10 else f"{v:,.0f}")
print(df.T.to_string())
for name in ("seattle", "full_pbd"):
    r, b = res[name], res["status_quo"]
    print(f"\n{name}: dCS {r['cs']/1e6:.1f}M = transfer {r['cs_transfer']/1e6:.1f}M + triangle {r['cs_triangle']/1e6:.1f}M; dRev {(r['revenue']-b['revenue'])/1e6:.1f}M")
    for k in ("proxy_dwl", "search_oK", "search_oK_cap95", "search_oK_latent_arrivals"):
        w = r["cs"] + (r["revenue"] - b["revenue"]) - (r[k] - b[k])
        print(f"   dCS + dRev - d({k:26s}) = {w/1e6:8.1f}M   (d search = {(r[k]-b[k])/1e6:.1f}M)")
print("\nSearch minutes per arrival under the sweep's shape (K=10): ", {o: round(float(expected_search_minutes(np.array([o]), np.array([10.0]), scfg)[0]), 2) for o in (0.7, 0.85, 0.9, 0.95, 0.99, 1.0)})
print("Search minutes per arrival, K=5 / K=15 at 0.95:", round(float(expected_search_minutes(np.array([0.95]), np.array([5.0]), scfg)[0]), 2), round(float(expected_search_minutes(np.array([0.95]), np.array([15.0]), scfg)[0]), 2))
print("Priced-segment capacity distribution (real):", segs.capacity.describe().round(1).to_dict())
