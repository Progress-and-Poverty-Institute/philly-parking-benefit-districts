#!/bin/bash
G=/c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4b/guard
ls -d $G/*/ | xargs -n1 basename | grep -v '^_' | xargs -P 4 -I{} $G/run_one.sh {}
echo ALLDONE > $G/ALLDONE
