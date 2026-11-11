#!/usr/bin/env bash
# Vypíše, kolik bezprostředně předchozích běhů Kontroly objednávek po sobě selhalo (nejvýš MAX).
# Použití: prev_failures.sh MAX   (potřebuje GH_TOKEN, REPO, RUN_ID)
#
# Selhaný běh = celý běh skončil chybou, nebo v něm proběhl krok „Vyhodnocení selhání“
# (ten běží jen při selhání). Běhy, které se vůbec nespustily (startup_failure — výpadek
# GitHubu) nebo byly zrušené, se přeskakují: sérii nepřeruší, ale ani se nepočítají.
set -euo pipefail

max=$1
failed=0
for run in $(gh api "repos/${REPO}/actions/workflows/check-orders.yml/runs?status=completed&per_page=50" \
    --jq "[.workflow_runs[] | select(.id != ${RUN_ID} and .conclusion != \"startup_failure\" and .conclusion != \"cancelled\")] | .[:${max}][] | \"\(.id):\(.conclusion)\""); do
  id=${run%%:*}
  conclusion=${run#*:}
  n=$(gh api "repos/${REPO}/actions/runs/${id}/jobs" \
    --jq '[.jobs[].steps[] | select(.name == "Vyhodnocení selhání" and .conclusion != "skipped")] | length')
  if [ "$conclusion" = "failure" ] || [ "$n" -gt 0 ]; then
    failed=$((failed + 1))
  else
    break
  fi
done
echo "$failed"
