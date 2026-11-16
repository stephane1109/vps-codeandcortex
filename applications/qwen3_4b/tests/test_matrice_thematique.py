"""Tests de la matrice thématique générique et de sa validation humaine."""
from __future__ import annotations

import unittest
import pandas as pd

from matrice_thematique import (
    analyser_sources_csv, initialiser_annotations_matrice, construire_matrice,
    construire_bilan_sources, comparer_sources_par_video,
)


THEMES = [
    {"titre": "Condamnation", "definition": "Jugement négatif."},
    {"titre": "Affect", "definition": "Réaction émotionnelle."},
]


class TestMatriceThematique(unittest.TestCase):
    def test_csv_une_colonne_sans_etiquette(self):
        docs, infos = analyser_sources_csv(
            "texte\nMessage SMS\nTexte descriptif\n",
            {"texte_libre": "texte"},
        )
        self.assertEqual(len(docs), 2)
        self.assertEqual(infos[1]["source_texte"], "texte")
        self.assertEqual(infos[1]["type_source"], "texte_libre")
        self.assertEqual(infos[1]["colonne_texte_source"], "texte")

    def test_nom_csv_personnalise_et_type_de_source_distinct(self):
        documents, infos = analyser_sources_csv(
            "id_video;Texte narration IA;Publication\n"
            "700;Description neutre;Quel scandale\n",
            {
                "texte_ia": "Texte narration IA",
                "texte_auteur": "Publication",
            },
            colonne_id_video="id_video",
        )
        self.assertEqual(len(documents), 2)
        self.assertEqual(infos[1]["source_texte"], "Texte narration IA")
        self.assertEqual(infos[2]["source_texte"], "Publication")
        self.assertEqual(infos[1]["type_source"], "texte_ia")
        self.assertEqual(infos[2]["type_source"], "texte_auteur")

    def test_plusieurs_textes_associes_a_une_video(self):
        docs, infos = analyser_sources_csv(
            "id_video;texte_ia;texte_auteur;voice_to_text\n"
            "700;Texte neutre;Texte engagé;Transcription\n",
            {
                "texte_ia": "texte_ia",
                "texte_auteur": "texte_auteur",
                "voice_to_text": "voice_to_text",
            },
            colonne_id_video="id_video",
        )
        self.assertEqual(len(docs), 3)
        self.assertTrue(all(infos[i]["id_video"] == "700" for i in (1, 2, 3)))

    def test_annotations_non_exclusives_et_correction(self):
        tableau = pd.DataFrame([
            {
                "numero_document": 1, "id_video": "700",
                "source_texte": "Texte narration IA",
                "type_source": "texte_ia",
                "texte": "Texte descriptif", "statut_codage": "ok",
            },
            {
                "numero_document": 2, "id_video": "700",
                "source_texte": "Publication",
                "type_source": "texte_auteur",
                "texte": "Texte critique", "statut_codage": "ok",
            },
        ])
        tableau = initialiser_annotations_matrice(tableau, THEMES)
        for indice in tableau.index:
            for code in ("theme_1", "theme_2"):
                tableau.at[indice, code] = False
        tableau.at[1, "theme_1"] = True
        tableau.at[1, "theme_2"] = True
        tableau.at[0, "manuel_theme_1"] = True
        matrice = construire_matrice(tableau, THEMES)
        self.assertTrue(matrice.at[0, "final_theme_1"])
        self.assertFalse(matrice.at[0, "theme_1"])
        self.assertEqual(matrice.at[0, "source_texte"], "Texte narration IA")
        self.assertEqual(matrice.at[0, "type_source"], "texte_ia")
        bilan = construire_bilan_sources(matrice, THEMES)
        self.assertEqual(
            int(bilan.loc[
                bilan["source_texte"].eq("Publication")
                & bilan["theme"].eq("Affect"), "presence"
            ].iloc[0]), 1,
        )
        comparaison = comparer_sources_par_video(matrice, THEMES)
        ligne = comparaison.loc[comparaison["theme"].eq("Affect")].iloc[0]
        self.assertEqual(ligne["texte_auteur"], "oui")
        self.assertEqual(ligne["voice_to_text"], "non_disponible")

    def test_non_traite_est_distinct_de_absence(self):
        t = pd.DataFrame([{
            "numero_document": 1, "id_video": "700",
            "source_texte": "Texte narration IA",
            "type_source": "texte_ia", "texte": "Texte",
            "statut_codage": "non_traite",
        }])
        matrice = construire_matrice(
            initialiser_annotations_matrice(t, THEMES), THEMES
        )
        resultat = comparer_sources_par_video(matrice, THEMES)
        self.assertEqual(resultat.iloc[0]["texte_ia"], "non_traite")
        self.assertEqual(resultat.iloc[0]["texte_auteur"], "non_disponible")


if __name__ == "__main__":
    unittest.main()
