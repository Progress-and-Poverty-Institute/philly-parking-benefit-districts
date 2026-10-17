#!/bin/bash
cd "/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47"
export PYTHONPATH="/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/src"
for n in baseline msh09 nocurb peak099 ctr1 classes23 buf50 temp5 lowpeak50 ihigh w_jobs ccc6 hrs; do
  PHILLYPARKING_CONFIG_DIR="/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/inject/cfg_$n" C:/Users/druss/miniconda3/python.exe -m pytest tests -k "not hierarchical_bayes" -q --tb=no -p no:cacheprovider -rf > "/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/inject/out_$n.txt" 2>&1
  echo "$n done exit $?" >> "/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/inject/progress.txt"
done
echo ALLDONE >> "/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4a/inject/progress.txt"
