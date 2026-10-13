"""Format étoilé du TXT, compteurs distincts et déplacement facultatif des hashtags."""
from copy import deepcopy
from itertools import combinations
import tempfile
import unittest
from pathlib import Path

import webapp as web
from collecte.engagement import extraire_engagement


class FormatTxt(unittest.TestCase):
    def publication(self):
        return {"id": "7694262098129603843", "author": "bfmtv",
            "url": "https://www.tiktok.com/@bfmtv/video/7694262098129603843",
            "created_at": "2026-10-08T11:46:46+00:00",
            "description": "Les élèves manifestent.\n#blocage #lycee #manifestation #lyceen #lyon",
            "hashtags": ["blocage", "lycee", "manifestation", "lyceen", "lyon"],
            "engagement": extraire_engagement({"stats": {"playCount": 8000000,
                "diggCount": 576000, "repostCount": 0, "shareCount": 42, "commentCount": 123, "collectCount": 456}})}

    def test_format_demande_et_compteurs_reels(self):
        publication = self.publication()
        avant = deepcopy(publication)
        texte = web.text_export([publication], True, variables_txt=["date", "profil", "url",
            "vues", "likes", "partages", "commentaires", "favoris", "hashtags"])
        self.assertEqual(texte,
            "*date_2026-10-08 *profil_@bfmtv *url_https://www.tiktok.com/@bfmtv/video/7694262098129603843 "
            "*vues_8000000 *likes_576000 *partages_42 *comment_123 *favoris_456\n"
            "Les élèves manifestent.\n#blocage #lycee #manifestation #lyceen #lyon\n")
        self.assertEqual(publication, avant)
        self.assertNotIn("*hashtags", texte)
        self.assertNotIn("*republications", texte)
        self.assertNotIn("*urlvidéo", texte)

    def test_options_independantes_pour_les_huit_variables(self):
        marqueurs = {"date": "*date_", "profil": "*profil_", "url": "*url_", "vues": "*vues_",
                     "likes": "*likes_", "partages": "*partages_", "commentaires": "*comment_", "favoris": "*favoris_"}
        publication = self.publication()
        for taille in range(len(marqueurs) + 1):
            for selection in combinations(marqueurs, taille):
                with self.subTest(selection=selection):
                    texte = web.text_export([publication], True, True, list(selection))
                    for nom, marqueur in marqueurs.items():
                        self.assertEqual(marqueur in texte, nom in selection)
                    self.assertIn(publication["description"], texte)

    def test_partages_absents_ne_reutilisent_pas_repostcount(self):
        publication = self.publication()
        publication["engagement"] = extraire_engagement({"stats": {"repostCount": 15, "commentCount": 0}})
        texte = web.text_export([publication], False, variables_txt=["partages", "commentaires"])
        self.assertTrue(texte.startswith("*partages_indetermine *comment_0\n"))
        publication["engagement"] = extraire_engagement({"stats": {"shareCount": 0}})
        texte = web.text_export([publication], False, variables_txt=["partages", "commentaires"])
        self.assertTrue(texte.startswith("*partages_0 *comment_indetermine\n"))

    def test_favoris_facultatifs_zero_et_valeur_inconnue(self):
        for brut, attendu in [(456, "456"), (0, "0"), (None, "indetermine")]:
            with self.subTest(favoris=brut):
                publication = self.publication()
                publication["engagement"] = extraire_engagement({"stats": {"collectCount": brut, "diggCount": 999}})
                self.assertEqual(web.entete_publication(publication, ["favoris"]), f"*favoris_{attendu}\n")
                self.assertNotIn("*favoris_", web.text_export([publication], False, variables_txt=[]))
        variables = ["date", "profil", "url", "vues", "likes", "partages", "commentaires", "favoris", "hashtags"]
        settings = web.StartRequest(hashtag="manifestation", variables_txt=variables)
        self.assertEqual(settings.variables_txt, variables)

    def test_compteur_commentaires_independant_des_textes_recuperes(self):
        publication = self.publication()
        commentaire = {"publication_id": publication["id"], "texte": "Un seul commentaire récupéré."}
        for recuperes in ([], [commentaire]):
            with self.subTest(commentaires=recuperes):
                texte = web.text_export([publication], False,
                    variables_txt=["commentaires", "hashtags"], commentaires=recuperes)
                self.assertTrue(texte.startswith("*comment_123\n"))
                self.assertEqual("Commentaire 1 :" in texte, bool(recuperes))
                if recuperes:
                    self.assertLess(texte.index("#blocage"), texte.index("Commentaire 1 :"))
        texte = web.text_export([publication], False, variables_txt=[], commentaires=[commentaire])
        self.assertNotIn("*comment_", texte)
        self.assertIn(commentaire["texte"], texte)

    def test_hashtags_sous_le_texte_sans_repetition_et_sans_modification_du_record(self):
        publication = self.publication()
        publication.update(description="Avant #Manifestation  après.\nAutre ligne #lycéen #Manifestation",
                           hashtags=["#Manifestation", "manifestation"])
        avant = deepcopy(publication)
        texte = web.text_export([publication], False, variables_txt=["hashtags"])
        self.assertEqual(texte, "Avant après.\nAutre ligne\n#Manifestation #lycéen\n")
        self.assertEqual(publication, avant)
        self.assertEqual(web.text_export([publication], False, variables_txt=[]), publication["description"] + "\n")
        publication.update(description="#lycéen #lycéen", hashtags=[])
        self.assertEqual(web.text_export([publication], False, variables_txt=["hashtags"]), "#lycéen\n")
        publication.update(description="Une légende sans hashtag.", hashtags=[])
        self.assertEqual(web.text_export([publication], False, variables_txt=["hashtags"]), publication["description"] + "\n")

    def test_liens_dans_la_legende_conserves(self):
        publication = self.publication()
        publication.update(description="Lire https://exemple.fr/page#section #lycee", hashtags=["lycee"])
        self.assertEqual(web.text_export([publication], False, variables_txt=["hashtags"]),
                         "Lire https://exemple.fr/page#section\n#lycee\n")

    def test_date_sans_heure_et_absence_explicite(self):
        for date, attendu in [("2026-10-08T11:46:46+00:00", "2026-10-08"),
                              ("2026-10-08T11:46:46Z", "2026-10-08"),
                              ("2026-10-08", "2026-10-08"), (None, "indetermine"),
                              ("2026-99-99", "indetermine")]:
            with self.subTest(date=date):
                self.assertEqual(web.entete_publication({"created_at": date}, ["date"]), f"*date_{attendu}\n")

    def test_estimation_reste_dans_les_mesures_brutes(self):
        publication = self.publication()
        publication["engagement"] = extraire_engagement(dom={"vues": "8M"})
        texte = web.text_export([publication], False, variables_txt=["vues"])
        self.assertTrue(texte.startswith("*vues_8000000\n"))
        self.assertEqual(publication["engagement"]["vues"]["brut"], "8M")
        self.assertTrue(publication["engagement"]["vues"]["estime"])

    def test_anciennes_selections_migrees_et_fichier_sauvegarde(self):
        settings = web.StartRequest(hashtag="manifestation", variables_txt=["republications", "partages", "commentaires"])
        self.assertEqual(settings.variables_txt, ["partages", "commentaires"])
        publication = self.publication()
        self.assertEqual(web.entete_publication(publication, ["republications"]), "*partages_42\n")
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job("test", settings, Path(dossier))
            job.records.append(publication)
            job.save()
            self.assertTrue(job.path.read_text().startswith("*partages_42 *comment_123\n"))
            self.assertFalse(settings.collecter_commentaires)


if __name__ == "__main__":
    unittest.main()
