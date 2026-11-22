"""Tests du filtre positif : uniquement les résumés natifs réellement extraits de TikTok."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import webapp as application
from corpus.publications_csv import ligne_publication_csv


def publication(identifiant, description, *, resume="", statut=None, etiquette=None):
    """Construire une publication factice sans accès au réseau TikTok."""
    return {
        "id": str(identifiant),
        "author": "lemondefr",
        "url": f"https://www.tiktok.com/@lemondefr/video/{identifiant}",
        "description": description,
        "created_at": "2026-10-25T12:00:00+00:00",
        "status": "ok",
        "engagement": {},
        "resume_ia_tiktok": resume,
        "statut_resume_ia": statut,
        "contenu_genere_ia": etiquette,
    }


class TestsFiltreTexteIATikTok(unittest.TestCase):

    def test_option_facultative_et_activation_automatique_lecture(self):
        """Conserver le fonctionnement par défaut et activer la lecture si filtrage."""
        ancien = application.StartRequest(source_collecte="presse", medias=["lemonde"])
        self.assertFalse(ancien.filtrer_texte_ia_tiktok)
        self.assertFalse(ancien.inclure_texte_genere_ia)
        filtre = application.StartRequest(
            source_collecte="presse", medias=["lemonde"],
            filtrer_texte_ia_tiktok=True, inclure_texte_genere_ia=False)
        self.assertTrue(filtre.inclure_texte_genere_ia)
        self.assertTrue(filtre.enrichie)
        hashtags = application.StartRequest(
            source_collecte="hashtags", hashtag="manifestation",
            filtrer_texte_ia_tiktok=True)
        self.assertTrue(hashtags.inclure_texte_genere_ia)
        self.assertTrue(hashtags.enrichie)

    def test_resume_veritable_distinct_et_etiquette_non_suffisante(self):
        """L'étiquette IA et le texte original ne sont pas des preuves de synthèse."""
        vrai = publication(
            7701005447410552001, "Manifestation lycéenne.",
            resume="TikTok rapporte des tensions entre plusieurs groupes de manifestants.",
            statut="recupere")
        self.assertTrue(application.texte_ia_tiktok_exploitable(vrai))
        self.assertFalse(application.texte_ia_tiktok_exploitable(
            publication(7701005447410552002, "Manifestation.",
                        etiquette="etiquete_automatique")))
        self.assertFalse(application.texte_ia_tiktok_exploitable(
            publication(7701005447410552003, "Une manifestation.",
                        resume="Une   manifestation.\n", statut="recupere")))
        self.assertFalse(application.texte_ia_tiktok_exploitable(
            publication(7701005447410552004, "Manifestation.",
                        resume="Un résumé incomplet.", statut="erreur_lecture")))

    def test_collecte_presse_conserve_uniquement_les_publications_ia_et_hashtag(self):
        """Le TXT, les publications archivées et les CSV excluent les posts non retenus."""
        publications = [
            publication(7701005447410552011, "Vidéo #manifestation.",
                        resume="Résumé TikTok distinct explicitement identifié comme IA.",
                        statut="recupere"),
            publication(7701005447410552012, "Autre #manifestation.",
                        etiquette="etiquete_automatique"),
            publication(7701005447410552013, "Encore #manifestation.",
                        resume="Encore #manifestation.", statut="recupere"),
            publication(7701005447410552014, "Analyse #manifestation.",
                        resume="Résumé trouvé malgré une erreur de lecture.",
                        statut="erreur_lecture"),
            publication(7701005447410552015, "Un autre #sujet.",
                        resume="TikTok ajoute un résumé sur un autre sujet.",
                        statut="recupere"),
        ]
        source = {p["url"]: p for p in publications}

        def decouvrir(media, rapport, **options):
            return [item["url"] for item in publications]

        options = application.StartRequest(
            source_collecte="presse", medias=["lemonde"],
            presse_moteur="api", filtrer_texte_ia_tiktok=True,
            croiser_hashtag_presse=True, hashtags_presse=["manifestation"],
            variables_txt=["profil", "id"], french_only=False, limit=10)
        with tempfile.TemporaryDirectory() as dossier:
            travail = application.Job("essai", options, Path(dossier))
            travail.base = None
            with patch("connect_presse.ConnexionPresse.decouvrir",
                       side_effect=decouvrir), patch.object(
                       application.scraper, "read_post",
                       side_effect=lambda navigateur, url, *args, **kwargs:
                       dict(source[url])), patch.object(travail, "pause"):
                application.execute_job(travail, driver_factory=lambda args: Mock())

            self.assertEqual(len(travail.records), 1, travail.message)
            self.assertEqual(len(travail.publications), 1)
            self.assertEqual(travail.exclus_sans_texte_ia, 3)
            self.assertEqual(travail.filtered, 1)
            self.assertEqual(travail.records[0]["id"], publications[0]["id"])
            self.assertTrue(travail.records[0]["retenue"])
            self.assertIn("résumé natif exploitable", travail.message)
            texte = travail.texte_a_exporter()
            self.assertIn("*source_original", texte)
            self.assertIn("*source_ia", texte)
            self.assertIn(publications[0]["resume_ia_tiktok"], texte)
            self.assertNotIn(publications[1]["description"], texte)
            self.assertNotIn(publications[4]["description"], texte)
            colonnes = ligne_publication_csv(travail.publications[0])
            self.assertEqual(colonnes["id"], publications[0]["id"])
            self.assertEqual(colonnes["resume_ia_tiktok"],
                             publications[0]["resume_ia_tiktok"])
            bilan = travail.snapshot()
            self.assertTrue(bilan["filtrer_texte_ia_tiktok"])
            self.assertEqual(bilan["exclus_sans_texte_ia"], 3)
            self.assertEqual(
                len([item for item in travail.journal
                     if item.get("filtre") == "sans_texte_ia_tiktok"]), 3)


if __name__ == "__main__":
    unittest.main()
