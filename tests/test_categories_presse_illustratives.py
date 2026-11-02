"""Vérifier les catégories de presse dans les métadonnées et les exports."""
import csv
import io
import unittest

from collecte.presse import (
    CODES_CATEGORIES_PRESSE,
    categorie_presse_publication,
    code_presse_publication,
    colonnes_categories_presse,
)
from corpus.construction import COLONNES_ENGAGEMENT, lignes_engagement
from corpus.export_csv import serialiser_csv
from corpus.export_iramuteq import construire_corpus
from corpus.corpus_legendes import construire_legendes
from corpus.publications_csv import (
    COLONNES_PUBLICATIONS_CSV, lignes_publications_csv,
)
from webapp import entete_publication, text_export


class TestsCategoriesPresseIllustratives(unittest.TestCase):
    def publication(self, auteur):
        """Construire une publication minimale sans accès à TikTok."""
        return {
            "id": "1234567890123456789",
            "url": "https://www.tiktok.com/@" + auteur.lstrip("@") +
                   "/video/1234567890123456789",
            "author": auteur,
            "description": "Manifestation",
            "created_at": "2026-10-25T12:00:00+00:00",
            "engagement": {
                cle: {"valeur": valeur, "brut": str(valeur)}
                for cle, valeur in (
                    ("vues", 100), ("likes", 10), ("commentaires", 2),
                    ("partages", 3), ("favoris", 1))
            },
        }

    def test_correspondance_categorie_depuis_auteur(self):
        """Reconnaître toutes les catégories, même lors d'une recherche hashtag."""
        exemples = {
            "@lemondefr": "presse_nationale",
            "france3occitanie": "presse_regio_dpt",
            "@f3cvdl": "presse_regio_dpt",
            "@clpress": "presse_indep",
            "@noahdecrypte": "presse_autre",
        }
        for compte, attendu in exemples.items():
            with self.subTest(compte=compte):
                publication = self.publication(compte)
                code = code_presse_publication(publication)
                self.assertEqual(code, attendu)
                colonnes = colonnes_categories_presse(publication)
                self.assertEqual(colonnes[attendu], 1)
                self.assertEqual(sum(colonnes.values()), 1)
                self.assertTrue(all(
                    valeur == 0 for cle, valeur in colonnes.items()
                    if cle != attendu))
        self.assertEqual(len(CODES_CATEGORIES_PRESSE), 4)
        self.assertEqual(categorie_presse_publication(
            self.publication("@CLPRESS")), "presse_independante")

    def test_compte_hors_inventaire_ne_devient_pas_autre_media(self):
        """L'absence de classement n'est ni une catégorie ni un zéro observé."""
        publication = self.publication("compte_inconnu_non_reference")
        self.assertIsNone(code_presse_publication(publication))
        self.assertTrue(all(
            valeur is None for valeur in
            colonnes_categories_presse(publication).values()))
        entete = entete_publication(publication, ("profil", "id"))
        self.assertIn("*profil_@", entete)
        self.assertNotIn("*presse_", entete)

    def test_export_txt_conserve_profil_et_categorie(self):
        """Une seule variable illustrative est ajoutée à l'en-tête principal."""
        publication = self.publication("@france3occitanie")
        contenu = text_export([publication], include_sources=False,
                             variables_txt=("date", "profil", "id"))
        self.assertIn("*profil_@france3occitanie", contenu)
        self.assertIn("*presse_regio_dpt", contenu)
        self.assertNotIn("*presse_indep", contenu)
        self.assertNotIn("*presse_nationale", contenu)
        # Un choix sans métadonnées conserve malgré tout la catégorie du média.
        texte_minimal = text_export([publication], include_sources=False,
                                    variables_txt=())
        self.assertIn("*presse_regio_dpt", texte_minimal)

    def test_colonnes_csv_publications_et_engagement(self):
        """Les quatre indicatrices apparaissent dans les deux formats de CSV."""
        publications = [
            self.publication("lemondefr"),
            self.publication("france3occitanie"),
            self.publication("clpress"),
            self.publication("noahdecrypte"),
            self.publication("compte_inconnu_non_reference"),
        ]
        noms = tuple(CODES_CATEGORIES_PRESSE.values())
        for colonnes, lignes in (
            (COLONNES_PUBLICATIONS_CSV, lignes_publications_csv(publications)),
            (COLONNES_ENGAGEMENT, lignes_engagement(publications)),
        ):
            for nom in noms:
                self.assertIn(nom, colonnes)
            for rang, nom in enumerate(noms):
                self.assertEqual(lignes[rang][nom], 1)
                self.assertEqual(
                    sum(lignes[rang][champ] for champ in noms), 1)
            self.assertTrue(all(lignes[-1][champ] is None for champ in noms))
            texte = serialiser_csv(lignes, colonnes)
            tableau = list(csv.DictReader(io.StringIO(texte), delimiter=";"))
            self.assertEqual([tableau[i][noms[i]] for i in range(4)],
                             ["1", "1", "1", "1"])
            self.assertTrue(all(tableau[-1][nom] == "" for nom in noms))

    def test_corpus_iramuteq_alternatif(self):
        """La modalité est autonome, sans suffixe _true."""
        publication = self.publication("clpress")
        documents = construire_legendes([publication])
        texte = construire_corpus(documents)
        self.assertIn("*presse_indep", texte)
        self.assertNotIn("*presse_indep_true", texte)
        self.assertIn("*type_legende", texte)


if __name__ == "__main__":
    unittest.main()
