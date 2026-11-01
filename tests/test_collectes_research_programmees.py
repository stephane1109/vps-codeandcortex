"""Tests de la collecte Research planifiée et de sa base SQLite permanente."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from stockage.collectes_research import (
    candidats, changer_etat, chemin_base, creer_plan, detail_plan, donnees_plan,
    enregistrer_lot, enregistrer_partiel, etat_quota, exporter, lister_plans,
    reprendre_apres_redemarrage, reserver_lot, reserver_requete,
)


def aujourd_hui():
    return datetime.now(timezone.utc).date()


def parametres(debut, fin):
    return {
        "source_collecte": "presse", "presse_moteur": "research",
        "medias": ["lemonde", "franceinfo"],
        "date_debut": debut.isoformat(), "date_fin": fin.isoformat(),
        "collecte_research_complete": True,
        "collecter_commentaires": True, "research_client_secret": "NE_PAS_STOCKER",
    }


class TestsCollectesResearchProgrammees(unittest.TestCase):
    def test_sqlite_proprietaire_dedoublonnage_et_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            debut = aujourd_hui() - timedelta(days=1)
            fin = aujourd_hui()
            identifiant = creer_plan(
                tmp, "cookie_prive", parametres(debut, fin),
                aujourd_hui().isoformat(), (aujourd_hui()+timedelta(days=2)).isoformat())
            self.assertIsNone(detail_plan(tmp, identifiant, "autre_utilisateur"))
            self.assertEqual(len(lister_plans(tmp, "cookie_prive")), 1)
            self.assertNotIn(b"NE_PAS_STOCKER", chemin_base(tmp).read_bytes())
            lot = reserver_lot(tmp, identifiant)
            self.assertEqual(lot["source"], "lemonde")
            self.assertEqual(lot["jour"], debut.isoformat())
            pub = {
                "id": "7000000000000000001",
                "url": "https://www.tiktok.com/@lemondefr/video/7000000000000000001",
                "author": "lemondefr", "description": "Manifestation",
                "engagement": {"vues": {"valeur": 30}},
                "retenue": True,
            }
            commentaire = {
                "id": "101", "publication_id": pub["id"],
                "texte": "Commentaire", "auteur": "lecteur",
            }
            enregistrer_partiel(tmp, identifiant, pub, [commentaire])
            enregistrer_partiel(tmp, identifiant, pub, [commentaire])
            travail = SimpleNamespace(
                id="a"*32, publications=[pub], records=[pub],
                commentaires=[commentaire], message="Lot terminé",
                status="completed", settings=SimpleNamespace(date_debut=lot["jour"]))
            enregistrer_lot(tmp, identifiant, travail, abouti=True)
            details = detail_plan(tmp, identifiant, "cookie_prive")
            self.assertEqual(details["publications"], 1)
            self.assertEqual(details["commentaires"], 1)
            self.assertEqual(details["lots_termines"], 1)
            self.assertEqual(details["statut"], "programme")
            self.assertEqual(reserver_lot(tmp, identifiant)["source"], "franceinfo")
            self.assertIn("Manifestation", exporter(tmp, identifiant, "cookie_prive", "txt").decode())
            self.assertIn("lemondefr", exporter(tmp, identifiant, "cookie_prive", "csv").decode("utf-8-sig"))
            self.assertIn("101", exporter(tmp, identifiant, "cookie_prive", "commentaires.csv").decode("utf-8-sig"))
            self.assertIn("Manifestation", exporter(tmp, identifiant, "cookie_prive", "json").decode())
            self.assertIsNone(exporter(tmp, identifiant, "autre_utilisateur", "csv"))
            copie = Path(tmp)/"copie.sqlite3"
            copie.write_bytes(exporter(tmp, identifiant, "cookie_prive", "sqlite3"))
            with sqlite3.connect(copie) as base:
                self.assertEqual(base.execute("SELECT count(*) FROM publications").fetchone()[0], 1)
                self.assertEqual(base.execute("SELECT count(*) FROM commentaires").fetchone()[0], 1)

    def test_suspension_et_reprise_apres_redemarrage(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = aujourd_hui()
            identifiant = creer_plan(tmp, "prive", parametres(d, d),
                d.isoformat(), (d+timedelta(days=1)).isoformat())
            self.assertEqual(changer_etat(tmp, identifiant, "prive", "suspendre"), "suspendu")
            self.assertEqual(candidats(tmp), [])
            self.assertEqual(changer_etat(tmp, identifiant, "prive", "reprendre"), "programme")
            self.assertIsNotNone(reserver_lot(tmp, identifiant))
            reprendre_apres_redemarrage(tmp)
            self.assertEqual(detail_plan(tmp, identifiant, "prive")["statut"], "programme")
            self.assertEqual(changer_etat(tmp, identifiant, "prive", "arreter"), "arrete")
            self.assertEqual(candidats(tmp), [])

    def test_budget_quotidien_local_est_durable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {"RESEARCH_QUOTA_LOCAL_JOUR": "2"}):
            self.assertTrue(reserver_requete(tmp))
            self.assertTrue(reserver_requete(tmp))
            self.assertFalse(reserver_requete(tmp))
            etat = etat_quota(tmp)
            self.assertEqual(etat["appels_enregistres"], 2)
            self.assertEqual(etat["reste_local"], 0)

    def test_planificateur_lance_un_lot_sans_requeter_tiktok(self):
        from webapp import Manager, StartRequest
        appels = []
        def executer_faux(job):
            appels.append(job.settings)
            publication = {
                "id": "7000000000000000001",
                "url": "https://www.tiktok.com/@lemondefr/video/7000000000000000001",
                "author": "lemondefr", "description": "Texte", "retenue": True,
            }
            job.publications = [publication]
            job.records = [publication]
            job.update(status="completed", busy=False,
                       message="Lot terminé", finished=time.monotonic())

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                "TIKTOK_RESEARCH_CLIENT_KEY": "test_key",
                "TIKTOK_RESEARCH_CLIENT_SECRET": "test_secret",
                "RESEARCH_QUOTA_LOCAL_JOUR": "900",
            }):
            manager = Manager(data_dir=tmp, runner=executer_faux)
            d = aujourd_hui()
            options = StartRequest(
                source_collecte="presse", medias=["lemonde"],
                presse_moteur="research", nom_sauvegarde="Recherche de test",
                date_debut=d.isoformat(),
                date_fin=d.isoformat(), collecte_research_complete=True)
            plan = manager.programmer_research("cookie_historique", options,
                d.isoformat(), (d+timedelta(days=1)).isoformat())
            manager.traiter_plans_research()
            for job in list(manager.jobs.values()):
                if job.thread:
                    job.thread.join(timeout=5)
            suivi = detail_plan(tmp, plan["id"], "cookie_historique")
            self.assertEqual(suivi["statut"], "termine")
            self.assertEqual(suivi["publications"], 1)
            self.assertEqual(len(appels), 1)
            self.assertEqual(appels[0].date_debut, d.isoformat())
            self.assertTrue(appels[0].collecte_research_complete)
            self.assertFalse(appels[0].test_research_10_publications)
            manager.shutdown()


if __name__ == "__main__":
    unittest.main()
