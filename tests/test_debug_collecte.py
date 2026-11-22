"""Les diagnostics distinguent les arrêts sans exporter de données de connexion."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from webapp import Job, Manager, StartRequest


class TestsDebugCollecte(unittest.TestCase):
    def test_causes_automatiques_et_premiere_cause_conservee(self):
        for cause in ('acces_inactif','inactivite','duree_maximale'):
            with self.subTest(cause=cause),tempfile.TemporaryDirectory() as dossier:
                gestionnaire=Manager(data_dir=dossier)
                tache=Job('secret-session',StartRequest(hashtag='test'),Path(dossier))
                gestionnaire.jobs[tache.id]=tache
                tache.update(discovered=383,processed=65,publication_en_cours='7552202548308872470')
                if cause=='inactivite': tache.last_seen=time.monotonic()-gestionnaire.idle_timeout-1
                if cause=='duree_maximale': tache.created=time.monotonic()-gestionnaire.max_duration-1
                with patch('ticket_gate.verifier_session_active',return_value=cause!='acces_inactif'):
                    gestionnaire.cleanup()
                tache.demander_arret('utilisateur')
                diagnostic=tache.diagnostic_collecte()
                self.assertEqual(diagnostic['cause_arret']['code'],cause)
                self.assertEqual(diagnostic['compteurs']['restantes'],318)
                self.assertNotIn('secret-session',str(diagnostic))

    def test_historique_borne_et_arret_manuel(self):
        with tempfile.TemporaryDirectory() as dossier:
            tache=Job('secret',StartRequest(hashtag='test'),Path(dossier))
            for nombre in range(200): tache.update(processed=nombre)
            tache.demander_arret('utilisateur')
            self.assertEqual(len(tache.snapshot()['debug_collecte']['evenements_recents']),100)
            self.assertEqual(tache.cause_arret['code'],'utilisateur')
