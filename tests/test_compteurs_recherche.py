"""Compteurs, filtres, likes, commentaires et écriture atomique du TXT."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webapp as web


class CompteursRecherche(unittest.TestCase):
    def test_filtre_et_erreur_de_lecture_ne_gonflent_pas_le_txt(self):
        with tempfile.TemporaryDirectory() as dossier:
            requete = web.StartRequest(source_collecte="comptes", comptes=["media"], hashtag="test",
                french_only=False, collecter_commentaires=True, variables_txt=["profil", "likes"])
            job = web.Job("test", requete, Path(dossier))
            urls = [f"https://www.tiktok.com/@media/video/{i}" for i in (100,101,102)]
            def decouvrir(navigateur, arguments, comptes, hashtag, rapport, **options):
                rapport.update(hashtag_url="https://www.tiktok.com/tag/test",
                    candidats_ids=["100","101","102","999"], candidats_examines=4,
                    discovered_urls=urls, collecte_partielle=True)
                options["progress"](3)
                return urls
            publications = [
                {"id":"100", "author":"media", "url":urls[0], "description":"#test conservé",
                 "engagement":{"likes":{"valeur":5}}},
                {"id":"101", "author":"media", "url":urls[1], "description":"#autre exclu", "engagement":{}},
                web.scraper.WebDriverException("Lecture indisponible"),
            ]
            commentaire = {"id":"c1", "publication_id":"100", "auteur":"lecteur", "texte":"Commentaire conservé"}
            with patch("collecte.comptes.collecter_comptes_par_hashtag", side_effect=decouvrir), \
                 patch.object(web.scraper,"read_post",side_effect=publications), patch.object(job,"pause"), \
                 patch("collecte.commentaires.collecter_commentaires", return_value={"commentaires":[commentaire],"statut":"termine","exhaustif":False}) as commentaires:
                web.execute_job(job, driver_factory=lambda args: Mock())
            self.assertEqual(job.snapshot()["compteurs_collecte"], {"decouvertes":4,"retenues":3,"traitees":3,"exportees":1})
            self.assertEqual(job.status, "partial")
            self.assertIn("Collecte partielle", job.message)
            self.assertIn("*likes 5", job.path.read_text())
            self.assertIn("Commentaire conservé", job.path.read_text())
            self.assertNotIn("#autre", job.path.read_text())
            commentaires.assert_called_once()

    def test_echec_ecriture_ne_compte_pas_un_post_non_enregistre(self):
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job("test", web.StartRequest(hashtag="test"), Path(dossier))
            job.records = [{"id":"1","author":"media","url":"https://www.tiktok.com/@media/video/1","description":"Premier texte"}]
            job.save()
            job.records.append({"id":"2","author":"media","url":"https://www.tiktok.com/@media/video/2","description":"Second texte"})
            with patch.object(Path, "replace", side_effect=OSError("Écriture impossible")):
                with self.assertRaises(OSError):
                    job.save()
            self.assertEqual(job.exportees, 1)
            self.assertNotIn("Second texte", job.path.read_text())
