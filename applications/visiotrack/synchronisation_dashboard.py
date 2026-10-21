"""Publier l'état de configuration de VisioTrack indépendamment des sessions Streamlit.

Le dashboard lit app:visiotrack:config dans le même Redis que les tickets.
Sans utilisateur, l'app.py Streamlit ne s'exécute pas : ce petit processus
garantit que la configuration reste publiée tant que le conteneur fonctionne.
"""
from __future__ import annotations

import signal
import time

from ticket_gate import _config, _publish_runtime_config, _redis_client


_arret = False


def arreter(_signal, _frame):
    global _arret
    _arret = True


def publier() -> bool:
    """Publier la configuration si Redis est joignable, sans divulguer REDIS_URL."""
    cfg = _config("visiotrack", "VisioTrack")
    if not cfg["enabled"]:
        return True
    client, _message = _redis_client()
    if client is None:
        return False
    _publish_runtime_config(client, cfg)
    return True


def main():
    signal.signal(signal.SIGTERM, arreter)
    signal.signal(signal.SIGINT, arreter)
    dernier_etat = None
    while not _arret:
        try:
            etat = publier()
        except Exception:
            etat = False
        if etat != dernier_etat:
            print(
                "[VisioTrack] Synchronisation Redis " + (
                    "active." if etat else "indisponible (vérifier REDIS_URL commune au dashboard)."
                ),
                flush=True,
            )
            dernier_etat = etat
        for _ in range(60):
            if _arret:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
