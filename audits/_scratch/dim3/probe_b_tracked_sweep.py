"""(2) Tracked sweep tables, read only: is "up to 19 minutes" anywhere; how many of the 52/54
'peak wins at 5 min' cells have replication ranges straddling 5; sigma=0 vs sigma=0.1 (noise bias)
on welfare_diff and breakeven; median-of-ratios vs ratio-of-medians per cell."""
import numpy as np, pandas as pd
W = "C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/outputs/tables/"
p = pd.read_csv(W + "cm_sweep_paired.csv")
raw = pd.read_parquet(W + "cm_sweep.parquet")
AX = ["elasticity", "start_occupancy", "block_dispersion", "observation_noise"]
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
same = p[p.rule.isin(["mean_zone", "mean_band", "seattle_rule"])]
print("== max breakeven_minutes_median / _max over ALL years, same-instrument pairs:")
print(same.groupby(["rule", "reference"])[["breakeven_minutes_median", "breakeven_minutes_max"]].max().round(2))
print("\n== any row (any pair, any year) with breakeven_minutes_median >= 15:")
print(p[p.breakeven_minutes_median >= 15][AX + ["rule", "reference", "year", "breakeven_minutes_median", "share_comparator_searches_more"]].to_string())
y8 = same[same.year == 8]
print("\n== year 8, same-instrument pairs: cells with median breakeven < 5 (peak wins at config level) and how many of those have replication range straddling 5:")
for (r, ref), g in y8.groupby(["rule", "reference"]):
    win = g.breakeven_minutes_median < 5
    straddle = win & (g.breakeven_minutes_max >= 5)
    lose = ~win
    lose_straddle = lose & (g.breakeven_minutes_min < 5)
    print(f"  {r} vs {ref}: cells {len(g)}, median<5: {int(win.sum())}, of which max>=5 (range straddles): {int(straddle.sum())}; "
          f"median>=5: {int(lose.sum())}, of which min<5: {int(lose_straddle.sum())}; share_welfare_better in (0,1): {int(((g.share_welfare_better > 0) & (g.share_welfare_better < 1)).sum())}")
print("\n== year 8 mean_zone vs peak_zone: sigma = 0 vs 0.1, by start x tau (median breakeven, welfare_diff_median):")
mz = y8[(y8.rule == "mean_zone")]
piv = mz.pivot_table(index=["start_occupancy", "block_dispersion", "elasticity"], columns="observation_noise",
                     values=["breakeven_minutes_median", "welfare_diff_median"])
print(piv.round(2).to_string())
# noise bias: year-8 mean price of peak_zone under sigma 0 vs 0.1 at tau = 0 (same u, so the only difference is z)
r8 = raw[(raw.year == 8)]
mp = r8.groupby(AX + ["rule"])["mean_price"].median().reset_index()
pz = mp[mp.rule.isin(["peak_zone", "mean_zone"])].pivot_table(index=["start_occupancy", "block_dispersion", "elasticity", "rule"],
                                                              columns="observation_noise", values="mean_price")
print("\n== year-8 median mean_price by sigma (peak_zone vs mean_zone):")
print(pz.round(2).to_string())
# median of per-rep breakeven vs ratio of medians
raw8 = raw[raw.year == 8]
a = raw8[raw8.rule == "mean_zone"].set_index(AX + ["replication"]); b = raw8[raw8.rule == "peak_zone"].set_index(AX + ["replication"]).reindex(a.index)
gain = (a.cs_change - b.cs_change) + (a.revenue - b.revenue); scd = (a.search_cost - b.search_cost) / 5.0
be = (gain / scd).rename("be").reset_index()
cell_med_of_ratio = be.groupby(AX).be.median()
cell_ratio_of_med = (gain.groupby(level=AX).median() / scd.groupby(level=AX).median())
cmp = pd.DataFrame({"median_of_ratios": cell_med_of_ratio, "ratio_of_medians": cell_ratio_of_med})
cmp["abs_diff"] = (cmp.median_of_ratios - cmp.ratio_of_medians).abs()
print("\n== per-cell breakeven: median of per-replication ratios (tracked) vs ratio of medians; max abs diff:", round(float(cmp.abs_diff.max()), 3))
print(cmp.sort_values("abs_diff", ascending=False).head(5).round(2).to_string())
# share of cells where the comparator is better at config level, but the sign flips somewhere in the replication range
print("\n== cells (year 8, mean_zone vs peak_zone) where share_welfare_better is strictly between 0 and 1:",
      int(((mz.share_welfare_better > 0) & (mz.share_welfare_better < 1)).sum()), "of", len(mz))
print(mz[(mz.share_welfare_better > 0) & (mz.share_welfare_better < 1)][AX + ["share_welfare_better", "breakeven_minutes_median", "breakeven_minutes_min", "breakeven_minutes_max"]].round(2).to_string())
