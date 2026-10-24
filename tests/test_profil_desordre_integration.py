"""Intégration des grilles paginées et des vidéos sans légende en mode compte/presse."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.comptes import collecter_compte, collecter_profil_public
from analyse_desordre.sources import (
    construire_sources_visuelles, inventaire_sources, lire_publications,
)
from analyse_desordre.service import executer, lire_etat


def liens(compte, premier, dernier):
    return [f"https://www.tiktok.com/@{compte}/video/{numero}"
            for numero in range(premier, dernier)]


class IntegrationProfilsVisuels(unittest.TestCase):
    def test_comptes_et_presse_utilisent_bien_le_module_pagine(self):
        urls=liens("lemondefr",100,112)
        with patch("collecte.profil_selenium.collecter_grille_profil",return_value=urls) as pagine:
            rapport={}
            resultat=collecter_profil_public(
                Mock(),SimpleNamespace(limit=12),"lemondefr",rapport,
                interact=Mock(),check=Mock(),
            )
        self.assertEqual(resultat,urls)
        self.assertEqual(len(resultat),12)
        self.assertEqual(rapport["mode_decouverte"],"profil_direct")
        self.assertEqual(rapport["collecte_partielle"],False)
        pagine.assert_called_once()

    def test_compte_ne_sarrete_pas_aux_six_premieres_vignettes(self):
        urls=liens("lemondefr",100,112)
        with patch("collecte.profil_selenium.collecter_grille_profil",return_value=urls), \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            rapport={}
            resultat=collecter_compte(Mock(),SimpleNamespace(limit=12),"lemondefr",
                rapport,hashtags=[],interact=Mock(),check=Mock())
        self.assertEqual(resultat,urls)
        self.assertEqual(rapport["retenues_par_compte"],{"lemondefr":12})
        recherche.assert_not_called()

    def test_visuels_sans_legendes_separent_le_corpus_texte(self):
        with tempfile.TemporaryDirectory() as d:
            session=Path(d)
            corpus=[{
                "id":"100","url":"https://www.tiktok.com/@lemondefr/video/100",
                "author":"lemondefr","description":"légende existante",
            }]
            (session/"publications.json").write_text(
                json.dumps(corpus),encoding="utf-8"
            )
            urls=[*liens("lemondefr",100,103),
                  "https://www.tiktok.com/@lemondefr/photo/104",
                  "https://www.tiktok.com/@autre/video/105"]
            # Les URL entrantes ont déjà été filtrées par auteur du compte
            # sélectionné, comme dans execute_job ; ici on n'en transmet qu'un.
            visuelles=construire_sources_visuelles(urls[:4],corpus)
            self.assertEqual([p["id"] for p in visuelles],["101","102"])
            self.assertTrue(all(p["retenue"] is False and not p["description"]
                                for p in visuelles))
            (session/"sources_visuelles.json").write_text(
                json.dumps(visuelles),encoding="utf-8"
            )
            resultat=lire_publications(session)
            self.assertEqual([p["id"] for p in resultat],["100","101","102"])
            self.assertEqual(inventaire_sources(session),{
                "publications_collectees":3,
                "mp4_locaux":0,
                "mp4_manquants":3,
                "mp4_telechargeables":3,
            })
            # Pas de réécriture ni enrichissement artificiel du corpus SHS.
            self.assertEqual(json.loads(
                (session/"publications.json").read_text(encoding="utf-8")
            ),corpus)

    def test_collecte_presse_prepare_multimodale_meme_si_une_legende_manque(self):
        """La collecte Presse exporte les métadonnées et les URL utilisables."""
        from webapp import Job, StartRequest, execute_job
        from collecte.presse import charger_inventaire
        from scraptiktok import WebDriverException

        media = charger_inventaire()[0]
        compte = media["compte"]
        urls = liens(compte, 100000, 100002)

        class ConnexionPresseSimulee:
            def __init__(self, *args, **kwargs):
                pass

            def preparer_sources(self, reglages):
                return [{"id": media["id"], "compte": compte}]

            def ouvrir(self):
                return Mock()

            def decouvrir(self, source, rapport, *, contexte="", progression=None):
                rapport.update(discovered_urls=urls, collecte_partielle=False)
                return urls

            def lire_publication(self, url):
                if url == urls[1]:
                    raise WebDriverException("Légende inaccessible")
                return {
                    "id": "100000", "url": urls[0], "author": compte,
                    "description": "Manifestation lycéenne",
                    "engagement": {"likes": {"valeur": 10, "brut": "10"},
                                    "vues": {"valeur": 100, "brut": "100"}},
                }

            def fermer(self):
                pass

        with tempfile.TemporaryDirectory() as d:
            job = Job("a" * 64, StartRequest(
                source_collecte="presse", medias=[media["id"]], limit=2,
            ), Path(d))
            with (
                patch("connect_presse.ConnexionPresse", ConnexionPresseSimulee),
                patch.object(job, "pause", return_value=None),
            ):
                execute_job(job)
            self.assertTrue(job.archive_prete, job.message)
            self.assertTrue((job.directory / "archive.zip").is_file())
            self.assertEqual(len(json.loads(
                (job.directory / "publications.json").read_text())), 1)
            donnees = lire_publications(job.directory)
            self.assertEqual({p["id"] for p in donnees}, {"100000", "100001"})
            self.assertEqual(inventaire_sources(job.directory), {
                "publications_collectees": 2,
                "mp4_locaux": 0, "mp4_manquants": 2,
                "mp4_telechargeables": 2,
            })
            self.assertEqual(donnees[0]["engagement"]["likes"]["valeur"], 10)
            self.assertEqual(donnees[1]["engagement"], {})

    def test_sources_presse_sans_fichier_publications_restent_exploitables(self):
        with tempfile.TemporaryDirectory() as d:
            session = Path(d)
            urls = liens("lemondefr", 200000, 200002)
            sources = construire_sources_visuelles(urls, [])
            (session / "sources_visuelles.json").write_text(
                json.dumps(sources), encoding="utf-8",
            )
            self.assertEqual([p["id"] for p in lire_publications(session)],
                             ["200000", "200001"])
            self.assertEqual(inventaire_sources(session)["mp4_telechargeables"], 2)

    def test_desordre_analyse_les_mp4_sans_legende(self):
        with tempfile.TemporaryDirectory() as d:
            session=Path(d)
            corpus=[{"id":"100","url":"https://www.tiktok.com/@lemondefr/video/100",
                     "author":"lemondefr","description":"légende"}]
            complement=construire_sources_visuelles(
                liens("lemondefr",101,103),corpus
            )
            (session/"publications.json").write_text(json.dumps(corpus))
            (session/"sources_visuelles.json").write_text(json.dumps(complement))
            (session/"videos").mkdir()
            (session/"videos"/"100.mp4").write_bytes(b"video")
            analysees=[]

            def telecharger(publication,cible,limites):
                cible.mkdir(exist_ok=True)
                chemin=cible/(publication["id"]+".mp4")
                chemin.write_bytes(b"video")
                return chemin

            def analyser(dossier,metadonnees,sortie,options,progression):
                source=json.loads(Path(metadonnees).read_text(encoding="utf-8"))
                analysees.extend(source)
                self.assertEqual({p.name for p in Path(dossier).glob("*.mp4")},
                                 {"100.mp4","101.mp4","102.mp4"})
                return {"statuts":{"mesure":3}}

            # Tester l'orchestration sans importer OpenCV / les modèles visuels.
            module_moteur=SimpleNamespace(analyser_lot=analyser)
            with patch("collecte.telechargement.telecharger_video",side_effect=telecharger), \
                 patch.dict("sys.modules",{"analyse_desordre.lancement":module_moteur}):
                executer(session,"desordre_0123456789abcdef",10,320,10,True)
            self.assertEqual([p["id"] for p in analysees],["100","101","102"])
            self.assertEqual(lire_etat(session)["statut"],"termine")
            self.assertEqual(json.loads((session/"publications.json").read_text()),corpus)


if __name__=="__main__":
    unittest.main()
