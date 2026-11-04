"""Vérifier les bilans, les variables et les reprises de hashtags Research."""
import csv
import io
import unittest
from pathlib import Path

from collecte.suivi_hashtags import (
    etablir_bilan_hashtags, exporter_bilan_hashtags_csv,
    hashtags_a_reprendre, identifier_collecte_bilan_hashtags_csv,
    identifier_collecte_bilans_hashtags_csv, importer_bilan_hashtags_csv,
    importer_bilans_hashtags_csv, preparer_reprise_hashtags,
    positions_pagination_bilans_csv, variantes_par_hashtag,
    regrouper_bilans_hashtags_csv,
)
from collecte.presse import charger_inventaire
from interface.reprise_hashtags_ui import reprendre_depuis_bilans_csv
from webapp import StartRequest


class TestsRepriseHashtags(unittest.TestCase):
    def setUp(self):
        self.identifiant = "a" * 32
        self.hashtags = ["17octobre", "24octobre", "31octobre"]
        self.journal = [
            {"source": "#17octobre", "statut_source": "traitee",
             "rapport": {"discovered_urls": ["url1"], "collecte_partielle": False}},
            {"source": "#24octobre", "statut": "inaccessible",
             "statut_source": "interrompue",
             "rapport": {"discovered_urls": ["url2"], "collecte_partielle": True},
             "message": "Quota Research API atteint."},
        ]

    def test_bilan_source_apres_quota(self):
        bilan = etablir_bilan_hashtags(
            self.hashtags, False, self.journal,
            collecte_id=self.identifiant, termine=True)
        self.assertEqual(
            [ligne["etat"] for ligne in bilan],
            ["traitee", "interrompue", "non_commencee"])
        self.assertEqual(
            hashtags_a_reprendre(bilan), ["24octobre", "31octobre"])
        self.assertEqual([ligne["liens"] for ligne in bilan], [1, 1, 0])
        self.assertTrue(all(ligne["collecte_id"] == self.identifiant
                            for ligne in bilan))

    def test_export_csv_enregistre_cursor_search_id_et_dates(self):
        """Le bilan téléchargeable restaure exactement la page suivante."""
        journal = [{
            "source": "#manifestation",
            "statut_source": "partielle",
            "rapport": {
                "collecte_partielle": True,
                "discovered_urls": ["https://www.tiktok.com/@x/video/123"],
                "reprise_pagination_research": {
                    "indice_periode": 0,
                    "debut_periode": "20261001",
                    "fin_periode": "20261025",
                    "cursor": 521,
                    "search_id": "recherche_tiktok_521",
                    "pagination_invalide": False,
                },
            },
        }]
        bilan = etablir_bilan_hashtags(
            ["manifestation", "lyceen"], False, journal,
            termine=True, collecte_id=self.identifiant,
            date_debut="2026-10-01", date_fin="2026-10-25")
        contenu = exporter_bilan_hashtags_csv(bilan)
        lignes = list(csv.DictReader(
            io.StringIO(contenu.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(lignes[0]["cursor"], "521")
        self.assertEqual(lignes[0]["search_id"], "recherche_tiktok_521")
        self.assertEqual(lignes[0]["debut_periode"], "20261001")
        self.assertEqual(lignes[0]["fin_periode"], "20261025")
        self.assertEqual(lignes[0]["indice_periode"], "0")
        self.assertEqual(lignes[0]["source_pagination"], "#manifestation")
        self.assertTrue(lignes[0]["positions_research_json"])
        self.assertTrue(lignes[0]["exporte_le"])
        self.assertEqual(lignes[1]["etat"], "non_commencee")
        self.assertEqual(lignes[1]["cursor"], "")
        positions = positions_pagination_bilans_csv(
            [contenu], collecte_id=self.identifiant,
            hashtags_autorises=["manifestation", "lyceen"],
            date_debut="2026-10-01", date_fin="2026-10-25")
        self.assertEqual(positions["#manifestation"]["cursor"], 521)
        self.assertEqual(
            positions["#manifestation"]["search_id"], "recherche_tiktok_521")
        self.assertNotIn("#lyceen", positions)

    def test_anciens_csv_cinq_colonnes_restent_importables_sans_curseur(self):
        """Les bilans téléchargés avant la correction restent utilisables."""
        contenu = (
            "collecte_id;hashtag;etat;liens;motif\n"
            f"{self.identifiant};manifestation;partielle;521;HTTP 401\n"
            f"{self.identifiant};lyceen;non_commencee;0;\n"
        ).encode("utf-8")
        self.assertEqual(
            importer_bilans_hashtags_csv(
                [contenu], collecte_id=self.identifiant,
                hashtags_autorises=["manifestation", "lyceen"]),
            ["manifestation", "lyceen"])
        self.assertEqual(
            positions_pagination_bilans_csv(
                [contenu], collecte_id=self.identifiant,
                hashtags_autorises=["manifestation", "lyceen"],
                date_debut="2026-10-01", date_fin="2026-10-25"),
            {})

    def test_positions_par_variante_et_refus_des_periodes_modifiees(self):
        """Chaque variante garde son curseur propre et les dates sont contrôlées."""
        variantes = variantes_par_hashtag(["lyceen"], True)["lyceen"]
        autre = next(v for v in variantes if v != "lyceen")
        journal = [
            {"source": "#lyceen", "statut_source": "traitee",
             "rapport": {"collecte_partielle": False}},
            {"source": "#" + autre, "statut_source": "partielle",
             "rapport": {
                 "collecte_partielle": True,
                 "reprise_pagination_research": {
                     "indice_periode": 0, "debut_periode": "20261001",
                     "fin_periode": "20261025",
                     "cursor": 75, "search_id": "variante_research",
                 },
             }},
        ]
        bilan = etablir_bilan_hashtags(
            ["lyceen"], True, journal, collecte_id=self.identifiant,
            termine=True, date_debut="2026-10-01", date_fin="2026-10-25")
        fichier = exporter_bilan_hashtags_csv(bilan)
        positions = positions_pagination_bilans_csv(
            [fichier], collecte_id=self.identifiant,
            hashtags_autorises=["lyceen"], avec_accents=True,
            date_debut="2026-10-01", date_fin="2026-10-25")
        self.assertEqual(positions["#" + autre]["cursor"], 75)
        self.assertNotIn("#lyceen", positions)
        with self.assertRaisesRegex(ValueError, "période"):
            positions_pagination_bilans_csv(
                [fichier], collecte_id=self.identifiant,
                hashtags_autorises=["lyceen"], avec_accents=True,
                date_debut="2026-09-01", date_fin="2026-10-25")

    def test_reprendre_uniquement_les_hashtags_inacheves(self):
        selection, graphies, _ = preparer_reprise_hashtags(
            self.hashtags, False, self.journal,
            ["24octobre", "31octobre"])
        self.assertEqual(selection, ["24octobre", "31octobre"])
        self.assertEqual(graphies, ["24octobre", "31octobre"])
        with self.assertRaisesRegex(ValueError, "inachevés"):
            preparer_reprise_hashtags(
                self.hashtags, False, self.journal, ["17octobre"])
        with self.assertRaises(ValueError):
            preparer_reprise_hashtags(
                self.hashtags, False, self.journal, ["31octobre", "31octobre"])

    def test_une_variante_achevee_n_est_pas_relancee(self):
        journal = [
            {"source": "#lyceen", "statut_source": "traitee",
             "rapport": {"collecte_partielle": False}},
        ]
        _, variantes, bilan = preparer_reprise_hashtags(
            ["lyceen"], True, journal, ["lyceen"])
        self.assertNotIn("lyceen", variantes)
        self.assertTrue(len(variantes) > 0)
        self.assertEqual(bilan[0]["etat"], "partielle")

    def test_export_import_csv_protege_l_identifiant_du_corpus(self):
        bilan = etablir_bilan_hashtags(
            self.hashtags, False, self.journal,
            collecte_id=self.identifiant, termine=True)
        contenu = exporter_bilan_hashtags_csv(bilan)
        self.assertEqual(
            identifier_collecte_bilan_hashtags_csv(contenu),
            self.identifiant)
        self.assertEqual(
            importer_bilan_hashtags_csv(
                contenu, collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags),
            ["24octobre", "31octobre"])
        with self.assertRaisesRegex(ValueError, "autre collecte"):
            importer_bilan_hashtags_csv(
                contenu, collecte_id="b" * 32,
                hashtags_autorises=self.hashtags)
        with self.assertRaises(ValueError):
            importer_bilan_hashtags_csv(
                b"media_id;etat\nfrance_tv;interrompue\n",
                collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags)

    def test_importer_plusieurs_bilans_csv_du_meme_corpus(self):
        """Regrouper les hashtags incomplets de deux fichiers sans doublons."""
        premier = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "17octobre",
             "etat": "traitee", "liens": 12, "motif": ""},
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "partielle", "liens": 18, "motif": "Séquence interrompue"},
        ])
        second = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "interrompue", "liens": 18, "motif": "Quota atteint"},
            {"collecte_id": self.identifiant, "hashtag": "31octobre",
             "etat": "non_commencee", "liens": 0, "motif": ""},
        ])
        self.assertEqual(
            identifier_collecte_bilans_hashtags_csv([second, premier]),
            self.identifiant)
        attendu = ["24octobre", "31octobre"]
        self.assertEqual(importer_bilans_hashtags_csv(
            [premier, second], collecte_id=self.identifiant,
            hashtags_autorises=self.hashtags), attendu)
        self.assertEqual(importer_bilans_hashtags_csv(
            [second, premier], collecte_id=self.identifiant,
            hashtags_autorises=self.hashtags), attendu)
        # La situation actuelle du journal reste prioritaire sur le CSV.
        bilan_actuel = etablir_bilan_hashtags(
            self.hashtags, False, self.journal,
            collecte_id=self.identifiant, termine=True)
        disponibles = set(hashtags_a_reprendre(bilan_actuel))
        self.assertEqual([tag for tag in attendu if tag in disponibles],
                         ["24octobre", "31octobre"])

    def test_import_multiple_rejette_les_autres_corpus_et_fichiers_invalides(self):
        """Ne jamais fusionner les journaux de deux collectes PostgreSQL."""
        premier = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "partielle", "liens": 10, "motif": ""},
        ])
        autre = exporter_bilan_hashtags_csv([
            {"collecte_id": "b" * 32, "hashtag": "24octobre",
             "etat": "interrompue", "liens": 15, "motif": ""},
        ])
        with self.assertRaisesRegex(ValueError, "collectes différentes"):
            identifier_collecte_bilans_hashtags_csv([premier, autre])
        with self.assertRaisesRegex(ValueError, "collectes différentes"):
            importer_bilans_hashtags_csv(
                [premier, autre], collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags)
        with self.assertRaisesRegex(ValueError, "autre collecte"):
            importer_bilans_hashtags_csv(
                [autre], collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags)
        with self.assertRaisesRegex(ValueError, "maximum 20"):
            identifier_collecte_bilans_hashtags_csv([premier] * 21)
        with self.assertRaises(ValueError):
            identifier_collecte_bilans_hashtags_csv([])
        with self.assertRaises(ValueError):
            importer_bilans_hashtags_csv(
                [premier, b"fichier non valide"],
                collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags)

    def test_interface_charge_plusieurs_bilans_sans_remplacer_corpus(self):
        """Le contrôle Streamlit accepte le multi-upload et préserve le bouton."""
        interface = (
            Path(__file__).resolve().parents[1] /
            "interface" / "reprise_hashtags_ui.py").read_text("utf-8")
        self.assertIn("accept_multiple_files=True", interface)
        self.assertIn("identifier_collecte_bilans_hashtags_csv", interface)
        self.assertIn("importer_bilans_hashtags_csv", interface)
        self.assertIn("reprendre_hashtags_selection_", interface)
        self.assertIn("st.multiselect(", interface)
        self.assertNotIn('st.button("Poursuivre la collecte (séquence suivante)"',
                         interface)

    def test_bilans_de_collectes_distinctes_sont_selectionnables_separement(self):
        """Les deux identifiants demeurent disponibles sans mélange des curseurs."""
        bilan_origine = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "17octobre",
             "etat": "partielle", "liens": 521, "motif": ""},
        ])
        autre_id = "b" * 32
        bilan_nouvelle_collecte = exporter_bilan_hashtags_csv([
            {"collecte_id": autre_id, "hashtag": "17octobre",
             "etat": "partielle", "liens": 4, "motif": ""},
        ])
        groupes = regrouper_bilans_hashtags_csv(
            [bilan_origine, bilan_nouvelle_collecte])
        self.assertEqual(set(groupes), {self.identifiant, autre_id})
        self.assertEqual(groupes[self.identifiant], [bilan_origine])
        self.assertEqual(groupes[autre_id], [bilan_nouvelle_collecte])
        self.assertEqual(
            importer_bilans_hashtags_csv(
                groupes[self.identifiant],
                collecte_id=self.identifiant,
                hashtags_autorises=self.hashtags),
            ["17octobre"])
        interface = (
            Path(__file__).resolve().parents[1] /
            "interface" / "reprise_hashtags_ui.py").read_text("utf-8")
        self.assertIn("regrouper_bilans_hashtags_csv", interface)
        self.assertIn("Collecte d'origine à reprendre", interface)
        self.assertIn("contenus_corpus", interface)
        self.assertIn("reprendre_depuis_bilans_csv(", interface)

    def test_import_csv_declenche_reprise_originale_et_pas_un_nouveau_job(self):
        """Deux bilans relancent l'ancien corpus avec ses 521 publications."""
        premiere = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "17octobre",
             "etat": "traitee", "liens": 521, "motif": ""},
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "partielle", "liens": 0, "motif": ""},
        ])
        seconde = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "partielle", "liens": 0, "motif": ""},
            {"collecte_id": self.identifiant, "hashtag": "31octobre",
             "etat": "non_commencee", "liens": 0, "motif": ""},
        ])
        appels = []
        def api(chemin, donnees):
            appels.append((chemin, donnees))
            if chemin.endswith("/ouvrir"):
                return {
                    "id": self.identifiant, "source_collecte": "hashtags",
                    "hashtag_moteur": "research", "busy": False,
                    "hashtags_saisis": self.hashtags, "processed": 521,
                    "bilan_hashtags_sources": [
                        {"hashtag": "17octobre", "etat": "traitee"},
                        {"hashtag": "24octobre", "etat": "partielle"},
                        {"hashtag": "31octobre", "etat": "non_commencee"},
                    ],
                }
            self.assertEqual(
                chemin,
                f"/api/historique/{self.identifiant}/reprendre-hashtags")
            self.assertEqual(donnees, {
                "hashtags": ["24octobre", "31octobre"],
                "research_client_key": "cle", "research_client_secret": "secret",
            })
            return {"id": self.identifiant, "processed": 521, "busy": True}

        reprise, selection = reprendre_depuis_bilans_csv(
            api, [premiere, seconde], cle="cle", secret="secret")
        self.assertEqual(selection, ["24octobre", "31octobre"])
        self.assertEqual(reprise["id"], self.identifiant)
        self.assertEqual(reprise["processed"], 521)
        self.assertEqual(len(appels), 2)
        self.assertEqual(appels[0][0],
                         f"/api/historique/{self.identifiant}/ouvrir")
        self.assertTrue(all("/api/jobs" not in chemin for chemin, _ in appels))

    def test_import_csv_bloque_reprise_differents_corpus_ou_termines(self):
        """Un CSV ne peut pas déplacer ou réinitialiser les publications."""
        premiere = exporter_bilan_hashtags_csv([
            {"collecte_id": self.identifiant, "hashtag": "24octobre",
             "etat": "partielle", "liens": 521, "motif": ""},
        ])
        autre = exporter_bilan_hashtags_csv([
            {"collecte_id": "b" * 32, "hashtag": "24octobre",
             "etat": "partielle", "liens": 5, "motif": ""},
        ])
        appels = []
        def api(chemin, donnees):
            appels.append(chemin)
            return {
                "id": self.identifiant, "source_collecte": "hashtags",
                "hashtag_moteur": "research", "busy": False,
                "hashtags_saisis": self.hashtags,
                "bilan_hashtags_sources": [
                    {"hashtag": tag, "etat": "traitee"}
                    for tag in self.hashtags
                ],
            }

        with self.assertRaisesRegex(ValueError, "collectes différentes"):
            reprendre_depuis_bilans_csv(api, [premiere, autre])
        self.assertFalse(appels)
        with self.assertRaisesRegex(ValueError, "Aucun hashtag"):
            reprendre_depuis_bilans_csv(api, [premiere])
        self.assertEqual(appels, [
            f"/api/historique/{self.identifiant}/ouvrir"])
        interface = (Path(__file__).resolve().parents[1]
                     / "streamlit_app.py").read_text("utf-8")
        self.assertIn("bilans_importes_pour_reprise", interface)
        self.assertIn("or bilans_importes_pour_reprise", interface)

    def test_metriques_comptes_autorisees_pour_les_hashtags(self):
        variables = ["following_count", "follower_count",
                     "likes_count", "video_count"]
        options = StartRequest(
            source_collecte="hashtags", hashtag_moteur="research",
            hashtags_saisis=["17octobre"],
            nom_sauvegarde="Hashtags avec métriques auteurs",
            research_client_key="cle_test", research_client_secret="secret_test",
            profils_medias_variables=variables,
            profils_medias_classes=variables,
        )
        self.assertEqual(options.profils_medias_variables, variables)
        self.assertIsNone(options.limit)
        self.assertEqual(options.model_dump()["profils_medias_classes"], variables)
        self.assertTrue(len(charger_inventaire()) >= 1)

    def test_fenetre_utc_reste_identique_apres_reouverture(self):
        """Une reprise le lendemain doit conserver les bornes de la collecte."""
        options = StartRequest(
            source_collecte="hashtags", hashtag_moteur="research",
            hashtags_saisis=["17octobre"], nom_sauvegarde="Période stable",
            research_client_key="cle_test", research_client_secret="secret_test",
        )
        self.assertRegex(options.date_debut, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(options.date_fin, r"^\d{4}-\d{2}-\d{2}$")
        ancien = options.model_dump()
        reouvert = StartRequest.model_validate(
            {**ancien, "research_client_key": "cle_test",
             "research_client_secret": "secret_test"},
            context={"reprise_historique": True})
        self.assertEqual(
            (reouvert.date_debut, reouvert.date_fin),
            (options.date_debut, options.date_fin))

    def test_hashtags_avec_variantes_communes_ont_un_etat_reel(self):
        """Ne pas considérer automatiquement un alias accentué comme terminé."""
        bilan = etablir_bilan_hashtags(
            ["lyceen", "lycéen"], True, [],
            collecte_id=self.identifiant, termine=True)
        self.assertEqual(
            [ligne["etat"] for ligne in bilan],
            ["non_commencee", "non_commencee"])

    def test_interface_importe_fonctions_suivi_hashtags(self):
        """Les fonctions du bilan et de la reprise doivent être importées."""
        import ast
        racine = Path(__file__).resolve().parents[1]
        arbre = ast.parse((racine / "streamlit_app.py").read_text("utf-8"))
        noms_importes = {
            alias.name
            for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.ImportFrom)
            and noeud.module == "collecte.suivi_hashtags"
            for alias in noeud.names
        }
        self.assertTrue({
            "hashtags_a_reprendre", "exporter_bilan_hashtags_csv"
        }.issubset(noms_importes))

    def test_moteur_et_interface_disposent_du_meme_export(self):
        racine = Path(__file__).resolve().parents[1]
        interface = (racine / "streamlit_app.py").read_text("utf-8")
        moteur = (racine / "webapp.py").read_text("utf-8")
        self.assertIn('source in {"presse", "hashtags"}', interface)
        self.assertIn(
            "Poursuivre la collecte",
            interface)
        self.assertNotIn(
            '"Poursuivre la collecte (séquence suivante)"',
            (racine / "interface" / "reprise_hashtags_ui.py").read_text("utf-8"))
        self.assertIn("bilan_hashtags.csv", moteur)
        self.assertIn("def reprendre_hashtags_existants(", moteur)
        self.assertIn("initialiser_donnees_reprise(job, dossier, manifeste, [])",
                      moteur)


if __name__ == "__main__":
    unittest.main()
