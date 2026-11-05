"""Tests du réseau statistique d'engagement et des trois réseaux historiques."""

import ast
import unittest
from pathlib import Path

from analyse_sociometrique.similarite_engagement import (
    convertir_nombre, importer_engagement, construire_reseau_engagement,
)
from analyse_sociometrique.reseaux import exporter, NOMS


RACINE = Path(__file__).resolve().parents[1]


def creer_csv(lignes):
    """Construire un fichier de métriques dans le format ScrapTikTok."""
    entete = "publication_id;url;vues;likes;commentaires;partages\n"
    return (entete + "\n".join(lignes) + "\n").encode("utf-8")


class TestSimilariteEngagement(unittest.TestCase):
    def test_import_et_doublons(self):
        """L'import conserve les ID vidéo comme du texte et dédoublonne."""
        fichier = creer_csv([
            "01234;https://exemple.test/1;1000;100;20;10",
            "01234;https://exemple.test/1;999;999;999;999",
            "01235;https://exemple.test/2;1000;100;20;10",
        ])
        donnees = importer_engagement([("engagement.csv", fichier)])
        self.assertEqual(len(donnees["videos"]), 2)
        self.assertEqual(donnees["videos"][0]["id"], "01234")
        self.assertEqual(donnees["videos"][0]["vues"], 1000)
        self.assertEqual(donnees["doublons"], 1)

    def test_alias_api_et_valeurs_absentes(self):
        """Les noms officiels API et les vrais zéros sont préservés."""
        csv_api = (
            "id,view_count,like_count,comment_count,share_count\n"
            "8001,0,0,0,0\n"
            "8002,1000,,10,2\n"
        ).encode("utf-8")
        donnees = importer_engagement([("api.csv", csv_api)])
        self.assertEqual(donnees["videos"][0]["vues"], 0)
        self.assertEqual(donnees["videos"][0]["likes"], 0)
        self.assertIsNone(donnees["videos"][1]["likes"])

    def test_compteurs_manquants_ne_sont_pas_zero(self):
        """Une mesure absente retire la vidéo du calcul sélectionné."""
        donnees = importer_engagement([("engagement.csv", creer_csv([
            "1;;100;10;1;1",
            "2;;110;11;1;1",
            "3;;120;;1;1",
        ]))])
        reseau = construire_reseau_engagement(
            donnees, ["vues", "likes"], seuil=0.2, voisins=2)
        self.assertEqual(reseau["statistiques"]["videos_completes"], 2)
        self.assertEqual(reseau["statistiques"]["videos_analysees"], 2)

    def test_paires_sans_identite_d_utilisateur(self):
        """Les liens décrivent une similarité, jamais des auteurs communs."""
        donnees = importer_engagement([("engagement.csv", creer_csv([
            "100;;1000;100;20;10",
            "101;;1050;105;22;11",
            "102;;100000;9000;3000;2000",
        ]))])
        reseau = construire_reseau_engagement(
            donnees, ["vues", "likes", "commentaires", "partages"],
            seuil=0.6, voisins=2)
        self.assertTrue(reseau["liens"])
        self.assertEqual(reseau["mode"], "similarite_engagement")
        self.assertFalse(reseau["oriente"])
        self.assertEqual({noeud["type"] for noeud in reseau["noeuds"]},
                         {"video"})
        self.assertTrue(all(lien["relation"] == "similarite_engagement"
                            and 0 < lien["poids"] <= 1
                            for lien in reseau["liens"]))
        self.assertTrue(all("auteur" not in noeud
                            for noeud in reseau["noeuds"]))

    def test_export_graphml_gexf_et_liens(self):
        """Réutiliser les exports historiques sans perturber leur schéma."""
        donnees = importer_engagement([("engagement.csv", creer_csv([
            "1;;100;10;1;1",
            "2;;100;10;1;2",
            "3;;400;40;4;4",
        ]))])
        reseau = construire_reseau_engagement(
            donnees, ["vues", "partages"], seuil=0.25, voisins=2)
        self.assertIn(b"graphml", exporter(reseau, "graphml"))
        self.assertIn(b"gexf", exporter(reseau, "gexf"))
        self.assertIn(b"similarite_engagement", exporter(reseau, "liens.csv"))
        self.assertIn(b"vues", exporter(reseau, "noeuds.csv"))

    def test_echantillon_partiel_signale(self):
        """Une limite explicite est documentée et non présentée comme exhaustive."""
        donnees = {"videos": [
            {"id": str(n), "vues": n, "likes": n, "commentaires": n,
             "partages": n, "url": ""} for n in range(1200)
        ], "diagnostics": []}
        reseau = construire_reseau_engagement(
            donnees, ["vues"], seuil=0.9, limite=100, voisins=3)
        self.assertEqual(reseau["statistiques"]["videos_analysees"], 100)
        self.assertTrue(any("Corpus partiel" in texte
                            for texte in reseau["diagnostics"]))

    def test_valeur_absente_distincte_du_zero(self):
        """Rejeter les valeurs non numériques, négatives ou infinies."""
        self.assertEqual(convertir_nombre("0"), 0)
        self.assertEqual(convertir_nombre("1 000"), 1000)
        self.assertIsNone(convertir_nombre(""))
        self.assertIsNone(convertir_nombre("-1"))
        self.assertIsNone(convertir_nombre("inf"))
        self.assertIsNone(convertir_nombre("non disponible"))

    def test_nombre_de_comparaisons_et_memoire_bornee(self):
        """Un corpus dense conserve un nombre linéaire de liens, pas toutes les paires."""
        n = 180
        donnees = {"videos": [
            {"id": str(i), "url": "", "vues": 10 + i,
             "likes": 1 + i % 37, "commentaires": i % 17,
             "partages": i % 7}
            for i in range(n)
        ], "diagnostics": []}
        reseau = construire_reseau_engagement(
            donnees, ["vues", "likes", "commentaires", "partages"],
            seuil=0.01, voisins=3, limite=n)
        stats = reseau["statistiques"]
        self.assertEqual(stats["comparaisons"], n * (n - 1) // 2)
        self.assertEqual(stats["paires_au_seuil"], n * (n - 1) // 2)
        self.assertLessEqual(len(reseau["liens"]), 3 * n)
        self.assertEqual(len({(lien["source"], lien["cible"])
                              for lien in reseau["liens"]}),
                         len(reseau["liens"]))

    def test_interface_calcul_sur_action_et_exports_differes(self):
        """Les curseurs n'exécutent ni le calcul, ni la génération de gros fichiers."""
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(source)
        zone = source.split('elif mode_alimentation == "engagement":', 1)[1]
        zone = zone.split(
            'st.subheader("Analyse sociométrique des commentaires")', 1)[0]
        self.assertIn('"Calculer le réseau de similarité"', zone)
        self.assertIn('st.session_state["sociometrie_engagement_resultat"]', zone)
        self.assertIn('if st.button(', zone)
        self.assertIn('st.checkbox(', zone)
        self.assertIn('"Afficher l\'aperçu du réseau"', zone)
        self.assertIn('on_click="ignore"', zone)
        self.assertIn('data=lambda format_sortie=nom, reseau=reseau_mesures:', zone)
        self.assertIn('data=lambda reseau=reseau_mesures:', zone)
        self.assertIn('max_noeuds=taille_apercu_mesures', zone)
        self.assertIn('st.session_state.pop("sociometrie_engagement_resultat", None)', zone)

    def test_aucune_metrique_selectionnee_est_refusee(self):
        """Une sélection vide ne réactive pas les quatre métriques en secret."""
        donnees = importer_engagement([("engagement.csv", creer_csv([
            "1;;100;10;1;1",
            "2;;200;20;2;2",
        ]))])
        with self.assertRaisesRegex(ValueError, "au moins une métrique"):
            construire_reseau_engagement(donnees, [])

    def test_trois_modes_historiques_restent_visibles(self):
        """La nouvelle origine n'efface aucun des trois graphes précédents."""
        self.assertEqual(NOMS, ("auteurs_videos", "videos_communes", "reponses"))
        interface = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(interface)
        self.assertIn('["collecte", "csv", "engagement"]', interface)
        self.assertIn('mode_csv = st.selectbox(', interface)
        self.assertIn('mode_reseau = st.radio(', interface)
        self.assertNotIn(
            'st.session_state["sociometrie_csv_mode"] = "reponses"', interface)


if __name__ == "__main__":
    unittest.main()
