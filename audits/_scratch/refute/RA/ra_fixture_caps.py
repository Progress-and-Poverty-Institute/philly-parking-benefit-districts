"""RA probe (A2): is the o^K shape applied in the sweep to blocks like the real ones? Fixture capacity
distribution vs real priced segments; share of sweep search cost from block-hours at the cap."""
import numpy as np, pandas as pd, pyarrow.parquet as pq
from phillyparking.spatial.synthetic import make_synthetic_segments
from phillyparking.spatial.segments import load_priced_segments
MAIN = "C:/projects/philly-parking-benefit-districts"
fx = make_synthetic_segments(n=120, seed=42)
fx = fx[fx.zone_id != "other"]
print("fixture priced blocks:", len(fx), "capacity:", fx.capacity.describe().round(1).to_dict())
print("fixture share of blocks with capacity <= 3:", round(float((fx.capacity <= 3).mean()), 3))
rs = load_priced_segments(f"{MAIN}/data/processed/segments.parquet")
print("real priced blocks:", len(rs), "share capacity <= 3:", round(float((rs.capacity <= 3).mean()), 3), " share <= 5:", round(float((rs.capacity <= 5).mean()), 3), " share == 0:", round(float((rs.capacity == 0).mean()), 3))
pf = pq.ParquetFile("outputs/tables/cm_sweep.parquet")
print("sweep parquet columns:", pf.schema.names, "rows:", pf.metadata.num_rows)
