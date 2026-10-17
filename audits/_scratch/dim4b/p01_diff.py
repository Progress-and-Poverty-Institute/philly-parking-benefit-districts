import pandas as pd, numpy as np, json, os, hashlib
from pathlib import Path
W=Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47"); S=W/"audits/_scratch/dim4b"
SAVED=Path("C:/projects/philly-parking-benefit-districts/outputs/models")
for name in ["comparison_table.csv","scenario_ranges.csv","scenario_runs.csv"]:
    a = pd.read_csv(S/"outputs/models"/name); b = pd.read_csv(W/"outputs/tables"/name); c = pd.read_csv(SAVED.parent/"models"/name)
    for lab,x in (("tracked",b),("saved-main",c)):
        assert list(a.columns)==list(x.columns), (name, lab, "cols differ")
        assert a.shape==x.shape,(name,lab,a.shape,x.shape)
        num = a.select_dtypes("number").columns
        mx = float((a[num]-x[num]).abs().max().max()) if len(num) else 0
        nonnum_eq = a.drop(columns=num).equals(x.drop(columns=num))
        print(f"{name} scratch vs {lab}: shape {a.shape}, max abs numeric diff {mx:.3g}, nonnumeric equal {nonnum_eq}; cells compared {a.size}")
    print(" raw bytes sha equal scratch/tracked:", hashlib.sha256((S/'outputs/models'/name).read_bytes()).hexdigest()[:12], hashlib.sha256((W/'outputs/tables'/name).read_bytes()).hexdigest()[:12])
# per-scenario parquet equality scratch vs saved
for sc in ["status_quo","seattle","full_pbd"]:
    for f in ["occupancy","prices","revenue","cruising_dwl"]:
        a=pd.read_parquet(S/"outputs/models"/sc/f"{f}.parquet"); b=pd.read_parquet(SAVED/sc/f"{f}.parquet")
        eq = a.shape==b.shape and all((np.allclose(a[c],b[c],rtol=0,atol=1e-12) if a[c].dtype.kind in "fi" else (a[c]==b[c]).all()) for c in a.columns)
        print(sc,f,a.shape,"identical" if eq else "DIFFERS")
    ma=json.load(open(S/"outputs/models"/sc/"meta.json")); mb=json.load(open(SAVED/sc/"meta.json"))
    print(sc,"meta alloc equal:",ma["allocation"]==mb["allocation"],"cs equal",ma["cs_change_total"]==mb["cs_change_total"],"diagnostics equal",ma["diagnostics"]==mb["diagnostics"],
          "| saved commit",mb["provenance"]["git"],"| scratch commit",ma["provenance"]["git"])
    print("   config hashes equal:", ma["provenance"]["config_sha256"]==mb["provenance"]["config_sha256"])
