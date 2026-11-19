"""Vérification du quadriptyque sans télécharger de vidéos ni charger YOLO."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from montage import annoter_video, assembler_quatre_videos, creer_montage
from detection import lire_metadonnees


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/ffprobe ne sont pas disponibles.")
class TestMontageComparatif(unittest.TestCase):
    """Contrôler le format, le gel de l'image et l'annotation."""

    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temporaire.name)

    def tearDown(self):
        self.temporaire.cleanup()

    def creer_video(self, nom, couleur, duree):
        """Créer une vidéo muette de test à cadence et dimensions fixes."""
        chemin = self.dossier / nom
        subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
            "-i", f"color=c={couleur}:s=960x540:r=15",
            "-t", str(duree), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(chemin),
        ], capture_output=True, check=True)
        return chemin

    @patch("montage.extraire_telephones", return_value=[(40, 60, 110, 140)])
    def test_annotations_sans_modele_reel(self, detection):
        """Les cadres et les compteurs sont rendus dans une case 960 × 540."""
        import cv2

        source = self.creer_video("source.mp4", "red", 0.6)
        sortie = self.dossier / "annotee.mp4"
        annoter_video(source, sortie, object(), frequence=5.0)
        capture = cv2.VideoCapture(str(sortie))
        lu, image = capture.read()
        capture.release()
        self.assertTrue(lu)
        self.assertEqual(image.shape[:2], (540, 960))
        self.assertGreater(detection.call_count, 0)
        # La bordure jaune du rectangle doit être distincte de la source rouge.
        self.assertGreater(int(image[60, 70, 1]), 100)

    def test_quadriptyque_prolonge_videos_courtes(self):
        """Le montage dure autant que la plus longue piste et reste muet."""
        sources = [
            self.creer_video(f"source_{i}.mp4", couleur, duree)
            for i, (couleur, duree) in enumerate([
                ("red", 0.6), ("green", 0.8), ("blue", 1.0), ("yellow", 1.4)
            ])
        ]
        sortie = self.dossier / "montage.mp4"
        duree = assembler_quatre_videos(sources, sortie)
        duree_reelle, _ = lire_metadonnees(sortie)
        self.assertAlmostEqual(duree, duree_reelle, delta=0.1)
        self.assertGreaterEqual(duree_reelle, 1.3)
        verification = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,width,height", "-of", "json", str(sortie),
        ], capture_output=True, text=True, check=True)
        import json
        pistes = json.loads(verification.stdout)["streams"]
        self.assertEqual(len(pistes), 1)
        self.assertEqual(pistes[0]["codec_type"], "video")
        self.assertEqual((pistes[0]["width"], pistes[0]["height"]), (1920, 1080))


class TestAnalyseQuatreUrls(unittest.TestCase):
    """Vérifier que quatre analyses complètes précèdent le lecteur comparatif."""

    def test_quatre_urls_sont_analysees_et_mesurees(self):
        """Chaque entrée doit appeler le moteur YOLO avec la catégorie retenue."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            urls = [f"https://www.youtube.com/watch?v=video{i}" for i in range(1, 5)]
            appels_analyses = []
            appels_apercus = []

            def simuler_analyse(chemin, video_id, nom, categories, frequence,
                               modele, repertoire, progression, **options):
                appels_analyses.append((video_id, nom, list(categories), frequence, options))
                (Path(repertoire) / "observations.jsonl").write_text("", encoding="utf-8")
                progression(1.0)
                return [{
                    "video_id": video_id, "source": nom, "statut": "ok",
                    "duree_totale_s": 1.0, "categorie": "smartphone",
                    "maximum_simultane": 1, "objet_detecte": True,
                    "nombre_objets_distincts_estime": 1, "images_analysees": 5,
                    "frequence_demandee_ips": frequence, "duree_visibilite_s": 0.5,
                    "pourcentage_visible": 50.0,
                }]

            def simuler_apercu(chemin, observations, destination, duree,
                              progression, **options):
                appels_apercus.append(options)
                Path(destination).write_bytes(b"video annotee")
                progression(1.0)

            def simuler_assemblage(chemins, sortie):
                self.assertEqual(len(chemins), 4)
                Path(sortie).write_bytes(b"video finale")
                return 1.0

            with (
                patch("montage.charger_modele", return_value=object()),
                patch("montage.preparer_video", return_value=racine / "source.mp4"),
                patch("montage.analyser_video", side_effect=simuler_analyse),
                patch("montage.creer_video_annotee", side_effect=simuler_apercu),
                patch("montage.assembler_quatre_videos", side_effect=simuler_assemblage),
            ):
                sortie, duree = creer_montage(urls, racine, 5.0, categorie=67)

            self.assertTrue(sortie.is_file())
            self.assertEqual(duree, 1.0)
            self.assertEqual(len(appels_analyses), 4)
            self.assertEqual([x[0] for x in appels_analyses],
                             ["v000001", "v000002", "v000003", "v000004"])
            for identifiant, nom, categories, frequence, options in appels_analyses:
                self.assertEqual(categories, [67])
                self.assertEqual(frequence, 5.0)
                self.assertTrue(options["quantifier_temps"])
                self.assertTrue(options["compter_distincts"])
            self.assertEqual(len(appels_apercus), 4)
            self.assertTrue(all(x["categories_compteur"] == [67] for x in appels_apercus))
            csv = (racine / "visiotrack_montage_resultats.csv").read_text(encoding="utf-8-sig")
            self.assertEqual(csv.count("v00000"), 4)



if __name__ == "__main__":
    unittest.main()
