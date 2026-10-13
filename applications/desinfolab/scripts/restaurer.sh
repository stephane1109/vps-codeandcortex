#!/bin/sh
# Restaurer uniquement vers une base vide explicitement désignée.
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage : sh scripts/restaurer.sh sauvegarde.dump nom_base_vide" >&2
  exit 1
fi
export PGDATABASE="$2"
nombre=$(psql -X -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if [ "$nombre" != "0" ]; then
  echo "Restauration refusée : la base cible doit être vide." >&2
  exit 1
fi
pg_restore --exit-on-error --single-transaction --no-owner --no-acl --dbname="$PGDATABASE" "$1"
