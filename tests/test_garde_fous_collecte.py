"""Quotas applicatifs, persistants et testables sans joindre TikTok."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request

from pydantic import ValidationError

from collecte.garde_fous import (
    QuotaLocalDepasse, demarrer_job, terminer_job,
    reserver_requete_api, utilisation, reglages,
)
from collecte.presse_api import ClientAvecQuota, PresseBudgetError
from webapp import StartRequest


ENV={
    "SCRAPTIKTOK_MAX_POSTS_PER_SOURCE":"50",
    "SCRAPTIKTOK_MAX_SOURCES_PER_JOB":"3",
    "SCRAPTIKTOK_MAX_POSTS_PER_JOB":"150",
    "SCRAPTIKTOK_MAX_COMMENTS_PER_POST":"20",
    "SCRAPTIKTOK_MAX_JOBS_PER_DAY":"2",
    "SCRAPTIKTOK_API_REQUESTS_PER_HOUR":"2",
    "SCRAPTIKTOK_API_REQUESTS_PER_DAY":"3",
    "SCRAPTIKTOK_API_GAP_SECONDS":"5",
    "JOB_TIMEOUT_SECONDS":"900",
}


class TestQuotas(unittest.TestCase):
    def test_regles_sont_configurables_et_imposees_sur_requetes_api(self):
        with patch.dict(os.environ,ENV):
            self.assertEqual(reglages()["max_posts_source"],50)
            with self.assertRaisesRegex(ValidationError,"maximum 50 publications"):
                StartRequest(hashtag="test",limit=51)
            with self.assertRaisesRegex(ValidationError,"maximum 20 commentaires"):
                StartRequest(hashtag="test",collecter_commentaires=True,limite_commentaires=21)
            with self.assertRaisesRegex(ValidationError,"maximum 3 sources"):
                StartRequest(source_collecte="comptes",hashtag="test",limit=10,
                             comptes=["lemonde","franceinfo","lefigaro","liberation"])
            valeurs=StartRequest(source_collecte="comptes",hashtag="test",
                                 limit=50,comptes=["lemonde","franceinfo","lefigaro"])
            self.assertEqual(len(valeurs.comptes),3)

    def test_nombre_collectes_global_limite_a_deux_sur_24h(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV):
            demarrer_job(d,"job_a","session-abc","presse",2,50,maintenant=1000)
            demarrer_job(d,"job_b","session-def","hashtags",1,10,maintenant=1100)
            with self.assertRaisesRegex(QuotaLocalDepasse,"2 collectes"):
                demarrer_job(d,"job_c","session-ghi","presse",1,10,maintenant=1200)
            terminer_job(d,"job_a","completed",38,maintenant=1200)
            statut=utilisation(d,maintenant=1200)
            self.assertEqual(statut["jobs_last_24h"],2)
            with sqlite3.connect(Path(d)/"scraptiktok_usage.sqlite") as db:
                lignes=db.execute("SELECT session_hash,statut,traites FROM usage_jobs "
                                   "WHERE job_id='job_a'").fetchall()
            self.assertEqual(len(lignes[0][0]),16)
            self.assertNotEqual(lignes[0][0],"session-abc")
            self.assertEqual(lignes[0][1:],("completed",38))
            demarrer_job(d,"job_c","session-ghi","presse",1,10,maintenant=1000+86401)

    def test_quota_et_intervalle_api_commun_toutes_sessions(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV):
            self.assertEqual(reserver_requete_api(d,maintenant=1000),0)
            self.assertEqual(reserver_requete_api(d,maintenant=1000),5)
            with self.assertRaisesRegex(QuotaLocalDepasse,"Quota de précaution"):
                reserver_requete_api(d,maintenant=1000)
            # Le quota horaire se renouvelle ; le quota journalier persiste.
            self.assertEqual(reserver_requete_api(d,maintenant=4700),0)
            with self.assertRaises(QuotaLocalDepasse):
                reserver_requete_api(d,maintenant=4700)

    def test_client_ne_fait_pas_de_requete_apres_limite(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{
            **ENV,"DATA_DIR":d,"SCRAPTIKTOK_API_REQUESTS_PER_HOUR":"1",
        }):
            client=Mock()
            client.open.return_value=Mock()
            limite=ClientAvecQuota(client)
            limite.open(Request("https://www.tiktok.com/embed/@lemondefr"))
            with self.assertRaises(PresseBudgetError):
                limite.open(Request("https://www.tiktok.com/embed/@lemondefr"))
            self.assertEqual(client.open.call_count,1)

    def test_quotas_sont_propreset_a_scraptiktok_pas_a_tiktok(self):
        with patch.dict(os.environ,ENV):
            self.assertEqual(reglages()["nature"],"plafonds_locaux_non_officiels")
            self.assertEqual(reglages()["max_job_seconds"],900)


if __name__=="__main__":
    unittest.main()
