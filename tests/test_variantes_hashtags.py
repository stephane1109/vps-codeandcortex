"""Variantes accentuées uniquement à la demande, sans combinaisons illimitées."""
import unittest
from unittest.mock import Mock, patch

from collecte.hashtags import variantes_hashtag
from connect_htag import ConnexionHashtag
from webapp import StartRequest


class TestVariantesHashtags(unittest.TestCase):
    def test_defaut_strict_ne_recherche_que_le_tag_demande(self):
        self.assertEqual(variantes_hashtag("lyceen"), ["lyceen"])
        reglages = StartRequest(hashtag="lyceen")
        sources = ConnexionHashtag(Mock()).preparer_sources(reglages)
        self.assertEqual([s["hashtag"] for s in sources], ["lyceen"])

    def test_avec_accents_ajoute_lyceen_et_lyceen_accentue(self):
        variantes = variantes_hashtag("lyceen", avec_accents=True)
        self.assertEqual(variantes[0], "lyceen")
        self.assertIn("lycéen", variantes)
        self.assertLessEqual(len(variantes), 8)
        reglages = StartRequest(hashtag="lyceen", variantes_accents=True)
        sources = ConnexionHashtag(Mock()).preparer_sources(reglages)
        self.assertIn("lycéen", [s["hashtag"] for s in sources])
        self.assertTrue(all(s["hashtag_demande"] == "lyceen" for s in sources))

    def test_entree_accentuee_conserve_original_et_ajoute_forme_simple(self):
        variantes = variantes_hashtag("lycéen", avec_accents=True)
        self.assertEqual(variantes[0], "lycéen")
        self.assertIn("lyceen", variantes)

    def test_double_accent_pour_ete(self):
        variantes = variantes_hashtag("ete", avec_accents=True)
        self.assertIn("été", variantes)
        self.assertLessEqual(len(variantes), 8)

    def test_recherches_bornees_avec_deux_hashtags(self):
        reglages = StartRequest(hashtag="lyceen", second_hashtag="manifestation",
                               variantes_accents=True)
        sources = ConnexionHashtag(Mock()).preparer_sources(reglages)
        valeurs = [s["hashtag"] for s in sources]
        self.assertLessEqual(len(valeurs), 16)
        self.assertEqual(len(valeurs), len({s.casefold() for s in valeurs}))

    def test_variantes_partagent_un_seul_quota_par_hashtag(self):
        reglages = StartRequest(hashtag="lyceen", variantes_accents=True, limit=3)
        connexion = ConnexionHashtag(Mock(limit=3))
        connexion.arguments.limit = 3
        sources = connexion.preparer_sources(reglages)
        connexion.navigateur = Mock()
        visités = []
        urls = [
            "https://www.tiktok.com/@test/video/123",
            "https://www.tiktok.com/@test/video/456",
            "https://www.tiktok.com/@test/video/789",
        ]

        def trouver(navigateur, arguments, rapport, **options):
            visités.append((rapport["hashtag_url"], arguments.limit))
            # Deux pages différentes peuvent présenter des vidéos identiques.
            if len(visités) == 1:
                return [urls[0]]
            if len(visités) == 2:
                return [urls[0], urls[1]]
            return [urls[0], urls[2]]

        resultat = []
        with patch("collecte.hashtags.collecter_hashtag", side_effect=trouver):
            for source in sources:
                resultat.extend(connexion.decouvrir(source, {}))
        self.assertEqual(len(resultat), 3)
        self.assertEqual(len(set(resultat)), 3)
        self.assertTrue(any("/lycéen" in url or "/lyc%C3%A9en" in url for url, _ in visités))
        self.assertEqual(connexion._ids_par_hashtag["lyceen"], {"123", "456", "789"})
        self.assertLessEqual(sum(quantite for _url, quantite in visités), 3)

    def test_deux_hashtags_50_posts_signifie_50_au_total_et_ou(self):
        for operateur in ("AND", "OR"):
            with self.subTest(operateur=operateur):
                reglages = StartRequest(
                    hashtag="manifestation", second_hashtag="lyceen",
                    limit=50, operator=operateur,
                )
                connexion = ConnexionHashtag(Mock(limit=50))
                sources = connexion.preparer_sources(reglages)
                self.assertEqual(connexion._quota_hashtag,
                                 {"manifestation": 25, "lyceen": 25})
                connexion.navigateur = Mock()
                appels = []

                def trouver(navigateur, arguments, rapport, **options):
                    appels.append(arguments.limit)
                    base = 1000 if "/manifestation" in rapport["hashtag_url"] else 2000
                    return [
                        f"https://www.tiktok.com/@journal/video/{base + i}"
                        for i in range(arguments.limit)
                    ]

                with patch("collecte.hashtags.collecter_hashtag", side_effect=trouver):
                    liens = [url for source in sources for url in connexion.decouvrir(source,{})]
                self.assertEqual(appels, [25, 25])
                self.assertEqual(len(liens), 50)
                self.assertEqual(len(set(liens)), 50)
                self.assertEqual(len(connexion._ids_globaux), 50)

    def test_deux_hashtags_avec_doublons_et_variantes_ne_depassent_pas_limite(self):
        reglages = StartRequest(
            hashtag="lyceen", second_hashtag="manifestation",
            variantes_accents=True, limit=11,
        )
        connexion = ConnexionHashtag(Mock(limit=11))
        sources = connexion.preparer_sources(reglages)
        connexion.navigateur = Mock()
        compteur = [0]

        def trouver(navigateur, arguments, rapport, **options):
            compteur[0] += 1
            return [
                f"https://www.tiktok.com/@journal/video/{1000 + ((compteur[0] * 13 + i) % 50)}"
                for i in range(arguments.limit)
            ]

        with patch("collecte.hashtags.collecter_hashtag", side_effect=trouver):
            liens = [url for source in sources for url in connexion.decouvrir(source,{})]
        self.assertLessEqual(len(liens), 11)
        self.assertEqual(len(set(liens)), len(liens))
        self.assertEqual(sum(connexion._quota_hashtag.values()), 11)
        self.assertLessEqual(len(connexion._ids_globaux), 11)

    def test_presse_ne_lance_pas_de_variantes(self):
        reglages = StartRequest(source_collecte="presse", medias=["lemonde"],
                               variantes_accents=True)
        self.assertFalse(reglages.variantes_accents)


if __name__ == "__main__":
    unittest.main()
