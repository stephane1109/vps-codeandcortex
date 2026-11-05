"""Tests des imports de comptes CSV dans le formulaire Profils."""

import unittest

from collecte.import_comptes_csv import lire_comptes_csv, lire_plusieurs_csv


class TestImportComptesCSV(unittest.TestCase):
    def test_export_territorial_scraptiktok(self):
        """Relire directement un comptes.csv avec son séparateur et son BOM."""
        contenu = (
            "territoire;username;url_compte;videos_trouvees;"
            "url_video_preuve\n"
            "Toulouse;@microbalade;https://www.tiktok.com/@microbalade;2;"
            "https://www.tiktok.com/@microbalade/video/123\n"
            "Toulouse;@lyceens.tlse;https://www.tiktok.com/@lyceens.tlse;1;\n"
        ).encode("utf-8-sig")
        resultat = lire_comptes_csv(contenu)
        self.assertEqual(
            resultat["comptes"], ["microbalade", "lyceens.tlse"])
        self.assertEqual(resultat["doublons"], 0)
        self.assertEqual(resultat["invalides"], [])

    def test_csv_virgules_et_urls_de_profils(self):
        """Accepter un export avec une colonne url_compte."""
        contenu = (
            'nom,url_compte\n'
            'Premier,https://www.tiktok.com/@compte.test\n'
            'Deuxième,https://www.tiktok.com/@autre_compte\n'
        ).encode("utf-8")
        resultat = lire_comptes_csv(contenu)
        self.assertEqual(resultat["comptes"], ["compte.test", "autre_compte"])

    def test_colonne_unique_sans_entete(self):
        """Accepter une liste directe à une colonne."""
        contenu = b"@profil_a\nprofil_b\nhttps://www.tiktok.com/@profil_c\n"
        resultat = lire_comptes_csv(contenu)
        self.assertEqual(
            resultat["comptes"], ["profil_a", "profil_b", "profil_c"])

    def test_doublons_et_lignes_invalides(self):
        """Conserver les comptes distincts sans importer les cellules invalides."""
        contenu = (
            "compte\n@Profil_A\nprofil_a\nincorrect!!\n"
            "profil_b\n\n"
        ).encode("utf-8")
        resultat = lire_comptes_csv(contenu)
        self.assertEqual(resultat["comptes"], ["profil_a", "profil_b"])
        self.assertEqual(resultat["doublons"], 1)
        self.assertEqual(len(resultat["invalides"]), 1)

    def test_import_multi_csv_sans_limite_de_dix_profils(self):
        """Fusionner des inventaires supérieurs à dix profils."""
        un = "username\n" + "\n".join(
            f"@compte_{i:03d}" for i in range(20)) + "\n"
        deux = "username\n" + "\n".join(
            f"@compte_{i:03d}" for i in range(15, 40)) + "\n"
        resultat = lire_plusieurs_csv([
            ("comptes_1.csv", un.encode()),
            ("comptes_2.csv", deux.encode()),
        ])
        self.assertEqual(len(resultat["comptes"]), 40)
        self.assertEqual(resultat["doublons"], 5)
        self.assertEqual(resultat["comptes"][0], "compte_000")
        self.assertEqual(resultat["comptes"][-1], "compte_039")

    def test_colonne_inconnue_refusee(self):
        """Ne pas confondre un CSV de métriques avec un CSV de comptes."""
        with self.assertRaisesRegex(ValueError, "Colonne de comptes"):
            lire_comptes_csv(b"likes;vues\n12;103\n")

    def test_csv_vide_refuse(self):
        """Un fichier vide ne doit pas remplacer la sélection courante."""
        with self.assertRaisesRegex(ValueError, "vide"):
            lire_comptes_csv(b"")

    def test_nom_fichier_rapporte_sur_erreur(self):
        """Identifier le CSV incorrect parmi plusieurs imports."""
        with self.assertRaisesRegex(ValueError, "incorrect.csv"):
            lire_plusieurs_csv([
                ("correct.csv", b"username\n@compte_a\n"),
                ("incorrect.csv", b"likes;vues\n12;103\n"),
            ])


if __name__ == "__main__":
    unittest.main()
