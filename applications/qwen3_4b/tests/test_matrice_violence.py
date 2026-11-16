"""Tests du regroupement thématique par texte et par source."""
from __future__ import annotations
import unittest
import pandas as pd
from matrice_violence import (
    analyser_sources_csv, initialiser_annotations_matrice,
    construire_matrice, construire_bilan_sources,
    comparer_sources_par_video,
)


class TestMatriceViolence(unittest.TestCase):
    def test_un_seul_texte_csv_sans_configuration_speciale(self):
        documents, infos = analyser_sources_csv(
            "texte\nC honteux\nBonjour\n",
            {"texte_libre": "texte"},
        )
        self.assertEqual(len(documents), 2)
        self.assertEqual(infos[1]["source_texte"], "texte_libre")
        self.assertEqual(documents[0].texte, "C honteux")

    def test_trois_textes_meme_video(self):
        documents, infos = analyser_sources_csv(
            "id_video;texte_ia;texte_auteur;voice_to_text\n"
            "700;Neutre;Scandaleux;Une accusation\n",
            {
                "texte_ia": "texte_ia",
                "texte_auteur": "texte_auteur",
                "voice_to_text": "voice_to_text",
            },
            colonne_id_video="id_video",
        )
        self.assertEqual(len(documents), 3)
        self.assertEqual([infos[i]["id_video"] for i in (1, 2, 3)],
                         ["700", "700", "700"])

    def test_matrice_non_exclusive_et_correction(self):
        tableau = pd.DataFrame([
            {"numero_document": 1, "id_video": "700",
             "source_texte": "texte_ia", "texte": "description",
             "statut_codage": "ok"},
            {"numero_document": 2, "id_video": "700",
             "source_texte": "texte_auteur", "texte": "indignation",
             "statut_codage": "ok"},
        ])
        tableau = initialiser_annotations_matrice(tableau)
        for i in tableau.index:
            for code in ("theme_denonciation", "theme_indignation",
                         "theme_persecuteur"):
                tableau.at[i, code] = False
        tableau.at[1, "theme_denonciation"] = True
        tableau.at[1, "theme_indignation"] = True
        tableau.at[0, "manuel_theme_denonciation"] = True
        matrice = construire_matrice(tableau)
        self.assertTrue(matrice.at[0, "final_theme_denonciation"])
        self.assertFalse(matrice.at[0, "theme_denonciation"])
        bilan = construire_bilan_sources(matrice)
        self.assertEqual(int(bilan.loc[
            bilan["source_texte"].eq("texte_auteur")
            & bilan["theme"].eq("Indignation"), "presence"
        ].iloc[0]), 1)
        comparaison = comparer_sources_par_video(matrice)
        ligne = comparaison.loc[
            comparaison["theme"].eq("Indignation")
        ].iloc[0]
        self.assertEqual(ligne["texte_auteur"], "oui")
        self.assertEqual(ligne["voice_to_text"], "non_disponible")

    def test_non_traite_distinct_source_absente(self):
        tableau = pd.DataFrame([{
            "numero_document": 1, "id_video": "800",
            "source_texte": "texte_ia", "texte": "description",
            "statut_codage": "non_traite",
        }])
        matrice = construire_matrice(initialiser_annotations_matrice(tableau))
        comparaison = comparer_sources_par_video(matrice)
        self.assertEqual(comparaison.iloc[0]["texte_ia"], "non_traite")
        self.assertEqual(comparaison.iloc[0]["texte_auteur"], "non_disponible")


if __name__ == "__main__":
    unittest.main()
