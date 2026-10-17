"""(j) Does any tracked artifact rest on an unrecorded state? Config hashes now vs the metas; code
identity between 7744eeb (the recorded commit) and HEAD; why the sweep says dirty: true."""
import hashlib, json, subprocess
from pathlib import Path
W = Path("C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47")
MAIN = Path("C:/projects/philly-parking-benefit-districts")
now = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((W / "config").glob("*.yaml"))}
sweep = json.loads((W / "outputs/tables/cm_sweep.meta.json").read_text())
print("sweep meta git:", sweep["git"], "created", sweep["created_utc"])
print("config hashes equal to current W/config:", {k: now[k] == v for k, v in sweep["config_sha256"].items()})
for s in ("status_quo", "seattle", "full_pbd"):
    m = json.loads((MAIN / f"outputs/models/{s}/meta.json").read_text())["provenance"]
    print(s, "git", m["git"], "created", m["created_utc"], "hashes equal:", all(now[k] == v for k, v in m["config_sha256"].items()))
def git(*a):
    return subprocess.run(["git", *a], cwd=W, capture_output=True, text=True).stdout.strip()
print("\nfiles changed 7744eeb..HEAD under src/ config/ scripts/:", repr(git("diff", "--stat", "7744eeb", "HEAD", "--", "src", "config", "scripts")) or "(none)")
print("files changed in f779618 (the regeneration commit) outside outputs/:", repr(git("diff", "--stat", "7744eeb", "f779618", "--", ".", ":!outputs")) or "(none)")
print("tracked under outputs/ at 7744eeb:", len(git("ls-tree", "-r", "--name-only", "7744eeb", "outputs").splitlines()), "files")
print("=> git_state() reports dirty when any TRACKED file is modified (provenance.py:37 'git status --porcelain --untracked-files=no'); outputs/tables and outputs/figures are tracked, so after scripts 05 and 06 rewrote them the tree was dirty when 07 --rebuild-cm-sweep ran (18:19Z vs 17:14Z).")
