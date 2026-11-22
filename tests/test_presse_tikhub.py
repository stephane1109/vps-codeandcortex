"""Tests du moteur TikHub, sans requête payante réelle."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from collecte.presse_tikhub import (
    ErreurTikHub, PresseTikHub, _page_publications, _profil_secuid, _resume_ia,
)
from webapp import StartRequest, text_export


IDENTIFIANT = "7701005447410552097"
SECUid = "MS4wLjABAAAAv7iSuuXDJGDvJkmH_vz1qkDZYo1apxgzaxdBSeIuPiM"


def enveloppe(donnees):
    return {"code": 200, "message": "Request successful.", "data": donnees}


def video(identifiant=IDENTIFIANT, compte="lemondefr", secuid=SECUid):
    return {
        "id": identifiant, "desc": "La police réprime violemment les manifestants.",
        "createTime": 1750000000, "video": {"duration": 30},
        "author": {"uniqueId": compte, "secUid": secuid},
        "stats": {"playCount": 250, "diggCount": 18,
                  "commentCount": 0, "shareCount": 3},
    }


class ReponseSimulee:
    status = 200

    def __init__(self, contenu):
        self.contenu = json.dumps(contenu).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, nombre):
        return self.contenu[:nombre]


class TestsTikHub(unittest.TestCase):
    def test_valide_profil_et_refuse_un_autre_compte(self):
        profil = enveloppe({"userInfo": {"user": {
            "uniqueId": "lemondefr", "secUid": SECUid
        }}})
        self.assertEqual(_profil_secuid(profil, "lemondefr"), SECUid)
        with self.assertRaises(ErreurTikHub):
            _profil_secuid(profil, "bfmtv")

    def test_filtre_publications_et_pagination(self):
        page = enveloppe({"itemList": [
            video(), video(compte="bfmtv"),
            video(identifiant="7701005447410552098"),
            {**video(identifiant="7701005447410552099"), "video": None},
        ], "hasMore": True, "cursor": 1720000000000})
        fiches, suite, curseur = _page_publications(page, "lemondefr", SECUid, 15)
        self.assertEqual(len(fiches), 2)
        self.assertTrue(suite)
        self.assertEqual(curseur, 1720000000000)
        self.assertEqual(fiches[IDENTIFIANT]["engagement"]["vues"]["valeur"], 250)
        self.assertEqual(fiches[IDENTIFIANT]["engagement"]["commentaires"]["valeur"], 0)

    def test_resume_natif_uniquement_depuis_itemcustomtdk(self):
        donnees = enveloppe({"itemCustomTDK": {
            "title": "Manifestation", "desc": "Des tensions ont été observées.",
            "keywords": ["manifestation", "police"], "article": "Analyse détaillée."
        }})
        extrait = _resume_ia(donnees)
        self.assertEqual(extrait["resume_ia_tiktok"], "Des tensions ont été observées.")
        self.assertEqual(extrait["article_ia_tiktok"], "Analyse détaillée.")
        self.assertEqual(extrait["mots_cles_ia_tiktok"], ["manifestation", "police"])
        self.assertEqual(extrait["statut_resume_ia"], "recupere")
        vide = _resume_ia(enveloppe({"desc": "Texte du créateur"}))
        self.assertEqual(vide["resume_ia_tiktok"], "")
        self.assertEqual(vide["statut_resume_ia"], "absent")
        self.assertEqual(_resume_ia(enveloppe({"itemCustomTDK": {"article": "Texte long"}}))["resume_ia_tiktok"], "")

    def test_secrets_absents_des_exports_et_cle_obligatoire(self):
        with patch.dict("os.environ", {"TIKHUB_API_KEY": ""}):
            with self.assertRaisesRegex(Exception, "TikHub"):
                StartRequest(source_collecte="presse", presse_moteur="tikhub",
                             medias=["lemonde"])
        settings = StartRequest(source_collecte="presse", presse_moteur="tikhub",
                                medias=["lemonde"], tikhub_api_key="CLE_TEST_PRIVEE")
        self.assertNotIn("CLE_TEST_PRIVEE", str(settings))
        self.assertNotIn("tikhub_api_key", settings.model_dump())
        self.assertEqual(settings.presse_moteur, "tikhub")
        for moteur in ("api", "gallerydl", "navigateur"):
            self.assertEqual(StartRequest(source_collecte="presse",
                             presse_moteur=moteur, medias=["lemonde"]).presse_moteur, moteur)

    def test_pagination_complete_et_resume_seulement_sur_demande(self):
        reponses = [
            enveloppe({"userInfo": {"user": {"uniqueId": "lemondefr", "secUid": SECUid}}}),
            enveloppe({"itemList": [video()], "hasMore": False, "cursor": 0}),
            enveloppe({"itemCustomTDK": {"desc": "Résumé de TikTok.", "title": "Titre"}}),
        ]
        urls = []
        def ouverture(requete, timeout):
            urls.append(requete.full_url)
            self.assertEqual(requete.get_header("Authorization"), "Bearer CLE_TEST_PRIVEE")
            return ReponseSimulee(reponses.pop(0))
        with patch("collecte.presse_tikhub.urlopen", side_effect=ouverture):
            client = PresseTikHub(SimpleNamespace(limit=5), cle="CLE_TEST_PRIVEE")
            rapport = {}
            liens = client.decouvrir("lemondefr", rapport)
            self.assertEqual(len(liens), 1)
            self.assertEqual(len(urls), 2)
            self.assertNotIn("fetch_post_ai_article", " ".join(urls))
            ai = client.lire_resume(liens[0])
            self.assertEqual(ai["resume_ia_tiktok"], "Résumé de TikTok.")
            self.assertEqual(len(urls), 3)
            self.assertIn("itemId=" + IDENTIFIANT, urls[-1])
            self.assertEqual(client.nombre_requetes, 3)
            client.fermer()
            self.assertEqual(client._cle, "")

    def test_export_iramuteq_deux_sources_et_option(self):
        fichier = {**_page_publications(
            enveloppe({"itemList": [video()], "hasMore": False}),
            "lemondefr", SECUid, 1)[0][IDENTIFIANT],
            "resume_ia_tiktok": "Des tensions ont été observées."}
        sans = text_export([fichier], False, variables_txt=["profil"],
                           inclure_texte_genere_ia=False)
        self.assertNotIn("*source_ia", sans)
        avec = text_export([fichier], False, variables_txt=["profil"],
                           inclure_texte_genere_ia=True, themes=["manifestation"])
        self.assertEqual(avec.count("****"), 2)
        self.assertIn("*source_original *theme_manifestation", avec)
        self.assertIn("*source_ia *theme_manifestation", avec)
        self.assertIn("Des tensions ont été observées.", avec)


if __name__ == "__main__":
    unittest.main()
