"""Vérifier la réservation, l'attente et la libération sans Redis de production."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import fakeredis
from streamlit.testing.v1 import AppTest

import ticket_gate


class TestsAcces(unittest.TestCase):
    """Exercer le contrôle d'accès et les boutons de la barre latérale."""

    def setUp(self):
        self.environnement = patch.dict(os.environ, {
            "APP_TICKET_ENFORCED": "1", "APP_TICKET_ID": "visiotrack",
            "APP_TICKET_MAX_ACTIVE": "1", "APP_TICKET_COST": "4",
            "CAPACITE_SERVEUR": "10", "APP_TICKET_RELEASE_URL": "",
        })
        self.environnement.start()
        self.addCleanup(self.environnement.stop)
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.connexion = patch.object(ticket_gate, "_redis_client", return_value=(self.redis, None))
        self.connexion.start()
        self.addCleanup(self.connexion.stop)

    def ouvrir_application(self):
        """Créer une session utilisateur indépendante."""
        application = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"))
        application.run(timeout=20)
        self.assertEqual(len(application.exception), 0)
        return application

    def test_liberation_reprise_et_promotion_utilisateur_suivant(self):
        premiere = self.ouvrir_application()
        self.assertIn("Libérer l'accès", [b.label for b in premiere.sidebar.button])
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:actifs"), 1)
        seconde = self.ouvrir_application()
        self.assertEqual(len(seconde.text_area), 0)
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:attente"), 1)
        next(b for b in premiere.sidebar.button if b.label == "Libérer l'accès").click().run()
        self.assertEqual(len(premiere.exception), 0)
        self.assertIn("Reprendre l'accès", [b.label for b in premiere.sidebar.button])
        self.assertEqual(len(premiere.text_area), 0)
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:attente"), 0)
        seconde.run()
        self.assertIn("Libérer l'accès", [b.label for b in seconde.sidebar.button])
        # Un rafraîchissement après libération ne reprend pas l'accès tout seul.
        premiere.run()
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:attente"), 0)
        next(b for b in premiere.sidebar.button if b.label == "Reprendre l'accès").click().run()
        self.assertEqual(len(premiere.exception), 0)
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:attente"), 1)

    def test_redis_indisponible_bloque_analyse(self):
        with patch.object(ticket_gate, "_redis_client", return_value=(None, "Redis indisponible.")):
            application = self.ouvrir_application()
        self.assertEqual(len(application.text_area), 0)
        self.assertGreater(len(application.error), 0)

    def test_capacite_globale_respectee(self):
        configuration = ticket_gate._config("visiotrack", "VisioTrack")
        autre = {**configuration, "app_id": "autre-application", "cost": 8}
        self.assertEqual(ticket_gate._claim_or_refresh(self.redis, autre, "autre-session")["statut"], "actif")
        application = self.ouvrir_application()
        self.assertEqual(len(application.text_area), 0)
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:actifs"), 0)
        self.assertEqual(self.redis.zcard("app:visiotrack:tickets:attente"), 1)

    def test_renouvellement_ne_recree_pas_un_ticket_libere(self):
        configuration = ticket_gate._config("visiotrack", "VisioTrack")
        ticket = ticket_gate._claim_or_refresh(self.redis, configuration, "session-test")["ticket_id"]
        with patch.object(ticket_gate.st, "session_state", {ticket_gate.SESSION_STATE_KEY: "session-test"}):
            self.assertTrue(ticket_gate.renouveler_acces_analyse(ticket))
            self.redis.delete("ticket:" + ticket)
            self.assertFalse(ticket_gate.renouveler_acces_analyse(ticket))
            self.assertFalse(self.redis.exists("ticket:" + ticket))


if __name__ == "__main__":
    unittest.main()
