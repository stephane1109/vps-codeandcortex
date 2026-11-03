"""Vérifier les bilans, les variables et les reprises de hashtags Research."""
import unittest
from pathlib import Path

from collecte.suivi_hashtags import (
    etablir_bilan_hashtags, exporter_bilan_hashtags_csv,
    hashtags_a_reprendre, identifier_collecte_bilan_hashtags_csv,
    importer_bilan_hashtags_csv, preparer_reprise_hashtags,
)
from collecte.presse import charger_inventaire
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
            ancien, context={"reprise_historique": True})
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

    def test_moteur_et_interface_disposent_du_meme_export(self):
        racine = Path(__file__).resolve().parents[1]
        interface = (racine / "streamlit_app.py").read_text("utf-8")
        moteur = (racine / "webapp.py").read_text("utf-8")
        self.assertIn('source in {"presse", "hashtags"}', interface)
        self.assertIn(
            "Reprendre les hashtags (même corpus PostgreSQL)",
            (racine / "interface" / "reprise_hashtags_ui.py").read_text("utf-8"))
        self.assertIn("bilan_hashtags.csv", moteur)
        self.assertIn("def reprendre_hashtags_existants(", moteur)
        self.assertIn("initialiser_donnees_reprise(job, dossier, manifeste, [])",
                      moteur)


if __name__ == "__main__":
    unittest.main()
