import numpy as np
from phillyparking.welfare.targeting_welfare import load_search_cost_config, expected_search_minutes, search_cost_usd
c=load_search_cost_config(); print(c)
# reference point
m=expected_search_minutes(np.array([0.95]),np.array([10.0]),c); print("minutes at (0.95,K=10):",m,"(config 5.0)")
for o in [0.5,0.7,0.85,0.9,0.95,0.99,0.999,1.0]:
    K=10; oc=min(o,0.99); pf=oc**K; hand=5.0/((0.95**10)/(1-0.95**10))*pf/(1-pf)
    got=float(expected_search_minutes(np.array([o]),np.array([float(K)]),c)[0])
    cost=float(search_cost_usd(np.array([o]),np.array([float(K)]),c)[0]); hand_cost=(o*K/1.5)*(hand/60)*20
    print(f"o={o:5.3f} K=10 minutes hand {hand:8.4f} code {got:8.4f} | $/block-hr hand {hand_cost:8.4f} code {cost:8.4f}")
for K in [1,2,5,10,20]:
    print(f"K={K:2d} minutes at o=0.7:{float(expected_search_minutes(np.array([.7]),np.array([float(K)]),c)[0]):8.4f}  o=0.85:{float(expected_search_minutes(np.array([.85]),np.array([float(K)]),c)[0]):8.4f}  o=0.95:{float(expected_search_minutes(np.array([.95]),np.array([float(K)]),c)[0]):8.4f}")
# linearity in the level
for L in [1,5,50]:
    cc=load_search_cost_config(L); print("level",L,"cost at (0.9,10):",float(search_cost_usd(np.array([.9]),np.array([10.]),cc)[0]))
# dimensional note: occupancy_cap applies to minutes but arrivals use uncapped o
print("share of the 0.99-capped value to uncapped at o=1:", float(search_cost_usd(np.array([1.0]),np.array([10.]),c)[0]))
import pandas as pd
from phillyparking.spatial.synthetic import make_synthetic_segments
s=make_synthetic_segments(n=120,seed=42); print("fixture capacity dist:",s.capacity.describe().round(1).to_dict())
