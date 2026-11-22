"""Tests des exports privés de comptes et de leur authentification."""
import unittest
from unittest.mock import MagicMock, patch

from interface.client import appeler_api


class TestTelechargementsAuthentifies(unittest.TestCase):
    """Le téléchargement doit réutiliser les deux cookies de session."""

    @patch("interface.client.httpx.Client")
    def test_export_csv_avec_cookie_de_session_et_historique(self, client):
        reponse = MagicMock()
        reponse.is_error = False
        reponse.content = b"territoire;username;url_compte\\nToulouse;@compte;https://www.tiktok.com/@compte\\n"
        client.return_value.__enter__.return_value.request.return_value = reponse

        resultat = appeler_api(
            "/api/decouverte-territoriale/abcdef1234567890/comptes.csv",
            "a" * 64, "Bearer jeton-de-test", cookie_historique="b" * 64,
            contenu_binaire=True)

        self.assertEqual(resultat, reponse.content)
        arguments = client.return_value.__enter__.return_value.request.call_args
        self.assertEqual(arguments.args[0], "GET")
        self.assertIn("scraptiktok_session=" + "a" * 64,
                      arguments.kwargs["headers"]["Cookie"])
        self.assertIn("scraptiktok_historique=" + "b" * 64,
                      arguments.kwargs["headers"]["Cookie"])

    @patch("interface.client.httpx.Client")
    def test_appels_json_restent_inchanges(self, client):
        reponse = MagicMock()
        reponse.is_error = False
        reponse.json.return_value = {"nombre_comptes": 3}
        client.return_value.__enter__.return_value.request.return_value = reponse
        resultat = appeler_api(
            "/api/decouverte-territoriale", "a" * 64,
            cookie_historique="b" * 64)
        self.assertEqual(resultat, {"nombre_comptes": 3})


if __name__ == "__main__":
    unittest.main()
