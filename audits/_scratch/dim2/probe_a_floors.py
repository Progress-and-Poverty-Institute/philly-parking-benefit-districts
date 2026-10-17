"""(a) Floors: unclipped Arnott prices, what busiest-hour occupancy each zone needs to come off
its floor, what the law says demand is at a zero price; then the two reforms re-run with floors
relaxed (PHILLYPARKING_CONFIG_DIR -> scratch copy) to see how load-bearing the floors are.
Part 2 runs only when PHILLYPARKING_CONFIG_DIR is set (one process per config: load_config caches)."""
import os, sys, json
import numpy as np, pandas as pd
from phillyparking._config import load_config, config_dir
from phillyparking.spatial.segments import load_priced_segments
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.arnott_inci import optimal_price_arnott_inci

MAIN = "C:/projects/philly-parking-benefit-districts"
segs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
sq = pd.read_parquet(f"{MAIN}/outputs/models/status_quo/occupancy.parquet")
zones = load_config("zones")["zones"]
print("config dir:", config_dir())
print("floors in force:", {z["id"]: z["floor"] for z in zones})

if os.environ.get("PHILLYPARKING_CONFIG_DIR") is None:
    panel = sq.drop(columns=["zone_id"]).merge(segs[["segment_id", "zone_id", "capacity"]], on="segment_id")
    panel = panel.loc[frame_priced_mask(panel)]
    panel["_oc"] = panel.occupancy * panel.capacity
    zh = panel.groupby(["zone_id", "hour_of_week"]).agg(_oc=("_oc", "sum"), _c=("capacity", "sum"))
    zh["occ"] = zh._oc / zh._c
    peak = zh.groupby("zone_id")["occ"].max()
    print("\nBusiest priced capacity-weighted zone-hour (status quo):", peak.round(3).to_dict())
    for e in (-0.2, -0.4, -0.7):
        print(f"\n--- elasticity {e}: q(0)/q(p_ref) under the exponential law = exp(|e|) = {np.exp(-e):.3f}")
        rows = []
        for z in zones:
            zid, pref, floor = z["id"], float(z["current_rate_usd_per_hr"]), float(z["floor"])
            pk = float(peak[zid])
            p_unclipped = optimal_price_arnott_inci(pk, pref, 1.0, e, 0.15, reference_price=pref)
            # busiest-hour occupancy at which the unclipped price equals the floor / zero
            need_floor = 0.85 * np.exp(-e * (floor - pref) / pref)
            need_zero = 0.85 * np.exp(-e * (0.0 - pref) / pref)
            rows.append(dict(zone=zid, posted=pref, floor=floor, busiest=round(pk, 3),
                             arnott_unclipped=round(p_unclipped, 3), clipped=round(max(floor, p_unclipped), 3),
                             busiest_needed_to_clear_floor=round(need_floor, 3),
                             busiest_needed_for_nonneg_price=round(need_zero, 3),
                             occ_at_zero_price=round(pk * np.exp(-e), 3)))
        print(pd.DataFrame(rows).to_string(index=False))
    sys.exit(0)

# Part 2: run the two reforms under the config in PHILLYPARKING_CONFIG_DIR.
from phillyparking.scenarios.runner import run_scenario
from phillyparking.pricing.priced_hours import zone_mean_price
panel = sq[["segment_id", "hour_of_week", "occupancy", "occupancy_sd"]]
out = {}
for name in ("seattle", "full_pbd"):
    r = run_scenario(name, segments=segs, baseline_panel=panel, seed=42)
    d = r.diagnostics
    out[name] = dict(total_revenue=float(r.revenue.annual_revenue_usd.sum()),
                     cs_change_total=r.cs_change_total,
                     cruising_dwl_total=float(r.cruising_dwl.annual_dwl_usd.sum()),
                     mean_price=zone_mean_price(r.prices.dropna(subset=["price_usd_per_hr"])).round(3).to_dict(),
                     years_run=d["years_run"], converged=d["converged"], cycle=d.get("cycle_period"))
print(json.dumps(out, indent=1))
