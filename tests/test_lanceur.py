"""Non-régression du démarrage et de la supervision de l'interface."""
import asyncio
import unittest
from unittest.mock import Mock, patch
import lancer_interface as lanceur


class TestsLanceur(unittest.TestCase):
    def test_port_interne_occupe_refuse_avant_lancement(self):
        with patch.object(lanceur.socket, 'socket') as fabrique:
            fabrique.return_value.__enter__.return_value.bind.side_effect = OSError('occupé')
            with self.assertRaisesRegex(RuntimeError, 'déjà utilisé'):
                lanceur.verifier_port_interne(8511)

    def test_enfant_mort_ne_valide_pas_ancien_serveur(self):
        processus = Mock(); processus.poll.return_value = 1
        arret = Mock(); arret.is_set.return_value = False
        with patch.object(lanceur.urllib.request, 'build_opener') as client:
            with self.assertRaisesRegex(RuntimeError, 'arrêté'):
                lanceur.attendre_streamlit(processus, 8511, arret)
            client.return_value.open.assert_not_called()

    def test_sante_positive_mais_enfant_arrete_refusee(self):
        processus = Mock(); processus.poll.side_effect = [None, 1]
        arret = Mock(); arret.is_set.return_value = False; arret.wait.return_value = False
        with patch.object(lanceur.urllib.request, 'build_opener') as client:
            reponse = client.return_value.open.return_value.__enter__.return_value
            reponse.status = 200; reponse.read.return_value = b'ok'
            with self.assertRaisesRegex(RuntimeError, 'démarrage annulé'):
                lanceur.attendre_streamlit(processus, 8511, arret)


class TestsSupervision(unittest.IsolatedAsyncioTestCase):
    async def test_perte_interface_arrete_moteur(self):
        class Serveur:
            should_exit = False
            async def serve(self, sockets):
                while not self.should_exit: await asyncio.sleep(.01)
        serveur = Serveur(); processus = Mock(); processus.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'redémarrage complet'):
            await lanceur.superviser(serveur, processus, None)
        self.assertTrue(serveur.should_exit)
