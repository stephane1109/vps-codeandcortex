"""Vérifier l'intégration des quatre URL au module historique de VisioTrack."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import generer_split_analyses


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


if __name__ == "__main__":
    unittest.main()
