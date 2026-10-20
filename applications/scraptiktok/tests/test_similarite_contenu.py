"""La proximité de contenu reste indépendante des preuves de séquences communes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fixtures_video import VIDEO, ecrire_video
from video.embeddings import construire_similarites_semantiques
from video.lots import analyser_lot
from video.parametres import charger_parametres


@unittest.skipUnless(VIDEO, 'OpenCV requis')
class TestsSimilariteContenu(unittest.TestCase):
    def preparer(self, dossier):
        (dossier/'videos').mkdir(parents=True)
        publications=[]
        for i in (1,2):
            ecrire_video(dossier/'videos'/f'{i}.mp4', graines=tuple(range(i*10,i*10+5)))
            publications.append({'id':str(i),'author':str(i),'url':f'https://www.tiktok.com/@test/video/{i}',
                                 'description':'Texte','engagement':{}})
        (dossier/'publications.json').write_text(json.dumps(publications))
        parametres=charger_parametres()
        parametres.update(embeddings=True, comparer_sequences=False, comparer_sha256=False, conserver_images=False)
        return parametres

    def test_contenu_exporte_sans_reemploi_ni_orb(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier=Path(temporaire)/'sessions'/'lot'
            parametres=self.preparer(dossier)
            embedding={'statut':'mesure','vecteur':[1.,0.,0.], 'modele':'test','poids':'test'}
            with patch('video.lots.calculer_embeddings',return_value=embedding), patch('video.recherche_similaires.comparer_orb',side_effect=AssertionError('ORB non requis')):
                analyser_lot(dossier,parametres)
            self.assertEqual(json.loads((dossier/'groupes_visuels.json').read_text()),[])
            similaires=json.loads((dossier/'similarites_semantiques.json').read_text())
            self.assertEqual(len(similaires),1)
            self.assertEqual(similaires[0]['score_cosinus'],1.)
            self.assertFalse(similaires[0]['preuve_reemploi'])
            self.assertIn('https://www.tiktok.com/',similaires[0]['url_a'])
            self.assertIn('score_cosinus',(dossier/'similarites_semantiques.csv').read_text())
            diagnostic=json.loads((dossier/'diagnostic_visuel.json').read_text())
            self.assertEqual(diagnostic['semantique']['statuts'],{'mesure':2})

    def test_modele_indisponible_signale(self):
        with tempfile.TemporaryDirectory() as temporaire:
            dossier=Path(temporaire)/'sessions'/'lot'; parametres=self.preparer(dossier)
            with patch('video.lots.calculer_embeddings',return_value={'statut':'poids_locaux_requis','vecteur':None}):
                analyser_lot(dossier,parametres)
            diagnostic=json.loads((dossier/'diagnostic_visuel.json').read_text())
            self.assertEqual(diagnostic['semantique']['statuts'],{'poids_locaux_requis':2})
            self.assertEqual(json.loads((dossier/'similarites_semantiques.json').read_text()),[])

    def test_sequence_seule_non_exportee_comme_contenu(self):
        self.assertEqual(construire_similarites_semantiques([{'type':'reemploi_sequence'}]),[])
