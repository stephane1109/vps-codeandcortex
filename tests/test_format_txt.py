"""Format étoilé du TXT, compteurs distincts et déplacement facultatif des hashtags."""
from copy import deepcopy
from itertools import combinations
import tempfile
import unittest
from pathlib import Path

import webapp as web
from collecte.engagement import extraire_engagement


class FormatTxt(unittest.TestCase):
    def test_ancien_choix_url_repris_comme_id_sans_arrondir_le_numero(self):
        settings = web.StartRequest(hashtag="test", variables_txt=["url", "id", "profil"])
        self.assertEqual(settings.variables_txt, ["id", "profil"])
        publication = self.publication()
        self.assertEqual(web.entete_publication(publication, ["url"]), "*id_7694262098129603843\n")
        texte = web.text_export([publication], True, variables_txt=["id"])
        self.assertTrue(texte.startswith("*id_7694262098129603843\n"))
        self.assertNotIn(publication["url"], texte)
        self.assertNotIn("*url_", texte)
        self.assertEqual(web.entete_publication({}, ["id"]), "*id_indetermine\n")

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
        texte = web.text_export([publication], True, variables_txt=["date", "profil", "id",
            "vues", "likes", "partages", "commentaires", "favoris", "hashtags"])
        self.assertEqual(texte,
            "*date_2026-10-08 *profil_@bfmtv *id_7694262098129603843 "
            "*vues_8000000 *likes_576000 *partages_42 *comment_123 *favoris_456\n"
            "Les élèves manifestent.\n#blocage #lycee #manifestation #lyceen #lyon\n")
        self.assertEqual(publication, avant)
        self.assertNotIn("*hashtags", texte)
        self.assertNotIn("*republications", texte)
        self.assertNotIn("*urlvidéo", texte)

    def test_options_independantes_pour_les_huit_variables(self):
        marqueurs = {"date": "*date_", "profil": "*profil_", "id": "*id_", "vues": "*vues_",
                     "likes": "*likes_", "partages": "*partages_", "commentaires": "*comment_", "favoris": "*favoris_"}
        publication = self.publication()
        for taille in range(len(marqueurs) + 1):
            for selection in combinations(marqueurs, taille):
                with self.subTest(selection=selection):
                    texte = web.text_export([publication], True, True, list(selection))
                    for nom, marqueur in marqueurs.items():
                        self.assertEqual(marqueur in texte, nom in selection)
                    self.assertIn(publication["description"], texte)

    def test_deux_sources_iramuteq_uniquement_sur_option_explicite(self):
        publication = self.publication()
        publication.update(
            author="ulyces", description="La police réprime violemment les manifestants. Une honte pour notre démocratie !",
            resume_ia_tiktok="Des tensions ont été observées entre les forces de l'ordre et des participants lors d'une manifestation.",
        )
        avant = deepcopy(publication)
        sans_ia = web.text_export([publication], True, variables_txt=["profil"])
        self.assertNotIn("source_ia", sans_ia)
        self.assertNotIn("Des tensions ont été", sans_ia)
        texte = web.text_export([publication], True, variables_txt=["profil"],
                               inclure_texte_genere_ia=True, themes=["manifestation"])
        self.assertEqual(
            texte,
            "**** *source_original *theme_manifestation *profil_@ulyces\n"
            "La police réprime violemment les manifestants. Une honte pour notre démocratie !\n\n"
            "**** *source_ia *theme_manifestation *profil_@ulyces\n"
            "Des tensions ont été observées entre les forces de l'ordre et des participants lors d'une manifestation.\n",
        )
        self.assertEqual(publication, avant)

    def test_ia_absente_ne_cree_pas_de_fausse_source(self):
        publication = self.publication()
        publication["resume_ia_tiktok"] = ""
        publication["texte_secondaire"] = "Texte non identifié : ne pas étiqueter IA"
        sortie = web.text_export([publication], True, variables_txt=["id"],
                                inclure_texte_genere_ia=True, themes=["manifestation"])
        self.assertEqual(sortie.count("****"), 1)
        self.assertIn("*source_original", sortie)
        self.assertNotIn("*source_ia", sortie)
        self.assertNotIn("Texte non identifié", sortie)

    def test_option_ia_propagee_dans_sauvegarde_et_export(self):
        settings = web.StartRequest(hashtag="manifestation", inclure_texte_genere_ia=True,
                                    variables_txt=["profil"])
        publication = self.publication()
        publication["resume_ia_tiktok"] = "Résumé vérifié par le navigateur."
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job("test", settings, Path(dossier))
            job.records.append(publication)
            job.save()
            texte = job.path.read_text(encoding="utf-8")
            self.assertEqual(texte.count("****"), 2)
            self.assertIn("*source_ia *theme_manifestation", texte)
            self.assertEqual(job.texte_a_exporter(), texte)

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
        variables = ["date", "profil", "id", "vues", "likes", "partages", "commentaires", "favoris", "hashtags"]
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

    def test_arobase_optionnelle_avec_et_sans_ia_sans_compte_automatique(self):
        publication = dict(self.publication(), author='@baddydeadpool',
                           description='Texte authentique @autre.', resume_ia_tiktok='Un résumé distinct @autre.')
        for ia in (False, True):
            for supprimer in (False, True):
                texte = web.text_export([publication], True, variables_txt=['date', 'profil'],
                    inclure_texte_genere_ia=ia, supprimer_arobase_profil=supprimer)
                profil = '*profil_' + ('' if supprimer else '@') + 'baddydeadpool'
                self.assertEqual(texte.count(profil), 2 if ia else 1)
                self.assertNotIn('*compte_', texte)
                self.assertIn('@autre', texte)
        texte = web.text_export([publication], True, variables_txt=['date'], inclure_texte_genere_ia=True)
        self.assertNotIn('*profil_', texte)
        self.assertNotIn('*compte_', texte)

    def test_memes_variables_dans_les_deux_sources_et_apercu(self):
        publication = self.publication()
        publication["resume_ia_tiktok"] = "Résumé TikTok extrait et identifié comme IA."
        variables = ["date", "profil", "id", "vues", "likes", "partages", "commentaires", "favoris"]
        texte = web.text_export([publication], True, variables_txt=variables,
                                inclure_texte_genere_ia=True)
        entetes = [ligne for ligne in texte.splitlines() if ligne.startswith("****")]
        self.assertEqual(len(entetes), 2)
        self.assertEqual(entetes[0].replace("*source_original", "*source_ia"), entetes[1])
        for nom in ("date", "profil", "id", "vues", "likes", "partages", "comment", "favoris"):
            self.assertIn("*" + nom + "_", entetes[0])
        with tempfile.TemporaryDirectory() as dossier:
            job = web.Job("test", web.StartRequest(hashtag="manifestation", variables_txt=variables,
                          inclure_texte_genere_ia=True), Path(dossier))
            job.records.append(publication)
            self.assertEqual(job.snapshot()["preview"][0]["texte_export"], job.texte_a_exporter())


if __name__ == "__main__":
    unittest.main()
