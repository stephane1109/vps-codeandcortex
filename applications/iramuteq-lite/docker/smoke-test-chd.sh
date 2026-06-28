#!/bin/sh
set -eu

# Test de fumee build-time :
# si une vraie CHD ne produit plus ses exports principaux,
# le build Docker doit echouer avant le deploiement Coolify.
OUTPUT_ROOT="/tmp/iramuteq-smoke"
JOB_ID="build-smoke"
JOB_ROOT="$OUTPUT_ROOT/$JOB_ID"
RESULTS_JSON="$JOB_ROOT/results.json"
STATUS_JSON="$JOB_ROOT/status.json"
STDOUT_LOG="$JOB_ROOT/stdout.log"
STDERR_LOG="$JOB_ROOT/stderr.log"

dump_debug() {
  echo "===== IRAMUTEQ SMOKE DEBUG ====="
  echo "JOB_ROOT=$JOB_ROOT"
  if [ -f "$RESULTS_JSON" ]; then
    echo "--- results.json ---"
    cat "$RESULTS_JSON"
  fi
  if [ -f "$STATUS_JSON" ]; then
    echo "--- status.json ---"
    cat "$STATUS_JSON"
  fi
  if [ -f "$STDOUT_LOG" ]; then
    echo "--- stdout.log ---"
    cat "$STDOUT_LOG"
  fi
  if [ -f "$STDERR_LOG" ]; then
    echo "--- stderr.log ---"
    cat "$STDERR_LOG"
  fi
  if [ -d "$JOB_ROOT" ]; then
    echo "--- job files ---"
    find "$JOB_ROOT" -maxdepth 3 -type f | sort
  fi
  echo "===== END SMOKE DEBUG ====="
}

rm -rf "$JOB_ROOT"

if ! python3 /app/backend/run_job.py run \
  --input /app/docker/smoke-corpus.txt \
  --config /app/docker/smoke-chd-config.json \
  --output-root "$OUTPUT_ROOT" \
  --job-id "$JOB_ID" \
  > /tmp/iramuteq-smoke-result.json; then
  echo "Le smoke test CHD a retourne un code d'erreur."
  if [ -f /tmp/iramuteq-smoke-result.json ]; then
    echo "--- cli-result.json ---"
    cat /tmp/iramuteq-smoke-result.json
  fi
  dump_debug
  exit 1
fi

for expected_file in \
  "$JOB_ROOT/exports/stats_par_classe.csv" \
  "$JOB_ROOT/exports/segments_par_classe.txt" \
  "$JOB_ROOT/exports/dendrogramme_chd.png"; do
  if [ ! -f "$expected_file" ]; then
    echo "Fichier d'export attendu manquant: $expected_file"
    if [ -f /tmp/iramuteq-smoke-result.json ]; then
      echo "--- cli-result.json ---"
      cat /tmp/iramuteq-smoke-result.json
    fi
    dump_debug
    exit 1
  fi
done

if [ -f "$JOB_ROOT/exports/segments_par_classe.html" ]; then
  :
elif [ -f "$JOB_ROOT/exports/concordancier.html" ]; then
  :
else
  echo "Aucun export HTML concordancier trouve."
  if [ -f /tmp/iramuteq-smoke-result.json ]; then
    echo "--- cli-result.json ---"
    cat /tmp/iramuteq-smoke-result.json
  fi
  dump_debug
  exit 1
fi
