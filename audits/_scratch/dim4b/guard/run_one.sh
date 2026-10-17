#!/bin/bash
# usage: run_one.sh <variant>
source /c/projects/philly-parking-benefit-districts/.claude/worktrees/audit-2026-10-16-1cfc47/audits/_scratch/dim4b/env.sh
G=$S/guard; n=$1
export PHILLYPARKING_CONFIG_DIR=$G/$n PHILLYPARKING_DATA_DIR=$G/$n/_data PHILLYPARKING_OUTPUTS_DIR=$G/$n/_out PYTHONDONTWRITEBYTECODE=1
mkdir -p $PHILLYPARKING_DATA_DIR $PHILLYPARKING_OUTPUTS_DIR
cd $W
$PY -m pytest tests -k "not hierarchical_bayes" -q -p no:cacheprovider -rf --no-header -x --maxfail=1000 > $G/$n.pytest.txt 2>&1
echo "done $n exit $?" >> $G/$n.pytest.txt
