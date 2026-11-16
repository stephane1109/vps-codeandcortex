"""Tests d'import de commentaires CSV dans l'application Qwen."""
from __future__ import annotations

import unittest
from dataclasses import replace

from lecture_commentaires import analyser_commentaires_csv, lister_colonnes_csv
from lecture_iramuteq import analyser_corpus, exporter_iramuteq, tableau_documents


class TestImportCommentaires(unittest.TestCase):

    def test_commentaire_csv_utf8_emoji(self):
        contenu = (
            "nom_affiche;texte\n"
            'Beryl;"Rome, Milan et Turin en vrac."\n'
            "julie;\"l'Italie et la France aujourd'hui\"\n"
            'M@th_❤️💙;"Paname influence le monde"\n'
            "Cysko🇨🇫🇨🇦🇫🇷;Y a 1-1 merci la pluie\n"
        )
        documents, infos = analyser_commentaires_csv(contenu.encode("utf-8-sig"))
        self.assertEqual(len(documents), 4)
        self.assertEqual(documents[0].texte, "Rome, Milan et Turin en vrac.")
        self.assertEqual(infos[2]["nom_affiche"], "julie")
        self.assertEqual(infos[3]["nom_affiche"], "M@th_❤️💙")
        self.assertEqual(documents[3].texte, "Y a 1-1 merci la pluie")
        self.assertEqual(tableau_documents(documents).loc[0, "variable_source"], "commentaires_csv")

    def test_csv_virgules_et_sauts_ligne(self):
        source = (
            'nom_affiche,texte\n'
            "kray!!,\"c'est partout comme ça\"\n"
            'Beryl,"Première ligne\nseconde ligne"\n'
        )
        documents, infos = analyser_commentaires_csv(source)
        self.assertEqual(documents[0].texte, "c'est partout comme ça")
        self.assertEqual(documents[1].texte, "Première ligne\nseconde ligne")
        self.assertEqual(infos[2]["ligne_csv"], "3")

    def test_fichiers_mixtes_et_export_iramuteq(self):
        un, infos = analyser_commentaires_csv("nom_affiche;texte\nBeryl;bonjour\n", 0)
        deux = analyser_corpus("**** *source_original *profil_exemple\nbonjour ailleurs\n")
        deux = [replace(doc, numero=doc.numero + len(un)) for doc in deux]
        tous = un + deux
        self.assertEqual([doc.numero for doc in tous], [1, 2])
        sortie = exporter_iramuteq(
            tous, {1: "analyse_libre", 2: "indetermine"}, "qwen_position",
        ).decode("utf-8")
        self.assertIn("*qwen_position_analyse_libre", sortie)
        self.assertIn("*profil_exemple", sortie)
        self.assertEqual(infos[1]["nom_affiche"], "Beryl")

    def test_erreur_colonne_texte_absente(self):
        with self.assertRaisesRegex(ValueError, "obligatoires"):
            analyser_commentaires_csv("nom_affiche;commentaire\njulie;bonjour\n")

    def test_selection_colonne_commentaire_personnalisee(self):
        """Un CSV n'est plus obligé de contenir une colonne nommée « texte »."""
        contenu = (
            "pseudo;message;likes\n"
            "Nina;Un premier commentaire;27\n"
            "José;\"Un commentaire sur plusieurs\nlignes\";12\n"
        )
        colonnes = lister_colonnes_csv(contenu)
        self.assertEqual(colonnes, ["pseudo", "message", "likes"])
        documents, informations = analyser_commentaires_csv(
            contenu, colonne_texte="message", colonne_auteur="pseudo",
        )
        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].texte, "Un premier commentaire")
        self.assertEqual(informations[1]["nom_affiche"], "Nina")
        self.assertEqual(informations[1]["csv_likes"], "27")
        self.assertEqual(informations[1]["colonne_texte_source"], "message")

    def test_choix_colonne_sans_auteur(self):
        """Une colonne unique de commentaires doit être acceptable."""
        documents, informations = analyser_commentaires_csv(
            "avis\nBonjour\nAu revoir\n",
            colonne_texte="avis",
            colonne_auteur=None,
        )
        self.assertEqual([document.texte for document in documents],
                         ["Bonjour", "Au revoir"])
        self.assertEqual(informations[1]["nom_affiche"], "")
        self.assertEqual(informations[1]["colonne_auteur_source"], "")

    def test_choix_colonnes_dans_fichiers_mixtes(self):
        """Les numéros doivent rester distincts entre différents fichiers."""
        premiers, _ = analyser_commentaires_csv(
            "auteur;commentaire\nAlice;premier\n",
            colonne_texte="commentaire",
            colonne_auteur="auteur",
        )
        seconds, infos = analyser_commentaires_csv(
            "nom_affiche;texte\nBenoît;second\n", numero_depart=len(premiers)
        )
        self.assertEqual([document.numero for document in premiers + seconds],
                         [1, 2])
        self.assertEqual(infos[2]["nom_affiche"], "Benoît")

    def test_erreur_colonne_personnalisee_inconnue(self):
        with self.assertRaisesRegex(ValueError, "colonne de commentaire"):
            analyser_commentaires_csv(
                "auteur;message\nAlice;Bonjour\n",
                colonne_texte="inexistante",
                colonne_auteur="auteur",
            )

    def test_csv_tabulation_unicode(self):
        contenu = "auteur\tavis\tville\nZoé\t\"C'est intéressant.\"\tFoix\n"
        documents, infos = analyser_commentaires_csv(
            contenu.encode("utf-8-sig"),
            colonne_texte="avis", colonne_auteur="auteur",
        )
        self.assertEqual(documents[0].texte, "C'est intéressant.")
        self.assertEqual(infos[1]["csv_ville"], "Foix")

    def test_texte_vide_preserve(self):
        documents, infos = analyser_commentaires_csv("nom_affiche;texte\nBeryl;\n")
        self.assertEqual(documents[0].texte, "")
        self.assertEqual(infos[1]["nom_affiche"], "Beryl")


if __name__ == "__main__":
    unittest.main()
