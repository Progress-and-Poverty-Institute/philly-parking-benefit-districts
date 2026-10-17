import ast, pathlib, collections, re, json
root=pathlib.Path('.')
src=root/'src'/'phillyparking'
mods={}
for p in src.rglob('*.py'):
    if p.name=='__init__.py': continue
    rel=p.relative_to(root/'src').with_suffix('')
    mods['.'.join(rel.parts)]=p
def imports(path):
    t=ast.parse(path.read_text(encoding='utf-8'))
    out=[]  # (module, name or None)
    for n in ast.walk(t):
        if isinstance(n,ast.Import):
            for a in n.names: out.append((a.name,None))
        elif isinstance(n,ast.ImportFrom):
            m=n.module or ''
            if n.level:
                # relative: resolve against package
                pkg=list(path.relative_to(root/'src').with_suffix('').parts[:-1])
                base=pkg[:len(pkg)-(n.level-1)]
                m='.'.join(base+([m] if m else []))
            for a in n.names: out.append((m,a.name))
    return out
def resolve(m,name):
    res=set()
    if m in mods: res.add(m)
    if name and f'{m}.{name}' in mods: res.add(f'{m}.{name}')
    return res
groups={'src':list(src.rglob('*.py')),'scripts':list((root/'scripts').glob('*.py')),'app':list((root/'app').rglob('*.py')),'tests':list((root/'tests').rglob('*.py'))}
callers=collections.defaultdict(lambda: collections.defaultdict(set))
for g,files in groups.items():
    for f in files:
        me=None
        if g=='src': me='.'.join(f.relative_to(root/'src').with_suffix('').parts)
        for m,name in imports(f):
            for r in resolve(m,name):
                if r!=me: callers[r][g].add(str(f.as_posix()))
lines=[]
for m in sorted(mods):
    c=callers[m]
    nontest=sorted(set().union(*(c[g] for g in ('src','scripts','app'))))
    lines.append((m,len(nontest),len(c['tests']),nontest))
for m,n,t,nt in lines:
    print(f"{m:55s} nontest={n} tests={t} {nt if n<=3 else ''}")
json.dump({m:{'nontest':nt,'tests':t} for m,n,t,nt in lines},open('audits/_scratch/dim1/modules.json','w'),default=list)
