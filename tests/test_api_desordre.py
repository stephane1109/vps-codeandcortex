"""L'analyse facultative et ses exports restent privés, avec réservation du calcul CPU."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import webapp as web
from analyse_desordre.service import ecrire_etat


class TestsApiDesordre(unittest.TestCase):
    def test_duree_analyse_defaut_60_secondes(self):
        from analyse_desordre.parametres import Parametres
        self.assertEqual(web.OptionsDesordre().duree_max, 60)
        self.assertEqual(Parametres().duree_max, 60)
        self.assertEqual(web.OptionsDesordre(duree_max=3600).duree_max, 3600)

    def test_exports_prives_et_lancement_explicitement_valide(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get('/')
                job=web.Job(client.cookies[web.COOKIE],web.StartRequest(hashtag='test',enrichir=True),Path(d))
                job.update(busy=False,archive_prete=True)
                manager.jobs[job.id]=job
                (job.directory/'publications.json').write_text('[{"id":"1"}]')
                base=f'/api/jobs/{job.id}/desordre'
                self.assertEqual(client.get(base).json()['etat']['statut'],'non_lance')
                self.assertEqual(client.post(base,json={}).status_code,403)
                entetes={'X-ScrapTikTok':'1'}
                with patch('ticket_gate.verifier_session_active',return_value=True),patch('analyse_desordre.service.dependances_disponibles',return_value=True):
                    self.assertEqual(client.post(base,json={},headers=entetes).status_code,409)
                    (job.directory/'videos').mkdir();(job.directory/'videos'/'id_1.mp4').write_bytes(b'test')
                    self.assertEqual(client.post(base,json={'frequence':0},headers=entetes).status_code,422)
                    with patch('webapp.executer_desordre') as executer:
                        self.assertEqual(client.post(base,json={},headers=entetes).status_code,202)
                        job.video_thread.join(2);self.assertTrue(executer.called)
                        self.assertTrue(job.video_busy)
                        self.assertEqual(client.post(base,json={},headers=entetes).status_code,409)
                job.update(video_busy=False)
                dossier=job.directory/'desordre_0123456789abcdef';dossier.mkdir()
                ecrire_etat(job.directory,{'statut':'termine','dossier':dossier.name})
                (dossier/'indicateurs_engagement.csv').write_text('publication_id,likes,indice_desordre\n7697829530844663072,100,12.3\n')
                resultat=client.get(base).json()
                self.assertEqual(resultat['indicateurs'][0]['publication_id'],'7697829530844663072')
                self.assertEqual(resultat['indicateurs'][0]['likes'],100)
                self.assertEqual(client.get(base+'/export/indicateurs_engagement.csv').status_code,200)
                self.assertEqual(client.get(base+'/export/desordre.log').status_code,404)
                for statut in ('en_cours','echec','interrompu'):
                    ecrire_etat(job.directory,{'statut':statut,'dossier':dossier.name})
                    self.assertEqual(len(client.get(base).json()['indicateurs']),1)
                    self.assertEqual(client.get(base+'/export/indicateurs_engagement.csv').status_code,200)
                client.cookies.clear();client.get('/')
                self.assertEqual(client.get(base).status_code,404)
                self.assertEqual(client.get(base+'/export/indicateurs_engagement.csv').status_code,404)

    def test_arret_libere_la_reservation_cpu(self):
        from unittest.mock import MagicMock
        from analyse_desordre.service import lire_etat
        with tempfile.TemporaryDirectory() as d:
            job=web.Job('a'*64,web.StartRequest(hashtag='test',enrichir=True),Path(d))
            job.update(video_busy=True)
            job.video_stop.set()
            ecrire_etat(job.directory,{'statut':'en_cours','dossier':'desordre_0123456789abcdef'})
            processus=MagicMock();processus.poll.side_effect=[None,0]
            with patch('webapp.subprocess.Popen',return_value=processus),patch('webapp.os.killpg') as arreter:
                web.executer_desordre(job,web.OptionsDesordre(),'desordre_0123456789abcdef')
            self.assertTrue(arreter.called)
            self.assertFalse(job.video_busy)
            self.assertIsNone(job.video_process)
            self.assertEqual(lire_etat(job.directory)['statut'],'interrompu')

    def test_collecte_sans_mp4_autorise_preparation_explicitement(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get('/')
                job=web.Job(client.cookies[web.COOKIE],web.StartRequest(hashtag='test',enrichir=True),Path(d))
                job.update(busy=False,archive_prete=True);manager.jobs[job.id]=job
                (job.directory/'publications.json').write_text(json.dumps([{'id':'123','url':'https://www.tiktok.com/@test/video/123'}]))
                url=f'/api/jobs/{job.id}/desordre';entetes={'X-ScrapTikTok':'1'}
                inventaire=client.get(url).json()
                self.assertEqual(inventaire['mp4_locaux'],0);self.assertEqual(inventaire['mp4_telechargeables'],1)
                with patch('ticket_gate.verifier_session_active',return_value=True),patch('analyse_desordre.service.dependances_disponibles',return_value=True),patch('webapp.executer_desordre') as executer:
                    self.assertEqual(client.post(url,json={'telecharger_manquants':False},headers=entetes).status_code,409)
                    self.assertEqual(client.post(url,json={'telecharger_manquants':True},headers=entetes).status_code,202)
                    job.video_thread.join(2);self.assertTrue(executer.call_args.args[1].telecharger_manquants)
                job.update(video_busy=False)
