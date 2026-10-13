#!/bin/sh
# Sauvegardes atomiques ; aucune URL ou donnée de contribution dans les journaux.
set -eu
umask 077
repertoire="${DOSSIER_SAUVEGARDES:-/sauvegardes}"
mkdir -p "$repertoire"
trap 'exit 0' TERM INT
while :; do
  fichier="$repertoire/desinfolab-$(date -u +%Y%m%dT%H%M%SZ).dump"
  pg_dump --format=custom --no-owner --no-acl --file="$fichier.part"
  pg_restore --list "$fichier.part" >/dev/null
  mv "$fichier.part" "$fichier"
  find "$repertoire" -type f -name 'desinfolab-*.dump' -mtime "+${RETENTION_JOURS:-14}" -delete
  if [ "${UNE_SEULE_FOIS:-0}" = "1" ]; then exit 0; fi
  sleep "${INTERVALLE_SAUVEGARDE:-86400}" &
  wait $!
done
