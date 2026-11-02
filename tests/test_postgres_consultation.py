"""Tests du stockage privé PostgreSQL, sans connexion réseau."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from threading import RLock
from unittest.mock import patch

from stockage.postgres_consultation import (
    IDENTIFIANT, adresse_configuree, empreinte, valeur_colonne,
    archiver_collecte, importer_historique, preparer_tables,
)
from stockage.colonnes_publications import (
    colonnes_publications, preparer_colonnes_publications,
)


class CurseurFictif:
    def __init__(self):
        self.executions = []

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        return False

    def execute(self, instruction, parametres=None):
        self.executions.append((instruction, parametres))

    def fetchall(self):
        """Simuler une table sans les colonnes calculées avant migration."""
        return []


class ConnexionFictive:
    def __init__(self):
        self.curseur = CurseurFictif()

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        return False

    def cursor(self):
        return self.curseur


class ParametresFictifs:
    nom_sauvegarde = "Test 24 octobre"
    libelle = "Autre libellé"
    source_collecte = "presse"
    moteur_actif = "research"

    def model_dump(self):
        return {"nom_sauvegarde": self.nom_sauvegarde,
                "research_client_key": "cle_interdite",
                "research_client_secret": "secret_interdit"}


class TestsPostgresConsultation(unittest.TestCase):
    def test_id_et_cookie_proteges(self):
        self.assertTrue(IDENTIFIANT.fullmatch("a" * 32))
        self.assertFalse(IDENTIFIANT.fullmatch("a" * 31))
        self.assertFalse(IDENTIFIANT.fullmatch("a" * 32 + "_"))
        self.assertEqual(len(empreinte("cookie_prive")), 64)

    def test_extraction_compteurs_exacte(self):
        self.assertEqual(valeur_colonne(
            {"engagement": {"vues": {"valeur": 0}}}, "vues"), "0")
        self.assertEqual(valeur_colonne(
            {"engagement": {"vues": {"valeur": None}}}, "vues"), "")

    def test_vues_tabulaire_creees_avec_les_tables(self):
        """Les métadonnées et compteurs ont des colonnes consultables."""
        connexion = ConnexionFictive()
        preparer_tables(connexion)
        instructions = [
            sql for sql, _ in connexion.curseur.executions]
        vue_videos = next(
            sql for sql in instructions
            if "CREATE OR REPLACE VIEW scraptiktok_publications_tableau" in sql)
        vue_commentaires = next(
            sql for sql in instructions
            if "CREATE OR REPLACE VIEW scraptiktok_commentaires_tableau" in sql)
        for variable in (
            "publication_id", "nom_sauvegarde", "region_code",
            "is_verified", "follower_count", "vues", "likes",
            "commentaires", "partages", "favoris", "taux_engagement",
            "hashtags", "contenu_genere_ia", "duree_secondes"):
            self.assertIn(variable, vue_videos)
        self.assertIn("COALESCE", vue_commentaires)
        self.assertIn("commentaire_id", vue_commentaires)
        self.assertIn("JOIN scraptiktok_collectes", vue_videos)
        self.assertIn("JOIN scraptiktok_collectes", vue_commentaires)

    def test_colonnes_reelles_dans_scraptiktok_publications(self):
        """Le tableau original, et pas seulement une vue, est enrichi."""
        colonnes = colonnes_publications()
        for nom in (
            "url", "profil", "date_publication", "region_code", "is_verified",
            "follower_count", "duree_secondes", "vues", "likes",
            "commentaires", "partages", "favoris", "taux_engagement",
            "classe_abonnes", "vues_classe", "likes_classe",
            "commentaires_classe", "partages_classe", "favoris_classe",
            "duree_classe", "classe_taux_engagement", "hashtags",
            "langue_detection", "contenu_genere_ia", "resume_ia_tiktok"):
            self.assertIn(nom, colonnes)

        curseur = CurseurFictif()
        nombre = preparer_colonnes_publications(curseur)
        self.assertEqual(nombre, len(colonnes))
        alterations = [
            texte for texte, _ in curseur.executions
            if texte.startswith("ALTER TABLE scraptiktok_publications")]
        self.assertEqual(len(alterations), 1)
        self.assertIn("ADD COLUMN IF NOT EXISTS region_code TEXT", alterations[0])
        self.assertIn("GENERATED ALWAYS AS", alterations[0])
        self.assertIn("STORED", alterations[0])
        self.assertIn("donnees#>>'{engagement,vues,valeur}'", alterations[0])
        self.assertIn("THEN", alterations[0])

    def test_schema_existant_ne_declenche_pas_de_migration(self):
        """Aucun verrou DDL si toutes les colonnes existent déjà."""
        curseur = CurseurFictif()
        curseur.fetchall = lambda: [(nom,) for nom in colonnes_publications()]
        self.assertEqual(preparer_colonnes_publications(curseur), 0)
        self.assertFalse(any(
            commande.startswith("ALTER TABLE") for commande, _ in curseur.executions))

    def test_archive_republications_et_vue_pgadmin(self):
        """Sauver chaque relation compte–vidéo et exposer les champs de la vue."""
        connexion = ConnexionFictive()
        preparer_tables(connexion)
        commandes = [sql for sql, _ in connexion.curseur.executions]
        self.assertTrue(any(
            "CREATE TABLE IF NOT EXISTS scraptiktok_republications" in sql
            for sql in commandes))
        vue = next(sql for sql in commandes
                   if "CREATE OR REPLACE VIEW v_scraptiktok_republications" in sql)
        for champ in ("compte_reposteur", "auteur_original", "id_video_originale",
                      "vues", "likes", "commentaires", "partages", "favoris"):
            self.assertIn(champ, vue)
        travail = SimpleNamespace(
            lock=RLock(), id="f" * 32, owner_historique="cookie_prive",
            settings=ParametresFictifs(), status="completed", processed=0,
            publications=[], records=[], commentaires=[],
            republications=[
                {"id": "123", "id_video_originale": "123",
                 "auteur_original": "autre_auteur",
                 "compte_reposteur": "lemondefr",
                 "republication_confirmee": 1},
                {"id": "123", "id_video_originale": "123",
                 "auteur_original": "autre_auteur",
                 "compte_reposteur": "brutofficiel",
                 "republication_confirmee": 1},
            ])
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            resultat = archiver_collecte(travail)
        self.assertEqual(resultat["republications"], 2)
        lignes = [
            parametres for sql, parametres in connexion.curseur.executions
            if "INSERT INTO scraptiktok_republications" in sql]
        self.assertEqual(len(lignes), 2)
        self.assertEqual(
            {(ligne[1], ligne[2]) for ligne in lignes},
            {("lemondefr", "123"), ("brutofficiel", "123")})

    def test_archiver_test_sans_texte_retenu_et_sans_secrets(self):
        """Les vidéos rejetées sont archivées, même si le TXT est vide."""
        identifiant = "b" * 32
        travail = SimpleNamespace(
            lock=RLock(), id=identifiant, owner_historique="cookie_prive",
            settings=ParametresFictifs(), status="completed", processed=1,
            publications=[{"id": "123", "author": "brutofficiel",
                           "description": "#actu", "retenue": False}],
            records=[], commentaires=[])
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            bilan = archiver_collecte(travail)
        self.assertEqual(bilan["publications"], 1)
        self.assertEqual(bilan["commentaires"], 0)
        textes = " ".join(str(entree) for entree in connexion.curseur.executions)
        self.assertIn("scraptiktok_publications", textes)
        self.assertIn("Test 24 octobre", textes)
        self.assertNotIn("cle_interdite", textes)
        self.assertNotIn("secret_interdit", textes)
        self.assertNotIn("cookie_prive", textes)
        self.assertIn(empreinte("cookie_prive"), textes)

    def test_archivage_incremental_ne_reecrit_pas_les_anciens_enregistrements(self):
        """Un point automatique ne réinsère que les publications nouvelles."""
        travail = SimpleNamespace(
            lock=RLock(), id="d" * 32, owner_historique="cookie_prive",
            settings=ParametresFictifs(), status="collecting", processed=2,
            publications=[
                {"id": "101", "description": "Ancienne vidéo"},
                {"id": "102", "description": "Nouvelle vidéo"}],
            records=[], commentaires=[
                {"id": "201", "publication_id": "101", "texte": "Ancien"},
                {"id": "202", "publication_id": "102", "texte": "Nouveau"}])
        connexion = ConnexionFictive()
        with patch("stockage.postgres_consultation.ouvrir_connexion",
                   return_value=connexion):
            bilan = archiver_collecte(
                travail, a_partir_publications=1, a_partir_commentaires=1)
        self.assertEqual(bilan["publications"], 1)
        self.assertEqual(bilan["commentaires"], 1)
        insertions = [
            (sql, valeurs) for sql, valeurs in connexion.curseur.executions
            if sql.lstrip().upper().startswith("INSERT INTO")]
        donnees = {
            "publications": [
                valeurs[1] for sql, valeurs in insertions
                if "INSERT INTO scraptiktok_publications" in sql],
            "commentaires": [
                valeurs[1] for sql, valeurs in insertions
                if "INSERT INTO scraptiktok_commentaires" in sql],
        }
        self.assertEqual(donnees["publications"], ["102"])
        self.assertEqual(donnees["commentaires"], ["202"])
        self.assertEqual(
            len([1 for sql, _ in insertions
                 if "INSERT INTO scraptiktok_collectes" in sql]), 1)

    def test_points_postgres_rejouables_sans_reecriture_inutile(self):
        """Un deuxième point inchangé ne réécrit pas le même corpus."""
        from webapp import Job, StartRequest
        with tempfile.TemporaryDirectory() as dossier:
            parametres = StartRequest(
                source_collecte="hashtags", hashtag="test",
                nom_sauvegarde="Corpus de test")
            travail = Job(
                "e" * 64, parametres, Path(dossier),
                owner_historique="f" * 64)
            travail.records.append({"id": "101", "description": "Première"})
            travail.update(processed=1)
            with patch("stockage.postgres_consultation.archiver_collecte",
                       return_value={"statut": "synchronise",
                                     "publications": 1, "commentaires": 0}
                       ) as enregistrer:
                self.assertTrue(travail.sauvegarder_postgres(progressif=True))
                self.assertTrue(travail.sauvegarder_postgres(progressif=True))
                self.assertEqual(enregistrer.call_count, 1)
                travail.records.append({"id": "102", "description": "Deuxième"})
                travail.update(processed=2)
                self.assertTrue(travail.sauvegarder_postgres(progressif=True))
                self.assertEqual(enregistrer.call_count, 2)
                self.assertEqual(
                    enregistrer.call_args.kwargs["a_partir_publications"], 1)
                self.assertEqual(travail.sauvegarde_postgres_publications, 2)

    def test_import_historique_autorise_par_cookie(self):
        """L'import reprend la sauvegarde possédée par le même navigateur."""
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            (racine / "publications.json").write_text(
                json.dumps([{"id": "123", "description": "Légende"}]),
                encoding="utf-8")
            (racine / "commentaires.json").write_text("[]", encoding="utf-8")
            entree = {"id": "c" * 32, "titre": "Ancienne recherche",
                      "statut": "completed"}
            manifeste = {"parametres": {"source_collecte": "presse",
                                        "presse_moteur": "research"},
                         "traites": 1}
            with patch("stockage.historique_analyses.lister",
                       return_value=[entree]), patch(
                           "stockage.historique_analyses.retrouver",
                           return_value=(entree, racine, manifeste)), patch(
                           "stockage.postgres_consultation.archiver_collecte",
                           return_value={"publications": 1, "commentaires": 0}
                           ) as enregistrer:
                bilan = importer_historique(dossier, "cookie_original")
            self.assertEqual(bilan["imports"], 1)
            self.assertEqual(bilan["publications"], 1)
            self.assertEqual(bilan["erreurs"], 0)
            travail = enregistrer.call_args.args[0]
            self.assertEqual(travail.owner_historique, "cookie_original")
            self.assertEqual(travail.settings.nom_sauvegarde,
                             "Ancienne recherche")


if __name__ == "__main__":
    unittest.main()
