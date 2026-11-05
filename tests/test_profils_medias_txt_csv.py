"""Vérifier les destinations indépendantes des métriques de comptes TikTok."""

import ast
import tempfile
import unittest
from pathlib import Path

from collecte.profils_medias import (
    VARIABLES_PROFILS_MEDIAS, LIBELLES_PROFILS_MEDIAS,
    colonnes_profils_medias, enrichir_publications_profils_txt,
    ligne_profil_media,
)
from webapp import StartRequest, Job, entete_publication, text_export


RACINE = Path(__file__).resolve().parents[1]


def creer_fiche():
    """Créer des métriques de compte sans appel réseau."""
    valeurs = {
        "following_count": 98,
        "follower_count": 10001,
        "likes_count": 200000,
        "video_count": 11,
    }
    return ligne_profil_media(
        {"compte": "microbalade", "categorie": None},
        list(VARIABLES_PROFILS_MEDIAS), list(VARIABLES_PROFILS_MEDIAS),
        donnees=valeurs, statut="ok",
        date_collecte="2026-11-05T12:00:00Z")


class TestProfilsMediasTxtCsv(unittest.TestCase):
    def test_huit_lignes_et_seuils_intacts(self):
        """Quatre valeurs réelles et quatre classes gardent leurs intervalles."""
        self.assertEqual(len(VARIABLES_PROFILS_MEDIAS), 4)
        self.assertIn("≥ 1 000", LIBELLES_PROFILS_MEDIAS["following_count"][1])
        self.assertIn("≥ 1 M", LIBELLES_PROFILS_MEDIAS["follower_count"][1])
        self.assertIn("≥ 10 M", LIBELLES_PROFILS_MEDIAS["likes_count"][1])
        self.assertIn("100–999", LIBELLES_PROFILS_MEDIAS["video_count"][1])

    def test_csv_valeur_brute_seule(self):
        """Décocher CSV classe ne supprime pas la valeur brute."""
        colonnes = colonnes_profils_medias(
            ["likes_count"], ["likes_count"],
            csv_bruts=["likes_count"], csv_classes=[])
        self.assertIn("likes_count", colonnes)
        self.assertNotIn("classe_likes_count", colonnes)
        self.assertIn("compte", colonnes)

    def test_csv_classe_seule(self):
        """Décocher la valeur réelle ne désactive pas l'export de la classe."""
        colonnes = colonnes_profils_medias(
            ["likes_count"], ["likes_count"],
            csv_bruts=[], csv_classes=["likes_count"])
        self.assertNotIn("likes_count", colonnes)
        self.assertIn("classe_likes_count", colonnes)

    def test_csv_deux_cases_et_ancienne_collecte(self):
        """Deux cases activées et export historique restent compatibles."""
        explicite = colonnes_profils_medias(
            ["following_count"], ["following_count"],
            csv_bruts=["following_count"], csv_classes=["following_count"])
        ancien = colonnes_profils_medias(
            ["following_count"], ["following_count"])
        self.assertEqual(explicite, ancien)
        self.assertIn("following_count", explicite)
        self.assertIn("classe_following_count", explicite)

    def test_txt_classe_seule_sur_la_publication(self):
        """La classe du compte est liée au bon auteur, sans valeur brute."""
        fiche = creer_fiche()
        self.assertEqual(fiche["nom"], "microbalade")
        publications = [
            {"id": "101", "author": "@microbalade", "description": "Manifestation"},
            {"id": "102", "author": "@autre_compte", "description": "Manifestation"},
        ]
        enrichies = enrichir_publications_profils_txt(
            publications, [fiche], [], ["following_count"])
        header = entete_publication(enrichies[0], ["id"])
        self.assertIn("*profilfollowingclasse_10_99", header)
        self.assertNotIn("*profilfollowing_98", header)
        self.assertNotIn("balises_profils_txt", enrichies[1])
        self.assertNotIn("balises_profils_txt", publications[0])

    def test_txt_brut_et_classe_sans_csv(self):
        """TXT peut contenir deux variables quand CSV n'en contient aucune."""
        enrichies = enrichir_publications_profils_txt(
            [{"id": "101", "author": "microbalade", "description": "Mobilisation"}],
            [creer_fiche()],
            ["following_count"], ["following_count"])
        entete = entete_publication(enrichies[0], ["id"])
        self.assertIn("*profilfollowing_98", entete)
        self.assertIn("*profilfollowingclasse_10_99", entete)
        colonnes = colonnes_profils_medias(
            ["following_count"], ["following_count"],
            csv_bruts=[], csv_classes=[])
        self.assertNotIn("following_count", colonnes)
        self.assertNotIn("classe_following_count", colonnes)

    def test_txt_manquant_reste_indetermine(self):
        """Ne jamais assimiler un refus Research à une mesure égale à zéro."""
        fiche = ligne_profil_media(
            {"compte": "microbalade", "categorie": None},
            ["video_count"], ["video_count"], donnees={},
            statut="acces_refuse")
        texte = enrichir_publications_profils_txt(
            [{"id": "101", "author": "microbalade"}], [fiche],
            ["video_count"], ["video_count"])
        entete = entete_publication(texte[0], ["id"])
        self.assertIn("*profilvideos_indetermine", entete)
        self.assertIn("*profilvideosclasse_indetermine", entete)

    def test_txt_original_et_resume_ia(self):
        """L'annotation de compte figure dans les deux segments textuels."""
        publications = enrichir_publications_profils_txt([{
            "id": "101", "author": "microbalade",
            "description": "Manifestation de lycéens",
            "resume_ia_tiktok": "Mobilisation dans la rue",
            "engagement": {},
        }], [creer_fiche()], ["likes_count"], ["likes_count"])
        texte = text_export(
            publications, include_sources=True,
            variables_txt=["id"], inclure_texte_genere_ia=True)
        self.assertEqual(texte.count("*profillikes_200000"), 2)
        self.assertEqual(
            texte.count("*profillikesclasse_100k_1m"), 2)

    def test_requete_comptes_research_classes_seules_autorisee(self):
        """Les classes seules sont disponibles dans Autres comptes TikTok."""
        requete = StartRequest(
            source_collecte="comptes", comptes=["microbalade"],
            hashtags_saisis=["manifestation"], profil_moteur="research",
            research_client_key="cle_test", research_client_secret="secret_test",
            profils_medias_variables=["video_count"],
            profils_medias_classes=["video_count"],
            profils_medias_txt_bruts=[],
            profils_medias_txt_classes=["video_count"],
            profils_medias_csv_bruts=[],
            profils_medias_csv_classes=["video_count"])
        self.assertEqual(requete.profils_medias_variables, ["video_count"])
        self.assertEqual(requete.profils_medias_txt_bruts, [])
        self.assertEqual(requete.profils_medias_csv_classes, ["video_count"])

    def test_job_utilise_l_inventaire_des_profils_txt(self):
        """L'en-tête du TXT est enrichi après collecte des comptes."""
        requete = StartRequest(
            source_collecte="comptes", comptes=["microbalade"],
            hashtags_saisis=["manifestation"], profil_moteur="research",
            research_client_key="cle_test", research_client_secret="secret_test",
            profils_medias_variables=["following_count"],
            profils_medias_classes=["following_count"],
            profils_medias_txt_bruts=["following_count"],
            profils_medias_txt_classes=["following_count"],
            profils_medias_csv_bruts=[], profils_medias_csv_classes=[],
            variables_txt=["id"])
        with tempfile.TemporaryDirectory() as racine:
            job = Job("a" * 64, requete, Path(racine))
            job.records = [{
                "id": "101", "author": "microbalade",
                "description": "Manifestation", "engagement": {},
            }]
            job.profils_medias = [creer_fiche()]
            texte = job.texte_a_exporter()
            self.assertIn("*profilfollowing_98", texte)
            self.assertIn("*profilfollowingclasse_10_99", texte)

    def test_code_interface_deux_cases_et_texte_en_infobulle(self):
        """Vérifier la grille compacte sur une ligne, dans les trois modes."""
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        serveur = (RACINE / "webapp.py").read_text(encoding="utf-8")
        ast.parse(source)
        ast.parse(serveur)
        self.assertIn('with st.container(key="bloc_metriques_profils"):', source)
        self.assertIn('cle + "txt_brut", cle + "csv_brut"', source)
        self.assertIn('cle + "txt_classe", cle + "csv_classe"', source)
        self.assertIn('aide="Codage proposé : " + intervalles', source)
        self.assertIn('st.session_state.setdefault(', source)
        self.assertIn('job.settings.source_collecte in {"presse", "comptes"}',
                      serveur)
        self.assertIn('source_collecte == "hashtags" and moteur_actif == "research"',
                      serveur)
        self.assertIn('profils_medias_csv_classes=job.settings.profils_medias_csv_classes',
                      serveur)


if __name__ == "__main__":
    unittest.main()
