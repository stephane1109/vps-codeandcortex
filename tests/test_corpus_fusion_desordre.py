"""La table d'analyse complète est réimportable, sans perte d'ID ni double comptage."""
import csv
from io import StringIO
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

import webapp as web
from analyse_desordre.corpus_fusion import (
    construire_tableau_complet, sauvegarder_tableau_complet, fusionner_tableaux,
)
from analyse_desordre.annotation import enregistrer_annotations
from analyse_desordre.codages_personnalises import creer_variable, enregistrer
from stockage.historique_analyses import retrouver


ID_A = "7697829530844663072"
ID_B = "7697829530844663073"
ID_C = "7697829530844663074"
ID_D = "7697829530844663075"


def csv_reader(texte):
    return list(csv.DictReader(StringIO(texte.lstrip("\ufeff")),delimiter=";"))


def preparer_session(racine, identifiant, *, second=False):
    session=Path(racine)/identifiant
    session.mkdir()
    dossier=session/"desordre_0123456789abcdef"
    dossier.mkdir()
    (session/"desordre_etat.json").write_text(
        json.dumps({"statut":"termine","dossier":dossier.name}),encoding="utf-8")
    (dossier/"parametres.json").write_text(
        json.dumps({"frequence":10,"dimension":320,"duree_max":15}),encoding="utf-8")
    if second:
        donnees=[
            {"id":ID_B,"url":f"https://www.tiktok.com/@media/video/{ID_B}"},
            {"id":ID_D,"url":f"https://www.tiktok.com/@media/video/{ID_D}"},
        ]
        valeurs=f"publication_id;url;indice_desordre;vitesse_residuelle;likes\n{ID_B};{donnees[0]['url']};72;5;110\n{ID_D};{donnees[1]['url']};44;3;90\n"
    else:
        donnees=[
            {"id":ID_A,"url":f"https://www.tiktok.com/@media/video/{ID_A}"},
            {"id":ID_B,"url":f"https://www.tiktok.com/@media/video/{ID_B}"},
            {"id":ID_C,"url":f"https://www.tiktok.com/@media/video/{ID_C}"},
        ]
        valeurs=f"publication_id;url;indice_desordre;vitesse_residuelle;likes\n{ID_A};{donnees[0]['url']};27;-2.3;100\n{ID_B};{donnees[1]['url']};55;1.2;80\n"
    (session/"publications.json").write_text(
        json.dumps(donnees),encoding="utf-8")
    (dossier/"indicateurs_engagement.csv").write_text(valeurs,encoding="utf-8-sig")
    return session,dossier


class FusionDesordreTests(unittest.TestCase):
    def test_export_sauve_urls_indices_mouvements_annotations_et_sans_mesure(self):
        with tempfile.TemporaryDirectory() as racine:
            session,dossier=preparer_session(racine,"a"*32)
            enregistrer_annotations(session,[{"publication_id":ID_A,
                "violence_visible":1}],{ID_A,ID_B,ID_C})
            variable=creer_variable(session,"Symbole de l'État")
            enregistrer(session,[{"publication_id":ID_B,
                "variable_id":variable["id"],"valeur":0}],{ID_A,ID_B,ID_C})
            texte=construire_tableau_complet(session,dossier)
            self.assertTrue(texte.startswith("\ufeff"))
            lignes=csv_reader(texte)
            self.assertEqual([v["publication_id"] for v in lignes],[ID_A,ID_B,ID_C])
            a,b,c=lignes
            self.assertEqual(a["url"],f"https://www.tiktok.com/@media/video/{ID_A}")
            self.assertEqual(a["indice_desordre"],"27")
            self.assertEqual(a["vitesse_residuelle"],"-2.3")
            self.assertEqual(a["violence_visible"],"1")
            self.assertEqual(b["codage:Symbole de l'État"],"0")
            self.assertEqual(b["violence_visible"],"")
            self.assertEqual(c["statut"],"sans_mesure")
            self.assertEqual(c["indice_desordre"],"")
            self.assertEqual(a["analyse_source"],"a"*32)
            self.assertEqual(a["parametres_duree_max"],"15")
            chemin=sauvegarder_tableau_complet(session)
            self.assertEqual(chemin.name,"tableau_complet.csv")
            self.assertEqual(chemin.read_text(encoding="utf-8"),texte)

    def test_concatenation_preserve_ids_dedoublonne_et_signale_divergences(self):
        with tempfile.TemporaryDirectory() as racine:
            session_a,dossier_a=preparer_session(racine,"a"*32)
            session_b,dossier_b=preparer_session(racine,"b"*32,second=True)
            variable=creer_variable(session_a,"Violence symbolique")
            enregistrer(session_a,[{"publication_id":ID_A,
                "variable_id":variable["id"],"valeur":1}],{ID_A,ID_B,ID_C})
            a=construire_tableau_complet(session_a,dossier_a).encode("utf-8")
            b=construire_tableau_complet(session_b,dossier_b).encode("utf-8")
            fusion=fusionner_tableaux([("lot_a.csv",a),("lot_b.csv",b)])
            self.assertEqual(fusion["nombre_unique"],4)
            self.assertEqual(fusion["total_initial"],5)
            self.assertEqual(fusion["doublons"],1)
            self.assertEqual(fusion["doublons_divergents"],1)
            lignes={ligne["publication_id"]:ligne for ligne in csv_reader(fusion["csv"])}
            self.assertEqual(lignes[ID_B]["indice_desordre"],"55")
            self.assertEqual(lignes[ID_D]["indice_desordre"],"44")
            self.assertEqual(lignes[ID_A]["codage:Violence symbolique"],"1")
            self.assertEqual(lignes[ID_D]["codage:Violence symbolique"],"")
            self.assertEqual(lignes[ID_D]["analyse_source"],"b"*32)
            fusion_inverse=fusionner_tableaux([("lot_a.csv",a),("lot_b.csv",b)],
                                              priorite="dernier")
            dernier={x["publication_id"]:x for x in csv_reader(fusion_inverse["csv"])}
            self.assertEqual(dernier[ID_B]["indice_desordre"],"72")

    def test_mauvais_csv_est_refuse(self):
        with self.assertRaisesRegex(ValueError,"tableau complet"):
            fusionner_tableaux([("invalide.csv",
                b"publication_id;url\n123;https://www.tiktok.com/@media/video/123\n")])
        with self.assertRaisesRegex(ValueError,"Identifiant TikTok"):
            fusionner_tableaux([("invalide.csv",
                b"publication_id;url;indice_desordre\n7.69782E+18;url;12\n")])
        with self.assertRaisesRegex(ValueError,"10 Mo"):
            fusionner_tableaux([("gros.csv", b"x"*(10*1024*1024+1))])

    def test_api_export_complet_et_achivage_sur_30_jours(self):
        with tempfile.TemporaryDirectory() as racine:
            manager=web.Manager(data_dir=racine)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                origine=client.cookies[web.COOKIE]
                history=client.cookies[web.HISTORIQUE_COOKIE]
                job=web.Job(origine,web.StartRequest(hashtag="test",enrichir=True),
                            Path(racine),owner_historique=history)
                job.update(busy=False,archive_prete=True,status="completed")
                manager.jobs[job.id]=job
                (job.directory/"publications.json").write_text(json.dumps([
                    {"id":ID_A,"url":f"https://www.tiktok.com/@media/video/{ID_A}",
                     "author":"media","description":"Texte","retenue":True,"engagement":{}},
                ]))
                mesures=job.directory/"desordre_0123456789abcdef"
                mesures.mkdir()
                (job.directory/"desordre_etat.json").write_text(json.dumps({
                    "statut":"termine","dossier":mesures.name}))
                (mesures/"indicateurs_engagement.csv").write_text(
                    f"publication_id;url;indice_desordre;likes\n"
                    f"{ID_A};https://www.tiktok.com/@media/video/{ID_A};20;30\n"
                )
                url=f"/api/jobs/{job.id}/desordre/tableau-complet.csv"
                response=client.get(url)
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(csv_reader(response.text)[0]["indice_desordre"],"20")
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    saved=client.post(f"/api/jobs/{job.id}/desordre/sauvegarder",
                                      json={},headers={"X-ScrapTikTok":"1"})
                self.assertEqual(saved.status_code,200,saved.text)
                archive=retrouver(racine,job.id,history)
                self.assertTrue((archive[1]/mesures.name/"tableau_complet.csv").is_file())
                zip_=client.get(f"/api/historique/{job.id}/archive")
                with ZipFile(BytesIO(zip_.content)) as z:
                    self.assertIn(mesures.name+"/tableau_complet.csv",z.namelist())


if __name__=="__main__":
    unittest.main()
