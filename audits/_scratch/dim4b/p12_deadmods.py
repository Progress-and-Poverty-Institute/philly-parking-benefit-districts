import ast, re
from pathlib import Path
W=Path(".")
mods={}
for p in (W/"src/phillyparking").rglob("*.py"):
    rel=p.relative_to(W/"src").with_suffix("")
    name=".".join(rel.parts)
    if name.endswith(".__init__"): name=name[:-9]
    mods[name]=p
files={"src":list((W/"src").rglob("*.py")),"scripts":list((W/"scripts").glob("*.py")),"app":list((W/"app").rglob("*.py")),"tests":list((W/"tests").rglob("*.py"))}
imports={}   # file -> set of (module, names)
def scan(f):
    out=set()
    try: tree=ast.parse(f.read_text(encoding="utf-8"))
    except Exception as e: return out
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            for a in n.names: out.add((a.name,None))
        elif isinstance(n,ast.ImportFrom):
            if n.module and n.level==0:
                for a in n.names: out.add((n.module,a.name))
    return out
imp={f:scan(f) for fs in files.values() for f in fs}
def users(mod):
    res={k:[] for k in files}
    for kind,fs in files.items():
        for f in fs:
            fm=".".join(f.relative_to(W/"src").with_suffix("").parts) if kind=="src" else None
            if fm==mod: continue
            for (m,name) in imp[f]:
                if m==mod or (name and f"{m}.{name}"==mod):
                    res[kind].append(str(f).replace("\\","/")); break
    return res
targets=["phillyparking.welfare.consumer_surplus","phillyparking.pricing.optimizer","phillyparking.validation.calibration","phillyparking.validation.crossval","phillyparking.validation.manual_counts","phillyparking.demand.ml_occupancy","phillyparking.demand.occupancy_estimator","phillyparking.demand.features","phillyparking.io.ppa_stub","phillyparking.elasticity.scenarios","phillyparking.viz.maps","phillyparking.viz.charts","phillyparking.viz.tables","phillyparking.viz.report_figures","phillyparking.welfare.incidence","phillyparking.revenue.forecast","phillyparking.elasticity.priors","phillyparking.elasticity.hierarchical_bayes","phillyparking.pricing.arnott_inci"]
for t in targets:
    u=users(t); print(f"{t}\n   src: {u['src']}\n   scripts: {u['scripts']}\n   app: {u['app']}\n   tests: {[x.split('/')[-1] for x in u['tests']]}")
