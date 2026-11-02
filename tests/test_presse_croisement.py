"""Tests du croisement facultatif compte média × hashtag, indépendants du réseau."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webapp as web


def publication(compte, identifiant, description, avec_ia=False):
    fiche = {
        "id": str(identifiant),
        "url": f"https://www.tiktok.com/@{compte}/video/{identifiant}",
        "author": compte,
        "description": description,
        "created_at": "2026-10-20T14:00:00+00:00",
        "engagement": {},
        "status": "ok",
    }
    if avec_ia:
        fiche["resume_ia_tiktok"] = "Résumé élaboré par TikTok."
    return fiche


class CroisementPresseTests(unittest.TestCase):
    def test_option_desactivee_et_requetes_anterieures(self):
        sans = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                                hashtag="#ancien", second_hashtag="#memoire",
                                croiser_hashtag_presse=False,
                                hashtag_presse="#manifestation")
        self.assertEqual(sans.hashtag_presse, "")
        self.assertFalse(sans.croiser_hashtag_presse)
        self.assertEqual(sans.hashtags, [])
        self.assertTrue(web.matches_hashtags("Une publication sans hashtag.", sans))
        self.assertNotIn("_hashtag_", sans.filename)

    def test_option_activee_avec_validation_et_matching_strict(self):
        params = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                                  croiser_hashtag_presse=True,
                                  hashtag_presse="#MANIFESTATION")
        self.assertEqual(params.hashtag_presse, "MANIFESTATION")
        self.assertTrue(web.matches_hashtags("Des lycéens #manifestation.", params))
        self.assertTrue(web.matches_hashtags("Des lycéens #MANIFESTATION.", params))
        self.assertFalse(web.matches_hashtags("Des lycéens manifestent.", params))
        self.assertFalse(web.matches_hashtags("Une #manifestations lycéenne.", params))
        self.assertFalse(web.matches_hashtags("#antimanifestation.", params))
        self.assertIn("hashtag_MANIFESTATION", params.filename)
        with self.assertRaises(ValueError):
            web.StartRequest(source_collecte="presse", medias=["lemonde"],
                             croiser_hashtag_presse=True)
        with self.assertRaises(ValueError):
            web.StartRequest(source_collecte="presse", medias=["lemonde"],
                             croiser_hashtag_presse=True,
                             hashtag_presse="deux mots")
        # Les modes Hashtags et Comptes ignorent les réglages Presse.
        autres = web.StartRequest(hashtag="mobilisation",
                                  croiser_hashtag_presse=True,
                                  hashtag_presse="#manifestation")
        self.assertEqual(autres.hashtag_presse, "")
        self.assertFalse(autres.croiser_hashtag_presse)
        self.assertTrue(web.matches_hashtags("#mobilisation", autres))

    def test_plusieurs_hashtags_et_ou_validation_et_compatibilite(self):
        """Une liste dédoublonnée accepte deux opérateurs sans changer les anciens appels."""
        criteres = ["#manifestation", "#blocage", "#MANIFESTATION"]
        commun = dict(source_collecte="presse", medias=["lemonde"],
                      croiser_hashtag_presse=True, hashtags_presse=criteres)
        disjonction = web.StartRequest(**commun, operator_presse="OR")
        conjonction = web.StartRequest(**commun, operator_presse="AND")
        self.assertEqual(disjonction.hashtags_presse, ["manifestation", "blocage"])
        self.assertEqual(disjonction.hashtag_presse, "manifestation")
        self.assertTrue(web.matches_hashtags("Une #manifestation", disjonction))
        self.assertTrue(web.matches_hashtags("Un #blocage", disjonction))
        self.assertFalse(web.matches_hashtags("Aucune étiquette", disjonction))
        self.assertFalse(web.matches_hashtags("Une #manifestations", disjonction))
        self.assertFalse(web.matches_hashtags("Une #manifestation", conjonction))
        self.assertTrue(web.matches_hashtags("Une #manifestation et un #blocage",
                                             conjonction))
        self.assertTrue(web.matches_hashtags(
            "Sans étiquette dans la légende", disjonction,
            hashtags_observes=["blocage"]))
        self.assertEqual(
            web.hashtags_correspondants_presse(
                "Une #manifestation et un #blocage", disjonction),
            ["manifestation", "blocage"])
        self.assertIn("OU", disjonction.libelle)
        self.assertIn("_OU_", disjonction.filename)
        self.assertIn("_ET_", conjonction.filename)
        with self.assertRaises(ValueError):
            web.StartRequest(**{**commun, "hashtags_presse": [
                "tag" + str(indice) for indice in range(11)]})
        with self.assertRaises(ValueError):
            web.StartRequest(**{**commun, "hashtags_exclus": ["blocage"]})

    def test_les_medias_sont_filtres_apres_decouverte_et_compteurs_corrects(self):
        with tempfile.TemporaryDirectory() as dossier:
            reglages = web.StartRequest(source_collecte="presse",
                                       medias=["lemonde", "franceinfo"],
                                       limit=3, french_only=False,
                                       croiser_hashtag_presse=True,
                                       hashtag_presse="#manifestation",
                                       variables_txt=["profil"])
            job = web.Job("test-croisement", reglages, Path(dossier))
            job.base = None
            medias = {
                "lemondefr": [
                    publication("lemondefr", "7701005447410552097", "Une #manifestation pacifique."),
                    publication("lemondefr", "7701005447410552098", "Politique et démocratie."),
                    publication("lemondefr", "7701005447410552099", "La #manifestations."),
                ],
                "franceinfo": [
                    publication("franceinfo", "7701005447410552096", "Mobilisation #MANIFESTATION."),
                ],
            }
            records = {p["url"]: p for sources in medias.values() for p in sources}

            def decouvrir(source, rapport, **kwargs):
                return [p["url"] for p in medias[source["compte"]]]

            with patch("connect_presse.ConnexionPresse.decouvrir", side_effect=decouvrir), \
                 patch.object(web.scraper, "read_post",
                              side_effect=lambda driver, url, *a, **k: dict(records[url])), \
                 patch.object(job, "pause"):
                web.execute_job(job, driver_factory=lambda args: Mock())
            self.assertEqual(job.processed, 4)
            self.assertEqual(len(job.records), 2)
            self.assertEqual(job.filtered, 2)
            self.assertEqual(job.correspondances_hashtags, 2)
            self.assertEqual(job.bilan_hashtags, {"manifestation": 2})
            self.assertEqual([r["author"] for r in job.records],
                             ["lemondefr", "franceinfo"])
            texte = job.texte_a_exporter()
            self.assertIn("Une #manifestation pacifique.", texte)
            self.assertIn("Mobilisation #MANIFESTATION.", texte)
            self.assertNotIn("Politique et démocratie.", texte)
            self.assertNotIn("La #manifestations.", texte)
            apercu = job.snapshot()
            self.assertTrue(apercu["croiser_hashtag_presse"])
            self.assertEqual(apercu["hashtag_presse"], "manifestation")
            self.assertEqual(apercu["bilan_hashtags"]["manifestation"], 2)

    def test_collecte_multi_hashtags_et_exports_csv(self):
        """Le filtrage des vidéos et les colonnes restent cohérents après la collecte."""
        from corpus.publications_csv import ligne_publication_csv
        from corpus.construction import lignes_engagement
        medias = {
            "lemondefr": [
                publication("lemondefr", "7701005447410552031",
                            "Des jeunes #manifestation."),
                publication("lemondefr", "7701005447410552032",
                            "Un #blocage du lycée."),
                publication("lemondefr", "7701005447410552033",
                            "#manifestation et #blocage."),
                publication("lemondefr", "7701005447410552034",
                            "Publication sans hashtag."),
            ]
        }
        videos = {p["url"]: p for p in medias["lemondefr"]}
        def decouvrir(source, rapport, **options):
            return [p["url"] for p in medias[source["compte"]]]

        for operateur, comptes_attendus in (("OR", 3), ("AND", 1)):
            with self.subTest(operateur=operateur), tempfile.TemporaryDirectory() as dossier:
                options = web.StartRequest(
                    source_collecte="presse", medias=["lemonde"],
                    presse_moteur="api", limit=10,
                    croiser_hashtag_presse=True,
                    hashtags_presse=["#manifestation", "#blocage"],
                    operator_presse=operateur, variables_txt=["profil", "id"])
                travail = web.Job("essai-multiple", options, Path(dossier))
                travail.base = None
                with patch("connect_presse.ConnexionPresse.decouvrir",
                           side_effect=decouvrir), patch.object(
                           web.scraper, "read_post",
                           side_effect=lambda driver, url, *args, **kwargs:
                           dict(videos[url])), patch.object(travail, "pause"):
                    web.execute_job(travail, driver_factory=lambda args: Mock())
                self.assertEqual(len(travail.records), comptes_attendus)
                self.assertEqual(travail.bilan_hashtags,
                                 {"manifestation": 2, "blocage": 2})
                self.assertEqual(travail.correspondances_hashtags, comptes_attendus)
                self.assertEqual(travail.filtered, 4 - comptes_attendus)
                for record in travail.records:
                    self.assertEqual(record["hashtags_recherches"],
                                     ["manifestation", "blocage"])
                    self.assertEqual(record["operateur_hashtags"], operateur)
                    csv_publication = ligne_publication_csv(record)
                    csv_engagement = lignes_engagement([record])[0]
                    self.assertEqual(csv_publication["hashtags_correspondants"],
                                     record["hashtags_correspondants"])
                    self.assertEqual(csv_publication["htag_collecte"],
                                     "manifestation, blocage")
                    self.assertEqual(csv_engagement["htag_collecte"],
                                     "manifestation, blocage")
                    self.assertNotIn("hashtags_recherches", csv_publication)
                    self.assertNotIn("hashtags_recherches", csv_engagement)
                    self.assertEqual(csv_engagement["operateur_hashtags"], operateur)
                self.assertIn(
                    "Des jeunes #manifestation" if operateur == "OR"
                    else "#manifestation et #blocage",
                    travail.texte_a_exporter())
                self.assertEqual(travail.snapshot()["hashtags_presse"],
                                 ["manifestation", "blocage"])
                self.assertEqual(travail.snapshot()["operator_presse"], operateur)

    def test_croisement_et_export_double_source_ia(self):
        with tempfile.TemporaryDirectory() as dossier:
            params = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                                      croiser_hashtag_presse=True,
                                      hashtag_presse="#manifestation",
                                      inclure_texte_genere_ia=True,
                                      variables_txt=["profil"])
            job = web.Job("test-double-source", params, Path(dossier))
            fiche = publication("lemondefr", "7701005447410552097",
                                "Violence lors de la #manifestation.", True)
            job.records.append(fiche)
            contenu = job.texte_a_exporter()
            self.assertEqual(contenu.count("****"), 2)
            self.assertIn("*source_original *theme_manifestation", contenu)
            self.assertIn("*source_ia *theme_manifestation", contenu)
            self.assertIn("Résumé élaboré par TikTok.", contenu)

    def test_emplacement_ui_sous_les_comptes_et_compatibilite_moteurs(self):
        interface = (Path(__file__).resolve().parents[1] /
                     "streamlit_app.py").read_text(encoding="utf-8")
        pos_comptes = interface.index('st.write("Choisir les médias à collecter")')
        pos_selection = interface.index('st.session_state["medias"] = selection', pos_comptes)
        pos_croisement = interface.index('st.checkbox("Croisement avec des hashtags"', pos_selection)
        pos_infos = interface.index('informations_presse = []', pos_croisement)
        self.assertLess(pos_selection, pos_croisement)
        self.assertIn('"Hashtags du croisement (1 à 10)"', interface)
        self.assertIn('"Combiner les hashtags de presse"', interface)
        self.assertLess(pos_croisement, pos_infos)
        for moteur in ("api", "navigateur", "gallerydl", "research", "tikhub"):
            if moteur == "research":
                continue  # Une clé Research est obligatoire et testée ailleurs.
            if moteur == "tikhub":
                params = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                                          presse_moteur=moteur,
                                          tikhub_api_key="SECRET_DE_TEST",
                                          croiser_hashtag_presse=True,
                                          hashtag_presse="#manifestation")
            else:
                params = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                                          presse_moteur=moteur,
                                          croiser_hashtag_presse=True,
                                          hashtag_presse="#manifestation")
            self.assertEqual(params.presse_moteur, moteur)


if __name__ == "__main__":
    unittest.main()
