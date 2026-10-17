"""(2) Null control for the sweep: a DGP where peak and mean targeting should tie. Every priced
block-hour in a zone has the same true occupancy (flat panel, tau = 0), so q95 == mean and the
two rules must give identical prices and welfare. Run the package's own rule and scorer code
(same loop as cm_sweep.chatman_manville_sweep) for sigma = 0 and sigma = 0.1. With noise the
reviewed q95 is the mean + 1.645 sigma while the reviewed mean is unbiased, so the peak rule
raises on nothing. Expect: sigma = 0 -> exact tie; sigma = 0.1 -> a nonzero 'peak vs mean'
welfare difference and a finite breakeven where no peak exists."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.demand.response import demand_level
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import load_targeting_config, review
from phillyparking.scenarios.cm_sweep import _observation_draw, _apply_prices, WEEKS_PER_YEAR
from phillyparking.welfare.targeting_welfare import load_search_cost_config, search_cost_usd, cs_change_usd
from phillyparking.spatial.synthetic import make_synthetic_segments

cfg = load_config("scenarios")["chatman_manville_sweep"]
segments = make_synthetic_segments(n=120, seed=42)
priced_zones = {z["id"] for z in load_config("zones")["zones"]}
segments = segments.loc[segments.zone_id.isin(priced_zones)].reset_index(drop=True)
tcfg, scfg = load_targeting_config(), load_search_cost_config()
P0 = 2.0
rows = []
for seg in segments.itertuples():
    for h in range(168):
        rows.append({"segment_id": seg.segment_id, "zone_id": seg.zone_id, "capacity": seg.capacity, "hour_of_week": h})
base = pd.DataFrame(rows)
base["price_usd_per_hr"] = P0
priced = frame_priced_mask(base)
cap = base.capacity.to_numpy(float); p0 = np.full(len(base), P0)
YEARS = 8

def run(level, sigma, eps, rule, rep=0):
    d0 = np.full(len(base), float(level))          # flat: identical in every priced block-hour
    z = {y: _observation_draw(42, rep, y, len(base)) for y in range(1, YEARS + 1)}
    panel = base.copy(); price = p0.copy(); d = d0.copy()
    occ0 = np.minimum(d0, 1.0)
    rev0 = float((occ0 * cap * p0)[priced].sum() * WEEKS_PER_YEAR)
    cost0 = float(search_cost_usd(occ0, cap, scfg)[priced].sum() * WEEKS_PER_YEAR)
    out = []
    for year in range(1, YEARS + 1):
        panel["occupancy"] = np.clip(np.minimum(d, 1.0) + sigma * z[year], 0.0, 1.0)
        panel["price_usd_per_hr"] = price
        new = _apply_prices(review(rule, panel, tcfg), panel, price)
        price = np.where(priced, new, price)
        d = np.where(priced, d0 * demand_level(price, eps, p0), d0)
        occ = np.minimum(d, 1.0)
        rev = float((occ * cap * price)[priced].sum() * WEEKS_PER_YEAR)
        cost = float(search_cost_usd(occ, cap, scfg)[priced].sum() * WEEKS_PER_YEAR)
        cs = float(cs_change_usd(d0, p0, price, eps, cap)[priced].sum() * WEEKS_PER_YEAR)
        out.append(dict(year=year, mean_price=float(price[priced].mean()), true_occ=float(occ[priced].mean()),
                        reviewed_q95=float(np.quantile(panel.occupancy[priced], 0.95)), reviewed_mean=float(panel.occupancy[priced].mean()),
                        cs=cs, rev=rev - rev0, sc=cost - cost0, welfare=cs + (rev - rev0) - (cost - cost0)))
    return pd.DataFrame(out)

pd.set_option("display.width", 220)
for level in (0.60, 0.75, 0.80, 0.90):
    for sigma in (0.0, 0.10):
        eps = -0.4
        a = run(level, sigma, eps, "mean_zone"); b = run(level, sigma, eps, "peak_zone")
        last_a, last_b = a.iloc[-1], b.iloc[-1]
        gain = (last_a.cs - last_b.cs) + (last_a.rev - last_b.rev); scd = (last_a.sc - last_b.sc) / scfg.minutes_at_reference
        be = gain / scd if abs(scd) > 1e-9 else float("nan")
        print(f"flat m={level:.2f} sigma={sigma:.2f} e={eps}: year-8 price mean_zone {last_a.mean_price:.2f} peak_zone {last_b.mean_price:.2f} | "
              f"true occ {last_a.true_occ:.3f} / {last_b.true_occ:.3f} | welfare mean-peak {last_a.welfare - last_b.welfare:,.0f} $/yr | "
              f"cs_diff {last_a.cs - last_b.cs:,.0f} rev_diff {last_a.rev - last_b.rev:,.0f} sc_diff {last_a.sc - last_b.sc:,.0f} | breakeven {be:.2f} min")
        if sigma > 0:
            print("    peak_zone year 1 reviewed q95 %.3f vs reviewed mean %.3f (true %.3f)" % (b.iloc[0].reviewed_q95, b.iloc[0].reviewed_mean, level))
