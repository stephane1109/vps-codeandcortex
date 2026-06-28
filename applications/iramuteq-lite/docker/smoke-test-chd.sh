#!/bin/sh
set -eu

# Test de fumee build-time :
# si une vraie CHD ne produit plus ses exports principaux,
# le build Docker doit echouer avant le deploiement Coolify.
OUTPUT_ROOT="/tmp/iramuteq-smoke"
JOB_ID="build-smoke"

rm -rf "$OUTPUT_ROOT/$JOB_ID"

python3 /app/backend/run_job.py run \
  --input /app/docker/smoke-corpus.txt \
  --config /app/docker/smoke-chd-config.json \
  --output-root "$OUTPUT_ROOT" \
  --job-id "$JOB_ID" \
  >/tmp/iramuteq-smoke-result.json

test -f "$OUTPUT_ROOT/$JOB_ID/exports/stats_par_classe.csv"
test -f "$OUTPUT_ROOT/$JOB_ID/exports/segments_par_classe.txt"
test -f "$OUTPUT_ROOT/$JOB_ID/exports/dendrogramme_chd.png"
test -f "$OUTPUT_ROOT/$JOB_ID/exports/segments_par_classe.html"
