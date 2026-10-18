"""Vérifier l'affichage réel des résultats et leur sérialisation par PyArrow."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from detection import (COLONNES_DETECTIONS, COLONNES_INTERVALLES,
                       COLONNES_RESULTATS, ouvrir_csv)


class TestsInterface(unittest.TestCase):
    """Exercer le tableau sans télécharger de modèle ni analyser de vidéo."""

    def test_affichage_resultats_et_erreurs(self):
        """Afficher les mesures, les cellules absentes et les exports sans erreur."""
        resultat = {
            "video_id": "v000001", "source": "exemple.mp4", "statut": "ok",
            "erreur": "", "duree_totale_s": 40.0, "categorie": "smartphone",
            "objet_detecte": True, "duree_visibilite_s": 10.0,
            "pourcentage_visible": 25.0, "maximum_simultane": 2,
            "frequence_demandee_ips": 1.0, "images_analysees": 40,
        }
        erreur = {"video_id": "v000002", "source": "illisible.mp4",
                  "statut": "erreur", "erreur": "Fichier illisible",
                  "frequence_demandee_ips": 1.0}
        with tempfile.TemporaryDirectory() as dossier, patch.dict(
                "os.environ", {"APP_TICKET_ENFORCED": "0"}):
            # Préparer les fichiers attendus par les trois boutons de téléchargement.
            for nom, colonnes in (("resultats", COLONNES_RESULTATS),
                                  ("intervalles", COLONNES_INTERVALLES),
                                  ("detections", COLONNES_DETECTIONS)):
                fichier, _ = ouvrir_csv(Path(dossier) / f"{nom}.csv", colonnes)
                fichier.close()
            for resultats in ([resultat, erreur], [erreur]):
                with self.subTest(videos=len(resultats)):
                    application = AppTest.from_file(
                        str(Path(__file__).resolve().parents[1] / "app.py"))
                    application.session_state["visiotrack_exports"] = SimpleNamespace(name=dossier)
                    application.session_state["visiotrack_resultats"] = resultats
                    application.run(timeout=20)
                    self.assertEqual(len(application.exception), 0)
                    tableau = application.dataframe[0].value
                    self.assertEqual(list(tableau.video_id), [r["video_id"] for r in resultats])
                    if len(resultats) == 2:
                        self.assertEqual(tableau.iloc[0].pourcentage_visible, 25.0)
                    self.assertEqual(len(application.table[0].value), len(COLONNES_RESULTATS))
                    self.assertEqual(len(application.get("download_button")), 3)


if __name__ == "__main__":
    unittest.main()
