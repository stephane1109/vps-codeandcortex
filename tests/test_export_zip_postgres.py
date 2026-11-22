"""Vérifier l'archive unique et la priorité de la route PostgreSQL."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from stockage.export_zip_postgres import construire_archive_postgres


class CurseurFictif:
    """Simuler l'identité et les paramètres d'une collecte."""
    def __init__(self, nom, parametres=None):
        self.nom = nom
        self.parametres = parametres or {}
        self.instructions = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, instruction, valeurs):
        self.instructions.append((instruction, valeurs))

    def fetchone(self):
        if not self.nom:
            return None
        if "parametres" in self.instructions[-1][0]:
            return self.nom, self.parametres
        return (self.nom,)


class ConnexionFictive:
    def __init__(self, nom, parametres=None):
        self.curseur = CurseurFictif(nom, parametres)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def cursor(self):
        return self.curseur


PUBLICATION = {
    "id": "7702544004629531937",
    "url": "https://www.tiktok.com/@exemple/video/7702544004629531937",
    "author": "exemple",
    "description": "Une manifestation lycéenne",
    "retenue": True,
    "engagement": {
        "vues": {"valeur": 219, "brut": "219"},
        "likes": {"valeur": 5, "brut": "5"},
    },
}
COMMENTAIRE = {
    "id": "1234567890",
    "publication_id": "7702544004629531937",
    "auteur": "utilisateur",
    "texte": "Un commentaire",
}


def faux_exporter(cookie, type_, identifiant, categorie, format_):
    if format_ == "json":
        yield json.dumps(
            [PUBLICATION] if categorie == "publications" else [COMMENTAIRE],
            ensure_ascii=False)
    else:
        yield "\ufeffid;vues\n7702544004629531937;219\n"


def fausses_lignes(cookie, type_, identifiant, categorie):
    return [PUBLICATION] if categorie == "publications" else [COMMENTAIRE]


class TestsExportPostgresZip(unittest.TestCase):
    def _generer(self, *args, **kwargs):
        """Simuler la génération pour isoler le test du regroupement ZIP."""
        dossier = Path(args[0])
        (dossier / "engagement.csv").write_text(
            "publication_id;vues\n7702544004629531937;219\n",
            encoding="utf-8")
        (dossier / "textes.txt").write_text(
            "Texte régénéré depuis PostgreSQL", encoding="utf-8")
        (dossier / "commentaires.txt").write_text(
            "Un commentaire", encoding="utf-8")
        (dossier / "corpus.sqlite3").write_bytes(b"SQLite format 3\x00")

    def _construire(self, archive_active=None, type_collecte="collecte"):
        connexion = ConnexionFictive(
            "Manifestations lycéennes", {"include_sources": True})
        with patch("stockage.export_zip_postgres.ouvrir_connexion",
                   return_value=connexion), patch(
                       "stockage.export_zip_postgres.exporter_sauvegarde",
                       side_effect=faux_exporter), patch(
                       "stockage.export_zip_postgres._enregistrements",
                       side_effect=fausses_lignes), patch(
                       "stockage.export_zip_postgres._generer_fichiers",
                       side_effect=self._generer):
            fichier, nom = construire_archive_postgres(
                "cookie_prive", type_collecte, "a" * 32,
                archive_active=archive_active)
        return fichier, nom, connexion

    def test_zip_postgres_regroupe_tous_les_resultats(self):
        fichier, nom, connexion = self._construire()
        self.assertEqual(nom, "Manifestations_lycéennes.zip")
        try:
            with ZipFile(fichier) as archive:
                noms = archive.namelist()
                self.assertEqual(len(noms), len(set(noms)))
                attendus = {
                    "informations_export.json",
                    "publications.csv", "publications.json",
                    "commentaires.csv", "commentaires.json",
                    "engagement.csv", "textes.txt",
                    "commentaires.txt", "corpus.sqlite3",
                }
                self.assertTrue(attendus.issubset(noms))
                informations = json.loads(
                    archive.read("informations_export.json"))
                self.assertEqual(informations["nom_collecte"],
                                 "Manifestations lycéennes")
                self.assertEqual(informations["publications"], 1)
                self.assertEqual(informations["commentaires"], 1)
                self.assertIn(b"219", archive.read("publications.csv"))
        finally:
            fichier.close()
        self.assertIn("proprietaire_hash=%s",
                      connexion.curseur.instructions[0][0])
        self.assertNotIn("cookie_prive",
                         str(connexion.curseur.instructions[0][1]))

    def test_zip_regroupe_les_fichiers_originaux_mp4_disponibles(self):
        """Les MP4 déjà collectés et les TXT originaux sont conservés."""
        with tempfile.TemporaryDirectory() as dossier:
            source = Path(dossier) / "archive_originale.zip"
            with ZipFile(source, "w") as archive:
                archive.writestr("videos/video.mp4", b"\x00\x00\x00\x18ftypmp42")
                archive.writestr("textes.txt", "Texte exact original")
                archive.writestr("publications.csv", "ancienne version")
            fichier, _, _ = self._construire(archive_active=source)
            try:
                with ZipFile(fichier) as archive:
                    noms = archive.namelist()
                    self.assertEqual(len(noms), len(set(noms)))
                    self.assertIn("videos/video.mp4", noms)
                    self.assertEqual(archive.read("textes.txt"),
                                     "Texte exact original".encode("utf-8"))
                    self.assertIn(b"219", archive.read("publications.csv"))
                    manifeste = json.loads(
                        archive.read("informations_export.json"))
                    self.assertTrue(manifeste["mp4_presents"])
            finally:
                fichier.close()

    def test_generer_de_nouveau_les_resultats_depuis_postgres(self):
        """Les CSV, TXT et SQLite sont recréés sans archive locale."""
        import sqlite3
        from stockage.export_zip_postgres import _generer_fichiers
        with tempfile.TemporaryDirectory() as dossier:
            _generer_fichiers(
                dossier, [PUBLICATION], [COMMENTAIRE],
                "a" * 32,
                {"include_sources": True,
                 "variables_txt": ["date", "profil", "id", "vues"]},
            )
            noms = {f.name for f in Path(dossier).iterdir()}
            self.assertTrue({
                "publications.csv", "publications.json",
                "commentaires.csv", "commentaires.json",
                "engagement.csv", "ratios_engagement.csv",
                "comparaison_medias.csv", "textes.txt",
                "corpus_iramuteq.txt", "corpus_commentaires_iramuteq.txt",
                "commentaires.txt", "corpus.sqlite3",
            }.issubset(noms))
            self.assertIn("7702544004629531937",
                          (Path(dossier) / "textes.txt").read_text(
                              encoding="utf-8"))
            with sqlite3.connect(Path(dossier) / "corpus.sqlite3") as base:
                self.assertEqual(
                    base.execute("SELECT count(*) FROM publications").fetchone()[0],
                    1)
                self.assertEqual(
                    base.execute("SELECT count(*) FROM commentaires").fetchone()[0],
                    1)

    def test_route_zip_prioritaire_sur_consultation_generique(self):
        """Le 404 « Sauvegarde ou catégorie introuvable » est éliminé."""
        from webapp import app
        routes = [getattr(route, "path", "") for route in app.routes]
        route_zip = (
            "/api/base-donnees/{type_sauvegarde}/{identifiant}/archive.zip"
        )
        route_generique = (
            "/api/base-donnees/{type_sauvegarde}/{identifiant}/{categorie}"
        )
        self.assertIn(route_zip, routes)
        self.assertIn(route_generique, routes)
        self.assertLess(routes.index(route_zip), routes.index(route_generique))

    def test_collecte_inconnue_ne_produit_pas_de_zip(self):
        with patch("stockage.export_zip_postgres.ouvrir_connexion",
                   return_value=ConnexionFictive(None)):
            with self.assertRaises(ValueError):
                construire_archive_postgres("cookie_prive", "collecte",
                                            "a" * 32)

    def test_type_table_limite(self):
        with self.assertRaises(ValueError):
            construire_archive_postgres("cookie", "autre_table", "a" * 32)


if __name__ == "__main__":
    unittest.main()
