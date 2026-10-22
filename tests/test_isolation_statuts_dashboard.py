"""Tests de non-régression des statuts et des capacités du tableau de bord."""

import time
from unittest.mock import Mock, patch

from dashboard_shared.tickets import (
    _statut_application_depuis_compteurs,
    construire_tableau_de_bord,
    relever_ecarts_capacite_serveur,
    compter_tickets_actifs_application,
    nettoyer_tickets_expires,
)


def test_scraptiktok_occupe_ne_marque_pas_les_autres_applications_occupees():
    """Un ticket ScrapTikTok ne doit pas rendre les autres applications occupées."""
    def configuration(application_id, client_redis=None):
        return {
            "application_id": application_id,
            "label": application_id,
            "max_active": 3 if application_id == "scraptiktok" else 1,
            "cout": 2 if application_id == "scraptiktok" else 4,
            "capacite_serveur": 10,
        }

    applications = ["scraptiktok", "iramuteq-lite", "iramuteqlite_autochd", "chdrainette"]
    client_redis = Mock()

    with patch.multiple(
        "dashboard_shared.tickets",
        nettoyer_tickets_expires=Mock(),
        promouvoir_tickets_en_attente=Mock(),
        _configuration_globale=Mock(return_value={"capacite_serveur": 10}),
        _application_ids_connues=Mock(return_value=applications),
        lire_configuration_tickets=Mock(side_effect=configuration),
        compter_tickets_actifs_application=Mock(
            side_effect=lambda _client, application: int(application == "scraptiktok")
        ),
        compter_tickets_attente_application=Mock(return_value=0),
        compter_tickets_actifs_total=Mock(return_value=1),
        compter_tickets_attente_total=Mock(return_value=0),
        calculer_charge_active=Mock(return_value=2),
        relever_ecarts_capacite_serveur=Mock(return_value=[]),
    ):
        resultat = construire_tableau_de_bord(client_redis, applications)

    assert resultat["global"]["activeUsers"] == 1
    assert resultat["global"]["activeLoad"] == 2
    assert resultat["global"]["maxLoad"] == 10
    assert resultat["apps"]["scraptiktok"]["state"] == "busy"
    for application in applications[1:]:
        assert resultat["apps"][application]["active"] == 0
        assert resultat["apps"][application]["state"] == "available"
        assert resultat["apps"][application]["stateLabel"] == "Libre"


def test_statut_propre_a_chaque_application():
    """Une attente ne doit pas contaminer les statuts d'autres applications."""
    assert _statut_application_depuis_compteurs(1, 1, 1) == ("queued", "File d'attente")
    assert _statut_application_depuis_compteurs(0, 1, 0) == ("available", "Libre")


def test_ecarts_capacite_sont_signales_sans_changer_les_statuts():
    """L'écart de capacité doit être visible sans déclarer les applications occupées."""
    client_redis = Mock()
    client_redis.hgetall.side_effect = lambda cle: (
        {"global_capacity": "10"} if cle == "app:scraptiktok:config"
        else {"global_capacity": "6"} if cle == "app:chdrainette:config"
        else {}
    )
    ecarts = relever_ecarts_capacite_serveur(
        client_redis, ["scraptiktok", "chdrainette"], capacite_dashboard=10
    )
    assert ecarts == [{
        "applicationId": "chdrainette",
        "applicationCapacity": 6,
        "dashboardCapacity": 10,
    }]



def test_ticket_scraptiktok_dans_index_etranger_ne_bloque_pas_autres_applications():
    """Un index Redis erroné ne doit ni compter ni supprimer un ticket tiers."""
    identifiant_ticket = "ticket-scraptiktok"
    identifiant_session = "session-scraptiktok"
    tickets = {
        "tickets:global:actifs": [identifiant_ticket],
        "app:scraptiktok:tickets:actifs": [identifiant_ticket],
        "app:chdrainette:tickets:actifs": [identifiant_ticket],
        "app:iramuteq-lite:tickets:actifs": [identifiant_ticket],
        "app:iramuteqlite_autochd:tickets:actifs": [identifiant_ticket],
    }
    contenu_ticket = {
        "application_id": "scraptiktok",
        "session_id": identifiant_session,
        "status": "actif",
        "updated_at": str(int(time.time())),
    }
    client_redis = Mock()
    client_redis.zrange.side_effect = lambda cle, debut, fin: list(tickets.get(cle, []))
    client_redis.zrem.side_effect = (
        lambda cle, ticket: tickets.setdefault(cle, []).remove(ticket)
        if ticket in tickets.get(cle, []) else None
    )
    client_redis.exists.side_effect = lambda cle: cle == f"ticket:{identifiant_ticket}"
    client_redis.hgetall.side_effect = lambda cle: (
        contenu_ticket if cle == f"ticket:{identifiant_ticket}" else {}
    )
    client_redis.get.side_effect = lambda cle: (
        identifiant_ticket
        if cle == f"session:scraptiktok:{identifiant_session}:ticket" else None
    )

    configuration = {
        "duree_ticket": 3600,
        "duree_attente": 120,
        "max_active": 3,
        "cout": 2,
    }
    with patch("dashboard_shared.tickets.lire_configuration_tickets", return_value=configuration):
        for application in ("chdrainette", "iramuteq-lite", "iramuteqlite_autochd"):
            assert compter_tickets_actifs_application(client_redis, application) == 0
        assert compter_tickets_actifs_application(client_redis, "scraptiktok") == 1

    assert tickets["tickets:global:actifs"] == [identifiant_ticket]
    assert tickets["app:scraptiktok:tickets:actifs"] == [identifiant_ticket]
    assert tickets["app:chdrainette:tickets:actifs"] == []
    assert tickets["app:iramuteq-lite:tickets:actifs"] == []
    assert tickets["app:iramuteqlite_autochd:tickets:actifs"] == []
    client_redis.delete.assert_not_called()


def test_nettoyage_ticket_indexe_sous_mauvaise_application_ne_supprime_pas_sa_session():
    """La correction d'un index étranger doit préserver le ticket Redis valide."""
    ticket = "ticket-valide"
    client_redis = Mock()
    client_redis.zrange.side_effect = lambda cle, debut, fin: (
        [ticket] if cle == "app:chdrainette:tickets:actifs" else []
    )
    client_redis.exists.return_value = True
    client_redis.hgetall.return_value = {"application_id": "scraptiktok", "status": "actif"}
    with patch(
        "dashboard_shared.tickets.lire_configuration_tickets",
        return_value={"duree_ticket": 3600, "duree_attente": 120},
    ):
        nettoyer_tickets_expires(client_redis, "chdrainette")

    client_redis.zrem.assert_any_call("app:chdrainette:tickets:actifs", ticket)
    assert all(
        appel.args[0] != "tickets:global:actifs"
        for appel in client_redis.zrem.call_args_list
    )
    client_redis.delete.assert_not_called()
