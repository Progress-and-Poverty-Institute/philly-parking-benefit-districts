import numpy as np, pandas as pd
from scipy.integrate import quad
from phillyparking.demand import response as R
from phillyparking.elasticity.scenarios import apply_elasticity
print("form in config:", R.load_demand_form())
# (a) 2-row panel: exponential form
e=-0.4
panel=pd.DataFrame({"segment_id":["a","b"],"zone_id":["ccc","ccc"],"hour_of_week":[10,10],"occupancy":[0.5,0.8],"price_usd_per_hr":[4.0,4.0]})
newp=pd.DataFrame({"zone_id":["ccc"],"hour_of_week":[10],"price_usd_per_hr":[2.5]})
out=apply_elasticity(panel,newp,e,reference_price=4.0)
hand = np.array([0.5,0.8])*np.exp(e*(2.5-4.0)/4.0)
print("apply_elasticity:",out.occupancy.values,"hand q_ref*exp(e(p-p_ref)/p_ref):",hand, "maxdiff",np.abs(out.occupancy.values-hand).max())
# reference differs from old price: posted 4, panel price 3 -> new 2.5
panel2=panel.assign(price_usd_per_hr=3.0)
out2=apply_elasticity(panel2,newp,e,reference_price=4.0)
hand2=np.array([0.5,0.8])*np.exp(e*(2.5-4.0)/4.0)/np.exp(e*(3.0-4.0)/4.0)
print("with p_old=3,p_ref=4:",out2.occupancy.values,"hand",hand2, np.abs(out2.occupancy.values-hand2).max())
# (b) cs_change vs numeric quadrature
for form in R.FORMS:
    for (p_ref,p,e) in [(4.0,2.5,-0.4),(4.0,6.0,-0.7),(2.0,0.5,-0.2),(3.5,1.0,-1.0)]:
        q_ref=10.0
        f=lambda x: q_ref*float(R.demand_level(x,e,p_ref,form))
        num=-quad(f,p_ref,p,limit=200)[0]
        ex=float(R.cs_change(q_ref,p_ref,p,e,form))
        print(f"cs_change {form:20s} p_ref={p_ref} p={p} e={e}: closed {ex:12.6f} quad {num:12.6f} diff {abs(ex-num):.2e}")
# (c) revenue_curve peak
from phillyparking.revenue.forecast import revenue_curve
segs=pd.DataFrame({"segment_id":["a","b"],"zone_id":["ccc","ccc"],"capacity":[10.0,10.0]})
bp=pd.DataFrame({"zone_id":["ccc"],"price_usd_per_hr":[4.0]})
bpanel=pd.DataFrame({"segment_id":["a","b"]*1,"hour_of_week":[10,10],"occupancy":[0.2,0.3]})  # low so clip at 1 never binds up to p_ref*? lowering price raises demand
for form in R.FORMS:
    import yaml
    # monkeypatch form
    R.load_demand_form=lambda f=form: f
    import phillyparking.revenue.forecast as F
    grid=np.linspace(0.25,4.0,376)  # multiplier of 4.0 -> price 1..16
    cur=revenue_curve(segs,bpanel,bp,-0.4,price_multiplier_grid=grid)
    # revenue_curve is limited by occupancy clip at 1 only on price cuts; with low occupancy no clip at the peak
    k=cur["revenue"].idxmax(); print(f"revenue_curve {form:20s}: argmax price {cur.loc[k,'price']:.3f}; analytic peak {R.revenue_maximising_price(-0.4,4.0,form)}")
