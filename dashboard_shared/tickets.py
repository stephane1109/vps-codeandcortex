from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from dashboard_shared.app_catalog import load_ticket_app_defaults

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


def connecter_redis():
    """Créer une connexion Redis à partir de REDIS_URL."""
    if redis is None:
        raise RuntimeError("Le paquet Python 'redis' doit être installé pour utiliser la file d'attente.")

    url_redis = os.getenv("REDIS_URL", "").strip()
    if not url_redis:
        raise RuntimeError(
            "REDIS_URL absent sur le service dashboard : configure la même URL Redis que sur les applications à tickets."
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
    duree_ticket = max(60, int(brute.get("duree_ticket", configuration_globale["duree_ticket"])))
    return {
        "application_id": application_id,
        "label": str(brute.get("label") or application_id),
        "cout": max(0, int(brute.get("cout", 1))),
        "max_active": max(1, int(brute.get("max_active", configuration_globale["max_active_defaut"]))),
        "max_file_attente": max(
            0,
            int(brute.get("max_file_attente", configuration_globale["max_file_attente_defaut"])),
        ),
        "duree_ticket": duree_ticket,
        "duree_attente": max(30, int(brute.get("duree_attente", min(duree_ticket, 120)))),
    }


def charger_configurations_applications() -> dict[str, dict[str, Any]]:
    """Construire la configuration multi-app à partir des applis et des overrides d'env."""
    configuration_globale = _configuration_globale()
    configurations: dict[str, dict[str, Any]] = {}

    for application_id, configuration in load_ticket_app_defaults().items():
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
            configurations[slug] = _fusionner_configuration_application(slug, configuration, configuration_globale)

    return configurations


def cles_redis_application(application_id: str) -> dict[str, str]:
    return {
        "tickets_actifs": f"app:{application_id}:tickets:actifs",
        "tickets_attente": f"app:{application_id}:tickets:attente",
    }


def cles_redis_configuration_application(application_id: str) -> tuple[str, ...]:
    return (
        f"app:{application_id}:config",
        f"application:{application_id}:config",
    )


def cle_ticket(identifiant_ticket: str) -> str:
    return f"ticket:{identifiant_ticket}"


def cle_session(application_id: str, identifiant_session: str) -> str:
    return f"session:{application_id}:{identifiant_session}:ticket"


def _zset_actifs_globale() -> str:
    return "tickets:global:actifs"


def _application_ids_configures() -> list[str]:
    return sorted(charger_configurations_applications().keys())


def _extraire_texte_mapping(donnees: dict[str, Any], *champs: str) -> str | None:
    for champ in champs:
        valeur = str(donnees.get(champ, "")).strip()
        if valeur:
            return valeur
    return None


def _extraire_entier_mapping(donnees: dict[str, Any], *champs: str, minimum: int | None = None) -> int | None:
    for champ in champs:
        valeur = donnees.get(champ)
        if valeur in (None, ""):
            continue
        try:
            nombre = int(float(valeur))
        except (TypeError, ValueError):
            continue
        return max(minimum, nombre) if minimum is not None else nombre
    return None


def _configuration_runtime_depuis_redis(client_redis, application_id: str) -> dict[str, Any]:
    if client_redis is None:
        return {}

    for cle in cles_redis_configuration_application(application_id):
        donnees = client_redis.hgetall(cle) or {}
        if not donnees:
            continue

        configuration: dict[str, Any] = {}
        label = _extraire_texte_mapping(donnees, "label", "application_label", "app_label", "nom_application")
        if label:
            configuration["label"] = label

        cout = _extraire_entier_mapping(donnees, "cost", "cout", "cout_application", minimum=0)
        if cout is not None:
            configuration["cout"] = cout

        max_active = _extraire_entier_mapping(donnees, "max_active", "maxActive", minimum=1)
        if max_active is not None:
            configuration["max_active"] = max_active

        max_file_attente = _extraire_entier_mapping(
            donnees,
            "max_waiting",
            "max_file_attente",
            "maxWaiting",
            minimum=0,
        )
        if max_file_attente is not None:
            configuration["max_file_attente"] = max_file_attente

        duree_ticket = _extraire_entier_mapping(donnees, "ttl_seconds", "duree_ticket", minimum=60)
        if duree_ticket is not None:
            configuration["duree_ticket"] = duree_ticket

        duree_attente = _extraire_entier_mapping(donnees, "duree_attente", minimum=30)
        if duree_attente is not None:
            configuration["duree_attente"] = duree_attente

        return configuration

    return {}


def _extraire_application_id_depuis_cle_redis(cle: str) -> str | None:
    if cle.startswith("app:") and cle.endswith(":config"):
        return normaliser_identifiant_application(cle[4:-7])
    if cle.startswith("application:") and cle.endswith(":config"):
        return normaliser_identifiant_application(cle[len("application:") : -7])
    if cle.startswith("app:") and cle.endswith(":tickets:actifs"):
        return normaliser_identifiant_application(cle[4:-15])
    if cle.startswith("app:") and cle.endswith(":tickets:attente"):
        return normaliser_identifiant_application(cle[4:-16])
    return None


def _application_ids_redis(client_redis) -> list[str]:
    if client_redis is None:
        return []

    ids: set[str] = set()
    for motif in (
        "app:*:config",
        "application:*:config",
        "app:*:tickets:actifs",
        "app:*:tickets:attente",
    ):
        for cle in client_redis.scan_iter(match=motif):
            application_id = _extraire_application_id_depuis_cle_redis(str(cle))
            if application_id:
                ids.add(application_id)
    return sorted(ids)


def _application_ids_connues(client_redis=None) -> list[str]:
    ids = set(_application_ids_configures())
    ids.update(_application_ids_redis(client_redis))
    return sorted(ids)


def lire_configuration_tickets(application_id: str | None = None, client_redis=None) -> dict[str, Any]:
    configuration_globale = _configuration_globale()
    identifiant_application = normaliser_identifiant_application(application_id)
    configurations_brutes = charger_configurations_applications()

    ids = _application_ids_connues(client_redis)
    ids.append(identifiant_application)

    applications: dict[str, dict[str, Any]] = {}
    for slug in sorted(set(ids)):
        brute = dict(configurations_brutes.get(slug) or {})
        brute.update(_configuration_runtime_depuis_redis(client_redis, slug))
        applications[slug] = _fusionner_configuration_application(slug, brute or {"label": slug}, configuration_globale)

    application = applications[identifiant_application]

    return {
        "capacite_serveur": configuration_globale["capacite_serveur"],
        "duree_ticket": configuration_globale["duree_ticket"],
        "applications": applications,
        **application,
    }


def _zscore(client_redis, key: str, member: str) -> float:
    score = client_redis.zscore(key, member)
    return float(score if score is not None else time.time())


def _lister_tickets(client_redis, key: str) -> list[str]:
    return [str(item) for item in client_redis.zrange(key, 0, -1)]


def _lire_donnees_ticket(client_redis, identifiant_ticket: str) -> dict[str, Any]:
    return client_redis.hgetall(cle_ticket(identifiant_ticket)) or {}


def _statut_ticket(donnees: dict[str, Any]) -> str:
    return str(donnees.get("status") or donnees.get("statut") or "attente").strip() or "attente"


def _session_ticket(donnees: dict[str, Any]) -> str:
    return str(donnees.get("session_id") or donnees.get("identifiant_session") or "").strip()


def _heartbeat_ticket(donnees: dict[str, Any], maintenant: int) -> int:
    brute = donnees.get("updated_at") or donnees.get("created_at") or donnees.get("date_creation") or maintenant
    try:
        return int(float(brute))
    except (TypeError, ValueError):
        return 0


def _cout_ticket_depuis_donnees(donnees: dict[str, Any], configuration: dict[str, Any] | None = None) -> int:
    cout_defaut = int(configuration["cout"]) if configuration else 1
    for champ in ("cout_application", "cost"):
        try:
            valeur = donnees.get(champ)
            if valeur not in (None, ""):
                return max(0, int(float(valeur)))
        except (TypeError, ValueError):
            continue
    return max(0, cout_defaut)


def _timeout_ticket(configuration: dict[str, Any], statut: str) -> int:
    if statut == "attente":
        return int(configuration.get("duree_attente", min(configuration["duree_ticket"], 120)))
    return int(configuration["duree_ticket"])


def _supprimer_ticket(
    client_redis,
    identifiant_ticket: str,
    application_id: str,
    donnees: dict[str, Any] | None = None,
) -> None:
    donnees_ticket = donnees or _lire_donnees_ticket(client_redis, identifiant_ticket)
    session_id = _session_ticket(donnees_ticket)
    client_redis.zrem(cles_redis_application(application_id)["tickets_actifs"], identifiant_ticket)
    client_redis.zrem(cles_redis_application(application_id)["tickets_attente"], identifiant_ticket)
    client_redis.zrem(_zset_actifs_globale(), identifiant_ticket)
    client_redis.delete(cle_ticket(identifiant_ticket))
    if session_id:
        client_redis.delete(cle_session(application_id, session_id))


def nettoyer_tickets_expires(client_redis, application_id: str | None = None):
    """Supprimer des index les tickets expirés ou abandonnés."""
    applications = [normaliser_identifiant_application(application_id)] if application_id else _application_ids_connues(client_redis)
    tickets_vus: set[tuple[str, str]] = set()
    maintenant = int(time.time())

    for identifiant_application in applications:
        configuration = lire_configuration_tickets(identifiant_application, client_redis=client_redis)
        cles = cles_redis_application(identifiant_application)
        for key in (cles["tickets_actifs"], cles["tickets_attente"]):
            for identifiant_ticket in _lister_tickets(client_redis, key):
                cle_vue = (identifiant_application, identifiant_ticket)
                if cle_vue in tickets_vus:
                    continue
                tickets_vus.add(cle_vue)

                if not client_redis.exists(cle_ticket(identifiant_ticket)):
                    client_redis.zrem(cles["tickets_actifs"], identifiant_ticket)
                    client_redis.zrem(cles["tickets_attente"], identifiant_ticket)
                    client_redis.zrem(_zset_actifs_globale(), identifiant_ticket)
                    continue

                donnees = _lire_donnees_ticket(client_redis, identifiant_ticket)
                statut = _statut_ticket(donnees)
                heartbeat = _heartbeat_ticket(donnees, maintenant)
                session_id = _session_ticket(donnees)
                cle_session_ticket = cle_session(identifiant_application, session_id) if session_id else ""
                ticket_session = client_redis.get(cle_session_ticket) if cle_session_ticket else None
                if (
                    heartbeat <= 0
                    or heartbeat > maintenant + 300
                    or maintenant - heartbeat > _timeout_ticket(configuration, statut)
                    or (statut == "actif" and session_id and ticket_session != identifiant_ticket)
                    or (statut == "actif" and not session_id)
                ):
                    _supprimer_ticket(client_redis, identifiant_ticket, identifiant_application, donnees)

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
            application_id = str(donnees.get("application_id", "")).strip()
            configuration = lire_configuration_tickets(application_id, client_redis=client_redis) if application_id else None
            charge += _cout_ticket_depuis_donnees(donnees, configuration)
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
    for application_id in _application_ids_connues(client_redis):
        total += compter_tickets_attente_application(client_redis, application_id)
    return total


def calculer_position_attente(client_redis, identifiant_ticket: str, application_id: str | None = None):
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
    configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
    donnees = _lire_donnees_ticket(client_redis, identifiant_ticket)
    position = calculer_position_attente(client_redis, identifiant_ticket, application_id)
    active = compter_tickets_actifs_application(client_redis, application_id)
    queued = compter_tickets_attente_application(client_redis, application_id)
    state, label = _statut_application_depuis_compteurs(active, configuration["max_active"], queued)

    return {
        "identifiant_ticket": identifiant_ticket,
        "statut": _statut_ticket(donnees) if donnees else "inconnu",
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
    for application_id in _application_ids_connues(client_redis):
        key = cles_redis_application(application_id)["tickets_attente"]
        for identifiant_ticket in _lister_tickets(client_redis, key):
            candidats.append((_zscore(client_redis, key, identifiant_ticket), application_id, identifiant_ticket))
    candidats.sort(key=lambda item: item[0])
    return candidats


def promouvoir_tickets_en_attente(client_redis, capacite_serveur: int | None = None):
    configuration_globale = _configuration_globale()
    capacite = capacite_serveur if capacite_serveur is not None else configuration_globale["capacite_serveur"]
    nettoyer_tickets_expires(client_redis)

    for _score, application_id, identifiant_ticket in _candidats_attente(client_redis):
        donnees = _lire_donnees_ticket(client_redis, identifiant_ticket)
        if not donnees:
            client_redis.zrem(cles_redis_application(application_id)["tickets_attente"], identifiant_ticket)
            continue

        configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
        cout_application = _cout_ticket_depuis_donnees(donnees, configuration)
        charge_active = calculer_charge_active(client_redis)
        actifs_application = compter_tickets_actifs_application(client_redis, application_id)

        if actifs_application >= configuration["max_active"]:
            continue
        if charge_active + cout_application > capacite:
            continue

        maintenant = int(time.time())
        client_redis.hset(
            cle_ticket(identifiant_ticket),
            mapping={"statut": "actif", "status": "actif", "updated_at": maintenant},
        )
        session_id = _session_ticket(donnees)
        client_redis.expire(cle_ticket(identifiant_ticket), configuration["duree_ticket"])
        if session_id:
            client_redis.expire(cle_session(application_id, session_id), configuration["duree_ticket"])
        client_redis.zrem(cles_redis_application(application_id)["tickets_attente"], identifiant_ticket)
        client_redis.zadd(cles_redis_application(application_id)["tickets_actifs"], {identifiant_ticket: time.time()})
        client_redis.zadd(_zset_actifs_globale(), {identifiant_ticket: time.time()})


def creer_ou_recuperer_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
    identifiant_application = configuration["application_id"]
    cout_application = configuration["cout"]
    capacite_serveur = configuration["capacite_serveur"]
    max_active = configuration["max_active"]
    max_file_attente = configuration["max_file_attente"]

    nettoyer_tickets_expires(client_redis)
    promouvoir_tickets_en_attente(client_redis, capacite_serveur)

    cle_ticket_session = cle_session(identifiant_application, identifiant_session)
    ticket_existant = client_redis.get(cle_ticket_session)

    if ticket_existant and client_redis.exists(cle_ticket(ticket_existant)):
        donnees_existant = _lire_donnees_ticket(client_redis, ticket_existant)
        statut_existant = _statut_ticket(donnees_existant)
        duree_effective = _timeout_ticket(configuration, statut_existant)
        client_redis.hset(cle_ticket(ticket_existant), mapping={"updated_at": int(time.time())})
        client_redis.expire(cle_ticket(ticket_existant), duree_effective)
        client_redis.expire(cle_ticket_session, duree_effective)
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

    maintenant = int(time.time())
    client_redis.hset(
        cle_ticket(identifiant_ticket),
        mapping={
            "identifiant_ticket": identifiant_ticket,
            "identifiant_session": identifiant_session,
            "session_id": identifiant_session,
            "application_id": identifiant_application,
            "nom_application": configuration["label"],
            "application_label": configuration["label"],
            "cout_application": cout_application,
            "cost": cout_application,
            "statut": statut,
            "status": statut,
            "date_creation": maintenant,
            "created_at": maintenant,
            "updated_at": maintenant,
        },
    )

    duree_effective = _timeout_ticket(configuration, statut)
    client_redis.expire(cle_ticket(identifiant_ticket), duree_effective)
    client_redis.setex(cle_ticket_session, duree_effective, identifiant_ticket)

    return _resume_ticket(client_redis, identifiant_ticket, identifiant_application)


def rafraichir_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
    identifiant_application = configuration["application_id"]
    cle_ticket_session = cle_session(identifiant_application, identifiant_session)
    identifiant_ticket = client_redis.get(cle_ticket_session)
    if not identifiant_ticket or not client_redis.exists(cle_ticket(identifiant_ticket)):
        return None

    donnees = _lire_donnees_ticket(client_redis, identifiant_ticket)
    statut = _statut_ticket(donnees)
    duree_effective = _timeout_ticket(configuration, statut)
    client_redis.hset(cle_ticket(identifiant_ticket), mapping={"updated_at": int(time.time())})
    client_redis.expire(cle_ticket(identifiant_ticket), duree_effective)
    client_redis.expire(cle_ticket_session, duree_effective)
    return _resume_ticket(client_redis, identifiant_ticket, identifiant_application)


def liberer_ticket(client_redis, identifiant_session: str, application_id: str | None = None):
    configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
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
    configuration = lire_configuration_tickets(application_id, client_redis=client_redis)
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
    nettoyer_tickets_expires(client_redis)
    configuration_globale = _configuration_globale()
    promouvoir_tickets_en_attente(client_redis, configuration_globale["capacite_serveur"])

    ids = [normaliser_identifiant_application(item) for item in application_ids] if application_ids else _application_ids_connues(client_redis)
    applications = {application_id: lire_statut_application(client_redis, application_id) for application_id in ids}

    active_users = compter_tickets_actifs_total(client_redis)
    total_queued = compter_tickets_attente_total(client_redis)
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
            "state": "unavailable",
            "stateLabel": "Synchronisation indisponible",
            "message": erreur,
        }

    return {
        "global": {
            "activeUsers": 0,
            "maxActiveUsers": configuration_globale["capacite_serveur"],
            "activeLoad": 0,
            "maxLoad": configuration_globale["capacite_serveur"],
            "totalQueued": 0,
            "serverState": "degraded",
            "serverLabel": "Synchronisation indisponible",
            "message": erreur,
            "updatedAt": int(time.time()),
        },
        "apps": applications,
    }
