"""RA probe (A2): the project's own two cruising models side by side on the sweep fixture:
cm_sweep.parquet carries both search_cost (o^K) and cruising_dwl (proxy) per rule-cell-year."""
import pandas as pd, numpy as np
d = pd.read_parquet("outputs/tables/cm_sweep.parquet", columns=["elasticity","start_occupancy","block_dispersion","observation_noise","rule","replication","year","search_cost","cruising_dwl","share_block_hours_above_high","revenue","cs_change","welfare_change"])
last = d[d.year == d.year.max()]
g = last.groupby(["start_occupancy","rule"]).agg(search=("search_cost","median"), proxy=("cruising_dwl","median"), above=("share_block_hours_above_high","median"), rev=("revenue","median"), cs=("cs_change","median"), w=("welfare_change","median"))
g["ratio"] = g.search / g.proxy.replace(0, np.nan)
pd.set_option("display.width", 200)
print("final-year medians over cells and replications, by start occupancy and rule ($):")
print(g.round(1).to_string())
print("\noverall: search/proxy ratio median", round(float((last.search_cost / last.cruising_dwl.replace(0, np.nan)).median()), 1), " p10/p90", (last.search_cost / last.cruising_dwl.replace(0, np.nan)).quantile([.1,.9]).round(1).tolist())
