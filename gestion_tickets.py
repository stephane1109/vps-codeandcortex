import os
import time
import uuid
import redis


def connecter_redis():
    """Créer une connexion Redis à partir de la variable d’environnement REDIS_URL."""
    url_redis = os.getenv("REDIS_URL", "redis://redis:6379/0")
    return redis.from_url(url_redis, decode_responses=True)


def lire_configuration_tickets():
    """Lire les paramètres de limitation depuis les variables d’environnement."""
    return {
        "nom_application": os.getenv("NOM_APPLICATION", "application"),
        "cout_application": int(os.getenv("COUT_APPLICATION", "1")),
        "capacite_serveur": int(os.getenv("CAPACITE_SERVEUR", "4")),
        "duree_ticket": int(os.getenv("DUREE_TICKET", "3600")),
    }


def nettoyer_tickets_expires(client_redis):
    """Supprimer des index les tickets dont la clé Redis a expiré."""
    tickets_actifs = client_redis.zrange("tickets:actifs", 0, -1)
    tickets_attente = client_redis.zrange("tickets:attente", 0, -1)

    for identifiant_ticket in tickets_actifs:
        if not client_redis.exists(f"ticket:{identifiant_ticket}"):
            client_redis.zrem("tickets:actifs", identifiant_ticket)

    for identifiant_ticket in tickets_attente:
        if not client_redis.exists(f"ticket:{identifiant_ticket}"):
            client_redis.zrem("tickets:attente", identifiant_ticket)


def calculer_charge_active(client_redis):
    """Calculer la charge totale des tickets actifs."""
    nettoyer_tickets_expires(client_redis)

    charge = 0
    tickets_actifs = client_redis.zrange("tickets:actifs", 0, -1)

    for identifiant_ticket in tickets_actifs:
        donnees = client_redis.hgetall(f"ticket:{identifiant_ticket}")
        if donnees:
            charge += int(donnees.get("cout_application", 1))

    return charge


def calculer_position_attente(client_redis, identifiant_ticket):
    """Calculer la position d’un ticket dans la file d’attente."""
    tickets_attente = client_redis.zrange("tickets:attente", 0, -1)

    if identifiant_ticket not in tickets_attente:
        return None

    return tickets_attente.index(identifiant_ticket) + 1


def promouvoir_tickets_en_attente(client_redis, capacite_serveur):
    """Promouvoir les premiers tickets en attente si la capacité serveur le permet."""
    nettoyer_tickets_expires(client_redis)

    tickets_attente = client_redis.zrange("tickets:attente", 0, -1)

    for identifiant_ticket in tickets_attente:
        donnees = client_redis.hgetall(f"ticket:{identifiant_ticket}")

        if not donnees:
            client_redis.zrem("tickets:attente", identifiant_ticket)
            continue

        cout_application = int(donnees.get("cout_application", 1))
        charge_active = calculer_charge_active(client_redis)

        if charge_active + cout_application <= capacite_serveur:
            client_redis.hset(f"ticket:{identifiant_ticket}", "statut", "actif")
            client_redis.zrem("tickets:attente", identifiant_ticket)
            client_redis.zadd("tickets:actifs", {identifiant_ticket: time.time()})
        else:
            break


def creer_ou_recuperer_ticket(client_redis, identifiant_session):
    """Créer un ticket pour une session ou récupérer le ticket déjà existant."""
    configuration = lire_configuration_tickets()

    nom_application = configuration["nom_application"]
    cout_application = configuration["cout_application"]
    capacite_serveur = configuration["capacite_serveur"]
    duree_ticket = configuration["duree_ticket"]

    nettoyer_tickets_expires(client_redis)
    promouvoir_tickets_en_attente(client_redis, capacite_serveur)

    cle_session = f"session:{identifiant_session}:ticket"
    ticket_existant = client_redis.get(cle_session)

    if ticket_existant and client_redis.exists(f"ticket:{ticket_existant}"):
        donnees = client_redis.hgetall(f"ticket:{ticket_existant}")
        position = calculer_position_attente(client_redis, ticket_existant)

        return {
            "identifiant_ticket": ticket_existant,
            "statut": donnees.get("statut", "inconnu"),
            "position": position,
            "charge_active": calculer_charge_active(client_redis),
            "capacite_serveur": capacite_serveur,
        }

    identifiant_ticket = str(uuid.uuid4())
    charge_active = calculer_charge_active(client_redis)

    if charge_active + cout_application <= capacite_serveur and client_redis.zcard("tickets:attente") == 0:
        statut = "actif"
        client_redis.zadd("tickets:actifs", {identifiant_ticket: time.time()})
    else:
        statut = "attente"
        client_redis.zadd("tickets:attente", {identifiant_ticket: time.time()})

    client_redis.hset(
        f"ticket:{identifiant_ticket}",
        mapping={
            "identifiant_ticket": identifiant_ticket,
            "identifiant_session": identifiant_session,
            "nom_application": nom_application,
            "cout_application": cout_application,
            "statut": statut,
            "date_creation": int(time.time()),
        },
    )

    client_redis.expire(f"ticket:{identifiant_ticket}", duree_ticket)
    client_redis.setex(cle_session, duree_ticket, identifiant_ticket)

    position = calculer_position_attente(client_redis, identifiant_ticket)

    return {
        "identifiant_ticket": identifiant_ticket,
        "statut": statut,
        "position": position,
        "charge_active": calculer_charge_active(client_redis),
        "capacite_serveur": capacite_serveur,
    }


def liberer_ticket(client_redis, identifiant_session):
    """Libérer le ticket d’une session après traitement."""
    configuration = lire_configuration_tickets()
    capacite_serveur = configuration["capacite_serveur"]

    cle_session = f"session:{identifiant_session}:ticket"
    identifiant_ticket = client_redis.get(cle_session)

    if identifiant_ticket:
        client_redis.zrem("tickets:actifs", identifiant_ticket)
        client_redis.zrem("tickets:attente", identifiant_ticket)
        client_redis.delete(f"ticket:{identifiant_ticket}")
        client_redis.delete(cle_session)

    promouvoir_tickets_en_attente(client_redis, capacite_serveur)