"""Annotations humaines de violence : persistance, API privée, exclusion des non-évaluées."""
import json
import tempfile
import pandas as pd
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import webapp as web
from analyse_desordre.annotation import (
    lire_annotations, enregistrer_annotations, exporter_annotations_csv,
    correlations_violence, modifications_depuis_tableau, publications_annotables
)
from analyse_desordre.service import ecrire_etat


class TestsAnnotations(unittest.TestCase):
    def test_sauvegarde_atomique_et_non_evalue_distinct_de_zero(self):
        with tempfile.TemporaryDirectory() as d:
            session=Path(d)
            assert lire_annotations(session)=={}
            enregistrer_annotations(session, [
                {"publication_id":"123", "violence_visible":0},
                {"publication_id":"456", "violence_visible":1},
            ], {"123","456"})
            self.assertEqual(lire_annotations(session), {"123":0,"456":1})
            with self.assertRaises(ValueError):
                enregistrer_annotations(session, [
                    {"publication_id":"123", "violence_visible":1},
                    {"publication_id":"999", "violence_visible":0},
                ], {"123","456"})
            self.assertEqual(lire_annotations(session), {"123":0,"456":1})
            enregistrer_annotations(session, [
                {"publication_id":"123","violence_visible":None},
            ], {"123","456"})
            self.assertEqual(lire_annotations(session), {"456":1})
            # Le CSV conserve une cellule vide pour les vidéos non évaluées.
            csv=exporter_annotations_csv([
                {"id":"123","url":"https://www.tiktok.com/@x/video/123"},
                {"id":"456","url":"https://www.tiktok.com/@x/video/456"}
            ],lire_annotations(session))
            self.assertIn("123;https://www.tiktok.com/@x/video/123;\r\n",csv)
            self.assertIn("456;https://www.tiktok.com/@x/video/456;1",csv)

    def test_menus_deroulants_dans_tableau_principal_codes_et_identifiants(self):
        avant=pd.DataFrame({
            "publication_id":["7697829530844663072","101","102"],
            "annotation_violence":["Non évaluée","Non (0)","Oui (1)"]
        })
        apres=avant.copy()
        # Simuler un tableau trié par l'utilisateur avant l'enregistrement.
        apres=apres.iloc[[2,0,1]].reset_index(drop=True)
        apres.loc[apres["publication_id"]=="7697829530844663072","annotation_violence"]="Oui (1)"
        apres.loc[apres["publication_id"]=="101","annotation_violence"]="Non évaluée"
        changements=modifications_depuis_tableau(avant,apres)
        self.assertEqual(changements,[
            {"publication_id":"7697829530844663072","violence_visible":1},
            {"publication_id":"101","violence_visible":None}
        ])
        self.assertEqual(modifications_depuis_tableau(avant,avant),[])
        invalide=apres.copy()
        invalide.loc[0,"annotation_violence"]="inconnue"
        with self.assertRaises(ValueError):
            modifications_depuis_tableau(avant,invalide)

    def test_publications_supplementaires_conservent_identifiants_et_urls(self):
        publications=publications_annotables(
            [{"id":"123","url":"https://www.tiktok.com/@test/video/123"}],
            [{"publication_id":"123"},{"publication_id":"456","url":"https://www.tiktok.com/@test/video/456"}]
        )
        self.assertEqual([p["id"] for p in publications],["123","456"])
        self.assertEqual(publications[1]["url"],"https://www.tiktok.com/@test/video/456")

    def test_correlations_binaires_excluent_non_evaluees(self):
        with tempfile.TemporaryDirectory() as d:
            csv=Path(d)/"indicateurs_engagement.csv"
            csv.write_text("publication_id,commentaires,likes,indice_desordre\n"
                           "1,10,1,11\n2,12,3,12\n3,15,2,13\n"
                           "4,200,14,80\n5,250,15,81\n6,300,16,82\n"
                           "7,999,20,99\n",encoding="utf-8")
            codes={"1":0,"2":0,"3":0,"4":1,"5":1,"6":1}
            correlations=correlations_violence(csv,codes)
            self.assertEqual(len(correlations),13)
            result=next(c for c in correlations if c["engagement"]=="commentaires")
            self.assertEqual(result["indicateur"],"violence_visible")
            self.assertEqual(result["n"],6)
            self.assertGreater(result["rho"],0.8)
            self.assertIsNotNone(result["p_ajustee_bh"])
            visuel=next(c for c in correlations if c["engagement"]=="indice_desordre")
            self.assertEqual(visuel["n"],6)
            self.assertGreater(visuel["rho"],0.8)
            # Un groupe constant n'est pas une corrélation calculable.
            constante=correlations_violence(csv,{"1":0,"2":0,"3":0})
            result=next(c for c in constante if c["engagement"]=="commentaires")
            self.assertIsNone(result["rho"])
            self.assertEqual(result["raison"],"indicateur_constant")

    def test_routes_sauvegarde_enrichissent_resultats_et_exports_prives(self):
        with tempfile.TemporaryDirectory() as d:
            manager=web.Manager(data_dir=d)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                owner=client.cookies[web.COOKIE]
                job=web.Job(owner,web.StartRequest(hashtag="test",enrichir=True),Path(d))
                job.update(busy=False,archive_prete=True)
                manager.jobs[job.id]=job
                data=[
                    {"id":str(i),"url":f"https://www.tiktok.com/@test/video/{i}"}
                    for i in range(1,7)
                ]
                (job.directory/"publications.json").write_text(json.dumps(data))
                dossier=job.directory/"desordre_0123456789abcdef"
                dossier.mkdir()
                (dossier/"indicateurs_engagement.csv").write_text(
                    "publication_id,indice_desordre,commentaires,vues\n"
                    + "".join(f"{i},{i*10},{i*20},{i*100}\n" for i in range(1,7))
                )
                chemin=f"/api/jobs/{job.id}/desordre"
                entetes={"X-ScrapTikTok":"1"}
                payload={"annotations":[
                    {"publication_id":str(i),"violence_visible":int(i>=4)}
                    for i in range(1,7)
                ]}
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    self.assertEqual(client.post(chemin+"/annotations",json=payload,
                                                 headers=entetes).status_code,409)
                ecrire_etat(job.directory,{"statut":"termine","dossier":dossier.name})
                self.assertEqual(client.post(chemin+"/annotations",json=payload).status_code,403)
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    self.assertEqual(client.post(chemin+"/annotations",json={
                        "annotations":[{"publication_id":"77","violence_visible":1}]
                    },headers=entetes).status_code,422)
                    self.assertEqual(client.post(chemin+"/annotations",json={
                        "annotations":[{"publication_id":"1","violence_visible":2}]
                    },headers=entetes).status_code,422)
                    response=client.post(chemin+"/annotations",json=payload,
                                         headers=entetes)
                    self.assertEqual(response.status_code,200,response.text)
                retour=client.get(chemin).json()
                self.assertEqual(retour["annotations_violence"],{
                    "oui":3,"non":3,"non_evaluees":0
                })
                self.assertEqual(retour["indicateurs"][0]["violence_visible"],0)
                self.assertEqual(retour["indicateurs"][5]["violence_visible"],1)
                mesure=next(r for r in retour["correlations"]
                            if r["indicateur"]=="violence_visible"
                            and r["engagement"]=="commentaires")
                self.assertEqual(mesure["n"],6)
                self.assertIsNotNone(mesure["rho"])
                visuel=next(r for r in retour["correlations"]
                    if r["indicateur"]=="violence_visible"
                    and r["engagement"]=="indice_desordre")
                self.assertEqual(visuel["n"],6)
                self.assertEqual(client.get(chemin+"/annotations.csv").status_code,200)
                self.assertIn("1;https://www.tiktok.com/@test/video/1;0",
                              client.get(chemin+"/annotations.csv").text)
                self.assertIn("violence_visible",
                              client.get(chemin+"/correlations_violence.csv").text)
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    self.assertEqual(client.post(chemin+"/annotations",json={
                        "annotations":[{"publication_id":"2","violence_visible":None}]
                    },headers=entetes).status_code,200)
                retour=client.get(chemin).json()
                self.assertIsNone(retour["indicateurs"][1]["violence_visible"])
                self.assertEqual(retour["annotations_violence"]["non_evaluees"],1)
                self.assertEqual(next(r for r in retour["correlations"]
                    if r["indicateur"]=="violence_visible"
                    and r["engagement"]=="commentaires")["n"],5)
                stranger=TestClient(web.create_app(manager))
                with stranger:
                    stranger.get("/")
                    self.assertEqual(stranger.get(chemin+"/annotations.csv").status_code,404)
                    self.assertEqual(stranger.get(chemin+"/correlations_violence.csv").status_code,404)
                    with patch("ticket_gate.verifier_session_active",return_value=True):
                        self.assertEqual(stranger.post(chemin+"/annotations",json=payload,
                            headers=entetes).status_code,404)
