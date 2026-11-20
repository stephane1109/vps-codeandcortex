"""Vérifier l'intégration des quatre URL au module historique de VisioTrack."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import (associer_identifiants_urls, etablir_bilan_urls,
                 generer_split_analyses, preparer_urls_saisies)
from detection import inventorier_sources


class TestSplitAnalysePrincipale(unittest.TestCase):
    """Contrôler la composition des aperçus sans nouveau téléchargement."""

    def test_deux_trois_quatre_apercus_existants(self):
        """Assembler les vidéos existantes pour chaque nombre d'URL possible."""
        for nombre in (2, 3, 4):
            with self.subTest(nombre=nombre):
                with tempfile.TemporaryDirectory() as temporaire:
                    racine = Path(temporaire)
                    manifeste = {}
                    resultats = []
                    urls = []
                    for indice in range(1, nombre + 1):
                        adresse = f"https://www.youtube.com/watch?v=test{indice}"
                        identifiant = f"v{indice:06d}"
                        relatif = f"apercus/{identifiant}.mp4"
                        chemin = racine / relatif
                        chemin.parent.mkdir(parents=True, exist_ok=True)
                        chemin.write_bytes(b"simulation video")
                        urls.append(adresse)
                        manifeste[identifiant] = {"fichier": relatif}
                        resultats.append({
                            "source": adresse,
                            "video_id": identifiant,
                            "statut": "ok",
                            "categorie": "smartphone",
                        })
                    (racine / "apercus.json").write_text(
                        json.dumps(manifeste), encoding="utf-8"
                    )

                    def simuler_assemblage(chemins, destination):
                        """Créer un fichier de sortie sans décoder de vidéos."""
                        self.assertEqual(len(chemins), nombre)
                        self.assertTrue(all(chemin.is_file() for chemin in chemins))
                        Path(destination).write_bytes(b"simulation split")
                        return 1.5

                    with patch("app.assembler_videos", side_effect=simuler_assemblage):
                        destination, duree = generer_split_analyses(
                            racine, resultats, urls
                        )
                    self.assertTrue(destination.is_file())
                    self.assertEqual(
                        destination.name, f"visiotrack_montage_{nombre}_fenetres.mp4"
                    )
                    self.assertEqual(duree, 1.5)

    def test_refuser_un_split_apres_echec_d_analyse(self):
        """Ne jamais substituer une vidéo vide à un échec YOLO."""
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            (racine / "apercus.json").write_text("{}", encoding="utf-8")
            urls = [
                "https://www.youtube.com/watch?v=bonne",
                "https://www.youtube.com/watch?v=erreur",
            ]
            resultats = [
                {"source": urls[0], "video_id": "v000001", "statut": "ok"},
                {"source": urls[1], "video_id": "v000002", "statut": "erreur"},
            ]
            with self.assertRaisesRegex(ValueError, "URL 1"):
                generer_split_analyses(racine, resultats, urls)


class TestCorrespondanceIdentifiants(unittest.TestCase):
    """Prouver que les deux URL sont bien suivies, même si l'une échoue."""

    def test_mapping_par_id_avec_fichier_ajoute(self):
        """Les fichiers importés peuvent décaler les identifiants v000001, etc."""
        from detection import SourceVideo

        adresses = [
            "https://www.youtube.com/watch?v=premiere",
            "https://www.youtube.com/watch?v=seconde",
        ]
        sources = [
            SourceVideo("manuel.mp4", "fichier", object()),
            SourceVideo(adresses[0], "url", adresses[0]),
            SourceVideo(adresses[1], "url", adresses[1]),
        ]
        self.assertEqual(
            associer_identifiants_urls(sources, adresses),
            {adresses[0]: "v000002", adresses[1]: "v000003"},
        )

    def test_echec_url_1_explique_sans_masquer_url_2(self):
        """Une erreur HTTP de l'URL 1 ne doit jamais masquer l'URL 2 analysée."""
        adresses = [
            "https://www.youtube.com/watch?v=premiere",
            "https://www.youtube.com/watch?v=seconde",
        ]
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            chemin = racine / "apercus" / "v000002.mp4"
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(b"simulation")
            (racine / "apercus.json").write_text(
                json.dumps({"v000002": {"fichier": "apercus/v000002.mp4"}}),
                encoding="utf-8",
            )
            resultats = [
                {
                    "video_id": "v000001", "statut": "erreur",
                    "source": adresses[0], "erreur": "HTTP Error 403: Forbidden",
                },
                {
                    "video_id": "v000002", "statut": "ok",
                    "source": adresses[1], "categorie": "smartphone",
                },
            ]
            correspondances = {
                adresses[0]: "v000001", adresses[1]: "v000002",
            }
            bilans = etablir_bilan_urls(
                racine, resultats, adresses, correspondances
            )
            self.assertEqual([b["statut"] for b in bilans], ["Erreur", "Prête"])
            self.assertIn("403", bilans[0]["detail"])
            self.assertEqual(bilans[1]["video_id"], "v000002")
            self.assertTrue(bilans[1]["chemin"].is_file())
            with self.assertRaisesRegex(ValueError, "URL 1.*403"):
                generer_split_analyses(
                    racine, resultats, adresses, correspondances
                )

    def test_split_deux_urls_associees_sans_dependre_du_nom_resultat(self):
        """Les identifiants de la collecte priment sur une chaîne URL modifiée."""
        adresses = [
            "https://www.youtube.com/watch?v=premiere",
            "https://www.youtube.com/watch?v=seconde",
        ]
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            apercus = {}
            resultats = []
            for indice in range(2):
                video_id = f"v{indice + 2:06d}"
                relatif = f"apercus/{video_id}.mp4"
                chemin = racine / relatif
                chemin.parent.mkdir(parents=True, exist_ok=True)
                chemin.write_bytes(b"simulation")
                apercus[video_id] = {"fichier": relatif}
                resultats.append({
                    "video_id": video_id, "statut": "ok",
                    "source": f"nom public {indice + 1}",
                    "categorie": "smartphone",
                })
            (racine / "apercus.json").write_text(
                json.dumps(apercus), encoding="utf-8"
            )
            correspondances = {
                adresses[0]: "v000002", adresses[1]: "v000003",
            }

            def assembler_sans_decoder(chemins, destination):
                """S'assurer que les deux vidéos annotées sont utilisées."""
                self.assertEqual(len(chemins), 2)
                self.assertEqual([p.name for p in chemins],
                                 ["v000002.mp4", "v000003.mp4"])
                destination.write_bytes(b"montage")
                return 3.0

            with patch("app.assembler_videos", side_effect=assembler_sans_decoder):
                destination, duree = generer_split_analyses(
                    racine, resultats, adresses, correspondances
                )
            self.assertTrue(destination.is_file())
            self.assertEqual(duree, 3.0)


class TestChampsUrl(unittest.TestCase):
    """Vérifier que les quatre champs alimentent une analyse unique."""

    def test_deux_url_split_avec_deux_champs_vides(self):
        """URL 1 et URL 2 suffisent, sans ancien champ principal."""
        url_1 = "https://www.youtube.com/watch?v=video1"
        url_2 = "https://www.youtube.com/watch?v=video2"
        adresses = preparer_urls_saisies([url_1, url_2, "", ""])
        self.assertEqual(len(adresses), 2)
        self.assertIn(len(adresses), (2, 3, 4))
        sources = inventorier_sources([], "\n".join(adresses))
        self.assertEqual(len(sources), 2)
        self.assertEqual([source.contenu for source in sources], [url_1, url_2])

    def test_les_champs_non_consecutifs_sont_acceptes(self):
        """URL 1 et URL 4 doivent suffire pour deux fenêtres."""
        adresses = preparer_urls_saisies([
            "  https://www.youtube.com/watch?v=video1  ",
            "",
            "",
            "https://www.youtube.com/watch?v=video4",
        ])
        self.assertEqual(len(adresses), 2)
        self.assertEqual(adresses[0], "https://www.youtube.com/watch?v=video1")
        self.assertEqual(adresses[1], "https://www.youtube.com/watch?v=video4")

    def test_url_unique_et_doublons(self):
        """Une seule URL est analysable ; les répétitions sont ignorées."""
        url = "https://www.youtube.com/watch?v=video1"
        self.assertEqual(preparer_urls_saisies([url, "", "", ""]), [url])
        self.assertEqual(preparer_urls_saisies([url, "", url, ""]), [url])
        self.assertEqual(preparer_urls_saisies(["", "", "", ""]), [])



if __name__ == "__main__":
    unittest.main()
