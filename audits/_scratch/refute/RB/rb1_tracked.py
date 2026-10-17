"""RB1: read-only checks on the tracked sweep (outputs/tables/cm_sweep.parquet, _paired.csv).
B1(i): per replication-year, is the lower-statistic rule lower priced, with cs+rev gain > 0 and
search-cost diff > 0 (the claimed theorem)? B1(iv): share of peak-rule rep-years whose mean price
exceeds the exponential form's revenue peak p0/|e|. B2: per-year maxima of the cell-median breakeven
and the cells_welfare_better count. B4: ordering_violations on the tracked sweep."""
import numpy as np, pandas as pd
from phillyparking.scenarios.cm_sweep import ordering_violations, paired_table, window_dependence
W = "C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/outputs/tables/"
raw = pd.read_parquet(W + "cm_sweep.parquet")
AX = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
K = AX + ["replication", "year"]
pd.set_option("display.width", 220)
print("rows", len(raw), "reps", raw.replication.nunique(), "years", sorted(raw.year.unique()), "rules", list(raw.rule.unique()))

print("\n== B1(i): replication-year level, same-instrument pairs")
for comp, ref in (("mean_zone", "peak_zone"), ("mean_band", "peak_band"), ("seattle_rule", "peak_band")):
    a = raw[raw.rule == comp].set_index(K); b = raw[raw.rule == ref].set_index(K).reindex(a.index)
    gain = (a.cs_change - b.cs_change) + (a.revenue - b.revenue)
    scd = a.search_cost - b.search_cost
    rev = a.revenue - b.revenue
    print(f"  {comp:12s} vs {ref:9s}: rep-years {len(a)}; mean_price comp<=ref {int((a.mean_price <= b.mean_price + 1e-9).sum())}; "
          f"comp<ref strictly {int((a.mean_price < b.mean_price - 1e-9).sum())}; gain>0 {int((gain > 0).sum())}; gain<=0 {int((gain <= 0).sum())}; "
          f"scd>0 {int((scd > 1e-9).sum())}; scd==0 {int((np.abs(scd) <= 1e-9).sum())}; revenue_diff>0 (lower-priced rule earns MORE) {int((rev > 1e-9).sum())}")
    be = gain / scd.where(scd.abs() > 1e-9)
    print(f"      breakeven over rep-years: min {be.min():.3f} median {be.median():.3f} max {be.max():.3f}; NaN {int(be.isna().sum())}; <=0 {int((be <= 0).sum())}")
    # gain decomposition where revenue_diff > 0 (beyond the revenue peak): does gain stay > 0?
    m = rev > 1e-9
    if m.any():
        print(f"      where revenue_diff>0: elasticities {sorted(a.index.get_level_values('elasticity')[m].unique())}, gain min {gain[m].min():,.0f}")

print("\n== B1(iv): peak-rule rep-years with mean priced-hour price above the exponential revenue peak p0/|e| (necessary condition only; mean over zones)")
for eps in sorted(raw.elasticity.unique()):
    pk = 2.0 / abs(eps)
    for rule in ("peak_zone", "peak_band", "mean_zone"):
        s = raw[(raw.elasticity == eps) & (raw.rule == rule)]
        print(f"  e={eps:+.1f} rev-max ${pk:.2f}: {rule:9s} share rep-years mean_price > rev-max {float((s.mean_price > pk).mean()):.3f}; "
              f"mean_price median {s.mean_price.median():.2f} max {s.mean_price.max():.2f}; year-8 median {s[s.year==8].mean_price.median():.2f}")

print("\n== B2: per year, same-instrument pairs, across the 54 cells: max/median of the cell-median breakeven and cells_welfare_better")
paired = paired_table(raw)
for yr in sorted(paired.year.unique()):
    w = window_dependence(paired, year=yr)
    w = w[w.rule.isin(["mean_zone", "mean_band", "seattle_rule"])]
    print(f"  year {yr}: " + "; ".join(f"{r.rule}/{r.reference} med {r.breakeven_minutes_median_cells_median:.2f} max {r.breakeven_minutes_median_cells_max:.2f} meanbetter {r.cells_welfare_better}" for r in w.itertuples()))
y8 = paired[(paired.year == 8) & paired.rule.isin(["mean_zone", "mean_band"])]
print("  year 8 same-instrument: cells with breakeven_minutes_max (over reps) >= 15:", int((y8.breakeven_minutes_max >= 15).sum()),
      "; max over reps overall", round(float(y8.breakeven_minutes_max.max()), 2))
print("  year 8 mean_zone/peak_zone breakeven median by start x tau (median over e x sigma):")
mz = y8[y8.rule == "mean_zone"]
print(mz.groupby(["start_occupancy", "block_dispersion"]).breakeven_minutes_median.median().unstack().round(2).to_string())
print("  by elasticity x sigma:")
print(mz.groupby(["elasticity", "observation_noise"]).breakeven_minutes_median.median().unstack().round(2).to_string())
print("  mean-rule-better cells (welfare_diff_median>0) at year 8:")
print(y8[y8.welfare_diff_median > 0][AX + ["rule", "breakeven_minutes_median"]].to_string())
print("  of the 'peak better' cells at year 8 per pair, how many are sigma=0.1 cells:",
      y8[y8.welfare_diff_median < 0].groupby("rule").observation_noise.apply(lambda s: f"{int((s==0.1).sum())} of {len(s)}").to_dict())

print("\n== B4: ordering_violations on the tracked sweep")
for comp, ref in (("mean_zone", "peak_zone"), ("mean_band", "peak_band")):
    v = ordering_violations(raw, comp, ref)
    print(f"  {comp} vs {ref}: {len(v)} violating rep-years of {int((raw.rule == comp).sum())}")
    if len(v):
        v["kind"] = np.where(v.cruising_dwl_cmp < v.cruising_dwl_ref - 1e-9, "dwl", "revenue")
        print(v.groupby(["kind", "elasticity", "start_occupancy", "block_dispersion", "observation_noise"]).size().to_string())
        # the prices in those rep-years
        j = v.merge(raw[raw.rule == ref][K + ["mean_price"]], on=K).merge(raw[raw.rule == comp][K + ["mean_price"]], on=K, suffixes=("_ref", "_cmp"))
        print("    mean_price ref (peak) in violating rows: min %.2f max %.2f; cmp (mean rule): min %.2f max %.2f; rev-max at e=-0.7 is $2.86" % (
            j.mean_price_ref.min(), j.mean_price_ref.max(), j.mean_price_cmp.min(), j.mean_price_cmp.max()))
