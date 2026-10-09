"""Disponibilité réelle et traitement vidéo lancé par l’API, sans téléchargement réseau."""
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from video.disponibilite import video_disponible
from fixtures_video import VIDEO, ecrire_video
import webapp as web


class TestsDisponibilite(unittest.TestCase):
    def test_une_variable_ne_remplace_pas_les_dependances(self):
        with patch.dict(os.environ, {'INSTALL_VIDEO':'1'}), patch('video.disponibilite.find_spec', return_value=None):
            self.assertFalse(video_disponible())

    def test_profil_texte_et_detection_sans_charger_les_moteurs(self):
        with patch('video.disponibilite.find_spec', return_value=object()) as modules, patch('video.disponibilite.shutil.which', return_value='/ffmpeg'):
            with patch.dict(os.environ, {'INSTALL_VIDEO':'0'}):
                self.assertFalse(video_disponible())
                modules.assert_not_called()
            with patch.dict(os.environ, {'INSTALL_VIDEO':'base'}):
                self.assertTrue(video_disponible())

    @unittest.skipUnless(VIDEO and video_disponible(), 'Comparaison vidéo non installée')
    def test_api_compare_de_vrais_fichiers_et_exporte(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get('/')
                self.assertTrue(client.get('/api/configuration').json()['video_disponible'])
                job=web.Job(client.cookies[web.COOKIE],web.StartRequest(hashtag='test',enrichir=True),Path(d))
                manager.jobs[job.id]=job
                videos=job.directory/'videos'; videos.mkdir(exist_ok=True)
                ecrire_video(videos/'1.mp4')
                shutil.copyfile(videos/'1.mp4',videos/'2.mp4')
                ecrire_video(videos/'3.mp4',recadrer=True)
                ecrire_video(videos/'4.mp4',graines=(51,52,53,54,55))
                job.publications=[{'id':str(i),'url':f'https://www.tiktok.com/@media{i}/video/{i}',
                    'author':f'media{i}','media_id':f'm{i}','description':'Une description en français.',
                    'engagement':{}} for i in range(1,5)]
                (job.directory/'publications.json').write_text(json.dumps(job.publications))
                job.update(busy=False,status='completed',archive_prete=True)
                reponse=client.post(f'/api/jobs/{job.id}/video',headers={'X-ScrapTikTok':'1'},
                    json={'comparer_sha256':True,'comparer_sequences':True})
                self.assertEqual(reponse.status_code,202,reponse.text)
                limite=time.monotonic()+60
                while job.video_busy and time.monotonic()<limite: time.sleep(.1)
                self.assertFalse(job.video_busy,'Le traitement doit se terminer dans le délai de test')
                journal=(job.directory/'traitement.log').read_text()
                self.assertEqual(job.video_statut,'termine',journal)
                archive=client.get(f'/api/jobs/{job.id}/archive')
                self.assertEqual(archive.status_code,200)
                with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
                    comparaisons=json.loads(z.read('comparaisons.json'))
                par_paire={(c['a'],c['b']):c['type'] for c in comparaisons}
                self.assertEqual(par_paire['1','2'],'fichier_identique')
                self.assertIn(par_paire['1','3'],('reemploi_sequence','videos_visuellement_quasi_identiques'))
                self.assertEqual(par_paire['1','4'],'aucun_reemploi_detecte')
