"""Régressions du chargement différé du résumé TikTok et de son export."""
import argparse
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import scraptiktok as moteur
import webapp as web

URL = "https://www.tiktok.com/@test/video/1234567890"
ORIGINAL = "Une légende authentique #manifestation"
RESUME = "Des participants se rassemblent dans les rues de la ville."
AVIS = "Ceci est un résumé généré par l’IA. Feedback et aide – TikTok"


def instantane(resume=""):
    """Représenter une publication dont la légende est disponible avant la synthèse."""
    return {"url": URL, "payloads": [json.dumps({"id": "1234567890", "desc": ORIGINAL})],
            "titre_page": "TikTok", "blocs_resume_ia": [resume + "\n" + AVIS] if resume else []}


class Horloge:
    """Simuler le délai du navigateur sans ralentir la suite."""
    def __init__(self):
        self.temps = 0.0

    def maintenant(self):
        return self.temps

    def attendre(self, secondes):
        self.temps += secondes


class TestsResumeIA(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js requis pour valider le JavaScript exécuté par Selenium")
    def test_syntaxe_javascript_reelle_du_depliage_et_de_la_lecture(self):
        for script in (moteur.DEPLIER_LEGENDE_JS, moteur.PAGE_JS):
            resultat = subprocess.run([shutil.which("node"), "--check"],
                input="function verifier(){\n" + script + "\n}",
                text=True, capture_output=True, timeout=10)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)

    def test_resume_sans_titre_de_page_et_sans_legende(self):
        self.assertEqual(moteur.extraire_resume_ia_tiktok(instantane(RESUME), ORIGINAL), RESUME)
        self.assertEqual(moteur.extraire_resume_ia_tiktok(instantane(RESUME), ""), RESUME)

    def test_titre_explicite_sans_exporter_avis_technique(self):
        page = {"resume_ia_tiktok": RESUME + "\nⓘ " + AVIS}
        self.assertEqual(moteur.extraire_resume_ia_tiktok(page, ORIGINAL), RESUME)

    def test_ne_pas_attribuer_une_legende_ou_etiquette_createur_a_ia(self):
        for bloc in [ORIGINAL + "\n" + AVIS,
                     ORIGINAL.upper() + "\n" + AVIS,
                     RESUME + "\nLe créateur a indiqué que ce contenu était généré par l’IA",
                     RESUME]:
            with self.subTest(bloc=bloc):
                self.assertEqual(moteur.extraire_resume_ia_tiktok({"blocs_resume_ia": [bloc]}, ORIGINAL), "")

    def test_titre_sur_plusieurs_lignes_et_avis_multilingue(self):
        for avis in [AVIS, "This is an AI-generated summary", "Dies ist eine KI-generierte Zusammenfassung"]:
            page = {"titre_page": "Une synthèse de la manifestation | TikTok",
                    "texte_article_deplie": ORIGINAL + "\nUne synthèse\nde la manifestation\n" + RESUME + "\n" + avis}
            self.assertEqual(moteur.extraire_resume_ia_tiktok(page, ORIGINAL),
                             "Une synthèse\nde la manifestation\n" + RESUME)

    def test_attendre_reessayer_apres_hydratation_puis_exporter(self):
        horloge = Horloge()
        navigateur = Mock()
        clics = []

        def executer(script, identifiant):
            self.assertEqual(identifiant, "1234567890")
            if script == moteur.DEPLIER_LEGENDE_JS:
                clics.append(horloge.temps)
                return True
            # Le premier clic n'a pas d'effet, puis le résumé arrive après le second.
            return instantane(RESUME if horloge.temps >= 5 and len(clics) >= 2 else "")

        navigateur.execute_script.side_effect = executer
        args = argparse.Namespace(timeout=12, interactive=False, inclure_texte_genere_ia=True)
        with patch.object(moteur, "open_page"), patch.object(moteur, "fermer_invitation_connexion"), \
             patch.object(moteur, "captcha_present", return_value=False), \
             patch.object(moteur.time, "monotonic", side_effect=horloge.maintenant), \
             patch.object(moteur.time, "sleep", side_effect=horloge.attendre):
            publication = moteur.read_post(navigateur, URL, args)
        self.assertEqual(publication["description"], ORIGINAL)
        self.assertEqual(publication["resume_ia_tiktok"], RESUME)
        self.assertEqual(publication["statut_resume_ia"], "recupere")
        self.assertGreaterEqual(clics[0], 2)
        self.assertGreaterEqual(len(clics), 2)
        self.assertIn("**** *source_ia", web.text_export([publication], True, inclure_texte_genere_ia=True))
        self.assertIn(RESUME, web.text_export([publication], True, inclure_texte_genere_ia=True))

    def test_delai_ou_erreur_ne_supprime_pas_la_legende_et_bilan_explicite(self):
        for erreur in (False, True):
            horloge = Horloge()
            navigateur = Mock()
            if erreur:
                navigateur.execute_script.side_effect = moteur.WebDriverException("Lecture impossible")
            else:
                navigateur.execute_script.return_value = instantane()
            publication = moteur.extract_record(instantane(), URL)
            with patch.object(moteur.time, "monotonic", side_effect=horloge.maintenant), \
                 patch.object(moteur.time, "sleep", side_effect=horloge.attendre):
                moteur.completer_resume_ia(navigateur, publication, argparse.Namespace(timeout=3), lambda: None)
            self.assertEqual(horloge.temps, 3)
            self.assertEqual(publication["description"], ORIGINAL)
            self.assertEqual(publication["statut_resume_ia"], "erreur_lecture" if erreur else "non_trouve")
            with tempfile.TemporaryDirectory() as dossier:
                tache = web.Job("test", web.StartRequest(hashtag="manifestation", inclure_texte_genere_ia=True), Path(dossier))
                tache.records.append(publication)
                self.assertEqual(tache.snapshot()["bilan_textes_ia"]["recuperes"], 0)
                self.assertNotIn("*source_ia", tache.texte_a_exporter())
                self.assertIn(ORIGINAL, tache.texte_a_exporter())

    def test_case_decochee_ne_declenche_pas_attente_ia(self):
        navigateur = Mock()
        navigateur.execute_script.side_effect = lambda script, *_: False if script == moteur.DEPLIER_LEGENDE_JS else instantane()
        with patch.object(moteur, "open_page"), patch.object(moteur, "fermer_invitation_connexion"), \
             patch.object(moteur, "captcha_present", return_value=False), \
             patch.object(moteur, "completer_resume_ia") as completer:
            publication = moteur.read_post(navigateur, URL, argparse.Namespace(timeout=1, interactive=False))
        completer.assert_not_called()
        self.assertEqual(publication["statut_resume_ia"], "desactive")

    def test_arret_utilisateur_reste_prioritaire(self):
        with self.assertRaises(web.Stopped):
            moteur.completer_resume_ia(Mock(), {}, argparse.Namespace(timeout=12),
                                      Mock(side_effect=web.Stopped))

    def test_api_conserve_metadonnees_et_lit_le_resume_si_coche(self):
        from collecte.presse_research import _fiche
        from connect_presse import ConnexionPresse
        fiche = _fiche({"id": "7000000000000000001", "username": "lemondefr",
                        "video_description": "Manifestation #France", "create_time": 1760000000,
                        "view_count": 0, "like_count": 12, "share_count": 3,
                        "comment_count": 2, "hashtag_names": ["France"]}, "lemondefr")

        def decouvrir(_source, rapport, **_options):
            rapport.update(discovered_urls=[fiche["url"]], metadonnees_api={fiche["id"]: fiche})
            return [fiche["url"]]

        for mode in ("api", "research"):
            for echec in (False, True):
                with self.subTest(mode=mode, echec=echec), tempfile.TemporaryDirectory() as dossier:
                    choix = web.StartRequest(source_collecte="presse", medias=["lemonde"],
                        presse_moteur=mode, inclure_texte_genere_ia=True,
                        research_client_key="test", research_client_secret="test")
                    tache = web.Job("a" * 64, choix, Path(dossier))
                    navigateur = Mock()
                    fabrique = Mock(return_value=navigateur)
                    with patch.object(ConnexionPresse, "decouvrir", side_effect=decouvrir), \
                         patch.object(ConnexionPresse, "lire_publication", return_value={
                             "resume_ia_tiktok": RESUME, "statut_resume_ia": "recupere"},
                             side_effect=moteur.WebDriverException("Erreur") if echec else None) as lire, \
                         patch.object(tache, "pause"):
                        web.execute_job(tache, driver_factory=fabrique)
                    self.assertEqual(len(tache.records), 1, tache.message)
                    lire.assert_called_once_with(fiche["url"])
                    self.assertTrue(fabrique.call_args.args[0].inclure_texte_genere_ia)
                    self.assertEqual(tache.records[0]["description"], fiche["description"])
                    self.assertEqual(tache.records[0]["engagement"], fiche["engagement"])
                    self.assertEqual(tache.snapshot()["bilan_textes_ia"]["recuperes"], 0 if echec else 1)
                    self.assertEqual("*source_ia" in tache.path.read_text(), not echec)

    def test_redirection_autre_publication_ne_fournit_pas_un_resume(self):
        horloge = Horloge()
        page = instantane(RESUME)
        page["url"] = URL.replace("1234567890", "9999999999")
        publication = moteur.extract_record(instantane(), URL)
        with patch.object(moteur.time, "monotonic", side_effect=horloge.maintenant), \
             patch.object(moteur.time, "sleep", side_effect=horloge.attendre):
            moteur.completer_resume_ia(Mock(execute_script=Mock(return_value=page)), publication,
                                      argparse.Namespace(timeout=1), lambda: None)
        self.assertEqual(publication["resume_ia_tiktok"], "")


if __name__ == "__main__":
    unittest.main()
