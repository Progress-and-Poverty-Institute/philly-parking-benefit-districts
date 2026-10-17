"""Count notebook-builder snippets (scripts/build_notebooks.py) whose calls do not bind to the current signatures."""
import re, inspect, importlib, ast
src=open("scripts/build_notebooks.py",encoding="utf-8").read()
# gather imported names per module from import strings
imports=re.findall(r'from (phillyparking[\w\.]*) import ([\w, ]+)',src)
names={}
for mod,lst in imports:
    for n in [x.strip() for x in lst.split(",") if x.strip()]:
        try:
            m=importlib.import_module(mod); names[n]=getattr(m,n)
        except Exception as e: names[n]=f"IMPORT-FAIL {type(e).__name__}"
bad=[];ok=0;fail_imports=[n for n,v in names.items() if isinstance(v,str)]
# crude: find call expressions name(...) in the source text and try to bind
for mm in re.finditer(r'\b(\w+)\(([^()]*(?:\([^()]*\)[^()]*)*)\)',src):
    n,args=mm.group(1),mm.group(2)
    if n in names and callable(names[n]):
        try:
            call=ast.parse(f"{n}({args.replace(chr(92)+'n','')})",mode="eval").body
        except Exception: continue
        pos=[None]*len(call.args); kw={k.arg:None for k in call.keywords if k.arg}
        try:
            inspect.signature(names[n]).bind_partial(*pos,**kw); ok+=1
        except TypeError as e: bad.append((n,args[:60],str(e)[:70]))
print("imports that fail:",fail_imports)
print("calls that bind:",ok,"| calls that do not bind to the current signature:",len(bad))
for b in bad: print("  ",b)
