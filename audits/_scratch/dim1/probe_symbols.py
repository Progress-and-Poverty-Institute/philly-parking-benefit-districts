import ast, pathlib, re
root=pathlib.Path('.')
nontest=[p for d in ('src','scripts','app') for p in (root/d).rglob('*.py')]
tests=[p for p in (root/'tests').rglob('*.py')]
txt={p:p.read_text(encoding='utf-8') for p in nontest+tests}
nb=(root/'scripts'/'build_notebooks.py')
res=[]
for p in (root/'src').rglob('*.py'):
    t=ast.parse(txt[p])
    for n in t.body:
        if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and not n.name.startswith('_'):
            pat=re.compile(r'\b'+re.escape(n.name)+r'\b')
            nt=0
            for q in nontest:
                c=len(pat.findall(txt[q]))
                if q==p: c-=1  # definition
                # count own-file uses too (calls inside module count as live if module live)
                nt+=max(c,0) if q!=nb else 0
            tt=sum(len(pat.findall(txt[q])) for q in tests)
            res.append((str(p.as_posix()),n.name,nt,tt))
dead=[r for r in res if r[2]==0]
print("public top-level symbols:",len(res),"with zero non-test references (incl. own-file):",len(dead))
for r in sorted(dead): print(f"{r[0]}::{r[1]} tests_refs={r[3]}")
