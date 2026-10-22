"""Non-régression des variables de codage créées dans Désordre visuel."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from analyse_desordre.codages_personnalises import (
    creer_variable, renommer_variable, lire, enregistrer,
    modifications_depuis_tableau, export_csv,
)
import webapp as web


class CodagesPersonnalisesTests(unittest.TestCase):
    def test_renommer_conserve_annotations_identifiant_et_export(self):
        with tempfile.TemporaryDirectory() as dossier:
            variable=creer_variable(dossier, "Symbole de l'État")
            identifiant=variable["id"]
            enregistrer(dossier,[
                {"variable_id":identifiant,"publication_id":"100","valeur":1},
                {"variable_id":identifiant,"publication_id":"101","valeur":0},
            ],{"100","101"})
            modifiee=renommer_variable(dossier,identifiant,"Symboles institutionnels")
            donnees=lire(dossier)
            self.assertEqual(modifiee,{"id":identifiant,"nom":"Symboles institutionnels"})
            self.assertEqual(donnees["valeurs"][identifiant],{"100":1,"101":0})
            contenu=export_csv([{"id":"100"},{"id":"101"}],donnees,{})
            self.assertIn("Symboles institutionnels",contenu)
            self.assertIn("100;;;1",contenu)
            self.assertIn("101;;;0",contenu)

    def test_noms_uniques_et_id_existant(self):
        with tempfile.TemporaryDirectory() as dossier:
            a=creer_variable(dossier,"Violence symbolique")
            b=creer_variable(dossier,"Présence policière")
            with self.assertRaisesRegex(ValueError,"déjà"):
                renommer_variable(dossier,b["id"]," violence symbolique ")
            with self.assertRaisesRegex(ValueError,"absente"):
                renommer_variable(dossier,"codage_000000000000","Nouveau nom")
            self.assertEqual(lire(dossier)["variables"][0]["id"],a["id"])

    def test_modifications_par_id_et_non_par_numero_de_ligne(self):
        variables=[{"id":"codage_aaaaaaaaaaaa","nom":"Violence"},
                   {"id":"codage_bbbbbbbbbbbb","nom":"Symbole de l'État"}]
        original=pd.DataFrame([
            {"publication_id":"100","codage_aaaaaaaaaaaa":"Non évaluée",
             "codage_bbbbbbbbbbbb":"Oui (1)"},
            {"publication_id":"101","codage_aaaaaaaaaaaa":"Non (0)",
             "codage_bbbbbbbbbbbb":"Non évaluée"},
        ])
        modifie=original.iloc[::-1].reset_index(drop=True).copy()
        modifie.loc[0,"codage_aaaaaaaaaaaa"]="Oui (1)"
        modifie.loc[1,"codage_bbbbbbbbbbbb"]="Non évaluée"
        deltas=modifications_depuis_tableau(original,modifie,variables)
        self.assertEqual(deltas,[
            {"publication_id":"101","variable_id":"codage_aaaaaaaaaaaa","valeur":1},
            {"publication_id":"100","variable_id":"codage_bbbbbbbbbbbb","valeur":None},
        ])

    def test_api_creer_renommer_enregistrer_et_relire(self):
        with tempfile.TemporaryDirectory() as dossier:
            manager=web.Manager(data_dir=dossier)
            with TestClient(web.create_app(manager)) as client:
                client.get("/")
                session=web.Job(client.cookies[web.COOKIE],
                                web.StartRequest(hashtag="test",enrichir=True),Path(dossier))
                session.update(busy=False,archive_prete=True)
                manager.jobs[session.id]=session
                (session.directory/"publications.json").write_text(
                    '[{"id":"100","url":"https://www.tiktok.com/@test/video/100"}]',
                    encoding="utf-8")
                base=f"/api/jobs/{session.id}/desordre"
                headers={"X-ScrapTikTok":"1"}
                with patch("ticket_gate.verifier_session_active",return_value=True):
                    creation=client.post(base+"/variables",json={"nom":"Symbole État"},headers=headers)
                    self.assertEqual(creation.status_code,200,creation.text)
                    identifiant=creation.json()["variable"]["id"]
                    sauvegarde=client.post(base+"/codages",json={
                        "annotations":[{"variable_id":identifiant,"publication_id":"100","valeur":1}]
                    },headers=headers)
                    self.assertEqual(sauvegarde.status_code,200,sauvegarde.text)
                    renommage=client.post(base+f"/variables/{identifiant}/renommer",
                        json={"nom":"Symbole de l'État"},headers=headers)
                    self.assertEqual(renommage.status_code,200,renommage.text)
                    retour=client.get(base)
                    self.assertEqual(retour.status_code,200,retour.text)
                    donnees=retour.json()["codages_personnalises"]
                    self.assertEqual(donnees["variables"][0],
                        {"id":identifiant,"nom":"Symbole de l'État"})
                    self.assertEqual(donnees["valeurs"][identifiant]["100"],1)
                    csv=client.get(base+"/codages.csv").text
                    self.assertIn("Symbole de l'État",csv)
                    self.assertIn("100",csv)


if __name__=="__main__":
    unittest.main()
