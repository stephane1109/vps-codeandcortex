"""Vérifications des mesures, du suivi et de la poursuite des lots après erreur."""

import csv
import io
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from detection import (MesureVisibilite, SourceVideo, analyser_video, creer_suivis,
                       detecter_image, inventorier_sources, preparer_video,
                       texte_csv, traiter_lot, verifier_url)


def fabriquer_video(chemin, nombre=25, fps=10):
    """Créer une petite vidéo déterministe sans téléchargement ni modèle."""
    sortie = cv2.VideoWriter(str(chemin), cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 64))
    if not sortie.isOpened():
        raise RuntimeError("Encodeur MP4 indisponible pour les tests.")
    for indice in range(nombre):
        sortie.write(np.full((64, 64, 3), indice, dtype=np.uint8))
    sortie.release()


def detection_telephone(piste=1):
    """Représenter un smartphone observé avec son identifiant de suivi."""
    return {"categorie_id": 67, "piste_id": piste, "confiance": 0.9,
            "x1": 1, "y1": 1, "x2": 10, "y2": 20}


class TestsVisibilite(unittest.TestCase):
    """Couvrir les règles métier qui peuvent fausser les durées."""

    def test_union_et_absence(self):
        intervalles = []
        mesure = MesureVisibilite([67, 0], intervalles.append)
        mesure.ajouter(0, 1, {67: 2})
        mesure.ajouter(1, 2, {67: 1, 0: 3})
        mesure.ajouter(2, 3, {})
        mesure.ajouter(3, 3.25, {67: 1})
        mesure.terminer()
        self.assertEqual(mesure.durees[67], 2.25)
        self.assertEqual(mesure.maximums[67], 2)
        self.assertEqual(mesure.durees[0], 1)
        self.assertEqual([(i["debut_s"], i["fin_s"]) for i in intervalles
                          if i["categorie"] == "smartphone"], [(0, 2), (3, 3.25)])

    def test_video_et_derniere_fraction(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "court.mp4"
            fabriquer_video(chemin)
            observations = [[detection_telephone(1), detection_telephone(2)], [],
                            [detection_telephone(3)]]
            with patch("detection.detecter_image", side_effect=observations):
                resultat = analyser_video(chemin, "v1", "court.mp4", [67, 0], 1, None, dossier)
            self.assertAlmostEqual(resultat[0]["duree_totale_s"], 2.5)
            self.assertAlmostEqual(resultat[0]["duree_visibilite_s"], 1.5)
            self.assertAlmostEqual(resultat[0]["pourcentage_visible"], 60)
            self.assertEqual(resultat[0]["maximum_simultane"], 2)
            self.assertEqual(resultat[1]["duree_visibilite_s"], 0)
            with (Path(dossier) / "detections.csv").open(encoding="utf-8-sig") as fichier:
                self.assertEqual([float(l["horodatage_s"]) for l in csv.DictReader(fichier)], [0, 0, 2])

    def test_frequence_superieure_au_media(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "court.mp4"
            fabriquer_video(chemin, nombre=3, fps=5)
            with patch("detection.detecter_image", side_effect=lambda *args: [detection_telephone()]):
                resultat = analyser_video(chemin, "v1", "court", [67], 30, None, dossier)[0]
            self.assertEqual(resultat["images_analysees"], 3)
            self.assertAlmostEqual(resultat["duree_visibilite_s"], 0.6)
            self.assertAlmostEqual(resultat["pourcentage_visible"], 100)

    def test_suivi_reel_et_nouvelles_detections(self):
        from ultralytics.engine.results import Results

        image = np.zeros((64, 64, 3), dtype=np.uint8)

        class ModeleSimule:
            """Isoler ByteTrack du réseau neuronal pour un scénario reproductible."""

            boites = np.empty((0, 6), dtype=np.float32)

            def predict(self, *args, **kwargs):
                return [Results(image, "test", {67: "cell phone"}, boxes=self.boites)]

        modele = ModeleSimule()
        suivis = creer_suivis([67], 1)
        self.assertEqual(detecter_image(modele, suivis, image, [67]), [])
        modele.boites = np.array([[1, 1, 10, 20, 0.9, 67]], dtype=np.float32)
        premiere = detecter_image(modele, suivis, image, [67])
        self.assertEqual(len(premiere), 1)  # La nouvelle piste n'est pas encore confirmée.
        self.assertEqual(premiere[0]["piste_id"], "")
        seconde = detecter_image(modele, suivis, image, [67])
        self.assertIsInstance(seconde[0]["piste_id"], int)
        modele.boites = np.empty((0, 6), dtype=np.float32)
        self.assertEqual(detecter_image(modele, suivis, image, [67]), [])
        self.assertEqual(creer_suivis([67], 1)[67].frame_id, 0)

    def test_cadence_variable(self):
        with tempfile.TemporaryDirectory() as dossier:
            original = Path(dossier) / "original.mp4"
            variable = Path(dossier) / "variable.mp4"
            fabriquer_video(original)
            subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(original), "-vf",
                "select='eq(n,0)+eq(n,7)+eq(n,14)+eq(n,21)+eq(n,24)'",
                "-fps_mode", "vfr", "-c:v", "libx264", str(variable),
            ], check=True, capture_output=True)
            with patch("detection.detecter_image", side_effect=[
                    [detection_telephone()], [], [detection_telephone()]]):
                resultat = analyser_video(variable, "v1", "variable", [67], 1, None, dossier)[0]
            self.assertAlmostEqual(resultat["duree_totale_s"], 2.5)
            self.assertAlmostEqual(resultat["duree_visibilite_s"], 1.8)
            with (Path(dossier) / "detections.csv").open(encoding="utf-8-sig") as fichier:
                self.assertEqual([float(l["horodatage_s"]) for l in csv.DictReader(fichier)], [0, 2.1])

    def test_erreur_apres_detections_exclut_exports_partiels(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "court.mp4"
            fabriquer_video(chemin)
            with patch("detection.charger_modele", return_value=None), \
                    patch("detection.detecter_image", side_effect=[
                        [detection_telephone()], RuntimeError("Image invalide")]):
                resultat = traiter_lot([SourceVideo("court", "serveur", chemin)], [67], 1, dossier)
            self.assertEqual(resultat[0]["statut"], "erreur")
            for nom in ("intervalles", "detections"):
                with (Path(dossier) / f"{nom}.csv").open(encoding="utf-8-sig") as fichier:
                    self.assertEqual(list(csv.DictReader(fichier)), [])

    def test_archive_et_identifiants(self):
        archive = io.BytesIO()
        archive.name = "lot.zip"
        with zipfile.ZipFile(archive, "w") as sortie:
            sortie.writestr("../../test.mp4", b"video")
            sortie.writestr("sous-dossier/test.mp4", b"autre")
            sortie.writestr("notes.txt", "ignoré")
        sources = inventorier_sources([archive], "https://youtu.be/abc\nhttps://youtu.be/abc")
        self.assertEqual(len(sources), 3)
        with tempfile.TemporaryDirectory() as dossier:
            cible = preparer_video(sources[0], dossier)
            self.assertEqual(cible.parent, Path(dossier))
            self.assertEqual(cible.read_bytes(), b"video")

    def test_lot_continue_et_exports_coherents(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "court.mp4"
            fabriquer_video(chemin, nombre=3)
            sources = [SourceVideo("invalide", "erreur", None, erreur="Erreur attendue"),
                       SourceVideo("court", "serveur", chemin)]
            with patch("detection.charger_modele", return_value=None), \
                    patch("detection.detecter_image", side_effect=lambda *args: [detection_telephone()]):
                resultats = traiter_lot(sources, [67], 1, dossier)
            self.assertEqual([r["statut"] for r in resultats], ["erreur", "ok"])
            with (Path(dossier) / "intervalles.csv").open(encoding="utf-8-sig") as fichier:
                lignes = list(csv.DictReader(fichier))
            self.assertEqual(len(lignes), 1)
            self.assertEqual(lignes[0]["video_id"], "v000002")

    def test_sources_non_valides(self):
        for url in ("http://youtube.com/watch?v=x", "https://youtube.com.evil.test/x",
                    "https://localhost/x", "https://user:pass@youtu.be/x"):
            with self.assertRaises(ValueError):
                verifier_url(url)
        verifier_url("https://www.youtube.com/watch?v=x")
        verifier_url("https://vm.tiktok.com/abc/")
        self.assertEqual(texte_csv("=1+1"), "'=1+1")

    def test_url_refuse_direct_avant_telechargement(self):
        with tempfile.TemporaryDirectory() as dossier, patch("yt_dlp.YoutubeDL") as outil:
            client = outil.return_value.__enter__.return_value
            client.extract_info.return_value = {"is_live": True}
            with self.assertRaises(ValueError):
                preparer_video(SourceVideo("direct", "url", "https://youtu.be/abc"), dossier)
            client.extract_info.assert_called_once_with("https://youtu.be/abc", download=False)
            client.process_ie_result.assert_not_called()

    def test_url_prepare_fichier_video(self):
        with tempfile.TemporaryDirectory() as dossier, patch("yt_dlp.YoutubeDL") as outil:
            client = outil.return_value.__enter__.return_value
            client.extract_info.return_value = {"id": "abc", "is_live": False}
            cible = Path(dossier) / "video.mp4"
            cible.write_bytes(b"video")
            client.prepare_filename.return_value = str(cible)
            self.assertEqual(preparer_video(
                SourceVideo("test", "url", "https://youtu.be/abc"), dossier), cible)
            client.process_ie_result.assert_called_once_with(
                {"id": "abc", "is_live": False}, download=True)


if __name__ == "__main__":
    unittest.main()
