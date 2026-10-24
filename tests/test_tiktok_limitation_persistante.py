"""Pause HTTP 429 commune aux sessions ScrapTikTok (volume /app/data)."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from collecte.presse_api import (
    PresseRateLimitError, PresseCooldownError, collecter_videos_presse_api,
)
from collecte.tiktok_limitation import (
    consulter_limitation, enregistrer_limitation, pause_par_defaut,
)


def embed_sans_secuid():
    profil = {"source":{"data":{"/embed/@lemondefr":{
        "userInfo":{"uniqueId":"lemondefr","privateAccount":False},
        "videoList":[{"id":"7000000000000000001"},
                     {"id":"7000000000000000002"}],
    }}}}
    return ('<script id="__FRONTITY_CONNECT_STATE__">'
            +json.dumps(profil)+'</script>').encode()


class TestTemporisation429(unittest.TestCase):
    def test_pause_locale_et_retry_after_sont_distincts_du_quota_officiel(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ,{
            "DATA_DIR":root,"SCRAPTIKTOK_API_429_PAUSE_SECONDS":"3600"
        }):
            self.assertFalse(consulter_limitation(maintenant=1000)["actif"])
            etat=enregistrer_limitation(None,maintenant=1000)
            self.assertEqual(etat["restant_secondes"],3600)
            self.assertEqual(etat["origine"],"pause_locale")
            self.assertFalse(etat["quota_officiel_applicable"])
            encore=enregistrer_limitation(120,maintenant=1010)
            self.assertEqual(encore["jusqua"],4600)  # ne pas écourter
            self.assertEqual(consulter_limitation(maintenant=4601)["actif"],False)
            autre=enregistrer_limitation(120,maintenant=4700)
            self.assertEqual(autre["origine"],"retry_after_tiktok")
            self.assertEqual(autre["restant_secondes"],120)

    def test_429_enregistre_et_bloque_requêtes_suivantes_sans_envoyer_de_requete(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ,{
            "DATA_DIR":root,"SCRAPTIKTOK_API_429_PAUSE_SECONDS":"3600"
        }):
            client=Mock()
            visites=[]
            def reponse(c,url,**options):
                visites.append(url)
                if "/embed/@" in url:
                    return embed_sans_secuid()
                raise PresseRateLimitError(240)
            with patch("collecte.presse_api._client",return_value=client), \
                 patch("collecte.presse_api._obtenir",side_effect=reponse):
                with self.assertRaises(PresseRateLimitError):
                    collecter_videos_presse_api("lemondefr",50,{})
                self.assertEqual(len(visites),2)
                etat=consulter_limitation()
                self.assertTrue(etat["actif"])
                self.assertEqual(etat["origine"],"retry_after_tiktok")
                self.assertTrue(235 <= etat["restant_secondes"] <= 240)
                bilan={}
                with self.assertRaises(PresseCooldownError) as caught:
                    collecter_videos_presse_api("lemondefr",50,bilan)
                self.assertTrue(caught.exception.retry_after > 0)
                self.assertEqual(len(visites),2)
                self.assertEqual(bilan["discovery_stop"],"cooldown_429")
                self.assertEqual(bilan["pages_api"],0)

    def test_dossier_persistant_relit_pendant_une_nouvelle_session(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{"DATA_DIR":root}):
            enregistrer_limitation(200,maintenant=100)
            self.assertTrue(os.path.isfile(os.path.join(root,"tiktok_api_429.json")))
            self.assertEqual(consulter_limitation(maintenant=145)["restant_secondes"],155)


if __name__=="__main__":
    unittest.main()
