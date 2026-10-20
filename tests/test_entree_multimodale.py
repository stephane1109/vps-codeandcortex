"""Régressions entre collecte publique, fichiers MP4 et analyse."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch, Mock
import scraptiktok

class TestsEntreeMultimodale(unittest.TestCase):
    def test_recherche_bloquee_repli_hashtag_filtre(self):
        rapport={'mode_decouverte':'recherche_compte_hashtag','hashtag_recherche':'manifestation',
                 'hashtag_url':'https://www.tiktok.com/search/video?q=manifestation+test'}
        args=SimpleNamespace(limit=10,interactive=True)
        interaction=Mock()
        with patch('scraptiktok.open_page'), patch('scraptiktok.fermer_invitation_connexion'), patch('scraptiktok.type_intervention_tiktok',return_value='connexion'), patch('collecte.comptes.collecter_comptes_par_hashtag',return_value=['lien']) as repli:
            self.assertEqual(scraptiktok.collect_links(Mock(),args,rapport,comptes_attendus=['test'],interact=interaction),['lien'])
            self.assertEqual(repli.call_args.args[2:4],(['test'],'manifestation'))
            interaction.assert_not_called()
            self.assertEqual(rapport['repli_public']['motif'],'connexion_recherche')
