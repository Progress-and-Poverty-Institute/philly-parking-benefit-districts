import ast, json, pathlib, sys
root=pathlib.Path('.')
def modinfo(modname):
    p=root/'src'/pathlib.Path(*modname.split('.'))
    if p.with_suffix('.py').exists(): f=p.with_suffix('.py')
    elif (p/'__init__.py').exists(): f=p/'__init__.py'
    else: return None
    t=ast.parse(f.read_text(encoding='utf-8'))
    d={}
    for n in t.body:
        if isinstance(n,ast.FunctionDef):
            a=n.args
            names=[x.arg for x in a.posonlyargs+a.args+a.kwonlyargs]; req=len(a.args)-len(a.defaults); d[n.name+"__arity"]=(req,len(a.args),a.vararg is not None, [x.arg for x in a.kwonlyargs if True])
            d[n.name]=(names,a.kwarg is not None, len([x for x in a.args if True]))
        elif isinstance(n,ast.ClassDef): d[n.name]=None
    return d
def check_code(code, where, out):
    lines=[l for l in code.splitlines() if not l.strip().startswith(('%','!'))]
    try: t=ast.parse('\n'.join(lines))
    except SyntaxError as e:
        out.append((where,'SYNTAXERROR',str(e))); return
    modalias={}; fnalias={}
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('phillyparking'):
            for a in n.names:
                full=f"{n.module}.{a.name}"
                if modinfo(full) is not None: modalias[a.asname or a.name]=full
                else:
                    info=modinfo(n.module)
                    if info is None: out.append((where,'MISSING MODULE',n.module))
                    elif a.name not in info: out.append((where,'MISSING NAME',f"{n.module}.{a.name}"))
                    else: fnalias[a.asname or a.name]=(n.module,a.name)
        elif isinstance(n,ast.Import):
            for a in n.names:
                if a.name.startswith('phillyparking'): modalias[a.asname or a.name]=a.name
    for n in ast.walk(t):
        if isinstance(n,ast.Call):
            f=n.func; target=None
            if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id in modalias:
                target=(modalias[f.value.id],f.attr)
            elif isinstance(f,ast.Name) and f.id in fnalias: target=fnalias[f.id]
            if target:
                info=modinfo(target[0])
                if info is None or target[1] not in info: out.append((where,'MISSING FUNC',f"{target[0]}.{target[1]}")); continue
                sig=info[target[1]]
                if sig is None: continue
                names,haskw,_=sig
                for k in n.keywords:
                    if k.arg and k.arg not in names and not haskw: out.append((where,'BAD KWARG',f"{target[0]}.{target[1]}({k.arg}=...) ; accepts {names}"))
out=[]
for nb in sorted((root/'notebooks').glob('*.ipynb')):
    j=json.loads(nb.read_text(encoding='utf-8'))
    for i,c in enumerate(j['cells']):
        if c['cell_type']=='code': check_code(''.join(c['source']),f"{nb.name}#cell{i}",out)
import collections
print("notebook issues:",len(out))
for o in out: print(*o,sep=' | ')
print("\nby notebook:",dict(collections.Counter(o[0].split('#')[0] for o in out)))
# also build_notebooks.py: strings of code
src=(root/'scripts'/'build_notebooks.py').read_text(encoding='utf-8')
print("quarto qmd:")
for q in sorted((root/'notebooks'/'paper').glob('*.qmd')):
    txt=q.read_text(encoding='utf-8')
    print(q.name, 'python chunks:', txt.count('```{python}'))

# arity pass
def arity_pass():
    res=[]
    for nb in sorted((root/'notebooks').glob('*.ipynb')):
        j=json.loads(nb.read_text(encoding='utf-8'))
        for i,c in enumerate(j['cells']):
            if c['cell_type']!='code': continue
            code='\n'.join(l for l in ''.join(c['source']).splitlines() if not l.strip().startswith(('%','!')))
            t=ast.parse(code); modalias={}; fnalias={}
            for n in ast.walk(t):
                if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('phillyparking'):
                    for a in n.names:
                        if modinfo(f"{n.module}.{a.name}") is not None: modalias[a.asname or a.name]=f"{n.module}.{a.name}"
                        else: fnalias[a.asname or a.name]=(n.module,a.name)
                if isinstance(n,ast.ImportFrom) and n.module=='tests.fixtures': res.append((f"{nb.name}#cell{i}",'IMPORT FROM tests.fixtures',','.join(a.name for a in n.names)))
            for n in ast.walk(t):
                if isinstance(n,ast.Call):
                    f=n.func; tg=None
                    if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name) and f.value.id in modalias: tg=(modalias[f.value.id],f.attr)
                    elif isinstance(f,ast.Name) and f.id in fnalias: tg=fnalias[f.id]
                    if tg:
                        info=modinfo(tg[0]); 
                        if not info or tg[1]+'__arity' not in info: continue
                        req,tot,va,kwo=info[tg[1]+'__arity']
                        npos=len(n.args); given={k.arg for k in n.keywords}
                        names=info[tg[1]][0]
                        required=set(names[:req])
                        satisfied=set(names[:npos])|given
                        missing=required-satisfied
                        if missing or (npos>tot and not va):
                            res.append((f"{nb.name}#cell{i}",'ARITY',f"{tg[1]} given {npos} pos {sorted(given)}; signature {names} required {sorted(required)}; missing {sorted(missing)}"))
    return res
r=arity_pass()
print("arity/tests.fixtures issues:",len(r))
for x in r: print(*x,sep=' | ')
