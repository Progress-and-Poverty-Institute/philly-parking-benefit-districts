"""(c)+(d) Replica of the Chatman-Manville sweep inner loop (same package functions, same draws),
N_REP replications x 54 cells x 8 years, for the four same-instrument rules. Validated against the
tracked parquet (replications 0..N_REP-1 must match), then rescored:
  CS: latent (tracked) | from block-hours with d0 > 1 only | on served demand min(q, cap)
  search cost: o^K cap 0.99 (tracked) | cap 0.95 | arrivals = latent demand | zone-pool (Arnott-Inci
  aggregate, K = 10) | the scenarios linear proxy (excess over 0.85 x 5 min x $20)
and the breakeven minutes of mean-vs-peak under each variant, per cell at year 8."""
import sys, time, dataclasses
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.demand.response import demand_level, load_demand_form
from phillyparking.pricing.priced_hours import frame_priced_mask
from phillyparking.pricing.targeting_rules import load_targeting_config, review
from phillyparking.scenarios.cm_sweep import (_block_draw, _observation_draw, _scale_to_start_occupancy,
                                               _apply_prices, WEEKS_PER_YEAR)
from phillyparking.welfare.targeting_welfare import (load_search_cost_config, search_cost_usd,
                                                     expected_search_minutes, cs_change_usd)
from phillyparking.demand.synthetic_baseline import baseline_occupancy
from phillyparking.spatial.synthetic import make_synthetic_segments

OUT = "C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim2/"
N_REP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
assert load_demand_form() == "exponential"
cfg = load_config("scenarios")["chatman_manville_sweep"]
segments = make_synthetic_segments(n=int(cfg["fixture"]["n"]), seed=int(cfg["fixture"]["seed"]))
priced_zones = {z["id"] for z in load_config("zones")["zones"]}
segments = segments.loc[segments.zone_id.isin(priced_zones)].reset_index(drop=True)
baseline = baseline_occupancy(segments, seed=42, anchor_set="synthetic_fixture")
tcfg, scfg = load_targeting_config(), load_search_cost_config()
scfg95 = dataclasses.replace(scfg, occupancy_cap=0.95)
base = baseline.drop(columns=[c for c in ("zone_id", "capacity") if c in baseline.columns]).merge(
    segments[["segment_id", "zone_id", "capacity"]], on="segment_id", how="left")
base = base.sort_values(["segment_id", "hour_of_week"]).reset_index(drop=True)
P0 = float(cfg["start_price_usd"]); base["price_usd_per_hr"] = P0
priced = frame_priced_mask(base)
seg_index = pd.factorize(base.segment_id)[0]; zone_index = pd.factorize(base.zone_id)[0]
n_seg = int(seg_index.max()) + 1
base_d = np.clip(base.occupancy.to_numpy(float), 0.01, None)
cap = base.capacity.to_numpy(float); p0 = np.full(len(base), P0)
how = base.hour_of_week.to_numpy()
zh_key = zone_index * 1000 + how
target_vacancy = 1.0 - tcfg.occ_high
VOT, DUR = scfg.value_of_time_usd_per_hr, scfg.mean_duration_hr


def pool_occ(occ):
    s = pd.DataFrame({"k": zh_key, "oc": occ * cap, "c": cap}).groupby("k").sum()
    return (s.oc / s.c).reindex(zh_key).to_numpy()


def cs_served(d0, price, eps):
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
    cs_bh = cs_change_usd(d0, p0, price, eps, cap)
    m["cs_change"] = cs_bh[priced].sum() * WEEKS_PER_YEAR
    m["cs_from_overfull_d0"] = cs_bh[priced & (d0 > 1)].sum() * WEEKS_PER_YEAR
    m["cs_served"] = cs_served(d0, price, eps)[priced].sum() * WEEKS_PER_YEAR
    m["search_cost"] = search_cost_usd(occ, cap, scfg)[priced].sum() * WEEKS_PER_YEAR
    m["sc_cap95"] = search_cost_usd(occ, cap, scfg95)[priced].sum() * WEEKS_PER_YEAR
    mins = expected_search_minutes(occ, cap, scfg)
    m["sc_latent_arrivals"] = (d * cap / DUR * mins / 60 * VOT)[priced].sum() * WEEKS_PER_YEAR
    po = pool_occ(occ)
    mins_pool = expected_search_minutes(po, np.full_like(po, scfg.reference_capacity), scfg)
    m["sc_pool"] = (occ * cap / DUR * mins_pool / 60 * VOT)[priced].sum() * WEEKS_PER_YEAR
    m["cruising_dwl"] = (np.maximum(occ * cap - (1 - target_vacancy) * cap, 0) * (5 / 60) * VOT)[priced].sum() * WEEKS_PER_YEAR
    m["share_bh_d0_gt_1"] = float((d0[priced] > 1).mean())
    m["share_bh_d_gt_1"] = float((d[priced] > 1).mean())
    m["mean_price"] = float(price[priced].mean())
    return m


RULES = ["peak_zone", "mean_zone", "peak_band", "mean_band"]
rows = []; t0 = time.time()
for rep in range(N_REP):
    u = _block_draw(42, rep, n_seg)[seg_index]
    z = {y: _observation_draw(42, rep, y, len(base)) for y in range(1, 9)}
    for level in cfg["start_occupancy"]:
        for tau in cfg["block_dispersion"]:
            d0 = _scale_to_start_occupancy(base_d * np.exp(tau * u - 0.5 * tau * tau), zone_index, priced, float(level))
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
                            rows.append(dict(elasticity=eps, start_occupancy=level, block_dispersion=tau,
                                             observation_noise=sigma, rule=rule, replication=rep, year=year,
                                             rev0=m0["revenue"], sc0=m0["search_cost"], sc0_cap95=m0["sc_cap95"],
                                             sc0_latent=m0["sc_latent_arrivals"], sc0_pool=m0["sc_pool"], dwl0=m0["cruising_dwl"], **m))
    print(f"rep {rep} done, {time.time()-t0:.0f}s, {len(rows)} rows", flush=True)
df = pd.DataFrame(rows)
df["welfare_change"] = df.cs_change + (df.revenue - df.rev0) - (df.search_cost - df.sc0)
df.to_parquet(OUT + "probe_c_rows.parquet")

tr = pd.read_parquet("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/outputs/tables/cm_sweep.parquet")
keys = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise", "rule", "replication", "year"]
j = df.merge(tr[keys + ["welfare_change", "cs_change", "revenue", "search_cost", "cruising_dwl"]], on=keys, suffixes=("", "_tr"))
print("\nVALIDATION vs tracked parquet:", len(j), "rule-years matched of", len(df))
for c in ("welfare_change", "cs_change", "revenue", "search_cost", "cruising_dwl"):
    print(f"  {c:15s} max |diff| = {np.abs(j[c] - j[c + '_tr']).max():.6g}   (max |tracked| {np.abs(j[c + '_tr']).max():.4g})")

axes = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
y8 = df[df.year == 8]


def pair(comp, ref):
    a = y8[y8.rule == comp].set_index(axes + ["replication"]); b = y8[y8.rule == ref].set_index(axes + ["replication"]).reindex(a.index)
    out = pd.DataFrame(index=a.index)
    rev = a.revenue - b.revenue
    scd = (a.search_cost - b.search_cost) / scfg.minutes_at_reference
    variants = {
        "tracked": (a.cs_change - b.cs_change + rev, scd),
        "CS_served": (a.cs_served - b.cs_served + rev, scd),
        "CS_excl_d0gt1": (a.cs_change - a.cs_from_overfull_d0 - (b.cs_change - b.cs_from_overfull_d0) + rev, scd),
        "SC_latent_arrivals": (a.cs_change - b.cs_change + rev, (a.sc_latent_arrivals - b.sc_latent_arrivals) / scfg.minutes_at_reference),
        "SC_cap095": (a.cs_change - b.cs_change + rev, (a.sc_cap95 - b.sc_cap95) / scfg.minutes_at_reference),
        "SC_zone_pool": (a.cs_change - b.cs_change + rev, (a.sc_pool - b.sc_pool) / scfg.minutes_at_reference),
        "SC_linear_proxy": (a.cs_change - b.cs_change + rev, (a.cruising_dwl - b.cruising_dwl) / 5.0),
    }
    for k, (gain, s) in variants.items():
        out[k] = np.where(np.abs(s) > 1e-9, gain / np.where(np.abs(s) > 1e-9, s, 1), np.nan)
    out["share_csdiff_d0gt1"] = (a.cs_from_overfull_d0 - b.cs_from_overfull_d0) / (a.cs_change - b.cs_change)
    out["share_bh_d0gt1"] = a.share_bh_d0_gt_1
    out["share_bh_dgt1_peak"] = b.share_bh_d_gt_1
    out["share_bh_dgt1_mean"] = a.share_bh_d_gt_1
    return out.reset_index()


pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
vcols = ["tracked", "CS_served", "CS_excl_d0gt1", "SC_latent_arrivals", "SC_cap095", "SC_zone_pool", "SC_linear_proxy"]
for comp, ref in (("mean_zone", "peak_zone"), ("mean_band", "peak_band")):
    p = pair(comp, ref)
    cell = p.groupby(axes).median(numeric_only=True).drop(columns=["replication"])
    print(f"\n==== {comp} vs {ref}, year 8: breakeven minutes per cell (median over {N_REP} reps), summarised across the 54 cells")
    print(cell.agg(["median", "min", "max"]).T.round(3).to_string())
    print("\n  share of cs_diff from block-hours with d0 > 1, and over-full shares, by start level x dispersion (median over cells):")
    print(cell.reset_index().groupby(["start_occupancy", "block_dispersion"])[["share_csdiff_d0gt1", "share_bh_d0gt1", "share_bh_dgt1_peak", "share_bh_dgt1_mean"]].median().round(3).to_string())
    print("\n  breakeven by start level x dispersion (median over the e x sigma cells):")
    print(cell.reset_index().groupby(["start_occupancy", "block_dispersion"])[vcols].median().round(2).to_string())
    print("\n  breakeven by elasticity (median over the other cells):")
    print(cell.reset_index().groupby(["elasticity"])[vcols].median().round(2).to_string())
    cell.to_csv(OUT + f"probe_c_breakeven_{comp}_vs_{ref}.csv")
print(f"\ntotal {time.time()-t0:.0f}s")
