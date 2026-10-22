"""Non-régression : les places globales ne sont pas l'occupation des applications."""
import unittest
from unittest.mock import Mock, patch

from gestion_tickets import (
    _statut_application_depuis_compteurs,
    lire_statut_application,
    nettoyer_tickets_expires,
    _compter_tickets_actifs_application_brut,
)


class StatutsIndividuelsTests(unittest.TestCase):
    def test_application_libre_meme_si_charge_globale_ne_permet_pas_un_nouvel_acces(self):
        """Une session d'une autre app peut bloquer l'admission mais pas rendre cette app occupée."""
        client = Mock()

        def hgetall(cle):
            if cle == "app:chdrainette:config":
                return {"application_id": "chdrainette", "max_active": "1", "cost": "4"}
            if cle == "ticket:ticket-scraptiktok":
                return {"application_id": "scraptiktok", "cost": "8", "status": "actif"}
            return {}

        client.hgetall.side_effect = hgetall
        client.zrange.side_effect = lambda cle, debut, fin: (
            ["ticket-scraptiktok"] if cle == "tickets:global:actifs" else []
        )

        with patch("gestion_tickets._configuration_globale", return_value={
            "capacite_serveur": 10,
            "duree_ticket": 3600,
            "max_active_defaut": 3,
            "max_file_attente_defaut": 20,
        }):
            etat = lire_statut_application(client, "chdrainette", maintain=False)

        self.assertEqual(etat["active"], 0)
        self.assertEqual(etat["queued"], 0)
        self.assertEqual(etat["state"], "available")
        self.assertEqual(etat["stateLabel"], "Libre")
        self.assertIn("capacité globale insuffisante", etat["metaText"])

    def test_application_reellement_occupee_est_occupee(self):
        self.assertEqual(
            _statut_application_depuis_compteurs(1, 1, 0),
            ("busy", "Occupée"),
        )
        self.assertEqual(
            _statut_application_depuis_compteurs(0, 1, 0, capacity_blocked=True),
            ("available", "Libre"),
        )

    def test_ticket_scraptiktok_reference_ailleurs_reste_seulement_a_scraptiktok(self):
        client = Mock()
        client.exists.return_value = True
        client.hgetall.side_effect = lambda cle: (
            {"application_id": "scraptiktok", "session_id": "session-unique", "status": "actif"}
            if cle == "ticket:ticket-scraptiktok" else {}
        )

        tickets = {
            "app:chdrainette:tickets:actifs": ["ticket-scraptiktok"],
            "app:scraptiktok:tickets:actifs": ["ticket-scraptiktok"],
            "tickets:global:actifs": ["ticket-scraptiktok"],
        }
        client.zrange.side_effect = lambda cle, _start, _stop: list(tickets.get(cle, []))

        def zrem(cle, identifiant):
            if identifiant in tickets.get(cle, []):
                tickets[cle].remove(identifiant)
        client.zrem.side_effect = zrem

        with patch("gestion_tickets._lire_configuration_application", return_value={
            "duree_ticket": 3600, "duree_attente": 120,
        }):
            nettoyer_tickets_expires(client, "chdrainette")

        self.assertEqual(_compter_tickets_actifs_application_brut(client, "chdrainette"), 0)
        self.assertEqual(_compter_tickets_actifs_application_brut(client, "scraptiktok"), 1)
        self.assertEqual(tickets["tickets:global:actifs"], ["ticket-scraptiktok"])
        client.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()
