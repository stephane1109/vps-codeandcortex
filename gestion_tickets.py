from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - dépend de l'environnement local
    redis = None


CAPACITE_SERVEUR_DEFAUT = 6
DUREE_TICKET_DEFAUT = 3600
MAX_ACTIVE_DEFAUT = 3
MAX_FILE_ATTENTE_DEFAUT = 20
APPLICATION_PAR_DEFAUT = "application"
APPLICATIONS_TICKETS_JSON = "APPLICATIONS_TICKETS_JSON"

# #### NOMS EXACTS DES APPLICATIONS
# Ici on utilise uniquement les noms exacts des dossiers du dépôt GitHub
# `applications/`. Aucun alias, aucune faute tolérée, aucune normalisation
# implicite ne doit transformer le nom d'une application.
APPLICATIONS_PAR_DEFAUT = {
    "europresse-to-iramuteq": {
        "label": "Europresse → IRaMuTeQ",
        "max_active": 2,
        "cout": 1,
    },
    "extraction-multimedia": {
        "label": "Extraction Multimédia",
        "max_active": 2,
        "cout": 2,
    },
    "extract_comments_youtube": {
        "label": "Extraction YouTube",
        "max_active": 2,
        "cout": 2,
    },
    "scraping_reddit": {
        "label": "Scraping Reddit",
        "max_active": 3,
        "cout": 1,
    },
    "Extraction_infos_YouTube": {
        "label": "Réseau de vidéo YouTube",
        "max_active": 2,
        "cout": 1,
    },
    "analyse_cooccurrences": {
        "label": "Cooccurrences",
        "max_active": 2,
        "cout": 2,
    },
    "symbolic_connectors": {
        "label": "Symbolic Connectors",
        "max_active": 1,
        "cout": 4,
    },
    "mp3_to_text": {
        "label": "MP3 to Text",
        "max_active": 1,
        "cout": 4,
    },
    "vecteur-emotionnel": {
        "label": "Vecteur émotionnel",
        "max_active": 1,
        "cout": 4,
    },
    "iramuteq-lite": {
        "label": "IRaMuTeQ Lite",
        "max_active": 1,
        "cout": 4,
    },
    "stopmotion_opticalflow": {
        "label": "StopMotion",
        "max_active": 1,
        "cout": 4,
    },
    "Analyses_multi_modales": {
        "label": "Analyses multi-modales",
        "max_active": 1,
        "cout": 4,
    },
    "divergence-jensen-shannon": {
        "label": "Divergence Jensen-Shannon",
        "max_active": 1,
        "cout": 4,
    },
}


def connecter_redis():
    """Créer une connexion Redis à partir de la variable d’environnement REDIS_URL."""
    if redis is None:
        raise RuntimeError("Le paquet Python 'redis' doit être installé pour utiliser la file d'attente.")
    # #### URL REDIS
    # Priorite :
    # 1. REDIS_URL
    # 2. APP_TICKET_DEFAULT_REDIS_URL
    # 3. valeur par defaut Coolify : redis://redis:6379/0
    url_redis = (
        os.getenv("REDIS_URL", "").strip()
        or os.getenv("APP_TICKET_DEFAULT_REDIS_URL", "redis://redis:6379/0").strip()
    )
    client = redis.from_url(url_redis, decode_responses=True)
    client.ping()
    return client


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def normaliser_identifiant_application(application_id: str | None) -> str:
    # #### NOM STRICT
    # On conserve uniquement le nom exact fourni par l'application ou par le
    # dashboard. Aucun alias n'est appliqué ici.
    value = (application_id or os.getenv("NOM_APPLICATION") or APPLICATION_PAR_DEFAUT).strip()
    return value or APPLICATION_PAR_DEFAUT


def _configuration_globale() -> dict[str, int]:
    return {
        "capacite_serveur": _env_int("CAPACITE_SERVEUR", CAPACITE_SERVEUR_DEFAUT),
        "duree_ticket": _env_int("DUREE_TICKET", DUREE_TICKET_DEFAUT),
        "max_active_defaut": _env_int("MAX_ACTIVE_PAR_APPLICATION", MAX_ACTIVE_DEFAUT),
        "max_file_attente_defaut": _env_int("MAX_FILE_ATTENTE_PAR_APPLICATION", MAX_FILE_ATTENTE_DEFAUT),
    }


def _configuration_legacy() -> dict[str, dict[str, Any]]:
    if not os.getenv("NOM_APPLICATION", "").strip():
        return {}
    application_id = normaliser_identifiant_application(os.getenv("NOM_APPLICATION"))
    return {
        application_id: {
            "label": os.getenv("NOM_APPLICATION", application_id),
            "cout": _env_int("COUT_APPLICATION", 1),
            "max_active": _env_int("MAX_ACTIVE_APPLICATION", MAX_ACTIVE_DEFAUT),
            "max_file_attente": _env_int("MAX_FILE_ATTENTE_APPLICATION", MAX_FILE_ATTENTE_DEFAUT),
            "duree_ticket": _env_int("DUREE_TICKET", DUREE_TICKET_DEFAUT),
        }
    }


def _fusionner_configuration_application(
    application_id: str,
    configuration_brute: dict[str, Any] | None,
    configuration_globale: dict[str, int],
) -> dict[str, Any]:
    brute = configuration_brute or {}
    return {
        "application_id": application_id,
        "label": str(brute.get("label") or application_id),
        "cout": max(0, int(brute.get("cout", 1))),
        "max_active": max(
            1,
            int(brute.get("max_active", configuration_globale["max_active_defaut"])),
        ),
        "max_file_attente": max(
            0,
            int(brute.get("max_file_attente", configuration_globale["max_file_attente_defaut"])),
        ),
        "duree_ticket": max(
            60,
            int(brute.get("duree_ticket", configuration_globale["duree_ticket"])),
        ),
    }


def charger_configurations_applications() -> dict[str, dict[str, Any]]:
    """Construire la configuration multi-app à partir des variables d’environnement."""
    configuration_globale = _configuration_globale()
    configurations: dict[str, dict[str, Any]] = {}

    for application_id, configuration in APPLICATIONS_PAR_DEFAUT.items():
        slug = normaliser_identifiant_application(application_id)
        configurations[slug] = _fusionner_configuration_application(slug, configuration, configuration_globale)

    for application_id, configuration in _configuration_legacy().items():
        slug = normaliser_identifiant_application(application_id)
        configurations[slug] = _fusionner_configuration_application(slug, configuration, configuration_globale)

    contenu_json = os.getenv(APPLICATIONS_TICKETS_JSON, "").strip()
    if contenu_json:
        donnees = json.loads(contenu_json)
        if not isinstance(donnees, dict):
            raise ValueError(f"{APPLICATIONS_TICKETS_JSON} doit contenir un objet JSON.")
        for application_id, configuration in donnees.items():
            if not isinstance(configuration, dict):
                raise ValueError(
                    f"{APPLICATIONS_TICKETS_JSON}.{application_id} doit contenir un objet JSON."
                )
            slug = normaliser_identifiant_application(application_id)
            configurations[slug] = _fusionner_configuration_application(
                slug,
                configuration,
                configuration_globale,
            )

    return configurations


def lire_configuration_tickets(application_id: str | None = None) -> dict[str, Any]:
    """Lire la configuration globale et celle d'une application donnée."""
    configuration_globale = _configuration_globale()
    applications = charger_configurations_applications()
    identifiant_application = normaliser_identifiant_application(application_id)
    application = applications.get(identifiant_application)
    if application is None:
        application = _fusionner_configuration_application(
            identifiant_application,
            {"label": identifiant_application},
            configuration_globale,
        )
        applications[identifiant_application] = application

    return {
        "capacite_serveur": configuration_globale["capacite_serveur"],
        "duree_ticket": configuration_globale["duree_ticket"],
        "applications": applications,
        **application,
    }


def cles_redis_application(application_id: str) -> dict[str, str]:
    return {
        "tickets_actifs": f"app:{application_id}:tickets:actifs",
        "tickets_attente": f"app:{application_id}:tickets:attente",
    }


def cle_ticket(identifiant_ticket: str) -> str:
    return f"ticket:{identifiant_ticket}"


def cle_session(application_id: str, identifiant_session: str) -> str:
    return f"session:{application_id}:{identifiant_session}:ticket"


def _zset_actifs_globale() -> str:
    return "tickets:global:actifs"


def _application_ids_configures() -> list[str]:
    return sorted(charger_configurations_applications().keys())


def _zscore(client_redis, key: str, member: str) -> float:
    score = client_redis.zscore(key, member)
    return float(score if score is not None else time.time())


def _lister_tickets(client_redis, key: str) -> list[str]:
    return [str(item) for item in client_redis.zrange(key, 0, -1)]


def nettoyer_tickets_expires(client_redis, application_id: str | None = None):
    """Supprimer des index les tickets dont la clé Redis a expiré."""
    applications = [normaliser_identifiant_application(application_id)] if application_id else _application_ids_configures()

    for identifiant_application in applications:
        cles = cles_redis_application(identifiant_application)
        for key in (cles["tickets_actifs"], cles["tickets_attente"]):
            for identifiant_ticket in _lister_tickets(client_redis, key):
                if not client_redis.exists(cle_ticket(identifiant_ticket)):
                    client_redis.zrem(key, identifiant_ticket)

    for identifiant_ticket in _lister_tickets(client_redis, _zset_actifs_globale()):
        if not client_redis.exists(cle_ticket(identifiant_ticket)):
            client_redis.zrem(_zset_actifs_globale(), identifiant_ticket)


def calculer_charge_active(client_redis):
    """Calculer la charge totale des tickets actifs sur tout le VPS."""
    nettoyer_tickets_expires(client_redis)
    charge = 0
    for identifiant_ticket in _lister_tickets(client_redis, _zset_actifs_globale()):
        donnees = client_redis.hgetall(cle_ticket(identifiant_ticket))
        if donnees:
            charge += int(donnees.get("cout_application", 1))
    return charge


def compter_tickets_actifs_application(client_redis, application_id: str) -> int:
    nettoyer_tickets_expires(client_redis, application_id)
    return client_redis.zcard(cles_redis_application(application_id)["tickets_actifs"])


def compter_tickets_attente_application(client_redis, application_id: str) -> int:
    nettoyer_tickets_expires(client_redis, application_id)
    return client_redis.zcard(cles_redis_application(application_id)["tickets_attente"])


def compter_tickets_actifs_total(client_redis) -> int:
    nettoyer_tickets_expires(client_redis)
    return client_redis.zcard(_zset_actifs_globale())


def compter_tickets_attente_total(client_redis) -> int:
    nettoyer_tickets_expires(client_redis)
    total = 0
    for application_id in _application_ids_configures():
        total += compter_tickets_attente_application(client_redis, application_id)
    return total


def calculer_position_attente(client_redis, identifiant_ticket: str, application_id: str | None = None):
    """Calculer la position d’un ticket dans la file d’attente d'une application."""
    identifiant_application = normaliser_identifiant_application(application_id)
    tickets_attente = _lister_tickets(client_redis, cles_redis_application(identifiant_application)["tickets_attente"])

    if identifiant_ticket not in tickets_attente:
        return None

    return tickets_attente.index(identifiant_ticket) + 1


def _statut_application_depuis_compteurs(active: int, max_active: int, queued: int) -> tuple[str, str]:
    if queued > 0:
        return "queued", "File d'attente"
    if active <= 0:
        return "available", "Libre"
    if active >= max_active:
        return "busy", "Occupée"
    return "busy", "En cours"


def _resume_ticket(client_redis, identifiant_ticket: str, application_id: str) -> dict[str, Any]:
    configuration = lire_configuration_tickets(application_id)
    donnees = client_redis.hgetall(cle_ticket(identifiant_ticket))
    position = calculer_position_attente(client_redis, identifiant_ticket, application_id)
    active = compter_tickets_actifs_application(client_redis, application_id)
    queued = compter_tickets_attente_application(client_redis, application_id)
    state, label = _statut_application_depuis_compteurs(active, configuration["max_active"], queued)

    return {
        "identifiant_ticket": identifiant_ticket,
        "statut": donnees.get("statut", "inconnu"),
        "position": position,
        "charge_active": calculer_charge_active(client_redis),
        "capacite_serveur": configuration["capacite_serveur"],
        "application_id": application_id,
        "application_label": configuration["label"],
        "active": active,
        "max_active": configuration["max_active"],
        "queued": queued,
        "state": state,
        "state_label": label,
    }


def _candidats_attente(client_redis) -> list[tuple[float, str, str]]:
    candidats: list[tuple[float, str, str]] = []
    for application_id in _application_ids_configures():
        key = cles_redis_application(application_id)["tickets_attente"]
        for identifiant_ticket in _lister_tickets(client_redis, key):
            candidats.append((_zscore(client_redis, key, identifiant_ticket), application_id, identifiant_ticket))
    candidats.sort(key=lambda item: item[0])
    return candidats


def promouvoir_tickets_en_attente(client_redis, capacite_serveur: int | None = None):
    """Promouvoir les premiers tickets en attente si les capacités le permettent."""
    configuration_globale = _configuration_globale()
    capacite = capacite_serveur if capacite_serveur is not None else configuration_globale["capacite_serveur"]
    nettoyer_tickets_expires(client_redis)

    for _score, application_id, identifiant_ticket in _candidats_attente(client_redis):
        donnees = client_redis.hgetall(cle_ticket(identifiant_ticket))
        if not donnees:
            client_redis.zrem(cles_redis_application(application_id)["tickets_attente"], identifiant_ticket)
            continue

        configuration = lire_configuration_tickets(application_id)
        cout_application = int(donnees.get("cout_application", configuration["cout"]))
        charge_active = calculer_charge_active(client_redis)
        actifs_application = compter_tickets_actifs_application(client_redis, application_id)

        if actifs_application >= configuration["max_active"]:
            continue

        if charge_active + cout_application > capacite:
            continue

        client_redis.hset(cle_ticket(identifiant_ticket), "statut", "actif")
        client_redis.zrem(cles_redis_application(application_id)["tickets_attente"], identifiant_ticket)
        client_redis.zadd(cles_redis_application(application_id)["tickets_actifs"], {identifiant_ticket: time.time()})
        client_redis.zadd(_zset_actifs_globale(), {identifiant_ticket: time.time()})


def creer_ou_recuperer_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    """Créer un ticket pour une session ou récupérer le ticket déjà existant."""
    configuration = lire_configuration_tickets(application_id)
    identifiant_application = configuration["application_id"]
    cout_application = configuration["cout"]
    capacite_serveur = configuration["capacite_serveur"]
    duree_ticket = configuration["duree_ticket"]
    max_active = configuration["max_active"]
    max_file_attente = configuration["max_file_attente"]

    nettoyer_tickets_expires(client_redis)
    promouvoir_tickets_en_attente(client_redis, capacite_serveur)

    cle_ticket_session = cle_session(identifiant_application, identifiant_session)
    ticket_existant = client_redis.get(cle_ticket_session)

    if ticket_existant and client_redis.exists(cle_ticket(ticket_existant)):
        client_redis.expire(cle_ticket(ticket_existant), duree_ticket)
        client_redis.expire(cle_ticket_session, duree_ticket)
        return _resume_ticket(client_redis, ticket_existant, identifiant_application)

    if ticket_existant:
        client_redis.delete(cle_ticket_session)

    identifiant_ticket = str(uuid.uuid4())
    charge_active = calculer_charge_active(client_redis)
    actifs_application = compter_tickets_actifs_application(client_redis, identifiant_application)
    total_attente = compter_tickets_attente_total(client_redis)

    if actifs_application < max_active and charge_active + cout_application <= capacite_serveur and total_attente == 0:
        statut = "actif"
        client_redis.zadd(cles_redis_application(identifiant_application)["tickets_actifs"], {identifiant_ticket: time.time()})
        client_redis.zadd(_zset_actifs_globale(), {identifiant_ticket: time.time()})
    else:
        if compter_tickets_attente_application(client_redis, identifiant_application) >= max_file_attente:
            return {
                "identifiant_ticket": None,
                "statut": "refuse",
                "position": None,
                "charge_active": charge_active,
                "capacite_serveur": capacite_serveur,
                "application_id": identifiant_application,
                "application_label": configuration["label"],
                "message": "File d'attente pleine pour cette application.",
            }

        statut = "attente"
        client_redis.zadd(cles_redis_application(identifiant_application)["tickets_attente"], {identifiant_ticket: time.time()})

    client_redis.hset(
        cle_ticket(identifiant_ticket),
        mapping={
            "identifiant_ticket": identifiant_ticket,
            "identifiant_session": identifiant_session,
            "application_id": identifiant_application,
            "nom_application": configuration["label"],
            "cout_application": cout_application,
            "statut": statut,
            "date_creation": int(time.time()),
        },
    )

    client_redis.expire(cle_ticket(identifiant_ticket), duree_ticket)
    client_redis.setex(cle_ticket_session, duree_ticket, identifiant_ticket)

    return _resume_ticket(client_redis, identifiant_ticket, identifiant_application)


def rafraichir_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    """Renouveler la durée de vie d'un ticket déjà attribué à une session."""
    configuration = lire_configuration_tickets(application_id)
    identifiant_application = configuration["application_id"]
    duree_ticket = configuration["duree_ticket"]
    cle_ticket_session = cle_session(identifiant_application, identifiant_session)
    identifiant_ticket = client_redis.get(cle_ticket_session)

    if not identifiant_ticket or not client_redis.exists(cle_ticket(identifiant_ticket)):
        return None

    client_redis.expire(cle_ticket(identifiant_ticket), duree_ticket)
    client_redis.expire(cle_ticket_session, duree_ticket)
    return _resume_ticket(client_redis, identifiant_ticket, identifiant_application)


def liberer_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    """Libérer le ticket d’une session après traitement."""
    configuration = lire_configuration_tickets(application_id)
    capacite_serveur = configuration["capacite_serveur"]
    identifiant_application = configuration["application_id"]

    cle_ticket_session = cle_session(identifiant_application, identifiant_session)
    identifiant_ticket = client_redis.get(cle_ticket_session)

    if identifiant_ticket:
        client_redis.zrem(cles_redis_application(identifiant_application)["tickets_actifs"], identifiant_ticket)
        client_redis.zrem(cles_redis_application(identifiant_application)["tickets_attente"], identifiant_ticket)
        client_redis.zrem(_zset_actifs_globale(), identifiant_ticket)
        client_redis.delete(cle_ticket(identifiant_ticket))
        client_redis.delete(cle_ticket_session)

    promouvoir_tickets_en_attente(client_redis, capacite_serveur)


def lire_statut_application(client_redis, application_id: str) -> dict[str, Any]:
    """Retourner l'état agrégé d'une application pour le tableau de bord."""
    configuration = lire_configuration_tickets(application_id)
    identifiant_application = configuration["application_id"]
    nettoyer_tickets_expires(client_redis, identifiant_application)
    promouvoir_tickets_en_attente(client_redis, configuration["capacite_serveur"])

    active = compter_tickets_actifs_application(client_redis, identifiant_application)
    queued = compter_tickets_attente_application(client_redis, identifiant_application)
    state, state_label = _statut_application_depuis_compteurs(active, configuration["max_active"], queued)

    return {
        "applicationId": identifiant_application,
        "label": configuration["label"],
        "active": active,
        "maxActive": configuration["max_active"],
        "queued": queued,
        "cost": configuration["cout"],
        "state": state,
        "stateLabel": state_label,
    }


def construire_tableau_de_bord(client_redis, application_ids: list[str] | None = None) -> dict[str, Any]:
    """Construire un résumé JSON exploitable par une page HTML ou une API FastAPI."""
    nettoyer_tickets_expires(client_redis)
    configuration_globale = _configuration_globale()
    promouvoir_tickets_en_attente(client_redis, configuration_globale["capacite_serveur"])

    ids = [normaliser_identifiant_application(item) for item in application_ids] if application_ids else _application_ids_configures()
    applications = {application_id: lire_statut_application(client_redis, application_id) for application_id in ids}

    active_users = sum(item["active"] for item in applications.values())
    total_queued = sum(item["queued"] for item in applications.values())
    active_load = calculer_charge_active(client_redis)

    if total_queued > 0:
        server_state = "full"
        server_label = "Avec attente"
    elif active_users > 0:
        server_state = "busy"
        server_label = "Utilisé"
    else:
        server_state = "available"
        server_label = "Disponible"

    return {
        "global": {
            "activeUsers": active_users,
            "maxActiveUsers": configuration_globale["capacite_serveur"],
            "activeLoad": active_load,
            "maxLoad": configuration_globale["capacite_serveur"],
            "totalQueued": total_queued,
            "serverState": server_state,
            "serverLabel": server_label,
            "updatedAt": int(time.time()),
        },
        "apps": applications,
    }


def construire_tableau_de_bord_indisponible(
    application_ids: list[str] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Retourner un JSON exploitable meme quand Redis est indisponible."""
    configuration_globale = _configuration_globale()
    ids = [normaliser_identifiant_application(item) for item in application_ids] if application_ids else _application_ids_configures()
    erreur = message or "Redis indisponible pour le tableau de bord."

    applications: dict[str, dict[str, Any]] = {}
    for application_id in ids:
        configuration = lire_configuration_tickets(application_id)
        applications[application_id] = {
            "applicationId": configuration["application_id"],
            "label": configuration["label"],
            "active": 0,
            "maxActive": configuration["max_active"],
            "queued": 0,
            "cost": configuration["cout"],
            "state": "offline",
            "stateLabel": "Hors ligne",
            "message": erreur,
        }

    return {
        "global": {
            "activeUsers": 0,
            "maxActiveUsers": configuration_globale["capacite_serveur"],
            "activeLoad": 0,
            "maxLoad": configuration_globale["capacite_serveur"],
            "totalQueued": 0,
            "serverState": "offline",
            "serverLabel": "Redis hors ligne",
            "message": erreur,
            "updatedAt": int(time.time()),
        },
        "apps": applications,
    }


if __name__ == "__main__":
    client_redis = connecter_redis()
    print(json.dumps(construire_tableau_de_bord(client_redis), ensure_ascii=False, indent=2))
