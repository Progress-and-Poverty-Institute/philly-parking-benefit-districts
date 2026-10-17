"""(e) The exponential form's extrapolation and the per-zone anchoring of the same prior."""
import numpy as np, pandas as pd
from phillyparking._config import load_config
from phillyparking.demand.response import demand_level, elasticity_at, revenue_maximising_price

print("=== Sweep: every zone anchored at $2; peak rules reach ~$4.80 (dim4b). What the law says there:")
rows = []
for e in (-0.2, -0.4, -0.7):
    for p in (2.5, 3.0, 4.0, 4.8):
        rows.append(dict(e=e, price=p,
            elasticity_at_price=round(float(elasticity_at(p, e, 2.0, "exponential")), 2),
            q_ratio_exp=round(float(demand_level(p, e, 2.0, "exponential")), 3),
            q_ratio_const=round(float(demand_level(p, e, 2.0, "constant_elasticity")), 3),
            q_ratio_lin=round(float(demand_level(p, e, 2.0, "linear")), 3),
            rev_ratio_exp=round(float(p / 2.0 * demand_level(p, e, 2.0, "exponential")), 3),
            rev_peak_price=round(revenue_maximising_price(e, 2.0, "exponential"), 2)))
print(pd.DataFrame(rows).to_string(index=False))

print("\n=== Scenario pipeline: the same e = -0.4 is the elasticity at every zone's posted rate (zones.yaml), while the form says elasticity rises in proportion to price.")
zones = load_config("zones")["zones"]
for z in zones:
    pref = float(z["current_rate_usd_per_hr"])
    # One law anchored at the cheapest zone's rate ($1.50, e=-0.4) would imply this elasticity at pref:
    implied = -0.4 * pref / 1.5
    print(f"{z['id']:13s} posted {pref:4.2f}: config elasticity at posted rate -0.40; a single exponential law anchored at $1.50 would give {implied:.2f}; q(0)/q(posted) = {np.exp(0.4):.2f}; q($0.50)/q(posted) = {float(demand_level(0.5, -0.4, pref)):.2f}")

print("\n=== Semi-log justification: logit with utility linear in price gives elasticity beta p (1 - s); the pure exponential is the s -> 0 limit. At share s the elasticity rises slower than e p / p_ref by the factor (1 - s)/(1 - s_ref).")
print("research note 5.6 premise: 'Central (E = -0.4): revenue rises monotonically through plausible price ranges' -- under the configured form revenue peaks at p_ref/|e|: ccc $10.00, sweep $5.00 (e=-0.4) / $2.86 (e=-0.7).")
