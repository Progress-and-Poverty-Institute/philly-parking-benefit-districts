import numpy as np, pandas as pd
from phillyparking.elasticity.identification import identification_table, check_identification, IdentificationError
hrs=np.arange(8,20)
def cells(spec):
    rows=[]
    for z,prices in spec.items():
        for per,p in enumerate(prices):
            for h in hrs: rows.append((z,f"P{per}",h,p))
    return pd.DataFrame(rows,columns=["zone_id","period","hour_of_week","price_usd_per_hr"])
cases={
 "(a) one period, 3 zones, one price each": cells({"ccc":[4.0],"cca":[3.5],"ucity":[2.0]}),
 "(b) two periods, two zones both change, no control": cells({"ccc":[3.0,4.0],"cca":[2.5,3.5]}),
 "(b2) two periods, two zones change by same ratio": cells({"ccc":[2.0,4.0],"cca":[1.75,3.5]}),
 "(c) two periods, one changed, one control": cells({"ccc":[3.0,4.0],"ucity":[2.0,2.0]}),
 "(c2) the stub-like: ccc and cca change, ucity control": cells({"ccc":[3.0,4.0],"cca":[2.5,3.5],"ucity":[2.0,2.0]}),
 "(d) three periods, two zones changing differently, no control": cells({"ccc":[3.0,4.0,4.5],"cca":[2.5,3.5,3.6]}),
}
for k,df in cases.items():
    t=identification_table(df)
    try:
        check_identification(df); verdict="passes (>=1 zone identified)"
    except IdentificationError as e: verdict="RAISES: "+str(e)[:60]
    print(k,"\n   ",t.assign(ident=t.identified).set_index('zone_id')[['n_prices','identified']].to_dict('index'),"\n    check_identification:",verdict)
# also: panel with period column missing -> falls back (no period effect)
df=cases["(a) one period, 3 zones, one price each"].drop(columns="period"); print("(e) no period col:",identification_table(df).identified.tolist())
