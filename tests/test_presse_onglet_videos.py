"""Collecte Presse : onglet Vidéos du profil, jamais la recherche générale."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
from collecte.comptes import collecter_compte
from collecte.profil_selenium import (
    collecter_grille_profil, ETAT_ONGLET_VIDEOS_JS, LIENS_ONGLET_VIDEOS_JS,
    LIENS_PROFIL_JS,
)
from connect_presse import ConnexionPresse


def lien(numero, type_="video", compte="lemondefr"):
    return f"https://www.tiktok.com/@{compte}/{type_}/{numero}"


class AttendreVueVideos:
    def __init__(self, navigateur, delai, **kw):
        self.navigateur=navigateur
    def until(self, condition):
        for _ in range(5):
            if condition(self.navigateur):
                return True
        raise moteur.TimeoutException()


class PresseVideoTests(unittest.TestCase):
    def test_clic_vidéos_avant_de_lire_la_grille_sans_compter_l_apercu(self):
        bouton=Mock()
        navigateur=Mock()
        navigateur.current_url="https://www.tiktok.com/@lemondefr"
        avant=[lien(i) for i in range(100,106)]
        apres=[lien(i) for i in range(100,112)]
        appels={"vue":0,"scans":0}
        def script(code,*args):
            if code == ETAT_ONGLET_VIDEOS_JS:
                appels["vue"]+=1
                return ({"etat":"selectionne","element":None,"grille":True}
                        if bouton.click.called else
                        {"etat":"a_ouvrir","element":bouton,"grille":True})
            if code == LIENS_ONGLET_VIDEOS_JS:
                appels["scans"]+=1
                self.assertTrue(bouton.click.called)
                self.assertEqual(args,("lemondefr",))
                return apres
            if code == LIENS_PROFIL_JS:
                self.fail("Le mode Presse ne doit pas lire l'aperçu non ciblé.")
            return []
        navigateur.execute_script.side_effect=script
        rapport={"compte_attendu":"lemondefr","hashtag_url":"https://www.tiktok.com/@lemondefr"}
        args=SimpleNamespace(limit=12,timeout=.01,delay=0,max_scrolls=1,
                             idle_rounds=1,interactive=False)
        with patch("collecte.profil_selenium.ObservationProfil") as obs, \
             patch("collecte.profil_selenium.WebDriverWait",AttendreVueVideos), \
             patch.object(moteur,"open_page"), \
             patch.object(moteur,"type_intervention_tiktok",return_value=""), \
             patch.object(moteur,"fermer_invitation_connexion"):
            obs.return_value.lire.return_value=[]
            resultat=collecter_grille_profil(navigateur,args,rapport,
                              interact=Mock(),cibler_onglet_videos=True)
        bouton.click.assert_called_once()
        self.assertGreaterEqual(appels["vue"],2)
        self.assertEqual(appels["scans"],1)
        self.assertEqual(resultat,apres)
        self.assertEqual(rapport["navigation_publications"],"onglet_videos_selectionne")

    def test_onglet_deja_actif_et_photos_exclues(self):
        navigateur=Mock()
        navigateur.current_url="https://www.tiktok.com/@lemondefr"
        urls=[lien(100),lien(101)]
        navigateur.execute_script.side_effect=lambda code,*args: (
            {"etat":"selectionne","element":None,"grille":True}
            if code==ETAT_ONGLET_VIDEOS_JS else
            [*urls,lien(102,"photo"),lien(103,compte="autre")]
            if code==LIENS_ONGLET_VIDEOS_JS else [])
        rapport={"compte_attendu":"lemondefr","hashtag_url":"https://www.tiktok.com/@lemondefr"}
        args=SimpleNamespace(limit=2,timeout=.01,delay=0,max_scrolls=1,
                             idle_rounds=1,interactive=False)
        with patch("collecte.profil_selenium.ObservationProfil") as obs, \
             patch.object(moteur,"open_page"), \
             patch.object(moteur,"type_intervention_tiktok",return_value=""), \
             patch.object(moteur,"fermer_invitation_connexion"):
            obs.return_value.lire.return_value=[]
            resultat=collecter_grille_profil(navigateur,args,rapport,
                         interact=Mock(),cibler_onglet_videos=True)
        self.assertEqual(resultat,urls)

    def test_presse_ne_bascule_pas_vers_la_recherche_video_generale(self):
        args=SimpleNamespace(limit=50)
        urls=[lien(i) for i in range(100,112)]
        with patch("collecte.profil_selenium.collecter_grille_profil",return_value=urls) as grille, \
             patch("collecte.recherche_comptes.collecter_recherche_compte") as recherche:
            rapport={}
            resultat=collecter_compte(
                Mock(),args,"lemondefr",rapport,interact=Mock(),
                presse_videos_uniquement=True,
            )
        self.assertEqual(resultat,urls)
        self.assertEqual(rapport["retenues_par_compte"],{"lemondefr":12})
        self.assertEqual(rapport["recherches_compte"][0]["requete_recherche"],
                         "@lemondefr : onglet Vidéos")
        self.assertEqual(len(rapport["recherches_compte"]),1)
        self.assertTrue(rapport["collecte_partielle"])
        grille.assert_called_once()
        self.assertTrue(grille.call_args.kwargs["cibler_onglet_videos"])
        recherche.assert_not_called()

    def test_connecteur_presse_active_uniquement_le_parcours_videos(self):
        connecteur=object.__new__(ConnexionPresse)
        connecteur.arguments=SimpleNamespace(limit=50)
        connecteur.medias_selectionnes={"lemonde":{"id":"lemonde","compte":"lemondefr"}}
        connecteur.obtenir_navigateur=Mock(return_value=Mock())
        connecteur.options_decouverte=Mock(return_value={"interact":Mock()})
        with patch("collecte.comptes.collecter_compte",return_value=[]) as collecte:
            connecteur.decouvrir({"id":"lemonde","compte":"lemondefr"},{})
        self.assertTrue(collecte.call_args.kwargs["presse_videos_uniquement"])


if __name__=="__main__":
    unittest.main()
