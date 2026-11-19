"""Vérification du quadriptyque sans télécharger de vidéos ni charger YOLO."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from montage import annoter_video, assembler_quatre_videos, assembler_videos, creer_montage
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

    def test_split_deux_et_trois_ecrans(self):
        """Vérifier les deux dispositions horizontales en 1920 × 1080."""
        import json

        for nombre in (2, 3):
            with self.subTest(nombre=nombre):
                sources = [
                    self.creer_video(
                        f"split_{nombre}_{indice}.mp4",
                        ("red", "green", "blue")[indice],
                        (0.6, 1.0, 1.4)[indice],
                    )
                    for indice in range(nombre)
                ]
                sortie = self.dossier / f"split_{nombre}.mp4"
                duree = assembler_videos(sources, sortie)
                duree_reelle, _ = lire_metadonnees(sortie)
                self.assertAlmostEqual(duree, duree_reelle, delta=0.1)
                controle = subprocess.run(
                    [
                        "ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height", "-of", "json", str(sortie),
                    ],
                    capture_output=True, text=True, check=True,
                )
                pistes = json.loads(controle.stdout)["streams"]
                self.assertEqual(len(pistes), 1)
                self.assertEqual(pistes[0]["codec_type"], "video")
                self.assertEqual(
                    (pistes[0]["width"], pistes[0]["height"]), (1920, 1080)
                )

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


    def test_analyse_sans_split_avec_deux_urls(self):
        """Les deux URL sont analysées sans assembler leurs vidéos."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            urls = [
                "https://www.youtube.com/watch?v=video1",
                "",
                "https://www.youtube.com/watch?v=video3",
                "",
            ]
            appels = []

            def simuler_analyse(chemin, video_id, nom, categories, frequence,
                               modele, repertoire, progression, **options):
                appels.append(nom)
                progression(1.0)
                return [{
                    "video_id": video_id, "source": nom, "statut": "ok",
                    "categorie": "smartphone", "duree_totale_s": 1.0,
                }]

            def simuler_video(chemin, observations, destination, duree,
                             progression, **options):
                Path(destination).write_bytes(b"video annotee")
                progression(1.0)

            with (
                patch("montage.charger_modele", return_value=object()),
                patch("montage.preparer_video", return_value=racine / "source.mp4"),
                patch("montage.analyser_video", side_effect=simuler_analyse),
                patch("montage.creer_video_annotee", side_effect=simuler_video),
                patch("montage.assembler_videos") as assemblage,
            ):
                sortie, duree = creer_montage(
                    urls, racine, generer_split=False, categorie=67
                )

            self.assertIsNone(sortie)
            self.assertIsNone(duree)
            self.assertEqual(appels, [urls[0], urls[2]])
            self.assertTrue((racine / "case_1.mp4").is_file())
            self.assertTrue((racine / "case_2.mp4").is_file())
            self.assertFalse((racine / "case_3.mp4").exists())
            assemblage.assert_not_called()

    def test_reutilisation_une_url_sans_second_telechargement(self):
        """Une analyse précédente évite l'accès au réseau pour l'URL déjà traitée."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            urls = [f"https://www.youtube.com/watch?v=video{i}" for i in range(1, 5)]
            precedent = racine / "apercu_initial.mp4"
            chronologie = racine / "chronologie.csv"
            precedent.write_bytes(b"apercu YOLO deja calcule")
            chronologie.write_text(
                "video_id,horodatage_s,categorie,nombre_visible,nombre_distincts_cumule\n"
                "v000008,0.0,smartphone,1,1\n",
                encoding="utf-8"
            )
            existants = {
                urls[0]: {
                    "apercu": str(precedent),
                    "chronologie": str(chronologie),
                    "video_id": "v000008",
                    "resultat": {
                        "video_id": "v000008", "source": urls[0], "statut": "ok",
                        "categorie": "smartphone", "duree_totale_s": 2.0,
                        "images_analysees": 2, "frequence_demandee_ips": 1.0,
                    },
                }
            }
            telechargements = []
            analyses = []

            def simuler_reprise(chemin_apercu, chemin_chronologie, identifiant,
                               categorie, destination, progression):
                Path(destination).write_bytes(b"apercu reutilise")
                progression(1.0)

            def simuler_telechargement(source, repertoire):
                telechargements.append(source.contenu)
                return racine / "source.mp4"

            def simuler_analyse(chemin, video_id, nom, categories, frequence,
                               modele, repertoire, progression, **options):
                analyses.append(nom)
                progression(1.0)
                return [{
                    "video_id": video_id, "source": nom, "statut": "ok",
                    "categorie": "smartphone", "duree_totale_s": 2.0,
                }]

            def simuler_apercu(chemin, observations, destination, duree,
                              progression, **options):
                Path(destination).write_bytes(b"annotation neuve")
                progression(1.0)

            def simuler_assemblage(chemins, sortie):
                self.assertEqual(len(chemins), 4)
                Path(sortie).write_bytes(b"montage")
                return 2.0

            with (
                patch("montage.reutiliser_apercu_analyse", side_effect=simuler_reprise),
                patch("montage.preparer_video", side_effect=simuler_telechargement),
                patch("montage.charger_modele", return_value=object()),
                patch("montage.analyser_video", side_effect=simuler_analyse),
                patch("montage.creer_video_annotee", side_effect=simuler_apercu),
                patch("montage.assembler_quatre_videos", side_effect=simuler_assemblage),
            ):
                sortie, duree = creer_montage(
                    urls, racine, categorie=67, reutilisations=existants
                )

            self.assertTrue(sortie.is_file())
            self.assertEqual(duree, 2.0)
            self.assertEqual(telechargements, urls[1:])
            self.assertEqual(analyses, urls[1:])
            fichier_csv = (racine / "visiotrack_montage_resultats.csv").read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("v000001", fichier_csv)
            self.assertIn("v000004", fichier_csv)



if __name__ == "__main__":
    unittest.main()
