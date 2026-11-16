"""Tests d'import CSV TikTok et de corpus IRaMuTeQ."""
from __future__ import annotations

import unittest
from dataclasses import replace

from lecture_commentaires import analyser_commentaires_csv
from lecture_iramuteq import analyser_corpus, exporter_csv, tableau_documents


class TestImports(unittest.TestCase):
    def test_csv_utf8_avec_emoji(self):
        donnees = (
            "nom_affiche;texte\n"
            "Exemple_❤️;\"Ce débat porte sur l'éducation.\"\n"
            'Autre;"Première ligne\nseconde ligne"\n'
        )
        documents, infos = analyser_commentaires_csv(
            donnees.encode("utf-8-sig")
        )
        self.assertEqual(len(documents), 2)
        self.assertEqual(infos[1]["nom_affiche"], "Exemple_❤️")
        self.assertIn("éducation", documents[0].texte)
        self.assertEqual(documents[1].texte, "Première ligne\nseconde ligne")

    def test_formats_melanges(self):
        csv, _ = analyser_commentaires_csv(
            "nom_affiche,texte\nNina,bonjour\n"
        )
        txt = analyser_corpus(
            "**** *source_original *date_2026-10-24\nun commentaire\n"
        )
        corpus = csv + [
            replace(doc, numero=doc.numero + len(csv)) for doc in txt
        ]
        tableau = tableau_documents(corpus)
        self.assertEqual(len(corpus), 2)
        self.assertEqual(tableau.loc[1, "variable_date"], "2026-10-24")
        self.assertIn("bonjour", exporter_csv(tableau).decode("utf-8-sig"))

    def test_colonnes_obligatoires(self):
        with self.assertRaisesRegex(ValueError, "obligatoires"):
            analyser_commentaires_csv("compte,commentaire\nNina,bonjour\n")


if __name__ == "__main__":
    unittest.main()
