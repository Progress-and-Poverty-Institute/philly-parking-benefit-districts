"""(2) Per-zone year-8 prices for the cells whose median mean price was a plateau (5.29 for the
peak rules, 0.82 / 1.00 for the mean rules): which zones sit at a zones.yaml floor or ceiling.
One replication, rule loop copied from cm_sweep (same draws as the tracked sweep)."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.demand.response import demand_level
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import load_targeting_config, review
from phillyparking.scenarios.cm_sweep import _block_draw, _observation_draw, _scale_to_start_occupancy, _apply_prices
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.spatial.synthetic import make_synthetic_segments
zones = {z["id"]: z for z in load_config("zones")["zones"]}
segments = make_synthetic_segments(n=120, seed=42)
segments = segments.loc[segments.zone_id.isin(zones)].reset_index(drop=True)
baseline = baseline_occupancy(segments, seed=42, anchor_set="synthetic_fixture")
tcfg = load_targeting_config()
base = baseline.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline.columns]).merge(
    segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
base = base.sort_values(["segment_id", "hour_of_week"]).reset_index(drop=True)
base["price_usd_per_hr"] = 2.0
priced = frame_priced_mask(base)
seg_index = pd.factorize(base.segment_id)[0]; zone_index = pd.factorize(base.zone_id)[0]
n_seg = int(seg_index.max()) + 1
base_d = np.clip(base.occupancy.to_numpy(float), 0.01, None); p0 = np.full(len(base), 2.0)

def year8_zone_prices(level, tau, sigma, eps, rule, rep=0):
    u = _block_draw(42, rep, n_seg)[seg_index]
    z = {y: _observation_draw(42, rep, y, len(base)) for y in range(1, 9)}
    d0 = _scale_to_start_occupancy(base_d * np.exp(tau * u - 0.5 * tau * tau), zone_index, priced, float(level))
    panel = base.copy(); price = p0.copy(); d = d0.copy()
    for year in range(1, 9):
        panel["occupancy"] = np.clip(np.minimum(d, 1.0) + sigma * z[year], 0.0, 1.0)
        panel["price_usd_per_hr"] = price
        new = _apply_prices(review(rule, panel, tcfg), panel, price)
        price = np.where(priced, new, price)
        d = np.where(priced, d0 * demand_level(price, eps, p0), d0)
    df = base[["zone_id"]].assign(p=price)[priced]
    return df.groupby("zone_id").p.mean().round(2).to_dict(), float(df.p.mean())

cells = [(0.75, 0.6, 0.0, -0.2, "peak_zone"), (0.9, 0.3, 0.0, -0.4, "peak_zone"), (0.75, 0.0, 0.0, -0.2, "peak_zone"),
         (0.6, 0.0, 0.0, -0.4, "mean_zone"), (0.6, 0.0, 0.0, -0.7, "mean_zone"), (0.6, 0.3, 0.0, -0.4, "mean_zone"), (0.9, 0.6, 0.0, -0.2, "mean_zone")]
for level, tau, sigma, eps, rule in cells:
    zp, mp = year8_zone_prices(level, tau, sigma, eps, rule)
    tags = {z: ("CEIL" if abs(p - zones[z]["ceiling"]) < 1e-6 else "FLOOR" if abs(p - zones[z]["floor"]) < 1e-6 else "") for z, p in zp.items()}
    print(f"m={level} tau={tau} sigma={sigma} e={eps} {rule}: mean price {mp:.2f}; zones {zp}; bounds {[z for z, t in tags.items() if t]} -> {[t for t in tags.values() if t]}")
