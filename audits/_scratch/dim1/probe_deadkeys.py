import yaml, pathlib, re, collections
root=pathlib.Path('.')
nontest=[p for d in ('src','scripts','app') for p in (root/d).rglob('*.py')]
tests=list((root/'tests').rglob('*.py'))
T={p:p.read_text(encoding='utf-8') for p in nontest+tests}
def leaves(o,path=()):
    if isinstance(o,dict):
        for k,v in o.items(): yield from leaves(v,path+(str(k),))
    elif isinstance(o,list) and o and all(isinstance(x,dict) for x in o):
        for i,x in enumerate(o): yield from leaves(x,path+(f"[{x.get('id',i)}]",))
    else: yield path,o
for cfg in ['zones','demand_baseline','pricing_rules','allocation','elasticity_priors','scenarios','ppa_ingest']:
    d=yaml.safe_load((root/'config'/f'{cfg}.yaml').read_text(encoding='utf-8'))
    seen=collections.OrderedDict()
    for path,v in leaves(d):
        key=[p for p in path if not p.startswith('[')][-1]
        top=[p for p in path if not p.startswith('[')]
        seen[tuple(top)]=(key,v)
    print("=====",cfg)
    for top,(key,v) in seen.items():
        pat=re.compile(r'\b'+re.escape(key)+r'\b')
        nt=[str(p.as_posix()) for p in nontest if pat.search(T[p])]
        tt=[p.name for p in tests if pat.search(T[p])]
        print(f"{'.'.join(top):70s} nontest={len(nt)} tests={len(tt)}  {','.join(sorted(set(x.split('/')[-1] for x in nt)))[:90]}")
