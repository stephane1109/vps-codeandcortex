"""Vérifier la distinction entre panne Redis et configuration VisioTrack absente."""
import unittest
from unittest.mock import Mock, patch

from dashboard_api import DashboardHandler


class DashboardHealthTests(unittest.TestCase):
    def test_health_redis_disponible_sans_configuration(self):
        client = Mock()
        client.hgetall.return_value = {}
        client.ttl.return_value = -2
        handler = DashboardHandler.__new__(DashboardHandler)
        handler._send_json = Mock()
        with patch("dashboard_api.connecter_redis", return_value=client):
            handler._serve_health(True)
        payload = handler._send_json.call_args.args[1]
        self.assertEqual(payload["redis"], "connecte")
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["visiotrack"]["configuration_publiee"])

    def test_health_redis_disponible_avec_configuration(self):
        client = Mock()
        client.hgetall.return_value = {
            "application_id": "visiotrack", "updated_at": "1792597200"
        }
        client.ttl.return_value = 840
        handler = DashboardHandler.__new__(DashboardHandler)
        handler._send_json = Mock()
        with patch("dashboard_api.connecter_redis", return_value=client):
            handler._serve_health(True)
        payload = handler._send_json.call_args.args[1]
        self.assertTrue(payload["visiotrack"]["configuration_publiee"])
        self.assertEqual(payload["visiotrack"]["ttl_configuration_secondes"], 840)

    def test_health_redis_injoignable(self):
        handler = DashboardHandler.__new__(DashboardHandler)
        handler._send_json = Mock()
        with patch("dashboard_api.connecter_redis", side_effect=ConnectionError("secret")):
            handler._serve_health(True)
        payload = handler._send_json.call_args.args[1]
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["erreur_type"], "ConnectionError")
        self.assertNotIn("secret", str(payload))


if __name__ == "__main__":
    unittest.main()
