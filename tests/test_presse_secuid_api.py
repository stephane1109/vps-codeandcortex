"""Tests sans accès TikTok : identité secUid, pagination multi-pages et repli Chrome."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from collecte.presse_api import (
    PresseApiError, extraire_identite_embed, extraire_identite_video_embed,
    extraire_page_createur, collecter_videos_presse_api,
)
from collecte.comptes import collecter_compte


COMPTE = "lemondefr"
SECUID = "MS4wLjABAAAAThisIsATestSecUid01234567890"


def embed(compte=COMPTE, auteur=COMPTE):
    etat = {"source":{"data":{f"/embed/@{compte}":{
        "userInfo":{"uniqueId":auteur,"secUid":SECUID,"privateAccount":False}
    }}}}
    return ('<script id="__FRONTITY_CONNECT_STATE__">'
            + json.dumps(etat) + '</script>').encode()


def embed_sans_secuid(identifiants=("7000000000000000001", "7000000000000000002"),
                     compte=COMPTE):
    etat={"source":{"data":{f"/embed/@{compte}":{
        "userInfo":{"uniqueId":compte,"id":"1234567890123456789",
                    "privateAccount":False},
        "videoList":[{"id":identifiant} for identifiant in identifiants],
    }}}}
    return ('<script id="__FRONTITY_CONNECT_STATE__">'
            +json.dumps(etat)+'</script>').encode()


def embed_video(identifiant="7000000000000000001", auteur=COMPTE,
                secuid=SECUID):
    donnees={"source":{"data":{f"/embed/v2/{identifiant}":{
        "videoData":{
            "itemInfos":{"id":identifiant,"text":"Publication sans contrainte de légende"},
            "authorInfos":{"uniqueId":auteur,"id":"1234567890123456789",
                           "secUid":secuid},
        }
    }}}}
    return ('<script id="__FRONTITY_CONNECT_STATE__">'
            +json.dumps(donnees)+'</script>').encode()


def item(i, auteur=COMPTE, secuid=SECUID):
    return {
        "id": str(7000000000000000000 + i),
        "author": {"uniqueId": auteur, "secUid": secuid},
        "video": {"id": str(i)},
        "createTime": 1770000000 - i,
    }


class Reponse:
    def __init__(self, contenu):
        self.contenu=contenu
    def read(self, size):
        return self.contenu[:size]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class Client:
    def __init__(self,pages,embed_content=None,video_embeds=None):
        self.pages=pages
        self.embed_content=embed_content if embed_content is not None else embed()
        self.video_embeds=video_embeds or {}
        self.vues=[]
    def open(self,request,timeout=20):
        url=request.full_url
        self.vues.append(url)
        if "/embed/@" in url:
            return Reponse(self.embed_content)
        if "/embed/v2/" in url:
            identifiant=url.rstrip("/").split("/")[-1]
            if identifiant not in self.video_embeds:
                raise AssertionError("Embed vidéo non prévu : "+identifiant)
            return Reponse(self.video_embeds[identifiant])
        if "/api/creator/item_list/" in url:
            numero=sum("/api/creator/item_list/" in x for x in self.vues)
            return Reponse(json.dumps(self.pages[min(numero - 1,len(self.pages) - 1)]).encode())
        raise AssertionError("Host inattendu " + url)


class PresseSecUidTests(unittest.TestCase):
    def test_identite_du_media_provient_de_embed_et_non_d_un_selecteur_videos(self):
        self.assertEqual(extraire_identite_embed(embed(),COMPTE),SECUID)
        with self.assertRaisesRegex(PresseApiError,"autre média"):
            extraire_identite_embed(embed(auteur="autremedia"),COMPTE)
        with self.assertRaisesRegex(PresseApiError,"données de profil"):
            extraire_identite_embed(b"<html>6 videos</html>",COMPTE)

    def test_secuid_absent_du_profil_recupere_dans_embed_video_du_meme_media(self):
        identifiant="7000000000000000001"
        client=Client([{"statusCode":0,"itemList":[item(1)],
                        "hasMorePrevious":False}],
            embed_content=embed_sans_secuid(),
            video_embeds={identifiant:embed_video(identifiant)})
        rapport={}
        urls=collecter_videos_presse_api(COMPTE,50,rapport,
            client=client,pause=lambda _:None)
        self.assertEqual(urls,[f"https://www.tiktok.com/@{COMPTE}/video/{identifiant}"])
        self.assertEqual(rapport["source_secuid"],"embed_video")
        self.assertTrue(rapport["secuid_resolu"])
        self.assertEqual(rapport["tentatives_embed_video"],1)
        self.assertEqual(rapport["videos_amorcage_disponibles"],2)
        self.assertEqual(rapport["pages_api"],1)
        self.assertEqual(
            [url.split("?")[0] for url in client.vues],
            [f"https://www.tiktok.com/embed/@{COMPTE}",
             f"https://www.tiktok.com/embed/v2/{identifiant}",
             "https://www.tiktok.com/api/creator/item_list/"])

    def test_un_embed_video_d_un_autre_media_est_refuse_et_suivant_essaye(self):
        premier="7000000000000000001"
        second="7000000000000000002"
        client=Client([{"statusCode":0,"itemList":[item(2)],
                        "hasMorePrevious":False}],
            embed_content=embed_sans_secuid(),
            video_embeds={
                premier:embed_video(premier,auteur="autremedia"),
                second:embed_video(second),
            })
        rapport={}
        liens=collecter_videos_presse_api(COMPTE,50,rapport,
            client=client,pause=lambda _:None)
        self.assertEqual(len(liens),1)
        self.assertEqual(rapport["source_secuid"],"embed_video")
        self.assertEqual(rapport["tentatives_embed_video"],2)

    def test_l_embed_video_mauvais_auteur_ou_mauvais_id_n_est_pas_accepte(self):
        with self.assertRaisesRegex(PresseApiError,"autre média"):
            extraire_identite_video_embed(
                embed_video(auteur="autremedia"),COMPTE,"7000000000000000001")
        identifiant="7000000000000000001"
        contenu=embed_video(identifiant).decode()
        prefixe,texte=contenu.split(">",1)
        document=json.loads(texte.split("</script>",1)[0])
        document["source"]["data"][f"/embed/v2/{identifiant}"]["videoData"]["itemInfos"]["id"]="7000000000000000002"
        faux=(prefixe+">"+json.dumps(document)+"</script>").encode()
        with self.assertRaisesRegex(PresseApiError,"ne correspond"):
            extraire_identite_video_embed(faux,COMPTE,identifiant)

    def test_aucun_secuid_et_aucune_video_amorcage_donne_une_cause_precise(self):
        client=Client([],embed_content=embed_sans_secuid(identifiants=()))
        with self.assertRaisesRegex(PresseApiError,"ni de vidéo récente"):
            collecter_videos_presse_api(COMPTE,50,{},
                client=client,pause=lambda _:None)
        self.assertEqual(len(client.vues),1)

    def test_collecte_50_videos_en_quatre_pages_de_15(self):
        pages=[]
        for debut in (0,15,30,45):
            pages.append({
                "statusCode":0,
                "itemList":[item(i) for i in range(debut,debut+15)],
                "hasMorePrevious":debut<45,
            })
        client=Client(pages)
        rapport={}
        progression=[]
        urls=collecter_videos_presse_api(COMPTE,50,rapport,
            progress=progression.append,client=client,
            clock=lambda:1780000000,pause=lambda _:None)
        self.assertEqual(len(urls),50)
        self.assertEqual(len(set(urls)),50)
        self.assertEqual(rapport["pages_api"],4)
        self.assertEqual(rapport["discovery_stop"],"limit")
        self.assertEqual(progression,[15,30,45,50])
        self.assertTrue(all("/api/creator/item_list/" in x
            for x in client.vues[1:]))
        self.assertEqual(rapport["navigation_publications"],"api_liste_createur")

    def test_rejet_des_videos_autres_auteurs_et_du_contenu_photo(self):
        photo=item(10)
        photo.pop("video")
        photo["imagePost"]={"images":[{}]}
        donnees={"statusCode":0,"itemList":[
            item(1),item(2,auteur="autre"),item(3,secuid="WrongSecUid01234567890"),
            photo,
        ],"hasMorePrevious":False}
        res=extraire_page_createur(donnees,COMPTE,SECUID)
        self.assertEqual(res["urls"],[
            f"https://www.tiktok.com/@{COMPTE}/video/7000000000000000001"
        ])
        self.assertFalse(res["suite"])
        self.assertEqual(res["nombre_brut"],4)

    def test_paginer_sans_legende_ni_champ_video_titre(self):
        client=Client([{
            "statusCode":0,
            "itemList":[item(10),item(11)],
            "hasMorePrevious":False,
        }])
        rapport={}
        urls=collecter_videos_presse_api(COMPTE,50,rapport,
            client=client,pause=lambda _:None)
        self.assertEqual(len(urls),2)
        self.assertEqual(rapport["discovery_stop"],"fin_signalee_par_tiktok")
        self.assertTrue(rapport["collecte_partielle"])

    def test_presse_privilegie_api_et_n_appelle_pas_chrome_pour_50_videos(self):
        urls=[f"https://www.tiktok.com/@lemondefr/video/{7000000000000000000+i}"
              for i in range(50)]
        rapport={}
        with patch("collecte.presse_api.collecter_videos_presse_api",
                   side_effect=lambda compte,limite,etat,**kw: (
                       etat.update(discovered_urls=urls,
                                   candidats_examines=50,discovery_stop="limit")
                       or urls)), \
             patch("collecte.profil_selenium.collecter_grille_profil") as grille, \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            resultat=collecter_compte(Mock(),SimpleNamespace(limit=50),
                            COMPTE,rapport,presse_videos_uniquement=True,
                            presse_moteur="api")
        self.assertEqual(resultat,urls)
        grille.assert_not_called()
        recherche.assert_not_called()
        self.assertEqual(rapport["retenues_par_compte"],{COMPTE:50})

    def test_presse_ne_lance_pas_navigateur_apres_echec_api(self):
        urls=[f"https://www.tiktok.com/@lemondefr/video/{7000000000000000000+i}"
              for i in range(6)]
        rapport={}
        with patch("collecte.presse_api.collecter_videos_presse_api",
                   side_effect=PresseApiError("TikTok HTTP 403")), \
             patch("collecte.profil_selenium.collecter_grille_profil",return_value=urls), \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            with self.assertRaisesRegex(PresseApiError,"TikTok HTTP 403"):
                collecter_compte(Mock(),SimpleNamespace(limit=50),
                                COMPTE,rapport,presse_videos_uniquement=True,
                                presse_moteur="api")
        self.assertEqual(rapport["recherches_compte"][0]["echec"],"PresseApiError")
        self.assertEqual(rapport["recherches_compte"][0]["diagnostic"]["code"],
                         "acces_tiktok_indisponible")
        self.assertEqual(len(rapport["recherches_compte"]),1)
        recherche.assert_not_called()
        # Ne pas masquer l'échec de l'API derrière une autre méthode.
        grille.assert_not_called()


if __name__=="__main__":
    unittest.main()
