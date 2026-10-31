"""Parcours séparés, navigateur unique et CAPTCHA partagé, sans accès à TikTok."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import scraptiktok as moteur
import webapp as service
from connect_htag import ConnexionHashtag
from connect_presse import ConnexionPresse
from connect_profil import ConnexionProfil


class ConnexionsModes(unittest.TestCase):
    def connexion(self, classe):
        navigateur, interaction = Mock(), Mock()
        fabrique = Mock(return_value=navigateur)
        connexion = classe(SimpleNamespace(limit=20), fabrique=fabrique, interaction=interaction)
        return connexion, navigateur, fabrique, interaction

    def test_hashtags_gardent_leurs_pages_et_partagent_la_validation(self):
        connexion, navigateur, fabrique, interaction = self.connexion(ConnexionHashtag)
        sources = connexion.preparer_sources(SimpleNamespace(hashtags=["#manifestation", "lycéen"]))
        fabrique.assert_not_called()
        connexion.ouvrir()
        connexion.ouvrir()
        validations, adresses = [], []

        def decouvrir(pilote, arguments, rapport, **options):
            self.assertIs(pilote, navigateur)
            self.assertTrue(options["sans_connexion"])
            validations.append(options["validation_initiale"])
            adresses.append(rapport["hashtag_url"])
            if options["validation_initiale"]:
                options["interact"]("CAPTCHA initial")
            else:
                # La validation initiale ne doit pas masquer un CAPTCHA ultérieur.
                options["interact"]("Nouveau CAPTCHA")
            return []

        try:
            with patch("collecte.hashtags.collecter_hashtag", side_effect=decouvrir):
                for source in sources:
                    rapport = {}
                    connexion.decouvrir(source, rapport, contexte="#" + source["hashtag"])
                    self.assertEqual(rapport["connexion"]["module"], "connect_htag")
            with patch.object(moteur, "read_post", return_value={}) as lire:
                connexion.lire_publication("https://www.tiktok.com/@exemple/video/123")
                self.assertIs(lire.call_args.args[0], navigateur)
                self.assertTrue(lire.call_args.kwargs["sans_connexion"])
        finally:
            connexion.fermer()
        self.assertEqual(validations, [True, False])
        self.assertEqual(adresses, ["https://www.tiktok.com/tag/manifestation", "https://www.tiktok.com/tag/lyc%C3%A9en"])
        self.assertEqual(interaction.call_count, 2)
        self.assertTrue(all(appel.args[0] is navigateur for appel in interaction.call_args_list))
        fabrique.assert_called_once()
        navigateur.quit.assert_called_once()

    def test_presse_et_profils_emploient_uniquement_leur_selection(self):
        parametres = SimpleNamespace(hashtags=["manifestation", "lycéen"],
            medias=["lemonde", "franceinfo"], comptes=["@BRUTOFFICIEL", "@brutofficiel"])
        for classe, attendus in [(ConnexionPresse, ["lemondefr", "franceinfo"]),
                                 (ConnexionProfil, ["brutofficiel"])]:
            with self.subTest(mode=classe.mode):
                connexion, navigateur, fabrique, interaction = self.connexion(classe)
                sources = connexion.preparer_sources(parametres)
                self.assertEqual([source["compte"] for source in sources], attendus)
                connexion.ouvrir()
                validations = []

                def decouvrir(pilote, arguments, compte, rapport, **options):
                    self.assertIs(pilote, navigateur)
                    self.assertIn(compte, attendus)
                    # En Presse, aucun filtre de hashtag n'est appliqué sans
                    # activer le croisement spécifique de l'interface.
                    self.assertEqual(options["hashtags"],
                                     () if classe.mode == "presse"
                                     else parametres.hashtags)
                    self.assertTrue(options["sans_connexion"])
                    self.assertEqual(rapport["connexion"]["module"], classe.__module__)
                    validations.append(options["validation_initiale"])
                    if options["validation_initiale"]:
                        options["interact"]("Vérifiez le CAPTCHA.")
                    return []

                try:
                    with patch("collecte.comptes.collecter_compte", side_effect=decouvrir) as collecte:
                        for source in sources:
                            connexion.decouvrir(source, {})
                        self.assertEqual([appel.args[2] for appel in collecte.call_args_list], attendus)
                        nombre_appels = collecte.call_count
                        with self.assertRaises(ValueError):
                            connexion.decouvrir({**sources[0], "compte": "autrecompte"}, {})
                        self.assertEqual(collecte.call_count, nombre_appels)
                finally:
                    connexion.fermer()
                self.assertEqual(validations, [True] + [False] * (len(attendus) - 1))
                interaction.assert_called_once()
                fabrique.assert_called_once()
                navigateur.quit.assert_called_once()

    def test_aucun_mode_ne_peut_rouvrir_une_session_detruite(self):
        for classe in (ConnexionHashtag, ConnexionPresse, ConnexionProfil):
            with self.subTest(mode=classe.mode):
                connexion, navigateur, fabrique, _ = self.connexion(classe)
                connexion.ouvrir()
                connexion.fermer()
                connexion.fermer()
                with self.assertRaises(RuntimeError):
                    connexion.ouvrir()
                with self.assertRaises(RuntimeError):
                    connexion.lire_publication("https://www.tiktok.com/@exemple/video/123")
                navigateur.quit.assert_called_once()
                fabrique.assert_called_once()

    def test_service_choisit_le_module_du_mode_et_ferme_apres_echec(self):
        cas = [("hashtags", {}, "connect_htag.ConnexionHashtag"),
               ("presse", {"medias": ["lemonde"]}, "connect_presse.ConnexionPresse"),
               ("comptes", {"comptes": ["lemondefr"]}, "connect_profil.ConnexionProfil")]
        for mode, selection, cible in cas:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as dossier:
                job = service.Job("test", service.StartRequest(
                    source_collecte=mode, hashtag="manifestation", **selection), Path(dossier))
                navigateur = Mock()
                fabrique = Mock(return_value=navigateur)
                with patch(cible + ".decouvrir", side_effect=RuntimeError("Source inaccessible")) as decouvrir:
                    service.execute_job(job, driver_factory=fabrique)
                decouvrir.assert_called_once()
                self.assertEqual(job.status, "failed")
                self.assertFalse(job.busy)
                fabrique.assert_called_once()
                navigateur.quit.assert_called_once()

    def test_arret_avant_ouverture_ne_cree_pas_de_navigateur(self):
        with tempfile.TemporaryDirectory() as dossier:
            job = service.Job("test", service.StartRequest(hashtag="manifestation"), Path(dossier))
            fabrique = Mock()
            with patch.object(job, "check", side_effect=service.Stopped):
                service.execute_job(job, driver_factory=fabrique)
            fabrique.assert_not_called()
            self.assertEqual(job.status, "stopped")


if __name__ == "__main__":
    unittest.main()
