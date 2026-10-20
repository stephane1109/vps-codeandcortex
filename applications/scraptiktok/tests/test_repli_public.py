"""Une connexion sur la recherche déclenche le repli public configuré."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import scraptiktok

class TestsRepliPublic(unittest.TestCase):
    def test_page_hashtag_avant_interaction(self):
        rapport={'hashtag_url':'https://www.tiktok.com/search/video?q=test','compte_attendu':'test','hashtag_repli':'manifestation'}
        interaction=Mock()
        with patch('scraptiktok.open_page',side_effect=[None,ValueError('arrêt du test')]) as ouvrir, patch('scraptiktok.fermer_invitation_connexion'), patch('scraptiktok.type_intervention_tiktok',return_value='connexion'):
            with self.assertRaisesRegex(ValueError,'arrêt du test'):
                scraptiktok.collect_links(Mock(),SimpleNamespace(interactive=True),rapport,sans_connexion=True,interact=interaction)
            self.assertEqual(ouvrir.call_args.args[1],'https://www.tiktok.com/tag/manifestation')
            interaction.assert_not_called()
