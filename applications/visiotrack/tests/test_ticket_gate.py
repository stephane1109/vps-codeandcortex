"""Régressions du renouvellement des tickets VisioTrack."""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ticket_gate as gate
import synchronisation_dashboard as synchronisation


class TestRenouvellementTicket(unittest.TestCase):
    def setUp(self):
        self.cfg = {
            "app_id": "visiotrack", "app_label": "VisioTrack",
            "enabled": True, "ttl_seconds": 3600,
            "max_active": 1, "cost": 4, "global_capacity": 10,
            "max_waiting": 20, "wait_refresh_ms": 10000,
            "heartbeat_ms": 300000,
        }

    def test_publication_runtime_meme_sans_session_streamlit(self):
        client = MagicMock()
        with patch.object(synchronisation, "_config", return_value=self.cfg), \
             patch.object(synchronisation, "_redis_client", return_value=(client, None)), \
             patch.object(synchronisation, "_publish_runtime_config") as publier:
            self.assertTrue(synchronisation.publier())
        publier.assert_called_once_with(client, self.cfg)

    def test_publication_runtime_signale_redis_indisponible(self):
        with patch.object(synchronisation, "_config", return_value=self.cfg), \
             patch.object(synchronisation, "_redis_client", return_value=(None, "non connecte")), \
             patch.object(synchronisation, "_publish_runtime_config") as publier:
            self.assertFalse(synchronisation.publier())
        publier.assert_not_called()

    def test_renouvellement_rafraichit_horodatage_et_config(self):
        client = MagicMock()
        client.get.return_value = "ticket-123"
        client.hgetall.return_value = {
            "status": "actif", "application_id": "visiotrack",
            "session_id": "session-1",
        }
        pipeline = client.pipeline.return_value.__enter__.return_value
        pipeline.execute.return_value = [1, True, True]
        with patch.object(gate, "_config", return_value=self.cfg), \
             patch.object(gate, "_redis_client", return_value=(client, None)), \
             patch.object(gate.st, "session_state", {gate.SESSION_STATE_KEY: "session-1"}), \
             patch.object(gate, "_publish_runtime_config") as publish:
            self.assertTrue(gate.renouveler_acces_analyse("ticket-123"))
        pipeline.hset.assert_called_once()
        self.assertEqual(pipeline.hset.call_args.args[:2],
                         ("ticket:ticket-123", "updated_at"))
        self.assertLess(abs(pipeline.hset.call_args.args[2] - time.time()), 5)
        pipeline.expire.assert_any_call("ticket:ticket-123", 3600)
        pipeline.expire.assert_any_call("session:visiotrack:session-1:ticket", 3600)
        publish.assert_called_once_with(client, self.cfg)

    def test_renouvellement_refuse_ticket_non_associe(self):
        client = MagicMock()
        client.get.return_value = "autre-ticket"
        client.hgetall.return_value = {
            "status": "actif", "application_id": "visiotrack",
            "session_id": "session-1",
        }
        with patch.object(gate, "_config", return_value=self.cfg), \
             patch.object(gate, "_redis_client", return_value=(client, None)), \
             patch.object(gate.st, "session_state", {gate.SESSION_STATE_KEY: "session-1"}):
            self.assertFalse(gate.renouveler_acces_analyse("ticket-123"))
        client.pipeline.assert_not_called()

    def test_refresh_session_existante_actualise_updated_at(self):
        client = MagicMock()
        client.get.return_value = "ticket-123"
        client.exists.return_value = True
        with patch.object(gate, "_cleanup_expired"), \
             patch.object(gate, "_promote_waiting"), \
             patch.object(gate, "_snapshot", return_value={"statut": "actif"}):
            resultat = gate._claim_or_refresh(client, self.cfg, "session-1")
        self.assertEqual(resultat["statut"], "actif")
        client.hset.assert_called_once()
        self.assertEqual(client.hset.call_args.args[:2],
                         ("ticket:ticket-123", "updated_at"))
        client.expire.assert_any_call("ticket:ticket-123", 3600)
        client.expire.assert_any_call("session:visiotrack:session-1:ticket", 3600)


if __name__ == "__main__":
    unittest.main()
