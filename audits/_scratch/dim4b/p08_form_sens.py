import sys, pandas as pd, numpy as np
from phillyparking.scenarios.cm_sweep import chatman_manville_sweep, paired_table
sw=chatman_manville_sweep(n_replications=2, rolls_forward_years=3, observation_noise=[0.1], block_dispersion=[0.3])
sw.to_parquet(sys.argv[1])
