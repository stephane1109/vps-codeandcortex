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
        requete = StartRequest(hashtag="test", source_collecte="presse", medias=[m["id"] for m in inventaire])
        self.assertEqual(len(requete.sources), len(inventaire))
        self.assertEqual(selectionner_medias(["lemonde"])[0]["compte"], "lemondefr")
        with self.assertRaises(ValueError): selectionner_medias(["inconnu"])
        self.assertTrue(StartRequest(hashtag="test", source_collecte="comptes", comptes=["lemondefr"]).enrichie)
        with self.assertRaises(ValueError): StartRequest(hashtag="test", source_collecte="comptes")
    def test_hashtag_obligatoire_pour_profils_et_presse(self):
        for source in (
            {"source_collecte": "comptes", "comptes": ["lemondefr"]},
            {"source_collecte": "presse", "medias": ["lemonde"]},
        ):
            for filtres in ({}, {"hashtag": ""}, {"hashtag": "   "}, {"second_hashtag": "actualité"}):
                with self.subTest(source=source["source_collecte"], filtres=filtres):
                    with self.assertRaisesRegex(ValueError, "au moins un hashtag"):
                        StartRequest(**source, **filtres)
            with self.subTest(source=source["source_collecte"], filtre="unique"):
                requete = StartRequest(**source, hashtag="#actualité")
                self.assertEqual(requete.hashtags, ["actualité"])
                self.assertEqual(requete.second_hashtag, "")
            for operateur in ("AND", "OR"):
                with self.subTest(source=source["source_collecte"], operateur=operateur):
                    requete = StartRequest(
                        **source, hashtag="#actualité", second_hashtag="#politique", operator=operateur
                    )
                    self.assertEqual(requete.hashtags, ["actualité", "politique"])
                    self.assertEqual(requete.operator, operateur)

    def test_badge_ne_prouve_pas_propriete(self):
        resultat = verifier_profil("lemondefr", {"uniqueId":"lemondefr", "verified":True})
        self.assertTrue(resultat["concordant"])
        self.assertEqual(resultat["proprietaire_editorial"], "indetermine")

class TestsRechercheComptes(unittest.TestCase):
    def test_profils_recherchent_le_compte_dans_chaque_requete(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        from types import SimpleNamespace
        rapport = {}
        with patch('scraptiktok.collect_links', return_value=[]) as moteur:
            collecter_compte(Mock(), SimpleNamespace(limit=50), '@LeMondeFR', rapport,
                            hashtags=['#lyceen', '#manifestation'])
        self.assertEqual([c.args[2]['hashtag_url'] for c in moteur.call_args_list],
                         ['https://www.tiktok.com/search/video?q=%40lemondefr%20%23lyceen', 'https://www.tiktok.com/search/video?q=%40lemondefr%20%23manifestation'])
        self.assertTrue(all(c.kwargs['comptes_attendus'] == ['lemondefr'] for c in moteur.call_args_list))
        self.assertTrue(all(c.kwargs['sans_connexion'] for c in moteur.call_args_list))
        self.assertEqual(rapport['compte_attendu'], 'lemondefr')
        with self.assertRaisesRegex(ValueError, 'au moins un hashtag'):
            collecter_compte(Mock(), SimpleNamespace(limit=50), 'lemondefr')

    def test_erreur_ou_captcha_ne_declenche_aucun_repli_profil(self):
        from unittest.mock import Mock, patch
        from collecte.comptes import collecter_compte
        from types import SimpleNamespace
        for message in ('Erreur TikTok', 'CAPTCHA'):
            with self.subTest(message=message), patch('scraptiktok.collect_links', side_effect=RuntimeError(message)) as moteur:
                rapport = {}
                with self.assertRaises(RuntimeError):
                    collecter_compte(Mock(), SimpleNamespace(limit=50), 'lemondefr', rapport, hashtags=['test'])
                moteur.assert_called_once()
                self.assertEqual(rapport['recherches_en_echec'], 1)
                self.assertEqual(rapport['hashtag_url'], 'https://www.tiktok.com/search/video?q=%40lemondefr%20%23test')

    def test_entree_collect_links_compte_ne_navigue_jamais_vers_profil(self):
        from unittest.mock import Mock, patch
        from types import SimpleNamespace
        import scraptiktok
        pilote = Mock()
        rapport = {'compte_attendu':'lemondefr', 'hashtag_url':'https://www.tiktok.com/@lemondefr'}
        with patch('collecte.recherche_comptes.collecter_recherche_compte', return_value=[]) as recherche:
            self.assertEqual(scraptiktok.collect_links(pilote, SimpleNamespace(), rapport), [])
        recherche.assert_called_once()
        pilote.get.assert_not_called()

    def test_ancienne_recherche_non_acceptee_apres_delai(self):
        import scraptiktok
        self.assertFalse(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search/video?q=%40autre',
                                                     'https://www.tiktok.com/search/video?q=%40lemondefr'))
        self.assertTrue(scraptiktok.meme_page_tiktok('https://www.tiktok.com/search/video?q=%40lemondefr&lang=fr',
                                                    'https://www.tiktok.com/search/video?q=%40lemondefr'))

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
