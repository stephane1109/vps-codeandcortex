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

    def test_sans_hashtag_lit_profil_et_exclut_autres_auteurs(self):
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
        pilote.get.assert_called_once_with('https://www.tiktok.com/@lemondefr')
        self.assertEqual(liens, ['https://www.tiktok.com/@lemondefr/video/222',
                                'https://www.tiktok.com/@lemondefr/video/333'])
        self.assertEqual(rapport['recherches'][0]['candidats_examines'], 3)
        self.assertFalse(rapport['exhaustif'])

    def test_deux_hashtags_recherches_ciblees_sans_pause_imposee_et_dedoublonnage(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        args = self.arguments(); args.limit = 3; args.interactive = True
        pilote, intervention = Mock(), Mock()
        resultats = {
            'https://www.tiktok.com/search/video?q=%40lemondefr%20%23lyceen': ['https://www.tiktok.com/@lemondefr/video/111'],
            'https://www.tiktok.com/search/video?q=%40lemondefr%20%23manifestation': ['https://www.tiktok.com/@autre/video/999',
                'https://www.tiktok.com/@lemondefr/video/111', 'https://www.tiktok.com/@lemondefr/video/222'],
        }
        pilote.execute_script.side_effect = lambda code: resultats[pilote.get.call_args.args[0]] if code == moteur.DISCOVER_JS else False
        rapport = {}
        liens = collecter_compte(pilote, args, 'lemondefr', rapport,
                                hashtags=['#lyceen', '#manifestation'], interact=intervention)
        self.assertEqual([c.args[0] for c in pilote.get.call_args_list], list(resultats))
        intervention.assert_not_called()
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
        self.assertFalse(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search/video?q=%40autre',
                                                     'https://www.tiktok.com/search/video?q=%40lemondefr'))
        self.assertTrue(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search/video?q=%40lemondefr&lang=fr',
                                                    'https://www.tiktok.com/search/video?q=%40lemondefr'))

    def test_limite_premier_hashtag_ne_supprime_pas_le_second(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        args = self.arguments(); args.limit = 1
        liens = ['https://www.tiktok.com/@lemondefr/video/111', 'https://www.tiktok.com/@lemondefr/video/222']
        with patch('scraptiktok.collect_links', side_effect=[[liens[0]], [liens[1]]]) as collecte:
            self.assertEqual(collecter_compte(Mock(), args, 'lemondefr', hashtags=['lyceen','manifestation']), liens)
        self.assertEqual(collecte.call_count, 2)

    def test_profil_inaccessible_recherche_de_repli_meme_session(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        pilote = Mock(); rapport = {}
        lien = 'https://www.tiktok.com/@lemondefr/video/222'
        with patch('scraptiktok.collect_links', side_effect=[RuntimeError('Erreur chargement'), [lien]]) as collecte:
            self.assertEqual(collecter_compte(pilote, self.arguments(), 'lemondefr', rapport), [lien])
        self.assertEqual([c.args[2]['hashtag_url'] for c in collecte.call_args_list],
                         ['https://www.tiktok.com/@lemondefr', 'https://www.tiktok.com/search/video?q=%40lemondefr'])
        self.assertTrue(all(c.args[0] is pilote for c in collecte.call_args_list))
        self.assertEqual(rapport['recherches_en_echec'], 1)

    def test_captcha_ne_declenche_pas_navigation_de_repli(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        def blocage(pilote, args, rapport, **options):
            rapport['diagnostic'] = {'code': 'verification_tiktok'}
            raise RuntimeError('Vérification nécessaire')
        with patch('scraptiktok.collect_links', side_effect=blocage) as collecte:
            with self.assertRaises(RuntimeError):
                collecter_compte(Mock(), self.arguments(), 'lemondefr')
        collecte.assert_called_once()

    def test_brut_sans_hashtag_grille_vide_ou_erreur_repli_sans_pause(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        lien = 'https://www.tiktok.com/@brutofficiel/video/222'
        for erreur in (False, True):
            with self.subTest(erreur_tiktok=erreur):
                args = self.arguments(); args.limit = 1; args.interactive = True
                pilote, intervention = Mock(), Mock()
                def executer(code):
                    url = pilote.get.call_args.args[0]
                    if code == moteur.BLOCKED_JS: return False
                    if code == moteur.DISCOVER_JS: return [lien] if '/search/video' in url else []
                    if code == moteur.DIAGNOSTIC_JS: return {'erreur_tiktok': erreur, 'liens': 0}
                    return []
                pilote.execute_script.side_effect = executer
                rapport = {}
                self.assertEqual(collecter_compte(pilote, args, 'brutofficiel', rapport,
                                                  interact=intervention), [lien])
                intervention.assert_not_called()
                visites = [c.args[0] for c in pilote.get.call_args_list]
                self.assertEqual(visites, ['https://www.tiktok.com/@brutofficiel'] * (2 if erreur else 1)
                                 + ['https://www.tiktok.com/search/video?q=%40brutofficiel'])
                self.assertEqual(rapport['repli'], 'recherche_compte')

    def test_verification_reelle_du_profil_reste_interactive(self):
        from unittest.mock import Mock
        from collecte.comptes import collecter_compte
        import scraptiktok as moteur
        args = self.arguments(); args.limit = 1; args.interactive = True
        pilote = Mock(); verifie = []
        lien = 'https://www.tiktok.com/@brutofficiel/video/222'
        def executer(code):
            if code == moteur.BLOCKED_JS: return not verifie
            if code == moteur.DISCOVER_JS: return [lien] if verifie else []
            return []
        pilote.execute_script.side_effect = executer
        intervention = Mock(side_effect=lambda message: verifie.append(True))
        self.assertEqual(collecter_compte(pilote, args, 'brutofficiel', interact=intervention), [lien])
        intervention.assert_called_once()
        self.assertIn('vérification', intervention.call_args.args[0])
        pilote.get.assert_called_once_with('https://www.tiktok.com/@brutofficiel')

    def test_donnees_json_identite_et_type_de_publication(self):
        import json
        from scraptiktok import liens_donnees_publications
        donnees = {'items': [
            {'id': '111', 'author': {'uniqueId':'lemondefr'}, 'desc':'Texte', 'video':{'duration':5}},
            {'id': '222', 'author':'franceinfo', 'desc':'Texte', 'imagePost':{'images':[{}]}},
            {'id': '333', 'author':'autre', 'desc':'Texte sans média'},
            {'id': '444', 'author':'a/b', 'desc':'URL invalide', 'video':{'duration':2}},
            {'id': '555', 'author':{'nickname':'Sans identifiant'}, 'desc':'Texte', 'video':{'duration':2}},
        ]}
        self.assertEqual(set(liens_donnees_publications(['{', json.dumps(donnees)])),
                         {'https://www.tiktok.com/@lemondefr/video/111', 'https://www.tiktok.com/@franceinfo/photo/222'})
