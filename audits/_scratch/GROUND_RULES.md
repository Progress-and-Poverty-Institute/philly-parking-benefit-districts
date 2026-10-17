# Ground rules for every audit agent (second methods review, 2026-10-16)

Read this file first. It is binding.

## Where things are
- Worktree (the code under audit, branch claude/audit-2026-10-16-1cfc47, commit b27c7b2):
  W = C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47
  Run every command from W. Never `cd` to the main checkout.
- Python: C:/Users/druss/miniconda3/python.exe (the bare `python` is a Store stub and fails).
- The package is pip-installed editable from the MAIN checkout (same commit). To make the worktree's
  code the one that imports, prefix every Python run with the environment variable
  PYTHONPATH=C:/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/src
  (in Git Bash: `PYTHONPATH=.../src C:/Users/druss/miniconda3/python.exe ...`). `project_root()` then
  resolves to W, so config comes from W/config.
- Real data (READ-ONLY, do not modify, do not copy into the worktree's tracked tree):
  C:/projects/philly-parking-benefit-districts/data/processed/segments.parquet (+ segments.meta.json,
  demand_panel.parquet, demand_panel.key) and raw layers under C:/projects/philly-parking-benefit-districts/data/raw/.
  Saved scenario results (READ-ONLY): C:/projects/philly-parking-benefit-districts/outputs/models/{status_quo,seattle,full_pbd}/
  (occupancy.parquet, prices.parquet, revenue.parquet, cruising_dwl.parquet, meta.json).
  Tracked tables/figures: W/outputs/tables/*.csv|parquet, W/outputs/figures/.
- Audit plan: W/audits/review_plan_2026-10-16.md (sections 4 and 5 are the decision inventory and the
  twelve pre-audit observations: hypotheses, not facts). Prior audit: W/audits/audit_2026-10-14.md
  (27 findings: claims to re-verify, not settled). Project mechanism notes: W/CLAUDE.md.
- Skill checklists: C:/Users/druss/.claude/skills/analysis-audit/references/{question,assumptions,inference,implementation}.md

## Stop rules (hard)
- NEVER run scripts/01_download_public_data.py (with or without --refresh) or any network fetch.
  Block the network for any run that could fetch: prefix with
  HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9
- NEVER run scripts 02, 05, 06, 07 or derive_baseline_anchors.py against the tracked tree. Any run you
  need goes into scratch: set PHILLYPARKING_DATA_DIR and PHILLYPARKING_OUTPUTS_DIR to directories under
  W/audits/_scratch/<your-wave>/. derive_baseline_anchors.py writes config/demand_baseline.yaml between
  markers: run it ONLY with --check, or on a copy of config via PHILLYPARKING_CONFIG_DIR pointing to a
  scratch copy of W/config.
- For script 02 in scratch, give the scratch data dir a `raw` junction to the real raw cache
  (PowerShell: New-Item -ItemType Junction -Path <scratch>/data/raw -Target C:/projects/philly-parking-benefit-districts/data/raw)
  AND block the network as above, so a cached layer is read and a missing one raises instead of fetching.
- The Chatman-Manville sweep only at n_replications <= 5 (and few years) if at all; read the tracked parquet otherwise.
- The fast test suite: `PYTHONPATH=W/src C:/Users/druss/miniconda3/python.exe -m pytest tests -k "not hierarchical_bayes" -q` (~60 s).
  The PyMC test takes ~8 min; do not run it unless your brief says so.
- NEVER write to W/outputs/, W/data/, W/docs/, W/paper/, W/src/, W/config/, W/scripts/, W/tests/, W/README.md,
  W/CLAUDE.md, or the main checkout. Probe scripts, scratch configs and outputs go under W/audits/_scratch/<your-wave>/.
  To test a changed constant, copy W/config to scratch, edit the copy, and point PHILLYPARKING_CONFIG_DIR at it.
- Posture: read and report. Do not fix anything.

## Evidence standard
- A check with no output has not passed: print counts, print what was found, or feed a guard the defect it
  should catch and show it firing.
- Every finding: file:line (or command + observed output), what the code does, what the argument/doc says it does,
  severity you propose (Blocking / Material / Advisory), confidence (Verified ran / Verified read / Suspected),
  a reproduction path (your probe script path under _scratch), and which plan item (A1..K3, O1..O12) or prior
  finding (1..27) it bears on.
- Append each finding to W/audits/_scratch/<your-wave>/findings.md THE MOMENT it is confirmed (numbered
  <wave>-<n>), with the probe script and its captured output saved beside it. Also record items you checked and
  found CLEAN in a "Clean" list at the end of the file (the denominator matters as much as the findings).
- Prose in README.md / docs / notebooks / Report.tex is OUT OF SCOPE except where it states a mechanism or a data
  premise the code must honour.
- Return to the orchestrator ONLY: a <=400-word summary, the numbered list of finding titles with severity and
  confidence, the clean-list count, and anything you could not finish. Full evidence stays in the file.
