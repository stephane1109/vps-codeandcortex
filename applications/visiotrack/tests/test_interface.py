"""Vérifier l'affichage réel des résultats et leur sérialisation par PyArrow."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import streamlit as st
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

    def test_chronologie_par_objet_et_temps_en_abscisse(self):
        """Tracer les apparitions séparées et leur durée, jamais un total sur l'axe temporel."""
        import pandas as pd
        script = """
import pandas as pd
import streamlit as st
from pathlib import Path
from app import afficher_graphiques
identifiant = afficher_graphiques(pd.DataFrame(st.session_state.lignes), st.session_state.choix,
                                  Path(st.session_state.dossier))
"""
        lignes = [
            {"video_id": "v1", "source": "meme.mp4", "categorie": "smartphone", "statut": "ok",
             "duree_totale_s": 4},
            {"video_id": "v2", "source": "meme.mp4", "categorie": "smartphone", "statut": "ok",
             "duree_totale_s": 10},
            {"video_id": "erreur", "source": "illisible.mp4", "statut": "erreur"},
        ]
        with tempfile.TemporaryDirectory() as dossier:
            pd.DataFrame([
                {"video_id": "v1", "categorie": "smartphone", "objet_id": "67-1",
                 "debut_s": 0, "fin_s": 1, "duree_s": 1},
                {"video_id": "v1", "categorie": "smartphone", "objet_id": "67-1",
                 "debut_s": 2, "fin_s": 3.5, "duree_s": 1.5},
                {"video_id": "v1", "categorie": "smartphone", "objet_id": "67-2",
                 "debut_s": 0.5, "fin_s": 2, "duree_s": 1.5},
            ]).to_csv(Path(dossier) / "visibilite_objets.csv", index=False)
            pd.DataFrame([
                {"video_id": video, "horodatage_s": instant, "categorie": "smartphone",
                 "nombre_visible": visibles, "nombre_distincts_cumule": cumul}
                for video, instant, visibles, cumul in [("v1", 0, 1, 1), ("v1", 1, 2, 2),
                                                       ("v1", 2, 0, 2), ("v1", 4, 0, 2),
                                                       ("v2", 0, 0, 0), ("v2", 10, 0, 0)]
            ]).to_csv(Path(dossier) / "chronologie.csv", index=False)
            for temps, distincts in ((True, True), (True, False), (False, True)):
                with self.subTest(temps=temps, distincts=distincts), \
                        patch.object(st, "vega_lite_chart", wraps=st.vega_lite_chart) as graphique:
                    application = AppTest.from_string(script)
                    application.session_state["lignes"] = lignes
                    application.session_state["dossier"] = dossier
                    application.session_state["choix"] = {"quantifier_temps": temps, "compter_distincts": distincts}
                    application.run()
                    self.assertEqual(len(application.exception), 0)
                    self.assertEqual(graphique.call_count, int(temps) + int(distincts))
                    self.assertEqual(application.selectbox[0].options, ["v1 — meme.mp4", "v2 — meme.mp4"])
                    for appel in graphique.call_args_list:
                        donnees, specification = appel.args
                        encodage = specification["encoding"]
                        self.assertEqual(encodage["x"]["scale"]["domain"], [0, 4])
                        self.assertEqual(set(donnees.video_id), {"v1"})
                        if specification["mark"]["type"] == "bar":
                            self.assertEqual(encodage["x"]["field"], "debut_s")
                            self.assertEqual(encodage["x2"]["field"], "fin_s")
                            self.assertEqual(len(donnees), 3)
                            objet1 = donnees[donnees.objet_id == "67-1"]
                            self.assertEqual(list(objet1.debut_s), [0, 2])
                            self.assertEqual(list(objet1.fin_s), [1, 3.5])
                            self.assertEqual(set(objet1.duree_objet_s), {2.5})
                        else:
                            self.assertEqual(encodage["x"]["field"], "horodatage_s")
                            self.assertEqual(specification["mark"]["interpolate"], "step-after")
                            self.assertEqual(list(donnees.nombre_distincts_cumule), [1, 2, 2, 2])
                    graphique.reset_mock()
                    application.selectbox[0].select("v2").run()
                    self.assertEqual(len(application.exception), 0)
                    self.assertEqual(graphique.call_count, int(distincts))
                    if distincts:
                        self.assertEqual(set(graphique.call_args.args[0].nombre_distincts_cumule), {0})
                    graphique.reset_mock()
                    application.session_state["lignes"] = [lignes[-1]]
                    application.run()
                    self.assertEqual(len(application.exception), 0)
                    graphique.assert_not_called()


if __name__ == "__main__":
    unittest.main()
