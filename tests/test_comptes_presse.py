import unittest
from collecte.verification_comptes import normaliser_compte, verifier_profil
from collecte.presse import charger_inventaire, selectionner_medias
from webapp import StartRequest

class TestsComptes(unittest.TestCase):
    def test_normalisation_et_validation(self):
        self.assertEqual(normaliser_compte("https://www.tiktok.com/@LeMondeFR/"), "lemondefr")
        self.assertEqual(normaliser_compte("@.sofino"), ".sofino")
        self.assertEqual(normaliser_compte("https://www.tiktok.com/@.sofino/"), ".sofino")
        self.assertEqual(normaliser_compte("@rtl.officiel"), "rtl.officiel")
        self.assertEqual(normaliser_compte("@streetpress_"), "streetpress_")
        for valeur in ("https://evil.test/@media", "../etc", "@", "a/b", "@compte.", "..", "a"*25):
            with self.assertRaises(ValueError): normaliser_compte(valeur)
    def test_inventaire_et_sources(self):
        inventaire = charger_inventaire()
        self.assertGreaterEqual(len(inventaire), 2)
        requete = StartRequest(source_collecte="presse", medias=[m["id"] for m in inventaire])
        self.assertEqual(len(requete.sources), len(inventaire))
        self.assertEqual(selectionner_medias(["lemonde"])[0]["compte"], "lemondefr")
        with self.assertRaises(ValueError): selectionner_medias(["inconnu"])
        self.assertTrue(StartRequest(source_collecte="comptes", comptes=["lemondefr"]).enrichie)
        with self.assertRaises(ValueError): StartRequest(source_collecte="comptes")
    def test_badge_ne_prouve_pas_propriete(self):
        resultat = verifier_profil("lemondefr", {"uniqueId":"lemondefr", "verified":True})
        self.assertTrue(resultat["concordant"])
        self.assertEqual(resultat["proprietaire_editorial"], "indetermine")

class TestsRechercheComptes(unittest.TestCase):
    def arguments(self):
        import scraptiktok
        args = scraptiktok.parse_args(['test', '--limit', '2'])
        args.timeout = .01
        args.delay = 0
        args.idle_rounds = 1
        args.max_scrolls = 3
        return args

    def test_sans_hashtag_recherche_compte_et_exclut_autres_auteurs(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        pilote = Mock()
        pages = iter([
            ['https://www.tiktok.com/@autre/video/111'],
            ['https://www.tiktok.com/@lemondefr/video/222',
             'https://www.tiktok.com/@lemondefr/video/333'],
        ])
        pilote.execute_script.side_effect = lambda code: next(pages) if code == moteur.DISCOVER_JS else False
        rapport = {}
        liens = collecter_compte(pilote, self.arguments(), '@LeMondeFR', rapport)
        pilote.get.assert_called_once_with('https://www.tiktok.com/search?q=%40lemondefr')
        self.assertEqual(liens, ['https://www.tiktok.com/@lemondefr/video/222',
                                'https://www.tiktok.com/@lemondefr/video/333'])
        self.assertEqual(rapport['recherches'][0]['candidats_examines'], 3)
        self.assertFalse(rapport['exhaustif'])

    def test_deux_hashtags_memes_pages_une_validation_et_dedoublonnage(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        args = self.arguments(); args.limit = 3; args.interactive = True
        pilote, intervention = Mock(), Mock()
        resultats = {
            'https://www.tiktok.com/tag/lyceen': ['https://www.tiktok.com/@lemondefr/video/111'],
            'https://www.tiktok.com/tag/manifestation': ['https://www.tiktok.com/@autre/video/999',
                'https://www.tiktok.com/@lemondefr/video/111', 'https://www.tiktok.com/@lemondefr/video/222'],
        }
        pilote.execute_script.side_effect = lambda code: resultats[pilote.get.call_args.args[0]] if code == moteur.DISCOVER_JS else False
        rapport = {}
        liens = collecter_compte(pilote, args, 'lemondefr', rapport,
                                hashtags=['#lyceen', '#manifestation'], interact=intervention)
        self.assertEqual([c.args[0] for c in pilote.get.call_args_list], list(resultats))
        intervention.assert_called_once()
        self.assertEqual(liens, ['https://www.tiktok.com/@lemondefr/video/111', 'https://www.tiktok.com/@lemondefr/video/222'])

    def test_autres_auteurs_seulement_ne_declenche_pas_fausse_erreur_acces(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        pilote = Mock()
        pilote.execute_script.side_effect = lambda code: ['https://www.tiktok.com/@autre/video/111'] if code == moteur.DISCOVER_JS else False
        rapport = {}
        self.assertEqual(collecter_compte(pilote, self.arguments(), 'lemondefr', rapport), [])
        self.assertEqual(rapport['discovery_stop'], 'no_new_links')

    def test_une_recherche_en_echec_conserve_les_resultats_de_l_autre(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        url = 'https://www.tiktok.com/@lemondefr/video/222'
        with patch('scraptiktok.collect_links', side_effect=[RuntimeError('Échec TikTok'), [url]]):
            rapport = {}
            self.assertEqual(collecter_compte(Mock(), self.arguments(), 'lemondefr', rapport,
                                             hashtags=['lyceen', 'manifestation']), [url])
        self.assertEqual(rapport['recherches_en_echec'], 1)

    def test_ancienne_recherche_non_acceptee_apres_delai(self):
        import scraptiktok
        self.assertFalse(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search?q=%40autre',
                                                     'https://www.tiktok.com/search?q=%40lemondefr'))
        self.assertTrue(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search?q=%40lemondefr&lang=fr',
                                                    'https://www.tiktok.com/search?q=%40lemondefr'))
