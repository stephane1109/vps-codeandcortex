"""Les échecs yt-dlp doivent expliquer la cause, jamais afficher la commande brute."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from collecte.telechargement import telecharger_video, expliquer_echec, ErreurTelechargement


class TestsTelechargementMultimodal(unittest.TestCase):
    def test_classification_sans_sortie_sensible(self):
        for texte,statut in [('ERROR: HTTP Error 403: Forbidden','acces_refuse'),
                             ('ERROR: HTTP Error 429','requetes_limitees'),
                             ('ERROR: Unable to extract webpage video data','extraction_impossible'),
                             ('video does not pass filter duration <= 60','duree_depassee'),
                             ('File is larger than max-filesize','taille_depassee'),
                             ('ERROR: invalid filter','configuration_invalide')]:
            erreur=expliquer_echec(texte+' https://cdn.example/secret-token',1)
            self.assertEqual(erreur.statut,statut)
            self.assertNotIn('secret-token',str(erreur))

    def test_echec_nettoie_fichier_et_retient_cause(self):
        with tempfile.TemporaryDirectory() as d:
            chemin=Path(d)/'7697829530844663072.mp4';chemin.write_bytes(b'incomplet')
            with patch('collecte.telechargement.subprocess.run',return_value=subprocess.CompletedProcess([],1,b'',b'HTTP Error 403')):
                with self.assertRaises(ErreurTelechargement) as erreur: self.telecharger(d)
            self.assertEqual(erreur.exception.statut,'acces_refuse')
            self.assertFalse(chemin.exists())

    def test_filtre_sans_fichier_malgre_code_zero(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('collecte.telechargement.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'Video does not pass filter',b'')):
                with self.assertRaises(ErreurTelechargement) as erreur: self.telecharger(d)
            self.assertEqual(erreur.exception.statut,'duree_depassee')

    def test_timeout_sans_commande(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('collecte.telechargement.subprocess.run',side_effect=subprocess.TimeoutExpired(['commande-sensible'],180)):
                with self.assertRaises(ErreurTelechargement) as erreur: self.telecharger(d)
            self.assertEqual(erreur.exception.statut,'delai_depasse')
            self.assertNotIn('commande-sensible',str(erreur.exception))

    def test_succes(self):
        with tempfile.TemporaryDirectory() as d:
            def executer(commande,**options):
                Path(d,'7697829530844663072.mp4').write_bytes(b'mp4-test')
                self.assertIn('--ignore-config',commande)
                return subprocess.CompletedProcess(commande,0,b'',b'')
            with patch('collecte.telechargement.subprocess.run',side_effect=executer):
                self.assertTrue(self.telecharger(d).is_file())

    def telecharger(self,dossier):
        return telecharger_video({'id':'7697829530844663072','url':'https://www.tiktok.com/@brutofficiel/video/7697829530844663072'},dossier,
            {'espace_libre_min_mo':0,'taille_max_mo':150,'duree_max_s':600})
