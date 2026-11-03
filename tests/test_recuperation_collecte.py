"""Tester la récupération des publications après une reconnexion Streamlit."""
import unittest
from pathlib import Path
from unittest.mock import patch

from webapp import StartRequest


class TestsRecuperationCollecte(unittest.TestCase):
    def test_archives_research_consultables_sans_identifiants_api(self):
        """Une archive historique ne demande pas de nouveau le secret TikTok."""
        from collecte.presse import charger_inventaire
        identifiant = charger_inventaire()[0]["id"]
        parametres = {
            "source_collecte": "presse",
            "presse_moteur": "research",
            "medias": [identifiant],
            "nom_sauvegarde": "Collecte enregistrée",
        }
        with patch("collecte.presse_research.identifiants_disponibles",
                   return_value=False):
            with self.assertRaisesRegex(ValueError, "Client key"):
                StartRequest.model_validate(parametres)
            archive = StartRequest.model_validate(
                parametres, context={"consultation_historique": True})
        self.assertEqual(archive.medias, [identifiant])
        self.assertIsNone(archive.research_client_key)
        self.assertIsNone(archive.research_client_secret)

    def test_importance_du_corpus_meme_si_zip_absent(self):
        """L'interface n'écarte plus un résultat valide sans archive finale."""
        interface = (Path(__file__).resolve().parents[1] /
                     "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('ancienne.get("can_download", False)', interface)
        self.assertIn(
            'int(ancienne.get("sauvegarde_postgres_publications") or 0) > 0',
            interface)
        self.assertIn(
            "Récupérer la dernière collecte (ZIP PostgreSQL)", interface)
        self.assertIn(
            "Récupérer les publications sauvegardées (ZIP PostgreSQL)",
            interface)

    def test_fin_apres_archivages(self):
        """Ne plus signaler une fin avant les deux sauvegardes."""
        code = (Path(__file__).resolve().parents[1] /
                "webapp.py").read_text(encoding="utf-8")
        debut = code.index(
            "job.update(status=final_status, message=final_message)")
        postgres = code.index("job.sauvegarder_postgres()", debut)
        historique = code.index("job.sauvegarder_historique()", debut)
        termine = code.index("job.update(busy=False, finished=", debut)
        self.assertLess(postgres, historique)
        self.assertLess(historique, termine)

    def test_historique_sans_zip_si_json_existent(self):
        """Les données écrites ne sont pas privées d'historique par un ZIP manquant."""
        code = (Path(__file__).resolve().parents[1] /
                "webapp.py").read_text(encoding="utf-8")
        self.assertIn('(self.directory / "publications.json").is_file()', code)
        self.assertIn('(self.directory / "journal.json").is_file()', code)
        self.assertIn('context={"consultation_historique": True}', code)


if __name__ == "__main__":
    unittest.main()
