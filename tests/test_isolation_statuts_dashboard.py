"""Tests de non-régression des statuts et des capacités du tableau de bord."""

from unittest.mock import Mock, patch

from dashboard_shared.tickets import (
    _statut_application_depuis_compteurs,
    construire_tableau_de_bord,
    relever_ecarts_capacite_serveur,
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
