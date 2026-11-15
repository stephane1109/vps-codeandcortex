"""Vérifier l'import des commentaires sans perdre les noms ni les caractères."""
from __future__ import annotations

import unittest

from lecture_commentaires import analyser_commentaires_csv, identifiant_auteur
from lecture_iramuteq import exporter_iramuteq, tableau_documents


class TestLectureCommentaires(unittest.TestCase):

    def test_csv_point_virgule_et_emojis(self) -> None:
        contenu = (
            "\ufeffnom_affiche;texte\n"
            'M@th_❤️💙;"Rome, Milan et Turin en vrac."\n'
            'Cysko🇨🇫🇨🇦🇫🇷;"Y a 1-1 merci la pluie"\n'
        ).encode("utf-8")
        documents, metadonnees = analyser_commentaires_csv(contenu)
        tableau = tableau_documents(documents)
        self.assertEqual(len(documents), 2)
        self.assertEqual(metadonnees[1]["nom_affiche"], "M@th_❤️💙")
        self.assertEqual(documents[0].texte, "Rome, Milan et Turin en vrac.")
        self.assertEqual(documents[1].texte, "Y a 1-1 merci la pluie")
        self.assertEqual(tableau.loc[0, "variable_source"], "commentaires_csv")
        self.assertEqual(tableau.loc[0, "numero_document"], 1)

    def test_csv_virgule_avec_citation_multiligne(self) -> None:
        contenu = (
            'nom_affiche,texte\n'
            'julie,"l\'Italie et la France aujourd\'hui"\n'
            'Beryl,"Une première ligne\net une seconde."\n'
        )
        documents, metadonnees = analyser_commentaires_csv(contenu, numero_depart=10)
        self.assertEqual([doc.numero for doc in documents], [11, 12])
        self.assertEqual(documents[1].texte, "Une première ligne\net une seconde.")
        self.assertEqual(metadonnees[11]["nom_affiche"], "julie")
        self.assertEqual(metadonnees[12]["ligne_csv"], "3")

    def test_csv_espaces_et_texte_vide(self) -> None:
        documents, infos = analyser_commentaires_csv(" NOM_AFFICHE , TEXTE \nBaye sidibe,\n")
        self.assertEqual(documents[0].texte, "")
        self.assertEqual(infos[1]["nom_affiche"], "Baye sidibe")

    def test_erreur_colonnes_manquantes(self) -> None:
        with self.assertRaisesRegex(ValueError, "obligatoires"):
            analyser_commentaires_csv("pseudo;message\nabc;salut\n")

    def test_entete_exportable_et_noms_distincts(self) -> None:
        source = "nom_affiche;texte\nM@th_❤️💙;Salut\nM@th_❤️💙;Autre\n"
        documents, infos = analyser_commentaires_csv(source)
        self.assertEqual(identifiant_auteur(infos[1]["nom_affiche"]),
                         identifiant_auteur(infos[2]["nom_affiche"]))
        sortie = exporter_iramuteq(documents, {1: "theme_01", 2: "non_analyse"}, "dartopic")
        self.assertIn(b"*dartopic_theme_01", sortie)
        self.assertIn("Salut", sortie.decode("utf-8"))

    def test_lignes_avec_trop_de_champs(self) -> None:
        with self.assertRaisesRegex(ValueError, "trop de champs"):
            analyser_commentaires_csv("nom_affiche;texte\njulie;Bonjour;inattendu\n")


if __name__ == "__main__":
    unittest.main()
