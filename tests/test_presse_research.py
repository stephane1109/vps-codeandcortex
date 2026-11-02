"""Tests sans accès réseau de la Research API officielle et du moteur secUid."""
import json
import os
import unittest
from datetime import date
from unittest.mock import patch, Mock
from urllib.parse import parse_qs
from collecte.presse_research import (
    _dates, _fiche, _jeton, _cache_token, collecter_videos_presse_research,
    ResearchErreur, ResearchAccesRefuse, URL_TOKEN, URL_VIDEOS,
)


def v(numero, compte="lemondefr"):
    return {"id": str(7000000000000000000 + numero), "username": compte,
            "video_description": "Manifestation #France",
            "create_time": 1760000000, "view_count": 0, "like_count": 12,
            "share_count": 3, "comment_count": 2, "hashtag_names": ["France"]}


class TestsResearch(unittest.TestCase):
    def test_fenetres_trente_jours_incluses(self):
        fenetres = list(_dates("2026-07-01", "2026-09-01",
                              aujourd_hui=date(2026, 10, 25)))
        self.assertEqual(fenetres, [
            ("20260803", "20260901"),
            ("20260704", "20260802"),
            ("20260701", "20260703"),
        ])
        self.assertEqual(list(_dates(None, None, aujourd_hui=date(2026, 10, 25))),
                         [("20260926", "20261025")])

    def test_manque_cle_ne_contacte_pas_le_serveur(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ResearchAccesRefuse):
                collecter_videos_presse_research(
                    "lemondefr", 10, {}, requete=Mock(),
                    aujourd_hui=date(2026, 10, 25))

    def test_authentification_secrete_et_token_reutilisable(self):
        _cache_token.update(valeur=None, expire=0.0, identite=None)
        appels = []
        def serveur(url, *, data, headers):
            appels.append((url, parse_qs(data.decode()), headers))
            return {"access_token": "jeton_test", "expires_in": 7200}
        with patch.dict(os.environ, {"TIKTOK_RESEARCH_CLIENT_KEY": "test_cle",
                                     "TIKTOK_RESEARCH_CLIENT_SECRET": "test_secret"}):
            self.assertEqual(_jeton(requete=serveur, maintenant=lambda:100.), "jeton_test")
            self.assertEqual(_jeton(requete=serveur, maintenant=lambda:110.), "jeton_test")
        self.assertEqual(len(appels), 1)
        self.assertEqual(appels[0][0], URL_TOKEN)
        self.assertEqual(appels[0][1]["grant_type"], ["client_credentials"])
        self.assertEqual(appels[0][1]["client_secret"], ["test_secret"])

    def test_pagination_authenticite_et_metadonnees(self):
        appels = []
        def api(url, *, data, headers):
            requete = json.loads(data)
            appels.append((url, requete, headers))
            if len(appels) == 1:
                return {"data":{"videos":[v(1),v(9,"unautreauteur")],
                                "cursor":2,"search_id":"recherche1","has_more":True},
                        "error":{"code":"ok"}}
            return {"data":{"videos":[v(2)], "cursor":3,
                            "search_id":"recherche1","has_more":False},
                    "error":{"code":"ok"}}
        rapport = {}
        urls = collecter_videos_presse_research(
            "lemondefr", 2, rapport, requete=api, jeton="test_token",
            debut="2026-10-01", fin="2026-10-25",
            aujourd_hui=date(2026, 10, 25), pause=lambda _:None)
        self.assertEqual(len(urls), 2)
        self.assertEqual(len(appels), 2)
        self.assertTrue(all(u.startswith(URL_VIDEOS) for u,_,_ in appels))
        self.assertEqual(appels[0][1]["query"]["and"][0]["field_values"], ["lemondefr"])
        self.assertEqual(appels[1][1]["cursor"], 2)
        self.assertEqual(appels[1][1]["search_id"], "recherche1")
        self.assertEqual(rapport["auteurs_ecartes"], 1)
        self.assertEqual(rapport["pages_research"], 2)
        self.assertEqual(rapport["metadonnees_api"][str(7000000000000000001)]
                         ["engagement"]["vues"]["valeur"], 0)
        self.assertEqual(rapport["discovery_stop"], "limit")

    def test_research_requete_compte_et_hashtag_combines_et_verifies(self):
        """La sélection du croisement filtre les vidéos dès la requête API."""
        demandes = []

        def serveur(url, *, data, headers):
            corps = json.loads(data)
            demandes.append(corps)
            return {"data": {"videos": [
                {**v(1, "parismatch"), "hashtag_names": ["24octobre"],
                 "video_description": "Manifestation #24octobre"},
                {**v(2, "parismatch"), "hashtag_names": ["autre"],
                 "video_description": "Actualité sans rapport"},
                {**v(3, "brutofficiel"), "hashtag_names": ["24octobre"],
                 "video_description": "Autre auteur #24octobre"},
            ], "has_more": False}}

        etat = {}
        urls = collecter_videos_presse_research(
            "parismatch", 10, etat, requete=serveur, jeton="test",
            hashtag="24octobre", debut="2026-10-01", fin="2026-10-25",
            aujourd_hui=date(2026, 10, 25), pause=lambda _: None)
        self.assertEqual(demandes[0]["query"]["and"], [
            {"field_name": "username", "operation": "EQ",
             "field_values": ["parismatch"]},
            {"field_name": "hashtag_name", "operation": "EQ",
             "field_values": ["24octobre"]}
        ])
        self.assertEqual(len(urls), 1)
        self.assertIn("@parismatch ET #24octobre", etat["requete_recherche"])
        self.assertEqual(etat["auteurs_ecartes"], 2)

    def test_multi_hashtags_query_research_et_ou_et_dedoublonnage(self):
        """IN et AND conservent username et excluent les vidéos non conformes."""
        videos = [
            {**v(1), "hashtag_names": ["manifestation"]},
            {**v(2), "hashtag_names": ["blocage"]},
            {**v(3), "hashtag_names": ["blocage", "manifestation"]},
            {**v(4), "hashtag_names": ["autre"]},
            {**v(5, "franceinfo"), "hashtag_names": ["blocage", "manifestation"]},
        ]
        for operateur, nombre in (("OR", 3), ("AND", 1)):
            with self.subTest(operateur=operateur):
                demandes = []
                def serveur(url, *, data, headers):
                    demandes.append(json.loads(data))
                    return {"data": {"videos": videos + [videos[0]],
                                     "has_more": False}}
                resultat = {}
                urls = collecter_videos_presse_research(
                    "lemondefr", 10, resultat, jeton="jeton_de_test",
                    requete=serveur, hashtags=["#manifestation", "#blocage"],
                    operateur=operateur,
                    debut="2026-10-01", fin="2026-10-25",
                    aujourd_hui=date(2026, 10, 25), pause=lambda _: None)
                self.assertEqual(len(urls), nombre)
                conditions = demandes[0]["query"]["and"]
                self.assertEqual(conditions[0], {
                    "field_name": "username", "operation": "EQ",
                    "field_values": ["lemondefr"]})
                if operateur == "OR":
                    self.assertEqual(conditions[1], {
                        "field_name": "hashtag_name", "operation": "IN",
                        "field_values": ["manifestation", "blocage"]})
                else:
                    self.assertEqual([c["field_values"] for c in conditions[1:]],
                                     [["manifestation"], ["blocage"]])
                self.assertEqual(resultat["hashtags_recherches"],
                                 ["manifestation", "blocage"])
                self.assertEqual(resultat["operateur_hashtags"], operateur)

    def test_mode_automatique_depasse_ancien_plafond_pages(self):
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            numero = len(appels)
            return {"data": {"videos": [v(numero)], "cursor": numero,
                             "search_id": "recherche_auto", "has_more": numero < 4}}

        rapport = {}
        with patch("collecte.researchapi.MAX_PAGES", 2):
            urls = collecter_videos_presse_research(
                "lemondefr", None, rapport, requete=api, jeton="test_token",
                debut="2026-10-01", fin="2026-10-25",
                aujourd_hui=date(2026, 10, 25), pause=lambda _: None)
        self.assertEqual(len(appels), 4)
        self.assertEqual(len(urls), 4)
        self.assertTrue(all(a["max_count"] == 100 for a in appels))
        self.assertEqual(rapport["discovery_stop"], "fin_des_periodes")
        self.assertFalse(rapport["collecte_partielle"])

    def test_erreur_quota_conserve_pages_precedentes(self):
        numero = 0
        def api(url, *, data, headers):
            nonlocal numero
            numero += 1
            if numero == 1:
                return {"data":{"videos":[v(1)],"has_more":True,
                                "cursor":1,"search_id":"test"}}
            raise ResearchAccesRefuse("Research API HTTP 429")
        rapport = {}
        with self.assertRaises(ResearchAccesRefuse):
            collecter_videos_presse_research(
                "lemondefr", 20, rapport, requete=api, jeton="test",
                aujourd_hui=date(2026,10,25), pause=lambda _:None)
        self.assertEqual(rapport["pages_research"], 1)
        self.assertEqual(len(rapport["discovered_urls"]), 1)
        self.assertEqual(rapport["discovery_stop"], "research_refus_ou_erreur")

    def test_absence_description_ne_necessite_pas_chrome(self):
        fiche = _fiche({**v(1), "video_description":None}, "lemondefr")
        self.assertEqual(fiche["description"], "")
        self.assertEqual(fiche["source"], "research_api_officielle")
        self.assertEqual(fiche["status"], "empty_caption")

    def test_identifiant_video_id_officiel_est_accepte(self):
        objet = v(4)
        objet["video_id"] = objet.pop("id")
        fiche = _fiche(objet, "lemondefr")
        self.assertIsNotNone(fiche)
        self.assertEqual(fiche["id"], str(7000000000000000004))

    def test_rejet_autres_auteurs(self):
        self.assertIsNone(_fiche(v(1, "autre"), "lemondefr"))


    def test_worker_presse_research_sans_chrome_et_export_txt(self):
        """Les résultats Research utilisent le même pipeline et ne lancent pas Chrome."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job
        from connect_presse import ConnexionPresse
        publication = v(1)
        fiche = _fiche(publication, "lemondefr")
        def collecte(compte, limite, rapport, **kwargs):
            self.assertIsNone(limite)
            self.assertEqual(compte, "lemondefr")
            self.assertEqual(kwargs.get("credentiels"),
                             ("client_test_secret", "secret_test_secret"))
            rapport.update(discovered_urls=[fiche["url"]],
                           metadonnees_api={fiche["id"]:fiche},
                           candidats_examines=1, pages_research=1,
                           navigation_publications="research_officielle",
                           discovery_stop="fin_des_periodes")
            if kwargs.get("progress"):
                kwargs["progress"](1)
            return [fiche["url"]]
        navigateur = Mock(side_effect=AssertionError("Chrome ne doit pas démarrer"))
        with TemporaryDirectory() as dossier:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", limit=5,
                collecte_research_complete=True,
                research_client_key="client_test_secret",
                research_client_secret="secret_test_secret",
            ), Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecte):
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(job.processed, 1)
            self.assertEqual(len(job.records), 1)
            self.assertEqual(job.records[0]["source"], "research_api_officielle")
            self.assertIn("Manifestation", job.path.read_text(encoding="utf-8"))
            self.assertIsNone(job.settings.research_client_key)
            self.assertIsNone(job.settings.research_client_secret)
            import json
            for fichier in Path(dossier).rglob("*"):
                if fichier.is_file() and fichier.suffix in {".txt", ".json", ".csv", ".sqlite"}:
                    # Contrôler exports et SQLite (octets inclus).
                    self.assertNotIn(b"secret_test_secret", fichier.read_bytes())
                    self.assertNotIn(b"client_test_secret", fichier.read_bytes())



    def test_test_research_dix_publications_partagees_entre_medias(self):
        """Le mode test arrête la découverte et la lecture après dix vidéos."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job

        demandes = []
        def collecter(compte, limite, rapport, **options):
            demandes.append((compte, limite))
            base = {"lemondefr": 0, "franceinfo": 100,
                    "leparisien": 200}.get(compte, 300)
            maximum = 6 if compte == "lemondefr" else 20
            candidats = [
                _fiche({**v(base + numero, compte),
                        "video_description": "Manifestation #manifestation",
                        "hashtag_names": ["manifestation"]}, compte)
                for numero in range(1, maximum + 1)
            ]
            retenus = candidats[:limite]
            rapport.update(
                discovered_urls=[item["url"] for item in retenus],
                metadonnees_api={item["id"]: item for item in retenus},
                candidats_examines=len(retenus), pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes", collecte_partielle=False)
            return [item["url"] for item in retenus]

        navigateur = Mock(side_effect=AssertionError("Pas de navigateur avec Research"))
        with TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse",
                medias=["lemonde", "franceinfo", "leparisien"],
                presse_moteur="research",
                test_research_10_publications=True,
                research_client_key="test_key",
                research_client_secret="test_secret")
            self.assertEqual(options.limit, 10)
            self.assertTrue(options.collecte_research_complete)
            job = Job("f"*64, options, Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecter):
                execute_job(job, driver_factory=navigateur)
            navigateur.assert_not_called()
            self.assertEqual(demandes, [("lemondefr", 4),
                                        ("franceinfo", 3),
                                        ("leparisien", 3)])
            self.assertEqual(job.processed, 10)
            self.assertEqual(len(job.records), 10)
            self.assertEqual(len(job.publications), 10)
            self.assertIn("Mode test Research", job.message)
            self.assertEqual(job.snapshot()["test_research_10_publications"], True)

    def test_test_research_repartit_parismatch_et_brut_et_explique_les_exclusions(self):
        """Deux médias contribuent au budget, malgré des légendes indéterminées."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job

        demandes = []

        def collecter(compte, limite, rapport, **options):
            demandes.append((compte, limite))
            depart = 0 if compte == "parismatch" else 100
            legende = ("#actu" if compte == "parismatch" else
                       "Les élèves manifestent dans les rues de Paris aujourd'hui.")
            fiches = [
                _fiche({**v(depart + i, compte),
                        "video_description": legende}, compte)
                for i in range(1, limite + 1)
            ]
            rapport.update(
                discovered_urls=[fiche["url"] for fiche in fiches],
                metadonnees_api={fiche["id"]: fiche for fiche in fiches},
                candidats_examines=len(fiches), pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="limit")
            return [fiche["url"] for fiche in fiches]

        with TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse", medias=["parismatch", "brut"],
                presse_moteur="research", french_only=True,
                test_research_10_publications=True,
                research_client_key="cle_test", research_client_secret="secret_test")
            job = Job("f" * 64, options, Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecter), patch(
                           "webapp.classify_description",
                           side_effect=lambda texte: "unknown" if texte == "#actu" else "fr"):
                execute_job(job, driver_factory=Mock(
                    side_effect=AssertionError("Chrome interdit avec Research")))
            self.assertEqual(demandes, [("parismatch", 5), ("brutofficiel", 5)])
            self.assertEqual(job.processed, 10)
            self.assertEqual(job.language_unknown, 5)
            self.assertEqual(len(job.records), 10)
            self.assertEqual(job.exportees, 10)
            self.assertIn("#actu", job.path.read_text(encoding="utf-8"))
            resultat = job.snapshot()
            self.assertEqual(len(resultat["apercu_filtrage"]), 10)
            self.assertEqual(
                {element["motif"] for element in resultat["apercu_filtrage"]},
                {"retenue_langue_indeterminee", "retenue"})
            self.assertTrue(all(element["retenue"] for element in job.records))

    def test_research_filtre_langue_inconnue_et_absence_de_legende(self):
        """Préserver les légendes incertaines, rejeter l'anglais, signaler le vide."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job

        textes = ["#24octobre", "Today we are discussing international news.",
                  "Manifestation de lycéens ce matin à Paris.", ""]
        def collecter(compte, limite, rapport, **options):
            donnees = [
                _fiche({**v(numero + 300, compte),
                        "video_description": texte,
                        "hashtag_names": ["24octobre"]}, compte)
                for numero, texte in enumerate(textes, 1)
            ]
            rapport.update(
                discovered_urls=[item["url"] for item in donnees],
                metadonnees_api={item["id"]: item for item in donnees},
                candidats_examines=len(donnees), pages_research=1,
                discovery_stop="fin_des_periodes")
            return [item["url"] for item in donnees]

        with TemporaryDirectory() as dossier:
            parametres = StartRequest(
                source_collecte="presse", medias=["brut"],
                presse_moteur="research", french_only=True,
                test_research_10_publications=True,
                research_client_key="cle_test", research_client_secret="secret_test")
            travail = Job("d" * 64, parametres, Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecter), patch(
                           "webapp.classify_description",
                           side_effect=lambda texte: (
                               "unknown" if texte.startswith("#") else
                               "other" if texte.startswith("Today") else "fr")):
                execute_job(travail, driver_factory=Mock(
                    side_effect=AssertionError("Pas de navigateur en Research")))
            self.assertEqual(travail.processed, 4)
            self.assertEqual(travail.language_unknown, 1)
            self.assertEqual(travail.non_french, 1)
            self.assertEqual(travail.legendes_vides, 1)
            self.assertEqual(len(travail.records), 2)
            self.assertEqual(len(travail.publications), 4)
            contenu = travail.path.read_text(encoding="utf-8")
            self.assertIn("#24octobre", contenu)
            self.assertIn("Manifestation de lycéens", contenu)
            self.assertNotIn("Today we are discussing", contenu)
            motifs = [v["motif_non_retenue"] for v in travail.publications]
            self.assertEqual(motifs, [
                "retenue_langue_indeterminee", "autre_langue",
                "retenue", "legende_vide"
            ])

    def test_research_achemine_croisement_presse_vers_les_deux_medias(self):
        """Le hashtag explicite est transmis pour chaque auteur interrogé."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from webapp import Job, StartRequest, execute_job

        observations = []

        def collecter(compte, limite, rapport, **options):
            observations.append((compte, limite, options.get("hashtag")))
            fiche = _fiche({**v(len(observations), compte),
                           "video_description": "Manifestation #24octobre",
                           "hashtag_names": ["24octobre"]}, compte)
            rapport.update(
                discovered_urls=[fiche["url"]],
                metadonnees_api={fiche["id"]: fiche},
                candidats_examines=1, pages_research=1,
                navigation_publications="research_officielle",
                discovery_stop="fin_des_periodes")
            return [fiche["url"]]

        with TemporaryDirectory() as dossier:
            options = StartRequest(
                source_collecte="presse", medias=["parismatch", "brut"],
                presse_moteur="research", test_research_10_publications=True,
                croiser_hashtag_presse=True, hashtag_presse="24octobre",
                research_client_key="test_key", research_client_secret="test_secret")
            job = Job("c" * 64, options, Path(dossier))
            with patch("collecte.presse_research.collecter_videos_presse_research",
                       side_effect=collecter):
                execute_job(job, driver_factory=Mock(
                    side_effect=AssertionError("Chrome interdit avec Research")))
            # Le budget de quatre résultats non obtenus sur Paris Match
            # est réaffecté à Brut pour atteindre dix publications au total.
            self.assertEqual(observations, [
                ("parismatch", 5, "24octobre"),
                ("brutofficiel", 9, "24octobre")])
            self.assertEqual(job.processed, 2)
            self.assertEqual(len(job.records), 2)

    def test_test_research_est_ignore_pour_un_autre_moteur(self):
        """Le mode test ne change pas le fonctionnement des moteurs non Research."""
        from webapp import StartRequest
        options = StartRequest(
            source_collecte="presse", medias=["lemonde"],
            presse_moteur="navigateur", limit=75,
            test_research_10_publications=True)
        self.assertFalse(options.test_research_10_publications)
        self.assertEqual(options.limit, 75)

    def test_identifiants_du_formulaire_sont_exclus_des_serialisations(self):
        from webapp import StartRequest
        with patch.dict(os.environ, {}, clear=True):
            requete = StartRequest(source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", research_client_key="cle_privee_123",
                research_client_secret="secret_prive_456")
            self.assertEqual(requete.research_client_key.get_secret_value(),
                             "cle_privee_123")
            contenu = json.dumps(requete.model_dump())
            self.assertNotIn("cle_privee_123", contenu)
            self.assertNotIn("secret_prive_456", contenu)
            self.assertNotIn("research_client_secret", contenu)
            self.assertNotIn("research_client_key", contenu)
            self.assertNotIn("secret_prive_456", repr(requete))
            with self.assertRaisesRegex(ValueError, "les deux identifiants"):
                StartRequest(source_collecte="presse", medias=["lemonde"],
                    presse_moteur="research", research_client_key="une_cle")

    def test_identifiants_saisis_sont_utilises_au_lieu_des_variables_serveur(self):
        appels = []
        def serveur(url, *, data, headers):
            appels.append(parse_qs(data.decode()))
            return {"access_token":"test_par_formulaire","expires_in":60}
        _cache_token.update(valeur=None, expire=0.0, identite=None)
        with patch.dict(os.environ, {
            "TIKTOK_RESEARCH_CLIENT_KEY":"autre_cle",
            "TIKTOK_RESEARCH_CLIENT_SECRET":"autre_secret",
        }):
            token = _jeton(requete=serveur, maintenant=lambda:200.,
                           credentiels=("cle_formulaire", "secret_formulaire"))
        self.assertEqual(token,"test_par_formulaire")
        self.assertEqual(appels[0]["client_key"],["cle_formulaire"])
        self.assertEqual(appels[0]["client_secret"],["secret_formulaire"])
        self.assertNotIn("secret_formulaire", str(_cache_token))

    def test_research_cle_secrete_non_presente_en_sortie_health(self):
        from tempfile import TemporaryDirectory
        from fastapi.testclient import TestClient
        from webapp import create_app, Manager
        with TemporaryDirectory() as dossier, \
             patch.dict(os.environ, {"TIKTOK_RESEARCH_CLIENT_KEY": "cle_test",
                                     "TIKTOK_RESEARCH_CLIENT_SECRET": "secret_test"}), \
             patch("urllib.request.urlopen") as controle:
            controle.return_value.__enter__.return_value = Mock()
            with TestClient(create_app(Manager(data_dir=dossier))) as client:
                rep = client.get("/healthz")
        self.assertEqual(rep.status_code, 200)
        self.assertTrue(rep.json()["research_configuree"])
        self.assertNotIn("secret_test", rep.text)
        self.assertNotIn("cle_test", rep.text)


if __name__ == "__main__":
    unittest.main()
