from phillyparking.revenue.allocation import allocate
def hand(R,s,F=35e6):
    gf=min(R,F); claim=R*s; pbd=max(0,min(claim,R-gf)); sd=R-gf-pbd; return dict(gf=gf,pbd=pbd,unfunded=claim-pbd,sd=sd)
for R,s in [(140663329.77371413,0.0),(75720702.53,0.0),(81959676.06,0.30),(81959676.06,0.90),(20e6,0.30),(35e6,0.3),(35.0000001e6,0.3)]:
    a=allocate(R,s).to_dict(); h=hand(R,s)
    ok=all(abs(a[k1]-h[k2])<1e-6 for k1,k2 in (("general_fund_usd","gf"),("pbd_usd","pbd"),("pbd_unfunded_usd","unfunded"),("school_district_usd","sd")))
    print(f"R={R:>16,.2f} share={s}: GF {a['general_fund_usd']:>13,.0f} PBD {a['pbd_usd']:>13,.0f} unfunded {a['pbd_unfunded_usd']:>13,.0f} SDP {a['school_district_usd']:>13,.0f} | hand-match {ok} | conserves {abs(a['general_fund_usd']+a['pbd_usd']+a['school_district_usd']-R)<1e-6}")
