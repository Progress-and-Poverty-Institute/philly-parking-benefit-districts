import geopandas as gpd, numpy as np, pandas as pd
from phillyparking.demand.synthetic_baseline import baseline_anchors, _mix_weights, _kernels, _latent_intensity
from phillyparking.spatial.segments import load_priced_segments
from phillyparking._config import load_config
R="C:/projects/philly-parking-benefit-districts/data/processed"
segs=load_priced_segments(f"{R}/segments.parquet")
cfg=load_config("demand_baseline")
for aset in ("philadelphia","synthetic_fixture"):
    an=baseline_anchors(aset)
    mix=_mix_weights(pd.DataFrame(segs),temperature=an["mix_temperature"],anchors=an)
    df=pd.DataFrame(mix,columns=["office","retail","resid"]); df["zone"]=segs.zone_id.values
    print(f"\n== mix under anchor set {aset}: mean weights by zone; share of segments with dominant weight > .9")
    print(df.groupby("zone")[["office","retail","resid"]].mean().round(3).to_string())
    print("  share with any weight>0.9:",round((df[["office","retail","resid"]].max(axis=1)>0.9).mean(),3),
          "; share resid>0.9:",round((df.resid>0.9).mean(),3),"; office>0.9:",round((df.office>0.9).mean(),3),"; retail>0.9:",round((df.retail>0.9).mean(),3))
# the mix uses (log1p(x)-center) with NO division by the scale
an=baseline_anchors("philadelphia")
raw=pd.DataFrame({c:np.log1p(segs[c].astype(float))-an["covariates"][c]["center"] for c in ("jobs_within_200m","pois_count","pop_density")})
print("\nsd of the mix inputs (mix_weight * centred log1p) on philadelphia priced:",{c:round(float(an['covariates'][c]['mix_weight']*raw[c].std(ddof=0)),3) for c in raw})
fx=baseline_anchors("synthetic_fixture")
print("same sds implied by the fixture scales (fixture's own spread):",{c:round(float(fx['covariates'][c]['mix_weight']*fx['covariates'][c]['scale']),3) for c in raw})
# how many segments have pop_density z contribution beyond |3|
z=(np.log1p(segs.pop_density)-an["covariates"]["pop_density"]["center"])/an["covariates"]["pop_density"]["scale"]
print("pop_density z: share < -3:",round((z<-3).mean(),4),"; z quantiles",z.quantile([0,.05,.5,.95,1]).round(2).to_dict())
lam_noPop=sum(an['covariates'][c]['intensity_weight']*(np.log1p(segs[c])-an['covariates'][c]['center'])/an['covariates'][c]['scale'] for c in ("jobs_within_200m","pois_count","transit_trips_per_hr"))
lam_pop=an['covariates']['pop_density']['intensity_weight']*z
print("sd of lambda contributions: jobs %.3f pois %.3f pop %.3f transit %.3f"%tuple(float((an['covariates'][c]['intensity_weight']*(np.log1p(segs[c])-an['covariates'][c]['center'])/an['covariates'][c]['scale']).std(ddof=0)) for c in ("jobs_within_200m","pois_count","pop_density","transit_trips_per_hr")))
# fixture on its own anchor set
from phillyparking.spatial.synthetic import make_synthetic_segments
fx_seg=make_synthetic_segments(n=120,seed=42)
fa=baseline_anchors("synthetic_fixture")
mx=_mix_weights(pd.DataFrame(fx_seg),temperature=fa["mix_temperature"],anchors=fa)
print("\nfixture segments under fixture anchors: share with any mix weight>0.9:",round((mx.max(axis=1)>0.9).mean(),3),"; mean weights",mx.mean(axis=0).round(3).tolist())
mxn=_mix_weights(pd.DataFrame(fx_seg),temperature=fa["mix_temperature"],anchors=baseline_anchors("philadelphia"))
