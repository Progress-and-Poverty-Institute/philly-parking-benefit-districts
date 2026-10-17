"""RB3: one-replication replica of the sweep's inner loop (package functions, same draws), validated
against replication 0 of the tracked parquet, then rescored at year 8 per cell:
  (ii)  search cost with occupancy_cap 0.95 / 0.999 instead of 0.99; minutes a full block costs
  (iii) consumer surplus on served demand min(q, cap) (efficient rationing) instead of latent q;
        search cost with latent arrivals instead of served
  (v)   per-zone year-8 prices: zones at the zones.yaml floor / ceiling per rule and cell; zone prices
        above the exponential revenue peak p0/|e|
Usage: rb3_replica.py <tag>   (config comes from PHILLYPARKING_CONFIG_DIR if set)"""
import sys, time, dataclasses
import numpy as np, pandas as pd
from phillyparking._config import load_config, config_dir
from phillyparking.demand.response import demand_level, load_demand_form
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import load_targeting_config, review
from phillyparking.scenarios.cm_sweep import (_block_draw, _observation_draw, _scale_to_start_occupancy,
                                               _apply_prices, WEEKS_PER_YEAR)
from phillyparking.welfare.targeting_welfare import (load_search_cost_config, search_cost_usd,
                                                     expected_search_minutes, cs_change_usd)
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.spatial.synthetic import make_synthetic_segments

TAG = sys.argv[1] if len(sys.argv) > 1 else "default"
OUT = "C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/refute/RB/"
print("config dir:", config_dir(), "| demand form:", load_demand_form())
cfg = load_config("scenarios")["chatman_manville_sweep"]
zones = {z["id"]: z for z in load_config("zones")["zones"]}
segments = make_synthetic_segments(n=int(cfg["fixture"]["n"]), seed=int(cfg["fixture"]["seed"]))
segments = segments.loc[segments.zone_id.isin(zones)].reset_index(drop=True)
baseline = baseline_occupancy(segments, seed=42, anchor_set="synthetic_fixture")
tcfg, scfg = load_targeting_config(), load_search_cost_config()
scfg95 = dataclasses.replace(scfg, occupancy_cap=0.95)
scfg999 = dataclasses.replace(scfg, occupancy_cap=0.999)
base = baseline.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline.columns]).merge(
    segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
base = base.sort_values(["segment_id", "hour_of_week"]).reset_index(drop=True)
P0 = float(cfg["start_price_usd"]); base["price_usd_per_hr"] = P0
priced = np.asarray(frame_priced_mask(base), dtype=bool)
seg_index = pd.factorize(base.segment_id)[0]; n_seg = int(seg_index.max()) + 1
zone_codes, zone_names = pd.factorize(base.zone_id)
base_d = np.clip(base.occupancy.to_numpy(float), 0.01, None)
cap = base.capacity.to_numpy(float); p0 = np.full(len(base), P0)
VOT, DUR = scfg.value_of_time_usd_per_hr, scfg.mean_duration_hr
floor = np.array([zones[z]["floor"] for z in zone_names]); ceil_ = np.array([zones[z]["ceiling"] for z in zone_names])
print("zones:", list(zone_names), "floors", floor.tolist(), "ceilings", ceil_.tolist())
full99 = expected_search_minutes(np.array([1.0]), np.array([10.0]), scfg)[0]
full95 = expected_search_minutes(np.array([1.0]), np.array([10.0]), scfg95)[0]
full999 = expected_search_minutes(np.array([1.0]), np.array([10.0]), scfg999)[0]
print(f"(ii) minutes a FULL 10-space block costs: cap 0.99 -> {full99:.1f} min ({full99/scfg.minutes_at_reference:.2f}x the 5-min reference); cap 0.95 -> {full95:.1f}; cap 0.999 -> {full999:.1f}")
print(f"     at 0.85 occupancy: {expected_search_minutes(np.array([0.85]), np.array([10.0]), scfg)[0]:.2f} min; at 0.90: {expected_search_minutes(np.array([0.90]), np.array([10.0]), scfg)[0]:.2f}")


def cs_served(d0, price, eps):
    """-int_{p0}^{p} min(q(x), cap) dx with q(x) = d0 cap exp(a (x - p0)), a = eps / p0; q = cap at p_c."""
    a = eps / P0
    p_c = p0 + np.log(1.0 / d0) / a

    def Q(t):
        return d0 * cap / a * np.exp(a * (t - p0))

    def G(x):
        return np.where(x <= p_c, cap * x, cap * p_c + Q(x) - Q(p_c))
    return -(G(price) - G(p0))


def score(d, price, d0, eps):
    occ = np.minimum(d, 1.0)
    m = {}
    m["revenue"] = (occ * cap * price)[priced].sum() * WEEKS_PER_YEAR
    m["cs_change"] = cs_change_usd(d0, p0, price, eps, cap)[priced].sum() * WEEKS_PER_YEAR
    m["cs_served"] = cs_served(d0, price, eps)[priced].sum() * WEEKS_PER_YEAR
    sc = search_cost_usd(occ, cap, scfg)
    m["search_cost"] = sc[priced].sum() * WEEKS_PER_YEAR
    m["sc_cap95"] = search_cost_usd(occ, cap, scfg95)[priced].sum() * WEEKS_PER_YEAR
    m["sc_cap999"] = search_cost_usd(occ, cap, scfg999)[priced].sum() * WEEKS_PER_YEAR
    mins = expected_search_minutes(occ, cap, scfg)
    m["sc_latent_arr"] = (d * cap / DUR * mins / 60 * VOT)[priced].sum() * WEEKS_PER_YEAR
    full = priced & (occ >= 0.999)
    m["sc_full_share"] = float(full.sum() / priced.sum())
    m["sc_from_full"] = sc[full].sum() * WEEKS_PER_YEAR
    zp = pd.Series(price[priced]).groupby(zone_codes[priced]).agg(["min", "max", "mean"])
    m["zones_at_floor"] = int((np.isclose(zp["max"], floor[zp.index], atol=1e-6)).sum())
    m["zones_at_ceiling"] = int((np.isclose(zp["min"], ceil_[zp.index], atol=1e-6)).sum())
    m["zones_any_bound"] = int((np.isclose(zp["min"], floor[zp.index], atol=1e-6) | np.isclose(zp["max"], ceil_[zp.index], atol=1e-6)).sum())
    m["zones_above_revmax"] = int((zp["mean"] > P0 / abs(eps)).sum())
    m["zone_prices"] = ",".join(f"{v:.2f}" for v in zp["mean"].to_numpy())
    return m


RULES = ["peak_zone", "mean_zone", "peak_band", "mean_band"]
rows = []; t0 = time.time(); rep = 0
u = _block_draw(42, rep, n_seg)[seg_index]
z = {y: _observation_draw(42, rep, y, len(base)) for y in range(1, 9)}
for level in cfg["start_occupancy"]:
    for tau in cfg["block_dispersion"]:
        d0 = _scale_to_start_occupancy(base_d * np.exp(tau * u - 0.5 * tau * tau), zone_codes, priced, float(level))
        m0 = score(d0, p0, d0, -0.4)
        for sigma in cfg["observation_noise"]:
            for eps in cfg["elasticity_values"]:
                for rule in RULES:
                    panel = base.copy(); price = p0.copy(); d = d0.copy()
                    for year in range(1, 9):
                        panel["occupancy"] = np.clip(np.minimum(d, 1.0) + sigma * z[year], 0.0, 1.0)
                        panel["price_usd_per_hr"] = price
                        new = _apply_prices(review(rule, panel, tcfg), panel, price)
                        price = np.where(priced, new, price)
                        d = np.where(priced, d0 * demand_level(price, eps, p0), d0)
                        m = score(d, price, d0, eps)
                        rows.append(dict(elasticity=eps, start_occupancy=level, block_dispersion=tau, observation_noise=sigma,
                                         rule=rule, replication=rep, year=year, rev0=m0["revenue"], sc0=m0["search_cost"], **m))
print(f"replica done {time.time()-t0:.0f}s, {len(rows)} rows")
df = pd.DataFrame(rows)
df["welfare_change"] = df.cs_change + (df.revenue - df.rev0) - (df.search_cost - df.sc0)
df.to_parquet(OUT + f"rb3_rows_{TAG}.parquet")

if TAG == "default":
    tr = pd.read_parquet("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/outputs/tables/cm_sweep.parquet")
    keys = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise", "rule", "replication", "year"]
    j = df.merge(tr[keys + ["welfare_change", "cs_change", "revenue", "search_cost"]], on=keys, suffixes=("", "_tr"))
    print("VALIDATION vs tracked parquet rep 0:", len(j), "rule-years matched of", len(df),
          "; max |diff|:", {c: float(np.abs(j[c] - j[c + "_tr"]).max()) for c in ("welfare_change", "cs_change", "revenue", "search_cost")})

AX = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
y8 = df[df.year == 8]
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
for comp, ref in (("mean_zone", "peak_zone"), ("mean_band", "peak_band")):
    a = y8[y8.rule == comp].set_index(AX); b = y8[y8.rule == ref].set_index(AX).reindex(a.index)
    rev = a.revenue - b.revenue
    M = scfg.minutes_at_reference
    out = pd.DataFrame(index=a.index)
    out["c_tracked"] = (a.cs_change - b.cs_change + rev) / ((a.search_cost - b.search_cost) / M)
    out["c_cs_served"] = (a.cs_served - b.cs_served + rev) / ((a.search_cost - b.search_cost) / M)
    out["c_sc_latent_arr"] = (a.cs_change - b.cs_change + rev) / ((a.sc_latent_arr - b.sc_latent_arr) / M)
    out["c_cap095"] = (a.cs_change - b.cs_change + rev) / ((a.sc_cap95 - b.sc_cap95) / M)
    out["c_cap0999"] = (a.cs_change - b.cs_change + rev) / ((a.sc_cap999 - b.sc_cap999) / M)
    out["share_scd_from_full_blocks"] = (a.sc_from_full - b.sc_from_full) / (a.search_cost - b.search_cost)
    out["full_share_mean_rule"] = a.sc_full_share; out["full_share_peak_rule"] = b.sc_full_share
    out["mean_zones_at_floor"] = a.zones_at_floor; out["peak_zones_at_ceiling"] = b.zones_at_ceiling
    out["peak_zones_any_bound"] = b.zones_any_bound; out["mean_zones_any_bound"] = a.zones_any_bound
    out["peak_zones_above_revmax"] = b.zones_above_revmax
    out["mean_prices"] = a.zone_prices; out["peak_prices"] = b.zone_prices
    out = out.reset_index()
    out.to_csv(OUT + f"rb3_cells_{comp}_vs_{ref}_{TAG}.csv", index=False)
    cc = ["c_tracked", "c_cs_served", "c_sc_latent_arr", "c_cap095", "c_cap0999", "share_scd_from_full_blocks", "full_share_mean_rule", "full_share_peak_rule"]
    print(f"\n==== [{TAG}] {comp} vs {ref}, year 8, rep 0, 54 cells: breakeven minutes under each variant (summary over cells)")
    print(out[cc].agg(["median", "min", "max"]).T.round(3).to_string())
    print("  by start x tau (median over e x sigma):")
    print(out.groupby(["start_occupancy", "block_dispersion"])[cc[:5]].median().round(2).to_string())
    print(f"\n  (v) bounds, year 8: cells with ALL zones of the mean rule at floor: {int((out.mean_zones_at_floor == 5).sum())}; any zone at floor: {int((out.mean_zones_at_floor > 0).sum())}; "
          f"cells with >=1 zone of the peak rule at ceiling: {int((out.peak_zones_at_ceiling > 0).sum())} (zones-at-ceiling distribution {out.peak_zones_at_ceiling.value_counts().sort_index().to_dict()}); "
          f"cells with any bound binding on either rule: {int(((out.mean_zones_any_bound > 0) | (out.peak_zones_any_bound > 0)).sum())} of 54")
    print("  cells by start_occupancy with mean rule at all floors:", out[out.mean_zones_at_floor == 5].groupby("start_occupancy").size().to_dict(),
          "; peak at any ceiling by (start, e):", out[out.peak_zones_at_ceiling > 0].groupby(["start_occupancy", "elasticity"]).size().to_dict())
    print("  (iv) cells by elasticity with >=1 peak-rule zone above the revenue-max price (count, mean zones):",
          out[out.peak_zones_above_revmax > 0].groupby("elasticity").peak_zones_above_revmax.agg(["count", "mean"]).round(2).to_dict())
    print("  sample zone prices (e=-0.4, sigma=0):")
    print(out[(out.elasticity == -0.4) & (out.observation_noise == 0.0)][["start_occupancy", "block_dispersion", "mean_prices", "peak_prices", "c_tracked"]].round(2).to_string())
print(f"total {time.time()-t0:.0f}s")
