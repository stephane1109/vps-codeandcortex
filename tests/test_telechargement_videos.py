"""Cas simulés : aucune requête TikTok ni création de navigateur."""
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from zipfile import ZipFile

import telechargement_videos as module
from corpus.construction import construire_exports, lignes_engagement
from corpus.export_zip import exporter_zip, archive_avec_texte

IDENTIFIANT = "7694262098129603843"
PUBLICATION = {"id": IDENTIFIANT, "url": f"https://www.tiktok.com/@bfmtv/video/{IDENTIFIANT}",
               "author": "bfmtv", "description": "Un texte @bfmtv", "engagement": {}}
# Signature synthétique : ces tests portent sur le transfert et le rangement, pas le décodage.
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 20


class TestsTelechargementVideos(unittest.TestCase):
    def setUp(self):
        self.temporaire = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporaire.cleanup)
        self.dossier = Path(self.temporaire.name) / "videos"
        self.processus = Mock()
        self.processus.wait.return_value = 0
        self.processus.poll.return_value = 0
        self.commande = None
        self.sortie_ytdlp = b""
        self.cookie_contenu = None
        self.chemin_cookie = None
        def lancer(commande, **options):
            self.commande = commande
            self.processus.stdout = io.BytesIO(self.sortie_ytdlp)
            if "--cookies" in commande:
                self.chemin_cookie = Path(commande[commande.index("--cookies") + 1])
                self.cookie_contenu = self.chemin_cookie.read_text()
                self.assertEqual(self.chemin_cookie.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(self.dossier, self.chemin_cookie.parents)
            Path(commande[commande.index("--output") + 1]).write_bytes(MP4)
            return self.processus
        for cible, options in [
            ("telechargement_videos.find_spec", {"return_value": object()}),
            ("telechargement_videos.shutil.disk_usage", {"return_value": Mock(free=20 * 1024**3)}),
            ("telechargement_videos.subprocess.Popen", {"side_effect": lancer}),
        ]:
            remplacement = patch(cible, **options)
            actif = remplacement.start()
            self.addCleanup(remplacement.stop)
            if cible.endswith("Popen"):
                self.lancer = actif

    def test_mp4_nom_identifiant_et_dedoublonnage(self):
        premier = module.telecharger_video(PUBLICATION, self.dossier)
        second = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(premier["video_statut"], "telecharge")
        self.assertEqual(second["video_statut"], "existant")
        self.assertEqual(premier["video_fichier"], f"videos/id_{IDENTIFIANT}.mp4")
        self.assertEqual((self.dossier / f"id_{IDENTIFIANT}.mp4").read_bytes(), MP4)
        self.lancer.assert_called_once()
        self.assertIn("best[ext=mp4]", self.commande)
        self.assertIn("--ignore-config", self.commande)
        self.assertIn("id = '" + IDENTIFIANT + "'", self.commande)
        self.assertFalse(any("cookie" in v for v in self.commande))

    def test_dependance_absente_sans_echec_du_texte(self):
        with patch.object(module, "find_spec", return_value=None):
            resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "dependance_absente")
        self.assertIsNone(resultat["video_fichier"])
        self.assertEqual(PUBLICATION["description"], "Un texte @bfmtv")
        self.lancer.assert_not_called()

    def test_validation_url_et_diaporama(self):
        for url, statut in [
            ("https://example.org/@bfmtv/video/" + IDENTIFIANT, "url_invalide"),
            ("https://www.tiktok.com/@bfmtv/video/123", "url_invalide"),
            ("https://www.tiktok.com/@bfmtv/photo/" + IDENTIFIANT, "pas_une_video"),
        ]:
            with self.subTest(url=url):
                resultat = module.telecharger_video({**PUBLICATION, "url": url}, self.dossier)
                self.assertEqual(resultat["video_statut"], statut)
                self.assertIsNone(resultat["video_fichier"])
        self.lancer.assert_not_called()

    def test_echec_ne_laisse_aucun_mp4_partiel(self):
        self.processus.wait.return_value = 1
        resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "indisponible")
        self.assertIsNone(resultat["video_fichier"])
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_arret_tue_le_transfert_et_nettoie(self):
        arreter = Mock(side_effect=[False, True])
        self.processus.poll.return_value = None
        resultat = module.telecharger_video(PUBLICATION, self.dossier, arreter=arreter)
        self.assertEqual(resultat["video_statut"], "arrete")
        self.processus.terminate.assert_called_once()
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_limites_de_temps_volume_et_espace(self):
        with patch.object(module.time, "monotonic", side_effect=[0, 121]):
            resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "delai_depasse")
        resultat = module.telecharger_video(PUBLICATION, self.dossier, taille_max_mo=0)
        self.assertEqual(resultat["video_statut"], "taille_depassee")
        with patch.object(module.shutil, "disk_usage", return_value=Mock(free=1)):
            resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "espace_insuffisant")
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_exception_du_telechargeur_isolee(self):
        self.lancer.side_effect = OSError("échec simulé")
        resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "erreur")
        self.assertIsNone(resultat["video_fichier"])

    def test_correspondance_csv_json_zip_et_option_arobase(self):
        dossier = self.dossier.parent
        publication = {**PUBLICATION, **module.telecharger_video(PUBLICATION, self.dossier)}
        contenu = f"*id_{IDENTIFIANT} *profil_@bfmtv\nUn texte @bfmtv\n"
        (dossier / "textes.txt").write_text(contenu)
        construire_exports(dossier, [publication], [], {"parametres": {"telecharger_mp4": True}})
        ligne = lignes_engagement([publication])[0]
        self.assertEqual(ligne["video_id"], IDENTIFIANT)
        self.assertEqual(ligne["video_url"], PUBLICATION["url"])
        self.assertEqual(ligne["video_fichier"], f"videos/id_{IDENTIFIANT}.mp4")
        self.assertEqual(json.loads((dossier / "publications.json").read_text())[0]["video_fichier"], ligne["video_fichier"])
        with (dossier / "videos.csv").open(encoding="utf-8-sig") as flux:
            self.assertEqual(next(csv.DictReader(flux, delimiter=";"))["video_id"], IDENTIFIANT)
        exporter_zip(dossier, dossier / "archive.zip")
        with ZipFile(dossier / "archive.zip") as archive:
            self.assertNotIn(ligne["video_fichier"], archive.namelist())
        exporter_zip(dossier, dossier / "archive.zip", inclure_mp4=True)
        sans_arobase = contenu.replace("*profil_@bfmtv", "*profil_bfmtv").encode()
        with archive_avec_texte(dossier / "archive.zip", sans_arobase) as flux, ZipFile(flux) as archive:
            self.assertEqual(archive.read(ligne["video_fichier"]), MP4)
            self.assertEqual(archive.read("textes.txt"), sans_arobase)
            self.assertEqual(archive.read("corpus_iramuteq.txt"), sans_arobase)

    def test_id_obligatoire_dans_le_txt_seulement_avec_mp4(self):
        try:
            from collecte.service import text_export
        except ModuleNotFoundError as erreur:
            if erreur.name != "collecte.service":
                raise
            from webapp import text_export
        sans_mp4 = text_export([PUBLICATION], False, variables_txt=[])
        avec = {**PUBLICATION, **module.correspondance_video(PUBLICATION)}
        avec_mp4 = text_export([avec], False, variables_txt=[])
        self.assertEqual(sans_mp4, PUBLICATION["description"] + "\n")
        self.assertEqual(avec_mp4, f"*id_{IDENTIFIANT}\n" + sans_mp4)
        selection = text_export([avec], True, variables_txt=["profil", "id"], supprimer_arobase_profil=True)
        self.assertEqual(selection.count("*id_"), 1)
        self.assertIn("*profil_bfmtv", selection)
        self.assertIn("Un texte @bfmtv", selection)


    def test_cookies_techniques_uniquement_et_fichier_detruit(self):
        navigateur = Mock()
        navigateur.current_url = PUBLICATION["url"]
        navigateur.execute_script.return_value = "Mozilla/5.0 Chrome/130.0"
        navigateur.get_cookies.return_value = [
            {"name": "ttwid", "value": "technique", "domain": ".tiktok.com", "path": "/", "secure": True},
            {"name": "sessionid", "value": "secret-compte", "domain": ".tiktok.com"},
            {"name": "sid_tt", "value": "secret-compte", "domain": ".tiktok.com"},
            {"name": "ttwid", "value": "tiers", "domain": ".example.org"},
            {"name": "msToken", "value": "injection\nligne", "domain": ".tiktok.com"},
        ]
        contexte = module.capturer_contexte_anonyme(navigateur)
        self.assertEqual(len(contexte["cookies"]), 1)
        resultat = module.telecharger_video(PUBLICATION, self.dossier, contexte_anonyme=contexte)
        self.assertEqual(resultat["video_statut"], "telecharge")
        self.assertIn("technique", self.cookie_contenu)
        self.assertNotIn("secret-compte", self.cookie_contenu)
        self.assertNotIn("tiers", self.cookie_contenu)
        self.assertFalse(self.chemin_cookie.exists())
        self.assertIn("--user-agent", self.commande)
        self.assertEqual(resultat["video_diagnostic"]["cookies_techniques"], 1)
        self.assertNotIn("technique\t", json.dumps(resultat))
        navigateur.get.assert_not_called()

    def test_contexte_absent_ou_autre_domaine_reste_anonyme(self):
        navigateur = Mock(current_url="https://example.org/")
        self.assertEqual(module.capturer_contexte_anonyme(navigateur), {})
        navigateur.get_cookies.assert_not_called()
        navigateur.current_url = PUBLICATION["url"]
        navigateur.get_cookies.side_effect = RuntimeError("Session perdue")
        self.assertEqual(module.capturer_contexte_anonyme(navigateur), {})

    def test_diagnostic_precis_sans_sortie_brute(self):
        cas = [
            ("ERROR: HTTP Error 403: Forbidden https://cdn.example/file?secret=xyz", "acces_refuse"),
            ("ERROR: HTTP Error 429: Too Many Requests", "requetes_limitees"),
            ("ERROR: TikTok is requiring login for access to this content", "connexion_requise"),
            ("ERROR: Unable to extract challenge data", "verification_requise"),
            ("ERROR: Requested format is not available", "format_absent"),
            ("ERROR: Unable to extract universal data for rehydration", "extraction_impossible"),
            ("ERROR: Impersonation target is not available", "support_navigateur_absent"),
            ("ERROR: no such option: --option", "configuration_invalide"),
            ("ERROR: certificate verify failed", "reseau_indisponible"),
            ("video does not pass filter", "identifiant_rejete"),
        ]
        for texte, attendu in cas:
            with self.subTest(attendu=attendu):
                self.assertEqual(module.diagnostiquer_echec(texte, 1), attendu)
        self.processus.wait.return_value = 1
        self.sortie_ytdlp = cas[0][0].encode()
        resultat = module.telecharger_video(PUBLICATION, self.dossier)
        self.assertEqual(resultat["video_statut"], "acces_refuse")
        self.assertEqual(resultat["video_diagnostic"]["code_sortie"], 1)
        self.assertNotIn("secret=xyz", json.dumps(resultat))
        self.assertEqual(list(self.dossier.iterdir()), [])

    def test_sortie_bornee_et_pas_de_fausse_cause_cookie(self):
        from collections import deque
        morceaux = deque(maxlen=8)
        module.lire_sortie_bornee(io.BytesIO(b"x" * 200000), morceaux)
        self.assertLessEqual(sum(map(len, morceaux)), 32768)
        self.assertEqual(module.diagnostiquer_echec("Use --cookies-from-browser or --cookies", 1), "indisponible")
        self.assertEqual(module.diagnostiquer_echec("", 0), "aucun_fichier")
