"""Vérifier l'affichage réel des résultats et leur sérialisation par PyArrow."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from detection import (COLONNES_DETECTIONS, COLONNES_INTERVALLES,
                       COLONNES_RESULTATS, colonnes_resultats, ouvrir_csv)


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
                    self.assertEqual(len(application.table[0].value), len(colonnes_resultats()))
                    self.assertEqual(len(application.get("download_button")), 3)

    def test_choix_mesures_transmis_et_resultats_figes(self):
        """Le formulaire transmet les cases et conserve les choix du lot affiché."""
        def simuler_lot(sources, categories, frequence, dossier, progression, **choix):
            for nom, colonnes in (("resultats", colonnes_resultats(**choix)),
                                  ("intervalles", COLONNES_INTERVALLES),
                                  ("detections", COLONNES_DETECTIONS)):
                fichier, _ = ouvrir_csv(Path(dossier) / f"{nom}.csv", colonnes)
                fichier.close()
            return [{"video_id": "v1", "source": "test", "statut": "ok", "erreur": "",
                     "categorie": "smartphone", "duree_totale_s": 10, "objet_detecte": True,
                     "maximum_simultane": 1, "nombre_objets_distincts_estime": 2,
                     "frequence_demandee_ips": 1, "images_analysees": 10}]

        with patch.dict("os.environ", {"APP_TICKET_ENFORCED": "0"}), \
                patch("detection.traiter_lot", side_effect=simuler_lot) as traiter:
            application = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
            application.text_area[0].input("https://www.tiktok.com/@test/video/123")
            application.checkbox[0].uncheck()
            application.checkbox[1].check()
            next(b for b in application.button if b.label == "Lancer l'analyse").click().run()
            self.assertEqual(len(application.exception), 0)
            self.assertFalse(traiter.call_args.kwargs["quantifier_temps"])
            self.assertTrue(traiter.call_args.kwargs["compter_distincts"])
            self.assertNotIn("duree_visibilite_s", application.dataframe[0].value.columns)
            self.assertEqual(application.dataframe[0].value.iloc[0].nombre_objets_distincts_estime, 2)
            self.assertEqual(len(application.get("download_button")), 2)
            application.checkbox[0].check()
            application.checkbox[1].uncheck()
            application.run()
            self.assertNotIn("duree_visibilite_s", application.dataframe[0].value.columns)
            application.session_state["visiotrack_exports"].cleanup()

    def test_aucune_case_cochee_ne_lance_pas_analyse(self):
        with patch.dict("os.environ", {"APP_TICKET_ENFORCED": "0"}), \
                patch("detection.traiter_lot") as traiter:
            application = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
            for case in application.checkbox:
                case.uncheck()
            next(b for b in application.button if b.label == "Lancer l'analyse").click().run()
            self.assertEqual(application.error[0].value, "Cochez au moins une mesure à quantifier.")
            traiter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
