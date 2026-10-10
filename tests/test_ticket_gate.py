"""Accès Redis, identité privée et protection des traitements."""
import os
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
import ticket_gate as tickets
import webapp

class TestsTickets(unittest.TestCase):
    def test_variables_configurees_sont_respectees(self):
        with patch.dict(os.environ, {'APP_TICKET_ENFORCED':'1','APP_TICKET_ID':'scraptiktok',
            'APP_TICKET_MAX_ACTIVE':'8','APP_TICKET_COST':'1','CAPACITE_SERVEUR':'10',
            'APP_TICKET_TTL_SECONDS':'3600'}):
            cfg = tickets._config('autre', 'ScrapTikTok')
        self.assertEqual((cfg['app_id'],cfg['max_active'],cfg['cost'],cfg['global_capacity'],cfg['ttl_seconds']),
                         ('scraptiktok',8,1,10,3600))

    def test_ticket_actif_uniquement_pour_la_bonne_session_et_application(self):
        client = Mock(); client.get.return_value = 'ticket-test'
        with patch.dict(os.environ, {'APP_TICKET_ENFORCED':'1','APP_TICKET_ID':'scraptiktok'}), patch.object(tickets,'_redis_client',return_value=(client,None)):
            for statut, compte, session, attendu in [('actif','scraptiktok','privee',True),
                ('attente','scraptiktok','privee',False),('actif','autre','privee',False),
                ('actif','scraptiktok','autre',False)]:
                client.hgetall.return_value={'status':statut,'application_id':compte,'session_id':tickets.identifiant_ticket_session(session)}
                self.assertEqual(tickets.verifier_session_active('privee'),attendu)
            client.get.return_value=None
            self.assertFalse(tickets.verifier_session_active('privee'))

    def test_api_refuse_le_demarrage_sans_ticket_mais_permet_arret(self):
        manager=Mock(); manager.latest.return_value=None
        with TestClient(webapp.create_app(manager)) as client, patch.object(tickets,'verifier_session_active',return_value=False):
            client.get('/')
            self.assertEqual(client.post('/api/jobs',json={'hashtag':'test'},headers={'X-ScrapTikTok':'1'}).status_code,403)
            manager.start.assert_not_called()
            self.assertEqual(client.post('/api/jobs/existant/stop',json={},headers={'X-ScrapTikTok':'1'}).status_code,200)
            manager.get.return_value.stop.set.assert_called_once()

    def test_liberation_externe_arrete_les_traitements_au_nettoyage(self):
        with tempfile.TemporaryDirectory() as dossier:
            manager=webapp.Manager(data_dir=dossier)
            job=webapp.Job('a'*64,webapp.StartRequest(hashtag='test'),Path(dossier))
            job.video_busy=True; job.video_debut=time.monotonic(); manager.jobs[job.id]=job
            with patch.object(tickets,'verifier_session_active',return_value=False): manager.cleanup()
            self.assertTrue(job.stop.is_set()); self.assertTrue(job.video_stop.is_set())
